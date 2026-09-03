import {
  ArnFormat,
  CfnOutput,
  Duration,
  RemovalPolicy,
  Stack,
  StackProps,
  aws_ec2 as ec2,
  aws_ecr as ecr,
  aws_ecs as ecs,
  aws_iam as iam,
  aws_lambda as lambda,
  aws_logs as logs,
  aws_rds as rds,
  aws_s3 as s3,
  aws_s3_notifications as s3notifications,
  aws_scheduler as scheduler,
  aws_secretsmanager as secretsmanager,
  aws_sqs as sqs,
  aws_stepfunctions as sfn,
  aws_stepfunctions_tasks as tasks,
} from "aws-cdk-lib";
import { Construct } from "constructs";
import { join } from "node:path";

import { DeploymentConfiguration } from "./configuration";

export interface FoundationStackProps extends StackProps {
  readonly config: DeploymentConfiguration;
}

export class FoundationStack extends Stack {
  readonly vpc: ec2.Vpc;
  readonly repository: ecr.Repository;
  readonly cluster: ecs.Cluster;
  readonly database: rds.DatabaseInstance;
  readonly ingestionQueue: sqs.Queue;
  readonly deadLetterQueue: sqs.Queue;
  readonly evidenceValidator: lambda.Function;
  readonly dataSecurityGroup: ec2.SecurityGroup;
  readonly applicationSecret: secretsmanager.Secret;
  readonly artifactBucket: s3.Bucket;
  readonly logGroups: Record<string, logs.LogGroup>;

  constructor(scope: Construct, id: string, props: FoundationStackProps) {
    super(scope, id, props);

    const { projectName, stage, logRetentionDays } = props.config;
    const prefix = `${projectName}-${stage}`;

    this.vpc = new ec2.Vpc(this, "Vpc", {
      vpcName: `${prefix}-vpc`,
      maxAzs: 2,
      natGateways: 0,
      subnetConfiguration: [
        {
          name: "runtime",
          subnetType: ec2.SubnetType.PUBLIC,
          cidrMask: 24,
        },
        {
          name: "data",
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
          cidrMask: 24,
        },
      ],
    });

    this.dataSecurityGroup = new ec2.SecurityGroup(this, "DataSecurityGroup", {
      vpc: this.vpc,
      securityGroupName: `${prefix}-data`,
      description: "PostgreSQL access from ECS runtime only",
      allowAllOutbound: false,
    });

    this.database = new rds.DatabaseInstance(this, "Database", {
      databaseName: "supportcopilot",
      engine: rds.DatabaseInstanceEngine.postgres({
        version: rds.PostgresEngineVersion.VER_16_13,
      }),
      credentials: rds.Credentials.fromGeneratedSecret("supportcopilot"),
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.T4G, ec2.InstanceSize.MICRO),
      allocatedStorage: 20,
      storageType: rds.StorageType.GP3,
      storageEncrypted: true,
      multiAz: false,
      publiclyAccessible: false,
      deletionProtection: false,
      deleteAutomatedBackups: true,
      backupRetention: Duration.days(1),
      vpc: this.vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      securityGroups: [this.dataSecurityGroup],
      removalPolicy: RemovalPolicy.DESTROY,
    });

    this.deadLetterQueue = new sqs.Queue(this, "IngestionDeadLetterQueue", {
      queueName: `${prefix}-ingestion-dlq`,
      encryption: sqs.QueueEncryption.SQS_MANAGED,
      enforceSSL: true,
      retentionPeriod: Duration.days(1),
      removalPolicy: RemovalPolicy.DESTROY,
    });
    this.ingestionQueue = new sqs.Queue(this, "IngestionQueue", {
      queueName: `${prefix}-ingestion`,
      encryption: sqs.QueueEncryption.SQS_MANAGED,
      enforceSSL: true,
      retentionPeriod: Duration.days(1),
      visibilityTimeout: Duration.seconds(180),
      receiveMessageWaitTime: Duration.seconds(20),
      deadLetterQueue: {
        queue: this.deadLetterQueue,
        maxReceiveCount: 5,
      },
      removalPolicy: RemovalPolicy.DESTROY,
    });

    this.repository = new ecr.Repository(this, "BackendRepository", {
      repositoryName: `${prefix}-backend`,
      imageScanOnPush: true,
      imageTagMutability: ecr.TagMutability.IMMUTABLE,
      emptyOnDelete: true,
      removalPolicy: RemovalPolicy.DESTROY,
      lifecycleRules: [{ maxImageCount: 5 }],
    });

    this.cluster = new ecs.Cluster(this, "Cluster", {
      clusterName: `${prefix}-cluster`,
      vpc: this.vpc,
      containerInsightsV2: ecs.ContainerInsights.DISABLED,
    });

    this.artifactBucket = new s3.Bucket(this, "ArtifactBucket", {
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      versioned: true,
      autoDeleteObjects: true,
      removalPolicy: RemovalPolicy.DESTROY,
      lifecycleRules: [{ expiration: Duration.days(14) }],
    });

    const evidenceValidatorLogGroup = new logs.LogGroup(this, "EvidenceValidatorLogGroup", {
      logGroupName: `/aws/lambda/${prefix}-evidence-validator`,
      retention: retention(logRetentionDays),
      removalPolicy: RemovalPolicy.DESTROY,
    });
    this.evidenceValidator = new lambda.Function(this, "EvidenceValidator", {
      functionName: `${prefix}-evidence-validator`,
      runtime: lambda.Runtime.PYTHON_3_12,
      architecture: lambda.Architecture.ARM_64,
      handler: "handler.handle",
      code: lambda.Code.fromAsset(join(__dirname, "..", "lambda")),
      timeout: Duration.seconds(30),
      memorySize: 128,
      logGroup: evidenceValidatorLogGroup,
      environment: {
        OUTPUT_PREFIX: "validation-output/",
        MAX_SOURCE_BYTES: "1048576",
        QUEUE_URL: this.ingestionQueue.queueUrl,
        QUEUE_NAME: this.ingestionQueue.queueName,
      },
    });
    this.evidenceValidator.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["s3:GetObject"],
        resources: [this.artifactBucket.arnForObjects("validation-input/*")],
      }),
    );
    this.evidenceValidator.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["s3:PutObject"],
        resources: [this.artifactBucket.arnForObjects("validation-output/*")],
      }),
    );
    this.ingestionQueue.grantSendMessages(this.evidenceValidator);
    this.artifactBucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3notifications.LambdaDestination(this.evidenceValidator),
      { prefix: "validation-input/" },
    );

    this.applicationSecret = new secretsmanager.Secret(this, "ApplicationSecret", {
      secretName: `${prefix}/application`,
      description: "Runtime credentials populated outside CloudFormation before service deploy",
      generateSecretString: {
        secretStringTemplate: JSON.stringify({
          SUPPORT_COPILOT_CLERK_SECRET_KEY: "replace_before_runtime_deploy",
          SUPPORT_COPILOT_CLERK_JWT_KEY: "replace_before_runtime_deploy",
          SUPPORT_COPILOT_OPENAI_API_KEY: "replace_before_runtime_deploy",
          SUPPORT_COPILOT_GOOGLE_OAUTH_CLIENT_ID: "replace_before_runtime_deploy",
          SUPPORT_COPILOT_GOOGLE_OAUTH_CLIENT_SECRET: "replace_before_runtime_deploy",
          SUPPORT_COPILOT_CREDENTIAL_VAULT_KEY: "replace_before_runtime_deploy",
          SUPPORT_COPILOT_INBOX_SCHEDULER_SECRET: "replace_before_runtime_deploy",
          SUPPORT_COPILOT_POLICY_INDEX_SCHEDULER_SECRET: "replace_before_runtime_deploy",
        }),
        generateStringKey: "BOOTSTRAP_NONCE",
        excludePunctuation: true,
        passwordLength: 32,
      },
      removalPolicy: RemovalPolicy.DESTROY,
    });

    this.logGroups = Object.fromEntries(
      ["api", "worker", "scheduler", "migration"].map((service) => [
        service,
        new logs.LogGroup(this, `${service}LogGroup`, {
          logGroupName: `/ecs/${prefix}/${service}`,
          retention: retention(logRetentionDays),
          removalPolicy: RemovalPolicy.DESTROY,
        }),
      ]),
    );

    this.createAutoDestroyWatchdog(props.config.autoDestroyAt);

    new CfnOutput(this, "RepositoryUri", { value: this.repository.repositoryUri });
    new CfnOutput(this, "ApplicationSecretName", {
      value: this.applicationSecret.secretName,
    });
    new CfnOutput(this, "ArtifactBucketName", { value: this.artifactBucket.bucketName });
    new CfnOutput(this, "IngestionQueueName", { value: this.ingestionQueue.queueName });
    new CfnOutput(this, "IngestionQueueUrl", { value: this.ingestionQueue.queueUrl });
    new CfnOutput(this, "IngestionDeadLetterQueueUrl", {
      value: this.deadLetterQueue.queueUrl,
    });
    new CfnOutput(this, "EvidenceValidatorName", {
      value: this.evidenceValidator.functionName,
    });
    new CfnOutput(this, "EvidenceValidatorLogGroupName", {
      value: evidenceValidatorLogGroup.logGroupName,
    });
    new CfnOutput(this, "WorkerLogGroupName", {
      value: this.logGroups.worker.logGroupName,
    });
    new CfnOutput(this, "CostBoundary", {
      value: "Ephemeral portfolio defaults; destroy after validation",
    });
  }

  private createAutoDestroyWatchdog(autoDestroyAt: string): void {
    const stackArns = {
      runtime: Stack.of(this).formatArn({
        service: "cloudformation",
        resource: "stack",
        resourceName: "CaseResolutionRuntime/*",
        arnFormat: ArnFormat.SLASH_RESOURCE_NAME,
      }),
      foundation: Stack.of(this).formatArn({
        service: "cloudformation",
        resource: "stack",
        resourceName: "CaseResolutionFoundation/*",
        arnFormat: ArnFormat.SLASH_RESOURCE_NAME,
      }),
    };
    const deleteFoundation = new tasks.CallAwsService(this, "DeleteFoundationStack", {
      service: "cloudformation",
      action: "deleteStack",
      parameters: { StackName: "CaseResolutionFoundation" },
      iamResources: [stackArns.foundation],
    });
    const deleteRuntime = new tasks.CallAwsService(this, "DeleteRuntimeStack", {
      service: "cloudformation",
      action: "deleteStack",
      parameters: { StackName: "CaseResolutionRuntime" },
      iamResources: [stackArns.runtime],
    });
    const describeRuntime = new tasks.CallAwsService(this, "DescribeRuntimeStack", {
      service: "cloudformation",
      action: "describeStacks",
      parameters: { StackName: "CaseResolutionRuntime" },
      iamResources: [stackArns.runtime],
      resultPath: "$.runtime",
    });
    const describeRuntimeAfterDelete = new tasks.CallAwsService(
      this,
      "DescribeRuntimeAfterDelete",
      {
        service: "cloudformation",
        action: "describeStacks",
        parameters: { StackName: "CaseResolutionRuntime" },
        iamResources: [stackArns.runtime],
        resultPath: "$.runtime",
      },
    );
    const waitForRuntime = new sfn.Wait(this, "WaitForRuntimeDeletion", {
      time: sfn.WaitTime.duration(Duration.seconds(60)),
    });
    const deletionFailed = new sfn.Fail(this, "RuntimeDeletionFailed", {
      error: "RuntimeDeletionFailed",
      cause: "The runtime stack entered DELETE_FAILED and needs operator attention.",
    });
    const inspectRuntime = new sfn.Choice(this, "RuntimeStillExists")
      .when(
        sfn.Condition.stringEquals("$.runtime.Stacks[0].StackStatus", "DELETE_FAILED"),
        deletionFailed,
      )
      .otherwise(waitForRuntime);
    describeRuntime.addCatch(deleteFoundation, { resultPath: "$.runtimeMissing" });
    describeRuntime.next(deleteRuntime);
    deleteRuntime.next(waitForRuntime);
    waitForRuntime.next(describeRuntimeAfterDelete);
    describeRuntimeAfterDelete.addCatch(deleteFoundation, {
      resultPath: "$.runtimeDeleted",
    });
    describeRuntimeAfterDelete.next(inspectRuntime);

    const definition = sfn.Chain.start(describeRuntime);
    const stateMachine = new sfn.StateMachine(this, "AutoDestroyStateMachine", {
      stateMachineName: "case-resolution-portfolio-auto-destroy",
      definitionBody: sfn.DefinitionBody.fromChainable(definition),
      stateMachineType: sfn.StateMachineType.STANDARD,
      timeout: Duration.hours(2),
      removalPolicy: RemovalPolicy.DESTROY,
    });
    new CfnOutput(this, "AutoDestroyStateMachineArn", {
      value: stateMachine.stateMachineArn,
    });
    new CfnOutput(this, "AutoDestroyAtUtc", { value: autoDestroyAt });
    const schedulerRole = new iam.Role(this, "AutoDestroySchedulerRole", {
      assumedBy: new iam.ServicePrincipal("scheduler.amazonaws.com"),
    });
    stateMachine.grantStartExecution(schedulerRole);
    const autoDestroySchedule = new scheduler.CfnSchedule(this, "AutoDestroySchedule", {
      name: "case-resolution-portfolio-auto-destroy",
      description: "Starts teardown even if the operator terminal disconnects",
      scheduleExpression: `at(${autoDestroyAt.slice(0, -1)})`,
      scheduleExpressionTimezone: "UTC",
      flexibleTimeWindow: { mode: "OFF" },
      state: "ENABLED",
      target: {
        arn: stateMachine.stateMachineArn,
        roleArn: schedulerRole.roleArn,
        input: JSON.stringify({ requestedBy: "portfolio-validation-watchdog" }),
      },
    });
    new CfnOutput(this, "AutoDestroyScheduleName", {
      value: autoDestroySchedule.name ?? "case-resolution-portfolio-auto-destroy",
    });
  }
}

function retention(days: number): logs.RetentionDays {
  const supported: Record<number, logs.RetentionDays> = {
    1: logs.RetentionDays.ONE_DAY,
    3: logs.RetentionDays.THREE_DAYS,
    5: logs.RetentionDays.FIVE_DAYS,
    7: logs.RetentionDays.ONE_WEEK,
    14: logs.RetentionDays.TWO_WEEKS,
    30: logs.RetentionDays.ONE_MONTH,
  };
  const value = supported[days];
  if (!value) {
    throw new Error("logRetentionDays must be one of 1, 3, 5, 7, 14, or 30");
  }
  return value;
}

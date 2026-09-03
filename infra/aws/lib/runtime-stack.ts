import {
  CfnOutput,
  Duration,
  Size,
  Stack,
  StackProps,
  aws_cloudfront as cloudfront,
  aws_cloudfront_origins as origins,
  aws_ec2 as ec2,
  aws_ecs as ecs,
  aws_ecs_patterns as patterns,
  aws_elasticloadbalancingv2 as elbv2,
  aws_iam as iam,
  aws_secretsmanager as secretsmanager,
} from "aws-cdk-lib";
import { Construct } from "constructs";

import { DeploymentConfiguration } from "./configuration";
import { FoundationStack } from "./foundation-stack";

export interface RuntimeStackProps extends StackProps {
  readonly config: DeploymentConfiguration;
  readonly foundation: FoundationStack;
}

export class RuntimeStack extends Stack {
  constructor(scope: Construct, id: string, props: RuntimeStackProps) {
    super(scope, id, props);

    const { config, foundation } = props;
    const prefix = `${config.projectName}-${config.stage}`;
    const image = ecs.ContainerImage.fromEcrRepository(
      foundation.repository,
      config.imageDigest,
    );
    const apiRole = this.applicationRole("ApiTaskRole", `${prefix}-api-task`);
    const workerRole = this.applicationRole("WorkerTaskRole", `${prefix}-worker-task`);
    const schedulerRole = this.applicationRole(
      "SchedulerTaskRole",
      `${prefix}-scheduler-task`,
    );
    const migrationRole = this.applicationRole(
      "MigrationTaskRole",
      `${prefix}-migration-task`,
    );
    foundation.ingestionQueue.grantSendMessages(apiRole);
    foundation.ingestionQueue.grantConsumeMessages(workerRole);
    foundation.ingestionQueue.grantSendMessages(workerRole);
    foundation.ingestionQueue.grantSendMessages(schedulerRole);
    const apiSecurityGroup = new ec2.SecurityGroup(this, "ApiSecurityGroup", {
      vpc: foundation.vpc,
      securityGroupName: `${prefix}-api`,
      description: "Outbound API task access",
      allowAllOutbound: true,
    });
    const backgroundSecurityGroup = new ec2.SecurityGroup(this, "BackgroundSecurityGroup", {
      vpc: foundation.vpc,
      securityGroupName: `${prefix}-background`,
      description: "Outbound worker, scheduler, and migration access",
      allowAllOutbound: true,
    });
    for (const [id, port, source] of [
      ["DatabaseFromApi", 5432, apiSecurityGroup],
      ["DatabaseFromBackground", 5432, backgroundSecurityGroup],
    ] as const) {
      new ec2.CfnSecurityGroupIngress(this, id, {
        groupId: foundation.dataSecurityGroup.securityGroupId,
        ipProtocol: "tcp",
        fromPort: port,
        toPort: port,
        sourceSecurityGroupId: source.securityGroupId,
        description: `${port} from ${source.node.id}`,
      });
    }

    const loadBalancerSecurityGroup = new ec2.SecurityGroup(this, "LoadBalancerSecurityGroup", {
      vpc: foundation.vpc,
      securityGroupName: `${prefix}-alb`,
      description: "HTTP ingress from CloudFront origin-facing addresses only",
      allowAllOutbound: true,
    });
    loadBalancerSecurityGroup.addIngressRule(
      ec2.Peer.prefixList(config.cloudFrontPrefixListId),
      ec2.Port.tcp(80),
      "CloudFront origin-facing prefix list",
    );
    const loadBalancer = new elbv2.ApplicationLoadBalancer(this, "ApiLoadBalancer", {
      vpc: foundation.vpc,
      internetFacing: true,
      securityGroup: loadBalancerSecurityGroup,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
    });

    const apiTask = this.taskDefinition("ApiTask", apiRole, 512, 1024);
    const apiContainer = apiTask.addContainer("api", {
      image,
      command: [
        ".venv/bin/uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--workers",
        "2",
        "--proxy-headers",
      ],
      environment: this.commonEnvironment(config, foundation),
      secrets: this.applicationSecrets(foundation.applicationSecret, foundation),
      logging: ecs.LogDrivers.awsLogs({
        logGroup: foundation.logGroups.api,
        streamPrefix: "api",
        mode: ecs.AwsLogDriverMode.NON_BLOCKING,
        maxBufferSize: Size.mebibytes(4),
      }),
      readonlyRootFilesystem: true,
      user: "10001",
      healthCheck: {
        command: [
          "CMD-SHELL",
          "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/live', timeout=2)\" || exit 1",
        ],
        interval: Duration.seconds(30),
        timeout: Duration.seconds(5),
        retries: 3,
        startPeriod: Duration.seconds(60),
      },
    });
    apiContainer.addPortMappings({
      name: "http",
      containerPort: 8000,
      protocol: ecs.Protocol.TCP,
      appProtocol: ecs.AppProtocol.http,
    });

    const apiService = new patterns.ApplicationLoadBalancedFargateService(this, "ApiService", {
      serviceName: `${prefix}-api`,
      cluster: foundation.cluster,
      taskDefinition: apiTask,
      desiredCount: 1,
      assignPublicIp: true,
      publicLoadBalancer: true,
      loadBalancer,
      openListener: false,
      taskSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      securityGroups: [apiSecurityGroup],
      circuitBreaker: { rollback: true },
      healthCheckGracePeriod: Duration.seconds(90),
      minHealthyPercent: 50,
    });
    this.scaleToZeroByDefault(apiService.service);
    apiService.targetGroup.configureHealthCheck({
      path: "/api/health/ready",
      healthyHttpCodes: "200",
      interval: Duration.seconds(30),
      timeout: Duration.seconds(5),
    });

    const workerService = this.workerService(
      config,
      foundation,
      image,
      workerRole,
      backgroundSecurityGroup,
    );
    const schedulerService = this.schedulerService(
      config,
      foundation,
      image,
      schedulerRole,
      backgroundSecurityGroup,
    );
    const migrationTask = this.migrationTask(
      config,
      foundation,
      image,
      migrationRole,
    );

    const distribution = new cloudfront.Distribution(this, "ApiDistribution", {
      comment: `${prefix} HTTPS API endpoint`,
      defaultBehavior: {
        origin: new origins.LoadBalancerV2Origin(apiService.loadBalancer, {
          protocolPolicy: cloudfront.OriginProtocolPolicy.HTTP_ONLY,
        }),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
        cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
        originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
      },
      priceClass: cloudfront.PriceClass.PRICE_CLASS_200,
    });

    new CfnOutput(this, "ApiBaseUrl", {
      value: `https://${distribution.distributionDomainName}`,
    });
    new CfnOutput(this, "ClusterName", { value: foundation.cluster.clusterName });
    new CfnOutput(this, "ApiServiceName", { value: apiService.service.serviceName });
    new CfnOutput(this, "WorkerServiceName", { value: workerService.serviceName });
    new CfnOutput(this, "SchedulerServiceName", { value: schedulerService.serviceName });
    new CfnOutput(this, "MigrationSecurityGroupId", {
      value: backgroundSecurityGroup.securityGroupId,
    });
    new CfnOutput(this, "RuntimeSubnetIds", {
      value: foundation.vpc
        .selectSubnets({ subnetType: ec2.SubnetType.PUBLIC })
        .subnetIds.join(","),
    });
    new CfnOutput(this, "MigrationTaskDefinitionArn", {
      value: migrationTask.taskDefinitionArn,
    });
  }

  private workerService(
    config: DeploymentConfiguration,
    foundation: FoundationStack,
    image: ecs.ContainerImage,
    taskRole: iam.Role,
    runtimeSecurityGroup: ec2.SecurityGroup,
  ): ecs.FargateService {
    const task = this.taskDefinition("WorkerTask", taskRole, 512, 1024);
    task.addContainer("worker", {
      image,
      command: [
        ".venv/bin/celery",
        "--app",
        "app.async_jobs.celery_worker:app",
        "worker",
        "--loglevel=INFO",
        "--concurrency=2",
        "--prefetch-multiplier=1",
        "--max-tasks-per-child=100",
      ],
      environment: this.commonEnvironment(config, foundation),
      secrets: this.applicationSecrets(foundation.applicationSecret, foundation),
      logging: ecs.LogDrivers.awsLogs({
        logGroup: foundation.logGroups.worker,
        streamPrefix: "worker",
        mode: ecs.AwsLogDriverMode.NON_BLOCKING,
      }),
      readonlyRootFilesystem: true,
      user: "10001",
      stopTimeout: Duration.seconds(120),
    });
    const service = new ecs.FargateService(this, "WorkerService", {
      serviceName: `${config.projectName}-${config.stage}-worker`,
      cluster: foundation.cluster,
      taskDefinition: task,
      desiredCount: 1,
      assignPublicIp: true,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      securityGroups: [runtimeSecurityGroup],
      circuitBreaker: { rollback: true },
      minHealthyPercent: 50,
    });
    this.scaleToZeroByDefault(service);
    return service;
  }

  private schedulerService(
    config: DeploymentConfiguration,
    foundation: FoundationStack,
    image: ecs.ContainerImage,
    taskRole: iam.Role,
    runtimeSecurityGroup: ec2.SecurityGroup,
  ): ecs.FargateService {
    const task = this.taskDefinition("SchedulerTask", taskRole, 256, 512);
    const container = task.addContainer("scheduler", {
      image,
      command: [
        ".venv/bin/celery",
        "--app",
        "app.async_jobs.celery_worker:app",
        "beat",
        "--loglevel=INFO",
        "--schedule=/tmp/celerybeat-schedule",
        "--pidfile=/tmp/celerybeat.pid",
      ],
      environment: this.commonEnvironment(config, foundation),
      secrets: this.applicationSecrets(foundation.applicationSecret, foundation),
      logging: ecs.LogDrivers.awsLogs({
        logGroup: foundation.logGroups.scheduler,
        streamPrefix: "scheduler",
        mode: ecs.AwsLogDriverMode.NON_BLOCKING,
      }),
      readonlyRootFilesystem: true,
      user: "10001",
    });
    task.addVolume({ name: "scheduler-tmp" });
    container.addMountPoints({
      sourceVolume: "scheduler-tmp",
      containerPath: "/tmp",
      readOnly: false,
    });
    const service = new ecs.FargateService(this, "SchedulerService", {
      serviceName: `${config.projectName}-${config.stage}-scheduler`,
      cluster: foundation.cluster,
      taskDefinition: task,
      desiredCount: 1,
      assignPublicIp: true,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      securityGroups: [runtimeSecurityGroup],
      circuitBreaker: { rollback: true },
      minHealthyPercent: 0,
      maxHealthyPercent: 100,
    });
    this.scaleToZeroByDefault(service);
    return service;
  }

  private migrationTask(
    config: DeploymentConfiguration,
    foundation: FoundationStack,
    image: ecs.ContainerImage,
    taskRole: iam.Role,
  ): ecs.FargateTaskDefinition {
    const task = this.taskDefinition("MigrationTask", taskRole, 256, 512);
    task.addContainer("migration", {
      image,
      command: [".venv/bin/alembic", "upgrade", "head"],
      environment: this.migrationEnvironment(config, foundation),
      secrets: this.migrationSecrets(foundation.applicationSecret, foundation),
      logging: ecs.LogDrivers.awsLogs({
        logGroup: foundation.logGroups.migration,
        streamPrefix: "migration",
      }),
      readonlyRootFilesystem: true,
      user: "10001",
    });
    return task;
  }

  private taskDefinition(
    id: string,
    taskRole: iam.Role,
    cpu: number,
    memoryLimitMiB: number,
  ): ecs.FargateTaskDefinition {
    return new ecs.FargateTaskDefinition(this, id, {
      cpu,
      memoryLimitMiB,
      taskRole,
      runtimePlatform: {
        cpuArchitecture: ecs.CpuArchitecture.X86_64,
        operatingSystemFamily: ecs.OperatingSystemFamily.LINUX,
      },
    });
  }

  private applicationRole(id: string, roleName: string): iam.Role {
    return new iam.Role(this, id, {
      roleName,
      assumedBy: new iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
      description: `Runtime role for ${id}`,
    });
  }

  private scaleToZeroByDefault(service: ecs.FargateService): void {
    const resource = service.node.defaultChild;
    if (!(resource instanceof ecs.CfnService)) {
      throw new Error("Expected an ECS CfnService resource");
    }
    resource.desiredCount = 0;
  }

  private commonEnvironment(
    config: DeploymentConfiguration,
    foundation: FoundationStack,
  ): Record<string, string> {
    return {
      SUPPORT_COPILOT_ENVIRONMENT: "production",
      SUPPORT_COPILOT_AUTH_MODE: "provider",
      SUPPORT_COPILOT_MODEL_PROVIDER: "openai",
      SUPPORT_COPILOT_EMBEDDING_PROVIDER: "deterministic",
      SUPPORT_COPILOT_LOG_LEVEL: "INFO",
      SUPPORT_COPILOT_DEV_MIGRATE: "false",
      SUPPORT_COPILOT_DEV_SEED: "false",
      SUPPORT_COPILOT_CORS_ORIGINS: config.frontendOrigin,
      SUPPORT_COPILOT_CLERK_AUTHORIZED_PARTIES: config.frontendOrigin,
      SUPPORT_COPILOT_SOURCE_REVISION: config.sourceRevision,
      SUPPORT_COPILOT_DB_HOST: foundation.database.dbInstanceEndpointAddress,
      SUPPORT_COPILOT_DB_PORT: foundation.database.dbInstanceEndpointPort,
      SUPPORT_COPILOT_DB_NAME: "supportcopilot",
      SUPPORT_COPILOT_ASYNC_BROKER_URL: "sqs://",
      SUPPORT_COPILOT_ASYNC_QUEUE_NAME: foundation.ingestionQueue.queueName,
      SUPPORT_COPILOT_ASYNC_SQS_QUEUE_URL: foundation.ingestionQueue.queueUrl,
      SUPPORT_COPILOT_ASYNC_AWS_REGION: this.region,
      SUPPORT_COPILOT_ASYNC_SQS_VISIBILITY_TIMEOUT_SECONDS: "180",
      SUPPORT_COPILOT_INBOX_CONNECTIONS_ENABLED: "true",
      SUPPORT_COPILOT_GMAIL_ADAPTER_ENABLED: "true",
      SUPPORT_COPILOT_INBOX_SCHEDULED_SYNC_ENABLED: "true",
      SUPPORT_COPILOT_GMAIL_PUSH_ENABLED: "false",
      SUPPORT_COPILOT_INBOX_DRAFT_WRITEBACK_ENABLED: "true",
      SUPPORT_COPILOT_INBOX_AI_DATA_TRANSFER_ENABLED: "true",
      SUPPORT_COPILOT_GOOGLE_OAUTH_REDIRECT_URI: `${config.frontendOrigin}/connections/inbox/callback`,
      SUPPORT_COPILOT_CREDENTIAL_VAULT_KEY_ID: "aws-portfolio-v1",
      SUPPORT_COPILOT_POLICY_RETRIEVAL_MODE: "v2",
      SUPPORT_COPILOT_POLICY_V2_EMBEDDING_PROVIDER: "deterministic",
      SUPPORT_COPILOT_POLICY_V2_PROFILE_KEY: "deterministic-hash-v2-d512",
      SUPPORT_COPILOT_POLICY_INDEXING_ENABLED: "true",
    };
  }

  private migrationEnvironment(
    config: DeploymentConfiguration,
    foundation: FoundationStack,
  ): Record<string, string> {
    return {
      SUPPORT_COPILOT_ENVIRONMENT: "production",
      SUPPORT_COPILOT_AUTH_MODE: "provider",
      SUPPORT_COPILOT_MODEL_PROVIDER: "deterministic",
      SUPPORT_COPILOT_EMBEDDING_PROVIDER: "deterministic",
      SUPPORT_COPILOT_LOG_LEVEL: "INFO",
      SUPPORT_COPILOT_DEV_MIGRATE: "false",
      SUPPORT_COPILOT_DEV_SEED: "false",
      SUPPORT_COPILOT_CORS_ORIGINS: config.frontendOrigin,
      SUPPORT_COPILOT_CLERK_AUTHORIZED_PARTIES: config.frontendOrigin,
      SUPPORT_COPILOT_SOURCE_REVISION: config.sourceRevision,
      SUPPORT_COPILOT_DB_HOST: foundation.database.dbInstanceEndpointAddress,
      SUPPORT_COPILOT_DB_PORT: foundation.database.dbInstanceEndpointPort,
      SUPPORT_COPILOT_DB_NAME: "supportcopilot",
    };
  }

  private applicationSecrets(
    applicationSecret: secretsmanager.Secret,
    foundation: FoundationStack,
  ): Record<string, ecs.Secret> {
    const databaseSecret = foundation.database.secret;
    if (!databaseSecret) {
      throw new Error("RDS generated credentials secret is required");
    }
    return {
      SUPPORT_COPILOT_DB_USERNAME: ecs.Secret.fromSecretsManager(databaseSecret, "username"),
      SUPPORT_COPILOT_DB_PASSWORD: ecs.Secret.fromSecretsManager(databaseSecret, "password"),
      SUPPORT_COPILOT_CLERK_SECRET_KEY: ecs.Secret.fromSecretsManager(
        applicationSecret,
        "SUPPORT_COPILOT_CLERK_SECRET_KEY",
      ),
      SUPPORT_COPILOT_CLERK_JWT_KEY: ecs.Secret.fromSecretsManager(
        applicationSecret,
        "SUPPORT_COPILOT_CLERK_JWT_KEY",
      ),
      SUPPORT_COPILOT_OPENAI_API_KEY: ecs.Secret.fromSecretsManager(
        applicationSecret,
        "SUPPORT_COPILOT_OPENAI_API_KEY",
      ),
      SUPPORT_COPILOT_GOOGLE_OAUTH_CLIENT_ID: ecs.Secret.fromSecretsManager(
        applicationSecret,
        "SUPPORT_COPILOT_GOOGLE_OAUTH_CLIENT_ID",
      ),
      SUPPORT_COPILOT_GOOGLE_OAUTH_CLIENT_SECRET: ecs.Secret.fromSecretsManager(
        applicationSecret,
        "SUPPORT_COPILOT_GOOGLE_OAUTH_CLIENT_SECRET",
      ),
      SUPPORT_COPILOT_CREDENTIAL_VAULT_KEY: ecs.Secret.fromSecretsManager(
        applicationSecret,
        "SUPPORT_COPILOT_CREDENTIAL_VAULT_KEY",
      ),
      SUPPORT_COPILOT_INBOX_SCHEDULER_SECRET: ecs.Secret.fromSecretsManager(
        applicationSecret,
        "SUPPORT_COPILOT_INBOX_SCHEDULER_SECRET",
      ),
      SUPPORT_COPILOT_POLICY_INDEX_SCHEDULER_SECRET: ecs.Secret.fromSecretsManager(
        applicationSecret,
        "SUPPORT_COPILOT_POLICY_INDEX_SCHEDULER_SECRET",
      ),
    };
  }

  private migrationSecrets(
    applicationSecret: secretsmanager.Secret,
    foundation: FoundationStack,
  ): Record<string, ecs.Secret> {
    const databaseSecret = foundation.database.secret;
    if (!databaseSecret) {
      throw new Error("RDS generated credentials secret is required");
    }
    return {
      SUPPORT_COPILOT_DB_USERNAME: ecs.Secret.fromSecretsManager(databaseSecret, "username"),
      SUPPORT_COPILOT_DB_PASSWORD: ecs.Secret.fromSecretsManager(databaseSecret, "password"),
      SUPPORT_COPILOT_CLERK_SECRET_KEY: ecs.Secret.fromSecretsManager(
        applicationSecret,
        "SUPPORT_COPILOT_CLERK_SECRET_KEY",
      ),
      SUPPORT_COPILOT_CLERK_JWT_KEY: ecs.Secret.fromSecretsManager(
        applicationSecret,
        "SUPPORT_COPILOT_CLERK_JWT_KEY",
      ),
    };
  }
}

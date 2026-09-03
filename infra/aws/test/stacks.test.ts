import { App } from "aws-cdk-lib";
import { Match, Template } from "aws-cdk-lib/assertions";
import { describe, expect, it } from "vitest";

import { DeploymentConfiguration } from "../lib/configuration";
import { FoundationStack } from "../lib/foundation-stack";
import { RuntimeStack } from "../lib/runtime-stack";

const config: DeploymentConfiguration = {
  projectName: "case-resolution-copilot",
  stage: "portfolio",
  frontendOrigin: "https://example.vercel.app",
  cloudFrontPrefixListId: "pl-31a34658",
  includeRuntime: true,
  imageDigest: `sha256:${"b".repeat(64)}`,
  sourceRevision: "a".repeat(40),
  logRetentionDays: 7,
  autoDestroyAt: "2099-01-01T00:00:00Z",
};

function stacks(): { foundation: Template; runtime: Template } {
  const app = new App({
    context: { "@aws-cdk/core:defaultCrossStackReferences": "strong" },
  });
  const foundationStack = new FoundationStack(app, "Foundation", {
    config,
    env: { account: "111111111111", region: "ap-southeast-1" },
  });
  const runtimeStack = new RuntimeStack(app, "Runtime", {
    config,
    foundation: foundationStack,
    env: { account: "111111111111", region: "ap-southeast-1" },
  });
  runtimeStack.addStackDependency(foundationStack);
  return {
    foundation: Template.fromStack(foundationStack),
    runtime: Template.fromStack(runtimeStack),
  };
}

describe("portfolio AWS stacks", () => {
  it(
    "keeps data private and avoids fixed Redis and NAT costs",
    () => {
      const { foundation } = stacks();
      foundation.resourceCountIs("AWS::EC2::NatGateway", 0);
      foundation.resourceCountIs("AWS::ElastiCache::ReplicationGroup", 0);
      foundation.hasResourceProperties("AWS::RDS::DBInstance", {
        DBInstanceClass: "db.t4g.micro",
        MultiAZ: false,
        PubliclyAccessible: false,
        StorageType: "gp3",
        DeletionProtection: false,
      });
      foundation.hasResourceProperties("AWS::SQS::Queue", {
        VisibilityTimeout: 180,
        ReceiveMessageWaitTimeSeconds: 20,
        RedrivePolicy: Match.anyValue(),
      });
      foundation.hasResourceProperties("AWS::Lambda::Function", {
        Handler: "handler.handle",
        Runtime: "python3.12",
      });
      foundation.hasResourceProperties("AWS::Scheduler::Schedule", {
        ScheduleExpression: "at(2099-01-01T00:00:00)",
        ScheduleExpressionTimezone: "UTC",
        State: "ENABLED",
      });
      foundation.hasResourceProperties("AWS::StepFunctions::StateMachine", {
        StateMachineType: "STANDARD",
      });
      foundation.hasResourceProperties("AWS::S3::Bucket", {
        VersioningConfiguration: { Status: "Enabled" },
      });
    },
    30_000,
  );

  it(
    "creates immutable images and short-retention logs",
    () => {
      const { foundation } = stacks();
      foundation.hasResourceProperties("AWS::ECR::Repository", {
        ImageTagMutability: "IMMUTABLE",
        ImageScanningConfiguration: { ScanOnPush: true },
      });
      foundation.hasResourceProperties("AWS::Logs::LogGroup", {
        RetentionInDays: 7,
      });
    },
    30_000,
  );

  it(
    "registers four task contracts but leaves services scaled to zero",
    () => {
      const { runtime } = stacks();
      runtime.resourceCountIs("AWS::ECS::TaskDefinition", 4);
      runtime.resourceCountIs("AWS::ECS::Service", 3);
      runtime.hasResourceProperties("AWS::ECS::Service", {
        DesiredCount: 0,
        DeploymentConfiguration: Match.objectLike({
          DeploymentCircuitBreaker: { Enable: true, Rollback: true },
        }),
      });
      runtime.resourceCountIs("AWS::CloudFront::Distribution", 1);
      runtime.hasResourceProperties("AWS::EC2::SecurityGroupIngress", {
        FromPort: 80,
        ToPort: 80,
        SourcePrefixListId: "pl-31a34658",
      });
      const ingress = runtime.findResources("AWS::EC2::SecurityGroupIngress");
      expect(Object.values(ingress)).not.toEqual(
        expect.arrayContaining([
          expect.objectContaining({ Properties: expect.objectContaining({ CidrIp: "0.0.0.0/0" }) }),
        ]),
      );
      const templateText = JSON.stringify(runtime.toJSON());
      expect(templateText).not.toContain("replace_before_runtime_deploy");
      expect(templateText).toContain(`@sha256:${"b".repeat(64)}`);
      expect(templateText).toContain("SUPPORT_COPILOT_INBOX_CONNECTIONS_ENABLED");
      expect(templateText).toContain("SUPPORT_COPILOT_POLICY_INDEXING_ENABLED");
      expect(templateText).toContain("SUPPORT_COPILOT_ASYNC_SQS_QUEUE_URL");
      expect(templateText).not.toContain("SUPPORT_COPILOT_REDIS_AUTH_TOKEN");
      expect(templateText).not.toContain("SUPPORT_COPILOT_ARTIFACT_BUCKET");
    },
    30_000,
  );
});

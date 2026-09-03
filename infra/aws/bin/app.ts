#!/usr/bin/env node
import { App, Stack, Tags } from "aws-cdk-lib";

import { readConfiguration } from "../lib/configuration";
import { FoundationStack } from "../lib/foundation-stack";
import { RuntimeStack } from "../lib/runtime-stack";

const app = new App();
const config = readConfiguration(app);
const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION ?? "ap-southeast-1",
};

if (env.region !== "ap-southeast-1") {
  throw new Error("Wave 2C is intentionally bounded to ap-southeast-1");
}

const foundation = new FoundationStack(app, "CaseResolutionFoundation", {
  env,
  config,
  description: "Ephemeral portfolio foundation for Case Resolution Copilot",
});

if (config.includeRuntime) {
  const runtime = new RuntimeStack(app, "CaseResolutionRuntime", {
    env,
    config,
    foundation,
    description: "Ephemeral ECS runtime for Case Resolution Copilot",
  });
  runtime.addStackDependency(foundation);
}

for (const child of app.node.children) {
  if (child instanceof Stack) {
    Tags.of(child).add("Project", config.projectName);
    Tags.of(child).add("Environment", config.stage);
    Tags.of(child).add("Lifecycle", "ephemeral-validation");
    Tags.of(child).add("ManagedBy", "aws-cdk");
  }
}

import { App } from "aws-cdk-lib";

export interface DeploymentConfiguration {
  readonly projectName: string;
  readonly stage: string;
  readonly frontendOrigin: string;
  readonly cloudFrontPrefixListId: string;
  readonly includeRuntime: boolean;
  readonly imageDigest: string;
  readonly sourceRevision: string;
  readonly logRetentionDays: number;
  readonly autoDestroyAt: string;
}

const SAFE_NAME = /^[a-z][a-z0-9-]{2,31}$/;
const IMAGE_DIGEST = /^sha256:[0-9a-f]{64}$/;
const PREFIX_LIST_ID = /^pl-[0-9a-f]+$/;
const SOURCE_REVISION = /^[0-9a-f]{40}$/;

export function readConfiguration(app: App): DeploymentConfiguration {
  const projectName = context(app, "projectName");
  const stage = context(app, "stage");
  const frontendOrigin = context(app, "frontendOrigin");
  const cloudFrontPrefixListId = context(app, "cloudFrontPrefixListId");
  const imageDigest = context(app, "imageDigest").toLowerCase();
  const sourceRevision = context(app, "sourceRevision").toLowerCase();
  const includeRuntime = context(app, "includeRuntime") === "true";
  const logRetentionDays = Number(context(app, "logRetentionDays"));
  const autoDestroyAt = context(app, "autoDestroyAt");

  if (!SAFE_NAME.test(projectName)) {
    throw new Error("projectName must be a lowercase, hyphenated AWS-safe name");
  }
  if (!SAFE_NAME.test(stage)) {
    throw new Error("stage must be a lowercase, hyphenated AWS-safe name");
  }
  if (!isHttpsOrigin(frontendOrigin)) {
    throw new Error("frontendOrigin must be an HTTPS origin without a path");
  }
  if (!PREFIX_LIST_ID.test(cloudFrontPrefixListId)) {
    throw new Error("cloudFrontPrefixListId must be an AWS managed prefix-list ID");
  }
  if (includeRuntime && !IMAGE_DIGEST.test(imageDigest)) {
    throw new Error("imageDigest must be a sha256 container digest");
  }
  if (includeRuntime && !SOURCE_REVISION.test(sourceRevision)) {
    throw new Error("sourceRevision must be the full 40-character Git commit SHA");
  }
  if (![1, 3, 5, 7, 14, 30].includes(logRetentionDays)) {
    throw new Error("logRetentionDays must be one of 1, 3, 5, 7, 14, or 30");
  }
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(autoDestroyAt)) {
    throw new Error("autoDestroyAt must be a UTC timestamp without milliseconds");
  }

  return {
    projectName,
    stage,
    frontendOrigin,
    cloudFrontPrefixListId,
    includeRuntime,
    imageDigest,
    sourceRevision,
    logRetentionDays,
    autoDestroyAt,
  };
}

function context(app: App, name: string): string {
  const value = app.node.tryGetContext(name);
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`Missing CDK context value: ${name}`);
  }
  return value.trim();
}

function isHttpsOrigin(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && url.pathname === "/" && !url.search && !url.hash;
  } catch {
    return false;
  }
}

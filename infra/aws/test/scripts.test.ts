import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const scriptsRoot = join(__dirname, "..", "scripts");

function script(name: string): string {
  return readFileSync(join(scriptsRoot, name), "utf8");
}

describe("AWS lifecycle scripts", () => {
  it("fails fast on native command errors and pins the requested region", () => {
    const common = script("common.ps1");

    expect(common).toContain("$PSNativeCommandUseErrorActionPreference = $true");
    expect(common).toContain("$env:AWS_DEFAULT_REGION = $Region");
    expect(common).toContain("$env:CDK_DEFAULT_REGION = $Region");
  });

  it("deploys stack dependencies before runtime and consumes a scanned digest", () => {
    const deploy = script("deploy-runtime.ps1");

    expect(deploy).not.toContain("--exclusively");
    expect(deploy).toContain("release.local.json");
    expect(deploy).toContain("-c imageDigest=$imageDigest");
    expect(deploy).toContain("MigrationSecurityGroupId");
    expect(deploy).toContain("--desired-count 0");
    expect(deploy).toContain("imageDigest=$imageDigest");
    expect(deploy).toContain("Assert-ApplicationSecretPayload");
  });

  it("publishes only a clean exact revision and records its ECR scan result", () => {
    const publish = script("publish-image.ps1");

    expect(publish).toContain("rev-parse HEAD");
    expect(publish).toContain("status --porcelain");
    expect(publish).toContain("image-scan-complete");
    expect(publish).toContain("CRITICAL,HIGH");
    expect(publish).toContain("release.local.json");
  });

  it("requires the existing cost budget before creating the foundation", () => {
    const deploy = script("deploy-foundation.ps1");
    const common = script("common.ps1");

    expect(deploy).toContain("portfolio-aws-monthly-budget");
    expect(deploy).toContain("Assert-CostBudget");
    expect(common).toContain("budgets describe-budget");
    expect(common).toContain("budgets describe-notifications-for-budget");
    expect(common).toContain("BudgetLimit.Unit -ne \"USD\"");
    expect(common).toContain("-gt 25");
    expect(common).toContain("ThresholdType -eq \"PERCENTAGE\"");
    expect(common).toContain("$actualThresholds -notcontains 80");
    expect(common).toContain("Test-UrlSafeBase64Key");
  });

  it("bounds live validation and records teardown evidence", () => {
    const foundation = script("deploy-foundation.ps1");
    const validate = script("validate-live.ps1");
    const destroy = script("destroy.ps1");

    expect(foundation).toContain("AddMinutes(45)");
    expect(foundation).toContain("AddMinutes(35)");
    expect(foundation).toContain("-c autoDestroyAt=$watchdogAtText");
    expect(validate).toContain("Assert-ValidationWindow");
    expect(validate).toContain("IngestionDeadLetterQueueUrl");
    expect(validate).toContain("aws_validation_passed");
    expect(validate).toContain("rdsMigrationRevision");
    expect(destroy).toContain("aws-teardown-evidence.local.json");
    expect(destroy).toContain("stacksRemaining = 0");
  });
});

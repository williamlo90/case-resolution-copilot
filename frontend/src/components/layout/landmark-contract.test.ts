import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const sourceRoot = path.resolve(__dirname, "../..");

function tsxFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return tsxFiles(entryPath);
    return entry.isFile() && entry.name.endsWith(".tsx") ? [entryPath] : [];
  });
}

describe("protected-page landmark contract", () => {
  it("keeps the application shell as the only main landmark", () => {
    const protectedFeatures = tsxFiles(path.join(sourceRoot, "features")).filter(
      (file) => !file.includes(`${path.sep}features${path.sep}access${path.sep}`),
    );
    const protectedRoutes = tsxFiles(
      path.join(sourceRoot, "app", "(operations)"),
    );

    for (const file of [...protectedFeatures, ...protectedRoutes]) {
      expect(readFileSync(file, "utf-8"), file).not.toMatch(/<main(?:\s|>)/);
    }
    expect(
      readFileSync(path.join(sourceRoot, "components", "layout", "app-shell.tsx"), "utf-8"),
    ).toMatch(/<main id="main-content"/);
  });
});

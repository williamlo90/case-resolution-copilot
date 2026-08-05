import { readFileSync, readdirSync } from "node:fs";
import { extname, join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const sourceRoot = resolve(process.cwd(), "src");
const protectedRoots = [
  resolve(sourceRoot, "app", "(operations)"),
  resolve(sourceRoot, "components", "layout"),
  resolve(sourceRoot, "features", "actions"),
  resolve(sourceRoot, "features", "administration"),
  resolve(sourceRoot, "features", "cases"),
  resolve(sourceRoot, "features", "evidence"),
  resolve(sourceRoot, "features", "policies"),
  resolve(sourceRoot, "features", "quality"),
  resolve(sourceRoot, "features", "reviews"),
];

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      return sourceFiles(path);
    }
    return [".ts", ".tsx"].includes(extname(path)) ? [path] : [];
  });
}

describe("protected workspace navigation", () => {
  it("uses the Next.js data router with intent-only prefetch", () => {
    const workspaceLinkSource = readFileSync(
      resolve(sourceRoot, "components", "navigation", "workspace-link.tsx"),
      "utf8",
    );

    expect(workspaceLinkSource).toContain("next/link");
    expect(workspaceLinkSource).toContain(
      "prefetch={intentShown ? null : false}",
    );
    expect(workspaceLinkSource).toContain("onMouseEnter={handleMouseEnter}");
  });

  it("routes all operational links through WorkspaceLink", () => {
    const directNextLinkImports = protectedRoots
      .flatMap(sourceFiles)
      .filter((path) =>
        /from\s+["']next\/link["']/.test(readFileSync(path, "utf8")),
      );

    expect(directNextLinkImports).toEqual([]);
  });
});

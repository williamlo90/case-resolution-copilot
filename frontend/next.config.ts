import type { NextConfig } from "next";
import { SECURITY_HEADERS } from "./src/config/security-headers";

const sourceRevision = process.env.VERCEL_GIT_COMMIT_SHA?.toLowerCase();
const revisionHeaders = /^[0-9a-f]{40}$/.test(sourceRevision ?? "")
  ? [{ key: "X-Source-Revision", value: sourceRevision as string }]
  : [];

const nextConfig: NextConfig = {
  output: process.env.SUPPORT_COPILOT_STANDALONE === "true" ? "standalone" : undefined,
  allowedDevOrigins: ["localhost", "127.0.0.1"],
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [...SECURITY_HEADERS, ...revisionHeaders],
      },
    ];
  },
  experimental: {
    cpus: 2,
    preloadEntriesOnStart: false,
    serverSourceMaps: false,
    webpackMemoryOptimizations: true,
  },
};

export default nextConfig;

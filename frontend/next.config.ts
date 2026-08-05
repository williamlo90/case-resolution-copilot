import type { NextConfig } from "next";
import { SECURITY_HEADERS } from "./src/config/security-headers";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["localhost", "127.0.0.1"],
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [...SECURITY_HEADERS],
      },
    ];
  },
  experimental: {
    preloadEntriesOnStart: false,
    serverSourceMaps: false,
    webpackMemoryOptimizations: true,
  },
};

export default nextConfig;

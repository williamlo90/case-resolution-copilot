import { describe, expect, it } from "vitest";
import {
  CLERK_CSP_DIRECTIVES,
  SECURITY_HEADERS,
} from "@/config/security-headers";

describe("security headers", () => {
  it("blocks framing, content sniffing, and unused browser capabilities", () => {
    expect(Object.fromEntries(SECURITY_HEADERS.map(({ key, value }) => [key, value]))).toEqual({
      "Permissions-Policy":
        "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
      "Referrer-Policy": "strict-origin-when-cross-origin",
      "X-Content-Type-Options": "nosniff",
      "X-Frame-Options": "DENY",
      "X-Robots-Tag": "noindex, nofollow, noarchive",
    });
  });

  it("adds restrictive directives to Clerk's nonce-based policy", () => {
    expect(CLERK_CSP_DIRECTIVES).toEqual({
      "base-uri": ["'self'"],
      "frame-ancestors": ["'none'"],
      "object-src": ["'none'"],
    });
  });
});

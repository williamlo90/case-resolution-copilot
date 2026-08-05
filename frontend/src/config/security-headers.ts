export const SECURITY_HEADERS = [
  {
    key: "X-Content-Type-Options",
    value: "nosniff",
  },
  {
    key: "X-Frame-Options",
    value: "DENY",
  },
  {
    key: "X-Robots-Tag",
    value: "noindex, nofollow, noarchive",
  },
  {
    key: "Referrer-Policy",
    value: "strict-origin-when-cross-origin",
  },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
  },
] satisfies Array<{ key: string; value: string }>;

export const CLERK_CSP_DIRECTIVES: Record<string, string[]> = {
  "base-uri": ["'self'"],
  "frame-ancestors": ["'none'"],
  "object-src": ["'none'"],
};

# Deployment Security Hardening

Status: Application controls implemented; perimeter smoke verification required after every
production deployment

## Frontend Boundary

The frontend uses Clerk's strict nonce-based Content Security Policy. `ClerkProvider` remains
dynamic so Next.js and Clerk can propagate a fresh nonce on each document request. Additional CSP
directives block objects, base URL replacement, and framing.

Every frontend response also sets:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- a restrictive `Permissions-Policy`
- `X-Robots-Tag: noindex, nofollow, noarchive`

Vercel owns HSTS for the deployment domain. Do not duplicate or weaken it in application code.

References:

- [Clerk CSP configuration](https://clerk.com/docs/guides/secure/best-practices/csp-headers)
- [Next.js security headers](https://nextjs.org/docs/app/api-reference/config/next-config-js/headers)

## Backend Boundary

API responses set `Cache-Control: no-store`, anti-framing, no-sniff, no-referrer, permissions, and
no-index headers. Production responses also use a JSON-only CSP:

```text
default-src 'none'; base-uri 'none'; frame-ancestors 'none'
```

FastAPI Swagger, ReDoc, and OpenAPI endpoints are disabled when
`SUPPORT_COPILOT_ENVIRONMENT=production`. Test and development environments retain them for
contract verification.

## Release Verification

After both Vercel services finish deploying, run from the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\production-smoke.ps1
```

The script performs five bounded, unauthenticated checks:

1. `/cases` redirects once to the local sign-in route.
2. The frontend sends strict CSP and defensive headers.
3. Backend readiness reports a healthy database.
4. Backend responses send no-store and defensive headers.
5. Production OpenAPI returns `404`.

The script never reads credentials, browser state, or local environment files.

## External Controls Still Required

These application headers do not replace:

- account-level MFA and credential rotation;
- provider-side DDoS and WAF controls;
- distributed rate limiting for authenticated business commands;
- centralized log retention, alert delivery, and incident paging;
- penetration testing and dependency-vulnerability monitoring.

Do not claim these external controls until their provider configuration and failure evidence are
recorded.

# Case Resolution Copilot Frontend

Next.js 16 frontend for the complex customer-case decision workspace.

The operational product reads generic case, review, action, policy, quality, connection, member, and
settings APIs by default. Mock data is an explicit opt-in for isolated UI work; legacy `/tasks`
routes are redirects or diagnostics and are not active data dependencies.

## Data Mode

Copy `.env.example` to an ignored local environment file only when activation is approved.

- `SUPPORT_COPILOT_DATA_MODE=api` is the default and requires the FastAPI service.
- `SUPPORT_COPILOT_DATA_MODE=mock` keeps the deterministic UI repository isolated from the backend.
- `SUPPORT_COPILOT_API_INTERNAL_URL` is the server-side API origin.
- `SUPPORT_COPILOT_AUTH_MODE=deterministic_development` uses the server-owned demo actor.
- `SUPPORT_COPILOT_AUTH_MODE=provider` enables Clerk route protection and bearer sessions.
- `SUPPORT_COPILOT_DEMO_ACTOR_ID` selects a server-owned deterministic actor in development only.

In provider mode, configure the Clerk publishable and secret keys only in `.env.local`. The
frontend does not send demo actor or role headers in that mode. No browser-visible role,
organization, or Clerk Organization claim grants authority; the backend derives both from its
membership record.

See [authentication activation](../docs/runbooks/AUTHENTICATION_ACTIVATION.md).

## Safe Local Commands

```powershell
pnpm test
pnpm lint
pnpm typecheck
```

The resource-safe local gate does not include `pnpm build`. When explicitly run, the build uses
Webpack with two workers; Turbopack is not part of this workflow.
`pnpm dev` also fails closed because the Next.js Webpack and Clerk route compilation needs about
1 GB of working set on the current laptop. Use a hosted preview for manual login and visual checks.
The bounded `pnpm check:dev-memory` diagnostic is reserved for explicitly approved memory work and
always stops its temporary server.

## Browser Verification Boundary

Playwright is not part of the default local workflow and must not be paired with a persistent local
`next dev` process on this machine. A bounded hosted-browser acceptance journey is allowed when the
required session is available and the scope, screenshots, and stop condition are explicit.

See [resource safety policy](../RESOURCE_SAFETY_POLICY.md).

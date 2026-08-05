# Resource Safety Policy

This project must not use local verification steps that can spike CPU, RAM, or laptop thermals.

Reason:

- Local Playwright browser automation against `next dev` caused severe memory pressure.
- The likely failure mode is high RAM usage, CPU load, and thermal stress from browser automation plus framework compilation.
- This machine is a development laptop, not an isolated CI runner.

Allowed local checks:

- Small unit/component tests.
- Static checks.
- Type checks.
- Lightweight API health/readiness checks.
- One bounded `pnpm check:dev-memory` diagnostic only after explicit approval.
- Docker/Compose config checks that do not start heavy services unless explicitly approved.

Allowed hosted-browser exception:

- One explicitly approved in-app browser session against the deployed Vercel application.
- Reuse one existing browser and one tab; do not start a local Next.js server.
- Keep the pass targeted to navigation, accessibility semantics, responsive overflow, and critical
  workflow smoke checks.
- Do not record video or traces, open multiple browsers, or repeat the pass as a loop.

Allowed commands:

- `pnpm test`
- `pnpm lint`
- `pnpm typecheck`
- `pnpm build` only when a production bundle is truly needed.
- Backend unit/contract/integration tests.
- `docker compose config --quiet`
- `GET /health` or `GET /ready` after a backend is already running.

Blacklisted local checks:

- Standalone local Playwright.
- Local browser E2E.
- Automated Chromium/WebKit/Firefox runs.
- Unapproved `pnpm dev` or other persistent frontend development servers.
- Automated browser runs against `next dev`.
- Turbopack/browser verification loops.
- Load tests, stress tests, concurrency tests, benchmark loops, or repeated watch-mode verification.
- Any test command that starts multiple browsers, multiple dev servers, or multiple heavy workers locally.

Operational rule:

- If fan speed, laptop heat, CPU, or RAM spikes noticeably, stop the command and mark the check as unsafe rather than retrying.
- `pnpm dev` fails closed unless `SUPPORT_COPILOT_ALLOW_LOCAL_DEV=1` is set after explicit approval.
- `pnpm test` is pinned to one Vitest worker; `pnpm test:watch` fails closed.
- Prefer a hosted preview for authentication and visual acceptance; local Webpack compilation of the
  Clerk sign-in route needs about 1 GB of working set on this machine.
- Prefer reviewable evidence notes over heavy verification.
- Heavy verification may only run later in isolated CI/container or on a separate machine with
  explicit approval. The bounded hosted-browser exception above is not authorization for a local
  browser suite.

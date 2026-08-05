# Local E2E Blacklist

Playwright browser E2E is disabled for this local project workflow.

Reason:

- `next dev` with Turbopack exhausted Node memory during local Playwright runs.
- The run caused severe machine instability.
- The likely local impact is excessive CPU, RAM, and thermal load on the laptop.
- The current frontend sprint can be verified with unit/component tests, lint, and typecheck.

For the broader project rule, see `../RESOURCE_SAFETY_POLICY.md`.

Allowed local checks:

- `pnpm test`
- `pnpm lint`
- `pnpm typecheck`

Do not run locally:

- `pnpm test:e2e`
- `pnpm exec playwright test`
- any command that starts Playwright browser automation against `next dev`
- any browser automation, load test, stress test, or worker-heavy verification that can spike CPU, RAM, or thermals

Hosted exception:

- After an explicit user approval, one existing in-app browser tab may inspect the deployed Vercel
  application.
- Do not start `next dev`, install or launch a standalone browser runner, record video or traces, or
  repeat the inspection as a loop.
- Stop immediately if CPU, RAM, fan speed, or temperature rises noticeably.

If E2E is needed later, run it only in an isolated CI/container or a separate machine with explicit approval.

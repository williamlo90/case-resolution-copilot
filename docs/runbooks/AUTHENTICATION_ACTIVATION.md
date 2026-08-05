# Authentication Activation

Status: Clerk production sign-in activated and manually verified; Team invitation synchronization
is implemented in the release candidate but still needs post-deployment evidence

## Current Boundary

- Clerk owns sign-in, session lifecycle, account recovery, and restricted account access.
- The backend owns organizations, memberships, roles, permissions, and audit records.
- Clerk Organizations is intentionally disabled.
- Next.js protects application routes only when
  `SUPPORT_COPILOT_AUTH_MODE=provider`.
- The frontend sends a Clerk session token as `Authorization: Bearer ...`.
- FastAPI verifies the Clerk PEM signature, time bounds, issuer shape, session identifier, pending
  status, and any present authorized-party claim. It reads only the token subject for identity.
- Provider-mode CORS does not allow the deterministic `X-Actor-ID` or `X-Actor-Role` headers.
- The token subject is resolved through `memberships.subject_id`. Role and organization claims from
  the browser or Clerk are not authority.
- Team invitations are created in the internal database and Clerk as one compensated operation.
  After an invited account verifies its email, the first authenticated request claims exactly one
  matching pending internal invitation. The database remains the source of truth for role access.
- Incomplete provider configuration fails with `503` in development/test. Production configuration
  rejects missing database or Clerk settings at startup.

## Credential Files

Add real values only to ignored local files or a deployment secret manager. Never put them in Git,
captured command output, screenshots, or chat.

Frontend `frontend/.env.local`:

```dotenv
SUPPORT_COPILOT_AUTH_MODE=provider
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=replace_locally
CLERK_SECRET_KEY=replace_locally
NEXT_PUBLIC_CLERK_KEYLESS_DISABLED=true
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/invite
NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL=/cases
NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL=/cases
```

Backend `backend/.env`:

```dotenv
SUPPORT_COPILOT_AUTH_MODE=provider
SUPPORT_COPILOT_CLERK_SECRET_KEY=replace_locally
SUPPORT_COPILOT_CLERK_JWT_KEY="replace_locally"
SUPPORT_COPILOT_CLERK_AUTHORIZED_PARTIES=http://127.0.0.1:3000,http://localhost:3000
```

The JWT public key may be stored as a quoted value with literal `\n` separators. The backend
normalizes those separators before verification. Authorized parties must be the exact frontend
origins used by the browser. Production accepts HTTPS authorized parties only. Keyless Clerk mode is
disabled so a missing key fails clearly instead of creating an unintended temporary application.

## Link The First Account

Clerk proves who the user is, but it does not grant workspace access. Copy the non-secret Clerk User
ID, which starts with `user_`, from Clerk Dashboard -> Users. Then run the guarded linker against the
existing local membership:

```powershell
cd backend
.venv\Scripts\python.exe -m scripts.link_clerk_identity `
  --organization ORG-0001 `
  --member USR-0003 `
  --subject user_replace_me
```

The first command is a dry run. If the reported member and workspace are correct:

```powershell
.venv\Scripts\python.exe -m scripts.link_clerk_identity `
  --organization ORG-0001 `
  --member USR-0003 `
  --subject user_replace_me `
  --apply
```

The linker rejects production use, unknown records, malformed Clerk subjects, and a subject already
linked elsewhere. The applied change is audited without storing a credential.

## Activation Sequence

1. Keep Clerk Organizations off and Restricted mode on.
2. Add the frontend and backend values locally.
3. Confirm the database is migrated and contains the intended organization and member.
4. Link the invited Clerk user to exactly one active internal membership.
5. Start the API and frontend only when a manual preview is explicitly requested.
6. Sign in with the invited account and verify `/cases` loads the matching internal role.
7. Verify sign-out, session expiry, denied membership, role denial, and provider outage.
8. Test specialist, supervisor, administrator, and auditor accounts separately before pilot use.

## Production Evidence

On 28 July 2026, the invited administrator completed Clerk sign-in, new-device email verification,
and redirect to the protected `/cases` route on Vercel. Catch-all sign-in routing and the Clerk
application URL configuration were corrected to prevent signed-in redirect loops.

This evidence covers the primary administrator happy path. It does not yet cover all four roles,
session expiry, denied membership, or an identity-provider outage.

## Honest Failure States

| Condition | API result | User outcome |
| --- | --- | --- |
| Missing or invalid Clerk session | `401 authentication_required` | Sent to sign in |
| Valid Clerk user without active membership | `403 workspace_access_denied` | Workspace access guidance |
| More than one active membership | `409 workspace_selection_required` | Workspace selection guidance |
| Clerk or membership lookup unavailable | `503 authentication_unavailable` | Honest retryable failure |

There is no fallback from provider mode to deterministic actors.

## Team Invitation Workflow

Migration `20260728_0016` adds the Clerk invitation reference to the internal invitation record.
Creating an invitation from **Team** asks Clerk to send the email and rolls back the database record
if delivery setup fails. Revocation removes internal access first; a Clerk revocation failure is
reported honestly, while first-login provisioning still rejects the revoked internal invitation.

Clerk transfers application-invitation metadata to the new user's public metadata after sign-up.
The backend uses that metadata only as a matching hint. A verified email may fall back to exactly
one pending invitation so stale metadata from an older invitation does not block a legitimate
re-invite. Multiple matches are denied. See the
[Clerk invitation contract](https://clerk.com/docs/reference/backend/invitations/create-invitation).

This workflow is implemented and covered by deterministic tests. Do not call it production-proven
until a real Team invite, email acceptance, first login, role denial, and revocation have passed
after deployment.

## Required Evidence

- Valid identity reaches only its linked organization.
- Cross-tenant and role-escalation attempts fail closed.
- Client role, organization, and `X-Actor-ID` values cannot grant provider-mode authority.
- Expired, malformed, wrong-party, and non-session tokens are rejected. Networkless verification
  cannot observe revocation after issuance, so a revoked token remains valid only until its short
  Clerk expiry unless an online session check is added.
- Sign-out removes access and provider outage never enables demo fallback.
- Team invite, acceptance, re-invite, and revocation preserve one internal source of role authority.
- Logs and audit records contain no token, cookie, private key, or secret value.

## Resource Boundary

Authentication verification on this machine uses sequential unit, contract, lint, type, and manual
checks. It does not authorize Playwright, local browser automation, Turbopack, a local production
build, Docker, load tests, watch processes, or background workers.

## Rollback

Do not switch production to deterministic actors. On activation failure, stop provider traffic or
restore the prior provider-capable release, preserve audit evidence, and keep consequential commands
unavailable until identity is trustworthy.

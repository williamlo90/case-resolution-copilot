# Wave 2B Master Plan

## Objective

Validate the Wave 2A framework integration with one bounded synthetic case.

This phase must prove that:

- the production LangGraph path still works;
- LangChain formatting and schema support work where integrated;
- the CrewAI prototype runs in isolation;
- the AutoGen prototype runs in isolation;
- every output preserves facts, safety boundaries, approval requirements, and evidence discipline.

This is not a learning module, benchmark leaderboard, or refactor phase.

## Strict Scope

- Do not build before-and-after learning material.
- Do not create a new application or rewrite the production backend.
- Do not run a browser, Playwright, local UI server, load test, or broad evaluation suite.
- Do not use private or personal data.
- Do not present CrewAI or AutoGen as production runtime paths.
- Do not commit secrets or expose API keys in output, documentation, or chat.
- Run all framework paths serially.

## Startup Checks

- Inspect repository instructions and current Wave 2A changes.
- Identify existing validation commands.
- Confirm required environment variable names without printing values.
- Confirm whether bounded OpenAI calls can run.
- Run a lightweight regression check first.

## Validation Case

Use exactly one synthetic customer-support case for every path.

The case must:

- contain no personal data;
- require evidence-aware summarization, risk classification, a next action, and human approval;
- define expected schema, facts, evidence boundary, and safety behavior before execution.

## Framework Runs

### Production path

- LangGraph orchestration;
- LangChain prompt and schema formatting;
- OpenAI structured response;
- one bounded case.

### CrewAI prototype

- analyst role;
- safety reviewer role;
- no more than three iterations per agent;
- same synthetic case;
- isolated from production wiring.

### AutoGen prototype

- one structured conversational agent;
- no more than one tool iteration;
- same synthetic case;
- isolated from production wiring.

## Scoring

For each path, record:

- output schema valid;
- facts preserved;
- evidence not fabricated;
- approval requirement preserved;
- no claim that an external action already executed;
- latency, when available;
- model calls, when available;
- token usage and cost, when the provider exposes them;
- failure handling behavior;
- practical usefulness notes.

## Evidence

Create only:

- `docs/evidence/framework-validation.json`;
- `docs/evidence/framework-validation.md`.

Keep both concise. Do not turn them into tutorial material or marketing copy.

## Fix Rule

Fix only material findings:

- schema mismatch;
- unsafe external-action wording;
- fabricated evidence;
- broken default LangGraph path;
- prototype dependency/runtime failure;
- secret leakage;
- misleading documentation.

Do not perform unrelated cleanup or cosmetic refactors.

## Review And Verification

After the runs and material fixes:

- run the closest backend regression gate;
- run frontend checks only if frontend source files changed;
- scan for secrets and inspect the final diff;
- obtain an independent reviewer verdict.

Allowed reviewer verdicts:

- Accept
- Accept with small fixes
- Needs revision
- Reject

## Delivery

When validation passes and the reviewer accepts:

1. Commit Wave 2A and 2B together with message `Wave 2 framework orchestration validation`.
2. Push once to the configured repository remote.
3. Check the connected Vercel deployment status.
4. Report validated claims and explicit non-claims.

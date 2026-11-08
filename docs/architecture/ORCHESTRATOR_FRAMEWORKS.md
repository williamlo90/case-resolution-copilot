# Orchestrator Framework Boundary

Case Resolution Copilot uses frameworks according to their fit, not as interchangeable labels.
The production workflow remains deterministic around authority, policy, risk, and side effects.

## Runtime Map

| Framework | Role | Runtime status | Evidence boundary |
| --- | --- | --- | --- |
| LangGraph | Runs and verifies the governed decision checkpoint chain | Production default | Unit and contract tested in the normal backend suite |
| LangChain Core | Builds the bounded OpenAI narrative prompt and schema-format instructions | Production utility on the optional OpenAI path | Unit tested without a paid model call |
| CrewAI | Compares an analyst/reviewer role split | Isolated optional prototype | Adapter contract and one bounded live test case validated |
| AutoGen | Compares a bounded structured conversational agent | Isolated optional prototype | Adapter contract and one bounded live test case validated |

Only LangGraph is wired by `app.main`. CrewAI and AutoGen cannot be selected through application
settings and do not receive raw case workspaces. Their adapters accept the same minimized control
record used for safe narrative drafting and require the same `DecisionNarrative` output contract.

## Why This Shape

LangGraph fits the main workflow because the application needs named checkpoints, explicit state,
and fail-closed validation around a deterministic decision engine. Business rules remain in the
domain engine so the graph does not become a god object.

LangChain Core removes prompt and schema-formatting boilerplate from the optional OpenAI narrative
gateway. Its portable parser helper is contract-tested but the OpenAI Responses SDK performs the
runtime Pydantic parsing. LangChain does not own policy selection, approval, risk, or execution.

CrewAI is useful here only as a role-based experiment: one agent drafts and another checks safety.
AutoGen is useful only as a conversational structured-output experiment. Neither design currently
improves the validated production path enough to justify its dependency and operational cost.

## Commands

The framework inventory performs no model call:

```powershell
cd backend
uv run python -m scripts.inspect_orchestrator_frameworks
```

Optional demos are deliberately resolved outside the production dependency lock. `uv run` creates
an ephemeral environment for the selected command:

```powershell
uv run --with-requirements examples/orchestrator_prototypes/requirements.txt `
  python -m scripts.inspect_orchestrator_frameworks --run-prototype crewai
```

After setting `SUPPORT_COPILOT_OPENAI_API_KEY` in the local process, substitute `autogen` for
`crewai` to run the other prototype:

```powershell
uv run --with-requirements examples/orchestrator_prototypes/requirements.txt `
  python -m scripts.inspect_orchestrator_frameworks --run-prototype autogen
```

These commands incur provider usage. Their output reports contract validity and elapsed time; it
keeps the generated customer narrative private.

The combined serial validation command and sanitized result are documented in
[`framework-validation.md`](../evidence/framework-validation.md). The recorded run covers one
test case to verify contract compatibility.

## Framework Roles

LangGraph coordinates the default decision path. LangChain Core supplies prompt templates and
schema-formatting utilities. CrewAI and AutoGen provide isolated comparison prototypes.

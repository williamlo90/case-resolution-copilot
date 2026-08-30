# Framework Validation

- Case: `CS-2047` (synthetic)
- Result: `3/3` paths passed
- Execution: serial and bounded
- Production runtime: LangGraph with LangChain formatting
- Prototype runtimes: CrewAI and AutoGen

| Path | Role | Schema | Facts | Evidence | Approval | No false execution | Latency | Result |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- |
| langgraph_langchain | production | pass | pass | pass | pass | pass | 3321 ms | passed |
| crewai | prototype | pass | pass | pass | pass | pass | 8885 ms | passed |
| autogen | prototype | pass | pass | pass | pass | pass | 2824 ms | passed |

## Interpretation

The run validates contract and safety behavior on one representative case. It does not establish framework superiority or production readiness for the prototypes.

## Non-claims

- CrewAI and AutoGen are isolated prototypes, not production runtime paths.
- This bounded run is framework validation, not a quality leaderboard.
- No external refund or customer communication was executed.

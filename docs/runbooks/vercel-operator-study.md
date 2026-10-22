# Hosted operator study

The opt-in study station runs in branch-scoped Vercel Preview deployments with a dedicated Neon
database. Operators need a browser and their existing Clerk account. Docker, WSL and local servers
are not part of this workflow.

## Engineer preparation

1. Freeze the input-only primary packet, order, practice packet and separate withheld labels locally.
   Keep these files, credentials and raw operator observations ignored by Git.
2. Create a fresh database named `operator_study_*` on the designated disposable Neon endpoint.
   Run `backend/scripts/bootstrap_operator_study.py` from `backend` with the existing operator's
   verified Clerk subject and the two input packet paths. It refuses to reset an initialized study.
3. In the backend project's **specific Preview branch**, configure the new database URL,
   `SUPPORT_COPILOT_OPERATOR_STUDY_ENABLED=true`,
   `SUPPORT_COPILOT_OPERATOR_STUDY_DATABASE_SCOPE=disposable`, and
   `SUPPORT_COPILOT_OPERATOR_STUDY_OWNER_SUBJECT`. Retain provider authentication. Disable connected
   inbox scheduling, push and external writeback. Match the frozen model/retrieval profile.
4. In the frontend's same Preview branch, enable the study and point
   `SUPPORT_COPILOT_API_INTERNAL_URL` at that backend deployment. Retain Clerk and deployment
   protection. Restrict backend authorized parties to the actual frontend origin.
5. Verify source revision, database readiness, unauthorized rejection, durable duplicate handling,
   manual recommendation isolation, refresh recovery, and the practice workflow. Engineering
   `practice`, operator `training`, and human `primary` packets have separate cases and targets.
6. Record acceptance evidence and only then enable the primary session. Do not start primary
   cases during engineering acceptance. Pin the tested deployment and runtime for the study.

## Operator flow

Open `/study` for training. Read Ticket, CRM, Business Records and Policy, then submit the decision.
In assisted mode generate and check the Decision Brief first. In manual mode enter your own
decision and parameters. Both modes require the same evidence selection and downstream work.

For a resolution: Approve → Execute → Inspect Read-back → Record Communication → Close → Finish.
For an escalation: Acknowledge → Record Communication → Finish. Acknowledge and review roles are
simulated by the same operator; no customer email or live payment/identity system is contacted.

Use `/study?packet=primary` for the frozen 24-task order after training. Timer starts when the
source task is first returned and continues through refresh or interruption. Save unfinished
tasks with Finish; do not silently restart them. Take breaks between tasks, with at least ten
minutes after each block of six. Export the JSON evidence at the end.

## Evidence and interpretation

PostgreSQL `clock_timestamp()` supplies timing across serverless instances. Session progress,
request UUIDs, receipts and independently persisted synthetic target state survive cold starts.
The station uses real product proposal, review, action and resolution APIs; internal role context
exists only on the server. Study routes are absent by default and refuse production activation.

Score only after all scheduled primary observations are exported and sealed. Quality uses all
12 scheduled cases per condition. A handling-time claim needs at least eight pairs with correct,
equivalent outcomes; preserve zero/negative reductions. Engineering practice is never operator
timing. The current controlled profile uses the deterministic Copilot engine; a hosted run does
not establish live-LLM or real-provider performance.

Latency samples measure internal product API calls. Follow-up is a separately marked virtual
7/30-day replay with actual event timestamps preserved. Runtime cost remains unmeasured until a
reconciled cost ledger is supplied. Keep these scopes attached to derived claims.

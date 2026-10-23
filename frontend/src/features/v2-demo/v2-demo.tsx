"use client";

import { useState } from "react";
import {
  commandV2Demo,
  createV2Demo,
  loadV2Demo,
} from "@/app/(operations)/_actions/v2-demo";
import {
  scenarios,
  type DemoCommand,
  type DemoRole,
  type DemoScenario,
  type DemoSession,
  type DemoView,
} from "./contract";

const button =
  "rounded-md border border-line bg-white px-3 py-2 text-sm font-medium hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed";
const panel = "rounded-lg border border-line bg-white p-5";
const input = "w-full rounded-md border border-line bg-white px-3 py-2 text-sm";
type Command = DemoCommand["command"];

export function V2Demo({
  sessions: initialSessions,
}: {
  sessions: DemoSession[];
}) {
  const [sessions, setSessions] = useState(initialSessions);
  const [view, setView] = useState<DemoView | null>(null);
  const [scenario, setScenario] = useState<DemoScenario>("verified_reopen");
  const [role, setRole] = useState<DemoRole>("specialist");
  const [reason, setReason] = useState("");
  const [reference, setReference] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState(false);
  // Keep the creation key through an ambiguous response; retry cannot create a second tenant.
  const [creationKey, setCreationKey] = useState<string | null>(null);

  async function accept(
    work: () => Promise<{
      data: DemoView | null;
      error: string | null;
      code: string | null;
    }>,
    success: string,
  ) {
    setBusy(true);
    setNotice("Working… Keep this page open.");
    try {
      const result = await work();
      if (result.data) {
        if (result.data.session.session_id !== view?.session.session_id) {
          setRole("specialist");
          setReason("");
          setReference("");
        }
        setView(result.data);
        setSessions((items) => [
          result.data!.session,
          ...items.filter(
            (s) => s.session_id !== result.data!.session.session_id,
          ),
        ]);
      }
      setError(Boolean(result.error));
      setNotice(result.error ? `${result.error} (${result.code})` : success);
      return result;
    } finally {
      setBusy(false);
    }
  }
  async function create() {
    const key = creationKey ?? crypto.randomUUID();
    setCreationKey(key);
    const result = await accept(
      () => createV2Demo(scenario, key),
      "Fresh synthetic session created. Start by reading the case and SOP.",
    );
    if (result.data) {
      setCreationKey(null);
      setReason("");
      setReference("");
      setRole("specialist");
    }
  }
  async function run(command: Command) {
    if (!view) return;
    let version = view.case.version;
    if (["reserve", "approve"].includes(command))
      version = view.review?.review.version ?? 1;
    if (["execute", "reconcile"].includes(command))
      version = view.action?.action.version ?? 1;
    if (["publish_revision", "rollback"].includes(command))
      version = view.policy.policy.version;
    await accept(
      () =>
        commandV2Demo(view.session.session_id, {
          command,
          role,
          expected_version: version,
          command_id: crypto.randomUUID(),
          snapshot_fingerprint:
            view.review?.review.snapshot_fingerprint ?? null,
          resource_id: ["reserve", "approve"].includes(command)
            ? (view.review?.review.id ?? null)
            : (view.action?.action.id ?? null),
          expected_proposal_version: view.brief?.proposal.version ?? null,
          reason:
            reason.trim() ||
            "Operator requested this synthetic walkthrough step.",
          reference: reference.trim() || null,
        }),
      `${command.replaceAll("_", " ")} recorded. Inspect the updated state below.`,
    );
  }
  function commandButton(command: Command, label: string, disabled = false) {
    return (
      <button
        type="button"
        className={button}
        disabled={busy || disabled}
        onClick={() => void run(command)}
      >
        {label}
      </button>
    );
  }
  function exportTrace() {
    if (!view) return;
    const url = URL.createObjectURL(
      new Blob(
        [
          JSON.stringify(
            {
              pack: "v2-interactive-1",
              scope: "single_operator_synthetic_walkthrough",
              ...view,
            },
            null,
            2,
          ),
        ],
        { type: "application/json" },
      ),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `${view.session.session_id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }
  const task = scenarios.find((s) => s.id === view?.session.scenario);
  const verified =
    view?.lifecycle.events.filter((e) => e.kind === "action_verified") ?? [];
  return (
    <div className="space-y-5 p-5 lg:p-8">
      <header>
        <p className="text-xs font-semibold uppercase tracking-wide text-teal-700">
          Case Resolution · V2
        </p>
        <h1 className="mt-1 text-2xl font-semibold">
          Interactive resolution demo
        </h1>
        <p className="mt-2 max-w-3xl text-sm text-secondary">
          Follow the full lifecycle with a persistent synthetic target. Each
          session is isolated from your normal cases and policies.
        </p>
      </header>
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
        Synthetic walkthrough · one operator switches simulated roles. No real
        payments or email delivery. This is a functional demonstration, not a
        timing benchmark.
      </div>
      <section className={panel} aria-label="Demo sessions">
        <div className="flex flex-wrap items-end gap-3">
          <label className="min-w-64 flex-1 text-sm font-medium">
            Choose scenario
            <select
              className={`${input} mt-1`}
              value={scenario}
              disabled={busy || creationKey !== null}
              onChange={(e) => setScenario(e.target.value as DemoScenario)}
            >
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.title}
                </option>
              ))}
            </select>
          </label>
          <button
            className={`${button} bg-teal-700 text-white hover:bg-teal-800`}
            disabled={busy}
            onClick={() => void create()}
          >
            {creationKey ? "Retry session creation" : "Create fresh session"}
          </button>
        </div>
        {sessions.length > 0 && (
          <label className="mt-4 block text-sm">
            Resume a saved session
            <select
              className={`${input} mt-1`}
              disabled={busy}
              value={view?.session.session_id ?? ""}
              onChange={(e) => {
                if (e.target.value)
                  void accept(
                    () => loadV2Demo(e.target.value),
                    "Persisted session reloaded.",
                  );
              }}
            >
              <option value="">Choose a session</option>
              {sessions.map((s) => (
                <option value={s.session_id} key={s.session_id}>
                  {scenarios.find((x) => x.id === s.scenario)?.title} ·{" "}
                  {s.session_id}
                </option>
              ))}
            </select>
          </label>
        )}
      </section>
      <p
        role="status"
        aria-live="polite"
        className={`min-h-6 text-sm ${error ? "text-red-800" : "text-teal-800"}`}
      >
        {notice}
      </p>
      {view && (
        <>
          <section className={panel}>
            <div className="flex flex-wrap justify-between gap-3">
              <div>
                <h2 className="font-semibold">{task?.title}</h2>
                <p className="mt-1 text-sm text-secondary">{task?.task}</p>
                <p className="mt-2 font-mono text-xs">
                  {view.session.session_id} · {view.case.status} · case v
                  {view.case.version}
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  className={button}
                  disabled={busy}
                  onClick={() =>
                    void accept(
                      () => loadV2Demo(view.session.session_id),
                      "Fresh database read completed.",
                    )
                  }
                >
                  Reload saved state
                </button>
                <button
                  className={button}
                  disabled={busy}
                  onClick={exportTrace}
                >
                  Download trace
                </button>
              </div>
            </div>
          </section>
          <div className="grid items-start gap-5 xl:grid-cols-2">
            <section className={panel}>
              <h2 className="font-semibold">Case & source evidence</h2>
              <p className="mt-3 text-sm">{view.case.request}</p>
              {view.case.records.map((r) => (
                <div key={r.id} className="mt-4">
                  <p className="font-mono text-xs text-secondary">
                    {r.reference}
                  </p>
                  <dl className="mt-2 space-y-1 text-sm">
                    {Object.entries(r.fields).map(([k, v]) => (
                      <div key={k} className="grid grid-cols-2 gap-3">
                        <dt className="break-words text-secondary">
                          {k.replaceAll("_", " ")}
                        </dt>
                        <dd className="break-all">{v}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              ))}
            </section>
            <section className={panel}>
              <h2 className="font-semibold">
                Published SOP · revision {view.policy.policy.current_version}
              </h2>
              {view.policy.versions.map((v) => (
                <details
                  key={v.version}
                  className="mt-3 rounded border border-line p-3"
                  open={v.version === view.policy.policy.current_version}
                >
                  <summary className="cursor-pointer text-sm font-medium">
                    Revision {v.version} · {v.status} ·{" "}
                    {v.effective_from
                      ? new Date(v.effective_from).toLocaleString()
                      : "not effective"}
                  </summary>
                  <pre className="mt-3 whitespace-pre-wrap break-words text-xs leading-relaxed">
                    {v.source_text}
                  </pre>
                </details>
              ))}
            </section>
          </div>
          <section className={panel}>
            <h2 className="font-semibold">Operator controls</h2>
            <p className="mt-1 text-sm text-secondary">
              Select the simulated role for each step. Specialist prepares and
              submits; reviewer reserves, approves, executes and closes; policy
              manager publishes SOP revisions. Denied commands remain visible in
              the trace.
            </p>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <label className="text-sm">
                Simulated role
                <select
                  className={`${input} mt-1`}
                  value={role}
                  disabled={busy}
                  onChange={(e) => setRole(e.target.value as DemoRole)}
                >
                  <option value="specialist">Specialist</option>
                  <option value="reviewer">
                    Reviewer (administrator authority)
                  </option>
                  <option value="policy_manager">Policy manager</option>
                </select>
              </label>
              <label className="text-sm">
                Decision / step reason
                <input
                  className={`${input} mt-1`}
                  value={reason}
                  disabled={busy}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Explain your decision"
                />
              </label>
              <label className="text-sm">
                Communication / new evidence reference
                <input
                  className={`${input} mt-1`}
                  value={reference}
                  disabled={busy}
                  onChange={(e) => setReference(e.target.value)}
                  placeholder="e.g. SIM-MESSAGE-01 or NEW-EVIDENCE-01"
                />
              </label>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {commandButton(
                "generate",
                "1. Generate Decision Brief",
                view.case.status !== "investigating",
              )}
              {commandButton(
                "submit",
                "2. Submit frozen brief",
                view.brief?.proposal.state !== "ready_for_review",
              )}
              {commandButton(
                "reserve",
                "3. Reserve review",
                view.review?.review.status !== "pending",
              )}
              {commandButton(
                "approve",
                "4. Approve snapshot",
                view.review?.review.status !== "reserved" ||
                  reason.trim().length < 3,
              )}
              {commandButton("execute", "5. Execute / try again", !view.action)}
              {commandButton(
                "reconcile",
                "6. Read back & reconcile",
                !view.action,
              )}
              {commandButton(
                "close",
                "7. Close with proof",
                !view.action ||
                  view.case.status === "completed" ||
                  !reference.trim() ||
                  reason.trim().length < 3,
              )}
              {commandButton(
                "reopen",
                "8. Reopen with new evidence",
                view.case.status !== "completed" ||
                  !reference.trim() ||
                  reason.trim().length < 3,
              )}
            </div>
            {view.session.scenario === "sop_revision" && (
              <div className="mt-4 flex flex-wrap gap-2 border-t border-line pt-4">
                {commandButton(
                  "publish_revision",
                  "Publish SOP v2 · cap USD 100",
                  view.policy.policy.current_version !== 1,
                )}
                {commandButton(
                  "rollback",
                  "Publish rollback v3 · cap USD 500",
                  view.policy.policy.current_version !== 2,
                )}
              </div>
            )}
            <details className="mt-4 text-sm">
              <summary className="cursor-pointer">
                Optional escalation handoff
              </summary>
              <div className="mt-3 flex flex-wrap gap-2">
                {commandButton(
                  "route_escalation",
                  "Route to simulated reviewer",
                )}
                {commandButton(
                  "acknowledge",
                  "Acknowledge latest routing event",
                  !reference.trim(),
                )}
              </div>
              <p className="mt-2 text-secondary">
                For acknowledgement, copy the routing event ID from the
                lifecycle below into the reference field. Only its assigned
                recipient can acknowledge.
              </p>
            </details>
          </section>
          {view.brief && (
            <section className={panel}>
              <h2 className="font-semibold">
                Decision Brief · proposal v{view.brief.proposal.version}
              </h2>
              <p className="mt-2 text-xs text-secondary">
                {view.brief.proposal.state} ·{" "}
                {view.brief.proposal.model_version} · evidence:{" "}
                {view.brief.proposal.evidence_ids.join(", ")}
              </p>
              <p className="mt-3 font-medium">{view.brief.proposal.outcome}</p>
              <p className="mt-2 whitespace-pre-wrap text-sm">
                {view.brief.proposal.rationale}
              </p>
              <ul className="mt-3 space-y-2 text-sm">
                {view.brief.facts.map((fact, i) => (
                  <li key={i}>
                    {fact.statement}
                    <span className="block text-xs text-secondary">
                      Source: {fact.source}
                    </span>
                  </li>
                ))}
              </ul>
              {view.brief.missing_information.map((g) => (
                <p className="mt-2 text-sm text-amber-900" key={g.label}>
                  {g.label}: {g.description}
                </p>
              ))}
              <details className="mt-4 text-sm">
                <summary className="cursor-pointer">
                  Suggested customer response (not sent)
                </summary>
                <p className="mt-2 font-medium">
                  {view.brief.response_draft.subject}
                </p>
                <p className="mt-2 whitespace-pre-wrap">
                  {view.brief.response_draft.body}
                </p>
              </details>
            </section>
          )}
          <div className="grid items-start gap-5 xl:grid-cols-2">
            <section className={panel}>
              <h2 className="font-semibold">Review & action authority</h2>
              {view.review ? (
                <>
                  <p className="mt-3 text-sm">
                    Review: {view.review.review.status} · v
                    {view.review.review.version} · snapshot{" "}
                    {view.review.review.snapshot_freshness.status}
                  </p>
                  <p className="mt-1 text-sm text-secondary">
                    Submitted by {view.review.review.submitted_by.name}.{" "}
                    {view.review.review.snapshot_freshness.reason}
                  </p>
                  <p className="mt-2 break-all font-mono text-xs">
                    Snapshot: {view.review.review.snapshot_fingerprint}
                  </p>
                  {view.review.evidence.map((e) => (
                    <blockquote
                      className="mt-3 border-l-2 border-teal-600 pl-3 text-sm"
                      key={e.id}
                    >
                      <p className="font-medium">
                        {e.citation} · SOP v{e.policy_version}
                      </p>
                      <p className="mt-1 text-secondary">{e.excerpt}</p>
                    </blockquote>
                  ))}
                  {view.review.decision_history.map((d, i) => (
                    <p key={i} className="mt-2 text-sm">
                      {d.actor.name}: {d.reason}
                    </p>
                  ))}
                </>
              ) : (
                <p className="mt-3 text-sm text-secondary">
                  No review submitted yet.
                </p>
              )}
              {view.action && (
                <div className="mt-4 border-t border-line pt-4">
                  <p className="text-sm font-medium">
                    Action: {view.action.action.status} · attempts{" "}
                    {view.action.action.attempt_count}
                  </p>
                  <p className="mt-1 text-sm">
                    Blocker: {view.action.execution_blocker ?? "none"}
                  </p>
                  <p className="mt-2 break-all font-mono text-xs">
                    Operation: {view.action.idempotency_key}
                  </p>
                  <p className="mt-2 text-sm">
                    Receipt: {view.action.receipt?.external_reference ?? "none"}
                  </p>
                  <p className="mt-2 text-sm">{view.action.observed_outcome}</p>
                  <pre className="mt-3 whitespace-pre-wrap break-all text-xs">
                    {JSON.stringify(view.action.typed_parameters, null, 2)}
                  </pre>
                </div>
              )}
            </section>
            <section className={panel}>
              <h2 className="font-semibold">Independent synthetic target</h2>
              <p className="mt-3 text-lg font-semibold">
                {view.target.effect_count} effect(s) · {verified.length}{" "}
                verified event(s)
              </p>
              <p className="mt-1 text-sm text-secondary">
                Read from database ledger on every request. Reloading creates a
                fresh gateway; it does not repeat the action.
              </p>
              <pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-all text-xs">
                {JSON.stringify(view.target, null, 2)}
              </pre>
            </section>
          </div>
          <section className={panel}>
            <h2 className="font-semibold">Lifecycle & command trace</h2>
            <ol className="mt-3 space-y-3">
              {view.lifecycle.events.map((e) => (
                <li
                  key={e.id}
                  className="rounded border border-line p-3 text-sm"
                >
                  <p className="font-medium">
                    {e.kind} · {new Date(e.at).toLocaleString()}
                  </p>
                  <p className="mt-1 break-all font-mono text-xs">
                    {e.id}
                    {e.previous_event_id
                      ? ` → previous ${e.previous_event_id}`
                      : ""}
                  </p>
                  <details className="mt-2">
                    <summary className="cursor-pointer">Event proof</summary>
                    <pre className="mt-2 whitespace-pre-wrap break-all text-xs">
                      {JSON.stringify(e.data, null, 2)}
                    </pre>
                  </details>
                </li>
              ))}
            </ol>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <caption className="mb-2 text-left text-xs text-secondary">
                  Actual operator commands, including blocked attempts
                </caption>
                <thead>
                  <tr>
                    <th className="py-2">Simulated role</th>
                    <th>Command</th>
                    <th>Result</th>
                  </tr>
                </thead>
                <tbody>
                  {view.observations.map((o, i) => (
                    <tr key={i} className="border-t border-line">
                      <td className="py-2">{o.simulated_role}</td>
                      <td>{o.command}</td>
                      <td>{o.outcome}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}

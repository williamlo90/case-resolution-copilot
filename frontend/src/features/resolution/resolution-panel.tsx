"use client";

import { useActionState, useState, useRef } from "react";
import { CheckCircle2, Clock3, History, ShieldCheck } from "lucide-react";
import { WorkspaceLink as Link } from "@/components/navigation/workspace-link";
import { CommandStatus } from "@/components/ui/command-status";
import { initialCommandState, type ServerCommand } from "@/data/commands/command-state";
import type { Resolution } from "./contract";
import { ProofSummary } from "./proof-summary";
import { resolutionHeading } from "./presentation";

const labels: Record<string, string> = {
  completed: "Case closed", reopened: "Case reopened",
  escalation_routed: "Escalation assigned", escalation_acknowledged: "Escalation accepted",
  action_verified: "Outcome verified", action_observed: "Outcome checked",
};
const inputClass = "w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm text-primary outline-none focus:border-focus";
const buttonClass = "inline-flex min-h-11 items-center justify-center rounded-md bg-action px-4 text-sm font-semibold text-white hover:bg-action-strong disabled:opacity-50";

function ResolutionForm({ kind, action, simulated }: {kind: "completed" | "reopened"; data: Resolution; action: ServerCommand; simulated: boolean}) {
  const commandId = useRef<string | null>(null);
  const [state, formAction, pending] = useActionState(async (previous: typeof initialCommandState, form: FormData) => {
    commandId.current ??= crypto.randomUUID();
    form.set("command_id", commandId.current);
    return action(previous, form);
  }, initialCommandState);
  const [reason, setReason] = useState("");
  const [reference, setReference] = useState("");
  const title = { completed: "Close case", reopened: "Reopen case", escalation_routed: "Assign escalation", escalation_acknowledged: "Accept escalation" }[kind];
  const referenceLabel = kind === "completed"
    ? simulated ? "Simulated customer communication reference" : "Delivered customer communication reference"
    : kind === "reopened" ? "New evidence reference" : "Escalation recipient";
  return <form action={formAction} className="space-y-4">
    <input type="hidden" name="kind" value={kind} />
    <label className="grid gap-2 text-sm font-medium text-primary">Reason
      <textarea name="reason" value={reason} onChange={e => setReason(e.target.value)} required minLength={3} maxLength={1000} className={inputClass + " min-h-24"} placeholder={kind === "reopened" ? "What new information requires investigation?" : "Explain the outcome or next responsibility"} />
    </label>
    <label className="grid gap-2 text-sm font-medium text-primary">{referenceLabel}
      <input name="reference" value={reference} onChange={e => setReference(e.target.value)} required maxLength={200} className={inputClass} placeholder={simulated ? kind === "completed" ? "SIM-MESSAGE-01" : "NEW-EVIDENCE-01" : "Reference to the supporting record"} />
    </label>
    {kind === "completed" ? <p className="text-xs leading-5 text-secondary">{simulated ? "This records a simulated customer notification. No email is sent." : "Confirm the customer was informed. A saved email draft is not proof of delivery."}</p> : null}
    <button disabled={pending || reason.trim().length < 3 || !reference.trim()} className={buttonClass}>{pending ? "Saving…" : title}</button>
    <CommandStatus state={state} />
  </form>;
}

export function ResolutionPanel({ data, commandAction, simulated = false }: { data: Resolution; commandAction?: ServerCommand; simulated?: boolean }) {
  const complete = data.status === "completed";
  const verified = data.closure.eligible;
  const primary: "completed" | "reopened" | undefined = data.available_commands.includes("reopened") ? "reopened"
    : data.available_commands.includes("completed") ? "completed" : undefined;
  return <section aria-label="Case resolution" className="grid gap-8 px-4 py-7 sm:px-6 lg:px-7 xl:grid-cols-[minmax(0,1fr)_360px]">
    <div>
      <div className="flex items-start gap-3">
        {complete || verified ? <CheckCircle2 className="mt-1 text-success" size={24} /> : <Clock3 className="mt-1 text-warning" size={24} />}
        <div><h2 className="text-xl font-semibold text-primary">{resolutionHeading(data)}</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-secondary">{complete ? "The resolution history below preserves the evidence used at closure." : verified ? "Every required action has a matching, current outcome check. Record the customer communication to complete the case." : data.closure.blocker}</p>
        </div>
      </div>
      {data.actions.length ? <div className="mt-6 divide-y divide-border border-y border-border">{data.actions.map(a => <Link key={a.id} href={`/actions/${a.id}`} className="flex items-center justify-between gap-4 py-4 text-sm">
        <span className="font-semibold text-info">View action and verification</span><span className="text-secondary">{a.status.replaceAll("_", " ")}</span>
      </Link>)}</div> : null}
      <h3 className="mt-8 flex items-center gap-2 text-base font-semibold text-primary"><History size={18} />Resolution history</h3>
      {data.events.length ? <ol className="mt-4 space-y-5">{data.events.map(e => <li key={e.id} className="border-l-2 border-border pl-4">
        <p className="text-sm font-semibold text-primary">{labels[e.kind] ?? e.kind.replaceAll("_", " ")}</p>
        <p className="mt-1 text-xs text-secondary">{new Date(e.at).toLocaleString("en-GB", { timeZone: "UTC" }) + " UTC"} · {e.actor_id}</p>
        {typeof e.data.request === "object" && e.data.request !== null && "reason" in e.data.request ? <p className="mt-2 text-sm text-secondary">{String(e.data.request.reason)}</p> : null}
        {e.kind === "action_verified" ? <ProofSummary proof={e.data.proof}/> : null}
        {e.previous_event_id ? <p className="mt-1 text-xs text-muted">Linked to the previous {e.kind === "reopened" ? "closure" : "handoff"} record.</p> : null}
      </li>)}</ol> : <p className="mt-3 text-sm text-secondary">No verified outcome or resolution has been recorded yet.</p>}
    </div>
    <aside className="space-y-6 border-t border-border pt-6 xl:border-l xl:border-t-0 xl:pl-7 xl:pt-0">
      <h3 className="flex items-center gap-2 text-base font-semibold text-primary"><ShieldCheck size={18} />Next step</h3>
      {primary && commandAction ? <ResolutionForm key={`${data.case_id}-${data.version}-${primary}`} kind={primary} data={data} action={commandAction} simulated={simulated} /> :
        <p className="text-sm leading-6 text-secondary">{complete ? "This case is complete." : verified ? "An authorized reviewer can close this case." : "Open the action to check its target outcome. Closure becomes available only after verification succeeds."}</p>}
    </aside>
  </section>;
}

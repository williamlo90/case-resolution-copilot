import { CheckCircle2, Clock3, AlertTriangle } from "lucide-react";
import { WorkspaceLink as Link } from "@/components/navigation/workspace-link";
import type { ActionDetail } from "@/domain/actions/action";
import { ProofSummary } from "./proof-summary";
import type { Resolution } from "./contract";

export function ActionOutcome({detail,resolution,synthetic=false}:{detail:ActionDetail;resolution:Resolution;synthetic?:boolean}) {
  const event = [...resolution.events].reverse().find(e=>e.kind==="action_verified" && e.data.action_id===detail.action.id);
  const verified = detail.action.status==="completed" && !!event;
  const uncertain = ["outcome_unknown","recovery_required","running"].includes(detail.action.status);
  const stale = detail.executionBlocker==="stale_proposal" || detail.executionBlocker==="expired_approval";
  const Icon = stale ? AlertTriangle : verified ? CheckCircle2 : Clock3;
  return <section aria-label="Outcome verification" className="border-b border-border bg-canvas px-4 py-5 sm:px-6 lg:px-7"><div className="mx-auto flex max-w-[1540px] items-start gap-3">
    <Icon size={22} className={stale ? "mt-1 text-danger" : verified ? "mt-1 text-success" : "mt-1 text-warning"}/>
    <div className="flex-1"><h2 className="text-base font-semibold text-primary">{stale ? "Approval needs a new review" : verified ? "Outcome verified at last check" : uncertain ? "Outcome uncertain" : "Outcome not checked yet"}</h2>
      <p className="mt-1 max-w-3xl text-sm leading-6 text-secondary">{stale ? "The policy, evidence or approval changed. The previous approval cannot authorize this action. Review the current case before proceeding." : verified ? "The result matched the approved operation, recipient, amount and parameters. Open the case to review closure eligibility." : uncertain ? "The request may already have succeeded. Check target outcome below before taking another step; sending it again could duplicate the refund." : "An accepted request is not proof of completion. After execution, check the target outcome before closing the case."}</p>
      {verified && event ? <p className="mt-2 text-xs text-secondary">Checked {new Date(event.at).toLocaleString("en-GB", { timeZone: "UTC" }) + " UTC"}{synthetic ? " against the synthetic payment ledger. No real money moved." : "."}</p> : null}
      {verified && event ? <ProofSummary proof={event.data.proof}/> : null}
      <Link href={`/cases/${detail.action.caseId}?tab=resolution`} className="mt-3 inline-block text-sm font-semibold text-info hover:underline">{verified ? "Review evidence and close case" : "View case resolution"}</Link>
    </div>
  </div></section>;
}

import Link from "next/link";
import { ArrowRight, FlaskConical } from "lucide-react";
import type { DemoView } from "@/features/v2-demo/contract";
import { practiceHref } from "./href";
import type { ServerCommand } from "@/data/commands/command-state";
import { practiceOutcome } from "./outcome";
import { StepForm } from "./step-form";

export type PracticeArea = "cases" | "reviews" | "actions" | "policies";
export function WorkflowGuidance({view,area,policyAction}:{view:DemoView;area:PracticeArea;policyAction?:ServerCommand}) {
  const id = view.session.session_id;
  const href = (path:string) => practiceHref(path,id);
  const caseUrl = href(`/cases/${view.case.id}`);
  const reviewUrl = view.review ? href(`/reviews/${view.review.review.id}`) : caseUrl;
  const actionUrl = view.action ? href(`/actions/${view.action.action.id}`) : caseUrl;
  const policyUrl = href(`/policies/${view.policy.policy.id}`);
  const sop = view.session.scenario === "sop_revision";
  const outcome = practiceOutcome(view);
  const uncertain = outcome === "uncertain";
  const completed = view.case.status === "completed";
  const reopened = view.lifecycle.events.some(e=>e.kind==="reopened");
  const approved = view.review?.review.status === "approved";
  const verified = outcome === "verified";
  const role = area==="policies" ? "Policy manager" : area==="reviews" || area==="actions" || verified || completed ? "Reviewer" : "Specialist";
  let title = "Read the case, then analyze it";
  let detail = "Check the customer request and policy. Analyze case prepares the recommendation for review.";
  let next: {label:string;url:string}|null = null;
  if (view.brief && !view.review) {title="Ready for human review";detail="Read the recommendation and its evidence, then submit it for review.";}
  if (view.review && !approved) {title="A reviewer must check the recommendation";detail="The specialist's submission is saved. Open Reviews, take the review and record the decision.";if(area!=="reviews") next={label:"Open review as reviewer",url:reviewUrl};}
  if (approved && !verified) {
    title="Approval recorded";detail="Open the approved action to run the refund, then check its result.";if(area!=="actions") next={label:"Open approved action",url:actionUrl};
    if (sop && view.policy.policy.current_version===1) {title="Now change the refund policy";detail="This approval used the USD 500 limit. Publish a USD 100 limit to see why the old approval stops authorizing this refund.";next=area==="policies" ? null : {label:"Open policy as policy manager",url:policyUrl};}
    if (sop && view.policy.policy.current_version>1) {title="The policy changed; approval must be reviewed again";detail=view.policy.policy.current_version===2 ? "The refund is USD 240, above the new USD 100 limit. Open Actions to see the old approval blocked. You can also restore the former limit as a new revision." : "The limit is restored to USD 500 as a new revision. The earlier approval stays invalid; rollback does not restore permission to execute.";next=area==="actions" ? {label:"View policy versions",url:policyUrl} : {label:"See blocked action",url:actionUrl};}
  }
  if (uncertain) {title="Check the result before trying again";detail="The response was interrupted. The refund may already be recorded. Use Check target outcome to find the original result.";next=area==="actions" ? null : {label:"Check the original action",url:actionUrl};}
  if (outcome === "acknowledged") {title="Request accepted; check the result";detail="The payment system acknowledged the request. Use Check target outcome to verify the refund before closing.";next=area==="actions" ? null : {label:"Verify the original action",url:actionUrl};}
  if (verified) {title="The refund outcome is verified";detail="Return to the case, review the evidence and record the simulated customer communication before closing.";next=area==="cases" ? null : {label:"Review evidence and close case",url:caseUrl+"&tab=resolution"};}
  if (completed) {title="Case closed with evidence";detail=view.session.scenario==="verified_reopen" ? "To continue the example, a new customer message reports a problem. Reopen the case with an explanation and new evidence reference." : "The interrupted request was recovered and the case is closed. The ledger records one refund.";next=area==="cases" ? null : {label:"View completed case",url:caseUrl+"&tab=resolution"};}
  if (reopened) {title="The case is open for investigation again";detail="The earlier closure is preserved and linked to this new investigation. The original refund remains recorded.";next=null;}
  return <section aria-label="Practice context" className="border-b border-border bg-info-bg/40 px-4 py-4 sm:px-6 lg:px-7">
    <div className="mx-auto max-w-[1540px]">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-secondary"><p className="flex items-center gap-2"><FlaskConical size={15}/>Practice case · Synthetic payment · Acting as {role}</p><Link href="/cases" className="font-semibold text-info hover:underline">Exit practice</Link></div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-4"><div><h2 className="text-base font-semibold text-primary">{title}</h2><p className="mt-1 max-w-3xl text-sm leading-6 text-secondary">{detail}</p></div>{next ? <Link href={next.url} className="inline-flex min-h-10 items-center gap-2 rounded-md border border-action px-4 text-sm font-semibold text-action">{next.label}<ArrowRight size={16}/></Link> : null}</div>
      {area==="policies" && sop && policyAction ? <div className="mt-4"><StepForm action={policyAction} label={view.policy.policy.current_version===1 ? "Publish USD 100 refund limit" : "Restore USD 500 limit as a new revision"} /></div> : null}
      {area==="cases" && approved && !verified && !completed ? <Link href={actionUrl} className="mt-3 inline-block text-sm font-semibold text-info hover:underline">View approved action</Link> : null}
    </div>
  </section>;
}

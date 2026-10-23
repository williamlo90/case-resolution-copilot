import { notFound } from "next/navigation";
import { CaseWorkspace } from "@/features/cases/components/case-workspace";
import { ReviewWorkspace } from "@/features/reviews/components/review-workspace";
import { ActionDetail } from "@/features/actions/components/action-detail";
import { PolicyDetail } from "@/features/policies/components/policy-detail";
import { ActionOutcome } from "@/features/resolution/action-outcome";
import { runPracticeStep, type PracticeBinding } from "@/app/(operations)/_actions/practice";
import { getPractice } from "./data";
import { WorkflowGuidance, type PracticeArea } from "./workflow-guidance";

export async function PracticeWorkspacePage({sessionId,area,resourceId,tab}:{sessionId:string;area:PracticeArea;resourceId:string;tab?:string}) {
  const data = await getPractice(sessionId);
  const {view,workspace,review,action,policy,resolution} = data;
  const expectedId = area==="cases" ? workspace.case.id : area==="reviews" ? review?.review.id : area==="actions" ? action?.action.id : policy.policy.id;
  if (resourceId!==expectedId) notFound();
  const step = (command:PracticeBinding["command"], role:PracticeBinding["role"], version:number, resource:string|null=null) => runPracticeStep.bind(null,sessionId,{
    command, role, expected_version:version, resource_id:resource,
    snapshot_fingerprint:review?.review.snapshotFingerprint ?? null,
    expected_proposal_version:workspace.proposal?.version ?? null,
  });
  const policyAction = view.session.scenario==="sop_revision" && review?.review.status==="approved" && view.policy.policy.current_version<3
    ? step(view.policy.policy.current_version===1 ? "publish_revision" : "rollback","policy_manager",policy.policy.recordVersion) : undefined;
  return <>
    <WorkflowGuidance view={view} area={area} policyAction={policyAction}/>
    {area==="cases" ? <CaseWorkspace key={sessionId} workspace={workspace}
      prepareBriefAction={workspace.availableCommands.includes("revise_resolution") && !action ? step("generate","specialist",workspace.case.version) : undefined}
      submitReviewAction={workspace.proposal ? step("submit","specialist",workspace.case.version) : undefined}
      resolution={resolution} resolutionAction={step("close","reviewer",resolution.version)}
      simulated initialTab={tab==="resolution" ? "resolution" : "brief"}
    /> : null}
    {area==="reviews" && review ? <ReviewWorkspace key={review.review.id} snapshot={review}
      reserveAction={step("reserve","reviewer",review.review.version,review.review.id)}
      decideAction={step("approve","reviewer",review.review.version,review.review.id)}
    /> : null}
    {area==="actions" && action ? <>
      <ActionOutcome detail={action} resolution={resolution} synthetic/>
      <ActionDetail key={action.action.id} detail={{...action,availableCommands:action.availableCommands.filter(c=>c==="execute" || c==="reconcile")}}
        commandAction={step("execute","reviewer",action.action.version,action.action.id)}/>
    </> : null}
    {area==="policies" ? <PolicyDetail detail={{...policy,availableCommands:[]}}/> : null}
  </>;
}

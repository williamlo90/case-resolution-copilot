import { getActionRepository } from "@/data/actions/action-repository-provider";
import { ActionDetail } from "@/features/actions/components/action-detail";
import { notFound } from "next/navigation";
import { practiceId, type PageSearch } from "@/features/practice/data";
import { PracticeWorkspacePage } from "@/features/practice/workspace-page";
import { apiRequest } from "@/data/api/api-client";
import { resolutionSchema } from "@/features/resolution/contract";
import { ActionOutcome } from "@/features/resolution/action-outcome";
import { runActionCommand } from "../../_actions/actions";

export const dynamic = "force-dynamic";

export default async function ActionDetailPage({ params, searchParams }: { params: Promise<{ actionId: string }>; searchParams: PageSearch }) {
  const { actionId } = await params;
  const practice = practiceId((await searchParams).practice);
  if (practice) return <PracticeWorkspacePage sessionId={practice} area="actions" resourceId={actionId}/>;
  const repository = getActionRepository();
  const detail = await repository.getActionDetail(actionId);
  if (!detail) notFound();
  const resolution = repository.source === "api" ? await apiRequest(`/api/cases/${encodeURIComponent(detail.action.caseId)}/resolution`, resolutionSchema) : null;
  return (
    <>{resolution ? <ActionOutcome detail={detail} resolution={resolution}/> : null}<ActionDetail
      detail={detail}
      commandAction={
        repository.source === "api"
          ? runActionCommand.bind(null, actionId, detail.action.version)
          : undefined
      }
    /></>
  );
}

import { getActionRepository } from "@/data/actions/action-repository-provider";
import { ActionDetail } from "@/features/actions/components/action-detail";
import { notFound } from "next/navigation";
import { runActionCommand } from "../../_actions/actions";

export const dynamic = "force-dynamic";

export default async function ActionDetailPage({ params }: { params: Promise<{ actionId: string }> }) {
  const { actionId } = await params;
  const repository = getActionRepository();
  const detail = await repository.getActionDetail(actionId);
  if (!detail) notFound();
  return (
    <ActionDetail
      detail={detail}
      commandAction={
        repository.source === "api"
          ? runActionCommand.bind(null, actionId, detail.action.version)
          : undefined
      }
    />
  );
}

import { runPolicyLifecycleCommand } from "@/app/(operations)/_actions/policies";
import { getPolicyRepository } from "@/data/policies/policy-repository-provider";
import { PolicyDetail } from "@/features/policies/components/policy-detail";
import { notFound } from "next/navigation";

export const dynamic = "force-dynamic";

export default async function PolicyDetailPage({ params }: { params: Promise<{ policyId: string }> }) {
  const { policyId } = await params;
  const repository = getPolicyRepository();
  const detail = await repository.getPolicyDetail(policyId);
  if (!detail) notFound();
  const currentVersion = detail.versions.find(
    (item) => item.version === detail.policy.currentVersion,
  );
  return (
    <PolicyDetail
      detail={detail}
      lifecycleAction={
        repository.source === "api" &&
        detail.availableCommands.length &&
        currentVersion
          ? runPolicyLifecycleCommand.bind(
              null,
              detail.policy.id,
              detail.policy.recordVersion,
              currentVersion.version,
              currentVersion.recordVersion,
            )
          : undefined
      }
    />
  );
}

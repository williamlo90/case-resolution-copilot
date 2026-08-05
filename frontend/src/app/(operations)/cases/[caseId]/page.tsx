import { getCaseRepository } from "@/data/cases/case-repository-provider";
import { CaseWorkspace } from "@/features/cases/components/case-workspace";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

export const metadata: Metadata = { title: "Case workspace" };

export default async function CasePage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  const workspace = await getCaseRepository().getCaseWorkspace(caseId);

  if (!workspace) {
    notFound();
  }

  return <CaseWorkspace workspace={workspace} />;
}

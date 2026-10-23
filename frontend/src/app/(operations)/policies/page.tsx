import { getAdministrationRepository } from "@/data/administration/administration-repository-provider";
import { getPolicyRepository } from "@/data/policies/policy-repository-provider";
import { PolicyLibrary } from "@/features/policies/components/policy-library";
import type { Metadata } from "next";
import { practiceId, openPracticeArea, type PageSearch } from "@/features/practice/data";

export const metadata: Metadata = { title: "Policies" };
export const dynamic = "force-dynamic";

export default async function PoliciesPage({searchParams}: {searchParams: PageSearch}) {
  const practice = practiceId((await searchParams).practice);
  if (practice) return openPracticeArea(practice, "policies");
  const repository = getPolicyRepository();
  const [policies, context] = await Promise.all([
    repository.listPolicies(),
    getAdministrationRepository().getSessionContext(),
  ]);
  return (
    <PolicyLibrary
      policies={policies}
      canManage={context.actor.permissions.includes("policy:manage")}
      sourceLabel={
        repository.source === "api" ? "Connected policy records" : "Sample policy data"
      }
    />
  );
}

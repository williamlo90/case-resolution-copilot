import { createPolicy } from "@/app/(operations)/_actions/policies";
import { getAdministrationRepository } from "@/data/administration/administration-repository-provider";
import { PolicyCreateForm } from "@/features/policies/components/policy-create-form";
import type { Metadata } from "next";
import { redirect } from "next/navigation";

export const metadata: Metadata = { title: "New policy" };
export const dynamic = "force-dynamic";

export default async function NewPolicyPage() {
  const context =
    await getAdministrationRepository().getSessionContext();
  if (!context.actor.permissions.includes("policy:manage")) {
    redirect("/permission-denied");
  }
  return <PolicyCreateForm action={createPolicy} />;
}

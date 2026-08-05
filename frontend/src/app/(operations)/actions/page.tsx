import { getActionRepository } from "@/data/actions/action-repository-provider";
import { ActionQueue } from "@/features/actions/components/action-queue";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Actions" };
export const dynamic = "force-dynamic";

export default async function ActionsPage() {
  const repository = getActionRepository();
  return (
    <ActionQueue
      actions={await repository.listActions()}
      sourceLabel={
        repository.source === "api" ? "Connected action records" : "Sample action data"
      }
    />
  );
}

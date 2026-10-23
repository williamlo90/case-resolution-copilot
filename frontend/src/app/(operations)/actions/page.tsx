import { getActionRepository } from "@/data/actions/action-repository-provider";
import { ActionQueue } from "@/features/actions/components/action-queue";
import type { Metadata } from "next";
import { practiceId, openPracticeArea, type PageSearch } from "@/features/practice/data";

export const metadata: Metadata = { title: "Actions" };
export const dynamic = "force-dynamic";

export default async function ActionsPage({searchParams}: {searchParams: PageSearch}) {
  const practice = practiceId((await searchParams).practice);
  if (practice) return openPracticeArea(practice, "actions");
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

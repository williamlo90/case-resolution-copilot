import { auth } from "@clerk/nextjs/server";
import { notFound, redirect } from "next/navigation";

export default async function OperatorStudyPage({ searchParams }: {
  searchParams: Promise<{ packet?: string }>;
}) {
  if (process.env.SUPPORT_COPILOT_OPERATOR_STUDY_ENABLED !== "true") notFound();
  const session = await auth();
  if (!session.userId) redirect("/sign-in");
  const selected = (await searchParams).packet;
  const packet = selected === "primary" || selected === "practice" ? selected : "training";
  redirect(`/operator-study.html?packet=${packet}`);
}

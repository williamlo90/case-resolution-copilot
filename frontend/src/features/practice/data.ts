import { apiRequest } from "@/data/api/api-client";
import { parseCaseWorkspace } from "@/data/cases/api-case-repository";
import { parseReviewSnapshot } from "@/data/reviews/api-review-repository";
import { parseActionDetail } from "@/data/actions/api-action-repository";
import { parsePolicyDetail } from "@/data/policies/api-policy-repository";
import { demoViewSchema } from "@/features/v2-demo/contract";
import { resolutionSchema } from "@/features/resolution/contract";
import { cache } from "react";
import { notFound, redirect } from "next/navigation";
import { z } from "zod";

export type PageSearch = Promise<Record<string, string | string[] | undefined>>;
export function practiceId(value: string | string[] | undefined): string | null {
  if (!value) return null;
  if (typeof value !== "string" || !/^VD-[A-F0-9]{16}$/.test(value)) notFound();
  return value;
}
export const getPractice = cache(async (id: string) => {
  if (!/^VD-[A-F0-9]{16}$/.test(id)) notFound();
  const envelope = await apiRequest(`/api/demo/v2/sessions/${id}`, z.object({data: z.object({
    workspace: z.unknown(), review: z.unknown(), action: z.unknown(), policy: z.unknown(), lifecycle: z.unknown(),
  }).passthrough()}), {timeoutMs: 60000});
  const raw = envelope.data;
  return {
    view: demoViewSchema.parse(raw),
    workspace: parseCaseWorkspace(raw.workspace),
    review: raw.review ? parseReviewSnapshot(raw.review) : null,
    action: raw.action ? parseActionDetail(raw.action) : null,
    policy: parsePolicyDetail(raw.policy),
    resolution: resolutionSchema.parse(raw.lifecycle),
  };
});
export type PracticeData = Awaited<ReturnType<typeof getPractice>>;
export async function openPracticeArea(id: string, area: "cases" | "reviews" | "actions" | "policies"): Promise<never> {
  const data = await getPractice(id);
  const destination = area === "reviews" && data.review ? `/reviews/${data.review.review.id}`
    : area === "actions" && data.action ? `/actions/${data.action.action.id}`
    : area === "policies" ? `/policies/${data.policy.policy.id}` : `/cases/${data.workspace.case.id}`;
  redirect(destination + "?practice=" + id);
}

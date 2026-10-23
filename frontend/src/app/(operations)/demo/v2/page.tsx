import { apiRequest } from "@/data/api/api-client";
import { V2Demo } from "@/features/v2-demo/v2-demo";
import { demoSessionsSchema } from "@/features/v2-demo/contract";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "V2 interactive demo" };
export const dynamic = "force-dynamic";
export default async function V2DemoPage() {
  const sessions = await apiRequest("/api/demo/v2/sessions", demoSessionsSchema);
  return <V2Demo sessions={sessions.items} />;
}

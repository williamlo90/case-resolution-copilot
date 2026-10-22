import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { ApiClientError, apiRequest } from "@/data/api/api-client";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

async function handle(request: NextRequest, context: { params: Promise<{ kind: string }> }) {
  if (process.env.SUPPORT_COPILOT_OPERATOR_STUDY_ENABLED !== "true") {
    return NextResponse.json({ detail: "Study unavailable" }, { status: 404 });
  }
  const { kind } = await context.params;
  const allowed = new Set(["state", "start", "brief", "submit", "approve", "execute", "reconcile", "readback", "acknowledge", "communicate", "close", "finish", "export"]);
  const packet = request.nextUrl.searchParams.get("packet") ?? "practice";
  if (!allowed.has(kind) || !["practice", "primary", "training"].includes(packet)) {
    return NextResponse.json({ detail: "Unknown study command" }, { status: 404 });
  }
  if (request.method === "POST" && request.headers.get("origin") !== request.nextUrl.origin) {
    return NextResponse.json({ detail: "Same-origin commands required" }, { status: 403 });
  }
  try {
    const path = kind === "export" ? "evidence/export" : kind;
    const result = await apiRequest(`/api/operator-study/${path}?packet=${packet}`, z.unknown(), {
      method: request.method,
      ...(request.method === "POST" ? { body: await request.json() } : {}), timeoutMs: 55000,
    });
    return NextResponse.json(result, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    if (error instanceof ApiClientError) {
      return NextResponse.json({ detail: error.message, correlation_id: error.correlationId }, { status: error.status });
    }
    return NextResponse.json({ detail: "Study command unavailable; inspect state before retrying." }, { status: 503 });
  }
}
export { handle as GET, handle as POST };

import { ApiClientError, apiRequest } from "@/data/api/api-client";
import { z } from "zod";

const auditExportSchema = z.object({
  data: z.object({
    case_id: z.string().min(1),
    organization_id: z.string().min(1),
    source_id: z.string().min(1),
    external_reference: z.string().min(1),
    legacy_task_id: z.string().min(1).nullable(),
    generated_at: z.string().datetime(),
    generated_by: z.string().min(1),
    governance: z.unknown().nullable(),
    events: z.array(z.unknown()),
  }),
});

export async function POST(
  _request: Request,
  context: { params: Promise<{ caseId: string }> },
) {
  const { caseId } = await context.params;
  try {
    const exportRecord = await apiRequest(
      `/api/cases/${encodeURIComponent(caseId)}/audit-export`,
      auditExportSchema,
      { method: "POST" },
    );
    const filename = `${caseId.replace(/[^a-zA-Z0-9._-]/g, "_")}-audit.json`;
    return new Response(JSON.stringify(exportRecord.data, null, 2), {
      status: 200,
      headers: {
        "Cache-Control": "no-store",
        "Content-Disposition": `attachment; filename="${filename}"`,
        "Content-Type": "application/json; charset=utf-8",
      },
    });
  } catch (error) {
    if (error instanceof ApiClientError) {
      return Response.json(
        {
          error: {
            code: error.code,
            message: error.message,
            correlation_id: error.correlationId,
          },
        },
        {
          status: error.status,
          headers: { "Cache-Control": "no-store" },
        },
      );
    }
    return Response.json(
      {
        error: {
          code: "audit_export_failed",
          message: "The audit file could not be prepared.",
        },
      },
      {
        status: 500,
        headers: { "Cache-Control": "no-store" },
      },
    );
  }
}

import { z } from "zod";

const proofSchema = z.object({
  external_reference: z.string(), effect_count: z.number().int(),
  impact_amount: z.union([z.string(), z.number()]).nullable(),
  impact_currency: z.string().nullable(),
  observed_at: z.string(),
});

export function ProofSummary({proof}: {proof: unknown}) {
  const parsed = proofSchema.safeParse(proof);
  if (!parsed.success) return null;
  const data = parsed.data;
  return <dl aria-label="Verified result" className="mt-3 grid gap-3 rounded-md border border-success/25 bg-success-bg p-4 text-sm sm:grid-cols-2">
    {data.impact_amount !== null ? <div><dt className="text-xs text-secondary">Verified amount</dt><dd className="mt-1 font-semibold text-primary">{data.impact_currency} {Number(data.impact_amount).toFixed(2)}</dd></div> : null}
    <div><dt className="text-xs text-secondary">Recorded changes</dt><dd className="mt-1 font-semibold text-primary">{data.effect_count}</dd></div>
    <div className="sm:col-span-2"><dt className="text-xs text-secondary">Confirmation reference</dt><dd className="mt-1 break-all text-primary">{data.external_reference}</dd></div>
  </dl>;
}

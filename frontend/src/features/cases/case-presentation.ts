import type { PresentationPreferences } from "@/components/providers/presentation-provider";
import type { CaseCategory, CaseStatus } from "@/domain/cases/case";
import { formatCurrency, formatDateTime } from "@/lib/presentation-format";

export const caseCategoryLabels: Record<CaseCategory, string> = {
  billing_dispute: "Billing dispute",
  refund_request: "Refund request",
  account_access: "Account access",
  service_exception: "Service exception",
};

export const caseStatusPresentation: Record<
  CaseStatus,
  { label: string; tone: "neutral" | "warning" | "info" | "danger" | "success" }
> = {
  new: { label: "New", tone: "neutral" },
  investigating: { label: "Investigating", tone: "info" },
  information_needed: { label: "Information needed", tone: "danger" },
  needs_review: { label: "Needs review", tone: "warning" },
  waiting_customer: { label: "Waiting for customer", tone: "neutral" },
  in_progress: { label: "In progress", tone: "info" },
  completed: { label: "Completed", tone: "success" },
};

export function formatSla(minutes: number) {
  if (minutes < 60) return `${minutes}m left`;
  const hours = Math.floor(minutes / 60);
  const remaining = minutes % 60;
  return remaining ? `${hours}h ${remaining}m` : `${hours}h`;
}

export function formatUpdatedAt(
  value: string | null,
  preferences: PresentationPreferences,
) {
  if (!value) return "Unknown";
  return formatDateTime(value, preferences, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatMoney(
  amount: number,
  currency: string,
  preferences: PresentationPreferences,
) {
  return formatCurrency(amount, currency, preferences);
}

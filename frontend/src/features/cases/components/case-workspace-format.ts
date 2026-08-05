import type { PresentationPreferences } from "@/components/providers/presentation-provider";
import { formatDateTime } from "@/lib/presentation-format";

export function formatCaseDateTime(
  value: string,
  preferences: PresentationPreferences,
) {
  return formatDateTime(value, preferences, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

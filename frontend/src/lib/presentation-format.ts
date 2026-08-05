import type { PresentationPreferences } from "@/components/providers/presentation-provider";

export function formatDateTime(
  value: string | Date,
  preferences: PresentationPreferences,
  options: Intl.DateTimeFormatOptions,
): string {
  return new Intl.DateTimeFormat(preferences.locale, {
    ...options,
    timeZone: preferences.timeZone,
  }).format(typeof value === "string" ? new Date(value) : value);
}

export function formatCurrency(
  amount: number,
  currency: string,
  preferences: PresentationPreferences,
): string {
  return new Intl.NumberFormat(preferences.locale, {
    style: "currency",
    currency,
    currencyDisplay: "symbol",
  }).format(amount);
}

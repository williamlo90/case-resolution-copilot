import type { ReactNode } from "react";

export type StatusTone = "neutral" | "info" | "success" | "warning" | "danger";

const toneClassNames: Record<StatusTone, string> = {
  neutral: "border-border bg-neutral-bg text-neutral",
  info: "border-info/20 bg-info-bg text-info",
  success: "border-success/20 bg-success-bg text-success",
  warning: "border-warning/25 bg-warning-bg text-warning",
  danger: "border-danger/20 bg-danger-bg text-danger",
};

export function StatusLabel({
  children,
  tone = "neutral",
  icon,
}: {
  children: ReactNode;
  tone?: StatusTone;
  icon?: ReactNode;
}) {
  return (
    <span className={`inline-flex min-h-7 items-center gap-1.5 rounded border px-2 text-xs font-medium ${toneClassNames[tone]}`}>
      {icon ?? <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />}
      {children}
    </span>
  );
}

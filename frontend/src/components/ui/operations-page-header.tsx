import type { ReactNode } from "react";

export function OperationsPageHeader({
  title,
  description,
  meta,
  actions,
}: {
  title: string;
  description: string;
  meta?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="border-b border-border px-4 py-6 sm:px-6 lg:px-7">
      <div className="mx-auto flex max-w-[1540px] flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-[28px] font-semibold leading-tight text-primary">{title}</h1>
          <p className="mt-1.5 max-w-3xl text-sm text-secondary">{description}</p>
        </div>
        {actions ?? (meta ? <div className="text-xs text-muted">{meta}</div> : null)}
      </div>
    </header>
  );
}

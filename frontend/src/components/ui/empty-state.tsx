import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="grid min-h-64 place-items-center px-6 text-center">
      <div className="max-w-md">
        <Icon aria-hidden="true" className="mx-auto text-muted" size={24} />
        <p className="mt-3 text-sm font-semibold text-primary">{title}</p>
        <p className="mt-1 text-sm leading-6 text-secondary">{description}</p>
        {action ? <div className="mt-4">{action}</div> : null}
      </div>
    </div>
  );
}

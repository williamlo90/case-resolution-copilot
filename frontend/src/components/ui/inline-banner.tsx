import { Info } from "lucide-react";

export function InlineBanner({ children }: { children: React.ReactNode }) {
  return (
    <div
      role="status"
      className="flex min-h-8 items-center gap-2 rounded-md bg-info-bg px-3 py-2 text-xs font-medium text-info"
    >
      <Info aria-hidden="true" size={14} />
      {children}
    </div>
  );
}

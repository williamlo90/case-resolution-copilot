import { ArrowLeft } from "lucide-react";
import { WorkspaceLink as Link } from "@/components/navigation/workspace-link";

export default function CaseNotFound() {
  return (
    <div className="grid min-h-[calc(100vh-60px)] place-items-center px-6 text-center">
      <div>
        <p className="text-sm font-semibold text-primary">Case not found</p>
        <p className="mt-2 text-sm text-secondary">The case may have moved, closed, or never existed in this workspace.</p>
        <Link href="/cases" className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-action hover:underline">
          <ArrowLeft aria-hidden="true" size={15} /> Return to Cases
        </Link>
      </div>
    </div>
  );
}

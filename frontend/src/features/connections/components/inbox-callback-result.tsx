import { WorkspaceLink as Link } from "@/components/navigation/workspace-link";
import { AlertTriangle, CheckCircle2 } from "lucide-react";

export function InboxCallbackResult({
  success,
  message,
}: {
  success: boolean;
  message: string;
}) {
  const Icon = success ? CheckCircle2 : AlertTriangle;
  return (
    <div className="grid min-h-[calc(100vh-60px)] place-items-center bg-surface px-4 py-12">
      <section className="w-full max-w-xl border border-border bg-surface px-6 py-8 text-center">
        <Icon
          aria-hidden="true"
          size={28}
          className={success ? "mx-auto text-success" : "mx-auto text-danger"}
        />
        <h1 className="mt-4 text-xl font-semibold text-primary">
          {success ? "Inbox connected" : "Inbox was not connected"}
        </h1>
        <p className="mt-2 text-sm leading-6 text-secondary">{message}</p>
        <Link
          href="/connections"
          className="mt-6 inline-flex h-10 items-center rounded-md bg-action px-4 text-sm font-semibold text-white"
        >
          Return to connections
        </Link>
      </section>
    </div>
  );
}

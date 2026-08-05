import { AlertTriangle, RotateCcw } from "lucide-react";

type DataLoadFailureProps = {
  title: string;
  description: string;
  retryHref: string;
  code: string;
  reference?: string | null;
  diagnosticPaths?: readonly string[];
};

export function DataLoadFailure({
  title,
  description,
  retryHref,
  code,
  reference,
  diagnosticPaths = [],
}: DataLoadFailureProps) {
  const supportReference =
    reference && reference !== "unavailable" ? reference : code;

  return (
    <div className="grid min-h-[calc(100vh-60px)] place-items-center bg-surface px-4">
      <section
        className="w-full max-w-lg border border-danger/25 bg-danger-bg px-6 py-6"
        data-load-error-code={code}
        data-load-error-paths={diagnosticPaths.join(",")}
      >
        <AlertTriangle aria-hidden="true" size={22} className="text-danger" />
        <h1 className="mt-4 text-xl font-semibold text-primary">{title}</h1>
        <p className="mt-2 text-sm leading-6 text-secondary">{description}</p>
        <p className="mt-3 text-xs text-muted">
          Support reference: {supportReference}
        </p>
        <a
          href={retryHref}
          className="mt-5 inline-flex h-10 items-center gap-2 rounded-md bg-action px-4 text-sm font-semibold text-white"
        >
          <RotateCcw aria-hidden="true" size={16} />
          Try again
        </a>
      </section>
    </div>
  );
}

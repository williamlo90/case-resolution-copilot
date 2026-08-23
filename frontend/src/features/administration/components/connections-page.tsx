"use client";

import { usePresentationPreferences } from "@/components/providers/presentation-provider";
import { useModalDialog } from "@/components/accessibility/use-modal-dialog";
import { OperationsPageHeader } from "@/components/ui/operations-page-header";
import { StatusLabel } from "@/components/ui/status-label";
import { CommandStatus } from "@/components/ui/command-status";
import {
  initialCommandState,
  type CommandState,
} from "@/data/commands/command-state";
import type { Connection } from "@/domain/administration/administration";
import {
  CheckCircle2,
  ChevronRight,
  Link2,
  PlugZap,
  ShieldCheck,
  X,
} from "lucide-react";
import { formatDateTime } from "@/lib/presentation-format";
import {
  useActionState,
  useCallback,
  useRef,
  useState,
  type ReactNode,
} from "react";

const healthTone = {
  healthy: "success",
  degraded: "warning",
  unavailable: "danger",
  not_configured: "neutral",
} as const;

const environmentLabels: Record<Connection["environment"], string> = {
  demo: "Demo",
  sandbox: "Test",
  production: "Live",
};

const accessStatusLabels: Record<Connection["credentialStatus"], string> = {
  demo: "Demo access",
  connected: "Connected",
  missing: "Setup required",
  expired: "Reconnect required",
};

const healthLabels: Record<Connection["health"], string> = {
  healthy: "Ready",
  degraded: "Needs attention",
  unavailable: "Unavailable",
  not_configured: "Setup required",
};

const providerLabels: Record<string, string> = {
  billing: "Billing system",
  identity: "Account system",
  service_operations: "Service operations",
  case_source: "Case source",
  business_operations: "Business operations",
  general_operations: "General operations",
};

const capabilityLabels: Record<string, string> = {
  receive_case: "Receive new support cases",
  check_action_outcome: "Check whether a change completed",
  lookup_transaction: "View transactions",
  lookup_refund: "View refunds",
  lookup_account: "View account status",
  lookup_service_order: "View service orders",
  reverse_duplicate_charge: "Reverse a duplicate charge",
  issue_refund: "Issue a refund",
  start_verified_recovery: "Start verified account recovery",
  apply_service_correction: "Apply a service correction",
};

const workLabels: Record<string, string> = {
  billing_dispute: "Billing disputes",
  refund_request: "Refund requests",
  account_access: "Account access",
  service_exception: "Service exceptions",
};

function plainLabel(value: string, labels: Record<string, string>): string {
  return (
    labels[value] ??
    value
      .split("_")
      .filter(Boolean)
      .map((part) => part[0]?.toUpperCase() + part.slice(1))
      .join(" ")
  );
}

type TestConnectionCommand = (
  connectionId: string,
  expectedVersion: number,
  previousState: CommandState,
  formData: FormData,
) => Promise<CommandState>;

function ConnectionHealthControl({
  connection,
  action,
}: {
  connection: Connection;
  action?: TestConnectionCommand;
}) {
  const boundAction = action?.bind(null, connection.id, connection.version);
  const [state, formAction, pending] = useActionState(
    boundAction ??
      (async () => ({
        ...initialCommandState,
        status: "error" as const,
        message: "Sample data is read-only.",
      })),
    initialCommandState,
  );
  return (
    <form action={formAction}>
      <button
        type="submit"
        disabled={!action || pending}
        className="inline-flex h-10 items-center rounded-md bg-action px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
      >
        {pending ? "Checking..." : "Test connection"}
      </button>
      <div className="mt-4">
        <CommandStatus state={state} />
      </div>
    </form>
  );
}

export function ConnectionsPage({
  connections,
  connected,
  testConnectionAction,
  featuredContent,
}: {
  connections: readonly Connection[];
  connected: boolean;
  testConnectionAction?: TestConnectionCommand;
  featuredContent?: ReactNode;
}) {
  const presentation = usePresentationPreferences();
  const [selected, setSelected] = useState<Connection | null>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const openerRef = useRef<HTMLButtonElement | null>(null);

  const closeDetails = useCallback(() => {
    setSelected(null);
    window.setTimeout(() => openerRef.current?.focus(), 0);
  }, []);
  useModalDialog({
    open: selected !== null,
    dialogRef,
    initialFocusRef: closeButtonRef,
    onDismiss: closeDetails,
  });

  return (
    <div className="min-h-[calc(100vh-60px)] bg-surface">
      <div
        aria-hidden={selected ? true : undefined}
        inert={selected ? true : undefined}
      >
        <OperationsPageHeader
          title="Connections"
          description="Case sources, permitted changes, and current status."
          meta={connected ? "Connected workspace" : "Sample workspace"}
        />
        <div className="mx-auto max-w-[1540px] px-4 py-6 sm:px-6 lg:px-7">
        {featuredContent ? <div className="mb-6">{featuredContent}</div> : null}
        {connections.length ? (
          <div className="grid gap-px border border-border bg-border lg:grid-cols-2">
            {connections.map((item) => (
            <article key={item.id} className="bg-surface px-5 py-5">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="grid size-9 place-items-center rounded-md bg-info-bg text-info">
                    <Link2 aria-hidden="true" size={18} />
                  </span>
                  <div>
                    <h2 className="text-sm font-semibold text-primary">{item.name}</h2>
                    <p className="mt-0.5 text-xs text-muted">{plainLabel(item.providerType, providerLabels)} / {environmentLabels[item.environment]}</p>
                  </div>
                </div>
                <StatusLabel tone={healthTone[item.health]}>{healthLabels[item.health]}</StatusLabel>
              </div>
              <dl className="mt-5 grid grid-cols-2 gap-4 border-y border-border py-4 text-xs">
                <div><dt className="text-muted">Data views</dt><dd className="mt-1 font-medium text-primary">{item.capabilities.read.length}</dd></div>
                <div><dt className="text-muted">Permitted changes</dt><dd className="mt-1 font-medium text-primary">{item.capabilities.write.length}</dd></div>
                <div><dt className="text-muted">Access status</dt><dd className="mt-1 font-medium text-primary">{accessStatusLabels[item.credentialStatus]}</dd></div>
                <div>
                  <dt className="text-muted">Last connection check</dt>
                  <dd className="mt-1 font-medium text-primary">
                    {item.lastCheckedAt
                      ? formatDateTime(item.lastCheckedAt, presentation, {
                          dateStyle: "medium",
                          timeStyle: "short",
                        })
                      : "Never"}
                  </dd>
                </div>
              </dl>
              <button
                type="button"
                onClick={(event) => {
                  openerRef.current = event.currentTarget;
                  setSelected(item);
                }}
                className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-action"
              >
                View details <ChevronRight aria-hidden="true" size={15} />
              </button>
            </article>
            ))}
          </div>
        ) : !featuredContent ? (
          <section className="border border-border px-5 py-12 text-center">
            <PlugZap aria-hidden="true" size={24} className="mx-auto text-muted" />
            <h2 className="mt-4 text-base font-semibold text-primary">
              No connections registered
            </h2>
            <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-secondary">
              Add a support case source or controlled action tool through the
              deployment setup before pilot use.
            </p>
          </section>
        ) : null}
        </div>
      </div>

      {selected ? (
        <div className="fixed inset-0 z-50 flex justify-end">
          <button type="button" aria-label="Dismiss connection details" className="absolute inset-0 bg-black/30" onClick={closeDetails} />
          <aside ref={dialogRef} role="dialog" aria-modal="true" aria-label={`${selected.name} connection details`} tabIndex={-1} className="relative h-full w-full max-w-[520px] overflow-y-auto bg-surface px-5 py-6 shadow-2xl sm:px-7">
            <div className="flex items-start justify-between gap-4">
              <div><p className="font-mono text-xs text-muted">{selected.id}</p><h2 className="mt-1 text-xl font-semibold text-primary">{selected.name}</h2></div>
              <button ref={closeButtonRef} type="button" aria-label="Close connection details" onClick={closeDetails} className="grid size-10 place-items-center rounded-md text-secondary hover:bg-surface-subtle"><X aria-hidden="true" size={18} /></button>
            </div>
            <div className="mt-6 border-y border-border py-5">
              <h3 className="text-sm font-semibold text-primary">Permitted reads</h3>
              {selected.capabilities.read.length ? (
                <ul className="mt-3 space-y-2 text-sm text-secondary">{selected.capabilities.read.map((item) => <li key={item} className="flex gap-2"><CheckCircle2 aria-hidden="true" size={15} className="mt-0.5 text-success" />{plainLabel(item, capabilityLabels)}</li>)}</ul>
              ) : (
                <p className="mt-3 text-sm text-muted">No read access.</p>
              )}
              <h3 className="mt-6 text-sm font-semibold text-primary">Permitted changes</h3>
              {selected.capabilities.write.length ? (
                <ul className="mt-3 space-y-2 text-sm text-secondary">{selected.capabilities.write.map((item) => <li key={item} className="flex gap-2"><ShieldCheck aria-hidden="true" size={15} className="mt-0.5 text-warning" />{plainLabel(item, capabilityLabels)}</li>)}</ul>
              ) : (
                <p className="mt-3 text-sm text-muted">No change access.</p>
              )}
            </div>
            <section className="py-5"><h3 className="text-sm font-semibold text-primary">Supported cases</h3><p className="mt-2 text-sm text-secondary">{selected.affectedWork.length ? selected.affectedWork.map((item) => plainLabel(item, workLabels)).join(", ") : "Not limited to a case type."}</p></section>
            {testConnectionAction ? (
              <ConnectionHealthControl
                connection={selected}
                action={testConnectionAction}
              />
            ) : (
              <p className="text-sm text-secondary">
                You can inspect this connection, but only an administrator can
                check it.
              </p>
            )}
            <p className="mt-4 text-xs leading-5 text-muted">
              Connection secrets are stored in deployment settings and are
              never shown here.
            </p>
          </aside>
        </div>
      ) : null}
    </div>
  );
}

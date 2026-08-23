"use client";

import { CommandStatus } from "@/components/ui/command-status";
import {
  initialCommandState,
  type ServerCommand,
} from "@/data/commands/command-state";
import type { CaseWorkspace } from "@/domain/cases/case";
import { Plus } from "lucide-react";
import { useActionState, useState } from "react";

type RecordType = CaseWorkspace["businessContexts"][number]["type"];

const recordTypes: readonly { value: RecordType; label: string }[] = [
  { value: "payment", label: "Payment" },
  { value: "invoice", label: "Invoice" },
  { value: "subscription", label: "Subscription" },
  { value: "order", label: "Order" },
  { value: "delivery", label: "Delivery" },
  { value: "account", label: "Account" },
  { value: "other", label: "Other" },
];

const recordStatuses: Record<
  RecordType,
  readonly { value: string; label: string }[]
> = {
  payment: [
    { value: "settled", label: "Settled" },
    { value: "pending", label: "Pending" },
    { value: "failed", label: "Failed" },
    { value: "reversed", label: "Reversed" },
    { value: "refunded", label: "Refunded" },
    { value: "duplicate", label: "Marked as duplicate" },
  ],
  invoice: [
    { value: "open", label: "Open" },
    { value: "paid", label: "Paid" },
    { value: "disputed", label: "Disputed" },
    { value: "void", label: "Void" },
  ],
  subscription: [
    { value: "active", label: "Active" },
    { value: "paused", label: "Paused" },
    { value: "cancelled", label: "Cancelled" },
  ],
  order: [
    { value: "unused", label: "Unused" },
    { value: "active", label: "Active" },
    { value: "fulfilled", label: "Fulfilled" },
    { value: "cancelled", label: "Cancelled" },
  ],
  delivery: [
    { value: "not_started", label: "Not started" },
    { value: "in_transit", label: "In transit" },
    { value: "delivered", label: "Delivered" },
    { value: "failed", label: "Failed" },
    { value: "incomplete", label: "Incomplete" },
    { value: "not_delivered", label: "Not delivered" },
  ],
  account: [
    { value: "active", label: "Active" },
    { value: "locked", label: "Locked" },
    { value: "restricted", label: "Restricted" },
    { value: "closed", label: "Closed" },
  ],
  other: [
    { value: "verified", label: "Verified" },
    { value: "pending", label: "Pending" },
    { value: "unavailable", label: "Unavailable" },
  ],
};

const inputClassName =
  "h-10 rounded-md border border-border bg-surface px-3 text-sm text-primary outline-none placeholder:text-muted focus:border-focus";

export function CaseEvidenceRecordForm({ action }: { action: ServerCommand }) {
  const [recordType, setRecordType] = useState<RecordType>("payment");
  const [state, formAction, pending] = useActionState(
    action,
    initialCommandState,
  );
  const hasMoney = recordType === "payment" || recordType === "invoice";
  const hasDelivery = recordType === "order" || recordType === "delivery";
  const hasProduct =
    recordType === "subscription" ||
    recordType === "order" ||
    recordType === "delivery";
  const hasIdentity = recordType === "account";

  return (
    <form action={formAction} className="mt-5 border-y border-border py-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="grid gap-1.5 text-xs font-semibold text-primary">
          Record type
          <select
            name="type"
            value={recordType}
            onChange={(event) =>
              setRecordType(event.target.value as RecordType)
            }
            className={inputClassName}
          >
            {recordTypes.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1.5 text-xs font-semibold text-primary">
          Record name
          <input
            name="label"
            required
            maxLength={300}
            placeholder="Second settled charge"
            className={inputClassName}
          />
        </label>
        <label className="grid gap-1.5 text-xs font-semibold text-primary">
          Where you checked it
          <input
            name="source"
            required
            maxLength={100}
            placeholder="Billing system"
            className={inputClassName}
          />
        </label>
        <label className="grid gap-1.5 text-xs font-semibold text-primary">
          Record reference
          <input
            name="source_reference"
            required
            maxLength={200}
            placeholder="PAY-2048-02"
            className={inputClassName}
          />
        </label>
        <label className="grid gap-1.5 text-xs font-semibold text-primary">
          Current status
          <select
            key={recordType}
            name="status"
            defaultValue={recordStatuses[recordType][0].value}
            className={inputClassName}
          >
            {recordStatuses[recordType].map((status) => (
              <option key={status.value} value={status.value}>
                {status.label}
              </option>
            ))}
          </select>
        </label>
        {hasProduct ? (
          <label className="grid gap-1.5 text-xs font-semibold text-primary">
            Product or service
            <input
              name="product"
              maxLength={200}
              placeholder="Pro monthly plan"
              className={inputClassName}
            />
          </label>
        ) : null}
        {hasMoney ? (
          <>
            <label className="grid gap-1.5 text-xs font-semibold text-primary">
              Amount{recordType === "payment" ? " (required)" : ""}
              <input
                name="amount"
                inputMode="decimal"
                required={recordType === "payment"}
                placeholder="49.00"
                className={inputClassName}
              />
            </label>
            <label className="grid gap-1.5 text-xs font-semibold text-primary">
              Currency{recordType === "payment" ? " (required)" : ""}
              <input
                name="currency"
                required={recordType === "payment"}
                minLength={3}
                maxLength={3}
                placeholder="USD"
                className={`${inputClassName} uppercase`}
              />
            </label>
          </>
        ) : null}
        {hasDelivery ? (
          <label className="grid gap-1.5 text-xs font-semibold text-primary">
            Delivery result
            <select
              name="delivery_state"
              defaultValue=""
              required
              className={inputClassName}
            >
              <option value="" disabled>
                Choose a result
              </option>
              <option value="not_started">Not started</option>
              <option value="in_transit">In transit</option>
              <option value="delivered">Delivered</option>
              <option value="failed">Failed</option>
              <option value="incomplete">Incomplete</option>
              <option value="not_delivered">Not delivered</option>
            </select>
          </label>
        ) : null}
        {hasIdentity ? (
          <>
            <label className="grid gap-1.5 text-xs font-semibold text-primary">
              Identity check
              <select
                name="identity_check"
                defaultValue=""
                required
                className={inputClassName}
              >
                <option value="" disabled>
                  Choose a result
                </option>
                <option value="verified">Verified</option>
                <option value="pending">Pending</option>
                <option value="not_verified">Not verified</option>
              </select>
            </label>
            <label className="grid gap-1.5 text-xs font-semibold text-primary">
              Sign-in protection
              <select
                name="mfa_state"
                defaultValue=""
                className={inputClassName}
              >
                <option value="">Not checked</option>
                <option value="enabled">Enabled</option>
                <option value="disabled">Disabled</option>
                <option value="locked">Locked</option>
              </select>
            </label>
          </>
        ) : null}
      </div>
      <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <p className="max-w-lg text-xs leading-5 text-secondary">
          Only add a record you checked against the named source. Adding it makes
          an earlier decision brief or approval out of date.
        </p>
        <button
          type="submit"
          disabled={pending}
          className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-md bg-action px-4 text-sm font-semibold text-white hover:bg-action-strong disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Plus aria-hidden="true" size={16} />
          {pending ? "Adding record..." : "Add checked record"}
        </button>
      </div>
      <div className="mt-3">
        <CommandStatus state={state} />
      </div>
    </form>
  );
}

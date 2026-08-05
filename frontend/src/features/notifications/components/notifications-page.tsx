"use client";

import { usePresentationPreferences } from "@/components/providers/presentation-provider";
import { WorkspaceLink as Link } from "@/components/navigation/workspace-link";
import { CommandStatus } from "@/components/ui/command-status";
import { OperationsPageHeader } from "@/components/ui/operations-page-header";
import {
  initialCommandState,
  type CommandState,
  type ServerCommand,
} from "@/data/commands/command-state";
import type {
  Notification,
  NotificationPage as NotificationPageModel,
} from "@/domain/notifications/notification";
import {
  ArrowUpRight,
  Bell,
  Check,
  CheckCheck,
  CircleAlert,
} from "lucide-react";
import { formatDateTime } from "@/lib/presentation-format";
import { useActionState } from "react";

type MarkNotificationReadCommand = (
  notificationId: string,
  expectedVersion: number,
  previousState: CommandState,
  formData: FormData,
) => Promise<CommandState>;

const kindLabels: Record<Notification["kind"], string> = {
  sla_risk: "Response limit",
  review_waiting: "Review waiting",
  action_recovery: "Action recovery",
  membership_changed: "Team",
  settings_changed: "Settings",
  system: "System",
};

function resourceHref(notification: Notification): string {
  if (notification.resourceType === "case") {
    return `/cases/${encodeURIComponent(notification.resourceId)}`;
  }
  if (notification.resourceType === "review") {
    return `/reviews/${encodeURIComponent(notification.resourceId)}`;
  }
  if (notification.resourceType === "action") {
    return `/actions/${encodeURIComponent(notification.resourceId)}`;
  }
  if (notification.resourceType === "connection") return "/connections";
  if (notification.resourceType === "member") return "/team";
  if (notification.resourceType === "settings") return "/settings/general";
  return "/cases";
}

function MarkReadControl({
  notification,
  action,
}: {
  notification: Notification;
  action?: MarkNotificationReadCommand;
}) {
  const boundAction = action?.bind(
    null,
    notification.id,
    notification.version,
  );
  const [state, formAction, pending] = useActionState(
    boundAction ??
      (async () => ({
        ...initialCommandState,
        status: "error" as const,
        message: "Sample notifications are read-only.",
      })),
    initialCommandState,
  );
  return (
    <div>
      <form action={formAction}>
        <button
          type="submit"
          disabled={!action || pending}
          className="inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-xs font-semibold text-primary hover:bg-surface-subtle disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Check aria-hidden="true" size={14} />
          {pending ? "Updating..." : "Mark as read"}
        </button>
      </form>
      <CommandStatus state={state} />
    </div>
  );
}

function MarkAllControl({ action }: { action?: ServerCommand }) {
  const [state, formAction, pending] = useActionState(
    action ??
      (async () => ({
        ...initialCommandState,
        status: "error" as const,
        message: "Sample notifications are read-only.",
      })),
    initialCommandState,
  );
  return (
    <div>
      <form action={formAction}>
        <button
          type="submit"
          disabled={!action || pending}
          className="inline-flex h-10 items-center gap-2 rounded-md border border-border bg-surface px-3 text-sm font-semibold text-primary hover:bg-surface-subtle disabled:cursor-not-allowed disabled:opacity-50"
        >
          <CheckCheck aria-hidden="true" size={16} />
          {pending ? "Updating..." : "Mark all as read"}
        </button>
      </form>
      <CommandStatus state={state} />
    </div>
  );
}

export function NotificationsPage({
  notifications,
  connected,
  markReadAction,
  markAllReadAction,
}: {
  notifications: NotificationPageModel;
  connected: boolean;
  markReadAction?: MarkNotificationReadCommand;
  markAllReadAction?: ServerCommand;
}) {
  const presentation = usePresentationPreferences();
  return (
    <div className="min-h-[calc(100vh-60px)] bg-surface">
      <OperationsPageHeader
        title="Notifications"
        description="Work that needs your attention across this workspace."
        meta={`${notifications.unreadCount} unread / ${connected ? "connected" : "sample"}`}
        actions={
          notifications.unreadCount > 0 ? (
            <MarkAllControl action={markAllReadAction} />
          ) : undefined
        }
      />
      <div className="mx-auto max-w-[1100px] px-4 py-6 sm:px-6 lg:px-7">
        {notifications.items.length === 0 ? (
          <section className="border border-border px-5 py-12 text-center">
            <Bell aria-hidden="true" size={24} className="mx-auto text-muted" />
            <h2 className="mt-4 text-base font-semibold text-primary">
              No notifications
            </h2>
            <p className="mt-2 text-sm text-secondary">
              New review, response limit, and recovery updates will appear here.
            </p>
          </section>
        ) : (
          <ol className="divide-y divide-border border-y border-border">
            {notifications.items.map((notification) => (
              <li
                key={notification.id}
                className={`grid gap-4 px-1 py-5 sm:grid-cols-[24px_minmax(0,1fr)_auto] ${
                  notification.status === "unread" ? "bg-info-bg/35" : ""
                }`}
              >
                <span
                  className={`mt-0.5 grid size-6 place-items-center rounded-full ${
                    notification.status === "unread"
                      ? "bg-info-bg text-info"
                      : "bg-surface-subtle text-muted"
                  }`}
                >
                  {notification.status === "unread" ? (
                    <CircleAlert aria-hidden="true" size={14} />
                  ) : (
                    <Check aria-hidden="true" size={14} />
                  )}
                </span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <p className="text-sm font-semibold text-primary">
                      {notification.title}
                    </p>
                    <span className="text-xs font-medium text-info">
                      {kindLabels[notification.kind]}
                    </span>
                  </div>
                  <p className="mt-1 text-sm leading-6 text-secondary">
                    {notification.message}
                  </p>
                  <time
                    dateTime={notification.createdAt}
                    className="mt-2 block text-xs text-muted"
                  >
                    {formatDateTime(notification.createdAt, presentation, {
                      dateStyle: "medium",
                      timeStyle: "short",
                    })}
                  </time>
                </div>
                <div className="flex flex-wrap items-start gap-2 sm:justify-end">
                  <Link
                    href={resourceHref(notification)}
                    className="inline-flex h-9 items-center gap-2 rounded-md bg-action px-3 text-xs font-semibold text-white"
                  >
                    Open
                    <ArrowUpRight aria-hidden="true" size={14} />
                  </Link>
                  {notification.status === "unread" ? (
                    <MarkReadControl
                      notification={notification}
                      action={markReadAction}
                    />
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}

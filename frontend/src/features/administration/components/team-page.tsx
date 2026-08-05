"use client";

import { usePresentationPreferences } from "@/components/providers/presentation-provider";
import { CommandStatus } from "@/components/ui/command-status";
import { EmptyState } from "@/components/ui/empty-state";
import { OperationsPageHeader } from "@/components/ui/operations-page-header";
import { StatusLabel } from "@/components/ui/status-label";
import {
  initialCommandState,
  type CommandState,
  type ServerCommand,
} from "@/data/commands/command-state";
import type {
  Invitation,
  Member,
} from "@/domain/administration/administration";
import { MailPlus, UserRoundCog, Users, UserX, X } from "lucide-react";
import { formatDateTime } from "@/lib/presentation-format";
import { useActionState, useState } from "react";

type UpdateMemberCommand = (
  memberId: string,
  expectedVersion: number,
  previousState: CommandState,
  formData: FormData,
) => Promise<CommandState>;

type RevokeInvitationCommand = (
  invitationId: string,
  expectedVersion: number,
  previousState: CommandState,
  formData: FormData,
) => Promise<CommandState>;

const roleAuthorityLabels: Record<Member["role"], string> = {
  specialist: "Manage cases and prepare customer responses",
  supervisor: "Review decisions and run approved actions",
  administrator: "Manage the workspace, team, policies, and actions",
  auditor: "Inspect cases, quality checks, and audit records",
};

function InviteMemberForm({
  action,
  onClose,
}: {
  action?: ServerCommand;
  onClose: () => void;
}) {
  const [state, formAction, pending] = useActionState(
    action ??
      (async () => ({
        ...initialCommandState,
        status: "error" as const,
        message: "Sample data is read-only.",
      })),
    initialCommandState,
  );
  return (
    <form
      action={formAction}
      className="mt-5 border border-border bg-canvas/45 px-4 py-4"
    >
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-sm font-semibold text-primary">Invite team member</h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close invitation form"
          className="grid size-9 place-items-center rounded-md text-secondary hover:bg-surface-subtle"
        >
          <X aria-hidden="true" size={17} />
        </button>
      </div>
      <div className="mt-4 grid gap-4 sm:grid-cols-[minmax(0,1fr)_220px_auto] sm:items-end">
        <label className="grid gap-2 text-xs font-semibold text-primary">
          Email
          <input
            name="email"
            type="email"
            required
            className="h-10 rounded-md border border-border bg-surface px-3 text-sm font-normal"
          />
        </label>
        <label className="grid gap-2 text-xs font-semibold text-primary">
          Role
          <select
            name="role"
            defaultValue="specialist"
            className="h-10 rounded-md border border-border bg-surface px-3 text-sm font-normal"
          >
            <option value="specialist">Specialist</option>
            <option value="supervisor">Supervisor</option>
            <option value="administrator">Administrator</option>
            <option value="auditor">Auditor</option>
          </select>
        </label>
        <button
          type="submit"
          disabled={!action || pending}
          className="inline-flex h-10 items-center justify-center rounded-md bg-action px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          {pending ? "Sending..." : "Send invitation"}
        </button>
      </div>
      <p className="mt-3 text-xs leading-5 text-muted">
        The invitation email opens secure account setup. Workspace access starts
        only after the invited address is verified.
      </p>
      <div className="mt-4">
        <CommandStatus state={state} />
      </div>
    </form>
  );
}

function MemberUpdateForm({
  member,
  action,
  onClose,
}: {
  member: Member;
  action?: UpdateMemberCommand;
  onClose: () => void;
}) {
  const boundAction = action?.bind(null, member.id, member.version);
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
    <form
      action={formAction}
      className="border-b border-border bg-canvas/45 px-4 py-4"
    >
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-primary">
            Manage {member.name}
          </h2>
          <p className="mt-1 text-xs text-muted">{member.email}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close member controls"
          className="grid size-9 place-items-center rounded-md text-secondary hover:bg-surface-subtle"
        >
          <X aria-hidden="true" size={17} />
        </button>
      </div>
      <div className="mt-4 grid gap-4 sm:grid-cols-[220px_220px_auto] sm:items-end">
        <label className="grid gap-2 text-xs font-semibold text-primary">
          Role
          <select
            name="role"
            defaultValue={member.role}
            className="h-10 rounded-md border border-border bg-surface px-3 text-sm font-normal"
          >
            <option value="specialist">Specialist</option>
            <option value="supervisor">Supervisor</option>
            <option value="administrator">Administrator</option>
            <option value="auditor">Auditor</option>
          </select>
        </label>
        <label className="grid gap-2 text-xs font-semibold text-primary">
          Status
          <select
            name="status"
            defaultValue={member.status === "deactivated" ? "deactivated" : "active"}
            className="h-10 rounded-md border border-border bg-surface px-3 text-sm font-normal"
          >
            <option value="active">Active</option>
            <option value="deactivated">Deactivated</option>
          </select>
        </label>
        <button
          type="submit"
          disabled={!action || pending || member.status === "invited"}
          className="inline-flex h-10 items-center justify-center rounded-md bg-action px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          {pending ? "Saving..." : "Save member"}
        </button>
      </div>
      <div className="mt-4">
        <CommandStatus state={state} />
      </div>
    </form>
  );
}

function RevokeInvitationControl({
  invitation,
  action,
}: {
  invitation: Invitation;
  action?: RevokeInvitationCommand;
}) {
  const boundAction = action?.bind(
    null,
    invitation.id,
    invitation.version,
  );
  const [state, formAction, pending] = useActionState(
    boundAction ??
      (async () => ({
        ...initialCommandState,
        status: "error" as const,
        message: "This invitation cannot be changed.",
      })),
    initialCommandState,
  );
  return (
    <div>
      <form action={formAction}>
        <button
          type="submit"
          disabled={!action || pending || invitation.status !== "pending"}
          className="inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-xs font-semibold text-danger hover:bg-danger-bg disabled:cursor-not-allowed disabled:opacity-50"
        >
          <UserX aria-hidden="true" size={14} />
          {pending ? "Revoking..." : "Revoke"}
        </button>
      </form>
      <CommandStatus state={state} />
    </div>
  );
}

export function TeamPage({
  members,
  invitations = [],
  connected,
  inviteAction,
  updateMemberAction,
  revokeInvitationAction,
}: {
  members: readonly Member[];
  invitations?: readonly Invitation[];
  connected: boolean;
  inviteAction?: ServerCommand;
  updateMemberAction?: UpdateMemberCommand;
  revokeInvitationAction?: RevokeInvitationCommand;
}) {
  const presentation = usePresentationPreferences();
  const [invitationOpen, setInvitationOpen] = useState(false);
  const [selectedMember, setSelectedMember] = useState<Member | null>(null);

  return (
    <div className="min-h-[calc(100vh-60px)] bg-surface">
      <OperationsPageHeader
        title="Team"
        description="People, roles, and what each person can do."
        meta={`${members.length} people / ${invitations.filter((item) => item.status === "pending").length} pending / ${connected ? "connected" : "sample"}`}
      />
      <div className="mx-auto max-w-[1540px] px-4 py-6 sm:px-6 lg:px-7">
        {inviteAction ? (
          <div className="flex justify-end">
          <button
            type="button"
            onClick={() => {
              setInvitationOpen((open) => !open);
              setSelectedMember(null);
            }}
            className="inline-flex h-10 items-center gap-2 rounded-md bg-action px-4 text-sm font-semibold text-white"
          >
            <MailPlus aria-hidden="true" size={16} /> Invite team member
          </button>
          </div>
        ) : null}
        {invitationOpen ? (
          <InviteMemberForm
            action={inviteAction}
            onClose={() => setInvitationOpen(false)}
          />
        ) : null}
        {invitations.length > 0 ? (
          <section
            aria-labelledby="pending-invitations-heading"
            className="mt-5 border border-border"
          >
            <div className="border-b border-border bg-canvas/65 px-4 py-3">
              <h2
                id="pending-invitations-heading"
                className="text-sm font-semibold text-primary"
              >
                Invitations
              </h2>
            </div>
            <ul className="divide-y divide-border">
              {invitations.map((invitation) => (
                <li
                  key={invitation.id}
                  className="grid gap-3 px-4 py-4 sm:grid-cols-[minmax(0,1fr)_140px_160px_auto] sm:items-center"
                >
                  <div>
                    <p className="text-sm font-semibold text-primary">
                      {invitation.email}
                    </p>
                    <p className="mt-1 text-xs text-muted">
                      Expires{" "}
                      {formatDateTime(invitation.expiresAt, presentation, {
                        dateStyle: "medium",
                      })}
                    </p>
                  </div>
                  <p className="text-sm capitalize text-secondary">
                    {invitation.role}
                  </p>
                  <StatusLabel
                    tone={
                      invitation.status === "pending"
                        ? "warning"
                        : invitation.status === "accepted"
                          ? "success"
                          : "neutral"
                    }
                  >
                    {invitation.status}
                  </StatusLabel>
                  {invitation.status === "pending" &&
                  revokeInvitationAction ? (
                    <RevokeInvitationControl
                      invitation={invitation}
                      action={revokeInvitationAction}
                    />
                  ) : null}
                </li>
              ))}
            </ul>
          </section>
        ) : null}
        <div className="mt-5 overflow-x-auto border border-border">
          {selectedMember ? (
            <MemberUpdateForm
              member={selectedMember}
              action={updateMemberAction}
              onClose={() => setSelectedMember(null)}
            />
          ) : null}
          {members.length ? <table className="w-full min-w-[960px] border-collapse text-left">
            <caption className="sr-only">Workspace team members</caption>
            <thead className="bg-canvas/65 text-[11px] font-semibold uppercase text-muted">
              <tr className="border-b border-border">
                <th className="px-4 py-3">Member</th>
                <th className="px-3 py-3">Role</th>
                <th className="px-3 py-3">What they can do</th>
                <th className="px-3 py-3">Status</th>
                <th className="px-3 py-3">Last active</th>
                <th className="px-4 py-3">Manage</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {members.map((member) => (
                <tr key={member.id}>
                  <td className="px-4 py-4">
                    <p className="text-sm font-semibold text-primary">
                      {member.name}
                    </p>
                    <p className="mt-1 text-xs text-muted">{member.email}</p>
                  </td>
                  <td className="px-3 py-4 text-sm capitalize text-secondary">
                    {member.role}
                  </td>
                  <td className="max-w-[300px] px-3 py-4 text-xs leading-5 text-secondary">
                    {roleAuthorityLabels[member.role]}
                  </td>
                  <td className="px-3 py-4">
                    <StatusLabel
                      tone={
                        member.status === "active"
                          ? "success"
                          : member.status === "invited"
                            ? "warning"
                            : "neutral"
                      }
                    >
                      {member.status}
                    </StatusLabel>
                  </td>
                  <td className="px-3 py-4 text-xs text-secondary">
                    {member.lastActiveAt
                      ? formatDateTime(member.lastActiveAt, presentation, {
                          dateStyle: "medium",
                          timeStyle: "short",
                        })
                      : "Not yet"}
                  </td>
                  <td className="px-4 py-4">
                    {updateMemberAction ? (
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedMember(member);
                          setInvitationOpen(false);
                        }}
                        aria-label={`Manage ${member.name}`}
                        className="grid size-9 place-items-center rounded-md border border-border text-secondary hover:bg-surface-subtle"
                      >
                        <UserRoundCog aria-hidden="true" size={16} />
                      </button>
                    ) : (
                      <span className="text-xs text-muted">View only</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table> : (
            <EmptyState
              icon={Users}
              title="No team members yet"
              description="Create the first invitation to give someone workspace access."
            />
          )}
        </div>
      </div>
    </div>
  );
}

import { TeamPage } from "@/features/administration/components/team-page";
import { getAdministrationRepository } from "@/data/administration/administration-repository-provider";
import type { Metadata } from "next";
import {
  inviteMember,
  revokeInvitation,
  updateMember,
} from "../_actions/team";

export const metadata: Metadata = { title: "Team" };
export const dynamic = "force-dynamic";

export default async function TeamRoute() {
  const repository = getAdministrationRepository();
  const context = await repository.getSessionContext();
  const canInvite = context.actor.permissions.includes("member:invite");
  const canManage = context.actor.permissions.includes("member:manage");
  const [members, invitations] = await Promise.all([
    repository.listMembers(),
    canInvite ? repository.listInvitations() : Promise.resolve([]),
  ]);
  return (
    <TeamPage
      members={members}
      invitations={invitations}
      connected={repository.source === "api"}
      inviteAction={
        repository.source === "api" && canInvite ? inviteMember : undefined
      }
      updateMemberAction={
        repository.source === "api" && canManage ? updateMember : undefined
      }
      revokeInvitationAction={
        repository.source === "api" && canManage
          ? revokeInvitation
          : undefined
      }
    />
  );
}

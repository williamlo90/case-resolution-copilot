"use server";

import { ApiClientError, apiRequest } from "@/data/api/api-client";
import type { CommandState } from "@/data/commands/command-state";
import { revalidatePath } from "next/cache";
import {
  commandEnvelopeSchema,
  commandFailure,
  commandSuccess,
  postCommand,
} from "./shared";

export async function inviteMember(
  _previousState: CommandState,
  formData: FormData,
): Promise<CommandState> {
  const email = String(formData.get("email") ?? "").trim();
  const role = String(formData.get("role") ?? "");
  if (
    !email ||
    !["specialist", "supervisor", "administrator", "auditor"].includes(role)
  ) {
    return commandFailure(
      new ApiClientError(
        "A valid email and role are required.",
        422,
        "invitation_input_required",
        "unavailable",
      ),
    );
  }
  try {
    await apiRequest("/api/invitations", commandEnvelopeSchema, {
      method: "POST",
      body: { email, role },
    });
    revalidatePath("/team");
    return commandSuccess("The invitation was created.");
  } catch (error) {
    return commandFailure(error);
  }
}

export async function revokeInvitation(
  invitationId: string,
  expectedVersion: number,
  _previousState: CommandState,
  _formData: FormData,
): Promise<CommandState> {
  void _previousState;
  void _formData;
  try {
    await postCommand(
      `/api/invitations/${encodeURIComponent(invitationId)}/revoke`,
      { expected_version: expectedVersion },
    );
    revalidatePath("/team");
    return commandSuccess("The invitation was revoked.");
  } catch (error) {
    return commandFailure(error);
  }
}

export async function updateMember(
  memberId: string,
  expectedVersion: number,
  _previousState: CommandState,
  formData: FormData,
): Promise<CommandState> {
  const role = String(formData.get("role") ?? "");
  const status = String(formData.get("status") ?? "");
  if (
    !["specialist", "supervisor", "administrator", "auditor"].includes(role) ||
    !["active", "deactivated"].includes(status)
  ) {
    return commandFailure(
      new ApiClientError(
        "Choose a valid role and membership status.",
        422,
        "member_update_input_required",
        "unavailable",
      ),
    );
  }
  try {
    await apiRequest(
      `/api/members/${encodeURIComponent(memberId)}`,
      commandEnvelopeSchema,
      {
        method: "PATCH",
        body: { expected_version: expectedVersion, role, status },
      },
    );
    revalidatePath("/team");
    return commandSuccess("The member authority was updated.");
  } catch (error) {
    return commandFailure(error);
  }
}

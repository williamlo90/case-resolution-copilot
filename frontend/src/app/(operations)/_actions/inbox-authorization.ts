"use server";

import { ApiClientError } from "@/data/api/api-client";
import { apiInboxAuthorizationRepository } from "@/data/connections/api-inbox-authorization-repository";
import type { CommandState } from "@/data/commands/command-state";
import type { InboxCallbackState } from "@/features/connections/action-contracts";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { commandFailure, commandSuccess } from "./shared";

function safeAuthorizationUrl(value: string): string {
  const url = new URL(value);
  if (url.protocol !== "https:") {
    throw new ApiClientError(
      "The inbox sign-in address was not secure.",
      502,
      "inbox_authorization_url_invalid",
      "unavailable",
    );
  }
  return url.toString();
}

function safeReturnPath(value: string): string {
  return value === "/connections" ? value : "/connections";
}

export async function startInboxOAuth(
  _previousState: CommandState,
  formData: FormData,
): Promise<CommandState> {
  void _previousState;
  let authorizationUrl: string;
  try {
    const includeDrafts = formData.get("include_drafts") === "true";
    const result = await apiInboxAuthorizationRepository.start(includeDrafts);
    authorizationUrl = safeAuthorizationUrl(result.authorizationUrl);
  } catch (error) {
    return commandFailure(error);
  }
  redirect(authorizationUrl);
}

export async function completeInboxOAuth(
  _previousState: InboxCallbackState,
  formData: FormData,
): Promise<InboxCallbackState> {
  void _previousState;
  const state = String(formData.get("state") ?? "");
  const code = String(formData.get("code") ?? "");
  if (state.length < 32 || state.length > 512 || !code || code.length > 4000) {
    return {
      ...commandFailure(
        new ApiClientError(
          "This inbox sign-in link is incomplete or expired.",
          422,
          "inbox_callback_invalid",
          "unavailable",
        ),
      ),
      returnPath: null,
    };
  }

  try {
    const result = await apiInboxAuthorizationRepository.complete(state, code);
    revalidatePath("/connections");
    return {
      ...commandSuccess(`Connected ${result.accountAddress}.`),
      returnPath: safeReturnPath(result.returnPath),
    };
  } catch (error) {
    return { ...commandFailure(error), returnPath: null };
  }
}

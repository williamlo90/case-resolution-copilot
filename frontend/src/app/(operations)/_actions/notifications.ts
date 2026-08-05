"use server";

import type { CommandState } from "@/data/commands/command-state";
import { revalidatePath } from "next/cache";
import { commandFailure, commandSuccess, postCommand } from "./shared";

export async function markNotificationRead(
  notificationId: string,
  expectedVersion: number,
  _previousState: CommandState,
  _formData: FormData,
): Promise<CommandState> {
  void _previousState;
  void _formData;
  try {
    await postCommand(
      `/api/notifications/${encodeURIComponent(notificationId)}/read`,
      { expected_version: expectedVersion },
    );
    revalidatePath("/notifications");
    return commandSuccess("The notification was marked as read.");
  } catch (error) {
    return commandFailure(error);
  }
}

export async function markAllNotificationsRead(
  _previousState: CommandState,
  _formData: FormData,
): Promise<CommandState> {
  void _previousState;
  void _formData;
  try {
    await postCommand("/api/notifications/read-all", {});
    revalidatePath("/notifications");
    return commandSuccess("All notifications were marked as read.");
  } catch (error) {
    return commandFailure(error);
  }
}

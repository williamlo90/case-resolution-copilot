"use server";

import type { CommandState } from "@/data/commands/command-state";
import { revalidatePath } from "next/cache";
import { commandFailure, commandSuccess, postCommand } from "./shared";

export async function testConnection(
  connectionId: string,
  expectedVersion: number,
  _previousState: CommandState,
  _formData: FormData,
): Promise<CommandState> {
  void _previousState;
  void _formData;
  try {
    await postCommand(
      `/api/connections/${encodeURIComponent(connectionId)}/test`,
      { expected_version: expectedVersion },
    );
    revalidatePath("/connections");
    return commandSuccess("The connection health check completed.");
  } catch (error) {
    return commandFailure(error);
  }
}

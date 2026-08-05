import type { ActionDetail, ActionSummary } from "@/domain/actions/action";

export interface ActionRepository {
  readonly source: "api" | "mock";
  listActions(): Promise<readonly ActionSummary[]>;
  getActionDetail(actionId: string): Promise<ActionDetail | null>;
}

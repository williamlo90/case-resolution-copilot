import { actionDetailFixtures, actionSummaryFixtures } from "@/mocks/fixtures/action-fixtures";
import type { ActionRepository } from "./action-repository";

export const mockActionRepository: ActionRepository = {
  source: "mock",
  async listActions() { return actionSummaryFixtures; },
  async getActionDetail(actionId) { return actionDetailFixtures.find((item) => item.action.id === actionId) ?? null; },
};

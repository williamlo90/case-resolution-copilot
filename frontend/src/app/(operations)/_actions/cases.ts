import type {
  CaseActivity,
  CaseConversationMessage,
} from "@/domain/cases/case";

export type CaseHistoryLoadResult<Item> =
  | {
      status: "success";
      items: Item[];
      nextCursor: string | null;
      total: number;
    }
  | {
      status: "error";
      message: string;
    };

export type ConversationHistoryAction = (
  cursor: string,
) => Promise<CaseHistoryLoadResult<CaseConversationMessage>>;

export type ActivityHistoryAction = (
  cursor: string,
) => Promise<CaseHistoryLoadResult<CaseActivity>>;

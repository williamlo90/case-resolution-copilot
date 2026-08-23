import {
  initialCommandState,
  type CommandState,
} from "@/data/commands/command-state";
import type {
  InboxDraftDelivery,
  InboxThread,
} from "@/domain/connections/connected-inbox";

export type InboxThreadsState = CommandState & {
  items: InboxThread[];
  nextCursor: string | null;
};

export type InboxImportState = CommandState & {
  caseId: string | null;
};

export type InboxControlState = CommandState & {
  connectionState: "unchanged" | "ready" | "paused" | "disconnected";
};

export type InboxDraftState = CommandState & {
  delivery: InboxDraftDelivery | null;
};

export type InboxCallbackState = CommandState & {
  returnPath: string | null;
};

export type InboxThreadsAction = (
  previousState: InboxThreadsState,
  formData: FormData,
) => Promise<InboxThreadsState>;

export type InboxImportAction = (
  previousState: InboxImportState,
  formData: FormData,
) => Promise<InboxImportState>;

export type InboxControlAction = (
  previousState: InboxControlState,
  formData: FormData,
) => Promise<InboxControlState>;

export type InboxDraftAction = (
  previousState: InboxDraftState,
  formData: FormData,
) => Promise<InboxDraftState>;

export const initialInboxThreadsState: InboxThreadsState = {
  ...initialCommandState,
  items: [],
  nextCursor: null,
};

export const initialInboxImportState: InboxImportState = {
  ...initialCommandState,
  caseId: null,
};

export const initialInboxControlState: InboxControlState = {
  ...initialCommandState,
  connectionState: "unchanged",
};

export const initialInboxDraftState: InboxDraftState = {
  ...initialCommandState,
  delivery: null,
};

export const initialInboxCallbackState: InboxCallbackState = {
  ...initialCommandState,
  returnPath: null,
};

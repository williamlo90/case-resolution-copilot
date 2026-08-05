export type CommandState = {
  status: "idle" | "success" | "error";
  message: string;
  correlationId: string | null;
  retryAfterSeconds: number | null;
  tone?: "success" | "warning" | "error";
};

export const initialCommandState: CommandState = {
  status: "idle",
  message: "",
  correlationId: null,
  retryAfterSeconds: null,
};

export type ServerCommand = (
  previousState: CommandState,
  formData: FormData,
) => Promise<CommandState>;

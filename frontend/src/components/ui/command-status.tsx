import type { CommandState } from "@/data/commands/command-state";

export function CommandStatus({ state }: { state: CommandState }) {
  if (state.status === "idle") return null;
  const error = state.status === "error";
  const tone = state.tone ?? (error ? "error" : "success");
  const toneClass = {
    error: "border-danger/25 bg-danger-bg text-danger",
    success: "border-success/25 bg-success-bg text-success",
    warning: "border-warning/30 bg-warning-bg text-warning",
  }[tone];
  return (
    <div
      role={error ? "alert" : "status"}
      className={`border px-3 py-3 text-sm ${toneClass}`}
    >
      <p>{state.message}</p>
      {state.retryAfterSeconds !== null ? (
        <p className="mt-1 text-xs">
          Try again in about {state.retryAfterSeconds} seconds.
        </p>
      ) : null}
      {state.correlationId ? (
        <p className="mt-1 font-mono text-[11px] opacity-80">
          Reference {state.correlationId}
        </p>
      ) : null}
    </div>
  );
}

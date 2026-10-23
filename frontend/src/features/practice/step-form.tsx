"use client";
import { useActionState } from "react";
import { initialCommandState, type ServerCommand } from "@/data/commands/command-state";
import { CommandStatus } from "@/components/ui/command-status";
export function StepForm({action,label}:{action:ServerCommand;label:string}) {
  const [state,formAction,pending]=useActionState(action,initialCommandState);
  return <form action={formAction} className="space-y-3"><button disabled={pending} className="inline-flex min-h-11 items-center justify-center rounded-md bg-action px-4 text-sm font-semibold text-white hover:bg-action-strong disabled:opacity-50">{pending ? "Saving…" : label}</button><CommandStatus state={state}/></form>;
}

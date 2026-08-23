"use client";

import {
  initialInboxCallbackState,
  type InboxCallbackState,
} from "@/features/connections/action-contracts";
import { LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useActionState, useEffect, useRef, useTransition } from "react";
import { InboxCallbackResult } from "./inbox-callback-result";

type CallbackAction = (
  previousState: InboxCallbackState,
  formData: FormData,
) => Promise<InboxCallbackState>;

export function InboxCallbackCompletion({
  code,
  state,
  action,
}: {
  code: string;
  state: string;
  action: CallbackAction;
}) {
  const router = useRouter();
  const submitted = useRef(false);
  const [transitionPending, startTransition] = useTransition();
  const [result, formAction, actionPending] = useActionState(
    action,
    initialInboxCallbackState,
  );

  useEffect(() => {
    if (submitted.current) return;
    submitted.current = true;
    const formData = new FormData();
    formData.set("code", code);
    formData.set("state", state);
    startTransition(() => formAction(formData));
  }, [code, formAction, state]);

  useEffect(() => {
    if (result.status === "success") {
      router.replace(result.returnPath ?? "/connections");
    }
  }, [result.returnPath, result.status, router]);

  if (result.status === "error") {
    return <InboxCallbackResult success={false} message={result.message} />;
  }

  return (
    <div className="grid min-h-[calc(100vh-60px)] place-items-center bg-surface px-4 py-12">
      <div role="status" className="text-center">
        <LoaderCircle aria-hidden="true" size={28} className="mx-auto animate-spin text-info" />
        <h1 className="mt-4 text-xl font-semibold text-primary">
          Finishing inbox connection
        </h1>
        <p className="mt-2 text-sm text-secondary">
          {actionPending || transitionPending
            ? "Confirming access securely..."
            : "Returning to connections..."}
        </p>
      </div>
    </div>
  );
}

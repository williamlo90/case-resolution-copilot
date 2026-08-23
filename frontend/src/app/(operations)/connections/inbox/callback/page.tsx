import { completeInboxOAuth } from "@/app/(operations)/_actions/inbox-authorization";
import { InboxCallbackCompletion } from "@/features/connections/components/inbox-callback-completion";
import { InboxCallbackResult } from "@/features/connections/components/inbox-callback-result";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Connect inbox" };
export const dynamic = "force-dynamic";

type CallbackSearchParams = Record<
  string,
  string | string[] | undefined
>;

function firstValue(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

function providerErrorMessage(error: string): string {
  if (error === "access_denied") {
    return "Inbox access was not approved. No connection was created.";
  }
  return "Google could not complete inbox sign-in. No connection was created.";
}

export default async function InboxCallbackPage({
  searchParams,
}: {
  searchParams: Promise<CallbackSearchParams>;
}) {
  const parameters = await searchParams;
  const error = firstValue(parameters.error);
  if (error) {
    return (
      <InboxCallbackResult
        success={false}
        message={providerErrorMessage(error)}
      />
    );
  }

  const code = firstValue(parameters.code);
  const state = firstValue(parameters.state);
  if (!code || state.length < 32) {
    return (
      <InboxCallbackResult
        success={false}
        message="This inbox sign-in link is incomplete or expired. Start again from Connections."
      />
    );
  }

  return (
    <InboxCallbackCompletion
      code={code}
      state={state}
      action={completeInboxOAuth}
    />
  );
}

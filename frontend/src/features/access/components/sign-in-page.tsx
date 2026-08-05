"use client";

import { SignIn, SignUp, useAuth } from "@clerk/nextjs";
import { ArrowRight, PlayCircle, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { replaceDocument } from "./full-document-navigation";

const clerkAppearance = {
  elements: {
    rootBox: "w-full",
    cardBox: "w-full",
    card: "w-full rounded-md border border-border shadow-none",
    headerTitle: "sr-only",
    headerSubtitle: "sr-only",
  },
} as const;

function ProductIdentity() {
  return (
    <div className="flex items-center gap-3">
      <span className="grid size-10 place-items-center rounded-md bg-[#17232d] text-white">
        <ShieldCheck aria-hidden="true" size={20} />
      </span>
      <div>
        <p className="text-xs font-semibold uppercase text-muted">
          Case Resolution
        </p>
        <p className="text-sm font-semibold text-primary">Copilot</p>
      </div>
    </div>
  );
}

function ProviderAccessPanel({ invite }: { invite: boolean }) {
  const { isLoaded, isSignedIn } = useAuth();
  const redirectStarted = useRef(false);
  const [redirectFailed, setRedirectFailed] = useState(false);
  const [redirectDelayed, setRedirectDelayed] = useState(false);

  const openWorkspace = useCallback(() => {
    if (redirectStarted.current) {
      return;
    }
    redirectStarted.current = true;
    setRedirectFailed(false);
    try {
      replaceDocument("/cases");
    } catch {
      redirectStarted.current = false;
      setRedirectFailed(true);
    }
  }, []);

  useEffect(() => {
    if (!isLoaded || !isSignedIn) {
      return;
    }

    const redirectTimer = window.setTimeout(openWorkspace, 0);
    const fallbackTimer = window.setTimeout(() => {
      setRedirectDelayed(true);
    }, 4000);
    return () => {
      window.clearTimeout(redirectTimer);
      window.clearTimeout(fallbackTimer);
    };
  }, [isLoaded, isSignedIn, openWorkspace]);

  if (!isLoaded) {
    return (
      <div
        className="rounded-md border border-border bg-surface px-4 py-4 text-sm text-secondary"
        role="status"
      >
        Checking your sign-in...
      </div>
    );
  }

  if (isSignedIn) {
    return (
      <div className="rounded-md border border-border bg-surface px-4 py-4">
        <p className="text-sm text-secondary" role="status">
          {redirectFailed || redirectDelayed
            ? "Your account is ready. Continue to the workspace."
            : "Opening your workspace..."}
        </p>
        {redirectFailed || redirectDelayed ? (
          <button
            type="button"
            className="mt-3 inline-flex h-10 items-center justify-center gap-2 rounded-md bg-action px-4 text-sm font-semibold text-white"
            onClick={() => {
              redirectStarted.current = false;
              openWorkspace();
            }}
          >
            Continue
            <ArrowRight aria-hidden="true" size={16} />
          </button>
        ) : null}
      </div>
    );
  }

  return invite ? (
    <SignUp
      routing="path"
      path="/invite"
      signInUrl="/sign-in"
      fallbackRedirectUrl="/cases"
      forceRedirectUrl="/cases"
      appearance={clerkAppearance}
    />
  ) : (
    <SignIn
      routing="path"
      path="/sign-in"
      fallbackRedirectUrl="/cases"
      forceRedirectUrl="/cases"
      withSignUp={false}
      appearance={clerkAppearance}
    />
  );
}

export function SignInPage({
  invite = false,
  providerAuthentication = false,
}: {
  invite?: boolean;
  providerAuthentication?: boolean;
}) {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);

  if (providerAuthentication) {
    return (
      <main className="grid min-h-screen place-items-center bg-canvas px-4 py-10">
        <section
          aria-labelledby="access-heading"
          className="w-full max-w-[430px]"
        >
          <ProductIdentity />
          <h1
            id="access-heading"
            className="mt-8 text-2xl font-semibold text-primary"
          >
            {invite ? "Finish setting up your account" : "Sign in to your workspace"}
          </h1>
          <p className="mt-2 text-sm leading-6 text-secondary">
            {invite
              ? "Use the work email address that received the invitation."
              : "Use your invited work account to continue."}
          </p>
          <div className="mt-6">
            <ProviderAccessPanel invite={invite} />
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="grid min-h-screen place-items-center bg-canvas px-4 py-10">
      <section aria-labelledby="access-heading" className="w-full max-w-[430px] border border-border bg-surface px-6 py-7 sm:px-8">
        <ProductIdentity />
        <h1 id="access-heading" className="mt-8 text-2xl font-semibold text-primary">{invite ? "Accept your invitation" : "Sign in to your workspace"}</h1>
        <p className="mt-2 text-sm leading-6 text-secondary">{invite ? "Confirm the invited email address to continue." : "Use your work email to enter the demo workspace."}</p>
        {sent ? (
          <div role="status" className="mt-6 border border-success/25 bg-success-bg px-4 py-4 text-sm text-success">Preview sign-in link prepared for {email}.</div>
        ) : (
          <form className="mt-6" onSubmit={(event) => { event.preventDefault(); if (email) setSent(true); }}>
            <label className="grid gap-2 text-sm font-semibold text-primary">Work email<input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" className="h-11 rounded-md border border-border px-3 font-normal outline-none focus:border-focus" /></label>
            <button type="submit" className="mt-4 inline-flex h-11 w-full items-center justify-center gap-2 rounded-md bg-action text-sm font-semibold text-white">Continue <ArrowRight aria-hidden="true" size={16} /></button>
          </form>
        )}
        <div className="my-6 flex items-center gap-3 text-xs text-muted"><span className="h-px flex-1 bg-border" />or<span className="h-px flex-1 bg-border" /></div>
        <Link href="/onboarding" className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-md border border-border text-sm font-semibold text-primary hover:bg-surface-subtle"><PlayCircle aria-hidden="true" size={16} /> Open demo setup</Link>
      </section>
    </main>
  );
}

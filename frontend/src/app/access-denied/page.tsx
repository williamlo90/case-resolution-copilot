import { AccountExit } from "@/components/access/account-exit";
import { providerAuthenticationEnabled } from "@/config/authentication";
import { ShieldAlert } from "lucide-react";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Workspace access needed" };

export default function AccessDeniedPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-canvas px-4 py-10">
      <section className="w-full max-w-lg border border-warning/30 bg-surface px-6 py-7 sm:px-8">
        <ShieldAlert aria-hidden="true" className="text-warning" size={24} />
        <h1 className="mt-4 text-2xl font-semibold text-primary">
          This account needs workspace access
        </h1>
        <p className="mt-2 text-sm leading-6 text-secondary">
          Your sign-in worked, but this account has not been added to an active
          workspace. Ask a workspace administrator to add the account, or sign
          out and use another one.
        </p>
        <div className="mt-6">
          <AccountExit
            providerAuthentication={providerAuthenticationEnabled()}
          />
        </div>
      </section>
    </main>
  );
}

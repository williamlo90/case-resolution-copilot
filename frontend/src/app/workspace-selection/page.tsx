import { AccountExit } from "@/components/access/account-exit";
import { providerAuthenticationEnabled } from "@/config/authentication";
import { Building2 } from "lucide-react";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Choose a workspace" };

export default function WorkspaceSelectionPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-canvas px-4 py-10">
      <section className="w-full max-w-lg border border-border bg-surface px-6 py-7 sm:px-8">
        <Building2 aria-hidden="true" className="text-action" size={24} />
        <h1 className="mt-4 text-2xl font-semibold text-primary">
          One workspace must be selected
        </h1>
        <p className="mt-2 text-sm leading-6 text-secondary">
          This account is linked to more than one active workspace. Ask an
          administrator to select the workspace that should be used for this
          pilot, or sign out and use another account.
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

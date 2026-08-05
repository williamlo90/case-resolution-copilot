import { AccountExit } from "@/components/access/account-exit";
import { providerAuthenticationEnabled } from "@/config/authentication";
import { ArrowLeft, ShieldAlert } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Page access unavailable" };

export default function PermissionDeniedPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-canvas px-4 py-10">
      <section className="w-full max-w-lg border border-warning/30 bg-surface px-6 py-7 sm:px-8">
        <ShieldAlert aria-hidden="true" className="text-warning" size={24} />
        <h1 className="mt-4 text-2xl font-semibold text-primary">
          Your role cannot open this page
        </h1>
        <p className="mt-2 text-sm leading-6 text-secondary">
          You still have workspace access. Return to your cases, or ask a
          workspace administrator if you need different access.
        </p>
        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Link
            href="/cases"
            className="inline-flex h-10 items-center gap-2 rounded-md bg-action px-4 text-sm font-semibold text-white hover:bg-action-strong"
          >
            <ArrowLeft aria-hidden="true" size={16} />
            Return to cases
          </Link>
          <AccountExit
            providerAuthentication={providerAuthenticationEnabled()}
          />
        </div>
      </section>
    </main>
  );
}

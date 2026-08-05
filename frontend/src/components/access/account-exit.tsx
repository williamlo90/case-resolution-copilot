"use client";

import { SignOutButton } from "@clerk/nextjs";
import { LogOut } from "lucide-react";
import Link from "next/link";

export function AccountExit({
  providerAuthentication,
}: {
  providerAuthentication: boolean;
}) {
  const className =
    "inline-flex h-10 items-center gap-2 rounded-md border border-border px-4 text-sm font-semibold text-primary hover:bg-surface-subtle";

  if (!providerAuthentication) {
    return (
      <Link href="/sign-in" className={className}>
        <LogOut aria-hidden="true" size={16} />
        Return to sign in
      </Link>
    );
  }

  return (
    <SignOutButton redirectUrl="/sign-in">
      <button type="button" className={className}>
        <LogOut aria-hidden="true" size={16} />
        Sign out
      </button>
    </SignOutButton>
  );
}

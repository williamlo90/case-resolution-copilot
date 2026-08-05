import { providerAuthenticationEnabled } from "@/config/authentication";
import { SignInPage } from "@/features/access/components/sign-in-page";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Accept invitation" };

export default function InviteRoute() {
  return (
    <SignInPage
      invite
      providerAuthentication={providerAuthenticationEnabled()}
    />
  );
}

import { providerAuthenticationEnabled } from "@/config/authentication";
import { SignInPage } from "@/features/access/components/sign-in-page";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Sign in" };

export default function SignInRoute() {
  return (
    <SignInPage
      providerAuthentication={providerAuthenticationEnabled()}
    />
  );
}

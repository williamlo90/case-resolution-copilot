import { ClerkProvider } from "@clerk/nextjs";
import {
  assertProviderAuthenticationConfigured,
  providerAuthenticationEnabled,
} from "@/config/authentication";
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "Case Resolution Copilot",
    template: "%s - Case Resolution Copilot",
  },
  description:
    "Policy-governed case resolution with evidence-bound proposals, human approval, and controlled actions.",
  robots: {
    index: false,
    follow: false,
    noarchive: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const providerAuthentication = providerAuthenticationEnabled();
  if (providerAuthentication) {
    assertProviderAuthenticationConfigured();
  }
  const document = (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-canvas text-primary">{children}</body>
    </html>
  );
  if (!providerAuthentication) {
    return document;
  }
  return (
    <ClerkProvider
      dynamic
      signInUrl="/sign-in"
      signUpUrl="/invite"
      signInFallbackRedirectUrl="/cases"
      signInForceRedirectUrl="/cases"
      signUpFallbackRedirectUrl="/cases"
      signUpForceRedirectUrl="/cases"
      afterSignOutUrl="/sign-in"
    >
      {document}
    </ClerkProvider>
  );
}

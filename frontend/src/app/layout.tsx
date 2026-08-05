import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Case Resolution Copilot",
  description: "A policy-governed workspace for complex support decisions.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

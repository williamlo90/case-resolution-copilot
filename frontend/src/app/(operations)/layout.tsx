import { AppShell, type ShellContext } from "@/components/layout/app-shell";
import type { ReactNode } from "react";

const demoContext: ShellContext = {
  organizationName: "Northstar Cloud",
  actorName: "Ari Specialist",
  actorRole: "specialist",
  locale: "en-US",
  timeZone: "UTC",
  permissions: ["cases:view"],
};

export default function OperationsLayout({ children }: { children: ReactNode }) {
  return <AppShell context={demoContext}>{children}</AppShell>;
}

"use client";

import { Menu, X } from "lucide-react";
import { usePathname } from "next/navigation";
import { useCallback, useRef, useState, type ReactNode } from "react";
import { useModalDialog } from "@/components/accessibility/use-modal-dialog";
import { PresentationProvider } from "@/components/providers/presentation-provider";
import { AppNavigation, type AppPermission } from "./app-navigation";

export type ShellContext = {
  organizationName: string;
  actorName: string;
  actorRole: string;
  locale: string;
  timeZone: string;
  permissions: readonly AppPermission[];
};

export function AppShell({
  children,
  context,
}: {
  children: ReactNode;
  context: ShellContext;
}) {
  const pathname = usePathname();
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);
  const mobileDialogRef = useRef<HTMLElement>(null);
  const mobileCloseButtonRef = useRef<HTMLButtonElement>(null);
  const mobileMenuButtonRef = useRef<HTMLButtonElement>(null);
  const closeMobileNavigation = useCallback(() => {
    setMobileNavigationOpen(false);
    window.setTimeout(() => mobileMenuButtonRef.current?.focus(), 0);
  }, []);

  useModalDialog({
    open: mobileNavigationOpen,
    dialogRef: mobileDialogRef,
    initialFocusRef: mobileCloseButtonRef,
    onDismiss: closeMobileNavigation,
  });

  const permissions = new Set(context.permissions);
  const actorInitials = context.actorName
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  const navigationProps = {
    pathname,
    permissions,
    organizationName: context.organizationName,
    workspaceMode: "Demo",
    actorName: context.actorName,
    actorRole: context.actorRole,
  };

  return (
    <div className="min-h-screen bg-canvas">
      <a
        href="#main-content"
        className="fixed left-3 top-3 z-[60] -translate-y-20 rounded-md bg-action px-3 py-2 text-sm font-semibold text-white focus:translate-y-0"
      >
        Skip to content
      </a>

      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[232px] flex-col bg-[#17232d] lg:flex">
        <AppNavigation {...navigationProps} />
      </aside>

      {mobileNavigationOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Dismiss navigation"
            tabIndex={-1}
            className="absolute inset-0 bg-black/45"
            onClick={closeMobileNavigation}
          />
          <aside
            ref={mobileDialogRef}
            id="mobile-navigation"
            role="dialog"
            aria-modal="true"
            aria-label="Navigation menu"
            tabIndex={-1}
            className="relative flex h-full w-[280px] flex-col bg-[#17232d] shadow-2xl"
          >
            <button
              ref={mobileCloseButtonRef}
              type="button"
              aria-label="Close navigation"
              onClick={closeMobileNavigation}
              className="absolute right-3 top-3 grid size-10 place-items-center rounded-md text-white/70 hover:bg-white/8 hover:text-white"
            >
              <X aria-hidden="true" size={19} />
            </button>
            <AppNavigation {...navigationProps} onNavigate={closeMobileNavigation} />
          </aside>
        </div>
      ) : null}

      <div className="lg:pl-[232px]">
        <header className="sticky top-0 z-30 flex h-[60px] items-center justify-between border-b border-border bg-surface/95 px-4 sm:px-6 lg:px-7">
          <button
            ref={mobileMenuButtonRef}
            type="button"
            aria-label="Open navigation"
            aria-controls="mobile-navigation"
            aria-expanded={mobileNavigationOpen}
            onClick={() => setMobileNavigationOpen(true)}
            className="grid size-10 place-items-center rounded-md text-secondary hover:bg-surface-subtle lg:hidden"
          >
            <Menu aria-hidden="true" size={19} />
          </button>
          <div className="ml-auto flex h-10 items-center gap-2 text-sm font-medium text-primary">
            <span className="grid size-7 place-items-center rounded-full bg-[#1d2933] text-[11px] font-bold text-white">
              {actorInitials || "?"}
            </span>
            <span className="hidden sm:inline">{context.actorName}</span>
          </div>
        </header>

        <main id="main-content" className="min-h-[calc(100vh-60px)]">
          <PresentationProvider locale={context.locale} timeZone={context.timeZone}>
            {children}
          </PresentationProvider>
        </main>
      </div>
    </div>
  );
}

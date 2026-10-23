"use client";

import { UserButton } from "@clerk/nextjs";
import { Bell, Menu, X } from "lucide-react";
import { usePathname } from "next/navigation";
import { useModalDialog } from "@/components/accessibility/use-modal-dialog";
import { WorkspaceLink as Link } from "@/components/navigation/workspace-link";
import { PresentationProvider } from "@/components/providers/presentation-provider";
import type { SessionContext } from "@/domain/administration/administration";
import type { ReactNode } from "react";
import { useCallback, useMemo, useRef, useState } from "react";
import { AppNavigation, type AppPermission } from "./app-navigation";

type AppShellProps = {
  children: ReactNode;
  context: SessionContext;
  providerAuthentication?: boolean;
};

const permissionMap: Readonly<Record<string, AppPermission>> = {
  "case:read": "cases:view",
  "review:read": "reviews:view",
  "action:read": "actions:view",
  "policy:read": "policies:view",
  "quality:read": "quality:view",
  "connection:read": "connections:manage",
  "member:read": "team:manage",
  "settings:manage": "settings:manage",
};

export function AppShell({
  children,
  context,
  providerAuthentication = false,
}: AppShellProps) {
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
  const permissions = useMemo(
    () =>
      new Set(
        context.actor.permissions.flatMap((permission) => {
          const mapped = permissionMap[permission];
          return mapped ? [mapped] : [];
        }),
      ),
    [context.actor.permissions],
  );
  const workspaceMode =
    context.actor.authenticationMode === "deterministic_development"
      ? "Demo"
      : "Live";
  const actorInitials = context.actor.name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  const navigationProps = {
    organizationName: context.organization.name,
    workspaceMode,
    actorName: context.actor.name,
    actorRole: context.actor.role ?? "service",
  };

  return (
    <div className="min-h-screen bg-canvas">
      <a
        href="#main-content"
        className="fixed left-3 top-3 z-[60] -translate-y-20 rounded-md bg-action px-3 py-2 text-sm font-semibold text-white focus:translate-y-0"
      >
        Skip to content
      </a>

      <aside
        aria-hidden={mobileNavigationOpen ? true : undefined}
        inert={mobileNavigationOpen ? true : undefined}
        className="fixed inset-y-0 left-0 z-40 hidden w-[232px] flex-col bg-[#17232d] lg:flex"
      >
        <AppNavigation
          pathname={pathname}
          permissions={permissions}
          {...navigationProps}
        />
      </aside>

      {mobileNavigationOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Dismiss navigation"
            aria-hidden="true"
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
              className="absolute right-3 top-3 z-10 grid size-10 place-items-center rounded-md text-white/70 hover:bg-white/8 hover:text-white"
            >
              <X aria-hidden="true" size={19} />
            </button>
            <AppNavigation
              pathname={pathname}
              permissions={permissions}
              {...navigationProps}
              onNavigate={closeMobileNavigation}
            />
          </aside>
        </div>
      ) : null}

      <div
        aria-hidden={mobileNavigationOpen ? true : undefined}
        inert={mobileNavigationOpen ? true : undefined}
        className="lg:pl-[232px]"
      >
        <header className="sticky top-0 z-30 flex h-[60px] items-center justify-between border-b border-border bg-surface/95 px-4 backdrop-blur sm:px-6 lg:px-7">
          <div className="flex items-center gap-3">
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
            <div className="hidden items-center gap-2 text-xs text-secondary sm:flex">
              <span className="size-2 rounded-full bg-success" aria-hidden="true" />
              {workspaceMode === "Demo" ? "Connected simulator" : "Connected workspace"}
            </div>
          </div>

          <div className="flex items-center gap-2" aria-label="Signed in user">
            <Link
              href="/notifications"
              aria-label="Notifications"
              title="Notifications"
              className={`grid size-10 place-items-center rounded-md ${
                pathname.startsWith("/notifications")
                  ? "bg-info-bg text-info"
                  : "text-secondary hover:bg-surface-subtle hover:text-primary"
              }`}
            >
              <Bell aria-hidden="true" size={18} />
            </Link>
            <span className="h-6 w-px bg-border" />
            <div className="flex h-10 items-center gap-2 px-1.5 text-sm font-medium text-primary">
              {providerAuthentication ? (
                <UserButton
                  signInUrl="/sign-in"
                  appearance={{
                    elements: {
                      avatarBox: "size-7",
                    },
                  }}
                />
              ) : (
                <span className="grid size-7 place-items-center rounded-full bg-[#1d2933] text-[11px] font-bold text-white">
                  {actorInitials || "?"}
                </span>
              )}
              <span className="hidden sm:inline">{context.actor.name}</span>
            </div>
          </div>
        </header>

        <main id="main-content" className="min-h-[calc(100vh-60px)]">
          <PresentationProvider
            locale={context.organization.locale}
            timeZone={context.organization.timeZone}
          >
            {children}
          </PresentationProvider>
        </main>
      </div>
    </div>
  );
}

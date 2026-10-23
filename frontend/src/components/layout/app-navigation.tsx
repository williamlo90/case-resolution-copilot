import {
  Activity,
  BookOpen,
  Building2,
  CheckSquare2,
  CircleUserRound,
  FileText,
  Link2,
  Settings,
  ShieldCheck,
  Users,
} from "lucide-react";
import { WorkspaceLink as Link } from "@/components/navigation/workspace-link";

export type AppPermission =
  | "cases:view"
  | "reviews:view"
  | "actions:view"
  | "policies:view"
  | "quality:view"
  | "connections:manage"
  | "team:manage"
  | "settings:manage";

type NavigationItem = {
  label: string;
  href: string;
  activePrefix: string;
  icon: typeof FileText;
  permission: AppPermission;
  available: boolean;
};

const primaryNavigation: readonly NavigationItem[] = [
  { label: "Cases", href: "/cases", activePrefix: "/cases", icon: FileText, permission: "cases:view", available: true },
  { label: "Reviews", href: "/reviews", activePrefix: "/reviews", icon: ShieldCheck, permission: "reviews:view", available: true },
  { label: "Actions", href: "/actions", activePrefix: "/actions", icon: CheckSquare2, permission: "actions:view", available: true },
  { label: "Policies", href: "/policies", activePrefix: "/policies", icon: BookOpen, permission: "policies:view", available: true },
  { label: "Quality", href: "/quality", activePrefix: "/quality", icon: Activity, permission: "quality:view", available: true },
];

const administrativeNavigation: readonly NavigationItem[] = [
  { label: "Connections", href: "/connections", activePrefix: "/connections", icon: Link2, permission: "connections:manage", available: true },
  { label: "Team", href: "/team", activePrefix: "/team", icon: Users, permission: "team:manage", available: true },
  { label: "Settings", href: "/settings/general", activePrefix: "/settings", icon: Settings, permission: "settings:manage", available: true },
];

function NavigationGroup({
  items,
  pathname,
  permissions,
  onNavigate,
}: {
  items: readonly NavigationItem[];
  pathname: string;
  permissions: ReadonlySet<AppPermission>;
  onNavigate?: () => void;
}) {
  return (
    <div className="space-y-1">
      {items.filter((item) => permissions.has(item.permission)).map((item) => {
        const Icon = item.icon;
        const active = pathname.startsWith(item.activePrefix);
        const className = `flex h-10 items-center gap-3 rounded-md px-3 text-sm font-medium transition-colors ${
          active ? "bg-[#0f817c] text-white" : "text-white/72 hover:bg-white/7 hover:text-white"
        }`;

        if (!item.available) {
          return (
            <span
              key={item.label}
              aria-disabled="true"
              title={`${item.label} is not available in the current frontend sprint`}
              className="flex h-10 cursor-not-allowed items-center gap-3 rounded-md px-3 text-sm font-medium text-white/38"
            >
              <Icon aria-hidden="true" size={18} strokeWidth={1.8} />
              <span>{item.label}</span>
            </span>
          );
        }

        return (
          <Link
            key={item.label}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={className}
          >
            <Icon aria-hidden="true" size={18} strokeWidth={1.8} />
            <span>{item.label}</span>
          </Link>
        );
      })}
    </div>
  );
}

export function AppNavigation({
  pathname,
  permissions,
  organizationName,
  workspaceMode,
  actorName,
  actorRole,
  onNavigate,
}: {
  pathname: string;
  permissions: ReadonlySet<AppPermission>;
  organizationName: string;
  workspaceMode: string;
  actorName: string;
  actorRole: string;
  onNavigate?: () => void;
}) {
  const initials = actorName
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <>
      <div className="flex h-[68px] items-center border-b border-white/10 px-3">
        <div className="flex h-10 w-full items-center gap-2 rounded-md border border-white/12 px-2.5 text-left text-sm font-semibold text-white">
          <span className="grid size-7 place-items-center rounded bg-white/9 text-[#5dd5c8]">
            <Building2 aria-hidden="true" size={16} />
          </span>
          <span className="min-w-0 flex-1 truncate">{organizationName}</span>
          <span className="text-[10px] font-medium uppercase text-white/45">
            {workspaceMode}
          </span>
        </div>
      </div>

      <nav aria-label="Primary navigation" className="flex-1 px-2.5 py-4">
        <NavigationGroup items={primaryNavigation} pathname={pathname} permissions={permissions} onNavigate={onNavigate} />
        <div className="my-4 border-t border-white/10" />
        <NavigationGroup items={administrativeNavigation} pathname={pathname} permissions={permissions} onNavigate={onNavigate} />
      </nav>

      <div className="border-t border-white/10 p-3">
        <div className="flex items-center gap-3 rounded-md px-2 py-2">
          <span className="grid size-8 place-items-center rounded-full bg-[#dcefee] text-xs font-bold text-[#0c6965]">
            {initials || "?"}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold text-white">{actorName}</p>
            <p className="truncate text-[11px] capitalize text-white/48">
              {actorRole}
            </p>
          </div>
          <CircleUserRound aria-hidden="true" size={16} className="text-white/36" />
        </div>
      </div>
    </>
  );
}

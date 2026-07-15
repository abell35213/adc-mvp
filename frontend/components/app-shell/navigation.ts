import { hasRoleCapability } from "@/lib/permissions";

export type ShellVariant = "default" | "admin";
export type NavigationSection = "primary" | "secondary";

export interface ShellNavItem {
  href: string;
  label: string;
  section: NavigationSection;
  icon: "command" | "cases" | "evidence" | "exports" | "vehicles" | "reports" | "settings" | "help" | "admin";
  activePrefixes?: string[];
  hidden?: boolean;
}

export function getDefaultLandingForRole(role: string): string {
  switch (role) {
    case "admin":
      return "/admin/driver-protocol";
    case "legal_reviewer":
      return "/exports";
    case "operator":
    case "safety_manager":
      return "/incidents";
    default:
      return "/dashboard";
  }
}

export function routeIsActive(pathname: string, href: string, prefixes: string[] = []): boolean {
  const candidates = [href, ...prefixes];
  return candidates.some((candidate) => pathname === candidate || pathname.startsWith(`${candidate}/`));
}

export function getOrganizationLabel(orgIds: string[]): string {
  const first = orgIds[0];
  if (!first) return "Primary organization";
  if (/^[a-f0-9-]{20,}$/i.test(first)) return "Primary organization";
  return first.replace(/[-_]/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

export function buildNavigation(role: string, variant: ShellVariant = "default"): ShellNavItem[] {
  const canViewReadiness = hasRoleCapability(role, "readiness:view");
  const canManageQr = hasRoleCapability(role, "vehicle_qr:write");
  const canViewAdmin = hasRoleCapability(role, "vehicle_qr:read");
  const canManageUsers = hasRoleCapability(role, "user_management:write");

  const base: ShellNavItem[] = [
    { href: "/dashboard", label: "Command Center", section: "primary", icon: "command" },
    { href: "/incidents", label: "Cases", section: "primary", icon: "cases", activePrefixes: ["/incidents"] },
    { href: "/timeline", label: "Evidence", section: "primary", icon: "evidence" },
    { href: "/exports", label: "Exports", section: "primary", icon: "exports", activePrefixes: ["/exports"] },
    { href: "/vehicles", label: "Vehicles", section: "primary", icon: "vehicles", hidden: !canManageQr },
    { href: "/reports", label: "Reports", section: "primary", icon: "reports" },
    { href: "/help", label: "Help", section: "secondary", icon: "help" },
    { href: "/settings/integrations", label: "Settings", section: "secondary", icon: "settings", hidden: !canViewReadiness },
    { href: "/admin/ops", label: "Administration", section: "secondary", icon: "admin", activePrefixes: ["/admin"], hidden: !canViewAdmin },
  ];

  if (variant !== "admin") return base.filter((item) => !item.hidden);

  const adminItems: ShellNavItem[] = [
    { href: "/admin/ops", label: "Admin overview", section: "primary", icon: "admin", activePrefixes: ["/admin/ops"] },
    { href: "/admin/driver-protocol", label: "Driver Protocol", section: "primary", icon: "evidence", activePrefixes: ["/admin/driver-protocol"] },
    { href: "/admin/vehicles", label: "Admin Vehicles", section: "primary", icon: "vehicles", activePrefixes: ["/admin/vehicles"], hidden: !canManageQr },
    { href: "/admin/plan-features", label: "Plan & Features", section: "primary", icon: "settings", activePrefixes: ["/admin/plan-features"], hidden: !canManageUsers },
    { href: "/help", label: "Help", section: "secondary", icon: "help" },
    { href: "/dashboard", label: "Command Center", section: "secondary", icon: "command" },
  ];

  return adminItems.filter((item) => !item.hidden);
}

export type AppCapability =
  | "org_settings:read"
  | "org_settings:write"
  | "user_management:read"
  | "user_management:write"
  | "imports:read"
  | "imports:write"
  | "vehicle_qr:read"
  | "vehicle_qr:write"
  | "integrations:read"
  | "integrations:write"
  | "onboarding:read"
  | "onboarding:write"
  | "test_runs:read"
  | "test_runs:write"
  | "readiness:view";

const ROLE_CAPABILITIES: Record<string, ReadonlySet<AppCapability>> = {
  system_admin: new Set<AppCapability>([
    "org_settings:read",
    "org_settings:write",
    "user_management:read",
    "user_management:write",
    "imports:read",
    "imports:write",
    "vehicle_qr:read",
    "vehicle_qr:write",
    "integrations:read",
    "integrations:write",
    "onboarding:read",
    "onboarding:write",
    "test_runs:read",
    "test_runs:write",
    "readiness:view",
  ]),
  org_admin: new Set<AppCapability>([
    "org_settings:read",
    "org_settings:write",
    "user_management:read",
    "user_management:write",
    "imports:read",
    "imports:write",
    "vehicle_qr:read",
    "vehicle_qr:write",
    "integrations:read",
    "integrations:write",
    "onboarding:read",
    "onboarding:write",
    "test_runs:read",
    "test_runs:write",
    "readiness:view",
  ]),
  safety_manager: new Set<AppCapability>([
    "imports:read",
    "imports:write",
    "vehicle_qr:read",
    "vehicle_qr:write",
    "integrations:read",
    "onboarding:read",
    "onboarding:write",
    "test_runs:read",
    "test_runs:write",
    "readiness:view",
  ]),
  read_only: new Set<AppCapability>([
    "org_settings:read",
    "user_management:read",
    "imports:read",
    "vehicle_qr:read",
    "integrations:read",
    "onboarding:read",
    "test_runs:read",
    "readiness:view",
  ]),
  support_admin: new Set<AppCapability>([
    "org_settings:read",
    "org_settings:write",
    "user_management:read",
    "user_management:write",
    "imports:read",
    "imports:write",
    "vehicle_qr:read",
    "vehicle_qr:write",
    "integrations:read",
    "integrations:write",
    "onboarding:read",
    "onboarding:write",
    "test_runs:read",
    "test_runs:write",
    "readiness:view",
  ]),
  support_agent: new Set<AppCapability>([
    "org_settings:read",
    "user_management:read",
    "imports:read",
    "vehicle_qr:read",
    "integrations:read",
    "onboarding:read",
    "test_runs:read",
    "readiness:view",
  ]),
};

export function hasRoleCapability(role: string | null | undefined, capability: AppCapability): boolean {
  const normalized = (role ?? "").trim().toLowerCase();
  return ROLE_CAPABILITIES[normalized]?.has(capability) ?? false;
}


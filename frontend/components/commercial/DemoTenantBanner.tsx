interface DemoTenantBannerProps {
  tenantName: string;
  mode: "Sandbox" | "Pilot";
}

export default function DemoTenantBanner({ tenantName, mode }: DemoTenantBannerProps) {
  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-200">
      <p className="font-semibold">{tenantName} demo tenant</p>
      <p>
        Environment mode: <span className="font-medium">{mode}</span>. Actions in this workspace are non-production.
      </p>
    </div>
  );
}

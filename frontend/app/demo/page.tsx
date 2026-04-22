import MainLayout from "@/components/MainLayout";
import DemoScenarioLauncher from "@/components/commercial/DemoScenarioLauncher";
import DemoTenantBanner from "@/components/commercial/DemoTenantBanner";
import FeatureGate from "@/components/commercial/FeatureGate";

export default function DemoPage() {
  return (
    <MainLayout title="Demo Workspace">
      <div className="space-y-4">
        <DemoTenantBanner tenantName="Northstar Logistics" mode="Sandbox" />
        <DemoScenarioLauncher
          scenarios={[
            {
              id: "onboarding-recovery",
              label: "Onboarding recovery",
              description: "Simulates mapping + integration blockers with guided remediation.",
            },
            {
              id: "incident-queue-spike",
              label: "Incident queue spike",
              description: "Loads a high-volume queue with mixed driver response status.",
            },
            {
              id: "enterprise-multi-org",
              label: "Enterprise multi-org",
              description: "Cross-org tenancy demo for internal teams.",
              enabled: false,
            },
          ]}
        />

        <FeatureGate
          available={false}
          requiredPlan="Enterprise"
          reason="Cross-org demo orchestration is available only on Enterprise plans."
        >
          <div className="rounded border bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
            <h3 className="font-semibold">Cross-org orchestration console</h3>
            <p className="text-sm text-gray-600 dark:text-gray-300">Provision demo users across tenants.</p>
          </div>
        </FeatureGate>
      </div>
    </MainLayout>
  );
}

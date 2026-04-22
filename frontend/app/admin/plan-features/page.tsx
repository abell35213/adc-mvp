"use client";

import MainLayout from "@/components/MainLayout";
import CommercialSummaryCards from "@/components/commercial/CommercialSummaryCards";
import FeatureGate from "@/components/commercial/FeatureGate";
import PlanBadge from "@/components/commercial/PlanBadge";
import { hasRoleCapability } from "@/lib/permissions";
import { useAuth } from "@/lib/useAuth";

export default function PlanFeaturesPage() {
  const { user } = useAuth();
  const isOrgOrInternalAdmin = hasRoleCapability(user?.role, "user_management:write");

  return (
    <MainLayout title="Plan & Features">
      <div className="space-y-4">
        <header>
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">Plan and feature controls</h2>
          <p className="text-sm text-gray-600 dark:text-gray-300">
            Feature availability by plan tier for organization and internal administrators.
          </p>
        </header>

        <FeatureGate
          available={isOrgOrInternalAdmin}
          mode="hide"
          reason="Only organization and internal admins can access commercial feature controls."
        >
          <>
            <CommercialSummaryCards
              items={[
                { label: "Current tier", value: "Growth", detail: "Billing cycle renews in 14 days" },
                { label: "Enabled add-ons", value: "3", detail: "Includes export governance" },
                { label: "Locked features", value: "2", detail: "Available with Enterprise" },
                { label: "Admin seats", value: "8", detail: "2 seats available" },
              ]}
            />

            <div className="grid gap-3 md:grid-cols-2">
              <section className="rounded-lg border bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold">Demo orchestration</h3>
                  <PlanBadge plan="Growth" />
                </div>
                <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">
                  Single-tenant scenario launcher and canned onboarding recovery playbooks.
                </p>
              </section>

              <FeatureGate
                available={false}
                requiredPlan="Enterprise"
                reason="Cross-organization orchestration and delegated support controls require Enterprise tier."
              >
                <section className="rounded-lg border bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold">Cross-org controls</h3>
                    <PlanBadge plan="Enterprise" />
                  </div>
                  <button
                    type="button"
                    disabled
                    className="mt-3 rounded bg-gray-300 px-3 py-1 text-sm font-medium text-gray-700"
                  >
                    Enable delegated support access
                  </button>
                </section>
              </FeatureGate>
            </div>
          </>
        </FeatureGate>
      </div>
    </MainLayout>
  );
}

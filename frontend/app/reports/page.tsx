import MainLayout from "@/components/MainLayout";
import CommercialSummaryCards from "@/components/commercial/CommercialSummaryCards";

export default function ReportsPage() {
  return (
    <MainLayout title="Commercial Reports">
      <div className="space-y-4">
        <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">Commercial performance reports</h2>
        <CommercialSummaryCards
          items={[
            { label: "Active tenants", value: "48", detail: "+6 from last quarter" },
            { label: "Pilot conversions", value: "73%", detail: "12-month rolling average" },
            { label: "Expansion-ready markets", value: "5", detail: "2 blocked by protocol gaps" },
            { label: "Support SLA attainment", value: "99.4%", detail: "Last 30 days" },
          ]}
        />
      </div>
    </MainLayout>
  );
}

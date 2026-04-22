import MainLayout from "@/components/MainLayout";
import TrustSectionCard from "@/components/commercial/TrustSectionCard";

export default function TrustPage() {
  return (
    <MainLayout title="Trust Center">
      <div className="grid gap-4 md:grid-cols-2">
        <TrustSectionCard
          title="Security controls"
          summary="Operational controls designed for legal and safety workflows."
          highlights={[
            "Role-based access control across operations and administration surfaces.",
            "Immutable export audit trail with event-level timestamps.",
            "Scoped production and sandbox tenant isolation.",
          ]}
        />
        <TrustSectionCard
          title="Compliance evidence"
          summary="Artifacts and runbooks used by internal and customer compliance teams."
          highlights={[
            "Incident evidence retention policies aligned with export obligations.",
            "Onboarding readiness checkpoints with blocker ownership.",
            "Documented deployment SOPs for phased market launches.",
          ]}
        />
      </div>
    </MainLayout>
  );
}

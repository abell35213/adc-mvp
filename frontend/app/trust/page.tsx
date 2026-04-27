import MainLayout from "@/components/MainLayout";
import ReportSummaryCards from "@/components/reports/ReportSummaryCards";
import TrustSectionCard from "@/components/support/TrustSectionCard";

const TRUST_SECTIONS = [
  {
    id: "security-controls",
    title: "Security controls",
    summary: "Controls focused on protecting operational evidence and limiting access to need-to-know teams.",
    points: [
      "Role-based access separates incident operators, managers, and administrators.",
      "Export activity is recorded with immutable audit events and actor timestamps.",
      "Production and sandbox tenant data are scoped to prevent cross-environment bleed.",
    ],
  },
  {
    id: "compliance-evidence",
    title: "Compliance evidence",
    summary: "Short-form artifacts that help legal and compliance teams verify readiness and retention posture.",
    points: [
      "Retention policy summary maps evidence classes to required storage windows.",
      "Runbook checkpoints define owner and next action for blocked readiness cases.",
      "Quarterly control attestations are packaged with export readiness reports.",
    ],
  },
  {
    id: "incident-response",
    title: "Incident response",
    summary: "Operational response commitments and escalation mechanics for security-impacting events.",
    points: [
      "On-call rotation guarantees acknowledgement targets for critical events.",
      "Post-incident reviews capture corrective actions and ownership deadlines.",
      "Customer communication templates support timely trust updates.",
    ],
  },
];

export default function TrustPage() {
  return (
    <MainLayout title="Trust Center">
      <div className="space-y-4">
        <section className="rounded-lg border border-border-default bg-surface p-4 shadow-card">
          <h2 className="text-xl font-semibold text-text-primary">Trust and assurance overview</h2>
          <p className="mt-1 text-sm text-text-secondary">
            Review concise controls, evidence commitments, and next actions for audit-ready operations.
          </p>
          <nav className="mt-3 flex flex-wrap gap-2 text-sm">
            {TRUST_SECTIONS.map((section) => (
              <a
                key={section.id}
                href={`#${section.id}`}
                className="rounded-md border border-border-subtle px-3 py-1.5 text-text-secondary hover:bg-surface-raised"
              >
                {section.title}
              </a>
            ))}
          </nav>
        </section>

        <ReportSummaryCards
          items={[
            { id: "trust-control-coverage", label: "Control coverage", value: "96%", detail: "Core controls documented", tone: "success" },
            { id: "trust-open-followups", label: "Open trust follow-ups", value: "4", detail: "2 require policy sign-off", tone: "warning" },
            { id: "trust-audit-blockers", label: "Audit blockers", value: "1", detail: "Pending vendor attestation", tone: "critical" },
            { id: "trust-latest-review", label: "Latest review", value: "Apr 22", detail: "Quarterly trust review completed" },
          ]}
        />

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {TRUST_SECTIONS.map((section) => (
            <TrustSectionCard
              key={section.id}
              id={section.id}
              title={section.title}
              summary={section.summary}
              points={section.points}
            />
          ))}
        </section>
      </div>
    </MainLayout>
  );
}

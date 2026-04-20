import MainLayout from "@/components/MainLayout";
import DocumentationCenter from "@/components/commercial/DocumentationCenter";
import RelatedDocsPanel from "@/components/commercial/RelatedDocsPanel";

export default function HelpPage() {
  const docs = [
    { title: "Onboarding setup guide", href: "/onboarding", description: "Step-by-step launch checklist and blockers." },
    { title: "Incident operations", href: "/incidents", description: "Queue management, response tracking, and evidence coverage." },
    { title: "Export package details", href: "/exports", description: "Audit history, package manifests, and legal-ready delivery." },
  ];

  return (
    <MainLayout title="Help Center">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <DocumentationCenter docs={docs} />
        <RelatedDocsPanel
          docs={[
            { title: "Trust center", href: "/trust", description: "Security and compliance posture details." },
            { title: "Deployment coverage", href: "/deployment", description: "Market expansion and rollout readiness." },
          ]}
        />
      </div>
    </MainLayout>
  );
}

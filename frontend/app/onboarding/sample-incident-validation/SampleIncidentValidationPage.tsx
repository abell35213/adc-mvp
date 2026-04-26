"use client";

import { useEffect, useMemo, useState } from "react";
import MainLayout from "@/components/MainLayout";
import OnboardingStepLayout from "@/components/onboarding/OnboardingStepLayout";
import SampleIncidentRunPanel from "@/components/onboarding/SampleIncidentRunPanel";
import { getOrgOnboardingStatus, toUserErrorMessage, type OrgLaunchReadiness } from "@/lib/api";
import { getReadinessBlockersForStep, getReadinessStepStatus } from "@/lib/onboarding";

export default function SampleIncidentValidationPage() {
  const [readiness, setReadiness] = useState<OrgLaunchReadiness | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getOrgOnboardingStatus()
      .then((payload) => {
        setReadiness(payload);
        setError("");
      })
      .catch((err) => setError(toUserErrorMessage(err, "Failed to load sample incident validation data")));
  }, []);

  const status = useMemo(() => getReadinessStepStatus(readiness?.steps ?? [], "testIncidentCompleted"), [readiness]);
  const blockers = useMemo(
    () => getReadinessBlockersForStep(readiness?.blockers ?? [], "testIncidentCompleted"),
    [readiness]
  );

  return (
    <MainLayout title="Sample Incident Validation">
      <OnboardingStepLayout
        title="Sample incident validation"
        breadcrumbs={[{ label: "Onboarding", href: "/onboarding" }, { label: "Sample Incident Validation" }]}
        progressRow={<p className="text-sm text-gray-700">Step status: <span className="font-semibold">{status.replaceAll("_", " ")}</span></p>}
        whyThisMatters="A successful sample incident validates end-to-end readiness and confirms teams can complete the next critical action quickly."
        requirements={[
          "Run a sample incident through workflow.",
          "Capture findings and resolve critical execution issues.",
        ]}
        blockingIssues={
          blockers.length === 0 ? (
            <p>No blocking issues reported.</p>
          ) : (
            <ul className="space-y-2">
              {blockers.map((blocker) => (
                <li key={blocker.code}>
                  <p className="font-semibold">{blocker.title}</p>
                  <p>{blocker.detail}</p>
                </li>
              ))}
            </ul>
          )
        }
        helpLinks={[
          { label: "Open dashboard blockers", href: "/dashboard?blockers=critical" },
          { label: "Back to onboarding wizard", href: "/onboarding" },
        ]}
        backAction={{ label: "Back", href: "/onboarding/mapping-validation" }}
        saveDraftAction={{ label: "Save Draft", href: "/onboarding" }}
        continueAction={{ label: "Continue", href: "/onboarding/qr-deployment" }}
      >
        <div className="space-y-4">
          {error ? <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
          <SampleIncidentRunPanel status={status} blockers={blockers} />
        </div>
      </OnboardingStepLayout>
    </MainLayout>
  );
}

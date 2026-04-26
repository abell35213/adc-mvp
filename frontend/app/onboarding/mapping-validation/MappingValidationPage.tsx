"use client";

import { useEffect, useMemo, useState } from "react";
import MainLayout from "@/components/MainLayout";
import MappingValidationPanel from "@/components/onboarding/MappingValidationPanel";
import OnboardingStepLayout from "@/components/onboarding/OnboardingStepLayout";
import { getOrgOnboardingStatus, toUserErrorMessage, type OrgLaunchReadiness } from "@/lib/api";
import { getReadinessBlockersForStep, getReadinessStepStatus } from "@/lib/onboarding";

export default function MappingValidationPage() {
  const [readiness, setReadiness] = useState<OrgLaunchReadiness | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getOrgOnboardingStatus()
      .then((payload) => {
        setReadiness(payload);
        setError("");
      })
      .catch((err) => setError(toUserErrorMessage(err, "Failed to load mapping validation data")));
  }, []);

  const status = useMemo(() => getReadinessStepStatus(readiness?.steps ?? [], "mappings"), [readiness]);
  const blockers = useMemo(() => getReadinessBlockersForStep(readiness?.blockers ?? [], "mappings"), [readiness]);

  return (
    <MainLayout title="Mapping Validation">
      <OnboardingStepLayout
        title="Mapping validation"
        breadcrumbs={[{ label: "Onboarding", href: "/onboarding" }, { label: "Mapping Validation" }]}
        progressRow={<p className="text-sm text-gray-700">Step status: <span className="font-semibold">{status.replaceAll("_", " ")}</span></p>}
        whyThisMatters="Mapping completeness keeps owner routing and evidence relationships correct from intake to export readiness."
        requirements={[
          "Map external entities needed for case operations.",
          "Resolve any mapping gaps that impact pilot readiness.",
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
          { label: "Open remediation actions", href: "/onboarding/mapping-validation" },
          { label: "Back to onboarding wizard", href: "/onboarding" },
        ]}
        backAction={{ label: "Back", href: "/onboarding/protocol-setup" }}
        saveDraftAction={{ label: "Save Draft", href: "/onboarding" }}
        continueAction={{ label: "Continue", href: "/onboarding/sample-incident-validation" }}
      >
        <div className="space-y-4">
          {error ? <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
          <MappingValidationPanel status={status} blockers={blockers} />
        </div>
      </OnboardingStepLayout>
    </MainLayout>
  );
}

"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import MainLayout from "@/components/MainLayout";
import IntegrationValidationPanel from "@/components/onboarding/IntegrationValidationPanel";
import OnboardingStepLayout from "@/components/onboarding/OnboardingStepLayout";
import {
  getIntegrationValidationResults,
  getOrgOnboardingStatus,
  toUserErrorMessage,
  type IntegrationValidationResult,
  type OrgLaunchReadiness,
} from "@/lib/api";
import { getReadinessStepStatus } from "@/lib/onboarding";

export default function IntegrationSetupPage() {
  const [readiness, setReadiness] = useState<OrgLaunchReadiness | null>(null);
  const [results, setResults] = useState<IntegrationValidationResult[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getOrgOnboardingStatus(), getIntegrationValidationResults()])
      .then(([readinessPayload, validationPayload]) => {
        setReadiness(readinessPayload);
        setResults(validationPayload);
        setError("");
      })
      .catch((err) => setError(toUserErrorMessage(err, "Failed to load integration setup data")));
  }, []);

  const status = useMemo(() => getReadinessStepStatus(readiness?.steps ?? [], "integrations"), [readiness]);
  const blockers = useMemo(
    () => readiness?.blockers.filter((blocker) => blocker.blocking_step_key === "integrations") ?? [],
    [readiness]
  );

  return (
    <MainLayout title="Integration Setup">
      <OnboardingStepLayout
        title="Integration setup"
        breadcrumbs={[{ label: "Onboarding", href: "/onboarding" }, { label: "Integration Setup" }]}
        progressRow={<p className="text-sm text-gray-700">Step status: <span className="font-semibold">{status.replaceAll("_", " ")}</span></p>}
        whyThisMatters="Integration health controls evidence capture quality and determines whether operators can trust incoming incident data."
        requirements={[
          "Activate at least one integration connection.",
          "Address integration validation errors before launch.",
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
          { label: "Open integrations settings", href: "/settings/integrations" },
          { label: "Back to onboarding wizard", href: "/onboarding" },
        ]}
        backAction={{ label: "Back", href: "/onboarding" }}
        saveDraftAction={{ label: "Save Draft", href: "/onboarding" }}
        continueAction={{ label: "Continue", href: "/onboarding/protocol-setup" }}
      >
        <div className="space-y-4">
          {error ? <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
          <IntegrationValidationPanel status={status} results={results} />
          <Link className="text-sm font-semibold text-blue-700 hover:underline" href="/settings/integrations">
            Open remediation actions
          </Link>
        </div>
      </OnboardingStepLayout>
    </MainLayout>
  );
}

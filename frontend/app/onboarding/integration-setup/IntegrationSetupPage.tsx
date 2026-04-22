"use client";

import { useEffect, useMemo, useState } from "react";
import MainLayout from "@/components/MainLayout";
import IntegrationValidationPanel from "@/components/onboarding/IntegrationValidationPanel";
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

  return (
    <MainLayout title="Integration Setup">
      <div className="space-y-4">
        {error ? <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
        <IntegrationValidationPanel status={status} results={results} />
      </div>
    </MainLayout>
  );
}

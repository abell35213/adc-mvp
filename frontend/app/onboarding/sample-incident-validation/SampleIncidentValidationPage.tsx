"use client";

import { useEffect, useMemo, useState } from "react";
import MainLayout from "@/components/MainLayout";
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
      <div className="space-y-4">
        {error ? <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
        <SampleIncidentRunPanel status={status} blockers={blockers} />
      </div>
    </MainLayout>
  );
}

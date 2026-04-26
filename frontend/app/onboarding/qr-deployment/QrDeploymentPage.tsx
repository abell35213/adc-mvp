"use client";

import { useEffect, useMemo, useState } from "react";
import MainLayout from "@/components/MainLayout";
import OnboardingStepLayout from "@/components/onboarding/OnboardingStepLayout";
import QrDeploymentTable from "@/components/onboarding/QrDeploymentTable";
import {
  getOrgOnboardingQrStats,
  getOrgOnboardingStatus,
  toUserErrorMessage,
  type OrgLaunchReadiness,
  type VehicleQrStats,
} from "@/lib/api";
import { getReadinessStepStatus } from "@/lib/onboarding";
import { formatStatus, getStatusClasses } from "@/components/onboarding/status";

const EMPTY_QR_STATS: VehicleQrStats = {
  required_vehicle_count: 0,
  generated_count: 0,
  distributed_count: 0,
  confirmed_count: 0,
  coverage_blockers: [],
};

export default function QrDeploymentPage() {
  const [readiness, setReadiness] = useState<OrgLaunchReadiness | null>(null);
  const [qrStats, setQrStats] = useState<VehicleQrStats>(EMPTY_QR_STATS);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getOrgOnboardingStatus(), getOrgOnboardingQrStats()])
      .then(([readinessPayload, qrPayload]) => {
        setReadiness(readinessPayload);
        setQrStats(qrPayload);
        setError("");
      })
      .catch((err) => setError(toUserErrorMessage(err, "Failed to load QR deployment data")));
  }, []);

  const status = useMemo(() => getReadinessStepStatus(readiness?.steps ?? [], "vehicle_qr"), [readiness]);
  const blockers = qrStats.coverage_blockers;

  return (
    <MainLayout title="QR Deployment">
      <OnboardingStepLayout
        title="QR deployment"
        breadcrumbs={[{ label: "Onboarding", href: "/onboarding" }, { label: "QR Deployment" }]}
        progressRow={<p className="text-sm text-gray-700">Step status: <span className="font-semibold">{formatStatus(status)}</span></p>}
        whyThisMatters="QR deployment quality drives incident attention speed and ensures events are attached to the right vehicle records."
        requirements={[
          "Generate and distribute vehicle QR tokens.",
          "Track and close outstanding QR deployment coverage blockers.",
        ]}
        blockingIssues={
          blockers.length === 0 ? (
            <p>No blocking issues reported.</p>
          ) : (
            <ul className="space-y-2">
              {blockers.map((blocker) => (
                <li key={blocker}>
                  <p>{blocker}</p>
                </li>
              ))}
            </ul>
          )
        }
        helpLinks={[
          { label: "Open vehicles", href: "/vehicles" },
          { label: "Back to onboarding wizard", href: "/onboarding" },
        ]}
        backAction={{ label: "Back", href: "/onboarding/sample-incident-validation" }}
        saveDraftAction={{ label: "Save Draft", href: "/onboarding" }}
        continueAction={{ label: "Continue", href: "/onboarding" }}
      >
        <div className="space-y-4">
          {error ? <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-semibold text-gray-900">QR deployment coverage</h2>
              <span className={`rounded-full px-2 py-1 text-xs font-semibold ${getStatusClasses(status)}`}>{formatStatus(status)}</span>
            </div>
            <p className="mt-1 text-sm text-gray-600">Track deployment status, blockers, and remediation actions for vehicle QR onboarding.</p>
            <div className="mt-4">
              <QrDeploymentTable stats={qrStats} />
            </div>
          </section>
        </div>
      </OnboardingStepLayout>
    </MainLayout>
  );
}

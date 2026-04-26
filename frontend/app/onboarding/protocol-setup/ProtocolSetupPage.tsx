"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import MainLayout from "@/components/MainLayout";
import OnboardingStepLayout from "@/components/onboarding/OnboardingStepLayout";
import {
  getOrgOnboardingStatus,
  getProtocolSetupStepData,
  toUserErrorMessage,
  type OrgLaunchReadiness,
  type ProtocolSetupStepData,
} from "@/lib/api";
import { getReadinessStepStatus } from "@/lib/onboarding";
import { formatStatus, getStatusClasses } from "@/components/onboarding/status";

const EMPTY_PROTOCOL: ProtocolSetupStepData = {
  instruction_set_selected: false,
  instruction_source: "default",
  safety_contact_configured: false,
  safety_manager_phone: null,
  required_media_prompts_defaulted: false,
  export_profile_defaulted: false,
  export_profiles_available: [],
};

export default function ProtocolSetupPage() {
  const [readiness, setReadiness] = useState<OrgLaunchReadiness | null>(null);
  const [data, setData] = useState<ProtocolSetupStepData>(EMPTY_PROTOCOL);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getOrgOnboardingStatus(), getProtocolSetupStepData()])
      .then(([readinessPayload, protocolPayload]) => {
        setReadiness(readinessPayload);
        setData(protocolPayload);
        setError("");
      })
      .catch((err) => setError(toUserErrorMessage(err, "Failed to load protocol setup data")));
  }, []);

  const status = useMemo(() => getReadinessStepStatus(readiness?.steps ?? [], "driver_protocol"), [readiness]);
  const blockers = useMemo(
    () => readiness?.blockers.filter((blocker) => blocker.blocking_step_key === "driver_protocol") ?? [],
    [readiness]
  );

  return (
    <MainLayout title="Protocol Setup">
      <OnboardingStepLayout
        title="Protocol setup"
        breadcrumbs={[{ label: "Onboarding", href: "/onboarding" }, { label: "Protocol Setup" }]}
        progressRow={<p className="text-sm text-gray-700">Step status: <span className="font-semibold">{formatStatus(status)}</span></p>}
        whyThisMatters="Protocol readiness defines who owns response actions and keeps incident handling consistent across operators and drivers."
        requirements={[
          "Enable an instruction set with at least one active step.",
          "Set safety contact details and default export profile behavior.",
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
          { label: "Open driver protocol admin", href: "/admin/driver-protocol" },
          { label: "View critical blockers", href: "/dashboard?blockers=critical" },
        ]}
        backAction={{ label: "Back", href: "/onboarding/integration-setup" }}
        saveDraftAction={{ label: "Save Draft", href: "/onboarding" }}
        continueAction={{ label: "Continue", href: "/onboarding/mapping-validation" }}
      >
        <div className="space-y-4">
          {error ? <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-semibold text-gray-900">Driver protocol readiness</h2>
              <span className={`rounded-full px-2 py-1 text-xs font-semibold ${getStatusClasses(status)}`}>{formatStatus(status)}</span>
            </div>
            <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
              <div className="rounded border border-gray-200 p-2">
                <dt className="text-xs text-gray-500">Instruction set</dt>
                <dd className="font-semibold text-gray-900">{data.instruction_set_selected ? data.instruction_source : "Not configured"}</dd>
              </div>
              <div className="rounded border border-gray-200 p-2">
                <dt className="text-xs text-gray-500">Safety contact configured</dt>
                <dd className="font-semibold text-gray-900">{data.safety_contact_configured ? "Yes" : "No"}</dd>
              </div>
              <div className="rounded border border-gray-200 p-2">
                <dt className="text-xs text-gray-500">Safety manager phone</dt>
                <dd className="font-semibold text-gray-900">{data.safety_manager_phone ?? "Missing"}</dd>
              </div>
              <div className="rounded border border-gray-200 p-2">
                <dt className="text-xs text-gray-500">Export profiles available</dt>
                <dd className="font-semibold text-gray-900">{data.export_profiles_available.length}</dd>
              </div>
            </dl>
            <Link href="/admin/driver-protocol" className="mt-3 inline-block text-sm font-semibold text-blue-700 hover:underline">Open remediation actions</Link>
          </section>
        </div>
      </OnboardingStepLayout>
    </MainLayout>
  );
}

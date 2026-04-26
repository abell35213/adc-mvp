"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import MainLayout from "@/components/MainLayout";
import OnboardingStepLayout from "@/components/onboarding/OnboardingStepLayout";
import {
  getOrgOnboardingStatus,
  toUserErrorMessage,
  type OrgLaunchReadiness,
  type OnboardingStepStatus,
} from "@/lib/api";
import DemoTenantBanner from "@/components/commercial/DemoTenantBanner";
import { ONBOARDING_WIZARD_STORAGE_KEY } from "@/lib/onboarding";

type WizardStep = {
  key: string;
  title: string;
  path: string;
  readinessKeys: string[];
  requirements: string[];
  whyThisMatters: string;
};

const WIZARD_STEPS: WizardStep[] = [
  {
    key: "integrations",
    title: "Integration Setup",
    path: "/onboarding/integration-setup",
    readinessKeys: ["integrations"],
    requirements: ["Activate at least one integration connection.", "Address integration validation errors before launch."],
    whyThisMatters: "Integrations feed incident evidence automatically so your team can act without manual uploads.",
  },
  {
    key: "protocol",
    title: "Protocol Setup",
    path: "/onboarding/protocol-setup",
    readinessKeys: ["driver_protocol"],
    requirements: [
      "Enable an instruction set with at least one active step.",
      "Set safety contact details and default export profile behavior.",
    ],
    whyThisMatters: "Protocol setup ensures operators and drivers follow a consistent response workflow in every incident.",
  },
  {
    key: "mappings",
    title: "Mapping Validation",
    path: "/onboarding/mapping-validation",
    readinessKeys: ["mappings"],
    requirements: ["Map external entities needed for case operations.", "Resolve any mapping gaps that impact pilot readiness."],
    whyThisMatters: "Validated mappings keep ownership and routing accurate, preventing missing evidence downstream.",
  },
  {
    key: "sample-incident",
    title: "Sample Incident Validation",
    path: "/onboarding/sample-incident-validation",
    readinessKeys: ["testIncidentCompleted"],
    requirements: ["Run a sample incident through workflow.", "Capture findings and resolve critical execution issues."],
    whyThisMatters: "A dry run proves your team can close the loop from incident capture to export-ready case output.",
  },
  {
    key: "qr",
    title: "QR Deployment",
    path: "/onboarding/qr-deployment",
    readinessKeys: ["vehicle_qr"],
    requirements: ["Generate and distribute vehicle QR tokens.", "Track and close outstanding QR deployment coverage blockers."],
    whyThisMatters: "QR adoption determines how reliably incidents can be started in-field and tied to the right vehicles.",
  },
];

function getStepStatus(steps: OrgLaunchReadiness["steps"], readinessKeys: string[]): OnboardingStepStatus {
  const mapped = steps.filter((step) => readinessKeys.includes(step.key));
  if (mapped.some((step) => step.status === "blocked")) return "blocked";
  if (mapped.length > 0 && mapped.every((step) => step.status === "completed")) return "completed";
  if (mapped.some((step) => step.status === "in_progress" || step.status === "completed")) return "in_progress";
  return "not_started";
}

function statusClasses(status: OnboardingStepStatus): string {
  if (status === "completed") return "bg-green-100 text-green-700";
  if (status === "blocked") return "bg-red-100 text-red-700";
  if (status === "in_progress") return "bg-amber-100 text-amber-700";
  return "bg-gray-100 text-gray-700";
}

export default function OnboardingWizardClient() {
  const router = useRouter();
  const [readiness, setReadiness] = useState<OrgLaunchReadiness | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeStepKey, setActiveStepKey] = useState(() => {
    if (typeof window === "undefined") return WIZARD_STEPS[0].key;
    const fromQuery = new URLSearchParams(window.location.search).get("step") ?? "";
    if (WIZARD_STEPS.some((step) => step.key === fromQuery)) return fromQuery;
    const stored = window.localStorage.getItem(ONBOARDING_WIZARD_STORAGE_KEY) ?? "";
    return WIZARD_STEPS.some((step) => step.key === stored) ? stored : WIZARD_STEPS[0].key;
  });

  useEffect(() => {
    getOrgOnboardingStatus()
      .then((payload) => {
        setReadiness(payload);
        setError("");
      })
      .catch((err) => setError(toUserErrorMessage(err, "Failed to load onboarding status")))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(ONBOARDING_WIZARD_STORAGE_KEY, activeStepKey);
    router.replace(`/onboarding?step=${encodeURIComponent(activeStepKey)}`);
  }, [activeStepKey, router]);

  const activeIndex = Math.max(
    0,
    WIZARD_STEPS.findIndex((step) => step.key === activeStepKey)
  );
  const activeStep = WIZARD_STEPS[activeIndex];

  const stepStatuses = useMemo(() => {
    const steps = readiness?.steps ?? [];
    return new Map(WIZARD_STEPS.map((step) => [step.key, getStepStatus(steps, step.readinessKeys)]));
  }, [readiness]);

  const currentStepBlockers = useMemo(() => {
    if (!readiness) return [];
    return readiness.blockers.filter((blocker) =>
      blocker.blocking_step_key ? activeStep.readinessKeys.includes(blocker.blocking_step_key) : false
    );
  }, [activeStep, readiness]);

  return (
    <MainLayout title="Onboarding Wizard">
      <DemoTenantBanner tenantName="Org onboarding workspace" mode="Pilot" />
      <OnboardingStepLayout
        backAction={{
          label: "Back",
          onClick: () => setActiveStepKey(WIZARD_STEPS[Math.max(0, activeIndex - 1)].key),
          disabled: activeIndex === 0,
        }}
        breadcrumbs={[{ label: "Onboarding", href: "/onboarding" }, { label: "Launch Wizard" }]}
        continueAction={{
          label: "Continue",
          onClick: () => setActiveStepKey(WIZARD_STEPS[Math.min(WIZARD_STEPS.length - 1, activeIndex + 1)].key),
          disabled: activeIndex === WIZARD_STEPS.length - 1,
        }}
        blockingIssues={
          loading ? (
            <p>Loading blockers…</p>
          ) : currentStepBlockers.length === 0 ? (
            <p>No blockers reported for this step.</p>
          ) : (
            <ul className="space-y-2">
              {currentStepBlockers.map((blocker) => (
                <li className="rounded border border-amber-200 bg-white px-2 py-1" key={blocker.code}>
                  <p className="font-semibold">{blocker.title}</p>
                  <p>{blocker.detail}</p>
                </li>
              ))}
            </ul>
          )
        }
        helpLinks={WIZARD_STEPS.map((step) => ({ href: step.path, label: step.title }))}
        progressRow={
          <div className="flex flex-wrap gap-2">
            {WIZARD_STEPS.map((step, idx) => {
              const status = stepStatuses.get(step.key) ?? "not_started";
              const isActive = step.key === activeStep.key;
              return (
                <button
                  className={`rounded border px-3 py-2 text-left ${isActive ? "border-blue-300 bg-blue-50" : "border-gray-200 bg-white"}`}
                  key={step.key}
                  onClick={() => setActiveStepKey(step.key)}
                  type="button"
                >
                  <p className="text-xs text-gray-500">Step {idx + 1}</p>
                  <p className="text-sm font-medium text-gray-900">{step.title}</p>
                  <span className={`mt-1 inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold ${statusClasses(status)}`}>
                    {status.replaceAll("_", " ")}
                  </span>
                </button>
              );
            })}
          </div>
        }
        requirements={activeStep.requirements}
        saveDraftAction={{ label: "Save Draft", href: "/onboarding" }}
        title="Launch onboarding wizard"
        whyThisMatters={activeStep.whyThisMatters}
      >
        <div className="space-y-3">
          <p className="text-sm text-gray-600">
            Keep onboarding momentum by resolving blockers and moving each step to completion with a clear owner and next action.
          </p>
          <div className="flex flex-wrap items-center gap-2 text-xs text-gray-600">
            <span className="rounded-full bg-blue-100 px-3 py-1 font-semibold text-blue-700">
              Progress {readiness?.percent_complete ?? 0}%
            </span>
            <span className="rounded-full bg-gray-100 px-3 py-1 font-semibold text-gray-700">
              Readiness: {(readiness?.status ?? "not_started").replaceAll("_", " ")}
            </span>
          </div>
          {error ? <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
          <div className="rounded-lg border border-gray-200 p-3">
            <p className="text-sm font-semibold text-gray-900">Current step: {activeStep.title}</p>
            <p className="mt-1 text-sm text-gray-600">Open the step page to complete detailed remediation and validation tasks.</p>
            <Link className="mt-2 inline-block text-sm font-semibold text-blue-700 hover:underline" href={activeStep.path}>
              Open step workspace
            </Link>
          </div>
        </div>
      </OnboardingStepLayout>
    </MainLayout>
  );
}

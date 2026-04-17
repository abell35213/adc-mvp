"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import MainLayout from "@/components/MainLayout";
import {
  getOrgOnboardingStatus,
  toUserErrorMessage,
  type OrgLaunchReadiness,
  type OnboardingStepStatus,
} from "@/lib/api";
import { ONBOARDING_WIZARD_STORAGE_KEY } from "@/lib/onboarding";

type WizardStep = {
  key: string;
  title: string;
  readinessKeys: string[];
  requirements: string[];
};

const WIZARD_STEPS: WizardStep[] = [
  {
    key: "organization-basics",
    title: "Organization Basics",
    readinessKeys: ["org_settings"],
    requirements: [
      "Configure organization profile and safety communication settings.",
      "Ensure required operational defaults are saved.",
    ],
  },
  {
    key: "admin-users",
    title: "Admin Users",
    readinessKeys: ["users_roles"],
    requirements: ["Assign at least one org_admin user.", "Keep at least one active admin for onboarding ownership."],
  },
  {
    key: "roles",
    title: "Roles",
    readinessKeys: ["users_roles"],
    requirements: [
      "Assign at least one safety-capable user for incident workflows.",
      "Validate that role coverage supports go-live operations.",
    ],
  },
  {
    key: "vehicles",
    title: "Vehicles",
    readinessKeys: ["imports", "vehicle_qr"],
    requirements: ["Import and confirm active vehicle records.", "Verify vehicle list is ready for QR distribution."],
  },
  {
    key: "drivers",
    title: "Drivers",
    readinessKeys: ["driversImported"],
    requirements: ["Import driver roster with no unresolved failures.", "Confirm required drivers are available for assignments."],
  },
  {
    key: "assignments",
    title: "Assignments",
    readinessKeys: ["mappings"],
    requirements: ["Map external entities needed for case operations.", "Resolve any mapping gaps that impact pilot readiness."],
  },
  {
    key: "integrations",
    title: "Integrations",
    readinessKeys: ["integrations"],
    requirements: ["Activate at least one integration connection.", "Address integration validation errors before launch."],
  },
  {
    key: "protocol",
    title: "Protocol",
    readinessKeys: ["driver_protocol"],
    requirements: [
      "Enable an instruction set with at least one active step.",
      "Set safety contact details and default export profile behavior.",
    ],
  },
  {
    key: "qr",
    title: "QR",
    readinessKeys: ["vehicle_qr"],
    requirements: ["Generate and distribute vehicle QR tokens.", "Track and close outstanding QR deployment coverage blockers."],
  },
  {
    key: "sample-incident",
    title: "Sample Incident",
    readinessKeys: ["testIncidentCompleted"],
    requirements: ["Run a sample incident through workflow.", "Capture findings and resolve critical execution issues."],
  },
  {
    key: "export-validation",
    title: "Export Validation",
    readinessKeys: ["export_validation"],
    requirements: ["Produce a successful test export package.", "Resolve missing artifacts and blocking validation checks."],
  },
  {
    key: "launch-checklist-review",
    title: "Launch Checklist Review",
    readinessKeys: [],
    requirements: [
      "Review all steps and blockers for final sign-off.",
      "Confirm launch readiness state is pilot_ready or launch_ready.",
    ],
  },
];

function getStepStatus(steps: OrgLaunchReadiness["steps"], readinessKeys: string[]): OnboardingStepStatus {
  if (readinessKeys.length === 0) {
    if (steps.length === 0) return "not_started";
    return steps.every((step) => step.status === "completed") ? "completed" : "in_progress";
  }

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
    if (activeStep.readinessKeys.length === 0) return readiness.blockers;
    return readiness.blockers.filter((blocker) =>
      blocker.blocking_step_key ? activeStep.readinessKeys.includes(blocker.blocking_step_key) : false
    );
  }, [activeStep, readiness]);

  return (
    <MainLayout title="Onboarding Wizard">
      <div className="space-y-4">
        <header className="space-y-2">
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">Launch onboarding wizard</h2>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Follow the setup sequence, clear blockers inline, and resume where you left off.
          </p>
          <div className="flex flex-wrap items-center gap-2 text-xs text-gray-600 dark:text-gray-300">
            <span className="rounded-full bg-blue-100 px-3 py-1 font-semibold text-blue-700">
              Progress {readiness?.percent_complete ?? 0}%
            </span>
            <span className="rounded-full bg-gray-100 px-3 py-1 font-semibold text-gray-700">
              Readiness: {(readiness?.status ?? "not_started").replaceAll("_", " ")}
            </span>
          </div>
        </header>

        {error ? <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}

        <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
          <aside className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-800">
            <ol className="space-y-2">
              {WIZARD_STEPS.map((step, idx) => {
                const status = stepStatuses.get(step.key) ?? "not_started";
                const isActive = step.key === activeStep.key;
                return (
                  <li key={step.key}>
                    <button
                      type="button"
                      onClick={() => setActiveStepKey(step.key)}
                      className={`w-full rounded-md border px-3 py-2 text-left transition ${
                        isActive
                          ? "border-blue-300 bg-blue-50"
                          : "border-gray-200 bg-white hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs text-gray-500">{idx + 1}</span>
                        <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${statusClasses(status)}`}>
                          {status.replaceAll("_", " ")}
                        </span>
                      </div>
                      <p className="mt-1 text-sm font-medium text-gray-900 dark:text-white">{step.title}</p>
                    </button>
                  </li>
                );
              })}
            </ol>
          </aside>

          <section className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Step {activeIndex + 1}: {activeStep.title}
              </h3>
              <span
                className={`rounded-full px-2 py-1 text-xs font-semibold ${statusClasses(
                  stepStatuses.get(activeStep.key) ?? "not_started"
                )}`}
              >
                {(stepStatuses.get(activeStep.key) ?? "not_started").replaceAll("_", " ")}
              </span>
            </div>

            <div className="mt-4 space-y-4">
              <div>
                <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">Completion requirements</p>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-gray-700 dark:text-gray-300">
                  {activeStep.requirements.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>

              <div>
                <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">Blockers</p>
                {loading ? (
                  <p className="mt-2 text-sm text-gray-500">Loading blockers…</p>
                ) : currentStepBlockers.length === 0 ? (
                  <p className="mt-2 text-sm text-green-700">No blockers reported for this step.</p>
                ) : (
                  <ul className="mt-2 space-y-2">
                    {currentStepBlockers.map((blocker) => (
                      <li key={blocker.code} className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm">
                        <p className="font-semibold text-amber-900">{blocker.title}</p>
                        <p className="text-amber-800">{blocker.detail}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            <div className="mt-6 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setActiveStepKey(WIZARD_STEPS[Math.max(0, activeIndex - 1)].key)}
                disabled={activeIndex === 0}
                className="rounded border border-gray-300 px-3 py-1 text-sm text-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Previous
              </button>
              <button
                type="button"
                onClick={() => setActiveStepKey(WIZARD_STEPS[Math.min(WIZARD_STEPS.length - 1, activeIndex + 1)].key)}
                disabled={activeIndex === WIZARD_STEPS.length - 1}
                className="rounded bg-blue-600 px-3 py-1 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </section>
        </div>
      </div>
    </MainLayout>
  );
}

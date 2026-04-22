import type { OnboardingReadinessStep, OnboardingStepStatus } from "@/lib/api";

export const ONBOARDING_WIZARD_STORAGE_KEY = "adc.onboarding.currentStep";

export function getReadinessStepStatus(steps: OnboardingReadinessStep[], key: string): OnboardingStepStatus {
  return steps.find((step) => step.key === key)?.status ?? "not_started";
}

export function getReadinessBlockersForStep<T extends { blocking_step_key?: string | null }>(
  blockers: T[],
  stepKey: string
): T[] {
  return blockers.filter((blocker) => blocker.blocking_step_key === stepKey);
}

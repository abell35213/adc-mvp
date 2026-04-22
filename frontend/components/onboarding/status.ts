import type { OnboardingStepStatus } from "@/lib/api";

export function getStatusClasses(status: OnboardingStepStatus): string {
  if (status === "completed") return "bg-green-100 text-green-700";
  if (status === "blocked") return "bg-red-100 text-red-700";
  if (status === "in_progress") return "bg-amber-100 text-amber-700";
  return "bg-gray-100 text-gray-700";
}

export function formatStatus(status: OnboardingStepStatus): string {
  return status.replaceAll("_", " ");
}

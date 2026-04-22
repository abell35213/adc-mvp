"use client";

import { useState } from "react";

interface DemoScenario {
  id: string;
  label: string;
  description: string;
  enabled?: boolean;
}

interface DemoScenarioLauncherProps {
  scenarios: DemoScenario[];
}

export default function DemoScenarioLauncher({ scenarios }: DemoScenarioLauncherProps) {
  const defaultScenario = scenarios.find((scenario) => scenario.enabled !== false)?.id ?? "";
  const [selected, setSelected] = useState(defaultScenario);

  const current = scenarios.find((scenario) => scenario.id === selected);
  const available = Boolean(current && current.enabled !== false);

  return (
    <section className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <h3 className="text-base font-semibold text-gray-900 dark:text-white">Demo scenario launcher</h3>
      <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">
        Preview tenant behavior for onboarding, incident response, and exports.
      </p>

      <div className="mt-3 space-y-3">
        <select
          value={selected}
          onChange={(event) => setSelected(event.target.value)}
          className="w-full rounded border px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900"
        >
          {scenarios.map((scenario) => (
            <option key={scenario.id} value={scenario.id}>
              {scenario.label}
            </option>
          ))}
        </select>

        <p className="text-sm text-gray-600 dark:text-gray-300">{current?.description ?? "Select a scenario."}</p>

        <button
          type="button"
          disabled={!available}
          className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
          aria-disabled={!available}
          title={available ? "Launch selected scenario" : "This scenario is currently unavailable."}
        >
          {available ? "Launch scenario" : "Scenario unavailable"}
        </button>
      </div>
    </section>
  );
}

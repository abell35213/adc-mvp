"use client";

import { useEffect, useState } from "react";
import type { DragEvent } from "react";
import AdminLayout from "@/components/AdminLayout";
import {
  getDriverProtocolInstructions,
  getDriverProtocolSettings,
  resetDriverProtocolInstructions,
  updateDriverProtocolInstructions,
  type DriverInstructionStep,
} from "@/lib/api";

type InstructionStepState = DriverInstructionStep & { client_id: string };

type DraftStep = {
  title: string;
  body: string;
  enabled: boolean;
};

const createClientId = () => {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `step-${Date.now()}-${Math.random()}`;
};

const toStateSteps = (steps: DriverInstructionStep[]): InstructionStepState[] =>
  steps.map((step, index) => ({
    ...step,
    order: step.order ?? index + 1,
    client_id: step.step_id ?? createClientId(),
  }));

export default function DriverProtocolInstructionsPage() {
  const [scope, setScope] = useState("default");
  const [steps, setSteps] = useState<InstructionStepState[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [draftIndex, setDraftIndex] = useState<number | null>(null);
  const [draft, setDraft] = useState<DraftStep>({
    title: "",
    body: "",
    enabled: true,
  });

  const loadInstructions = async () => {
    setLoading(true);
    setError("");
    try {
      const settings = await getDriverProtocolSettings();
      const instructionScope = settings.instruction_source;
      const data = await getDriverProtocolInstructions(instructionScope);
      setScope(data.scope);
      setSteps(toStateSteps(data.steps));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load instructions");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInstructions();
  }, []);

  const handleDragStart = (index: number) => (event: DragEvent) => {
    event.dataTransfer.effectAllowed = "move";
    setDragIndex(index);
  };

  const handleDragOver = (event: DragEvent) => {
    event.preventDefault();
  };

  const handleDrop = (index: number) => (event: DragEvent) => {
    event.preventDefault();
    if (dragIndex === null || dragIndex === index) {
      return;
    }
    setSteps((prev) => {
      const updated = [...prev];
      const [moved] = updated.splice(dragIndex, 1);
      updated.splice(index, 0, moved);
      return updated.map((step, idx) => ({ ...step, order: idx + 1 }));
    });
    setDragIndex(null);
  };

  const handleDragEnd = () => {
    setDragIndex(null);
  };

  const openEditModal = (index: number | null) => {
    if (index === null) {
      setDraftIndex(null);
      setDraft({ title: "", body: "", enabled: true });
    } else {
      const step = steps[index];
      setDraftIndex(index);
      setDraft({ title: step.title, body: step.body, enabled: step.enabled });
    }
    setIsModalOpen(true);
  };

  const handleModalSave = () => {
    if (draft.title.trim() === "" || draft.body.trim() === "") {
      setError("Title and body are required.");
      return;
    }
    setError("");
    setSteps((prev) => {
      if (draftIndex === null) {
        return [
          ...prev,
          {
            client_id: createClientId(),
            order: prev.length + 1,
            title: draft.title.trim(),
            body: draft.body.trim(),
            enabled: draft.enabled,
          },
        ];
      }
      return prev.map((step, index) =>
        index === draftIndex
          ? {
              ...step,
              title: draft.title.trim(),
              body: draft.body.trim(),
              enabled: draft.enabled,
            }
          : step
      );
    });
    setIsModalOpen(false);
  };

  const handleToggleEnabled = (index: number) => {
    setSteps((prev) =>
      prev.map((step, idx) =>
        idx === index ? { ...step, enabled: !step.enabled } : step
      )
    );
  };

  const handleSaveAll = async () => {
    setSaving(true);
    setStatus("");
    setError("");
    try {
      const normalized = steps.map((step, index) => ({
        ...step,
        order: index + 1,
      }));
      setSteps(normalized);
      const payload = normalized.map((step) => ({
        step_id: step.step_id,
        order: step.order,
        title: step.title,
        body: step.body,
        enabled: step.enabled,
      }));
      const updated = await updateDriverProtocolInstructions({
        scope,
        steps: payload,
      });
      setSteps(toStateSteps(updated.steps));
      setStatus("Instructions saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save instructions");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    setSaving(true);
    setStatus("");
    setError("");
    try {
      const data = await resetDriverProtocolInstructions(scope);
      setSteps(toStateSteps(data.steps));
      setStatus("Instructions reset.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reset instructions");
    } finally {
      setSaving(false);
    }
  };

  return (
    <AdminLayout title="Instruction Editor">
      {loading && <p className="text-gray-500">Loading…</p>}
      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}
      {status && <p className="mb-4 text-sm text-green-600">{status}</p>}

      {!loading && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-400">
                Scope
              </p>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-200">
                {scope}
              </p>
            </div>
            <button
              onClick={() => openEditModal(null)}
              className="rounded-md border px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700"
            >
              Add step
            </button>
          </div>

          <div className="space-y-3">
            {steps.map((step, index) => (
              <div
                key={step.client_id}
                draggable
                onDragStart={handleDragStart(index)}
                onDragOver={handleDragOver}
                onDrop={handleDrop(index)}
                onDragEnd={handleDragEnd}
                className="flex flex-col gap-2 rounded-lg border bg-white p-4 shadow-sm transition hover:border-blue-400 dark:border-gray-700 dark:bg-gray-800"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gray-100 text-sm font-semibold text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                      {step.order}
                    </span>
                    <div>
                      <p className="text-sm font-semibold text-gray-800 dark:text-gray-100">
                        {step.title}
                      </p>
                      <p className="text-xs text-gray-500">Drag to reorder</p>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <label className="flex items-center gap-2 text-gray-500">
                      <input
                        type="checkbox"
                        checked={step.enabled}
                        onChange={() => handleToggleEnabled(index)}
                      />
                      Enabled
                    </label>
                    <button
                      onClick={() => openEditModal(index)}
                      className="rounded-md border px-3 py-1 text-xs font-medium text-gray-600 hover:bg-gray-100 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700"
                    >
                      Edit
                    </button>
                  </div>
                </div>
                <p className="text-sm text-gray-600 dark:text-gray-300">
                  {step.body}
                </p>
              </div>
            ))}
            {steps.length === 0 && (
              <div className="rounded-lg border border-dashed p-6 text-center text-sm text-gray-500">
                No instruction steps yet.
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              onClick={handleSaveAll}
              disabled={saving}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
            >
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              onClick={handleReset}
              disabled={saving}
              className="rounded-md border px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-60 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700"
            >
              Reset to defaults
            </button>
          </div>
        </div>
      )}

      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-lg dark:bg-gray-800">
            <h2 className="text-base font-semibold text-gray-800 dark:text-gray-100">
              {draftIndex === null ? "Add step" : "Edit step"}
            </h2>
            <div className="mt-4 space-y-3">
              <label className="block text-xs font-medium uppercase text-gray-400">
                Title
                <input
                  type="text"
                  value={draft.title}
                  onChange={(event) =>
                    setDraft((prev) => ({ ...prev, title: event.target.value }))
                  }
                  className="mt-1 w-full rounded-md border px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-900 dark:text-gray-200"
                />
              </label>
              <label className="block text-xs font-medium uppercase text-gray-400">
                Body
                <textarea
                  value={draft.body}
                  onChange={(event) =>
                    setDraft((prev) => ({ ...prev, body: event.target.value }))
                  }
                  rows={4}
                  className="mt-1 w-full rounded-md border px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-900 dark:text-gray-200"
                />
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
                <input
                  type="checkbox"
                  checked={draft.enabled}
                  onChange={(event) =>
                    setDraft((prev) => ({
                      ...prev,
                      enabled: event.target.checked,
                    }))
                  }
                />
                Enabled
              </label>
            </div>
            <div className="mt-6 flex flex-wrap justify-end gap-3">
              <button
                onClick={() => setIsModalOpen(false)}
                className="rounded-md border px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700"
              >
                Cancel
              </button>
              <button
                onClick={handleModalSave}
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                Save step
              </button>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}

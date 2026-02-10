"use client";

import { useEffect, useState } from "react";
import type { ChangeEvent } from "react";
import AdminLayout from "@/components/AdminLayout";
import {
  getDriverProtocolSettings,
  updateDriverProtocolSettings,
  type DriverProtocolSettings,
} from "@/lib/api";

const INSTRUCTION_SOURCES = [
  { value: "default", label: "Default" },
  { value: "company", label: "Company" },
  { value: "insurer", label: "Insurer" },
];

export default function DriverProtocolSettingsPage() {
  const [settings, setSettings] = useState<DriverProtocolSettings | null>(null);
  const [form, setForm] = useState<DriverProtocolSettings>({
    instruction_source: "default",
    require_ack: false,
    sms_enabled: false,
    voice_enabled: false,
    safety_manager_phone: null,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    getDriverProtocolSettings()
      .then((data) => {
        setSettings(data);
        setForm(data);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const handleToggle = (key: keyof DriverProtocolSettings) => {
    return (event: ChangeEvent<HTMLInputElement>) => {
      setForm((prev) => ({ ...prev, [key]: event.target.checked }));
    };
  };

  const handleSave = async () => {
    setSaving(true);
    setStatus("");
    setError("");
    try {
      const payload: DriverProtocolSettings = {
        ...form,
        safety_manager_phone:
          form.safety_manager_phone && form.safety_manager_phone.trim() !== ""
            ? form.safety_manager_phone.trim()
            : null,
      };
      const updated = await updateDriverProtocolSettings(payload);
      setSettings(updated);
      setForm(updated);
      setStatus("Settings saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (settings) {
      setForm(settings);
      setStatus("");
      setError("");
    }
  };

  return (
    <AdminLayout title="Driver Protocol Settings">
      {loading && <p className="text-gray-500">Loading…</p>}
      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}
      {status && <p className="mb-4 text-sm text-green-600">{status}</p>}

      {!loading && (
        <div className="space-y-6">
          <section className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200">
              Instruction Source
            </h2>
            <div className="mt-3 flex flex-wrap gap-4 text-sm text-gray-600 dark:text-gray-300">
              {INSTRUCTION_SOURCES.map((source) => (
                <label key={source.value} className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="instruction_source"
                    value={source.value}
                    checked={form.instruction_source === source.value}
                    onChange={() =>
                      setForm((prev) => ({
                        ...prev,
                        instruction_source: source.value,
                      }))
                    }
                  />
                  {source.label}
                </label>
              ))}
            </div>
          </section>

          <section className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200">
              Driver Acknowledgement
            </h2>
            <label className="mt-3 flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
              <input
                type="checkbox"
                checked={form.require_ack}
                onChange={handleToggle("require_ack")}
              />
              Require driver acknowledgment before proceeding
            </label>
          </section>

          <section className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200">
              Communication Channels
            </h2>
            <div className="mt-3 space-y-2 text-sm text-gray-600 dark:text-gray-300">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.sms_enabled}
                  onChange={handleToggle("sms_enabled")}
                />
                Enable SMS notifications
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.voice_enabled}
                  onChange={handleToggle("voice_enabled")}
                />
                Enable voice call notifications
              </label>
              <div className="pt-2">
                <label className="block text-xs font-medium uppercase text-gray-400">
                  Safety manager phone
                </label>
                <input
                  type="text"
                  value={form.safety_manager_phone ?? ""}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      safety_manager_phone: event.target.value,
                    }))
                  }
                  placeholder="+1 (555) 123-4567"
                  className="mt-1 w-full rounded-md border px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-900 dark:text-gray-200"
                />
              </div>
            </div>
          </section>

          <div className="flex flex-wrap gap-3">
            <button
              onClick={handleSave}
              disabled={saving}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
            >
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              onClick={handleReset}
              className="rounded-md border px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700"
            >
              Reset
            </button>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}

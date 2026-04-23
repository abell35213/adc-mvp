"use client";

import { useEffect, useMemo, useState } from "react";
import QRCode from "qrcode";
import Image from "next/image";
import AdminLayout from "@/components/AdminLayout";
import CategorizedIssueList from "@/components/imports/CategorizedIssueList";
import DriverImportPreviewTable from "@/components/imports/DriverImportPreviewTable";
import VehicleImportPreviewTable from "@/components/imports/VehicleImportPreviewTable";
import {
  createDriverImportJob,
  createVehicleImportJob,
  getDriverImportJob,
  getVehicleImportJob,
  getVehicleQrPayload,
  listAdminVehicles,
  rotateVehicleQr,
  type AdminVehicle,
  type DriverImportJobResponse,
  type ImportJobStatus,
  type VehicleImportJobResponse,
} from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import { hasRoleCapability } from "@/lib/permissions";
import {
  autoMapHeaders,
  buildDriverPreview,
  buildRowObjects,
  buildVehiclePreview,
  parseCsv,
  type DriverPreviewRow,
  type ImportIssue,
  type VehiclePreviewRow,
} from "@/lib/csvImport";

type QrModalState = {
  vehicle: AdminVehicle;
  payload: string;
  imageUrl: string;
};

const VEHICLE_ALIASES = {
  unit_number: ["unitNumber", "unit_number", "unit", "trucknumber", "vehicleunit"],
  vin: ["vin", "vehiclevin"],
  provider_vehicle_id: ["providerVehicleId", "provider_vehicle_id", "externalid", "providerid"],
  is_active: ["isActive", "active", "status"],
};

const DRIVER_ALIASES = {
  first_name: ["firstName", "first_name", "first"],
  last_name: ["lastName", "last_name", "last"],
  phone: ["phone", "mobile", "mobilephone", "phone_e164"],
  provider_driver_id: ["providerDriverId", "provider_driver_id", "externaldriverid"],
  is_active: ["isActive", "active", "status"],
};

function ImportJobProgress({ status, total, processed }: { status: ImportJobStatus; total: number; processed: number }) {
  const pct = total > 0 ? Math.round((processed / total) * 100) : status === "running" ? 10 : 0;
  return (
    <div className="space-y-1">
      <p className="text-xs text-gray-600">Status: <span className="font-semibold">{status}</span></p>
      <div className="h-2 rounded bg-gray-200">
        <div className="h-2 rounded bg-blue-600" style={{ width: `${Math.min(100, pct)}%` }} />
      </div>
      <p className="text-xs text-gray-500">{processed}/{total || "?"} processed</p>
    </div>
  );
}

function ImportSummary({ title, items }: { title: string; items: Array<{ label: string; value: number }> }) {
  return (
    <div className="rounded-md border border-gray-200 bg-white p-3">
      <p className="text-sm font-semibold text-gray-800">{title}</p>
      <dl className="mt-2 grid grid-cols-2 gap-2 text-xs">
        {items.map((item) => (
          <div key={item.label}>
            <dt className="text-gray-500">{item.label}</dt>
            <dd className="font-semibold text-gray-800">{item.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export default function AdminVehiclesPage() {
  const { user } = useAuth();
  const [vehicles, setVehicles] = useState<AdminVehicle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [qrModal, setQrModal] = useState<QrModalState | null>(null);
  const [busyVehicleId, setBusyVehicleId] = useState<string | null>(null);

  const [vehicleCsv, setVehicleCsv] = useState("");
  const [driverCsv, setDriverCsv] = useState("");
  const [vehicleMapping, setVehicleMapping] = useState<Record<string, string>>({});
  const [driverMapping, setDriverMapping] = useState<Record<string, string>>({});
  const [vehiclePreview, setVehiclePreview] = useState<VehiclePreviewRow[]>([]);
  const [driverPreview, setDriverPreview] = useState<DriverPreviewRow[]>([]);
  const [vehicleIssues, setVehicleIssues] = useState<ImportIssue[]>([]);
  const [driverIssues, setDriverIssues] = useState<ImportIssue[]>([]);
  const [vehicleConfirm, setVehicleConfirm] = useState(false);
  const [driverConfirm, setDriverConfirm] = useState(false);
  const [vehicleSubmitting, setVehicleSubmitting] = useState(false);
  const [driverSubmitting, setDriverSubmitting] = useState(false);
  const [vehicleJob, setVehicleJob] = useState<VehicleImportJobResponse | null>(null);
  const [driverJob, setDriverJob] = useState<DriverImportJobResponse | null>(null);

  useEffect(() => {
    listAdminVehicles()
      .then(setVehicles)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!vehicleCsv.trim()) return;
    const parsed = parseCsv(vehicleCsv);
    const mapping = autoMapHeaders(parsed.headers, VEHICLE_ALIASES);
    setVehicleMapping(mapping);
    const rowObjects = buildRowObjects(parsed.headers, parsed.rows);
    const preview = buildVehiclePreview(rowObjects, mapping);
    setVehiclePreview(preview.previewRows);
    setVehicleIssues(preview.issues);
  }, [vehicleCsv]);

  useEffect(() => {
    if (!driverCsv.trim()) return;
    const parsed = parseCsv(driverCsv);
    const mapping = autoMapHeaders(parsed.headers, DRIVER_ALIASES);
    setDriverMapping(mapping);
    const rowObjects = buildRowObjects(parsed.headers, parsed.rows);
    const preview = buildDriverPreview(rowObjects, mapping);
    setDriverPreview(preview.previewRows);
    setDriverIssues(preview.issues);
  }, [driverCsv]);

  useEffect(() => {
    if (!vehicleJob || (vehicleJob.status !== "pending" && vehicleJob.status !== "running")) return;
    const timer = window.setInterval(async () => {
      const detail = await getVehicleImportJob(vehicleJob.job_id);
      setVehicleJob(detail);
      if (detail.status !== "pending" && detail.status !== "running") {
        window.clearInterval(timer);
      }
    }, 2500);
    return () => window.clearInterval(timer);
  }, [vehicleJob]);

  useEffect(() => {
    if (!driverJob || (driverJob.status !== "pending" && driverJob.status !== "running")) return;
    const timer = window.setInterval(async () => {
      const detail = await getDriverImportJob(driverJob.job_id);
      setDriverJob(detail);
      if (detail.status !== "pending" && detail.status !== "running") {
        window.clearInterval(timer);
      }
    }, 2500);
    return () => window.clearInterval(timer);
  }, [driverJob]);

  const vehicleErrorCount = useMemo(() => vehicleIssues.filter((i) => i.severity === "error").length, [vehicleIssues]);
  const driverErrorCount = useMemo(() => driverIssues.filter((i) => i.severity === "error").length, [driverIssues]);
  const canManageImports = hasRoleCapability(user?.role, "imports:write");
  const canManageQr = hasRoleCapability(user?.role, "vehicle_qr:write");

  const handleGenerateQr = async (vehicle: AdminVehicle) => {
    setError("");
    setBusyVehicleId(vehicle.adc_vehicle_id);
    try {
      await rotateVehicleQr(vehicle.adc_vehicle_id);
      const payload = await getVehicleQrPayload(vehicle.adc_vehicle_id);
      const imageUrl = await QRCode.toDataURL(payload.deep_link, { margin: 1, width: 240 });
      setQrModal({ vehicle, payload: payload.deep_link, imageUrl });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate QR");
    } finally {
      setBusyVehicleId(null);
    }
  };

  const submitVehicleImport = async () => {
    setVehicleSubmitting(true);
    try {
      const created = await createVehicleImportJob({
        provider: "csv_upload",
        csv_content: vehicleCsv,
        header_mapping: vehicleMapping,
        inactive_unit_numbers: [],
      });
      setVehicleJob(await getVehicleImportJob(created.job_id));
    } finally {
      setVehicleSubmitting(false);
    }
  };

  const submitDriverImport = async () => {
    setDriverSubmitting(true);
    try {
      const created = await createDriverImportJob({
        provider: "csv_upload",
        csv_content: driverCsv,
        header_mapping: driverMapping,
        inactive_mobile_phones: [],
      });
      setDriverJob(await getDriverImportJob(created.job_id));
    } finally {
      setDriverSubmitting(false);
    }
  };

  return (
    <AdminLayout title="Vehicles">
      {loading && <p className="text-gray-500">Loading…</p>}
      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      <section className="mb-8 space-y-4 rounded-lg border border-gray-200 bg-white p-4">
        <h2 className="text-base font-semibold text-gray-900">Vehicle CSV import</h2>
        {!canManageImports ? <p className="text-xs text-amber-700">You have read-only access to imports.</p> : null}
        <textarea value={vehicleCsv} onChange={(e) => setVehicleCsv(e.target.value)} rows={5} className="w-full rounded-md border p-2 text-sm" placeholder="Paste vehicle CSV content here" />
        {vehiclePreview.length > 0 && <VehicleImportPreviewTable rows={vehiclePreview} />}
        <CategorizedIssueList issues={vehicleIssues} />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={vehicleConfirm} onChange={(e) => setVehicleConfirm(e.target.checked)} />
          I reviewed mapping + validation and want to apply this vehicle import.
        </label>
        <button disabled={!canManageImports || !vehicleConfirm || vehicleErrorCount > 0 || vehicleSubmitting || !vehicleCsv.trim()} onClick={submitVehicleImport} className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
          {vehicleSubmitting ? "Submitting…" : "Apply vehicle import"}
        </button>
        {vehicleJob && (
          <div className="space-y-3 rounded-md border border-gray-200 bg-gray-50 p-3">
            <ImportJobProgress status={vehicleJob.status} total={vehicleJob.records_total} processed={vehicleJob.records_processed} />
            {(vehicleJob.status === "succeeded" || vehicleJob.status === "failed") && (
              <ImportSummary
                title="Final summary"
                items={[
                  { label: "Imported", value: vehicleJob.records_imported },
                  { label: "Updated", value: vehicleJob.records_updated },
                  { label: "Skipped", value: vehicleJob.records_skipped },
                  { label: "Errors", value: vehicleJob.records_errored },
                  { label: "Missing QR", value: vehicleJob.summary.missing_qr_count },
                  { label: "Missing mapping", value: vehicleJob.summary.missing_provider_mapping_count },
                ]}
              />
            )}
          </div>
        )}
      </section>

      <section className="mb-8 space-y-4 rounded-lg border border-gray-200 bg-white p-4">
        <h2 className="text-base font-semibold text-gray-900">Driver CSV import</h2>
        {!canManageImports ? <p className="text-xs text-amber-700">You have read-only access to imports.</p> : null}
        <textarea value={driverCsv} onChange={(e) => setDriverCsv(e.target.value)} rows={5} className="w-full rounded-md border p-2 text-sm" placeholder="Paste driver CSV content here" />
        {driverPreview.length > 0 && <DriverImportPreviewTable rows={driverPreview} />}
        <CategorizedIssueList issues={driverIssues} />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={driverConfirm} onChange={(e) => setDriverConfirm(e.target.checked)} />
          I reviewed mapping + validation and want to apply this driver import.
        </label>
        <button disabled={!canManageImports || !driverConfirm || driverErrorCount > 0 || driverSubmitting || !driverCsv.trim()} onClick={submitDriverImport} className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
          {driverSubmitting ? "Submitting…" : "Apply driver import"}
        </button>
        {driverJob && (
          <div className="space-y-3 rounded-md border border-gray-200 bg-gray-50 p-3">
            <ImportJobProgress status={driverJob.status} total={driverJob.records_total} processed={driverJob.records_processed} />
            {(driverJob.status === "succeeded" || driverJob.status === "failed") && (
              <ImportSummary
                title="Final summary"
                items={[
                  { label: "Imported", value: driverJob.records_imported },
                  { label: "Updated", value: driverJob.records_updated },
                  { label: "Skipped", value: driverJob.records_skipped },
                  { label: "Errors", value: driverJob.records_errored },
                  { label: "Needs review", value: driverJob.summary.needs_review_count },
                  { label: "Invalid phone", value: driverJob.summary.invalid_phone_count },
                ]}
              />
            )}
          </div>
        )}
      </section>

      {!loading && (
        <div className="overflow-hidden rounded-lg border bg-white shadow dark:border-gray-700 dark:bg-gray-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-100 dark:bg-gray-700">
              <tr>
                <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">Vehicle</th>
                <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-gray-700">
              {vehicles.map((vehicle) => (
                <tr key={vehicle.adc_vehicle_id}>
                  <td className="px-4 py-3">
                    <p className="font-medium text-gray-800 dark:text-gray-100">{vehicle.display_label}</p>
                    <p className="text-xs text-gray-500">{vehicle.adc_vehicle_id}</p>
                  </td>
                  <td className="px-4 py-3">
                    <button onClick={() => handleGenerateQr(vehicle)} disabled={!canManageQr || busyVehicleId === vehicle.adc_vehicle_id} className="rounded-md bg-blue-600 px-3 py-2 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-60">
                      {busyVehicleId === vehicle.adc_vehicle_id ? "Generating…" : "Generate/Rotate QR"}
                    </button>
                  </td>
                </tr>
              ))}
              {vehicles.length === 0 && (
                <tr>
                  <td colSpan={2} className="px-4 py-6 text-center text-sm text-gray-500">No vehicles configured.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {qrModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-lg dark:bg-gray-800">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-base font-semibold text-gray-800 dark:text-gray-100">QR for {qrModal.vehicle.display_label}</h2>
                <p className="text-xs text-gray-500">{qrModal.vehicle.adc_vehicle_id}</p>
              </div>
              <button onClick={() => setQrModal(null)} className="text-sm text-gray-500 hover:text-gray-700">Close</button>
            </div>
            <div className="mt-4 flex flex-col items-center gap-4">
              <Image src={qrModal.imageUrl} alt={`QR for ${qrModal.vehicle.adc_vehicle_id}`} width={240} height={240} unoptimized className="h-60 w-60" />
              <p className="break-all text-xs text-gray-500">{qrModal.payload}</p>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}

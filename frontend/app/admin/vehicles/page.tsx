"use client";

import { useEffect, useState } from "react";
import QRCode from "qrcode";
import Image from "next/image";
import AdminLayout from "@/components/AdminLayout";
import {
  getVehicleQrPayload,
  listAdminVehicles,
  rotateVehicleQr,
  type AdminVehicle,
} from "@/lib/api";

type QrModalState = {
  vehicle: AdminVehicle;
  payload: string;
  imageUrl: string;
};

export default function AdminVehiclesPage() {
  const [vehicles, setVehicles] = useState<AdminVehicle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [qrModal, setQrModal] = useState<QrModalState | null>(null);
  const [busyVehicleId, setBusyVehicleId] = useState<string | null>(null);

  useEffect(() => {
    listAdminVehicles()
      .then(setVehicles)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const handleGenerateQr = async (vehicle: AdminVehicle) => {
    setError("");
    setBusyVehicleId(vehicle.adc_vehicle_id);
    try {
      await rotateVehicleQr(vehicle.adc_vehicle_id);
      const payload = await getVehicleQrPayload(vehicle.adc_vehicle_id);
      const imageUrl = await QRCode.toDataURL(payload.deep_link, {
        margin: 1,
        width: 240,
      });
      setQrModal({
        vehicle,
        payload: payload.deep_link,
        imageUrl,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate QR");
    } finally {
      setBusyVehicleId(null);
    }
  };

  return (
    <AdminLayout title="Vehicles">
      {loading && <p className="text-gray-500">Loading…</p>}
      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      {!loading && (
        <div className="overflow-hidden rounded-lg border bg-white shadow dark:border-gray-700 dark:bg-gray-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-100 dark:bg-gray-700">
              <tr>
                <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">
                  Vehicle
                </th>
                <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-gray-700">
              {vehicles.map((vehicle) => (
                <tr key={vehicle.adc_vehicle_id}>
                  <td className="px-4 py-3">
                    <p className="font-medium text-gray-800 dark:text-gray-100">
                      {vehicle.display_label}
                    </p>
                    <p className="text-xs text-gray-500">
                      {vehicle.adc_vehicle_id}
                    </p>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleGenerateQr(vehicle)}
                      disabled={busyVehicleId === vehicle.adc_vehicle_id}
                      className="rounded-md bg-blue-600 px-3 py-2 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
                    >
                      {busyVehicleId === vehicle.adc_vehicle_id
                        ? "Generating…"
                        : "Generate/Rotate QR"}
                    </button>
                  </td>
                </tr>
              ))}
              {vehicles.length === 0 && (
                <tr>
                  <td
                    colSpan={2}
                    className="px-4 py-6 text-center text-sm text-gray-500"
                  >
                    No vehicles configured.
                  </td>
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
                <h2 className="text-base font-semibold text-gray-800 dark:text-gray-100">
                  QR for {qrModal.vehicle.display_label}
                </h2>
                <p className="text-xs text-gray-500">
                  {qrModal.vehicle.adc_vehicle_id}
                </p>
              </div>
              <button
                onClick={() => setQrModal(null)}
                className="text-sm text-gray-500 hover:text-gray-700"
              >
                Close
              </button>
            </div>
            <div className="mt-4 flex flex-col items-center gap-4">
              <Image
                src={qrModal.imageUrl}
                alt={`QR for ${qrModal.vehicle.adc_vehicle_id}`}
                width={240}
                height={240}
                unoptimized
                className="h-60 w-60"
              />
              <p className="break-all text-xs text-gray-500">
                {qrModal.payload}
              </p>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}

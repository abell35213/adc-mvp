"use client";

import { useEffect, useState } from "react";
import MainLayout from "@/components/MainLayout";
import {
  listAdminVehicles,
  rotateVehicleQr,
  type AdminVehicle,
} from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import Link from "next/link";
import { hasRoleCapability } from "@/lib/permissions";

/**
 * Vehicles management page (admin only).  Lists all vehicles in the
 * organisation and provides an action to rotate the QR token for
 * each vehicle.  Non‑admin users are redirected to the dashboard.
 */
export default function VehiclesPage() {
  const { user, loading: authLoading } = useAuth();
  const [vehicles, setVehicles] = useState<AdminVehicle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [rotatingId, setRotatingId] = useState<string | null>(null);

  useEffect(() => {
    if (!user || !hasRoleCapability(user.role, "vehicle_qr:read")) return;
    listAdminVehicles()
      .then(setVehicles)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [user]);

  async function handleRotate(id: string) {
    setRotatingId(id);
    try {
      await rotateVehicleQr(id);
      // No need to refresh the list; QR code rotation does not change displayed fields.
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to rotate QR code");
    } finally {
      setRotatingId(null);
    }
  }

  // If still checking auth, show loading
  if (authLoading) {
    return (
      <MainLayout title="Vehicles">
        <p className="text-gray-500">Loading…</p>
      </MainLayout>
    );
  }

  // If not an admin, inform and link back
  const canReadVehicles = hasRoleCapability(user?.role, "vehicle_qr:read");
  const canWriteVehicles = hasRoleCapability(user?.role, "vehicle_qr:write");

  if (!canReadVehicles) {
    return (
      <MainLayout title="Vehicles">
        <p className="mb-4 text-red-600">You do not have permission to view this page.</p>
        <Link href="/dashboard" className="text-blue-600 hover:underline dark:text-blue-400">
          Return to dashboard
        </Link>
      </MainLayout>
    );
  }

  return (
    <MainLayout title="Vehicles">
      <div className="mb-4">
        <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
          Vehicles
        </h2>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Manage your fleet and QR codes.  You can rotate the QR token
          for each vehicle to regenerate its scanning link.
        </p>
      </div>
      {loading && <p className="text-gray-500">Loading…</p>}
      {error && <p className="text-red-600">{error}</p>}
      {!loading && vehicles.length === 0 && (
        <p className="text-gray-500">No vehicles found.</p>
      )}
      {!loading && vehicles.length > 0 && (
        <div className="overflow-hidden rounded-lg border bg-white shadow dark:border-gray-700 dark:bg-gray-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">
                  Vehicle ID
                </th>
                <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">
                  Label
                </th>
                <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-gray-700">
              {vehicles.map((veh) => (
                <tr key={veh.adc_vehicle_id}>
                  <td className="px-4 py-3 font-mono text-xs">
                    {veh.adc_vehicle_id}
                  </td>
                    <td className="px-4 py-3">
                      {veh.display_label}
                    </td>
                  <td className="px-4 py-3">
                    {canWriteVehicles ? <button
                      type="button"
                      onClick={() => handleRotate(veh.adc_vehicle_id)}
                      disabled={rotatingId === veh.adc_vehicle_id}
                      className="cursor-pointer rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {rotatingId === veh.adc_vehicle_id
                        ? "Rotating…"
                        : "Rotate QR"}
                    </button> : <span className="text-xs text-gray-500">Read only</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </MainLayout>
  );
}

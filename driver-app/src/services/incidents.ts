import { ApiRequestError } from '../api';
import { getStoredToken } from '../auth';
import { API_BASE_URL } from '../config';

type ApiError = {
  detail?: string;
};

export type ResolveVehicleQrResponse = {
  adc_vehicle_id: string;
  display_label: string;
};

export async function resolveVehicleQr(
  qrToken: string,
): Promise<ResolveVehicleQrResponse> {
  const token = await getStoredToken();
  const headers = new Headers({
    'Content-Type': 'application/json',
  });

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}/driver/resolve-vehicle-qr`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ qr_token: qrToken }),
  });

  const text = await response.text();
  let data: ResolveVehicleQrResponse | ApiError = {};
  if (text) {
    try {
      data = JSON.parse(text) as ResolveVehicleQrResponse | ApiError;
    } catch {
      data = { detail: text };
    }
  }

  if (!response.ok) {
    const apiDetail = (data as ApiError).detail;
    throw new ApiRequestError(
      typeof apiDetail === 'string' ? apiDetail : response.statusText || 'Request failed',
      response.status,
    );
  }

  return data as ResolveVehicleQrResponse;
}

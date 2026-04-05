import { getStoredToken } from './auth';

const API_BASE_URL = (process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:8000')
  .replace(/\/$/, '');

type ApiError = {
  detail?: string;
};

export class ApiRequestError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiRequestError';
    this.status = status;
  }
}

export type DriverMeResponse = {
  driver_id: string;
  org_id: string;
  phone_e164: string;
  display_name: string;
  vehicle: {
    adc_vehicle_id: string;
    display_label: string;
  } | null;
};

export type ResolveQrResponse = {
  adc_vehicle_id: string;
  display_label: string;
};

export type VerifyOtpResponse = {
  access_token: string;
};

export type DriverActiveIncidentResponse = {
  incident_id: string;
  status: string;
  created_at?: string;
  updated_at?: string;
  adc_vehicle_id?: string | null;
};

export type DriverIncidentInitiateRequest = {
  vehicle_strategy: 'last_assigned' | 'qr';
  qr_token?: string;
  device_location?: {
    latitude: number;
    longitude: number;
    accuracy_meters?: number | null;
    timestamp_utc?: string;
  } | null;
  device?: Record<string, unknown> | null;
};

export type DriverIncidentInitiateResponse = {
  incident_id: string;
  safety_notified: boolean;
  capture_started: boolean;
};

const request = async <T>(
  path: string,
  init: RequestInit = {},
  includeAuth = false,
): Promise<T> => {
  const headers = new Headers(init.headers);
  headers.set('Content-Type', 'application/json');

  if (includeAuth) {
    const token = await getStoredToken();
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });
  const text = await response.text();
  let data: T | ApiError = {} as T;
  if (text) {
    try {
      data = JSON.parse(text) as T | ApiError;
    } catch {
      data = { detail: text };
    }
  }

  if (!response.ok) {
    const apiDetail = (data as ApiError).detail;
    const errorMessage =
      typeof apiDetail === 'string'
        ? apiDetail
        : response.statusText || 'Request failed';
    throw new ApiRequestError(errorMessage, response.status);
  }

  return data as T;
};

export const requestOtp = (phoneE164: string) =>
  request('/driver/auth/request-otp', {
    method: 'POST',
    body: JSON.stringify({ phone_e164: phoneE164 }),
  });

export const verifyOtp = (phoneE164: string, otpCode: string) =>
  request<VerifyOtpResponse>('/driver/auth/verify-otp', {
    method: 'POST',
    body: JSON.stringify({ phone_e164: phoneE164, otp_code: otpCode }),
  });

export const getDriverMe = () => request<DriverMeResponse>('/driver/me', {}, true);

export const getDriverActiveIncident = async () => {
  try {
    return await request<DriverActiveIncidentResponse>(
      '/driver/incidents/active',
      {},
      true,
    );
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 404) {
      return null;
    }
    throw error;
  }
};

export const resolveQr = (qrToken: string) =>
  request<ResolveQrResponse>(
    '/driver/vehicle/resolve-qr',
    {
      method: 'POST',
      body: JSON.stringify({ qr_token: qrToken }),
    },
    true,
  );

export const initiateDriverIncident = (payload: DriverIncidentInitiateRequest) =>
  request<DriverIncidentInitiateResponse>(
    '/driver/incidents/initiate',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
    true,
  );

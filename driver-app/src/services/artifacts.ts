import { ApiRequestError } from '../api';
import { getStoredToken } from '../auth';

const API_BASE_URL = (process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:8000').replace(
  /\/$/,
  '',
);

type ApiError = {
  detail?: string;
};

export type ArtifactUploadHeaders = Record<string, string>;

export type RequestArtifactUploadUrlPayload = {
  artifact_type: string;
  filename: string;
  mime_type: string;
  byte_size: number;
  captured_at_utc?: string;
  gps?: {
    latitude: number;
    longitude: number;
  } | null;
  metadata?: Record<string, unknown>;
};

export type RequestArtifactUploadUrlResponse = {
  artifact_id: string;
  upload_url: string;
  upload_method?: string;
  upload_headers?: ArtifactUploadHeaders;
  storage_key?: string;
};

export type CompleteArtifactUploadPayload = {
  artifact_id: string;
  storage_key?: string;
  checksum_sha256?: string;
  byte_size?: number;
  mime_type?: string;
  metadata?: Record<string, unknown>;
};

export type CompleteArtifactUploadResponse = {
  artifact_id: string;
  status: string;
};

async function parseApiResponse<T>(response: Response): Promise<T> {
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
    throw new ApiRequestError(
      typeof apiDetail === 'string' ? apiDetail : response.statusText || 'Request failed',
      response.status,
    );
  }

  return data as T;
}

async function getAuthorizedJsonHeaders(): Promise<Headers> {
  const headers = new Headers({
    'Content-Type': 'application/json',
  });

  const token = await getStoredToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  return headers;
}

export async function requestArtifactUploadUrl(
  incidentId: string,
  payload: RequestArtifactUploadUrlPayload,
): Promise<RequestArtifactUploadUrlResponse> {
  const headers = await getAuthorizedJsonHeaders();
  const response = await fetch(
    `${API_BASE_URL}/driver/incidents/${incidentId}/artifacts/upload-url`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    },
  );

  return parseApiResponse<RequestArtifactUploadUrlResponse>(response);
}

export async function completeArtifactUpload(
  incidentId: string,
  payload: CompleteArtifactUploadPayload,
): Promise<CompleteArtifactUploadResponse> {
  const headers = await getAuthorizedJsonHeaders();
  const response = await fetch(
    `${API_BASE_URL}/driver/incidents/${incidentId}/artifacts/complete`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    },
  );

  return parseApiResponse<CompleteArtifactUploadResponse>(response);
}

import { ApiRequestError } from '../api';
import {
  completeArtifactUpload,
  requestArtifactUploadUrl,
  RequestArtifactUploadUrlPayload,
} from './artifacts';
import {
  enqueueUpload,
  getProcessableQueueItems,
  hydrateUploadQueueStore,
  markUploadFailed,
  markUploadPrepared,
  markUploadPreparing,
  markUploadSucceeded,
  scheduleUploadRetry,
  UploadQueueItem,
} from '../store/uploadQueueStore';
import {
  emitTimelineAndAnalyticsEvent,
  emitUploadAnalyticsEvent,
} from '../telemetry/protocolEvents';


export type QueueArtifactUploadInput = {
  incidentId: string;
  artifactType: string;
  localUri: string;
  fileName: string;
  mimeType: string;
  byteSize: number;
  capturedAtUtc?: string;
  gps?: {
    latitude: number;
    longitude: number;
  } | null;
  metadata?: Record<string, unknown>;
};

export async function queueArtifactUpload(input: QueueArtifactUploadInput): Promise<string> {
  const item = await enqueueUpload({
    incidentId: input.incidentId,
    artifactType: input.artifactType,
    localUri: input.localUri,
    fileName: input.fileName,
    mimeType: input.mimeType,
    byteSize: input.byteSize,
    capturedAtUtc: input.capturedAtUtc ?? new Date().toISOString(),
    gps: input.gps ?? null,
    metadata: input.metadata,
  });

  void processUploadQueueNow();
  return item.id;
}

const DEFAULT_UPLOAD_METHOD = 'PUT';
const MAX_ATTEMPTS = 5;
const BASE_BACKOFF_MS = 1_500;
const MAX_BACKOFF_MS = 45_000;
const TICK_INTERVAL_MS = 3_000;

let workerTimer: ReturnType<typeof setInterval> | null = null;
let workerRunning = false;

function getBackoffMs(attempt: number): number {
  const exponentialDelay = BASE_BACKOFF_MS * 2 ** Math.max(0, attempt - 1);
  const jitterFactor = 0.85 + Math.random() * 0.3;
  return Math.min(Math.floor(exponentialDelay * jitterFactor), MAX_BACKOFF_MS);
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return 'Unknown upload error';
}

function isRetryable(error: unknown): boolean {
  if (error instanceof ApiRequestError) {
    return error.status >= 500 || error.status === 429;
  }

  return true;
}

async function uploadArtifactBytes(
  item: UploadQueueItem,
  params: {
    uploadUrl: string;
    uploadMethod?: string;
    uploadHeaders?: Record<string, string>;
  },
): Promise<void> {
  const fileResponse = await fetch(item.localUri);
  if (!fileResponse.ok) {
    throw new Error(`Unable to read local file for upload (${fileResponse.status}).`);
  }

  const body = await fileResponse.blob();

  const headers = new Headers(params.uploadHeaders ?? {});
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', item.mimeType);
  }

  const response = await fetch(params.uploadUrl, {
    method: params.uploadMethod ?? DEFAULT_UPLOAD_METHOD,
    headers,
    body,
  });

  if (!response.ok) {
    throw new Error(`Storage upload failed with status ${response.status}.`);
  }
}

async function processUploadItem(item: UploadQueueItem): Promise<void> {
  await markUploadPreparing(item.id);

  try {
    emitUploadAnalyticsEvent('driver_upload_attempted', {
      queue_item_id: item.id,
      incident_id: item.incidentId,
      artifact_type: item.artifactType,
      attempt: item.attempts + 1,
    });

    const uploadPayload: RequestArtifactUploadUrlPayload = {
      artifact_type: item.artifactType,
      filename: item.fileName,
      mime_type: item.mimeType,
      byte_size: item.byteSize,
      captured_at_utc: item.capturedAtUtc,
      gps: item.gps,
      metadata: item.metadata,
    };

    const uploadDescriptor = await requestArtifactUploadUrl(item.incidentId, uploadPayload);
    await markUploadPrepared(item.id, {
      artifactId: uploadDescriptor.artifact_id,
      storageKey: uploadDescriptor.storage_key,
    });

    await uploadArtifactBytes(item, {
      uploadUrl: uploadDescriptor.upload_url,
      uploadMethod: uploadDescriptor.upload_method,
      uploadHeaders: uploadDescriptor.upload_headers,
    });

    await completeArtifactUpload(item.incidentId, {
      artifact_id: uploadDescriptor.artifact_id,
      storage_key: uploadDescriptor.storage_key,
      byte_size: item.byteSize,
      mime_type: item.mimeType,
      metadata: item.metadata,
    });

    await markUploadSucceeded(item.id);
    emitTimelineAndAnalyticsEvent('driver_media_uploaded', {
      incidentId: item.incidentId,
      payload: {
        artifact_type: item.artifactType,
        queue_item_id: item.id,
      },
    });
    emitUploadAnalyticsEvent('driver_upload_succeeded', {
      queue_item_id: item.id,
      incident_id: item.incidentId,
      artifact_type: item.artifactType,
    });
  } catch (error) {
    const errorMessage = getErrorMessage(error);
    const nextAttempt = item.attempts + 1;

    if (isRetryable(error) && nextAttempt < MAX_ATTEMPTS) {
      const delayMs = getBackoffMs(nextAttempt);
      await scheduleUploadRetry(item.id, {
        error: errorMessage,
        delayMs,
      });
      emitUploadAnalyticsEvent('driver_upload_retry_scheduled', {
        queue_item_id: item.id,
        incident_id: item.incidentId,
        artifact_type: item.artifactType,
        attempt: nextAttempt,
        delay_ms: delayMs,
      });
      return;
    }

    await markUploadFailed(item.id, errorMessage);
    emitTimelineAndAnalyticsEvent('driver_media_upload_failed', {
      incidentId: item.incidentId,
      payload: {
        artifact_type: item.artifactType,
        queue_item_id: item.id,
        reason: errorMessage,
      },
    });
    emitUploadAnalyticsEvent('driver_upload_failed', {
      queue_item_id: item.id,
      incident_id: item.incidentId,
      artifact_type: item.artifactType,
      attempt: nextAttempt,
      reason: errorMessage,
    });
  }
}

async function processTick(): Promise<void> {
  if (workerRunning) {
    return;
  }

  workerRunning = true;
  try {
    const items = getProcessableQueueItems();
    for (const item of items) {
      await processUploadItem(item);
    }
  } finally {
    workerRunning = false;
  }
}

export async function startUploadWorker(): Promise<void> {
  await hydrateUploadQueueStore();

  if (workerTimer) {
    return;
  }

  void processTick();
  workerTimer = setInterval(() => {
    void processTick();
  }, TICK_INTERVAL_MS);
}

export function stopUploadWorker(): void {
  if (!workerTimer) {
    return;
  }

  clearInterval(workerTimer);
  workerTimer = null;
}

export async function processUploadQueueNow(): Promise<void> {
  await hydrateUploadQueueStore();
  await processTick();
}

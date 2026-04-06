import AsyncStorage from '@react-native-async-storage/async-storage';

const UPLOAD_QUEUE_STORAGE_KEY = 'driver_upload_queue_v1';
const UPLOAD_QUEUE_VERSION = 1;

export type UploadQueueStatus = 'pending' | 'uploading' | 'uploaded' | 'failed';

export type UploadQueueItem = {
  id: string;
  incidentId: string;
  artifactType: string;
  localUri: string;
  fileName: string;
  mimeType: string;
  byteSize: number;
  capturedAtUtc: string;
  gps: {
    latitude: number;
    longitude: number;
  } | null;
  metadata?: Record<string, unknown>;
  status: UploadQueueStatus;
  attempts: number;
  nextAttemptAt: string;
  lastError: string | null;
  artifactId: string | null;
  storageKey: string | null;
};

type UploadQueueState = {
  version: number;
  items: UploadQueueItem[];
  updatedAt: string;
};

type UploadQueueListener = (state: UploadQueueState) => void;

const EMPTY_STATE: UploadQueueState = {
  version: UPLOAD_QUEUE_VERSION,
  items: [],
  updatedAt: new Date(0).toISOString(),
};

let queueState: UploadQueueState = EMPTY_STATE;
let hydrated = false;
let hydrateInFlight: Promise<void> | null = null;
const listeners = new Set<UploadQueueListener>();

function makeNowIso(): string {
  return new Date().toISOString();
}

function normalizeState(candidate: Partial<UploadQueueState>): UploadQueueState {
  const items = Array.isArray(candidate.items)
    ? candidate.items
        .filter((item): item is UploadQueueItem => {
          return (
            typeof item?.id === 'string' &&
            typeof item?.incidentId === 'string' &&
            typeof item?.artifactType === 'string' &&
            typeof item?.localUri === 'string' &&
            typeof item?.fileName === 'string' &&
            typeof item?.mimeType === 'string' &&
            typeof item?.byteSize === 'number' &&
            typeof item?.capturedAtUtc === 'string' &&
            typeof item?.status === 'string' &&
            typeof item?.attempts === 'number' &&
            typeof item?.nextAttemptAt === 'string'
          );
        })
        .map((item) => ({
          ...item,
          status:
            item.status === 'pending' ||
            item.status === 'uploading' ||
            item.status === 'uploaded' ||
            item.status === 'failed'
              ? item.status
              : 'pending',
          lastError: typeof item.lastError === 'string' ? item.lastError : null,
          artifactId: typeof item.artifactId === 'string' ? item.artifactId : null,
          storageKey: typeof item.storageKey === 'string' ? item.storageKey : null,
          gps:
            item.gps &&
            typeof item.gps.latitude === 'number' &&
            typeof item.gps.longitude === 'number'
              ? item.gps
              : null,
        }))
    : [];

  return {
    version: UPLOAD_QUEUE_VERSION,
    items,
    updatedAt: typeof candidate.updatedAt === 'string' ? candidate.updatedAt : makeNowIso(),
  };
}

async function persistState(nextState: UploadQueueState): Promise<void> {
  await AsyncStorage.setItem(UPLOAD_QUEUE_STORAGE_KEY, JSON.stringify(nextState));
}

function emit(nextState: UploadQueueState): void {
  for (const listener of listeners) {
    listener(nextState);
  }
}

async function updateState(
  updater: (current: UploadQueueState) => UploadQueueState,
): Promise<UploadQueueState> {
  await hydrateUploadQueueStore();
  const nextState = updater(queueState);
  queueState = {
    ...nextState,
    updatedAt: makeNowIso(),
  };
  await persistState(queueState);
  emit(queueState);
  return queueState;
}

export async function hydrateUploadQueueStore(): Promise<void> {
  if (hydrated) {
    return;
  }

  if (hydrateInFlight) {
    await hydrateInFlight;
    return;
  }

  hydrateInFlight = (async () => {
    try {
      const raw = await AsyncStorage.getItem(UPLOAD_QUEUE_STORAGE_KEY);
      if (!raw) {
        queueState = { ...EMPTY_STATE, updatedAt: makeNowIso() };
      } else {
        const parsed = JSON.parse(raw) as Partial<UploadQueueState>;
        queueState = normalizeState(parsed);
      }
    } catch {
      queueState = { ...EMPTY_STATE, updatedAt: makeNowIso() };
    } finally {
      hydrated = true;
      hydrateInFlight = null;
      emit(queueState);
    }
  })();

  await hydrateInFlight;
}

export function getUploadQueueSnapshot(): UploadQueueState {
  return queueState;
}

export function subscribeToUploadQueue(listener: UploadQueueListener): () => void {
  listeners.add(listener);
  listener(queueState);
  return () => {
    listeners.delete(listener);
  };
}

export async function enqueueUpload(
  input: Omit<
    UploadQueueItem,
    'id' | 'status' | 'attempts' | 'nextAttemptAt' | 'lastError' | 'artifactId' | 'storageKey'
  >,
): Promise<UploadQueueItem> {
  const newItem: UploadQueueItem = {
    ...input,
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    status: 'pending',
    attempts: 0,
    nextAttemptAt: makeNowIso(),
    lastError: null,
    artifactId: null,
    storageKey: null,
  };

  await updateState((current) => ({
    ...current,
    items: [...current.items, newItem],
  }));

  return newItem;
}

export async function markUploadPreparing(itemId: string): Promise<void> {
  await updateState((current) => ({
    ...current,
    items: current.items.map((item) =>
      item.id === itemId
        ? {
            ...item,
            status: 'uploading',
            attempts: item.attempts + 1,
            lastError: null,
          }
        : item,
    ),
  }));
}

export async function markUploadPrepared(
  itemId: string,
  payload: { artifactId: string; storageKey?: string },
): Promise<void> {
  await updateState((current) => ({
    ...current,
    items: current.items.map((item) =>
      item.id === itemId
        ? {
            ...item,
            artifactId: payload.artifactId,
            storageKey: payload.storageKey ?? item.storageKey,
          }
        : item,
    ),
  }));
}

export async function markUploadSucceeded(itemId: string): Promise<void> {
  await updateState((current) => ({
    ...current,
    items: current.items.map((item) =>
      item.id === itemId
        ? {
            ...item,
            status: 'uploaded',
            lastError: null,
          }
        : item,
    ),
  }));
}

export async function scheduleUploadRetry(
  itemId: string,
  payload: { error: string; delayMs: number },
): Promise<void> {
  await updateState((current) => ({
    ...current,
    items: current.items.map((item) =>
      item.id === itemId
        ? {
            ...item,
            status: 'pending',
            nextAttemptAt: new Date(Date.now() + payload.delayMs).toISOString(),
            lastError: payload.error,
          }
        : item,
    ),
  }));
}

export async function markUploadFailed(itemId: string, error: string): Promise<void> {
  await updateState((current) => ({
    ...current,
    items: current.items.map((item) =>
      item.id === itemId
        ? {
            ...item,
            status: 'failed',
            lastError: error,
          }
        : item,
    ),
  }));
}

export async function clearUploadedItemsForIncident(incidentId: string): Promise<void> {
  await updateState((current) => ({
    ...current,
    items: current.items.filter(
      (item) => !(item.incidentId === incidentId && item.status === 'uploaded'),
    ),
  }));
}

export function getProcessableQueueItems(now = new Date()): UploadQueueItem[] {
  const nowMs = now.getTime();
  return queueState.items.filter((item) => {
    if (item.status === 'uploaded') {
      return false;
    }

    const nextAttemptMs = new Date(item.nextAttemptAt).getTime();
    return Number.isFinite(nextAttemptMs) && nextAttemptMs <= nowMs;
  });
}

import * as SecureStore from 'expo-secure-store';

import { ProtocolRouteName, PROTOCOL_ROUTE_ORDER } from '../navigation/protocolFlow';

export const PROTOCOL_RESUME_STORAGE_KEY = 'driver_protocol_resume_v1';

const SCENE_FACTS_STORAGE_KEY = 'driver_scene_facts_draft_v1';
const THIRD_PARTY_STORAGE_KEY = 'driver_third_party_info_draft_v1';
const MEDIA_CAPTURE_STORAGE_KEY = 'driver_media_capture_draft_v1';
const NARRATIVE_STORAGE_KEY = 'driver_narrative_draft_v1';
const INSTRUCTION_PROGRESS_STORAGE_KEY = 'driver_instruction_progress_v1';

const PROTOCOL_DRAFT_STORAGE_KEYS = [
  SCENE_FACTS_STORAGE_KEY,
  THIRD_PARTY_STORAGE_KEY,
  MEDIA_CAPTURE_STORAGE_KEY,
  NARRATIVE_STORAGE_KEY,
  INSTRUCTION_PROGRESS_STORAGE_KEY,
] as const;

type ProtocolResumePayload = {
  incidentId: string | null;
  completedRoutes: ProtocolRouteName[];
  updatedAt: string;
};

type ResumeResolution = {
  hasLocalDrafts: boolean;
  completedRoutes: Set<ProtocolRouteName>;
};

function isProtocolRouteName(value: string): value is ProtocolRouteName {
  return (PROTOCOL_ROUTE_ORDER as readonly string[]).includes(value);
}

function parseStoredIncidentId(raw: string | null): string | null {
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as { incidentId?: string | null } | null;
    if (!parsed || typeof parsed !== 'object') {
      return null;
    }

    if (typeof parsed.incidentId !== 'string') {
      return null;
    }

    const trimmed = parsed.incidentId.trim();
    return trimmed.length ? trimmed : null;
  } catch {
    return null;
  }
}

function buildDraftCompatibleRoutesByFurthestStep(storedDrafts: Map<string, string | null>): Set<ProtocolRouteName> {
  const routes = new Set<ProtocolRouteName>();

  if (storedDrafts.get(INSTRUCTION_PROGRESS_STORAGE_KEY)) {
    routes.add('IncidentConfirm');
    routes.add('VehicleConfirm');
    routes.add('SafetyGate');
  }

  if (storedDrafts.get(SCENE_FACTS_STORAGE_KEY)) {
    routes.add('IncidentConfirm');
    routes.add('VehicleConfirm');
    routes.add('SafetyGate');
    routes.add('InstructionStep');
  }

  if (storedDrafts.get(THIRD_PARTY_STORAGE_KEY)) {
    routes.add('IncidentConfirm');
    routes.add('VehicleConfirm');
    routes.add('SafetyGate');
    routes.add('InstructionStep');
    routes.add('SceneFacts');
  }

  if (storedDrafts.get(MEDIA_CAPTURE_STORAGE_KEY)) {
    routes.add('IncidentConfirm');
    routes.add('VehicleConfirm');
    routes.add('SafetyGate');
    routes.add('InstructionStep');
    routes.add('SceneFacts');
    routes.add('ThirdPartyInfo');
  }

  if (storedDrafts.get(NARRATIVE_STORAGE_KEY)) {
    routes.add('IncidentConfirm');
    routes.add('VehicleConfirm');
    routes.add('SafetyGate');
    routes.add('InstructionStep');
    routes.add('SceneFacts');
    routes.add('ThirdPartyInfo');
    routes.add('MediaCapture');
  }

  return routes;
}

export async function persistProtocolResumeState(
  incidentId: string | null,
  completedRoutes: Iterable<ProtocolRouteName>,
): Promise<void> {
  const normalizedIncidentId = incidentId?.trim() ? incidentId.trim() : null;

  const payload: ProtocolResumePayload = {
    incidentId: normalizedIncidentId,
    completedRoutes: Array.from(completedRoutes).filter(isProtocolRouteName),
    updatedAt: new Date().toISOString(),
  };

  await SecureStore.setItemAsync(
    PROTOCOL_RESUME_STORAGE_KEY,
    JSON.stringify(payload),
  );
}

export async function resolveProtocolResumeState(
  activeIncidentId: string | null,
): Promise<ResumeResolution> {
  const normalizedActiveIncidentId = activeIncidentId?.trim() ? activeIncidentId.trim() : null;

  const keyReads = await Promise.all(
    [PROTOCOL_RESUME_STORAGE_KEY, ...PROTOCOL_DRAFT_STORAGE_KEYS].map((key) =>
      SecureStore.getItemAsync(key),
    ),
  );

  const [resumeRaw, ...draftsRaw] = keyReads;
  const draftValues = new Map<string, string | null>();
  PROTOCOL_DRAFT_STORAGE_KEYS.forEach((key, index) => {
    draftValues.set(key, draftsRaw[index]);
  });

  const hasLocalDrafts = draftsRaw.some((value) => Boolean(value));

  let storedIncidentId: string | null = null;
  let storedCompletedRoutes = new Set<ProtocolRouteName>();

  if (resumeRaw) {
    try {
      const parsed = JSON.parse(resumeRaw) as ProtocolResumePayload;
      storedIncidentId = parsed.incidentId?.trim() ? parsed.incidentId.trim() : null;
      storedCompletedRoutes = new Set(
        (parsed.completedRoutes ?? []).filter(isProtocolRouteName),
      );
    } catch {
      storedIncidentId = null;
      storedCompletedRoutes = new Set();
    }
  }

  const draftsIncidentIds = new Set<string>();
  for (const raw of draftsRaw) {
    const incidentId = parseStoredIncidentId(raw);
    if (incidentId) {
      draftsIncidentIds.add(incidentId);
    }
  }

  const hasActiveIncidentConflict =
    normalizedActiveIncidentId != null &&
    ((storedIncidentId != null && storedIncidentId !== normalizedActiveIncidentId) ||
      [...draftsIncidentIds].some((incidentId) => incidentId !== normalizedActiveIncidentId));

  if (hasActiveIncidentConflict) {
    return {
      hasLocalDrafts,
      completedRoutes: new Set(),
    };
  }

  const inferredFromDrafts = buildDraftCompatibleRoutesByFurthestStep(draftValues);

  return {
    hasLocalDrafts,
    completedRoutes: new Set([...storedCompletedRoutes, ...inferredFromDrafts]),
  };
}

export async function clearProtocolLocalDraftsAndResumeState(): Promise<void> {
  await Promise.all(
    [PROTOCOL_RESUME_STORAGE_KEY, ...PROTOCOL_DRAFT_STORAGE_KEYS].map((key) =>
      SecureStore.deleteItemAsync(key),
    ),
  );
}

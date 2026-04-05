import {
  DriverProtocolState,
  INITIAL_PROTOCOL_CONTEXT,
  INITIAL_PROTOCOL_SNAPSHOT,
  hasMinimumSubmissionValidations,
  IncidentDraftStatus,
  PROTOCOL_PERSISTENCE_VERSION,
  ProtocolContext,
  ProtocolSnapshot,
  UploadState,
} from '../types/protocol';

const TRANSITION_MAP: Readonly<Record<DriverProtocolState, DriverProtocolState[]>> = {
  unauthenticated: ['authenticated'],
  authenticated: ['incident_confirmed'],
  incident_confirmed: ['incident_initiated'],
  incident_initiated: ['evidence_collecting', 'submitted'],
  evidence_collecting: ['submitted'],
  submitted: [],
};

const DEFAULT_DRAFT_STATUS_BY_STATE: Readonly<
  Record<DriverProtocolState, IncidentDraftStatus>
> = {
  unauthenticated: 'idle',
  authenticated: 'idle',
  incident_confirmed: 'idle',
  incident_initiated: 'drafting',
  evidence_collecting: 'drafting',
  submitted: 'submitted',
};

const DEFAULT_UPLOAD_STATE_BY_STATE: Readonly<Record<DriverProtocolState, UploadState>> = {
  unauthenticated: 'idle',
  authenticated: 'idle',
  incident_confirmed: 'idle',
  incident_initiated: 'idle',
  evidence_collecting: 'uploading',
  submitted: 'uploaded',
};

type TransitionGuard = (snapshot: ProtocolSnapshot) => boolean;

const TRANSITION_GUARDS: Partial<Record<DriverProtocolState, TransitionGuard>> = {
  incident_confirmed: (snapshot) => snapshot.context.isAuthenticated,
  incident_initiated: (snapshot) =>
    snapshot.context.vehicleResolved && snapshot.context.safetyAcknowledged,
  submitted: (snapshot) =>
    hasMinimumSubmissionValidations(snapshot.context.submissionValidations),
};

function isTransitionListed(from: DriverProtocolState, to: DriverProtocolState): boolean {
  return TRANSITION_MAP[from].includes(to);
}

export function canTransition(
  snapshot: ProtocolSnapshot,
  toState: DriverProtocolState,
): boolean {
  if (!isTransitionListed(snapshot.state, toState)) {
    return false;
  }

  const guard = TRANSITION_GUARDS[toState];
  return guard ? guard(snapshot) : true;
}

export function getAllowedTransitions(
  snapshot: ProtocolSnapshot,
): DriverProtocolState[] {
  return TRANSITION_MAP[snapshot.state].filter((nextState) =>
    canTransition(snapshot, nextState),
  );
}

export function createProtocolSnapshot(
  initial?: Partial<ProtocolSnapshot>,
): ProtocolSnapshot {
  const context: ProtocolContext = {
    ...INITIAL_PROTOCOL_CONTEXT,
    ...(initial?.context ?? {}),
    submissionValidations: {
      ...INITIAL_PROTOCOL_CONTEXT.submissionValidations,
      ...(initial?.context?.submissionValidations ?? {}),
    },
  };

  return {
    ...INITIAL_PROTOCOL_SNAPSHOT,
    ...initial,
    context,
    version: PROTOCOL_PERSISTENCE_VERSION,
    updatedAt: initial?.updatedAt ?? new Date().toISOString(),
  };
}

export function transitionProtocol(
  snapshot: ProtocolSnapshot,
  toState: DriverProtocolState,
  contextPatch?: Partial<ProtocolContext>,
): ProtocolSnapshot {
  const candidate = createProtocolSnapshot({
    ...snapshot,
    context: {
      ...snapshot.context,
      ...(contextPatch ?? {}),
      submissionValidations: {
        ...snapshot.context.submissionValidations,
        ...(contextPatch?.submissionValidations ?? {}),
      },
    },
  });

  if (!canTransition(candidate, toState)) {
    throw new Error(
      `Invalid protocol transition: ${candidate.state} -> ${toState}`,
    );
  }

  return createProtocolSnapshot({
    ...candidate,
    state: toState,
    incidentDraftStatus: DEFAULT_DRAFT_STATUS_BY_STATE[toState],
    uploadState: DEFAULT_UPLOAD_STATE_BY_STATE[toState],
    updatedAt: new Date().toISOString(),
  });
}

export function serializeProtocolSnapshot(snapshot: ProtocolSnapshot): string {
  return JSON.stringify(createProtocolSnapshot(snapshot));
}

function isDriverProtocolState(value: unknown): value is DriverProtocolState {
  return (
    typeof value === 'string' &&
    [
      'unauthenticated',
      'authenticated',
      'incident_confirmed',
      'incident_initiated',
      'evidence_collecting',
      'submitted',
    ].includes(value)
  );
}

function isIncidentDraftStatus(value: unknown): value is IncidentDraftStatus {
  return (
    typeof value === 'string' &&
    ['idle', 'drafting', 'ready_for_submission', 'submitted'].includes(value)
  );
}

function isUploadState(value: unknown): value is UploadState {
  return (
    typeof value === 'string' &&
    ['idle', 'uploading', 'uploaded', 'failed'].includes(value)
  );
}

export function deserializeProtocolSnapshot(payload: string): ProtocolSnapshot {
  try {
    const parsed = JSON.parse(payload) as Partial<ProtocolSnapshot>;
    const candidate = createProtocolSnapshot(parsed);

    if (!isDriverProtocolState(parsed.state)) {
      return createProtocolSnapshot();
    }

    if (parsed.incidentDraftStatus && !isIncidentDraftStatus(parsed.incidentDraftStatus)) {
      return createProtocolSnapshot();
    }

    if (parsed.uploadState && !isUploadState(parsed.uploadState)) {
      return createProtocolSnapshot();
    }

    if (parsed.version !== PROTOCOL_PERSISTENCE_VERSION) {
      return reconcilePersistedSnapshot(candidate);
    }

    return reconcilePersistedSnapshot(candidate);
  } catch {
    return createProtocolSnapshot();
  }
}

export function reconcilePersistedSnapshot(
  snapshot: ProtocolSnapshot,
): ProtocolSnapshot {
  let reconciled = createProtocolSnapshot(snapshot);

  const progressionOrder: DriverProtocolState[] = [
    'authenticated',
    'incident_confirmed',
    'incident_initiated',
    'evidence_collecting',
    'submitted',
  ];

  for (const state of progressionOrder) {
    if (reconciled.state === state) {
      const fallback = progressionOrder[progressionOrder.indexOf(state) - 1];
      if (!fallback) {
        return createProtocolSnapshot({
          ...reconciled,
          state: 'unauthenticated',
          incidentDraftStatus: 'idle',
          uploadState: 'idle',
        });
      }

      if (!canTransition({ ...reconciled, state: fallback }, state)) {
        return createProtocolSnapshot({
          ...reconciled,
          state: fallback,
          incidentDraftStatus: DEFAULT_DRAFT_STATUS_BY_STATE[fallback],
          uploadState: DEFAULT_UPLOAD_STATE_BY_STATE[fallback],
        });
      }
    }
  }

  return reconciled;
}

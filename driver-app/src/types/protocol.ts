export type DriverProtocolState =
  | 'unauthenticated'
  | 'authenticated'
  | 'incident_confirmed'
  | 'incident_initiated'
  | 'evidence_collecting'
  | 'submitted';

export type IncidentDraftStatus =
  | 'idle'
  | 'drafting'
  | 'ready_for_submission'
  | 'submitted';

export type UploadState =
  | 'idle'
  | 'uploading'
  | 'uploaded'
  | 'failed';

export type SubmissionValidations = {
  hasIncidentType: boolean;
  hasDescription: boolean;
  hasMedia: boolean;
};

export type VehicleResolutionMethod = 'assigned_vehicle' | 'qr_scan';

export type ProtocolContext = {
  isAuthenticated: boolean;
  vehicleResolved: boolean;
  vehicleResolutionMethod: VehicleResolutionMethod | null;
  vehicleId: string | null;
  qrToken: string | null;
  safetyAcknowledged: boolean;
  safetyGateViewedAt: string | null;
  safetyGateAcknowledgedAt: string | null;
  emergencyCallTapTimestamps: string[];
  safetyManagerCallTapTimestamps: string[];
  submissionValidations: SubmissionValidations;
};

export type ProtocolSnapshot = {
  state: DriverProtocolState;
  incidentDraftStatus: IncidentDraftStatus;
  uploadState: UploadState;
  context: ProtocolContext;
  updatedAt: string;
  version: 1;
};

export const PROTOCOL_PERSISTENCE_VERSION = 1 as const;

export const INITIAL_PROTOCOL_CONTEXT: ProtocolContext = {
  isAuthenticated: false,
  vehicleResolved: false,
  vehicleResolutionMethod: null,
  vehicleId: null,
  qrToken: null,
  safetyAcknowledged: false,
  safetyGateViewedAt: null,
  safetyGateAcknowledgedAt: null,
  emergencyCallTapTimestamps: [],
  safetyManagerCallTapTimestamps: [],
  submissionValidations: {
    hasIncidentType: false,
    hasDescription: false,
    hasMedia: false,
  },
};

export const INITIAL_PROTOCOL_SNAPSHOT: ProtocolSnapshot = {
  state: 'unauthenticated',
  incidentDraftStatus: 'idle',
  uploadState: 'idle',
  context: INITIAL_PROTOCOL_CONTEXT,
  updatedAt: new Date(0).toISOString(),
  version: PROTOCOL_PERSISTENCE_VERSION,
};

export const MINIMUM_SUBMISSION_VALIDATION_KEYS: ReadonlyArray<
  keyof SubmissionValidations
> = ['hasIncidentType', 'hasDescription', 'hasMedia'];

export function hasMinimumSubmissionValidations(
  validations: SubmissionValidations,
): boolean {
  return MINIMUM_SUBMISSION_VALIDATION_KEYS.every((key) => validations[key]);
}

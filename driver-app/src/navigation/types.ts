export type MediaPromptType =
  | 'general_scene'
  | 'third_party_vehicle'
  | 'third_party_document';

export type RootStackParamList = {
  PhoneEntry: undefined;
  OtpEntry: { phoneE164: string };
  DriverHome: undefined;
  QrScan: undefined;
  IncidentConfirm: undefined;
  VehicleConfirm: undefined;
  SafetyGate: undefined;
  IncidentStartLoading: undefined;
  InstructionStep: undefined;
  SceneFacts: undefined;
  ThirdPartyInfo: undefined;
  MediaCapture: {
    destinationPromptType?: MediaPromptType;
  } | undefined;
  Narrative: undefined;
  ReviewSubmit: undefined;
  IncidentStatus: undefined;
};

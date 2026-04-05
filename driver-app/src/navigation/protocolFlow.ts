export const PROTOCOL_ROUTE_ORDER = [
  'IncidentConfirm',
  'VehicleConfirm',
  'SafetyGate',
  'IncidentStartLoading',
  'InstructionStep',
  'SceneFacts',
  'ThirdPartyInfo',
  'MediaCapture',
  'Narrative',
  'ReviewSubmit',
  'IncidentStatus',
] as const;

export type ProtocolRouteName = (typeof PROTOCOL_ROUTE_ORDER)[number];

export const getProtocolPrerequisites = (
  routeName: ProtocolRouteName,
): ProtocolRouteName[] => {
  const routeIndex = PROTOCOL_ROUTE_ORDER.indexOf(routeName);
  return routeIndex <= 0 ? [] : [...PROTOCOL_ROUTE_ORDER.slice(0, routeIndex)];
};

export const getFirstIncompleteRoute = (
  completedRoutes: Set<ProtocolRouteName>,
): ProtocolRouteName => {
  return (
    PROTOCOL_ROUTE_ORDER.find((routeName) => !completedRoutes.has(routeName)) ??
    PROTOCOL_ROUTE_ORDER[PROTOCOL_ROUTE_ORDER.length - 1]
  );
};

export const canAccessProtocolRoute = (
  routeName: ProtocolRouteName,
  completedRoutes: Set<ProtocolRouteName>,
): boolean => {
  return getProtocolPrerequisites(routeName).every((route) =>
    completedRoutes.has(route),
  );
};

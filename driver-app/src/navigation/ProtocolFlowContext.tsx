import { ReactNode, createContext, useContext, useMemo, useState } from 'react';

import { INITIAL_PROTOCOL_CONTEXT } from '../types/protocol';
import { transitionProtocol } from '../store/protocolStore';
import {
  DriverProtocolState,
  ProtocolContext,
  VehicleResolutionMethod,
} from '../types/protocol';
import { ProtocolRouteName } from './protocolFlow';

type ProtocolFlowContextValue = {
  completedRoutes: Set<ProtocolRouteName>;
  workflowState: DriverProtocolState;
  protocolContext: ProtocolContext;
  startProtocol: () => void;
  completeRoute: (routeName: ProtocolRouteName) => void;
  transitionWorkflow: (toState: DriverProtocolState) => void;
  resolveVehicle: (payload: {
    vehicleId: string;
    method: VehicleResolutionMethod;
    qrToken?: string | null;
  }) => void;
  markSafetyGateViewed: () => void;
  acknowledgeSafetyGate: () => void;
  recordEmergencyCallTap: () => void;
  recordSafetyManagerCallTap: () => void;
  resetProtocol: () => void;
};

const ProtocolFlowContext = createContext<ProtocolFlowContextValue | undefined>(
  undefined,
);

export function ProtocolFlowProvider({ children }: { children: ReactNode }) {
  const [completedRoutes, setCompletedRoutes] = useState<Set<ProtocolRouteName>>(
    new Set(),
  );
  const [workflowState, setWorkflowState] =
    useState<DriverProtocolState>('authenticated');
  const [protocolContext, setProtocolContext] =
    useState<ProtocolContext>(INITIAL_PROTOCOL_CONTEXT);

  const value = useMemo<ProtocolFlowContextValue>(
    () => ({
      completedRoutes,
      workflowState,
      protocolContext,
      startProtocol: () => {
        setCompletedRoutes(new Set());
        setWorkflowState('authenticated');
        setProtocolContext({
          ...INITIAL_PROTOCOL_CONTEXT,
          isAuthenticated: true,
        });
      },
      completeRoute: (routeName) => {
        setCompletedRoutes((previous) => {
          const updated = new Set(previous);
          updated.add(routeName);
          return updated;
        });
      },
      transitionWorkflow: (toState) => {
        setWorkflowState((previousState) =>
          transitionProtocol(
            {
              state: previousState,
              incidentDraftStatus: 'idle',
              uploadState: 'idle',
              updatedAt: new Date().toISOString(),
              version: 1,
              context: protocolContext,
            },
            toState,
          ).state,
        );
      },
      resolveVehicle: ({ vehicleId, method, qrToken }) => {
        setProtocolContext((previous) => ({
          ...previous,
          vehicleResolved: true,
          vehicleResolutionMethod: method,
          vehicleId,
          qrToken: qrToken ?? null,
        }));
      },
      markSafetyGateViewed: () => {
        setProtocolContext((previous) => ({
          ...previous,
          safetyGateViewedAt: previous.safetyGateViewedAt ?? new Date().toISOString(),
        }));
      },
      acknowledgeSafetyGate: () => {
        setProtocolContext((previous) => ({
          ...previous,
          safetyAcknowledged: true,
          safetyGateAcknowledgedAt: new Date().toISOString(),
        }));
      },
      recordEmergencyCallTap: () => {
        setProtocolContext((previous) => ({
          ...previous,
          emergencyCallTapTimestamps: [
            ...previous.emergencyCallTapTimestamps,
            new Date().toISOString(),
          ],
        }));
      },
      recordSafetyManagerCallTap: () => {
        setProtocolContext((previous) => ({
          ...previous,
          safetyManagerCallTapTimestamps: [
            ...previous.safetyManagerCallTapTimestamps,
            new Date().toISOString(),
          ],
        }));
      },
      resetProtocol: () => {
        setCompletedRoutes(new Set());
        setWorkflowState('authenticated');
        setProtocolContext({
          ...INITIAL_PROTOCOL_CONTEXT,
          isAuthenticated: true,
        });
      },
    }),
    [completedRoutes, protocolContext, workflowState],
  );

  return (
    <ProtocolFlowContext.Provider value={value}>
      {children}
    </ProtocolFlowContext.Provider>
  );
}

export function useProtocolFlow() {
  const context = useContext(ProtocolFlowContext);
  if (!context) {
    throw new Error('useProtocolFlow must be used within ProtocolFlowProvider.');
  }

  return context;
}

import { ReactNode, createContext, useContext, useMemo, useState } from 'react';

import { transitionProtocol } from '../store/protocolStore';
import { DriverProtocolState } from '../types/protocol';
import { ProtocolRouteName } from './protocolFlow';

type ProtocolFlowContextValue = {
  completedRoutes: Set<ProtocolRouteName>;
  workflowState: DriverProtocolState;
  startProtocol: () => void;
  completeRoute: (routeName: ProtocolRouteName) => void;
  transitionWorkflow: (toState: DriverProtocolState) => void;
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

  const value = useMemo<ProtocolFlowContextValue>(
    () => ({
      completedRoutes,
      workflowState,
      startProtocol: () => {
        setCompletedRoutes(new Set());
        setWorkflowState('authenticated');
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
              context: {
                isAuthenticated: true,
                vehicleResolved: false,
                safetyAcknowledged: false,
                submissionValidations: {
                  hasIncidentType: false,
                  hasDescription: false,
                  hasMedia: false,
                },
              },
            },
            toState,
          ).state,
        );
      },
      resetProtocol: () => {
        setCompletedRoutes(new Set());
        setWorkflowState('authenticated');
      },
    }),
    [completedRoutes, workflowState],
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

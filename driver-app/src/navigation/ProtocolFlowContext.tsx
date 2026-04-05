import { ReactNode, createContext, useContext, useMemo, useState } from 'react';

import { ProtocolRouteName } from './protocolFlow';

type ProtocolFlowContextValue = {
  completedRoutes: Set<ProtocolRouteName>;
  startProtocol: () => void;
  completeRoute: (routeName: ProtocolRouteName) => void;
  resetProtocol: () => void;
};

const ProtocolFlowContext = createContext<ProtocolFlowContextValue | undefined>(
  undefined,
);

export function ProtocolFlowProvider({ children }: { children: ReactNode }) {
  const [completedRoutes, setCompletedRoutes] = useState<Set<ProtocolRouteName>>(
    new Set(),
  );

  const value = useMemo<ProtocolFlowContextValue>(
    () => ({
      completedRoutes,
      startProtocol: () => {
        setCompletedRoutes(new Set());
      },
      completeRoute: (routeName) => {
        setCompletedRoutes((previous) => {
          const updated = new Set(previous);
          updated.add(routeName);
          return updated;
        });
      },
      resetProtocol: () => {
        setCompletedRoutes(new Set());
      },
    }),
    [completedRoutes],
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

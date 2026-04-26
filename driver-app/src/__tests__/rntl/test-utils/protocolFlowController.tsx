/**
 * `protocolFlowController` — a tiny inspector component for tests that
 * need to assert on or seed the live `ProtocolFlowContext` value.
 *
 * Render it as a sibling of the screen under test:
 *
 *   const controller = createProtocolFlowController();
 *   renderWithProviders(
 *     <>
 *       <ProtocolFlowSpy controller={controller} />
 *       <SomeScreen />
 *     </>,
 *   );
 *
 *   // Read the latest snapshot any time:
 *   expect(controller.current?.protocolContext.vehicleResolved).toBe(false);
 *
 *   // Drive the state machine from a test:
 *   act(() => controller.current?.startProtocol());
 *
 * The controller object is mutable; `current` is updated on every render
 * of `<ProtocolFlowSpy />`, mirroring the React `ref.current` ergonomics
 * without requiring a `useRef` in the test body.
 */

import { useEffect } from 'react';

import { useProtocolFlow } from '../../../navigation/ProtocolFlowContext';

export type ProtocolFlowSnapshot = ReturnType<typeof useProtocolFlow>;

export type ProtocolFlowController = {
  current: ProtocolFlowSnapshot | null;
};

export function createProtocolFlowController(): ProtocolFlowController {
  return { current: null };
}

export function ProtocolFlowSpy({
  controller,
}: {
  controller: ProtocolFlowController;
}) {
  const value = useProtocolFlow();
  // Sync on every commit so tests always see the latest snapshot. Using
  // an effect (as opposed to assigning during render) keeps the assignment
  // out of React's render phase, which avoids the strict-mode double-call
  // landmines.
  useEffect(() => {
    controller.current = value;
  }, [controller, value]);
  return null;
}

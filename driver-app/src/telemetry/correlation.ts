export function createWorkflowCorrelationId(): string {
  if (typeof globalThis.crypto?.randomUUID === 'function') {
    return globalThis.crypto.randomUUID();
  }

  return `wf-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

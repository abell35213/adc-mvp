import AsyncStorageMock from './mocks/asyncStorage';
import {
  PROTOCOL_RESUME_STORAGE_KEY,
  resolveProtocolResumeState,
} from '../store/protocolResumeStore';

describe('protocolResumeStore — corruption hydration', () => {
  beforeEach(() => {
    AsyncStorageMock.__reset();
  });

  it('returns an empty resume state when storage has no entries', async () => {
    const result = await resolveProtocolResumeState(null);

    expect(result.hasLocalDrafts).toBe(false);
    expect(result.completedRoutes.size).toBe(0);
  });

  it('treats corrupted JSON as an empty state instead of throwing', async () => {
    // Simulate a partially-written or downgrade-corrupted payload. The store
    // must absorb this without throwing or the user gets stuck on the
    // protocol-resume screen forever.
    await AsyncStorageMock.setItem(PROTOCOL_RESUME_STORAGE_KEY, '{not-valid-json');

    const result = await resolveProtocolResumeState(null);

    expect(result.hasLocalDrafts).toBe(false);
    expect(result.completedRoutes.size).toBe(0);
  });

  it('resets when the stored payload is a non-object (e.g. a stray string)', async () => {
    await AsyncStorageMock.setItem(
      PROTOCOL_RESUME_STORAGE_KEY,
      JSON.stringify('an older build wrote a bare string here'),
    );

    const result = await resolveProtocolResumeState(null);

    expect(result.completedRoutes.size).toBe(0);
  });

  it('honours a valid stored payload and ignores unknown route names', async () => {
    await AsyncStorageMock.setItem(
      PROTOCOL_RESUME_STORAGE_KEY,
      JSON.stringify({
        incidentId: 'incident-123',
        completedRoutes: ['SafetyGate', 'TotallyMadeUpRoute', 'SceneFacts'],
        updatedAt: new Date().toISOString(),
      }),
    );

    const result = await resolveProtocolResumeState('incident-123');

    // Unknown route names must be filtered out by the runtime guard.
    expect(result.completedRoutes.has('TotallyMadeUpRoute' as never)).toBe(false);
    // Known routes survive (the exact set depends on what's in
    // PROTOCOL_ROUTE_ORDER, so we just assert presence of at least one valid
    // entry rather than the full set, to keep this test resilient to
    // future additions to the flow.)
    expect(result.completedRoutes.size).toBeGreaterThan(0);
  });
});

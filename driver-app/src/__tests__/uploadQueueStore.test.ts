const UPLOAD_QUEUE_STORAGE_KEY = 'driver_upload_queue_v1';

type AsyncStorageMockModule = typeof import('./mocks/asyncStorage')['default'];
type UploadQueueStoreModule = typeof import('../store/uploadQueueStore');

function loadFreshModules(): {
  store: UploadQueueStoreModule;
  asyncStorage: AsyncStorageMockModule;
} {
  // Reset the module registry so the store's module-level cached state
  // (``hydrated``, ``queueState``) AND the async-storage mock's in-memory
  // backing map are both freshly created. This guarantees the next hydrate
  // call actually reads from storage (instead of returning the memoised
  // result from a previous test).
  let store!: UploadQueueStoreModule;
  let asyncStorage!: AsyncStorageMockModule;
  jest.isolateModules(() => {
    // The mock is wired in via ``moduleNameMapper`` in jest.config.js, so the
    // store-under-test will receive *this same* freshly-loaded mock instance.
    asyncStorage = (require('./mocks/asyncStorage') as { default: AsyncStorageMockModule })
      .default;
    store = require('../store/uploadQueueStore') as UploadQueueStoreModule;
  });
  return { store, asyncStorage };
}

describe('uploadQueueStore — hydration shape guard', () => {
  beforeEach(() => {
    jest.resetModules();
  });

  it('starts with an empty items[] when storage has no entry', async () => {
    const { store } = loadFreshModules();

    await store.hydrateUploadQueueStore();
    const snap = store.getUploadQueueSnapshot();

    expect(snap).toBeDefined();
    expect(Array.isArray(snap.items)).toBe(true);
    expect(snap.items).toHaveLength(0);
    expect(typeof snap.version).toBe('number');
    expect(typeof snap.updatedAt).toBe('string');
  });

  it('does not throw when storage contains corrupted JSON', async () => {
    const { store, asyncStorage } = loadFreshModules();
    await asyncStorage.setItem(UPLOAD_QUEUE_STORAGE_KEY, '{not-valid-json');

    // The first hydration after a fresh module load is the one that exercises
    // the JSON.parse path — the corruption guard must swallow the parse error
    // and leave the queue in a safe empty state.
    await expect(store.hydrateUploadQueueStore()).resolves.toBeUndefined();

    const snap = store.getUploadQueueSnapshot();
    expect(Array.isArray(snap.items)).toBe(true);
    expect(snap.items).toHaveLength(0);
  });
});



/**
 * Lightweight in-memory mock for ``@react-native-async-storage/async-storage``.
 *
 * Tracks the latest value for each key in a ``Map``. ``__reset()`` is exposed
 * for tests that need a clean slate between cases.
 */

const store = new Map<string, string>();

const AsyncStorage = {
  async getItem(key: string): Promise<string | null> {
    return store.has(key) ? (store.get(key) as string) : null;
  },
  async setItem(key: string, value: string): Promise<void> {
    store.set(key, value);
  },
  async removeItem(key: string): Promise<void> {
    store.delete(key);
  },
  async multiRemove(keys: readonly string[]): Promise<void> {
    keys.forEach((key) => store.delete(key));
  },
  async clear(): Promise<void> {
    store.clear();
  },
  /** Test helper. Not part of the real AsyncStorage API. */
  __reset(): void {
    store.clear();
  },
};

export default AsyncStorage;

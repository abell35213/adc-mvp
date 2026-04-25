/**
 * Minimal in-memory mock for ``expo-secure-store``.
 */

const store = new Map<string, string>();

export async function getItemAsync(key: string): Promise<string | null> {
  return store.has(key) ? (store.get(key) as string) : null;
}

export async function setItemAsync(key: string, value: string): Promise<void> {
  store.set(key, value);
}

export async function deleteItemAsync(key: string): Promise<void> {
  store.delete(key);
}

/** Test helper. Not part of the real expo-secure-store API. */
export function __reset(): void {
  store.clear();
}

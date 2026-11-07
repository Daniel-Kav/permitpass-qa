import { Outbox, Storage } from '../src/outbox';

/** Storage that survives "restarting the app" as long as you reuse the same instance. */
export function memoryStorage(): Storage & { data: Record<string, string> } {
  const data: Record<string, string> = {};
  return { data, getItem: async (k) => data[k] ?? null, setItem: async (k, v) => { data[k] = v; } };
}

let n = 0;
export const sequentialKey = () => `key-${String(++n).padStart(4, '0')}`;
export const freshOutbox = (storage = memoryStorage(), now?: () => number) => new Outbox(storage, sequentialKey, now);

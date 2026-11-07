// Offline outbox (#48): applications created without a connection are kept on the phone and sent later,
// oldest first. Each item keeps ONE Idempotency-Key for its whole life, so a retry after a lost response
// replays the server's first answer instead of creating a duplicate (#47).
export interface OutboxItem {
  key: string;                 // Idempotency-Key, reused on every attempt
  owner: string;               // email of the citizen who created it; never sent under another account
  business_name: string;
  kra_pin: string;
  createdAt: number;
  attempts: number;
  nextAttemptAt: number;
  status: 'queued' | 'failed';
  error?: string;
}

export type SendResult = { kind: 'sent' } | { kind: 'refused'; reason: string } | { kind: 'retry' };

export interface Storage {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
}

const STORAGE_KEY = 'permitpass.outbox.v1';
export const backoffMs = (attempts: number) => Math.min(5_000 * 2 ** Math.max(0, attempts - 1), 5 * 60_000);

export class Outbox {
  private items: OutboxItem[] = [];
  private listeners = new Set<(items: OutboxItem[]) => void>();
  private flushing: Promise<{ sent: OutboxItem[]; refused: OutboxItem[] }> | null = null;

  constructor(private storage: Storage, private newKey: () => string, private now: () => number = Date.now) {}

  async load() {
    try {
      const raw = await this.storage.getItem(STORAGE_KEY);
      this.items = raw ? JSON.parse(raw) : [];
    } catch {
      this.items = [];                                   // unreadable storage: start empty rather than crash
    }
    this.emit();
    return this.list();
  }

  list(owner?: string) {
    return this.items.filter((i) => owner === undefined || i.owner === owner).map((i) => ({ ...i }));
  }

  subscribe(fn: (items: OutboxItem[]) => void) {
    this.listeners.add(fn);
    return () => { this.listeners.delete(fn); };
  }

  /** Keep an application for later. Pass the key already used for the failed online attempt, if any. */
  async add(owner: string, business_name: string, kra_pin: string, key?: string) {
    const item: OutboxItem = { key: key ?? this.newKey(), owner, business_name, kra_pin, createdAt: this.now(),
      attempts: 0, nextAttemptAt: 0, status: 'queued' };
    this.items.push(item);
    await this.save();
    return { ...item };
  }

  async remove(key: string) {
    this.items = this.items.filter((i) => i.key !== key);
    await this.save();
  }

  /** Send due items for this owner, oldest first. Stops at the first 'retry' so order is kept. */
  flush(owner: string, send: (item: OutboxItem) => Promise<SendResult>) {
    if (!this.flushing) {
      this.flushing = this.run(owner, send).finally(() => { this.flushing = null; });
    }
    return this.flushing;
  }

  private async run(owner: string, send: (item: OutboxItem) => Promise<SendResult>) {
    const sent: OutboxItem[] = [];
    const refused: OutboxItem[] = [];
    const due = this.items
      .filter((i) => i.owner === owner && i.status === 'queued')
      .sort((a, b) => a.createdAt - b.createdAt);
    for (const item of due) {
      if (item.nextAttemptAt > this.now()) break;
      item.attempts += 1;
      let result: SendResult;
      try {
        result = await send(item);
      } catch {
        result = { kind: 'retry' };
      }
      if (result.kind === 'sent') {
        this.items = this.items.filter((i) => i.key !== item.key);
        sent.push(item);
      } else if (result.kind === 'refused') {
        item.status = 'failed';
        item.error = result.reason;
        refused.push(item);
      } else {
        item.nextAttemptAt = this.now() + backoffMs(item.attempts);
        await this.save();
        break;
      }
      await this.save();
    }
    return { sent, refused };
  }

  private async save() {
    await this.storage.setItem(STORAGE_KEY, JSON.stringify(this.items));
    this.emit();
  }

  private emit() {
    const snapshot = this.list();
    this.listeners.forEach((fn) => fn(snapshot));
  }
}

// The outbox on its own: ordering, one key per item for life, backoff, refusals, persistence, owners. (#48)
import { Outbox, OutboxItem, SendResult, backoffMs } from '../src/outbox';
import { freshOutbox, memoryStorage } from '../test-utils/memoryStorage';

const ME = 'citizen@permitpass.test';
const sent = (): SendResult => ({ kind: 'sent' });

test('items are sent oldest first, each with its own key', async () => {
  let t = 1000;
  const box = freshOutbox(memoryStorage(), () => t);
  await box.add(ME, 'First', 'A123456789Z'); t += 1;
  await box.add(ME, 'Second', 'A123456789Z');
  const seen: OutboxItem[] = [];
  const r = await box.flush(ME, async (i) => { seen.push(i); return sent(); });
  expect(seen.map((i) => i.business_name)).toEqual(['First', 'Second']);
  expect(new Set(seen.map((i) => i.key)).size).toBe(2);
  expect(r.sent).toHaveLength(2);
  expect(box.list()).toEqual([]);
});

test('a retried item keeps the SAME key on every attempt', async () => {
  let t = 0;
  const box = freshOutbox(memoryStorage(), () => t);
  const item = await box.add(ME, 'Duka', 'A123456789Z', 'key-from-the-failed-online-attempt');
  const keys: string[] = [];
  const results: SendResult[] = [{ kind: 'retry' }, { kind: 'retry' }, { kind: 'sent' }];
  for (const _ of results) {
    t += 10 * 60_000;                                            // well past any backoff
    await box.flush(ME, async (i) => { keys.push(i.key); return results[keys.length - 1]; });
  }
  expect(keys).toEqual([item.key, item.key, item.key]);
  expect(item.key).toBe('key-from-the-failed-online-attempt');
});

test('after a retry the item waits for its backoff, and order is kept', async () => {
  let t = 0;
  const box = freshOutbox(memoryStorage(), () => t);
  await box.add(ME, 'A', 'A123456789Z'); t += 1;
  await box.add(ME, 'B', 'A123456789Z');
  const send = jest.fn(async () => ({ kind: 'retry' }) as SendResult);
  await box.flush(ME, send);
  expect(send).toHaveBeenCalledTimes(1);                        // stopped at A: B must not overtake it
  t += backoffMs(1) - 1;
  await box.flush(ME, send);
  expect(send).toHaveBeenCalledTimes(1);                        // still backing off
  t += 1;
  await box.flush(ME, send);
  expect(send).toHaveBeenCalledTimes(2);
});

test.each([[1, 5_000], [2, 10_000], [3, 20_000], [7, 300_000], [20, 300_000]])('backoff after %i attempts is %i ms', (n, ms) => {
  expect(backoffMs(n)).toBe(ms);
});

test('a refusal is kept with its reason and never resent', async () => {
  const box = freshOutbox();
  await box.add(ME, 'Ghost', 'A999999999Z');
  const send = jest.fn(async () => ({ kind: 'refused', reason: 'KRA PIN is not registered' }) as SendResult);
  await box.flush(ME, send);
  await box.flush(ME, send);
  expect(send).toHaveBeenCalledTimes(1);
  expect(box.list()[0]).toMatchObject({ status: 'failed', error: 'KRA PIN is not registered' });
  await box.remove(box.list()[0].key);
  expect(box.list()).toEqual([]);
});

test('a thrown error counts as retry, not as sent', async () => {
  const box = freshOutbox();
  await box.add(ME, 'Duka', 'A123456789Z');
  await box.flush(ME, async () => { throw new Error('boom'); });
  expect(box.list()[0]).toMatchObject({ status: 'queued', attempts: 1 });
});

test('the outbox survives closing the app', async () => {
  const storage = memoryStorage();
  const before = freshOutbox(storage);
  const item = await before.add(ME, 'Duka', 'A123456789Z');
  const after = new Outbox(storage, () => 'unused');            // a fresh start with the same phone storage
  expect(await after.load()).toEqual([expect.objectContaining({ key: item.key, business_name: 'Duka' })]);
});

test('unreadable storage starts empty instead of crashing', async () => {
  const storage = memoryStorage();
  storage.data['permitpass.outbox.v1'] = '{not json';
  expect(await new Outbox(storage, () => 'k').load()).toEqual([]);
});

test("another citizen on the same phone never sends someone else's items", async () => {
  const box = freshOutbox();
  await box.add('owner@example.com', 'Theirs', 'A123456789Z');
  const send = jest.fn(async () => sent());
  await box.flush(ME, send);
  expect(send).not.toHaveBeenCalled();
  expect(box.list(ME)).toEqual([]);
  expect(box.list('owner@example.com')).toHaveLength(1);
});

test('two flushes at once run only once', async () => {
  const box = freshOutbox();
  await box.add(ME, 'Duka', 'A123456789Z');
  let release!: () => void;
  const send = jest.fn(() => new Promise<SendResult>((r) => { release = () => r(sent()); }));
  const a = box.flush(ME, send);
  const b = box.flush(ME, send);
  release();
  await Promise.all([a, b]);
  expect(send).toHaveBeenCalledTimes(1);
});

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import NetInfo from '@react-native-community/netinfo';
import { Application, ApiError, api, isRetryable } from '../api';
import { Outbox, OutboxItem, SendResult } from '../outbox';
import { newKey as defaultNewKey, outbox as defaultOutbox } from '../outboxInstance';
import { Button, Field, Message, colors } from '../ui';

const STATE_TEXT: Record<string, string> = {
  draft: 'Draft', submitted: 'Submitted', payment_pending: 'Waiting for M-Pesa', paid: 'Paid',
  approved: 'Approved', issued: 'Issued', rejected: 'Rejected', revoked: 'Revoked',
};

export function ApplicationsScreen({ token, owner, onVerify, outbox = defaultOutbox, newKey = defaultNewKey }: {
  token: string; owner: string; onVerify: (n: string, sig: string) => void; outbox?: Outbox; newKey?: () => string;
}) {
  const [apps, setApps] = useState<Application[]>([]);
  const [name, setName] = useState('');
  const [pin, setPin] = useState('');
  const [msg, setMsg] = useState<{ text: string; kind: 'error' | 'success' }>({ text: '', kind: 'success' });
  const [refreshing, setRefreshing] = useState(false);
  const latest = useRef(0);           // only the newest response may render (same rule as the portal, #43)
  const waiting = useRef(new Set<string>());
  const [saved, setSaved] = useState<OutboxItem[]>([]);

  const load = useCallback(async () => {
    const ticket = ++latest.current;
    const items = await api.list(token);
    if (ticket !== latest.current) return;
    for (const a of items) {
      if (waiting.current.has(a.id) && a.state !== 'payment_pending') {
        waiting.current.delete(a.id);
        setMsg(a.state === 'paid' ? { text: `Payment received for ${a.business_name}.`, kind: 'success' }
          : { text: `Payment for ${a.business_name} did not go through.`, kind: 'error' });
      }
    }
    setApps(items);
  }, [token]);

  useEffect(() => { load().catch((e) => setMsg({ text: e.message, kind: 'error' })); }, [load]);

  // ---------- offline outbox (#48) ----------
  const send = useCallback(async (item: OutboxItem): Promise<SendResult> => {
    try {
      await api.create(token, item.business_name, item.kra_pin, item.key);
      return { kind: 'sent' };
    } catch (e) {
      if (isRetryable(e)) return { kind: 'retry' };
      return { kind: 'refused', reason: e instanceof ApiError ? e.message : String(e) };
    }
  }, [token]);

  const flush = useCallback(async () => {
    const { sent, refused } = await outbox.flush(owner, send);
    if (sent.length) {
      setMsg({ text: `Sent ${sent.length} saved application${sent.length === 1 ? '' : 's'}.`, kind: 'success' });
      await load().catch(() => {});
    } else if (refused.length) {
      setMsg({ text: `${refused[0].business_name} could not be sent: ${refused[0].error}`, kind: 'error' });
    }
  }, [outbox, owner, send, load]);

  useEffect(() => {
    const off = outbox.subscribe(() => setSaved(outbox.list(owner)));
    outbox.load().then(() => { setSaved(outbox.list(owner)); flush(); });
    const offNet = NetInfo.addEventListener((s) => { if (s.isConnected) flush(); });   // back online
    return () => { off(); offNet(); };
  }, [outbox, owner, flush]);

  const queued = saved.some((i) => i.status === 'queued');
  useEffect(() => {
    if (!queued) return;
    const t = setInterval(() => { flush(); }, 15000);                                    // and keep trying
    return () => clearInterval(t);
  }, [queued, flush]);

  // Poll every 2 s while any payment is waiting for M-Pesa
  const pending = apps.some((a) => a.state === 'payment_pending');
  useEffect(() => {
    if (!pending) return;
    const t = setInterval(() => load().catch(() => {}), 2000);
    return () => clearInterval(t);
  }, [pending, load]);

  async function run(fn: () => Promise<unknown>, success?: string) {
    try {
      await fn();
      if (success) setMsg({ text: success, kind: 'success' });
      await load();
    } catch (e: any) {
      setMsg({ text: e.message, kind: 'error' });
    }
  }

  async function create() {
    const n = name.trim();
    const p = pin.trim().toUpperCase();
    const key = newKey();          // one key for this application, online or later from the outbox
    try {
      await api.create(token, n, p, key);
      setName(''); setPin('');
      setMsg({ text: `Application for ${n} created as a draft.`, kind: 'success' });
      await load();
    } catch (e) {
      if (e instanceof ApiError && (e.status === 0 || e.status >= 500)) {
        await outbox.add(owner, n, p, key);
        setName(''); setPin('');
        setMsg({ text: `No connection. ${n} is saved on this phone and will be sent automatically when you're back online.`, kind: 'success' });
      } else {
        setMsg({ text: (e as Error).message, kind: 'error' });
      }
    }
  }

  return (
    <ScrollView refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load().catch(() => {}); setRefreshing(false); }} />}>
      <Text accessibilityRole="header" style={st.h1}>My applications</Text>
      <Message text={msg.text} kind={msg.kind} />
      <View style={st.card}>
        <Text accessibilityRole="header" style={st.h2}>New permit application</Text>
        <Field label="Business name" testID="business-name" value={name} onChangeText={setName} />
        <Field label="KRA PIN" testID="kra-pin" value={pin} onChangeText={setPin} autoCapitalize="characters"
          hint="A or P, 9 digits, then a letter, e.g. A123456789Z" />
        <Button title="Create application" testID="create" onPress={create} />
      </View>
      {saved.length > 0 && (
        <View style={st.card} testID="outbox">
          <Text accessibilityRole="header" style={st.h2}>Saved on this phone</Text>
          {saved.map((i) => (
            <View key={i.key} testID={`outbox-${i.business_name}`} style={{ marginBottom: 10 }}>
              <Text style={st.name}>{i.business_name}</Text>
              {i.status === 'queued'
                ? <Text style={st.note}>Waiting for a connection. It will be sent automatically.</Text>
                : <>
                    <Text style={[st.note, { color: colors.danger }]}>Not sent: {i.error}</Text>
                    <Button title="Remove" kind="secondary" label={`Remove ${i.business_name}`} testID={`remove-${i.business_name}`}
                      onPress={() => outbox.remove(i.key)} />
                  </>}
            </View>
          ))}
        </View>
      )}
      {apps.length === 0 ? <Text style={st.muted}>No applications yet.</Text> : null}
      {apps.map((a) => (
        <AppCard key={a.id} a={a} token={token} onVerify={onVerify}
          onSubmit={() => run(() => api.submit(token, a.id), `${a.business_name} submitted.`)}
          onPay={(phone) => run(async () => { await api.pay(token, a.id, phone, newKey()); waiting.current.add(a.id); },
            `Payment request sent to ${phone}. Approve it on your phone.`)} />
      ))}
    </ScrollView>
  );
}

function AppCard({ a, token, onSubmit, onPay, onVerify }: {
  a: Application; token: string; onSubmit: () => void; onPay: (phone: string) => void; onVerify: (n: string, sig: string) => void;
}) {
  const [paying, setPaying] = useState(false);
  const [phone, setPhone] = useState('');
  return (
    <View style={st.card} testID={`app-${a.business_name}`} accessible={false}>
      <Text style={st.name}>{a.business_name}</Text>
      <Text accessibilityLabel={`Status: ${STATE_TEXT[a.state]}`} testID={`state-${a.business_name}`}
        style={[st.badge, { color: a.state === 'rejected' || a.state === 'revoked' ? colors.danger : a.state === 'issued' || a.state === 'paid' ? colors.brand : colors.warn }]}>
        {STATE_TEXT[a.state]}
      </Text>
      {a.state === 'draft' && <Button title="Submit" label={`Submit ${a.business_name}`} testID={`submit-${a.business_name}`} onPress={onSubmit} />}
      {a.state === 'submitted' && (
        <>
          {a.payment_note ? <Text style={st.note} testID={`note-${a.business_name}`}>{a.payment_note}</Text> : null}
          {!paying ? (
            <Button title={`Pay KES ${a.fee_kes.toLocaleString()}`} label={`Pay KES ${a.fee_kes} for ${a.business_name}`}
              testID={`pay-${a.business_name}`} onPress={() => setPaying(true)} />
          ) : (
            <View>
              <Field label="M-Pesa phone number" testID={`phone-${a.business_name}`} value={phone} onChangeText={setPhone}
                keyboardType="phone-pad" autoComplete="tel" autoFocus placeholder="0712 345 678" />
              <Button title="Send payment request" testID={`send-${a.business_name}`} onPress={() => { onPay(phone.trim()); setPaying(false); }} />
              <View style={{ height: 8 }} />
              <Button title="Cancel" kind="secondary" onPress={() => setPaying(false)} />
            </View>
          )}
        </>
      )}
      {a.state === 'payment_pending' && <Text style={st.note}>Check your phone and enter your M-Pesa PIN to approve the payment…</Text>}
      {a.state === 'rejected' && a.rejection_reason ? <Text style={st.note}>Rejected: {a.rejection_reason}</Text> : null}
      {(a.state === 'issued' || a.state === 'revoked') && (
        <Button title="View certificate" kind="secondary" label={`View certificate for ${a.business_name}`} testID={`cert-${a.business_name}`}
          onPress={async () => { const c = await api.certificate(token, a.id); onVerify(c.number, c.signature); }} />
      )}
    </View>
  );
}

const st = StyleSheet.create({
  h1: { fontSize: 24, fontWeight: '700', color: colors.ink, marginBottom: 8 },
  h2: { fontSize: 18, fontWeight: '700', color: colors.ink, marginBottom: 12 },
  card: { backgroundColor: '#fff', borderColor: colors.line, borderWidth: 1, borderRadius: 8, padding: 16, marginBottom: 12 },
  name: { fontSize: 17, fontWeight: '700', color: colors.ink },
  badge: { fontWeight: '700', marginVertical: 6 },
  note: { color: colors.ink, marginBottom: 8 },
  muted: { color: colors.muted, marginVertical: 8 },
});

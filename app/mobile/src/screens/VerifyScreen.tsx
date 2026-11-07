import React, { useEffect, useState } from 'react';
import { Text, View } from 'react-native';
import { Verdict, api } from '../api';
import { Button, Field, Message, colors } from '../ui';

const TEXT = { valid: 'Valid permit', revoked: 'This permit has been revoked', expired: 'This permit has expired', invalid: 'Not a valid PermitPass certificate' };

export function VerifyScreen({ initial }: { initial?: { number: string; sig: string } }) {
  const [number, setNumber] = useState(initial?.number ?? '');
  const [sig, setSig] = useState(initial?.sig ?? '');
  const [result, setResult] = useState<Verdict | null>(null);
  const [error, setError] = useState('');

  async function check(n = number, s = sig) {
    setError('');
    setResult(null);
    try { setResult(await api.verify(n, s)); } catch (e: any) { setError(e.message); }
  }
  useEffect(() => { if (initial) check(initial.number, initial.sig); }, []);   // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <View>
      <Text accessibilityRole="header" style={{ fontSize: 24, fontWeight: '700', color: colors.ink, marginBottom: 16 }}>Verify a permit</Text>
      <Field label="Certificate number" testID="cert-number" value={number} onChangeText={setNumber} autoCapitalize="characters" placeholder="PP-2026-XXXXXXXX" />
      <Field label="Security code" testID="cert-code" value={sig} onChangeText={setSig} autoCapitalize="none" />
      <Button title="Verify" testID="verify" onPress={() => check()} />
      <Message text={error} kind="error" />
      {result && (
        <View accessibilityLiveRegion="polite" testID="verdict" style={{ marginTop: 16 }}>
          <Text testID={`verdict-${result.status}`} style={{ fontSize: 20, fontWeight: '700', color: result.status === 'valid' ? colors.brand : colors.danger }}>
            {TEXT[result.status]}
          </Text>
          {result.business_name ? <Text>Business: {result.business_name}</Text> : null}
          {result.expires_at ? <Text>Valid until: {new Date(result.expires_at).toDateString()}</Text> : null}
        </View>
      )}
    </View>
  );
}

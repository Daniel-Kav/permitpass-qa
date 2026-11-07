import React, { useState } from 'react';
import { Text, View } from 'react-native';
import { api } from '../api';
import { Button, Field, Message, colors } from '../ui';

export function LoginScreen({ onLoggedIn }: { onLoggedIn: (token: string) => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit() {
    setError('');
    setBusy(true);
    try {
      const r = await api.login(email, password);
      if (r.role !== 'citizen') setError('This app is for business owners. Officers use the web portal.');
      else onLoggedIn(r.access_token);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <View>
      <Text accessibilityRole="header" style={{ fontSize: 24, fontWeight: '700', color: colors.ink, marginBottom: 16 }}>Log in</Text>
      <Field label="Email" testID="email" value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" autoComplete="email" />
      <Field label="Password" testID="password" value={password} onChangeText={setPassword} secureTextEntry autoComplete="password" />
      <Message text={error} kind="error" />
      <Button title={busy ? 'Logging in…' : 'Log in'} label="Log in" testID="login" onPress={submit} disabled={busy} />
    </View>
  );
}

import { StatusBar } from 'expo-status-bar';
import React, { useState } from 'react';
import { SafeAreaView, StyleSheet, View } from 'react-native';
import { ApplicationsScreen } from './src/screens/ApplicationsScreen';
import { LoginScreen } from './src/screens/LoginScreen';
import { VerifyScreen } from './src/screens/VerifyScreen';
import { Button, colors } from './src/ui';

type Screen = { name: 'apps' } | { name: 'verify'; initial?: { number: string; sig: string } };

export default function App() {
  const [session, setSession] = useState<{ token: string; email: string } | null>(null);
  const token = session?.token ?? null;
  const [screen, setScreen] = useState<Screen>({ name: 'apps' });

  return (
    <SafeAreaView style={styles.root}>
      <StatusBar style="light" />
      <View style={styles.header} />
      <View style={styles.body}>
        {screen.name === 'verify' ? (
          <VerifyScreen initial={screen.initial} />
        ) : token ? (
          <ApplicationsScreen token={token} owner={session!.email} onVerify={(number, sig) => setScreen({ name: 'verify', initial: { number, sig } })} />
        ) : (
          <LoginScreen onLoggedIn={(t, email) => setSession({ token: t, email })} />
        )}
      </View>
      <View style={styles.nav}>
        {screen.name === 'verify'
          ? <Button title={token ? 'My applications' : 'Back to log in'} kind="secondary" testID="nav-apps" onPress={() => setScreen({ name: 'apps' })} />
          : <Button title="Verify a permit" kind="secondary" testID="nav-verify" onPress={() => setScreen({ name: 'verify' })} />}
        {token ? <Button title="Log out" kind="secondary" testID="logout" onPress={() => { setSession(null); setScreen({ name: 'apps' }); }} /> : null}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  header: { height: 8, backgroundColor: colors.brand },
  body: { flex: 1, padding: 16 },
  nav: { flexDirection: 'row', gap: 8, padding: 12, borderTopWidth: 1, borderColor: colors.line, justifyContent: 'space-around' },
});

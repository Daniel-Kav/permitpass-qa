import React from 'react';
import { Pressable, StyleSheet, Text, TextInput, TextInputProps, View } from 'react-native';

export const colors = { brand: '#0b5d3b', ink: '#1b1f24', muted: '#57606a', line: '#d0d7de', danger: '#a40e26', warn: '#7a4b00', bg: '#f6f7f9' };

export function Button({ title, onPress, label, kind = 'primary', disabled, testID }: {
  title: string; onPress: () => void; label?: string; kind?: 'primary' | 'secondary' | 'danger'; disabled?: boolean; testID?: string;
}) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label ?? title} accessibilityState={{ disabled: !!disabled }}
      testID={testID} onPress={onPress} disabled={disabled}
      style={({ pressed }) => [s.button, s[kind], (pressed || disabled) && { opacity: 0.6 }]}>
      <Text style={[s.buttonText, kind === 'secondary' && { color: colors.brand }]}>{title}</Text>
    </Pressable>
  );
}

export function Field({ label, hint, ...props }: TextInputProps & { label: string; hint?: string }) {
  return (
    <View style={{ marginBottom: 12 }}>
      <Text style={s.label}>{label}</Text>
      <TextInput accessibilityLabel={label} accessibilityHint={hint} placeholderTextColor={colors.muted} style={s.input} {...props} />
      {hint ? <Text style={s.hint}>{hint}</Text> : null}
    </View>
  );
}

export function Message({ text, kind }: { text: string; kind: 'error' | 'success' }) {
  if (!text) return null;
  return (
    <Text accessibilityLiveRegion="polite" accessibilityRole="alert" testID={`message-${kind}`}
      style={[s.message, { color: kind === 'error' ? colors.danger : colors.brand }]}>{text}</Text>
  );
}

const s = StyleSheet.create({
  button: { borderRadius: 8, paddingVertical: 12, paddingHorizontal: 16, alignItems: 'center', minHeight: 48, justifyContent: 'center' },
  primary: { backgroundColor: colors.brand }, secondary: { backgroundColor: '#fff', borderWidth: 1, borderColor: colors.brand },
  danger: { backgroundColor: colors.danger },
  buttonText: { color: '#fff', fontWeight: '600', fontSize: 16 },
  label: { fontWeight: '600', marginBottom: 4, color: colors.ink, fontSize: 15 },
  hint: { color: colors.muted, fontSize: 13, marginTop: 2 },
  input: { borderWidth: 1, borderColor: '#8c959f', borderRadius: 6, padding: 12, fontSize: 16, backgroundColor: '#fff', color: colors.ink },
  message: { marginVertical: 8, fontSize: 15, fontWeight: '600' },
});

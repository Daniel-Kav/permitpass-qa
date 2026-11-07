// Every control a screen-reader user can reach must say what it is.
import { fireEvent, render, screen } from '@testing-library/react-native';
import React from 'react';
import { ReactTestInstance } from 'react-test-renderer';
import App from '../App';
import { ApplicationsScreen } from '../src/screens/ApplicationsScreen';
import { VerifyScreen } from '../src/screens/VerifyScreen';
import { installFakeApi } from '../test-utils/fakeApi';
import { freshOutbox } from '../test-utils/memoryStorage';

function unlabelled(root: ReactTestInstance): string[] {
  const problems: string[] = [];
  root.findAll((n) => typeof n.type === 'string' && ((n.type as string) === 'TextInput' || n.props.accessibilityRole === 'button'))
    .forEach((n) => {
      if (!n.props.accessibilityLabel) problems.push(`${n.type} ${n.props.testID ?? ''}`);
      if (n.props.accessibilityRole === 'button' && (n.props.style?.minHeight ?? 48) < 44) problems.push(`small target ${n.props.testID}`);
    });
  return problems;
}

test('login screen', () => {
  installFakeApi();
  render(<App />);
  expect(unlabelled(screen.root)).toEqual([]);
});

test('applications screen in every state, with the pay form open', async () => {
  installFakeApi(['draft', 'submitted', 'payment_pending', 'paid', 'approved', 'issued', 'rejected', 'revoked']
    .map((state, i) => ({ business_name: `Duka ${i}`, state: state as any, rejection_reason: state === 'rejected' ? 'x' : null })));
  render(<ApplicationsScreen token="tok" owner="citizen@permitpass.test" onVerify={jest.fn()} outbox={freshOutbox()} />);
  fireEvent.press(await screen.findByRole('button', { name: 'Pay KES 2500 for Duka 1' }));
  expect(unlabelled(screen.root)).toEqual([]);
});

test('verify screen', () => {
  installFakeApi();
  render(<VerifyScreen />);
  expect(unlabelled(screen.root)).toEqual([]);
});

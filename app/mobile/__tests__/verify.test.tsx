import { fireEvent, render, screen } from '@testing-library/react-native';
import React from 'react';
import { VerifyScreen } from '../src/screens/VerifyScreen';
import { installFakeApi } from '../test-utils/fakeApi';

test('a genuine permit verifies without logging in', async () => {
  const api = installFakeApi();
  render(<VerifyScreen />);
  fireEvent.changeText(screen.getByLabelText('Certificate number'), 'PP-2026-ABCDEF12');
  fireEvent.changeText(screen.getByLabelText('Security code'), 'sig123');
  fireEvent.press(screen.getByRole('button', { name: 'Verify' }));
  expect(await screen.findByText('Valid permit')).toBeOnTheScreen();
  expect(screen.getByText('Business: Kibanda Coffee House')).toBeOnTheScreen();
  expect(api.calls[0].path).toBe('/verify/PP-2026-ABCDEF12?sig=sig123');
});

test('a forged code is not valid and reveals nothing', async () => {
  installFakeApi();
  render(<VerifyScreen />);
  fireEvent.changeText(screen.getByLabelText('Certificate number'), 'PP-2026-ABCDEF12');
  fireEvent.changeText(screen.getByLabelText('Security code'), 'forged');
  fireEvent.press(screen.getByRole('button', { name: 'Verify' }));
  expect(await screen.findByText('Not a valid PermitPass certificate')).toBeOnTheScreen();
  expect(screen.queryByText(/Business:/)).toBeNull();
});

test('opened from a certificate it checks straight away', async () => {
  installFakeApi();
  render(<VerifyScreen initial={{ number: 'PP-2026-ABCDEF12', sig: 'sig123' }} />);
  expect(await screen.findByText('Valid permit')).toBeOnTheScreen();
});

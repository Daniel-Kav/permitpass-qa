import { act, fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import React from 'react';
import { ApplicationsScreen } from '../src/screens/ApplicationsScreen';
import { installFakeApi } from '../test-utils/fakeApi';

const renderScreen = (onVerify = jest.fn()) => render(<ApplicationsScreen token="tok" onVerify={onVerify} />);

test('lists applications with a readable status', async () => {
  installFakeApi([{ business_name: 'Kibanda Coffee House', state: 'issued' }, { business_name: 'Thika Tyres', state: 'payment_pending' }]);
  renderScreen();
  expect(await screen.findByText('Kibanda Coffee House')).toBeOnTheScreen();
  expect(screen.getByLabelText('Status: Issued')).toBeOnTheScreen();
  expect(screen.getByLabelText('Status: Waiting for M-Pesa')).toBeOnTheScreen();
  expect(screen.getByText(/Check your phone/)).toBeOnTheScreen();
});

test('creating an application upper-cases the PIN', async () => {
  const api = installFakeApi();
  renderScreen();
  await screen.findByText('No applications yet.');
  fireEvent.changeText(screen.getByLabelText('Business name'), '  Mama Mboga  ');
  fireEvent.changeText(screen.getByLabelText('KRA PIN'), 'a123456789z');
  fireEvent.press(screen.getByRole('button', { name: 'Create application' }));
  expect(await screen.findByText('Application for Mama Mboga created as a draft.')).toBeOnTheScreen();
  expect(api.calls.find((c) => c.method === 'POST')!.body).toEqual({ business_name: 'Mama Mboga', kra_pin: 'A123456789Z' });
  expect(screen.getByLabelText('Status: Draft')).toBeOnTheScreen();
});

test.each([
  ['B123', 'kra_pin: String should match pattern'],
  ['A999999999Z', 'KRA PIN is not registered'],
])('a bad KRA PIN (%s) is explained', async (pin, message) => {
  installFakeApi();
  renderScreen();
  await screen.findByText('No applications yet.');
  fireEvent.changeText(screen.getByLabelText('Business name'), 'Ghost Ltd');
  fireEvent.changeText(screen.getByLabelText('KRA PIN'), pin);
  fireEvent.press(screen.getByRole('button', { name: 'Create application' }));
  expect(await screen.findByText(message)).toBeOnTheScreen();
});

test('submit then pay: phone spaces are removed and the app waits for M-Pesa', async () => {
  const api = installFakeApi([{ business_name: 'Duka', state: 'draft' }]);
  renderScreen();
  fireEvent.press(await screen.findByRole('button', { name: 'Submit Duka' }));
  fireEvent.press(await screen.findByRole('button', { name: 'Pay KES 2500 for Duka' }));
  fireEvent.changeText(screen.getByLabelText('M-Pesa phone number'), '0712 345 678');
  fireEvent.press(screen.getByRole('button', { name: 'Send payment request' }));
  expect(await screen.findByLabelText('Status: Waiting for M-Pesa')).toBeOnTheScreen();
  expect(api.calls.find((c) => c.path.endsWith('/pay'))!.body).toEqual({ phone: '0712345678' });
});

test('an invalid phone number is refused and nothing changes', async () => {
  installFakeApi([{ business_name: 'Duka', state: 'submitted' }]);
  renderScreen();
  fireEvent.press(await screen.findByRole('button', { name: 'Pay KES 2500 for Duka' }));
  fireEvent.changeText(screen.getByLabelText('M-Pesa phone number'), '0812345678');
  fireEvent.press(screen.getByRole('button', { name: 'Send payment request' }));
  expect(await screen.findByText('phone: String should match pattern')).toBeOnTheScreen();
  expect(screen.getByLabelText('Status: Submitted')).toBeOnTheScreen();
});

test('while waiting, the screen polls and announces the result', async () => {
  jest.useFakeTimers();
  const api = installFakeApi([{ business_name: 'Duka', state: 'submitted' }]);
  renderScreen();
  fireEvent.press(await screen.findByRole('button', { name: 'Pay KES 2500 for Duka' }));
  fireEvent.changeText(screen.getByLabelText('M-Pesa phone number'), '0712345678');
  fireEvent.press(screen.getByRole('button', { name: 'Send payment request' }));
  await screen.findByLabelText('Status: Waiting for M-Pesa');
  api.set('id-0', { state: 'paid' });                                  // M-Pesa callback arrives on the server
  await act(async () => { jest.advanceTimersByTime(2100); });
  expect(await screen.findByText('Payment received for Duka.')).toBeOnTheScreen();
  expect(screen.getByLabelText('Status: Paid')).toBeOnTheScreen();
  const lists = api.calls.filter((c) => c.path === '/applications?limit=100').length;
  await act(async () => { jest.advanceTimersByTime(6000); });
  expect(api.calls.filter((c) => c.path === '/applications?limit=100').length).toBe(lists);   // polling stopped
  jest.useRealTimers();
});

test('a failed payment shows its reason and offers Pay again', async () => {
  installFakeApi([{ business_name: 'Duka', state: 'submitted', payment_note: 'Payment failed: Request cancelled by user (M-Pesa code 1032)' }]);
  renderScreen();
  expect(await screen.findByText(/Request cancelled by user/)).toBeOnTheScreen();
  expect(screen.getByRole('button', { name: 'Pay KES 2500 for Duka' })).toBeOnTheScreen();
});

test('issued permits link to verification', async () => {
  installFakeApi([{ business_name: 'Kibanda', state: 'issued' }]);
  const onVerify = jest.fn();
  renderScreen(onVerify);
  fireEvent.press(await screen.findByRole('button', { name: 'View certificate for Kibanda' }));
  await waitFor(() => expect(onVerify).toHaveBeenCalledWith('PP-2026-ABCDEF12', 'sig123'));
});

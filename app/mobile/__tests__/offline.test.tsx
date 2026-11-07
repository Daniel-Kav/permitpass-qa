// Applying without a connection, then syncing exactly once (#48, built on #47).
import NetInfo from '@react-native-community/netinfo';
import { act, fireEvent, render, screen } from '@testing-library/react-native';
import React from 'react';
import { ApplicationsScreen } from '../src/screens/ApplicationsScreen';
import { installFakeApi } from '../test-utils/fakeApi';
import { freshOutbox, memoryStorage } from '../test-utils/memoryStorage';

const ME = 'citizen@permitpass.test';

function renderScreen(outbox = freshOutbox()) {
  render(<ApplicationsScreen token="tok" owner={ME} onVerify={jest.fn()} outbox={outbox} />);
  return outbox;
}

async function apply(name: string, pin = 'A123456789Z') {
  fireEvent.changeText(screen.getByLabelText('Business name'), name);
  fireEvent.changeText(screen.getByLabelText('KRA PIN'), pin);
  fireEvent.press(screen.getByRole('button', { name: 'Create application' }));
}

/** Simulate the phone's connection coming back (NetInfo's listener fires). */
async function backOnline() {
  const listener = (NetInfo.addEventListener as jest.Mock).mock.calls.at(-1)[0];
  await act(async () => { listener({ isConnected: true, isInternetReachable: true }); });
}

test('without a connection the application is saved on the phone, then sent when back online', async () => {
  const api = installFakeApi();
  renderScreen();
  await screen.findByText('No applications yet.');
  api.net.offline = true;
  await apply('Offline Duka');
  expect(await screen.findByText(/No connection\. Offline Duka is saved on this phone/)).toBeOnTheScreen();
  expect(screen.getByText('Saved on this phone')).toBeOnTheScreen();
  expect(screen.getByText(/Waiting for a connection/)).toBeOnTheScreen();

  api.net.offline = false;
  await backOnline();
  expect(await screen.findByText('Sent 1 saved application.')).toBeOnTheScreen();
  expect(screen.queryByText('Saved on this phone')).toBeNull();
  expect(screen.getByText('Offline Duka')).toBeOnTheScreen();
  expect(api.apps().filter((a) => a.business_name === 'Offline Duka')).toHaveLength(1);
});

test('the request arrived but the reply was lost: the retry creates nothing new', async () => {
  const api = installFakeApi();
  renderScreen();
  await screen.findByText('No applications yet.');
  api.net.loseNextResponse = true;                          // server creates it; the phone sees a network error
  await apply('Lost Reply Duka');
  await screen.findByText(/is saved on this phone/);
  await backOnline();
  await screen.findByText('Sent 1 saved application.');
  const creates = api.created();
  expect(creates).toHaveLength(2);                           // the original attempt and the retry...
  expect(creates[0].key).toBe(creates[1].key);               // ...with the SAME Idempotency-Key...
  expect(api.apps().filter((a) => a.business_name === 'Lost Reply Duka')).toHaveLength(1);   // ...so ONE application
});

test('a saved application the server refuses is shown with the reason and can be removed', async () => {
  const api = installFakeApi();
  renderScreen();
  await screen.findByText('No applications yet.');
  api.net.offline = true;
  await apply('Ghost Traders', 'A999999999Z');
  await screen.findByText(/is saved on this phone/);
  api.net.offline = false;
  await backOnline();
  expect(await screen.findByText('Not sent: KRA PIN is not registered')).toBeOnTheScreen();
  fireEvent.press(screen.getByRole('button', { name: 'Remove Ghost Traders' }));
  await act(async () => {});
  expect(screen.queryByText('Saved on this phone')).toBeNull();
});

test('saved applications are sent when the app starts again', async () => {
  const storage = memoryStorage();
  const before = freshOutbox(storage);
  await before.add(ME, 'Saved Yesterday', 'A123456789Z');
  const api = installFakeApi();
  renderScreen(freshOutbox(storage));                        // a new session reading the same phone storage
  expect(await screen.findByText('Sent 1 saved application.')).toBeOnTheScreen();
  expect(api.created()[0].body).toEqual({ business_name: 'Saved Yesterday', kra_pin: 'A123456789Z' });
});

test('while still offline it keeps retrying in the background', async () => {
  jest.useFakeTimers();
  const api = installFakeApi();
  renderScreen();
  await screen.findByText('No applications yet.');
  api.net.offline = true;
  await apply('Patient Duka');
  await screen.findByText(/is saved on this phone/);
  api.net.offline = false;                                    // connection back, but no NetInfo event this time
  await act(async () => { jest.advanceTimersByTime(16_000); });
  expect(await screen.findByText('Sent 1 saved application.')).toBeOnTheScreen();
  jest.useRealTimers();
});

test('online creates also send an Idempotency-Key', async () => {
  const api = installFakeApi();
  renderScreen();
  await screen.findByText('No applications yet.');
  await apply('Online Duka');
  await screen.findByText('Application for Online Duka created as a draft.');
  expect(api.created()[0].key).toMatch(/^key-\d{4}$|^[0-9a-f-]{36}$/);
});

import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import React from 'react';
import { LoginScreen } from '../src/screens/LoginScreen';
import { installFakeApi } from '../test-utils/fakeApi';

function logIn(email: string, password: string) {
  fireEvent.changeText(screen.getByLabelText('Email'), email);
  fireEvent.changeText(screen.getByLabelText('Password'), password);
  fireEvent.press(screen.getByRole('button', { name: 'Log in' }));
}

test('a citizen logs in', async () => {
  installFakeApi();
  const onLoggedIn = jest.fn();
  render(<LoginScreen onLoggedIn={onLoggedIn} />);
  logIn('citizen@permitpass.test', 'PermitPass!2026');
  await waitFor(() => expect(onLoggedIn).toHaveBeenCalledWith('tok'));
});

test('a wrong password shows the generic message', async () => {
  installFakeApi();
  render(<LoginScreen onLoggedIn={jest.fn()} />);
  logIn('citizen@permitpass.test', 'nope');
  expect(await screen.findByText('Incorrect email or password')).toBeOnTheScreen();
});

test('officers are sent to the web portal', async () => {
  installFakeApi();
  const onLoggedIn = jest.fn();
  render(<LoginScreen onLoggedIn={onLoggedIn} />);
  logIn('officer@permitpass.test', 'PermitPass!2026');
  expect(await screen.findByText(/Officers use the web portal/)).toBeOnTheScreen();
  expect(onLoggedIn).not.toHaveBeenCalled();
});

test('no network gives a clear message', async () => {
  global.fetch = jest.fn(async () => { throw new TypeError('Network request failed'); }) as any;
  render(<LoginScreen onLoggedIn={jest.fn()} />);
  logIn('citizen@permitpass.test', 'PermitPass!2026');
  expect(await screen.findByText(/Cannot reach PermitPass/)).toBeOnTheScreen();
});

test('the password field hides what is typed', () => {
  installFakeApi();
  render(<LoginScreen onLoggedIn={jest.fn()} />);
  expect(screen.getByLabelText('Password').props.secureTextEntry).toBe(true);
});

import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Crypto from 'expo-crypto';
import { Outbox } from './outbox';

export const newKey = () => Crypto.randomUUID();
export const outbox = new Outbox(AsyncStorage, newKey);

import * as SecureStore from 'expo-secure-store';

const TOKEN_KEY = 'driver_jwt';

export const getStoredToken = () => SecureStore.getItemAsync(TOKEN_KEY);

export const setStoredToken = (token: string) =>
  SecureStore.setItemAsync(TOKEN_KEY, token);

export const clearStoredToken = () => SecureStore.deleteItemAsync(TOKEN_KEY);

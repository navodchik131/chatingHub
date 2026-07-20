import * as SecureStore from 'expo-secure-store';

export const TOKEN_KEY = 'chating_token';

let memoryToken: string | null = null;

export async function getToken(): Promise<string | null> {
  if (memoryToken) return memoryToken;
  try {
    memoryToken = await SecureStore.getItemAsync(TOKEN_KEY);
    return memoryToken;
  } catch {
    return null;
  }
}

export async function setToken(token: string | null): Promise<void> {
  memoryToken = token;
  try {
    if (token) {
      await SecureStore.setItemAsync(TOKEN_KEY, token);
    } else {
      await SecureStore.deleteItemAsync(TOKEN_KEY);
    }
  } catch {
    /* ignore secure store errors in dev */
  }
}

export function getTokenSync(): string | null {
  return memoryToken;
}

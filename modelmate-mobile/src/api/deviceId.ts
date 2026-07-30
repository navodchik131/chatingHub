import * as SecureStore from 'expo-secure-store';

const DEVICE_ID_KEY = 'mm_device_id';
export const DEVICE_ID_HEADER = 'X-Device-Id';

function newDeviceId(): string {
  return `mm-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

export async function getOrCreateDeviceId(): Promise<string> {
  try {
    const existing = await SecureStore.getItemAsync(DEVICE_ID_KEY);
    if (existing) return existing;
    const id = newDeviceId();
    await SecureStore.setItemAsync(DEVICE_ID_KEY, id);
    return id;
  } catch {
    return newDeviceId();
  }
}

export async function appendDeviceIdHeader(headers: Headers): Promise<void> {
  headers.set(DEVICE_ID_HEADER, await getOrCreateDeviceId());
}

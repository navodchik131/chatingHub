export type PushSetupResult = {
  ok: boolean;
  permissionGranted: boolean;
  tokenRegistered: boolean;
  reason?: string;
  token?: string;
};

export function ensureNotificationHandler() {}

export async function ensureNotificationChannel() {}

export async function isPushPermissionGranted(): Promise<boolean> {
  return false;
}

export async function registerMobilePush(): Promise<PushSetupResult> {
  return {
    ok: false,
    permissionGranted: false,
    tokenRegistered: false,
    reason: 'Push недоступен в web preview.',
  };
}

export async function unregisterMobilePush(): Promise<void> {}

export async function syncMobilePushEnabled(enabled: boolean): Promise<PushSetupResult> {
  if (enabled) {
    return registerMobilePush();
  }
  return { ok: true, permissionGranted: false, tokenRegistered: false };
}

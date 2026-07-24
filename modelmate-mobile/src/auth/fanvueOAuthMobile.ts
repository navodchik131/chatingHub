import * as Linking from 'expo-linking';
import * as WebBrowser from 'expo-web-browser';
import { startFanvueOAuth } from '@/src/api/actions';
import { getSiteBaseUrl } from '@/src/api/config';

WebBrowser.maybeCompleteAuthSession();

export async function connectFanvue(studioModelId?: number): Promise<'connected' | 'error' | 'cancelled'> {
  const redirectUrl = Linking.createURL('oauth-return');
  const returnPage = `${getSiteBaseUrl()}/mobile-oauth-return.html?return=${encodeURIComponent(redirectUrl)}`;
  const data = await startFanvueOAuth(studioModelId, '__mobile__');
  const authorizeUrl = String(data.authorize_url || '').trim();
  if (!authorizeUrl) throw new Error('OAuth URL не получен');

  const result = await WebBrowser.openAuthSessionAsync(authorizeUrl, redirectUrl);
  if (result.type !== 'success' || !result.url) return 'cancelled';

  const parsed = Linking.parse(result.url);
  const q = parsed.queryParams ?? {};
  const pick = (key: string) => {
    const v = q[key];
    return typeof v === 'string' ? v : Array.isArray(v) ? v[0] : '';
  };
  const status = pick('status').trim();
  if (status === 'connected') return 'connected';
  return 'error';
}

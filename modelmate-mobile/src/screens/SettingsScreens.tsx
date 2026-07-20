import * as LocalAuthentication from 'expo-local-authentication';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { CheckRow } from '@/src/components/forms';
import { IcoFaceId, IcoFinger } from '@/src/components/Icons';
import { Card, ScreenScroll, TopBar } from '@/src/components/ui';
import { useAppSettings } from '@/src/context/AppSettingsContext';
import { AppLocale } from '@/src/i18n/prefs';
import { settingsLanguageRow } from '@/src/i18n/strings';
import { color, font } from '@/src/styles/tokens';

type Props = {
  onBack: () => void;
  onOpenLanguage: () => void;
  onOpenBiometric: () => void;
  onOpenPush: () => void;
};

export function SettingsMainScreen({ onBack, onOpenLanguage, onOpenBiometric, onOpenPush }: Props) {
  const { locale, t } = useAppSettings();

  return (
    <ScreenScroll>
      <TopBar title={t.settingsTitle} onBack={onBack} />
      <Card>
        <SettingsLink label={settingsLanguageRow(locale, t)} onPress={onOpenLanguage} />
        <SettingsLink label={t.settingsBiometric} onPress={onOpenBiometric} />
        <SettingsLink label={t.settingsPush} onPress={onOpenPush} last />
      </Card>
    </ScreenScroll>
  );
}

export function SettingsLanguageScreen({ onBack }: { onBack: () => void }) {
  const { locale, setLocale, t } = useAppSettings();

  const pick = (next: AppLocale) => {
    if (next !== locale) void setLocale(next);
  };

  return (
    <ScreenScroll>
      <TopBar title={t.settingsLanguage} onBack={onBack} />
      <Text style={styles.hint}>{t.settingsLanguageHint}</Text>
      <Card>
        <CheckRow
          label={t.settingsLanguageRu}
          checked={locale === 'ru'}
          onToggle={() => pick('ru')}
        />
        <CheckRow
          label={t.settingsLanguageEn}
          checked={locale === 'en'}
          onToggle={() => pick('en')}
        />
      </Card>
    </ScreenScroll>
  );
}

export function SettingsBiometricScreen({ onBack }: { onBack: () => void }) {
  const { biometricLock, setBiometricLock, t } = useAppSettings();
  const [available, setAvailable] = useState<boolean | null>(null);
  const isIOS = Platform.OS === 'ios';

  useEffect(() => {
    void (async () => {
      const hasHardware = await LocalAuthentication.hasHardwareAsync();
      const enrolled = hasHardware ? await LocalAuthentication.isEnrolledAsync() : false;
      setAvailable(hasHardware && enrolled);
    })();
  }, []);

  const testBiometric = async () => {
    await LocalAuthentication.authenticateAsync({
      promptMessage: t.settingsBiometric,
      cancelLabel: 'Cancel',
    });
  };

  return (
    <ScreenScroll>
      <TopBar title={t.settingsBiometric} onBack={onBack} />
      <Text style={styles.hint}>{t.settingsBiometricHint}</Text>
      {available === false ? (
        <Card>
          <Text style={styles.warn}>{t.settingsBiometricUnavailable}</Text>
        </Card>
      ) : (
        <Card>
          <CheckRow
            label={t.settingsBiometricLock}
            checked={biometricLock}
            onToggle={() => void setBiometricLock(!biometricLock)}
          />
          <Text style={styles.subHint}>{t.settingsBiometricLockHint}</Text>
          <Pressable style={styles.testBtn} onPress={() => void testBiometric()}>
            {isIOS ? <IcoFaceId size={18} stroke={color.lime} /> : <IcoFinger size={18} stroke={color.lime} />}
            <Text style={styles.testBtnText}>{t.settingsBiometricTest}</Text>
          </Pressable>
        </Card>
      )}
    </ScreenScroll>
  );
}

export function SettingsPushScreen({ onBack }: { onBack: () => void }) {
  const {
    pushEnabled,
    pushRegistered,
    pushError,
    pushBusy,
    setPushEnabled,
    syncPushRegistration,
    refreshPushStatus,
    t,
  } = useAppSettings();

  useEffect(() => {
    void refreshPushStatus();
  }, [refreshPushStatus]);

  const statusLine = pushEnabled
    ? pushRegistered
      ? 'Уведомления включены и зарегистрированы на сервере.'
      : 'Разрешение получено. Регистрация push-токена…'
    : 'Уведомления выключены.';

  return (
    <ScreenScroll>
      <TopBar title={t.settingsPush} onBack={onBack} />
      <Text style={styles.hint}>{t.settingsPushHint}</Text>
      <Card>
        <CheckRow
          label={pushEnabled ? t.settingsPushEnabled : t.settingsPushDisabled}
          checked={pushEnabled}
          onToggle={() => void setPushEnabled(!pushEnabled)}
        />
        {pushBusy ? (
          <View style={styles.busyRow}>
            <ActivityIndicator color={color.lime} size="small" />
            <Text style={styles.subHint}>Настраиваем уведомления…</Text>
          </View>
        ) : (
          <Text style={styles.subHint}>{statusLine}</Text>
        )}
        {pushEnabled && !pushRegistered && !pushBusy ? (
          <Pressable style={styles.testBtn} onPress={() => void syncPushRegistration()}>
            <Text style={styles.testBtnText}>Повторить регистрацию</Text>
          </Pressable>
        ) : null}
      </Card>
      {pushError ? (
        <Text style={styles.warn}>{pushError}</Text>
      ) : null}
    </ScreenScroll>
  );
}

function SettingsLink({ label, onPress, last }: { label: string; onPress: () => void; last?: boolean }) {
  return (
    <Pressable style={[styles.linkRow, last && styles.linkRowLast]} onPress={onPress}>
      <Text style={styles.linkLabel}>{label}</Text>
      <Text style={styles.linkChevron}>›</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  hint: { fontSize: 11.5, color: color.muted, paddingHorizontal: 4, paddingBottom: 10 },
  subHint: { fontSize: 10.5, color: color.dim, paddingTop: 4, paddingBottom: 8 },
  busyRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingTop: 4 },
  warn: { fontSize: 12, color: color.orange, lineHeight: 18, paddingHorizontal: 4, paddingTop: 8 },
  linkRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.06)',
  },
  linkRowLast: { borderBottomWidth: 0 },
  linkLabel: { flex: 1, fontFamily: font.bodySemi, fontSize: 13, color: color.text },
  linkChevron: { fontSize: 18, color: color.dim, paddingLeft: 8 },
  testBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginTop: 8,
    paddingVertical: 11,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: 'rgba(215,244,82,0.35)',
    backgroundColor: 'rgba(215,244,82,0.08)',
  },
  testBtnText: { fontFamily: font.bodyBold, fontSize: 12.5, color: color.lime },
});

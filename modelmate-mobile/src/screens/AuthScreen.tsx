import * as LocalAuthentication from 'expo-local-authentication';
import { useEffect, useState } from 'react';
import { Image, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { FieldLabel, TextField } from '@/src/components/forms';
import { IcoShield, IcoTelegram } from '@/src/components/Icons';
import { fetchTelegramLoginBotUsername } from '@/src/auth/telegramLoginMobile';
import { useAppData } from '@/src/context/AppDataProvider';
import { useNav } from '@/src/context/NavigationContext';
import { color, font } from '@/src/styles/tokens';

type AuthMode = 'login' | 'register';

export function AuthScreen() {
  const { authEmail, authPassword, patch, resetTo } = useNav();
  const { login, register, loginWithTelegram, busy, error, clearError } = useAppData();
  const [mode, setMode] = useState<AuthMode>('login');
  const [tgAvailable, setTgAvailable] = useState(false);

  useEffect(() => {
    void fetchTelegramLoginBotUsername().then((bot) => setTgAvailable(Boolean(bot)));
  }, []);

  const switchMode = (next: AuthMode) => {
    clearError();
    setMode(next);
  };

  const submitEmail = async () => {
    clearError();
    const email = authEmail.trim();
    if (!email) {
      return;
    }
    if (authPassword.length < 8) {
      return;
    }
    try {
      if (mode === 'login') {
        await login(email, authPassword);
      } else {
        await register(email, authPassword);
      }
      resetTo('overview');
    } catch {
      /* error in context */
    }
  };

  const submitTelegram = async () => {
    clearError();
    try {
      await loginWithTelegram();
      resetTo('overview');
    } catch {
      /* error in context */
    }
  };

  const loginWithBiometric = async () => {
    if (mode === 'register') return;
    const hasHardware = await LocalAuthentication.hasHardwareAsync();
    if (!hasHardware) {
      await submitEmail();
      return;
    }
    const enrolled = await LocalAuthentication.isEnrolledAsync();
    if (!enrolled) {
      await submitEmail();
      return;
    }
    const result = await LocalAuthentication.authenticateAsync({
      promptMessage: 'Войти в ModelMate',
      cancelLabel: 'Отмена',
    });
    if (result.success) await submitEmail();
  };

  const canSubmit = authEmail.trim().length > 0 && authPassword.length >= 8;
  const primaryLabel =
    mode === 'login' ? (busy ? 'Вход…' : 'Войти') : busy ? 'Регистрация…' : 'Зарегистрироваться';

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView
        contentContainerStyle={styles.scroll}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.logoBlock}>
          <View style={styles.logoWrap}>
            <Image source={require('@/assets/logo-m.jpeg')} style={styles.logo} />
          </View>
          <Text style={styles.brand}>ModelMate</Text>
        </View>

        <View style={styles.tabs}>
          <Pressable
            style={[styles.tab, mode === 'login' && styles.tabActive]}
            onPress={() => switchMode('login')}
            disabled={busy}
          >
            <Text style={[styles.tabText, mode === 'login' && styles.tabTextActive]}>Вход</Text>
          </Pressable>
          <Pressable
            style={[styles.tab, mode === 'register' && styles.tabActive]}
            onPress={() => switchMode('register')}
            disabled={busy}
          >
            <Text style={[styles.tabText, mode === 'register' && styles.tabTextActive]}>Регистрация</Text>
          </Pressable>
        </View>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        {tgAvailable ? (
          <>
            <Pressable style={styles.tgBtn} onPress={submitTelegram} disabled={busy}>
              <IcoTelegram size={17} stroke={color.blue} />
              <Text style={styles.tgText}>
                {mode === 'login' ? 'Войти через Telegram' : 'Зарегистрироваться через Telegram'}
              </Text>
            </Pressable>
            <Text style={styles.or}>или email</Text>
          </>
        ) : null}

        <View style={styles.form}>
          <View>
            <FieldLabel>EMAIL</FieldLabel>
            <TextField
              value={authEmail}
              onChangeText={(t) => patch({ authEmail: t })}
              keyboardType="email-address"
              autoCapitalize="none"
            />
          </View>
          <View>
            <FieldLabel>ПАРОЛЬ</FieldLabel>
            <TextField
              value={authPassword}
              onChangeText={(t) => patch({ authPassword: t })}
              secureTextEntry
            />
            {mode === 'register' ? (
              <Text style={styles.hint}>Минимум 8 символов</Text>
            ) : null}
          </View>
        </View>

        <Pressable
          style={[styles.loginBtn, (busy || !canSubmit) && styles.loginBtnDisabled]}
          onPress={submitEmail}
          disabled={busy || !canSubmit}
        >
          <Text style={styles.loginBtnText}>{primaryLabel}</Text>
        </Pressable>

        {mode === 'login' ? (
          <Pressable style={styles.bioBtn} onPress={loginWithBiometric} disabled={busy || !canSubmit}>
            <IcoShield size={17} stroke={color.lime} />
            <Text style={styles.bioText}>Войти по Face ID / отпечатку</Text>
          </Pressable>
        ) : null}

        <Pressable
          onPress={() => switchMode(mode === 'login' ? 'register' : 'login')}
          disabled={busy}
          style={styles.regPress}
        >
          <Text style={styles.reg}>
            {mode === 'login' ? 'Нет аккаунта? ' : 'Уже есть аккаунт? '}
            <Text style={styles.regLink}>{mode === 'login' ? 'Зарегистрироваться' : 'Войти'}</Text>
          </Text>
        </Pressable>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  scroll: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: 24,
    paddingVertical: 28,
    gap: 18,
  },
  logoBlock: { alignItems: 'center', gap: 10, marginBottom: 2 },
  logoWrap: {
    width: 56,
    height: 56,
    borderRadius: 16,
    overflow: 'hidden',
    shadowColor: '#C084FC',
    shadowOpacity: 0.35,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 6 },
    elevation: 8,
  },
  logo: { width: '100%', height: '100%' },
  brand: { fontFamily: font.displayBold, fontSize: 18, color: color.text },
  tabs: {
    flexDirection: 'row',
    gap: 8,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderRadius: 12,
    padding: 4,
  },
  tab: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 9,
    borderRadius: 9,
  },
  tabActive: { backgroundColor: 'rgba(255,255,255,0.08)' },
  tabText: { fontFamily: font.bodyBold, fontSize: 12.5, color: color.muted },
  tabTextActive: { color: color.text },
  error: { color: color.red, fontSize: 12, textAlign: 'center' },
  form: { gap: 10 },
  hint: { marginTop: 4, fontSize: 10.5, color: color.dim },
  loginBtn: {
    alignItems: 'center',
    paddingVertical: 13,
    borderRadius: 12,
    backgroundColor: color.lime,
  },
  loginBtnDisabled: { opacity: 0.45 },
  loginBtnText: { fontFamily: font.bodyExtra, fontSize: 13.5, color: color.limeText },
  or: { textAlign: 'center', fontSize: 11, color: color.dim },
  tgBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 9,
    paddingVertical: 12,
    borderRadius: 12,
    backgroundColor: 'rgba(56,189,248,0.12)',
    borderWidth: 1,
    borderColor: 'rgba(56,189,248,0.35)',
  },
  tgText: { fontFamily: font.bodyBold, fontSize: 12.5, color: color.blue },
  bioBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 9,
    paddingVertical: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.14)',
  },
  bioText: { fontFamily: font.bodyBold, fontSize: 12.5, color: color.text },
  regPress: { marginTop: 2 },
  reg: { textAlign: 'center', fontSize: 11.5, color: color.muted },
  regLink: { color: color.lime, fontWeight: '700' },
});

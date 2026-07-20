import * as LocalAuthentication from 'expo-local-authentication';
import { Image, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { FieldLabel, TextField } from '@/src/components/forms';
import { IcoShield, IcoTelegram } from '@/src/components/Icons';
import { useAppData } from '@/src/context/AppDataProvider';
import { useNav } from '@/src/context/NavigationContext';
import { color, font } from '@/src/styles/tokens';

export function AuthScreen() {
  const { authEmail, authPassword, patch, resetTo } = useNav();
  const { login, busy, error, clearError } = useAppData();

  const enterApp = async () => {
    clearError();
    try {
      await login(authEmail, authPassword);
      resetTo('overview');
    } catch {
      /* error in context */
    }
  };

  const loginWithBiometric = async () => {
    const hasHardware = await LocalAuthentication.hasHardwareAsync();
    if (!hasHardware) {
      await enterApp();
      return;
    }
    const enrolled = await LocalAuthentication.isEnrolledAsync();
    if (!enrolled) {
      await enterApp();
      return;
    }
    const result = await LocalAuthentication.authenticateAsync({
      promptMessage: 'Войти в ModelMate',
      cancelLabel: 'Отмена',
    });
    if (result.success) await enterApp();
  };

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

        {error ? <Text style={styles.error}>{error}</Text> : null}

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
          </View>
        </View>

        <Pressable style={[styles.loginBtn, busy && styles.loginBtnDisabled]} onPress={enterApp} disabled={busy}>
          <Text style={styles.loginBtnText}>{busy ? 'Вход…' : 'Войти'}</Text>
        </Pressable>

        <Text style={styles.or}>или</Text>

        <Pressable style={styles.tgBtn} onPress={enterApp} disabled={busy}>
          <IcoTelegram size={17} stroke={color.blue} />
          <Text style={styles.tgText}>Войти через Telegram</Text>
        </Pressable>

        <Pressable style={styles.bioBtn} onPress={loginWithBiometric} disabled={busy}>
          <IcoShield size={17} stroke={color.lime} />
          <Text style={styles.bioText}>Войти по Face ID / отпечатку</Text>
        </Pressable>

        <Text style={styles.reg}>
          Нет аккаунта?{' '}
          <Text style={styles.regLink}>Зарегистрироваться</Text>
        </Text>
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
    gap: 22,
  },
  logoBlock: { alignItems: 'center', gap: 10, marginBottom: 6 },
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
  error: { color: color.red, fontSize: 12, textAlign: 'center' },
  form: { gap: 10 },
  loginBtn: {
    alignItems: 'center',
    paddingVertical: 13,
    borderRadius: 12,
    backgroundColor: color.lime,
  },
  loginBtnDisabled: { opacity: 0.6 },
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
  reg: { textAlign: 'center', fontSize: 11.5, color: color.muted, marginTop: 4 },
  regLink: { color: color.lime, fontWeight: '700' },
});

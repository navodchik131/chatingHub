import 'react-native-gesture-handler';
import {
  JetBrainsMono_500Medium,
  JetBrainsMono_700Bold,
} from '@expo-google-fonts/jetbrains-mono';
import {
  Manrope_400Regular,
  Manrope_500Medium,
  Manrope_600SemiBold,
  Manrope_700Bold,
  Manrope_800ExtraBold,
} from '@expo-google-fonts/manrope';
import {
  Unbounded_600SemiBold,
  Unbounded_700Bold,
} from '@expo-google-fonts/unbounded';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { AppProvider } from '@/src/context/AppDataProvider';
import { AppSettingsProvider } from '@/src/context/AppSettingsContext';
import { MobilePushAuthSync } from '@/src/push/MobilePushAuthSync';
import { LocaleAccountSync } from '@/src/components/LocaleAccountSync';
import { MobileStartupErrorBoundary } from '@/src/components/MobileStartupErrorBoundary';
import { ensureNotificationHandler } from '@/src/push/notifications';
import { color } from '@/src/styles/tokens';

export { ErrorBoundary } from 'expo-router';

SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const [loaded, error] = useFonts({
    Manrope_400Regular,
    Manrope_500Medium,
    Manrope_600SemiBold,
    Manrope_700Bold,
    Manrope_800ExtraBold,
    Unbounded_600SemiBold,
    Unbounded_700Bold,
    JetBrainsMono_500Medium,
    JetBrainsMono_700Bold,
  });

  useEffect(() => {
    if (error) console.error('[ModelMate] font load failed', error);
  }, [error]);

  useEffect(() => {
    if (loaded || error) SplashScreen.hideAsync();
  }, [loaded, error]);

  useEffect(() => {
    ensureNotificationHandler();
  }, []);

  if (!loaded && !error) return null;

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <AppSettingsProvider>
          <MobileStartupErrorBoundary>
            <AppProvider>
              <LocaleAccountSync />
              <MobilePushAuthSync />
              <View style={{ flex: 1, backgroundColor: color.bg }}>
                <StatusBar style="light" />
                <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: color.bg } }}>
                  <Stack.Screen name="index" />
                  <Stack.Screen name="system/lock" />
                  <Stack.Screen name="system/biometric" />
                </Stack>
              </View>
            </AppProvider>
          </MobileStartupErrorBoundary>
        </AppSettingsProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

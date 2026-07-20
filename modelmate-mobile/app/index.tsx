import { AppState, BackHandler, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { BiometricUnlock } from '@/src/components/BiometricUnlock';
import { AppShell } from '@/src/components/TabBar';
import { SwipeBackWrapper } from '@/src/components/SwipeBackWrapper';
import { useAppData } from '@/src/context/AppDataProvider';
import { useAppSettings } from '@/src/context/AppSettingsContext';
import { NavigationProvider, useNav } from '@/src/context/NavigationContext';
import { hideTabBar } from '@/src/navigation/types';
import { ScreenRouter } from '@/src/screens/ScreenRouter';
import { SplashScreen } from '@/src/screens/SplashScreen';
import { color } from '@/src/styles/tokens';
import { useEffect, useRef, useState } from 'react';

function MainApp() {
  const app = useAppData();
  const { biometricLock } = useAppSettings();
  const { stack, cur, resetTo, patch, pop } = useNav();
  const canGoBack = stack.length > 1 && cur !== 'auth' && cur !== 'splash';
  const [locked, setLocked] = useState(false);
  const appState = useRef(AppState.currentState);

  useEffect(() => {
    if (!app.ready) return;
    if (cur === 'splash') return;
    if (app.authenticated && cur === 'auth') resetTo('overview');
    if (!app.authenticated && cur !== 'auth' && cur !== 'splash') {
      void app.logout().then(() => patch({ stack: ['auth'] }));
    }
  }, [app.ready, app.authenticated, cur, resetTo, patch, app]);

  useEffect(() => {
    if (cur === 'admin' || cur.startsWith('admin-')) {
      void app.loadAdmin();
    }
    if (cur === 'admin-users') {
      void app.searchAdminUsers('');
    }
  }, [cur, app]);

  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (canGoBack) {
        pop();
        return true;
      }
      return false;
    });
    return () => sub.remove();
  }, [canGoBack, pop]);

  useEffect(() => {
    const sub = AppState.addEventListener('change', (next) => {
      if (
        appState.current.match(/inactive|background/) &&
        next === 'active' &&
        biometricLock &&
        app.authenticated
      ) {
        setLocked(true);
      }
      appState.current = next;
    });
    return () => sub.remove();
  }, [biometricLock, app.authenticated]);

  if (cur === 'splash') {
    return (
      <SplashScreen
        ready={app.ready}
        onContinue={() => {
          if (!app.ready) return;
          if (app.authenticated) resetTo('overview');
          else patch({ stack: ['auth'] });
        }}
      />
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={['top', 'left', 'right']}>
      <AppShell showTabBar={!hideTabBar(stack)}>
        <SwipeBackWrapper enabled={canGoBack} onBack={pop}>
          <ScreenRouter />
        </SwipeBackWrapper>
      </AppShell>
      {locked && biometricLock && app.authenticated ? (
        <BiometricUnlock onUnlock={() => setLocked(false)} />
      ) : null}
    </SafeAreaView>
  );
}

export default function Index() {
  return (
    <NavigationProvider>
      <MainApp />
    </NavigationProvider>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: color.bg },
});

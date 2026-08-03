import { AppState, ActivityIndicator, BackHandler, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { BiometricUnlock } from '@/src/components/BiometricUnlock';
import { AppShell } from '@/src/components/TabBar';
import { SwipeBackWrapper } from '@/src/components/SwipeBackWrapper';
import { MobileStartupErrorBoundary } from '@/src/components/MobileStartupErrorBoundary';
import { useAppData } from '@/src/context/AppDataProvider';
import { useAppSettings } from '@/src/context/AppSettingsContext';
import { NavigationProvider, useNav } from '@/src/context/NavigationContext';
import { hideTabBar } from '@/src/navigation/types';
import { SplashScreen } from '@/src/screens/SplashScreen';
import { MobilePushNavigation } from '@/src/push/MobilePushNavigation';
import { color } from '@/src/styles/tokens';
import { useCallback, useEffect, useRef, useState, type ComponentType } from 'react';

type ScreenRouterComponent = ComponentType;

function ScreenRouterFallback() {
  return (
    <View style={styles.loader}>
      <ActivityIndicator size="large" color={color.lime} />
    </View>
  );
}

function MainApp() {
  const app = useAppData();
  const { biometricLock } = useAppSettings();
  const { stack, cur, resetTo, patch, pop } = useNav();
  const [ScreenRouter, setScreenRouter] = useState<ScreenRouterComponent | null>(null);
  const canGoBack = stack.length > 1 && cur !== 'auth' && cur !== 'splash';
  const canReturnToOverview = cur !== 'overview' && cur !== 'auth' && cur !== 'splash';

  useEffect(() => {
    if (cur === 'splash' || ScreenRouter) return;
    let cancelled = false;
    void import('@/src/screens/ScreenRouter').then((mod) => {
      if (!cancelled) setScreenRouter(() => mod.ScreenRouter);
    });
    return () => {
      cancelled = true;
    };
  }, [cur, ScreenRouter]);

  const handleBack = useCallback(() => {
    if (canGoBack) {
      pop();
      return true;
    }
    if (canReturnToOverview) {
      resetTo('overview');
      return true;
    }
    return false;
  }, [canGoBack, canReturnToOverview, pop, resetTo]);
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
    const sub = BackHandler.addEventListener('hardwareBackPress', handleBack);
    return () => sub.remove();
  }, [handleBack]);

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
      <MobilePushNavigation />
      <AppShell showTabBar={!hideTabBar(stack)}>
        <SwipeBackWrapper enabled={canGoBack || canReturnToOverview} onBack={handleBack}>
          <MobileStartupErrorBoundary>
            {ScreenRouter ? <ScreenRouter /> : <ScreenRouterFallback />}
          </MobileStartupErrorBoundary>
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
  loader: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: color.bg },
});

import { Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { font } from '@/src/styles/tokens';

const logo = require('../../assets/logo-m.jpeg');

export function SplashScreen({
  ready,
  onContinue,
}: {
  ready: boolean;
  onContinue: () => void;
}) {
  return (
    <Pressable style={styles.root} onPress={ready ? onContinue : undefined}>
      <View style={styles.logoWrap}>
        <Image source={logo} style={styles.logo} resizeMode="cover" />
      </View>
      <Text style={styles.title}>ModelMate</Text>
      <Text style={styles.subtitle}>
        AI OFM · единственное приложение для ведения моделей
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#fff',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 14,
    paddingHorizontal: 40,
  },
  logoWrap: {
    width: 120,
    height: 120,
    borderRadius: 28,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOpacity: 0.15,
    shadowRadius: 30,
    shadowOffset: { width: 0, height: 10 },
    elevation: 8,
  },
  logo: { width: '100%', height: '100%' },
  title: {
    fontFamily: font.displayBold,
    fontSize: 20,
    color: '#111',
  },
  subtitle: {
    fontFamily: font.mono,
    fontSize: 10.5,
    letterSpacing: 0.6,
    color: '#8a8f95',
    textAlign: 'center',
    lineHeight: 16,
  },
});

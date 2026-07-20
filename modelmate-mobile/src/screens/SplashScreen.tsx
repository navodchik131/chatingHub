import { useCallback, useEffect, useRef, useState } from 'react';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { font } from '@/src/styles/tokens';

const logo = require('../../assets/logo-m.jpeg');
const TAGLINE = 'AI OFM · лучшее приложение для ai креаторов';

export function SplashScreen({
  ready,
  onContinue,
}: {
  ready: boolean;
  onContinue: () => void;
  /** @deprecated kept for API compat */
  onSkip?: () => void;
}) {
  const [text, setText] = useState('');
  const [typingDone, setTypingDone] = useState(false);
  const continuedRef = useRef(false);

  const finish = useCallback(() => {
    if (continuedRef.current || !ready) return;
    continuedRef.current = true;
    onContinue();
  }, [ready, onContinue]);

  useEffect(() => {
    let i = 0;
    const timer = setInterval(() => {
      i += 1;
      setText(TAGLINE.slice(0, i));
      if (i >= TAGLINE.length) {
        clearInterval(timer);
        setTypingDone(true);
      }
    }, 34);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!ready || !typingDone) return;
    const timer = setTimeout(finish, 500);
    return () => clearTimeout(timer);
  }, [ready, typingDone, finish]);

  useEffect(() => {
    if (!ready) return;
    const safety = setTimeout(finish, 4500);
    return () => clearTimeout(safety);
  }, [ready, finish]);

  return (
    <Pressable style={styles.root} onPress={finish}>
      <View style={styles.logoWrap}>
        <Image source={logo} style={styles.logo} resizeMode="cover" />
      </View>
      <Text style={styles.title}>ModelMate</Text>
      <Text style={styles.subtitle}>
        {text}
        {!typingDone ? <Text style={styles.cursor}>|</Text> : null}
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
    minHeight: 32,
  },
  cursor: {
    color: '#8a8f95',
    opacity: 0.85,
  },
});

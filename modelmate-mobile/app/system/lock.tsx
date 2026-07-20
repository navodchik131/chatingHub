import { LinearGradient } from 'expo-linear-gradient';
import { router } from 'expo-router';
import { Image, Platform, Pressable, SafeAreaView, StyleSheet, Text, View } from 'react-native';
import { color, font } from '@/src/styles/tokens';

export default function LockScreen() {
  const notification =
    Platform.OS === 'ios' ? 'Mia: по милости 💬' : 'Новый донат — 100 ₽ получен';

  return (
    <Pressable style={styles.root} onPress={() => router.push('/system/biometric')}>
      <LinearGradient colors={['#1a1c26', '#08090b']} style={styles.gradient}>
        <SafeAreaView style={styles.safe}>
          <Text style={styles.clock}>9:41</Text>
          <Text style={styles.date}>Суббота, 19 июля</Text>

          <View style={styles.notif}>
            <Image source={require('@/assets/logo-m.jpeg')} style={styles.logo} />
            <View style={styles.notifText}>
              <View style={styles.notifHead}>
                <Text style={styles.notifTitle}>ModelMate</Text>
                <Text style={styles.notifTime}>сейчас</Text>
              </View>
              <Text style={styles.notifBody}>{notification}</Text>
            </View>
          </View>

          <Text style={styles.hint}>Нажмите, чтобы открыть биометрию</Text>
        </SafeAreaView>
      </LinearGradient>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  gradient: { flex: 1 },
  safe: { flex: 1, alignItems: 'center', paddingTop: 70 },
  clock: { fontFamily: font.display, fontSize: 56, color: color.text },
  date: { fontSize: 13, color: color.muted, marginBottom: 36, marginTop: 4 },
  notif: {
    width: '86%',
    backgroundColor: 'rgba(30,32,38,0.85)',
    borderRadius: 16,
    paddingHorizontal: 14,
    paddingVertical: 12,
    flexDirection: 'row',
    gap: 10,
    alignItems: 'center',
  },
  logo: { width: 34, height: 34, borderRadius: 9 },
  notifText: { flex: 1, minWidth: 0 },
  notifHead: { flexDirection: 'row', justifyContent: 'space-between' },
  notifTitle: { fontFamily: font.bodyExtra, fontSize: 12.5, color: color.text },
  notifTime: { fontSize: 10, color: color.muted },
  notifBody: { fontSize: 12, color: '#E5E7EA', marginTop: 2 },
  hint: { marginTop: 40, fontSize: 12, color: color.dim },
});

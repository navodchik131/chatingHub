import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { color, font } from '@/src/styles/tokens';

export const EMOJI_CHOICES = [
  '😊', '😍', '🥰', '😘', '💕', '🔥', '😂', '😅', '🙈', '😉',
  '💋', '🌹', '✨', '👀', '🥂', '💫', '😎', '🤗', '😏', '💯',
  '👍', '❤️', '😮', '😢', '🎉', '🙏', '💪', '😴', '🤔', '😭',
];

type EmojiPickerSheetProps = {
  visible: boolean;
  lang?: 'ru' | 'en';
  onClose: () => void;
  onPick: (emoji: string) => void;
};

export function EmojiPickerSheet({ visible, lang = 'ru', onClose, onPick }: EmojiPickerSheetProps) {
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.overlay} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <View style={styles.head}>
            <Text style={styles.title}>{lang === 'ru' ? 'Эмодзи' : 'Emoji'}</Text>
            <Pressable onPress={onClose} hitSlop={8}>
              <Text style={styles.close}>✕</Text>
            </Pressable>
          </View>
          <ScrollView contentContainerStyle={styles.grid} keyboardShouldPersistTaps="handled">
            {EMOJI_CHOICES.map((emoji) => (
              <Pressable
                key={emoji}
                style={styles.cell}
                onPress={() => {
                  onPick(emoji);
                  onClose();
                }}
              >
                <Text style={styles.emoji}>{emoji}</Text>
              </Pressable>
            ))}
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: '#17181C',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 28,
    maxHeight: '52%',
  },
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },
  title: { fontFamily: font.bodyExtra, fontSize: 16, color: color.text },
  close: { color: color.muted, fontSize: 18 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, paddingBottom: 8 },
  cell: {
    width: '18%',
    aspectRatio: 1,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 12,
    backgroundColor: 'rgba(255,255,255,0.04)',
  },
  emoji: { fontSize: 26 },
});

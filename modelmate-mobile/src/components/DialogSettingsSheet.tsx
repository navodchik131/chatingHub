import { Modal, Pressable, StyleSheet, Switch, Text, View } from 'react-native';
import { outboundLangOptions, replyLangDisplay, type ConversationSettingsPatch } from '@/src/api/dialogSettings';
import { color, font } from '@/src/styles/tokens';
import type { ConversationOut } from '@/src/api/types';

type DialogSettingsSheetProps = {
  visible: boolean;
  conv: ConversationOut | null;
  lang: 'ru' | 'en';
  onClose: () => void;
  onPatch: (patch: ConversationSettingsPatch) => void;
};

const MODE_OPTIONS = [
  { id: 'off' as const, labelKey: 'dlgAutoOff' as const },
  { id: 'semi_auto' as const, labelKey: 'dlgAutoSemi' as const },
  { id: 'auto' as const, labelKey: 'dlgAutoFull' as const },
];

const COPY = {
  ru: {
    title: 'Настройки диалога',
    autoMode: 'РЕЖИМ АВТООТВЕТЧИКА',
    dlgAutoOff: 'Отключён — отвечаете только вы',
    dlgAutoSemi: 'Полуавтомат — AI предлагает ответ',
    dlgAutoFull: 'Автоматически — AI отвечает сам',
    translateToggle: 'Переводить сообщения фану',
    translateLang: 'ЯЗЫК ПЕРЕВОДА',
    translateHint: 'По умолчанию язык определяется автоматически по сообщениям фана. Можно закрепить вручную.',
  },
  en: {
    title: 'Dialog settings',
    autoMode: 'AUTO-REPLY MODE',
    dlgAutoOff: 'Off — you reply manually',
    dlgAutoSemi: 'Semi-auto — AI suggests replies',
    dlgAutoFull: 'Automatic — AI replies on its own',
    translateToggle: 'Translate messages for the fan',
    translateLang: 'TRANSLATION LANGUAGE',
    translateHint: 'By default the language is detected from the fan’s messages. You can pin it manually.',
  },
};

export function DialogSettingsSheet({ visible, conv, lang, onClose, onPatch }: DialogSettingsSheetProps) {
  if (!conv) return null;
  const t = COPY[lang];
  const translateOn = !conv.auto_translate_disabled;
  const companionMode = conv.companion_mode_override ?? conv.effective_companion_mode ?? 'off';
  const outboundLangValue = (conv.outbound_lang || '').trim()
    ? String(conv.outbound_lang).trim().toLowerCase().replace('*', '')
    : 'auto';
  const langOptions = outboundLangOptions(lang, conv.user_lang);

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.overlay} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <View style={styles.head}>
            <Text style={styles.title}>{t.title}</Text>
            <Pressable onPress={onClose} hitSlop={8}>
              <Text style={styles.close}>✕</Text>
            </Pressable>
          </View>

          <Text style={styles.sectionLabel}>{t.autoMode}</Text>
          {MODE_OPTIONS.map((mo) => {
            const active = companionMode === mo.id;
            return (
              <Pressable
                key={mo.id}
                style={[styles.modeRow, active && styles.modeRowActive]}
                onPress={() => onPatch({ companion_mode_override: mo.id })}
              >
                <Text style={[styles.modeText, active && styles.modeTextActive]}>{t[mo.labelKey]}</Text>
                <View style={[styles.dot, active && styles.dotActive]} />
              </Pressable>
            );
          })}

          <View style={styles.divider} />

          <View style={styles.switchRow}>
            <Text style={styles.switchLabel}>{t.translateToggle}</Text>
            <Switch
              value={translateOn}
              onValueChange={(v) => onPatch({ auto_translate_disabled: !v })}
              trackColor={{ false: 'rgba(255,255,255,0.14)', true: color.lime }}
              thumbColor="#fff"
            />
          </View>

          {translateOn ? (
            <View style={styles.langBlock}>
              <Text style={styles.sectionLabel}>{t.translateLang}</Text>
              <Text style={styles.langCurrent}>{replyLangDisplay(conv, lang)}</Text>
              <View style={styles.langGrid}>
                {langOptions.map((opt) => {
                  const active = outboundLangValue === opt.value;
                  return (
                    <Pressable
                      key={opt.value}
                      style={[styles.langChip, active && styles.langChipActive]}
                      onPress={() => onPatch({ outbound_lang: opt.value === 'auto' ? null : opt.value })}
                    >
                      <Text style={[styles.langChipText, active && styles.langChipTextActive]}>{opt.label}</Text>
                    </Pressable>
                  );
                })}
              </View>
              <Text style={styles.hint}>{t.translateHint}</Text>
            </View>
          ) : null}
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: '#17181C',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 28,
    gap: 10,
  },
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 },
  title: { fontFamily: font.bodyExtra, fontSize: 16, color: color.text },
  close: { color: color.muted, fontSize: 18 },
  sectionLabel: {
    fontFamily: font.mono,
    fontSize: 10,
    letterSpacing: 1.2,
    color: color.dim,
    marginTop: 4,
    marginBottom: 2,
  },
  modeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 10,
    paddingHorizontal: 10,
    borderRadius: 9,
  },
  modeRowActive: { backgroundColor: 'rgba(215,244,82,0.1)' },
  modeText: { flex: 1, fontSize: 13, color: color.muted, paddingRight: 8 },
  modeTextActive: { color: color.lime, fontFamily: font.bodySemi, fontWeight: '700' },
  dot: { width: 7, height: 7, borderRadius: 4, backgroundColor: 'transparent' },
  dotActive: { backgroundColor: color.lime },
  divider: { height: 1, backgroundColor: 'rgba(255,255,255,0.08)', marginVertical: 4 },
  switchRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  switchLabel: { flex: 1, fontSize: 13, fontFamily: font.bodySemi, fontWeight: '600', color: color.text },
  langBlock: { gap: 8 },
  langCurrent: { fontSize: 12, color: color.muted },
  langGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  langChip: {
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.12)',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 7,
  },
  langChipActive: { borderColor: color.lime, backgroundColor: 'rgba(215,244,82,0.1)' },
  langChipText: { fontSize: 12, color: color.muted },
  langChipTextActive: { color: color.lime, fontWeight: '700' },
  hint: { fontSize: 11, lineHeight: 16, color: color.dim },
});

import { LinearGradient } from 'expo-linear-gradient';
import { ReactNode } from 'react';
import {
  ActivityIndicator,
  Linking,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInputProps,
  View,
  TextStyle,
} from 'react-native';
import { TextInput } from 'react-native-gesture-handler';
import { RemoteImage } from '@/src/components/RemoteImage';
import { IcoUpload } from '@/src/components/Icons';
import { color, font, gradients } from '@/src/styles/tokens';

export function FieldLabel({ children }: { children: string }) {
  return <Text style={styles.fieldLabel}>{children}</Text>;
}

type InputProps = {
  value: string;
  onChangeText?: (text: string) => void;
  onBlur?: TextInputProps['onBlur'];
  placeholder?: string;
  secureTextEntry?: boolean;
  keyboardType?: TextInputProps['keyboardType'];
  autoCapitalize?: TextInputProps['autoCapitalize'];
  style?: TextStyle;
  flex?: number;
};

export function TextField({
  value,
  onChangeText,
  onBlur,
  placeholder,
  secureTextEntry,
  keyboardType,
  autoCapitalize = 'none',
  style,
  flex,
}: InputProps) {
  return (
    <TextInput
      value={value}
      onChangeText={onChangeText}
      onBlur={onBlur}
      placeholder={placeholder}
      placeholderTextColor={color.dim}
      secureTextEntry={secureTextEntry}
      keyboardType={keyboardType}
      autoCapitalize={autoCapitalize}
      autoCorrect={false}
      spellCheck={false}
      autoComplete="off"
      importantForAutofill="no"
      keyboardAppearance="dark"
      selectionColor={color.lime}
      style={[styles.textField, flex ? { flex } : null, style]}
    />
  );
}

export function TextAreaField({
  value,
  onChangeText,
  placeholder,
  rows = 3,
}: {
  value: string;
  onChangeText?: (text: string) => void;
  placeholder?: string;
  rows?: number;
}) {
  return (
    <TextInput
      value={value}
      onChangeText={onChangeText}
      placeholder={placeholder}
      placeholderTextColor={color.dim}
      multiline
      numberOfLines={rows}
      textAlignVertical="top"
      autoCapitalize="sentences"
      autoCorrect={false}
      spellCheck={false}
      autoComplete="off"
      importantForAutofill="no"
      keyboardAppearance="dark"
      selectionColor={color.lime}
      style={[styles.textField, styles.textArea, { minHeight: rows * 20 + 16 }]}
    />
  );
}

export function SelectChip({
  label,
  active,
  onPress,
}: {
  label: string;
  active?: boolean;
  onPress?: () => void;
}) {
  return (
    <Pressable onPress={onPress} style={[styles.chip, active && styles.chipActive]}>
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </Pressable>
  );
}

export function ChipPicker({
  items,
  value,
  onChange,
}: {
  items: string[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <View style={styles.chipRow}>
      {items.map((item) => (
        <SelectChip key={item} label={item} active={value === item} onPress={() => onChange(item)} />
      ))}
    </View>
  );
}

export function ChipRowInteractive({
  items,
  activeIndex = 0,
  onSelect,
}: {
  items: string[];
  activeIndex?: number;
  onSelect?: (index: number) => void;
}) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
      {items.map((item, i) => (
        <SelectChip key={item} label={item} active={i === activeIndex} onPress={() => onSelect?.(i)} />
      ))}
    </ScrollView>
  );
}

export function NumberChipPicker({
  items,
  value,
  onChange,
  suffix = '',
}: {
  items: number[];
  value: number;
  onChange: (v: number) => void;
  suffix?: string;
}) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
      {items.map((n) => (
        <SelectChip
          key={n}
          label={`${n}${suffix}`}
          active={value === n}
          onPress={() => onChange(n)}
        />
      ))}
    </ScrollView>
  );
}

export function TabChip({
  label,
  active,
  onPress,
}: {
  label: string;
  active?: boolean;
  onPress?: () => void;
}) {
  return (
    <Pressable onPress={onPress} style={[styles.tabChip, active && styles.tabChipActive]}>
      <Text style={[styles.tabChipText, active && styles.tabChipTextActive]}>{label}</Text>
    </Pressable>
  );
}

export function SegmentedToggle({
  left,
  right,
  activeLeft = true,
  onLeft,
  onRight,
}: {
  left: string;
  right: string;
  activeLeft?: boolean;
  onLeft?: () => void;
  onRight?: () => void;
}) {
  return (
    <View style={styles.segmented}>
      <Pressable onPress={onLeft} style={[styles.segItem, activeLeft && styles.segItemActive]}>
        <Text style={[styles.segText, activeLeft && styles.segTextActive]}>{left}</Text>
      </Pressable>
      <Pressable onPress={onRight} style={[styles.segItem, !activeLeft && styles.segItemActive]}>
        <Text style={[styles.segText, !activeLeft && styles.segTextActive]}>{right}</Text>
      </Pressable>
    </View>
  );
}

export function DropSlot({ label, onPress }: { label: string; onPress?: () => void }) {
  return (
    <Pressable style={styles.dropSlot} onPress={onPress}>
      <IcoUpload size={16} stroke={color.dim} />
      <Text style={styles.dropLabel}>{label}</Text>
    </Pressable>
  );
}

export function DropSlotWide({ label, onPress }: { label: string; onPress?: () => void }) {
  return (
    <Pressable style={styles.dropSlotWide} onPress={onPress}>
      <IcoUpload size={17} stroke={color.dim} />
      <Text style={styles.dropLabelWide}>{label}</Text>
    </Pressable>
  );
}

export function LimeButton({
  title,
  cost,
  onPress,
  icon,
}: {
  title: string;
  cost?: string;
  onPress?: () => void;
  icon?: ReactNode;
}) {
  return (
    <Pressable style={styles.limeBtn} onPress={onPress}>
      {icon}
      <Text style={styles.limeBtnTitle}>{title}</Text>
      {cost ? <Text style={styles.limeBtnCost}>{cost}</Text> : null}
    </Pressable>
  );
}

export function GhostButton({ title, onPress }: { title: string; onPress?: () => void }) {
  return (
    <Pressable style={styles.ghostBtn} onPress={onPress}>
      <Text style={styles.ghostBtnText}>{title}</Text>
    </Pressable>
  );
}

export function DashedAddButton({ title, onPress }: { title: string; onPress?: () => void }) {
  return (
    <Pressable style={styles.dashedBtn} onPress={onPress}>
      <Text style={styles.dashedBtnText}>{title}</Text>
    </Pressable>
  );
}

export function GenLoadingCard({ title, sub }: { title: string; sub: string }) {
  return (
    <View style={styles.genLoading}>
      <View style={styles.genLoadingIcon}>
        <ActivityIndicator color="#fff" />
      </View>
      <View style={styles.genLoadingText}>
        <Text style={styles.genLoadingTitle}>{title}</Text>
        <Text style={styles.genLoadingSub}>{sub}</Text>
      </View>
    </View>
  );
}

export function GenResultCard({
  imageUrl,
  gradIndex,
  badge,
  onRegen,
}: {
  imageUrl?: string;
  gradIndex: number;
  badge: string;
  onRegen?: () => void;
}) {
  const [a, b] = gradients[gradIndex % gradients.length];
  const preview = imageUrl ? (
    <RemoteImage uri={imageUrl} style={styles.genPreview} gradIndex={gradIndex} contentFit="cover" />
  ) : (
    <LinearGradient colors={[a, b]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.genPreview} />
  );

  return (
    <View style={styles.genResult}>
      <View style={styles.genPreviewWrap}>
        {preview}
        <View style={styles.genBadgeWrap}>
          <Text style={styles.genBadge}>{badge}</Text>
        </View>
      </View>
      <View style={styles.genActions}>
        <Pressable
          style={styles.genDownload}
          onPress={() => {
            if (imageUrl) void Linking.openURL(imageUrl);
          }}
          disabled={!imageUrl}
        >
          <Text style={styles.genDownloadText}>Скачать</Text>
        </Pressable>
        <Pressable style={styles.genRegen} onPress={onRegen}>
          <Text style={styles.genRegenText}>↻ Ещё раз</Text>
        </Pressable>
      </View>
    </View>
  );
}

export function CheckRow({
  label,
  checked,
  onToggle,
}: {
  label: string;
  checked: boolean;
  onToggle?: () => void;
}) {
  return (
    <Pressable style={styles.checkRow} onPress={onToggle}>
      <Text style={styles.checkLabel}>{label}</Text>
      <View style={[styles.checkbox, checked && styles.checkboxOn]}>
        {checked ? <Text style={styles.checkMark}>✓</Text> : null}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  fieldLabel: {
    fontFamily: font.mono,
    fontSize: 8.5,
    letterSpacing: 1,
    color: color.dim,
    marginBottom: 5,
  },
  textField: {
    backgroundColor: color.inputBg,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.09)',
    borderRadius: 9,
    paddingHorizontal: 11,
    paddingVertical: 8,
    fontSize: 11.5,
    color: color.text,
    fontFamily: font.body,
  },
  textArea: { paddingTop: 10 },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, paddingBottom: 2 },
  chip: {
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 6,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.08)',
  },
  chipActive: { backgroundColor: 'rgba(215,244,82,0.12)', borderColor: 'rgba(215,244,82,0.35)' },
  chipText: { fontFamily: font.monoBold, fontSize: 10, color: color.muted, fontWeight: '700' },
  chipTextActive: { color: color.lime },
  tabChip: {
    borderRadius: 20,
    paddingHorizontal: 11,
    paddingVertical: 6,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.1)',
  },
  tabChipActive: { backgroundColor: 'rgba(215,244,82,0.12)', borderColor: 'rgba(215,244,82,0.35)' },
  tabChipText: { fontFamily: font.monoBold, fontSize: 9.5, color: color.muted, fontWeight: '700' },
  tabChipTextActive: { color: color.lime },
  segmented: {
    flexDirection: 'row',
    backgroundColor: color.inputBg,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.09)',
    borderRadius: 10,
    padding: 3,
  },
  segItem: { flex: 1, alignItems: 'center', paddingVertical: 8, borderRadius: 8 },
  segItemActive: { backgroundColor: color.lime },
  segText: { fontSize: 11.5, fontFamily: font.bodyBold, color: color.muted },
  segTextActive: { color: color.limeText },
  dropSlot: {
    flex: 1,
    height: 96,
    borderWidth: 1.5,
    borderStyle: 'dashed',
    borderColor: 'rgba(255,255,255,0.18)',
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 5,
  },
  dropLabel: { fontSize: 9, fontWeight: '700', color: color.muted, textAlign: 'center', paddingHorizontal: 6 },
  dropSlotWide: {
    height: 110,
    borderWidth: 1.5,
    borderStyle: 'dashed',
    borderColor: 'rgba(255,255,255,0.18)',
    borderRadius: 12,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  dropLabelWide: { fontSize: 11, fontWeight: '700', color: color.muted },
  limeBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: color.lime,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 13,
  },
  limeBtnTitle: { flex: 1, fontFamily: font.bodyExtra, fontSize: 13.5, color: color.limeText },
  limeBtnCost: { fontFamily: font.mono, fontSize: 11, color: '#3D4213' },
  ghostBtn: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 11,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.12)',
  },
  ghostBtnText: { fontFamily: font.bodyBold, fontSize: 12.5, color: color.muted },
  dashedBtn: {
    alignItems: 'center',
    paddingVertical: 11,
    borderRadius: 10,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: 'rgba(215,244,82,0.4)',
  },
  dashedBtnText: { fontFamily: font.bodyBold, fontSize: 12.5, color: color.lime },
  genLoading: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: 'rgba(192,132,252,0.06)',
    borderWidth: 1,
    borderColor: 'rgba(192,132,252,0.25)',
    borderRadius: 14,
    padding: 12,
  },
  genLoadingIcon: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: gradients[0][0],
    alignItems: 'center',
    justifyContent: 'center',
  },
  genLoadingText: { flex: 1 },
  genLoadingTitle: { fontFamily: font.bodyExtra, fontSize: 12.5, color: color.purple },
  genLoadingSub: { fontSize: 10.5, color: color.muted, marginTop: 2 },
  genResult: { gap: 10 },
  genPreviewWrap: { position: 'relative', borderRadius: 12, overflow: 'hidden' },
  genPreview: { width: '100%', aspectRatio: 3 / 4 },
  genBadgeWrap: {
    position: 'absolute',
    left: 8,
    bottom: 8,
    backgroundColor: 'rgba(0,0,0,0.55)',
    borderRadius: 5,
    paddingHorizontal: 7,
    paddingVertical: 2,
  },
  genBadge: { fontFamily: font.mono, fontSize: 8.5, color: '#fff' },
  genActions: { flexDirection: 'row', gap: 7 },
  genDownload: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 9,
    borderRadius: 9,
    backgroundColor: color.lime,
  },
  genDownloadText: { fontFamily: font.bodyExtra, fontSize: 11.5, color: color.limeText },
  genRegen: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 9,
    borderRadius: 9,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.12)',
  },
  genRegenText: { fontFamily: font.bodyBold, fontSize: 11.5, color: color.muted },
  checkRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 4 },
  checkLabel: { fontSize: 12, color: color.text },
  checkbox: {
    width: 18,
    height: 18,
    borderRadius: 5,
    borderWidth: 1.5,
    borderColor: 'rgba(255,255,255,0.2)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkboxOn: { backgroundColor: color.lime, borderColor: color.lime },
  checkMark: { fontSize: 11, fontWeight: '900', color: color.limeText },
});

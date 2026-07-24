import { useState } from 'react';
import { ActivityIndicator, Image, Modal, Pressable, Text, View } from 'react-native';
import { IcoWand } from '@/src/components/Icons';
import { Card } from '@/src/components/ui';
import { color, font } from '@/src/styles/tokens';
import { pickImage } from '@/src/utils/mediaPicker';
import type { LocalFile } from '@/src/api/types';
import {
  runModelBootstrapBodyCompose,
  runModelBootstrapFaceMerge,
  uploadStudioModelImageFromUrl,
} from '@/src/api/actions';
import { resolveMediaUrl } from '@/src/api/config';
import { useAppSettings } from '@/src/context/AppSettingsContext';

type Stage = 'face-form' | 'face-loading' | 'face-result' | 'body-form' | 'body-loading' | 'body-result' | 'done';

export function CharacterGenPanel({
  charId,
  onSaved,
}: {
  charId: number;
  onSaved: () => Promise<void> | void;
}) {
  const { t } = useAppSettings();
  const [open, setOpen] = useState(false);
  const [stage, setStage] = useState<Stage>('face-form');
  const [error, setError] = useState<string | null>(null);
  const [face1, setFace1] = useState<LocalFile | null>(null);
  const [face2, setFace2] = useState<LocalFile | null>(null);
  const [bodyFile, setBodyFile] = useState<LocalFile | null>(null);
  const [faceResultUrl, setFaceResultUrl] = useState('');
  const [faceGenerationId, setFaceGenerationId] = useState<number | null>(null);
  const [bodyResultUrl, setBodyResultUrl] = useState('');
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null);

  const pickSlot = async (slot: 'face1' | 'face2' | 'body') => {
    try {
      const file = await pickImage();
      if (!file) return;
      if (slot === 'face1') setFace1(file);
      else if (slot === 'face2') setFace2(file);
      else setBodyFile(file);
    } catch {
      /* ignore */
    }
  };

  const runFace = async () => {
    if (!face1 || !face2) {
      setError(t.charBootstrapErrTwoFaces);
      return;
    }
    setError(null);
    setStage('face-loading');
    try {
      const { result } = await runModelBootstrapFaceMerge({ modelId: charId, face1, face2, aspect: '3:4' });
      const url = String(result?.generated_image_url || result?.image_url || '');
      if (!url) throw new Error(t.charBootstrapErrFaceResult);
      setFaceResultUrl(url);
      const genId = result?.generation_id;
      setFaceGenerationId(typeof genId === 'number' ? genId : genId != null ? Number(genId) : null);
      setStage('face-result');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStage('face-form');
    }
  };

  const useFace = async () => {
    if (!faceResultUrl) return;
    setError(null);
    try {
      await uploadStudioModelImageFromUrl(charId, faceResultUrl, 'face');
      await onSaved();
      setStage('body-form');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const runBody = async () => {
    if (!bodyFile) {
      setError(t.charBootstrapErrBodyRef);
      return;
    }
    setError(null);
    setStage('body-loading');
    try {
      const { result } = await runModelBootstrapBodyCompose({
        modelId: charId,
        bodyRef: bodyFile,
        faceGenerationId,
        aspect: '3:4',
      });
      const url = String(result?.generated_image_url || result?.image_url || '');
      if (!url) throw new Error(t.charBootstrapErrBodyResult);
      setBodyResultUrl(url);
      setStage('body-result');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStage('body-form');
    }
  };

  const saveBody = async () => {
    if (!bodyResultUrl) return;
    setError(null);
    try {
      await uploadStudioModelImageFromUrl(charId, bodyResultUrl, 'body');
      await onSaved();
      setStage('done');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const uploadSlot = (label: string, ratio: string, file: LocalFile | null, onPress: () => void, width?: number) => (
    <Pressable
      onPress={onPress}
      style={{
        width: width || '48%',
        aspectRatio: ratio === '1/1' ? 1 : 3 / 4,
        borderWidth: 1.5,
        borderStyle: 'dashed',
        borderColor: 'rgba(255,255,255,.2)',
        borderRadius: 10,
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden',
      }}
    >
      {file?.uri ? (
        <Image source={{ uri: file.uri }} style={{ width: '100%', height: '100%' }} resizeMode="cover" />
      ) : (
        <>
          <Text style={{ fontSize: 10, fontWeight: '700', color: color.muted }}>{label}</Text>
        </>
      )}
    </Pressable>
  );

  const purpleBtn = {
    textAlign: 'center' as const,
    padding: 11,
    borderRadius: 10,
    backgroundColor: color.purple,
    color: '#1A0A2E',
    fontWeight: '800' as const,
    fontSize: 13,
  };

  return (
    <>
      <Pressable onPress={() => setOpen((v) => !v)} style={{ flexDirection: 'row', alignItems: 'center', gap: 9, marginBottom: open ? 10 : 12 }}>
        <IcoWand size={17} stroke={color.purple} />
        <Text style={{ fontWeight: '800', fontSize: 14, flex: 1, color: color.text }}>{t.charBootstrapTitle}</Text>
        <Text style={{ color: color.muted, fontSize: 12 }}>{open ? '▲' : '▼'}</Text>
      </Pressable>

      {open ? (
        <Card style={{ gap: 10, marginBottom: 12, borderColor: 'rgba(192,132,252,.25)' }}>
          {error ? <Text style={{ fontSize: 11.5, color: color.red }}>{error}</Text> : null}

          {stage === 'face-form' ? (
            <>
              <Text style={{ fontWeight: '700', fontSize: 13, color: color.text }}>{t.charBootstrapFaceTitle}</Text>
              <Text style={{ fontSize: 11.5, color: color.muted, lineHeight: 18 }}>
                {t.charBootstrapFaceDesc}
              </Text>
              <Text style={{ fontSize: 10.5, color: '#FB923C', lineHeight: 18 }}>
                {t.charBootstrapFaceWarn}
              </Text>
              <View style={{ flexDirection: 'row', gap: 8, justifyContent: 'space-between' }}>
                {uploadSlot(t.charBootstrapFace1, '3/4', face1, () => void pickSlot('face1'))}
                {uploadSlot(t.charBootstrapFace2, '3/4', face2, () => void pickSlot('face2'))}
              </View>
              <Pressable onPress={() => void runFace()}>
                <Text style={purpleBtn}>{t.charBootstrapGenerate}</Text>
              </Pressable>
            </>
          ) : null}

          {stage === 'face-loading' ? (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
              <ActivityIndicator color={color.purple} />
              <View>
                <Text style={{ fontWeight: '800', fontSize: 12.5, color: color.purple }}>{t.charBootstrapFaceLoading}</Text>
                <Text style={{ fontSize: 10.5, color: color.muted }}>{t.charBootstrapFaceLoadingSub}</Text>
              </View>
            </View>
          ) : null}

          {stage === 'face-result' ? (
            <>
              <Text style={{ fontWeight: '700', fontSize: 13, color: color.text }}>{t.charBootstrapResult}</Text>
              <Pressable onPress={() => setLightboxUrl(resolveMediaUrl(faceResultUrl))}>
                <Image
                  source={{ uri: resolveMediaUrl(faceResultUrl) }}
                  style={{ width: 110, aspectRatio: 3 / 4, borderRadius: 10 }}
                  resizeMode="cover"
                />
              </Pressable>
              <View style={{ flexDirection: 'row', gap: 7 }}>
                <Pressable style={{ flex: 1 }} onPress={() => void runFace()}>
                  <Text style={{ textAlign: 'center', padding: 9, borderRadius: 9, borderWidth: 1, borderColor: 'rgba(255,255,255,.14)', color: color.muted, fontWeight: '700', fontSize: 12 }}>
                    {t.charBootstrapRegenerate}
                  </Text>
                </Pressable>
                <Pressable style={{ flex: 1 }} onPress={() => void useFace()}>
                  <Text style={{ textAlign: 'center', padding: 9, borderRadius: 9, backgroundColor: 'rgba(215,244,82,.12)', borderWidth: 1, borderColor: 'rgba(215,244,82,.35)', color: color.lime, fontWeight: '800', fontSize: 12 }}>
                    {t.charBootstrapUseThis}
                  </Text>
                </Pressable>
              </View>
            </>
          ) : null}

          {(stage === 'body-form' || stage === 'body-loading' || stage === 'body-result' || stage === 'done') ? (
            <View style={{ borderTopWidth: 1, borderTopColor: 'rgba(255,255,255,.08)', paddingTop: 12, gap: 10 }}>
              {stage !== 'done' ? (
                <Text style={{ fontFamily: font.mono, fontSize: 8.5, alignSelf: 'flex-start', backgroundColor: 'rgba(215,244,82,.15)', color: color.lime, paddingHorizontal: 8, paddingVertical: 2, borderRadius: 5 }}>
                  {t.charBootstrapFaceSaved}
                </Text>
              ) : null}

              {stage === 'body-form' ? (
                <>
                  <Text style={{ fontWeight: '700', fontSize: 13, color: color.text }}>{t.charBootstrapBodyTitle}</Text>
                  <Text style={{ fontSize: 11.5, color: color.muted, lineHeight: 18 }}>
                    {t.charBootstrapBodyDesc}
                  </Text>
                  {uploadSlot(t.charBootstrapBody, '3/4', bodyFile, () => void pickSlot('body'), 150)}
                  <Pressable onPress={() => void runBody()}>
                    <Text style={purpleBtn}>{t.charBootstrapGenerate}</Text>
                  </Pressable>
                </>
              ) : null}

              {stage === 'body-loading' ? (
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                  <ActivityIndicator color={color.purple} />
                  <View>
                    <Text style={{ fontWeight: '800', fontSize: 12.5, color: color.purple }}>{t.charBootstrapBodyLoading}</Text>
                    <Text style={{ fontSize: 10.5, color: color.muted }}>{t.charBootstrapBodyLoadingSub}</Text>
                  </View>
                </View>
              ) : null}

              {stage === 'body-result' ? (
                <>
                  <Text style={{ fontWeight: '700', fontSize: 13, color: color.text }}>{t.charBootstrapResult}</Text>
                  <Pressable onPress={() => setLightboxUrl(resolveMediaUrl(bodyResultUrl))}>
                    <Image
                      source={{ uri: resolveMediaUrl(bodyResultUrl) }}
                      style={{ width: 120, aspectRatio: 3 / 4, borderRadius: 10 }}
                      resizeMode="cover"
                    />
                  </Pressable>
                  <View style={{ flexDirection: 'row', gap: 7 }}>
                    <Pressable style={{ flex: 1 }} onPress={() => void runBody()}>
                      <Text style={{ textAlign: 'center', padding: 9, borderRadius: 9, borderWidth: 1, borderColor: 'rgba(255,255,255,.14)', color: color.muted, fontWeight: '700', fontSize: 12 }}>
                        {t.charBootstrapRegenerate}
                      </Text>
                    </Pressable>
                    <Pressable style={{ flex: 1 }} onPress={() => void saveBody()}>
                      <Text style={{ textAlign: 'center', padding: 9, borderRadius: 9, backgroundColor: 'rgba(215,244,82,.12)', borderWidth: 1, borderColor: 'rgba(215,244,82,.35)', color: color.lime, fontWeight: '800', fontSize: 12 }}>
                        {t.charBootstrapSave}
                      </Text>
                    </Pressable>
                  </View>
                </>
              ) : null}

              {stage === 'done' ? (
                <Text style={{ fontFamily: font.mono, fontSize: 11, color: color.green }}>
                  {t.charBootstrapDone}
                </Text>
              ) : null}
            </View>
          ) : null}
        </Card>
      ) : null}

      <Modal visible={Boolean(lightboxUrl)} transparent animationType="fade" onRequestClose={() => setLightboxUrl(null)}>
        <Pressable style={{ flex: 1, backgroundColor: 'rgba(0,0,0,.88)', justifyContent: 'center', padding: 16 }} onPress={() => setLightboxUrl(null)}>
          {lightboxUrl ? (
            <Image source={{ uri: lightboxUrl }} style={{ width: '100%', height: '70%' }} resizeMode="contain" />
          ) : null}
        </Pressable>
      </Modal>
    </>
  );
}

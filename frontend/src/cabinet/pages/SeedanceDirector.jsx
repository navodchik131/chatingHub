import { useMemo, useState } from 'react';

import { Fade, Field, NoteBlock, PageTitle, Panel, BackLink, SelectPill } from '../components/ui';
import Hoverable from '../components/Hoverable';
import { color, line, font } from '../styles/tokens';
import { useApp } from '../hooks/useApp';
import { photoKindShortLabel } from '../api/helpers';
import {
  composeSeedanceDirector,
  generateSeedanceDirectorVideo,
} from '../api/actions';

const CAMERA_MODES = [
  { id: 'A', ru: 'Селфи — телефон в руке на вытянутой руке', en: 'Selfie — arm\'s length front camera' },
  { id: 'B', ru: 'Снимает друг, стоя сбоку', en: 'Friend filming, standing still' },
  { id: 'C', ru: 'Телефон стоит, никто не держит', en: 'Phone propped, untouched' },
  { id: 'D', ru: 'Оператор идёт рядом', en: 'Operator walking with her' },
  { id: 'E', ru: 'Зеркало — телефон виден в кадре', en: 'Mirror — phone visible in frame' },
];

const ROLE_SUGGESTIONS = [
  'first frame',
  'face',
  'body',
  'character',
  'location',
  'wardrobe',
  'pose',
];

function uid() {
  return `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

async function fileFromModelImage(im) {
  const res = await fetch(im.url, { credentials: 'include' });
  if (!res.ok) throw new Error(`Не удалось загрузить фото модели #${im.id}`);
  const blob = await res.blob();
  const ext = (blob.type || '').includes('png') ? 'png' : 'jpg';
  const kind = (im.kind || 'other').replace(/[^\w-]+/g, '_');
  return new File([blob], `model_${im.id}_${kind}.${ext}`, {
    type: blob.type || 'image/jpeg',
  });
}

export default function SeedanceDirector() {
  const { lang, cabinet } = useApp();
  const models = cabinet.models || [];
  const [refs, setRefs] = useState([]);
  const [brief, setBrief] = useState('');
  const [cameraMode, setCameraMode] = useState('A');
  const [duration, setDuration] = useState('15');
  const [aspect, setAspect] = useState('9:16');
  const [resolution, setResolution] = useState('720p');
  const [generateAudio, setGenerateAudio] = useState(true);
  const [modelId, setModelId] = useState(cabinet.selectedModelId || models[0]?.id || '');
  const [pickerOpen, setPickerOpen] = useState(false);
  const [busyCompose, setBusyCompose] = useState(false);
  const [busyGen, setBusyGen] = useState(null);
  const [compose, setCompose] = useState(null);

  const selectedModel = useMemo(
    () => models.find((m) => Number(m.id) === Number(modelId)) || null,
    [models, modelId],
  );
  const modelImages = selectedModel?.images || selectedModel?.raw?.images || [];

  const canCompose = refs.length > 0 && brief.trim() && !busyCompose && !busyGen;

  const addUploadFiles = (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    setRefs((prev) => [
      ...prev,
      ...files.map((file) => ({
        id: uid(),
        file,
        role: '',
        preview: URL.createObjectURL(file),
        source: 'upload',
      })),
    ]);
  };

  const attachModelImage = async (im) => {
    cabinet.setError(null);
    try {
      const file = await fileFromModelImage(im);
      const kind = (im.kind || '').toLowerCase();
      const roleGuess =
        kind === 'face' ? 'face' : kind === 'body' || kind === 'turnaround' ? 'body' : kind || 'character';
      setRefs((prev) => [
        ...prev,
        {
          id: uid(),
          file,
          role: roleGuess,
          preview: im.url,
          source: 'model',
          modelImageId: im.id,
        },
      ]);
      setPickerOpen(false);
    } catch (e) {
      cabinet.setError(e?.message || String(e));
    }
  };

  const removeRef = (id) => {
    setRefs((prev) => {
      const next = prev.filter((r) => r.id !== id);
      const gone = prev.find((r) => r.id === id);
      if (gone?.preview && gone.source === 'upload') {
        try {
          URL.revokeObjectURL(gone.preview);
        } catch {
          /* ignore */
        }
      }
      return next;
    });
  };

  const setRole = (id, role) => {
    setRefs((prev) => prev.map((r) => (r.id === id ? { ...r, role } : r)));
  };

  const onCompose = async () => {
    if (!canCompose) return;
    setBusyCompose(true);
    cabinet.setError(null);
    try {
      const data = await composeSeedanceDirector({
        images: refs.map((r) => r.file),
        roles: refs.map((r, i) => (r.role || '').trim() || `reference ${i + 1}`),
        brief: brief.trim(),
        durationSeconds: Number(duration) || 15,
        aspectRatio: aspect,
        cameraMode,
      });
      setCompose(data);
    } catch (e) {
      cabinet.setError(e?.message || String(e));
    } finally {
      setBusyCompose(false);
    }
  };

  const onGenerate = async (piece) => {
    if (!piece?.prompt || !refs.length) return;
    const key = `${piece.version}_${piece.piece_id}`;
    setBusyGen(key);
    cabinet.setError(null);
    try {
      const span = String(piece.span || '');
      let dur = Number(duration) || 15;
      const m = span.replace(/[–—]/g, '-').match(/([\d.]+)\s*-\s*([\d.]+)/);
      if (m) {
        dur = Math.max(1, Math.round(Number(m[2]) - Number(m[1])));
      }
      if (piece.version === '2.5') dur = Math.min(30, Math.max(5, dur));
      else dur = Math.min(15, Math.max(5, dur));

      const data = await generateSeedanceDirectorVideo({
        images: refs.map((r) => r.file),
        prompt: piece.prompt,
        version: piece.version,
        durationSeconds: dur,
        aspectRatio: aspect,
        resolution,
        generateAudio,
      });
      setCompose((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          pieces: (prev.pieces || []).map((p) =>
            p.version === piece.version && p.piece_id === piece.piece_id
              ? { ...p, video_url: data.video_url, last_generate: data }
              : p,
          ),
        };
      });
    } catch (e) {
      cabinet.setError(e?.message || String(e));
    } finally {
      setBusyGen(null);
    }
  };

  const copyText = async (text) => {
    try {
      await navigator.clipboard.writeText(text || '');
    } catch {
      cabinet.setError(lang === 'ru' ? 'Не удалось скопировать' : 'Copy failed');
    }
  };

  const pieces20 = (compose?.pieces || []).filter((p) => p.version === '2.0');
  const pieces25 = (compose?.pieces || []).filter((p) => p.version === '2.5');

  const btn = (enabled) => ({
    background: color.lime,
    color: color.limeInk,
    fontWeight: 800,
    fontSize: 13,
    borderRadius: 10,
    padding: '11px 16px',
    cursor: enabled ? 'pointer' : 'not-allowed',
    opacity: enabled ? 1 : 0.55,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: 'none',
  });

  return (
    <Fade data-screen-label="Seedance Director">
      <div style={{ maxWidth: 1180, margin: '0 auto' }}>
        <BackLink onClick={() => window.location.assign('/workspace/video')}>
          {lang === 'ru' ? 'Назад в видео' : 'Back to video'}
        </BackLink>
        <div style={{ marginBottom: 16 }}>
          <PageTitle style={{ marginBottom: 6 }}>Seedance Director</PageTitle>
          <div style={{ fontSize: 12.5, color: color.textDim }}>
            {lang === 'ru'
              ? 'Скрытый экран: бриф + фото → Grok пишет промпты Seedance 2.0 / 2.5 → генерация в WaveSpeed.'
              : 'Hidden screen: brief + photos → Grok writes Seedance 2.0 / 2.5 prompts → WaveSpeed generate.'}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 440px) 1fr', gap: 16 }}>
          <Panel style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <NoteBlock>
              {lang === 'ru'
                ? 'Загрузи любые фото и подпиши роль каждого (first frame / face / body или character / location). Можно добавить фото из карточки персонажа.'
                : 'Upload any photos and label each role. You can also attach photos from a character card.'}
            </NoteBlock>

            <div>
              <div style={{ fontSize: 11, color: color.textMuted, marginBottom: 6 }}>
                {lang === 'ru' ? 'ФОТОГРАФИИ' : 'PHOTOS'}
              </div>
              <input
                type="file"
                accept="image/*"
                multiple
                onChange={(e) => {
                  addUploadFiles(e.target.files);
                  e.target.value = '';
                }}
              />
            </div>

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <Hoverable
                style={{
                  border: `1px solid ${line.mid}`,
                  borderRadius: 10,
                  padding: '8px 12px',
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
                onClick={() => setPickerOpen(true)}
              >
                {lang === 'ru' ? '+ Фото персонажа' : '+ Character photo'}
              </Hoverable>
              <select
                value={modelId || ''}
                onChange={(e) => setModelId(e.target.value)}
                style={{
                  border: `1px solid ${line.mid}`,
                  borderRadius: 10,
                  padding: '8px 10px',
                  fontSize: 12,
                  background: color.raised,
                  color: color.text,
                }}
              >
                <option value="">{lang === 'ru' ? 'Персонаж…' : 'Character…'}</option>
                {models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name || `#${m.id}`}
                  </option>
                ))}
              </select>
            </div>

            {!!refs.length && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {refs.map((r, idx) => (
                  <div
                    key={r.id}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '72px 1fr auto',
                      gap: 10,
                      alignItems: 'start',
                      border: `1px solid ${line.soft}`,
                      borderRadius: 12,
                      padding: 8,
                    }}
                  >
                    <img
                      src={r.preview}
                      alt=""
                      style={{ width: 72, height: 72, objectFit: 'cover', borderRadius: 8 }}
                    />
                    <div>
                      <div style={{ fontSize: 11, color: color.textMuted, marginBottom: 4 }}>
                        Image {idx + 1}
                        {r.source === 'model' ? ' · model' : ''}
                      </div>
                      <input
                        list="seedance-director-roles"
                        value={r.role}
                        placeholder={lang === 'ru' ? 'роль: face, first frame…' : 'role: face, first frame…'}
                        onChange={(e) => setRole(r.id, e.target.value)}
                        style={{
                          width: '100%',
                          border: `1px solid ${line.mid}`,
                          borderRadius: 8,
                          padding: '8px 10px',
                          fontSize: 12.5,
                          background: color.bg,
                          color: color.text,
                        }}
                      />
                      <div style={{ marginTop: 4, fontSize: 11, color: color.textDim }}>
                        {r.file?.name}
                      </div>
                    </div>
                    <Hoverable
                      style={{
                        fontSize: 11,
                        fontWeight: 700,
                        color: color.textMuted,
                        cursor: 'pointer',
                        padding: 4,
                      }}
                      onClick={() => removeRef(r.id)}
                    >
                      ✕
                    </Hoverable>
                  </div>
                ))}
                <datalist id="seedance-director-roles">
                  {ROLE_SUGGESTIONS.map((s) => (
                    <option key={s} value={s} />
                  ))}
                </datalist>
              </div>
            )}

            <div>
              <div style={{ fontSize: 11, color: color.textMuted, marginBottom: 6 }}>
                {lang === 'ru' ? 'БРИФ (что происходит)' : 'BRIEF (what happens)'}
              </div>
              <textarea
                value={brief}
                onChange={(e) => setBrief(e.target.value)}
                rows={5}
                placeholder={
                  lang === 'ru'
                    ? 'Свободно своими словами: она подходит к витрине, смотрит в камеру…'
                    : 'Plain language: she walks up to the window, looks at camera…'
                }
                style={{
                  width: '100%',
                  border: `1px solid ${line.mid}`,
                  borderRadius: 10,
                  padding: 10,
                  fontSize: 13,
                  background: color.bg,
                  color: color.text,
                  resize: 'vertical',
                  fontFamily: font.body,
                }}
              />
            </div>

            <div>
              <div style={{ fontSize: 11, color: color.textMuted, marginBottom: 6 }}>
                {lang === 'ru' ? 'ТИП СЪЁМКИ' : 'CAMERA MODE'}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {CAMERA_MODES.map((m) => (
                  <label
                    key={m.id}
                    style={{
                      display: 'flex',
                      gap: 8,
                      alignItems: 'flex-start',
                      fontSize: 12.5,
                      cursor: 'pointer',
                    }}
                  >
                    <input
                      type="radio"
                      name="cameraMode"
                      checked={cameraMode === m.id}
                      onChange={() => setCameraMode(m.id)}
                      style={{ marginTop: 2 }}
                    />
                    <span>
                      <b>{m.id}</b> — {lang === 'ru' ? m.ru : m.en}
                    </span>
                  </label>
                ))}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <Field label="Duration (s)" value={duration} onChange={(e) => setDuration(e.target.value)} />
              <div>
                <div style={{ fontSize: 11, color: color.textMuted, marginBottom: 6 }}>Aspect</div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {['9:16', '16:9', '1:1'].map((a) => (
                    <SelectPill key={a} on={aspect === a} onClick={() => setAspect(a)}>
                      {a}
                    </SelectPill>
                  ))}
                </div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <div>
                <div style={{ fontSize: 11, color: color.textMuted, marginBottom: 6 }}>Resolution</div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {['480p', '720p', '1080p'].map((r) => (
                    <SelectPill key={r} on={resolution === r} onClick={() => setResolution(r)}>
                      {r}
                    </SelectPill>
                  ))}
                </div>
              </div>
              <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 12.5, marginTop: 18 }}>
                <input
                  type="checkbox"
                  checked={generateAudio}
                  onChange={(e) => setGenerateAudio(e.target.checked)}
                />
                generate_audio
              </label>
            </div>

            <Hoverable style={btn(canCompose)} onClick={onCompose} disabled={!canCompose}>
              {busyCompose
                ? lang === 'ru'
                  ? 'Grok пишет…'
                  : 'Grok writing…'
                : lang === 'ru'
                  ? 'Собрать промпты в Grok'
                  : 'Compose prompts via Grok'}
            </Hoverable>
          </Panel>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {!compose && (
              <Panel>
                <div style={{ fontSize: 13, color: color.textDim }}>
                  {lang === 'ru'
                    ? 'После Grok здесь появятся промпты Seedance 2.0 и 2.5.'
                    : 'After Grok runs, Seedance 2.0 and 2.5 prompts appear here.'}
                </div>
              </Panel>
            )}

            {compose?.assumed ? (
              <NoteBlock>
                Assumed: {compose.assumed}
              </NoteBlock>
            ) : null}

            {[
              { title: 'Seedance 2.0', list: pieces20 },
              { title: 'Seedance 2.5', list: pieces25 },
            ].map((group) =>
              group.list.length ? (
                <Panel key={group.title} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{ fontWeight: 800, fontSize: 14 }}>{group.title}</div>
                  {group.list.map((p) => {
                    const key = `${p.version}_${p.piece_id}`;
                    const genBusy = busyGen === key;
                    return (
                      <div
                        key={key}
                        style={{
                          border: `1px solid ${line.soft}`,
                          borderRadius: 12,
                          padding: 12,
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 8,
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
                          <div style={{ fontWeight: 700, fontSize: 13 }}>
                            {p.label || `Seedance ${p.version} — ${p.piece_id} — ${p.span}`}
                          </div>
                          <div style={{ display: 'flex', gap: 8 }}>
                            <Hoverable
                              style={{
                                border: `1px solid ${line.mid}`,
                                borderRadius: 8,
                                padding: '6px 10px',
                                fontSize: 12,
                                fontWeight: 700,
                                cursor: 'pointer',
                              }}
                              onClick={() => copyText(p.prompt)}
                            >
                              {lang === 'ru' ? 'Копировать' : 'Copy'}
                            </Hoverable>
                            <Hoverable
                              style={btn(!genBusy && !busyCompose)}
                              onClick={() => onGenerate(p)}
                            >
                              {genBusy
                                ? lang === 'ru'
                                  ? 'Генерация…'
                                  : 'Generating…'
                                : lang === 'ru'
                                  ? 'Сгенерировать видео'
                                  : 'Generate video'}
                            </Hoverable>
                          </div>
                        </div>
                        {p.start_frame ? (
                          <div style={{ fontSize: 12, color: color.textDim }}>
                            Start frame: {p.start_frame}
                          </div>
                        ) : null}
                        <textarea
                          readOnly
                          value={p.prompt || ''}
                          rows={12}
                          style={{
                            width: '100%',
                            border: `1px solid ${line.mid}`,
                            borderRadius: 10,
                            padding: 10,
                            fontSize: 12,
                            background: color.bg,
                            color: color.text,
                            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
                            resize: 'vertical',
                          }}
                        />
                        {p.video_url ? (
                          <div>
                            <div style={{ fontSize: 12, marginBottom: 6 }}>
                              <a href={p.video_url} target="_blank" rel="noreferrer">
                                {p.video_url}
                              </a>
                            </div>
                            <video
                              src={p.video_url}
                              controls
                              style={{ width: '100%', maxHeight: 420, borderRadius: 10, background: '#000' }}
                            />
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </Panel>
              ) : null,
            )}

            {compose && !(pieces20.length || pieces25.length) ? (
              <Panel>
                <div style={{ fontSize: 13, color: color.textDim, marginBottom: 8 }}>
                  {lang === 'ru'
                    ? 'Не удалось разобрать куски 2.0/2.5 — сырой ответ Grok:'
                    : 'Could not parse 2.0/2.5 pieces — raw Grok reply:'}
                </div>
                <textarea
                  readOnly
                  value={compose.raw_text || ''}
                  rows={18}
                  style={{
                    width: '100%',
                    border: `1px solid ${line.mid}`,
                    borderRadius: 10,
                    padding: 10,
                    fontSize: 12,
                    background: color.bg,
                    color: color.text,
                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
                  }}
                />
              </Panel>
            ) : null}
          </div>
        </div>
      </div>

      {pickerOpen ? (
        <div
          onClick={() => setPickerOpen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.45)',
            zIndex: 80,
            display: 'grid',
            placeItems: 'center',
            padding: 16,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: 'min(920px, 96vw)',
              maxHeight: '84vh',
              overflow: 'auto',
              background: color.raised,
              border: `1px solid ${line.mid}`,
              borderRadius: 16,
              padding: 16,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
              <div style={{ fontWeight: 800 }}>
                {lang === 'ru' ? 'Фото персонажа' : 'Character photos'}
                {selectedModel ? ` — ${selectedModel.name}` : ''}
              </div>
              <Hoverable style={{ cursor: 'pointer', fontWeight: 700 }} onClick={() => setPickerOpen(false)}>
                ✕
              </Hoverable>
            </div>
            {!modelImages.length ? (
              <div style={{ color: color.textDim, fontSize: 13 }}>
                {lang === 'ru' ? 'У персонажа нет загруженных фото.' : 'No photos on this character.'}
              </div>
            ) : (
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))',
                  gap: 10,
                }}
              >
                {modelImages.map((im) => (
                  <Hoverable
                    key={im.id}
                    onClick={() => attachModelImage(im)}
                    style={{
                      border: `1px solid ${line.soft}`,
                      borderRadius: 12,
                      overflow: 'hidden',
                      cursor: 'pointer',
                      background: color.bg,
                    }}
                  >
                    <img
                      src={im.url}
                      alt=""
                      style={{ width: '100%', height: 120, objectFit: 'cover', display: 'block' }}
                    />
                    <div style={{ padding: '6px 8px', fontSize: 11, color: color.textDim }}>
                      {photoKindShortLabel(lang, im.kind) || im.kind || im.id}
                    </div>
                  </Hoverable>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : null}
    </Fade>
  );
}

import { useRef, useState } from 'react';
import Hoverable from './Hoverable';
import { IcoUpload, IcoSpark } from './Icons';
import { Overlay, CloseButton } from './ui';
import { useApp } from '../hooks/useApp';
import { color, line, font } from '../styles/tokens';
import { borderHoverOff } from '../styles/mixins';
import {
  runModelBootstrapFaceMerge,
  runModelBootstrapBodyCompose,
} from '../api/actions';

const slotStyle = {
  flex: 1,
  aspectRatio: '3/4',
  border: `1.5px dashed ${line.dashed}`,
  borderRadius: 10,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 5,
  cursor: 'pointer',
  overflow: 'hidden',
  position: 'relative',
};

const bodySlotStyle = {
  aspectRatio: '3/4',
  maxWidth: 150,
  border: `1.5px dashed ${line.dashed}`,
  borderRadius: 10,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 5,
  cursor: 'pointer',
  overflow: 'hidden',
  position: 'relative',
};

function Spinner({ size = 64, ratio = '1/1' }) {
  return (
    <div
      style={{
        width: size,
        aspectRatio: ratio,
        borderRadius: 10,
        background: color.base,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flex: 'none',
        animation: 'mmPulse 1.2s ease-in-out infinite',
      }}
    >
      <div
        style={{
          width: 22,
          height: 22,
          borderRadius: '50%',
          border: '2.5px solid rgba(192,132,252,.25)',
          borderTopColor: color.purple,
          animation: 'mmSpin .8s linear infinite',
        }}
      />
    </div>
  );
}

function UploadSlot({ label, previewUrl, onPick, style = slotStyle }) {
  return (
    <Hoverable
      style={{
        ...style,
        ...(previewUrl ? { border: `1px solid ${line.mid}`, background: `url(${previewUrl}) center/cover` } : {}),
      }}
      hover={previewUrl ? {} : { borderColor: 'rgba(192,132,252,.5)', background: 'rgba(192,132,252,.04)' }}
      onClick={onPick}
    >
      {!previewUrl && (
        <>
          <span style={{ display: 'flex', width: 16, height: 16, color: color.textMuted }}><IcoUpload /></span>
          <span style={{ fontSize: 9.5, fontWeight: 700, color: color.textDim }}>{label}</span>
        </>
      )}
    </Hoverable>
  );
}

export default function CharacterGenPanel({ charId, cabinet }) {
  const { t } = useApp();
  const face1Ref = useRef(null);
  const face2Ref = useRef(null);
  const bodyRef = useRef(null);

  const [open, setOpen] = useState(false);
  const [stage, setStage] = useState('face-form');
  const [error, setError] = useState(null);
  const [face1, setFace1] = useState(null);
  const [face2, setFace2] = useState(null);
  const [face1Preview, setFace1Preview] = useState('');
  const [face2Preview, setFace2Preview] = useState('');
  const [bodyFile, setBodyFile] = useState(null);
  const [bodyPreview, setBodyPreview] = useState('');
  const [faceResultUrl, setFaceResultUrl] = useState('');
  const [faceGenerationId, setFaceGenerationId] = useState(null);
  const [bodyResultUrl, setBodyResultUrl] = useState('');
  const [lightboxUrl, setLightboxUrl] = useState(null);

  const pickFile = (ref, setter, previewSetter) => {
    ref.current?.click();
    ref.current.onchange = (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      setter(file);
      previewSetter(URL.createObjectURL(file));
      e.target.value = '';
    };
  };

  const runFaceGen = async () => {
    if (!face1 || !face2) {
      setError(t.genFaceHint);
      return;
    }
    setError(null);
    setStage('face-loading');
    try {
      const { result } = await runModelBootstrapFaceMerge({
        modelId: charId,
        face1,
        face2,
        aspect: '3:4',
      });
      const url = result?.generated_image_url || '';
      if (!url) throw new Error('Не удалось получить изображение лица');
      setFaceResultUrl(url);
      setFaceGenerationId(result?.generation_id ?? null);
      setStage('face-result');
    } catch (e) {
      setError(e?.message || String(e));
      setStage('face-form');
    }
  };

  const useFace = async () => {
    if (!faceResultUrl) return;
    setError(null);
    try {
      await cabinet.uploadCharacterPhotoFromUrl(charId, faceResultUrl, 'face');
      setStage('body-form');
    } catch (e) {
      setError(e?.message || String(e));
    }
  };

  const runBodyGen = async () => {
    if (!bodyFile) {
      setError(t.genBodyHint);
      return;
    }
    setError(null);
    setStage('body-loading');
    try {
      const { result } = await runModelBootstrapBodyCompose({
        modelId: charId,
        bodyRef: bodyFile,
        faceGenerationId: faceGenerationId,
        aspect: '3:4',
      });
      const url = result?.generated_image_url || '';
      if (!url) throw new Error('Не удалось получить изображение тела');
      setBodyResultUrl(url);
      setStage('body-result');
    } catch (e) {
      setError(e?.message || String(e));
      setStage('body-form');
    }
  };

  const saveBody = async () => {
    if (!bodyResultUrl) return;
    setError(null);
    try {
      await cabinet.uploadCharacterPhotoFromUrl(charId, bodyResultUrl, 'body');
      setStage('done');
    } catch (e) {
      setError(e?.message || String(e));
    }
  };

  const purpleBtn = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    background: color.purple,
    color: '#1A0A2E',
    fontWeight: 800,
    fontSize: 13,
    borderRadius: 10,
    padding: 11,
    cursor: 'pointer',
  };

  const ghostBtn = {
    flex: 1,
    textAlign: 'center',
    border: `1px solid ${line.mid}`,
    borderRadius: 9,
    padding: 10,
    fontSize: 12.5,
    fontWeight: 700,
    color: color.textDim,
    cursor: 'pointer',
  };

  const limeBtn = {
    flex: 1,
    textAlign: 'center',
    background: 'rgba(215,244,82,.12)',
    border: '1px solid rgba(215,244,82,.35)',
    borderRadius: 9,
    padding: 10,
    fontSize: 12.5,
    fontWeight: 800,
    color: color.lime,
    cursor: 'pointer',
  };

  return (
    <>
      <Hoverable
        style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', marginBottom: open ? 14 : 16 }}
        onClick={() => setOpen((v) => !v)}
      >
        <span style={{ display: 'flex', width: 19, height: 19, color: color.purple }}><IcoSpark /></span>
        <span style={{ fontWeight: 800, fontSize: 15, flex: 1 }}>{t.genImageTitle}</span>
        <span style={{ color: color.textDim, fontSize: 13 }}>{open ? '▲' : '▼'}</span>
      </Hoverable>

      {open && (
        <div
          style={{
            background: color.base,
            border: '1px solid rgba(192,132,252,.25)',
            borderRadius: 14,
            padding: 14,
            marginBottom: 16,
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
          }}
        >
          {error && (
            <div style={{ fontSize: 11.5, color: color.red, lineHeight: 1.45 }}>{error}</div>
          )}

          {stage === 'face-form' && (
            <div>
              <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 4 }}>{t.genFaceTitle}</div>
              <div style={{ fontSize: 11.5, color: color.textDim, lineHeight: 1.5, marginBottom: 3 }}>{t.genFaceHint}</div>
              <div style={{ fontSize: 10.5, color: '#FB923C', lineHeight: 1.5, marginBottom: 12 }}>⚠ {t.genQualityNote}</div>
              <input ref={face1Ref} type="file" accept="image/*" style={{ display: 'none' }} />
              <input ref={face2Ref} type="file" accept="image/*" style={{ display: 'none' }} />
              <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
                <UploadSlot label={t.genFace1} previewUrl={face1Preview} onPick={() => pickFile(face1Ref, setFace1, setFace1Preview)} />
                <UploadSlot label={t.genFace2} previewUrl={face2Preview} onPick={() => pickFile(face2Ref, setFace2, setFace2Preview)} />
              </div>
              <Hoverable style={purpleBtn} hover={{ background: color.purpleHi }} onClick={() => void runFaceGen()}>
                {t.generate}
              </Hoverable>
            </div>
          )}

          {stage === 'face-loading' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <Spinner size={64} ratio="3/4" />
              <div>
                <div style={{ fontWeight: 800, fontSize: 13, color: color.purple, marginBottom: 3 }}>{t.genFaceLoading}</div>
                <div style={{ fontSize: 11, color: color.textDim }}>Nano Banana Pro · ~12 c</div>
              </div>
            </div>
          )}

          {stage === 'face-result' && (
            <div>
              <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 10 }}>{t.genFaceResult}</div>
              <Hoverable
                style={{
                  aspectRatio: '3/4',
                  maxWidth: 180,
                  borderRadius: 12,
                  marginBottom: 12,
                  cursor: 'zoom-in',
                  background: faceResultUrl ? `url(${faceResultUrl}) center/cover` : color.surface,
                }}
                onClick={() => setLightboxUrl(faceResultUrl)}
              />
              <div style={{ display: 'flex', gap: 8 }}>
                <Hoverable style={ghostBtn} hover={{ borderColor: borderHoverOff }} onClick={() => void runFaceGen()}>
                  ↻ {t.regen}
                </Hoverable>
                <Hoverable style={limeBtn} hover={{ background: 'rgba(215,244,82,.2)' }} onClick={() => void useFace()}>
                  ✓ {t.useThis}
                </Hoverable>
              </div>
            </div>
          )}

          {(stage === 'body-form' || stage === 'body-loading' || stage === 'body-result' || stage === 'done') && (
            <div style={{ borderTop: `1px solid ${line.hair}`, paddingTop: 12 }}>
              {stage !== 'done' && (
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 10 }}>
                  <span style={{ fontFamily: font.mono, fontSize: 8.5, background: 'rgba(215,244,82,.15)', color: color.lime, padding: '2px 8px', borderRadius: 5 }}>
                    ✓ {t.faceSaved}
                  </span>
                </div>
              )}

              {stage === 'body-form' && (
                <>
                  <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 4 }}>{t.genBodyTitle}</div>
                  <div style={{ fontSize: 11.5, color: color.textDim, lineHeight: 1.5, marginBottom: 12 }}>{t.genBodyHint}</div>
                  <input ref={bodyRef} type="file" accept="image/*" style={{ display: 'none' }} />
                  <UploadSlot
                    label={t.genBodyRef}
                    previewUrl={bodyPreview}
                    onPick={() => pickFile(bodyRef, setBodyFile, setBodyPreview)}
                    style={bodySlotStyle}
                  />
                  <Hoverable
                    style={{ ...purpleBtn, marginTop: 12 }}
                    hover={{ background: color.purpleHi }}
                    onClick={() => void runBodyGen()}
                  >
                    {t.generate}
                  </Hoverable>
                </>
              )}

              {stage === 'body-loading' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                  <Spinner size={56} ratio="3/4" />
                  <div>
                    <div style={{ fontWeight: 800, fontSize: 13, color: color.purple, marginBottom: 3 }}>{t.genBodyLoading}</div>
                    <div style={{ fontSize: 11, color: color.textDim }}>Seedream 5 Pro · ~15 c</div>
                  </div>
                </div>
              )}

              {stage === 'body-result' && (
                <>
                  <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 10 }}>{t.genBodyResult}</div>
                  <Hoverable
                    style={{
                      aspectRatio: '3/4',
                      maxWidth: 150,
                      borderRadius: 12,
                      marginBottom: 12,
                      cursor: 'zoom-in',
                      background: bodyResultUrl ? `url(${bodyResultUrl}) center/cover` : color.surface,
                    }}
                    onClick={() => setLightboxUrl(bodyResultUrl)}
                  />
                  <div style={{ display: 'flex', gap: 8 }}>
                    <Hoverable style={ghostBtn} hover={{ borderColor: borderHoverOff }} onClick={() => void runBodyGen()}>
                      ↻ {t.regen}
                    </Hoverable>
                    <Hoverable style={limeBtn} hover={{ background: 'rgba(215,244,82,.2)' }} onClick={() => void saveBody()}>
                      💾 {t.save}
                    </Hoverable>
                  </div>
                </>
              )}

              {stage === 'done' && (
                <div style={{ fontFamily: font.mono, fontSize: 11, color: color.green }}>✓ {t.genFlowDone}</div>
              )}
            </div>
          )}
        </div>
      )}

      {lightboxUrl && (
        <Overlay onClose={() => setLightboxUrl(null)}>
          <div
            onClick={(e) => e.stopPropagation()}
            style={{ position: 'relative', maxWidth: 'min(92vw,520px)', width: '100%' }}
          >
            <CloseButton
              onClick={() => setLightboxUrl(null)}
              label={t.close}
              style={{ position: 'absolute', top: -40, right: 0 }}
            />
            <img
              src={lightboxUrl}
              alt=""
              style={{ width: '100%', borderRadius: 12, display: 'block' }}
            />
          </div>
        </Overlay>
      )}
    </>
  );
}

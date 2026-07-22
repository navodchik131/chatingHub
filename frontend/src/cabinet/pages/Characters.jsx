import { useRef, useState, useEffect } from 'react';
import Hoverable from '../components/Hoverable';
import { IcoUpload, IcoImage, IcoFace, IcoFilm, IcoStar } from '../components/Icons';
import {
  Fade, PageTitle, StatusChip, Chip, BackLink, LimeButton, Field, Panel, Overlay, CloseButton,
} from '../components/ui';
import { useApp } from '../hooks/useApp';
import { color, line, font, G } from '../styles/tokens';
import { fieldLbl, inputSt, borderHoverOff, borderHoverLime, selectSt } from '../styles/mixins';
import { mapCharacter, mapCharHistory } from '../api/mappers';
import { photoTagDefs, photoKindShortLabel, normalizePhotoKind } from '../api/helpers';
import CharacterGenPanel from '../components/CharacterGenPanel';

function CharacterCreateModal({ open, name, setName, onClose, onCreate, t, lang }) {
  if (!open) return null;
  return (
    <Overlay onClose={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ width: 'min(92vw,420px)', background: color.raised, border: `1px solid ${line.mid}`, borderRadius: 16, padding: 20 }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <div style={{ fontWeight: 800, fontSize: 15 }}>{t.newCharacter}</div>
          <CloseButton onClick={onClose} label={t.close} />
        </div>
        <Field
          label={lang === 'ru' ? 'ИМЯ' : 'NAME'}
          placeholder={lang === 'ru' ? 'Например, Mia' : 'e.g. Mia'}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
          <Hoverable
            style={{
              background: color.lime, color: color.limeInk, fontWeight: 800, fontSize: 12.5,
              borderRadius: 10, padding: '10px 18px', cursor: 'pointer',
            }}
            hover={{ background: color.limeHi }}
            onClick={onCreate}
          >
            {t.create}
          </Hoverable>
          <Hoverable
            style={{
              border: `1px solid ${line.mid}`, color: color.textDim, fontWeight: 700,
              fontSize: 12.5, borderRadius: 10, padding: '10px 18px', cursor: 'pointer',
            }}
            hover={{ borderColor: borderHoverOff }}
            onClick={onClose}
          >
            {t.opCancel}
          </Hoverable>
        </div>
      </div>
    </Overlay>
  );
}

const histIcons = { image: IcoImage, face: IcoFace, film: IcoFilm, star: IcoStar };

const charTabDefs = (lang) => [
  { id: 'photos', label: lang === 'ru' ? 'Фото и внешность' : 'Photos & look' },
  { id: 'persona', label: lang === 'ru' ? 'Персона (AI-компаньон)' : 'Persona (AI companion)' },
  { id: 'exif', label: lang === 'ru' ? 'EXIF «как с телефона»' : 'EXIF "like a phone"' },
  { id: 'history', label: lang === 'ru' ? 'История модели' : 'Model history' },
];

const personaFieldDefs = (lang) => [
  { lbl: lang === 'ru' ? 'ВОЗРАСТ' : 'AGE', val: '', ph: '24', area: false, half: true },
  { lbl: lang === 'ru' ? 'ГОРОД' : 'CITY', val: '', ph: '', area: false, half: true },
  { lbl: lang === 'ru' ? 'СТРАНА' : 'COUNTRY', val: '', ph: '', area: false, half: true },
  { lbl: lang === 'ru' ? 'ЧАСОВОЙ ПОЯС' : 'TIMEZONE', val: '', ph: 'Europe/Madrid', area: false, half: true },
  { lbl: lang === 'ru' ? 'ХАРАКТЕР' : 'PERSONALITY', val: '', ph: lang === 'ru' ? 'тёплая, игривая…' : 'warm, playful…', area: true, half: false },
  { lbl: lang === 'ru' ? 'ХОББИ И УВЛЕЧЕНИЯ' : 'HOBBIES', val: '', ph: '', area: true, half: false },
  { lbl: lang === 'ru' ? 'ИНТЕРЕСЫ / ТЕМЫ ДЛЯ РАЗГОВОРА' : 'INTERESTS', val: '', ph: '', area: true, half: false },
  { lbl: lang === 'ru' ? 'ОБРАЗ ЖИЗНИ' : 'LIFESTYLE', val: '', ph: '', area: true, half: false },
  { lbl: lang === 'ru' ? 'СТИЛЬ ПЕРЕПИСКИ' : 'CHAT STYLE', val: '', ph: '', area: true, half: false },
  { lbl: lang === 'ru' ? 'ПРЕДЫСТОРИЯ' : 'BACKSTORY', val: '', ph: '', area: true, half: false },
];


function useActiveChar() {
  const { s, cabinet } = useApp();
  const charId = s.charDetail;
  const model = (cabinet.models || []).find((m) => String(m.id) === String(charId));
  return { charId, model, cabinet };
}

/* ── list view ───────────────────────────────────────────── */
function CharacterList() {
  const { t, lang, setS, cabinet } = useApp();
  const [createOpen, setCreateOpen] = useState(false);
  const [createName, setCreateName] = useState('');
  const charactersData = (cabinet.models || []).map((m) => mapCharacter(m, lang));

  const handleCreate = () => {
    const name = createName.trim();
    if (!name) return;
    void cabinet.createCharacter(name).then((data) => {
      setCreateOpen(false);
      setCreateName('');
      if (data?.id) setS({ charDetail: String(data.id), charTab: 'photos' });
    });
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 14, flexWrap: 'wrap', marginBottom: 16 }}>
        <div>
          <PageTitle style={{ marginBottom: 5 }}>{t.navCharacters}</PageTitle>
          <div style={{ fontSize: 12.5, color: color.textDim, maxWidth: 560, lineHeight: 1.5 }}>{t.charactersDesc}</div>
        </div>
        <LimeButton onClick={() => { setCreateName(''); setCreateOpen(true); }}>
          + {t.newCharacter}
        </LimeButton>
      </div>

      <CharacterCreateModal
        open={createOpen}
        name={createName}
        setName={setCreateName}
        onClose={() => setCreateOpen(false)}
        onCreate={handleCreate}
        t={t}
        lang={lang}
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(240px,1fr))', gap: 12 }}>
        {charactersData.map((p) => (
          <Hoverable
            key={p.id}
            style={{
              background: color.surface, border: `1px solid ${line.hair}`,
              borderRadius: 16, overflow: 'hidden', cursor: 'pointer',
            }}
            hover={{ borderColor: 'rgba(240,168,200,.45)' }}
            onClick={() => setS({ charDetail: p.id })}
          >
            <div style={{ height: 110, display: 'flex', alignItems: 'center', justifyContent: 'center', background: p.grad }}>
              <div
                style={{
                  width: 56, height: 56, borderRadius: '50%', background: 'rgba(0,0,0,.35)',
                  border: '2px solid rgba(255,255,255,.5)', display: 'flex',
                  alignItems: 'center', justifyContent: 'center',
                  fontFamily: font.display, fontWeight: 600, fontSize: 20, color: '#fff',
                }}
              >
                {p.initial}
              </div>
            </div>
            <div style={{ padding: '14px 16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <span style={{ fontWeight: 800, fontSize: 15 }}>{p.name}</span>
                <StatusChip tone={p.tone}>{p.status}</StatusChip>
              </div>
              <div style={{ fontSize: 11.5, color: color.textDim, lineHeight: 1.45, marginBottom: 10 }}>{p.blurb}</div>
              <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                {p.tags.map((tg) => (
                  <span
                    key={tg}
                    style={{
                      fontFamily: font.mono, fontSize: 8.5, color: color.textDim,
                      border: '1px solid rgba(255,255,255,.1)', padding: '2px 8px', borderRadius: 20,
                    }}
                  >
                    {tg}
                  </span>
                ))}
              </div>
            </div>
          </Hoverable>
        ))}
      </div>

      <div
        style={{
          marginTop: 16, background: 'rgba(192,132,252,.06)', border: '1px solid rgba(192,132,252,.2)',
          borderRadius: 12, padding: '12px 16px', fontSize: 11.5, color: color.textMid, lineHeight: 1.55,
        }}
      >
        <b style={{ color: color.purple }}>{t.namingTitle}</b> — {t.namingBody}
      </div>
    </div>
  );
}

/* ── detail: photos & look ───────────────────────────────── */
function TabPhotos() {
  const { t, lang, s, setS } = useApp();
  const { charId, model, cabinet } = useActiveChar();
  const uploadRef = useRef(null);
  const [profileText, setProfileText] = useState('');
  const [profileGenState, setProfileGenState] = useState('idle');
  const [selectedPhotoKind, setSelectedPhotoKind] = useState('face');
  const tagOpts = photoTagDefs(lang);
  const images = model?.images || [];

  useEffect(() => {
    setProfileText(model?.profile_text || '');
  }, [charId, model?.profile_text]);

  useEffect(() => {
    setSelectedPhotoKind('face');
  }, [charId]);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))', gap: 12 }}>
      <Panel style={{ padding: '16px 18px' }}>
        <CharacterGenPanel charId={charId} cabinet={cabinet} />
        <div style={{ fontWeight: 800, fontSize: 13.5, marginBottom: 10 }}>{t.charPhotos}</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8, marginBottom: 10 }}>
          {images.map((im, i) => (
            <div
              key={im.id}
              style={{
                aspectRatio: '3/4', borderRadius: 10, display: 'flex', flexDirection: 'column',
                alignItems: 'stretch', justifyContent: 'space-between', padding: 6,
                position: 'relative', background: im.url ? `url(${im.url}) center/cover` : G[i % G.length],
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <Hoverable
                  as="span"
                  style={{
                    width: 22, height: 22, borderRadius: 7, background: 'rgba(0,0,0,.55)',
                    color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 13, fontWeight: 800, cursor: 'pointer',
                  }}
                  hover={{ background: 'rgba(0,0,0,.8)' }}
                  onClick={() => setS({ photoMenu: String(s.photoMenu) === String(im.id) ? null : im.id })}
                  aria-label={t.setTag}
                >
                  ⋯
                </Hoverable>
              </div>
              <span
                style={{
                  fontFamily: font.mono, fontSize: 7.5, background: 'rgba(0,0,0,.6)',
                  color: '#fff', padding: '2px 6px', borderRadius: 4, alignSelf: 'flex-start',
                }}
              >
                {photoKindShortLabel(lang, im.kind)}
              </span>

              {String(s.photoMenu) === String(im.id) && (
                <div
                  style={{
                    position: 'absolute', inset: 0, background: 'rgba(6,7,9,.92)', borderRadius: 10,
                    padding: 8, display: 'flex', flexDirection: 'column', gap: 3, overflowY: 'auto',
                  }}
                >
                  <div style={{ fontFamily: font.mono, fontSize: 8, letterSpacing: '1.2px', color: color.textMuted, marginBottom: 2 }}>
                    {t.setTag}
                  </div>
                  {tagOpts.map((tg) => (
                    <Hoverable
                      key={tg.kind}
                      style={{
                        fontSize: 10.5, fontWeight: 700, padding: '5px 10px', borderRadius: 7,
                        cursor: 'pointer', textAlign: 'left',
                        ...(tg.kind === normalizePhotoKind(im.kind)
                          ? { background: 'rgba(215,244,82,.15)', color: color.lime, border: `1px solid rgba(215,244,82,.35)` }
                          : { color: color.textDim, border: `1px solid ${line.strong}` }),
                      }}
                      hover={{
                        borderColor: tg.kind === normalizePhotoKind(im.kind) ? borderHoverLime : borderHoverOff,
                      }}
                      onClick={() => {
                        void cabinet.updateCharacterPhotoKind(charId, im.id, tg.kind).then(() => {
                          setS({ photoMenu: null });
                        });
                      }}
                    >
                      {tg.label}
                    </Hoverable>
                  ))}
                  <Hoverable
                    style={{
                      marginTop: 'auto', fontSize: 10.5, fontWeight: 800, color: color.red,
                      padding: '5px 10px', borderRadius: 7, border: '1px solid rgba(248,113,113,.3)',
                      textAlign: 'center', cursor: 'pointer',
                    }}
                    hover={{ background: 'rgba(248,113,113,.1)' }}
                    onClick={() => {
                      void cabinet.deleteCharacterPhoto(charId, im.id);
                      setS({ photoMenu: null });
                    }}
                  >
                    🗑 {t.deletePhoto}
                  </Hoverable>
                </div>
              )}
            </div>
          ))}

          <input
            ref={uploadRef}
            type="file"
            accept="image/*"
            style={{ display: 'none' }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file && charId) void cabinet.uploadCharacterPhoto(charId, file, selectedPhotoKind);
              e.target.value = '';
            }}
          />
          <Hoverable
            style={{
              aspectRatio: '3/4', border: `1.5px dashed ${line.dashed}`, borderRadius: 10,
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              gap: 4, color: color.textMuted, cursor: 'pointer',
            }}
            hover={{ borderColor: 'rgba(215,244,82,.5)' }}
            onClick={() => uploadRef.current?.click()}
          >
            <span style={{ display: 'flex', width: 18, height: 18 }}><IcoUpload /></span>
            <span style={{ fontSize: 9.5, fontWeight: 700 }}>{t.addPhoto}</span>
          </Hoverable>
        </div>

        <div style={{ fontFamily: font.mono, fontSize: 9, letterSpacing: '1.6px', color: color.textMuted, margin: '6px 0 7px' }}>
          {t.photoTags}
        </div>
        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
          {tagOpts.map((tg) => (
            <Chip
              key={tg.kind}
              on={selectedPhotoKind === tg.kind}
              onClick={() => setSelectedPhotoKind(tg.kind)}
            >
              {tg.label}
            </Chip>
          ))}
        </div>
      </Panel>

      <Panel style={{ padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontWeight: 800, fontSize: 13.5 }}>{t.charAppearance}</span>
          <Hoverable
            as="span"
            style={{ fontSize: 11, fontWeight: 700, color: color.purple, cursor: 'pointer' }}
            hover={{ color: color.purpleHi }}
            onClick={() => {
              const tagged = images.filter((im) => {
                const k = normalizePhotoKind(im.kind);
                return k === 'face' || k === 'body';
              });
              const pool = tagged.length ? tagged : images;
              if (!pool.length) return;
              setProfileGenState('loading');
              void cabinet.generateCharacterProfile(pool).then((data) => {
                if (data?.profile_text) setProfileText(String(data.profile_text));
                setProfileGenState('done');
              }).catch(() => setProfileGenState('idle'));
            }}
          >
            {profileGenState === 'loading' ? '…' : profileGenState === 'done' ? t.profileGenDone : `✦ ${t.genFromPhoto}`}
          </Hoverable>
        </div>
        <textarea
          rows={6}
          value={profileText}
          onChange={(e) => setProfileText(e.target.value)}
          aria-label={t.charAppearance}
          style={{
            width: '100%', background: color.bgPanel, border: `1px solid ${line.soft}`,
            borderRadius: 10, padding: '10px 12px', color: color.textMid,
            fontFamily: font.body, fontSize: 12, lineHeight: 1.55, resize: 'vertical', outline: 'none',
          }}
        />
        <div style={{ display: 'flex', gap: 8 }}>
          <Hoverable
            style={{
              flex: 1, background: 'rgba(215,244,82,.12)', border: '1px solid rgba(215,244,82,.3)',
              borderRadius: 9, padding: 9, textAlign: 'center', fontSize: 12,
              fontWeight: 800, color: color.lime, cursor: 'pointer',
            }}
            hover={{ background: 'rgba(215,244,82,.2)' }}
            onClick={() => charId && void cabinet.saveCharacterProfile(charId, profileText.trim())}
          >
            {t.save}
          </Hoverable>
          <Hoverable
            style={{
              border: '1px solid rgba(248,113,113,.3)', borderRadius: 9, padding: '9px 14px',
              fontSize: 12, fontWeight: 700, color: color.red, cursor: 'pointer',
            }}
            hover={{ background: 'rgba(248,113,113,.08)' }}
            onClick={() => {
              if (!charId || !model) return;
              if (!window.confirm(`${t.delete} «${model.name}»?`)) return;
              void cabinet.deleteCharacter(charId).then(() => setS({ charDetail: null }));
            }}
          >
            {t.delete}
          </Hoverable>
        </div>
      </Panel>
    </div>
  );
}

/* ── detail: persona ─────────────────────────────────────── */
function TabPersona() {
  const { t, lang } = useApp();
  const { charId, model, cabinet } = useActiveChar();
  const [persona, setPersona] = useState({});

  useEffect(() => {
    const p = model?.companion_persona || {};
    setPersona({
      age: p.age ?? '',
      city: p.city ?? '',
      country: p.country ?? '',
      timezone: p.timezone ?? '',
      personality: p.personality ?? '',
      hobbies: p.hobbies ?? '',
      interests: p.interests ?? '',
      lifestyle: p.lifestyle ?? '',
      speaking_style: p.speaking_style ?? '',
      backstory: p.backstory ?? '',
    });
  }, [charId, model?.companion_persona]);

  const fields = personaFieldDefs(lang);
  const keys = ['age', 'city', 'country', 'timezone', 'personality', 'hobbies', 'interests', 'lifestyle', 'speaking_style', 'backstory'];

  const savePersona = () => {
    if (!charId) return;
    const trim = (v) => String(v ?? '').trim();
    const out = {
      age: trim(persona.age) || null,
      city: trim(persona.city) || null,
      country: trim(persona.country) || null,
      timezone: trim(persona.timezone) || null,
      personality: trim(persona.personality) || null,
      hobbies: trim(persona.hobbies) || null,
      interests: trim(persona.interests) || null,
      lifestyle: trim(persona.lifestyle) || null,
      speaking_style: trim(persona.speaking_style) || null,
      backstory: trim(persona.backstory) || null,
    };
    void cabinet.saveCharacterPersona(charId, out);
  };

  return (
    <Panel style={{ padding: 18, maxWidth: 560 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        {fields.map((pf, i) => (
          <Field
            key={pf.lbl}
            label={pf.lbl}
            value={persona[keys[i]] ?? ''}
            onChange={(e) => setPersona({ ...persona, [keys[i]]: e.target.value })}
            placeholder={pf.ph}
            area={pf.area}
            style={pf.half ? undefined : { gridColumn: '1 / -1' }}
          />
        ))}
      </div>
      <Hoverable
        style={{
          marginTop: 14, background: 'rgba(215,244,82,.12)', border: '1px solid rgba(215,244,82,.3)',
          borderRadius: 9, padding: 10, textAlign: 'center', fontSize: 12,
          fontWeight: 800, color: color.lime, cursor: 'pointer',
        }}
        hover={{ background: 'rgba(215,244,82,.2)' }}
        onClick={savePersona}
      >
        {t.save}
      </Hoverable>
    </Panel>
  );
}

/* ── detail: EXIF ────────────────────────────────────────── */
function TabExif() {
  const { t, lang, s, setS, cabinet } = useApp();
  const { charId, model } = useActiveChar();
  const selfieRef = useRef(null);
  const mainRef = useRef(null);
  const presets = cabinet.cameraPresets || [];
  const noneLabel = lang === 'ru' ? '— не применять —' : '— none —';
  const camPreset = s.exifPreset ?? model?.camera_preset_id ?? '';
  const latVal = s.exifLat ?? (model?.export_lat != null ? String(model.export_lat) : '');
  const lonVal = s.exifLon ?? (model?.export_lon != null ? String(model.export_lon) : '');

  const FilePick = ({ label, hint, role, ready, summary, inputRef }) => (
    <div>
      <div style={fieldLbl}>{label}</div>
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/jpg"
        style={{ display: 'none' }}
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = '';
          if (!file || !charId) return;
          void cabinet.uploadPhoneExif(charId, role, file);
        }}
      />
      <Hoverable
        style={{
          display: 'flex', alignItems: 'center', gap: 8, border: `1px solid ${ready ? 'rgba(74,222,128,.4)' : line.mid}`,
          borderRadius: 9, padding: '8px 10px', cursor: 'pointer',
          ...(ready ? { background: 'rgba(74,222,128,.06)' } : {}),
        }}
        hover={{ borderColor: 'rgba(215,244,82,.4)' }}
        onClick={() => inputRef.current?.click()}
      >
        <span style={{ display: 'flex', width: 15, height: 15, color: color.textDim }}><IcoUpload /></span>
        <span style={{ fontSize: 11.5, color: ready ? color.lime : color.textDim }}>
          {ready ? (summary || t.chooseFile) : t.chooseFile}
        </span>
      </Hoverable>
      <div style={{ display: 'flex', gap: 8, marginTop: 5, flexWrap: 'wrap' }}>
        <div style={{ fontSize: 9.5, color: color.textGhost, flex: 1 }}>{hint}</div>
        {ready && (
          <Hoverable
            as="span"
            style={{ fontSize: 9.5, fontWeight: 700, color: color.red, cursor: 'pointer' }}
            hover={{ opacity: 0.8 }}
            onClick={() => charId && void cabinet.deletePhoneExif(charId, role)}
          >
            {t.delete}
          </Hoverable>
        )}
      </div>
    </div>
  );

  const saveExif = () => {
    if (!charId) return;
    const patch = {};
    const preset = camPreset || null;
    patch.camera_preset_id = preset;
    const lat = latVal.trim();
    const lon = lonVal.trim();
    patch.export_lat = lat === '' ? null : Number(lat);
    patch.export_lon = lon === '' ? null : Number(lon);
    void cabinet.saveCharacterExif(charId, patch).then(() => {
      setS({ exifPreset: undefined, exifLat: undefined, exifLon: undefined });
    });
  };

  return (
    <Panel style={{ padding: 18 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 14, flexWrap: 'wrap', marginBottom: 14 }}>
        <div style={{ fontWeight: 800, fontSize: 14 }}>{t.exifTitle}</div>
        <div style={{ fontSize: 11, color: color.textDim, maxWidth: 420, lineHeight: 1.5 }}>{t.exifHint}</div>
      </div>

      <div style={{ background: color.bgPanel, border: `1px solid ${line.hair}`, borderRadius: 12, padding: 14, marginBottom: 14 }}>
        <div style={{ fontWeight: 700, fontSize: 12.5, marginBottom: 10 }}>{t.exifRefs}</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <FilePick
            label={t.frontCam}
            hint={`JPEG ${t.fromGallery}`}
            role="selfie"
            ready={model?.phone_exif_selfie_ready}
            summary={model?.phone_exif_selfie_summary}
            inputRef={selfieRef}
          />
          <FilePick
            label={t.mainCam}
            hint={t.backCamPhoto}
            role="main"
            ready={model?.phone_exif_main_ready}
            summary={model?.phone_exif_main_summary}
            inputRef={mainRef}
          />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div>
          <div style={fieldLbl}>{t.camPreset}</div>
          <select
            value={camPreset}
            onChange={(e) => setS({ exifPreset: e.target.value })}
            style={selectSt}
          >
            <option value="">{noneLabel}</option>
            {presets.map((p) => (
              <option key={p.id} value={p.id}>{p.label}</option>
            ))}
          </select>
        </div>
        <div>
          <div style={fieldLbl}>{t.latGeo}</div>
          <input value={latVal} onChange={(e) => setS({ exifLat: e.target.value })} style={inputSt} aria-label={t.latGeo} />
        </div>
        <div>
          <div style={fieldLbl}>{t.lonGeo}</div>
          <input value={lonVal} onChange={(e) => setS({ exifLon: e.target.value })} style={inputSt} aria-label={t.lonGeo} />
        </div>
      </div>

      <Hoverable
        style={{
          marginTop: 14, background: 'rgba(215,244,82,.12)', border: '1px solid rgba(215,244,82,.3)',
          borderRadius: 9, padding: 10, textAlign: 'center', fontSize: 12,
          fontWeight: 800, color: color.lime, cursor: 'pointer', maxWidth: 200,
        }}
        hover={{ background: 'rgba(215,244,82,.2)' }}
        onClick={saveExif}
      >
        {t.save}
      </Hoverable>
    </Panel>
  );
}

/* ── detail: history ─────────────────────────────────────── */
function TabHistory() {
  const { t, lang, s, cabinet } = useApp();
  const rows = mapCharHistory(s.charDetail, cabinet.archiveImages, lang);

  return (
    <Panel style={{ padding: '16px 18px', maxWidth: 640 }}>
      <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 12 }}>{t.charHistoryTitle}</div>
      {rows.length === 0 && (
        <div style={{ fontSize: 12, color: color.textDim }}>{lang === 'ru' ? 'Пока нет генераций' : 'No generations yet'}</div>
      )}
      {rows.map((hr, i) => {
        const Icon = histIcons[hr.icon];
        return (
          <div
            key={i}
            style={{
              display: 'flex', alignItems: 'center', gap: 12, padding: '11px 4px',
              borderBottom: '1px solid rgba(255,255,255,.05)',
            }}
          >
            <span style={{ display: 'flex', width: 16, height: 16, color: color.textDim, flex: 'none' }}><Icon /></span>
            <span style={{ flex: 1, fontSize: 12.5, color: color.textMid }}>{hr.what}</span>
            <span style={{ fontFamily: font.mono, fontSize: 9.5, color: color.textGhost }}>{hr.when}</span>
            <span style={{ fontFamily: font.mono, fontSize: 10, color: color.lime, width: 56, textAlign: 'right' }}>{hr.tag}</span>
          </div>
        );
      })}
    </Panel>
  );
}

/* ── detail shell ────────────────────────────────────────── */
function CharacterDetail() {
  const { t, lang, s, setS } = useApp();
  const { model } = useActiveChar();
  const mapped = model ? mapCharacter(model, lang) : null;

  const tabs = charTabDefs(lang);
  const TabBody = {
    photos: TabPhotos, persona: TabPersona, exif: TabExif, history: TabHistory,
  }[s.charTab];

  return (
    <div>
      <BackLink onClick={() => setS({ charDetail: null })}>{t.allCharacters}</BackLink>

      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 18 }}>
        <div
          style={{
            width: 52, height: 52, borderRadius: 16,
            background: mapped?.grad || 'linear-gradient(135deg,#F472B6,#C084FC)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: font.display, fontWeight: 600, fontSize: 20, color: '#2A0A1C',
          }}
        >
          {mapped?.initial || '?'}
        </div>
        <div>
          <PageTitle>{mapped?.name || '—'}</PageTitle>
          <div style={{ fontSize: 11.5, color: color.textDim }}>{t.charSub}</div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 16 }} role="tablist">
        {tabs.map((ct) => (
          <Chip key={ct.id} on={s.charTab === ct.id} onClick={() => setS({ charTab: ct.id })} role="tab">
            {ct.label}
          </Chip>
        ))}
      </div>

      <TabBody />
    </div>
  );
}

export default function Characters() {
  const { s } = useApp();
  return (
    <Fade data-screen-label="Персонажи">
      {s.charDetail ? <CharacterDetail /> : <CharacterList />}
    </Fade>
  );
}

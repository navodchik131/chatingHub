import Hoverable from '../components/Hoverable';
import { IcoUpload, IcoImage, IcoFace, IcoFilm, IcoStar } from '../components/Icons';
import {
  Fade, PageTitle, StatusChip, Chip, BackLink, LimeButton, Field, Panel,
} from '../components/ui';
import { useApp } from '../hooks/useApp';
import { color, line, font, G } from '../styles/tokens';
import { fieldLbl, inputSt } from '../styles/mixins';
import {
  charactersData, charTabDefs, photoTagNames, charPhotoKinds,
  personaFieldDefs, exifPresets, historyRowsData,
} from '../data/mock';

const histIcons = { image: IcoImage, face: IcoFace, film: IcoFilm, star: IcoStar };

/* ── list view ───────────────────────────────────────────── */
function CharacterList() {
  const { t, lang, setS } = useApp();

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 14, flexWrap: 'wrap', marginBottom: 16 }}>
        <div>
          <PageTitle style={{ marginBottom: 5 }}>{t.navCharacters}</PageTitle>
          <div style={{ fontSize: 12.5, color: color.textDim, maxWidth: 560, lineHeight: 1.5 }}>{t.charactersDesc}</div>
        </div>
        <LimeButton>+ {t.newCharacter}</LimeButton>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(240px,1fr))', gap: 12 }}>
        {charactersData(lang).map((p) => (
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
  const kinds = charPhotoKinds(lang);
  const tagOpts = photoTagNames(lang);
  const photos = [G[1], G[3], G[4], G[0], G[2]];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))', gap: 12 }}>
      <Panel style={{ padding: '16px 18px' }}>
        <div style={{ fontWeight: 800, fontSize: 13.5, marginBottom: 10 }}>{t.charPhotos}</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8, marginBottom: 10 }}>
          {photos.map((g, i) => (
            <div
              key={i}
              style={{
                aspectRatio: '3/4', borderRadius: 10, display: 'flex', flexDirection: 'column',
                alignItems: 'stretch', justifyContent: 'space-between', padding: 6,
                position: 'relative', background: g,
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
                  onClick={() => setS({ photoMenu: s.photoMenu === i ? null : i })}
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
                {kinds[i]}
              </span>

              {s.photoMenu === i && (
                <div
                  style={{
                    position: 'absolute', inset: 0, background: 'rgba(6,7,9,.92)', borderRadius: 10,
                    padding: 8, display: 'flex', flexDirection: 'column', gap: 3, overflowY: 'auto',
                  }}
                >
                  <div style={{ fontFamily: font.mono, fontSize: 7.5, letterSpacing: '.8px', color: color.textMuted, marginBottom: 2 }}>
                    {t.setTag}
                  </div>
                  {tagOpts.map((l, j) => (
                    <Hoverable
                      key={l}
                      style={{
                        fontSize: 11, fontWeight: 700, padding: '5px 10px', borderRadius: 7, cursor: 'pointer',
                        ...(j === 0 ? { background: 'rgba(215,244,82,.15)', color: color.lime } : { color: color.textMid }),
                      }}
                      hover={{ background: 'rgba(255,255,255,.08)' }}
                    >
                      {l}
                    </Hoverable>
                  ))}
                  <Hoverable
                    style={{
                      marginTop: 'auto', fontSize: 10.5, fontWeight: 800, color: color.red,
                      padding: '5px 10px', borderRadius: 7, border: '1px solid rgba(248,113,113,.3)',
                      textAlign: 'center', cursor: 'pointer',
                    }}
                    hover={{ background: 'rgba(248,113,113,.1)' }}
                    onClick={() => setS({ photoMenu: null })}
                  >
                    🗑 {t.deletePhoto}
                  </Hoverable>
                </div>
              )}
            </div>
          ))}

          <Hoverable
            style={{
              aspectRatio: '3/4', border: `1.5px dashed ${line.dashed}`, borderRadius: 10,
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              gap: 4, color: color.textMuted, cursor: 'pointer',
            }}
            hover={{ borderColor: 'rgba(215,244,82,.5)' }}
          >
            <span style={{ display: 'flex', width: 18, height: 18 }}><IcoUpload /></span>
            <span style={{ fontSize: 9.5, fontWeight: 700 }}>{t.addPhoto}</span>
          </Hoverable>
        </div>

        <div style={{ fontFamily: font.mono, fontSize: 9, letterSpacing: '1.6px', color: color.textMuted, margin: '6px 0 7px' }}>
          {t.photoTags}
        </div>
        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
          {tagOpts.map((l, i) => (
            <Chip key={l} on={i === 0}>{l}</Chip>
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
          >
            ✦ {t.genFromPhoto}
          </Hoverable>
        </div>
        <textarea
          rows={6}
          defaultValue="Slim athletic feminine body, long dark hair, green eyes, soft natural makeup…"
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
          >
            {t.save}
          </Hoverable>
          <Hoverable
            style={{
              border: '1px solid rgba(248,113,113,.3)', borderRadius: 9, padding: '9px 14px',
              fontSize: 12, fontWeight: 700, color: color.red, cursor: 'pointer',
            }}
            hover={{ background: 'rgba(248,113,113,.08)' }}
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

  return (
    <Panel style={{ padding: 18, maxWidth: 560 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        {personaFieldDefs(lang).map((pf) => (
          <Field
            key={pf.lbl}
            label={pf.lbl}
            value={pf.val}
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
      >
        {t.save}
      </Hoverable>
    </Panel>
  );
}

/* ── detail: EXIF ────────────────────────────────────────── */
function TabExif() {
  const { t, lang } = useApp();

  const FilePick = ({ label, hint }) => (
    <div>
      <div style={fieldLbl}>{label}</div>
      <Hoverable
        style={{
          display: 'flex', alignItems: 'center', gap: 8, border: `1px solid ${line.mid}`,
          borderRadius: 9, padding: '8px 10px', cursor: 'pointer',
        }}
        hover={{ borderColor: 'rgba(215,244,82,.4)' }}
      >
        <span style={{ display: 'flex', width: 15, height: 15, color: color.textDim }}><IcoUpload /></span>
        <span style={{ fontSize: 11.5, color: color.textDim }}>{t.chooseFile}</span>
      </Hoverable>
      <div style={{ fontSize: 9.5, color: color.textGhost, marginTop: 5 }}>{hint}</div>
    </div>
  );

  return (
    <Panel style={{ padding: 18 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 14, flexWrap: 'wrap', marginBottom: 14 }}>
        <div style={{ fontWeight: 800, fontSize: 14 }}>{t.exifTitle}</div>
        <div style={{ fontSize: 11, color: color.textDim, maxWidth: 420, lineHeight: 1.5 }}>{t.exifHint}</div>
      </div>

      <div style={{ background: color.bgPanel, border: `1px solid ${line.hair}`, borderRadius: 12, padding: 14, marginBottom: 14 }}>
        <div style={{ fontWeight: 700, fontSize: 12.5, marginBottom: 10 }}>{t.exifRefs}</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <FilePick label={t.frontCam} hint={`JPEG ${t.fromGallery}`} />
          <FilePick label={t.mainCam} hint={t.backCamPhoto} />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div>
          <div style={fieldLbl}>{t.camPreset}</div>
          <Hoverable
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              border: '1px solid rgba(215,244,82,.4)', borderRadius: 10,
              padding: '9px 12px', cursor: 'pointer', fontSize: 12.5,
            }}
            hover={{ borderColor: color.lime }}
          >
            {exifPresets(lang)[0]}
            <span style={{ color: color.textMuted }}>▾</span>
          </Hoverable>
        </div>
        <div>
          <div style={fieldLbl}>{t.latGeo}</div>
          <input defaultValue="55.7558" style={inputSt} aria-label={t.latGeo} />
        </div>
        <div>
          <div style={fieldLbl}>{t.lonGeo}</div>
          <input defaultValue="37.6173" style={inputSt} aria-label={t.lonGeo} />
        </div>
      </div>

      <Hoverable
        style={{
          marginTop: 14, background: 'rgba(215,244,82,.12)', border: '1px solid rgba(215,244,82,.3)',
          borderRadius: 9, padding: 10, textAlign: 'center', fontSize: 12,
          fontWeight: 800, color: color.lime, cursor: 'pointer', maxWidth: 200,
        }}
        hover={{ background: 'rgba(215,244,82,.2)' }}
      >
        {t.save}
      </Hoverable>
    </Panel>
  );
}

/* ── detail: history ─────────────────────────────────────── */
function TabHistory() {
  const { t, lang } = useApp();

  return (
    <Panel style={{ padding: '16px 18px', maxWidth: 640 }}>
      <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 12 }}>{t.charHistoryTitle}</div>
      {historyRowsData(lang).map((hr, i) => {
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
            background: 'linear-gradient(135deg,#F472B6,#C084FC)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: font.display, fontWeight: 600, fontSize: 20, color: '#2A0A1C',
          }}
        >
          M
        </div>
        <div>
          <PageTitle>Mia</PageTitle>
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
  const { charDetail } = useApp();
  return (
    <Fade data-screen-label="Персонажи">
      {charDetail ? <CharacterDetail /> : <CharacterList />}
    </Fade>
  );
}

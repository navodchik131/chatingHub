import Hoverable from '../components/Hoverable';
import { IcoTg, IcoWave, IcoHeart, IcoGift, IcoCam, IcoBell, IcoCopy } from '../components/Icons';
import {
  Fade, PageTitle, StatusChip, Panel, BackLink, IconBox, Field, SelectBox, Toggle, NoteBlock,
} from '../components/ui';
import { useApp } from '../hooks/useApp';
import { color, line, font } from '../styles/tokens';
import { connDefs, connFieldSets, curConfigMap } from '../data/catalog';

const connIcons = { tg: IcoTg, wave: IcoWave, heart: IcoHeart, gift: IcoGift, cam: IcoCam, bell: IcoBell };

function ConnectionList() {
  const { t, lang, setS } = useApp();

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <PageTitle style={{ marginBottom: 5 }}>{t.navConnections}</PageTitle>
        <div style={{ fontSize: 12.5, color: color.textDim }}>{t.connectionsDesc}</div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))', gap: 12 }}>
        {connDefs(lang).map((c) => {
          const Icon = connIcons[c.icon];
          return (
            <Hoverable
              key={c.id}
              style={{
                background: color.surface, border: `1px solid ${line.hair}`, borderRadius: 16,
                padding: '16px 18px', cursor: 'pointer', display: 'flex', gap: 14, alignItems: 'flex-start',
              }}
              hover={{ borderColor: 'rgba(255,255,255,.2)', background: color.surfaceHi }}
              onClick={() => setS({ connDetail: c.id })}
            >
              <IconBox size={38} iconSize={18} tint={c.iconCol}><Icon /></IconBox>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 800, fontSize: 14 }}>{c.name}</span>
                  <StatusChip tone={c.tone} style={{ display: 'inline-block', marginTop: 3 }}>{c.st}</StatusChip>
                </div>
                <div style={{ fontSize: 11.5, color: color.textDim, lineHeight: 1.5, marginTop: 4 }}>{c.desc}</div>
              </div>
            </Hoverable>
          );
        })}
      </div>
    </div>
  );
}

function ConnectionDetail() {
  const { t, lang, s, setS } = useApp();

  const defs = connDefs(lang);
  const data = defs.find((c) => c.id === s.connDetail) || defs[0];
  const cfs = connFieldSets(lang)[data.id] || connFieldSets(lang).tg;
  const current = (curConfigMap(lang)[data.id] || []).map((kv) => ({ k: kv[0], v: kv[1] }));
  const list = cfs.list || [];
  const hasCopy = ['fanvue', 'tribute'].includes(data.id);
  const Icon = connIcons[data.icon];

  return (
    <div>
      <BackLink onClick={() => setS({ connDetail: null })}>{t.allConnections}</BackLink>

      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 16 }}>
        <IconBox size={48} iconSize={22} tint={data.iconCol} style={{ borderRadius: 14 }}><Icon /></IconBox>
        <div>
          <PageTitle size={19}>{data.name}</PageTitle>
          <div style={{ fontSize: 11.5, color: color.textDim }}>{data.desc}</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(290px,1fr))', gap: 12 }}>
        {/* settings */}
        <Panel style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ fontWeight: 800, fontSize: 13.5 }}>{cfs.title}</div>

          {current.length > 0 && (
            <div style={{ background: 'rgba(74,222,128,.05)', border: '1px solid rgba(74,222,128,.2)', borderRadius: 12, padding: '12px 14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 9 }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: color.green }} />
                <span style={{ fontFamily: font.mono, fontSize: 9, letterSpacing: '1.4px', color: color.green }}>{t.curConfig}</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '7px 14px' }}>
                {current.map((cc) => (
                  <div key={cc.k} style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 11 }}>
                    <span style={{ color: color.textMuted }}>{cc.k}</span>
                    <span style={{ fontWeight: 700, color: color.textMid, textAlign: 'right' }}>{cc.v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {list.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {list.map((cl) => (
                <div
                  key={cl.name}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10, background: color.bgPanel,
                    border: `1px solid ${line.hair}`, borderRadius: 10, padding: '9px 12px',
                  }}
                >
                  <span style={{ width: 7, height: 7, borderRadius: '50%', background: color.green, flex: 'none' }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 700, fontSize: 12 }}>{cl.name}</div>
                    <div style={{ fontSize: 10, color: color.textMuted }}>{cl.meta}</div>
                  </div>
                  <Hoverable
                    as="span"
                    style={{ fontSize: 11, fontWeight: 700, color: color.textDim, cursor: 'pointer' }}
                    hover={{ color: color.red }}
                  >
                    {t.disconnect}
                  </Hoverable>
                </div>
              ))}
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {cfs.fields.map((f, i) => {
              const wrap = f.half ? undefined : { gridColumn: '1 / -1' };
              if (f.kind === 'text') {
                return <Field key={i} label={f.lbl} value={f.val} placeholder={f.ph} style={wrap} />;
              }
              if (f.kind === 'select') {
                return <SelectBox key={i} label={f.lbl} value={f.val} style={wrap} />;
              }
              if (f.kind === 'toggle') {
                return (
                  <div key={i} style={{ ...wrap, display: 'flex', flexDirection: 'column' }}>
                    <div
                      style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        background: color.bgPanel, border: `1px solid ${line.hair}`,
                        borderRadius: 10, padding: '10px 12px',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 700, fontSize: 12 }}>{f.lbl}</div>
                        <div style={{ fontSize: 10, color: color.textMuted }}>{f.sub}</div>
                      </div>
                      <Toggle on={f.on} />
                    </div>
                  </div>
                );
              }
              return (
                <div key={i} style={{ ...wrap, display: 'flex', flexDirection: 'column' }}>
                  <NoteBlock>{f.text}</NoteBlock>
                </div>
              );
            })}
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            <Hoverable
              style={{
                flex: 1, textAlign: 'center', borderRadius: 9, padding: 10, fontSize: 12,
                fontWeight: 800, cursor: 'pointer',
                ...(cfs.disabled
                  ? { background: 'rgba(255,255,255,.06)', color: color.textGhost }
                  : { background: 'linear-gradient(120deg,#C084FC,#F0A8C8)', color: color.purpleInk }),
              }}
              hover={cfs.disabled ? {} : { filter: 'brightness(1.08)' }}
            >
              {cfs.prim}
            </Hoverable>
            {hasCopy && (
              <Hoverable
                style={{
                  display: 'flex', alignItems: 'center', gap: 6, border: `1px solid ${line.mid}`,
                  borderRadius: 9, padding: '9px 12px', fontSize: 12,
                  fontWeight: 700, color: color.textDim, cursor: 'pointer',
                }}
                hover={{ borderColor: line.hover }}
              >
                <span style={{ display: 'flex', width: 13, height: 13 }}><IcoCopy /></span>
                {t.copy}
              </Hoverable>
            )}
          </div>
        </Panel>

        {/* help */}
        <Panel style={{ padding: 18 }}>
          <div style={{ fontWeight: 800, fontSize: 13.5, marginBottom: 10 }}>{t.howItWorks}</div>
          <div style={{ fontSize: 12, color: color.textDim, lineHeight: 1.65 }}>{data.help}</div>
          <div style={{ marginTop: 12 }}>
            <a href="#wiki" style={{ fontSize: 12, fontWeight: 700 }}>{t.wikiGuide} →</a>
          </div>
        </Panel>
      </div>
    </div>
  );
}

export default function Connections() {
  const { connDetail } = useApp();
  return (
    <Fade data-screen-label="Подключения">
      {connDetail ? <ConnectionDetail /> : <ConnectionList />}
    </Fade>
  );
}

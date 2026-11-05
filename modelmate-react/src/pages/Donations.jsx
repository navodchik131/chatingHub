import Hoverable from '../components/Hoverable';
import { IcoTg, IcoGlobe, IcoCopy } from '../components/Icons';
import { Fade, PageTitle, Eyebrow, Chip, StatusChip, Panel, Field } from '../components/ui';
import { useApp } from '../hooks/useApp';
import { color, line, font } from '../styles/tokens';
import { fieldLbl } from '../styles/mixins';
import { donStatsData, donLinksData, incomingData, myDonationsData } from '../data/mock';

const linkIcons = { tg: IcoTg, globe: IcoGlobe };

function DonOverview() {
  const { t, lang } = useApp();

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: 12, marginBottom: 16 }}>
        {donStatsData(lang).map((ds) => (
          <Panel key={ds.label} style={{ borderRadius: 14, padding: '14px 16px' }}>
            <Eyebrow size={9} style={{ marginBottom: 8 }}>{ds.label}</Eyebrow>
            <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 17, color: ds.color }}>{ds.value}</div>
          </Panel>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(300px,1fr))', gap: 12 }}>
        {/* payout */}
        <div
          style={{
            background: 'linear-gradient(140deg,rgba(240,168,200,.1),rgba(240,168,200,.02))',
            border: '1px solid rgba(240,168,200,.3)', borderRadius: 16, padding: '16px 18px',
          }}
        >
          <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 8 }}>{t.payout}</div>
          <div style={{ fontSize: 11.5, color: color.textDim, lineHeight: 1.6, marginBottom: 14 }}>{t.payoutHint}</div>
          <Hoverable
            style={{
              background: 'linear-gradient(120deg,#F0A8C8,#C084FC)', color: color.purpleInk,
              fontWeight: 800, fontSize: 12.5, borderRadius: 10, padding: '10px 16px',
              textAlign: 'center', cursor: 'pointer',
            }}
            hover={{ filter: 'brightness(1.08)' }}
          >
            {t.requestPayout}
          </Hoverable>
          <div style={{ fontSize: 11, color: color.textDim, marginTop: 12 }}>
            {t.holdPolicy} <a href="#policy">Wiki →</a>
          </div>
        </div>

        {/* links */}
        <Panel style={{ padding: '16px 18px' }}>
          <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 12 }}>{t.donLinks}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {donLinksData(lang).map((dl) => (
              <div key={dl.title} style={{ background: color.bgPanel, border: `1px solid ${line.hair}`, borderRadius: 12, padding: '12px 14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <span style={{ fontWeight: 700, fontSize: 12.5 }}>{dl.title}</span>
                  <StatusChip tone={dl.tone}>{dl.st}</StatusChip>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {dl.urls.map((u) => {
                    const Icon = linkIcons[u.icon];
                    return (
                      <div key={u.kind} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ display: 'flex', width: 13, height: 13, color: u.col, flex: 'none' }}><Icon /></span>
                        <span
                          style={{
                            flex: 1, fontFamily: font.mono, fontSize: 10, color: color.textDim,
                            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                          }}
                        >
                          {u.url}
                        </span>
                        <Hoverable
                          as="span"
                          style={{ display: 'flex', width: 13, height: 13, color: color.textMuted, cursor: 'pointer', flex: 'none' }}
                          hover={{ color: color.lime }}
                          aria-label={t.copy}
                        >
                          <IcoCopy />
                        </Hoverable>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </Panel>

        {/* incoming */}
        <Panel style={{ padding: '16px 18px' }}>
          <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 12 }}>{t.lastIncoming}</div>
          {incomingData(lang).map((inc, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 0', borderBottom: '1px solid rgba(255,255,255,.05)' }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 700, fontSize: 12.5, color: color.green }}>{inc.sum}</div>
                <div style={{ fontSize: 11, color: color.textDim }}>{inc.from}</div>
              </div>
              <span style={{ fontFamily: font.mono, fontSize: 9.5, color: color.textGhost }}>{inc.when}</span>
            </div>
          ))}
        </Panel>
      </div>
    </div>
  );
}

function DonCreate() {
  const { t, lang } = useApp();

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(300px,1fr))', gap: 12 }}>
      <Panel style={{ padding: 18 }}>
        <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 12 }}>{t.newDonation}</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Field label={t.donTitle} placeholder={lang === 'ru' ? 'Поддержать Mia 💕' : 'Support Mia 💕'} />
          <Field
            label={t.donDesc}
            area
            rows={3}
            placeholder={lang === 'ru' ? 'За что и на что собираете…' : 'What the donation is for…'}
          />
          <div style={{ maxWidth: 160 }}>
            <Field label={t.minSum} value="500 ₽" />
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
          <Hoverable
            style={{
              background: color.lime, color: color.limeInk, fontWeight: 800, fontSize: 12.5,
              borderRadius: 10, padding: '10px 18px', cursor: 'pointer',
            }}
            hover={{ background: color.limeHi }}
          >
            {t.toModeration}
          </Hoverable>
          <Hoverable
            style={{
              border: `1px solid ${line.mid}`, color: color.textDim, fontWeight: 700,
              fontSize: 12.5, borderRadius: 10, padding: '10px 18px', cursor: 'pointer',
            }}
            hover={{ borderColor: line.hover }}
          >
            {t.saveDraft}
          </Hoverable>
        </div>
      </Panel>

      <Panel style={{ padding: 18 }}>
        <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 12 }}>{t.myDonations}</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {myDonationsData(lang).map((d) => (
            <div
              key={d.title}
              style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10,
                background: color.bgPanel, border: `1px solid ${line.hair}`,
                borderRadius: 12, padding: '11px 14px',
              }}
            >
              <span style={{ fontWeight: 700, fontSize: 12.5 }}>{d.title}</span>
              <StatusChip tone={d.tone}>{d.st}</StatusChip>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

export default function Donations() {
  const { t, s, setS } = useApp();

  return (
    <Fade data-screen-label="Донаты">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 14, flexWrap: 'wrap', marginBottom: 16 }}>
        <div>
          <PageTitle style={{ marginBottom: 5 }}>{t.navDonations}</PageTitle>
          <div style={{ fontSize: 12.5, color: color.textDim }}>{t.donationsDesc}</div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <Chip on={s.donTab === 'overview'} onClick={() => setS({ donTab: 'overview' })}>{t.donTabOverview}</Chip>
          <Chip on={s.donTab === 'create'} onClick={() => setS({ donTab: 'create' })}>{t.donTabCreate}</Chip>
        </div>
      </div>

      {s.donTab === 'overview' ? <DonOverview /> : <DonCreate />}
    </Fade>
  );
}

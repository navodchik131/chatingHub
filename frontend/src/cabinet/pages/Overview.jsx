import Hoverable from '../components/Hoverable';
import { IcoSpark, IcoChat, IcoImage, IcoFilm, IcoStar } from '../components/Icons';
import { Fade, PageTitle, Eyebrow, Panel, Avatar, IconBox, LimeButton } from '../components/ui';
import { useApp } from '../hooks/useApp';
import { color, line, font, avG } from '../styles/tokens';
import { borderHoverOff } from '../styles/mixins';
import { guideDefs } from '../data/catalog';
import { fmtCredits, fmtMoney, fmtToday } from '../api/helpers';
import { mapDialogRow } from '../api/mappers';
import { sumOutboundMessages } from '../api/studioHelpers';
import { archiveThumbUrl } from '../api/actions';

const KpiCard = ({ children, onClick, accent }) => (
  <Hoverable
    style={{
      ...(accent
        ? {
            background: 'linear-gradient(140deg,rgba(215,244,82,.12),rgba(215,244,82,.02))',
            border: '1px solid rgba(215,244,82,.28)',
          }
        : { background: color.surface, border: `1px solid ${line.hair}` }),
      borderRadius: 16, padding: '16px 18px', cursor: 'pointer', position: 'relative',
    }}
    hover={{ borderColor: accent ? 'rgba(215,244,82,.55)' : borderHoverOff }}
    onClick={onClick}
  >
    {children}
  </Hoverable>
);

export default function Overview() {
  const { t, lang, go, cabinet } = useApp();
  const { me, conversations, donationOverview, archiveImages, chatterStats } = cabinet;

  const credits = fmtCredits(me?.credits_balance);
  const planName = me?.plan_display_name || me?.plan_tier || '—';
  const recentDialogs = conversations.slice(0, 4).map((c, i) => mapDialogRow(c, i));
  const recentFrames = archiveImages.slice(0, 4);
  const donationAvail = donationOverview?.available_minor != null
    ? fmtMoney(donationOverview.available_minor, donationOverview.currency)
    : '—';
  const donationTotal = donationOverview?.total_minor != null
    ? fmtMoney(donationOverview.total_minor, donationOverview.currency)
    : '—';
  const dialogCount = conversations.length;
  const teamReplies = sumOutboundMessages(chatterStats);
  const unreadTotal = conversations.reduce((a, c) => a + (c.unread_count || 0), 0);
  const helloName = (me?.email || '').split('@')[0] || '—';
  const hello = lang === 'ru' ? `С возвращением, ${helloName}` : `Welcome back, ${helloName}`;

  const studioCards = [
    { title: t.navImages, desc: t.imagesDesc, Icon: IcoImage, tint: { background: 'rgba(215,244,82,.12)', color: color.lime }, page: 'images' },
    { title: t.navVideo, desc: t.videoDesc, Icon: IcoFilm, tint: { background: 'rgba(192,132,252,.12)', color: color.purple }, page: 'video' },
    { title: t.navCharacters, desc: t.charactersDesc, Icon: IcoStar, tint: { background: 'rgba(240,168,200,.12)', color: color.pink }, page: 'characters' },
  ];

  const startSteps = guideDefs(lang).slice(0, 4).map((g, i) => ({ n: i + 1, label: g.title }));

  return (
    <Fade data-screen-label="Обзор">
      {/* header */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', marginBottom: 20 }}>
        <div>
          <Eyebrow size={10} spacing="2px" style={{ marginBottom: 6 }}>{fmtToday(lang)}</Eyebrow>
          <PageTitle size={24}>{hello}</PageTitle>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <LimeButton onClick={go('images')}>
            <span style={{ display: 'flex', width: 15, height: 15 }}><IcoSpark /></span>
            {t.newFrame}
          </LimeButton>
          <Hoverable
            style={{
              display: 'flex', alignItems: 'center', gap: 8, background: color.raised,
              border: `1px solid ${line.mid}`, fontWeight: 700, fontSize: 13,
              borderRadius: 10, padding: '10px 16px', cursor: 'pointer',
            }}
            hover={{ borderColor: borderHoverOff }}
            onClick={go('dialogs')}
          >
            <span style={{ display: 'flex', width: 15, height: 15, color: color.textDim }}><IcoChat /></span>
            {t.openDialogs}
          </Hoverable>
        </div>
      </div>

      {/* KPI row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(200px,1fr))', gap: 12, marginBottom: 24 }}>
        <KpiCard accent onClick={go('billing')}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontFamily: font.mono, fontSize: 9.5, letterSpacing: '1.8px', color: color.limeOlive }}>{t.kpiCredits}</span>
            <span style={{ fontSize: 10.5, fontWeight: 800, color: color.lime }}>{t.topup} →</span>
          </div>
          <div style={{ fontFamily: font.display, fontWeight: 700, fontSize: 26, color: color.lime }}>{credits}</div>
          <div style={{ fontSize: 11.5, color: color.textDim, marginTop: 4 }}>≈ {Math.floor(Number(credits) / 10)} {t.framesLeft}</div>
        </KpiCard>

        <KpiCard onClick={go('billing')}>
          <Eyebrow style={{ marginBottom: 10 }}>{t.kpiPlan}</Eyebrow>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontFamily: font.display, fontWeight: 600, fontSize: 18 }}>{planName}</span>
            <span
              style={{
                fontFamily: font.mono, fontSize: 9, letterSpacing: '1px',
                background: 'rgba(74,222,128,.12)', color: color.green,
                border: '1px solid rgba(74,222,128,.3)', padding: '2px 8px', borderRadius: 20,
              }}
            >
              {t.active}
            </span>
          </div>
          <div style={{ fontSize: 11.5, color: color.textDim, marginTop: 6 }}>
            {me?.subscription_expires_at ? `${t.until} ${new Date(me.subscription_expires_at).toLocaleDateString(lang === 'ru' ? 'ru-RU' : 'en-GB')}` : '—'}
          </div>
        </KpiCard>

        <KpiCard onClick={go('donations')}>
          <Eyebrow style={{ marginBottom: 10 }}>{t.kpiDonations}</Eyebrow>
          <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 20 }}>{donationTotal}</div>
          <div style={{ fontSize: 11.5, color: color.pink, marginTop: 6 }}>{t.toPayout}: {donationAvail} →</div>
        </KpiCard>

        <KpiCard onClick={go('dialogs')}>
          <Eyebrow style={{ marginBottom: 10 }}>{t.kpiDialogs}</Eyebrow>
          <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 20 }}>{dialogCount}</div>
          <div style={{ fontSize: 11.5, color: color.textDim, marginTop: 6 }}>
            {unreadTotal ? `${unreadTotal} ${lang === 'ru' ? 'новых' : 'new'}` : t.allRead} · {teamReplies} {t.teamReplies}
          </div>
        </KpiCard>
      </div>

      {/* Where to start */}
      <div
        style={{
          background: 'linear-gradient(120deg,rgba(192,132,252,.1),rgba(240,168,200,.04))',
          border: '1px solid rgba(192,132,252,.28)', borderRadius: 16,
          padding: '16px 18px', marginBottom: 24,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 14 }}>
          <div>
            <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 16, marginBottom: 3 }}>{t.startTitle}</div>
            <div style={{ fontSize: 12, color: color.textDim }}>{t.startDesc}</div>
          </div>
          <Hoverable
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              background: 'linear-gradient(120deg,#C084FC,#F0A8C8)', color: color.purpleInk,
              fontWeight: 800, fontSize: 12.5, borderRadius: 10, padding: '9px 16px', cursor: 'pointer',
            }}
            hover={{ filter: 'brightness(1.08)' }}
            onClick={go('guide')}
          >
            {t.openGuide} →
          </Hoverable>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))', gap: 8 }}>
          {startSteps.map((st) => (
            <Hoverable
              key={st.n}
              style={{
                display: 'flex', alignItems: 'center', gap: 10, background: color.surface,
                border: `1px solid ${line.hair}`, borderRadius: 12, padding: '10px 12px', cursor: 'pointer',
              }}
              hover={{ borderColor: 'rgba(192,132,252,.4)' }}
              onClick={go('guide')}
            >
              <div
                style={{
                  width: 24, height: 24, flex: 'none', borderRadius: 8,
                  background: 'rgba(192,132,252,.15)', color: color.purple,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontFamily: font.display, fontWeight: 600, fontSize: 12,
                }}
              >
                {st.n}
              </div>
              <span style={{ fontSize: 12, fontWeight: 700 }}>{st.label}</span>
            </Hoverable>
          ))}
        </div>
      </div>

      {/* Studio shortcuts */}
      <Eyebrow size={10} spacing="2px" style={{ margin: '0 0 10px' }}>{t.studioBlock}</Eyebrow>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(230px,1fr))', gap: 12, marginBottom: 24 }}>
        {studioCards.map((c) => (
          <Hoverable
            key={c.title}
            style={{
              background: color.surface, border: `1px solid ${line.hair}`, borderRadius: 16,
              padding: '16px 18px', cursor: 'pointer', display: 'flex', gap: 14, alignItems: 'flex-start',
            }}
            hover={{ borderColor: 'rgba(192,132,252,.45)', background: color.surfaceHi }}
            onClick={go(c.page)}
          >
            <IconBox size={40} iconSize={19} tint={c.tint}><c.Icon /></IconBox>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 3 }}>{c.title}</div>
              <div style={{ fontSize: 11.5, color: color.textDim, lineHeight: 1.45 }}>{c.desc}</div>
            </div>
            <span style={{ color: color.textGhost, fontSize: 14 }}>→</span>
          </Hoverable>
        ))}
      </div>

      {/* recents */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(300px,1fr))', gap: 12 }}>
        <Panel style={{ padding: '16px 18px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <span style={{ fontWeight: 800, fontSize: 14 }}>{t.recentDialogs}</span>
            <Hoverable as="span" style={{ fontSize: 11.5, fontWeight: 700, color: color.lime, cursor: 'pointer' }} hover={{ color: color.limeHi }} onClick={go('dialogs')}>
              {t.all} →
            </Hoverable>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {recentDialogs.length ? recentDialogs.map((d) => (
              <Hoverable
                key={d.id}
                style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '9px 6px', borderRadius: 10, cursor: 'pointer' }}
                hover={{ background: 'rgba(255,255,255,.04)' }}
                onClick={go('dialogs')}
              >
                <Avatar size={32} grad={avG[d.av % 5]}>{d.name[0]}</Avatar>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', gap: 7, alignItems: 'baseline' }}>
                    <span style={{ fontWeight: 700, fontSize: 12.5 }}>{d.name}</span>
                    <span
                      style={{
                        fontFamily: font.mono, fontSize: 8.5, letterSpacing: '1px',
                        color: d.platform === 'FANVUE' ? color.pink : color.blue,
                      }}
                    >
                      {d.platform}
                    </span>
                  </div>
                  <div style={{ fontSize: 11.5, color: color.textDim, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {d.last}
                  </div>
                </div>
                <span style={{ fontFamily: font.mono, fontSize: 10, color: color.textGhost }}>{d.time}</span>
              </Hoverable>
            )) : (
              <div style={{ fontSize: 12, color: color.textDim, padding: '8px 6px' }}>{lang === 'ru' ? 'Диалогов пока нет' : 'No dialogs yet'}</div>
            )}
          </div>
        </Panel>

        <Panel style={{ padding: '16px 18px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <span style={{ fontWeight: 800, fontSize: 14 }}>{t.recentFrames}</span>
            <Hoverable as="span" style={{ fontSize: 11.5, fontWeight: 700, color: color.lime, cursor: 'pointer' }} hover={{ color: color.limeHi }} onClick={go('images')}>
              {t.toStudio} →
            </Hoverable>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 8 }}>
            {recentFrames.length ? recentFrames.map((item, i) => {
              const thumb = archiveThumbUrl(item);
              const model = cabinet.models.find((m) => m.id === item.studio_model_id);
              const label = `${model?.name || '—'} · ${item.aspect_ratio || '9:16'}`;
              return (
              <Hoverable
                key={item.id || i}
                style={{
                  aspectRatio: '9/16', borderRadius: 10, display: 'flex', alignItems: 'flex-end',
                  padding: 8, position: 'relative', overflow: 'hidden', cursor: 'pointer',
                  background: thumb ? `center/cover no-repeat url(${thumb})` : color.surface,
                  border: thumb ? 'none' : `1px solid ${line.hair}`,
                }}
                hover={{ filter: thumb ? 'brightness(1.15)' : undefined, borderColor: borderHoverOff }}
                onClick={go('images')}
              >
                <span style={{ fontFamily: font.mono, fontSize: 8.5, letterSpacing: '1px', color: 'rgba(255,255,255,.75)' }}>
                  {label}
                </span>
              </Hoverable>
            );}) : (
              <div style={{ gridColumn: '1 / -1', fontSize: 12, color: color.textDim, padding: '8px 0' }}>
                {lang === 'ru' ? 'Кадров пока нет' : 'No frames yet'}
              </div>
            )}
          </div>
          <div style={{ fontSize: 10.5, color: color.textGhost, marginTop: 10 }}>{t.framesHint}</div>
        </Panel>
      </div>
    </Fade>
  );
}

import Hoverable from './Hoverable';
import { IcoBolt, IcoLogout } from './Icons';
import { useApp } from '../hooks/useApp';
import { mobileNavDefs, moreItemDefs, pageTitles } from '../data/nav';
import { filterMobileNavDefs, canAccessPage } from '../data/navAccess';
import { color, line, font } from '../styles/tokens';
import { fmtCredits } from '../api/helpers';
import { assetUrl } from '../utils/assets';
import { goToAdmin } from '../../marketing/workspaceEntry';

/** Top bar shown only on mobile. */
export function MobileTopBar() {
  const { t, page, lang, setS, go, cabinet } = useApp();
  const langLabel = lang === 'ru' ? 'RU → EN' : 'EN → RU';
  const credits = fmtCredits(cabinet.me?.credits_balance);

  return (
    <div
      style={{
        flex: 'none', display: 'flex', alignItems: 'center', gap: 10,
        padding: '10px 14px', borderBottom: `1px solid ${line.hair}`, background: color.bgPanel,
      }}
    >
      <div
        style={{
          width: 30, height: 30, flex: 'none', borderRadius: 9, overflow: 'hidden',
          boxShadow: 'inset 0 0 0 1px rgba(255,255,255,.08)',
        }}
      >
        <img src={assetUrl('assets/logo-m.jpeg')} alt="ModelMate" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
      </div>
      <div style={{ fontWeight: 800, fontSize: 14, flex: 1 }}>{pageTitles(t)[page]}</div>
      <Hoverable
        as="div"
        style={{
          fontFamily: font.mono, fontSize: 10, border: `1px solid ${line.strong}`,
          borderRadius: 7, padding: '3px 7px', color: color.textDim, cursor: 'pointer',
        }}
        hover={{ color: color.text }}
        onClick={() => setS({ lang: lang === 'ru' ? 'en' : 'ru' })}
      >
        {langLabel}
      </Hoverable>
      <Hoverable
        style={{
          display: 'flex', alignItems: 'center', gap: 5,
          background: 'rgba(215,244,82,.1)', border: '1px solid rgba(215,244,82,.3)',
          borderRadius: 20, padding: '4px 10px', cursor: 'pointer',
        }}
        hover={{ borderColor: 'rgba(215,244,82,.6)' }}
        onClick={go('billing')}
      >
        <span style={{ display: 'flex', width: 13, height: 13, color: color.lime }}>
          <IcoBolt />
        </span>
        <span style={{ fontFamily: font.mono, fontSize: 11, fontWeight: 600, color: color.lime }}>{credits}</span>
      </Hoverable>
    </div>
  );
}

/** Bottom tab bar shown only on mobile. */
export function MobileNav() {
  const { t, lang, page, moreOpen, go, setS, cabinet } = useApp();
  const navItems = filterMobileNavDefs(mobileNavDefs(t, lang), cabinet.me, cabinet.opRights);

  return (
    <div
      style={{
        flex: 'none', display: 'flex', borderTop: '1px solid rgba(255,255,255,.08)',
        background: color.bgPanel, padding: '6px 4px calc(6px + env(safe-area-inset-bottom))',
      }}
    >
      {navItems.map((mn) => {
        const active = mn.more ? moreOpen : mn.pages.includes(page);
        const tint = active ? color.lime : color.navMobileIdle;
        return (
          <Hoverable
            key={mn.label}
            style={{
              flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
              gap: 3, padding: '6px 2px', cursor: 'pointer', borderRadius: 10,
            }}
            hover={{ background: 'rgba(255,255,255,.04)' }}
            onClick={mn.more ? () => setS({ moreOpen: true }) : go(mn.go)}
          >
            <span style={{ display: 'flex', width: 19, height: 19, color: tint }}>
              <mn.Icon />
            </span>
            <span style={{ fontSize: 9, fontWeight: 700, color: tint }}>{mn.label}</span>
          </Hoverable>
        );
      })}
    </div>
  );
}

/** Slide-up sheet listing secondary sections. */
export function MoreSheet() {
  const { t, lang, setS, go, cabinet } = useApp();
  const moreItems = [
    ...moreItemDefs(t, lang).filter((mi) => canAccessPage(mi.go, cabinet.me, cabinet.opRights)),
    ...(cabinet.me?.is_platform_admin
      ? [{ label: t.adminPanel, desc: t.adminPanelDesc, admin: true }]
      : []),
  ];

  return (
    <div
      onClick={() => setS({ moreOpen: false })}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,.6)',
        zIndex: 50, display: 'flex', alignItems: 'flex-end',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%', background: color.sheet, borderRadius: '20px 20px 0 0',
          padding: '14px 14px calc(20px + env(safe-area-inset-bottom))',
        }}
      >
        <div style={{ width: 36, height: 4, borderRadius: 2, background: 'rgba(255,255,255,.2)', margin: '0 auto 14px' }} />
        {moreItems.map((mi) => (
          <Hoverable
            key={mi.label}
            style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '12px 10px', borderRadius: 12, cursor: 'pointer',
            }}
            hover={{ background: 'rgba(255,255,255,.05)' }}
            onClick={mi.admin ? () => { setS({ moreOpen: false }); goToAdmin(); } : go(mi.go)}
          >
            {mi.Icon ? (
              <span style={{ display: 'flex', width: 18, height: 18, color: mi.admin ? color.orange : color.textDim }}>
                <mi.Icon />
              </span>
            ) : (
              <span style={{ width: 18, flex: 'none', textAlign: 'center', color: color.orange }}>⚙</span>
            )}
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, fontSize: 13.5 }}>{mi.label}</div>
              <div style={{ fontSize: 11, color: color.textMuted }}>{mi.desc}</div>
            </div>
            <span style={{ color: color.textGhost }}>→</span>
          </Hoverable>
        ))}
        <Hoverable
          style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '12px 10px', borderRadius: 12, cursor: 'pointer',
            marginTop: 4, borderTop: `1px solid ${line.hair}`,
          }}
          hover={{ background: 'rgba(248,113,113,.08)' }}
          onClick={() => {
            setS({ moreOpen: false });
            cabinet.logout();
          }}
        >
          <span style={{ display: 'flex', width: 18, height: 18, color: color.red }}>
            <IcoLogout />
          </span>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 13.5, color: color.red }}>{t.logout}</div>
            <div style={{ fontSize: 11, color: color.textMuted }}>{t.logoutDesc}</div>
          </div>
        </Hoverable>
      </div>
    </div>
  );
}

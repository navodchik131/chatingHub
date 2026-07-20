import Hoverable from './Hoverable';
import { IcoBolt } from './Icons';
import { useApp } from '../hooks/useApp';
import { navGroups } from '../data/nav';
import { filterNavGroups } from '../data/navAccess';
import { color, line, font } from '../styles/tokens';
import { borderHoverOff } from '../styles/mixins';
import { fmtCredits } from '../api/helpers';
import { computeNavBadges } from '../api/mappers';
import { assetUrl } from '../utils/assets';
import { goToAdmin } from '../../marketing/workspaceEntry';

const NavItem = ({ item, active, onClick }) => (
  <Hoverable
    style={{
      display: 'flex', alignItems: 'center', gap: 11,
      padding: '8px 10px', borderRadius: 10, fontSize: 13, cursor: 'pointer',
      ...(active
        ? { background: 'rgba(215,244,82,.1)', color: color.lime, fontWeight: 800 }
        : { color: color.navIdle, fontWeight: 600 }),
    }}
    hover={active ? {} : { background: 'rgba(255,255,255,.05)', color: color.text }}
    onClick={onClick}
    aria-current={active ? 'page' : undefined}
  >
    <span style={{ display: 'flex', width: 17, height: 17, flex: 'none' }}>
      <item.Icon />
    </span>
    <span style={{ flex: 1 }}>{item.label}</span>
    {item.badge && (
      <span
        style={{
          fontFamily: font.mono, fontSize: 10,
          background: 'rgba(215,244,82,.12)', color: color.lime,
          padding: '1px 7px', borderRadius: 20,
        }}
      >
        {item.badge}
      </span>
    )}
  </Hoverable>
);

export default function Sidebar() {
  const { t, page, go, lang, setS, cabinet } = useApp();
  const langLabel = lang === 'ru' ? 'RU → EN' : 'EN → RU';
  const me = cabinet.me;
  const credits = fmtCredits(me?.credits_balance);
  const badges = computeNavBadges(cabinet, me);
  const groups = filterNavGroups(navGroups(t, badges), me, cabinet.opRights);
  const email = me?.email || '—';
  const userInitial = (email[0] || '?').toUpperCase();
  const planLabel = me?.plan_display_name || me?.plan_tier || '—';

  return (
    <nav
      style={{
        width: 248, flex: 'none', display: 'flex', flexDirection: 'column',
        borderRight: `1px solid ${line.hair}`, background: color.bgPanel,
      }}
      aria-label="Main"
    >
      {/* logo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '18px 18px 14px' }}>
        <div
          style={{
            width: 40, height: 40, flex: 'none', borderRadius: 12, overflow: 'hidden',
            boxShadow: '0 4px 14px rgba(0,0,0,.5), inset 0 0 0 1px rgba(255,255,255,.08)',
          }}
        >
          <img
            src={assetUrl('assets/logo-m.jpeg')}
            alt="ModelMate"
            style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
          />
        </div>
        <div>
          <div style={{ fontFamily: font.display, fontWeight: 700, fontSize: 15, letterSpacing: '-.3px', lineHeight: 1 }}>
            ModelMate
          </div>
          <div style={{ fontFamily: font.mono, fontSize: 8, letterSpacing: '1.4px', color: color.textFaint, marginTop: 3 }}>
            AI OFM · {t.fullCycle}
          </div>
        </div>
      </div>

      {/* nav groups */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '6px 10px 10px', display: 'flex', flexDirection: 'column', gap: 2 }}>
        {groups.map((grp) => (
          <div key={grp.label} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <div
              style={{
                fontFamily: font.mono, fontSize: 9, letterSpacing: '2.2px',
                color: color.textGhost, padding: '14px 10px 5px', textTransform: 'uppercase',
              }}
            >
              {grp.label}
            </div>
            {grp.items.map((it) => (
              <NavItem key={it.id} item={it} active={page === it.id} onClick={go(it.id)} />
            ))}
          </div>
        ))}
        {me?.is_platform_admin && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginTop: 4 }}>
            <Hoverable
              style={{
                display: 'flex', alignItems: 'center', gap: 11,
                padding: '8px 10px', borderRadius: 10, fontSize: 13, cursor: 'pointer',
                color: color.orange, fontWeight: 700,
              }}
              hover={{ background: 'rgba(255,255,255,.05)' }}
              onClick={goToAdmin}
            >
              <span style={{ flex: 1 }}>{t.adminPanel}</span>
            </Hoverable>
          </div>
        )}
      </div>

      {/* credits + user */}
      <div style={{ padding: 12, borderTop: `1px solid ${line.hair}`, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <Hoverable
          style={{
            display: 'flex', alignItems: 'center', gap: 10,
            background: 'linear-gradient(120deg,rgba(215,244,82,.10),rgba(215,244,82,.03))',
            border: '1px solid rgba(215,244,82,.25)', borderRadius: 12,
            padding: '10px 12px', cursor: 'pointer',
          }}
          hover={{ borderColor: 'rgba(215,244,82,.5)' }}
          onClick={go('billing')}
        >
          <span style={{ display: 'flex', width: 18, height: 18, color: color.lime }}>
            <IcoBolt />
          </span>
          <div style={{ flex: 1 }}>
            <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 15, color: color.lime, lineHeight: 1.1 }}>
              {credits}
            </div>
            <div style={{ fontSize: 10.5, color: color.textDim }}>{t.credits}</div>
          </div>
          <span style={{ fontSize: 11, fontWeight: 700, color: color.lime }}>{t.topup} →</span>
        </Hoverable>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '2px 4px' }}>
          <div
            style={{
              width: 30, height: 30, borderRadius: '50%',
              background: 'linear-gradient(135deg,#818CF8,#C084FC)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontWeight: 800, fontSize: 13, color: '#14102A',
            }}
          >
            {userInitial}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12.5, fontWeight: 700, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {email}
            </div>
            <div style={{ fontSize: 10.5, color: color.textDim }}>{t.owner} · {planLabel}</div>
          </div>
          <Hoverable
            style={{
              fontFamily: font.mono, fontSize: 10, fontWeight: 600,
              border: `1px solid ${line.strong}`, borderRadius: 7,
              padding: '4px 8px', cursor: 'pointer', color: color.textDim,
            }}
            hover={{ color: color.text, borderColor: borderHoverOff }}
            onClick={() => setS({ lang: lang === 'ru' ? 'en' : 'ru' })}
          >
            {langLabel}
          </Hoverable>
        </div>
      </div>
    </nav>
  );
}

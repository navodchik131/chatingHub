import { AppProvider, useApp } from './hooks/useApp';
import Sidebar from './components/Sidebar';
import { MobileTopBar, MobileNav, MoreSheet } from './components/MobileNav';
import { color, line } from './styles/tokens';
import Hoverable from './components/Hoverable';
import { fmtMoney } from './api/helpers';

import Overview from './pages/Overview';
import Guide, { MediaModal } from './pages/Guide';
import Dialogs from './pages/Dialogs';
import Images, { Lightbox } from './pages/Images';
import Video from './pages/Video';
import Characters from './pages/Characters';
import Donations from './pages/Donations';
import Billing from './pages/Billing';
import Connections from './pages/Connections';
import Team, { NewOperator } from './pages/Team';
import Workflow from './pages/Workflow';
import ApiStatusBar from './components/ApiStatusBar';

const pages = {
  overview: Overview,
  guide: Guide,
  dialogs: Dialogs,
  images: Images,
  video: Video,
  characters: Characters,
  donations: Donations,
  billing: Billing,
  connections: Connections,
  team: Team,
  newOperator: NewOperator,
  workflow: Workflow,
};

function DonationAlertBanner() {
  const { t, lang, go, cabinet } = useApp();
  const alert = cabinet.creatorDonationAlert;
  if (!alert || !cabinet.me?.is_workspace_owner) return null;

  const amount = alert.amount_minor != null
    ? fmtMoney(alert.amount_minor, alert.currency || 'RUB')
    : '';
  const body = [alert.donor_label || alert.title, amount].filter(Boolean).join(' · ') || t.newDonation;

  return (
    <div
      style={{
        position: 'fixed', right: 16, bottom: 16, zIndex: 60, maxWidth: 360,
        background: color.raised, border: `1px solid ${line.mid}`, borderRadius: 14,
        padding: '14px 16px', boxShadow: '0 12px 40px rgba(0,0,0,.55)',
      }}
    >
      <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 4 }}>
        {lang === 'ru' ? 'Новый донат ModelMate' : 'New ModelMate donation'}
      </div>
      <div style={{ fontSize: 12.5, color: color.textDim, marginBottom: 12 }}>{body}</div>
      <div style={{ display: 'flex', gap: 8 }}>
        <Hoverable
          style={{
            background: color.lime, color: color.limeInk, fontWeight: 800, fontSize: 12.5,
            borderRadius: 9, padding: '8px 14px', cursor: 'pointer',
          }}
          hover={{ filter: 'brightness(1.06)' }}
          onClick={() => {
            cabinet.setCreatorDonationAlert(null);
            go('donations')();
          }}
        >
          {t.donationAlertOpen}
        </Hoverable>
        <Hoverable
          style={{
            border: `1px solid ${line.mid}`, color: color.textDim, fontWeight: 700,
            fontSize: 12.5, borderRadius: 9, padding: '8px 14px', cursor: 'pointer',
          }}
          hover={{ borderColor: line.strong }}
          onClick={() => cabinet.setCreatorDonationAlert(null)}
        >
          {t.donationAlertDismiss}
        </Hoverable>
      </div>
    </div>
  );
}

function Shell() {
  const { page, isMobile, moreOpen, cabinet } = useApp();
  const Page = pages[page] || Overview;

  const contentPad = isMobile
    ? { padding: '16px 14px 20px', height: '100%', boxSizing: 'border-box' }
    : { padding: '24px 28px 32px', height: '100%', boxSizing: 'border-box', maxWidth: 1280, margin: '0 auto' };

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: color.bg }}>
      {!isMobile && <Sidebar />}

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {isMobile && <MobileTopBar />}

        {/* `key` remounts on page change so the fade animation replays */}
        <main style={{ flex: 1, overflowY: 'auto' }} key={page}>
          <div style={contentPad}>
            <Page />
          </div>
        </main>

        <Lightbox />
        <MediaModal />

        {isMobile && <MobileNav />}
        {moreOpen && <MoreSheet />}
      </div>
      <DonationAlertBanner />
      <ApiStatusBar error={cabinet.error} busy={cabinet.busy} onDismiss={() => cabinet.setError(null)} />
    </div>
  );
}

export default function App({ forceMobile = false }) {
  return (
    <AppProvider forceMobile={forceMobile}>
      <Shell />
    </AppProvider>
  );
}

import { AppProvider, useApp } from './hooks/useApp';
import Sidebar from './components/Sidebar';
import { MobileTopBar, MobileNav, MoreSheet } from './components/MobileNav';
import { color } from './styles/tokens';

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

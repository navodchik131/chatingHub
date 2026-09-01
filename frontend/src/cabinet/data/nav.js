import { IcoGrid, IcoChat, IcoImage, IcoFilm, IcoStar, IcoFlow,
  IcoHeart, IcoCard, IcoPlug, IcoTeam, IcoSpark, IcoLayers, IcoLifeBuoy, IcoUser, IcoHandshake, IcoBook,
} from '../components/Icons';

/** Sidebar groups — badges come from live cabinet data via computeNavBadges. */
export const navGroups = (t, badges = {}, { isPartner = false, evolinkEnabled = true } = {}) => [
  {
    label: t.grpWork,
    items: [
      { id: 'overview', label: t.navOverview, Icon: IcoGrid },
      { id: 'dialogs', label: t.navDialogs, Icon: IcoChat, badge: badges.dialogs },
    ],
  },
  {
    label: t.grpStudio,
    items: [
      { id: 'images', label: t.navImages, Icon: IcoImage },
      { id: 'video', label: t.navVideo, Icon: IcoFilm },
      ...(evolinkEnabled ? [{
        id: 'seedance-sale',
        label: t.navSeedanceSale,
        Icon: IcoSpark,
        badge: 'Best',
      }] : []),
      { id: 'characters', label: t.navCharacters, Icon: IcoStar },
      { id: 'references', label: t.navReferences, Icon: IcoLayers },
      { id: 'news', label: t.navNews, Icon: IcoBook },
      { id: 'workflow', label: t.navWorkflow, Icon: IcoFlow, badge: badges.workflow },
    ],
  },
  {
    label: t.grpMoney,
    items: [
      { id: 'donations', label: t.navDonations, Icon: IcoHeart, badge: badges.donations },
      { id: 'billing', label: t.navBilling, Icon: IcoCard },
    ].concat(isPartner ? [{ id: 'partner', label: t.navPartner, Icon: IcoHandshake, badge: '30%' }] : []),
  },
  {
    label: t.grpSettings,
    items: [
      { id: 'connections', label: t.navConnections, Icon: IcoPlug },
      { id: 'team', label: t.navTeam, Icon: IcoTeam },
      { id: 'support', label: t.navSupport, Icon: IcoLifeBuoy, badge: badges.support },
      { id: 'profile', label: t.navProfile, Icon: IcoUser },
    ],
  },
];

export const pageTitles = (t) => ({
  overview: t.navOverview, dialogs: t.navDialogs, images: t.navImages,
  video: t.navVideo, 'seedance-sale': t.navSeedanceSale, characters: t.navCharacters,
  references: t.navReferences, news: t.navNews, workflow: t.navWorkflow,
  donations: t.navDonations, billing: t.navBilling, partner: t.navPartner, connections: t.navConnections,
  team: t.navTeam, support: t.navSupport, profile: t.navProfile,
});

/** Bottom bar on mobile — each entry can light up for several pages. */
export const mobileNavDefs = (t, lang) => [
  { label: t.navOverview, Icon: IcoGrid, pages: ['overview'], go: 'overview' },
  { label: t.navDialogs, Icon: IcoChat, pages: ['dialogs'], go: 'dialogs' },
  { label: lang === 'ru' ? 'Студия' : 'Studio', Icon: IcoSpark, pages: ['images', 'video', 'seedance-sale', 'characters'], go: 'images' },
  { label: lang === 'ru' ? 'Финансы' : 'Money', Icon: IcoHeart, pages: ['donations', 'billing'], go: 'donations' },
  { label: lang === 'ru' ? 'Ещё' : 'More', Icon: IcoLayers, pages: [], more: true },
];

/** "More" sheet contents on mobile. */
export const moreItemDefs = (t, lang) => [
  { label: t.navVideo, desc: t.videoDesc, Icon: IcoFilm, go: 'video' },
  { label: t.navSeedanceSale, desc: t.seedanceSaleDesc, Icon: IcoSpark, go: 'seedance-sale' },
  { label: t.navCharacters, desc: lang === 'ru' ? 'Ваши виртуальные модели' : 'Your virtual models', Icon: IcoStar, go: 'characters' },
  { label: t.navReferences, desc: lang === 'ru' ? 'Референсы для студии' : 'Studio references', Icon: IcoLayers, go: 'references' },
  { label: t.navNews, desc: lang === 'ru' ? 'Обновления сервиса' : 'Product updates', Icon: IcoBook, go: 'news' },
  { label: t.navWorkflow, desc: lang === 'ru' ? 'Узловой конструктор (Pro)' : 'Node builder (Pro)', Icon: IcoFlow, go: 'workflow' },
  { label: t.navBilling, desc: t.billingNavDesc, Icon: IcoCard, go: 'billing' },
  { label: t.navConnections, desc: t.connectionsDesc, Icon: IcoPlug, go: 'connections' },
  { label: t.navTeam, desc: t.teamDesc, Icon: IcoTeam, go: 'team' },
  { label: t.navSupport, desc: t.supportDesc, Icon: IcoLifeBuoy, go: 'support' },
  { label: t.navProfile, desc: t.profileDesc, Icon: IcoUser, go: 'profile' },
];

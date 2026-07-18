import {
  IcoGrid, IcoChat, IcoImage, IcoFilm, IcoStar, IcoFlow,
  IcoHeart, IcoCard, IcoPlug, IcoTeam, IcoSpark, IcoLayers,
} from '../components/Icons';

/** Sidebar groups — badges come from live cabinet data via computeNavBadges. */
export const navGroups = (t, badges = {}) => [
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
      { id: 'characters', label: t.navCharacters, Icon: IcoStar },
      { id: 'workflow', label: t.navWorkflow, Icon: IcoFlow, badge: badges.workflow },
    ],
  },
  {
    label: t.grpMoney,
    items: [
      { id: 'donations', label: t.navDonations, Icon: IcoHeart, badge: badges.donations },
      { id: 'billing', label: t.navBilling, Icon: IcoCard },
    ],
  },
  {
    label: t.grpSettings,
    items: [
      { id: 'connections', label: t.navConnections, Icon: IcoPlug },
      { id: 'team', label: t.navTeam, Icon: IcoTeam },
    ],
  },
];

export const pageTitles = (t) => ({
  overview: t.navOverview, dialogs: t.navDialogs, images: t.navImages,
  video: t.navVideo, characters: t.navCharacters, workflow: t.navWorkflow,
  donations: t.navDonations, billing: t.navBilling, connections: t.navConnections,
  team: t.navTeam,
});

/** Bottom bar on mobile — each entry can light up for several pages. */
export const mobileNavDefs = (t, lang) => [
  { label: t.navOverview, Icon: IcoGrid, pages: ['overview'], go: 'overview' },
  { label: t.navDialogs, Icon: IcoChat, pages: ['dialogs'], go: 'dialogs' },
  { label: lang === 'ru' ? 'Студия' : 'Studio', Icon: IcoSpark, pages: ['images', 'video', 'characters'], go: 'images' },
  { label: lang === 'ru' ? 'Финансы' : 'Money', Icon: IcoHeart, pages: ['donations', 'billing'], go: 'donations' },
  { label: lang === 'ru' ? 'Ещё' : 'More', Icon: IcoLayers, pages: [], more: true },
];

/** "More" sheet contents on mobile. */
export const moreItemDefs = (t, lang) => [
  { label: t.navVideo, desc: t.videoDesc, Icon: IcoFilm, go: 'video' },
  { label: t.navCharacters, desc: lang === 'ru' ? 'Ваши виртуальные модели' : 'Your virtual models', Icon: IcoStar, go: 'characters' },
  { label: t.navWorkflow, desc: lang === 'ru' ? 'Узловой конструктор (Pro)' : 'Node builder (Pro)', Icon: IcoFlow, go: 'workflow' },
  { label: t.navBilling, desc: t.billingDesc, Icon: IcoCard, go: 'billing' },
  { label: t.navConnections, desc: t.connectionsDesc, Icon: IcoPlug, go: 'connections' },
  { label: t.navTeam, desc: t.teamDesc, Icon: IcoTeam, go: 'team' },
];

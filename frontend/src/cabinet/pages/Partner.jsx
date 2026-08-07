import { useCallback, useEffect, useMemo, useState } from 'react';
import Hoverable from '../components/Hoverable';
import { IcoGlobe, IcoCopy, IcoHandshake, IcoCoin, IcoTrend, IcoCard, IcoCheck } from '../components/Icons';
import { Fade, Eyebrow, Panel, Field } from '../components/ui';
import { useApp } from '../hooks/useApp';
import { color, line, font } from '../styles/tokens';
import { fieldLbl, selectSt } from '../styles/mixins';
import { apiFetch } from '../../api';
import { apiJson } from '../api/helpers';
import { copyText } from '../utils/clipboard';

const CHAN_COLORS = ['#F0A8C8', '#38BDF8', '#D7F452', '#C084FC', '#FB923C', '#4ADE80', '#F87171'];
const DESTS = ['home', 'pricing', 'studio', 'chats'];
const payoutAssets = ['USDT_TRC20', 'USDT_ERC20', 'TON'];

function fmtRub(kopecks, lang) {
  const rub = (Number(kopecks) || 0) / 100;
  return `${rub.toLocaleString(lang === 'ru' ? 'ru-RU' : 'en-US', { maximumFractionDigits: 0 })} ₽`;
}

function fmtTrend(cur, prev) {
  const d = (Number(cur) || 0) - (Number(prev) || 0);
  if (d === 0) return '0';
  return d > 0 ? `+${d}` : String(d);
}

function tabStyle(active) {
  return {
    fontFamily: font.mono, fontSize: 10, letterSpacing: '.6px', padding: '6px 13px', borderRadius: 20, cursor: 'pointer',
    border: `1px solid ${active ? 'rgba(215,244,82,.35)' : line.mid}`,
    background: active ? 'rgba(215,244,82,.1)' : 'transparent',
    color: active ? color.lime : color.textDim,
    fontWeight: active ? 700 : 600,
  };
}

function chipStyle(color) {
  return {
    fontFamily: font.mono, fontSize: 9, letterSpacing: '.6px', padding: '3px 8px', borderRadius: 6,
    background: `${color}22`, color, border: `1px solid ${color}4d`,
  };
}

export default function Partner() {
  const { t, lang, setS, cabinet, partnerTab } = useApp();
  const tab = partnerTab || 'overview';
  const [data, setData] = useState(null);
  const [refs, setRefs] = useState([]);
  const [srcFilter, setSrcFilter] = useState('all');
  const [heroLink, setHeroLink] = useState('all');
  const [linkCopied, setLinkCopied] = useState(false);
  const [newTag, setNewTag] = useState('');
  const [newNote, setNewNote] = useState('');
  const [newDest, setNewDest] = useState('home');
  const [chanSort, setChanSort] = useState('earned');
  const [wallet, setWallet] = useState('');
  const [asset, setAsset] = useState('USDT_TRC20');
  const [busy, setBusy] = useState(false);
  const [qrUrl, setQrUrl] = useState(null);

  const destLabel = (d) => ({
    home: t.destHome, pricing: t.destPricing, studio: t.destStudio, chats: t.destChats,
  }[d] || t.destHome);

  const load = useCallback(async () => {
    try {
      const me = await apiJson('/api/partner/me');
      setData(me);
      setWallet(me?.payout_settings?.wallet_address || '');
      setAsset(me?.payout_settings?.payout_asset || 'USDT_TRC20');
    } catch {
      setData(null);
    }
  }, []);

  const loadRefs = useCallback(async (src) => {
    const q = src && src !== 'all' ? `?src=${encodeURIComponent(src)}` : '';
    try {
      const rows = await apiJson(`/api/partner/referrals${q}`);
      setRefs(Array.isArray(rows) ? rows : []);
    } catch {
      setRefs([]);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (tab === 'refs') void loadRefs(srcFilter); }, [tab, srcFilter, loadRefs]);

  const analytics = data?.analytics || {};
  const links = analytics.links || [];
  const baseLinkStats = analytics.base_link || { clicks: 0, registrations: 0, paying_users: 0 };
  const slug = data?.partner_slug || '';
  const baseLink = data?.base_link || '';

  const linkUrl = useCallback((l) => {
    const tag = l?.tag;
    const dest = l?.dest || 'home';
    let url = baseLink;
    const params = [];
    if (tag) params.push(`src=${tag}`);
    if (dest && dest !== 'home') params.push(`to=${dest}`);
    if (params.length) url += `?${params.join('&')}`;
    return url;
  }, [baseLink]);

  const heroPick = heroLink === 'all' ? null : links.find((l) => l.tag === heroLink);
  const heroTotals = {
    clicks: baseLinkStats.clicks || 0,
    regs: baseLinkStats.registrations || 0,
    paid: baseLinkStats.paying_users || 0,
  };
  const heroScope = heroPick
    ? { clicks: heroPick.clicks, regs: heroPick.registrations, paid: heroPick.paying_users }
    : heroTotals;
  const heroUrl = heroPick ? linkUrl(heroPick) : baseLink;

  useEffect(() => {
    if (!heroUrl) {
      setQrUrl(null);
      return undefined;
    }
    let cancelled = false;
    let objectUrl = null;
    void apiFetch(`/api/partner/qr?url=${encodeURIComponent(heroUrl)}`)
      .then((r) => (r.ok ? r.blob() : null))
      .then((blob) => {
        if (cancelled || !blob) return;
        objectUrl = URL.createObjectURL(blob);
        setQrUrl(objectUrl);
      })
      .catch(() => setQrUrl(null));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [heroUrl]);

  const sortedLinks = useMemo(() => {
    const rows = [...links];
    const key = (l) => {
      if (chanSort === 'regs') return l.registrations || 0;
      if (chanSort === 'conv') return l.clicks ? (l.registrations || 0) / l.clicks : 0;
      return l.earned_kopecks || 0;
    };
    return rows.sort((a, b) => key(b) - key(a));
  }, [links, chanSort]);

  const copyLink = async (url) => {
    await copyText(url);
    setLinkCopied(true);
    setTimeout(() => setLinkCopied(false), 2000);
  };

  const createLink = async () => {
    if (!newTag.trim()) return;
    setBusy(true);
    try {
      await apiFetch('/api/partner/links', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tag: newTag.trim(), note: newNote, dest: newDest }),
      });
      setNewTag('');
      setNewNote('');
      await load();
    } finally {
      setBusy(false);
    }
  };

  const saveWallet = async () => {
    setBusy(true);
    try {
      await apiFetch('/api/partner/payout-settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ wallet_address: wallet, payout_asset: asset }),
      });
      await load();
    } finally {
      setBusy(false);
    }
  };

  const requestPayout = async () => {
    setBusy(true);
    try {
      await apiFetch('/api/partner/payout-requests', { method: 'POST', body: '{}' });
      await load();
    } finally {
      setBusy(false);
    }
  };

  if (!cabinet.me?.is_partner) {
    return (
      <Fade>
        <Panel style={{ padding: 24, textAlign: 'center', color: color.textDim }}>
          {lang === 'ru' ? 'Партнёрский кабинет недоступен для этого аккаунта.' : 'Partner cabinet is not available for this account.'}
        </Panel>
      </Fade>
    );
  }

  const chart = analytics.chart || [];
  const maxEarn = Math.max(...chart.map((c) => c.earn_kopecks || 0), 1);
  const maxRegs = Math.max(...chart.map((c) => c.registrations || 0), 1);

  const kpi = [
    { label: t.partnerKpiReferred, value: String(analytics.referred_total || 0), color: color.text, icon: IcoHandshake, trend: fmtTrend(analytics.referred_month, analytics.referred_prev_month) },
    { label: t.partnerKpiSubscribed, value: String(analytics.subscribed_count || 0), color: '#38BDF8', icon: IcoTrend, trend: '' },
    { label: t.partnerKpiEarned, value: fmtRub(analytics.earned_total_kopecks, lang), color: color.lime, icon: IcoCoin, trend: fmtRub((analytics.earned_month_kopecks || 0) - (analytics.earned_prev_month_kopecks || 0), lang) },
    { label: t.partnerKpiAvg, value: fmtRub(analytics.avg_payment_kopecks, lang), color: '#C084FC', icon: IcoCard, trend: '' },
  ];

  const sourceFilters = [{ id: 'all', label: `${lang === 'ru' ? 'Все каналы' : 'All channels'} ${refs.length}` }]
    .concat(links.filter((l) => refs.some((r) => r.source_tag === l.tag)).map((l) => ({
      id: l.tag,
      label: `${l.tag} ${refs.filter((r) => r.source_tag === l.tag).length}`,
    })));

  const previewUrl = slug
    ? `${baseLink}?src=${(newTag.trim().toLowerCase().replace(/\s+/g, '-') || 'your-tag')}${newDest !== 'home' ? `&to=${newDest}` : ''}`
    : '';

  return (
    <Fade>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 14, flexWrap: 'wrap', marginBottom: 16 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 5 }}>
            <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 20 }}>{t.navPartner}</div>
            <span style={{ fontFamily: font.mono, fontSize: 9, letterSpacing: 1, background: 'rgba(215,244,82,.14)', color: color.lime, border: '1px solid rgba(215,244,82,.32)', padding: '3px 9px', borderRadius: 20 }}>{t.partnerRate}</span>
          </div>
          <div style={{ fontSize: 12.5, color: color.textDim }}>{t.partnerDesc}</div>
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {[
            { id: 'overview', label: t.partnerTabOverview },
            { id: 'links', label: t.partnerTabLinks },
            { id: 'refs', label: t.partnerTabRefs },
            { id: 'assets', label: t.partnerTabAssets },
          ].map((pt) => (
            <Hoverable key={pt.id} style={tabStyle(tab === pt.id)} onClick={() => setS({ partnerTab: pt.id })}>
              {pt.label}
            </Hoverable>
          ))}
        </div>
      </div>

      {tab === 'overview' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ background: 'linear-gradient(140deg,rgba(215,244,82,.11),rgba(215,244,82,.02))', border: '1px solid rgba(215,244,82,.3)', borderRadius: 16, padding: '18px 20px', display: 'flex', gap: 22, flexWrap: 'wrap', alignItems: 'center' }}>
            <div style={{ flex: 1, minWidth: 280 }}>
              <Eyebrow size={9} style={{ color: '#8A9152', marginBottom: 10 }}>{t.partnerYourLink}</Eyebrow>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
              <Hoverable style={chipStyle(heroLink === 'all' ? color.lime : color.textMuted)} onClick={() => setHeroLink('all')}>{t.heroLinkAll}</Hoverable>
              {links.map((l, i) => (
                <Hoverable key={l.id} style={chipStyle(heroLink === l.tag ? CHAN_COLORS[i % CHAN_COLORS.length] : color.textMuted)} onClick={() => setHeroLink(l.tag)}>{l.tag}</Hoverable>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <div style={{ flex: 1, minWidth: 200, display: 'flex', alignItems: 'center', gap: 10, background: color.bgDeep, border: '1px solid rgba(215,244,82,.25)', borderRadius: 11, padding: '11px 14px' }}>
                <span style={{ display: 'flex', width: 15, height: 15, color: color.lime }}><IcoGlobe /></span>
                <span style={{ flex: 1, minWidth: 0, fontFamily: font.mono, fontSize: 11.5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{heroUrl}</span>
              </div>
              <Hoverable
                style={{ display: 'flex', alignItems: 'center', gap: 8, background: color.lime, color: color.limeInk, fontWeight: 800, fontSize: 12.5, borderRadius: 11, padding: '11px 16px', cursor: 'pointer' }}
                onClick={() => void copyLink(heroUrl)}
              >
                <span style={{ display: 'flex', width: 15, height: 15 }}><IcoCopy /></span>
                {linkCopied ? t.copied : t.copy}
              </Hoverable>
            </div>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 14 }}>
              {[
                { value: heroScope.clicks, label: t.funnelClicks, color: color.text },
                { value: heroScope.regs, label: t.funnelRegs, color: '#38BDF8' },
                { value: heroScope.regs ? `${Math.round((heroScope.paid / heroScope.regs) * 100)}%` : '0%', label: t.funnelConv, color: '#4ADE80' },
              ].map((pf) => (
                <div key={pf.label}>
                  <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 17, color: pf.color }}>{pf.value}</div>
                  <Eyebrow size={9}>{pf.label}</Eyebrow>
                </div>
              ))}
            </div>
            </div>
            <div style={{ width: 132, flex: 'none', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 9 }}>
              <div style={{ width: 112, height: 112, borderRadius: 14, background: color.bgDeep, border: '1px solid rgba(215,244,82,.25)', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
                {qrUrl ? (
                  <img src={qrUrl} alt="QR" style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }} />
                ) : (
                  <span style={{ fontFamily: font.mono, fontSize: 9, color: color.textMuted }}>QR</span>
                )}
              </div>
              <Eyebrow size={9}>{t.partnerQr}</Eyebrow>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(170px,1fr))', gap: 12 }}>
            {kpi.map((ps) => (
              <Panel key={ps.label} style={{ borderRadius: 14, padding: '14px 16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 9 }}>
                  <span style={{ display: 'flex', width: 14, height: 14, color: ps.color }}><ps.icon /></span>
                  <Eyebrow size={9}>{ps.label}</Eyebrow>
                </div>
                <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 20, color: ps.color }}>{ps.value}</div>
                {ps.trend ? <div style={{ fontFamily: font.mono, fontSize: 9.5, color: '#4ADE80', marginTop: 5 }}>{ps.trend} · {t.partnerVsMonth}</div> : null}
              </Panel>
            ))}
          </div>

          <Panel style={{ borderRadius: 16, padding: '18px 20px' }}>
            <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 4 }}>{t.partnerChartTitle}</div>
            <div style={{ fontSize: 11.5, color: color.textDim, marginBottom: 18 }}>{t.partnerChartHint}</div>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 10, height: 190 }}>
              {chart.map((pc, i) => (
                <div key={pc.month || i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, height: '100%', justifyContent: 'flex-end' }}>
                  <div style={{ width: '100%', display: 'flex', alignItems: 'flex-end', justifyContent: 'center', gap: 3, flex: 1 }}>
                    <div style={{ width: 14, borderRadius: '5px 5px 2px 2px', height: `${Math.round(((pc.earn_kopecks || 0) / maxEarn) * 100)}%`, background: i === chart.length - 1 ? color.lime : 'rgba(215,244,82,.55)' }} />
                    <div style={{ width: 14, borderRadius: '5px 5px 2px 2px', height: `${Math.round(((pc.registrations || 0) / maxRegs) * 88)}%`, background: i === chart.length - 1 ? '#38BDF8' : 'rgba(56,189,248,.42)' }} />
                  </div>
                  <div style={{ fontFamily: font.mono, fontSize: 9.5, color: color.textMuted }}>{(pc.month || '').slice(5)}</div>
                </div>
              ))}
            </div>
          </Panel>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(320px,1fr))', gap: 12 }}>
            <Panel style={{ borderRadius: 16, padding: '16px 18px' }}>
              <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 14 }}>{t.partnerTopClients}</div>
              {(analytics.top_clients || []).map((c, i) => (
                <div key={c.email_masked} style={{ marginBottom: 10 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                    <span style={{ fontWeight: 700, fontSize: 12.5 }}>{c.email_masked}</span>
                    <span style={{ fontFamily: font.display, fontWeight: 600, color: color.lime }}>{fmtRub(c.reward_kopecks, lang)}</span>
                  </div>
                  <div style={{ fontFamily: font.mono, fontSize: 9, color: color.textMuted }}>{c.plan} · {fmtRub(c.paid_kopecks, lang)}</div>
                </div>
              ))}
            </Panel>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
              <div style={{ background: 'linear-gradient(140deg,rgba(74,222,128,.1),rgba(74,222,128,.02))', border: '1px solid rgba(74,222,128,.3)', borderRadius: 16, padding: '16px 18px', minWidth: 0, overflow: 'hidden' }}>
                <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 6 }}>{t.partnerPayout}</div>
                <div style={{ fontSize: 11.5, color: color.textDim, lineHeight: 1.55, marginBottom: 13 }}>{t.partnerPayoutHint}</div>
                <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap', alignItems: 'stretch' }}>
                  <input value={wallet} onChange={(e) => setWallet(e.target.value)} placeholder={t.walletAddress} style={{ flex: '1 1 140px', minWidth: 0, background: color.bgDeep, border: `1px solid ${line.mid}`, borderRadius: 9, padding: '9px 12px', color: color.text, fontFamily: font.mono, fontSize: 11.5, boxSizing: 'border-box' }} />
                  <select value={asset} onChange={(e) => setAsset(e.target.value)} style={{ ...selectSt, width: 'auto', minWidth: 118, maxWidth: '100%', flex: '0 0 auto', boxSizing: 'border-box' }}>
                    {payoutAssets.map((a) => <option key={a} value={a}>{a.replace('_', ' ')}</option>)}
                  </select>
                </div>
                <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                  <Hoverable style={{ flex: 1, border: `1px solid ${line.mid}`, borderRadius: 9, padding: '9px 12px', textAlign: 'center', fontWeight: 700, fontSize: 12.5, cursor: 'pointer' }} onClick={() => void saveWallet()}>{t.saveWallet}</Hoverable>
                </div>
                <Hoverable
                  style={{ display: 'flex', alignItems: 'center', gap: 10, background: '#4ADE80', borderRadius: 11, padding: '11px 16px', cursor: 'pointer' }}
                  onClick={() => void requestPayout()}
                >
                  <span style={{ flex: 1, fontWeight: 800, fontSize: 13.5, color: '#08240F' }}>{t.partnerRequestPayout}</span>
                  <span style={{ fontFamily: font.mono, fontSize: 10.5, color: '#1F5C31' }}>{fmtRub(data?.payout_balance?.available_kopecks, lang)}</span>
                </Hoverable>
              </div>
              <Panel style={{ borderRadius: 16, padding: '16px 18px', flex: 1 }}>
                <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 12 }}>{t.partnerFeed}</div>
                {(analytics.recent_events || []).map((pe, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 9 }}>
                    <span style={{ flex: 1, fontSize: 12, color: color.textDim }}>{pe.text}</span>
                    <span style={{ fontFamily: font.mono, fontSize: 9.5, color: '#4ADE80' }}>{pe.amount_kopecks ? `+${fmtRub(pe.amount_kopecks, lang)}` : '—'}</span>
                  </div>
                ))}
              </Panel>
            </div>
          </div>
        </div>
      )}

      {tab === 'links' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ background: 'linear-gradient(140deg,rgba(56,189,248,.09),rgba(56,189,248,.02))', border: '1px solid rgba(56,189,248,.28)', borderRadius: 16, padding: '16px 18px' }}>
            <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 5 }}>{t.linkCreate}</div>
            <div style={{ fontSize: 11.5, color: color.textDim, marginBottom: 14 }}>{t.linkCreateHint}</div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
              <Field label={t.linkTagLabel} value={newTag} onChange={(e) => setNewTag(e.target.value)} placeholder="instagram" style={{ flex: 1, minWidth: 150 }} />
              <Field label={t.linkNoteLabel} value={newNote} onChange={(e) => setNewNote(e.target.value)} placeholder={t.linkNotePh} style={{ flex: 1, minWidth: 150 }} />
              <div style={{ flex: 1, minWidth: 130 }}>
                <div style={fieldLbl}>{t.linkDestLabel}</div>
                <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                  {DESTS.map((d) => (
                    <Hoverable key={d} style={chipStyle(newDest === d ? '#38BDF8' : color.textMuted)} onClick={() => setNewDest(d)}>{destLabel(d)}</Hoverable>
                  ))}
                </div>
              </div>
              <Hoverable style={{ background: '#38BDF8', color: '#041018', fontWeight: 800, borderRadius: 10, padding: '10px 16px', cursor: 'pointer', opacity: busy ? 0.6 : 1 }} onClick={() => void createLink()}>＋ {t.linkCreateBtn}</Hoverable>
            </div>
            <div style={{ marginTop: 12, background: color.bgDeep, border: `1px solid ${line.soft}`, borderRadius: 10, padding: '10px 13px', fontFamily: font.mono, fontSize: 11, color: '#38BDF8' }}>{previewUrl}</div>
          </div>

          <Panel style={{ borderRadius: 16, padding: '16px 18px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 14 }}>
              <div style={{ fontWeight: 800, fontSize: 14 }}>{t.linkChannels}</div>
              <div style={{ display: 'flex', gap: 6 }}>
                {[{ id: 'earned', label: t.sortByEarned }, { id: 'regs', label: t.sortByRegs }, { id: 'conv', label: t.sortByConv }].map((cs) => (
                  <Hoverable key={cs.id} style={tabStyle(chanSort === cs.id)} onClick={() => setChanSort(cs.id)}>{cs.label}</Hoverable>
                ))}
              </div>
            </div>
            {sortedLinks.map((l, i) => (
              <div key={l.id} style={{ marginBottom: 12, paddingLeft: 4 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ width: 9, height: 9, borderRadius: 3, background: CHAN_COLORS[i % CHAN_COLORS.length] }} />
                  <span style={{ fontFamily: font.mono, fontWeight: 700 }}>{l.tag}</span>
                  <span style={{ flex: 1, fontSize: 11, color: color.textMuted }}>{l.note}</span>
                  <span style={{ fontFamily: font.display, fontWeight: 600, color: CHAN_COLORS[i % CHAN_COLORS.length] }}>{fmtRub(l.earned_kopecks, lang)}</span>
                </div>
                <div style={{ display: 'flex', gap: 14, paddingLeft: 19, marginTop: 6, flexWrap: 'wrap' }}>
                  {[
                    { v: l.clicks, k: t.linkColClicks },
                    { v: l.registrations, k: t.linkColRegs },
                    { v: l.paying_users, k: lang === 'ru' ? 'ПЛАТЯТ' : 'PAYING' },
                    { v: l.clicks ? `${((l.registrations / l.clicks) * 100).toFixed(1)}%` : '0%', k: 'CR' },
                  ].map((m) => (
                    <div key={m.k}><span style={{ fontFamily: font.mono, fontSize: 11 }}>{m.v}</span> <Eyebrow size={8}>{m.k}</Eyebrow></div>
                  ))}
                </div>
              </div>
            ))}
          </Panel>

          <Panel style={{ borderRadius: 16, overflow: 'hidden' }}>
            <div style={{ padding: '14px 18px', fontWeight: 800, borderBottom: `1px solid ${line.soft}` }}>{t.linkAll} · {links.length}</div>
            {links.map((l, i) => (
              <div key={l.id} style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '11px 18px', borderBottom: `1px solid ${line.soft}` }}>
                <span style={chipStyle(CHAN_COLORS[i % CHAN_COLORS.length])}>{l.tag}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontFamily: font.mono, fontSize: 10.5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{linkUrl(l)}</div>
                  <div style={{ fontSize: 10.5, color: color.textMuted }}>{l.note}</div>
                </div>
                <span style={{ fontFamily: font.mono, fontSize: 10.5 }}>{l.clicks}</span>
                <span style={{ fontFamily: font.mono, fontSize: 10.5, color: '#38BDF8' }}>{l.registrations}</span>
                <span style={{ fontFamily: font.mono, fontSize: 10.5, color: color.lime }}>{fmtRub(l.earned_kopecks, lang)}</span>
                <Hoverable style={{ cursor: 'pointer', color: color.textDim }} onClick={() => void copyLink(linkUrl(l))}><IcoCopy /></Hoverable>
              </div>
            ))}
          </Panel>
        </div>
      )}

      {tab === 'refs' && (
        <div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
            {sourceFilters.map((sf) => (
              <Hoverable key={sf.id} style={tabStyle(srcFilter === sf.id)} onClick={() => setSrcFilter(sf.id)}>{sf.label}</Hoverable>
            ))}
          </div>
          <Panel style={{ borderRadius: 16, overflow: 'hidden' }}>
            <div style={{ display: 'flex', gap: 6, padding: '12px 14px', borderBottom: `1px solid ${line.soft}`, fontFamily: font.mono, fontSize: 9, color: color.textMuted }}>
              <span style={{ flex: 2.2 }}>{t.partnerColUser}</span>
              <span style={{ width: 70 }}>{t.partnerColSource}</span>
              <span style={{ flex: 1 }}>{t.partnerColPlan}</span>
              <span style={{ width: 72, textAlign: 'right' }}>{t.partnerColPaid}</span>
              <span style={{ width: 72, textAlign: 'right' }}>{t.partnerColReward}</span>
            </div>
            {refs.length === 0 ? (
              <div style={{ padding: 34, textAlign: 'center', color: color.textMuted }}>{t.partnerNoRefs}</div>
            ) : refs.map((pr) => (
              <div key={pr.user_id} style={{ display: 'flex', gap: 6, padding: '11px 14px', borderBottom: `1px solid ${line.soft}`, fontSize: 12 }}>
                <span style={{ flex: 2.2, fontWeight: 600 }}>{pr.email_masked}</span>
                <span style={{ width: 70 }}><span style={chipStyle('#38BDF8')}>{pr.source_tag}</span></span>
                <span style={{ flex: 1, fontFamily: font.mono, fontSize: 10, color: color.textDim }}>{pr.plan}</span>
                <span style={{ width: 72, textAlign: 'right', fontFamily: font.mono, fontSize: 10 }}>{fmtRub(pr.paid_kopecks, lang)}</span>
                <span style={{ width: 72, textAlign: 'right', fontFamily: font.mono, fontSize: 10, color: color.lime }}>{fmtRub(pr.reward_kopecks, lang)}</span>
              </div>
            ))}
          </Panel>
        </div>
      )}

      {tab === 'assets' && (
        <div style={{ background: 'linear-gradient(140deg,rgba(192,132,252,.1),rgba(192,132,252,.02))', border: '1px solid rgba(192,132,252,.28)', borderRadius: 16, padding: '16px 18px' }}>
          <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 8 }}>{t.partnerTerms}</div>
          {[t.partnerTerm1, t.partnerTerm2, t.partnerTerm3, t.partnerTerm4].map((ptm) => (
            <div key={ptm} style={{ display: 'flex', gap: 9, marginBottom: 7 }}>
              <span style={{ display: 'flex', width: 14, height: 14, color: '#C084FC', marginTop: 2 }}><IcoCheck /></span>
              <span style={{ fontSize: 12, color: color.textDim, lineHeight: 1.5 }}>{ptm}</span>
            </div>
          ))}
        </div>
      )}
    </Fade>
  );
}

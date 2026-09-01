import { useCallback, useEffect, useState } from 'react';
import Hoverable from '../components/Hoverable';
import { IcoHeart } from '../components/Icons';
import { Fade, PageTitle, Panel } from '../components/ui';
import { useApp } from '../hooks/useApp';
import { fetchNews, toggleNewsLike } from '../api/actions';
import { color, font, line } from '../styles/tokens';

function fmtDate(iso, lang) {
  try {
    return new Date(iso).toLocaleDateString(lang === 'ru' ? 'ru-RU' : 'en-US', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return '';
  }
}

export default function News() {
  const { lang, cabinet } = useApp();
  const ru = lang === 'ru';
  const [rows, setRows] = useState([]);
  const [openId, setOpenId] = useState(null);

  const reload = useCallback(async () => {
    try {
      const data = await fetchNews(lang);
      setRows(Array.isArray(data) ? data : []);
    } catch (e) {
      cabinet.setError(e?.message || String(e));
    }
  }, [lang, cabinet]);

  useEffect(() => { void reload(); }, [reload]);

  const onLike = async (id, e) => {
    e?.stopPropagation?.();
    try {
      await toggleNewsLike(id);
      await reload();
    } catch (err) {
      cabinet.setError(err?.message || String(err));
    }
  };

  const open = rows.find((r) => Number(r.id) === Number(openId));

  return (
    <Fade data-screen-label={ru ? 'Новости' : 'News'}>
      <PageTitle style={{ marginBottom: 8 }}>{ru ? 'Новости и обновления' : 'News & updates'}</PageTitle>
      <div style={{ fontSize: 12.5, color: color.textDim, maxWidth: 640, lineHeight: 1.55, marginBottom: 18 }}>
        {ru ? 'Что нового в сервисе — кратко в ленте, подробности по клику.' : 'What is new — summary in the feed, details on click.'}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 720 }}>
        {rows.map((p) => (
          <Panel
            key={p.id}
            style={{ padding: 16, cursor: 'pointer', borderColor: p.is_pinned ? 'rgba(215,244,82,.35)' : line.hair }}
            onClick={() => setOpenId(p.id)}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
              {p.is_pinned && (
                <span style={{ fontFamily: font.mono, fontSize: 9, letterSpacing: 1.2, background: color.lime, color: color.limeInk, padding: '3px 8px', borderRadius: 20 }}>
                  {ru ? 'ГЛАВНОЕ' : 'FEATURED'}
                </span>
              )}
              <span style={{ fontFamily: font.mono, fontSize: 9.5, color: color.textGhost }}>{fmtDate(p.published_at, lang)}</span>
            </div>
            <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 17, lineHeight: 1.35, marginBottom: 8 }}>{p.title}</div>
            <div style={{ fontSize: 12.5, color: color.textDim, lineHeight: 1.6 }}>{p.summary}</div>
            <Hoverable
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 12, fontSize: 11.5, color: p.liked_by_me ? color.lime : color.textGhost, cursor: 'pointer' }}
              onClick={(e) => void onLike(p.id, e)}
            >
              <span style={{ display: 'flex', width: 14, height: 14 }}><IcoHeart /></span>
              {p.likes_count || 0}
            </Hoverable>
          </Panel>
        ))}
        {!rows.length && (
          <div style={{ fontSize: 12, color: color.textDim }}>{ru ? 'Пока нет новостей' : 'No news yet'}</div>
        )}
      </div>

      {open && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 50, background: 'rgba(6,7,9,.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }} onClick={() => setOpenId(null)}>
          <Panel style={{ width: 'min(92vw,560px)', padding: 20, maxHeight: '85vh', overflowY: 'auto' }} onClick={(e) => e.stopPropagation()}>
            <div style={{ fontFamily: font.mono, fontSize: 9.5, color: color.textGhost, marginBottom: 8 }}>{fmtDate(open.published_at, lang)}</div>
            <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 20, lineHeight: 1.3, marginBottom: 12 }}>{open.title}</div>
            <div style={{ fontSize: 13.5, color: color.textMid, lineHeight: 1.65, whiteSpace: 'pre-wrap' }}>{open.body || open.summary}</div>
            <Hoverable
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 16, color: open.liked_by_me ? color.lime : color.textDim, cursor: 'pointer' }}
              onClick={(e) => void onLike(open.id, e)}
            >
              <span style={{ display: 'flex', width: 14, height: 14, flexShrink: 0 }}><IcoHeart /></span>
              {open.likes_count || 0}
            </Hoverable>
          </Panel>
        </div>
      )}
    </Fade>
  );
}

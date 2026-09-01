import { useCallback, useEffect, useRef, useState } from 'react';
import Hoverable from '../components/Hoverable';
import { IcoHeart, IcoUpload } from '../components/Icons';
import { Chip, Fade, Field, LimeButton, PageTitle, Panel } from '../components/ui';
import { useApp } from '../hooks/useApp';
import { deleteReference, fetchReferences, toggleReferenceLike, uploadReference } from '../api/actions';
import { color, font, G, line } from '../styles/tokens';

export default function ReferenceLibrary() {
  const { lang, cabinet } = useApp();
  const ru = lang === 'ru';
  const uploadRef = useRef(null);
  const [tab, setTab] = useState('photo');
  const [rows, setRows] = useState([]);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [detail, setDetail] = useState(null);

  const reload = useCallback(async () => {
    try {
      const data = await fetchReferences(tab);
      setRows(Array.isArray(data) ? data : []);
    } catch (e) {
      cabinet.setError(e?.message || String(e));
    }
  }, [tab, cabinet]);

  useEffect(() => { void reload(); }, [reload]);

  const onUpload = async (file) => {
    if (!file) return;
    try {
      await uploadReference({ file, title, description });
      setTitle('');
      setDescription('');
      await reload();
    } catch (e) {
      cabinet.setError(e?.message || String(e));
    }
  };

  const onLike = async (id) => {
    try {
      await toggleReferenceLike(id);
      await reload();
      if (detail?.id === id) {
        const next = (await fetchReferences(tab)).find((r) => r.id === id);
        if (next) setDetail(next);
      }
    } catch (e) {
      cabinet.setError(e?.message || String(e));
    }
  };

  return (
    <Fade data-screen-label={ru ? 'Библиотека референсов' : 'Reference library'}>
      <PageTitle style={{ marginBottom: 8 }}>{ru ? 'Библиотека референсов' : 'Reference library'}</PageTitle>
      <div style={{ fontSize: 12.5, color: color.textDim, maxWidth: 640, lineHeight: 1.55, marginBottom: 16 }}>
        {ru ? 'Загрузите референс с кратким описанием — отдельно фото и видео.' : 'Upload a reference with a short note — photos and videos separated.'}
      </div>

      <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
        <Chip on={tab === 'photo'} onClick={() => setTab('photo')}>{ru ? 'Фото' : 'Photos'}</Chip>
        <Chip on={tab === 'video'} onClick={() => setTab('video')}>{ru ? 'Видео' : 'Videos'}</Chip>
      </div>

      <Panel style={{ padding: 16, marginBottom: 16, display: 'grid', gap: 10, maxWidth: 520 }}>
        <Field label={ru ? 'НАЗВАНИЕ' : 'TITLE'} value={title} onChange={(e) => setTitle(e.target.value)} />
        <Field label={ru ? 'ОПИСАНИЕ' : 'DESCRIPTION'} value={description} onChange={(e) => setDescription(e.target.value)} area />
        <LimeButton onClick={() => uploadRef.current?.click()}>
          <span style={{ display: 'flex', width: 15, height: 15 }}><IcoUpload /></span>
          {ru ? 'Прикрепить файл' : 'Attach file'}
        </LimeButton>
        <input ref={uploadRef} type="file" accept={tab === 'video' ? 'video/*' : 'image/*'} style={{ display: 'none' }} onChange={(e) => { void onUpload(e.target.files?.[0]); e.target.value = ''; }} />
      </Panel>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(180px,1fr))', gap: 12 }}>
        {rows.map((r, i) => (
          <Hoverable
            key={r.id}
            style={{ background: color.bgPanel, border: `1px solid ${line.hair}`, borderRadius: 14, overflow: 'hidden', cursor: 'pointer' }}
            hover={{ borderColor: 'rgba(215,244,82,.35)' }}
            onClick={() => setDetail(r)}
          >
            <div style={{ aspectRatio: '4/5', background: G[i % G.length], position: 'relative' }}>
              {r.preview_url && (
                r.media_type === 'video'
                  ? <video src={r.preview_url} style={{ width: '100%', height: '100%', objectFit: 'cover' }} muted />
                  : <img src={r.preview_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              )}
            </div>
            <div style={{ padding: 10 }}>
              <div style={{ fontSize: 12.5, fontWeight: 700 }}>{r.title || `#${r.id}`}</div>
              <div style={{ fontSize: 11, color: color.textDim, marginTop: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.description || '—'}</div>
              <Hoverable
                style={{ display: 'inline-flex', alignItems: 'center', gap: 5, marginTop: 8, fontSize: 11, color: r.liked_by_me ? color.lime : color.textGhost, cursor: 'pointer' }}
                onClick={(e) => { e.stopPropagation(); void onLike(r.id); }}
              >
                <span style={{ display: 'flex', width: 14, height: 14 }}><IcoHeart /></span>
                {r.likes_count || 0}
              </Hoverable>
            </div>
          </Hoverable>
        ))}
      </div>

      {detail && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 50, background: 'rgba(6,7,9,.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }} onClick={() => setDetail(null)}>
          <Panel style={{ width: 'min(92vw,520px)', padding: 18 }} onClick={(e) => e.stopPropagation()}>
            <div style={{ fontWeight: 800, fontSize: 16, marginBottom: 8 }}>{detail.title || `#${detail.id}`}</div>
            <div style={{ fontSize: 13, color: color.textMid, lineHeight: 1.6, marginBottom: 12, whiteSpace: 'pre-wrap' }}>{detail.description || '—'}</div>
            {detail.preview_url && (
              detail.media_type === 'video'
                ? <video src={detail.preview_url} controls style={{ width: '100%', borderRadius: 12, maxHeight: 360 }} />
                : <img src={detail.preview_url} alt="" style={{ width: '100%', borderRadius: 12, maxHeight: 360, objectFit: 'contain' }} />
            )}
            <div style={{ display: 'flex', gap: 10, marginTop: 14 }}>
              <Hoverable style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', color: detail.liked_by_me ? color.lime : color.textDim }} onClick={() => void onLike(detail.id)}>
                <IcoHeart /> {detail.likes_count || 0}
              </Hoverable>
              <Hoverable
                style={{ marginLeft: 'auto', color: color.red, fontSize: 12, fontWeight: 700, cursor: 'pointer' }}
                onClick={() => {
                  if (!window.confirm(ru ? 'Удалить референс?' : 'Delete reference?')) return;
                  void deleteReference(detail.id).then(() => { setDetail(null); return reload(); });
                }}
              >
                {ru ? 'Удалить' : 'Delete'}
              </Hoverable>
            </div>
          </Panel>
        </div>
      )}
    </Fade>
  );
}

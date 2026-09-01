import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Hoverable from '../components/Hoverable';
import { IcoHeart, IcoUpload } from '../components/Icons';
import { Chip, Fade, LimeButton, PageTitle, Panel } from '../components/ui';
import { useApp } from '../hooks/useApp';
import {
  deleteReference,
  fetchReferences,
  toggleReferenceLike,
  updateReferenceTags,
  uploadReferenceBatch,
} from '../api/actions';
import { color, font, G, line } from '../styles/tokens';

/** Пресеты тегов — ключ хранится в БД, label зависит от языка. */
const TAG_PRESETS = [
  { key: 'selfie', ru: 'селфи', en: 'selfie' },
  { key: 'face', ru: 'лицо', en: 'face' },
  { key: 'body', ru: 'тело', en: 'body' },
  { key: 'outfit', ru: 'одежда', en: 'outfit' },
  { key: 'location', ru: 'локация', en: 'location' },
  { key: 'pose', ru: 'поза', en: 'pose' },
  { key: 'lighting', ru: 'свет', en: 'lighting' },
  { key: 'mirror', ru: 'зеркало', en: 'mirror' },
  { key: 'phone', ru: 'телефон', en: 'phone' },
  { key: 'beach', ru: 'пляж', en: 'beach' },
  { key: 'gym', ru: 'зал', en: 'gym' },
  { key: 'lingerie', ru: 'бельё', en: 'lingerie' },
];

function fmtDate(iso, lang) {
  try {
    return new Date(iso).toLocaleDateString(lang === 'ru' ? 'ru-RU' : 'en-US', {
      day: 'numeric',
      month: 'short',
    });
  } catch {
    return '';
  }
}

/** Группируем файлы одной загрузки в одну карточку. */
function groupReferences(rows) {
  const map = new Map();
  for (const row of rows) {
    const key = row.upload_batch_id || `single-${row.id}`;
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(row);
  }
  return [...map.values()]
    .map((items) => items.sort((a, b) => a.id - b.id))
    .sort((a, b) => b[b.length - 1].id - a[a.length - 1].id);
}

function mergedTags(items) {
  const seen = new Set();
  const out = [];
  for (const item of items) {
    for (const tag of item.tags || []) {
      const t = String(tag).trim().toLowerCase();
      if (t && !seen.has(t)) {
        seen.add(t);
        out.push(t);
      }
    }
  }
  return out;
}

function totalLikes(items) {
  return items.reduce((sum, item) => sum + (item.likes_count || 0), 0);
}

function TagChip({ tag, on, onClick, ru }) {
  const preset = TAG_PRESETS.find((p) => p.key === tag);
  const label = preset ? (ru ? preset.ru : preset.en) : tag;
  return (
    <Chip on={on} onClick={onClick} style={{ fontSize: 10.5, padding: '4px 10px' }}>
      {label}
    </Chip>
  );
}

function MediaThumb({ item, style }) {
  if (!item?.preview_url) {
    return <div style={{ ...style, background: G[0] }} />;
  }
  if (item.media_type === 'video') {
    return (
      <video
        src={item.preview_url}
        style={{ ...style, objectFit: 'cover', width: '100%', height: '100%' }}
        muted
        playsInline
      />
    );
  }
  return (
    <img
      src={item.preview_url}
      alt=""
      style={{ ...style, objectFit: 'cover', width: '100%', height: '100%' }}
    />
  );
}

export default function ReferenceLibrary() {
  const { lang, cabinet } = useApp();
  const ru = lang === 'ru';
  const uploadRef = useRef(null);
  const setErrorRef = useRef(cabinet.setError);
  setErrorRef.current = cabinet.setError;

  const [filter, setFilter] = useState('all');
  const [rows, setRows] = useState([]);
  const [uploadTags, setUploadTags] = useState([]);
  const [customTag, setCustomTag] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [detail, setDetail] = useState(null);
  const [detailIdx, setDetailIdx] = useState(0);
  const [editTags, setEditTags] = useState([]);
  const [editCustom, setEditCustom] = useState('');
  const [savingTags, setSavingTags] = useState(false);

  const reload = useCallback(async () => {
    try {
      const mediaType = filter === 'all' ? null : filter;
      const data = await fetchReferences(mediaType);
      setRows(Array.isArray(data) ? data : []);
    } catch (e) {
      setErrorRef.current(e?.message || String(e));
    }
  }, [filter]);

  useEffect(() => { void reload(); }, [reload]);

  const groups = useMemo(() => groupReferences(rows), [rows]);

  const toggleUploadTag = (key) => {
    setUploadTags((prev) => (prev.includes(key) ? prev.filter((t) => t !== key) : [...prev, key]));
  };

  const addCustomUploadTag = () => {
    const tag = customTag.trim().toLowerCase().slice(0, 48);
    if (!tag || uploadTags.includes(tag)) {
      setCustomTag('');
      return;
    }
    setUploadTags((prev) => [...prev, tag]);
    setCustomTag('');
  };

  const onUpload = async (fileList) => {
    const files = [...(fileList || [])].filter(Boolean);
    if (!files.length || uploading) return;
    setUploading(true);
    try {
      await uploadReferenceBatch({ files, tags: uploadTags });
      await reload();
    } catch (e) {
      setErrorRef.current(e?.message || String(e));
    } finally {
      setUploading(false);
    }
  };

  const openDetail = (items) => {
    setDetail(items);
    setDetailIdx(0);
    setEditTags(mergedTags(items));
    setEditCustom('');
  };

  const closeDetail = () => {
    setDetail(null);
    setDetailIdx(0);
  };

  const onLike = async (id, e) => {
    e?.stopPropagation?.();
    try {
      await toggleReferenceLike(id);
      await reload();
    } catch (err) {
      setErrorRef.current(err?.message || String(err));
    }
  };

  const toggleEditTag = (key) => {
    setEditTags((prev) => (prev.includes(key) ? prev.filter((t) => t !== key) : [...prev, key]));
  };

  const addCustomEditTag = () => {
    const tag = editCustom.trim().toLowerCase().slice(0, 48);
    if (!tag || editTags.includes(tag)) {
      setEditCustom('');
      return;
    }
    setEditTags((prev) => [...prev, tag]);
    setEditCustom('');
  };

  const saveTags = async () => {
    if (!detail?.length || savingTags) return;
    setSavingTags(true);
    try {
      await updateReferenceTags(detail[0].id, editTags);
      await reload();
      closeDetail();
    } catch (e) {
      setErrorRef.current(e?.message || String(e));
    } finally {
      setSavingTags(false);
    }
  };

  const deleteGroup = async () => {
    if (!detail?.length) return;
    const msg = detail.length > 1
      ? (ru ? `Удалить все ${detail.length} файлов?` : `Delete all ${detail.length} files?`)
      : (ru ? 'Удалить референс?' : 'Delete reference?');
    if (!window.confirm(msg)) return;
    try {
      for (const item of detail) {
        await deleteReference(item.id);
      }
      closeDetail();
      await reload();
    } catch (e) {
      setErrorRef.current(e?.message || String(e));
    }
  };

  const activeItem = detail?.[detailIdx] || null;

  return (
    <Fade data-screen-label={ru ? 'Библиотека референсов' : 'Reference library'}>
      <PageTitle style={{ marginBottom: 8 }}>
        {ru ? 'Библиотека референсов' : 'Reference library'}
      </PageTitle>
      <div style={{ fontSize: 12.5, color: color.textDim, maxWidth: 640, lineHeight: 1.55, marginBottom: 16 }}>
        {ru
          ? 'Загрузите фото или видео — одним файлом или паком. Отметьте теги или добавьте свои.'
          : 'Upload photos or videos — single file or batch. Pick tags or add your own.'}
      </div>

      <div style={{ display: 'flex', gap: 6, marginBottom: 14, flexWrap: 'wrap' }}>
        <Chip on={filter === 'all'} onClick={() => setFilter('all')}>{ru ? 'Все' : 'All'}</Chip>
        <Chip on={filter === 'photo'} onClick={() => setFilter('photo')}>{ru ? 'Фото' : 'Photos'}</Chip>
        <Chip on={filter === 'video'} onClick={() => setFilter('video')}>{ru ? 'Видео' : 'Videos'}</Chip>
      </div>

      {/* Зона загрузки */}
      <Panel
        style={{
          padding: 18,
          marginBottom: 18,
          maxWidth: 720,
          borderStyle: dragOver ? 'solid' : 'dashed',
          borderColor: dragOver ? 'rgba(215,244,82,.55)' : line.hair,
          background: dragOver ? 'rgba(215,244,82,.04)' : color.bgPanel,
        }}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          void onUpload(e.dataTransfer.files);
        }}
      >
        <div style={{ fontSize: 11, fontFamily: font.mono, letterSpacing: 1.1, color: color.textGhost, marginBottom: 10 }}>
          {ru ? 'ЗАГРУЗКА' : 'UPLOAD'}
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
          {TAG_PRESETS.map((p) => (
            <TagChip
              key={p.key}
              tag={p.key}
              ru={ru}
              on={uploadTags.includes(p.key)}
              onClick={() => toggleUploadTag(p.key)}
            />
          ))}
        </div>
        <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
          <input
            value={customTag}
            onChange={(e) => setCustomTag(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') addCustomUploadTag(); }}
            placeholder={ru ? 'Свой тег…' : 'Custom tag…'}
            style={{
              flex: '1 1 160px',
              minWidth: 140,
              background: color.bgDeep,
              border: `1px solid ${line.hair}`,
              borderRadius: 10,
              padding: '8px 12px',
              color: color.text,
              fontSize: 12.5,
            }}
          />
          <Hoverable
            style={{ fontSize: 12, color: color.lime, fontWeight: 700, cursor: 'pointer', alignSelf: 'center' }}
            onClick={addCustomUploadTag}
          >
            {ru ? '+ тег' : '+ tag'}
          </Hoverable>
        </div>
        {!!uploadTags.length && (
          <div style={{ fontSize: 11, color: color.textDim, marginBottom: 12 }}>
            {ru ? 'К загрузке:' : 'For upload:'}{' '}
            {uploadTags.map((t) => {
              const p = TAG_PRESETS.find((x) => x.key === t);
              return p ? (ru ? p.ru : p.en) : t;
            }).join(', ')}
          </div>
        )}
        <LimeButton disabled={uploading} onClick={() => uploadRef.current?.click()}>
          <span style={{ display: 'flex', width: 15, height: 15 }}><IcoUpload /></span>
          {uploading
            ? (ru ? 'Загрузка…' : 'Uploading…')
            : (ru ? 'Выбрать файлы' : 'Choose files')}
        </LimeButton>
        <div style={{ fontSize: 11, color: color.textGhost, marginTop: 10 }}>
          {ru ? 'Можно перетащить сюда несколько файлов' : 'Drag and drop multiple files here'}
        </div>
        <input
          ref={uploadRef}
          type="file"
          accept="image/*,video/*"
          multiple
          style={{ display: 'none' }}
          onChange={(e) => { void onUpload(e.target.files); e.target.value = ''; }}
        />
      </Panel>

      {/* Вертикальная лента карточек */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 720 }}>
        {groups.map((items) => {
          const tags = mergedTags(items);
          const primary = items[items.length - 1];
          const isBatch = items.length > 1;
          return (
            <Panel
              key={items.map((i) => i.id).join('-')}
              style={{ padding: 0, overflow: 'hidden', cursor: 'pointer' }}
              onClick={() => openDetail(items)}
            >
              <div style={{ display: 'flex', gap: 0, minHeight: isBatch ? 140 : 200 }}>
                {isBatch ? (
                  <div style={{ display: 'flex', flex: 1, gap: 2, background: color.bgDeep }}>
                    {items.slice(0, 4).map((item, idx) => (
                      <div key={item.id} style={{ flex: 1, position: 'relative', minWidth: 0 }}>
                        <MediaThumb item={item} style={{ display: 'block', height: 140 }} />
                        {idx === 3 && items.length > 4 && (
                          <div style={{
                            position: 'absolute',
                            inset: 0,
                            background: 'rgba(6,7,9,.55)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontWeight: 800,
                            fontSize: 18,
                          }}
                          >
                            +{items.length - 4}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ width: '100%', maxHeight: 320, background: G[primary.id % G.length] }}>
                    <MediaThumb item={primary} style={{ display: 'block', width: '100%', maxHeight: 320 }} />
                  </div>
                )}
              </div>
              <div style={{ padding: '12px 14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: tags.length ? 8 : 0 }}>
                  <span style={{ fontFamily: font.mono, fontSize: 9.5, color: color.textGhost }}>
                    {fmtDate(primary.created_at, lang)}
                  </span>
                  {isBatch && (
                    <span style={{ fontSize: 10.5, color: color.textDim }}>
                      {items.length} {ru ? 'файлов' : 'files'}
                    </span>
                  )}
                  {!isBatch && primary.media_type === 'video' && (
                    <span style={{ fontSize: 10, color: color.lime, fontWeight: 700 }}>VIDEO</span>
                  )}
                </div>
                {!!tags.length && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {tags.slice(0, 8).map((tag) => (
                      <span
                        key={tag}
                        style={{
                          fontSize: 10,
                          padding: '3px 8px',
                          borderRadius: 20,
                          background: 'rgba(215,244,82,.08)',
                          color: color.lime,
                          border: `1px solid rgba(215,244,82,.2)`,
                        }}
                      >
                        {TAG_PRESETS.find((p) => p.key === tag)?.[ru ? 'ru' : 'en'] || tag}
                      </span>
                    ))}
                    {tags.length > 8 && (
                      <span style={{ fontSize: 10, color: color.textGhost }}>+{tags.length - 8}</span>
                    )}
                  </div>
                )}
                <Hoverable
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    marginTop: 10,
                    fontSize: 11,
                    color: items.some((i) => i.liked_by_me) ? color.lime : color.textGhost,
                    cursor: 'pointer',
                  }}
                  onClick={(e) => void onLike(primary.id, e)}
                >
                  <span style={{ display: 'flex', width: 14, height: 14 }}><IcoHeart /></span>
                  {totalLikes(items)}
                </Hoverable>
              </div>
            </Panel>
          );
        })}
        {!groups.length && (
          <div style={{ fontSize: 12, color: color.textDim, padding: '8px 0' }}>
            {ru ? 'Пока нет референсов — загрузите первый файл' : 'No references yet — upload your first file'}
          </div>
        )}
      </div>

      {/* Просмотр и редактирование тегов */}
      {detail?.length > 0 && activeItem && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 50,
            background: 'rgba(6,7,9,.82)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
          }}
          onClick={closeDetail}
        >
          <Panel
            style={{ width: 'min(92vw,560px)', padding: 18, maxHeight: '92vh', overflow: 'auto' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ position: 'relative', marginBottom: 14, borderRadius: 12, overflow: 'hidden', background: color.bgDeep }}>
              {activeItem.media_type === 'video' ? (
                <video
                  src={activeItem.preview_url}
                  controls
                  style={{ width: '100%', maxHeight: 420, display: 'block' }}
                />
              ) : (
                <img
                  src={activeItem.preview_url}
                  alt=""
                  style={{ width: '100%', maxHeight: 420, objectFit: 'contain', display: 'block' }}
                />
              )}
              {detail.length > 1 && (
                <>
                  <Hoverable
                    style={{
                      position: 'absolute',
                      left: 8,
                      top: '50%',
                      transform: 'translateY(-50%)',
                      width: 36,
                      height: 36,
                      borderRadius: '50%',
                      background: 'rgba(6,7,9,.65)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      cursor: 'pointer',
                      color: color.text,
                      fontSize: 18,
                    }}
                    onClick={() => setDetailIdx((i) => (i > 0 ? i - 1 : detail.length - 1))}
                  >
                    ‹
                  </Hoverable>
                  <Hoverable
                    style={{
                      position: 'absolute',
                      right: 8,
                      top: '50%',
                      transform: 'translateY(-50%)',
                      width: 36,
                      height: 36,
                      borderRadius: '50%',
                      background: 'rgba(6,7,9,.65)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      cursor: 'pointer',
                      color: color.text,
                      fontSize: 18,
                    }}
                    onClick={() => setDetailIdx((i) => (i < detail.length - 1 ? i + 1 : 0))}
                  >
                    ›
                  </Hoverable>
                  <div style={{
                    position: 'absolute',
                    bottom: 10,
                    left: '50%',
                    transform: 'translateX(-50%)',
                    fontSize: 11,
                    background: 'rgba(6,7,9,.7)',
                    padding: '4px 10px',
                    borderRadius: 20,
                  }}
                  >
                    {detailIdx + 1} / {detail.length}
                  </div>
                </>
              )}
            </div>

            <div style={{ fontSize: 11, fontFamily: font.mono, letterSpacing: 1.1, color: color.textGhost, marginBottom: 8 }}>
              {ru ? 'ТЕГИ' : 'TAGS'}
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
              {TAG_PRESETS.map((p) => (
                <TagChip
                  key={p.key}
                  tag={p.key}
                  ru={ru}
                  on={editTags.includes(p.key)}
                  onClick={() => toggleEditTag(p.key)}
                />
              ))}
            </div>
            <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
              <input
                value={editCustom}
                onChange={(e) => setEditCustom(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') addCustomEditTag(); }}
                placeholder={ru ? 'Свой тег…' : 'Custom tag…'}
                style={{
                  flex: '1 1 160px',
                  minWidth: 140,
                  background: color.bgDeep,
                  border: `1px solid ${line.hair}`,
                  borderRadius: 10,
                  padding: '8px 12px',
                  color: color.text,
                  fontSize: 12.5,
                }}
              />
              <Hoverable
                style={{ fontSize: 12, color: color.lime, fontWeight: 700, cursor: 'pointer', alignSelf: 'center' }}
                onClick={addCustomEditTag}
              >
                {ru ? '+ тег' : '+ tag'}
              </Hoverable>
            </div>

            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <LimeButton disabled={savingTags} onClick={() => void saveTags()}>
                {savingTags ? (ru ? 'Сохранение…' : 'Saving…') : (ru ? 'Сохранить теги' : 'Save tags')}
              </LimeButton>
              <Hoverable
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6, cursor: 'pointer', color: activeItem.liked_by_me ? color.lime : color.textDim }}
                onClick={() => void onLike(activeItem.id)}
              >
                <span style={{ display: 'flex', width: 14, height: 14, flexShrink: 0 }}><IcoHeart /></span>
                {activeItem.likes_count || 0}
              </Hoverable>
              <Hoverable
                style={{ marginLeft: 'auto', color: color.red, fontSize: 12, fontWeight: 700, cursor: 'pointer' }}
                onClick={() => void deleteGroup()}
              >
                {detail.length > 1 ? (ru ? 'Удалить пак' : 'Delete pack') : (ru ? 'Удалить' : 'Delete')}
              </Hoverable>
            </div>
          </Panel>
        </div>
      )}
    </Fade>
  );
}

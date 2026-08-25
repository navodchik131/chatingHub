import { useMemo, useRef, useState } from 'react';

import Hoverable from '../components/Hoverable';
import { photoKindShortLabel } from '../api/helpers';
import { color, font, line } from '../styles/tokens';
import { PICKER_FILTERS, roleFromKind } from './seedanceDirectorConstants';

async function fileFromModelImage(im) {
  const res = await fetch(im.url, { credentials: 'include' });
  if (!res.ok) throw new Error(`Не удалось загрузить фото модели #${im.id}`);
  const blob = await res.blob();
  const ext = (blob.type || '').includes('png') ? 'png' : 'jpg';
  const kind = (im.kind || 'other').replace(/[^\w-]+/g, '_');
  return new File([blob], `model_${im.id}_${kind}.${ext}`, {
    type: blob.type || 'image/jpeg',
  });
}

function filterLabel(f, lang) {
  if (f === 'all') return lang === 'ru' ? 'все' : 'all';
  return f;
}

function roleFilterMatch(im, filter) {
  if (filter === 'all') return true;
  const role = roleFromKind(im.kind);
  if (filter === 'outfit') return role === 'outfit' || role === 'wardrobe';
  if (filter === 'first frame') return role === 'first frame' || im.kind === 'other';
  return role === filter;
}

/**
 * Модалка выбора фото из карточек персонажей (мультивыбор, как в .dc.html).
 */
export default function SeedanceDirectorPicker({
  lang,
  models,
  initialModelId,
  onClose,
  onConfirm,
  onUploadDisk,
  onError,
}) {
  const [pickerModelId, setPickerModelId] = useState(
    () => String(initialModelId || models[0]?.id || ''),
  );
  const [filter, setFilter] = useState('all');
  const [selectedIds, setSelectedIds] = useState([]);
  const [busy, setBusy] = useState(false);
  const diskInputRef = useRef(null);

  const selectedModel = useMemo(
    () => models.find((m) => String(m.id) === String(pickerModelId)) || null,
    [models, pickerModelId],
  );
  const modelImages = selectedModel?.images || selectedModel?.raw?.images || [];

  const gallery = useMemo(
    () => modelImages.filter((im) => roleFilterMatch(im, filter)),
    [modelImages, filter],
  );

  const toggleImage = (id) => {
    setSelectedIds((prev) => (
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    ));
  };

  const selectedImages = useMemo(
    () => selectedIds
      .map((id) => modelImages.find((im) => im.id === id))
      .filter(Boolean),
    [selectedIds, modelImages],
  );

  const confirm = async () => {
    if (!selectedImages.length || busy) return;
    setBusy(true);
    onError(null);
    try {
      const items = await Promise.all(
        selectedImages.map(async (im) => ({
          file: await fileFromModelImage(im),
          role: roleFromKind(im.kind),
          preview: im.url,
          modelImageId: im.id,
        })),
      );
      onConfirm(items, pickerModelId);
    } catch (e) {
      onError(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const pill = (active) => ({
    fontFamily: font.mono,
    fontSize: 10,
    letterSpacing: 0.4,
    padding: '6px 11px',
    borderRadius: 20,
    cursor: 'pointer',
    background: active ? 'rgba(215,244,82,.13)' : 'rgba(255,255,255,.04)',
    border: `1px solid ${active ? 'rgba(215,244,82,.4)' : line.soft}`,
    color: active ? color.lime : color.textDim,
  });

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 80,
        background: 'rgba(6,7,9,.72)',
        backdropFilter: 'blur(6px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%',
          maxWidth: 1020,
          maxHeight: 'min(92vh, 860px)',
          display: 'flex',
          flexDirection: 'column',
          background: '#0E0F12',
          border: `1px solid ${line.mid}`,
          borderRadius: 22,
          overflow: 'hidden',
          boxShadow: '0 40px 120px rgba(0,0,0,.7)',
        }}
      >
        {/* Шапка модалки */}
        <div
          style={{
            flex: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: 14,
            padding: '18px 22px',
            borderBottom: `1px solid ${line.hair}`,
          }}
        >
          <div>
            <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 17, letterSpacing: -0.3 }}>
              {lang === 'ru' ? 'Фото из карточки персонажа' : 'Photos from character card'}
            </div>
            <div style={{ fontSize: 11.5, color: color.textFaint, marginTop: 3 }}>
              {lang === 'ru'
                ? 'Выберите кадры — роль подставится автоматически, её можно поменять после добавления.'
                : 'Pick frames — roles are auto-filled and editable after adding.'}
            </div>
          </div>
          <div style={{ flex: 1 }} />
          <Hoverable
            onClick={onClose}
            style={{
              width: 30,
              height: 30,
              borderRadius: 9,
              display: 'grid',
              placeItems: 'center',
              fontSize: 13,
              color: color.textDim,
              cursor: 'pointer',
              background: 'rgba(255,255,255,.04)',
            }}
            hover={{ background: 'rgba(255,255,255,.1)', color: color.text }}
          >
            ✕
          </Hoverable>
        </div>

        <div style={{ flex: 1, minHeight: 0, display: 'flex' }}>
          {/* Список персонажей */}
          <div
            style={{
              width: 216,
              flex: 'none',
              borderRight: `1px solid ${line.hair}`,
              padding: '14px 12px',
              overflowY: 'auto',
              background: color.bg,
            }}
          >
            <div
              style={{
                fontFamily: font.mono,
                fontSize: 9,
                letterSpacing: 1.8,
                color: color.textGhost,
                padding: '2px 8px 9px',
              }}
            >
              {lang === 'ru' ? 'ПЕРСОНАЖИ' : 'CHARACTERS'}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {models.map((m) => {
                const on = String(m.id) === String(pickerModelId);
                const imgs = m.images || m.raw?.images || [];
                const avatar = imgs[0]?.url;
                return (
                  <Hoverable
                    key={m.id}
                    onClick={() => {
                      setPickerModelId(String(m.id));
                      setFilter('all');
                      setSelectedIds([]);
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      padding: '8px 9px',
                      borderRadius: 12,
                      cursor: 'pointer',
                      background: on ? 'rgba(215,244,82,.08)' : 'rgba(255,255,255,.02)',
                      boxShadow: on ? 'inset 0 0 0 1px rgba(215,244,82,.28)' : 'none',
                    }}
                  >
                    {avatar ? (
                      <img
                        src={avatar}
                        alt=""
                        style={{ width: 32, height: 32, borderRadius: '50%', objectFit: 'cover' }}
                      />
                    ) : (
                      <div
                        style={{
                          width: 32,
                          height: 32,
                          borderRadius: '50%',
                          background: color.raised,
                        }}
                      />
                    )}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          fontSize: 12.5,
                          fontWeight: on ? 800 : 600,
                          color: on ? color.lime : color.textMid,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {m.name || `#${m.id}`}
                      </div>
                      <div style={{ fontFamily: font.mono, fontSize: 9.5, color: color.textMuted, marginTop: 2 }}>
                        {imgs.length} {lang === 'ru' ? 'фото' : 'photos'}
                      </div>
                    </div>
                  </Hoverable>
                );
              })}
            </div>
            <div
              style={{
                marginTop: 14,
                borderTop: `1px solid ${line.hair}`,
                paddingTop: 12,
                display: 'flex',
                flexDirection: 'column',
                gap: 7,
              }}
            >
              <input
                ref={diskInputRef}
                type="file"
                accept="image/*"
                multiple
                hidden
                onChange={(e) => {
                  onUploadDisk?.(e.target.files);
                  e.target.value = '';
                }}
              />
              <Hoverable
                onClick={() => diskInputRef.current?.click()}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 7,
                  border: `1px dashed ${line.dashed}`,
                  borderRadius: 10,
                  padding: 9,
                  fontSize: 11.5,
                  fontWeight: 700,
                  color: color.textDim,
                  cursor: 'pointer',
                }}
                hover={{ borderColor: 'rgba(215,244,82,.4)', color: color.lime }}
              >
                ↑ {lang === 'ru' ? 'Загрузить с диска' : 'Upload from disk'}
              </Hoverable>
              <div style={{ fontSize: 10.5, color: color.textGhost, lineHeight: 1.45, padding: '0 2px' }}>
                {lang === 'ru'
                  ? 'Загруженные файлы не попадают в карточку персонажа.'
                  : 'Uploaded files are not saved to the character card.'}
              </div>
            </div>
          </div>

          {/* Галерея */}
          <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
            <div
              style={{
                flex: 'none',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '13px 18px',
                borderBottom: `1px solid ${line.hair}`,
                flexWrap: 'wrap',
              }}
            >
              {PICKER_FILTERS.map((f) => (
                <Hoverable
                  key={f}
                  onClick={() => setFilter(f)}
                  style={pill(filter === f)}
                  hover={{}}
                >
                  {filterLabel(f, lang)}
                </Hoverable>
              ))}
              <div style={{ flex: 1 }} />
              <div style={{ fontFamily: font.mono, fontSize: 10, color: color.textMuted }}>
                {modelImages.length} {lang === 'ru' ? 'фото в карточке ·' : 'photos · '}
                {selectedModel?.name || '—'}
              </div>
            </div>

            <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '16px 18px 20px' }}>
              {!gallery.length ? (
                <div style={{ fontSize: 13, color: color.textDim }}>
                  {lang === 'ru' ? 'Нет фото для этого фильтра.' : 'No photos for this filter.'}
                </div>
              ) : (
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
                    gap: 12,
                  }}
                >
                  {gallery.map((im) => {
                    const on = selectedIds.includes(im.id);
                    const order = on ? selectedIds.indexOf(im.id) + 1 : 0;
                    const role = roleFromKind(im.kind);
                    return (
                      <Hoverable
                        key={im.id}
                        onClick={() => toggleImage(im.id)}
                        style={{
                          borderRadius: 14,
                          overflow: 'hidden',
                          cursor: 'pointer',
                          background: color.surface,
                          border: `1px solid ${on ? 'rgba(215,244,82,.5)' : line.soft}`,
                        }}
                      >
                        <div style={{ position: 'relative', width: '100%', aspectRatio: '3/4', background: '#15171B' }}>
                          <img
                            src={im.url}
                            alt=""
                            style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                          />
                          <div
                            style={{
                              position: 'absolute',
                              top: 7,
                              right: 7,
                              width: 20,
                              height: 20,
                              borderRadius: 6,
                              display: 'grid',
                              placeItems: 'center',
                              fontSize: 11,
                              fontWeight: 800,
                              background: on ? color.lime : 'rgba(10,11,13,.6)',
                              border: `1px solid ${on ? color.lime : 'rgba(255,255,255,.28)'}`,
                              color: on ? color.limeInk : 'transparent',
                            }}
                          >
                            {on ? '✓' : ''}
                          </div>
                          {order > 0 ? (
                            <div
                              style={{
                                position: 'absolute',
                                left: 7,
                                top: 7,
                                fontFamily: font.mono,
                                fontSize: 9,
                                fontWeight: 600,
                                color: color.limeInk,
                                background: color.lime,
                                borderRadius: 6,
                                padding: '2px 7px',
                              }}
                            >
                              {order}
                            </div>
                          ) : null}
                          <div
                            style={{
                              position: 'absolute',
                              left: 7,
                              bottom: 7,
                              fontFamily: font.mono,
                              fontSize: 9,
                              color: color.text,
                              background: 'rgba(10,11,13,.74)',
                              borderRadius: 6,
                              padding: '2px 7px',
                            }}
                          >
                            {role}
                          </div>
                        </div>
                        <div style={{ padding: '8px 9px 9px' }}>
                          <div
                            style={{
                              fontFamily: font.mono,
                              fontSize: 9.5,
                              color: color.textFaint,
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {im.filename || `#${im.id}`}
                          </div>
                          <div style={{ fontSize: 10, color: color.textGhost, marginTop: 3 }}>
                            {photoKindShortLabel(lang, im.kind) || im.kind}
                          </div>
                        </div>
                      </Hoverable>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Футер модалки */}
        <div
          style={{
            flex: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: 14,
            padding: '14px 22px',
            borderTop: `1px solid ${line.hair}`,
            background: color.bg,
            flexWrap: 'wrap',
          }}
        >
          <div style={{ display: 'flex', gap: 5 }}>
            {selectedImages.slice(0, 5).map((im) => (
              <img
                key={im.id}
                src={im.url}
                alt=""
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 9,
                  objectFit: 'cover',
                  boxShadow: '0 0 0 1px rgba(215,244,82,.4)',
                }}
              />
            ))}
          </div>
          <div style={{ fontSize: 12, color: color.textDim }}>
            {selectedIds.length
              ? lang === 'ru'
                ? `Выбрано ${selectedIds.length} · роли подставятся автоматически`
                : `${selectedIds.length} selected · roles auto-filled`
              : lang === 'ru'
                ? 'Ничего не выбрано'
                : 'Nothing selected'}
          </div>
          <div style={{ flex: 1 }} />
          <Hoverable
            onClick={onClose}
            style={{
              fontSize: 11.5,
              fontWeight: 700,
              borderRadius: 10,
              padding: '10px 16px',
              background: color.raised,
              border: `1px solid ${line.soft}`,
              color: color.textMid,
              cursor: 'pointer',
            }}
            hover={{ borderColor: line.strong, color: color.text }}
          >
            {lang === 'ru' ? 'Отмена' : 'Cancel'}
          </Hoverable>
          <Hoverable
            onClick={confirm}
            style={{
              fontSize: 11.5,
              fontWeight: 800,
              borderRadius: 10,
              padding: '10px 18px',
              background: selectedIds.length && !busy ? color.lime : 'rgba(255,255,255,.03)',
              border: `1px solid ${selectedIds.length && !busy ? color.lime : line.hair}`,
              color: selectedIds.length && !busy ? color.limeInk : color.textGhost,
              cursor: selectedIds.length && !busy ? 'pointer' : 'not-allowed',
            }}
          >
            {busy
              ? '…'
              : selectedIds.length
                ? lang === 'ru'
                  ? `Добавить ${selectedIds.length} фото`
                  : `Add ${selectedIds.length} photos`
                : lang === 'ru'
                  ? 'Добавить фото'
                  : 'Add photos'}
          </Hoverable>
        </div>
      </div>
    </div>
  );
}

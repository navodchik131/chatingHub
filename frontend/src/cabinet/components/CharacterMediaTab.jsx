import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Hoverable from '../components/Hoverable';
import { IcoUpload } from '../components/Icons';
import { Chip, Field, LimeButton, Panel } from '../components/ui';
import { useApp } from '../hooks/useApp';
import {
  createCompanionMediaPack,
  deleteCompanionMediaAsset,
  deleteCompanionMediaPack,
  fetchCompanionMediaAssets,
  fetchCompanionMediaPacks,
  importCompanionMediaFromGeneration,
  reindexCompanionMedia,
  searchCompanionMedia,
  updateCompanionMediaAsset,
  updateCompanionMediaPack,
  uploadCompanionMediaAsset,
} from '../api/actions';
import { color, font, G, line } from '../styles/tokens';
import { fieldLbl, inputSt } from '../styles/mixins';

function fmtUsdCents(cents) {
  const v = Math.max(0, Number(cents) || 0);
  if (v === 0) return '$0';
  return `$${(v / 100).toFixed(v % 100 ? 2 : 0)}`;
}

function parseUsdToCents(raw) {
  const s = String(raw ?? '').trim().replace(',', '.');
  if (!s) return 0;
  const n = Number(s);
  if (!Number.isFinite(n) || n < 0) return 0;
  return Math.round(n * 100);
}

const tierMeta = {
  free: { label: 'FREE', color: '#4ADE80', bg: 'rgba(74,222,128,.13)', bd: 'rgba(74,222,128,.34)' },
  teaser: { label: 'TEASER', color: '#F0A814', bg: 'rgba(240,168,20,.13)', bd: 'rgba(240,168,20,.34)' },
  paid: { label: 'PAID', color: color.lime, bg: 'rgba(215,244,82,.13)', bd: 'rgba(215,244,82,.34)' },
};

function useActiveChar() {
  const { s, cabinet } = useApp();
  const charId = s.charDetail;
  const model = (cabinet.models || []).find((m) => String(m.id) === String(charId));
  return { charId, model, cabinet };
}

export default function TabMedia() {
  const { lang, cabinet } = useApp();
  const { charId, model } = useActiveChar();
  const ru = lang === 'ru';
  const uploadRef = useRef(null);

  const [subTab, setSubTab] = useState('assets');
  const [assets, setAssets] = useState([]);
  const [packs, setPacks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selId, setSelId] = useState(null);
  const [typeFilter, setTypeFilter] = useState('all');
  const [tierFilter, setTierFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [draft, setDraft] = useState(null);
  const [searchQ, setSearchQ] = useState('');
  const [searchConv, setSearchConv] = useState('');
  const [searchOut, setSearchOut] = useState(null);
  const [packName, setPackName] = useState('');
  const [importGenId, setImportGenId] = useState('');
  const [uploading, setUploading] = useState(false);

  const ml = useMemo(() => ({
    title: ru ? 'Медиатека персонажа' : 'Character media library',
    desc: ru
      ? 'Фото и видео для AI-компаньона. Бот ищет по смыслу (теги + описание) и не шлёт одно и то же дважды.'
      : 'Photos and videos for the AI companion. Semantic search; no repeats per fan.',
    upload: ru ? 'Загрузить' : 'Upload',
    fromStudio: ru ? 'Импорт из студии' : 'From studio',
    tabAssets: ru ? 'Файлы' : 'Assets',
    tabPacks: ru ? 'Паки' : 'Packs',
    tabSearch: ru ? 'Тест поиска' : 'Search test',
    fPrice: ru ? 'ЦЕНА, $' : 'PRICE, $',
    save: ru ? 'Сохранить' : 'Save',
    del: ru ? 'Удалить' : 'Delete',
    reindex: ru ? 'Пересчитать embeddings' : 'Reindex embeddings',
    run: ru ? 'Найти' : 'Search',
    newPack: ru ? 'Новый пак' : 'New pack',
    maxSend: ru ? 'Лимит на диалог' : 'Per-dialog cap',
  }), [ru]);

  const setErrorRef = useRef(cabinet.setError);
  setErrorRef.current = cabinet.setError;

  const reload = useCallback(async () => {
    if (!charId) return;
    setLoading(true);
    try {
      const [a, p] = await Promise.all([
        fetchCompanionMediaAssets(Number(charId)),
        fetchCompanionMediaPacks(Number(charId)),
      ]);
      setAssets(Array.isArray(a) ? a : []);
      setPacks(Array.isArray(p) ? p : []);
    } catch (e) {
      setErrorRef.current(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }, [charId]);

  // Перезагрузка только при смене персонажа — не сбрасываем форму на каждый refresh контекста.
  useEffect(() => {
    setSelId(null);
    setDraft(null);
    void reload();
  }, [charId, reload]);

  const selected = assets.find((a) => Number(a.id) === Number(selId)) || null;

  // Черновик только при выборе другого файла, не при фоновом reload списка.
  useEffect(() => {
    if (!selId) {
      setDraft(null);
      return;
    }
    const row = assets.find((a) => Number(a.id) === Number(selId));
    if (!row) return;
    setDraft({
      title: row.title || '',
      description: row.description || '',
      tags: (row.tags || []).join(', '),
      tier: row.tier || 'teaser',
      priceUsd: row.price_usd_cents ? (row.price_usd_cents / 100).toFixed(row.price_usd_cents % 100 ? 2 : 0) : '0',
      pack_id: row.pack_id || '',
    });
  }, [selId]);

  const filtered = assets.filter((a) => {
    if (typeFilter !== 'all' && a.media_type !== typeFilter) return false;
    if (tierFilter !== 'all' && a.tier !== tierFilter) return false;
    if (!query.trim()) return true;
    const blob = `${a.title || ''} ${a.description || ''} ${(a.tags || []).join(' ')}`.toLowerCase();
    return blob.includes(query.trim().toLowerCase());
  });

  const stats = useMemo(() => ({
    assets: assets.length,
    packs: packs.length,
    sent: assets.reduce((s, a) => s + (a.sent_count || 0), 0),
    indexed: assets.filter((a) => a.has_embedding).length,
  }), [assets, packs]);

  const onUpload = async (files) => {
    if (!charId || !files?.length || uploading) return;
    setUploading(true);
    try {
      for (const file of files) {
        await uploadCompanionMediaAsset({ studioModelId: Number(charId), file });
      }
      await reload();
    } catch (e) {
      cabinet.setError(e?.message || String(e));
    } finally {
      setUploading(false);
    }
  };

  const saveDraft = async () => {
    if (!selected || !draft) return;
    try {
      await updateCompanionMediaAsset(selected.id, {
        title: draft.title,
        description: draft.description,
        tags: draft.tags.split(',').map((t) => t.trim()).filter(Boolean),
        tier: draft.tier,
        price_usd_cents: parseUsdToCents(draft.priceUsd),
        pack_id: draft.pack_id ? Number(draft.pack_id) : null,
      });
      await reload();
    } catch (e) {
      cabinet.setError(e?.message || String(e));
    }
  };

  const removeAsset = async () => {
    if (!selected) return;
    if (!window.confirm(ru ? 'Удалить файл из медиатеки?' : 'Delete from media library?')) return;
    try {
      await deleteCompanionMediaAsset(selected.id);
      setSelId(null);
      await reload();
    } catch (e) {
      cabinet.setError(e?.message || String(e));
    }
  };

  const runSearch = async () => {
    if (!charId || !searchQ.trim()) return;
    try {
      const out = await searchCompanionMedia({
        studio_model_id: Number(charId),
        query: searchQ.trim(),
        conversation_id: searchConv ? Number(searchConv) : null,
        expand_pack: true,
      });
      setSearchOut(out);
    } catch (e) {
      cabinet.setError(e?.message || String(e));
    }
  };

  const createPack = async () => {
    const name = packName.trim();
    if (!name || !charId) return;
    try {
      await createCompanionMediaPack({
        studio_model_id: Number(charId),
        name,
        max_send_count: 4,
      });
      setPackName('');
      await reload();
    } catch (e) {
      cabinet.setError(e?.message || String(e));
    }
  };

  const importFromStudio = async () => {
    const gid = Number(importGenId);
    if (!charId || !gid) return;
    try {
      await importCompanionMediaFromGeneration({
        studio_model_id: Number(charId),
        studio_generation_id: gid,
      });
      setImportGenId('');
      await reload();
    } catch (e) {
      cabinet.setError(e?.message || String(e));
    }
  };

  if (!charId || !model) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 14, flexWrap: 'wrap' }}>
        <div style={{ minWidth: 260 }}>
          <div style={{ fontWeight: 800, fontSize: 15, marginBottom: 5 }}>{ml.title}</div>
          <div style={{ fontSize: 12, color: color.textDim, lineHeight: 1.55, maxWidth: 620 }}>{ml.desc}</div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <Field
            label=""
            placeholder={ru ? 'ID генерации' : 'Generation ID'}
            value={importGenId}
            onChange={(e) => setImportGenId(e.target.value)}
            style={{ marginBottom: 0, minWidth: 120 }}
          />
          <Hoverable
            style={{ border: `1px solid ${line.mid}`, borderRadius: 10, padding: '9px 14px', fontSize: 12.5, fontWeight: 700, color: color.textMid, cursor: 'pointer' }}
            hover={{ borderColor: line.strong }}
            onClick={() => void importFromStudio()}
          >
            {ml.fromStudio}
          </Hoverable>
          <LimeButton disabled={uploading} onClick={() => uploadRef.current?.click()}>
            <span style={{ display: 'flex', width: 15, height: 15 }}><IcoUpload /></span>
            {uploading ? (ru ? 'Загрузка…' : 'Uploading…') : ml.upload}
          </LimeButton>
          <input ref={uploadRef} type="file" accept="image/*,video/*" multiple style={{ display: 'none' }} onChange={(e) => { void onUpload(e.target.files); e.target.value = ''; }} />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))', gap: 10 }}>
        {[
          [stats.assets, ru ? 'ФАЙЛОВ' : 'ASSETS'],
          [stats.packs, ru ? 'ПАКОВ' : 'PACKS'],
          [stats.sent, ru ? 'ОТПРАВОК' : 'SENDS'],
          [stats.indexed, ru ? 'ПРОИНДЕКС.' : 'INDEXED'],
        ].map(([v, k]) => (
          <Panel key={k} style={{ padding: '13px 15px' }}>
            <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 19, marginBottom: 3 }}>{v}</div>
            <div style={{ fontFamily: font.mono, fontSize: 8.5, letterSpacing: 1.4, color: color.textGhost }}>{k}</div>
          </Panel>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {[
          { id: 'assets', label: ml.tabAssets },
          { id: 'packs', label: ml.tabPacks },
          { id: 'search', label: ml.tabSearch },
        ].map((t) => (
          <Chip key={t.id} on={subTab === t.id} onClick={() => setSubTab(t.id)}>{t.label}</Chip>
        ))}
      </div>

      {subTab === 'assets' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 320px', gap: 12, alignItems: 'start' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
            <Panel style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={ru ? 'Поиск по названию, описанию, тегам…' : 'Search title, description, tags…'}
                style={{ ...inputSt, width: '100%', boxSizing: 'border-box' }}
              />
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {['all', 'photo', 'video'].map((id) => (
                  <Chip key={id} on={typeFilter === id} onClick={() => setTypeFilter(id)}>
                    {id === 'all' ? (ru ? 'Все' : 'All') : id === 'photo' ? (ru ? 'Фото' : 'Photos') : (ru ? 'Видео' : 'Videos')}
                  </Chip>
                ))}
                {['all', 'free', 'teaser', 'paid'].map((id) => (
                  <Chip key={id} on={tierFilter === id} onClick={() => setTierFilter(id)}>
                    {id === 'all' ? '—' : tierMeta[id]?.label || id}
                  </Chip>
                ))}
              </div>
            </Panel>

            {loading && <div style={{ fontSize: 12, color: color.textDim }}>{ru ? 'Загрузка…' : 'Loading…'}</div>}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(150px,1fr))', gap: 10 }}>
              {filtered.map((a, i) => {
                const tm = tierMeta[a.tier] || tierMeta.teaser;
                const on = Number(selId) === Number(a.id);
                return (
                  <Hoverable
                    key={a.id}
                    style={{
                      background: color.bgPanel, border: `1px solid ${on ? 'rgba(215,244,82,.5)' : line.hair}`,
                      borderRadius: 14, overflow: 'hidden', cursor: 'pointer',
                    }}
                    hover={{ borderColor: 'rgba(215,244,82,.35)' }}
                    onClick={() => setSelId(a.id)}
                  >
                    <div style={{ position: 'relative', aspectRatio: '3/4', background: G[i % G.length] }}>
                      {a.preview_url && (
                        <img src={a.preview_url} alt="" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }} />
                      )}
                      <span style={{
                        position: 'absolute', top: 7, left: 7, fontFamily: font.mono, fontSize: 8, letterSpacing: 0.8,
                        background: tm.bg, color: tm.color, border: `1px solid ${tm.bd}`, padding: '2px 7px', borderRadius: 5,
                      }}
                      >
                        {tm.label}
                      </span>
                      <span style={{ position: 'absolute', top: 7, right: 7, fontFamily: font.mono, fontSize: 8, background: 'rgba(0,0,0,.55)', color: '#fff', padding: '2px 6px', borderRadius: 5 }}>
                        {a.media_type === 'video' ? '▶' : 'JPG'}
                      </span>
                    </div>
                    <div style={{ padding: '9px 10px' }}>
                      <div style={{ fontSize: 12, fontWeight: 700, lineHeight: 1.35 }}>{a.title || `#${a.id}`}</div>
                      <div style={{ fontFamily: font.mono, fontSize: 8.5, color: color.textGhost, marginTop: 4 }}>
                        {fmtUsdCents(a.price_usd_cents)} · {a.sent_count || 0} {ru ? 'отпр.' : 'sent'}
                      </div>
                    </div>
                  </Hoverable>
                );
              })}
            </div>
          </div>

          <Panel style={{ padding: 15, position: 'sticky', top: 0 }}>
            {!selected || !draft ? (
              <div>
                <div style={{ fontWeight: 800, fontSize: 13.5, marginBottom: 6 }}>{ru ? 'Выберите файл' : 'Select an asset'}</div>
                <div style={{ fontSize: 11.5, color: color.textMuted, lineHeight: 1.55 }}>
                  {ru ? 'Откройте карточку слева, чтобы редактировать описание, теги, тир и цену в $.' : 'Pick a card to edit description, tags, tier and USD price.'}
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <Field label={ru ? 'НАЗВАНИЕ' : 'TITLE'} value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
                <Field label={ru ? 'ОПИСАНИЕ (ищет бот)' : 'DESCRIPTION'} value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} area />
                <Field label={ru ? 'ТЕГИ' : 'TAGS'} value={draft.tags} onChange={(e) => setDraft({ ...draft, tags: e.target.value })} placeholder="beach, selfie" />
                <div>
                  <div style={fieldLbl}>{ru ? 'ТИР' : 'TIER'}</div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    {['free', 'teaser', 'paid'].map((tier) => (
                      <Chip key={tier} on={draft.tier === tier} onClick={() => setDraft({ ...draft, tier })}>{tierMeta[tier].label}</Chip>
                    ))}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 10 }}>
                  <div style={{ flex: 1 }}>
                    <Field label={ru ? 'ПАК' : 'PACK'} value={draft.pack_id} onChange={(e) => setDraft({ ...draft, pack_id: e.target.value })} placeholder={ru ? 'ID пака' : 'Pack ID'} />
                  </div>
                  <div style={{ width: 88, flex: 'none' }}>
                    <Field label={ml.fPrice} value={draft.priceUsd} onChange={(e) => setDraft({ ...draft, priceUsd: e.target.value })} />
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 10, borderTop: `1px solid ${line.hair}`, paddingTop: 11 }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 16 }}>{selected.sent_count || 0}</div>
                    <div style={{ fontFamily: font.mono, fontSize: 8, color: color.textGhost }}>{ru ? 'отправок' : 'sends'}</div>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 16 }}>{selected.fan_count || 0}</div>
                    <div style={{ fontFamily: font.mono, fontSize: 8, color: color.textGhost }}>{ru ? 'фанов' : 'fans'}</div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <LimeButton style={{ flex: 1, justifyContent: 'center' }} onClick={() => void saveDraft()}>{ml.save}</LimeButton>
                  <Hoverable
                    style={{ border: '1px solid rgba(248,113,113,.3)', color: color.red, borderRadius: 10, padding: '10px 14px', fontSize: 12.5, fontWeight: 700, cursor: 'pointer' }}
                    hover={{ background: 'rgba(248,113,113,.08)' }}
                    onClick={() => void removeAsset()}
                  >
                    {ml.del}
                  </Hoverable>
                </div>
                <div style={{ fontSize: 10, color: selected.has_embedding ? color.lime : color.orange }}>
                  ● {selected.has_embedding ? (ru ? 'Embedding OK' : 'Embedding OK') : (ru ? 'Нужен reindex' : 'Reindex needed')}
                </div>
              </div>
            )}
          </Panel>
        </div>
      )}

      {subTab === 'packs' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 760 }}>
          <div style={{ fontSize: 11.5, color: color.textMuted, lineHeight: 1.55 }}>
            {ru ? 'Пак — серия 3–4 кадра. При совпадении бот дошлёт остальные по порядку.' : 'Pack = 3–4 frames; on match the bot sends the rest in order.'}
          </div>
          {packs.map((pk) => (
            <Panel key={pk.id} style={{ padding: 14, display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap' }}>
              <div style={{ flex: 1, minWidth: 150 }}>
                <div style={{ fontWeight: 800, fontSize: 13.5 }}>{pk.name}</div>
                <div style={{ fontFamily: font.mono, fontSize: 9.5, color: color.textGhost }}>{pk.asset_count} · max {pk.max_send_count}</div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Hoverable
                  style={{ width: 26, height: 26, borderRadius: 8, border: `1px solid ${line.mid}`, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}
                  onClick={() => void updateCompanionMediaPack(pk.id, { max_send_count: Math.max(1, pk.max_send_count - 1) }).then(reload)}
                >
                  −
                </Hoverable>
                <span style={{ fontFamily: font.mono, fontWeight: 700, width: 18, textAlign: 'center' }}>{pk.max_send_count}</span>
                <Hoverable
                  style={{ width: 26, height: 26, borderRadius: 8, border: `1px solid ${line.mid}`, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}
                  onClick={() => void updateCompanionMediaPack(pk.id, { max_send_count: Math.min(10, pk.max_send_count + 1) }).then(reload)}
                >
                  +
                </Hoverable>
              </div>
              <Hoverable
                style={{ fontSize: 11, color: color.red, cursor: 'pointer' }}
                onClick={() => void deleteCompanionMediaPack(pk.id).then(reload)}
              >
                {ml.del}
              </Hoverable>
            </Panel>
          ))}
          <div style={{ display: 'flex', gap: 8 }}>
            <Field label="" value={packName} onChange={(e) => setPackName(e.target.value)} placeholder={ru ? 'Название серии' : 'Series name'} style={{ flex: 1, marginBottom: 0 }} />
            <LimeButton onClick={() => void createPack()}>+ {ml.newPack}</LimeButton>
          </div>
        </div>
      )}

      {subTab === 'search' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(300px,1fr))', gap: 12, maxWidth: 900 }}>
          <Panel style={{ padding: 15, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <Field label={ru ? 'ЗАПРОС ФАНА' : 'FAN REQUEST'} value={searchQ} onChange={(e) => setSearchQ(e.target.value)} placeholder={ru ? 'покажи с пляжа' : 'show from the beach'} />
            <Field label={ru ? 'ID ДИАЛОГА (исключить отправленное)' : 'CONVERSATION ID'} value={searchConv} onChange={(e) => setSearchConv(e.target.value)} />
            <LimeButton onClick={() => void runSearch()}>{ml.run}</LimeButton>
            <Hoverable
              style={{ fontSize: 11.5, color: color.textMuted, cursor: 'pointer' }}
              hover={{ color: color.lime }}
              onClick={() => void reindexCompanionMedia(Number(charId)).then(reload)}
            >
              ↻ {ml.reindex}
            </Hoverable>
          </Panel>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {(searchOut?.assets || []).map((sr) => (
              <Panel key={sr.id} style={{ padding: 12, display: 'flex', gap: 10, alignItems: 'center' }}>
                <div style={{ width: 48, aspectRatio: '3/4', borderRadius: 8, overflow: 'hidden', background: color.bgPanel, flex: 'none' }}>
                  {sr.preview_url && <img src={sr.preview_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 700 }}>{sr.title || `#${sr.id}`}</div>
                  <div style={{ fontSize: 11, color: color.textDim }}>{fmtUsdCents(sr.price_usd_cents)} · {sr.match_score != null ? `${Math.round(sr.match_score * 100)}%` : '—'}</div>
                </div>
              </Panel>
            ))}
            {searchOut && !searchOut.assets?.length && (
              <div style={{ fontSize: 12, color: color.textDim }}>{searchOut.reason}</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

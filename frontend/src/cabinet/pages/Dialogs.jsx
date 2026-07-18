import { useRef, useState, useEffect } from 'react';
import Hoverable from '../components/Hoverable';
import { IcoClip, IcoSendArrow } from '../components/Icons';
import { Fade, PageTitle, Avatar, Chip } from '../components/ui';
import { useApp } from '../hooks/useApp';
import { color, line, font, avG } from '../styles/tokens';
import { LANG_MAP, REACT_CHOICES, EMOJI_CHOICES } from '../api/helpers';
import { mapDialogRow, mapMessage, mapNote, modelNameById, formatCompanionMode } from '../api/mappers';
import { inputSt, borderHoverOff } from '../styles/mixins';

function handleDeleteDialog(c, lang, cabinet) {
  const ok = window.confirm(
    lang === 'ru'
      ? `Удалить диалог с «${c.name}»?`
      : `Delete conversation with "${c.name}"?`,
  );
  if (!ok) return;
  void cabinet.deleteConversation(c.id);
}

const noteToneMap = {
  lime: { background: 'rgba(215,244,82,.15)', color: color.lime },
  orange: { background: 'rgba(251,146,60,.15)', color: color.orange },
  purple: { background: 'rgba(192,132,252,.15)', color: color.purple },
};

/* ── list pane ───────────────────────────────────────────── */
function ChatList() {
  const { t, lang, s, setS, isMobile, cabinet } = useApp();
  const dialogsRaw = cabinet.conversations.map((c, i) => mapDialogRow(c, i));

  const count = (fn) => dialogsRaw.filter((c) => fn(c)).length;

  const filterDefs = [
    { id: 'all', label: lang === 'ru' ? 'Все' : 'All', n: dialogsRaw.length, test: () => true },
    { id: 'vip', label: 'VIP', n: count((c) => c.vip), test: (c) => c.vip },
    { id: 'hot', label: '24ч+', n: count((c) => c.hot), test: (c) => c.hot },
    { id: 'new', label: lang === 'ru' ? 'Новые' : 'New', n: count((c) => c.isNew), test: (c) => c.isNew },
  ];

  const platDefs = [
    { id: 'all', label: lang === 'ru' ? 'Все площадки' : 'All', col: color.textDim, bg: 'rgba(255,255,255,.05)', bd: line.mid },
    { id: 'TELEGRAM', label: `Telegram ${count((c) => c.platform === 'TELEGRAM')}`, col: color.blue, bg: 'rgba(56,189,248,.12)', bd: 'rgba(56,189,248,.35)' },
    { id: 'FANVUE', label: `Fanvue ${count((c) => c.platform === 'FANVUE')}`, col: color.pink, bg: 'rgba(240,168,200,.12)', bd: 'rgba(240,168,200,.35)' },
  ];

  const curFilter = filterDefs.find((f) => f.id === s.chatFilter) || filterDefs[0];
  const searchQ = (s.chatSearchQuery || '').trim().toLowerCase();
  const visible = dialogsRaw
    .map((c, i) => ({ c, i }))
    .filter(({ c }) => curFilter.test(c) && (s.chatPlatform === 'all' || c.platform === s.chatPlatform))
    .filter(({ c }) => !searchQ || c.name.toLowerCase().includes(searchQ) || c.last.toLowerCase().includes(searchQ));

  return (
    <div
      style={{
        background: color.surface, border: `1px solid ${line.hair}`, borderRadius: 16,
        display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 0, flex: 1,
      }}
    >
      <div style={{ padding: '12px 12px 8px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <input
          placeholder={t.searchDialogs}
          value={s.chatSearchQuery || ''}
          onChange={(e) => setS({ chatSearchQuery: e.target.value })}
          style={{ ...inputSt, borderRadius: 9, padding: '8px 12px' }}
          aria-label={t.searchDialogs}
        />
        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
          {platDefs.map((p) => {
            const on = s.chatPlatform === p.id;
            return (
              <Hoverable
                as="span"
                key={p.id}
                style={{
                  fontFamily: font.mono, fontSize: 9.5, letterSpacing: '.5px',
                  padding: '3px 10px', borderRadius: 20, cursor: 'pointer',
                  border: `1px solid ${on ? p.bd : 'rgba(255,255,255,.1)'}`,
                  color: on ? p.col : color.textMuted,
                  background: on ? p.bg : 'transparent',
                }}
                hover={{ borderColor: borderHoverOff }}
                onClick={() => setS({ chatPlatform: p.id })}
              >
                {p.label}
              </Hoverable>
            );
          })}
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {filterDefs.map((f) => (
            <Chip key={f.id} on={s.chatFilter === f.id} onClick={() => setS({ chatFilter: f.id })}>
              {f.label} · {f.n}
            </Chip>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '4px 8px 8px' }}>
        {visible.length === 0 && (
          <div style={{ padding: '40px 20px', textAlign: 'center', color: color.textGhost, fontSize: 12.5 }}>
            {t.noDialogs}
          </div>
        )}
        {visible.map(({ c, i }) => {
          const st = c.status || false;
          const active = cabinet.activeConvId === c.id;
          return (
            <Hoverable
              key={c.id}
              style={{
                display: 'flex', gap: 10, alignItems: 'center', padding: '9px 8px',
                borderRadius: 12, cursor: 'pointer', position: 'relative',
                ...(active
                  ? { background: 'rgba(215,244,82,.07)', border: '1px solid rgba(215,244,82,.2)' }
                  : { border: '1px solid transparent' }),
              }}
              hover={active ? {} : { background: 'rgba(255,255,255,.05)' }}
              onClick={() => {
                setS({ chatOpen: i, mobileChat: true, msgReact: null, emojiOpen: false });
                void cabinet.loadMessages(c.id);
              }}
            >
              <Avatar
                size={36}
                grad={avG[c.av % 5]}
                style={st ? { filter: 'grayscale(1)', opacity: 0.6 } : undefined}
              >
                {c.name[0]}
                {c.vip && (
                  <span
                    style={{
                      position: 'absolute', top: -4, left: -6, fontFamily: font.mono, fontSize: 7.5,
                      background: color.lime, color: color.limeInk, fontWeight: 700,
                      padding: '1px 4px', borderRadius: 5,
                    }}
                  >
                    VIP
                  </span>
                )}
              </Avatar>

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', gap: 6, alignItems: 'baseline' }}>
                  <span style={{ fontWeight: 700, fontSize: 12.5, ...(st ? { color: color.textDim } : {}) }}>{c.name}</span>
                  <span
                    style={{
                      fontFamily: font.mono, fontSize: 8, letterSpacing: '1px',
                      color: c.platform === 'FANVUE' ? color.pink : color.blue,
                    }}
                  >
                    {c.platform}
                  </span>
                </div>
                {st && (
                  <div style={{ marginTop: 2 }}>
                    <span
                      style={{
                        fontFamily: font.mono, fontSize: 7.5, letterSpacing: '.4px',
                        padding: '1px 6px', borderRadius: 4,
                        ...(st === 'blocked'
                          ? { background: 'rgba(248,113,113,.15)', color: color.red }
                          : { background: 'rgba(255,255,255,.08)', color: color.textDim }),
                      }}
                    >
                      ⛔ {st === 'blocked' ? t.dlgBlocked : t.dlgDeleted}
                    </span>
                  </div>
                )}
                <div style={{ fontSize: 11, color: color.textDim, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {c.last}
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3 }}>
                {c.unread > 0 && (
                  <span
                    style={{
                      fontFamily: font.mono, fontSize: 9, fontWeight: 700,
                      background: color.lime, color: color.limeInk,
                      minWidth: 18, height: 18, borderRadius: 9,
                      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 5px',
                    }}
                  >
                    {c.unread > 99 ? '99+' : c.unread}
                  </span>
                )}
                {st && (
                  <Hoverable
                    as="span"
                    style={{
                      width: 22, height: 22, borderRadius: 7, display: 'flex',
                      alignItems: 'center', justifyContent: 'center', color: color.red,
                      fontSize: 12, cursor: 'pointer', border: '1px solid rgba(248,113,113,.25)',
                    }}
                    hover={{ background: 'rgba(248,113,113,.12)' }}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteDialog(c, lang, cabinet);
                    }}
                    aria-label={t.deleteDialog}
                  >
                    🗑
                  </Hoverable>
                )}
                <span style={{ fontFamily: font.mono, fontSize: 9, color: color.textGhost }}>{c.lang}</span>
                {c.hot && (
                  <span
                    style={{
                      fontFamily: font.mono, fontSize: 7.5, background: 'rgba(251,146,60,.15)',
                      color: color.orange, padding: '1px 5px', borderRadius: 4,
                    }}
                  >
                    24ч+
                  </span>
                )}
              </div>
            </Hoverable>
          );
        })}
      </div>
    </div>
  );
}

/* ── thread pane ─────────────────────────────────────────── */
function Thread() {
  const { t, lang, s, setS, isMobile, cabinet } = useApp();
  const attachRef = useRef(null);
  const [attachFile, setAttachFile] = useState(null);
  const [attachPreview, setAttachPreview] = useState(null);
  const dialogsRaw = cabinet.conversations.map((c, i) => mapDialogRow(c, i));
  const cur = dialogsRaw.find((d) => d.id === cabinet.activeConvId) || dialogsRaw[s.chatOpen] || dialogsRaw[0];
  const rawConv = cabinet.conversations.find((c) => c.id === cur?.id);
  const personaName = modelNameById(cabinet.models, rawConv?.studio_model_id);
  const companionLabel = formatCompanionMode(rawConv?.effective_companion_mode, lang);
  const curSt = cur?.status || false;
  const msgDefs = cabinet.messages.map(mapMessage);
  const notesData = cabinet.notes.map((n) => mapNote(n, lang));
  const reactChoices = REACT_CHOICES;
  const emojiChoices = EMOJI_CHOICES;
  const langMap = LANG_MAP;

  if (!cur) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: color.textGhost, fontSize: 13 }}>
        {t.noDialogs}
      </div>
    );
  }

  const bubbleIn = {
    maxWidth: '80%', background: color.raised, border: `1px solid ${line.hair}`,
    borderRadius: '14px 14px 14px 4px', padding: '10px 13px', position: 'relative',
  };
  const bubbleOut = {
    maxWidth: '80%', background: 'rgba(215,244,82,.09)', border: '1px solid rgba(215,244,82,.2)',
    borderRadius: '14px 14px 4px 14px', padding: '10px 13px', position: 'relative',
  };

  const closePops = () => {
    if (s.msgReact !== null || s.emojiOpen) setS({ msgReact: null, emojiOpen: false });
  };

  const scrollDown = () => {
    const el = document.getElementById('mm-thread-scroll');
    if (el) el.scrollTop = el.scrollHeight;
  };

  useEffect(() => () => {
    if (attachPreview) URL.revokeObjectURL(attachPreview);
  }, [attachPreview]);

  const clearAttach = () => {
    if (attachPreview) URL.revokeObjectURL(attachPreview);
    setAttachFile(null);
    setAttachPreview(null);
    if (attachRef.current) attachRef.current.value = '';
  };

  const replyTarget = s.replyToMessageId
    ? msgDefs.find((m) => m.id === s.replyToMessageId)
    : null;

  const handleSend = () => {
    const text = (s.replyDraft || '').trim();
    if ((!text && !attachFile) || !cur?.id) return;
    void cabinet.sendReply(cur.id, text, s.replyToMessageId || null, attachFile).then(() => {
      setS({ replyDraft: '', emojiOpen: false, msgReact: null, replyToMessageId: null });
      clearAttach();
      scrollDown();
    });
  };

  return (
    <div
      onClick={closePops}
      style={{
        background: color.surface, border: `1px solid ${line.hair}`, borderRadius: 16,
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
        minHeight: 0, flex: 1, position: 'relative',
      }}
    >
      {/* head */}
      <div style={{ padding: '12px 16px', borderBottom: `1px solid ${line.hair}`, display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        {isMobile && s.mobileChat && (
          <Hoverable
            style={{
              width: 32, height: 32, borderRadius: 9, border: `1px solid ${line.mid}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 16, color: color.textDim, cursor: 'pointer', flex: 'none',
            }}
            hover={{ color: color.text }}
            onClick={() => setS({ mobileChat: false, msgReact: null, emojiOpen: false })}
            aria-label="Back"
          >
            ←
          </Hoverable>
        )}
        <Avatar size={36} grad={avG[cur.av % 5]}>{cur.name[0]}</Avatar>
        <div style={{ flex: 1, minWidth: 120 }}>
          <div style={{ display: 'flex', gap: 7, alignItems: 'center' }}>
            <span style={{ fontWeight: 800, fontSize: 14 }}>{cur.name}</span>
            {cur.vip && (
              <span
                style={{
                  fontFamily: font.mono, fontSize: 7.5, background: color.lime,
                  color: color.limeInk, fontWeight: 700, padding: '1px 5px', borderRadius: 5,
                }}
              >
                VIP
              </span>
            )}
          </div>
          <div style={{ fontSize: 10.5, color: color.textDim }}>
            {cur.platform === 'FANVUE' ? 'Fanvue' : 'Telegram'} · {t.persona}:{' '}
            <span style={{ color: color.pink, fontWeight: 700 }}>{personaName}</span>
            {cur.lang ? ` · ${t.replyLang}: ${langMap[cur.lang.replace('*', '')] || cur.lang}` : ''}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <Hoverable
            as="span"
            style={{
              fontFamily: font.mono, fontSize: 9.5, border: `1px solid ${line.mid}`,
              color: companionLabel === (lang === 'ru' ? 'ВЫКЛ' : 'OFF') ? color.textDim : color.lime,
              padding: '4px 10px', borderRadius: 8, cursor: 'default',
            }}
          >
            AI: {companionLabel}
          </Hoverable>
        </div>
      </div>

      {curSt === 'blocked' && (
        <div
          style={{
            background: 'rgba(248,113,113,.08)', borderBottom: '1px solid rgba(248,113,113,.2)',
            padding: '9px 16px', fontSize: 11.5, color: color.red,
            display: 'flex', alignItems: 'center', gap: 8,
          }}
        >
          ⛔ {t.dlgBlocked} — {t.dlgBlockedHint}
        </div>
      )}

      {/* messages */}
      <div
        id="mm-thread-scroll"
        style={{ flex: 1, overflowY: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}
      >
        {msgDefs.map((m, i) => {
          const rx = m.ownerReaction;
          const out = m.side === 'out';
          return (
            <div key={m.id ?? i} style={{ display: 'flex', flexDirection: 'column', gap: 3, alignItems: out ? 'flex-end' : 'flex-start' }}>
              <div style={{ ...(out ? bubbleOut : bubbleIn), opacity: m.pending ? 0.7 : 1 }}>
                {m.replyPreview && (
                  <div
                    style={{
                      fontSize: 11, color: color.textDim, marginBottom: 8, paddingBottom: 8,
                      borderBottom: '1px solid rgba(255,255,255,.08)', lineHeight: 1.4,
                    }}
                  >
                    ↩ {m.replyPreview}
                  </div>
                )}
                <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                  <div style={{ flex: 1, fontSize: 13, lineHeight: 1.5 }}>
                    {m.attachmentUrl && (
                      <a href={m.attachmentUrl} target="_blank" rel="noreferrer" style={{ display: 'block', marginBottom: m.text ? 8 : 0 }}>
                        <img
                          src={m.attachmentUrl}
                          alt=""
                          style={{
                            display: 'block', width: '100%', maxWidth: 240, maxHeight: 280,
                            borderRadius: 10, objectFit: 'cover', background: color.bgPanel,
                          }}
                        />
                      </a>
                    )}
                    {m.text || (!m.attachmentUrl && '—')}
                  </div>
                  {!m.pending && (
                  <Hoverable
                    as="span"
                    style={{ opacity: 0.5, fontSize: 12, cursor: 'pointer', flex: 'none', marginTop: 1 }}
                    hover={{ opacity: 1 }}
                    onClick={(e) => {
                      e.stopPropagation();
                      setS({ msgReact: s.msgReact === i ? null : i, emojiOpen: false });
                    }}
                    aria-label="React"
                  >
                    ☺
                  </Hoverable>
                  )}
                  {!m.pending && !out && (
                  <Hoverable
                    as="span"
                    style={{ opacity: 0.5, fontSize: 11, cursor: 'pointer', flex: 'none', marginTop: 1 }}
                    hover={{ opacity: 1, color: color.lime }}
                    onClick={(e) => {
                      e.stopPropagation();
                      setS({ replyToMessageId: m.id, msgReact: null, emojiOpen: false });
                    }}
                    aria-label={t.replyTo}
                    title={t.replyTo}
                  >
                    ↩
                  </Hoverable>
                  )}
                </div>
                {m.tr && (
                  <div
                    style={{
                      fontSize: 11.5, lineHeight: 1.45, color: color.textFaint, marginTop: 6,
                      paddingTop: 6, borderTop: '1px dashed rgba(255,255,255,.1)',
                    }}
                  >
                    {m.tr}
                  </div>
                )}
                <div style={{ fontFamily: font.mono, fontSize: 8.5, color: color.textGhost, marginTop: 6 }}>
                  {m.time}{m.pending ? (lang === 'ru' ? ' · отправка…' : ' · sending…') : ''}
                </div>

                {s.msgReact === i && !m.pending && (
                  <div
                    onClick={(e) => e.stopPropagation()}
                    style={{
                      position: 'absolute', bottom: 'calc(100% - 4px)', right: 0, zIndex: 5,
                      display: 'flex', gap: 2, background: color.raised,
                      border: `1px solid ${line.strong}`, borderRadius: 20,
                      padding: '4px 7px', boxShadow: '0 8px 24px rgba(0,0,0,.5)',
                    }}
                  >
                    {reactChoices.map((rc) => (
                      <Hoverable
                        as="span"
                        key={rc}
                        style={{ fontSize: 17, cursor: 'pointer', padding: '1px 2px' }}
                        hover={{ transform: 'scale(1.25)' }}
                        onClick={(ev) => {
                          ev.stopPropagation();
                          void cabinet.toggleReaction(cur.id, m.id, rc).then(() => setS({ msgReact: null }));
                        }}
                      >
                        {rc}
                      </Hoverable>
                    ))}
                  </div>
                )}
              </div>

              {rx && (
                <div
                  style={{
                    alignSelf: out ? 'flex-end' : 'flex-start', background: color.bgPanel,
                    border: `1px solid ${line.mid}`, borderRadius: 20,
                    padding: '1px 7px', fontSize: 12, marginTop: -8,
                  }}
                >
                  {rx}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* scroll to bottom */}
      <Hoverable
        style={{
          position: 'absolute', right: 16, bottom: 82, width: 36, height: 36, borderRadius: '50%',
          background: color.raised, border: `1px solid ${line.strong}`, display: 'flex',
          alignItems: 'center', justifyContent: 'center', fontSize: 16, color: color.textDim,
          cursor: 'pointer', boxShadow: '0 6px 18px rgba(0,0,0,.4)',
        }}
        hover={{ color: color.text, borderColor: borderHoverOff }}
        onClick={scrollDown}
        aria-label="Scroll to latest"
      >
        ↓
      </Hoverable>

      {/* emoji picker */}
      {s.emojiOpen && (
        <div
          onClick={(e) => e.stopPropagation()}
          style={{
            position: 'absolute', left: 12, right: 12, bottom: 66, zIndex: 6,
            background: color.raised, border: `1px solid ${line.strong}`, borderRadius: 14,
            padding: 10, display: 'grid', gridTemplateColumns: 'repeat(8,1fr)', gap: 4,
            boxShadow: '0 10px 30px rgba(0,0,0,.5)',
          }}
        >
          {emojiChoices.map((e) => (
            <Hoverable
              as="span"
              key={e}
              style={{ fontSize: 20, cursor: 'pointer', textAlign: 'center', padding: 3, borderRadius: 8 }}
              hover={{ background: 'rgba(255,255,255,.08)' }}
              onClick={() => {
                setS({ emojiOpen: false, replyDraft: (s.replyDraft || '') + e });
              }}
            >
              {e}
            </Hoverable>
          ))}
        </div>
      )}

      {/* composer */}
      {replyTarget && (
        <div style={{ padding: '8px 12px 0', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ flex: 1, fontSize: 11, color: color.textDim, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {t.replyTo}: {replyTarget.text || '—'}
          </div>
          <Hoverable
            as="span"
            style={{ fontSize: 11, fontWeight: 700, color: color.red, cursor: 'pointer' }}
            hover={{ opacity: 0.8 }}
            onClick={() => setS({ replyToMessageId: null })}
          >
            {t.cancelReply}
          </Hoverable>
        </div>
      )}
      {attachPreview && (
        <div style={{ padding: '8px 12px 0', display: 'flex', alignItems: 'center', gap: 10 }}>
          <img src={attachPreview} alt="" style={{ width: 56, height: 56, borderRadius: 8, objectFit: 'cover' }} />
          <span style={{ flex: 1, fontSize: 11, color: color.textDim, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {attachFile?.name}
          </span>
          <Hoverable
            as="span"
            style={{ fontSize: 11, fontWeight: 700, color: color.red, cursor: 'pointer' }}
            hover={{ opacity: 0.8 }}
            onClick={clearAttach}
          >
            ✕
          </Hoverable>
        </div>
      )}
      <div style={{ padding: '10px 12px', borderTop: `1px solid ${line.hair}`, display: 'flex', gap: 6, alignItems: 'flex-end' }}>
        <input
          ref={attachRef}
          type="file"
          accept="image/*"
          style={{ display: 'none' }}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            if (attachPreview) URL.revokeObjectURL(attachPreview);
            setAttachFile(file);
            setAttachPreview(URL.createObjectURL(file));
          }}
        />
        <Hoverable
          title={t.attach}
          style={{
            width: 38, height: 38, flex: 'none', borderRadius: 10,
            border: `1px solid ${attachFile ? 'rgba(215,244,82,.4)' : 'rgba(255,255,255,.1)'}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: attachFile ? color.lime : color.textDim, cursor: 'pointer',
          }}
          hover={{ color: color.lime, borderColor: 'rgba(215,244,82,.4)' }}
          onClick={() => attachRef.current?.click()}
        >
          <span style={{ display: 'flex', width: 18, height: 18 }}><IcoClip /></span>
        </Hoverable>
        <Hoverable
          style={{
            width: 38, height: 38, flex: 'none', borderRadius: 10, border: '1px solid rgba(255,255,255,.1)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, cursor: 'pointer',
          }}
          hover={{ borderColor: 'rgba(215,244,82,.4)' }}
          onClick={(e) => {
            e.stopPropagation();
            setS({ emojiOpen: !s.emojiOpen, msgReact: null });
          }}
          aria-label="Emoji"
        >
          😊
        </Hoverable>
        <textarea
          rows={1}
          placeholder={t.msgPlaceholder}
          aria-label={t.msgPlaceholder}
          value={s.replyDraft || ''}
          onChange={(e) => setS({ replyDraft: e.target.value })}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          style={{
            flex: 1, minHeight: 38, maxHeight: 120, background: color.bgPanel,
            border: `1px solid ${line.soft}`, borderRadius: 10, padding: '9px 12px',
            color: color.text, fontFamily: font.body, fontSize: 13, resize: 'none', outline: 'none',
          }}
        />
        <Hoverable
          style={{
            width: 38, height: 38, flex: 'none', background: color.lime, color: color.limeInk,
            borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
          }}
          hover={{ background: color.limeHi }}
          onClick={handleSend}
          aria-label={t.send}
        >
          <span style={{ display: 'flex', width: 17, height: 17 }}><IcoSendArrow /></span>
        </Hoverable>
      </div>
    </div>
  );
}

/* ── notes pane ──────────────────────────────────────────── */
function Notes() {
  const { t, lang, s, setS, cabinet } = useApp();
  const tags = [
    { label: lang === 'ru' ? 'ПРОФИЛЬ' : 'PROFILE', col: '#D7F452', bg: 'rgba(215,244,82' },
    { label: lang === 'ru' ? 'КОНТЕКСТ' : 'CONTEXT', col: '#FB923C', bg: 'rgba(251,146,60' },
    { label: lang === 'ru' ? 'ВАЖНО' : 'IMPORTANT', col: '#F87171', bg: 'rgba(248,113,113' },
  ];
  const notes = cabinet.notes.map((n) => mapNote(n, lang));
  const curName = cabinet.conversations.find((c) => c.id === cabinet.activeConvId)?.user_display_name || '—';
  const convId = cabinet.activeConvId;

  const saveNoteClick = () => {
    if (!convId) return;
    const tag = tags[s.noteTag ?? 0]?.label || tags[0].label;
    void cabinet.saveNote(convId, s.noteDraft || '', lang, tag).then(() => {
      setS({ noteFormOpen: false, noteDraft: '' });
    });
  };

  return (
    <div
      style={{
        background: color.surface, border: `1px solid ${line.hair}`, borderRadius: 16,
        display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 0,
      }}
    >
      <div style={{ padding: '12px 14px', borderBottom: `1px solid ${line.hair}`, fontWeight: 800, fontSize: 13 }}>
        {t.fanNotes} · {curName}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {notes.length ? notes.map((n, i) => (
          <div key={i} style={{ background: color.bgPanel, border: `1px solid ${line.hair}`, borderRadius: 12, padding: '10px 12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
              <span
                style={{
                  fontFamily: font.mono, fontSize: 8.5, letterSpacing: '1.2px',
                  padding: '2px 7px', borderRadius: 5, ...noteToneMap[n.kind],
                }}
              >
                {n.tag}
              </span>
              <span style={{ fontFamily: font.mono, fontSize: 8.5, color: color.textGhost }}>{n.when}</span>
            </div>
            <div style={{ fontSize: 11.5, lineHeight: 1.5, color: color.textMid }}>{n.text}</div>
          </div>
        )) : (
          <div style={{ fontSize: 12, color: color.textGhost, textAlign: 'center', padding: 24 }}>{lang === 'ru' ? 'Заметок пока нет' : 'No notes yet'}</div>
        )}
      </div>

      {s.noteFormOpen && (
        <div style={{ padding: 12, borderTop: `1px solid ${line.hair}`, display: 'flex', flexDirection: 'column', gap: 9 }}>
          <div style={{ fontFamily: font.mono, fontSize: 9, letterSpacing: '1.4px', color: color.textMuted }}>{t.noteTag}</div>
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
            {tags.map((nt, i) => (
              <Hoverable
                as="span"
                key={nt.label}
                style={{
                  fontFamily: font.mono, fontSize: 8.5, letterSpacing: '1px',
                  padding: '3px 10px', borderRadius: 6, cursor: 'pointer',
                  ...(s.noteTag === i
                    ? { background: `${nt.bg},.18)`, color: nt.col, border: `1px solid ${nt.bg},.4)` }
                    : { background: 'rgba(255,255,255,.05)', color: color.textDim, border: '1px solid rgba(255,255,255,.1)' }),
                }}
                hover={{ borderColor: borderHoverOff }}
                onClick={() => setS({ noteTag: i })}
              >
                {nt.label}
              </Hoverable>
            ))}
          </div>
          <textarea
            rows={3}
            placeholder={t.noteTextPh}
            aria-label={t.noteTextPh}
            value={s.noteDraft || ''}
            onChange={(e) => setS({ noteDraft: e.target.value })}
            style={{
              width: '100%', background: color.bgPanel, border: `1px solid ${line.soft}`,
              borderRadius: 10, padding: '9px 12px', color: color.text,
              fontFamily: font.body, fontSize: 12, lineHeight: 1.5, resize: 'vertical', outline: 'none',
            }}
          />
          <div style={{ display: 'flex', gap: 6 }}>
            <Hoverable
              style={{
                flex: 1, background: 'rgba(215,244,82,.12)', border: '1px solid rgba(215,244,82,.3)',
                borderRadius: 9, padding: 8, textAlign: 'center', fontSize: 12,
                fontWeight: 800, color: color.lime, cursor: 'pointer',
              }}
              hover={{ background: 'rgba(215,244,82,.2)' }}
              onClick={saveNoteClick}
            >
              {t.save}
            </Hoverable>
            <Hoverable
              style={{
                border: `1px solid ${line.mid}`, borderRadius: 9, padding: '8px 14px',
                textAlign: 'center', fontSize: 12, fontWeight: 700, color: color.textDim, cursor: 'pointer',
              }}
              hover={{ borderColor: borderHoverOff }}
              onClick={() => setS({ noteFormOpen: false, noteDraft: '' })}
            >
              {t.opCancel}
            </Hoverable>
          </div>
        </div>
      )}

      <div style={{ padding: '10px 12px', borderTop: `1px solid ${line.hair}`, display: 'flex', gap: 6 }}>
        <Hoverable
          style={{
            flex: 1, border: `1px solid ${line.mid}`, borderRadius: 9, padding: 7,
            textAlign: 'center', fontSize: 11.5, fontWeight: 700, color: color.purple, cursor: 'pointer',
          }}
          hover={{ borderColor: color.purple }}
          onClick={() => {
            if (!convId) return;
            void cabinet.analyzeNotes(convId);
          }}
        >
          ✦ AI-{t.analysis}
        </Hoverable>
        <Hoverable
          style={{
            flex: 1, background: 'rgba(215,244,82,.12)', border: '1px solid rgba(215,244,82,.3)',
            borderRadius: 9, padding: 7, textAlign: 'center', fontSize: 11.5,
            fontWeight: 700, color: color.lime, cursor: 'pointer',
          }}
          hover={{ background: 'rgba(215,244,82,.2)' }}
          onClick={() => setS({ noteFormOpen: !s.noteFormOpen })}
        >
          + {t.addNote}
        </Hoverable>
      </div>
    </div>
  );
}

/* ── page ────────────────────────────────────────────────── */
export default function Dialogs() {
  const { t, s, isMobile, isNarrow } = useApp();

  const showThread = !isMobile || s.mobileChat;
  const showList = !isMobile || !s.mobileChat;
  const showNotes = !isMobile && !isNarrow;

  const grid = isMobile
    ? { display: 'flex', flexDirection: 'column', gap: 12, flex: 1, minHeight: 0 }
    : {
        display: 'grid',
        gridTemplateColumns: isNarrow ? '270px 1fr' : '290px 1fr 270px',
        gap: 12, flex: 1, minHeight: 420,
      };

  return (
    <Fade style={{ height: '100%', display: 'flex', flexDirection: 'column' }} data-screen-label="Диалоги">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14, flexWrap: 'wrap' }}>
        <PageTitle>{t.navDialogs}</PageTitle>
        <div style={{ display: 'flex', gap: 6 }}>
          <span
            style={{
              fontFamily: font.mono, fontSize: 10, background: 'rgba(215,244,82,.12)',
              color: color.lime, border: '1px solid rgba(215,244,82,.3)',
              padding: '3px 10px', borderRadius: 20,
            }}
          >
            TELEGRAM 8
          </span>
          <span
            style={{
              fontFamily: font.mono, fontSize: 10, background: 'rgba(240,168,200,.1)',
              color: color.pink, border: '1px solid rgba(240,168,200,.3)',
              padding: '3px 10px', borderRadius: 20,
            }}
          >
            FANVUE 1
          </span>
        </div>
      </div>

      <div style={grid}>
        {showList && <ChatList />}
        {showThread && <Thread />}
        {showNotes && <Notes />}
      </div>
    </Fade>
  );
}

import { useEffect, useMemo, useState } from 'react';
import Hoverable from '../components/Hoverable';
import { Fade, PageTitle, Eyebrow, Chip } from '../components/ui';
import { useApp } from '../hooks/useApp';
import { color, line, font } from '../styles/tokens';
import { cardPickStyle } from '../styles/mixins';

const TICKET_TYPES = [
  { id: 'general', ru: 'Общие вопросы', en: 'General' },
  { id: 'technical', ru: 'Технические проблемы', en: 'Technical issues' },
  { id: 'payment', ru: 'Оплата', en: 'Payment' },
  { id: 'subscription', ru: 'Подписки', en: 'Subscriptions' },
];

function statusLabel(status, t) {
  const map = {
    submitted: t.stSent,
    in_review: t.stReview,
    answered: t.stAnswered,
    closed: t.stDone,
  };
  return map[status] || status;
}

function statusStyle(status) {
  const base = {
    fontFamily: font.mono, fontSize: 9, letterSpacing: '.8px', fontWeight: 800,
    padding: '3px 8px', borderRadius: 20, whiteSpace: 'nowrap',
  };
  if (status === 'answered') return { ...base, background: 'rgba(74,222,128,.12)', color: color.green, border: '1px solid rgba(74,222,128,.35)' };
  if (status === 'closed') return { ...base, background: 'rgba(255,255,255,.06)', color: color.textDim, border: `1px solid ${line.strong}` };
  if (status === 'in_review') return { ...base, background: 'rgba(251,146,60,.12)', color: color.orange, border: '1px solid rgba(251,146,60,.35)' };
  return { ...base, background: 'rgba(192,132,252,.12)', color: color.purple, border: '1px solid rgba(192,132,252,.35)' };
}

function typeLabel(type, lang) {
  const hit = TICKET_TYPES.find((x) => x.id === type);
  if (!hit) return type;
  return lang === 'ru' ? hit.ru : hit.en;
}

export default function Support() {
  const { t, lang, cabinet } = useApp();
  const [formOpen, setFormOpen] = useState(false);
  const [ticketType, setTicketType] = useState('general');
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [detail, setDetail] = useState(null);
  const [detailId, setDetailId] = useState(null);

  useEffect(() => {
    void cabinet.loadSupportTickets();
  }, [cabinet]);

  useEffect(() => {
    if (detailId == null) {
      setDetail(null);
      return;
    }
    void cabinet.fetchSupportTicketDetail(detailId).then(setDetail).catch(() => setDetail(null));
  }, [detailId, cabinet]);

  const tickets = cabinet.supportTickets || [];

  const thread = useMemo(() => {
    if (!detail) return [];
    const rows = [{ id: 'initial', is_staff: false, message: detail.message, created_at: detail.created_at }];
    for (const r of detail.replies || []) rows.push(r);
    return rows;
  }, [detail]);

  const submitTicket = async () => {
    const subj = subject.trim();
    const body = message.trim();
    if (!subj || !body) {
      cabinet.setError(lang === 'ru' ? 'Заполните тему и сообщение' : 'Fill in subject and message');
      return;
    }
    const row = await cabinet.createSupportTicket({ type: ticketType, subject: subj, message: body });
    setSubject('');
    setMessage('');
    setFormOpen(false);
    if (row?.id) setDetailId(row.id);
  };

  const inputStyle = {
    width: '100%', background: color.bgPanel, border: `1px solid ${line.soft}`,
    borderRadius: 10, padding: '10px 12px', color: color.text,
    fontFamily: font.body, fontSize: 12.5, outline: 'none', boxSizing: 'border-box',
  };

  return (
    <Fade data-screen-label="Поддержка">
      <div style={{ maxWidth: 760 }}>
        <div style={{ marginBottom: 16 }}>
          <PageTitle style={{ marginBottom: 5 }}>{t.navSupport}</PageTitle>
          <div style={{ fontSize: 12.5, color: color.textDim }}>{t.supportDesc}</div>
        </div>

        <Hoverable
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 8,
            background: color.lime, color: color.limeInk, fontWeight: 800, fontSize: 13,
            borderRadius: 10, padding: '10px 16px', cursor: 'pointer', marginBottom: 16,
          }}
          hover={{ background: color.limeHi }}
          onClick={() => setFormOpen((v) => !v)}
        >
          + {t.newTicket}
        </Hoverable>

        {formOpen && (
          <div
            style={{
              background: color.surface, border: `1px solid ${line.hair}`, borderRadius: 16,
              padding: 18, display: 'flex', flexDirection: 'column', gap: 14, marginBottom: 20,
            }}
          >
            <div>
              <Eyebrow>{t.ticketType}</Eyebrow>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {TICKET_TYPES.map((tt) => (
                  <Chip key={tt.id} on={ticketType === tt.id} onClick={() => setTicketType(tt.id)}>
                    {lang === 'ru' ? tt.ru : tt.en}
                  </Chip>
                ))}
              </div>
            </div>
            <div>
              <Eyebrow>{t.ticketSubject}</Eyebrow>
              <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder={t.ticketSubject} style={inputStyle} />
            </div>
            <div>
              <Eyebrow>{t.ticketMessage}</Eyebrow>
              <textarea rows={4} value={message} onChange={(e) => setMessage(e.target.value)} style={{ ...inputStyle, resize: 'vertical' }} />
            </div>
            <Hoverable
              style={{
                alignSelf: 'flex-start', background: 'rgba(215,244,82,.12)',
                border: '1px solid rgba(215,244,82,.3)', borderRadius: 10,
                padding: '10px 22px', fontSize: 13, fontWeight: 800, color: color.lime, cursor: 'pointer',
              }}
              hover={{ background: 'rgba(215,244,82,.2)' }}
              onClick={() => void submitTicket()}
            >
              {t.sendTicket}
            </Hoverable>
          </div>
        )}

        {detail && (
          <>
            <Hoverable
              style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 12.5, fontWeight: 700, color: color.textDim, cursor: 'pointer', marginBottom: 14 }}
              hover={{ color: color.text }}
              onClick={() => setDetailId(null)}
            >
              ← {t.myTickets}
            </Hoverable>
            <div
              style={{
                background: color.surface, border: `1px solid ${line.hair}`, borderRadius: 16,
                padding: '16px 18px', marginBottom: 20,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, marginBottom: 6 }}>
                <span style={{ fontWeight: 800, fontSize: 15, lineHeight: 1.35 }}>{detail.subject}</span>
                <span style={statusStyle(detail.status)}>{statusLabel(detail.status, t)}</span>
              </div>
              <div style={{ fontSize: 11, color: color.textDim, marginBottom: 16 }}>
                {typeLabel(detail.type, lang)} · {new Date(detail.created_at).toLocaleString(lang === 'ru' ? 'ru-RU' : 'en-GB')}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, paddingTop: 14, borderTop: `1px solid ${line.hair}` }}>
                {thread.map((m) => (
                  <div key={m.id} style={{ display: 'flex', justifyContent: m.is_staff ? 'flex-start' : 'flex-end' }}>
                    <div
                      style={{
                        maxWidth: '85%', padding: '10px 12px', borderRadius: 12,
                        background: m.is_staff ? 'rgba(215,244,82,.08)' : color.bgPanel,
                        border: `1px solid ${m.is_staff ? 'rgba(215,244,82,.25)' : line.soft}`,
                      }}
                    >
                      <div style={{ fontSize: 13, lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>{m.message}</div>
                      <div style={{ fontFamily: font.mono, fontSize: 8.5, color: color.textGhost, marginTop: 6 }}>
                        {new Date(m.created_at).toLocaleString(lang === 'ru' ? 'ru-RU' : 'en-GB')}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {!detail && (
          <>
            <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 10 }}>{t.myTickets}</div>
            {tickets.length ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {tickets.map((tk) => (
                  <Hoverable
                    key={tk.id}
                    style={{
                      background: color.surface, border: `1px solid ${line.hair}`, borderRadius: 14,
                      padding: '14px 16px', cursor: 'pointer',
                    }}
                    hover={{ borderColor: line.mid }}
                    onClick={() => setDetailId(tk.id)}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, marginBottom: 6 }}>
                      <span style={{ fontWeight: 700, fontSize: 13, lineHeight: 1.4 }}>{tk.subject}</span>
                      <span style={statusStyle(tk.status)}>{statusLabel(tk.status, t)}</span>
                    </div>
                    <div style={{ fontSize: 11, color: color.textDim }}>
                      {typeLabel(tk.type, lang)} · {new Date(tk.updated_at || tk.created_at).toLocaleString(lang === 'ru' ? 'ru-RU' : 'en-GB')}
                    </div>
                  </Hoverable>
                ))}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: 30, color: color.textGhost, fontSize: 12.5 }}>{t.noTickets}</div>
            )}
          </>
        )}
      </div>
    </Fade>
  );
}

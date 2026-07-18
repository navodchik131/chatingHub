import { useState } from 'react';
import Hoverable from '../components/Hoverable';
import { Fade, PageTitle, Eyebrow, Panel, Avatar, LimeButton, BackLink, Checkbox, Field, Overlay, CloseButton } from '../components/ui';
import { useApp } from '../hooks/useApp';
import { color, line, font } from '../styles/tokens';
import { fieldLbl, inputSt, borderHoverOff } from '../styles/mixins';
import { mapTeamKpi, mapMembers } from '../api/mappers';
import { maskFromOpRights, rightsFromMask } from '../api/actions';

const rightStyle = (on) => ({
  fontFamily: font.mono, fontSize: 8.5, letterSpacing: '.5px',
  padding: '2px 8px', borderRadius: 5,
  ...(on
    ? { background: 'rgba(215,244,82,.12)', color: color.lime }
    : { background: 'rgba(255,255,255,.05)', color: color.textGhost, textDecoration: 'line-through' }),
});

function SnippetModal({ open, editing, draft, setDraft, onClose, onSave, t, lang }) {
  if (!open) return null;
  return (
    <Overlay onClose={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ width: 'min(92vw,480px)', background: color.raised, border: `1px solid ${line.mid}`, borderRadius: 16, padding: 20 }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <div style={{ fontWeight: 800, fontSize: 15 }}>{editing ? t.editTemplate : t.newTemplate}</div>
          <CloseButton onClick={onClose} label={t.close} />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Field
            label={t.templateTitle}
            value={draft.title}
            onChange={(e) => setDraft({ ...draft, title: e.target.value })}
          />
          <Field
            label={t.templateBody}
            area
            rows={4}
            value={draft.body}
            onChange={(e) => setDraft({ ...draft, body: e.target.value })}
          />
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
          <Hoverable
            style={{
              background: color.lime, color: color.limeInk, fontWeight: 800, fontSize: 12.5,
              borderRadius: 10, padding: '10px 18px', cursor: 'pointer',
            }}
            hover={{ background: color.limeHi }}
            onClick={onSave}
          >
            {t.save}
          </Hoverable>
          <Hoverable
            style={{
              border: `1px solid ${line.mid}`, color: color.textDim, fontWeight: 700,
              fontSize: 12.5, borderRadius: 10, padding: '10px 18px', cursor: 'pointer',
            }}
            hover={{ borderColor: borderHoverOff }}
            onClick={onClose}
          >
            {t.opCancel}
          </Hoverable>
        </div>
      </div>
    </Overlay>
  );
}

export default function Team() {
  const { t, lang, setS, go, cabinet } = useApp();
  const [snippetOpen, setSnippetOpen] = useState(false);
  const [snippetEditId, setSnippetEditId] = useState(null);
  const [snippetDraft, setSnippetDraft] = useState({ title: '', body: '' });
  const teamKpiData = mapTeamKpi(cabinet.chatterStats, lang);
  const membersData = mapMembers(cabinet.members, cabinet.chatterStats, cabinet.models, lang);
  const templatesData = (cabinet.snippets || []).map((s) => ({
    id: s.id,
    title: s.title || '—',
    body: s.body || '',
  }));

  const openSnippetCreate = () => {
    setSnippetEditId(null);
    setSnippetDraft({ title: '', body: '' });
    setSnippetOpen(true);
  };

  const openSnippetEdit = (tp) => {
    setSnippetEditId(tp.id);
    setSnippetDraft({ title: tp.title === '—' ? '' : tp.title, body: tp.body });
    setSnippetOpen(true);
  };

  const saveSnippet = () => {
    const title = (snippetDraft.title || '').trim();
    const body = (snippetDraft.body || '').trim();
    if (!title || !body) return;
    const req = snippetEditId
      ? cabinet.updateSnippet(snippetEditId, title, body)
      : cabinet.createSnippet(title, body);
    void req.then(() => {
      setSnippetOpen(false);
      setSnippetEditId(null);
      setSnippetDraft({ title: '', body: '' });
    });
  };

  return (
    <Fade data-screen-label="Команда">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 14, flexWrap: 'wrap', marginBottom: 16 }}>
        <div>
          <PageTitle style={{ marginBottom: 5 }}>{t.navTeam}</PageTitle>
          <div style={{ fontSize: 12.5, color: color.textDim }}>{t.teamDesc}</div>
        </div>
        <LimeButton onClick={() => {
          setS({
            opEditId: null,
            opError: false,
            opForm: { login: '', password: '', tribute: '15', modelIds: [] },
            opRights: { chat: false, studio: false, models: false, keys: false, billing: false },
          });
          go('newOperator')();
        }}>+ {t.addOperator}</LimeButton>
      </div>

      {/* KPI */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: 12, marginBottom: 16 }}>
        {teamKpiData.map((tk) => (
          <Panel key={tk.label} style={{ borderRadius: 14, padding: '14px 16px' }}>
            <Eyebrow size={9} style={{ marginBottom: 8 }}>{tk.label}</Eyebrow>
            <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 17 }}>{tk.value}</div>
          </Panel>
        ))}
      </div>

      {/* members */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {membersData.map((mb) => (
          <Panel key={mb.id ?? mb.login} style={{ padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
            <Avatar size={38} grad={mb.grad}>{mb.initial}</Avatar>
            <div style={{ minWidth: 130 }}>
              <div style={{ fontWeight: 800, fontSize: 13.5 }}>{mb.login}</div>
              <div style={{ fontSize: 11, color: color.textDim }}>{mb.meta}</div>
            </div>
            <div style={{ flex: 1, display: 'flex', gap: 5, flexWrap: 'wrap', minWidth: 200 }}>
              {mb.rights.map((r) => (
                <span key={r.label} style={rightStyle(r.on)}>{r.label}</span>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontFamily: font.mono, fontSize: 12, fontWeight: 600, color: color.lime }}>{mb.sla}</div>
                <div style={{ fontSize: 9.5, color: color.textMuted }}>SLA</div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontFamily: font.mono, fontSize: 12, fontWeight: 600 }}>{mb.replies}</div>
                <div style={{ fontSize: 9.5, color: color.textMuted }}>{t.replies}</div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontFamily: font.mono, fontSize: 12, fontWeight: 600, color: color.pink }}>{mb.tribute}</div>
                <div style={{ fontSize: 9.5, color: color.textMuted }}>Tribute</div>
              </div>
              <Hoverable
                as="span"
                style={{
                  fontSize: 11.5, fontWeight: 700, color: color.textDim, cursor: 'pointer',
                  border: `1px solid ${line.mid}`, borderRadius: 8, padding: '6px 12px',
                }}
                hover={{ color: color.text, borderColor: borderHoverOff }}
                onClick={() => {
                  const m = mb.raw;
                  setS({
                    opEditId: m.id,
                    opError: false,
                    opForm: {
                      login: m.member_login || '',
                      password: '',
                      tribute: String(m.tribute_share_percent ?? 15),
                      modelIds: [...(m.allowed_studio_model_ids || [])],
                    },
                    opRights: rightsFromMask(m.permissions_mask),
                  });
                  go('newOperator')();
                }}
              >
                {t.edit}
              </Hoverable>
              <Hoverable
                as="span"
                style={{
                  fontSize: 11.5, fontWeight: 700, color: color.red, cursor: 'pointer',
                  border: `1px solid rgba(248,113,113,.35)`, borderRadius: 8, padding: '6px 12px',
                }}
                hover={{ borderColor: color.red, background: 'rgba(248,113,113,.08)' }}
                onClick={() => {
                  const name = mb.login;
                  const ok = window.confirm(
                    lang === 'ru'
                      ? `Удалить оператора «${name}»?`
                      : `Delete operator "${name}"?`,
                  );
                  if (!ok) return;
                  void cabinet.deleteMember(mb.id);
                }}
              >
                {t.delete}
              </Hoverable>
            </div>
          </Panel>
        ))}
      </div>

      {/* templates */}
      <Panel style={{ marginTop: 16, padding: '16px 18px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <span style={{ fontWeight: 800, fontSize: 14 }}>{t.templates}</span>
          <Hoverable
            as="span"
            style={{ fontSize: 11.5, fontWeight: 700, color: color.lime, cursor: 'pointer' }}
            hover={{ color: color.limeHi }}
            onClick={openSnippetCreate}
          >
            + {t.addTemplate}
          </Hoverable>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))', gap: 10 }}>
          {templatesData.map((tp) => (
            <div key={tp.id ?? tp.title} style={{ background: color.bgPanel, border: `1px solid ${line.hair}`, borderRadius: 12, padding: '12px 14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, marginBottom: 4 }}>
                <div style={{ fontWeight: 700, fontSize: 12.5 }}>{tp.title}</div>
                <div style={{ display: 'flex', gap: 10 }}>
                  <Hoverable as="span" style={{ fontSize: 10.5, fontWeight: 700, color: color.textDim, cursor: 'pointer' }} hover={{ color: color.lime }} onClick={() => openSnippetEdit(tp)}>
                    {t.edit}
                  </Hoverable>
                  <Hoverable
                    as="span"
                    style={{ fontSize: 10.5, fontWeight: 700, color: color.red, cursor: 'pointer' }}
                    hover={{ opacity: 0.8 }}
                    onClick={() => {
                      const ok = window.confirm(lang === 'ru' ? `Удалить шаблон «${tp.title}»?` : `Delete template "${tp.title}"?`);
                      if (!ok) return;
                      void cabinet.deleteSnippet(tp.id);
                    }}
                  >
                    {t.delete}
                  </Hoverable>
                </div>
              </div>
              <div style={{ fontSize: 11, color: color.textDim, lineHeight: 1.5 }}>{tp.body}</div>
            </div>
          ))}
        </div>
      </Panel>

      <SnippetModal
        open={snippetOpen}
        editing={Boolean(snippetEditId)}
        draft={snippetDraft}
        setDraft={setSnippetDraft}
        onClose={() => setSnippetOpen(false)}
        onSave={saveSnippet}
        t={t}
        lang={lang}
      />
    </Fade>
  );
}

/* ── new operator ────────────────────────────────────────── */
export function NewOperator() {
  const { t, lang, s, setS, go, cabinet } = useApp();
  const orR = s.opRights || { chat: false, studio: false, models: false, keys: false, billing: false };
  const editing = Boolean(s.opEditId);
  const opForm = s.opForm || { login: '', password: '', tribute: '15', modelIds: [] };
  const setOpForm = (patch) => setS({ opForm: { ...opForm, ...patch } });
  const opModelNames = cabinet.models || [];

  const opRightDefs = [
    { key: 'chat', label: t.rChat },
    { key: 'studio', label: t.rStudio },
    { key: 'models', label: t.rModels },
    { key: 'keys', label: t.rKeys },
    { key: 'billing', label: t.rBilling },
  ];

  const saveOp = () => {
    if (!Object.values(orR).some(Boolean)) {
      setS({ opError: true });
      return;
    }
    const login = (opForm.login || '').trim().toLowerCase();
    const password = opForm.password || '';
    if (!editing && (login.length < 3 || password.length < 8)) {
      setS({ opError: true });
      return;
    }
    if (editing && password && password.length < 8) {
      setS({ opError: true });
      return;
    }
    const tribute = opForm.tribute?.trim();
    const payload = {
      permissions_mask: maskFromOpRights(orR),
      allowed_studio_model_ids: opForm.modelIds || [],
    };
    if (tribute !== '') payload.tribute_share_percent = Math.round(Number(tribute));
    if (!editing) {
      payload.member_login = login;
      payload.password = password;
    } else if (password) {
      payload.password = password;
    }
    const req = editing
      ? cabinet.updateMember(s.opEditId, payload)
      : cabinet.createMember(payload);
    void req.then(() => {
      setS({
        opEditId: null,
        opError: false,
        opForm: { login: '', password: '', tribute: '15', modelIds: [] },
        opRights: { chat: false, studio: false, models: false, keys: false, billing: false },
      });
      go('team')();
    }).catch(() => setS({ opError: true }));
  };

  const removeOp = () => {
    if (!editing) return;
    const ok = window.confirm(
      lang === 'ru' ? `Удалить оператора «${opForm.login}»?` : `Delete operator "${opForm.login}"?`,
    );
    if (!ok) return;
    void cabinet.deleteMember(s.opEditId).then(() => {
      setS({ opEditId: null, opError: false });
      go('team')();
    });
  };

  return (
    <Fade style={{ maxWidth: 820 }} data-screen-label={editing ? 'Редактирование оператора' : 'Новый оператор'}>
      <BackLink onClick={go('team')}>{t.navTeam}</BackLink>
      <PageTitle style={{ marginBottom: 16 }}>{editing ? t.editOperator : t.newOperator}</PageTitle>

      <Panel style={{ padding: 18, marginBottom: 12 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <Field
            label={t.opLogin}
            placeholder={t.opLoginPh}
            value={opForm.login}
            onChange={(e) => setOpForm({ login: e.target.value })}
            readOnly={editing}
          />
          <Field
            label={editing ? (lang === 'ru' ? 'НОВЫЙ ПАРОЛЬ' : 'NEW PASSWORD') : t.opPass}
            type="password"
            placeholder={editing ? (lang === 'ru' ? 'оставьте пустым, если не меняете' : 'leave blank to keep') : ''}
            value={opForm.password}
            onChange={(e) => setOpForm({ password: e.target.value })}
          />
        </div>
      </Panel>

      <Panel style={{ padding: 18, marginBottom: 12 }}>
        <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 12 }}>{t.opRights}</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {opRightDefs.map((r) => (
            <Hoverable
              key={r.key}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 14,
                background: color.bgPanel,
                border: `1px solid ${orR[r.key] ? 'rgba(215,244,82,.25)' : line.hair}`,
                borderRadius: 12, padding: '14px 16px', cursor: 'pointer',
              }}
              hover={{ borderColor: orR[r.key] ? 'rgba(215,244,82,.5)' : borderHoverOff }}
              onClick={() => setS({ opRights: { ...orR, [r.key]: !orR[r.key] } })}
              role="checkbox"
              aria-checked={orR[r.key]}
            >
              <span style={{ fontFamily: font.mono, fontSize: 11, letterSpacing: '1px', color: color.textMid, textTransform: 'uppercase' }}>
                {r.label}
              </span>
              <Checkbox on={orR[r.key]} />
            </Hoverable>
          ))}
        </div>
      </Panel>

      <Panel style={{ padding: 18, marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginBottom: 12 }}>
          <span style={{ fontWeight: 800, fontSize: 14 }}>{t.opModels}</span>
          <div style={{ width: 120 }}>
            <div style={fieldLbl}>{t.opTribute}</div>
            <input value={opForm.tribute} onChange={(e) => setOpForm({ tribute: e.target.value })} style={inputSt} aria-label={t.opTribute} />
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(150px,1fr))', gap: 8 }}>
          {opModelNames.map((m) => {
            const on = (opForm.modelIds || []).includes(m.id);
            return (
            <Hoverable
              key={m.id}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
                background: color.bgPanel, border: `1px solid ${on ? 'rgba(215,244,82,.3)' : line.hair}`,
                borderRadius: 10, padding: '10px 12px', cursor: 'pointer',
              }}
              hover={{ borderColor: borderHoverOff }}
              onClick={() => {
                const ids = new Set(opForm.modelIds || []);
                if (ids.has(m.id)) ids.delete(m.id);
                else ids.add(m.id);
                setOpForm({ modelIds: [...ids] });
              }}
            >
              <span style={{ fontFamily: font.mono, fontSize: 11, letterSpacing: '.5px' }}>{m.name}</span>
              <Checkbox on={on} />
            </Hoverable>
          );})}
        </div>
      </Panel>

      {s.opError && (
        <div
          role="alert"
          style={{
            background: 'rgba(248,113,113,.08)', border: '1px solid rgba(248,113,113,.35)',
            borderRadius: 12, padding: '12px 14px', marginBottom: 12,
            fontSize: 12, fontWeight: 700, color: color.red,
          }}
        >
          ⚠ {t.opErr}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <Hoverable
          style={{
            background: color.lime, color: color.limeInk, fontWeight: 800, fontSize: 13,
            borderRadius: 10, padding: '11px 20px', cursor: 'pointer',
          }}
          hover={{ background: color.limeHi }}
          onClick={saveOp}
        >
          {t.opSave}
        </Hoverable>
        {editing && (
          <Hoverable
            style={{
              border: `1px solid rgba(248,113,113,.35)`, color: color.red, fontWeight: 700,
              fontSize: 13, borderRadius: 10, padding: '11px 20px', cursor: 'pointer',
            }}
            hover={{ background: 'rgba(248,113,113,.08)' }}
            onClick={removeOp}
          >
            {t.delete}
          </Hoverable>
        )}
        <Hoverable
          style={{
            border: `1px solid ${line.mid}`, color: color.textDim, fontWeight: 700,
            fontSize: 13, borderRadius: 10, padding: '11px 20px', cursor: 'pointer',
          }}
          hover={{ borderColor: borderHoverOff }}
          onClick={go('team')}
        >
          {t.opCancel}
        </Hoverable>
      </div>
    </Fade>
  );
}

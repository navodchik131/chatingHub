import Hoverable from '../components/Hoverable';
import { Fade, PageTitle, Eyebrow, Panel, Avatar, LimeButton, BackLink, Checkbox, Field } from '../components/ui';
import { useApp } from '../hooks/useApp';
import { color, line, font } from '../styles/tokens';
import { fieldLbl, inputSt } from '../styles/mixins';
import { teamKpiData, membersData, templatesData, opModelNames } from '../data/mock';

const rightStyle = (on) => ({
  fontFamily: font.mono, fontSize: 8.5, letterSpacing: '.5px',
  padding: '2px 8px', borderRadius: 5,
  ...(on
    ? { background: 'rgba(215,244,82,.12)', color: color.lime }
    : { background: 'rgba(255,255,255,.05)', color: color.textGhost, textDecoration: 'line-through' }),
});

export default function Team() {
  const { t, lang, setS } = useApp();

  return (
    <Fade data-screen-label="Команда">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 14, flexWrap: 'wrap', marginBottom: 16 }}>
        <div>
          <PageTitle style={{ marginBottom: 5 }}>{t.navTeam}</PageTitle>
          <div style={{ fontSize: 12.5, color: color.textDim }}>{t.teamDesc}</div>
        </div>
        <LimeButton onClick={() => setS({ page: 'newOperator', opError: false })}>+ {t.addOperator}</LimeButton>
      </div>

      {/* KPI */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: 12, marginBottom: 16 }}>
        {teamKpiData(lang).map((tk) => (
          <Panel key={tk.label} style={{ borderRadius: 14, padding: '14px 16px' }}>
            <Eyebrow size={9} style={{ marginBottom: 8 }}>{tk.label}</Eyebrow>
            <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 17 }}>{tk.value}</div>
          </Panel>
        ))}
      </div>

      {/* members */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {membersData(lang).map((mb) => (
          <Panel key={mb.login} style={{ padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
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
                hover={{ color: color.text, borderColor: line.hover }}
              >
                {t.edit}
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
          >
            + {t.addTemplate}
          </Hoverable>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))', gap: 10 }}>
          {templatesData(lang).map((tp) => (
            <div key={tp.title} style={{ background: color.bgPanel, border: `1px solid ${line.hair}`, borderRadius: 12, padding: '12px 14px' }}>
              <div style={{ fontWeight: 700, fontSize: 12.5, marginBottom: 4 }}>{tp.title}</div>
              <div style={{ fontSize: 11, color: color.textDim, lineHeight: 1.5 }}>{tp.body}</div>
            </div>
          ))}
        </div>
      </Panel>
    </Fade>
  );
}

/* ── new operator ────────────────────────────────────────── */
export function NewOperator() {
  const { t, s, setS, go } = useApp();
  const orR = s.opRights;

  const opRightDefs = [
    { key: 'chat', label: t.rChat },
    { key: 'studio', label: t.rStudio },
    { key: 'models', label: t.rModels },
    { key: 'keys', label: t.rKeys },
    { key: 'billing', label: t.rBilling },
  ];

  const saveOp = () => setS({ opError: !Object.values(orR).some(Boolean) });

  return (
    <Fade style={{ maxWidth: 820 }} data-screen-label="Новый оператор">
      <BackLink onClick={go('team')}>{t.navTeam}</BackLink>
      <PageTitle style={{ marginBottom: 16 }}>{t.newOperator}</PageTitle>

      <Panel style={{ padding: 18, marginBottom: 12 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <Field label={t.opLogin} placeholder={t.opLoginPh} />
          <Field label={t.opPass} type="password" />
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
              hover={{ borderColor: orR[r.key] ? 'rgba(215,244,82,.5)' : line.mid }}
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
            <input defaultValue="15" style={inputSt} aria-label={t.opTribute} />
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(150px,1fr))', gap: 8 }}>
          {opModelNames.map((n, i) => (
            <Hoverable
              key={n}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
                background: color.bgPanel, border: `1px solid ${line.hair}`,
                borderRadius: 10, padding: '10px 12px', cursor: 'pointer',
              }}
              hover={{ borderColor: 'rgba(255,255,255,.2)' }}
            >
              <span style={{ fontFamily: font.mono, fontSize: 11, letterSpacing: '.5px' }}>{n}</span>
              <Checkbox on={i >= 5} />
            </Hoverable>
          ))}
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

      <div style={{ display: 'flex', gap: 8 }}>
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
        <Hoverable
          style={{
            border: `1px solid ${line.mid}`, color: color.textDim, fontWeight: 700,
            fontSize: 13, borderRadius: 10, padding: '11px 20px', cursor: 'pointer',
          }}
          hover={{ borderColor: line.hover }}
          onClick={go('team')}
        >
          {t.opCancel}
        </Hoverable>
      </div>
    </Fade>
  );
}

import { useEffect, useState } from 'react';
import Hoverable from '../components/Hoverable';
import { IcoTg, IcoGlobe, IcoCopy } from '../components/Icons';
import { Fade, PageTitle, Eyebrow, Chip, StatusChip, Panel, Field } from '../components/ui';
import { useApp } from '../hooks/useApp';
import { color, line, font } from '../styles/tokens';
import { fieldLbl, borderHoverOff, selectSt } from '../styles/mixins';
import { fmtMoney } from '../api/helpers';
import { mapDonationStats } from '../api/mappers';
import { copyText } from '../utils/clipboard';

const linkIcons = { tg: IcoTg, globe: IcoGlobe };

const payoutAssets = ['USDT', 'TON'];

function DonOverview() {
  const { t, lang, cabinet } = useApp();
  const ps = cabinet.payoutSettings;
  const [wallet, setWallet] = useState('');
  const [asset, setAsset] = useState('USDT');

  useEffect(() => {
    setWallet(ps?.wallet_address || '');
    setAsset(ps?.payout_asset || 'USDT');
  }, [ps?.wallet_address, ps?.payout_asset]);

  const donStatsData = mapDonationStats(cabinet.donationOverview, lang);
  const donLinksData = (cabinet.donations || []).map((d) => ({
    id: d.id,
    title: d.title || '—',
    st: (d.status || 'DRAFT').toUpperCase(),
    tone: d.status === 'active' ? 'active' : d.status === 'moderation' ? 'warn' : 'dim',
    urls: [
      d.telegram_link ? { kind: 'Telegram', icon: 'tg', col: '#38BDF8', url: d.telegram_link } : null,
      d.web_link ? { kind: 'Web', icon: 'globe', col: '#C084FC', url: d.web_link } : null,
    ].filter(Boolean),
  }));
  const incomingData = (cabinet.donationEvents || [])
    .filter((e) => e.amount_minor > 0)
    .slice(0, 5)
    .map((e) => ({
      sum: `+${fmtMoney(e.amount_minor, e.currency)}`,
      from: e.donor_label || e.link_title || '—',
      when: e.occurred_at ? new Date(e.occurred_at).toLocaleString(lang === 'ru' ? 'ru-RU' : 'en-GB') : '—',
    }));

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: 12, marginBottom: 16 }}>
        {donStatsData.map((ds) => (
          <Panel key={ds.label} style={{ borderRadius: 14, padding: '14px 16px' }}>
            <Eyebrow size={9} style={{ marginBottom: 8 }}>{ds.label}</Eyebrow>
            <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 17, color: ds.color }}>{ds.value}</div>
          </Panel>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(300px,1fr))', gap: 12 }}>
        {/* payout */}
        <div
          style={{
            background: 'linear-gradient(140deg,rgba(240,168,200,.1),rgba(240,168,200,.02))',
            border: '1px solid rgba(240,168,200,.3)', borderRadius: 16, padding: '16px 18px',
          }}
        >
          <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 8 }}>{t.payout}</div>
          <div style={{ fontSize: 11.5, color: color.textDim, lineHeight: 1.6, marginBottom: 14 }}>{t.payoutHint}</div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 14 }}>
            <Field
              label={t.walletAddress}
              placeholder={lang === 'ru' ? 'Адрес кошелька' : 'Wallet address'}
              value={wallet}
              onChange={(e) => setWallet(e.target.value)}
            />
            <div>
              <div style={fieldLbl}>{t.payoutAsset}</div>
              <select
                value={asset}
                onChange={(e) => setAsset(e.target.value)}
                style={selectSt}
              >
                {payoutAssets.map((a) => (
                  <option key={a} value={a}>{a}</option>
                ))}
              </select>
            </div>
            <Hoverable
              style={{
                background: 'rgba(255,255,255,.06)', border: `1px solid ${line.mid}`,
                fontWeight: 700, fontSize: 12, borderRadius: 10, padding: '9px 14px',
                textAlign: 'center', cursor: 'pointer', color: color.textMid,
              }}
              hover={{ borderColor: borderHoverOff }}
              onClick={() => {
                const addr = wallet.trim();
                if (addr.length < 8) return;
                void cabinet.savePayoutSettings(addr, asset);
              }}
            >
              {t.saveWallet}
            </Hoverable>
          </div>

          <Hoverable
            style={{
              background: 'linear-gradient(120deg,#F0A8C8,#C084FC)', color: color.purpleInk,
              fontWeight: 800, fontSize: 12.5, borderRadius: 10, padding: '10px 16px',
              textAlign: 'center', cursor: 'pointer',
            }}
            hover={{ filter: 'brightness(1.08)' }}
            onClick={() => void cabinet.requestPayout()}
          >
            {t.requestPayout}
          </Hoverable>
          <div style={{ fontSize: 11, color: color.textDim, marginTop: 12 }}>
            {t.holdPolicy} <a href="#policy">Wiki →</a>
          </div>
        </div>

        {/* links */}
        <Panel style={{ padding: '16px 18px' }}>
          <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 12 }}>{t.donLinks}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {donLinksData.length === 0 && (
              <div style={{ fontSize: 12, color: color.textDim }}>{lang === 'ru' ? 'Ссылок пока нет' : 'No links yet'}</div>
            )}
            {donLinksData.map((dl) => (
              <div key={dl.id ?? dl.title} style={{ background: color.bgPanel, border: `1px solid ${line.hair}`, borderRadius: 12, padding: '12px 14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <span style={{ fontWeight: 700, fontSize: 12.5 }}>{dl.title}</span>
                  <StatusChip tone={dl.tone}>{dl.st}</StatusChip>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {dl.urls.map((u) => {
                    const Icon = linkIcons[u.icon];
                    return (
                      <div key={u.kind} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ display: 'flex', width: 13, height: 13, color: u.col, flex: 'none' }}><Icon /></span>
                        <span
                          style={{
                            flex: 1, fontFamily: font.mono, fontSize: 10, color: color.textDim,
                            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                          }}
                        >
                          {u.url}
                        </span>
                        <Hoverable
                          as="span"
                          style={{ display: 'flex', width: 13, height: 13, color: color.textMuted, cursor: 'pointer', flex: 'none' }}
                          hover={{ color: color.lime }}
                          aria-label={t.copy}
                          onClick={() => void copyText(u.url)}
                        >
                          <IcoCopy />
                        </Hoverable>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </Panel>

        {/* incoming */}
        <Panel style={{ padding: '16px 18px' }}>
          <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 12 }}>{t.lastIncoming}</div>
          {incomingData.length ? incomingData.map((inc, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 0', borderBottom: '1px solid rgba(255,255,255,.05)' }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 700, fontSize: 12.5, color: color.green }}>{inc.sum}</div>
                <div style={{ fontSize: 11, color: color.textDim }}>{inc.from}</div>
              </div>
              <span style={{ fontFamily: font.mono, fontSize: 9.5, color: color.textGhost }}>{inc.when}</span>
            </div>
          )) : (
            <div style={{ fontSize: 12, color: color.textDim }}>{lang === 'ru' ? 'Входящих пока нет' : 'No incoming yet'}</div>
          )}
        </Panel>
      </div>
    </div>
  );
}

function DonCreate() {
  const { t, lang, s, setS, cabinet } = useApp();
  const editingId = cabinet.donationEditId;
  const form = s.donForm || { title: '', description: '', minRub: 0, modelId: '' };
  const setForm = (patch) => setS({ donForm: { ...form, ...patch } });
  const modelOptions = (cabinet.models || []).map((m) => ({ id: String(m.id), name: m.name }));
  const myDonations = (cabinet.donations || []).map((d) => ({
    id: d.id,
    title: d.title || '—',
    st: (d.status || 'DRAFT').toUpperCase(),
    tone: d.status === 'active' ? 'active' : d.status === 'moderation' ? 'warn' : 'dim',
    raw: d,
  }));

  useEffect(() => {
    if (!editingId) return;
    const row = (cabinet.donations || []).find((d) => Number(d.id) === Number(editingId));
    if (!row) return;
    setS({
      donForm: {
        title: row.title || '',
        description: row.description || '',
        minRub: row.min_amount_minor ? Math.round(row.min_amount_minor / 100) : 0,
        modelId: row.studio_model_id ? String(row.studio_model_id) : '',
      },
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- только при смене editingId, не при каждом refresh
  }, [editingId]);

  const resetForm = () => {
    cabinet.setDonationEditId(null);
    setS({ donForm: { title: '', description: '', minRub: 0, modelId: '' } });
  };

  const startEdit = (row) => {
    cabinet.setDonationEditId(row.id);
    setS({
      donForm: {
        title: row.title || '',
        description: row.description || '',
        minRub: row.min_amount_minor ? Math.round(row.min_amount_minor / 100) : 0,
        modelId: row.studio_model_id ? String(row.studio_model_id) : '',
      },
    });
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(300px,1fr))', gap: 12 }}>
      <Panel style={{ padding: 18 }}>
        <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 12 }}>
          {editingId ? t.editDonation : t.newDonation}
        </div>
        {editingId && (
          <div style={{ fontSize: 11, color: color.textDim, marginBottom: 10 }}>
            {lang === 'ru' ? `Редактирование #${editingId}` : `Editing #${editingId}`}
          </div>
        )}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Field
            label={t.donTitle}
            placeholder={lang === 'ru' ? 'Поддержать 💕' : 'Support 💕'}
            value={form.title}
            onChange={(e) => setForm({ title: e.target.value })}
          />
          <Field
            label={t.donDesc}
            area
            rows={3}
            placeholder={lang === 'ru' ? 'За что и на что собираете…' : 'What the donation is for…'}
            value={form.description}
            onChange={(e) => setForm({ description: e.target.value })}
          />
          <div style={{ maxWidth: 160 }}>
            <Field
              label={t.minSum}
              value={String(form.minRub || '')}
              onChange={(e) => setForm({ minRub: Number(e.target.value) || 0 })}
            />
          </div>
          {modelOptions.length > 0 && (
            <div>
              <div style={fieldLbl}>{t.character}</div>
              <select
                value={form.modelId || ''}
                onChange={(e) => setForm({ modelId: e.target.value })}
                style={selectSt}
              >
                <option value="">{lang === 'ru' ? 'Не привязан' : 'Not linked'}</option>
                {modelOptions.map((m) => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
              </select>
            </div>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
          <Hoverable
            style={{
              background: color.lime, color: color.limeInk, fontWeight: 800, fontSize: 12.5,
              borderRadius: 10, padding: '10px 18px', cursor: 'pointer',
            }}
            hover={{ background: color.limeHi }}
            onClick={() => void cabinet.saveDonation(form, true).then(() => {
              resetForm();
              setS({ donTab: 'overview' });
            })}
          >
            {t.toModeration}
          </Hoverable>
          <Hoverable
            style={{
              border: `1px solid ${line.mid}`, color: color.textDim, fontWeight: 700,
              fontSize: 12.5, borderRadius: 10, padding: '10px 18px', cursor: 'pointer',
            }}
            hover={{ borderColor: borderHoverOff }}
            onClick={() => void cabinet.saveDonation(form, false).then(() => {
              if (editingId) resetForm();
              setS({ donTab: 'overview' });
            })}
          >
            {t.saveDraft}
          </Hoverable>
          {editingId && (
            <Hoverable
              style={{
                border: `1px solid ${line.mid}`, color: color.textDim, fontWeight: 700,
                fontSize: 12.5, borderRadius: 10, padding: '10px 18px', cursor: 'pointer',
              }}
              hover={{ borderColor: borderHoverOff }}
              onClick={resetForm}
            >
              {t.cancelEdit}
            </Hoverable>
          )}
        </div>
      </Panel>

      <Panel style={{ padding: 18 }}>
        <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 12 }}>{t.myDonations}</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {myDonations.map((d) => (
            <div
              key={d.id ?? d.title}
              style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10,
                background: color.bgPanel, border: `1px solid ${line.hair}`,
                borderRadius: 12, padding: '11px 14px',
              }}
            >
              <span style={{ fontWeight: 700, fontSize: 12.5 }}>{d.title}</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <StatusChip tone={d.tone}>{d.st}</StatusChip>
                <Hoverable
                  as="span"
                  style={{ fontSize: 11, fontWeight: 700, color: color.textDim, cursor: 'pointer' }}
                  hover={{ color: color.lime }}
                  onClick={() => startEdit(d.raw)}
                >
                  {t.edit}
                </Hoverable>
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

export default function Donations() {
  const { t, s, setS } = useApp();

  return (
    <Fade data-screen-label="Донаты">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 14, flexWrap: 'wrap', marginBottom: 16 }}>
        <div>
          <PageTitle style={{ marginBottom: 5 }}>{t.navDonations}</PageTitle>
          <div style={{ fontSize: 12.5, color: color.textDim }}>{t.donationsDesc}</div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <Chip on={s.donTab === 'overview'} onClick={() => setS({ donTab: 'overview' })}>{t.donTabOverview}</Chip>
          <Chip on={s.donTab === 'create'} onClick={() => setS({ donTab: 'create' })}>{t.donTabCreate}</Chip>
        </div>
      </div>

      {s.donTab === 'overview' ? <DonOverview /> : <DonCreate />}
    </Fade>
  );
}

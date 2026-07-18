import Hoverable from '../components/Hoverable';
import { IcoCopy, IcoBolt } from '../components/Icons';
import { Fade, PageTitle, Eyebrow, Panel, StatusChip } from '../components/ui';
import { useApp } from '../hooks/useApp';
import { color, line, font } from '../styles/tokens';
import { segOn, segOff, borderHoverOff } from '../styles/mixins';
import { fmtCredits, fmtMoney } from '../api/helpers';
import { mapUsageBars, mapCreditHistory } from '../api/mappers';
import { copyText } from '../utils/clipboard';

function normalizePlan(raw) {
  const p = String(raw || 'standard').toLowerCase();
  if (p === 'managed') return 'standard';
  if (p === 'byok') return 'pro';
  return p;
}

export default function Billing() {
  const { t, lang, s, setS, cabinet } = useApp();
  const { me, billingPlans, creditHistory, referral, tributeEarnings } = cabinet;
  const yookassaAvailable = Boolean(me?.online_payment_available);
  const tributeAvailable = Boolean(me?.tribute_billing_available);
  const defaultPayMethod = yookassaAvailable ? 'yookassa' : (tributeAvailable ? 'tribute' : 'credits');
  const tierOrder = { solo: 0, pro: 1, studio: 2 };
  const catalogPlans = billingPlans?.catalog?.plans || [];
  const tierPlans = catalogPlans
    .filter((p) => p.billing_plan === s.tier && p.period === s.period)
    .sort((a, b) => (tierOrder[a.tier] ?? 9) - (tierOrder[b.tier] ?? 9));
  const plans = tierPlans.map((p) => ({
    name: p.title || p.title_ru || p.product,
    price: String(p.price_rub ?? p.price ?? 0),
    tag: me?.plan_tier === p.tier && normalizePlan(me?.billing_plan) === p.billing_plan
      ? (lang === 'ru' ? 'ВАШ' : 'YOURS')
      : p.tier === 'pro' ? (lang === 'ru' ? 'ПОПУЛЯРНЫЙ' : 'POPULAR') : undefined,
    desc: `${p.limits?.max_users ?? '—'} ops · ${p.limits?.max_models ?? '—'} chars`,
    product: p.product,
  }));
  const perLabel = s.period === 'month' ? (lang === 'ru' ? 'мес' : 'mo') : (lang === 'ru' ? 'год' : 'yr');
  const credits = fmtCredits(me?.credits_balance);
  const planName = me?.plan_display_name || me?.plan_tier || '—';
  const usageBars = mapUsageBars(me, lang);
  const historyRows = mapCreditHistory(creditHistory, lang);
  const packs = (billingPlans?.items || [])
    .filter((x) => x.credits_pricing)
    .slice(0, 4)
    .map((x) => {
      const cp = x.credits_pricing;
      const qty = cp?.bulk_from || 100;
      const unit = cp?.unit_price_rub || 0;
      const bulk = cp?.bulk_unit_price_rub || unit;
      const price = Math.round(qty * bulk);
      return {
        cr: String(qty),
        price: `${price.toLocaleString(lang === 'ru' ? 'ru-RU' : 'en-GB')} ₽`,
        bonus: qty >= 600 ? '+15%' : qty >= 300 ? '+10%' : qty >= 150 ? '+5%' : null,
        product: x.product,
        creditsQty: qty,
      };
    });
  const referralLink = referral?.referral_link || '—';
  const tributeAmount = tributeEarnings?.display_minor != null
    ? fmtMoney(tributeEarnings.display_minor, tributeEarnings.currency || 'RUB')
    : null;

  return (
    <Fade data-screen-label="Тариф и баланс">
      <div style={{ marginBottom: 16 }}>
        <PageTitle style={{ marginBottom: 5 }}>{t.navBilling}</PageTitle>
        <div style={{ fontSize: 12.5, color: color.textDim }}>{t.billingDesc}</div>
      </div>

      {/* current plan + balance + referral */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))', gap: 12, marginBottom: 20 }}>
        <Panel style={{ padding: '16px 18px' }}>
          <Eyebrow size={9} style={{ marginBottom: 10 }}>{t.currentPlan}</Eyebrow>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <span style={{ fontFamily: font.display, fontWeight: 600, fontSize: 18 }}>{planName}</span>
            <StatusChip tone="active">{t.active}</StatusChip>
          </div>
          <div style={{ fontSize: 11.5, color: color.textDim, marginBottom: 14 }}>
            {me?.subscription_expires_at ? `${t.until} ${new Date(me.subscription_expires_at).toLocaleDateString(lang === 'ru' ? 'ru-RU' : 'en-GB')}` : '—'}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {usageBars.map((u) => (
              <div key={u.label}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                  <span style={{ color: color.textDim }}>{u.label}</span>
                  <span style={{ fontFamily: font.mono, color: color.textMid }}>{u.val}</span>
                </div>
                <div style={{ height: 6, background: 'rgba(255,255,255,.07)', borderRadius: 3, overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${u.pct}%`, background: color.green, borderRadius: 3 }} />
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <div
          style={{
            background: 'linear-gradient(140deg,rgba(215,244,82,.12),rgba(215,244,82,.02))',
            border: '1px solid rgba(215,244,82,.28)', borderRadius: 16, padding: '16px 18px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <span style={{ display: 'flex', width: 15, height: 15, color: color.lime }}><IcoBolt /></span>
            <Eyebrow size={9.5} style={{ marginBottom: 0, color: color.limeOlive }}>{t.kpiCredits}</Eyebrow>
          </div>
          <div style={{ fontFamily: font.display, fontWeight: 700, fontSize: 30, color: color.lime }}>{credits}</div>
          <div style={{ fontSize: 11.5, color: color.textDim, marginTop: 4, marginBottom: 14 }}>
            {t.balance} · ≈ {Math.floor(Number(credits) / 10)} {t.framesLeft}
          </div>
          <Hoverable
            style={{
              background: color.lime, color: color.limeInk, fontWeight: 800, fontSize: 12.5,
              borderRadius: 10, padding: '10px 16px', textAlign: 'center', cursor: 'pointer',
            }}
            hover={{ background: color.limeHi }}
            onClick={() => {
              const pack = packs[0];
              if (!pack) return;
              void cabinet.payBilling(defaultPayMethod, pack.product, pack.creditsQty);
            }}
          >
            {t.topup}
          </Hoverable>
        </div>

        <Panel style={{ padding: '16px 18px' }}>
          <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 8 }}>{t.referral}</div>
          <div style={{ fontSize: 11.5, color: color.textDim, lineHeight: 1.55, marginBottom: 12 }}>{t.referralHint}</div>
          <div
            style={{
              display: 'flex', alignItems: 'center', gap: 8, background: color.bgPanel,
              border: `1px solid ${line.soft}`, borderRadius: 9, padding: '8px 10px', marginBottom: 12,
            }}
          >
            <span
              style={{
                flex: 1, fontFamily: font.mono, fontSize: 10, color: color.textDim,
                whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
              }}
            >
              {referralLink}
            </span>
            <Hoverable
              as="span"
              style={{ display: 'flex', width: 13, height: 13, color: color.textMuted, cursor: 'pointer', flex: 'none' }}
              hover={{ color: color.lime }}
              aria-label={t.copy}
              onClick={() => { if (referralLink && referralLink !== '—') void copyText(referralLink); }}
            >
              <IcoCopy />
            </Hoverable>
          </div>
          <div style={{ display: 'flex', gap: 18 }}>
            <div>
              <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 16 }}>{referral?.invited_count ?? 0}</div>
              <div style={{ fontSize: 10, color: color.textMuted }}>{t.invited}</div>
            </div>
            <div>
              <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 16, color: color.lime }}>{referral?.credits_earned ?? 0} {t.cr}</div>
              <div style={{ fontSize: 10, color: color.textMuted }}>{t.earned}</div>
            </div>
          </div>
        </Panel>
      </div>

      {tributeAmount && (
        <Panel style={{ padding: '16px 18px', marginBottom: 20, maxWidth: 480 }}>
          <Eyebrow size={9} style={{ marginBottom: 10 }}>{t.tributeEarningsTitle}</Eyebrow>
          <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 22, color: color.purple, marginBottom: 6 }}>
            {tributeAmount}
          </div>
          <div style={{ fontSize: 11.5, color: color.textDim }}>{t.tributeEarningsHint}</div>
        </Panel>
      )}

      {/* plans */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 12 }}>
        <span style={{ fontWeight: 800, fontSize: 14 }}>{t.plans}</span>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', background: color.bgPanel, border: `1px solid ${line.soft}`, borderRadius: 10, padding: 3 }}>
            <div style={s.tier === 'standard' ? segOn : segOff} onClick={() => setS({ tier: 'standard' })}>Standard</div>
            <div style={s.tier === 'pro' ? segOn : segOff} onClick={() => setS({ tier: 'pro' })}>Pro</div>
          </div>
          <div style={{ display: 'flex', background: color.bgPanel, border: `1px solid ${line.soft}`, borderRadius: 10, padding: 3 }}>
            <div style={s.period === 'month' ? segOn : segOff} onClick={() => setS({ period: 'month' })}>{t.month}</div>
            <div style={s.period === 'year' ? segOn : segOff} onClick={() => setS({ period: 'year' })}>{t.year}</div>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))', gap: 12, marginBottom: 20 }}>
        {plans.map((p) => (
          <div
            key={p.product || p.name}
            style={{
              background: color.surface,
              border: `1px solid ${p.tag ? 'rgba(215,244,82,.35)' : line.hair}`,
              borderRadius: 16, padding: '16px 18px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontFamily: font.display, fontWeight: 600, fontSize: 16 }}>{p.name}</span>
              {p.tag && <StatusChip tone="active">{p.tag}</StatusChip>}
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 5, marginBottom: 10 }}>
              <span style={{ fontFamily: font.display, fontWeight: 700, fontSize: 22 }}>{p.price} ₽</span>
              <span style={{ fontSize: 11, color: color.textMuted }}>/ {perLabel}</span>
            </div>
            <div style={{ fontSize: 11.5, color: color.textDim, lineHeight: 1.5, marginBottom: 14 }}>{p.desc}</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {yookassaAvailable && (
              <Hoverable
                style={{
                  flex: 1, minWidth: 100, background: 'rgba(215,244,82,.12)', border: '1px solid rgba(215,244,82,.3)',
                  borderRadius: 9, padding: 8, textAlign: 'center', fontSize: 11.5,
                  fontWeight: 800, color: color.lime, cursor: 'pointer',
                }}
                hover={{ background: 'rgba(215,244,82,.2)' }}
                onClick={() => p.product && void cabinet.payBilling('yookassa', p.product)}
              >
                {t.payCard}
              </Hoverable>
              )}
              {tributeAvailable && (
              <Hoverable
                style={{
                  flex: 1, minWidth: 100, background: 'rgba(192,132,252,.12)', border: '1px solid rgba(192,132,252,.35)',
                  borderRadius: 9, padding: 8, textAlign: 'center', fontSize: 11.5,
                  fontWeight: 800, color: color.purple, cursor: 'pointer',
                }}
                hover={{ background: 'rgba(192,132,252,.2)' }}
                onClick={() => p.product && void cabinet.payBilling('tribute', p.product)}
              >
                {t.payTribute}
              </Hoverable>
              )}
              <Hoverable
                style={{
                  flex: 1, minWidth: 100, border: `1px solid ${line.mid}`, borderRadius: 9, padding: 8,
                  textAlign: 'center', fontSize: 11.5, fontWeight: 700, color: color.textDim, cursor: 'pointer',
                }}
                hover={{ borderColor: borderHoverOff }}
                onClick={() => p.product && void cabinet.payBilling('credits', p.product)}
              >
                {t.payCredits}
              </Hoverable>
            </div>
            {!yookassaAvailable && !tributeAvailable && (
              <div style={{ fontSize: 10.5, color: color.textMuted, marginTop: 8 }}>
                {lang === 'ru' ? 'Онлайн-оплата не настроена на сервере — доступна только оплата кредитами.' : 'Online payments are not configured — credits only.'}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* credit packs */}
      <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 12 }}>{t.creditPacks}</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))', gap: 12, marginBottom: 20 }}>
        {packs.map((p) => (
          <Hoverable
            key={p.cr}
            style={{
              background: color.surface, border: `1px solid ${line.hair}`, borderRadius: 14,
              padding: '14px 16px', cursor: 'pointer',
            }}
            hover={{ borderColor: 'rgba(215,244,82,.4)' }}
            onClick={() => void cabinet.payBilling(defaultPayMethod, p.product || 'credits_pack', p.creditsQty)}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 6 }}>
              <span style={{ fontFamily: font.display, fontWeight: 600, fontSize: 18, color: color.lime }}>{p.cr}</span>
              <span style={{ fontSize: 11, color: color.textMuted }}>{t.cr}</span>
              {p.bonus && (
                <span
                  style={{
                    fontFamily: font.mono, fontSize: 8.5, background: 'rgba(74,222,128,.12)',
                    color: color.green, border: '1px solid rgba(74,222,128,.3)',
                    padding: '1px 6px', borderRadius: 20, marginLeft: 'auto',
                  }}
                >
                  {p.bonus}
                </span>
              )}
            </div>
            <div style={{ fontSize: 13, fontWeight: 700 }}>{p.price}</div>
          </Hoverable>
        ))}
      </div>

      {/* history */}
      <Panel style={{ padding: '16px 18px' }}>
        <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 12 }}>{t.history}</div>
        {historyRows.map((h, i) => (
          <div
            key={i}
            style={{
              display: 'flex', alignItems: 'center', gap: 12, padding: '11px 2px',
              borderBottom: '1px solid rgba(255,255,255,.05)',
            }}
          >
            <span style={{ fontFamily: font.mono, fontSize: 9.5, color: color.textGhost, width: 62, flex: 'none' }}>{h.date}</span>
            <span style={{ flex: 1, fontSize: 12.5, color: color.textMid }}>{h.what}</span>
            <span style={{ fontFamily: font.mono, fontSize: 11, fontWeight: 600, color: h.color }}>{h.delta}</span>
          </div>
        ))}
      </Panel>
    </Fade>
  );
}

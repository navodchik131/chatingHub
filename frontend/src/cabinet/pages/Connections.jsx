import { useState } from 'react';
import Hoverable from '../components/Hoverable';
import { IcoTg, IcoWave, IcoHeart, IcoGift, IcoCam, IcoBell, IcoCopy } from '../components/Icons';
import {
  Fade, PageTitle, StatusChip, Panel, BackLink, IconBox, Field, SelectBox, Toggle, NoteBlock,
} from '../components/ui';
import { useApp } from '../hooks/useApp';
import { color, line, font } from '../styles/tokens';
import { fieldLbl, borderHoverOff, selectSt } from '../styles/mixins';
import { connDefs, connFieldSets } from '../data/catalog';
import { mapConnectionStatus, mapIntegrationConnections, mapIntegrationCurrent } from '../api/mappers';
import { copyText } from '../utils/clipboard';
import { isPlausibleTelegramBotToken } from '../api/helpers';
import * as actions from '../api/actions';
import { goToAdmin } from '../../marketing/workspaceEntry';

const connIcons = { tg: IcoTg, wave: IcoWave, heart: IcoHeart, gift: IcoGift, cam: IcoCam, bell: IcoBell };

const COMPANION_PLATFORMS = new Set(['tg', 'tg-user', 'fanvue', 'ig']);

function getRawConnection(platformId, integrations, connectionId) {
  if (!integrations || !connectionId) return null;
  if (platformId === 'tg') {
    return (integrations.telegram_connections || []).find((c) => Number(c.id) === Number(connectionId));
  }
  if (platformId === 'tg-user') {
    return (integrations.telegram_user_connections || []).find((c) => Number(c.id) === Number(connectionId));
  }
  if (platformId === 'fanvue') {
    return (integrations.fanvue_connections || []).find((c) => Number(c.id) === Number(connectionId));
  }
  if (platformId === 'ig') {
    return (integrations.instagram_connections || []).find((c) => Number(c.id) === Number(connectionId));
  }
  return null;
}

function companionModeOptions(lang) {
  return [
    { id: 'off', label: lang === 'ru' ? 'Выключен' : 'Off' },
    { id: 'draft', label: lang === 'ru' ? 'Черновики' : 'Drafts' },
    { id: 'semi_auto', label: lang === 'ru' ? 'Полуавто' : 'Semi-auto' },
    { id: 'auto', label: lang === 'ru' ? 'Авто' : 'Auto' },
  ];
}

function defaultGoalPresetForPlatform(platformId) {
  if (platformId === 'ig') return 'funnel';
  if (platformId === 'fanvue') return 'sales';
  return 'chat';
}

function companionGoalOptions(lang) {
  return [
    { id: 'chat', label: lang === 'ru' ? 'Общение / прогрев' : 'Chat / warm-up' },
    { id: 'funnel', label: lang === 'ru' ? 'Перелив трафика' : 'Traffic funnel' },
    { id: 'sales', label: lang === 'ru' ? 'Продажа контента' : 'Content sales' },
    { id: 'custom', label: lang === 'ru' ? 'Своя цель' : 'Custom goal' },
  ];
}

function platformGoalHint(platformId, lang) {
  if (platformId === 'ig') {
    return lang === 'ru'
      ? 'Instagram: болтай как обычно и помни диалог, но без сексинга. Когда тепло — веди в Telegram (ссылка из поля ниже).'
      : 'Instagram: chat normally and remember the thread, but no sexting. When it is warm, steer to Telegram (link below).';
  }
  if (platformId === 'fanvue') {
    return lang === 'ru'
      ? 'Fanvue: уместны лёгкие намёки на эксклюзив и платный контент, когда диалог тёплый.'
      : 'Fanvue: light tease for exclusive / paid content when the thread is warm.';
  }
  if (platformId === 'tg' || platformId === 'tg-user') {
    return lang === 'ru'
      ? 'Telegram: можно вести в приват / канал или сразу к продаже — задайте цель ниже.'
      : 'Telegram: funnel to private/channel or sell — set the goal below.';
  }
  return lang === 'ru'
    ? 'Цель действует только для этого подключения — персонаж и стиль остаются из модели.'
    : 'Goal applies to this connection only — persona stays from the character.';
}

function CompanionConnectionEditor({
  platformId, connectionId, integrations, modelOptions, lang, cabinet, onClose,
}) {
  const raw = getRawConnection(platformId, integrations, connectionId);
  const [modelId, setModelId] = useState(raw?.studio_model_id ? String(raw.studio_model_id) : '');
  const [companionMode, setCompanionMode] = useState(raw?.companion_mode || 'off');
  const [delayMin, setDelayMin] = useState(String(raw?.companion_delay_min_sec ?? 5));
  const [delayMax, setDelayMax] = useState(String(raw?.companion_delay_max_sec ?? 45));
  const [maxPerHour, setMaxPerHour] = useState(String(raw?.companion_max_replies_per_hour ?? 60));
  const [goalPreset, setGoalPreset] = useState(
    raw?.companion_goal_preset || defaultGoalPresetForPlatform(platformId),
  );
  const [goalText, setGoalText] = useState(raw?.companion_goal_text || '');
  const [goalLink, setGoalLink] = useState(raw?.companion_goal_link || '');
  const companionAllowed = cabinet?.me?.companion_allowed === true
    || (cabinet?.me?.companion_allowed == null
      && String(cabinet?.me?.plan_tier || '').toLowerCase() === 'studio'
      && String(cabinet?.me?.subscription_status || '').toLowerCase() === 'active');

  if (!raw) return null;

  const save = async () => {
    if (!companionAllowed && companionMode !== 'off') return;
    const ok = await cabinet.patchConnectionSettings(platformId, connectionId, {
      modelId: modelId || null,
      companionMode: companionAllowed ? companionMode : 'off',
      delayMin,
      delayMax,
      maxPerHour,
      goalPreset,
      goalText: goalText.trim(),
      goalLink: goalLink.trim(),
    });
    if (ok) onClose();
  };

  return (
    <Panel style={{ marginTop: 10, padding: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ fontWeight: 800, fontSize: 13 }}>
        {lang === 'ru' ? 'AI-компаньон на подключении' : 'Connection AI companion'}
      </div>
      {!companionAllowed ? (
        <NoteBlock>
          {lang === 'ru'
            ? 'AI-бот доступен только на тарифах Standard Studio и Pro Studio.'
            : 'AI bot is available only on Standard Studio and Pro Studio.'}
        </NoteBlock>
      ) : null}
      <ModelSelect
        label={lang === 'ru' ? 'ПЕРСОНАЖ' : 'CHARACTER'}
        value={modelId}
        options={modelOptions}
        lang={lang}
        onChange={(e) => setModelId(e.target.value)}
      />
      <div>
        <div style={fieldLbl}>{lang === 'ru' ? 'РЕЖИМ' : 'MODE'}</div>
        <select
          value={companionAllowed ? companionMode : 'off'}
          onChange={(e) => setCompanionMode(e.target.value)}
          style={selectSt}
          disabled={!companionAllowed}
        >
          {companionModeOptions(lang).map((o) => (
            <option key={o.id} value={o.id}>{o.label}</option>
          ))}
        </select>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
        <Field label={lang === 'ru' ? 'ЗАДЕРЖКА МИН' : 'DELAY MIN'} value={delayMin} onChange={(e) => setDelayMin(e.target.value)} />
        <Field label={lang === 'ru' ? 'ЗАДЕРЖКА МАКС' : 'DELAY MAX'} value={delayMax} onChange={(e) => setDelayMax(e.target.value)} />
        <Field label={lang === 'ru' ? 'АВТО/ЧАС' : 'AUTO/HR'} value={maxPerHour} onChange={(e) => setMaxPerHour(e.target.value)} />
      </div>

      <div>
        <div style={fieldLbl}>{lang === 'ru' ? 'ЦЕЛЬ БОТА' : 'BOT GOAL'}</div>
        <select value={goalPreset} onChange={(e) => setGoalPreset(e.target.value)} style={selectSt}>
          {companionGoalOptions(lang).map((o) => (
            <option key={o.id} value={o.id}>{o.label}</option>
          ))}
        </select>
      </div>
      <Field
        label={lang === 'ru' ? 'ССЫЛКА / @КАНАЛ' : 'LINK / @HANDLE'}
        value={goalLink}
        onChange={(e) => setGoalLink(e.target.value)}
        placeholder={lang === 'ru' ? '@mychannel или t.me/...' : '@mychannel or t.me/...'}
      />
      <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={fieldLbl}>
          {goalPreset === 'custom'
            ? (lang === 'ru' ? 'ИНСТРУКЦИЯ' : 'INSTRUCTIONS')
            : (lang === 'ru' ? 'УТОЧНЕНИЕ (необяз.)' : 'NOTES (optional)')}
        </span>
        <textarea
          value={goalText}
          onChange={(e) => setGoalText(e.target.value)}
          rows={3}
          maxLength={2000}
          placeholder={
            goalPreset === 'custom'
              ? (lang === 'ru'
                ? 'Например: веди в TG @mychannel. Общайся нормально, но без сексинга — туда зови, когда тепло.'
                : 'E.g. send them to TG @mychannel. Chat normally, no sexting — invite when the vibe is warm.')
              : (lang === 'ru' ? 'Доп. пожелания к стратегии…' : 'Extra strategy notes…')
          }
          style={{
            ...selectSt,
            minHeight: 72,
            resize: 'vertical',
            fontFamily: font.body,
            lineHeight: 1.45,
          }}
        />
      </label>
      <NoteBlock>{platformGoalHint(platformId, lang)}</NoteBlock>
      <NoteBlock>
        {lang === 'ru'
          ? 'Базовый режим для всех диалогов этого подключения. В отдельном чате можно переопределить в шапке диалога.'
          : 'Default mode for all dialogs on this connection. Override per chat in dialog settings.'}
      </NoteBlock>
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <Hoverable
          as="button"
          type="button"
          style={{ ...selectSt, width: 'auto', padding: '8px 14px', cursor: 'pointer' }}
          onClick={onClose}
        >
          {lang === 'ru' ? 'Отмена' : 'Cancel'}
        </Hoverable>
        <Hoverable
          as="button"
          type="button"
          style={{
            ...selectSt, width: 'auto', padding: '8px 14px', cursor: 'pointer',
            background: color.lime, color: color.limeInk, fontWeight: 800, border: 'none',
          }}
          onClick={() => { void save(); }}
        >
          {lang === 'ru' ? 'Сохранить' : 'Save'}
        </Hoverable>
      </div>
    </Panel>
  );
}

function oauthFlashErrorMessage(platformId, reason, t) {
  const r = (reason || '').trim().toLowerCase();
  if (platformId === 'fanvue') {
    if (r === 'access_denied') return t.fanvueOauthErrorDenied;
    if (r === 'invalid_scope' || r.includes('scope')) return t.fanvueOauthErrorScopes;
    if (r === 'invalid_state' || r === 'state_expired' || r === 'missing_code') return t.fanvueOauthErrorState;
    if (reason && reason.length > 8 && r !== 'callback_failed') return reason;
    return t.fanvueOauthErrorGeneric;
  }
  if (platformId === 'ig') {
    if (r === 'access_denied') return t.igOauthErrorDenied;
    if (r === 'invalid_state' || r === 'state_expired' || r === 'missing_code') return t.igOauthErrorState;
    if (r.includes('webhook')) return t.igOauthErrorWebhook;
    if (r.includes('token')) return t.igOauthErrorToken;
    if (r.includes('/me') || r.includes('profile')) return t.igOauthErrorProfile;
    if (reason && reason.length > 8 && r !== 'callback_failed') return reason;
    return t.igOauthErrorGeneric;
  }
  return t.fanvueOauthErrorGeneric.replace('Fanvue', platformId);
}

function ModelSelect({ label, value, options, onChange, lang, style }) {
  if (!options.length) return null;
  return (
    <div style={style}>
      <div style={fieldLbl}>{label}</div>
      <select
        value={value || ''}
        onChange={onChange}
        style={selectSt}
      >
        <option value="">{lang === 'ru' ? 'Не привязан' : 'Not linked'}</option>
        {options.map((m) => (
          <option key={m.id} value={m.id}>{m.name}</option>
        ))}
      </select>
    </div>
  );
}

function ConnectionList() {
  const { t, lang, setS, cabinet } = useApp();

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <PageTitle style={{ marginBottom: 5 }}>{t.navConnections}</PageTitle>
        <div style={{ fontSize: 12.5, color: color.textDim }}>{t.connectionsDesc}</div>
      </div>

      {cabinet.me?.is_platform_admin && (
        <Hoverable
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
            marginBottom: 14, padding: '12px 16px', borderRadius: 12,
            border: '1px solid rgba(251,146,60,.35)', background: 'rgba(251,146,60,.08)', cursor: 'pointer',
          }}
          hover={{ borderColor: 'rgba(251,146,60,.6)' }}
          onClick={goToAdmin}
        >
          <div>
            <div style={{ fontWeight: 800, fontSize: 13.5, color: color.orange }}>{t.adminPanel}</div>
            <div style={{ fontSize: 11.5, color: color.textDim }}>{t.adminPanelDesc}</div>
          </div>
          <span style={{ color: color.orange }}>→</span>
        </Hoverable>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))', gap: 12 }}>
        {connDefs(lang).map((c) => {
          const Icon = connIcons[c.icon];
          const live = mapConnectionStatus(cabinet.integrations, c.id, lang);
          const st = live?.st ?? c.st;
          const tone = live?.tone ?? c.tone;
          return (
            <Hoverable
              key={c.id}
              style={{
                background: color.surface, border: `1px solid ${line.hair}`, borderRadius: 16,
                padding: '16px 18px', cursor: 'pointer', display: 'flex', gap: 14, alignItems: 'flex-start',
              }}
              hover={{ borderColor: borderHoverOff, background: color.surfaceHi }}
              onClick={() => setS({ connDetail: c.id })}
            >
              <IconBox size={38} iconSize={18} tint={c.iconCol}><Icon /></IconBox>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 800, fontSize: 14 }}>{c.name}</span>
                  <StatusChip tone={tone} style={{ display: 'inline-block', marginTop: 3 }}>{st}</StatusChip>
                </div>
                <div style={{ fontSize: 11.5, color: color.textDim, lineHeight: 1.5, marginTop: 4 }}>{c.desc}</div>
              </div>
            </Hoverable>
          );
        })}
      </div>
    </div>
  );
}

function ConnectionDetail() {
  const { t, lang, s, setS, cabinet } = useApp();

  const defs = connDefs(lang);
  const data = defs.find((c) => c.id === s.connDetail) || defs[0];
  const cfs = connFieldSets(lang)[data.id] || connFieldSets(lang).tg;
  const ig = cabinet.integrations;
  const modelOptions = (cabinet.models || []).map((m) => ({ id: String(m.id), name: m.name }));

  const form = s.connForms?.[data.id] || {
    token: '', apiKey: '', label: '', modelId: modelOptions[0]?.id || '',
    phone: '', code: '', password: '', tgUserStep: 'phone', tgUserConnectionId: null,
    reconnectConnectionId: null, editConnectionId: null,
  };
  const [oauthBusy, setOauthBusy] = useState(false);
  const saving = cabinet.busy || oauthBusy;
  const setForm = (patch) =>
    setS({ connForms: { ...s.connForms, [data.id]: { ...form, ...patch } } });

  const current = mapIntegrationCurrent(data.id, ig, cabinet.models, lang);
  const list = mapIntegrationConnections(data.id, ig, cabinet.models, lang);

  const flashSuccessMessage = () => {
    if (data.id === 'wavespeed') {
      return lang === 'ru' ? 'Ключ WaveSpeed сохранён.' : 'WaveSpeed key saved.';
    }
    if (data.id === 'tg') {
      return lang === 'ru' ? 'Telegram-бот подключён.' : 'Telegram bot connected.';
    }
    if (data.id === 'tg-user') {
      return lang === 'ru' ? 'Личный Telegram подключён.' : 'Personal Telegram connected.';
    }
    if (data.id === 'tribute') {
      return lang === 'ru' ? 'Tribute API настроен.' : 'Tribute API configured.';
    }
    if (data.id === 'fanvue') {
      return lang === 'ru' ? 'Fanvue подключён.' : 'Fanvue connected.';
    }
    if (data.id === 'ig') {
      return lang === 'ru' ? 'Instagram подключён.' : 'Instagram connected.';
    }
    return lang === 'ru' ? 'Сохранено.' : 'Saved.';
  };

  const handleSave = async () => {
    let ok = false;
    if (data.id === 'wavespeed') {
      if (!form.apiKey?.trim()) return;
      ok = await cabinet.saveIntegration('wavespeed', { apiKey: form.apiKey.trim() });
      if (ok) setForm({ apiKey: '' });
    } else if (data.id === 'tg') {
      const token = form.token?.trim() || '';
      if (!token) return;
      if (!isPlausibleTelegramBotToken(token)) {
        cabinet.setError(
          lang === 'ru'
            ? 'Неверный формат токена BotFather. Скопируйте токен целиком: 123456789:AAH…'
            : 'Invalid BotFather token format. Paste the full token: 123456789:AAH…',
        );
        return;
      }
      ok = await cabinet.saveIntegration('tg', {
        token,
        modelId: form.modelId,
        connectionId: form.reconnectConnectionId || undefined,
      });
      if (ok) setForm({ token: '', reconnectConnectionId: null });
    } else if (data.id === 'tg-user') {
      const step = form.tgUserStep || 'phone';
      if (step === 'phone') {
        if (!(form.phone || '').trim()) return;
        setOauthBusy(true);
        try {
          const res = await actions.startTelegramUserLogin(
            form.phone,
            form.modelId,
            form.reconnectConnectionId ?? null,
          );
          setForm({
            tgUserStep: res.needs_password ? 'password' : 'code',
            tgUserConnectionId: res.connection_id,
            code: '',
            password: '',
          });
          cabinet.setError(null);
        } catch (e) {
          cabinet.setError(e?.message || String(e));
          ok = false;
        } finally {
          setOauthBusy(false);
        }
        return;
      }
      if (step === 'code') {
        if (!(form.code || '').trim() || !form.tgUserConnectionId) return;
        setOauthBusy(true);
        try {
          const res = await actions.confirmTelegramUserCode(form.tgUserConnectionId, form.code);
          if (res.needs_password) {
            setForm({ tgUserStep: 'password', code: '' });
            await cabinet.refreshAll();
            cabinet.setError(null);
          } else {
            await cabinet.refreshAll();
            setForm({ phone: '', code: '', password: '', tgUserStep: 'phone', tgUserConnectionId: null, reconnectConnectionId: null });
            ok = true;
          }
        } catch (e) {
          cabinet.setError(e?.message || String(e));
          ok = false;
        } finally {
          setOauthBusy(false);
        }
        if (ok) setS({ connFlash: 'ok' });
        return;
      }
      if (step === 'password') {
        if (!(form.password || '').trim() || !form.tgUserConnectionId) return;
        setOauthBusy(true);
        try {
          await actions.confirmTelegramUserPassword(form.tgUserConnectionId, form.password);
          await cabinet.refreshAll();
          setForm({ phone: '', code: '', password: '', tgUserStep: 'phone', tgUserConnectionId: null, reconnectConnectionId: null });
          ok = true;
        } catch (e) {
          cabinet.setError(e?.message || String(e));
          ok = false;
        } finally {
          setOauthBusy(false);
        }
        if (ok) setS({ connFlash: 'ok' });
        return;
      }
    } else if (data.id === 'fanvue') {
      setOauthBusy(true);
      try {
        ok = await cabinet.saveIntegration('fanvue', {
          modelId: form.modelId,
          connectionId: form.reconnectConnectionId || undefined,
        });
      } finally {
        setOauthBusy(false);
      }
    } else if (data.id === 'ig') {
      setOauthBusy(true);
      try {
        ok = await cabinet.saveIntegration('ig', {
          modelId: form.modelId,
          connectionId: form.reconnectConnectionId || undefined,
        });
      } finally {
        setOauthBusy(false);
      }
    } else if (data.id === 'tribute') {
      if (!form.apiKey?.trim()) return;
      ok = await cabinet.saveIntegration('tribute', {
        apiKey: form.apiKey.trim(),
        label: form.label?.trim(),
        modelId: form.modelId,
      });
      if (ok) setForm({ apiKey: '' });
    }
    if (!['fanvue', 'ig', 'tg-user'].includes(data.id)) {
      setS({ connFlash: ok ? 'ok' : 'error' });
    }
  };

  const handleDisconnect = (connectionId) => {
    const ok = window.confirm(
      lang === 'ru' ? 'Отключить это подключение?' : 'Disconnect this connection?',
    );
    if (!ok) return;
    void cabinet.disconnectIntegration(data.id, connectionId);
  };

  const hasCopy = ['fanvue', 'tribute', 'ig'].includes(data.id);
  const Icon = connIcons[data.icon];
  const disabled = data.id === 'push';
  const fanvueOAuthReady = ig?.fanvue_oauth_available !== false;
  const fanvueConnected = Boolean(ig?.fanvue_oauth_connected);
  const instagramOAuthReady = ig?.instagram_oauth_available !== false;
  const instagramConnected = (ig?.instagram_connections || []).length > 0;
  const maxConn = Number(ig?.max_connections_per_platform) || 1;
  const canAddMore = list.length < maxConn;
  const isReconnectMode = Boolean(form.reconnectConnectionId);
  const limitLabel = lang === 'ru'
    ? `Подключено: ${list.length} из ${maxConn}`
    : `Connected: ${list.length} of ${maxConn}`;

  const handleReconnectRow = (connectionId) => {
    if (data.id === 'ig' || data.id === 'fanvue') {
      setOauthBusy(true);
      void cabinet
        .saveIntegration(data.id, { modelId: form.modelId, connectionId })
        .finally(() => setOauthBusy(false));
      return;
    }
    if (data.id === 'tg') {
      setForm({ reconnectConnectionId: connectionId, token: '' });
      return;
    }
    if (data.id === 'tg-user') {
      setForm({
        reconnectConnectionId: connectionId,
        tgUserStep: 'phone',
        phone: '',
        code: '',
        password: '',
        tgUserConnectionId: null,
      });
    }
  };

  const webhookCopyUrl = () => {
    if (data.id === 'fanvue') {
      return ig?.fanvue_webhook_url || ig?.fanvue_connections?.[0]?.webhook_url || null;
    }
    if (data.id === 'tribute') {
      return ig?.tribute_connections?.[0]?.webhook_url || null;
    }
    if (data.id === 'ig') {
      return ig?.instagram_webhook_url || null;
    }
    return null;
  };

  const handleCopyWebhook = () => {
    const url = webhookCopyUrl();
    if (url) void copyText(url);
  };

  return (
    <div>
      <BackLink onClick={() => setS({ connDetail: null, connFlash: null, connOauthReason: null })}>{t.allConnections}</BackLink>

      {s.connFlash && ['fanvue', 'ig', 'wavespeed', 'tg', 'tg-user', 'tribute'].includes(data.id) && (
        <NoteBlock
          style={{
            marginBottom: 12,
            ...(s.connFlash === 'ok'
              ? { borderColor: 'rgba(74,222,128,.35)', background: 'rgba(74,222,128,.08)' }
              : { borderColor: 'rgba(248,113,113,.35)', background: 'rgba(248,113,113,.08)' }),
          }}
        >
          {s.connFlash === 'ok'
            ? flashSuccessMessage()
            : (['fanvue', 'ig'].includes(data.id)
              ? oauthFlashErrorMessage(data.id, s.connOauthReason, t)
              : (lang === 'ru' ? 'Не удалось сохранить. Проверьте ключ и попробуйте снова.' : 'Could not save. Check the key and try again.'))}
        </NoteBlock>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 16 }}>
        <IconBox size={48} iconSize={22} tint={data.iconCol} style={{ borderRadius: 14 }}><Icon /></IconBox>
        <div>
          <PageTitle size={19}>{data.name}</PageTitle>
          <div style={{ fontSize: 11.5, color: color.textDim }}>{data.desc}</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(290px,1fr))', gap: 12 }}>
        {/* settings */}
        <Panel style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ fontWeight: 800, fontSize: 13.5 }}>{cfs.title}</div>

          {['ig', 'fanvue', 'tg', 'tg-user'].includes(data.id) && maxConn > 1 && (
            <NoteBlock>{limitLabel}</NoteBlock>
          )}

          {current.length > 0 && list.length <= 1 && (
            <div style={{ background: 'rgba(74,222,128,.05)', border: '1px solid rgba(74,222,128,.2)', borderRadius: 12, padding: '12px 14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 9 }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: color.green }} />
                <span style={{ fontFamily: font.mono, fontSize: 9, letterSpacing: '1.4px', color: color.green }}>{t.curConfig}</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '7px 14px' }}>
                {current.map((cc) => (
                  <div key={cc.k} style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 11 }}>
                    <span style={{ color: color.textMuted }}>{cc.k}</span>
                    <span style={{ fontWeight: 700, color: color.textMid, textAlign: 'right' }}>{cc.v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {list.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {list.map((cl) => (
                <div
                  key={cl.id ?? cl.name}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10, background: color.bgPanel,
                    border: `1px solid ${line.hair}`, borderRadius: 10, padding: '9px 12px',
                  }}
                >
                  <span
                    style={{
                      width: 7,
                      height: 7,
                      borderRadius: '50%',
                      background: cl.statusTone === 'pending' ? color.yellow : color.green,
                      flex: 'none',
                    }}
                  />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 700, fontSize: 12 }}>{cl.name}</div>
                    <div style={{ fontSize: 10, color: color.textMuted }}>{cl.meta}</div>
                  </div>
                  {COMPANION_PLATFORMS.has(data.id) && cl.statusTone !== 'pending' && (
                    <Hoverable
                      as="span"
                      style={{ fontSize: 11, fontWeight: 700, color: color.textDim, cursor: 'pointer' }}
                      hover={{ color: color.lime }}
                      onClick={() => setForm({ editConnectionId: cl.id })}
                    >
                      {lang === 'ru' ? 'AI' : 'AI'}
                    </Hoverable>
                  )}
                  {['ig', 'fanvue', 'tg', 'tg-user'].includes(data.id) && cl.statusTone !== 'pending' && (
                    <Hoverable
                      as="span"
                      style={{ fontSize: 11, fontWeight: 700, color: color.textDim, cursor: 'pointer' }}
                      hover={{ color: color.green }}
                      onClick={() => handleReconnectRow(cl.id)}
                    >
                      {lang === 'ru' ? 'Переподключить' : 'Reconnect'}
                    </Hoverable>
                  )}
                  <Hoverable
                    as="span"
                    style={{ fontSize: 11, fontWeight: 700, color: color.textDim, cursor: 'pointer' }}
                    hover={{ color: color.red }}
                    onClick={() => handleDisconnect(cl.id)}
                  >
                    {t.disconnect}
                  </Hoverable>
                </div>
              ))}
            </div>
          )}

          {COMPANION_PLATFORMS.has(data.id) && form.editConnectionId && (
            <CompanionConnectionEditor
              platformId={data.id}
              connectionId={form.editConnectionId}
              integrations={ig}
              modelOptions={modelOptions}
              lang={lang}
              cabinet={cabinet}
              onClose={() => setForm({ editConnectionId: null })}
            />
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {data.id === 'wavespeed' && (
              <Field
                label={lang === 'ru' ? 'API KEY WAVESPEED' : 'WAVESPEED API KEY'}
                value={form.apiKey}
                onChange={(e) => setForm({ apiKey: e.target.value })}
                style={{ gridColumn: '1 / -1' }}
              />
            )}
            {data.id === 'tg' && (
              <>
                <Field
                  label="BOT TOKEN"
                  value={form.token}
                  onChange={(e) => setForm({ token: e.target.value })}
                  style={{ gridColumn: '1 / -1' }}
                />
                <ModelSelect
                  label={lang === 'ru' ? 'ПЕРСОНАЖ' : 'CHARACTER'}
                  value={form.modelId}
                  options={modelOptions}
                  lang={lang}
                  onChange={(e) => setForm({ modelId: e.target.value })}
                />
              </>
            )}
            {data.id === 'tg-user' && (
              <>
                {!ig?.telegram_user_available && (
                  <NoteBlock style={{ gridColumn: '1 / -1' }}>
                    {lang === 'ru'
                      ? 'Подключение личного Telegram пока недоступно. Обратитесь к администратору.'
                      : 'Personal Telegram connect is unavailable. Contact the administrator.'}
                  </NoteBlock>
                )}
                {(form.tgUserStep || 'phone') === 'phone' && (
                  <>
                    <Field
                      label={lang === 'ru' ? 'ТЕЛЕФОН' : 'PHONE'}
                      value={form.phone}
                      onChange={(e) => setForm({ phone: e.target.value })}
                      placeholder="+79001234567"
                      style={{ gridColumn: '1 / -1' }}
                    />
                    <ModelSelect
                      label={lang === 'ru' ? 'ПЕРСОНАЖ' : 'CHARACTER'}
                      value={form.modelId}
                      options={modelOptions}
                      lang={lang}
                      onChange={(e) => setForm({ modelId: e.target.value })}
                    />
                  </>
                )}
                {(form.tgUserStep || 'phone') === 'code' && (
                  <>
                    <Field
                      label={lang === 'ru' ? 'КОД ИЗ TELEGRAM / SMS' : 'CODE FROM TELEGRAM / SMS'}
                      value={form.code}
                      onChange={(e) => setForm({ code: e.target.value })}
                      style={{ gridColumn: '1 / -1' }}
                    />
                    <NoteBlock style={{ gridColumn: '1 / -1' }}>
                      {lang === 'ru'
                        ? 'Код приходит в приложение Telegram (чат «Telegram»), не путать с SMS. Если не подходит — вернитесь и запросите код заново.'
                        : 'The code arrives in the Telegram app, not always via SMS. If it fails, go back and request a new code.'}
                    </NoteBlock>
                  </>
                )}
                {(form.tgUserStep || 'phone') === 'password' && (
                  <>
                    <NoteBlock
                      style={{
                        gridColumn: '1 / -1',
                        borderColor: 'rgba(251,191,36,.35)',
                        background: 'rgba(251,191,36,.08)',
                      }}
                    >
                      {lang === 'ru'
                        ? 'Код принят. На аккаунте включена двухфакторная защита — введите облачный пароль из Telegram (Настройки → Конфиденциальность → Облачный пароль) и нажмите «Подтвердить пароль». Аккаунт появится в списке после успешного входа.'
                        : 'Code accepted. This account has 2FA enabled — enter the Telegram cloud password (Settings → Privacy → Cloud password) and click Confirm password. The account will appear in the list once login completes.'}
                    </NoteBlock>
                    <Field
                      label={lang === 'ru' ? 'ПАРОЛЬ 2FA (облачный)' : '2FA PASSWORD (cloud)'}
                      value={form.password}
                      onChange={(e) => setForm({ password: e.target.value })}
                      type="password"
                      style={{ gridColumn: '1 / -1' }}
                    />
                  </>
                )}
              </>
            )}
            {data.id === 'fanvue' && (
              <>
                {!fanvueOAuthReady && (
                  <NoteBlock style={{ gridColumn: '1 / -1' }}>
                    {lang === 'ru'
                      ? 'OAuth Fanvue недоступен на сервере — проверьте настройки интеграции.'
                      : 'Fanvue OAuth is not configured on the server.'}
                  </NoteBlock>
                )}
                {fanvueConnected && (
                  <NoteBlock style={{ gridColumn: '1 / -1', borderColor: 'rgba(74,222,128,.35)', background: 'rgba(74,222,128,.08)' }}>
                    {canAddMore
                      ? (lang === 'ru'
                        ? 'Можно добавить ещё один аккаунт Fanvue или переподключить существующий из списка.'
                        : 'You can add another Fanvue account or reconnect an existing one from the list.')
                      : (lang === 'ru'
                        ? 'Достигнут лимит подключений Fanvue на вашем тарифе.'
                        : 'Fanvue connection limit reached for your plan.')}
                  </NoteBlock>
                )}
                {fanvueOAuthReady && (
                  <NoteBlock style={{ gridColumn: '1 / -1' }}>
                    {lang === 'ru'
                      ? 'Для отправки изображений в Fanvue-чат нужны scopes write:media и write:creator. Если картинки не отправляются: включите их в Fanvue Developer Area → Authentication, отзовите доступ на fanvue.com/settings/account/third-party-apps и нажмите «Переподключить Fanvue».'
                      : 'Sending images in Fanvue chat requires write:media and write:creator scopes. If images fail: enable them in Fanvue Developer Area → Authentication, revoke access at fanvue.com/settings/account/third-party-apps, then click Reconnect Fanvue.'}
                  </NoteBlock>
                )}
                <ModelSelect
                  label={lang === 'ru' ? 'ПЕРСОНАЖ' : 'CHARACTER'}
                  value={form.modelId}
                  options={modelOptions}
                  lang={lang}
                  onChange={(e) => setForm({ modelId: e.target.value })}
                  style={{ gridColumn: '1 / -1' }}
                />
              </>
            )}
            {data.id === 'ig' && (
              <>
                {!instagramOAuthReady && (
                  <NoteBlock style={{ gridColumn: '1 / -1' }}>
                    {lang === 'ru'
                      ? 'OAuth Instagram недоступен на сервере — нужны INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET и INSTAGRAM_WEBHOOK_VERIFY_TOKEN.'
                      : 'Instagram OAuth is not configured on the server.'}
                  </NoteBlock>
                )}
                {instagramConnected && (
                  <NoteBlock style={{ gridColumn: '1 / -1', borderColor: 'rgba(74,222,128,.35)', background: 'rgba(74,222,128,.08)' }}>
                    {canAddMore
                      ? (lang === 'ru'
                        ? 'Можно добавить ещё один Instagram или переподключить существующий из списка.'
                        : 'You can add another Instagram account or reconnect an existing one from the list.')
                      : (lang === 'ru'
                        ? 'Достигнут лимит подключений Instagram на вашем тарифе.'
                        : 'Instagram connection limit reached for your plan.')}
                  </NoteBlock>
                )}
                <ModelSelect
                  label={lang === 'ru' ? 'ПЕРСОНАЖ' : 'CHARACTER'}
                  value={form.modelId}
                  options={modelOptions}
                  lang={lang}
                  onChange={(e) => setForm({ modelId: e.target.value })}
                  style={{ gridColumn: '1 / -1' }}
                />
              </>
            )}
            {data.id === 'tribute' && (
              <>
                <Field label="TRIBUTE API KEY" value={form.apiKey} onChange={(e) => setForm({ apiKey: e.target.value })} style={{ gridColumn: '1 / -1' }} />
                <Field label={lang === 'ru' ? 'МЕТКА' : 'LABEL'} value={form.label} onChange={(e) => setForm({ label: e.target.value })} />
                <ModelSelect
                  label={lang === 'ru' ? 'ПЕРСОНАЖ' : 'CHARACTER'}
                  value={form.modelId}
                  options={modelOptions}
                  lang={lang}
                  onChange={(e) => setForm({ modelId: e.target.value })}
                />
              </>
            )}
            {['wavespeed', 'tg', 'tg-user', 'fanvue', 'ig', 'tribute'].includes(data.id) ? null : cfs.fields.map((f, i) => {
              const wrap = f.half ? undefined : { gridColumn: '1 / -1' };
              if (f.kind === 'text') {
                return <Field key={i} label={f.lbl} value={f.val} placeholder={f.ph} style={wrap} />;
              }
              if (f.kind === 'select') {
                return <SelectBox key={i} label={f.lbl} value={f.val} style={wrap} />;
              }
              if (f.kind === 'toggle') {
                return (
                  <div key={i} style={{ ...wrap, display: 'flex', flexDirection: 'column' }}>
                    <div
                      style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        background: color.bgPanel, border: `1px solid ${line.hair}`,
                        borderRadius: 10, padding: '10px 12px',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 700, fontSize: 12 }}>{f.lbl}</div>
                        <div style={{ fontSize: 10, color: color.textMuted }}>{f.sub}</div>
                      </div>
                      <Toggle on={f.on} />
                    </div>
                  </div>
                );
              }
              return (
                <div key={i} style={{ ...wrap, display: 'flex', flexDirection: 'column' }}>
                  <NoteBlock>{f.text}</NoteBlock>
                </div>
              );
            })}
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            <Hoverable
              style={{
                flex: 1, textAlign: 'center', borderRadius: 9, padding: 10, fontSize: 12,
                fontWeight: 800, cursor: 'pointer',
                ...(cfs.disabled
                  ? { background: 'rgba(255,255,255,.06)', color: color.textGhost }
                  : { background: 'linear-gradient(120deg,#C084FC,#F0A8C8)', color: color.purpleInk }),
              }}
              hover={
                disabled
                || saving
                || (data.id === 'fanvue' && !fanvueOAuthReady)
                || (data.id === 'ig' && !instagramOAuthReady)
                || (data.id === 'tg-user' && !ig?.telegram_user_available)
                || ((data.id === 'ig' || data.id === 'fanvue') && !canAddMore && !isReconnectMode && list.length > 0)
                  ? {}
                  : { filter: 'brightness(1.08)' }
              }
              onClick={
                disabled
                || saving
                || (data.id === 'fanvue' && !fanvueOAuthReady)
                || (data.id === 'ig' && !instagramOAuthReady)
                || (data.id === 'tg-user' && !ig?.telegram_user_available)
                || ((data.id === 'ig' || data.id === 'fanvue') && !canAddMore && !isReconnectMode && list.length > 0)
                  ? undefined
                  : () => void handleSave()
              }
            >
              {saving
                ? (lang === 'ru' ? 'Сохранение…' : 'Saving…')
                : data.id === 'tg-user'
                ? ((form.tgUserStep || 'phone') === 'password'
                  ? (lang === 'ru' ? 'Подтвердить пароль' : 'Confirm password')
                  : (form.tgUserStep || 'phone') === 'code'
                  ? (lang === 'ru' ? 'Подтвердить код' : 'Confirm code')
                  : (form.reconnectConnectionId
                    ? (lang === 'ru' ? 'Переподключить аккаунт' : 'Reconnect account')
                    : (lang === 'ru' ? 'Отправить код' : 'Send code')))
                : data.id === 'fanvue'
                ? (isReconnectMode
                  ? (lang === 'ru' ? 'Переподключить Fanvue' : 'Reconnect Fanvue')
                  : (fanvueConnected && canAddMore
                    ? (lang === 'ru' ? 'Добавить Fanvue' : 'Add Fanvue account')
                    : (lang === 'ru' ? 'OAuth Fanvue' : 'Fanvue OAuth')))
                : data.id === 'ig'
                ? (isReconnectMode
                  ? (lang === 'ru' ? 'Переподключить Instagram' : 'Reconnect Instagram')
                  : (instagramConnected && canAddMore
                    ? (lang === 'ru' ? 'Добавить Instagram' : 'Add Instagram account')
                    : (lang === 'ru' ? 'Подключить Instagram' : 'Connect Instagram')))
                : data.id === 'tg' && isReconnectMode
                ? (lang === 'ru' ? 'Обновить токен бота' : 'Update bot token')
                : cfs.prim}
            </Hoverable>
            {hasCopy && (
              <Hoverable
                style={{
                  display: 'flex', alignItems: 'center', gap: 6, border: `1px solid ${line.mid}`,
                  borderRadius: 9, padding: '9px 12px', fontSize: 12,
                  fontWeight: 700, color: color.textDim, cursor: 'pointer',
                }}
                hover={{ borderColor: borderHoverOff }}
                onClick={handleCopyWebhook}
              >
                <span style={{ display: 'flex', width: 13, height: 13 }}><IcoCopy /></span>
                {t.copy}
              </Hoverable>
            )}
          </div>
        </Panel>

        {/* help */}
        <Panel style={{ padding: 18 }}>
          <div style={{ fontWeight: 800, fontSize: 13.5, marginBottom: 10 }}>{t.howItWorks}</div>
          <div style={{ fontSize: 12, color: color.textDim, lineHeight: 1.65 }}>{data.help}</div>
          <div style={{ marginTop: 12 }}>
            <a href="#wiki" style={{ fontSize: 12, fontWeight: 700 }}>{t.wikiGuide} →</a>
          </div>
        </Panel>
      </div>
    </div>
  );
}

export default function Connections() {
  const { s } = useApp();
  return (
    <Fade data-screen-label="Подключения">
      {s.connDetail ? <ConnectionDetail /> : <ConnectionList />}
    </Fade>
  );
}

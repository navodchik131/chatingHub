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
import { goToAdmin } from '../../marketing/workspaceEntry';

const connIcons = { tg: IcoTg, wave: IcoWave, heart: IcoHeart, gift: IcoGift, cam: IcoCam, bell: IcoBell };

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

  const form = s.connForms?.[data.id] || { token: '', apiKey: '', label: '', modelId: modelOptions[0]?.id || '' };
  const setForm = (patch) =>
    setS({ connForms: { ...s.connForms, [data.id]: { ...form, ...patch } } });

  const current = mapIntegrationCurrent(data.id, ig, cabinet.models, lang);
  const list = mapIntegrationConnections(data.id, ig, cabinet.models, lang);

  const handleSave = () => {
    if (data.id === 'wavespeed') {
      if (!form.apiKey?.trim()) return;
      void cabinet.saveIntegration('wavespeed', { apiKey: form.apiKey.trim() });
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
      void cabinet.saveIntegration('tg', { token, modelId: form.modelId });
    } else if (data.id === 'fanvue') {
      void cabinet.saveIntegration('fanvue', { modelId: form.modelId });
    } else if (data.id === 'tribute') {
      if (!form.apiKey?.trim()) return;
      void cabinet.saveIntegration('tribute', {
        apiKey: form.apiKey.trim(),
        label: form.label?.trim(),
        modelId: form.modelId,
      });
    }
  };

  const handleDisconnect = (connectionId) => {
    const ok = window.confirm(
      lang === 'ru' ? 'Отключить это подключение?' : 'Disconnect this connection?',
    );
    if (!ok) return;
    void cabinet.disconnectIntegration(data.id, connectionId);
  };

  const hasCopy = ['fanvue', 'tribute'].includes(data.id);
  const Icon = connIcons[data.icon];
  const disabled = data.id === 'ig' || data.id === 'push';
  const fanvueOAuthReady = ig?.fanvue_oauth_available !== false;
  const fanvueConnected = Boolean(ig?.fanvue_oauth_connected);

  const webhookCopyUrl = () => {
    if (data.id === 'fanvue') {
      return ig?.fanvue_webhook_url || ig?.fanvue_connections?.[0]?.webhook_url || null;
    }
    if (data.id === 'tribute') {
      return ig?.tribute_connections?.[0]?.webhook_url || null;
    }
    return null;
  };

  const handleCopyWebhook = () => {
    const url = webhookCopyUrl();
    if (url) void copyText(url);
  };

  return (
    <div>
      <BackLink onClick={() => setS({ connDetail: null, connFlash: null })}>{t.allConnections}</BackLink>

      {s.connFlash && data.id === 'fanvue' && (
        <NoteBlock
          style={{
            marginBottom: 12,
            ...(s.connFlash === 'ok'
              ? { borderColor: 'rgba(74,222,128,.35)', background: 'rgba(74,222,128,.08)' }
              : { borderColor: 'rgba(248,113,113,.35)', background: 'rgba(248,113,113,.08)' }),
          }}
        >
          {s.connFlash === 'ok'
            ? (lang === 'ru' ? 'Fanvue подключён.' : 'Fanvue connected.')
            : (lang === 'ru' ? 'Не удалось подключить Fanvue.' : 'Fanvue connection failed.')}
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

          {current.length > 0 && (
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
                  <span style={{ width: 7, height: 7, borderRadius: '50%', background: color.green, flex: 'none' }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 700, fontSize: 12 }}>{cl.name}</div>
                    <div style={{ fontSize: 10, color: color.textMuted }}>{cl.meta}</div>
                  </div>
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
                    {lang === 'ru' ? 'Fanvue уже подключён. Можно переподключить аккаунт.' : 'Fanvue is connected. You can reconnect the account.'}
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
            {['wavespeed', 'tg', 'fanvue', 'tribute'].includes(data.id) ? null : cfs.fields.map((f, i) => {
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
              hover={disabled || (data.id === 'fanvue' && !fanvueOAuthReady) ? {} : { filter: 'brightness(1.08)' }}
              onClick={disabled || (data.id === 'fanvue' && !fanvueOAuthReady) ? undefined : handleSave}
            >
              {data.id === 'fanvue'
                ? (fanvueConnected
                  ? (lang === 'ru' ? 'Переподключить Fanvue' : 'Reconnect Fanvue')
                  : (lang === 'ru' ? 'OAuth Fanvue' : 'Fanvue OAuth'))
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

/**
 * Синхронизация макета + патчи для API-моста (не трогаем исходник в «Доработка дизайна»).
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const repo = path.resolve(here, '../..')
const srcDir = path.join(repo, 'Доработка дизайна')
const osRoot = path.resolve(here, '..')
const BUILD_STAMP = process.env.BUILD_STAMP || Date.now().toString(36)

const files = [
  ['ModelMate OS.dc.html', 'index.html'],
  ['ModelMate OS.dc.html', path.join('design', 'ModelMate OS.dc.html')],
  ['support.js', path.join('public', 'support.js')],
  ['support.js', path.join('design', 'support.js')],
]

for (const [fromName, toRel] of files) {
  const from = path.join(srcDir, fromName)
  const to = path.join(osRoot, toRel)
  if (!fs.existsSync(from)) {
    console.error('missing', from)
    process.exit(1)
  }
  fs.mkdirSync(path.dirname(to), { recursive: true })
  fs.copyFileSync(from, to)
  console.log('synced', fromName, '→', toRel)
}

const AUTH_OVERLAY = `
<div id="mm-os-auth" class="mm-os-auth" style="display:none">
  <form id="mm-os-auth-form" class="mm-os-auth-card">
    <h1>ModelMate OS</h1>
    <p id="mm-os-auth-subtitle">Войдите или зарегистрируйтесь — тем же аккаунтом, что и в основном кабинете.</p>
    <div id="mm-os-auth-referral" class="mm-os-auth-referral" style="display:none"></div>
    <div class="mm-os-auth-tabs" role="tablist" aria-label="Авторизация">
      <button type="button" id="mm-os-auth-tab-login" class="mm-os-auth-tab is-active" data-auth-tab="login">Вход</button>
      <button type="button" id="mm-os-auth-tab-register" class="mm-os-auth-tab" data-auth-tab="register">Регистрация</button>
    </div>
    <div id="mm-os-auth-telegram" class="mm-os-auth-telegram" style="display:none">
      <div id="mm-os-auth-telegram-host" class="mm-os-auth-telegram-host"></div>
      <div id="mm-os-auth-telegram-busy" class="mm-os-auth-telegram-busy" style="display:none">Проверяем Telegram…</div>
    </div>
    <div id="mm-os-auth-or-email" class="mm-os-auth-divider" style="display:none">или email</div>
    <div id="mm-os-auth-credentials">
    <label for="mm-os-auth-email">Email</label>
    <input id="mm-os-auth-email" type="email" autocomplete="email" required>
    <label for="mm-os-auth-pass">Пароль</label>
    <input id="mm-os-auth-pass" type="password" autocomplete="current-password" required>
    <div id="mm-os-auth-member-wrap" class="mm-os-auth-member">
      <label for="mm-os-auth-member">Логин оператора (необязательно)</label>
      <input id="mm-os-auth-member" type="text" autocomplete="username">
    </div>
    <button id="mm-os-auth-submit" type="submit" class="mm-os-auth-submit">Войти</button>
    <p class="mm-os-auth-hint">Пароль — минимум 8 символов.</p>
    </div>
    <div id="mm-os-auth-err" class="mm-os-auth-err"></div>
    <div id="mm-os-auth-email-complete" class="mm-os-auth-email-complete">
      <p style="margin:0 0 12px;font-size:13px;color:#9BA0A6;line-height:1.5;">Вы вошли через Telegram. Укажите email и пароль для входа без Telegram и оплат.</p>
      <label for="mm-os-auth-complete-email">Email</label>
      <input id="mm-os-auth-complete-email" type="email" autocomplete="email">
      <label for="mm-os-auth-complete-pass">Пароль</label>
      <input id="mm-os-auth-complete-pass" type="password" autocomplete="new-password">
      <button type="button" id="mm-os-auth-complete-submit" class="mm-os-auth-submit" style="margin-top:14px;">Сохранить email</button>
    </div>
  </form>
</div>`

/** Подстановки в шаблон: хардкод макета → биндинги API */
const TEMPLATE_PATCHES = [
  [
    /<meta name="viewport" content="width=device-width, initial-scale=1">/,
    `<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="./favicon.ico" type="image/x-icon">`,
  ],
  [
    /<script src="\.\/support\.js"><\/script>/,
    `<link rel="stylesheet" href="./mm-os-auth.css">
<script src="./mm-os-api.js?v=${BUILD_STAMP}"></script>
<script src="./mm-os-telegram-login.js?v=${BUILD_STAMP}"></script>
<script src="./mm-os-studio-scenarios.js?v=${BUILD_STAMP}"></script>
<script src="./mm-os-bridge.js?v=${BUILD_STAMP}"></script>
<script src="./mm-os-api-full.js?v=${BUILD_STAMP}"></script>
<script src="./support.js?v=${BUILD_STAMP}"></script>`,
  ],
  [
    /<body>/,
    `<body>${AUTH_OVERLAY}`,
  ],
  [
    /<\/sc-if>\s*\n\s*<!-- content scroll -->/,
    `</sc-if>

    <sc-if value="{{ hasDonationAlert }}" hint-placeholder-val="{{ false }}">
      <div style="flex:none;margin:12px 16px 0;padding:14px 16px;border-radius:14px;background:linear-gradient(120deg,rgba(74,222,128,.12),rgba(240,168,200,.06));border:1px solid rgba(74,222,128,.35);display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;">
        <div>
          <div style="font-weight:800;font-size:14px;margin-bottom:4px;">{{ donationAlertTitle }}</div>
          <div style="font-size:12.5px;color:#9BA0A6;">{{ donationAlertBody }}</div>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <div onClick="{{ openDonationAlert }}" style="background:#D7F452;color:#171A05;font-weight:800;font-size:12.5px;border-radius:9px;padding:8px 14px;cursor:pointer;" style-hover="filter:brightness(1.06);">{{ t.donationAlertOpen }}</div>
          <div onClick="{{ dismissDonationAlert }}" style="border:1px solid rgba(255,255,255,.14);color:#9BA0A6;font-weight:700;font-size:12.5px;border-radius:9px;padding:8px 14px;cursor:pointer;" style-hover="border-color:rgba(255,255,255,.3);">{{ t.donationAlertDismiss }}</div>
        </div>
      </div>
    </sc-if>

    <!-- content scroll -->`,
  ],
  // кредиты в сайдбаре и mobile
  [
    /line-height:1\.1;">510<\/div>/,
    'line-height:1.1;">{{ creditsBalance }}</div>',
  ],
  [
    /font-size:11px;font-weight:600;color:#D7F452;">510<\/span>/,
    'font-size:11px;font-weight:600;color:#D7F452;">{{ creditsBalance }}</span>',
  ],
  [
    /font-size:26px;color:#D7F452;">510<\/div>/,
    'font-size:26px;color:#D7F452;">{{ creditsBalance }}</div>',
  ],
  [
    />utochkinrenat@g…<\/div>/,
    '>{{ userEmailShort }}</div>',
  ],
  [
    /{{ t\.owner }} · Standard Studio/,
    '{{ userRolePlan }}',
  ],
  [
    /font-family:'Unbounded';font-weight:600;font-size:20px;">100,00 ₽<\/div>/,
    "font-family:'Unbounded';font-weight:600;font-size:20px;\">{{ donationsKpiTotal }}</div>",
  ],
  [
    /{{ t\.toPayout }}: 100,00 ₽ →/,
    '{{ t.toPayout }}: {{ donationsKpiPayout }} →',
  ],
  [
    /{{ t\.allRead }}/,
    '{{ dialogsUnreadLabel }}',
  ],
  [
    /font-family:'Unbounded';font-weight:600;font-size:18px;margin-bottom:6px;">Standard Studio<\/div>/,
    "font-family:'Unbounded';font-weight:600;font-size:18px;margin-bottom:6px;\">{{ planDisplayName }}</div>",
  ],
  [
    /{{ t\.until }} 07\.12\.2026 · {{ t\.balance }}: <b style="color:#D7F452;">510 {{ t\.cr }}<\/b>/,
    '{{ t.until }} {{ planUntil }} · {{ t.balance }}: <b style="color:#D7F452;">{{ creditsBalance }} {{ t.cr }}</b>',
  ],
  // кнопки действий (картинки: triggerGen в макете, логика в bridge)
  [
    /<div style="display:flex;gap:8px;align-items:flex-start;">\s*<div style="flex:1;font-size:13px;line-height:1\.5;">\{\{ m\.text \}<\/div>\s*<span onClick="\{\{ m\.toggleReact \}\}" style="opacity:\.5;font-size:12px;cursor:pointer;flex:none;margin-top:1px;" style-hover="opacity:1;">☺<\/span>\s*<\/div>/,
    `<div style="display:flex;gap:8px;align-items:flex-start;">
                      <div style="flex:1;font-size:13px;line-height:1.5;min-width:0;">
                        <sc-if value="{{ m.imageUrl }}" hint-placeholder-val="{{ false }}">
                          <img src="{{ m.imageUrl }}" alt="" style="{{ m.imageStyle }}" loading="lazy" />
                        </sc-if>
                        <sc-if value="{{ m.text }}" hint-placeholder-val="{{ true }}">
                          <div>{{ m.text }}</div>
                        </sc-if>
                      </div>
                      <span onClick="{{ m.toggleReact }}" style="opacity:.5;font-size:12px;cursor:pointer;flex:none;margin-top:1px;" style-hover="opacity:1;">☺</span>
                    </div>`,
  ],
  [
    /<div style="background:#D7F452;color:#171A05;font-weight:800;font-size:12\.5px;border-radius:10px;padding:10px 16px;cursor:pointer;" style-hover="background:#E8FA8A;">{{ t\.send }}<\/div>/,
    `<div onClick="{{ sendReply }}" style="background:#D7F452;color:#171A05;font-weight:800;font-size:12.5px;border-radius:10px;padding:10px 16px;cursor:pointer;" style-hover="background:#E8FA8A;">{{ t.send }}</div>`,
  ],
  [
    /<div style="flex:1;display:flex;align-items:center;justify-content:center;gap:8px;background:#D7F452;color:#171A05;border-radius:11px;padding:12px;font-size:13px;font-weight:800;cursor:pointer;" style-hover="background:#E8FA8A;"><span style="display:flex;width:16px;height:16px;" dangerouslySetInnerHTML="\{\{ icoDownload \}\}"><\/span>\{\{ t\.download \}\}<\/div>/,
    '<div onClick="{{ downloadLightbox }}" style="flex:1;display:flex;align-items:center;justify-content:center;gap:8px;background:#D7F452;color:#171A05;border-radius:11px;padding:12px;font-size:13px;font-weight:800;cursor:pointer;" style-hover="background:#E8FA8A;"><span style="display:flex;width:16px;height:16px;" dangerouslySetInnerHTML="{{ icoDownload }}"></span>{{ t.download }}</div>',
  ],
  // обзор KPI — убрать хардкод макета
  [
    /font-family:'Unbounded';font-weight:600;font-size:18px;">Standard<\/span>/,
    "font-family:'Unbounded';font-weight:600;font-size:18px;\">{{ planDisplayName }}</span>",
  ],
  [
    /{{ t\.until }} 07\.12\.2026<\/div>/,
    '{{ t.until }} {{ planUntil }}</div>',
  ],
  [
    /font-size:11\.5px;color:#9BA0A6;margin-top:4px;">≈ 51 {{ t\.framesLeft }}<\/div>/,
    'font-size:11.5px;color:#9BA0A6;margin-top:4px;">{{ creditsFramesHint }}</div>',
  ],
  [
    /font-family:'Unbounded';font-weight:600;font-size:20px;">14<\/div>/,
    "font-family:'Unbounded';font-weight:600;font-size:20px;\">{{ dialogsTotal }}</div>",
  ],
  [
    /{{ dialogsUnreadLabel }} · 78 {{ t\.teamReplies }}/,
    '{{ dialogsUnreadLabel }} · {{ teamRepliesCount }} {{ t.teamReplies }}',
  ],
  [
    /<sc-if value="\{\{ isDonOverview \}\}" hint-placeholder-val="\{\{ true \}\}">\s*<div>/,
    `<sc-if value="{{ isDonOverview }}" hint-placeholder-val="{{ true }}">
        <sc-if value="{{ hasDonationsLoadError }}" hint-placeholder-val="{{ false }}">
          <div style="margin-bottom:12px;padding:12px 14px;border-radius:12px;background:rgba(248,113,113,.08);border:1px solid rgba(248,113,113,.35);color:#FCA5A5;font-size:12.5px;line-height:1.5;">{{ donationsLoadError }}</div>
        </sc-if>
        <div>`,
  ],
  // диалоги — шапка треда и заметки
  [
    /<div style="width:34px;height:34px;border-radius:50%;background:linear-gradient\(135deg,#38BDF8,#818CF8\);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:13px;color:#0A1526;">d<\/div>/,
    `<div style="width:34px;height:34px;border-radius:50%;background:{{ activeChat.avStyle }};display:flex;align-items:center;justify-content:center;font-weight:800;font-size:13px;">{{ activeChat.initial }}</div>`,
  ],
  [
    /<span style="font-weight:800;font-size:14px;">duty<\/span>/,
    '<span style="font-weight:800;font-size:14px;">{{ activeChat.name }}</span>',
  ],
  [
    /Telegram · {{ t\.persona }}: <span style="color:#F0A8C8;font-weight:700;">Mia<\/span> · {{ t\.replyLang }}: Español/,
    '{{ activeChat.platform }} · {{ t.persona }}: <span style="color:#F0A8C8;font-weight:700;">{{ activeChat.persona }}</span> · {{ t.replyLang }}: {{ activeChat.lang }}',
  ],
  [
    /{{ t\.fanNotes }} · duty<\/div>/,
    '{{ notesTitle }}</div>',
  ],
  [
    /<div style="font-family:'Unbounded';font-weight:600;font-size:20px;">Mia<\/div>/,
    `<div style="font-family:'Unbounded';font-weight:600;font-size:20px;">{{ activeCharName }}</div>`,
  ],
  [
    /<span style="\{\{ cc\.style \}\}" style-hover="border-color:rgba\(255,255,255,.3\);">\{\{ cc\.label \}\}<\/span>/g,
    '<span onClick="{{ cc.pick }}" style="{{ cc.style }}" style-hover="border-color:rgba(255,255,255,.3);">{{ cc.label }}</span>',
  ],
  [
    /<div style="flex:1;aspect-ratio:3\/4;border:1\.5px dashed rgba\(255,255,255,.18\);border-radius:12px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;cursor:pointer;" style-hover="border-color:rgba\(215,244,82,.5\);background:rgba\(215,244,82,.03\);">\s*<span style="display:flex;width:20px;height:20px;color:#6B7076;" dangerouslySetInnerHTML="\{\{ icoUpload \}\}"><\/span>/g,
    `<div data-mm-upload="ref" style="flex:1;aspect-ratio:3/4;border:1.5px dashed rgba(255,255,255,.18);border-radius:12px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;cursor:pointer;" style-hover="border-color:rgba(215,244,82,.5);background:rgba(215,244,82,.03);">
                  <span style="display:flex;width:20px;height:20px;color:#6B7076;" dangerouslySetInnerHTML="{{ icoUpload }}"></span>`,
  ],
  [
    /<div style="border:1\.5px dashed rgba\(255,255,255,.18\);border-radius:12px;padding:20px;display:flex;flex-direction:column;align-items:center;gap:8px;cursor:pointer;" style-hover="border-color:rgba\(215,244,82,.5\);background:rgba\(215,244,82,.03\);">\s*<span style="display:flex;width:22px;height:22px;color:#6B7076;" dangerouslySetInnerHTML="\{\{ icoFilm \}\}"><\/span>/,
    `<div data-mm-upload="motion-video" style="border:1.5px dashed rgba(255,255,255,.18);border-radius:12px;padding:20px;display:flex;flex-direction:column;align-items:center;gap:8px;cursor:pointer;" style-hover="border-color:rgba(215,244,82,.5);background:rgba(215,244,82,.03);">
                <span style="display:flex;width:22px;height:22px;color:#6B7076;" dangerouslySetInnerHTML="{{ icoFilm }}"></span>`,
  ],
  [
    /<div style="width:70px;aspect-ratio:9\/16;border:1\.5px dashed rgba\(255,255,255,.18\);border-radius:10px;display:flex;align-items:center;justify-content:center;cursor:pointer;flex:none;" style-hover="border-color:rgba\(215,244,82,.5\);">\s*<span style="display:flex;width:18px;height:18px;color:#6B7076;" dangerouslySetInnerHTML="\{\{ icoUpload \}\}"><\/span>/,
    `<div data-mm-upload="motion-frame" style="width:70px;aspect-ratio:9/16;border:1.5px dashed rgba(255,255,255,.18);border-radius:10px;display:flex;align-items:center;justify-content:center;cursor:pointer;flex:none;" style-hover="border-color:rgba(215,244,82,.5);">
                  <span style="display:flex;width:18px;height:18px;color:#6B7076;" dangerouslySetInnerHTML="{{ icoUpload }}"></span>`,
  ],
  // персонажи — API: фото, описание, кнопки
  [
    /<div style="display:flex;align-items:center;gap:8px;background:#D7F452;color:#171A05;font-weight:800;font-size:13px;border-radius:10px;padding:10px 16px;cursor:pointer;" style-hover="background:#E8FA8A;">\+ \{\{ t\.newCharacter \}\}<\/div>/,
    `<div data-mm-char-new style="display:flex;align-items:center;gap:8px;background:#D7F452;color:#171A05;font-weight:800;font-size:13px;border-radius:10px;padding:10px 16px;cursor:pointer;" style-hover="background:#E8FA8A;">+ {{ t.newCharacter }}</div>`,
  ],
  [
    /<div style="width:52px;height:52px;border-radius:16px;background:linear-gradient\(135deg,#F472B6,#C084FC\);display:flex;align-items:center;justify-content:center;font-family:'Unbounded';font-weight:600;font-size:20px;color:#2A0A1C;">M<\/div>/,
    `<div style="width:52px;height:52px;border-radius:16px;background:linear-gradient(135deg,#F472B6,#C084FC);display:flex;align-items:center;justify-content:center;font-family:'Unbounded';font-weight:600;font-size:20px;color:#2A0A1C;">{{ activeCharInitial }}</div>`,
  ],
  [
    /<div style="aspect-ratio:3\/4;border:1\.5px dashed rgba\(255,255,255,.18\);border-radius:10px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;color:#6B7076;cursor:pointer;" style-hover="border-color:rgba\(215,244,82,.5\);">\s*<span style="display:flex;width:18px;height:18px;" dangerouslySetInnerHTML="\{\{ icoUpload \}\}"><\/span>/,
    `<div data-mm-upload="char-photo" style="aspect-ratio:3/4;border:1.5px dashed rgba(255,255,255,.18);border-radius:10px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;color:#6B7076;cursor:pointer;" style-hover="border-color:rgba(215,244,82,.5);">
                  <span style="display:flex;width:18px;height:18px;" dangerouslySetInnerHTML="{{ icoUpload }}"></span>`,
  ],
  [
    /<textarea rows="6" style="width:100%;background:#0D0E11;border:1px solid rgba\(255,255,255,.09\);border-radius:10px;padding:10px 12px;color:#C9CDD1;font-family:'Manrope';font-size:12px;line-height:1.55;resize:vertical;outline:none;">Slim athletic feminine body[^<]*<\/textarea>/,
    `<textarea data-mm-char-profile rows="6" placeholder="{{ t.charAppearance }}" style="width:100%;background:#0D0E11;border:1px solid rgba(255,255,255,.09);border-radius:10px;padding:10px 12px;color:#C9CDD1;font-family:'Manrope';font-size:12px;line-height:1.55;resize:vertical;outline:none;"></textarea>`,
  ],
  [
    /<span style="\{\{ ct\.style \}\}" style-hover="border-color:rgba\(255,255,255,.3\);">\{\{ ct\.label \}\}<\/span>/g,
    '<span onClick="{{ ct.pick }}" style="{{ ct.style }}" style-hover="border-color:rgba(255,255,255,.3);">{{ ct.label }}</span>',
  ],
  [
    /<div style="\{\{ tm\.style \}\}" style-hover="background:rgba\(255,255,255,.08\);">\{\{ tm\.label \}\}<\/div>/g,
    '<div onClick="{{ tm.pick }}" style="{{ tm.style }}" style-hover="background:rgba(255,255,255,.08);">{{ tm.label }}</div>',
  ],
  [
    /<div style="\{\{ cp\.bg \}\}flex-direction:column;align-items:stretch;justify-content:space-between;">/,
    '<div style="{{ cp.cardStyle }}">',
  ],
  [
    /<div onClick="\{\{ cp\.open \}\}" style="margin-top:auto;font-size:10\.5px;font-weight:800;color:#F87171;/,
    '<div onClick="{{ cp.deletePhoto }}" style="margin-top:auto;font-size:10.5px;font-weight:800;color:#F87171;',
  ],
  [
    /<input placeholder="\{\{ t\.opLoginPh \}\}" style="\{\{ inputSt \}\}">/,
    '<input data-mm-op-login placeholder="{{ t.opLoginPh }}" style="{{ inputSt }}">',
  ],
  [
    /<input type="password" value="" style="\{\{ inputSt \}\}">/,
    '<input data-mm-op-pass type="password" autocomplete="new-password" style="{{ inputSt }}">',
  ],
  [
    /<div style="width:120px;"><div style="\{\{ fieldLbl \}\}">\{\{ t\.opTribute \}\}<\/div><input value="15" style="\{\{ inputSt \}\}"><\/div>/,
    '<div style="width:120px;"><div style="{{ fieldLbl }}">{{ t.opTribute }}</div><input data-mm-op-tribute value="20" style="{{ inputSt }}"></div>',
  ],
  [
    /<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;background:#0D0E11;border:1px solid rgba\(255,255,255,.07\);border-radius:10px;padding:10px 12px;cursor:pointer;" style-hover="border-color:rgba\(255,255,255,.2\);">\s*<span style="font-family:'JetBrains Mono';font-size:11px;letter-spacing:\.5px;">\{\{ om\.name \}\}<\/span>/g,
    '<div onClick="{{ om.toggle }}" style="display:flex;align-items:center;justify-content:space-between;gap:10px;background:#0D0E11;border:1px solid rgba(255,255,255,.07);border-radius:10px;padding:10px 12px;cursor:pointer;" style-hover="border-color:rgba(255,255,255,.2);"><span style="font-family:\'JetBrains Mono\';font-size:11px;letter-spacing:.5px;">{{ om.name }}</span>',
  ],
  [
    /<div style="flex:1;display:flex;align-items:center;justify-content:center;gap:8px;background:rgba\(192,132,252,.12\);border:1px solid rgba\(192,132,252,.4\);color:#C084FC;border-radius:11px;padding:12px;font-size:13px;font-weight:800;cursor:pointer;" style-hover="background:rgba\(192,132,252,.2\);"><span style="display:flex;width:16px;height:16px;" dangerouslySetInnerHTML="\{\{ icoGrid2 \}\}"><\/span>\{\{ t\.makeCarousel \}\}<\/div>/,
    '<div onClick="{{ makeCarousel }}" style="flex:1;display:flex;align-items:center;justify-content:center;gap:8px;background:rgba(192,132,252,.12);border:1px solid rgba(192,132,252,.4);color:#C084FC;border-radius:11px;padding:12px;font-size:13px;font-weight:800;cursor:pointer;" style-hover="background:rgba(192,132,252,.2);"><span style="display:flex;width:16px;height:16px;" dangerouslySetInnerHTML="{{ icoGrid2 }}"></span>{{ t.makeCarousel }}</div>',
  ],
  [
    /<div style="\{\{ ffImgStyle \}\}display:flex;align-items:center;justify-content:center;animation:mmPulse 1\.2s ease-in-out infinite;">/,
    '<div style="{{ ffImgStyleLoading }}">',
  ],
  [
    /<div style="\{\{ ffImgStyle \}\}display:flex;align-items:flex-end;padding:6px;">\s*<span style="font-family:'JetBrains Mono';font-size:7\.5px;background:rgba\(0,0,0,.6\);color:#fff;padding:2px 6px;border-radius:4px;">Mia · 9:16<\/span>/,
    '<div style="{{ ffImgStyleDone }}"><span style="font-family:\'JetBrains Mono\';font-size:7.5px;background:rgba(0,0,0,.6);color:#fff;padding:2px 6px;border-radius:4px;">{{ ffThumbLabel }}</span>',
  ],
  [
    /<div style="\{\{ lightboxData\.big \}\}min-height:0;display:flex;align-items:center;justify-content:center;overflow:hidden(?:;position:relative)?;">\s*<sc-if value="\{\{ lightboxData\.hasImage \}\}" hint-placeholder-val="\{\{ false \}\}">\s*<img src="\{\{ lightboxData\.url \}\}"[^>]*>\s*<\/sc-if>\s*<sc-if value="\{\{ lightboxData\.showPlaceholder \}\}" hint-placeholder-val="\{\{ true \}\}">\s*<span style="display:flex;width:48px;height:48px;color:rgba\(255,255,255,\.25\);" dangerouslySetInnerHTML="\{\{ icoImage \}\}"><\/span>\s*<\/sc-if>\s*<\/div>/,
    `<div style="{{ lightboxData.big }}min-height:0;display:flex;align-items:center;justify-content:center;overflow:hidden;position:relative;">
            <sc-if value="{{ lightboxData.hasImage }}" hint-placeholder-val="{{ false }}">
              <img src="{{ lightboxData.url }}" alt="" style="width:100%;height:100%;max-height:min(calc(92vh - 200px),640px);object-fit:contain;display:block;" />
            </sc-if>
            <sc-if value="{{ lightboxData.failed }}" hint-placeholder-val="{{ false }}">
              <span style="{{ lightboxData.failedWrap }}"><span style="{{ lightboxData.failedBadgeStyle }}">{{ lightboxData.failedBadge }}</span><span style="{{ lightboxData.failedStyle }}">{{ lightboxData.failedLabel }}</span></span>
            </sc-if>
            <sc-if value="{{ lightboxData.showPlaceholder }}" hint-placeholder-val="{{ true }}">
              <span style="display:flex;width:48px;height:48px;color:rgba(255,255,255,.25);" dangerouslySetInnerHTML="{{ icoImage }}"></span>
            </sc-if>
          </div>`,
  ],
  [
    /<div onClick="\{\{ stop \}\}" style="display:flex;flex-direction:column;gap:14px;max-height:92vh;max-width:min\(92vw,720px\);">/,
    '<div onClick="{{ stop }}" style="{{ lightboxData.cardStyle }}">',
  ],
  [
    /<div style="display:flex;gap:10px;">\s*<div style="flex:1;display:flex;align-items:center;justify-content:center;gap:8px;background:#D7F452;color:#171A05;border-radius:11px;padding:12px;font-size:13px;font-weight:800;cursor:pointer;" style-hover="background:#E8FA8A;"><span style="display:flex;width:16px;height:16px;" dangerouslySetInnerHTML="\{\{ icoDownload \}\}"><\/span>\{\{ t\.download \}<\/div>\s*<div style="flex:1;display:flex;align-items:center;justify-content:center;gap:8px;background:rgba\(192,132,252,\.12\);border:1px solid rgba\(192,132,252,\.4\);color:#C084FC;border-radius:11px;padding:12px;font-size:13px;font-weight:800;cursor:pointer;" style-hover="background:rgba\(192,132,252,\.2\);"><span style="display:flex;width:16px;height:16px;" dangerouslySetInnerHTML="\{\{ icoGrid2 \}\}"><\/span>\{\{ t\.makeCarousel \}<\/div>\s*<\/div>/,
    `<sc-if value="{{ lightboxData.showActions }}" hint-placeholder-val="{{ true }}">
          <div style="{{ lightboxData.actionsStyle }}"><div onClick="{{ downloadLightbox }}" style="flex:1;display:flex;align-items:center;justify-content:center;gap:8px;background:#D7F452;color:#171A05;border-radius:11px;padding:12px;font-size:13px;font-weight:800;cursor:pointer;" style-hover="background:#E8FA8A;"><span style="display:flex;width:16px;height:16px;" dangerouslySetInnerHTML="{{ icoDownload }}"></span>{{ t.download }}</div>
            <div onClick="{{ makeCarousel }}" style="flex:1;display:flex;align-items:center;justify-content:center;gap:8px;background:rgba(192,132,252,.12);border:1px solid rgba(192,132,252,.4);color:#C084FC;border-radius:11px;padding:12px;font-size:13px;font-weight:800;cursor:pointer;" style-hover="background:rgba(192,132,252,.2);"><span style="display:flex;width:16px;height:16px;" dangerouslySetInnerHTML="{{ icoGrid2 }}"></span>{{ t.makeCarousel }}</div>
          </div>
          </sc-if>`,
  ],
  [
    /<div onClick="\{\{ af\.open \}\}" style="border-radius:12px;overflow:hidden;background:#121316;border:1px solid rgba\(255,255,255,\.07\);cursor:pointer;" style-hover="border-color:rgba\(215,244,82,\.4\);">\s*<div style="\{\{ af\.bg \}\}position:relative;" style-hover="filter:brightness\(1\.08\);">\s*<span style="display:flex;width:22px;height:22px;color:rgba\(255,255,255,\.35\);" dangerouslySetInnerHTML="\{\{ icoImage \}\}"><\/span>\s*<span style="position:absolute;top:7px;right:7px;display:flex;width:15px;height:15px;color:rgba\(255,255,255,\.7\);background:rgba\(0,0,0,\.4\);border-radius:6px;padding:3px;" dangerouslySetInnerHTML="\{\{ icoZoom \}\}"><\/span>\s*<\/div>\s*<div style="padding:8px 10px;">\s*<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px;"><span style="font-weight:700;font-size:11px;">\{\{ af\.who \}\}<\/span><span style="font-family:'JetBrains Mono';font-size:8\.5px;color:#5C6066;">\{\{ af\.ratio \}\}<\/span><\/div>\s*<div style="display:flex;gap:8px;"><span style="font-size:10px;font-weight:700;color:#C084FC;cursor:pointer;">→ \{\{ t\.toVideo \}\}<\/span><span style="font-size:10px;font-weight:700;color:#9BA0A6;cursor:pointer;">↓<\/span><\/div>\s*<\/div>\s*<\/div>/,
    `<div onClick="{{ af.open }}" style="{{ af.cardStyle }}" style-hover="{{ af.cardHover }}">
                  <div style="{{ af.bg }}" style-hover="{{ af.pending || af.failed ? '' : 'filter:brightness(1.08);' }}">
                    <sc-if value="{{ af.pending }}" hint-placeholder-val="{{ false }}">
                      <span style="{{ af.spinnerWrap }}"><span style="{{ af.spinnerStyle }}"></span></span>
                    </sc-if>
                    <sc-if value="{{ af.failed }}" hint-placeholder-val="{{ false }}">
                      <span style="{{ af.failedWrap }}"><span style="{{ af.failedBadgeStyle }}">{{ af.failedBadge }}</span><span style="{{ af.failedStyle }}">{{ af.failedLabel }}</span></span>
                    </sc-if>
                    <sc-if value="{{ af.showPlaceholder }}" hint-placeholder-val="{{ true }}">
                    <span style="display:flex;width:22px;height:22px;color:rgba(255,255,255,.35);" dangerouslySetInnerHTML="{{ icoImage }}"></span>
                    </sc-if>
                    <sc-if value="{{ af.showActions }}" hint-placeholder-val="{{ true }}">
                    <span style="position:absolute;top:7px;right:7px;display:flex;width:15px;height:15px;color:rgba(255,255,255,.7);background:rgba(0,0,0,.4);border-radius:6px;padding:3px;" dangerouslySetInnerHTML="{{ icoZoom }}"></span>
                    </sc-if>
                  </div>
                  <div style="padding:8px 10px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px;"><span style="font-weight:700;font-size:11px;">{{ af.who }}</span><span style="{{ af.ratioStyle }}">{{ af.ratio }}</span></div>
                    <sc-if value="{{ af.showActions }}" hint-placeholder-val="{{ true }}">
                    <div style="display:flex;gap:8px;"><span style="font-size:10px;font-weight:700;color:#C084FC;cursor:pointer;">→ {{ t.toVideo }}</span><span style="font-size:10px;font-weight:700;color:#9BA0A6;cursor:pointer;">↓</span></div>
                    </sc-if>
                    <sc-if value="{{ af.failed }}" hint-placeholder-val="{{ false }}">
                    <div style="font-size:10px;font-weight:600;color:#F87171;line-height:1.3;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;">{{ af.failedLabel }}</div>
                    </sc-if>
                  </div>
                </div>`,
  ],
  [
    /<span style="font-size:11px;font-weight:700;color:#C084FC;cursor:pointer;" style-hover="color:#D8B4FE;">✦ \{\{ t\.genFromPhoto \}\}<\/span>/,
    `<span data-mm-char-gen-profile style="font-size:11px;font-weight:700;color:#C084FC;cursor:pointer;" style-hover="color:#D8B4FE;">✦ {{ t.genFromPhoto }}</span>`,
  ],
  [
    /<textarea rows="5" style="width:100%;background:#0D0E11;border:1px solid rgba\(255,255,255,.09\);border-radius:10px;padding:10px 12px;color:#C9CDD1;font-family:'Manrope';font-size:12px;line-height:1.55;resize:vertical;outline:none;">Slim athletic feminine body, long dark hair, green eyes, soft natural makeup…<\/textarea>/,
    `<textarea data-mm-char-profile rows="5" placeholder="{{ t.charAppearance }}" style="width:100%;background:#0D0E11;border:1px solid rgba(255,255,255,.09);border-radius:10px;padding:10px 12px;color:#C9CDD1;font-family:'Manrope';font-size:12px;line-height:1.55;resize:vertical;outline:none;"></textarea>`,
  ],
  [
    /<div style="flex:1;background:rgba\(215,244,82,.12\);border:1px solid rgba\(215,244,82,.3\);border-radius:9px;padding:9px;text-align:center;font-size:12px;font-weight:800;color:#D7F452;cursor:pointer;">\{\{ t\.save \}\}<\/div>\s*<div style="border:1px solid rgba\(248,113,113,.3\);border-radius:9px;padding:9px 14px;font-size:12px;font-weight:700;color:#F87171;cursor:pointer;" style-hover="background:rgba\(248,113,113,.08\);">\{\{ t\.delete \}\}<\/div>/,
    `<div data-mm-char-save style="flex:1;background:rgba(215,244,82,.12);border:1px solid rgba(215,244,82,.3);border-radius:9px;padding:9px;text-align:center;font-size:12px;font-weight:800;color:#D7F452;cursor:pointer;">{{ t.save }}</div>
                <div data-mm-char-delete style="border:1px solid rgba(248,113,113,.3);border-radius:9px;padding:9px 14px;font-size:12px;font-weight:700;color:#F87171;cursor:pointer;" style-hover="background:rgba(248,113,113,.08);">{{ t.delete }}</div>`,
  ],
  [
    /<span style="\{\{ pt\.style \}\}" style-hover="border-color:rgba\(255,255,255,.3\);">\{\{ pt\.label \}\}<\/span>/g,
    '<span onClick="{{ pt.pick }}" style="{{ pt.style }}" style-hover="border-color:rgba(255,255,255,.3);">{{ pt.label }}</span>',
  ],
  [
    /<div><div style="font-family:'JetBrains Mono';font-size:8\.5px;letter-spacing:1\.2px;color:#6B7076;margin-bottom:6px;">ВОЗРАСТ<\/div><input value="24" style="width:100%;background:#0D0E11;border:1px solid rgba\(255,255,255,.09\);border-radius:9px;padding:9px 11px;color:#F2F3F0;font-family:'Manrope';font-size:12\.5px;outline:none;"><\/div>/,
    `<div><div style="font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1.2px;color:#6B7076;margin-bottom:6px;">ВОЗРАСТ</div><input data-mm-persona="age" style="width:100%;background:#0D0E11;border:1px solid rgba(255,255,255,.09);border-radius:9px;padding:9px 11px;color:#F2F3F0;font-family:'Manrope';font-size:12.5px;outline:none;"></div>`,
  ],
  [
    /<div><div style="font-family:'JetBrains Mono';font-size:8\.5px;letter-spacing:1\.2px;color:#6B7076;margin-bottom:6px;">ГОРОД<\/div><input value="Пермь" style="width:100%;background:#0D0E11;border:1px solid rgba\(255,255,255,.09\);border-radius:9px;padding:9px 11px;color:#F2F3F0;font-family:'Manrope';font-size:12\.5px;outline:none;"><\/div>/,
    `<div><div style="font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1.2px;color:#6B7076;margin-bottom:6px;">ГОРОД</div><input data-mm-persona="city" style="width:100%;background:#0D0E11;border:1px solid rgba(255,255,255,.09);border-radius:9px;padding:9px 11px;color:#F2F3F0;font-family:'Manrope';font-size:12.5px;outline:none;"></div>`,
  ],
  [
    /<div><div style="font-family:'JetBrains Mono';font-size:8\.5px;letter-spacing:1\.2px;color:#6B7076;margin-bottom:6px;">СТРАНА<\/div><input value="Россия" style="width:100%;background:#0D0E11;border:1px solid rgba\(255,255,255,.09\);border-radius:9px;padding:9px 11px;color:#F2F3F0;font-family:'Manrope';font-size:12\.5px;outline:none;"><\/div>/,
    `<div><div style="font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1.2px;color:#6B7076;margin-bottom:6px;">СТРАНА</div><input data-mm-persona="country" style="width:100%;background:#0D0E11;border:1px solid rgba(255,255,255,.09);border-radius:9px;padding:9px 11px;color:#F2F3F0;font-family:'Manrope';font-size:12.5px;outline:none;"></div>`,
  ],
  [
    /<div><div style="font-family:'JetBrains Mono';font-size:8\.5px;letter-spacing:1\.2px;color:#6B7076;margin-bottom:6px;">ЧАСОВОЙ ПОЯС<\/div><input placeholder="Europe\/Madrid" style="width:100%;background:#0D0E11;border:1px solid rgba\(255,255,255,.09\);border-radius:9px;padding:9px 11px;color:#F2F3F0;font-family:'Manrope';font-size:12\.5px;outline:none;"><\/div>/,
    `<div><div style="font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1.2px;color:#6B7076;margin-bottom:6px;">ЧАСОВОЙ ПОЯС</div><input data-mm-persona="timezone" placeholder="Europe/Madrid" style="width:100%;background:#0D0E11;border:1px solid rgba(255,255,255,.09);border-radius:9px;padding:9px 11px;color:#F2F3F0;font-family:'Manrope';font-size:12.5px;outline:none;"></div>`,
  ],
  [
    /<div><div style="font-family:'JetBrains Mono';font-size:8\.5px;letter-spacing:1\.2px;color:#6B7076;margin-bottom:6px;">ХАРАКТЕР<\/div><textarea rows="2" placeholder="тёплая, игривая, немного застенчивая…" style="width:100%;background:#0D0E11;border:1px solid rgba\(255,255,255,.09\);border-radius:9px;padding:9px 11px;color:#F2F3F0;font-family:'Manrope';font-size:12px;line-height:1.5;resize:vertical;outline:none;"><\/textarea><\/div>/,
    `<div><div style="font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1.2px;color:#6B7076;margin-bottom:6px;">ХАРАКТЕР</div><textarea data-mm-persona="personality" rows="2" placeholder="тёплая, игривая, немного застенчивая…" style="width:100%;background:#0D0E11;border:1px solid rgba(255,255,255,.09);border-radius:9px;padding:9px 11px;color:#F2F3F0;font-family:'Manrope';font-size:12px;line-height:1.5;resize:vertical;outline:none;"></textarea></div>`,
  ],
  [
    /<div><div style="font-family:'JetBrains Mono';font-size:8\.5px;letter-spacing:1\.2px;color:#6B7076;margin-bottom:6px;">ХОББИ И УВЛЕЧЕНИЯ<\/div><textarea rows="2" placeholder="йога, кофе, путешествия…" style="width:100%;background:#0D0E11;border:1px solid rgba\(255,255,255,.09\);border-radius:9px;padding:9px 11px;color:#F2F3F0;font-family:'Manrope';font-size:12px;line-height:1.5;resize:vertical;outline:none;"><\/textarea><\/div>/,
    `<div><div style="font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1.2px;color:#6B7076;margin-bottom:6px;">ХОББИ И УВЛЕЧЕНИЯ</div><textarea data-mm-persona="hobbies" rows="2" placeholder="йога, кофе, путешествия…" style="width:100%;background:#0D0E11;border:1px solid rgba(255,255,255,.09);border-radius:9px;padding:9px 11px;color:#F2F3F0;font-family:'Manrope';font-size:12px;line-height:1.5;resize:vertical;outline:none;"></textarea></div>`,
  ],
  [
    /<div><div style="font-family:'JetBrains Mono';font-size:8\.5px;letter-spacing:1\.2px;color:#6B7076;margin-bottom:6px;">ИНТЕРЕСЫ \/ ТЕМЫ ДЛЯ РАЗГОВОРА<\/div><textarea rows="2" placeholder="музыка, мода, спорт…" style="width:100%;background:#0D0E11;border:1px solid rgba\(255,255,255,.09\);border-radius:9px;padding:9px 11px;color:#F2F3F0;font-family:'Manrope';font-size:12px;line-height:1.5;resize:vertical;outline:none;"><\/textarea><\/div>/,
    `<div><div style="font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1.2px;color:#6B7076;margin-bottom:6px;">ИНТЕРЕСЫ / ТЕМЫ ДЛЯ РАЗГОВОРА</div><textarea data-mm-persona="interests" rows="2" placeholder="музыка, мода, спорт…" style="width:100%;background:#0D0E11;border:1px solid rgba(255,255,255,.09);border-radius:9px;padding:9px 11px;color:#F2F3F0;font-family:'Manrope';font-size:12px;line-height:1.5;resize:vertical;outline:none;"></textarea></div>`,
  ],
  [
    /<div><div style="font-family:'JetBrains Mono';font-size:8\.5px;letter-spacing:1\.2px;color:#6B7076;margin-bottom:6px;">СТИЛЬ ПЕРЕПИСКИ<\/div><textarea rows="2" placeholder="короткие сообщения, эмодзи, без формальностей…" style="width:100%;background:#0D0E11;border:1px solid rgba\(255,255,255,.09\);border-radius:9px;padding:9px 11px;color:#F2F3F0;font-family:'Manrope';font-size:12px;line-height:1.5;resize:vertical;outline:none;"><\/textarea><\/div>/,
    `<div><div style="font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1.2px;color:#6B7076;margin-bottom:6px;">СТИЛЬ ПЕРЕПИСКИ</div><textarea data-mm-persona="speaking_style" rows="2" placeholder="короткие сообщения, эмодзи, без формальностей…" style="width:100%;background:#0D0E11;border:1px solid rgba(255,255,255,.09);border-radius:9px;padding:9px 11px;color:#F2F3F0;font-family:'Manrope';font-size:12px;line-height:1.5;resize:vertical;outline:none;"></textarea></div>`,
  ],
  [
    /<div><div style="font-family:'JetBrains Mono';font-size:8\.5px;letter-spacing:1\.2px;color:#6B7076;margin-bottom:6px;">ПРЕДЫСТОРИЯ<\/div><textarea rows="2" placeholder="откуда она, чем занимается, что важно в жизни…" style="width:100%;background:#0D0E11;border:1px solid rgba\(255,255,255,.09\);border-radius:9px;padding:9px 11px;color:#F2F3F0;font-family:'Manrope';font-size:12px;line-height:1.5;resize:vertical;outline:none;"><\/textarea><\/div>/,
    `<div><div style="font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1.2px;color:#6B7076;margin-bottom:6px;">ПРЕДЫСТОРИЯ</div><textarea data-mm-persona="backstory" rows="2" placeholder="откуда она, чем занимается, что важно в жизни…" style="width:100%;background:#0D0E11;border:1px solid rgba(255,255,255,.09);border-radius:9px;padding:9px 11px;color:#F2F3F0;font-family:'Manrope';font-size:12px;line-height:1.5;resize:vertical;outline:none;"></textarea></div>`,
  ],
  [
    /<div style="font-size:10\.5px;color:#9BA0A6;">\{\{ threadHead\.platform \}\} · \{\{ t\.persona \}\}: <span style="color:#F0A8C8;font-weight:700;">Mia<\/span>/,
    '<div style="font-size:10.5px;color:#9BA0A6;">{{ threadHead.platform }} · {{ t.persona }}: <span style="color:#F0A8C8;font-weight:700;">{{ threadHead.persona }}</span>',
  ],
  [
    /<sc-for list="\{\{ archiveMini \}\}" as="am"/,
    '<sc-for list="{{ s.archiveMini }}" as="am"',
  ],
  [
    /<div style="\{\{ am\.style \}\}" style-hover="border-color:#D7F452;"><\/div>/,
    '<div onClick="{{ am.pick }}" style="{{ am.style }}" style-hover="border-color:#D7F452;"></div>',
  ],
  [
    /<sc-if value="\{\{ s\.uploadMode \}\}" hint-placeholder-val="\{\{ true \}\}">\s*<div style="aspect-ratio:3\/4;border:1\.5px dashed/,
    '<sc-if value="{{ s.uploadMode }}" hint-placeholder-val="{{ true }}"><div data-mm-slot-upload="{{ s.uploadKey }}" style="aspect-ratio:3/4;border:1.5px dashed',
  ],
  // (composer block is patched by applyComposerBlock() below — regex was too fragile with style-hover)
  [
    /<span style="display:flex;width:14px;height:14px;color:#9BA0A6;cursor:pointer;flex:none;" style-hover="color:#D7F452;" dangerouslySetInnerHTML="\{\{ icoCopy \}\}"><\/span>\s*<\/div>\s*<\/sc-for>\s*<\/div>\s*<\/div>\s*<\/sc-for>/,
    '<span onClick="{{ u.copy }}" style="display:flex;width:14px;height:14px;color:#9BA0A6;cursor:pointer;flex:none;" style-hover="color:#D7F452;" dangerouslySetInnerHTML="{{ icoCopy }}"></span></div></sc-for></div></div></sc-for>',
  ],
  [
    /<sc-if value="\{\{ ch\.hot \}\}" hint-placeholder-val="\{\{ false \}\}"><span style="font-family:'JetBrains Mono';font-size:7\.5px;background:rgba\(251,146,60,.15\);color:#FB923C;padding:1px 5px;border-radius:4px;">24ч\+<\/span><\/sc-if>\s*<\/div>/,
    `<sc-if value="{{ ch.hot }}" hint-placeholder-val="{{ false }}"><span style="font-family:'JetBrains Mono';font-size:7.5px;background:rgba(251,146,60,.15);color:#FB923C;padding:1px 5px;border-radius:4px;">24ч+</span></sc-if>
                  </div>`,
  ],
  // Notes footer from design source (no data-mm attrs yet)
  [
    /<div style="padding:10px 12px;border-top:1px solid rgba\(255,255,255,.07\);display:flex;gap:6px;">\s*<div style="flex:1;border:1px solid rgba\(255,255,255,.12\);border-radius:9px;padding:7px;text-align:center;font-size:11\.5px;font-weight:700;color:#C084FC;cursor:pointer;" style-hover="border-color:#C084FC;">✦ AI-\{\{ t\.analysis \}\}<\/div>\s*<div onClick="\{\{ toggleNote \}\}" style="flex:1;background:rgba\(215,244,82,.12\);border:1px solid rgba\(215,244,82,.3\);border-radius:9px;padding:7px;text-align:center;font-size:11\.5px;font-weight:700;color:#D7F452;cursor:pointer;" style-hover="background:rgba\(215,244,82,.2\);">\+ \{\{ t\.addNote \}\}<\/div>\s*<\/div>/,
    `<sc-if value="{{ noteFormClosed }}" hint-placeholder-val="{{ false }}">
            <div style="padding:10px 12px;border-top:1px solid rgba(255,255,255,.07);display:flex;gap:6px;">
              <div onClick="{{ analyzeNotes }}" data-mm-note-analyze style="flex:1;border:1px solid rgba(255,255,255,.12);border-radius:9px;padding:7px;text-align:center;font-size:11.5px;font-weight:700;color:#C084FC;cursor:pointer;" style-hover="border-color:#C084FC;">{{ analyzeNotesLabel }}</div>
              <div onClick="{{ toggleNote }}" data-mm-note-toggle style="flex:1;background:rgba(215,244,82,.12);border:1px solid rgba(215,244,82,.3);border-radius:9px;padding:7px;text-align:center;font-size:11.5px;font-weight:700;color:#D7F452;cursor:pointer;" style-hover="background:rgba(215,244,82,.2);">+ {{ t.addNote }}</div>
            </div>
            </sc-if>`,
  ],
  [
    /<div onClick="\{\{ closePops \}\}" style="background:#121316;border:1px solid rgba\(255,255,255,.07\);border-radius:16px;display:flex;flex-direction:column;overflow:hidden;min-height:0;flex:1;position:relative;">/,
    '<div style="background:#121316;border:1px solid rgba(255,255,255,.07);border-radius:16px;display:flex;flex-direction:column;overflow:hidden;min-height:0;flex:1;position:relative;">',
  ],
  [
    /<div id="mm-thread-scroll" style="flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px;">/,
    '<div id="mm-thread-scroll" onClick="{{ closePops }}" style="flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px;">',
  ],
  [
    /(<\/sc-for>\s*)<\/div>\s*<!-- scroll to bottom/,
    `$1<div id="mm-thread-end" style="height:1px;flex:none;width:100%;margin-top:-1px;" aria-hidden="true"></div>
            </div>
            <!-- scroll to bottom`,
  ],
  [
    /<div style="display:flex;gap:6px;align-items:baseline;"><span style="\{\{ ch\.nameStyle \}\}">\{\{ ch\.name \}\}<\/span><span style="font-family:'JetBrains Mono';font-size:8px;letter-spacing:1px;color:\{\{ ch\.platColor \}\};">\{\{ ch\.platform \}\}<\/span><\/div>/,
    `<div style="display:flex;gap:6px;align-items:baseline;flex-wrap:wrap;min-width:0;"><span style="{{ ch.nameStyle }}">{{ ch.name }}</span><sc-if value="{{ ch.isUnread }}" hint-placeholder-val="{{ false }}"><span style="{{ ch.unreadLabelStyle }}">{{ ch.newLabel }}</span></sc-if><span style="font-family:'JetBrains Mono';font-size:8px;letter-spacing:1px;color:{{ ch.platColor }};">{{ ch.platform }}</span><sc-if value="{{ ch.unreadBadge }}" hint-placeholder-val="{{ false }}"><span style="{{ ch.unreadBadgeStyle }}">{{ ch.unreadBadge }}</span></sc-if></div>`,
  ],
  [
    /<div style="font-size:11px;color:#9BA0A6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">\{\{ ch\.last \}\}<\/div>/,
    '<div style="{{ ch.lastStyle }}">{{ ch.last }}</div>',
  ],
  [
    /<textarea rows="3" placeholder="\{\{ t\.noteTextPh \}\}" style="width:100%;background:#0D0E11;border:1px solid rgba\(255,255,255,.09\);border-radius:10px;padding:9px 12px;color:#F2F3F0;font-family:'Manrope';font-size:12px;line-height:1.5;resize:vertical;outline:none;"><\/textarea>/,
    '<textarea data-mm-note-text rows="3" value="{{ noteDraft }}" onInput="{{ onNoteInput }}" placeholder="{{ t.noteTextPh }}" style="width:100%;background:#0D0E11;border:1px solid rgba(255,255,255,.09);border-radius:10px;padding:9px 12px;color:#F2F3F0;font-family:\'Manrope\';font-size:12px;line-height:1.5;resize:vertical;outline:none;"></textarea>',
  ],
  [
    /<div onClick="\{\{ saveNote \}\}" style="flex:1;background:rgba\(215,244,82,.12\);border:1px solid rgba\(215,244,82,.3\);border-radius:9px;padding:8px;text-align:center;font-size:12px;font-weight:800;color:#D7F452;cursor:pointer;" style-hover="background:rgba\(215,244,82,.2\);">\{\{ t\.save \}\}<\/div>\s*<div onClick="\{\{ closeNote \}\}" style="border:1px solid rgba\(255,255,255,.12\);border-radius:9px;padding:8px 14px;text-align:center;font-size:12px;font-weight:700;color:#9BA0A6;cursor:pointer;" style-hover="border-color:rgba\(255,255,255,.3\);">\{\{ t\.opCancel \}\}<\/div>/,
    '<div onClick="{{ saveNote }}" data-mm-note-save style="flex:1;background:rgba(215,244,82,.12);border:1px solid rgba(215,244,82,.3);border-radius:9px;padding:8px;text-align:center;font-size:12px;font-weight:800;color:#D7F452;cursor:pointer;" style-hover="background:rgba(215,244,82,.2);">{{ t.save }}</div><div onClick="{{ closeNote }}" data-mm-note-cancel style="border:1px solid rgba(255,255,255,.12);border-radius:9px;padding:8px 14px;text-align:center;font-size:12px;font-weight:700;color:#9BA0A6;cursor:pointer;" style-hover="border-color:rgba(255,255,255,.3);">{{ t.opCancel }}</div>',
  ],
  [
    /<span onClick="\{\{ nt\.pick \}\}" style="\{\{ nt\.style \}\}">\{\{ nt\.label \}\}<\/span>/,
    '<span data-mm-note-tag onClick="{{ nt.pick }}" style="{{ nt.style }}">{{ nt.label }}</span>',
  ],
  [
    /<div style="display:flex;gap:8px;"><div style="flex:1;background:rgba\(215,244,82,.12\);border:1px solid rgba\(215,244,82,.3\);border-radius:9px;padding:10px;text-align:center;font-size:12px;font-weight:800;color:#D7F452;cursor:pointer;">\{\{ t\.save \}\}<\/div><\/div>\s*<\/div>\s*<\/sc-if>/,
    `<div style="display:flex;gap:8px;"><div data-mm-char-persona-save style="flex:1;background:rgba(215,244,82,.12);border:1px solid rgba(215,244,82,.3);border-radius:9px;padding:10px;text-align:center;font-size:12px;font-weight:800;color:#D7F452;cursor:pointer;">{{ t.save }}</div></div>
          </div>
          </sc-if>`,
  ],
]

const LOGIC_PATCHES = [
  [
    /const go = \(page\) => \(\) => setS\(\{ page, connDetail: null, charDetail: null, moreOpen: false \}\);/,
    `const go = (page) => () => {
      if (page === 'workflow') {
        const base = window.location.pathname.indexOf('/workspace/') >= 0 ? '/workspace/' : '/';
        window.location.href = base + 'workflow/';
        return;
      }
      setS({ page, connDetail: null, charDetail: null, moreOpen: false });
    };`,
  ],
  // хук mount
  [
    /componentDidMount\(\) \{\s*this\._onResize/,
    `componentDidMount() {
    this._onResize`,
  ],
  [
    /this\._onResize\(\);\s*\}/,
    `this._onResize();
    if (window.MMOS_BRIDGE) window.MMOS_BRIDGE.onMount(this);
  }`,
  ],
  [
    /msgReact: null, emojiOpen: false,/,
    'msgReact: null, emojiOpen: false, showScrollDown: false, replyDraft: \'\', noteDraft: \'\',',
  ],
  [
    /noteFormOpen: false, noteTag: 0/,
    'noteFormOpen: false, noteDraft: \'\', noteTag: 0, replyDraft: \'\'',
  ],
  [
    /framesLeft: 'кадров', active: 'АКТИВНА', until: 'до', toPayout: 'к выплате', allRead: 'все прочитаны', teamReplies: 'ответов',/,
    "framesLeft: 'кадров', active: 'АКТИВНА', until: 'до', toPayout: 'к выплате', allRead: 'все прочитаны', teamReplies: 'ответов',\n      donationAlertOpen: 'Открыть донаты', donationAlertDismiss: 'Закрыть',",
  ],
  [
    /framesLeft: 'frames', active: 'ACTIVE', until: 'until', toPayout: 'payable', allRead: 'all read', teamReplies: 'replies',/,
    "framesLeft: 'frames', active: 'ACTIVE', until: 'until', toPayout: 'payable', allRead: 'all read', teamReplies: 'replies',\n      donationAlertOpen: 'Open donations', donationAlertDismiss: 'Dismiss',",
  ],
  [
    /const donStats = \[\s*\{ label: lang === 'ru' \? 'ВСЕГО' : 'TOTAL', value: '100,00 ₽'/,
    `const donStats = [
      { label: lang === 'ru' ? 'ВСЕГО' : 'TOTAL', value: '—'`,
  ],
  [
    /const incoming = \[\{ sum: '\+100,00 ₽'/,
    `const incoming = [{ sum: '+—'`,
  ],
  [
    /noteFormOpen: s\.noteFormOpen, noteTagChips, toggleNote: \(\) => setS\(\{ noteFormOpen: !s\.noteFormOpen \}\), closeNote: \(\) => setS\(\{ noteFormOpen: false \}\), saveNote: \(\) => setS\(\{ noteFormOpen: false \}\),/,
    `noteFormOpen: s.noteFormOpen, noteFormClosed: !s.noteFormOpen, noteDraft: s.noteDraft || '', noteTagChips,
      toggleNote: () => window.MMOS_BRIDGE?.toggleNoteForm?.(),
      closeNote: () => window.MMOS_BRIDGE?.closeNoteForm?.(),
      saveNote: () => void window.MMOS_BRIDGE?.saveConversationNote?.(),
      analyzeNotes: () => void window.MMOS_BRIDGE?.analyzeConversationNotes?.(),
      analyzeNotesLabel: '✦ AI-' + (t.analysis || 'анализ'),
      onNoteInput: (e) => setS({ noteDraft: e?.target?.value ?? '' }),
      replyDraft: s.replyDraft || '',
      onReplyInput: (e) => setS({ replyDraft: e?.target?.value ?? '' }),
      onReplyKeyDown: (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void window.MMOS_BRIDGE?.sendReply?.(); } },
      pickChatFile: (e) => window.MMOS_BRIDGE?.pickChatFile?.(e),
      sendReplyClick: () => void window.MMOS_BRIDGE?.sendReply?.(),
      clearChatAttach: (e) => window.MMOS_BRIDGE?.clearChatAttachment?.(e),`,
  ],
  // enrich return
  [
    /return \{\s*t, isMobile/,
    `const __dcVals = {
      t, isMobile`,
  ],
  [
    /teamKpi, members, templates\s*\};\s*\}/,
    `teamKpi, members, templates,
      creditsBalance: '0', userEmailShort: '', userRolePlan: '', donationsKpiTotal: '—', donationsKpiPayout: '—',
      hasDonationAlert: false, donationAlertTitle: '', donationAlertBody: '',
      openDonationAlert: () => {}, dismissDonationAlert: () => {},
      hasDonationsLoadError: false, donationsLoadError: null,
      dialogsUnreadLabel: '', planDisplayName: '—', planUntil: '—', dialogsTotal: '0', teamRepliesCount: '0',
      creditsFramesHint: '', activeChat: { name: '—', initial: '?', vip: false, persona: '—', lang: '—', avStyle: '' },
      notesTitle: '', activeCharName: '—', activeCharInitial: '—',
      runGenerate: () => {}, runGenerateVideo: () => {}, sendReply: () => {}, logout: () => {},
      apiError: null, apiBusy: false, canChat: true, canStudio: true, canBilling: true,
      referralLink: '—', referralStats: '—', dialogsPlatformLine: '—', userSidebarInitial: 'R',
      payoutHint: '—',
    };
    return (window.MMOS_BRIDGE ? window.MMOS_BRIDGE.enrich(this, __dcVals) : __dcVals);
  }`,
  ],
]

const COMPOSER_BLOCK = `<!-- scroll to bottom (shown only when not at end) -->
            <sc-if value="{{ showScrollDown }}" hint-placeholder-val="{{ false }}">
            <div onClick="{{ scrollDown }}" data-mm-scroll-down style="position:absolute;right:16px;bottom:88px;z-index:8;width:36px;height:36px;border-radius:50%;background:#1A1C20;border:1px solid rgba(255,255,255,.14);display:flex;align-items:center;justify-content:center;font-size:16px;color:#9BA0A6;cursor:pointer;box-shadow:0 6px 18px rgba(0,0,0,.4);" style-hover="color:#F2F3F0;border-color:rgba(255,255,255,.3);">↓</div>
            </sc-if>
            <div onClick="{{ stop }}" data-mm-chat-composer style="padding:10px 12px;border-top:1px solid rgba(255,255,255,.07);display:flex;flex-direction:column;gap:8px;position:relative;z-index:4;">
              <sc-if value="{{ emojiOpen }}" hint-placeholder-val="{{ false }}">
                <div style="background:#1A1C20;border:1px solid rgba(255,255,255,.14);border-radius:14px;padding:10px;display:grid;grid-template-columns:repeat(8,1fr);gap:4px;box-shadow:0 10px 30px rgba(0,0,0,.5);">
                  <sc-for list="{{ emojiPick }}" as="ep" hint-placeholder-count="16">
                    <span data-mm-emoji-pick="{{ ep.e }}" onClick="{{ ep.pick }}" style="font-size:20px;cursor:pointer;text-align:center;padding:3px;border-radius:8px;" style-hover="background:rgba(255,255,255,.08);">{{ ep.e }}</span>
                  </sc-for>
                </div>
              </sc-if>
              <sc-if value="{{ chatAttachPreview }}" hint-placeholder-val="{{ false }}">
                <div style="display:flex;align-items:center;gap:10px;background:#0D0E11;border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:8px 10px;">
                  <img src="{{ chatAttachPreview }}" alt="" style="width:52px;height:52px;object-fit:cover;border-radius:8px;flex:none;">
                  <div style="flex:1;min-width:0;">
                    <div style="font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1px;color:#6B7076;margin-bottom:3px;">{{ t.attach }}</div>
                    <div style="font-size:12px;color:#F2F3F0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{{ chatAttachName }}</div>
                  </div>
                  <span data-mm-chat-clear-attach onClick="{{ clearChatAttach }}" style="cursor:pointer;color:#9BA0A6;font-size:18px;line-height:1;padding:2px 6px;" style-hover="color:#F87171;">✕</span>
                </div>
              </sc-if>
              <div style="display:flex;gap:6px;align-items:flex-end;">
                <div data-mm-chat-attach onClick="{{ pickChatFile }}" title="{{ t.attach }}" style="width:38px;height:38px;flex:none;border-radius:10px;border:1px solid rgba(255,255,255,.1);display:flex;align-items:center;justify-content:center;color:#9BA0A6;cursor:pointer;" style-hover="color:#D7F452;border-color:rgba(215,244,82,.4);"><span style="display:flex;width:18px;height:18px;" dangerouslySetInnerHTML="{{ icoClip }}"></span></div>
                <div data-mm-chat-emoji onClick="{{ toggleEmoji }}" style="width:38px;height:38px;flex:none;border-radius:10px;border:1px solid rgba(255,255,255,.1);display:flex;align-items:center;justify-content:center;font-size:18px;cursor:pointer;" style-hover="border-color:rgba(215,244,82,.4);">😊</div>
                <textarea data-mm-chat-reply rows="2" value="{{ replyDraft }}" onInput="{{ onReplyInput }}" onKeyDown="{{ onReplyKeyDown }}" placeholder="{{ t.msgPlaceholder }}" style="flex:1;min-height:52px;max-height:140px;background:#0D0E11;border:1px solid rgba(255,255,255,.09);border-radius:10px;padding:9px 12px;color:#F2F3F0;font-family:'Manrope';font-size:13px;resize:none;outline:none;"></textarea>
                <div data-mm-chat-send onClick="{{ sendReplyClick }}" style="{{ sendBtnStyle }}" style-hover="background:#E8FA8A;"><span style="display:flex;width:17px;height:17px;" dangerouslySetInnerHTML="{{ icoSendArrow }}"></span></div>
              </div>
              <div style="font-family:'JetBrains Mono';font-size:9px;color:#5C6066;text-align:right;">Enter — отправить · Shift+Enter — новая строка</div>
            </div>
          </div>
          </sc-if>
`

function applyComposerBlock(src) {
  const startMark = '<!-- scroll to bottom -->'
  const endMark = '<!-- notes -->'
  const start = src.indexOf(startMark)
  if (start < 0) {
    console.warn('composer block: start marker missing')
    return src
  }
  const end = src.indexOf(endMark, start)
  if (end < 0) {
    console.warn('composer block: end marker missing')
    return src
  }
  // Keep mm-thread-end sentinel just before scroll/composer region
  let before = src.slice(0, start)
  if (!before.includes('id="mm-thread-end"')) {
    before = before.replace(
      /(<\/sc-for>\s*)<\/div>\s*$/,
      `$1<div id="mm-thread-end" style="height:1px;flex:none;width:100%;margin-top:-1px;" aria-hidden="true"></div>
            </div>
            `,
    )
  }
  console.log('composer block: applied')
  return before + COMPOSER_BLOCK + '\n          ' + src.slice(end)
}

const indexPath = path.join(osRoot, 'index.html')
let html = fs.readFileSync(indexPath, 'utf8')

for (const [from, to] of TEMPLATE_PATCHES) {
  const next = html.replace(from, to)
  if (next === html) console.warn('template patch skipped:', String(from).slice(0, 60))
  html = next
}

html = applyComposerBlock(html)

for (const [from, to] of LOGIC_PATCHES) {
  const next = html.replace(from, to)
  if (next === html) console.warn('logic patch skipped:', String(from).slice(0, 60))
  html = next
}

// video generate — клик по всей кнопке (icoFilm в макете)
html = html.replace(
  /<div style="display:flex;align-items:center;gap:12px;background:#D7F452;border-radius:12px;padding:12px 16px;cursor:pointer;" style-hover="background:#E8FA8A;">\s*<span style="display:flex;width:17px;height:17px;color:#171A05;" dangerouslySetInnerHTML="\{\{ icoFilm \}\}"><\/span>\s*<span style="flex:1;font-weight:800;font-size:14px;color:#171A05;">\{\{ t\.generateVideo \}\}<\/span>/,
  `<div data-mm-video-generate onClick="{{ runGenerateVideo }}" style="display:flex;align-items:center;gap:12px;background:#D7F452;border-radius:12px;padding:12px 16px;cursor:pointer;" style-hover="background:#E8FA8A;">
              <span style="display:flex;width:17px;height:17px;color:#171A05;" dangerouslySetInnerHTML="{{ icoFilm }}"></span>
              <span style="flex:1;font-weight:800;font-size:14px;color:#171A05;">{{ t.generateVideo }}</span>`,
)
html = html.replace(
  /<div style="display:flex;align-items:center;gap:12px;background:#D7F452;border-radius:12px;padding:12px 16px;cursor:pointer;" style-hover="background:#E8FA8A;">\s*<span style="display:flex;width:17px;height:17px;color:#171A05;" dangerouslySetInnerHTML="\{\{ icoPlay \}\}"><\/span>\s*<span style="flex:1;font-weight:800;font-size:14px;color:#171A05;">\{\{ t\.generateVideo \}\}<\/span>/,
  `<div data-mm-video-generate onClick="{{ runGenerateVideo }}" style="display:flex;align-items:center;gap:12px;background:#D7F452;border-radius:12px;padding:12px 16px;cursor:pointer;" style-hover="background:#E8FA8A;">
              <span style="display:flex;width:17px;height:17px;color:#171A05;" dangerouslySetInnerHTML="{{ icoPlay }}"></span>
              <span style="flex:1;font-weight:800;font-size:14px;color:#171A05;">{{ t.generateVideo }}</span>`,
)

const FULL_API_PATCHES = [
  [/<span style="\{\{ rc\.style \}\}" style-hover="border-color:rgba\(255,255,255,.3\);">\{\{ rc\.label \}\}<\/span>/g, '<span onClick="{{ rc.pick }}" style="{{ rc.style }}" style-hover="border-color:rgba(255,255,255,.3);">{{ rc.label }}</span>'],
  [/<div style="\{\{ cf\.thumbStyle \}\}" style-hover="border-color:#D7F452;"><\/div>/g, '<div onClick="{{ cf.pick }}" style="{{ cf.thumbStyle }}" style-hover="border-color:#D7F452;"></div>'],
  [
    /<span style="font-family:'JetBrains Mono';font-size:10px;background:rgba\(215,244,82,.12\);color:#D7F452;border:1px solid rgba\(215,244,82,.3\);padding:3px 10px;border-radius:20px;">TELEGRAM 8<\/span>\s*<span style="font-family:'JetBrains Mono';font-size:10px;background:rgba\(240,168,200,.1\);color:#F0A8C8;border:1px solid rgba\(240,168,200,.3\);padding:3px 10px;border-radius:20px;">FANVUE 1<\/span>/,
    '<span style="font-family:\'JetBrains Mono\';font-size:10px;background:rgba(255,255,255,.06);color:#9BA0A6;border:1px solid rgba(255,255,255,.12);padding:3px 10px;border-radius:20px;">{{ dialogsPlatformLine }}</span>',
  ],
  [
    /<div style="width:30px;height:30px;border-radius:50%;background:linear-gradient\(135deg,#818CF8,#C084FC\);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:13px;color:#14102A;">R<\/div>/,
    '<div style="width:30px;height:30px;border-radius:50%;background:linear-gradient(135deg,#818CF8,#C084FC);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:13px;color:#14102A;">{{ userSidebarInitial }}</div>',
  ],
  [
    /<input placeholder="Вставьте ключ из wavespeed.ai" style="flex:1;min-width:200px;background:#0D0E11;border:1px solid rgba\(255,255,255,.09\);border-radius:9px;padding:10px 12px;color:#F2F3F0;font-family:'JetBrains Mono';font-size:12px;outline:none;">\s*<div style="background:linear-gradient\(135deg,#C084FC,#F0A8C8\);color:#1a0a1c;font-weight:800;font-size:12.5px;border-radius:10px;padding:10px 18px;cursor:pointer;" style-hover="filter:brightness\(1.08\);">Сохранить<\/div>/,
    '<input data-mm-conn-wavespeed-key placeholder="Вставьте ключ из wavespeed.ai" style="flex:1;min-width:200px;background:#0D0E11;border:1px solid rgba(255,255,255,.09);border-radius:9px;padding:10px 12px;color:#F2F3F0;font-family:\'JetBrains Mono\';font-size:12px;outline:none;"><div data-mm-conn-wavespeed-save style="background:linear-gradient(135deg,#C084FC,#F0A8C8);color:#1a0a1c;font-weight:800;font-size:12.5px;border-radius:10px;padding:10px 18px;cursor:pointer;" style-hover="filter:brightness(1.08);">Сохранить</div>',
  ],
  [
    /<input placeholder="Вставьте токен BotFather" style="width:100%;background:#0D0E11;border:1px solid rgba\(255,255,255,.09\);border-radius:9px;padding:10px 11px;color:#F2F3F0;font-family:'Manrope';font-size:12.5px;outline:none;"><\/div>\s*<div><div style="font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1.2px;color:#6B7076;margin-bottom:6px;">МОДЕЛЬ<\/div><select style="width:100%;background:#0D0E11;color:#F2F3F0;border:1px solid rgba\(255,255,255,.09\);border-radius:9px;padding:10px 11px;font-family:'Manrope';font-size:12.5px;outline:none;"><option>Не назначена<\/option><option>Mia<\/option><option>Ruby<\/option><\/select><\/div>\s*<div style="background:linear-gradient\(135deg,#C084FC,#F0A8C8\);color:#1a0a1c;font-weight:800;font-size:12.5px;border-radius:10px;padding:11px 16px;text-align:center;cursor:pointer;" style-hover="filter:brightness\(1.08\);">Добавить бота<\/div>/,
    '<input data-mm-conn-tg-token placeholder="Вставьте токен BotFather" style="width:100%;background:#0D0E11;border:1px solid rgba(255,255,255,.09);border-radius:9px;padding:10px 11px;color:#F2F3F0;font-family:\'Manrope\';font-size:12.5px;outline:none;"></div><div><div style="font-family:\'JetBrains Mono\';font-size:8.5px;letter-spacing:1.2px;color:#6B7076;margin-bottom:6px;">МОДЕЛЬ</div><select data-mm-conn-tg-model style="width:100%;background:#0D0E11;color:#F2F3F0;border:1px solid rgba(255,255,255,.09);border-radius:9px;padding:10px 11px;font-family:\'Manrope\';font-size:12.5px;outline:none;"><option value="">Не назначена</option></select></div><div data-mm-conn-tg-add style="background:linear-gradient(135deg,#C084FC,#F0A8C8);color:#1a0a1c;font-weight:800;font-size:12.5px;border-radius:10px;padding:11px 16px;text-align:center;cursor:pointer;" style-hover="filter:brightness(1.08);">Добавить бота</div>',
  ],
  [
    /<div style="background:linear-gradient\(135deg,#C084FC,#F0A8C8\);color:#1a0a1c;font-weight:800;font-size:12.5px;border-radius:10px;padding:11px 16px;text-align:center;cursor:pointer;white-space:nowrap;" style-hover="filter:brightness\(1.08\);">Добавить Fanvue \(OAuth\)<\/div>/,
    '<div data-mm-conn-fanvue-oauth style="background:linear-gradient(135deg,#C084FC,#F0A8C8);color:#1a0a1c;font-weight:800;font-size:12.5px;border-radius:10px;padding:11px 16px;text-align:center;cursor:pointer;white-space:nowrap;" style-hover="filter:brightness(1.08);">Добавить Fanvue (OAuth)</div>',
  ],
  [
    /<span onClick="\{\{ cf\.pick \}\}" style="\{\{ cf\.style \}\}" style-hover="border-color:rgba\(255,255,255,.3\);color:#D7F452;">\{\{ cf\.label \}\}<\/span>/g,
    '<span onClick="{{ cf.pick }}" style="{{ cf.style }}" style-hover="border-color:rgba(255,255,255,.3);">{{ cf.label }}</span>',
  ],
  [
    /<span onClick="\{\{ ct\.pick \}\}" style="\{\{ ct\.style \}\}" style-hover="border-color:rgba\(255,255,255,.3\);">\{\{ ct\.label \}\}<\/span>/g,
    '<span onClick="{{ ct.pick }}" style="{{ ct.style }}" style-hover="border-color:rgba(255,255,255,.3);">{{ ct.label }}</span>',
  ],
  [
    /<span style="\{\{ cf\.style \}\}" style-hover="border-color:rgba\(255,255,255,.3\);">\{\{ cf\.label \}\}<\/span>/g,
    '<span onClick="{{ cf.pick }}" style="{{ cf.style }}" style-hover="border-color:rgba(255,255,255,.3);">{{ cf.label }}</span>',
  ],
  [
    /<input placeholder="\{\{ t\.searchDialogs \}\}" style="background:#0D0E11/,
    '<input data-mm-chat-search placeholder="{{ t.searchDialogs }}" style="background:#0D0E11',
  ],
  [
    /<span style="font-weight:800;font-size:14px;">\{\{ activeChat\.name \}\}<\/span><span style="font-family:'JetBrains Mono';font-size:7\.5px;background:#D7F452;color:#171A05;font-weight:700;padding:1px 5px;border-radius:5px;">VIP<\/span>/,
    '<span style="font-weight:800;font-size:14px;">{{ activeChat.name }}</span><sc-if value="{{ activeChat.vip }}" hint-placeholder-val="{{ false }}"><span style="font-family:\'JetBrains Mono\';font-size:7.5px;background:#D7F452;color:#171A05;font-weight:700;padding:1px 5px;border-radius:5px;">VIP</span></sc-if>',
  ],
  [
    /<div style="flex:1;background:rgba\(215,244,82,.12\);border:1px solid rgba\(215,244,82,.3\);border-radius:9px;padding:7px;text-align:center;font-size:11.5px;font-weight:700;color:#D7F452;cursor:pointer;" style-hover="background:rgba\(215,244,82,.2\);">\+ \{\{ t\.addNote \}\}<\/div>/,
    '<div onClick="{{ toggleNote }}" data-mm-note-toggle style="flex:1;background:rgba(215,244,82,.12);border:1px solid rgba(215,244,82,.3);border-radius:9px;padding:7px;text-align:center;font-size:11.5px;font-weight:700;color:#D7F452;cursor:pointer;" style-hover="background:rgba(215,244,82,.2);">+ {{ t.addNote }}</div>',
  ],
  [
    /<input value="https:\/\/model-mate\.online\/login\?ref=N62KMA60" readOnly/,
    '<input value="{{ referralLink }}" readOnly',
  ],
  [
    /<div style="font-size:11px;color:#5C6066;">\{\{ t\.invited \}\}: 1 · \{\{ t\.earned \}\}: 0 \{\{ t\.cr \}\}<\/div>/,
    '<div style="font-size:11px;color:#5C6066;">{{ referralStats }}</div>',
  ],
  [
    /<div style="display:flex;align-items:center;gap:6px;border:1px solid rgba\(215,244,82,.3\);background:rgba\(215,244,82,.1\);border-radius:9px;padding:9px 12px;font-size:11.5px;font-weight:800;color:#D7F452;cursor:pointer;"><span style="display:flex;width:13px;height:13px;" dangerouslySetInnerHTML="\{\{ icoCopy \}\}"><\/span>\{\{ t\.copy \}\}<\/div>/,
    '<div data-mm-referral-copy style="display:flex;align-items:center;gap:6px;border:1px solid rgba(215,244,82,.3);background:rgba(215,244,82,.1);border-radius:9px;padding:9px 12px;font-size:11.5px;font-weight:800;color:#D7F452;cursor:pointer;"><span style="display:flex;width:13px;height:13px;" dangerouslySetInnerHTML="{{ icoCopy }}"></span>{{ t.copy }}</div>',
  ],
  [
    /<div style="flex:1;background:rgba\(215,244,82,.12\);border:1px solid rgba\(215,244,82,.3\);border-radius:9px;padding:8px;text-align:center;font-size:11.5px;font-weight:800;color:#D7F452;cursor:pointer;" style-hover="background:rgba\(215,244,82,.2\);">\{\{ t\.payCard \}\}<\/div>/,
    '<div onClick="{{ pl.payCard }}" style="flex:1;background:rgba(215,244,82,.12);border:1px solid rgba(215,244,82,.3);border-radius:9px;padding:8px;text-align:center;font-size:11.5px;font-weight:800;color:#D7F452;cursor:pointer;" style-hover="background:rgba(215,244,82,.2);">{{ t.payCard }}</div>',
  ],
  [
    /<div style="border:1px solid rgba\(255,255,255,.12\);border-radius:9px;padding:8px 10px;font-size:11.5px;font-weight:700;color:#9BA0A6;cursor:pointer;" style-hover="border-color:rgba\(255,255,255,.3\);">\{\{ t\.payCredits \}\}<\/div>/,
    '<div onClick="{{ pl.payCredits }}" style="border:1px solid rgba(255,255,255,.12);border-radius:9px;padding:8px 10px;font-size:11.5px;font-weight:700;color:#9BA0A6;cursor:pointer;" style-hover="border-color:rgba(255,255,255,.3);">{{ t.payCredits }}</div>',
  ],
  [
    /<div style="border:1px solid rgba\(255,255,255,.12\);border-radius:9px;padding:8px 10px;font-size:11.5px;font-weight:700;color:#9BA0A6;cursor:pointer;" style-hover="border-color:rgba\(255,255,255,.3\);">Tribute<\/div>/,
    '<div onClick="{{ pl.payTribute }}" style="border:1px solid rgba(255,255,255,.12);border-radius:9px;padding:8px 10px;font-size:11.5px;font-weight:700;color:#9BA0A6;cursor:pointer;" style-hover="border-color:rgba(255,255,255,.3);">Tribute</div>',
  ],
  [
    /<div style="background:#121316;border:1px solid rgba\(255,255,255,.07\);border-radius:14px;padding:14px 16px;cursor:pointer;" style-hover="border-color:rgba\(215,244,82,.4\);">\s*<div style="font-family:'Unbounded';font-weight:600;font-size:17px;color:#D7F452;margin-bottom:2px;">\{\{ pk\.cr \}\}<\/div>/g,
    '<div onClick="{{ pk.pick }}" style="background:#121316;border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:14px 16px;cursor:pointer;" style-hover="border-color:rgba(215,244,82,.4);"><div style="font-family:\'Unbounded\';font-weight:600;font-size:17px;color:#D7F452;margin-bottom:2px;">{{ pk.cr }}</div>',
  ],
  [
    /<input placeholder="\{\{ t\.donTitle \}\}" style="background:#0D0E11/,
    '<input data-mm-don-title placeholder="{{ t.donTitle }}" style="background:#0D0E11',
  ],
  [
    /<div>\s*<div style="display:flex;justify-content:space-between;margin-bottom:8px;"><span style="font-family:'JetBrains Mono';font-size:9.5px;letter-spacing:1.8px;color:#6B7076;">\{\{ t\.prompt \}\}<\/span><span style="font-size:10.5px;color:#5C6066;">\{\{ t\.optional \}\}<\/span><\/div>\s*<textarea data-mm-studio-prompt rows="3"/,
    '<sc-if value="{{ curMode.showPrompt }}" hint-placeholder-val="{{ false }}"><div><div style="font-family:\'JetBrains Mono\';font-size:9.5px;letter-spacing:1.8px;color:#6B7076;margin-bottom:8px;">{{ t.prompt }}</div><textarea data-mm-studio-prompt rows="3"',
  ],
  [
    /<textarea data-mm-studio-prompt rows="3" placeholder="\{\{ curMode\.promptHint \}\}" style="width:100%;background:#0D0E11[^>]*><\/textarea>\s*<\/div>\s*<sc-if value="\{\{ showGenError \}\}"/,
    '<textarea data-mm-studio-prompt rows="3" placeholder="{{ curMode.promptHint }}" style="width:100%;background:#0D0E11;border:1px solid rgba(255,255,255,.09);border-radius:10px;padding:10px 12px;color:#F2F3F0;font-family:\'Manrope\';font-size:12.5px;resize:vertical;outline:none;"></textarea></div></sc-if><sc-if value="{{ showGenError }}"',
  ],
  [
    /<textarea rows="3" placeholder="\{\{ curMode\.promptHint \}\}" style="width:100%;background:#0D0E11/,
    '<textarea data-mm-studio-prompt rows="3" placeholder="{{ curMode.promptHint }}" style="width:100%;background:#0D0E11',
  ],
  [
    /<textarea rows="3" placeholder="\{\{ t\.donDesc \}\}" style="background:#0D0E11/,
    '<textarea data-mm-don-desc rows="3" placeholder="{{ t.donDesc }}" style="background:#0D0E11',
  ],
  [
    /<input placeholder="\{\{ t\.minSum \}\}" style="flex:1;background:#0D0E11/,
    '<input data-mm-don-min placeholder="{{ t.minSum }}" style="flex:1;background:#0D0E11',
  ],
  [
    /<div style="border:1px solid rgba\(255,255,255,.12\);border-radius:10px;padding:10px 14px;font-size:12px;color:#9BA0A6;">Mia ▾<\/div>/,
    '<select data-mm-don-model style="border:1px solid rgba(255,255,255,.12);border-radius:10px;padding:10px 14px;font-size:12px;color:#9BA0A6;background:#0D0E11;"><option value="">Не назначена</option></select>',
  ],
  [
    /<div style="flex:1;background:rgba\(215,244,82,.12\);border:1px solid rgba\(215,244,82,.3\);border-radius:9px;padding:9px;text-align:center;font-size:12px;font-weight:800;color:#D7F452;cursor:pointer;">\{\{ t\.toModeration \}\}<\/div>/,
    '<div data-mm-don-create style="flex:1;background:rgba(215,244,82,.12);border:1px solid rgba(215,244,82,.3);border-radius:9px;padding:9px;text-align:center;font-size:12px;font-weight:800;color:#D7F452;cursor:pointer;">{{ t.toModeration }}</div>',
  ],
  [
    /<input value="TQrX…9fJk" style="flex:1;background:#0D0E11/,
    '<input data-mm-don-wallet placeholder="Адрес кошелька" style="flex:1;background:#0D0E11',
  ],
  [
    /<div style="border:1px solid rgba\(255,255,255,.12\);border-radius:9px;padding:9px 12px;font-family:'JetBrains Mono';font-size:11px;color:#9BA0A6;">USDT · TRC20 ▾<\/div>/,
    '<select data-mm-don-payout-asset style="border:1px solid rgba(255,255,255,.12);border-radius:9px;padding:9px 12px;font-family:\'JetBrains Mono\';font-size:11px;color:#9BA0A6;background:#0D0E11;"><option value="USDT_TRC20">USDT · TRC20</option><option value="USDT_ERC20">USDT · ERC20</option></select>',
  ],
  [
    /<div style="display:flex;align-items:center;gap:10px;background:#F0A8C8;border-radius:11px;padding:11px 16px;cursor:pointer;" style-hover="filter:brightness\(1.08\);">\s*<span style="flex:1;font-weight:800;font-size:13\.5px;color:#2A0A1C;">\{\{ t\.requestPayout \}\}<\/span>\s*<span style="font-family:'JetBrains Mono';font-size:10\.5px;color:#5E2140;">100,00 ₽ − 2%<\/span>\s*<\/div>/,
    '<div data-mm-don-payout-request style="display:flex;align-items:center;gap:10px;background:#F0A8C8;border-radius:11px;padding:11px 16px;cursor:pointer;" style-hover="filter:brightness(1.08);"><span style="flex:1;font-weight:800;font-size:13.5px;color:#2A0A1C;">{{ t.requestPayout }}</span><span style="font-family:\'JetBrains Mono\';font-size:10.5px;color:#5E2140;">{{ payoutHint }}</span></div>',
  ],
  [
    /<span style="font-size:11.5px;font-weight:700;color:#D7F452;cursor:pointer;">\+ \{\{ t\.addTemplate \}\}<\/span>/,
    '<span data-mm-snippet-add style="font-size:11.5px;font-weight:700;color:#D7F452;cursor:pointer;">+ {{ t.addTemplate }}</span>',
  ],
  [
    /<div onClick="\{\{ toggleLang \}\}" style="font-family:'JetBrains Mono';font-size:10px;font-weight:600;border:1px solid rgba\(255,255,255,.14\);border-radius:7px;padding:4px 8px;cursor:pointer;color:#9BA0A6;" style-hover="color:#F2F3F0;border-color:rgba\(255,255,255,.3\);">\{\{ langLabel \}\}<\/div>\s*<\/div>\s*<\/div>\s*<\/sc-if>/,
    '<div onClick="{{ toggleLang }}" style="font-family:\'JetBrains Mono\';font-size:10px;font-weight:600;border:1px solid rgba(255,255,255,.14);border-radius:7px;padding:4px 8px;cursor:pointer;color:#9BA0A6;" style-hover="color:#F2F3F0;border-color:rgba(255,255,255,.3);">{{ langLabel }}</div><div data-mm-logout onClick="{{ logout }}" style="font-family:\'JetBrains Mono\';font-size:10px;font-weight:600;border:1px solid rgba(248,113,113,.35);border-radius:7px;padding:4px 8px;cursor:pointer;color:#F87171;" style-hover="background:rgba(248,113,113,.1);">Выйти</div></div></div></sc-if>',
  ],
  [
    /<div style="background:#0D0E11;border:1px solid rgba\(255,255,255,.07\);border-radius:12px;padding:14px;display:flex;flex-direction:column;gap:12px;">\s*<div style="display:grid;grid-template-columns:repeat\(auto-fit,minmax\(170px,1fr\)\);gap:10px;align-items:end;">\s*<div><div style="font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1.2px;color:#6B7076;margin-bottom:6px;">БОТ<\/div><div style="font-family:'JetBrains Mono';font-size:10.5px;color:#C9CDD1;background:#0A0B0D;border:1px solid rgba\(255,255,255,.08\);border-radius:9px;padding:9px 10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">@miaklaim_chanel_bot · ✓<\/div><\/div>/,
    '<div data-mm-tg-list></div><div style="background:#0D0E11;border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:14px;display:flex;flex-direction:column;gap:12px;display:none;"><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;align-items:end;"><div><div style="font-family:\'JetBrains Mono\';font-size:8.5px;letter-spacing:1.2px;color:#6B7076;margin-bottom:6px;">БОТ</div><div style="font-family:\'JetBrains Mono\';font-size:10.5px;color:#C9CDD1;background:#0A0B0D;border:1px solid rgba(255,255,255,.08);border-radius:9px;padding:9px 10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">—</div></div>',
  ],
  [
    /<div style="background:#0D0E11;border:1px solid rgba\(255,255,255,.07\);border-radius:12px;padding:14px;display:flex;flex-direction:column;gap:12px;">\s*<div style="display:grid;grid-template-columns:repeat\(auto-fit,minmax\(170px,1fr\)\);gap:10px;align-items:end;">\s*<div><div style="font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1.2px;color:#6B7076;margin-bottom:6px;">АККАУНТ<\/div><div style="font-family:'JetBrains Mono';font-size:10.5px;color:#C9CDD1;background:#0A0B0D;border:1px solid rgba\(255,255,255,.08\);border-radius:9px;padding:9px 10px;">cb130848…<\/div><\/div>/,
    '<div data-mm-fv-list></div><div style="background:#0D0E11;border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:14px;display:none;"><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;align-items:end;"><div><div style="font-family:\'JetBrains Mono\';font-size:8.5px;letter-spacing:1.2px;color:#6B7076;margin-bottom:6px;">АККАУНТ</div><div style="font-family:\'JetBrains Mono\';font-size:10.5px;color:#C9CDD1;background:#0A0B0D;border:1px solid rgba(255,255,255,.08);border-radius:9px;padding:9px 10px;">—</div></div>',
  ],
  [
    /<div style="background:#0D0E11;border:1px solid rgba\(255,255,255,.07\);border-radius:12px;padding:14px;display:flex;flex-direction:column;gap:12px;">\s*<div style="display:grid;grid-template-columns:repeat\(auto-fit,minmax\(160px,1fr\)\);gap:10px;align-items:end;">\s*<div><div style="font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1.2px;color:#6B7076;margin-bottom:6px;">ПОДКЛЮЧЕНИЕ<\/div><div style="font-family:'JetBrains Mono';font-size:10.5px;color:#C9CDD1;background:#0A0B0D;border:1px solid rgba\(255,255,255,.08\);border-radius:9px;padding:9px 10px;">Mia Tribute<\/div><\/div>/,
    '<div data-mm-tribute-list></div><div style="background:#0D0E11;border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:14px;display:none;"><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;align-items:end;"><div><div style="font-family:\'JetBrains Mono\';font-size:8.5px;letter-spacing:1.2px;color:#6B7076;margin-bottom:6px;">ПОДКЛЮЧЕНИЕ</div><div style="font-family:\'JetBrains Mono\';font-size:10.5px;color:#C9CDD1;background:#0A0B0D;border:1px solid rgba(255,255,255,.08);border-radius:9px;padding:9px 10px;">—</div></div>',
  ],
  [
    /<input placeholder="Api-Key из Tribute → Настройки → API" style="flex:1;min-width:200px;background:#0D0E11[^>]*><div style="background:linear-gradient\(135deg,#C084FC,#F0A8C8\);color:#1a0a1c;font-weight:800;font-size:12.5px;border-radius:10px;padding:11px 16px;text-align:center;cursor:pointer;white-space:nowrap;" style-hover="filter:brightness\(1.08\);">Добавить Tribute<\/div>/,
    '<input data-mm-conn-tribute-key placeholder="Api-Key из Tribute → Настройки → API" style="flex:1;min-width:200px;background:#0D0E11;border:1px solid rgba(255,255,255,.09);border-radius:9px;padding:10px 11px;color:#F2F3F0;font-family:\'JetBrains Mono\';font-size:12px;outline:none;"><div data-mm-conn-tribute-save style="background:linear-gradient(135deg,#C084FC,#F0A8C8);color:#1a0a1c;font-weight:800;font-size:12.5px;border-radius:10px;padding:11px 16px;text-align:center;cursor:pointer;white-space:nowrap;" style-hover="filter:brightness(1.08);">Добавить Tribute</div>',
  ],
  [
    /<input placeholder="Например: Mia Tribute" style="width:100%;background:#0D0E11/,
    '<input data-mm-conn-tribute-label placeholder="Например: Mia Tribute" style="width:100%;background:#0D0E11',
  ],
  [
    /<div><div style="font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1.2px;color:#6B7076;margin-bottom:6px;">МОДЕЛЬ \(НОВОЕ ПОДКЛЮЧЕНИЕ\)<\/div><select style="width:100%;background:#0D0E11;color:#F2F3F0;border:1px solid rgba\(255,255,255,.09\);border-radius:9px;padding:10px 11px;font-family:'Manrope';font-size:12.5px;outline:none;"><option>Не назначена<\/option><option>Mia<\/option><option>Ruby<\/option><\/select><\/div><div data-mm-conn-fanvue-oauth/,
    '<div><div style="font-family:\'JetBrains Mono\';font-size:8.5px;letter-spacing:1.2px;color:#6B7076;margin-bottom:6px;">МОДЕЛЬ (НОВОЕ ПОДКЛЮЧЕНИЕ)</div><select data-mm-conn-fv-model style="width:100%;background:#0D0E11;color:#F2F3F0;border:1px solid rgba(255,255,255,.09);border-radius:9px;padding:10px 11px;font-family:\'Manrope\';font-size:12.5px;outline:none;"><option value="">Не назначена</option></select></div><div data-mm-conn-fanvue-oauth',
  ],
  [
    /<div><div style="font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1.2px;color:#6B7076;margin-bottom:6px;">МОДЕЛЬ<\/div><select style="width:100%;background:#0D0E11;color:#F2F3F0;border:1px solid rgba\(255,255,255,.09\);border-radius:9px;padding:10px 11px;font-family:'Manrope';font-size:12.5px;outline:none;"><option>Не назначена<\/option><option>Mia<\/option><\/select><\/div>\s*<div style="grid-column:1 \/ -1;"><div style="font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1.2px;color:#6B7076;margin-bottom:6px;">API-КЛЮЧ TRIBUTE<\/div>/,
    '<div><div style="font-family:\'JetBrains Mono\';font-size:8.5px;letter-spacing:1.2px;color:#6B7076;margin-bottom:6px;">МОДЕЛЬ</div><select data-mm-conn-tribute-model style="width:100%;background:#0D0E11;color:#F2F3F0;border:1px solid rgba(255,255,255,.09);border-radius:9px;padding:10px 11px;font-family:\'Manrope\';font-size:12.5px;outline:none;"><option value="">Не назначена</option></select></div><div style="grid-column:1 / -1;"><div style="font-family:\'JetBrains Mono\';font-size:8.5px;letter-spacing:1.2px;color:#6B7076;margin-bottom:6px;">API-КЛЮЧ TRIBUTE</div>',
  ],
  [
    /<div style="font-family:'JetBrains Mono';font-size:9.5px;letter-spacing:1.8px;color:#6B7076;margin-bottom:8px;">\{\{ t\.quality \}\}<\/div>\s*<div style="display:flex;gap:6px;">\s*<span style="font-family:'JetBrains Mono';font-size:11px;border:1px solid rgba\(255,255,255,.12\);color:#9BA0A6;padding:5px 14px;border-radius:8px;cursor:pointer;" style-hover="border-color:rgba\(255,255,255,.3\);">480p<\/span>\s*<span style="font-family:'JetBrains Mono';font-size:11px;background:rgba\(215,244,82,.12\);color:#D7F452;border:1px solid rgba\(215,244,82,.4\);padding:5px 14px;border-radius:8px;cursor:pointer;">720p<\/span>\s*<span style="font-family:'JetBrains Mono';font-size:11px;border:1px solid rgba\(255,255,255,.12\);color:#9BA0A6;padding:5px 14px;border-radius:8px;cursor:pointer;" style-hover="border-color:rgba\(255,255,255,.3\);">1080p<\/span>\s*<\/div>/,
    '<div style="font-family:\'JetBrains Mono\';font-size:9.5px;letter-spacing:1.8px;color:#6B7076;margin-bottom:8px;">{{ t.quality }}</div><div style="display:flex;gap:6px;flex-wrap:wrap;"><sc-for list="{{ videoQualityChips }}" as="vq"><span onClick="{{ vq.pick }}" style="{{ vq.style }}" style-hover="border-color:rgba(255,255,255,.3);">{{ vq.label }}</span></sc-for></div>',
  ],
  [
    /<div style="font-family:'JetBrains Mono';font-size:9.5px;letter-spacing:1.8px;color:#6B7076;margin-bottom:8px;">\{\{ t\.vidFormat \}\}<\/div>\s*<div style="display:flex;gap:6px;flex-wrap:wrap;">\s*<span style="font-family:'JetBrains Mono';font-size:11px;background:rgba\(215,244,82,.12\);color:#D7F452;border:1px solid rgba\(215,244,82,.4\);padding:5px 14px;border-radius:8px;cursor:pointer;">9:16<\/span>/,
    '<div style="font-family:\'JetBrains Mono\';font-size:9.5px;letter-spacing:1.8px;color:#6B7076;margin-bottom:8px;">{{ t.vidFormat }}</div><div style="display:flex;gap:6px;flex-wrap:wrap;"><sc-for list="{{ videoRatioChips }}" as="vr"><span onClick="{{ vr.pick }}" style="{{ vr.style }}" style-hover="border-color:rgba(255,255,255,.3);">{{ vr.label }}</span></sc-for><span style="display:none;font-family:\'JetBrains Mono\';font-size:11px;background:rgba(215,244,82,.12);color:#D7F452;border:1px solid rgba(215,244,82,.4);padding:5px 14px;border-radius:8px;cursor:pointer;">9:16</span>',
  ],
]
for (const [from, to] of FULL_API_PATCHES) {
  const next = html.replace(from, to)
  if (next === html) console.warn('full-api patch skipped:', String(from).slice(0, 50))
  html = next
}

html = html.replace(
  /(<div onClick="\{\{ toggleLang \}\}" style="font-family:'JetBrains Mono';font-size:10px;font-weight:600;border:1px solid rgba\(255,255,255,.14\);border-radius:7px;padding:4px 8px;cursor:pointer;color:#9BA0A6;" style-hover="color:#F2F3F0;border-color:rgba\(255,255,255,.3\);">\{\{ langLabel \}\}<\/div>)/,
  '$1<div data-mm-logout onClick="{{ logout }}" style="font-family:\'JetBrains Mono\';font-size:10px;font-weight:600;border:1px solid rgba(248,113,113,.35);border-radius:7px;padding:4px 8px;cursor:pointer;color:#F87171;" style-hover="background:rgba(248,113,113,.1);">Выйти</div>',
)

// подчистить артефакты старых патчей
html = html.replace(/<\/\/div>/g, '</div>').replace(/<\/\/span>/g, '</span>')

fs.writeFileSync(indexPath, html)
console.log('patched index.html (API bridge + bindings)')

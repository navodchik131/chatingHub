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
    <p>Войдите тем же аккаунтом, что и в текущем кабинете.</p>
    <label for="mm-os-auth-email">Email</label>
    <input id="mm-os-auth-email" type="email" autocomplete="username" required>
    <label for="mm-os-auth-pass">Пароль</label>
    <input id="mm-os-auth-pass" type="password" autocomplete="current-password" required>
    <label for="mm-os-auth-member">Логин оператора (необязательно)</label>
    <input id="mm-os-auth-member" type="text" autocomplete="username">
    <div id="mm-os-auth-err" class="mm-os-auth-err"></div>
    <button id="mm-os-auth-submit" type="submit" class="mm-os-auth-submit">Войти</button>
  </form>
</div>`

/** Подстановки в шаблон: хардкод макета → биндинги API */
const TEMPLATE_PATCHES = [
  [
    /<script src="\.\/support\.js"><\/script>/,
    `<link rel="stylesheet" href="./mm-os-auth.css">
<script src="./mm-os-api.js"></script>
<script src="./mm-os-bridge.js"></script>
<script src="./mm-os-api-full.js"></script>
<script src="./support.js"></script>`,
  ],
  [
    /<body>/,
    `<body>${AUTH_OVERLAY}`,
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
  // кнопки действий
  [
    /<div style="display:flex;align-items:center;gap:12px;background:#D7F452;border-radius:12px;padding:12px 16px;cursor:pointer;" style-hover="background:#E8FA8A;">\s*<span style="display:flex;width:17px;height:17px;color:#171A05;" dangerouslySetInnerHTML="{{ icoSpark }}"><\/span>\s*<span style="flex:1;font-weight:800;font-size:14px;color:#171A05;">{{ t\.generate }}<\/span>/,
    `<div onClick="{{ runGenerate }}" style="display:flex;align-items:center;gap:12px;background:#D7F452;border-radius:12px;padding:12px 16px;cursor:pointer;" style-hover="background:#E8FA8A;">
              <span style="display:flex;width:17px;height:17px;color:#171A05;" dangerouslySetInnerHTML="{{ icoSpark }}"></span>
              <span style="flex:1;font-weight:800;font-size:14px;color:#171A05;">{{ t.generate }}</span>`,
  ],
  [
    /<div style="background:#D7F452;color:#171A05;font-weight:800;font-size:12\.5px;border-radius:10px;padding:10px 16px;cursor:pointer;" style-hover="background:#E8FA8A;">{{ t\.send }}<\/div>/,
    `<div onClick="{{ sendReply }}" style="background:#D7F452;color:#171A05;font-weight:800;font-size:12.5px;border-radius:10px;padding:10px 16px;cursor:pointer;" style-hover="background:#E8FA8A;">{{ t.send }}</div>`,
  ],
  [
    /<div style="display:flex;align-items:center;gap:10px;background:#D7F452;border-radius:11px;padding:11px 16px;cursor:pointer;" style-hover="background:#E8FA8A;">\s*<span style="display:flex;width:16px;height:16px;color:#171A05;" dangerouslySetInnerHTML="\{\{ icoDownload \}\}"><\/span>\s*<span style="flex:1;font-weight:800;font-size:13px;color:#171A05;">\{\{ t\.download \}\}<\/span>/,
    '<div onClick="{{ downloadLightbox }}" style="display:flex;align-items:center;gap:10px;background:#D7F452;border-radius:11px;padding:11px 16px;cursor:pointer;" style-hover="background:#E8FA8A;"><span style="display:flex;width:16px;height:16px;color:#171A05;" dangerouslySetInnerHTML="{{ icoDownload }}"></span><span style="flex:1;font-weight:800;font-size:13px;color:#171A05;">{{ t.download }}</span>',
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
    /<div style="flex:1;aspect-ratio:3\/4;border:1\.5px dashed rgba\(255,255,255,.18\);border-radius:12px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;cursor:pointer;" style-hover="border-color:rgba\(215,244,82,.5\);background:rgba\(215,244,82,.03\);">\s*<span style="display:flex;width:20px;height:20px;color:#6B7076;" dangerouslySetInnerHTML="\{\{ icoUpload \}\}"><\/span>/,
    `<div data-mm-upload="ref" style="flex:1;aspect-ratio:3/4;border:1.5px dashed rgba(255,255,255,.18);border-radius:12px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;cursor:pointer;" style-hover="border-color:rgba(215,244,82,.5);background:rgba(215,244,82,.03);">
                  <span style="display:flex;width:20px;height:20px;color:#6B7076;" dangerouslySetInnerHTML="{{ icoUpload }}"></span>`,
  ],
  [
    /<div style="aspect-ratio:16\/8;border:1\.5px dashed rgba\(255,255,255,.18\);border-radius:12px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;cursor:pointer;" style-hover="border-color:rgba\(215,244,82,.5\);background:rgba\(215,244,82,.03\);">\s*<span style="display:flex;width:26px;height:26px;color:#6B7076;" dangerouslySetInnerHTML="\{\{ icoVid \}\}"><\/span>/,
    `<div data-mm-upload="motion-video" style="aspect-ratio:16/8;border:1.5px dashed rgba(255,255,255,.18);border-radius:12px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;cursor:pointer;" style-hover="border-color:rgba(215,244,82,.5);background:rgba(215,244,82,.03);">
                <span style="display:flex;width:26px;height:26px;color:#6B7076;" dangerouslySetInnerHTML="{{ icoVid }}"></span>`,
  ],
  [
    /<div style="width:96px;flex:none;aspect-ratio:3\/4;border:1\.5px dashed rgba\(255,255,255,.18\);border-radius:12px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;cursor:pointer;" style-hover="border-color:rgba\(215,244,82,.5\);background:rgba\(215,244,82,.03\);">\s*<span style="display:flex;width:20px;height:20px;color:#6B7076;" dangerouslySetInnerHTML="\{\{ icoUpload \}\}"><\/span>/,
    `<div data-mm-upload="motion-frame" style="width:96px;flex:none;aspect-ratio:3/4;border:1.5px dashed rgba(255,255,255,.18);border-radius:12px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;cursor:pointer;" style-hover="border-color:rgba(215,244,82,.5);background:rgba(215,244,82,.03);">
                  <span style="display:flex;width:20px;height:20px;color:#6B7076;" dangerouslySetInnerHTML="{{ icoUpload }}"></span>`,
  ],
  [
    /<div style="aspect-ratio:16\/7;border:1\.5px dashed rgba\(255,255,255,.18\);border-radius:12px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;cursor:pointer;" style-hover="border-color:rgba\(215,244,82,.5\);background:rgba\(215,244,82,.03\);">\s*<span style="display:flex;width:22px;height:22px;color:#6B7076;" dangerouslySetInnerHTML="\{\{ icoUpload \}\}"><\/span>/,
    `<div data-mm-upload="carousel" style="aspect-ratio:16/7;border:1.5px dashed rgba(255,255,255,.18);border-radius:12px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;cursor:pointer;" style-hover="border-color:rgba(215,244,82,.5);background:rgba(215,244,82,.03);">
              <span style="display:flex;width:22px;height:22px;color:#6B7076;" dangerouslySetInnerHTML="{{ icoUpload }}"></span>`,
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
    /<div style="aspect-ratio:3\/4;border:1\.5px dashed rgba\(255,255,255,.18\);border-radius:10px;display:flex;align-items:center;justify-content:center;color:#6B7076;font-size:20px;cursor:pointer;" style-hover="border-color:rgba\(215,244,82,.5\);">\+<\/div>/,
    `<div data-mm-upload="char-photo" style="aspect-ratio:3/4;border:1.5px dashed rgba(255,255,255,.18);border-radius:10px;display:flex;align-items:center;justify-content:center;color:#6B7076;font-size:20px;cursor:pointer;" style-hover="border-color:rgba(215,244,82,.5);">+</div>`,
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
    /<span style="font-size:11px;font-weight:700;border:1px solid rgba\(255,255,255,.12\);color:#9BA0A6;padding:5px 12px;border-radius:8px;cursor:pointer;" style-hover="border-color:rgba\(215,244,82,.5\);color:#D7F452;">\{\{ pt \}\}<\/span>/,
    `<span onClick="{{ pt.pick }}" style="{{ pt.style }}" style-hover="border-color:rgba(215,244,82,.5);color:#D7F452;">{{ pt.label }}</span>`,
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
    /<div style="display:flex;gap:8px;"><div style="flex:1;background:rgba\(215,244,82,.12\);border:1px solid rgba\(215,244,82,.3\);border-radius:9px;padding:10px;text-align:center;font-size:12px;font-weight:800;color:#D7F452;cursor:pointer;">\{\{ t\.save \}\}<\/div><\/div>\s*<\/div>\s*<\/sc-if>/,
    `<div style="display:flex;gap:8px;"><div data-mm-char-persona-save style="flex:1;background:rgba(215,244,82,.12);border:1px solid rgba(215,244,82,.3);border-radius:9px;padding:10px;text-align:center;font-size:12px;font-weight:800;color:#D7F452;cursor:pointer;">{{ t.save }}</div></div>
          </div>
          </sc-if>`,
  ],
]

const LOGIC_PATCHES = [
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
      dialogsUnreadLabel: '', planDisplayName: '—', planUntil: '—', dialogsTotal: '0', teamRepliesCount: '0',
      creditsFramesHint: '', activeChat: { name: '—', initial: '?', vip: false, persona: '—', lang: '—', avStyle: '' },
      notesTitle: '', activeCharName: '—', activeCharInitial: '—',
      charPhotos: [], photoTagList: [], charHistory: [],
      runGenerate: () => {}, runGenerateVideo: () => {}, sendReply: () => {}, logout: () => {},
      apiError: null, apiBusy: false, canChat: true, canStudio: true, canBilling: true,
      referralLink: '—', referralStats: '—', dialogsPlatformLine: '—', userSidebarInitial: 'R',
      payoutHint: '—', videoQualityChips: [], videoDurationChips: [], videoRatioChips: [],
    };
    return (window.MMOS_BRIDGE ? window.MMOS_BRIDGE.enrich(this, __dcVals) : __dcVals);
  }`,
  ],
]

const indexPath = path.join(osRoot, 'index.html')
let html = fs.readFileSync(indexPath, 'utf8')

for (const [from, to] of TEMPLATE_PATCHES) {
  const next = html.replace(from, to)
  if (next === html) console.warn('template patch skipped:', String(from).slice(0, 60))
  html = next
}

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
    '<div data-mm-note-add style="flex:1;background:rgba(215,244,82,.12);border:1px solid rgba(215,244,82,.3);border-radius:9px;padding:7px;text-align:center;font-size:11.5px;font-weight:700;color:#D7F452;cursor:pointer;" style-hover="background:rgba(215,244,82,.2);">+ {{ t.addNote }}</div>',
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
    /<div style="display:flex;align-items:center;gap:8px;background:#D7F452;color:#171A05;font-weight:800;font-size:13px;border-radius:10px;padding:10px 16px;cursor:pointer;" style-hover="background:#E8FA8A;">\+ \{\{ t\.addOperator \}\}<\/div>/,
    '<div data-mm-team-add style="display:flex;align-items:center;gap:8px;background:#D7F452;color:#171A05;font-weight:800;font-size:13px;border-radius:10px;padding:10px 16px;cursor:pointer;" style-hover="background:#E8FA8A;">+ {{ t.addOperator }}</div>',
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

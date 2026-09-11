# ModelMate Unibox — desktop (Tauri)

Обёртка над `https://chat.model-mate.online` (или `/chat/` на основном домене).

## Требования

- [Rust](https://rustup.rs/)
- Node.js 22+
- Windows: WebView2 (обычно уже есть в Win10/11)

## Сборка

```bash
cd frontend/chat-desktop
npm install
npm run tauri build
```

Dev-режим (hot reload окна):

```bash
npm run tauri dev
```

## URL

По умолчанию открывается `https://chat.model-mate.online/`.  
Локально можно задать `UNIBOX_URL=http://127.0.0.1:5174/` в `src-tauri/tauri.conf.json`.

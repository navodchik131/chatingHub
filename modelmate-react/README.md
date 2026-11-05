# ModelMate OS — React

React-реализация дизайна `ModelMate OS.dc.html` из handoff-бандла Claude Design.

Прототип был на HTML/CSS/JS с шаблонизатором `x-dc` (`<sc-if>`, `<sc-for>`, `style-hover`).
Здесь он пересобран на React — визуальный результат совпадает 1:1, внутренняя структура
переписана под нормальную компонентную архитектуру.

## Запуск

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # прод-сборка в dist/
npm run preview  # просмотр прод-сборки
```

## Тесты

```bash
npm test            # 51 smoke-тест: все страницы × 2 языка × 2 вьюпорта
npm run test:fidelity  # 68 проверок контента и интерактива
```

Тесты монтируют приложение в JSDOM, обходят все экраны и состояния и падают на любом
React-warning'е. `fidelity` дополнительно кликает по интерфейсу и проверяет, что
переключение языка, валидация, вкладки и навигация реально работают.

## Структура

```
src/
├── App.jsx              # шелл: layout + роутинг по state.page
├── main.jsx
├── hooks/
│   └── useApp.jsx       # контекст-стор: state, setS, go(), t, брейкпоинты
├── components/
│   ├── Hoverable.jsx    # замена style-hover из прототипа
│   ├── Icons.jsx        # 30 SVG-иконок (из фабрики I() прототипа)
│   ├── Sidebar.jsx
│   ├── MobileNav.jsx    # топбар, таббар, "Ещё"-шит
│   └── ui.jsx           # Panel, Chip, Field, Avatar, Overlay, Toggle…
├── pages/               # по файлу на экран
│   ├── Overview.jsx     ├── Dialogs.jsx    ├── Images.jsx
│   ├── Guide.jsx        ├── Video.jsx      ├── Characters.jsx
│   ├── Donations.jsx    ├── Billing.jsx    ├── Connections.jsx
│   ├── Team.jsx         └── Workflow.jsx
├── data/
│   ├── i18n.js          # RU/EN словари (перенесены дословно)
│   ├── mock.js          # демо-данные
│   ├── catalog.js       # режимы студии, гайд, подключения
│   └── nav.js           # конфиг навигации
└── styles/
    ├── tokens.js        # цвета, шрифты, градиенты
    ├── mixins.js        # переиспользуемые стили
    └── global.css       # из <helmet> прототипа
```

## Как переносился дизайн

| Прототип | React |
|---|---|
| `<sc-if value="{{ x }}">` | `{x && <…/>}` |
| `<sc-for list="{{ xs }}" as="x">` | `xs.map(x => …)` |
| `style-hover="…"` | `<Hoverable hover={{…}}>` |
| `renderVals()` — один метод на всё | стор + локальные хуки |
| `this.I(paths)` + `dangerouslySetInnerHTML` | компоненты в `Icons.jsx` |
| строки внутри разметки | `data/i18n.js` |

Все цвета, размеры и отступы вынесены в `styles/tokens.js` и взяты из прототипа
дословно — новых значений не придумывалось.

## Состояние

Один стор (`useApp`) повторяет `state` прототипа: `page`, `lang`, `imgMode`,
`chatOpen`, `ffState`, `opRights` и т.д. `setS(patch)` = `setState`, `go(page)`
переключает экран и сбрасывает detail-виды.

Для реального приложения: заменить `data/mock.js` на вызовы API, а `page` — на
роутер (React Router), состояние экранов при этом не меняется.

## Что осталось демо-заглушками (как в прототипе)

- Кадры и видео — CSS-градиенты вместо реальных картинок.
- Формы неуправляемые (`defaultValue`), сабмита нет.
- Валидация в студии срабатывает по клику на «Сгенерировать» — как в прототипе.
- «Сгенерировать первый кадр» — таймер на 2.2 c, имитирует загрузку.
- Данные (диалоги, персонажи, транзакции) захардкожены.

## Доступность

Добавлено сверх прототипа: видимый focus-ring, поддержка Enter/Space на кликабельных
элементах, `aria-label` на иконочных кнопках, `prefers-reduced-motion`.

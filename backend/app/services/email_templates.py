"""Готовые шаблоны для маркетинговых рассылок из админки."""

from __future__ import annotations

EMAIL_TEMPLATES: dict[str, dict[str, str]] = {
    "product_update": {
        "name": "Обновление продукта",
        "subject": "ModelMate — большое обновление: workflow и бесплатные демо",
        "body_html": """
<p>Здравствуйте!</p>
<p>Мы выпустили большое обновление ModelMate:</p>
<ul>
  <li><strong>Workflow</strong> — визуальный конструктор генераций</li>
  <li><strong>3 бесплатные демо-генерации</strong> для новых пользователей на тарифе Credits</li>
  <li>Улучшенный визард первой генерации</li>
</ul>
<p>Попробуйте прямо сейчас: <a href="{{app_url}}/workspace">{{app_url}}/workspace</a></p>
<p style="color:#888;font-size:12px;margin-top:2em;">{{unsubscribe_hint}}</p>
""".strip(),
        "body_text": """
Здравствуйте!

Мы выпустили большое обновление ModelMate:
- Workflow — визуальный конструктор генераций
- 3 бесплатные демо-генерации для новых пользователей
- Улучшенный визард первой генерации

Откройте кабинет: {{app_url}}/workspace

{{unsubscribe_hint}}
""".strip(),
    },
    "nudge_no_generation": {
        "name": "Напоминание: попробуйте генерацию",
        "subject": "ModelMate — 3 бесплатные генерации ждут вас",
        "body_html": """
<p>Здравствуйте!</p>
<p>Вы зарегистрировались в ModelMate, но ещё не пробовали студию генерации.</p>
<p>У вас есть <strong>бесплатные демо-генерации</strong> — создайте первую модель и сгенерируйте фото за пару минут.</p>
<p><a href="{{app_url}}/workspace">Открыть кабинет →</a></p>
<p style="color:#888;font-size:12px;margin-top:2em;">{{unsubscribe_hint}}</p>
""".strip(),
        "body_text": """
Здравствуйте!

Вы зарегистрировались в ModelMate, но ещё не пробовали студию.

У вас есть бесплатные демо-генерации — откройте кабинет: {{app_url}}/workspace

{{unsubscribe_hint}}
""".strip(),
    },
}


def list_email_templates() -> list[dict[str, str]]:
    return [
        {
            "id": tid,
            "name": t["name"],
            "subject": t["subject"],
            "body_html": t["body_html"],
            "body_text": t.get("body_text", ""),
        }
        for tid, t in EMAIL_TEMPLATES.items()
    ]

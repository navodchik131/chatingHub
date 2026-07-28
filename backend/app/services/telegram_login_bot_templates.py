"""Шаблоны рассылок login-бота."""

from __future__ import annotations

from app.config import settings


def _channel_url() -> str:
    return (settings.telegram_login_news_channel_url or "").strip() or "https://t.me/ModelMate_app"


def _channel_label() -> str:
    return (settings.telegram_login_news_channel_label or "").strip() or "ModelMate"


def _bot_url() -> str:
    username = (settings.telegram_login_bot_username or "").strip().lstrip("@")
    if not username:
        return "https://t.me/"
    return f"https://t.me/{username}"


LOGIN_BOT_TEMPLATES: dict[str, dict[str, str]] = {
    "channel_invite": {
        "name": "Приглашение в канал",
        "text": (
            "📢 Новости и обновления ModelMate — в нашем Telegram-канале.\n\n"
            "Подписывайтесь: {channel_url}"
        ),
    },
    "app_update": {
        "name": "Обновление приложения",
        "text": (
            "✨ Вышло обновление ModelMate!\n\n"
            "Откройте приложение и попробуйте новые функции. "
            "Подробности — в канале: {channel_url}"
        ),
    },
    "welcome_back": {
        "name": "Вернуться в кабинет",
        "text": (
            "👋 Давно не заходили в ModelMate?\n\n"
            "Войдите через бота и продолжите работу с вашими моделями и генерациями.\n\n"
            "→ {bot_url}"
        ),
    },
    "feature_studio": {
        "name": "Студия / workflow",
        "text": (
            "🎬 В ModelMate Studio можно собирать сцены и workflow за пару кликов.\n\n"
            "Зайдите в кабинет и попробуйте — {channel_url}"
        ),
    },
}


def render_login_bot_template(template_id: str) -> str | None:
    tpl = LOGIN_BOT_TEMPLATES.get(template_id.strip())
    if not tpl:
        return None
    return tpl["text"].format(
        channel_url=_channel_url(),
        channel_label=_channel_label(),
        bot_url=_bot_url(),
    )


def list_login_bot_templates() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for tid, tpl in LOGIN_BOT_TEMPLATES.items():
        out.append(
            {
                "id": tid,
                "name": tpl["name"],
                "text": render_login_bot_template(tid) or tpl["text"],
            }
        )
    return out

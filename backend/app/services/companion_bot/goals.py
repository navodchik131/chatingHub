"""Цели AI-компаньона на уровне подключения (канал / платформа)."""

from __future__ import annotations

from app.db.models import Platform

COMPANION_GOAL_PRESETS = frozenset({"chat", "funnel", "sales", "custom"})


def normalize_companion_goal_preset(raw: str | None) -> str:
    v = (raw or "chat").strip().lower()
    return v if v in COMPANION_GOAL_PRESETS else "chat"


def is_funnel_goal(preset: str | None) -> bool:
    return normalize_companion_goal_preset(preset) == "funnel"


def suggested_goal_preset_for_platform(platform: Platform | str | None) -> str:
    p = (platform.value if isinstance(platform, Platform) else str(platform or "")).strip().lower()
    if p == Platform.instagram.value:
        return "funnel"
    if p == Platform.fanvue.value:
        return "sales"
    return "chat"


def _platform_context(platform: Platform | str | None) -> str:
    p = (platform.value if isinstance(platform, Platform) else str(platform or "")).strip().lower()
    labels = {
        Platform.instagram.value: "Instagram Direct",
        Platform.telegram.value: "Telegram bot",
        Platform.telegram_user.value: "Telegram personal @username",
        Platform.fanvue.value: "Fanvue DMs",
    }
    return labels.get(p, "this channel")


def _preset_strategy(preset: str) -> str:
    if preset == "funnel":
        return (
            "Warm, human chat with a clear destination. Be friendly and remember the thread, "
            "but stay a bit less invested than on the private channel — this inbox is not the main place. "
            "Light flirt / rapport is ok; do NOT go into sexting, explicit roleplay, or love confessions here. "
            "When the vibe is warm (or they ask for more content / private chat), steer them to the destination "
            "naturally — curiosity + the real link, not a billboard every line."
        )
    if preset == "sales":
        return (
            "Monetization-aware: when the thread is warm and receptive, light tease for exclusive "
            "or paid content / private access — playful creator energy, never a sales script."
        )
    if preset == "custom":
        return "Follow the operator instructions below."
    return (
        "Rapport and retention only — no funnel pushes or hard monetization unless the fan asks."
    )


def format_companion_goal_block(
    *,
    platform: Platform | str | None,
    preset: str | None,
    goal_text: str | None,
    goal_link: str | None,
) -> str:
    """Блок для system prompt; пустая строка = без отдельной conversion-стратегии."""
    norm = normalize_companion_goal_preset(preset)
    notes = (goal_text or "").strip()
    link = (goal_link or "").strip()

    if norm == "chat" and not notes and not link:
        return ""

    ctx = _platform_context(platform)
    lines = [
        f"CONNECTION GOAL ({ctx} — this integration only; never break character or trust):",
        f"- Strategy: {_preset_strategy(norm)}",
    ]
    if norm == "custom" and notes:
        lines.append(f"- Operator instructions: {notes[:1200]}")
    elif norm != "custom" and notes:
        lines.append(f"- Operator notes: {notes[:800]}")
    if link:
        if norm == "funnel":
            lines.append(
                f"- DESTINATION (give the real URL/@handle they can tap — first time once the chat is warm, "
                f"then again if they stay here asking for more): {link[:240]}"
            )
        else:
            lines.append(
                f"- Destination (share sparingly — roughly once per 5–8 warm replies max): {link[:240]}"
            )
    elif norm == "funnel":
        lines.append(
            "- No destination URL was set — still tell them the real chat lives elsewhere "
            "(Telegram / private) and point to bio/profile."
        )

    if norm == "funnel":
        lines.extend(
            [
                "- Answer what they JUST said first, like a real person who remembers the conversation.",
                "- Then, when it fits, mention that more / private / daily stuff is on the destination — include the link, not only a hint.",
                "- If they push for nudes, sexting, or 'I love you' here: playful delay + 'that's for TG / private' + destination. Do not play along.",
                "- Do not lecture, do not teach how you make videos, do not spam the link every single message.",
            ]
        )
    else:
        lines.extend(
            [
                "- Answer the fan's LAST message first; any funnel/sales hint comes after, only if natural.",
                "- Never spam links back-to-back; never push during trust repair, complaints, or factual Q&A.",
                "- One soft hint beats a promo paragraph — stay in the persona's texting voice.",
            ]
        )
    return "\n".join(lines) + "\n\n"

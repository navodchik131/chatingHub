"""Правила генерации агента (Persona Studio): список запретов, редактируется в админке.

Пустая таблица заполняется правилами по умолчанию при первом обращении. Базовые правила (locked)
нельзя выключить, удалить или ослабить — их текст для моделей всегда берётся из кода.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentContentRule

DEFAULT_RULES: list[dict[str, Any]] = [
    {
        "code": "minors", "locked": True, "sort": 10,
        "title": "Никаких несовершеннолетних: все люди в кадре — взрослые 18+ и выглядят взрослыми. "
                 "Не генерировать детей и подростков, не делать модель моложе, не использовать детские черты, одежду и обстановку в откровенных кадрах.",
        "prompt_zh": "画面中所有人物都是成年人（18岁以上），外表明显是成年人；不能出现任何未成年人、儿童或少女的样子，不要把她画得更年轻。",
        "prompt_en": "Everyone in the image is a clearly adult person (18+); no minors, no childlike or teen appearance, do not make her look younger.",
    },
    {
        "code": "real_people", "locked": True, "sort": 20,
        "title": "Без реальных людей: лицо только вымышленной модели из эталонов. Не делать узнаваемых знаменитостей и реальных людей, "
                 "не переносить на модель лицо девушки с исходника.",
        "prompt_zh": "人物的脸只取自模特参考图，不要生成任何真实名人或可识别的真实人物的脸。",
        "prompt_en": "Her face comes only from the model reference images; do not depict any celebrity or identifiable real person.",
    },
    {
        "code": "nudity", "locked": False, "sort": 30,
        "title": "Без наготы: грудь и интимные зоны всегда закрыты тканью. «Сними/убери одежду» — снять верхнюю вещь или переодеть в бельё или купальник, "
                 "полностью раздетой не делать.",
        "prompt_zh": "胸部和私处必须被布料完全遮住：不能露出乳头和私处，不能全裸。",
        "prompt_en": "Breasts and intimate areas stay fully covered by fabric; no nudity.",
    },
    {
        "code": "sexual_acts", "locked": False, "sort": 40,
        "title": "Без сексуальных действий и порнографии: только позирование, без половых актов и имитации, без второго человека в интимной сцене.",
        "prompt_zh": "没有任何性行为或色情动作，只是普通的拍照姿势。",
        "prompt_en": "No sexual acts or pornographic poses, only ordinary photo posing.",
    },
    {
        "code": "violence", "locked": False, "sort": 50,
        "title": "Без насилия и крови: никаких ран, крови, увечий, оружия, направленного на человека.",
        "prompt_zh": "画面里没有血、伤口或暴力，没有指向人的武器。",
        "prompt_en": "No blood, wounds or violence, no weapons pointed at anyone.",
    },
    {
        "code": "hate", "locked": False, "sort": 60,
        "title": "Без символики ненависти и экстремизма: нацистская и экстремистская символика, оскорбительные надписи.",
        "prompt_zh": "画面里没有纳粹、极端主义或仇恨符号和侮辱性文字。",
        "prompt_en": "No Nazi, extremist or hate symbols and no offensive text.",
    },
    {
        "code": "drugs", "locked": False, "sort": 70,
        "title": "Без наркотиков: не показывать употребление наркотиков и их атрибуты.",
        "prompt_zh": "画面里没有毒品或吸毒用具。",
        "prompt_en": "No drugs or drug paraphernalia.",
    },
    {
        "code": "self_harm", "locked": False, "sort": 80,
        "title": "Без самоповреждений и пропаганды суицида.",
        "prompt_zh": "画面里没有自残或自杀的内容。",
        "prompt_en": "No self-harm or suicide imagery.",
    },
]
LOCKED = {r["code"]: r for r in DEFAULT_RULES if r["locked"]}


async def ensure_defaults(session: AsyncSession) -> None:
    """Пустая таблица → правила по умолчанию; базовые правила всегда есть, включены и с исходным текстом."""
    rows = list((await session.scalars(select(AgentContentRule))).all())
    by_code = {r.code: r for r in rows if r.code}
    changed = False
    seeds = DEFAULT_RULES if not rows else list(LOCKED.values())
    for d in seeds:
        r = by_code.get(d["code"])
        if r is None:
            session.add(AgentContentRule(**d, enabled=True))
            changed = True
        elif d["locked"] and (not r.enabled or not r.locked or r.title != d["title"]
                              or r.prompt_zh != d["prompt_zh"] or r.prompt_en != d["prompt_en"]):
            r.enabled, r.locked = True, True
            r.title, r.prompt_zh, r.prompt_en = d["title"], d["prompt_zh"], d["prompt_en"]
            changed = True
    if changed:
        await session.commit()


async def list_rules(session: AsyncSession, *, only_enabled: bool = False) -> list[AgentContentRule]:
    await ensure_defaults(session)
    q = select(AgentContentRule).order_by(AgentContentRule.sort, AgentContentRule.id)
    if only_enabled:
        q = q.where(AgentContentRule.enabled.is_(True))
    return list((await session.scalars(q)).all())


def rule_out(r: AgentContentRule) -> dict[str, Any]:
    return {"id": r.id, "code": r.code, "title": r.title, "prompt_zh": r.prompt_zh or "", "prompt_en": r.prompt_en or "",
            "enabled": bool(r.enabled), "locked": bool(r.locked), "sort": r.sort,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None}


def defaults_for_agent() -> list[dict[str, str]]:
    return [{"title": d["title"], "prompt_zh": d["prompt_zh"], "prompt_en": d["prompt_en"]} for d in DEFAULT_RULES]

"""Remove brandfix from RU presentation and build EN copy."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RU = ROOT / "frontend/public/about-service.html"
EN = ROOT / "frontend/public/about-service.en.html"

from about_service_en_pairs import PAIRS_EXTRA  # noqa: E402

PAIRS: list[tuple[str, str]] = [
    ('<html lang="ru">', '<html lang="en">'),
    ("<title>ModelMate — AI OFM полного цикла</title>", "<title>ModelMate — full-cycle AI OFM</title>"),
    ("анимация · ", "motion · "),
    ("'вкл'", "'on'"),
    ("'выкл'", "'off'"),
    ("Выключить движение", "Turn motion off"),
    (
        "Движение выключено — в системе включено «уменьшение движения». Нажмите, чтобы включить.",
        "Motion is off. Click to turn it back on.",
    ),
    (">Старт<", ">Start<"),
    (">Боли<", ">Pain<"),
    (">Цикл<", ">Cycle<"),
    (">Персонаж<", ">Character<"),
    (">Студия<", ">Studio<"),
    (">Диалоги<", ">Dialogs<"),
    (">Команда<", ">Team<"),
    (">Деньги<", ">Money<"),
    (">Финал<", ">End<"),
    (
        'Один цикл<br>вместо семи<br><span class="grad">вкладок</span>',
        'One cycle<br>instead of seven<br><span class="grad">tabs</span>',
    ),
    (
        "Сервис полного цикла для AI-моделей: собрать персонажа, снять кадр, оживить его в видео,\n"
        "      ответить фану на его языке и получить деньги — <b>в одном окне</b>.",
        "Full-cycle service for AI models: build a character, shoot a frame, bring it to life in video,\n"
        "      reply to fans in their language, and get paid — <b>in one window</b>.",
    ),
    ("Instagram · скоро", "Instagram · soon"),
    ("ПОЛНЫЙ ЦИКЛ", "FULL CYCLE"),
    ("БЕЗ ПЕРЕСКОКОВ", "NO TAB HOPPING"),
    (">ПЕРСОНАЖ<", ">CHARACTER<"),
    (">КАДР<", ">FRAME<"),
    (">ВИДЕО<", ">VIDEO<"),
    (">КАНАЛ<", ">CHANNEL<"),
    (">ДИАЛОГ<", ">CHAT<"),
    (">ДЕНЬГИ<", ">MONEY<"),
    (">Что болит<", ">What hurts<"),
    (
        'Работа идёт,<br>а половина времени уходит <span class="grad">не на неё</span>',
        'Work is happening,<br>but half the time goes <span class="grad">somewhere else</span>',
    ),
    (">Инструменты врозь<", ">Tools everywhere<"),
    (
        "Генерация в одной вкладке, переписка во второй, переводчик в третьей, деньги в четвёртой. "
        "Каждый переход — минуты и потерянный контекст.",
        "Generation in one tab, chat in another, translator in a third, money in a fourth. "
        "Every switch costs minutes and lost context.",
    ),
    ("→ ОДНО ОКНО", "→ ONE WINDOW"),
    (">Модель не держит лицо<", ">Face keeps changing<"),
    (
        "На каждом новом кадре чуть другие глаза и фигура. Фан листает ленту и видит трёх разных девушек — "
        "доверие рассыпается.",
        "Every new frame has slightly different eyes and body. Fans scroll the feed and see three different "
        "girls — trust breaks down.",
    ),
    ("→ ПЕРСОНАЖ С РЕФЕРЕНСАМИ", "→ CHARACTER WITH REFERENCES"),
    (">«Это же нейронка»<", ">&ldquo;That&rsquo;s AI&rdquo;<"),
    (
        "Фан просит селфи прямо сейчас, открывает свойства файла, ищет несостыковки в легенде. "
        "Голая генерация проверку не проходит.",
        "A fan asks for a selfie right now, opens file properties, hunts for plot holes. "
        "Raw generation fails the check.",
    ),
    ("→ EXIF «КАК С ТЕЛЕФОНА»", "→ EXIF &ldquo;LIKE FROM A PHONE&rdquo;"),
    (">Разные языки<", ">Different languages<"),
    (
        "Фаны из Испании, США, Бразилии. Оператор пишет по-русски и теряет темп и интонацию, "
        "пока копирует текст в переводчик.",
        "Fans from Spain, the US, Brazil. The operator writes in Russian and loses pace and tone "
        "while copying text into a translator.",
    ),
    ("→ ПЕРЕВОД В ЧАТЕ", "→ IN-CHAT TRANSLATION"),
    (">Ответ через час<", ">Reply an hour later<"),
    (
        "Диалог живёт минут пятнадцать. Ночью и в пересменок отвечать некому — фан просто уходит к другой модели.",
        "A chat stays hot for fifteen minutes. At night and between shifts nobody answers — the fan moves on.",
    ),
    ("→ AI-КОМПАНЬОН", "→ AI COMPANION"),
    (">Команда вслепую<", ">Team in the dark<"),
    (
        "Кто из операторов чем занят, кому какие модели открыты, кто сколько принёс и сколько ему платить с донатов.",
        "Who is doing what, which models each operator sees, who brought how much, and what to pay from donations.",
    ),
    ("→ ПРАВА, KPI И ДОЛЯ", "→ ROLES, KPI & SHARE"),
    (">Как устроено<", ">How it works<"),
    ("Шесть шагов, которые обычно живут в шести сервисах", "Six steps that usually live in six different tools"),
    (
        "Каждый шаг знает про предыдущий: описание внешности едет в генерацию, кадр — в видео, "
        "персонаж — в бота, диалог — в донат. Ничего не нужно копировать руками.",
        "Each step knows the previous one: looks feed generation, frames feed video, character feeds the bot, "
        "chat feeds donations. Nothing to copy by hand.",
    ),
    ("Фото-референсы, внешность, характер, легенда.", "Photo references, look, personality, backstory."),
    ("Семь режимов съёмки вместо пустого поля промпта.", "Seven shoot modes instead of an empty prompt box."),
    ("Кадр из архива оживает по референсу или описанию.", "A frame from the archive comes alive from reference or prompt."),
    ("Telegram-бот, Fanvue, Threads. Токен — и готово.", "Telegram bot, Fanvue, Threads. Paste a token — done."),
    ("Общий инбокс, перевод, досье фана, автоответчик.", "Shared inbox, translation, fan dossier, auto-reply."),
    ("Донат-ссылки, доли операторов, вывод в крипте.", "Donation links, operator shares, crypto payout."),
    (">Один аккаунт<", ">One account<"),
    ("До <b>30 персонажей</b> и безлимит операторов на старшем тарифе", "Up to <b>30 characters</b> and unlimited operators on the top plan"),
    (">Одна валюта действий<", ">One action currency<"),
    ("Кредиты: <b>1 кр = 3,6 ₽</b>, списываются только за генерации", "Credits: <b>1 cr = ₽3.6</b>, charged only for generations"),
    (">Один инбокс<", ">One inbox<"),
    ("Telegram, Fanvue, Threads и Instagram — <b>в общем списке</b>", "Telegram, Fanvue, Threads and Instagram — <b>in one list</b>"),
    ("Открыть ModelMate →", "Open ModelMate →"),
    (">Итог<", ">Summary<"),
    ('Цикл замыкается<br><span class="grad">внутри одного окна</span>', 'The loop closes<br><span class="grad">inside one window</span>'),
    (
        "Персонаж рождается в сервисе, снимается в сервисе, разговаривает с фаном в сервисе и приносит деньги туда же. "
        "Операторам остаётся работа, ради которой их наняли.",
        "Characters are born in the service, shot in the service, talk to fans in the service, and bring money back there. "
        "Operators keep the work they were hired for.",
    ),
    ("площадки в одном инбоксе", "platforms in one inbox"),
    ("режимов съёмки кадра", "frame shoot modes"),
    ("режима автоответчика", "auto-reply modes"),
    ("комиссия с донатов", "donation fee"),
]


def strip_brandfix(text: str) -> str:
    text = re.sub(r'<div class="brandfix"><i></i>ModelMate</div>\s*', "", text)
    text = re.sub(r"\.brandfix\{[^}]+\}\s*", "", text)
    text = re.sub(r"\.brandfix i\{[^}]+\}\s*", "", text)
    text = re.sub(r"\s*\.brandfix\{left:6vw;top:20px\}\s*", "\n", text)
    return text


def all_pairs() -> list[tuple[str, str]]:
    merged = PAIRS + PAIRS_EXTRA
    merged.sort(key=lambda p: len(p[0]), reverse=True)
    return merged


def main() -> None:
    ru_text = RU.read_text(encoding="utf-8")
    if 'class="brandfix"' in ru_text:
        ru_text = strip_brandfix(ru_text)
        RU.write_text(ru_text, encoding="utf-8")

    en_text = ru_text.replace('<html lang="ru">', '<html lang="en">')
    en_text = en_text.replace(
        "<title>ModelMate — AI OFM полного цикла</title>",
        "<title>ModelMate — full-cycle AI OFM</title>",
    )
    for src, dst in all_pairs():
        en_text = en_text.replace(src, dst)
    EN.write_text(en_text, encoding="utf-8")

    remaining = [
        line for line in en_text.splitlines()
        if re.search(r"[а-яА-ЯёЁ]", line) and "base64" not in line
    ]
    print(f"EN written ({len(en_text)} bytes), Cyrillic lines left: {len(remaining)}")
    if remaining[:5]:
        for line in remaining[:5]:
            print("  ", line[:100])


if __name__ == "__main__":
    main()

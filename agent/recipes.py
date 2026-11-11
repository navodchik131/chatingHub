"""Проверенные рецепты: подбор входов и сборка промптов для Seedream 5.5 (основной), Seedream V5.0 Pro (правка) и GPT Image 2.5.

Grok описывает только сцену (brief_en / brief_zh), а входы, их порядок, нумерацию 图N / image N
и все абзацы реализма собирает код — так промпт не «худеет» и всегда совпадает с картинками.
"""
import re

MODES = ("replace", "new", "carousel", "edit", "outfit", "free", "bodyref")
BRIEF_KEYS = ("scene", "action", "expression", "outfit", "hair", "camera", "background", "light", "orig_hair", "change", "extra")
BODYREF_VIEWS = ("front", "back", "side", "half")
BODYREF_RU = {"front": "фигура спереди", "back": "фигура сзади", "side": "фигура сбоку", "half": "по пояс"}
VIEW_ZH = {"front": "正面", "back": "背面", "side": "侧面"}
ROLE_RU = {"face": "лицо", "body": "тело", "lineart": "силуэт", "source": "исходник", "texture": "фактура ★",
           "base": "основа", "other": "картинка"}
CJK = re.compile(r"[一-鿿]")


# ---------------- роли и подбор входов ----------------
def face_angle_of(label):
    l = (label or "").lower()
    if "проф" in l or "profile" in l or "сбоку" in l:
        return "profile"
    if "3/4" in l or "34" in l:
        return "34"
    return "front"


def body_view_of(label):
    l = (label or "").lower()
    if "спин" in l or "сзади" in l or "back" in l:
        return "back34" if "3/4" in l else "back"
    if "проф" in l or "сбоку" in l or "side" in l:
        return "side"
    if "3/4" in l or "34" in l:
        return "34"
    return "front"


def role_of(chat, iid, a, k):
    """('face'|'body'|'cat'|'lineart'|'source'|'texture'|'base'|'other', детали)."""
    p = chat["persona"]; rec = chat["images"].get(iid, {})
    mode = a.get("mode") or "free"
    if mode in ("edit", "outfit") and k == 0:
        return "base", ""
    if mode == "carousel" and iid == a.get("source_id"):
        return "base", ""
    if iid in p["faces"]:
        return "face", rec.get("label", "")
    if iid in p["body"]:
        return "body", rec.get("label", "")
    for name, v in p.get("extra", {}).items():
        if iid in v.get("ids", []):
            return "cat", name
    if rec.get("source") == "lineart":
        return "lineart", ""
    if iid == a.get("source_id"):
        return "source", ""
    if rec.get("source") in ("gen", "crop", "post"):
        return "texture", ""
    if rec.get("source") in ("user", "frame"):
        return "source", ""
    return "other", ""


def role_label(chat, iid, a, k):
    r, d = role_of(chat, iid, a, k)
    if r == "face":
        return "лицо " + d if d else "лицо"
    if r == "body":
        return "тело " + d if d else "тело"
    if r == "cat":
        return d.lower()
    return ROLE_RU.get(r, "")


def ordered_faces(chat, angle):
    p = chat["persona"]
    pref = [angle or "front", "front", "34", "profile"]
    return sorted(p["faces"], key=lambda i: pref.index(face_angle_of(chat["images"].get(i, {}).get("label"))))[:3]


def pick_body(chat, view):
    p = chat["persona"]
    if not p["body"]:
        return []
    want = view or "front"
    for v in (want, "front", "34"):
        for i in p["body"]:
            if body_view_of(chat["images"].get(i, {}).get("label")) == v:
                return [i]
    return p["body"][:1]


def find_lineart(chat, src):
    best = None
    for i, r in chat["images"].items():
        if r.get("source") == "lineart" and src in (r.get("inputs") or []):
            if not best or r["t"] > chat["images"][best]["t"]:
                best = i
    return best


def texture_ref(chat):
    """Последний ★ кадр GPT этой модели — референс фактуры для Seedream."""
    favs = [(r["t"], i) for i, r in chat["images"].items()
            if r.get("fav") and r.get("source") in ("gen", "crop", "post") and r.get("engine") == "gpt"]
    return max(favs)[1] if favs else None


FACE_WORDS = ("headshot", "portrait shot", "face close-up", "close-up of her face", "close-up of the face", "face only", "крупный план лица",
              "крупно лицо", "портрет", "脸部特写", "面部特写", "头像", "大头")
FULL_WORDS = ("full-body", "full body", "full-length", "head to toe", "в рост", "в полный рост", "全身")
FACE_CATS = ("лиц", "волос", "причёс", "прическ", "макияж", "серьг", "очк", "face", "hair", "makeup")


def framing_of(a):
    """face — видно только лицо/плечи; half — по пояс; full — в рост; None — не понятно (берём как раньше)."""
    f = a.get("framing")
    if f in ("face", "half", "full"):
        return f
    txt = " ".join(str((a.get(f"brief_{L}") or {}).get("scene") or "") for L in ("en", "zh")
                   if isinstance(a.get(f"brief_{L}"), dict)).lower() + " " + str(a.get("label") or "").lower()
    if any(w in txt for w in FULL_WORDS):
        return "full"
    if any(w in txt for w in FACE_WORDS):
        return "face"
    return None


def live_body(chat):
    """Живые эталоны фигуры из GPT (спереди, сзади, сбоку) — по порядку."""
    p = chat["persona"]; out = []
    for v in ("front", "back", "side"):
        i = next((i for i in p["body"] if chat["images"].get(i, {}).get("bodyref") == v), None)
        if i:
            out.append(i)
    return out


LIVE_VIEW = {"front": "front", "34": "front", "side": "side", "back": "back", "back34": "back"}


def pick_body55(chat, view):
    """Одна фигура под ракурс тела: живой эталон этого ракурса, иначе студийный."""
    want = LIVE_VIEW.get(view or "front", "front")
    for v in (want, "front"):
        i = next((i for i in chat["persona"]["body"] if chat["images"].get(i, {}).get("bodyref") == v), None)
        if i:
            return [i]
    studio = [i for i in chat["persona"]["body"] if not chat["images"].get(i, {}).get("bodyref")]
    if not studio:
        return []
    for v in (view or "front", "front", "34"):
        for i in studio:
            if body_view_of(chat["images"].get(i, {}).get("label")) == v:
                return [i]
    return studio[:1]


def is_55(engine, a):
    """Seedream 5.5 — всё, кроме локальной правки (она пока на 5.0) и mode=free с явным 5.0."""
    return engine == "seedream" and a.get("mode") != "edit"


def pick_inputs(chat, a, engine):
    """Порядок входов по проверенным рецептам. Возвращает список id (силуэт должен уже существовать)."""
    mode = a.get("mode"); src = a.get("source_id")
    if mode == "bodyref":   # эталоны фигуры через GPT: на вход только лица, фигура — текстом
        return [i for i in ordered_faces(chat, "front") if not chat["images"].get(i, {}).get("bodyref")][:3]
    if mode == "outfit":
        # смена одежды: кадр первым; если на кадре модель — её портрет и фигура (открытое тело и лицо — её), чужое фото — только кадр
        rec = chat["images"].get(src, {}); p = chat["persona"]
        refs = set(p["faces"]) | set(p["body"])
        mine = a.get("with_model") if a.get("with_model") is not None else (rec.get("source") in ("gen", "post", "crop", "ref") or src in refs)
        if not mine:
            return [src]
        face = [i for i in ordered_faces(chat, a.get("face_angle")) if not chat["images"].get(i, {}).get("bodyref")][:1] or p["faces"][:1]
        body = [] if framing_of(a) == "face" else pick_body55(chat, a.get("body_view"))
        return [i for k, i in enumerate([src] + face + body) if i and i not in ([src] + face + body)[:k]]
    if is_55(engine, a) and mode in ("replace", "new", "carousel"):
        # минимум входов: один портрет под ракурс лица + одна фигура под ракурс тела (если тело в кадре).
        # Лишние эталоны в своей одежде (топ, легинсы, футболка) Seedream тащит в кадр и меняет одежду исходника.
        p = chat["persona"]
        portraits = [i for i in ordered_faces(chat, a.get("face_angle")) if not chat["images"].get(i, {}).get("bodyref")]
        faces = portraits[:1] or [i for i in p["faces"]][:1]
        body = [] if mode == "carousel" else pick_body55(chat, a.get("body_view"))   # карусель: фигура — с самой основы
        cats = []
        for name in a.get("categories") or []:
            for k, v in p.get("extra", {}).items():
                if k.lower() == str(name).lower() and v.get("ids"):
                    cats.append(v["ids"][0])
        if framing_of(a) == "face":
            body = []
            cats = [c for c in cats if any(w in next((k for k, v in p.get("extra", {}).items() if c in v.get("ids", [])), "").lower() for w in FACE_CATS)]
        if mode == "replace":
            # замена: исходник уходит СИЛУЭТОМ (линии поверх настоящего фона) — с настоящего фото Seedream копирует
            # лицо, фигуру и тату исходной девушки. Лица — два портрета (ракурс кадра + анфас), силуэт последним.
            la = find_lineart(chat, src)
            faces = portraits[:2] or [i for i in p["faces"]][:2]
            order = faces + body + cats[:2] + [la or src]
        else:
            order = ([src] if mode == "carousel" and src else []) + faces + body + cats[:2]
        ids = []
        for i in order:
            if i not in ids:
                ids.append(i)
        return ids[:10]
    faces = ordered_faces(chat, a.get("face_angle"))
    body = pick_body(chat, a.get("body_view"))
    cats = []
    p = chat["persona"]
    for name in a.get("categories") or []:
        for k, v in p.get("extra", {}).items():
            if k.lower() == str(name).lower() and v.get("ids"):
                cats.append(v["ids"][0])
    cats = cats[:2]
    if framing_of(a) == "face":
        # крупный план: тело и категории тела в кадр не попадут — только сбивают композицию и дорожают
        body = []
        cats = [c for c in cats if any(w in next((k for k, v in p.get("extra", {}).items() if c in v.get("ids", [])), "").lower() for w in FACE_CATS)]
    tex = a.get("texture_id") or texture_ref(chat)
    if a.get("texture_id") is False or a.get("no_texture"):
        tex = None
    if mode == "replace":
        if engine == "seedream":
            la = find_lineart(chat, src)
            ids = faces + body + cats + ([la] if la else [src])
            return ids + ([tex] if tex and tex not in ids else [])
        return [src] + faces[:2] + body + cats
    if mode == "new":
        if engine == "seedream":
            ids = body + faces + cats
        else:
            ids = faces + body + cats
        return ids + ([tex] if tex and tex not in ids else [])
    if mode == "carousel":
        # как в ручных каруселях: основа 图1 (одежда, место, свет), лица, тело; новизну кадра даёт подробная сцена
        ids = [src] + faces + body + cats
        return ids + ([tex] if engine == "seedream" and tex and tex not in ids else [])
    if mode == "edit":
        return [src] + (faces if a.get("with_faces") else []) + cats
    return a.get("image_ids") or []


def aspect_for(w, h):
    opts = {"1:1": 1, "3:4": 3 / 4, "4:5": 4 / 5, "2:3": 2 / 3, "9:16": 9 / 16, "4:3": 4 / 3, "16:9": 16 / 9}
    r = w / max(h, 1)
    return min(opts, key=lambda k: abs(opts[k] - r))


# ---------------- нумерация ----------------
def _idx(roles, *names):
    return [k + 1 for k, (r, _) in enumerate(roles) if r in names]


def zh_ref(ns):
    if not ns:
        return ""
    if len(ns) == 1:
        return f"图{ns[0]}"
    if ns == list(range(ns[0], ns[-1] + 1)):
        return f"图{ns[0]}到图{ns[-1]}"
    return "、".join(f"图{n}" for n in ns)


def en_ref(ns):
    if not ns:
        return ""
    if len(ns) == 1:
        return f"image {ns[0]}"
    if ns == list(range(ns[0], ns[-1] + 1)):
        return f"images {ns[0]}–{ns[-1]}"
    return "images " + ", ".join(str(n) for n in ns)


def _b(brief, k):
    v = (brief or {}).get(k) or ""
    return v.strip().rstrip("。.") if isinstance(v, str) else ""


# ---------------- абзацы реализма (проверено на Нике и MotoLola) ----------------
EYES_ZH = ("眼睛和神态（重要）：眼睛有神、有光，精神饱满，眼睛里有清晰的反光点，虹膜有放射状纹理和较深的外圈，下睫毛可见，"
           "两只眼睛看向同一方向，眼球不要偏到眼角；上眼皮不要下垂，不要眼袋，不要黑眼圈，不要疲惫感，不要空洞，不要呆滞。")
SKIN_ZH = ("皮肤（重要，像手机直出未修图）：皮肤完全哑光，脸、肩膀、手臂和腿都没有油光、没有汗湿、没有反光高光，柔和的漫反射；"
           "毛孔清晰可见，雀斑稀疏、深浅大小不一、分布不均，不要均匀的圆点图案，鼻翼和脸颊微微泛红，嘴唇有细小的唇纹，"
           "脸颊有细小的绒毛。不要磨皮，不要美颜，不要蜡像感，不要塑料感，不要CG渲染感，不要偏黄偏橙，不要晒黑。")
FRAME_ZH = ("画面：像用iPhone 16随手拍的真实照片，24mm等效，柔和、低对比度，自然真实的白平衡和色彩，手机自带的干净成像，没有可见噪点。画面干净：布料、皮肤和墙面上没有斑驳、斑点或一块一块的纹理，没有胶片颗粒，没有噪点花纹，没有重影和双边。"
            "大景深：背景和人物一样清晰对焦，没有背景虚化，没有焦外光斑，前景也不虚化。"
            "不要HDR，不要锐化，不要提高清晰度，发丝周围不要白边，不要电影感，不要单反感，不要商业广告感，不要过度精致。画面上不要任何文字或水印。")
REAL_EN = ("Realism: looks like a real unedited iPhone 16 photo, 24mm main camera, natural light, "
           "clean natural phone processing (Smart HDR, no visible noise), no cinematic look. "
           "Natural skin with fine pores and slight redness, sparse freckles, matte skin with no oily shine, natural soft lashes, "
           "iris texture with catchlights, both eyes looking the same direction, soft natural matte hair with darker roots and a few loose strands, "
           "smooth even-coloured fabric with natural folds and wrinkles (soft cotton fleece looks smooth, not knitted or slubby). "
           "Clean even surfaces: no mottled, blotchy or patchy texture on fabric, skin or walls, no film grain, no noise pattern, no double edges or ghosting. No oversharpening, no halos or white edges around hair, no crunchy or wiry hair, smooth even sky. "
           "Deep depth of field: the background is as sharp and in focus as she is — no bokeh, no background blur, no blurred foreground. "
           "No retouching, no beauty filter, no plastic or CGI look, no added text or watermark.")


def hair_zh(F):
    return (f"头发颜色和质感（重要）：发色按{F}，发根明显较深，过渡自然，不要一条条很亮的高光条纹，不要白金色，不要太浅，"
            "不要稻草感；发丝柔软，有一些细碎发和飞丝，哑光，没有刺眼的反光，不要沙龙发，不要像假发。")


_INTIMATE = re.compile(r"乳|阴|隐私|私处|生殖|nipple|labia|pubic|intimate|genital|breasts? (?:are|with)|natural shaped medium breasts", re.I)


def clean_card(card):
    """Из карточки в промпт идут только внешность и фигура — без интимных деталей (они толкают генератор к наготе)."""
    parts = [x.strip() for x in re.split(r"(?<=[。.!?])\s*", card or "") if x.strip()]
    keep = [x for x in parts if not _INTIMATE.search(x)]
    sep = "" if is_zh(card or "") else " "
    return sep.join(keep).strip().rstrip("。.")


def identity_zh(F, card):
    return (f"人物身份（最重要）：她就是{F}中的那位女性，同一个人，脸要和{F}一模一样" + (f"：{card}" if card else "") +
            f"。脸型、五官比例和{F}完全一样，不要瘦脸，不要尖下巴，素颜或淡妆。只取{F}的脸、肤色和发色，不取发型、衣服、背景和棚拍光线。")


def identity_en(F, card):
    return (f"IDENTITY (most important): she is the exact same woman as in {F} — same face shape, eyes, nose, lips, brows, freckles and moles"
            + (f": {card}" if card else "") +
            f". Natural, no heavy makeup. Take only her face, skin tone and hair colour from {F}, not their hairstyle, clothes, background or studio light.")


def cats_zh(chat, roles):
    out = []
    for k, (r, d) in enumerate(roles):
        if r == "cat":
            note = chat["persona"].get("extra", {}).get(d, {}).get("note", "")
            out.append(f"图{k + 1}只取{d}（{note}），不取它的姿势、衣服和背景。" if note else f"图{k + 1}只取{d}，不取它的姿势、衣服和背景。")
    return out


def cats_en(chat, roles):
    out = []
    for k, (r, d) in enumerate(roles):
        if r == "cat":
            note = chat["persona"].get("extra", {}).get(d, {}).get("note", "")
            out.append(f"Image {k + 1}: take only her {d}" + (f" ({note})" if note else "") + " from it, not its pose, clothes or background.")
    return out


# ---------------- сборка ----------------
_DRAPED = re.compile(r"披|搭在肩|滑落|空袖|draped|off[- ]the[- ]shoulder|over (?:her|the|both) shoulders?|slipp(?:ing|ed) off|empty sleeve|накинут|сполза|спущен[аы]? с плеч|пуст\w* рукав", re.I)
SLEEVES_ZH = ("袖子（严格）：外套是披在肩上的，空着的袖子软软地垂下来，袖口里没有手、没有手臂。她只有自己的两只手臂，"
              "每只手只在场景里写的位置；空袖子不能变成第三只手臂或第三只手。")
SLEEVES_EN = ("SLEEVES (strict): the jacket is draped over her shoulders; any empty sleeve hangs limp with no hand or arm inside. "
              "She has only her own two arms, each hand exactly where the scene says; an empty sleeve must never become a third arm or hand.")


def draped(a):
    """Одежда накинута на плечи — пустые рукава Seedream/GPT «заполняют» лишней рукой."""
    txt = " ".join(str(v) for L in ("en", "zh") for k, v in ((a.get(f"brief_{L}") or {}).items())
                   if k in ("outfit", "action", "scene", "change", "extra") and v)
    return bool(_DRAPED.search(txt))


def render(chat, a, engine):
    """Промпт по рецепту + правила платформы последним абзацем (их нельзя потерять ни в одном режиме)."""
    out = _render_core(chat, a, engine)
    lang = "zh" if engine == "seedream" else "en"
    if a.get("mode") not in ("free", "bodyref") and draped(a):
        sl = SLEEVES_ZH if lang == "zh" else SLEEVES_EN
        if sl not in out:
            out = out.rstrip() + "\n" + sl
    rules = rules_prompt(lang)
    if not rules or rules in out:
        return out
    return out.rstrip() + "\n" + rules


def _render_core(chat, a, engine):
    """Собрать промпт по рецепту. a — аргументы generate_image (mode, image_ids, brief_en/brief_zh…)."""
    mode = a.get("mode") or "free"
    ids = a.get("image_ids") or []
    if mode == "free":
        return a.get("prompt", "")
    roles = [role_of(chat, i, a, k) for k, i in enumerate(ids)]
    p = chat["persona"]
    if mode == "bodyref":
        return _render_bodyref(a, roles, p)
    if mode == "outfit":
        return _render_outfit(chat, a, roles, p, engine)
    if is_55(engine, a):
        return _render_55(chat, a, mode, roles, ids, p)
    if engine == "seedream":
        out = _render_zh(chat, a, mode, roles, p)
        return (fixes_zh(a) + "\n" + out) if fixes_zh(a) else out
    out = _render_en(chat, a, mode, roles, p)
    out = out[:1].upper() + out[1:]
    return (fixes_en(a) + "\n" + out) if fixes_en(a) else out


def _render_zh(chat, a, mode, roles, p):
    b = a.get("brief_zh") or {}
    F = zh_ref(_idx(roles, "face")); B = zh_ref(_idx(roles, "body")); T = zh_ref(_idx(roles, "texture"))
    L = zh_ref(_idx(roles, "lineart")); S = zh_ref(_idx(roles, "source")); base = zh_ref(_idx(roles, "base"))
    card = clean_card(p.get("card_zh"))
    P = []
    if mode == "replace":
        ref = L or S
        if L:
            P.append(f"一张真实的手机照片。{L}是一张线稿参考：白色剪影加黑色线条只提供人物的动作、姿势、表情和构图，背景是真实的照片，保持不变。"
                     f"把线稿里的人变成真人，她就是{F}中的那位女性。")
        else:
            P.append(f"把{S}中的女子换成{F}中的那位女性，{S}的其余内容全部保持不变。")
        if _b(b, "scene") or _b(b, "action"):
            P.append(f"场景和动作：{_b(b, 'scene')}{'，' if _b(b, 'scene') and _b(b, 'action') else ''}{_b(b, 'action')}。")
        P.append(identity_zh(F, card))
        P.append(f"比例（重要）：画面里人物的大小、位置、离镜头的距离、姿势、头部角度和手的位置都和{ref}完全一致，"
                 "头部大小自然，头身比例正常，头不要变大，脖子正常长度，肩膀正常宽度，只有两只手。")
        if B:
            P.append(f"身材按{B}（只取身材比例，不取{B}的姿势和衣服），不要沿用原图女子的身材，不要变瘦。")
        if _b(b, "outfit"):
            P.append(f"服装（线稿里看不出颜色和材质，按文字）：{_b(b, 'outfit')}。颜色均匀、表面平整的布料，有自然的褶皱；卫衣和抓绒是光滑的棉质，不是针织或粗纺纹理，哑光面料，不要塑料感，衣服上没有其他文字。"
                     if L else f"服装：{_b(b, 'outfit')}，和原图一样；颜色均匀、表面平整的布料，有自然的褶皱，不是针织或粗纺纹理。")
        if L:
            P.append("皮肤上没有任何纹身，都是干净的皮肤。")
        P.append(f"背景保持{ref}里的真实背景不变" + (f"：{_b(b, 'background')}" if _b(b, 'background') else "") +
                 (f"。光线：{_b(b, 'light')}" if _b(b, 'light') else "") + "。人物受到同样的光照，背景清晰，不要虚化。")
    elif mode == "new":
        P.append(f"一张竖屏手机照片：{F}中的那位女性，{_b(b, 'scene')}" + (f"，{_b(b, 'action')}" if _b(b, 'action') else "") + "。")
        P.append(identity_zh(F, card))
        P.append("比例（重要）：头部大小自然，头身比例正常，头不要变大，脖子正常长度，肩膀正常宽度，只有两只手。")
        if B:
            P.append(f"身材按{B}（只取身材比例，不取{B}的姿势和衣服），不要变瘦。")
        if _b(b, "outfit"):
            P.append(f"服装：{_b(b, 'outfit')}。颜色均匀、表面平整的布料，有自然的褶皱；卫衣和抓绒是光滑的棉质，不是针织或粗纺纹理，哑光面料，不要塑料感，衣服上没有其他文字。")
        P.append(f"环境：{_b(b, 'background') or '普通、有生活痕迹的真实地点'}，干净但有生活痕迹。光线：{_b(b, 'light') or '明亮自然的日光'}。背景清晰，不要虚化。")
    elif mode == "carousel":
        P.append(f"新拍一张（不是修改{base}）：{_b(b, 'scene')}" + (f"。{_b(b, 'action')}" if _b(b, 'action') else "") + "。")
        P.append(f"{base}只用来参考她的衣服、地点和光线。姿势、手的位置、机位、拍摄角度、景别和构图都必须和{base}明显不同，"
                 f"不要复制{base}的姿势和构图，不要和{base}几乎一样。")
        if F:
            P.append(f"人物身份（最重要）：她就是{F}中的那位女性，同一个人，脸要和{F}一模一样" + (f"：{card}" if card else "") +
                     f"。脸型和五官比例不要变，不要瘦脸，不要尖下巴。发型、衣服和妆容和{base}一样，不取{F}的衣服、背景和棚拍光线。")
        P.append(f"身材完全按{base}这张照片里她本人的身材" + (f"，也参考{B}的身材比例（不取{B}的姿势和衣服）" if B else "") + "，不要变瘦。比例：头部大小自然，头不要变大，只有两只手。")
        if _b(b, "outfit"):
            P.append(f"服装和{base}一样：{_b(b, 'outfit')}。颜色均匀、表面平整的布料，有自然的褶皱；卫衣和抓绒是光滑的棉质，不是针织或粗纺纹理，哑光。")
        P.append(f"背景和光线和{base}一样" + (f"：{_b(b, 'background')}" if _b(b, 'background') else "") + "，背景清晰，不要虚化。")
    elif mode == "edit":
        P.append(f"只修改{base}中的{_b(b, 'change') or _b(b, 'action')}，其余保持{base}完全不变：脸、表情、姿势、衣服、背景、光线和构图都不变。")
        if F:
            P.append(f"脸要和{F}中的那位女性一模一样" + (f"：{card}" if card else "") + "。")
        P += cats_zh(chat, roles)
        if _b(b, "extra"):
            P.append(_b(b, "extra") + "。")
        return "\n".join(P)
    if _b(b, "expression"):
        P.append(f"表情：{_b(b, 'expression')}。表情自然、略不对称，不要僵硬的摆拍笑容。")
    P.append(EYES_ZH)
    P.append(SKIN_ZH)
    if F or base:
        P.append(hair_zh(F or base))
    P.append(FRAME_ZH)
    P += cats_zh(chat, roles)
    if T:
        P.append(f"{T}只作为画面质感参考：皮肤、头发、面料的质感、柔和程度和色调按{T}，不要取{T}的脸、头部大小、姿势、衣服、背景和构图。")
    if mode == "replace" and L:
        P.append("画面里不能留下任何线稿、白色剪影或黑色描边，全部是真实照片。")
    if _b(b, "extra"):
        P.append(_b(b, "extra") + "。")
    return "\n".join(P)


def _render_en(chat, a, mode, roles, p):
    b = a.get("brief_en") or {}
    F = en_ref(_idx(roles, "face")); B = en_ref(_idx(roles, "body")); T = en_ref(_idx(roles, "texture"))
    L = en_ref(_idx(roles, "lineart")); S = en_ref(_idx(roles, "source")); base = en_ref(_idx(roles, "base"))
    card = clean_card(p.get("card_en"))
    P = []
    if mode == "replace":
        ref = S or L
        if S:
            P.append(f"Replace the woman in {S} with the woman from {F} (the same person). Keep everything else from {S} exactly the same: "
                     "composition, framing, camera angle and distance, lens distortion, her pose, head angle, hand positions, expression and mouth shape, "
                     "background, other people, lighting, colors and photo quality. Do not keep the face of the original woman.")
        else:
            P.append(f"{L} is a line-art reference: the white silhouette with black lines gives only the pose, expression and composition; the background is a real photo, keep it. "
                     f"Turn the line-art person into a real woman — the woman from {F}. No line art, white silhouette or black outlines may remain.")
        if _b(b, "scene") or _b(b, "action"):
            P.append(f"Scene: {_b(b, 'scene')}{'. ' if _b(b, 'scene') and _b(b, 'action') else ''}{_b(b, 'action')[:1].upper() + _b(b, 'action')[1:]}.")
        P.append(identity_en(F, card))
        P.append(f"Proportions: same size, position and distance from the camera as the woman in {ref}, natural head size, normal neck and shoulders, only two hands."
                 + (f" Body shape from {B} (only the proportions, not its pose or clothes) — do not keep the original woman's body, do not make her thinner." if B else ""))
        if _b(b, "outfit"):
            P.append(f"Outfit: {_b(b, 'outfit')} — as in {ref}, smooth even-coloured fabric with natural folds and wrinkles (soft cotton fleece looks smooth, not knitted or slubby), matte, no extra text on clothes.")
        P.append(f"Background (keep from {ref}): {_b(b, 'background') or 'unchanged'}." + (f" Light: {_b(b, 'light')}." if _b(b, 'light') else "")
                 + " She is lit by the same light.")
    elif mode == "new":
        P.append(f"A vertical phone photo of the woman from {F}: {_b(b, 'scene')}" + (f". {_b(b, 'action')}" if _b(b, 'action') else "") + ".")
        P.append(identity_en(F, card))
        P.append("Proportions: natural head size, normal neck and shoulders, only two hands."
                 + (f" Body shape from {B} (only the proportions, not its pose or clothes), do not make her thinner." if B else ""))
        if _b(b, "outfit"):
            P.append(f"Outfit: {_b(b, 'outfit')}, smooth even-coloured fabric with natural folds and wrinkles (soft cotton fleece looks smooth, not knitted or slubby), matte, no extra text on clothes.")
        P.append(f"Environment: {_b(b, 'background') or 'an ordinary lived-in real place'}, clean but lived-in, everyday details. Light: {_b(b, 'light') or 'bright natural daylight'}.")
    elif mode == "carousel":
        P.append(f"A completely new photo, not an edit of {base}: {_b(b, 'scene')}" + (f". {_b(b, 'action')}" if _b(b, 'action') else "") + ".")
        P.append(f"Use {base} only for her clothes, the location and the light. Pose, hand placement, camera position, camera angle, "
                 f"shot size and framing must be clearly different from {base} — do not copy its pose or composition.")
        if F:
            P.append(f"IDENTITY (most important): she is the exact same woman as in {F}" + (f": {card}" if card else "") +
                     f". Hairstyle, clothes and makeup as in {base}; do not take clothes, background or studio light from {F}.")
        P.append(f"Body exactly as hers in {base}" + (f", proportions also from {B} (not its pose or clothes)" if B else "") + ", do not make her thinner. Natural head size, only two hands.")
        if _b(b, "outfit"):
            P.append(f"Outfit as in {base}: {_b(b, 'outfit')}, smooth even-coloured fabric with natural folds and wrinkles (soft cotton fleece looks smooth, not knitted or slubby).")
        P.append(f"Background and light as in {base}" + (f": {_b(b, 'background')}" if _b(b, 'background') else "") + ".")
    elif mode == "edit":
        P.append(f"Edit {base}: only change {_b(b, 'change') or _b(b, 'action')}. Keep everything else in {base} exactly the same — face, expression, pose, clothes, background, light and framing.")
        if F:
            P.append(f"Her face must match the woman from {F}" + (f": {card}" if card else "") + ".")
        P += cats_en(chat, roles)
        if _b(b, "extra"):
            P.append(_b(b, "extra") + ".")
        return "\n".join(P)
    if _b(b, "expression"):
        P.append(f"Expression: {_b(b, 'expression')}, natural and slightly asymmetric, not a posed symmetrical smile.")
    P.append(REAL_EN)
    P += cats_en(chat, roles)
    if T:
        P.append(f"{T[0].upper() + T[1:]} is only a texture reference for skin, hair and fabric — do not take its face, head size, pose, clothes, background or framing.")
    if _b(b, "extra"):
        P.append(_b(b, "extra") + ".")
    return "\n".join(P)


# ---------------- Seedream 5.5 (опыт AI-чаттера) ----------------
ANATOMY_ZH = ("人体结构（必须正确）：画面里只有她一个人。她正好有两只手臂、两只手、两条腿、两只脚，不多不少；每只手正好五根手指，"
              "手指长短自然、关节正确，不粘连、不交叉、不多指、不缺指。拿手机的那只手和那只手臂只有一个，另一只手按场景描述放好。"
              "手臂和腿都连在身体正确的位置上，比例自然，没有扭曲、拉长或折断的四肢，没有多余的手、手臂、腿或脚，"
              "画面边缘也不能出现别人的手或身体部位。镜子里的倒影和她本人完全对应，不多出一个人。")
STYLE55_ZH = ("用iPhone 16主摄随手拍的手机照片：24mm等效广角，手机自带的干净成像，没有可见噪点。大景深：背景和人物一样清晰对焦，"
              "没有背景虚化，没有焦外光斑，前景也不虚化。画面柔和、低对比度，明亮、温暖的自然光，阴影里保留细节、不死黑，高光不过曝。"
              "不要HDR，不要锐化，不要提高清晰度，不要电影感，不要单反感，不要冷色调。\n"
              "眼睛和神态：精神饱满，眼神明亮，眼睛里有清晰的反光点，虹膜有放射状纹理，眼睛颜色自然，不过度饱和；不要空洞，不要呆滞。\n"
              "皮肤：完全哑光，毛孔清晰，肤色不均、鼻翼微微泛红，细小绒毛；没有油光、没有汗湿、没有反光高光；不要磨皮，不要美颜，"
              "不要塑料感，不要蜡像感，不要CG渲染感，不要偏黄偏橙。\n"
              "头发：柔软、哑光，一根一根分明，有碎发和飞丝，发根略深，不要沙龙发，不要像假发，不要结成一束一束，不要稻草感。\n"
              "衣服：颜色均匀、表面平整的布料，有自然的褶皱。\n"
              "画面干净：布料、皮肤和墙面上没有斑驳、斑点或一块一块的纹理，没有胶片颗粒，没有噪点花纹，没有重影和双边。画面里没有文字、水印和标志。")
COVER_ZH = "胸部和私处必须被布料完全遮住：不能露出乳头和私处，不能全裸。"

# ---------------- правила платформы (что запрещено) ----------------
# В хостинге список приходит из админки model-mate (/api/agent/session → rules); локально — эти правила по умолчанию.
# Базовые правила (несовершеннолетние, реальные люди) действуют всегда, даже если админка их не прислала.
LOCKED_RULES = [
    {"title": "Никаких несовершеннолетних: все люди в кадре — взрослые 18+ и выглядят взрослыми.",
     "prompt_zh": "画面中所有人物都是成年人（18岁以上），外表明显是成年人；不能出现任何未成年人、儿童或少女的样子，不要把她画得更年轻。",
     "prompt_en": "Everyone in the image is a clearly adult person (18+); no minors, no childlike or teen appearance, do not make her look younger."},
    {"title": "Без реальных людей: лицо только вымышленной модели из эталонов.",
     "prompt_zh": "人物的脸只取自模特参考图，不要生成任何真实名人或可识别的真实人物的脸。",
     "prompt_en": "Her face comes only from the model reference images; do not depict any celebrity or identifiable real person."},
]
DEFAULT_RULES = LOCKED_RULES + [
    {"title": "Без наготы: грудь и интимные зоны всегда закрыты тканью; «сними одежду» — до белья или купальника.",
     "prompt_zh": COVER_ZH, "prompt_en": "Breasts and intimate areas stay fully covered by fabric; no nudity."},
    {"title": "Без сексуальных действий и порнографии.", "prompt_zh": "没有任何性行为或色情动作，只是普通的拍照姿势。",
     "prompt_en": "No sexual acts or pornographic poses, only ordinary photo posing."},
    {"title": "Без насилия и крови.", "prompt_zh": "画面里没有血、伤口或暴力，没有指向人的武器。",
     "prompt_en": "No blood, wounds or violence, no weapons pointed at anyone."},
    {"title": "Без символики ненависти и экстремизма.", "prompt_zh": "画面里没有纳粹、极端主义或仇恨符号和侮辱性文字。",
     "prompt_en": "No Nazi, extremist or hate symbols and no offensive text."},
    {"title": "Без наркотиков.", "prompt_zh": "画面里没有毒品或吸毒用具。", "prompt_en": "No drugs or drug paraphernalia."},
    {"title": "Без самоповреждений.", "prompt_zh": "画面里没有自残或自杀的内容。", "prompt_en": "No self-harm or suicide imagery."},
]
RULES = list(DEFAULT_RULES)


def set_rules(rules):
    """Правила из админки. Базовые добавляются всегда; не-список — не трогаем текущие."""
    global RULES
    if not isinstance(rules, list):
        return
    clean = [{"title": str(r.get("title") or "").strip(), "prompt_zh": str(r.get("prompt_zh") or "").strip(),
              "prompt_en": str(r.get("prompt_en") or "").strip()} for r in rules if isinstance(r, dict) and r.get("title")]
    have = {r["prompt_zh"] for r in clean}
    RULES = [r for r in LOCKED_RULES if r["prompt_zh"] not in have] + clean


def rules_prompt(lang):
    """Строки правил для промпта модели (zh — Seedream, en — GPT)."""
    k = "prompt_zh" if lang == "zh" else "prompt_en"
    out = []
    for r in RULES:
        t = (r.get(k) or "").strip()
        if t and t not in out:
            out.append(t)
    return "\n".join(out) if lang == "zh" else " ".join(out)


def rules_titles():
    return [r["title"] for r in RULES if r.get("title")]


def body55_zh(chat, roles, ids, p):
    ns = _idx(roles, "body")
    if not ns:
        return ""
    B = zh_ref(ns); fig = (p.get("figure_zh") or "").strip().rstrip("。")
    views = [VIEW_ZH.get(chat["images"].get(ids[n - 1], {}).get("bodyref")) for n in ns]
    if all(views):
        return (f"{B}是她本人的全身照片（{'、'.join(views)}）：身材完全按这些照片" + (f"——{fig}" if fig else "") +
                "，肩膀和手臂的粗细也和照片一样。不要变瘦，不要缩小胯部和臀部，不要把胸部画大。只取她的身材，不取衣服、姿势和背景。")
    return (f"身材按{B}（只取身材比例，不取{B}的姿势、衣服和背景）" + (f"：{fig}" if fig else "") +
            "。不要变瘦，不要缩小胯部和臀部，不要把胸部画大。")


def face55_zh(F, card):
    return (f"人物身份（最重要）：她就是{F}中的那位女性，同一个人，脸要和{F}一模一样：脸型、五官比例和细微的不对称都相同。"
            f"只取脸、肤色和发色，不取发型、衣服、背景和棚拍光线。她是成年女性，不是少女。" + (f"{card}。" if card else "") +
            "脸型和五官比例完全按参考图：脸不要变窄，下巴不要变尖，不要瘦脸，不要V脸，脸颊保持原来的饱满度，不要变年轻。")


def _scene55(b):
    s = [x for x in (_b(b, "scene"), _b(b, "action")) if x]
    if _b(b, "expression"):
        s.append(f"表情：{_b(b, 'expression')}")
    if _b(b, "hair"):
        s.append(f"发型：{_b(b, 'hair')}")
    if _b(b, "background"):
        s.append(f"环境：{_b(b, 'background')}")
    if _b(b, "light"):
        s.append(f"光线：{_b(b, 'light')}")
    return ("场景：" + "。".join(s) + "。") if s else ""


def has_tattoo(p):
    """Есть ли у модели тату по карточке — тогда тату не запрещаем."""
    txt = " ".join(str(p.get(k) or "") for k in ("card_zh", "card_en", "figure_zh", "figure_en")).lower()
    if any(w in txt for w in ("没有纹身", "无纹身", "no tattoo", "without tattoo")):
        return False
    return any(w in txt for w in ("纹身", "tattoo", "тату"))


def fixes_zh(a):
    """Правки пользователя словами — первым абзацем, важнее всего остального."""
    fx = [x.strip().rstrip("。.") for x in (a.get("fixes_zh") or []) if isinstance(x, str) and x.strip()]
    if not fx:
        return ""
    return "这次必须改正（最重要，优先于下面所有描述）：" + "；".join(fx) + "。"


def fixes_en(a):
    fx = [x.strip().rstrip(".") for x in (a.get("fixes_en") or []) if isinstance(x, str) and x.strip()]
    if not fx:
        return ""
    return "MUST FIX THIS TIME (most important, overrides everything below): " + "; ".join(fx) + "."


def _render_55(chat, a, mode, roles, ids, p):
    b = a.get("brief_zh") or {}
    F = zh_ref(_idx(roles, "face")); S = zh_ref(_idx(roles, "source")); base = zh_ref(_idx(roles, "base"))
    who = zh_ref(_idx(roles, "body", "face"))
    card = clean_card(p.get("card_zh"))
    P = []
    fixes = fixes_zh(a)
    if fixes:
        P.append(fixes)
    if mode == "replace":
        L = zh_ref(_idx(roles, "lineart"))
        if L:
            # силуэт: настоящий фон, человек — белый с чёрными линиями. Лицо, фигуру и тату взять неоткуда — только с эталонов.
            S = L
            P.append(f"一张真实的手机照片。{L}是一张线稿参考：白色剪影加黑色线条只提供人物的动作、姿势、表情和构图，背景是真实的照片，保持不变。"
                     f"把线稿里的人变成真人，她就是{who or F}中的这位女性。画面里不能留下任何线稿、白色剪影或黑色描边。")
        else:
            P.append(f"{S}是要修改的照片。只把{S}中的女子换成{who or F}中的这位女性，{S}里其余的一切保持完全不变。")
        keep = [f"必须保持{S}的姿势" + (f"：{_b(b, 'action')}" if _b(b, "action") else "")]
        if _b(b, "expression"):
            keep.append(f"表情：{_b(b, 'expression')}")
        if _b(b, "background"):
            keep.append(f"地点：{_b(b, 'background')}")
        if _b(b, "light"):
            keep.append(f"光线：{_b(b, 'light')}")
        if _b(b, "scene"):
            keep.append(f"拍摄方式：{_b(b, 'scene')}")
        P.append("。".join(keep) + f"。构图、透视、光线和颜色都和{S}一样：人物在画面中的大小、位置、离镜头的距离、头部角度和手的位置都和{S}完全一致。")
        if L:
            P.append(f"衣服和饰品（线稿里看不出颜色和材质，严格按文字）" + (f"：{_b(b, 'outfit')}" if _b(b, "outfit") else "") +
                     f"。衣服的款式、长度和露出的皮肤范围和{L}的线条一致；不要添加、去掉或改变任何衣服、鞋子和饰品，不要多出外套、上衣或配饰。"
                     "其他参考图只取她的脸和身材，不取它们的衣服。")
        else:
            P.append(f"衣服和饰品完全按{S}" + (f"：{_b(b, 'outfit')}" if _b(b, "outfit") else "") +
                     f"。不要添加、去掉或改变任何衣服、鞋子和饰品，不要多出外套、上衣或配饰，衣服的颜色、长度、款式和露出的皮肤范围都和{S}一样。"
                     + (f"其他参考图只取她的脸和身材，不取它们的衣服。" if who else ""))
        if body55_zh(chat, roles, ids, p):
            P.append(body55_zh(chat, roles, ids, p) + "不要沿用原图女子的身材。")
        if F:
            P.append(face55_zh(F, card))
            P.append(f"发色按{F}，不是原图女子的发色" + (f"（不是{_b(b, 'orig_hair')}）" if _b(b, "orig_hair") else "") + "。")
        if not has_tattoo(p):
            P.append("皮肤上没有任何纹身、贴纸或图案，手臂、腿、身体都是干净的皮肤（原图女子的纹身不要保留）。")
    else:
        if mode == "carousel":
            P.append(f"延续：{base}是她几分钟前拍的照片。新照片是一分钟后在同一个位置拍的：保留{base}环境里所有能认出来的东西、同样的天气、同样的光线和时间；"
                     f"同样的衣服、面料和颜色（除了下面场景里写的她拉开或脱下的部分）。只改变拍摄角度、姿势和场景里描述的动作："
                     f"姿势、机位和构图都必须和{base}明显不同，不要复制{base}的姿势。"
                     f"地点、天气、光线和衣服按{base}；她的脸和身材按身份参考图。画面里只有她一个人：没有别人，没有别人的手或胳膊。")
        else:
            P.append("一张竖屏手机照片。")
        if body55_zh(chat, roles, ids, p):
            P.append(body55_zh(chat, roles, ids, p))
        elif mode == "carousel":
            P.append(f"身材完全按{base}这张照片里她本人的身材，不要变瘦，不要缩小胯部和臀部，不要把胸部画大。")
        if F:
            P.append(face55_zh(F, card))
        if _scene55(b):
            P.append(_scene55(b))
        if _b(b, "outfit"):
            P.append(f"穿着：{_b(b, 'outfit')}。" + (f"衣服完全和{base}一样，不要添加或去掉任何衣服和饰品。" if mode == "carousel" else ""))
        elif mode == "carousel":
            P.append(f"穿着：和{base}完全一样，不要添加或去掉任何衣服和饰品。")
        if _b(b, "camera"):
            P.append(f"拍摄方式：{_b(b, 'camera')}。")
    P += cats_zh(chat, roles)
    P.append(ANATOMY_ZH)
    P.append(STYLE55_ZH)
    if _b(b, "extra"):
        P.append(_b(b, "extra") + "。")
    return "\n".join(P)


def _render_outfit(chat, a, roles, p, engine):
    """Смена одежды на готовом кадре: меняем только одежду словами пользователя, остальное — как на кадре."""
    zh = engine == "seedream"
    b = a.get("brief_zh" if zh else "brief_en") or {}
    change = _b(b, "change") or _b(b, "outfit") or _b(b, "action")
    if zh:
        base = zh_ref(_idx(roles, "base")); F = zh_ref(_idx(roles, "face")); B = zh_ref(_idx(roles, "body"))
        P = [fixes_zh(a)] if fixes_zh(a) else []
        P.append(f"只修改{base}中女子的衣服：{change}。")
        P.append(f"其余保持{base}完全不变：她的脸、表情、发型、姿势、手的位置、身材比例、背景、光线、颜色和构图都不变，画面里其他东西都不动。"
                 f"画质、清晰度和颜色和{base}一样，不要重新渲染整张照片。")
        P.append(f"新衣服合身自然：真实的布料质感和自然的褶皱，受到和{base}一样的光照和阴影；脱下的衣服不留下痕迹，衣服下面露出的身体和衣服按场景自然补全。")
        if B:
            P.append(f"露出的身体是她本人的身材，按{B}（只取身材，不取{B}的衣服、姿势和背景），不要变瘦。")
        if F:
            P.append(f"脸保持{base}里的样子，和{F}是同一个人，不要变成别人，不取{F}的衣服和背景。")
        if F and not has_tattoo(p):   # чужое фото — тату не трогаем
            P.append("皮肤上没有纹身。")
        P.append("只有两只手、两条腿，手指自然。")
        if _b(b, "extra"):
            P.append(_b(b, "extra") + "。")
        return "\n".join(P)
    base = en_ref(_idx(roles, "base")); F = en_ref(_idx(roles, "face")); B = en_ref(_idx(roles, "body"))
    P = [fixes_en(a)] if fixes_en(a) else []
    P.append(f"Edit only the woman's clothing in {base}: {change}.")
    P.append(f"Keep everything else in {base} exactly the same: her face, expression, hair, pose, hand positions, body proportions, background, lighting, colors and framing. "
             f"Same image quality and colors as {base}, do not re-render the whole photo.")
    P.append(f"The new clothing fits naturally with real fabric texture and natural folds, lit like the rest of {base}; removed garments leave no trace.")
    if B:
        P.append(f"Any newly visible body is her own figure as in {B} (figure only, not the clothes or pose); do not make her slimmer.")
    if F:
        P.append(f"Her face stays as in {base} and is the same person as in {F}.")
    if F and not has_tattoo(p):
        P.append("No tattoos on her skin.")
    return " ".join(P)


# ---------------- эталоны фигуры через GPT ----------------
BODYREF_SHOT = {
    "front": ("a plain full-body photo on a phone on a tripod in a bright simple room with a white wall and wooden floor, she stands straight facing the camera, "
              "arms relaxed at her sides, feet slightly apart, whole body from head to feet in the frame, neutral relaxed face looking into the camera, even soft daylight",
              "a fitted black tank top and high-waisted black leggings, barefoot"),
    "back": ("a plain full-body photo on a phone on a tripod in a bright simple room with a white wall and wooden floor, she stands with her back to the camera, "
             "head turned slightly over her shoulder, arms relaxed at her sides, whole body from head to feet in the frame, even soft daylight",
             "a fitted black tank top and high-waisted black leggings, barefoot"),
    "side": ("a plain full-body photo on a phone on a tripod in a bright simple room with a white wall and wooden floor, she stands sideways in strict profile to the camera, "
             "arms relaxed, whole body from head to feet in the frame, even soft daylight",
             "a fitted black tank top and high-waisted black leggings, barefoot"),
    "half": ("a plain photo on a phone on a tripod in a bright simple room with a white wall, framed from the top of her head to mid-thigh, "
             "standing facing the camera, natural slight smile, even soft daylight",
             "a fitted plain white t-shirt and grey high-waisted leggings"),
}


def _render_bodyref(a, roles, p):
    view = a.get("view") if a.get("view") in BODYREF_SHOT else "front"
    shot, outfit = BODYREF_SHOT[view]
    F = en_ref(_idx(roles, "face"))
    fig = (a.get("figure_en") or p.get("figure_en") or "").strip().rstrip(".")
    card = clean_card(p.get("card_en"))
    return "\n".join([
        f"A{shot[1:]}. No mirror. Outfit: {outfit}.",
        identity_en(F, card),
        "BODY (as important as the face): " + (f"{fig}. " if fig else "") +
        "Keep exactly these proportions: do NOT make her slimmer, skinny or a thin model type, and do not exaggerate her curves or enlarge her bust; "
        f"real proportions of a real woman. Her face exactly as in {F}.",
        REAL_EN])


# ---------------- ручные промпты: перенумерация ----------------
_PAT = re.compile(r"(图|@image|[Ii]mages?\s)(\d+)((?:\s*(?:到|–|-|—|to|and|,|、)\s*(?:图|@image|[Ii]mages?\s)?\d+)*)")


def remap(prompt, old_ids, new_ids):
    """Перенумеровать ссылки 图N / image N / @imageN после перестановки входов (по id)."""
    pos = {i: k + 1 for k, i in enumerate(new_ids)}
    m = {k + 1: pos.get(i) for k, i in enumerate(old_ids)}

    def num(n):
        v = m.get(int(n))
        return str(v) if v else n

    def sub(mt):
        tail = re.sub(r"\d+", lambda x: num(x.group(0)), mt.group(3))
        return mt.group(1) + num(mt.group(2)) + tail
    out = _PAT.sub(sub, prompt)
    added = [i for i in new_ids if i not in old_ids]
    return out, added


def is_zh(text):
    return len(CJK.findall(text or "")) > 20

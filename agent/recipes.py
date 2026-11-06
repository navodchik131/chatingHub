"""Проверенные рецепты: подбор входов и сборка промптов для GPT Image 2.5 и Seedream V5.0 Pro.

Grok описывает только сцену (brief_en / brief_zh), а входы, их порядок, нумерацию 图N / image N
и все абзацы реализма собирает код — так промпт не «худеет» и всегда совпадает с картинками.
"""
import re

MODES = ("replace", "new", "carousel", "edit", "free")
BRIEF_KEYS = ("scene", "action", "expression", "outfit", "background", "light", "change", "extra")
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
    if mode == "edit" and k == 0:
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


def pick_inputs(chat, a, engine):
    """Порядок входов по проверенным рецептам. Возвращает список id (силуэт должен уже существовать)."""
    mode = a.get("mode"); src = a.get("source_id")
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
        return [src] + faces + body + cats
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
           "毛孔清晰可见，雀斑稀疏、深浅大小不一、分布不均，不要均匀的圆点图案，肤色不均，鼻翼和脸颊微微泛红，嘴唇有细小的唇纹，"
           "脸颊有细小的绒毛。不要磨皮，不要美颜，不要蜡像感，不要塑料感，不要CG渲染感，不要偏黄偏橙，不要晒黑。")
FRAME_ZH = ("画面：像用iPhone 16随手拍的真实照片，24mm等效，柔和、低对比度，自然真实的白平衡和色彩，暗部有轻微数码噪点。"
            "不要HDR，不要锐化，不要提高清晰度，不要电影感，不要单反感，不要商业广告感，不要过度精致。画面上不要任何文字或水印。")
REAL_EN = ("Realism: looks like a real unedited iPhone 16 photo, 24mm main camera, natural light, slight sensor noise, no cinematic look. "
           "Visible pores, uneven sparse freckles, matte skin with no oily shine, fine vellus hair, crisp lashes, iris texture with catchlights, "
           "both eyes looking the same direction, slightly frizzy matte hair with darker roots and flyaways, real fabric texture and wrinkles. "
           "No retouching, no beauty filter, no plastic or CGI look, sharp background, no bokeh, no added text or watermark.")


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
def render(chat, a, engine):
    """Собрать промпт по рецепту. a — аргументы generate_image (mode, image_ids, brief_en/brief_zh…)."""
    mode = a.get("mode") or "free"
    ids = a.get("image_ids") or []
    if mode == "free":
        return a.get("prompt", "")
    roles = [role_of(chat, i, a, k) for k, i in enumerate(ids)]
    p = chat["persona"]
    if engine == "seedream":
        return _render_zh(chat, a, mode, roles, p)
    out = _render_en(chat, a, mode, roles, p)
    return out[:1].upper() + out[1:]


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
            P.append(f"服装（线稿里看不出颜色和材质，按文字）：{_b(b, 'outfit')}。真实面料纹理、自然褶皱和缝线，哑光面料，不要塑料感，衣服上没有其他文字。"
                     if L else f"服装：{_b(b, 'outfit')}，和原图一样。")
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
            P.append(f"服装：{_b(b, 'outfit')}。真实面料纹理、自然褶皱、缝线和轻微起球，哑光面料，不要塑料感，衣服上没有其他文字。")
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
            P.append(f"服装和{base}一样：{_b(b, 'outfit')}。真实面料纹理和自然褶皱，哑光。")
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
            P.append(f"Outfit: {_b(b, 'outfit')} — as in {ref}, real fabric texture, natural wrinkles and seams, matte, no extra text on clothes.")
        P.append(f"Background (keep from {ref}): {_b(b, 'background') or 'unchanged'}." + (f" Light: {_b(b, 'light')}." if _b(b, 'light') else "")
                 + " She is lit by the same light.")
    elif mode == "new":
        P.append(f"A vertical phone photo of the woman from {F}: {_b(b, 'scene')}" + (f". {_b(b, 'action')}" if _b(b, 'action') else "") + ".")
        P.append(identity_en(F, card))
        P.append("Proportions: natural head size, normal neck and shoulders, only two hands."
                 + (f" Body shape from {B} (only the proportions, not its pose or clothes), do not make her thinner." if B else ""))
        if _b(b, "outfit"):
            P.append(f"Outfit: {_b(b, 'outfit')}, real fabric texture, natural wrinkles, seams and slight pilling, matte, no extra text on clothes.")
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
            P.append(f"Outfit as in {base}: {_b(b, 'outfit')}, real fabric texture.")
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

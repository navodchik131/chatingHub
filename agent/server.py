"""Persona Studio — локальный чат с Grok для создания ИИ-моделей и генерации фото через WaveSpeed.
Запуск: python server.py   ->  http://localhost:8765
"""
import base64, datetime, io, json, mimetypes, os, re, secrets, shutil, subprocess, threading, time, traceback, uuid, zipfile
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote

from PIL import Image, ImageOps
import recipes
import hosted

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ["PS_DATA"]) if os.environ.get("PS_DATA") else ROOT / "data"
CHATS = DATA / "chats"
STATIC = ROOT / "static"
CONFIG_FILE = DATA / "config.json"
SPEND_FILE = DATA / "spend.json"
PROMPTS = ROOT / "prompts"
PROMPT_NAMES = ("system", "rules")
PORT = int(os.environ.get("PORT", "8765"))
HOST = os.environ.get("HOST", "127.0.0.1")
OWNERS = DATA / "owners"   # хостинг: настройки владельцев (autorun)
GROK_RESERVE = 0.15        # хостинг: запас на один вызов Grok при проверке баланса, $

XAI = "https://api.x.ai/v1"
WS = "https://api.wavespeed.ai/api/v3"
WS_MODELS = {"gpt": "openai/gpt-image-2.5-sunburst/edit", "seedream": "bytedance/seedream-v5.0-pro/edit"}
ENGINE_NAMES = {"gpt": "GPT Image 2.5", "seedream": "Seedream V5.0 Pro"}
VIDEO_MODEL = "bytedance/seedance-2.5/video-edit"
VIDEO_EXT = (".mp4", ".mov", ".webm", ".m4v", ".mkv", ".avi")
RESOLUTIONS = ("480p", "720p", "1080p")

DEFAULT_CONFIG = {
    "xai_key": "", "wavespeed_key": "",
    "chat_model": "grok-4",
    "autorun": False,           # False = спрашивать перед платной генерацией
    # seedance_* — цена за секунду (вход + выход)
    "prices": {"gpt": 0.22, "seedream": 0.10, "seedance_480p": 0.11, "seedance_720p": 0.22, "seedance_1080p": 0.55},
    "limits": {"per_message": 0, "per_day": 0},   # 0 = без лимита
    "max_steps": 12,
}
LOCK = threading.RLock()
RUNNING = {}   # chat_id -> {"stop": bool}


# ---------------- prompts ----------------
def prompt_file(name):
    return PROMPTS / f"{name}.md"


def default_prompt_file(name):
    return PROMPTS / f"{name}.default.md"


def ensure_prompt_defaults():
    PROMPTS.mkdir(exist_ok=True)
    for n in PROMPT_NAMES:
        f, d = prompt_file(n), default_prompt_file(n)
        if not f.exists():
            f.write_text("", encoding="utf-8")
        if not d.exists():
            shutil.copy(f, d)


def system_prompt():
    """Читается заново на каждый запрос — правки в prompts/*.md действуют без перезапуска."""
    text = prompt_file("system").read_text(encoding="utf-8")
    rules = prompt_file("rules")
    if rules.exists() and rules.read_text(encoding="utf-8").strip():
        text += "\n\n" + rules.read_text(encoding="utf-8")
    return text


# ---------------- storage ----------------
def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if CONFIG_FILE.exists():
        saved = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        for k in ("prices", "limits"):
            if isinstance(saved.get(k), dict):
                cfg[k].update(saved.pop(k))
        cfg.update(saved)
    return cfg


def save_config(cfg):
    DATA.mkdir(exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")


def today():
    return datetime.date.today().isoformat()


def spend_today():
    if SPEND_FILE.exists():
        return float(json.loads(SPEND_FILE.read_text(encoding="utf-8")).get(today(), 0))
    return 0.0


def add_spend(amount):
    with LOCK:
        d = json.loads(SPEND_FILE.read_text(encoding="utf-8")) if SPEND_FILE.exists() else {}
        d[today()] = round(float(d.get(today(), 0)) + amount, 4)
        SPEND_FILE.write_text(json.dumps(d), encoding="utf-8")


def chat_dir(cid):
    if not re.fullmatch(r"[a-z0-9]{8,32}", cid):
        raise ValueError("bad chat id")
    return CHATS / cid


def new_mid():
    return "m_" + secrets.token_hex(4)


def load_chat(cid):
    f = chat_dir(cid) / "chat.json"
    for k in range(40):
        try:
            c = json.loads(f.read_text(encoding="utf-8")); break
        except (PermissionError, json.JSONDecodeError):
            if k == 39:
                raise
            time.sleep(0.05 * (k + 1))
    missing = [m for m in c["messages"] if "id" not in m]
    if missing:                       # миграция старых чатов — id сохраняем сразу
        with LOCK:
            for m in missing:
                m["id"] = new_mid()
            save_chat(c)
    c["persona"].setdefault("card_en", ""); c["persona"].setdefault("card_zh", ""); c["persona"].setdefault("extra", {})
    c.setdefault("jobs", []); c.setdefault("archived", False); c.setdefault("pinned", False)
    c.setdefault("videos", {})
    return c


def save_chat(chat):
    d = chat_dir(chat["id"]); d.mkdir(parents=True, exist_ok=True)
    tmp = d / f"chat.json.{threading.get_ident()}.tmp"
    tmp.write_text(json.dumps(chat, ensure_ascii=False, indent=1), encoding="utf-8")
    for k in range(40):   # Windows: файл может быть занят чтением — повторяем
        try:
            os.replace(tmp, d / "chat.json"); return
        except PermissionError:
            time.sleep(0.05 * (k + 1))
    os.replace(tmp, d / "chat.json")


def update_chat(cid, fn):
    with LOCK:
        chat = load_chat(cid); r = fn(chat); chat["updated"] = time.time(); save_chat(chat); return r


def new_chat(name, owner=None):
    cid = uuid.uuid4().hex[:24 if owner is not None else 12]   # id чата = часть секретной ссылки на картинки
    chat = {"id": cid, "name": name or "Новая модель", "created": time.time(), "updated": time.time(), "owner": owner,
            "persona": {"card": "", "card_en": "", "card_zh": "", "faces": [], "body": [], "extra": {}},
            "images": {}, "videos": {}, "messages": [], "status": "idle", "status_text": "", "pending": None,
            "jobs": [], "spent": 0.0, "archived": False, "pinned": False}
    (chat_dir(cid) / "files").mkdir(parents=True, exist_ok=True)
    save_chat(chat)
    return chat


def add_image(cid, data: bytes, source, label="", meta=None):
    """Сохраняет картинку (любой формат) как JPEG/PNG, возвращает id."""
    iid = "img_" + secrets.token_hex(3)
    img = Image.open(io.BytesIO(data)); img = ImageOps.exif_transpose(img)
    ext = "png" if img.mode in ("RGBA", "LA", "P") and source != "user" else "jpg"
    if ext == "jpg":
        img = img.convert("RGB")
    path = chat_dir(cid) / "files" / f"{iid}.{ext}"
    img.save(path, quality=95) if ext == "jpg" else img.save(path)
    rec = {"file": path.name, "source": source, "label": label, "w": img.width, "h": img.height,
           "t": time.time(), "fav": False, **(meta or {})}
    update_chat(cid, lambda c: c["images"].__setitem__(iid, rec))
    return iid


def image_path(cid, iid, chat=None):
    chat = chat or load_chat(cid)
    if iid not in chat["images"]:
        raise KeyError(f"нет картинки {iid}")
    return chat_dir(cid) / "files" / chat["images"][iid]["file"]


# ---------------- video ----------------
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def probe_video(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
                         capture_output=True, text=True, check=True, creationflags=NOWIN).stdout
    d = json.loads(out)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    if not v:
        raise RuntimeError("в файле нет видеодорожки")
    dur = float(d["format"].get("duration") or v.get("duration") or 0)
    fps = None
    if v.get("avg_frame_rate", "0/0") != "0/0":
        a, b = v["avg_frame_rate"].split("/")
        fps = round(float(a) / float(b), 2) if float(b) else None
    w, h = v.get("width"), v.get("height")
    rot = int(float(v.get("tags", {}).get("rotate", 0) or 0))
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(float(sd["rotation"]))
    if abs(rot) % 180 == 90:
        w, h = h, w
    return {"dur": round(dur, 2), "w": w, "h": h, "fps": fps,
            "audio": any(s["codec_type"] == "audio" for s in d["streams"])}


def scene_cuts(path, dur, thr=0.3):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-vf", f"select='gt(scene,{thr})',showinfo",
                        "-an", "-f", "null", "-"], capture_output=True, text=True, creationflags=NOWIN)
    cuts = [round(float(t), 2) for t in re.findall(r"pts_time:([0-9.]+)", r.stderr)]
    return [c for c in cuts if 0.2 < c < dur - 0.1][:12]


def grab_frame(path, t, max_side=1536):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{max(t, 0):.3f}", "-i", str(path),
                        "-frames:v", "1", "-vf", f"scale='min({max_side},iw)':-2", "-q:v", "2",
                        "-f", "image2pipe", "-vcodec", "mjpeg", "-"], capture_output=True, creationflags=NOWIN)
    if not r.stdout:
        raise RuntimeError(f"не удалось взять кадр {t:.2f} с")
    return r.stdout


def add_video(cid, data, source, label="", meta=None, n_frames=8, ext=".mp4"):
    """Сохраняет видео, считывает параметры, нарезает кадры (картинки source=frame). Возвращает id."""
    vid = "vid_" + secrets.token_hex(3)
    ext = ext.lower() if ext.lower() in VIDEO_EXT else ".mp4"
    path = chat_dir(cid) / "files" / f"{vid}{ext}"
    if isinstance(data, (str, Path)):
        shutil.move(str(data), path)
    else:
        path.write_bytes(data)
    info = probe_video(path)
    cuts = scene_cuts(path, info["dur"]) if source in ("user", "trim") else []
    dur = info["dur"] or 1
    times = [dur * (i + 0.5) / n_frames for i in range(n_frames)] + [min(c + 0.1, dur - 0.05) for c in cuts]
    times = sorted({round(t, 2) for t in times})[:16]
    frames = []
    for t in times:
        try:
            frames.append(add_image(cid, grab_frame(path, t), "frame", f"{vid} · {t:.1f}s", {"video": vid, "vt": t}))
        except Exception:
            traceback.print_exc()
    rec = {"file": path.name, "source": source, "label": label, **info, "cuts": cuts, "frames": frames,
           "t": time.time(), "fav": False, **(meta or {})}
    update_chat(cid, lambda c: c["videos"].__setitem__(vid, rec))
    return vid


_CASCADES = {}


def _cascade(name):
    import cv2
    if name not in _CASCADES:
        _CASCADES[name] = cv2.CascadeClassifier(cv2.data.haarcascades + name)
    return _CASCADES[name]


def face_score(jpeg):
    """Насколько хорошо видно лицо: крупнее и анфас — лучше, два открытых глаза — сильно лучше."""
    import cv2, numpy as np
    bgr = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    if bgr is None:
        return 0.0
    g = cv2.equalizeHist(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY))
    h, w = g.shape
    best = 0.0
    for (x, y, fw, fh) in _cascade("haarcascade_frontalface_default.xml").detectMultiScale(g, 1.1, 6, minSize=(max(24, w // 30),) * 2):
        roi = g[y: y + fh // 2 + fh // 8, x: x + fw]
        eyes = [e for e in _cascade("haarcascade_eye.xml").detectMultiScale(roi, 1.1, 5, minSize=(max(6, fw // 9),) * 2)
                if e[1] + e[3] / 2 < fh * 0.6]
        sc = (fw * fh) / (w * h) * (1.0 + 1.5 * min(len(eyes), 2)) * (0.3 if not eyes else 1.0)
        best = max(best, sc)
    return best


def face_times(cid, vid):
    """Секунды, где лицо видно лучше всего (анфас, глаза открыты). Кэшируется в записи видео."""
    chat = load_chat(cid); rec = chat["videos"][vid]
    if "face_times" in rec:
        return rec["face_times"]
    path = video_path(cid, vid, chat); dur = float(rec.get("dur") or 0)
    step = max(0.25, dur / 32)
    res = []
    t = 0.1
    while t < dur - 0.05:
        try:
            sc = face_score(grab_frame(path, t, 960))
            if sc > 0:
                res.append((sc, round(t, 2)))
        except Exception:
            traceback.print_exc()
        t += step
    res.sort(reverse=True)
    top = []
    for sc, t in res:   # разнесённые по времени моменты
        if all(abs(t - u) >= 1.0 for u in top):
            top.append(t)
        if len(top) == 3:
            break
    update_chat(cid, lambda c: c["videos"][vid].__setitem__("face_times", top))
    return top


def white_ratio(path):
    """Доля почти белых серых пикселей — у силуэта (белая фигура с линиями) она в разы выше, чем у оригинала."""
    im = Image.open(path).convert("RGB"); im.thumbnail((256, 256))
    px = list(im.getdata())
    return sum(1 for r, g, b in px if min(r, g, b) > 228 and max(r, g, b) - min(r, g, b) < 14) / max(len(px), 1)


def detect_pair(cid, vids):
    """Два видео в сообщении: какое из них готовый силуэт. → {"orig", "sil", "dur_diff"} или None."""
    chat = load_chat(cid)
    recs = [chat["videos"].get(v) for v in vids]
    if len(vids) != 2 or not all(recs):
        return None
    score = []
    for v, r in zip(vids, recs):
        fr = [i for i in r.get("frames", []) if i in chat["images"]][:6]
        vals = []
        for i in fr:
            try:
                vals.append(white_ratio(image_path(cid, i, chat)))
            except Exception:
                traceback.print_exc()
        score.append(sum(vals) / len(vals) if vals else 0.0)
    hi = 0 if score[0] >= score[1] else 1
    lo = 1 - hi
    orig, sil = vids[lo], vids[hi]
    dd = round(abs((recs[lo].get("dur") or 0) - (recs[hi].get("dur") or 0)), 2)
    # у силуэта тот же фон + белая фигура → белого заметно больше; белая стена в оригинале есть в обоих
    if score[hi] - score[lo] < 0.03 or (dd > 1.0 and score[hi] < 2.0 * score[lo]):
        return None   # не похоже на «оригинал + силуэт» — пусть разбирается Grok
    update_chat(cid, lambda c: c["videos"][sil].update(source="lineart", inputs_video=orig, label=f"силуэт (ваш) {orig}"))
    return {"orig": orig, "sil": sil, "dur_diff": dd, "white": [round(x, 3) for x in score]}


def video_path(cid, vid, chat=None):
    chat = chat or load_chat(cid)
    if vid not in chat["videos"]:
        raise KeyError(f"нет видео {vid}")
    return chat_dir(cid) / "files" / chat["videos"][vid]["file"]


def video_cost(dur, res, cfg):
    d = min(max(float(dur or 0), 0.1), 30.0)
    return round((d + max(4.0, d)) * float(cfg["prices"].get(f"seedance_{res}", 0.11)), 2)


def delete_videos(cid, ids):
    c = load_chat(cid)
    frames = [f for v in ids if v in c["videos"] for f in c["videos"][v].get("frames", [])]

    def f(c):
        n = 0
        for v in ids:
            rec = c["videos"].pop(v, None)
            if rec:
                n += 1
                (chat_dir(cid) / "files" / rec["file"]).unlink(missing_ok=True)
                (chat_dir(cid) / "thumbs" / (Path(rec["file"]).stem + ".jpg")).unlink(missing_ok=True)
        return n
    n = update_chat(cid, f)
    keep = set(all_ref_ids(load_chat(cid)["persona"]))
    delete_images(cid, [i for i in frames if i not in keep])
    return n


BUILTIN = {"faces": "Лицо", "body": "Тело"}
ALIASES = {"лицо": "faces", "лица": "faces", "face": "faces", "faces": "faces", "портрет": "faces",
           "тело": "body", "фигура": "body", "body": "body"}


def cat_key(p, name):
    """Имя категории от пользователя/Grok -> ключ: faces, body или имя доп. категории."""
    n = (name or "").strip()
    if n.lower() in ALIASES:
        return ALIASES[n.lower()]
    for k in p.get("extra", {}):
        if k.lower() == n.lower():
            return k
    return n[:40].strip() or "Разное"


def ref_groups(p):
    """[(key, name, ids, note)] — все категории эталонов модели."""
    out = [("faces", "Лицо", p["faces"], p.get("notes", {}).get("faces", "")),
           ("body", "Тело", p["body"], p.get("notes", {}).get("body", ""))]
    for k, v in p.get("extra", {}).items():
        out.append((k, k, v.get("ids", []), v.get("note", "")))
    return out


def all_ref_ids(p):
    return [i for _, _, ids, _ in ref_groups(p) for i in ids]


def group_ids(p, key):
    if key in BUILTIN:
        return p[key]
    return p.setdefault("extra", {}).setdefault(key, {"ids": [], "note": ""})["ids"]


def set_group_ids(p, key, ids):
    if key in BUILTIN:
        p[key] = ids
    else:
        p.setdefault("extra", {}).setdefault(key, {"ids": [], "note": ""})["ids"] = ids


def data_uri(path, max_side=None, quality=90):
    img = Image.open(path).convert("RGB")
    if max_side and max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=quality)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def delete_images(cid, ids):
    def f(c):
        n = 0
        for i in ids:
            rec = c["images"].pop(i, None)
            if rec:
                n += 1
                try:
                    (chat_dir(cid) / "files" / rec["file"]).unlink()
                    (chat_dir(cid) / "thumbs" / (Path(rec["file"]).stem + ".jpg")).unlink(missing_ok=True)
                except FileNotFoundError:
                    pass
        for k in ("faces", "body"):
            c["persona"][k] = [i for i in c["persona"][k] if i in c["images"]]
        for v in c["persona"].get("extra", {}).values():
            v["ids"] = [i for i in v["ids"] if i in c["images"]]
        return n
    return update_chat(cid, f)


# ---------------- http helpers ----------------
def http_json(url, key, payload=None, method=None, timeout=180):
    req = urllib.request.Request(url, data=json.dumps(payload).encode() if payload is not None else None,
                                 method=method or ("POST" if payload is not None else "GET"),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                          "User-Agent": "persona-studio/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:1500]
        raise RuntimeError(f"HTTP {e.code}: {body}")
    except (TimeoutError, urllib.error.URLError, ConnectionError) as e:
        raise RuntimeError(f"NET {type(e).__name__}: {getattr(e, 'reason', e)}")


def download(url):
    req = urllib.request.Request(url, headers={"User-Agent": "persona-studio/1.0"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read()


# ---------------- generators ----------------
def ws_upload_path(path, key):
    boundary = "----ps" + secrets.token_hex(8)
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
            f"Content-Type: {mimetypes.guess_type(path.name)[0] or 'application/octet-stream'}\r\n\r\n").encode() + \
        path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"{WS}/media/upload/binary", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.load(r)["data"]["download_url"]
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"WaveSpeed upload HTTP {e.code}: {e.read().decode('utf-8','replace')[:500]}")


def ws_upload(cid, iid, key, kind="images"):
    chat = load_chat(cid)
    rec = chat[kind][iid]
    if rec.get("ws_url"):
        return rec["ws_url"]
    path = (image_path if kind == "images" else video_path)(cid, iid, chat)
    url = ws_upload_path(path, key)
    update_chat(cid, lambda c: c[kind][iid].__setitem__("ws_url", url) if iid in c[kind] else None)
    return url


def ws_wait(job_id, key, limit=600, every=3):
    t0 = time.time()
    while True:
        try:
            res = http_json(f"{WS}/predictions/{job_id}/result", key, timeout=60)["data"]
        except RuntimeError as e:   # сбой сети при опросе — задача оплачена и идёт, не бросаем её
            if not (str(e).startswith("NET ") or re.match(r"HTTP 5\d\d", str(e))) or time.time() - t0 > limit:
                raise
            time.sleep(every)
            continue
        if res["status"] in ("completed", "failed"):
            break
        if time.time() - t0 > limit:
            raise RuntimeError(f"таймаут WaveSpeed (задача {job_id} может ещё доделаться — проверь на wavespeed.ai)")
        time.sleep(every)
    if res["status"] == "failed":
        raise RuntimeError(f"WaveSpeed failed: {res.get('error')}")
    return res


def gen_video(cid, vid, prompt, image_ids, resolution, audio, cfg, on_submit=None):
    key = cfg["wavespeed_key"]
    if not key:
        raise RuntimeError("Нет ключа WaveSpeed — Seedance недоступен")
    if key == "mock":   # самопроверка без оплаты: «результат» = входное видео
        time.sleep(1)
        return video_path(cid, vid).read_bytes()
    payload = {"video": ws_upload(cid, vid, key, "videos"), "prompt": prompt,
               "reference_images": [ws_upload(cid, i, key) for i in image_ids],
               "resolution": resolution, "generate_audio": bool(audio)}
    job = http_json(f"{WS}/{VIDEO_MODEL}", key, payload)["data"]
    if on_submit:
        on_submit(job["id"])
    res = ws_wait(job["id"], key, limit=1800, every=5)
    return download(res["outputs"][0])


def gen_wavespeed(cid, engine, prompt, image_ids, aspect, cfg):
    key = cfg["wavespeed_key"]
    if not key:
        raise RuntimeError("Нет ключа WaveSpeed — движки gpt/seedream недоступны")
    if not image_ids:
        raise RuntimeError(f"{engine} работает только как edit — нужна хотя бы одна картинка (эталон лица)")
    if key == "mock":   # самопроверка без оплаты и без отправки файлов: «результат» = первая входная картинка
        time.sleep(0.5)
        return [image_path(cid, image_ids[0]).read_bytes()]
    urls = [ws_upload(cid, i, key) for i in image_ids]
    payload = {"images": urls, "prompt": prompt, "resolution": "2k"}
    if engine == "gpt":
        payload.update(quality="high")
        if aspect and aspect != "auto":
            payload["aspect_ratio"] = aspect
    else:
        payload["prompt_optimization_mode"] = "standard"
    job = http_json(f"{WS}/{WS_MODELS[engine]}", key, payload)["data"]
    res = ws_wait(job["id"], key)
    return [download(u) for u in res["outputs"]]


# ---------------- tools ----------------
TOOLS = [
    {"type": "function", "function": {
        "name": "generate_image",
        "description": "Сгенерировать кадр через WaveSpeed (GPT Image 2.5 или Seedream V5.0 Pro). В режимах replace/new/carousel/edit входы (лица, тело, силуэт, фактура) и полный промпт с абзацами реализма собирает ПРИЛОЖЕНИЕ по проверенному рецепту — ты даёшь только mode, source_id и описание сцены brief_en + brief_zh (для carousel и new — ОБЯЗАТЕЛЬНО, у каждого кадра своё: scene с ракурсом и крупностью, action, expression; одной подписи label мало). Силуэт для Seedream-замены приложение сделает само. mode=free — только для особых случаев (создание эталонов модели, детализирующий проход, дорисовка серой области): тогда сам пишешь prompt и image_ids. Несколько вызовов в одном ответе идут параллельно.",
        "parameters": {"type": "object", "properties": {
            "engine": {"type": "string", "enum": ["gpt", "seedream"]},
            "mode": {"type": "string", "enum": list(recipes.MODES), "description": "replace — заменить девушку на фото/кадре видео на модель; new — новый кадр по описанию; carousel — новый кадр той же серии по основе; edit — локальная правка основы; free — свой промпт"},
            "source_id": {"type": "string", "description": "replace: исходное фото/кадр (не силуэт); carousel/edit: основа"},
            "brief_en": {"type": "object", "properties": {
                "scene": {"type": "string", "description": "что за кадр и кто снимает: селфи в зеркале / подруга снимает снизу / в рост на стадионе"},
                "action": {"type": "string", "description": "поза, куда смотрит, что делают руки, что в руках"},
                "expression": {"type": "string", "description": "эмоция словами точно как на исходнике"},
                "outfit": {"type": "string", "description": "одежда, обувь, аксессуары: цвета, ткань, крой, принты"},
                "background": {"type": "string", "description": "что на фоне (для замены — что сохранить)"},
                "light": {"type": "string", "description": "свет и время суток"},
                "change": {"type": "string", "description": "только для mode=edit: что именно поменять"},
                "extra": {"type": "string", "description": "особые указания: убрать тату, зеркальное отражение, другие люди не трогать…"}}}, "brief_zh": {"type": "object", "properties": {
                "scene": {"type": "string", "description": "что за кадр и кто снимает: селфи в зеркале / подруга снимает снизу / в рост на стадионе"},
                "action": {"type": "string", "description": "поза, куда смотрит, что делают руки, что в руках"},
                "expression": {"type": "string", "description": "эмоция словами точно как на исходнике"},
                "outfit": {"type": "string", "description": "одежда, обувь, аксессуары: цвета, ткань, крой, принты"},
                "background": {"type": "string", "description": "что на фоне (для замены — что сохранить)"},
                "light": {"type": "string", "description": "свет и время суток"},
                "change": {"type": "string", "description": "только для mode=edit: что именно поменять"},
                "extra": {"type": "string", "description": "особые указания: убрать тату, зеркальное отражение, другие люди не трогать…"}}},
            "face_angle": {"type": "string", "enum": ["front", "34", "profile"], "description": "ракурс лица в кадре — этот портрет пойдёт первым"},
            "body_view": {"type": "string", "enum": ["front", "34", "side", "back", "back34"], "description": "ракурс тела в кадре — какой эталон тела взять"},
            "framing": {"type": "string", "enum": ["face", "half", "full"], "description": "крупность кадра: face — лицо/плечи (эталоны тела и категории тела НЕ берутся), half — по пояс, full — в рост"},
            "categories": {"type": "array", "items": {"type": "string"}, "description": "доп. категории эталонов — ТОЛЬКО то, что реально видно в этом кадре (ноги — если ноги в кадре), максимум 2; лишний эталон сбивает композицию и дорожает"},
            "with_faces": {"type": "boolean", "description": "edit: добавить портреты (если правка касается лица)"},
            "no_texture": {"type": "boolean", "description": "не класть ★ кадр GPT как референс фактуры"},
            "prompt": {"type": "string", "description": "только для mode=free: полный промпт (английский для gpt, китайский для seedream)"},
            "image_ids": {"type": "array", "items": {"type": "string"}, "description": "только для mode=free: входы по порядку"},
            "image_roles": {"type": "array", "items": {"type": "string"}},
            "aspect_ratio": {"type": "string", "enum": ["auto", "1:1", "3:4", "4:5", "2:3", "9:16", "4:3", "16:9"]},
            "label": {"type": "string", "description": "Короткая подпись кадра, например 'карусель 2: портрет'"}},
            "required": ["engine", "mode"]}}},
    {"type": "function", "function": {
        "name": "carousel",
        "description": "Карусель N кадров по основе. ВСЕГДА используй его для «карусель N» (а не N вызовов generate_image): приложение само смотрит на основу, "
                       "планирует N разных кадров (ракурс камеры, крупность, поза, эмоция) и запускает их параллельно по проверенному рецепту.",
        "parameters": {"type": "object", "properties": {
            "source_id": {"type": "string", "description": "основа — принятый кадр (img_…)"},
            "n": {"type": "integer", "minimum": 2, "maximum": 8},
            "engine": {"type": "string", "enum": ["seedream", "gpt"], "description": "по умолчанию — движок основы"},
            "wishes": {"type": "string", "description": "пожелания пользователя к кадрам, если есть (по-русски)"}},
            "required": ["n"]}}},
    {"type": "function", "function": {
        "name": "lineart",
        "description": "Перерисовать человека на фото линейным силуэтом (белый с чёрными линиями, фон настоящий). Бесплатно, локально, ~10-30 с.",
        "parameters": {"type": "object", "properties": {"image_id": {"type": "string"}}, "required": ["image_id"]}}},
    {"type": "function", "function": {
        "name": "crop",
        "description": "Обрезать картинку под соотношение сторон. offset_y/offset_x 0..1: 0 — верх/лево, 0.5 — центр, 1 — низ/право.",
        "parameters": {"type": "object", "properties": {
            "image_id": {"type": "string"}, "aspect_ratio": {"type": "string", "description": "например 4:5"},
            "offset_x": {"type": "number"}, "offset_y": {"type": "number"}},
            "required": ["image_id", "aspect_ratio"]}}},
    {"type": "function", "function": {
        "name": "set_persona",
        "description": "Сохранить модель: карточку внешности (RU, EN, ZH) и/или эталоны. faces/body — полный новый список id (заменяет старый).",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"}, "card": {"type": "string", "description": "карточка по-русски"},
            "card_en": {"type": "string", "description": "identity-абзац для GPT по-английски"},
            "card_zh": {"type": "string", "description": "人物身份 для Seedream по-китайски"},
            "faces": {"type": "array", "items": {"type": "string"}},
            "body": {"type": "array", "items": {"type": "string"}}}}}},
    {"type": "function", "function": {
        "name": "add_reference",
        "description": "Сохранить картинки в модель как эталоны категории. category: 'faces' (лицо), 'body' (тело) или любая своя категория по-русски: 'Ноги', 'Руки', 'Спина', 'Тату', 'Ногти', 'Волосы', 'Улыбка', 'Образ: спорт', 'Телефон'… Если категории нет — создастся. note — что ВИДНО на эталонах этой категории (форма, детали, цвет), заменяет прежнюю заметку категории. После этого обнови карточку через set_persona.",
        "parameters": {"type": "object", "properties": {
            "image_ids": {"type": "array", "items": {"type": "string"}},
            "category": {"type": "string"},
            "labels": {"type": "array", "items": {"type": "string"}, "description": "подпись ракурса для каждой картинки по порядку: 'анфас', 'сбоку', 'крупно'…"},
            "note": {"type": "string", "description": "описание категории по-русски, 1–3 предложения"},
            "position": {"type": "string", "enum": ["end", "start"], "description": "start — сделать главным эталоном"}},
            "required": ["image_ids", "category"]}}},
    {"type": "function", "function": {
        "name": "remove_reference",
        "description": "Убрать картинки из категории эталонов (сами картинки остаются в чате). С delete_category=true — удалить категорию целиком (кроме faces/body).",
        "parameters": {"type": "object", "properties": {
            "category": {"type": "string"}, "image_ids": {"type": "array", "items": {"type": "string"}},
            "delete_category": {"type": "boolean"}}, "required": ["category"]}}},
    {"type": "function", "function": {
        "name": "postprocess",
        "description": "Бесплатная локальная обработка картинки, результат — новая картинка. Операции по порядку: "
                       "color_match {ref_id, strength 0..1} — подогнать цвет, яркость и контраст под эталонный кадр (исходник при замене или удачный кадр GPT); "
                       "matte {strength 0..1} — приглушить жирный блеск на коже; grain {amount 3..10} — мягкий шум телефона; "
                       "upscale {factor 2..4} — увеличить маленький исходник перед силуэтом; "
                       "gray_mask {polygon [[x,y],...] в долях 0..1} — закрасить область серым, чтобы потом попросить генератор дорисовать её.",
        "parameters": {"type": "object", "properties": {
            "image_id": {"type": "string"},
            "ops": {"type": "array", "items": {"type": "object", "properties": {
                "op": {"type": "string", "enum": ["color_match", "matte", "grain", "upscale", "gray_mask"]},
                "ref_id": {"type": "string"}, "strength": {"type": "number"}, "amount": {"type": "number"},
                "factor": {"type": "number"}, "polygon": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}}},
                "required": ["op"]}},
            "label": {"type": "string"}},
            "required": ["image_id", "ops"]}}},
    {"type": "function", "function": {
        "name": "review",
        "description": "Итог проверки результата для пользователя: отдельная карточка с галочками и крестиками и кнопками следующих действий. Вызывай после проверки каждой генерации.",
        "parameters": {"type": "object", "properties": {
            "image_ids": {"type": "array", "items": {"type": "string"}},
            "video_ids": {"type": "array", "items": {"type": "string"}, "description": "проверенные видео (vid_…)"},
            "ok": {"type": "array", "items": {"type": "string"}, "description": "что совпало"},
            "issues": {"type": "array", "items": {"type": "string"}, "description": "огрехи"},
            "suggestions": {"type": "array", "items": {"type": "string"}, "description": "2-3 коротких следующих действия, например 'Локальная правка: убери тату'"}},
            "required": ["ok", "issues"]}}},
    {"type": "function", "function": {
        "name": "video_frames",
        "description": "Бесплатно вынуть кадры из видео в нужные секунды (полное разрешение) — для разбора момента или как основа для ключевых кадров с заменой через generate_image.",
        "parameters": {"type": "object", "properties": {
            "video_id": {"type": "string"}, "times": {"type": "array", "items": {"type": "number"}, "description": "секунды"},
            "label": {"type": "string"}}, "required": ["video_id", "times"]}}},
    {"type": "function", "function": {
        "name": "trim_video",
        "description": "Бесплатно обрезать видео (start..end в секундах). Делай, если ролик длиннее 30 с или есть хвосты без действия — Seedance платится за секунды.",
        "parameters": {"type": "object", "properties": {
            "video_id": {"type": "string"}, "start": {"type": "number"}, "end": {"type": "number"}},
            "required": ["video_id", "start", "end"]}}},
    {"type": "function", "function": {
        "name": "lineart_video",
        "description": "Бесплатно, локально: перерисовать человека во ВСЁМ видео линейным силуэтом (белый с чёрными линиями, фон настоящий, звук сохраняется). Нужен, чтобы Seedance реально сменил лицо. Долго: ~15–20 с на каждую секунду ролика (15 с ролик ≈ 4–5 мин).",
        "parameters": {"type": "object", "properties": {"video_id": {"type": "string"}}, "required": ["video_id"]}}},
    {"type": "function", "function": {
        "name": "edit_video",
        "description": "Платно: Seedance 2.5 Video Edit через WaveSpeed — заменить человека в видео. video_id — основа (обычно силуэт из lineart_video), image_ids — референсы по порядку (@image1, @image2…: ключевые кадры с заменой, потом портрет). Цена = (секунды входа + выхода) × цена разрешения. Ролик 4–30 с.",
        "parameters": {"type": "object", "properties": {
            "video_id": {"type": "string"},
            "prompt": {"type": "string", "description": "один цельный промпт на китайском"},
            "image_ids": {"type": "array", "items": {"type": "string"}},
            "image_roles": {"type": "array", "items": {"type": "string"}},
            "resolution": {"type": "string", "enum": list(RESOLUTIONS), "description": "по умолчанию 480p"},
            "generate_audio": {"type": "boolean", "description": "false (по умолчанию) — оставить исходный звук и липсинк"},
            "label": {"type": "string"}},
            "required": ["video_id", "prompt", "image_ids"]}}},
]
PAID = ("generate_image", "edit_video")
QUIET = ("set_persona", "review", "add_reference", "remove_reference")


def gen_price(engine, n_images, cfg):
    """Цена одной картинки WaveSpeed. В хостинге — точная (2k, high; + за каждый доп. вход), локально — из настроек."""
    if cfg.get("_ctx"):
        n = max(1, int(n_images or 1))
        return (0.165 + 0.015 * (n - 1)) if engine == "gpt" else (0.09 + 0.003 * (n - 1))
    return cfg["prices"].get(engine, 0.1)


def money(cfg, usd):
    ctx = cfg.get("_ctx")
    if ctx:
        return f"{hosted.credits(ctx, usd)} кр." if ctx.get("ws_mode") == "platform" else f"${usd:.2f} с вашего WaveSpeed"
    return f"${usd:.2f}"


def charges_ws(cfg):
    ctx = cfg.get("_ctx")
    return bool(ctx) and ctx.get("ws_mode") == "platform"


def xai_chat(cfg, payload, timeout=180, cid=None, kind="grok"):
    """Запрос к Grok. В хостинге: проверка баланса до и списание по фактическим токенам после."""
    ctx = cfg.get("_ctx")
    if ctx:
        prob = hosted.check(ctx, GROK_RESERVE)
        if prob:
            raise hosted.NoCredits(prob[:1].upper() + prob[1:] + ".")
    for attempt in range(3):   # xAI иногда отвечает 5xx «Internal error during token generation» — повторяем
        try:
            res = http_json(f"{XAI}/chat/completions", cfg["xai_key"], payload, timeout=timeout)
            break
        except RuntimeError as e:
            net = str(e).startswith("NET ")
            if attempt == (1 if net else 2) or not (net or re.match(r"HTTP 5\d\d", str(e))):
                raise RuntimeError(("Grok не ответил вовремя — попробуйте ещё раз" if net else "Grok временно недоступен") + f" ({e})")
            time.sleep(4 * (attempt + 1))
    if ctx:
        bill(cfg, cid, f"agent_{kind}", usage=res.get("usage"), model=payload.get("model"))
    return res


def bill(cfg, cid, kind, usd=0.0, usage=None, model=None, meta=None):
    r = hosted.charge(cfg["_ctx"], kind, usd=usd, usage=usage, model=model, meta={"chat": cid, **(meta or {})})
    spent = float(r.get("usd") or usd or 0)
    if cid and spent:
        update_chat(cid, lambda c: c.__setitem__("spent", round(c.get("spent", 0) + spent, 4)))
    return r


def no_brief(a):
    """Карусель/новый кадр без описания сцены — модель просто повторит основу."""
    return a.get("mode") in ("carousel", "new") and not any(
        (a.get(f"brief_{L}") or {}).get(k) for L in ("en", "zh") for k in ("scene", "action") if isinstance(a.get(f"brief_{L}"), dict))


def tool_cost(call, cfg, chat=None):
    nm = call["function"]["name"]; a = parse_args(call)
    if nm == "edit_video":
        rec = (chat or {}).get("videos", {}).get(a.get("video_id"), {})
        return video_cost(rec.get("dur", 10), a.get("resolution", "480p"), cfg)
    if nm != "generate_image":
        return 0.0
    if no_brief(a):
        return 0.0   # не запустится (см. prepare) — не спрашиваем подтверждения и не резервируем
    return gen_price(a.get("engine", "gpt"), len(a.get("image_ids") or []), cfg)


def parse_args(call):
    try:
        return json.loads(call["function"].get("arguments") or "{}")
    except json.JSONDecodeError:
        return {}


def apply_op(cid, img, op):
    import numpy as np
    from PIL import ImageFilter, ImageDraw
    kind = op.get("op")
    a = np.asarray(img).astype(np.float32)
    if kind == "color_match":
        ref = Image.open(image_path(cid, op["ref_id"])).convert("RGB").resize((400, 700))
        r = np.asarray(ref).astype(np.float32); s = float(op.get("strength", 0.8))
        res = a.copy()
        for ch in range(3):
            m, sd = a[..., ch].mean(), max(a[..., ch].std(), 1e-3); tm, tsd = r[..., ch].mean(), r[..., ch].std()
            res[..., ch] = (a[..., ch] - m) * (tsd / sd) + tm
        return Image.fromarray(np.clip(a + (res - a) * s, 0, 255).astype(np.uint8))
    if kind == "matte":
        s = float(op.get("strength", 0.6)); x = a / 255
        blur = np.asarray(img.filter(ImageFilter.GaussianBlur(6))).astype(np.float32) / 255
        lum = x.mean(2, keepdims=True); lb = blur.mean(2, keepdims=True)
        warm = np.clip((x[..., 0:1] - x[..., 2:3]) * 8, 0, 1)
        spec = np.clip((lum - lb) * 6, 0, 1) * warm * np.clip((lum - 0.35) * 3, 0, 1)
        res = x - (x - blur) * spec * s * 1.5
        res = res - (np.clip(lum - 0.55, 0, 1) * 0.25 * s) * warm
        return Image.fromarray((np.clip(res, 0, 1) * 255).astype(np.uint8))
    if kind == "grain":
        amt = float(op.get("amount", 6)); rng = np.random.default_rng(1)
        n = rng.normal(0, 1, a.shape[:2]).astype(np.float32)
        n = np.asarray(Image.fromarray(((n * 40) + 128).clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7))).astype(np.float32) - 128
        n /= max(n.std(), 1e-3)
        w = amt * (1.4 - a.mean(2, keepdims=True) / 255)
        return Image.fromarray((a + n[..., None] * w).clip(0, 255).astype(np.uint8))
    if kind == "upscale":
        f = max(1.0, min(4.0, float(op.get("factor", 2))))
        return img.resize((round(img.width * f), round(img.height * f)), Image.LANCZOS)
    if kind == "gray_mask":
        pts = [(float(x) * img.width, float(y) * img.height) for x, y in op.get("polygon", [])]
        if len(pts) >= 3:
            img = img.copy(); ImageDraw.Draw(img).polygon(pts, fill=(128, 128, 128))
        return img
    raise RuntimeError(f"неизвестная операция {kind}")


def make_lineart(cid, src_id):
    import lineart as la   # тяжёлый импорт (rembg) — только по требованию
    import cv2, numpy as np
    src = image_path(cid, src_id)
    bgr = cv2.imdecode(np.fromfile(str(src), np.uint8), cv2.IMREAD_COLOR)
    ok, buf = cv2.imencode(".png", la.lineart(bgr))
    return add_image(cid, buf.tobytes(), "lineart", f"силуэт {src_id}", {"inputs": [src_id]})


LANG = {"en": "английский", "zh": "китайский (упрощённый)"}


def grok_translate(text, lang, cfg):
    """Перевести промпт (или JSON-описание сцены) на en/zh одним коротким запросом к Grok."""
    if not text:
        return text
    if cfg.get("xai_key") == "mock":
        return f"[{lang}] {text}"
    if not cfg.get("xai_key"):
        return text
    res = xai_chat(cfg, {"model": cfg["chat_model"], "temperature": 0.2, "messages": [
        {"role": "system", "content": f"Переведи текст для генератора изображений на {LANG[lang]} язык. Сохрани смысл и все детали полностью, ничего не добавляй. "
                                      "Ссылки на картинки переводи точно: 图N = image N, 图A到图B = images A–B, @imageN не трогай. "
                                      "Если на входе JSON — верни JSON с теми же ключами. Верни только перевод."},
        {"role": "user", "content": text}]}, timeout=120, kind="grok_translate")
    out = (res["choices"][0]["message"].get("content") or text).strip()
    if out.startswith("```"):
        out = out.strip("`").removeprefix("json").strip()
    return out


def translate_brief(brief, lang, cfg):
    if cfg.get("xai_key") == "mock":
        return {k: f"[{lang}] {v}" for k, v in brief.items()}
    try:
        out = json.loads(grok_translate(json.dumps(brief, ensure_ascii=False), lang, cfg))
        return out if isinstance(out, dict) else brief
    except (json.JSONDecodeError, RuntimeError):
        return brief


def auto_brief(cid, src, cfg):
    """Страховка: Grok не дал описание сцены — отдельный короткий запрос описывает исходник для рецепта замены."""
    if cfg.get("xai_key") in ("", None, "mock"):
        return {}
    keys = ["scene", "action", "expression", "outfit", "background", "light"]
    res = xai_chat(cfg, {"model": cfg["chat_model"], "temperature": 0.2, "messages": [
        {"role": "system", "content": "Ты описываешь фото для замены девушки на другую модель. Описывай ТОЛЬКО то, что реально видно, ничего не выдумывай. "
                                      "Верни JSON {\"en\": {...}, \"zh\": {...}} с одинаковыми по смыслу полями: "
                                      "scene (что за кадр, кто снимает, ракурс и крупность), action (поза, куда смотрит, что делают руки, что в руках), "
                                      "expression (эмоция точно), outfit (вся одежда, обувь, аксессуары: цвета, ткань, крой, принты), "
                                      "background (что на фоне), light (свет и время суток). Коротко, без внешности лица и волос. Только JSON."},
        {"role": "user", "content": [{"type": "text", "text": "Опиши фото:"},
                                     {"type": "image_url", "image_url": {"url": data_uri(image_path(cid, src), 1024, 88), "detail": "high"}}]}]}, timeout=120, cid=cid, kind="grok_brief")
    out = (res["choices"][0]["message"].get("content") or "").strip()
    out = out[out.find("{"):out.rfind("}") + 1]
    d = json.loads(out)
    return {L: {k: str(v) for k, v in (d.get(L) or {}).items() if k in keys and v} for L in ("en", "zh")}


def guess_source(chat, a):
    """Если Grok не указал source_id — первое не-эталонное фото из image_ids или последнее фото пользователя/кадр видео."""
    if a.get("source_id") in chat["images"]:
        return a["source_id"]
    refs = set(all_ref_ids(chat["persona"]))
    for i in a.get("image_ids") or []:
        r = chat["images"].get(i, {})
        if i not in refs and r.get("source") != "lineart":
            return i
    cands = [(r["t"], i) for i, r in chat["images"].items() if r.get("source") in ("user", "frame") and i not in refs]
    return max(cands)[1] if cands else None


CAROUSEL_TEMPLATE = [   # запасной план, если Grok не ответил: разные ракурс, крупность, поза, эмоция
    ("крупно, 3/4, улыбка", "face", "34", "34",
     "近景，镜头在她脸前约半米、略高于眼睛，取景从头顶到锁骨，她的脸转成3/4侧面", "她的一只手轻轻碰着下巴", "被逗笑，自然地笑出来，眼睛微微眯起",
     "close shot, camera half a meter from her face slightly above eye level, framed from the top of the head to the collarbones, her face turned to a 3/4 angle",
     "one hand lightly touching her chin", "laughing naturally, eyes slightly squinted"),
    ("по пояс, профиль, взгляд в сторону", "half", "profile", "side",
     "中景侧面，镜头在她身体左侧约一米半、胸口高度，取景从头顶到腰部", "她侧身站着，双手把头发拢到一边肩膀上，看向画面外", "放松、若有所思",
     "medium shot from the side, camera about 1.5 m to her left at chest height, framed from the top of the head to the waist",
     "standing sideways, gathering her hair over one shoulder with both hands, looking off-frame", "relaxed, thoughtful"),
    ("в рост, со спины, через плечо", "full", "34", "back34",
     "全身背面视角，镜头在她身后约三米、腰部高度，取景从头到脚", "她背对镜头站着，把头转过来越过右肩看向镜头，一只手放在腰上", "俏皮的坏笑",
     "full-body view from behind, camera about 3 m behind her at waist height, framed head to toe",
     "standing with her back to the camera, turning her head over her right shoulder to look into the lens, one hand on her waist", "playful smirk"),
    ("сидя, сверху, селфи", "half", "front", "front",
     "她自己举着手机从上方自拍，镜头比她的头高约三十厘米、向下拍，取景从头顶到大腿", "她坐着，身体微微前倾，另一只手撑在身旁", "挑逗的眼神，嘴角一边略高",
     "selfie she takes herself from above, phone about 30 cm above her head angled down, framed from the top of the head to the thighs",
     "sitting, leaning slightly forward, the other hand resting beside her", "teasing look, one corner of the mouth higher"),
    ("в рост, снизу, в движении", "full", "front", "front",
     "全身低角度，镜头在她前方约两米、膝盖高度向上拍，取景从头到脚", "她正朝镜头走来，一只脚在前，双臂自然摆动", "自信的微笑，看着镜头",
     "full-body low angle, camera about 2 m in front of her at knee height angled up, framed head to toe",
     "walking towards the camera mid-step, arms swinging naturally", "confident smile, looking into the lens"),
    ("по пояс, сверху, лёжа", "half", "front", "front",
     "中景俯拍，镜头在她正上方约一米、向下拍，取景从头顶到腰部", "她仰面躺着，头发散开，一只手放在头发旁边", "慵懒、温柔的微笑",
     "medium shot from directly above, camera about 1 m above her pointing down, framed from the top of the head to the waist",
     "lying on her back, hair spread out, one hand resting next to her hair", "lazy, soft smile"),
    ("по пояс, 3/4, смех", "half", "34", "34",
     "中景3/4侧面，镜头在她右前方约一米半、肩膀高度，取景从头顶到腰部", "她一只手扶着脖子，肩膀微微耸起", "开心地大笑，眼睛弯起来",
     "medium shot at a 3/4 angle, camera about 1.5 m to her front right at shoulder height, framed from the top of the head to the waist",
     "one hand on the side of her neck, shoulders slightly raised", "laughing happily, eyes crinkled"),
    ("крупно, анфас, серьёзный взгляд", "face", "front", "front",
     "近景正面，镜头在她正前方约四十厘米、与眼睛同高，取景从头顶到肩膀", "她的下巴微微抬起，直视镜头", "认真、自信的眼神，没有笑",
     "close shot from the front, camera about 40 cm in front of her at eye level, framed from the top of the head to the shoulders",
     "chin slightly raised, looking straight into the lens", "serious, confident look, no smile"),
]


def tmpl_all(n):
    return [{"label": f"карусель {k + 1}: {t[0]}", "framing": t[1], "face_angle": t[2], "body_view": t[3],
             "zh": {"scene": t[4], "action": t[5], "expression": t[6]}, "en": {"scene": t[7], "action": t[8], "expression": t[9]}}
            for k, t in enumerate(CAROUSEL_TEMPLATE[:n])]


def plan_carousel(cid, src, n, wishes, cfg):
    """План карусели: один запрос Grok по фото основы → N разных кадров (как планируется вручную). Без ответа — шаблон."""
    tmpl = tmpl_all(n)
    common = {"zh": {}, "en": {}}
    if cfg.get("xai_key") in ("", None, "mock"):
        return tmpl, common
    sys_p = ("Ты оператор и фотограф. По фото-основе спланируй карусель из N НОВЫХ кадров той же девушки в той же одежде и в том же месте, "
             "как серия фото с одной съёмки. Кадры обязаны отличаться и от основы, и друг от друга сразу по трём осям: "
             "ракурс камеры (анфас / 3/4 / профиль / со спины / сверху / снизу), крупность (крупный план / по пояс / в рост / сидя / лёжа), "
             "поза и эмоция. Ни один кадр не повторяет позу и ракурс основы. Для каждого кадра опиши физически: где стоит камера "
             "(высота, расстояние, угол), что попадает в кадр «от … до …», что делает тело и руки, куда смотрит, точная эмоция. "
             "Одежду, место и свет опиши один раз — ровно как на основе, ничего не выдумывай. Селфи в зеркале — все кадры тоже в зеркале с тем же телефоном. "
             "Верни только JSON: {\"outfit_zh\",\"outfit_en\",\"place_zh\",\"place_en\",\"light_zh\",\"light_en\","
             "\"frames\":[{\"label_ru\" (коротко: крупность, ракурс, поза),\"framing\" (face|half|full),\"face_angle\" (front|34|profile),"
             "\"body_view\" (front|34|side|back|back34),\"scene_zh\",\"scene_en\",\"action_zh\",\"action_en\",\"expression_zh\",\"expression_en\"}]}")
    try:
        res = xai_chat(cfg, {"model": cfg["chat_model"], "temperature": 0.7, "messages": [
            {"role": "system", "content": sys_p},
            {"role": "user", "content": [{"type": "text", "text": f"N = {n}." + (f" Пожелания: {wishes}" if wishes else "") + " Основа:"},
                                         {"type": "image_url", "image_url": {"url": data_uri(image_path(cid, src), 1024, 88), "detail": "high"}}]}]},
            timeout=180, cid=cid, kind="grok_carousel")
        txt = res["choices"][0]["message"].get("content") or ""
        j = json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
        frames = []
        for f in (j.get("frames") or [])[:n]:
            if not isinstance(f, dict) or not (f.get("scene_zh") or f.get("scene_en")):
                continue
            frames.append({"label": f"карусель {len(frames) + 1}: {f.get('label_ru') or ''}".strip(),
                           "framing": f.get("framing"), "face_angle": f.get("face_angle"), "body_view": f.get("body_view"),
                           "zh": {k2: f.get(f"{k2}_zh") for k2 in ("scene", "action", "expression") if f.get(f"{k2}_zh")},
                           "en": {k2: f.get(f"{k2}_en") for k2 in ("scene", "action", "expression") if f.get(f"{k2}_en")}})
        common = {L: {k: v for k, v in {"outfit": j.get(f"outfit_{L}"), "background": j.get(f"place_{L}"),
                                         "light": j.get(f"light_{L}")}.items() if v} for L in ("zh", "en")}
        used = {(f.get("framing"), f.get("body_view")) for f in frames}
        spare = [t for t in tmpl_all(len(CAROUSEL_TEMPLATE)) if (t["framing"], t["body_view"]) not in used]
        for t in spare[:max(0, n - len(frames))]:   # добиваем шаблоном — только ракурсами, которых ещё нет
            frames.append({**t, "label": f"карусель {len(frames) + 1}: " + t["label"].split(": ", 1)[-1]})
        return frames, common
    except Exception:
        traceback.print_exc()
        return tmpl, common


def carousel_base(chat, a):
    """Основа карусели: указанная → фото из последнего сообщения пользователя → последний ★ кадр → последний сгенерированный."""
    if a.get("source_id") in chat["images"]:
        return a["source_id"]
    last = next((m for m in reversed(chat["messages"]) if m["role"] == "user"), {})
    imgs = [i for i in last.get("images") or [] if i in chat["images"]]
    if imgs:
        return imgs[0]
    refs = set(all_ref_ids(chat["persona"]))
    for want_fav in (True, False):
        c = [(r["t"], i) for i, r in chat["images"].items()
             if r.get("source") in ("gen", "crop", "post") and i not in refs and (r.get("fav") or not want_fav)]
        if c:
            return max(c)[1]
    return None


def expand_carousel(cid, call, cfg):
    """Один вызов carousel → N вызовов generate_image с готовым описанием каждого кадра."""
    a = parse_args(call); chat = load_chat(cid)
    n = max(2, min(8, int(a.get("n") or 4)))
    src = carousel_base(chat, a)
    if not src:
        raise RuntimeError("нет основы для карусели — пришлите кадр или отметьте его ★")
    eng = a.get("engine") if a.get("engine") in WS_MODELS else (chat["images"][src].get("engine") or "seedream")
    if eng not in WS_MODELS:
        eng = "seedream"
    set_status(cid, "running", f"Планирую карусель из {n} кадров…")
    frames, common = plan_carousel(cid, src, n, a.get("wishes"), cfg)
    out = []
    for f in frames:
        g = {"engine": eng, "mode": "carousel", "source_id": src, "label": f["label"], "framing": f.get("framing"),
             "face_angle": f.get("face_angle") or "front", "body_view": f.get("body_view") or "front",
             "brief_zh": {**common["zh"], **f["zh"]}, "brief_en": {**common["en"], **f["en"]}}
        out.append({"id": "c" + secrets.token_hex(4), "type": "function",
                    "function": {"name": "generate_image", "arguments": json.dumps({k: v for k, v in g.items() if v}, ensure_ascii=False)}})
    return out


CAROUSEL_RE = re.compile(r"^\s*карусел\w*\s*(\d+)?\s*$", re.I)


def prepare_gen(cid, a, cfg, rebuild_inputs=True):
    """Довести вызов generate_image до готового: входы по рецепту, силуэт, промпт, язык. Меняет a."""
    fix_ids(cid, a)
    eng = a.get("engine") if a.get("engine") in WS_MODELS else "gpt"; a["engine"] = eng
    mode = a.get("mode") if a.get("mode") in recipes.MODES else ("free" if a.get("prompt") else "new")
    a["mode"] = mode
    chat = load_chat(cid)
    if mode != "free":
        if mode in ("replace", "carousel", "edit"):
            a["source_id"] = guess_source(chat, a)
            if not a["source_id"]:
                raise RuntimeError("не нашёл исходное фото (source_id)")
        lang = "zh" if eng == "seedream" else "en"
        other = "en" if lang == "zh" else "zh"
        if no_brief(a) and a.get("label"):
            # Grok часто кладёт позу только в подпись («карусель 2: 3/4, рука в волосах») — строим описание из неё
            desc = re.sub(r"^[^:]*:\s*", "", str(a["label"])).strip() or str(a["label"])
            a[f"brief_{lang}"] = translate_brief({"scene": desc}, lang, cfg)
        if no_brief(a):
            # без описания сцены модель просто повторит основу — не запускаем и не платим
            raise RuntimeError("не запущено: нет brief_en/brief_zh. Для каждого кадра опиши scene (ракурс камеры и крупность), "
                               "action (поза, руки, взгляд) и expression — разные у каждого кадра — и вызови заново")
        if mode == "replace" and not ((a.get("brief_en") or {}).get("outfit") or (a.get("brief_zh") or {}).get("outfit")):
            set_status(cid, "running", "Описываю исходник…")
            try:
                auto = auto_brief(cid, a["source_id"], cfg)
                for L in ("en", "zh"):
                    cur = a.get(f"brief_{L}") or {}
                    a[f"brief_{L}"] = {**(auto.get(L) or {}), **{k: v for k, v in cur.items() if v}}
            except Exception:
                traceback.print_exc()
        if not a.get(f"brief_{lang}") and a.get(f"brief_{other}"):
            a[f"brief_{lang}"] = translate_brief(a[f"brief_{other}"], lang, cfg)
        if mode == "replace" and eng == "seedream" and rebuild_inputs and not recipes.find_lineart(chat, a["source_id"]):
            set_status(cid, "running", "Делаю силуэт исходника…")
            make_lineart(cid, a["source_id"]); chat = load_chat(cid)
        if rebuild_inputs:
            a["image_ids"] = [i for i in recipes.pick_inputs(chat, a, eng) if i in chat["images"]]
            a["auto_inputs"] = True
        if mode == "replace" and eng == "gpt" and a.get("aspect_ratio") in (None, "", "auto"):
            r = chat["images"][a["source_id"]]
            if r.get("w") and r.get("h"):
                a["aspect_ratio"] = recipes.aspect_for(r["w"], r["h"])
        if not a.get("prompt_manual"):
            a["prompt"] = recipes.render(chat, a, eng)
    else:
        want_zh = eng == "seedream"
        if a.get("prompt") and recipes.is_zh(a["prompt"]) != want_zh:
            a["prompt"] = grok_translate(a["prompt"], "zh" if want_zh else "en", cfg)
    old = dict(zip(a.get("image_ids") or [], a.get("image_roles") or []))
    a["image_roles"] = [(old.get(i) if mode == "free" and old.get(i) else recipes.role_label(chat, i, a, k))
                        for k, i in enumerate(a.get("image_ids") or [])]
    return a


def expand_calls(cid, calls, cfg):
    out = []
    for c in calls:
        if c["function"]["name"] == "carousel":
            try:
                out += expand_carousel(cid, c, cfg)
                continue
            except Exception as e:
                traceback.print_exc()
                a = parse_args(c); a["prepare_error"] = str(e)[:300]
                c["function"]["arguments"] = json.dumps(a, ensure_ascii=False)
        out.append(c)
    return out


def prepare_calls(cid, calls, cfg):
    for c in calls:
        if c["function"]["name"] == "generate_image":
            a = parse_args(c)
            try:
                prepare_gen(cid, a, cfg)
            except Exception as e:   # не валим ход — Grok увидит ошибку в результате инструмента
                traceback.print_exc(); a["prepare_error"] = str(e)[:300]
            c["function"]["arguments"] = json.dumps(a, ensure_ascii=False)


def fix_ids(cid, a):
    """Grok иногда путает id (читает водяной знак как id). Неизвестный id → фото/видео из последнего сообщения пользователя."""
    chat = load_chat(cid)
    last = next((m for m in reversed(chat["messages"]) if m["role"] == "user"), {})
    imgs = [i for i in last.get("images") or [] if i in chat["images"]]
    vids = [v for v in last.get("videos") or [] if v in chat.get("videos", {})]
    for k in ("image_id", "source_id"):
        if a.get(k) and a[k] not in chat["images"] and len(imgs) == 1:
            a[k] = imgs[0]
    if a.get("video_id") and a["video_id"] not in chat.get("videos", {}) and len(vids) == 1:
        a["video_id"] = vids[0]
    if isinstance(a.get("image_ids"), list):
        bad = [i for i in a["image_ids"] if i not in chat["images"]]
        if len(bad) == 1 and len(imgs) == 1 and imgs[0] not in a["image_ids"]:
            a["image_ids"] = [imgs[0] if i in bad else i for i in a["image_ids"]]
    return a


def run_tool(cid, call, cfg):
    """Возвращает (text_result, [new image ids], cost)."""
    name = call["function"]["name"]; a = fix_ids(cid, parse_args(call))
    if name == "generate_image":
        if a.get("prepare_error"):
            raise RuntimeError(a["prepare_error"])
        eng = a.get("engine", "gpt")
        ids = a.get("image_ids") or []
        chat = load_chat(cid)
        for i in ids:
            image_path(cid, i, chat)
        aspect = a.get("aspect_ratio", "auto"); label = a.get("label", "")
        if eng not in WS_MODELS:
            raise RuntimeError(f"неизвестный движок {eng}")
        blobs = gen_wavespeed(cid, eng, a["prompt"], ids, aspect, cfg)
        new = [add_image(cid, b, "gen", label, {"engine": eng, "prompt": a["prompt"], "inputs": ids, "mode": a.get("mode")}) for b in blobs]
        cost = gen_price(eng, len(ids), cfg) * len(new)
        extra = ""
        src = a.get("source_id")
        if eng == "seedream" and a.get("mode") == "replace" and src in chat["images"]:
            # проверенный шаг: цвет Seedream под настоящее фото (иначе холодно, темно и «пластик»)
            post = []
            for i in new:
                img = apply_op(cid, Image.open(image_path(cid, i)).convert("RGB"), {"op": "color_match", "ref_id": src, "strength": 0.8})
                buf = io.BytesIO(); img.save(buf, "JPEG", quality=95)
                post.append(add_image(cid, buf.getvalue(), "post", label or "цвет под исходник",
                                      {"inputs": [i], "engine": eng, "prompt": a["prompt"], "ops": ["color_match"]}))
            extra = f" Цвет подогнан под исходник автоматически: {', '.join(post)} (это основной результат)."
            new += post
        return f"Готово ({eng}): {', '.join(new)}.{extra} Посмотри результат, проверь лицо и вызови review.", new, cost
    if name == "lineart":
        iid = make_lineart(cid, a["image_id"])
        return f"Силуэт готов: {iid}", [iid], 0.0
    if name == "crop":
        src = image_path(cid, a["image_id"]); img = Image.open(src)
        w, h = img.size
        rw, rh = [float(x) for x in a["aspect_ratio"].split(":")]
        tw, th = (w, round(w * rh / rw)) if w * rh / rw <= h else (round(h * rw / rh), h)
        ox = float(a.get("offset_x", 0.5)); oy = float(a.get("offset_y", 0.5))
        x0 = round((w - tw) * min(max(ox, 0), 1)); y0 = round((h - th) * min(max(oy, 0), 1))
        buf = io.BytesIO(); img.crop((x0, y0, x0 + tw, y0 + th)).convert("RGB").save(buf, "JPEG", quality=95)
        rec = load_chat(cid)["images"][a["image_id"]]
        iid = add_image(cid, buf.getvalue(), "crop", rec.get("label", ""),
                        {"inputs": [a["image_id"]], "engine": rec.get("engine"), "prompt": rec.get("prompt")})
        return f"Обрезано до {a['aspect_ratio']} ({tw}×{th}): {iid}", [iid], 0.0
    if name == "set_persona":
        def f(c):
            p = c["persona"]
            for k in ("faces", "body"):
                if k in a:
                    p[k] = [i for i in a[k] if i in c["images"]]
            for k in ("card", "card_en", "card_zh"):
                if a.get(k):
                    p[k] = a[k]
            if a.get("name"):
                c["name"] = a["name"]
            return f"Модель сохранена: лиц {len(p['faces'])}, тело {len(p['body'])}, карточка {'есть' if p['card'] else 'нет'}"
        return update_chat(cid, f), [], 0.0
    if name == "add_reference":
        chat = load_chat(cid)
        ids = [i for i in a.get("image_ids", []) if i in chat["images"]]
        if not ids:
            raise RuntimeError("нет таких картинок")
        labels = a.get("labels") or []

        def f(c):
            p = c["persona"]; key = cat_key(p, a.get("category"))
            cur = [i for i in group_ids(p, key) if i not in ids]
            set_group_ids(p, key, ids + cur if a.get("position") == "start" else cur + ids)
            if a.get("note"):
                if key in BUILTIN:
                    p.setdefault("notes", {})[key] = a["note"]
                else:
                    p["extra"][key]["note"] = a["note"]
            for i, lab in zip(ids, labels):
                if lab:
                    c["images"][i]["label"] = lab[:60]
            return key, len(group_ids(p, key))
        key, n = update_chat(cid, f)
        return f"Сохранено в категорию «{BUILTIN.get(key, key)}» ({key}): {', '.join(ids)}. В категории теперь {n}. Обнови карточку через set_persona.", [], 0.0
    if name == "remove_reference":
        def f(c):
            p = c["persona"]; key = cat_key(p, a.get("category"))
            if a.get("delete_category") and key not in BUILTIN:
                p.get("extra", {}).pop(key, None)
                return f"Категория «{key}» удалена"
            rm = set(a.get("image_ids") or [])
            set_group_ids(p, key, [i for i in group_ids(p, key) if i not in rm])
            return f"Убрано из «{BUILTIN.get(key, key)}»: {len(rm)}"
        return update_chat(cid, f), [], 0.0
    if name == "postprocess":
        img = Image.open(image_path(cid, a["image_id"])).convert("RGB")
        done = []
        for op in a.get("ops") or []:
            img = apply_op(cid, img, op); done.append(op.get("op"))
        buf = io.BytesIO(); img.save(buf, "JPEG", quality=95)
        rec = load_chat(cid)["images"][a["image_id"]]
        iid = add_image(cid, buf.getvalue(), "post", a.get("label") or rec.get("label", ""),
                        {"inputs": [a["image_id"]], "engine": rec.get("engine"), "prompt": rec.get("prompt"), "ops": done})
        return f"Обработано ({', '.join(done)}): {iid}", [iid], 0.0
    if name == "review":
        return "Проверка показана пользователю.", [], 0.0
    if name == "video_frames":
        vid = a["video_id"]; src = video_path(cid, vid); dur = load_chat(cid)["videos"][vid]["dur"]
        new = []
        for t in (a.get("times") or [])[:8]:
            t = min(max(float(t), 0), max(dur - 0.05, 0))
            lab = (a.get("label") + " · " if a.get("label") else "") + f"{vid} · {t:.2f}s"
            new.append(add_image(cid, grab_frame(src, t, 2048), "frame", lab, {"video": vid, "vt": round(t, 2)}))
        return f"Кадры: " + ", ".join(new), new, 0.0
    if name == "trim_video":
        vid = a["video_id"]; src = video_path(cid, vid)
        s, e = float(a.get("start", 0)), float(a["end"])
        if e - s < 1:
            raise RuntimeError("слишком коротко")
        tmp = src.with_name(f"trim_{secrets.token_hex(3)}.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{s:.3f}", "-to", f"{e:.3f}", "-i", str(src),
                        "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(tmp)],
                       check=True, creationflags=NOWIN)
        nv = add_video(cid, tmp, "trim", f"{s:.1f}–{e:.1f} с из {vid}", {"inputs_video": vid, "call": call["id"]})
        r = load_chat(cid)["videos"][nv]
        return f"Обрезано: {nv} ({r['dur']} с). Кадры: {', '.join(r['frames'])}", r["frames"], 0.0
    if name == "lineart_video":
        import lineart as la
        vid = a["video_id"]; src = video_path(cid, vid)
        tmp = src.with_name(f"la_{secrets.token_hex(3)}.mp4")
        la.do_video(str(src), str(tmp), progress=lambda n, tot: job_update(cid, call["id"], progress=f"{n}/{tot} кадров"))
        nv = add_video(cid, tmp, "lineart", f"силуэт {vid}", {"inputs_video": vid, "call": call["id"]}, n_frames=4)
        r = load_chat(cid)["videos"][nv]
        return f"Силуэт видео готов: {nv} ({r['dur']} с). Кадры для проверки: {', '.join(r['frames'])}", r["frames"], 0.0
    if name == "edit_video":
        chat = load_chat(cid); vid = a["video_id"]
        rec = chat["videos"].get(vid)
        if not rec:
            raise KeyError(f"нет видео {vid}")
        ids = a.get("image_ids") or []
        for i in ids:
            image_path(cid, i, chat)
        res = a.get("resolution") if a.get("resolution") in RESOLUTIONS else "480p"
        audio = bool(a.get("generate_audio", False))
        blob = gen_video(cid, vid, a["prompt"], ids, res, audio, cfg,
                         on_submit=lambda jid: job_update(cid, call["id"], ws_id=jid))
        nv = add_video(cid, blob, "gen", a.get("label", ""),
                       {"engine": "seedance", "prompt": a["prompt"], "inputs": ids, "inputs_video": vid,
                        "resolution": res, "gen_audio": audio, "call": call["id"]}, n_frames=8)
        r = load_chat(cid)["videos"][nv]
        cost = video_cost(rec["dur"], res, cfg)
        return (f"Видео готово (Seedance {res}): {nv}, {r['dur']} с. Кадры результата: {', '.join(r['frames'])}. "
                "Проверь лицо в каждом плане против эталонов, остатки линий, одежду, руки, фон — и вызови review с video_ids."), r["frames"], cost
    raise RuntimeError(f"неизвестный инструмент {name}")


# ---------------- agent ----------------
def state_block(chat, cfg):
    p = chat["persona"]
    engines = ["gpt", "seedream"] if cfg["wavespeed_key"] else []
    pr = cfg["prices"]
    lines = ["# Состояние",
             f"Модель (чат): {chat['name']}",
             f"Движки генерации (WaveSpeed): {', '.join(engines + (['seedance (видео)'] if engines else [])) or 'НЕТ — ключ WaveSpeed не задан, генерировать нельзя: попроси пользователя вписать его в настройках'}. Цены за кадр ≈ gpt ${pr['gpt']}, seedream ${pr['seedream']}. "
             f"Seedance за секунду (вход+выход): 480p ${pr.get('seedance_480p')}, 720p ${pr.get('seedance_720p')}, 1080p ${pr.get('seedance_1080p')}.",
             f"Подтверждение перед генерацией: {'выключено (запускай сразу)' if cfg['autorun'] else 'включено — приложение само спросит пользователя, просто вызывай инструмент'}.",
             "Эталоны модели по категориям:\n" + "\n".join(
                 f"- {name} [{key}]: " + (", ".join(i + (f" ({chat['images'][i]['label']})" if chat['images'].get(i, {}).get('label') else '') for i in ids) or "нет")
                 + (f" — {note}" if note else "")
                 for key, name, ids, note in ref_groups(p)),
             "Карточка RU:\n" + (p["card"] or "(пусто — модель ещё не создана, режим «Создание новой модели»)")]
    if p.get("card_en"):
        lines.append("Identity EN:\n" + p["card_en"])
    if p.get("card_zh"):
        lines.append("人物身份 ZH:\n" + p["card_zh"])
    favs = [i for i, r in chat["images"].items() if r.get("fav") and r.get("source") in ("gen", "crop", "post")]
    if favs:
        lines.append("Удачные кадры (★ — годятся как референс фактуры): " + ", ".join(
            f"{i} [{chat['images'][i].get('engine') or ''} {chat['images'][i].get('label') or ''}]" for i in favs[-8:]))
    vids = sorted(chat.get("videos", {}).items(), key=lambda kv: kv[1]["t"])[-10:]
    if vids:
        lines.append("Видео в чате (новые в конце):\n" + "\n".join(f"- {v}: {video_line(r)}" for v, r in vids))
    recent = [i for i, r in sorted(chat["images"].items(), key=lambda kv: kv[1]["t"])][-30:]
    if recent:
        lines.append("Картинки в чате (новые в конце): " + "; ".join(
            f"{i} [{chat['images'][i]['source']}{' ' + chat['images'][i]['label'] if chat['images'][i].get('label') else ''}{' ★' if chat['images'][i].get('fav') else ''}]"
            for i in recent))
    return "\n".join(lines)


def video_line(r):
    src = {"user": "исходник", "trim": "обрезка", "lineart": "силуэт", "gen": "результат Seedance"}.get(r["source"], r["source"])
    s = f"{src}, {r['dur']} с, {r['w']}×{r['h']}, {r.get('fps') or '?'} fps, звук: {'есть (не прослушан)' if r.get('audio') else 'нет'}"
    if r.get("cuts"):
        s += f", склейки на {', '.join(str(c) for c in r['cuts'])} с"
    if r.get("inputs_video"):
        s += f", из {r['inputs_video']}"
    if r.get("resolution"):
        s += f", {r['resolution']}"
    if r.get("label"):
        s += f" «{r['label']}»"
    if r.get("face_times"):
        s += "; лицо анфас с открытыми глазами лучше всего видно на " + ", ".join(f"{t} с" for t in r["face_times"]) + \
             " — ключевые кадры для замены бери отсюда"
    if r.get("frames"):
        s += "; кадры: " + ", ".join(r["frames"])
    return s


HISTORY_TURNS = 6
SLIM_DROP = ("prompt", "brief_zh", "brief_en", "image_roles", "prepare_error")


def slim_call(tc):
    try:
        a = json.loads(tc["function"].get("arguments") or "{}")
    except json.JSONDecodeError:
        return tc
    if not isinstance(a, dict):
        return tc
    a = {k: v for k, v in a.items() if k not in SLIM_DROP}
    return {**tc, "function": {**tc["function"], "arguments": json.dumps(a, ensure_ascii=False)}}


def build_messages(chat, cfg, turn_start):
    cid = chat["id"]
    msgs = [{"role": "system", "content": system_prompt() + "\n\n" + state_block(chat, cfg)}]
    p = chat["persona"]
    refs = [(i, "ЛИЦО") for i in p["faces"][:3]] + [(i, "ТЕЛО") for i in p["body"][:2]]
    for key, name, ids, note in ref_groups(p)[2:6]:
        refs += [(i, name.upper()) for i in ids[:1]]
    if refs:
        parts = [{"type": "text", "text": "Эталоны модели (для сравнения и выбора входов): " + ", ".join(f"{i} {k}" for i, k in refs)}]
        for i, kind in refs:
            try:
                parts.append({"type": "text", "text": f"{i} ({kind}):"})
                parts.append({"type": "image_url", "image_url": {"url": data_uri(image_path(cid, i, chat), 640, 85), "detail": "high"}})
            except KeyError:
                pass
        msgs.append({"role": "user", "content": parts})
        msgs.append({"role": "assistant", "content": "Эталоны вижу."})
    # согласовать tool_calls и ответы (после удаления/отката сообщений)
    answered = {m["tool_call_id"] for m in chat["messages"] if m["role"] == "tool"}
    called = set()
    # история: только последние HISTORY_TURNS ходов — длинный чат иначе даёт ~80k токенов на ход (медленно, дорого, таймауты)
    starts = [i for i, m in enumerate(chat["messages"]) if m["role"] == "user"]
    cut = starts[-HISTORY_TURNS] if len(starts) > HISTORY_TURNS else 0
    if cut:
        msgs.append({"role": "user", "content": f"[Ранние {cut} сообщений чата скрыты для краткости. Эталоны, карточка модели и все картинки чата доступны по id.]"})
        msgs.append({"role": "assistant", "content": "Понял."})
    for idx, m in enumerate(chat["messages"]):
        if idx < cut:
            continue
        show_imgs = idx >= turn_start   # картинки показываем только в текущем ходе
        if m["role"] in ("user", "review"):
            ids = [i for i in (m.get("images") or []) if i in chat["images"]]
            text = m.get("text") or ""
            if m["role"] == "user" and not text.strip() and (ids or m.get("videos")):
                if m.get("videos"):
                    text = f"[Видео без текста → замена девушки в видео на модель, режим 6. Видео: {', '.join(m['videos'])}]"
                else:
                    text = (f"[Фото без текста → замена девушки на модель: сразу generate_image mode=replace, source_id={ids[0]}. "
                            "Без вопросов и без отдельного lineart.]")
            if m["role"] == "user" and m.get("pair"):
                pr = m["pair"]
                text = (f"[Два видео: оригинал {pr['orig']} и ГОТОВЫЙ СИЛУЭТ {pr['sil']} (пользователь сделал сам). lineart_video НЕ делай. "
                        + (f"Ключевой кадр уже вынут приложением: {pr['key']} ({pr.get('key_t', 0):.2f} с — лицо анфас, глаза открыты). "
                           f"Режим 6 с готовым силуэтом: 1) generate_image engine=gpt mode=replace source_id={pr['key']} (одежда и место — с оригинала); "
                           if pr.get("key") else
                           f"Режим 6 с готовым силуэтом: 1) выбери ОДИН момент, где лицо анфас и глаза ОТКРЫТЫ (не опущенная голова, не рука на лице) "
                           f"→ video_frames оригинала; generate_image engine=gpt mode=replace по этому кадру (одежда и место — с оригинала); ")
                        + f"проверь: лицо на кадре должно совпадать с портретом модели, иначе переделай до видео; "
                        f"3) после проверки кадра — edit_video: video_id={pr['sil']}, image_ids=[кадр с заменой, портрет анфас из «Лицо»], "
                        f"промпт по режиму 6 (одежду словами — с оригинала)."
                        + (f" Длительность различается на {pr['dur_diff']} с — предупреди пользователя." if pr.get("dur_diff", 0) > 0.5 else "")
                        + "]" + ("\n" + text if text and not text.startswith("[Видео без текста") else ""))
            elif m["role"] == "user" and len(m.get("videos") or []) == 2 and "pair" in m:
                text = ("[Два видео, но готовый силуэт среди них не распознан — уточни у пользователя, что это за ролики.]"
                        + ("\n" + text if text and not text.startswith("[Видео без текста") else ""))
            if m.get("engine") and m["engine"] != "auto":
                text = f"[Движок для этого запроса: {m['engine']}]\n" + text
            if ids:
                text += ("\n" if text else "") + "[картинки: " + ", ".join(ids) + "]"
            pr = m.get("pair") or {}
            if pr.get("key") in chat["images"] and pr["key"] not in ids:
                ids.append(pr["key"])
            for v in m.get("videos") or []:
                r = chat.get("videos", {}).get(v)
                if r:
                    text += ("\n" if text else "") + f"[видео {v}: {video_line(r)}]"
                    fr = [i for i in r.get("frames", []) if i in chat["images"] and i not in ids]
                    if pr:   # пара: хватит 3 кадров оригинала и 2 силуэта — слишком тяжёлый запрос xAI роняет 500-кой
                        k = 2 if v == pr.get("sil") else 3
                        fr = fr[::max(1, len(fr) // k)][:k]
                    ids += fr
            if show_imgs and ids:
                parts = [{"type": "text", "text": text}]
                for i in ids[:20]:
                    rec = chat["images"][i]
                    parts.append({"type": "text", "text": f"Кадр {i} ({rec['label']}):" if rec.get("source") == "frame" else f"Картинка {i}:"})
                    parts.append({"type": "image_url", "image_url": {"url": data_uri(image_path(cid, i, chat), 1024, 88), "detail": "high"}})
                msgs.append({"role": "user", "content": parts})
            else:
                msgs.append({"role": "user", "content": text or "(пусто)"})
        elif m["role"] == "assistant":
            d = {"role": "assistant", "content": m.get("text") or ""}
            if m.get("tool_calls"):
                # прошлые ходы: без длинных промптов и описаний — Grok нужны только подпись, режим и id
                d["tool_calls"] = m["tool_calls"] if idx >= turn_start else [slim_call(tc) for tc in m["tool_calls"]]
                called |= {tc["id"] for tc in m["tool_calls"]}
            msgs.append(d)
            for tc in m.get("tool_calls") or []:
                if tc["id"] not in answered and idx < len(chat["messages"]) - 1:
                    msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": "Не выполнено."})
        elif m["role"] == "tool" and m["tool_call_id"] in called:
            msgs.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["text"]})
    return msgs


def set_status(cid, status, text=""):
    def f(c):
        c["status"] = status; c["status_text"] = text
    update_chat(cid, f)


def append_msg(cid, msg):
    msg.setdefault("t", time.time()); msg.setdefault("id", new_mid())
    update_chat(cid, lambda c: c["messages"].append(msg))


def edit_call(cid, call, e, cfg):
    """Правка задания из карточки: промпт, движок, входы. Промпт по рецепту пересобирается,
    ручной — перенумеровывается (图N / image N / @imageN) и переводится при смене движка."""
    a = parse_args(call); nm = call["function"]["name"]; chat = load_chat(cid)
    old_ids = list(a.get("image_ids") or [])
    if "prompt" in e and e["prompt"] != a.get("prompt"):
        a["prompt"] = e["prompt"]; a["prompt_manual"] = True
    if e.get("rebuild"):
        a["prompt_manual"] = False
    eng_changed = nm == "generate_image" and e.get("engine") in WS_MODELS and e["engine"] != a.get("engine")
    if eng_changed:
        a["engine"] = e["engine"]
    if nm == "edit_video":
        if e.get("resolution") in RESOLUTIONS:
            a["resolution"] = e["resolution"]
        if "audio" in e:
            a["generate_audio"] = bool(e["audio"])
        if e.get("video") in chat["videos"]:
            a["video_id"] = e["video"]
    inputs_changed = isinstance(e.get("inputs"), list)
    if inputs_changed:
        a["image_ids"] = [i for i in e["inputs"] if i in chat["images"]]
        a["auto_inputs"] = False
    if nm == "generate_image":
        recipe = a.get("mode") not in (None, "free")
        if recipe and not a.get("prompt_manual"):
            # пересобрать по рецепту; при смене движка и нетронутых входах — заново подобрать входы
            prepare_gen(cid, a, cfg, rebuild_inputs=eng_changed)   # у GPT и Seedream разные рецепты входов
        else:
            if inputs_changed and old_ids != a["image_ids"]:
                a["prompt"] = renumber(chat, a, old_ids, "seedream" if a.get("engine") == "seedream" else "gpt")
            if eng_changed:
                want_zh = a["engine"] == "seedream"
                if recipes.is_zh(a.get("prompt", "")) != want_zh:
                    a["prompt"] = grok_translate(a["prompt"], "zh" if want_zh else "en", cfg)
            a["image_roles"] = [recipes.role_label(chat, i, a, k) for k, i in enumerate(a.get("image_ids") or [])]
    elif nm == "edit_video" and inputs_changed:
        a["prompt"] = renumber(chat, a, old_ids, "video")
        roles = dict(zip(old_ids, a.get("image_roles") or []))
        a["image_roles"] = [roles.get(i) or recipes.role_label(chat, i, a, k) for k, i in enumerate(a["image_ids"])]
    call["function"]["arguments"] = json.dumps(a, ensure_ascii=False)
    call["edited"] = True


def renumber(chat, a, old_ids, kind):
    new_ids = a.get("image_ids") or []
    text, added = recipes.remap(a.get("prompt", ""), old_ids, new_ids)
    for i in added:
        n = new_ids.index(i) + 1; role = recipes.role_label(chat, i, a, n - 1) or "референс"
        text += {"seedream": f"\n图{n}：{role}参考。", "video": f"\n@image{n}：{role}参考。"}.get(kind, f"\nImage {n}: {role} reference.")
    return text


def pending_summary(calls, cfg, chat=None):
    jobs = []
    for idx, c in enumerate(calls):
        nm = c["function"]["name"]; a = parse_args(c)
        if nm == "generate_image":
            jobs.append({"i": idx, "kind": "image", "engine": a.get("engine"), "label": a.get("label", ""),
                         "inputs": a.get("image_ids", []), "roles": a.get("image_roles", []),
                         "aspect": a.get("aspect_ratio", "auto"), "prompt": a.get("prompt", ""),
                         "mode": a.get("mode", "free"), "manual": bool(a.get("prompt_manual")),
                         "cost": tool_cost(c, cfg)})
        elif nm == "edit_video":
            rec = (chat or {}).get("videos", {}).get(a.get("video_id"), {})
            jobs.append({"i": idx, "kind": "video", "engine": "seedance", "label": a.get("label", ""),
                         "video": a.get("video_id"), "dur": rec.get("dur"),
                         "inputs": a.get("image_ids", []), "roles": a.get("image_roles", []),
                         "resolution": a.get("resolution") if a.get("resolution") in RESOLUTIONS else "480p",
                         "costs": {r: video_cost(rec.get("dur", 10), r, cfg) for r in RESOLUTIONS},
                         "audio": bool(a.get("generate_audio", False)), "prompt": a.get("prompt", ""),
                         "cost": tool_cost(c, cfg, chat)})
    return {"cost": round(sum(j["cost"] for j in jobs), 2), "jobs": jobs}


def limit_problem(cost, cfg):
    if cfg.get("_ctx"):
        return hosted.check(cfg["_ctx"], (cost if charges_ws(cfg) else 0.0) + GROK_RESERVE)
    lim = cfg["limits"]
    if lim.get("per_message") and cost > float(lim["per_message"]) + 1e-9:
        return f"лимит на сообщение ${float(lim['per_message']):.2f}, а запуск стоит ≈ ${cost:.2f}"
    if lim.get("per_day") and spend_today() + cost > float(lim["per_day"]) + 1e-9:
        return f"дневной лимит ${float(lim['per_day']):.2f}: сегодня уже ${spend_today():.2f}, запуск ≈ ${cost:.2f}"
    return None


def job_update(cid, jid, **kw):
    def f(c):
        for j in c["jobs"]:
            if j["id"] == jid:
                j.update(kw)
    update_chat(cid, f)


def agent_loop(cid, cfg=None):
    cfg = cfg or load_config()
    flag = RUNNING.setdefault(cid, {"stop": False}); flag["stop"] = False
    try:
        chat = load_chat(cid)
        # начало хода = последнее сообщение пользователя
        turn_start = max([i for i, m in enumerate(chat["messages"]) if m["role"] == "user"] or [0])
        err_streak = 0
        for step in range(cfg["max_steps"]):
            if flag["stop"]:
                append_msg(cid, {"role": "assistant", "text": "Остановлено."}); break
            chat = load_chat(cid)
            last = chat["messages"][-1] if chat["messages"] else None
            # последний ответ Grok с tool_calls без результатов — исполняем (после подтверждения)
            if last and last["role"] == "assistant" and last.get("tool_calls"):
                calls = last["tool_calls"]
                cost = sum(tool_cost(c, cfg, chat) for c in calls)
                if cost > 0:
                    prob = limit_problem(cost, cfg)
                    if prob:
                        for c in calls:
                            append_msg(cid, {"role": "tool", "tool_call_id": c["id"], "name": c["function"]["name"],
                                             "text": f"Не запущено: {prob}. Скажи пользователю.", "images": []})
                        append_msg(cid, {"role": "error", "code": "no_credits" if cfg.get("_ctx") else "limit_exceeded",
                                         "text": f"Генерация не запущена: {prob}." + ("" if cfg.get("_ctx") else " Поменяй лимит в настройках.")})
                        break
                has_video = any(c["function"]["name"] == "edit_video" for c in calls)   # видео дорогое — спрашиваем всегда
                if cost > 0 and (not cfg["autorun"] or has_video) and not chat.get("approved"):
                    summ = pending_summary(calls, cfg, chat)
                    update_chat(cid, lambda c: c.update(pending=summ))
                    set_status(cid, "awaiting", f"Ждёт подтверждения ≈ {money(cfg, cost)}")
                    return
                now = time.time()
                jobs = []
                for c in calls:
                    a = parse_args(c); nm = c["function"]["name"]
                    if nm in QUIET:
                        continue
                    jobs.append({"id": c["id"], "name": nm,
                                 "engine": a.get("engine") if nm == "generate_image" else ("seedance" if nm == "edit_video" else None),
                                 "label": a.get("label") or {"lineart": "Силуэт", "crop": f"Обрезка {a.get('aspect_ratio', '')}", "postprocess": "Обработка",
                                                             "lineart_video": "Силуэт видео", "trim_video": "Обрезка видео", "video_frames": "Кадры из видео",
                                                             "edit_video": "Замена в видео"}.get(nm, nm),
                                 "state": "running", "started": now, "ended": None,
                                 "cost": tool_cost(c, cfg, chat)})
                update_chat(cid, lambda c: c.update(approved=False, pending=None, jobs=jobs))
                set_status(cid, "running", f"Выполняю {len(calls)} шаг(а)")
                new_imgs = []
                with ThreadPoolExecutor(max_workers=6) as ex:
                    futs = {ex.submit(safe_tool, cid, c, cfg): c for c in calls}
                    results = {futs[f]["id"]: f.result() for f in futs}
                total = 0.0
                vids_by_call = {}
                for v, r in load_chat(cid)["videos"].items():
                    if r.get("call"):
                        vids_by_call.setdefault(r["call"], []).append(v)
                for c in calls:
                    text, ids, cost_i = results[c["id"]]
                    if cost_i and cfg.get("_ctx"):
                        if charges_ws(cfg):
                            a_i = parse_args(c)
                            bill(cfg, None, f"agent_{c['function']['name']}", usd=cost_i,
                                 meta={"chat": cid, "call": c["id"], "engine": a_i.get("engine"), "mode": a_i.get("mode"), "outputs": len(ids)})
                        else:
                            cost_i = 0.0   # свой ключ WaveSpeed — платит владелец напрямую
                    total += cost_i; new_imgs += ids
                    append_msg(cid, {"role": "tool", "tool_call_id": c["id"], "name": c["function"]["name"],
                                     "text": text, "images": ids, "videos": vids_by_call.get(c["id"], []),
                                     "dt": round(time.time() - now, 1), "cost": cost_i})
                loud = [c for c in calls if c["function"]["name"] not in QUIET]
                if loud and all(str(results.get(c["id"], ("",))[0]).startswith("ОШИБКА") for c in loud):
                    err_streak += 1
                else:
                    err_streak = 0
                if err_streak >= 2:
                    update_chat(cid, lambda c: c.__setitem__("jobs", []))
                    append_msg(cid, {"role": "error", "code": "tool_loop",
                                     "text": "Остановлено: шаг дважды подряд закончился ошибкой. Уточните запрос или нажмите «Повторить»."})
                    break
                if total:
                    add_spend(total)
                    update_chat(cid, lambda c: c.__setitem__("spent", round(c.get("spent", 0) + total, 3)))
                update_chat(cid, lambda c: c.__setitem__("jobs", []))
                if new_imgs:
                    text = "Результаты инструментов для проверки (лицо vs эталоны, руки, одежда, фон). После проверки вызови review:"
                    bases = []
                    for c in calls:
                        a_c = parse_args(c)
                        if c["function"]["name"] == "generate_image" and a_c.get("mode") == "carousel" and a_c.get("source_id") in chat["images"]:
                            if a_c["source_id"] not in bases:
                                bases.append(a_c["source_id"])
                    if bases:
                        text = ("Карусель. ПЕРВАЯ картинка — основа (" + ", ".join(bases) + "), дальше — новые кадры. "
                                "Сравни каждый кадр с основой и кадры между собой: поза, руки, ракурс камеры, крупность, эмоция. "
                                "Если кадр почти повторяет основу или соседний кадр (поменялись только руки) — это брак: "
                                "в issues «повтор основы: <кадр>», и в этом же ходе переделай такие кадры с другим ракурсом и крупностью. "
                                "Не пиши «ракурс изменился», если он не изменился. Потом вызови review:")
                    append_msg(cid, {"role": "review", "text": text, "images": bases + [i for i in new_imgs if i not in bases], "hidden": True})
                continue
            if last and last["role"] == "user" and len(last.get("videos") or []) == 2 and "pair" not in last:
                set_status(cid, "running", "Смотрю, где оригинал, а где силуэт…")
                pair = detect_pair(cid, last["videos"])
                if pair:
                    set_status(cid, "running", "Ищу кадр, где лицо видно лучше всего…")
                    try:
                        ft = face_times(cid, pair["orig"])
                        if ft:
                            t = ft[0]
                            pair["key"] = add_image(cid, grab_frame(video_path(cid, pair["orig"]), t, 2048), "frame",
                                                    f"ключевой кадр · {pair['orig']} · {t:.2f}s", {"video": pair["orig"], "vt": t})
                            pair["key_t"] = t
                    except Exception:
                        traceback.print_exc()

                def mark(c, pair=pair):
                    c["messages"][-1]["pair"] = pair
                update_chat(cid, mark)
                chat = load_chat(cid); last = chat["messages"][-1]
            if last and last["role"] == "user" and last.get("videos") and not last.get("faces_done"):
                set_status(cid, "running", "Ищу кадры, где лицо видно лучше всего…")
                for v in last["videos"]:
                    if chat["videos"].get(v, {}).get("source") == "user":
                        try:
                            face_times(cid, v)
                        except Exception:
                            traceback.print_exc()
                update_chat(cid, lambda c: c["messages"][-1].__setitem__("faces_done", True))
                chat = load_chat(cid); last = chat["messages"][-1]
            mt = CAROUSEL_RE.match(last.get("text") or "") if last and last["role"] == "user" else None
            if mt:
                try:
                    calls = expand_carousel(cid, {"function": {"name": "carousel", "arguments": json.dumps({"n": int(mt.group(1) or 4)})}}, cfg)
                    set_status(cid, "running", "Собираю входы и промпт по рецепту…")
                    prepare_calls(cid, calls, cfg)
                    append_msg(cid, {"role": "assistant", "text": "План карусели:\n" + "\n".join("· " + parse_args(c).get("label", "") for c in calls),
                                     "tool_calls": calls})
                    continue
                except Exception:
                    traceback.print_exc()   # нет основы и т. п. — пусть разбирается Grok
            set_status(cid, "running", "Grok думает…")
            msgs = build_messages(chat, cfg, turn_start)
            if cfg["xai_key"] == "mock":   # самопроверка без оплаты
                res = mock_reply(chat, msgs)
                if cfg.get("_ctx"):   # самопроверка списаний: как будто Grok съел 30k/2k токенов
                    bill(cfg, cid, "agent_grok", usage={"prompt_tokens": 30000, "completion_tokens": 2000, "total_tokens": 32000},
                         model=cfg["chat_model"], meta={"mock": True})
            else:
                res = xai_chat(cfg, {"model": cfg["chat_model"], "messages": msgs, "tools": TOOLS,
                                     "tool_choice": "auto", "temperature": 0.6}, timeout=300, cid=cid)
            m = res["choices"][0]["message"]
            msg = {"role": "assistant", "text": m.get("content") or ""}
            if m.get("tool_calls"):
                msg["tool_calls"] = [{"id": tc["id"], "type": "function",
                                      "function": {"name": tc["function"]["name"],
                                                   "arguments": tc["function"].get("arguments") or "{}"}}
                                     for tc in m["tool_calls"]]
                msg["tool_calls"] = expand_calls(cid, msg["tool_calls"], cfg)
                if any(tc["function"]["name"] == "generate_image" for tc in msg["tool_calls"]):
                    set_status(cid, "running", "Собираю входы и промпт по рецепту…")
                    prepare_calls(cid, msg["tool_calls"], cfg)
            append_msg(cid, msg)
            if not msg.get("tool_calls"):
                break
        set_status(cid, "idle")
    except Exception as e:
        traceback.print_exc()
        append_msg(cid, {"role": "error", "text": str(e)[:2000]})
        update_chat(cid, lambda c: c.__setitem__("jobs", []))
        set_status(cid, "error")
    finally:
        RUNNING.pop(cid, None)


def mock_reply(chat, msgs):
    """Фейковый Grok для самопроверки: силуэт + обрезка + генерация, затем проверка и текст."""
    last = chat["messages"][-1]
    t = (last.get("text") or "").lower()
    mk = lambda n, a: {"id": "c" + secrets.token_hex(3), "type": "function", "function": {"name": n, "arguments": json.dumps(a, ensure_ascii=False)}}
    vids = chat.get("videos", {})
    if last["role"] == "user" and last.get("videos"):
        v = last["videos"][0]
        return {"choices": [{"message": {"content": "Разобрал ролик. Беру ключевой кадр и делаю силуэт видео.", "tool_calls": [
            mk("video_frames", {"video_id": v, "times": [0.5], "label": "ключевой"}),
            mk("lineart_video", {"video_id": v})]}}]}
    if last["role"] == "review":
        la_v = [k for k, r in vids.items() if r["source"] == "lineart"]
        gen_v = [k for k, r in vids.items() if r["source"] == "gen"]
        if la_v and not gen_v:
            refs = [i for i in last["images"] if chat["images"][i]["label"].startswith("ключевой")][:1] + chat["persona"]["faces"][:1]
            return {"choices": [{"message": {"content": "Силуэт ровный. Запускаю Seedance.", "tool_calls": [
                mk("edit_video", {"video_id": la_v[-1], "prompt": "输入视频中的人物被画成了白色的线稿剪影…", "image_ids": refs,
                                  "image_roles": ["ключевой кадр", "лицо"][:len(refs)], "resolution": "480p", "label": "тест видео"})]}}]}
        if gen_v:
            return {"choices": [{"message": {"content": "", "tool_calls": [mk("review", {"video_ids": [gen_v[-1]], "image_ids": last["images"][:3],
                "ok": ["Движение и липсинк как в исходнике"], "issues": ["Тест — лицо не проверялось"], "suggestions": ["Сделай 720p", "Ещё ключевой кадр в профиль"]})]}}]}
    if last["role"] == "user" and last.get("images") and "эталон" in t:
        return {"choices": [{"message": {"content": "Сохраняю как эталон ног и обновляю описание.", "tool_calls": [
            mk("add_reference", {"image_ids": last["images"], "category": "Ноги", "labels": ["сбоку"], "note": "длинные стройные ноги, полные бёдра"}),
            mk("set_persona", {"card": (chat["persona"]["card"] or "") + " Ноги: длинные стройные, полные бёдра."})]}}]}
    if last["role"] == "user" and last.get("images") and "post" in t:
        iid = last["images"][0]; ref = (chat["persona"]["faces"] or [iid])[0]
        return {"choices": [{"message": {"content": "Довожу цвет и кожу.", "tool_calls": [
            mk("postprocess", {"image_id": iid, "ops": [{"op": "color_match", "ref_id": ref, "strength": 0.7}, {"op": "matte", "strength": 0.6}, {"op": "gray_mask", "polygon": [[0.1, 0.1], [0.3, 0.1], [0.3, 0.3]]}]})]}}]}
    if last["role"] == "user" and last.get("images"):
        iid = last["images"][0]
        calls = [mk("generate_image", {"engine": "seedream", "mode": "replace", "source_id": iid, "face_angle": "34", "body_view": "front",
                                       "brief_en": {"scene": "full-body photo by a friend", "action": "standing, hand in hair", "expression": "slight smile",
                                                    "outfit": "pink bodysuit, white socks", "background": "stadium seats", "light": "evening light"},
                                       "label": "тест замены"})]
        return {"choices": [{"message": {"content": "Разобрал кадр: **тест**. Меняю через Seedream.", "tool_calls": calls}}]}
    if last["role"] == "review":
        return {"choices": [{"message": {"content": "", "tool_calls": [{"id": "c" + secrets.token_hex(3), "type": "function", "function": {"name": "review", "arguments": json.dumps({"image_ids": last["images"], "ok": ["Поза и свет как на исходнике"], "issues": ["Тестовый режим — лицо не проверялось"], "suggestions": ["Карусель 4", "Локальная правка: убери тату"]}, ensure_ascii=False)}}]}}]}
    n_img = sum(1 for m in msgs if isinstance(m.get("content"), list))
    return {"choices": [{"message": {"content": f"Готово. В контексте сообщений с картинками: {n_img}."}}]}


def safe_tool(cid, call, cfg):
    try:
        r = run_tool(cid, call, cfg)
        job_update(cid, call["id"], state="done", ended=time.time())
        return r
    except Exception as e:
        traceback.print_exc()
        job_update(cid, call["id"], state="error", ended=time.time())
        return f"ОШИБКА: {str(e)[:1200]}", [], 0.0


def start_agent(cid, cfg=None):
    if cid in RUNNING:
        return False
    RUNNING[cid] = {"stop": False, "owner": (cfg or {}).get("_ctx", {}).get("owner_id")}
    threading.Thread(target=agent_loop, args=(cid, cfg), daemon=True).start()
    return True


def import_folder(cid, folder):
    folder = Path(folder.strip().strip('"'))
    if not folder.is_dir():
        raise RuntimeError(f"папка не найдена: {folder}")
    faces, body, extra = [], [], {}

    def imgs(d):
        return [f for f in sorted(d.glob("*")) if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
    for sub, lst in (("faces", faces), ("body", body)):
        for f in imgs(folder / sub) if (folder / sub).is_dir() else []:
            lst.append(add_image(cid, f.read_bytes(), "ref", f.stem))
    for d in sorted(folder.iterdir()):
        if d.is_dir() and d.name not in ("faces", "body", "recipes") and imgs(d):
            note = (d / "note.txt").read_text(encoding="utf-8").strip() if (d / "note.txt").exists() else ""
            extra[d.name] = {"ids": [add_image(cid, f.read_bytes(), "ref", f.stem) for f in imgs(d)], "note": note}
    card = (folder / "card.md").read_text(encoding="utf-8") if (folder / "card.md").exists() else ""

    def f(c):
        c["persona"]["faces"] += faces; c["persona"]["body"] += body
        for k, v in extra.items():
            key = cat_key(c["persona"], k)
            set_group_ids(c["persona"], key, group_ids(c["persona"], key) + v["ids"])
            if v["note"] and key not in BUILTIN:
                c["persona"]["extra"][key]["note"] = v["note"]
        if card:
            c["persona"]["card"] = card
        if c["name"] in ("Новая модель", ""):
            c["name"] = folder.name
    update_chat(cid, f)
    return {"faces": len(faces), "body": len(body), "card": bool(card), "extra": {k: len(v["ids"]) for k, v in extra.items()}}


def export_folder(cid, folder):
    c = load_chat(cid)
    folder = Path(folder.strip().strip('"'))
    n = 0
    for key, name, ids, note in ref_groups(c["persona"]):
        sub = re.sub(r'[<>:"/\\|?*]+', "_", key)
        (folder / sub).mkdir(parents=True, exist_ok=True)
        if note and key not in BUILTIN:
            (folder / sub / "note.txt").write_text(note, encoding="utf-8")
        for k, i in enumerate(ids):
            src = image_path(cid, i, c)
            lab = re.sub(r"[^\w\-]+", "_", c["images"][i].get("label") or "")[:30]
            pre = sub[:4] if key in BUILTIN else "ref"
            shutil.copy(src, folder / sub / f"{pre}_{k + 1:02d}{'_' + lab if lab else ''}{src.suffix}")
            n += 1
    p = c["persona"]
    card = f"# {c['name']}\n\n{p['card']}\n"
    if p.get("card_en"):
        card += f"\n## Identity (EN)\n{p['card_en']}\n"
    if p.get("card_zh"):
        card += f"\n## 人物身份 (ZH)\n{p['card_zh']}\n"
    (folder / "card.md").write_text(card, encoding="utf-8")
    return {"files": n, "path": str(folder)}


def duplicate_chat(cid, name=None):
    src = load_chat(cid)
    dst = new_chat(name or f"{src['name']} (копия)", src.get("owner"))
    keep = all_ref_ids(src["persona"])
    imgs = {}
    for i in keep:
        rec = dict(src["images"][i]); rec.pop("ws_url", None)
        shutil.copy(chat_dir(cid) / "files" / rec["file"], chat_dir(dst["id"]) / "files" / rec["file"])
        imgs[i] = rec

    def f(c):
        c["images"] = imgs
        c["persona"] = json.loads(json.dumps(src["persona"]))
        c["parent"] = src.get("parent") or cid
    update_chat(dst["id"], f)
    return load_chat(dst["id"])


def owner_pref(owner):
    f = OWNERS / f"{int(owner)}.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except (OSError, ValueError):
        return {}


def set_owner_pref(owner, **kw):
    with LOCK:
        d = owner_pref(owner); d.update(kw)
        OWNERS.mkdir(parents=True, exist_ok=True)
        (OWNERS / f"{int(owner)}.json").write_text(json.dumps(d), encoding="utf-8")


def chat_usage(cid):
    c = load_chat(cid)
    d = chat_dir(cid) / "files"
    size = sum(f.stat().st_size for f in d.iterdir() if f.is_file()) if d.exists() else 0
    return {"images": len(c["images"]), "refs": len(all_ref_ids(c["persona"])),
            "messages": len([m for m in c["messages"] if m["role"] in ("user", "assistant")]),
            "bytes": size, "spent": c.get("spent", 0)}


def cut_after(c, idx):
    """Оставить сообщения [0..idx]."""
    c["messages"] = c["messages"][: idx + 1]
    c["pending"] = None; c["approved"] = False; c["jobs"] = []
    c["status"] = "idle"; c["status_text"] = ""


def msg_index(c, mid):
    for i, m in enumerate(c["messages"]):
        if m.get("id") == mid:
            return i
    raise KeyError("нет сообщения")


# ---------------- HTTP ----------------
def public_chat(chat):
    c = dict(chat)
    c["running"] = chat["id"] in RUNNING
    return c


def chat_summary(c):
    face = next((i for i in c["persona"]["faces"] if i in c["images"]), None)
    return {"id": c["id"], "name": c["name"], "updated": c["updated"],
            "thumb": f"/thumbs/{c['id']}/{c['images'][face]['file']}" if face else None,
            "status": c["status"], "running": c["id"] in RUNNING, "spent": c.get("spent", 0),
            "archived": c.get("archived", False), "pinned": c.get("pinned", False),
            "parent": c.get("parent"), "images": len(c["images"]),
            "refs": len(all_ref_ids(c["persona"]))}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, obj=None, ctype="application/json", raw=None, headers=None):
        body = raw if raw is not None else json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers(); self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def jbody(self):
        b = self.body()
        if not b:
            return {}
        try:
            return json.loads(b.decode("utf-8"))
        except UnicodeDecodeError:
            return json.loads(b.decode("cp1251"))

    def handle_any(self, method):
        try:
            self.route(method)
        except KeyError as e:
            self.send(404, {"error": str(e)})
        except Exception as e:
            traceback.print_exc(); self.send(500, {"error": str(e)})

    def do_GET(self): self.handle_any("GET")
    def do_POST(self): self.handle_any("POST")
    def do_PUT(self): self.handle_any("PUT")
    def do_PATCH(self): self.handle_any("PATCH")
    def do_DELETE(self): self.handle_any("DELETE")

    def cfg(self):
        """Настройки для запроса: в хостинге — ключи и модель от model-mate, autorun владельца."""
        cfg = load_config()
        ctx = getattr(self, "ctx", None)
        if ctx:
            cfg.update(xai_key=ctx.get("xai_key") or "", wavespeed_key=ctx.get("wavespeed_key") or "",
                       chat_model=ctx.get("grok_model") or cfg["chat_model"], limits={"per_message": 0, "per_day": 0},
                       autorun=bool(owner_pref(ctx["owner_id"]).get("autorun", False)))
            cfg["_ctx"] = {k: v for k, v in ctx.items() if k not in ("xai_key", "wavespeed_key")}
        return cfg

    def own(self, cid):
        """Хостинг: чат должен принадлежать владельцу пространства."""
        if getattr(self, "ctx", None) is None:
            return
        try:
            owner = load_chat(cid).get("owner")
        except (ValueError, OSError):
            raise KeyError("чат не найден")
        if owner != self.ctx["owner_id"]:
            raise KeyError("чат не найден")

    def route(self, method):
        path = unquote(urlparse(self.path).path)
        parts = [p for p in path.split("/") if p]
        self.ctx = None
        if hosted.ENABLED and parts[:1] == ["api"]:
            try:
                self.ctx = hosted.session(self.headers)
            except hosted.AuthError as e:
                return self.send(e.code if e.code in (401, 402, 403, 404) else 502,
                                 {"error": str(e), "reason": e.reason, "login": e.code == 401})
            except OSError as e:
                return self.send(503, {"error": f"Кабинет model-mate не ответил: {e}"})
            n = int(self.headers.get("Content-Length") or 0)
            if n > 300 * 1024 * 1024:
                return self.send(413, {"error": "Файл больше 300 МБ"})
            if parts[1:2] in (["prompts"], ["models"]) or parts[1:3] == ["config", "check"] or (len(parts) == 4 and parts[3] in ("import", "export")):
                return self.send(403, {"error": "Недоступно в кабинете model-mate"})
        if method == "GET" and (path == "/" or parts[:1] == ["static"]):
            f = STATIC / ("index.html" if path == "/" else "/".join(parts[1:]))
            f = f.resolve()
            if STATIC.resolve() not in f.parents or not f.is_file():
                return self.send(404, {"error": "not found"})
            return self.send(200, raw=f.read_bytes(), ctype=(mimetypes.guess_type(f.name)[0] or "text/plain") + "; charset=utf-8")
        if method == "GET" and parts[:1] == ["files"] and len(parts) == 3:
            f = (chat_dir(parts[1]) / "files" / parts[2]).resolve()
            if (chat_dir(parts[1]) / "files").resolve() not in f.parents or not f.is_file():
                return self.send(404, {"error": "not found"})
            ctype = mimetypes.guess_type(f.name)[0] or "image/jpeg"
            if f.suffix.lower() in VIDEO_EXT:   # видео: поддержка Range, чтобы работала перемотка
                size = f.stat().st_size
                m = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range") or "")
                if m and (m.group(1) or m.group(2)):
                    s = int(m.group(1)) if m.group(1) else size - int(m.group(2))
                    e = min(int(m.group(2)), size - 1) if m.group(1) and m.group(2) else size - 1
                    with open(f, "rb") as fh:
                        fh.seek(s); chunk = fh.read(e - s + 1)
                    self.send_response(206)
                    self.send_header("Content-Type", ctype); self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Range", f"bytes {s}-{e}/{size}"); self.send_header("Content-Length", str(len(chunk)))
                    self.end_headers(); self.wfile.write(chunk); return
                return self.send(200, raw=f.read_bytes(), ctype=ctype, headers={"Accept-Ranges": "bytes"})
            return self.send(200, raw=f.read_bytes(), ctype=ctype, headers={"Cache-Control": "max-age=86400"})
        if method == "GET" and parts[:1] == ["thumbs"] and len(parts) == 3:
            src = (chat_dir(parts[1]) / "files" / parts[2]).resolve()
            if (chat_dir(parts[1]) / "files").resolve() not in src.parents or not src.is_file():
                return self.send(404, {"error": "not found"})
            tdir = chat_dir(parts[1]) / "thumbs"; tdir.mkdir(exist_ok=True)
            t = tdir / (src.stem + ".jpg")
            if not t.exists() or t.stat().st_mtime < src.stat().st_mtime:
                im = Image.open(io.BytesIO(grab_frame(src, 0.05, 720)) if src.suffix.lower() in VIDEO_EXT else src)
                im = im.convert("RGB"); im.thumbnail((520, 520), Image.LANCZOS); im.save(t, "JPEG", quality=84)
            return self.send(200, raw=t.read_bytes(), ctype="image/jpeg", headers={"Cache-Control": "max-age=86400"})
        if parts[:1] != ["api"]:
            return self.send(404, {"error": "not found"})
        p = parts[1:]

        # ---- config ----
        if p == ["config"] and self.ctx:
            if method in ("POST", "PATCH"):
                new = self.jbody()
                if "autorun" in new:
                    set_owner_pref(self.ctx["owner_id"], autorun=bool(new["autorun"]))
            cfg = self.cfg(); ctx = self.ctx
            return self.send(200, {"hosted": True, "chat_model": cfg["chat_model"], "autorun": cfg["autorun"],
                                   "prices": {"gpt": gen_price("gpt", 5, cfg), "seedream": gen_price("seedream", 6, cfg),
                                              **{k: v for k, v in cfg["prices"].items() if k.startswith("seedance")}},
                                   "limits": cfg["limits"], "multiplier": ctx.get("multiplier"), "ws_mode": ctx.get("ws_mode"),
                                   "balance": ctx.get("balance"), "plan": ctx.get("plan"), "grok_reserve": GROK_RESERVE,
                                   "billing_url": ctx.get("billing_url") or "/workspace/", "xai_key": "", "wavespeed_key": ""})
        if p == ["config"]:
            cfg = load_config()
            if method in ("POST", "PATCH"):
                new = self.jbody()
                for k in ("xai_key", "wavespeed_key"):
                    if new.get(k) and "•" not in new[k]:
                        cfg[k] = new[k].strip()
                    elif new.get(k) == "":
                        cfg[k] = ""
                if new.get("chat_model"):
                    cfg["chat_model"] = new["chat_model"].strip()
                if "autorun" in new:
                    cfg["autorun"] = bool(new["autorun"])
                for k in ("prices", "limits"):
                    if isinstance(new.get(k), dict):
                        cfg[k].update({kk: float(v or 0) for kk, v in new[k].items()})
                save_config(cfg)
            out = dict(cfg)
            for k in ("xai_key", "wavespeed_key"):
                out[k] = ("••••" + cfg[k][-4:]) if cfg[k] else ""
            return self.send(200, out)
        if p == ["config", "check"]:
            svc = self.jbody().get("service"); cfg = load_config()
            try:
                if svc == "xai":
                    if not cfg["xai_key"]:
                        raise RuntimeError("ключ не задан")
                    n = len(http_json(f"{XAI}/models", cfg["xai_key"], timeout=30).get("data", []))
                    return self.send(200, {"ok": True, "info": f"моделей доступно: {n}"})
                if svc == "wavespeed":
                    if not cfg["wavespeed_key"]:
                        raise RuntimeError("ключ не задан")
                    b = http_json(f"{WS}/balance", cfg["wavespeed_key"], timeout=30)["data"]["balance"]
                    return self.send(200, {"ok": True, "info": f"баланс ${b}", "balance": b})
                return self.send(400, {"ok": False, "error": "service: xai | wavespeed"})
            except Exception as e:
                return self.send(200, {"ok": False, "error": str(e)[:300]})
        if p == ["models"]:
            cfg = load_config()
            if not cfg["xai_key"] or cfg["xai_key"] == "mock":
                return self.send(200, {"models": []})
            r = http_json(f"{XAI}/models", cfg["xai_key"])
            return self.send(200, {"models": sorted(m["id"] for m in r.get("data", []))})
        if p == ["balance"] and self.ctx:
            return self.send(200, {"credits": self.ctx.get("balance"), "ws_mode": self.ctx.get("ws_mode")})
        if p == ["spend"] and self.ctx:
            return self.send(200, {"today": 0, "limit": 0, "per_message": 0})
        if p == ["balance"]:
            cfg = load_config(); out = {}
            if cfg["wavespeed_key"]:
                try:
                    out["wavespeed"] = http_json(f"{WS}/balance", cfg["wavespeed_key"], timeout=30)["data"]["balance"]
                except Exception as e:
                    out["wavespeed_error"] = str(e)[:200]
            return self.send(200, out)
        if p == ["spend"]:
            cfg = load_config()
            return self.send(200, {"today": round(spend_today(), 3), "limit": cfg["limits"].get("per_day", 0),
                                   "per_message": cfg["limits"].get("per_message", 0)})

        # ---- prompts ----
        if len(p) >= 2 and p[0] == "prompts" and p[1] in PROMPT_NAMES:
            f, d = prompt_file(p[1]), default_prompt_file(p[1])
            if len(p) == 3 and p[2] == "reset" and method == "POST":
                shutil.copy(d, f)
            elif method in ("PUT", "POST"):
                f.write_text(self.jbody().get("text", ""), encoding="utf-8")
            text = f.read_text(encoding="utf-8")
            return self.send(200, {"name": p[1], "text": text,
                                   "modified": text != (d.read_text(encoding="utf-8") if d.exists() else text)})

        # ---- chats ----
        if p == ["chats"]:
            if method == "POST":
                b = self.jbody()
                return self.send(200, public_chat(new_chat(b.get("name", "").strip(), self.ctx["owner_id"] if self.ctx else None)))
            CHATS.mkdir(parents=True, exist_ok=True)
            lst = []
            for d in CHATS.iterdir():
                if (d / "chat.json").exists():
                    try:
                        c = load_chat(d.name)
                        if self.ctx and c.get("owner") != self.ctx["owner_id"]:
                            continue
                        lst.append(chat_summary(c))
                    except Exception:
                        traceback.print_exc()
            return self.send(200, sorted(lst, key=lambda x: -x["updated"]))
        if len(p) >= 2 and p[0] == "chats":
            cid = p[1]
            self.own(cid)
            if len(p) == 2 and method == "GET":
                return self.send(200, public_chat(load_chat(cid)))
            if len(p) == 2 and method == "DELETE":
                if cid in RUNNING:
                    RUNNING[cid]["stop"] = True
                shutil.rmtree(chat_dir(cid)); return self.send(200, {"ok": True})
            if len(p) == 2 and method == "PATCH" or (len(p) == 3 and p[2] == "meta"):
                b = self.jbody()

                def f(c):
                    if b.get("name", "").strip():
                        c["name"] = b["name"].strip()
                    for k in ("archived", "pinned"):
                        if k in b:
                            c[k] = bool(b[k])
                update_chat(cid, f)
                return self.send(200, public_chat(load_chat(cid)))
            act = p[2] if len(p) > 2 else ""
            if act == "usage":
                return self.send(200, chat_usage(cid))
            if act == "duplicate":
                return self.send(200, public_chat(duplicate_chat(cid, self.jbody().get("name"))))
            if act == "upload":
                fname = unquote(self.headers.get("X-Filename", ""))
                ext = Path(fname).suffix.lower()
                if ext in VIDEO_EXT or (self.headers.get("Content-Type") or "").startswith("video/"):
                    vid = add_video(cid, self.body(), "user", Path(fname).stem, ext=ext or ".mp4")
                    c = load_chat(cid)
                    return self.send(200, {"id": vid, "kind": "video", "video": c["videos"][vid]})
                iid = add_image(cid, self.body(), "user", fname)
                return self.send(200, {"id": iid, "kind": "image", "image": load_chat(cid)["images"][iid]})
            if act == "message":
                b = self.jbody()
                if cid in RUNNING:
                    return self.send(409, {"error": "уже выполняется"})
                cfg = self.cfg()
                if not cfg["xai_key"]:
                    return self.send(400, {"error": "Grok временно недоступен" if self.ctx else "Сначала впиши ключ xAI в настройках"})
                if self.ctx:
                    busy = sum(1 for r in RUNNING.values() if r.get("owner") == self.ctx["owner_id"])
                    if busy >= 3:
                        return self.send(429, {"error": "Уже идут 3 генерации в других чатах — дождитесь их"})
                    prob = hosted.check(self.ctx, GROK_RESERVE)
                    if prob:
                        return self.send(402, {"error": prob[:1].upper() + prob[1:]})
                cur = load_chat(cid)
                ids = [i for i in b.get("images", []) if i in cur["images"]]
                vids = [v for v in b.get("videos", []) if v in cur["videos"]]

                def f(c):
                    c["pending"] = None; c["approved"] = False
                    if c["messages"] and c["messages"][-1]["role"] == "assistant" and c["messages"][-1].get("tool_calls"):
                        for tc in c["messages"][-1]["tool_calls"]:
                            c["messages"].append({"id": new_mid(), "role": "tool", "tool_call_id": tc["id"], "name": tc["function"]["name"],
                                                  "text": "Не выполнено: пользователь написал новое сообщение.", "t": time.time()})
                    c["messages"].append({"id": new_mid(), "role": "user", "text": b.get("text", ""), "images": ids,
                                          "videos": vids, "engine": b.get("engine", "auto"), "t": time.time()})
                update_chat(cid, f)
                start_agent(cid, cfg)
                return self.send(200, {"ok": True})
            if act == "pending" and method in ("PATCH", "POST"):
                edits = self.jbody().get("jobs", [])
                cfg = self.cfg()
                c0 = load_chat(cid)
                if not c0.get("pending"):
                    raise KeyError("нечего править")
                calls = json.loads(json.dumps(c0["messages"][-1]["tool_calls"]))
                for e in edits:
                    edit_call(cid, calls[int(e["i"])], e, cfg)

                def f(c):
                    if not c.get("pending"):
                        raise KeyError("нечего править")
                    c["messages"][-1]["tool_calls"] = calls
                    c["pending"] = pending_summary(calls, cfg, c)
                    c["pending"]["edited"] = True
                    c["status"] = "awaiting"; c["status_text"] = f"Ждёт подтверждения ≈ {money(cfg, c['pending']['cost'])}"
                update_chat(cid, f)
                return self.send(200, public_chat(load_chat(cid)))
            if act == "approve":
                b = self.jbody(); ok = b.get("ok", False)
                if not load_chat(cid).get("pending"):
                    return self.send(409, {"error": "нечего подтверждать"})
                if ok:
                    if b.get("autorun"):
                        if self.ctx:
                            set_owner_pref(self.ctx["owner_id"], autorun=True)
                        else:
                            cfg = load_config(); cfg["autorun"] = True; save_config(cfg)
                    update_chat(cid, lambda c: c.update(approved=True, pending=None))
                    start_agent(cid, self.cfg())
                else:
                    def f(c):
                        c["pending"] = None
                        last = c["messages"][-1] if c["messages"] else {}
                        for tc in last.get("tool_calls", []) if last.get("role") == "assistant" else []:
                            c["messages"].append({"id": new_mid(), "role": "tool", "tool_call_id": tc["id"], "name": tc["function"]["name"],
                                                  "text": "Пользователь отменил запуск. Спроси, что изменить.", "t": time.time()})
                        c["status"] = "idle"; c["status_text"] = ""
                    update_chat(cid, f)
                return self.send(200, {"ok": True})
            if act == "stop":
                if cid in RUNNING:
                    RUNNING[cid]["stop"] = True
                return self.send(200, {"ok": True})
            if act in ("retry", "regenerate", "rollback"):
                if cid in RUNNING:
                    return self.send(409, {"error": "уже выполняется"})
                b = self.jbody()

                def f(c):
                    if act == "retry":
                        while c["messages"] and c["messages"][-1]["role"] == "error":
                            c["messages"].pop()
                        c["status"] = "idle"
                    elif act == "regenerate":
                        u = max([i for i, m in enumerate(c["messages"]) if m["role"] == "user"] or [-1])
                        if u < 0:
                            raise KeyError("нет сообщения пользователя")
                        cut_after(c, u)
                    else:
                        cut_after(c, msg_index(c, b.get("mid")))
                    return c["messages"][-1]["role"] if c["messages"] else None
                last_role = update_chat(cid, f)
                if last_role and (act != "rollback" or last_role == "user"):
                    start_agent(cid, self.cfg())
                return self.send(200, public_chat(load_chat(cid)))
            if len(p) == 4 and act == "messages" and method == "DELETE":
                mid = p[3]

                def f(c):
                    i = msg_index(c, mid); m = c["messages"][i]
                    drop = {i}
                    if m["role"] == "assistant" and m.get("tool_calls"):
                        ids = {tc["id"] for tc in m["tool_calls"]}
                        for j, x in enumerate(c["messages"]):
                            if x["role"] == "tool" and x.get("tool_call_id") in ids:
                                drop.add(j)
                        if i == len(c["messages"]) - 1:
                            c["pending"] = None
                    c["messages"] = [x for j, x in enumerate(c["messages"]) if j not in drop]
                update_chat(cid, f)
                return self.send(200, public_chat(load_chat(cid)))
            if act == "images":
                if len(p) == 4 and method in ("POST", "PATCH"):
                    b = self.jbody(); iid = p[3]

                    def f(c):
                        rec = c["images"][iid]
                        if "fav" in b:
                            rec["fav"] = bool(b["fav"])
                        if "label" in b:
                            rec["label"] = str(b["label"])[:80]
                    update_chat(cid, f)
                    return self.send(200, {"ok": True, "image": load_chat(cid)["images"][iid]})
                if len(p) == 3 and method in ("DELETE", "POST"):
                    n = delete_images(cid, self.jbody().get("ids", []))
                    return self.send(200, {"ok": True, "deleted": n})
            if act == "videos":
                if len(p) == 4 and method in ("POST", "PATCH"):
                    b = self.jbody(); vid = p[3]

                    def f(c):
                        rec = c["videos"][vid]
                        if "fav" in b:
                            rec["fav"] = bool(b["fav"])
                        if "label" in b:
                            rec["label"] = str(b["label"])[:80]
                    update_chat(cid, f)
                    return self.send(200, {"ok": True, "video": load_chat(cid)["videos"][vid]})
                if len(p) == 3 and method in ("DELETE", "POST"):
                    return self.send(200, {"ok": True, "deleted": delete_videos(cid, self.jbody().get("ids", []))})
            if act == "zip":
                c = load_chat(cid); ids = self.jbody().get("ids") or list(c["images"])
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
                    for i in ids:
                        if i in c["images"]:
                            z.write(image_path(cid, i, c), c["images"][i]["file"])
                        elif i in c["videos"]:
                            z.write(video_path(cid, i, c), c["videos"][i]["file"])
                name = re.sub(r"[^\w\-]+", "_", c["name"]) or "images"
                return self.send(200, raw=buf.getvalue(), ctype="application/zip",
                                 headers={"Content-Disposition": f"attachment; filename=\"{name}.zip\""})
            if act == "persona":
                b = self.jbody()

                def f(c):
                    per = c["persona"]
                    for k in ("card", "card_en", "card_zh"):
                        if k in b:
                            per[k] = b[k]
                    if b.get("name", "").strip():
                        c["name"] = b["name"].strip()
                    for k in ("faces", "body"):
                        if k in b:
                            per[k] = [i for i in b[k] if i in c["images"]]
                    if isinstance(b.get("extra"), dict):
                        per["extra"] = {str(k).strip()[:40]: {"ids": [i for i in v.get("ids", []) if i in c["images"]], "note": str(v.get("note", ""))}
                                        for k, v in b["extra"].items() if str(k).strip() and str(k).strip().lower() not in ALIASES}
                    if isinstance(b.get("notes"), dict):
                        per.setdefault("notes", {}).update({k: str(v) for k, v in b["notes"].items() if k in BUILTIN})
                update_chat(cid, f)
                return self.send(200, public_chat(load_chat(cid)))
            if act == "import":
                return self.send(200, import_folder(cid, self.jbody().get("path", "")))
            if act == "export":
                return self.send(200, export_folder(cid, self.jbody().get("path", "")))
        return self.send(404, {"error": "not found"})


if __name__ == "__main__":
    CHATS.mkdir(parents=True, exist_ok=True)
    ensure_prompt_defaults()
    for d in CHATS.iterdir():   # после перезапуска сбросить «running»
        if (d / "chat.json").exists():
            c = json.loads((d / "chat.json").read_text(encoding="utf-8"))
            if c.get("status") == "running":
                c["status"] = "idle"; c["jobs"] = []; save_chat(c)
    print(f"Persona Studio: http://localhost:{PORT}" + (f" (хостинг: {hosted.API})" if hosted.ENABLED else ""))
    ThreadingHTTPServer((HOST, PORT), H).serve_forever()

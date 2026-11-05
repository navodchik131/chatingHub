"""Person -> line-art silhouette over the real background.
Usage:
  python lineart.py frames <out_dir> <img1> [img2 ...]      # preview stills
  python lineart.py video <in.mp4> <out.mp4>                # full video (audio copied)
"""
import sys, os, subprocess
import cv2
import numpy as np
from rembg import new_session, remove
from PIL import Image

SESSION = new_session("u2net_human_seg")


def person_mask(bgr):
    rgb = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    m = np.array(remove(rgb, session=SESSION, only_mask=True))
    m = (m > 110).astype(np.uint8) * 255
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k)
    m = cv2.dilate(m, k, iterations=1)
    return m


def xdog(gray, sigma=0.9, k=1.6, p=22, eps=-0.08, phi=12.0):
    g = gray.astype(np.float32) / 255.0
    g1 = cv2.GaussianBlur(g, (0, 0), sigma)
    g2 = cv2.GaussianBlur(g, (0, 0), sigma * k)
    d = (1 + p) * g1 - p * g2
    out = np.where(d >= eps, 1.0, 1.0 + np.tanh(phi * (d - eps)))
    return (np.clip(out, 0, 1) * 255).astype(np.uint8)


def lineart(bgr):
    h, w = bgr.shape[:2]
    m = person_mask(bgr)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    # normalise local contrast so dark faces in night light still give lines
    gray = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(gray)
    gray = cv2.bilateralFilter(gray, 9, 50, 9)
    lines = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 6)
    # remove speckle noise
    inv = 255 - lines
    n, lab, stats, _ = cv2.connectedComponentsWithStats(inv, 8)
    keep = np.zeros_like(inv)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= max(6, (h * w) // 120000):
            keep[lab == i] = 255
    lines = 255 - keep
    # silhouette outline
    edge = cv2.morphologyEx(m, cv2.MORPH_GRADIENT, np.ones((5, 5), np.uint8))
    lines[edge > 0] = 0
    art = cv2.cvtColor(lines, cv2.COLOR_GRAY2BGR)
    a = cv2.GaussianBlur(m, (5, 5), 0).astype(np.float32)[..., None] / 255.0
    return (art * a + bgr * (1 - a)).astype(np.uint8)


def do_frames(out_dir, paths):
    os.makedirs(out_dir, exist_ok=True)
    for p in paths:
        img = cv2.imread(p)
        cv2.imwrite(os.path.join(out_dir, "la_" + os.path.basename(p)), lineart(img))


def do_video(src, dst, progress=None):
    cap = cv2.VideoCapture(src)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    ok, fr = cap.read()
    if not ok:
        raise RuntimeError("не удалось прочитать видео")
    h, w = fr.shape[:2]            # размер по реальному кадру (учитывает поворот телефона)
    w2, h2 = w - w % 2, h - h % 2
    tmp = dst + ".noaudio.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
                           "-s", f"{w2}x{h2}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", "16",
                           "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    n = 0
    while ok:
        ff.stdin.write(np.ascontiguousarray(lineart(fr)[:h2, :w2]).tobytes()); n += 1
        if progress and n % 10 == 0:
            progress(n, total)
        ok, fr = cap.read()
    ff.stdin.close(); ff.wait(); cap.release()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-i", src, "-map", "0:v", "-map", "1:a?",
                    "-c:v", "copy", "-c:a", "copy", "-shortest", dst], check=True)
    os.remove(tmp)
    print("frames", n, "->", dst)


if __name__ == "__main__":
    if sys.argv[1] == "frames":
        do_frames(sys.argv[2], sys.argv[3:])
    else:
        do_video(sys.argv[2], sys.argv[3])

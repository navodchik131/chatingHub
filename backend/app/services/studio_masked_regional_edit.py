"""
Утилиты для маски студии в legacy-пайплайне (бывший кроп+склейка).

При STUDIO_REGIONAL_MASKED_EDIT=true запрос студии маски уходит напрямую в Nano Banana / WAN
как пара URL (полный кадр + выровненная маска) см. backend/app/api/studio_routes.py.
Склеивание `compose_regional_masked_png` в основном студийном потоке больше не используется,
но остаётся в модуле на случай внешних вызовов / отката.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO
import numpy as np
from PIL import Image, ImageFilter, ImageOps

log = logging.getLogger(__name__)


@dataclass
class RegionalMaskedWorkspace:
    """Контекст для финальной сборки после ответа WaveSpeed."""

    crop_box: tuple[int, int, int, int]  # left, upper, right, lower (для PIL)
    feather_alpha: np.ndarray  # float HW, 0–1: вклад редактируемого кропа в центре белой маски
    full_rgb: Image.Image


def _open_rgb_transpose(data: bytes) -> Image.Image:
    im = Image.open(BytesIO(data))
    im = ImageOps.exif_transpose(im)
    return im.convert("RGB")


def _mask_luma_same_size(rgb_size: tuple[int, int], mask_bytes: bytes) -> Image.Image:
    m = Image.open(BytesIO(mask_bytes))
    m = ImageOps.exif_transpose(m)
    if m.mode in ("RGBA", "P"):
        m = m.convert("RGBA")
        r, g, b, a = m.split()
        # белая маска: max по каналам; альфа тоже учитывается
        np_r = np.array(r, dtype=np.uint16)
        np_g = np.array(g, dtype=np.uint16)
        np_b = np.array(b, dtype=np.uint16)
        np_a = np.array(a, dtype=np.uint16)
        lum = np.maximum(np.maximum(np_r, np_g), np.maximum(np_b, np_a)).astype(np.uint8)
        m_l = Image.fromarray(lum, mode="L")
    else:
        m_l = m.convert("L")
    if m_l.size != rgb_size:
        m_l = m_l.resize(rgb_size, resample=Image.Resampling.LANCZOS)
    return m_l


def studio_mask_png_bytes_aligned_to_reference(
    reference_image_bytes: bytes,
    inpaint_mask_bytes: bytes,
) -> bytes:
    """
    Маска в тех же WxH что и RGB-кадр (PNG L): при расхождении — NEAREST.

    WAN/Nano ожидают выровненную геометрию второго входа; иначе бывают невнятные отказы.
    """
    ref = _open_rgb_transpose(reference_image_bytes)
    m_img = Image.open(BytesIO(inpaint_mask_bytes))
    m_img = ImageOps.exif_transpose(m_img)
    if m_img.mode in ("RGBA", "P"):
        m_img = m_img.convert("RGBA")
        r, g, b, a = m_img.split()
        np_r = np.array(r, dtype=np.uint16)
        np_g = np.array(g, dtype=np.uint16)
        np_b = np.array(b, dtype=np.uint16)
        np_a = np.array(a, dtype=np.uint16)
        lum = np.maximum(np.maximum(np_r, np_g), np.maximum(np_b, np_a)).astype(np.uint8)
        m_gray = Image.fromarray(lum, mode="L")
    else:
        m_gray = m_img.convert("L")
    target = ref.size
    if m_gray.size != target:
        log.warning(
            "studio inpaint mask %s resized to reference %s before WaveSpeed",
            m_gray.size,
            target,
        )
        m_gray = m_gray.resize(target, resample=Image.Resampling.NEAREST)
    buf = BytesIO()
    m_gray.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def composite_fullframe_edit_preserving_unmasked(
    original_image_bytes: bytes,
    edited_image_bytes: bytes,
    mask_png_bytes_aligned: bytes,
    *,
    feather_radius: float = 10.0,
) -> bytes:
    """
    Выход редактора (полный кадр) смешивается с оригиналом: вклад редактирования ↑ там,
    где маска белая (после необязательного Gaussian blur по краю). Вне маски — исходные RGB.
    """
    orig = _open_rgb_transpose(original_image_bytes)
    edi = _open_rgb_transpose(edited_image_bytes)
    if edi.size != orig.size:
        edi = edi.resize(orig.size, resample=Image.Resampling.LANCZOS)

    mask_im = Image.open(BytesIO(mask_png_bytes_aligned))
    if mask_im.mode not in ("L", "1"):
        mask_im = mask_im.convert("L")
    if mask_im.size != orig.size:
        mask_im = mask_im.resize(orig.size, resample=Image.Resampling.NEAREST)

    alpha_l = mask_im
    if feather_radius > 0.05:
        alpha_l = alpha_l.filter(ImageFilter.GaussianBlur(radius=float(feather_radius)))

    o_arr = np.asarray(orig, dtype=np.float32)
    e_arr = np.asarray(edi, dtype=np.float32)
    a = (np.asarray(alpha_l, dtype=np.float32) / 255.0)[..., np.newaxis]
    a = np.clip(a, 0.0, 1.0)
    blended = e_arr * a + o_arr * (1.0 - a)
    out_u8 = np.clip(np.rint(blended), 0, 255).astype(np.uint8)
    out_im = Image.fromarray(out_u8, mode="RGB")
    out_buf = BytesIO()
    out_im.save(out_buf, format="PNG", optimize=True)
    return out_buf.getvalue()


def _bbox_white_fast(grey: np.ndarray, threshold: int) -> tuple[int, int, int, int] | None:
    ys, xs = np.where(grey >= threshold)
    if xs.size == 0:
        return None
    x0 = int(xs.min())
    x1_excl = int(xs.max()) + 1
    y0 = int(ys.min())
    y1_excl = int(ys.max()) + 1
    return x0, y0, x1_excl, y1_excl


def _pad_box(
    box: tuple[int, int, int, int],
    w: int,
    h: int,
    *,
    pad_x: int,
    pad_y: int,
) -> tuple[int, int, int, int]:
    l, t, r_excl, b_excl = box
    l = max(0, l - pad_x)
    t = max(0, t - pad_y)
    r_excl = min(w, r_excl + pad_x)
    b_excl = min(h, b_excl + pad_y)
    return l, t, r_excl, b_excl


def _inflate_to_min_side(
    box: tuple[int, int, int, int],
    w: int,
    h: int,
    min_side_px: int,
    max_iterations: int = 4096,
) -> tuple[int, int, int, int]:
    l, t, r_excl, b_excl = box
    for _ in range(max_iterations):
        cw = r_excl - l
        ch = b_excl - t
        if cw >= min_side_px and ch >= min_side_px:
            return l, t, r_excl, b_excl
        nl = max(0, l - 1)
        nt = max(0, t - 1)
        nr = min(w, r_excl + 1)
        nb = min(h, b_excl + 1)
        if (nl, nt, nr, nb) == (l, t, r_excl, b_excl):
            break  # упёрлись в границу всего изображения
        l, t, r_excl, b_excl = nl, nt, nr, nb
    return l, t, r_excl, b_excl


def _smooth_feather(mask_crop_l: Image.Image, feather_radius: float) -> np.ndarray:
    """Нормализованная альфа 0–1: белые зоны замены дают вклад генерации (~1 после размытия)."""
    a = np.asarray(mask_crop_l, dtype=np.float32) / 255.0
    if feather_radius <= 0.05:
        return np.clip(a, 0.0, 1.0)
    im = Image.fromarray(np.clip(a * 255.0, 0, 255).astype(np.uint8), mode="L")
    blurred = im.filter(ImageFilter.GaussianBlur(radius=float(feather_radius)))
    return np.clip(np.asarray(blurred, dtype=np.float32) / 255.0, 0.0, 1.0)


def _harmonize_rgb_mean_ring(
    ori: np.ndarray,
    edi: np.ndarray,
    alpha: np.ndarray,
    *,
    ring_thresh: float,
) -> np.ndarray:
    ring = alpha <= ring_thresh
    edi_f = edi.astype(np.float32)
    if ring.sum() < 48:
        return edi_f
    for c in range(3):
        mo = float(ori[..., c][ring].mean())
        me = float(edi_f[..., c][ring].mean())
        edi_f[..., c] = np.clip(edi_f[..., c] + (mo - me), 0.0, 255.0)
    return edi_f


def regional_masked_crop_to_png_workspace(
    image_bytes: bytes,
    mask_bytes: bytes,
    *,
    pad_ratio: float,
    min_crop_side_px: int,
    feather_radius: float,
    mask_threshold: int,
) -> tuple[bytes, RegionalMaskedWorkspace]:
    """Готовит PNG-кроп для WaveSpeed и рабочие данные для склейки."""
    rgb = _open_rgb_transpose(image_bytes)
    full_w, full_h = rgb.size
    lum = np.asarray(_mask_luma_same_size((full_w, full_h), mask_bytes), dtype=np.uint8)
    box = _bbox_white_fast(lum, mask_threshold)
    if box is None:
        raise RuntimeError(
            "На маске нет области для замены: закрасьте кистью или загрузите маску, "
            "где белый — редактировать, чёрное — сохранить."
        )
    bw = box[2] - box[0]
    bh = box[3] - box[1]
    px = max(8, int(max(bw, bh) * pad_ratio))
    padded = _pad_box(box, full_w, full_h, pad_x=px, pad_y=px)
    padded = _inflate_to_min_side(padded, full_w, full_h, min_crop_side_px)
    cl, ct, cr_excl, cb_excl = padded
    if cr_excl <= cl + 2 or cb_excl <= ct + 2:
        raise RuntimeError("Некорректный регион кропа по маске.")

    cropped_rgb = rgb.crop((cl, ct, cr_excl, cb_excl))
    mask_im = Image.fromarray(lum, mode="L")
    mask_crop = mask_im.crop((cl, ct, cr_excl, cb_excl))
    alpha = _smooth_feather(mask_crop, feather_radius)
    feather_alpha = alpha.astype(np.float64, copy=False)

    ws = RegionalMaskedWorkspace(
        crop_box=(cl, ct, cr_excl, cb_excl),
        feather_alpha=feather_alpha,
        full_rgb=rgb,
    )

    buf = BytesIO()
    cropped_rgb.save(buf, format="PNG", optimize=True)
    crop_png_bytes = buf.getvalue()
    log.debug(
        "regional masked workspace: bbox=%s pad_ratio=%s min_side=%s crop_png=%sb",
        (cl, ct, cr_excl, cb_excl),
        pad_ratio,
        min_crop_side_px,
        len(crop_png_bytes),
    )
    return crop_png_bytes, ws


REGIONAL_WS_PROMPT_ADDON_EN = (
    " CRITICAL: This view is already tightly cropped — apply the user's edit ONLY to the depicted region; "
    "keep identity, anatomy, materials, reflections, shadows and peripheral context consistent "
    "so server-side stitching across the boundaries looks natural."
)


def compose_regional_masked_png(
    workspace: RegionalMaskedWorkspace,
    edited_crop_bytes: bytes,
    *,
    harmonize_ring_thresh: float,
) -> bytes:
    """Протягивает выход модели до размеров кропа, подгонку по среднему в «контекстном кольце» и склейку."""
    eo = BytesIO(edited_crop_bytes)
    edi_im = Image.open(eo)
    edi_im = ImageOps.exif_transpose(edi_im).convert("RGB")

    box = workspace.crop_box
    cw = box[2] - box[0]
    ch = box[3] - box[1]
    if edi_im.size != (cw, ch):
        edi_im = edi_im.resize((cw, ch), resample=Image.Resampling.LANCZOS)

    full_array = np.asarray(workspace.full_rgb, dtype=np.float32)
    ori_crop = full_array[box[1] : box[3], box[0] : box[2]]
    edi_crop = np.asarray(edi_im, dtype=np.float32)
    ah = workspace.feather_alpha
    edi_harm = _harmonize_rgb_mean_ring(
        ori_crop,
        edi_crop,
        ah,
        ring_thresh=harmonize_ring_thresh,
    )

    a = ah[..., np.newaxis]
    patched = ori_crop * (1.0 - a) + edi_harm * a
    composed = np.array(full_array, copy=True)
    composed[box[1] : box[3], box[0] : box[2]] = patched
    composed_uint8 = np.clip(np.round(composed), 0.0, 255.0).astype(np.uint8)
    out_img = Image.fromarray(composed_uint8, mode="RGB")
    out_io = BytesIO()
    out_img.save(out_io, format="PNG", optimize=True)
    return out_io.getvalue()

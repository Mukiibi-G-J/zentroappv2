"""
50×30 mm labels: header (name left, UGX+price right), rule directly under content,
wide Code128 (width-first in ``_code128_bars_resized``, quiet-zone crop). One human-readable code
line under the bars (no duplicate spaced row). Bar height is capped by ``BARCODE_LABEL_BAR_MAX_HEIGHT_MM``
and space under the rule; writer options must pass through ``save(options=...)`` (python-barcode
merges defaults on render). Leftover slack may bump the digit line font only.
``BARCODE_LABEL_BAR_ZONE_HEIGHT_FRAC`` is legacy (unused for height cap).

Tuning (Django settings, all optional): BARCODE_LABEL_WIDTH_MM, HEIGHT_MM, DPI, CURRENCY,
BARCODE_LABEL_BARCODE_WIDTH_FRAC, BARCODE_LABEL_MODULE_HEIGHT_MM,
BARCODE_LABEL_BAR_ZONE_HEIGHT_FRAC (legacy, unused for height cap), BARCODE_LABEL_BAR_MAX_HEIGHT_MM,
BARCODE_LABEL_MODULE_HEIGHT_FLOOR_MM, BARCODE_LABEL_WRITER_QUIET_ZONE_MM,
BARCODE_LABEL_WRITER_MODULE_WIDTH_MM, BARCODE_LABEL_NAME_FONT_MIN/MAX, font paths.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from datetime import datetime
from io import BytesIO
from typing import TYPE_CHECKING, List, Tuple

from PIL import Image, ImageDraw, ImageFont
from barcode import Code128
from barcode.writer import ImageWriter
from django.conf import settings
from financials.currency import get_local_currency_code
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

if TYPE_CHECKING:
    from items.models import Item

logger = logging.getLogger(__name__)

MAX_LABELS = 500

# Physical label size (matches common cut labels / user reference)
LABEL_WIDTH_MM = float(getattr(settings, "BARCODE_LABEL_WIDTH_MM", 50))
LABEL_HEIGHT_MM = float(getattr(settings, "BARCODE_LABEL_HEIGHT_MM", 30))
# Raster resolution for PIL (higher = sharper when embedded in PDF at fixed mm)
LABEL_DPI = int(getattr(settings, "BARCODE_LABEL_DPI", 300))

# Default currency label (tenant LCY unless overridden in settings)
LABEL_CURRENCY = getattr(settings, "BARCODE_LABEL_CURRENCY", None) or get_local_currency_code()

# Barcode target width as fraction of inner_w (near full bleed for thermal labels)
BARCODE_WIDTH_FRAC = float(getattr(settings, "BARCODE_LABEL_BARCODE_WIDTH_FRAC", 0.995))
# Writer native bar height in mm (taller = easier scans; width-first still caps to label)
BARCODE_MODULE_HEIGHT_MM = float(getattr(settings, "BARCODE_LABEL_MODULE_HEIGHT_MM", 5.1))
# Legacy setting: no longer caps bar height (was too aggressive at low values and caused narrow bars).
BARCODE_BAR_ZONE_HEIGHT_FRAC = float(getattr(settings, "BARCODE_LABEL_BAR_ZONE_HEIGHT_FRAC", 0.52))
# Max pasted bar strip height (mm); raise for scanner-friendly bars on 50×30 stock (still width-first).
BARCODE_BAR_MAX_HEIGHT_MM = float(getattr(settings, "BARCODE_LABEL_BAR_MAX_HEIGHT_MM", 8.2))
BARCODE_MODULE_HEIGHT_FLOOR_MM = float(getattr(settings, "BARCODE_LABEL_MODULE_HEIGHT_FLOOR_MM", 2.65))
BARCODE_WRITER_QUIET_ZONE_MM = float(getattr(settings, "BARCODE_LABEL_WRITER_QUIET_ZONE_MM", 1.15))
BARCODE_WRITER_MODULE_WIDTH_MM = float(getattr(settings, "BARCODE_LABEL_WRITER_MODULE_WIDTH_MM", 0.30))
# Product name on label (px bounds; larger = more visible in header)
BARCODE_NAME_FONT_MIN = int(getattr(settings, "BARCODE_LABEL_NAME_FONT_MIN", 18))
BARCODE_NAME_FONT_MAX = int(getattr(settings, "BARCODE_LABEL_NAME_FONT_MAX", 34))


def _mm_to_px(mm_len: float, dpi: int) -> int:
    return int(round(mm_len * dpi / 25.4))


def _get_text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _font_candidates_bold() -> List[str | None]:
    return [
        getattr(settings, "BARCODE_LABEL_FONT_BOLD_PATH", None),
        os.path.join(settings.BASE_DIR, "static", "fonts", "DejaVuSans-Bold.ttf"),
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]


def _font_candidates_regular() -> List[str | None]:
    return [
        getattr(settings, "BARCODE_LABEL_FONT_PATH", None),
        os.path.join(settings.BASE_DIR, "static", "fonts", "DejaVuSans.ttf"),
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]


def _load_truetype(paths: List[str | None], size: int) -> ImageFont.ImageFont:
    for path in paths:
        if path and os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        pass
    return ImageFont.load_default()


def _break_long_word(
    draw: ImageDraw.ImageDraw, word: str, font: ImageFont.ImageFont, max_width: int
) -> List[str]:
    if not word:
        return []
    chunks: List[str] = []
    buf = ""
    for ch in word:
        trial = buf + ch
        if _get_text_size(draw, trial, font)[0] <= max_width:
            buf = trial
        else:
            if buf:
                chunks.append(buf)
            buf = ch
    if buf:
        chunks.append(buf)
    return chunks


def _wrap_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    max_lines: int,
) -> List[str]:
    text = (text or "").strip() or "—"
    words = text.split()
    if not words:
        return [text[:20]]

    lines: List[str] = []
    cur: List[str] = []

    def flush() -> None:
        nonlocal cur
        if cur:
            lines.append(" ".join(cur))
            cur = []

    for word in words:
        if len(lines) >= max_lines:
            break
        trial = " ".join(cur + [word]) if cur else word
        if _get_text_size(draw, trial, font)[0] <= max_width:
            cur.append(word)
            continue
        flush()
        if len(lines) >= max_lines:
            break
        if _get_text_size(draw, word, font)[0] <= max_width:
            cur = [word]
            continue
        for piece in _break_long_word(draw, word, font, max_width):
            if len(lines) >= max_lines:
                break
            if cur:
                t2 = " ".join(cur + [piece])
                if _get_text_size(draw, t2, font)[0] <= max_width:
                    cur.append(piece)
                else:
                    flush()
                    if len(lines) >= max_lines:
                        break
                    cur = [piece]
            else:
                cur = [piece]
        if len(lines) >= max_lines:
            break

    flush()
    lines = lines[:max_lines]

    if lines and len(lines) == max_lines:
        tail = " ".join(words)
        if " ".join(lines) != tail:
            last = lines[-1]
            ell = "…"
            while last and _get_text_size(draw, last + ell, font)[0] > max_width and len(last) > 1:
                last = last[:-1]
            lines[-1] = last + ell

    return lines if lines else [text[:8] + "…"]


def _format_price_display(item: "Item") -> str:
    """Whole currency amount with thousands separators (e.g. 1,000)."""
    try:
        p = item.unit_price
        if p is None:
            return "0"
        if hasattr(p, "quantize"):
            n = int(p)
        else:
            n = int(float(p))
        return f"{n:,}"
    except (TypeError, ValueError):
        return "0"


def _tight_crop_barcode_raster(im: Image.Image, white_threshold: int = 250) -> Image.Image:
    """Remove excess quiet-zone white from python-barcode PNG so width-first scaling uses real bar width."""
    g = im.convert("L")
    mask = g.point(lambda p: 0 if p > white_threshold else 255)
    bbox = mask.getbbox()
    if not bbox:
        return im
    x0, y0, x1, y1 = bbox
    pad = 1
    return im.crop(
        (
            max(0, x0 - pad),
            max(0, y0 - pad),
            min(im.width, x1 + pad),
            min(im.height, y1 + pad),
        )
    )


def _shrink_font_to_fit(
    draw: ImageDraw.ImageDraw,
    text: str,
    paths: List[str | None],
    start_size: int,
    min_size: int,
    max_width: int,
) -> Tuple[ImageFont.ImageFont, int]:
    for sz in range(start_size, min_size - 1, -1):
        font = _load_truetype(paths, sz)
        if _get_text_size(draw, text, font)[0] <= max_width:
            return font, sz
    font = _load_truetype(paths, min_size)
    return font, min_size


def _code128_bars_resized(
    code: str,
    barcode_max_w_px: int,
    barcode_max_h_px: int,
) -> Tuple[Image.Image, int, int]:
    """
    Render Code128 and scale width-first to barcode_max_w_px (full width, short bars).
    If proportional height exceeds barcode_max_h_px, re-render with lower module_height,
    then slightly reduce target width only as a last resort (avoids min(w,h) uniform shrink).
    """
    module_h = float(BARCODE_MODULE_HEIGHT_MM)
    module_w = float(BARCODE_WRITER_MODULE_WIDTH_MM)
    quiet = float(BARCODE_WRITER_QUIET_ZONE_MM)
    max_w = int(barcode_max_w_px)
    barcode_src: Image.Image | None = None
    bw = bh = 1

    for _ in range(24):
        with tempfile.TemporaryDirectory() as tmp:
            base_path = os.path.join(tmp, "bc")
            bc = Code128(code, writer=ImageWriter())
            # Barcode.render() merges default_writer_options and calls set_options — options passed
            # to save() must include module_* / quiet_zone or defaults (e.g. module_height=15mm) win.
            bc.save(
                base_path,
                options={
                    "dpi": LABEL_DPI,
                    "module_width": module_w,
                    "module_height": module_h,
                    "quiet_zone": quiet,
                    "margin_top": 0.35,
                    "margin_bottom": 0.35,
                    "background": "white",
                    "foreground": "black",
                    "write_text": False,
                },
            )
            png_path = f"{base_path}.png"
            if not os.path.isfile(png_path):
                raise FileNotFoundError("barcode writer did not produce png")
            with Image.open(png_path) as im:
                barcode_src = _tight_crop_barcode_raster(im.convert("RGB").copy())

        assert barcode_src is not None
        bw, bh = barcode_src.size
        if bw < 1 or bh < 1:
            raise ValueError("invalid barcode raster")
        scale_w = max_w / bw
        new_w = max_w
        new_h = max(1, int(round(bh * scale_w)))
        if new_h <= barcode_max_h_px:
            bar = barcode_src.resize((new_w, new_h), Image.Resampling.NEAREST)
            return bar, new_w, new_h
        if module_h > BARCODE_MODULE_HEIGHT_FLOOR_MM + 0.02:
            module_h = max(BARCODE_MODULE_HEIGHT_FLOOR_MM, module_h * 0.91)
            module_w = min(0.34, module_w * 1.025)
            continue
        if max_w > max(48, int(barcode_max_w_px * 0.88)):
            max_w = int(max_w * 0.98)
            continue
        new_h = min(new_h, barcode_max_h_px)
        new_w = max(1, int(round(bw * (new_h / bh))))
        bar = barcode_src.resize((new_w, new_h), Image.Resampling.NEAREST)
        return bar, new_w, new_h

    assert barcode_src is not None
    new_w = max_w
    new_h = max(1, min(int(round(bh * (new_w / bw))), barcode_max_h_px))
    new_w = max(1, int(round(bw * (new_h / bh))))
    bar = barcode_src.resize((new_w, new_h), Image.Resampling.NEAREST)
    return bar, new_w, new_h


def build_label_png_bytes(item: "Item") -> bytes:
    """
    Raster label: 50×30 mm at LABEL_DPI.
    Rule sits just under name/price. Code128 is width-first (full inner width, short bars).
    A single digit line under the bars (compact). Bar sits close under the rule (no mid-label gap).
    """
    code_raw = (item.bar_code_no or "").strip()
    if not code_raw:
        raise ValueError("empty bar_code_no")
    code = re.sub(r"\s+", "", code_raw)

    w_px = _mm_to_px(LABEL_WIDTH_MM, LABEL_DPI)
    h_px = _mm_to_px(LABEL_HEIGHT_MM, LABEL_DPI)
    # Tight margins — less empty band at edges
    margin = max(_mm_to_px(0.5, LABEL_DPI), int(min(w_px, h_px) * 0.016))
    line_thick = max(_mm_to_px(0.4, LABEL_DPI), 3)

    img = Image.new("RGB", (w_px, h_px), "white")
    draw = ImageDraw.Draw(img)

    inner_w = w_px - 2 * margin
    # Wider name column; compact price stays top-right
    split = int(inner_w * 0.74)
    name_max_w = max(52, split - 6)

    # Header block sits lower on the sheet (uses top margin) to tighten space above the barcode
    header_y0 = margin + max(_mm_to_px(1.0, LABEL_DPI), int(h_px * 0.05))
    header_budget = int(h_px * 0.63)
    # Product name: favor readable size from height and from column width
    name_from_h = int(header_budget / 2.2)
    name_from_w = int(name_max_w / 9)
    name_font_size = max(
        BARCODE_NAME_FONT_MIN,
        min(BARCODE_NAME_FONT_MAX, max(name_from_h, name_from_w)),
    )
    price_big = max(18, min(42, int(header_budget * 0.54)))
    currency_size = max(12, min(20, int(price_big * 0.46)))

    font_name = _load_truetype(_font_candidates_bold(), name_font_size)
    font_currency = _load_truetype(_font_candidates_bold(), currency_size)
    font_price = _load_truetype(_font_candidates_bold(), price_big)

    product = (item.item_name or item.no or "").strip() or code_raw
    name_lines = _wrap_lines(draw, product, font_name, name_max_w, max_lines=4)
    line_height = _get_text_size(draw, "Ag", font_name)[1]
    line_gap = 3
    ny = header_y0
    name_bottom = header_y0
    for nl in name_lines:
        draw.text((margin, ny), nl, font=font_name, fill="black")
        _, th = _get_text_size(draw, nl, font_name)
        name_bottom = max(name_bottom, ny + th)
        ny += line_height + line_gap

    currency = LABEL_CURRENCY
    price_str = _format_price_display(item)
    cur_w, cur_h = _get_text_size(draw, currency, font_currency)
    pr_w, pr_h = _get_text_size(draw, price_str, font_price)
    block_w = max(cur_w, pr_w)
    right_x = w_px - margin - block_w
    draw.text((right_x + (block_w - cur_w), header_y0), currency, font=font_currency, fill="black")
    draw.text((right_x + (block_w - pr_w), header_y0 + cur_h + 2), price_str, font=font_price, fill="black")
    price_bottom = header_y0 + cur_h + 2 + pr_h

    content_bottom = max(name_bottom, price_bottom)
    pad_below_header = max(4, _mm_to_px(0.5, LABEL_DPI))
    line_y0 = content_bottom + pad_below_header
    # Leave room for barcode block biased toward lower label (see push-down after layout)
    min_bottom = int(h_px * 0.14)
    line_y0 = min(line_y0, h_px - margin - line_thick - min_bottom)
    line_y0 = max(line_y0, header_y0 + cur_h)
    line_y1 = line_y0 + line_thick
    barcode_zone_top = line_y1 + max(2, margin // 6)
    barcode_zone_bottom = h_px - max(2, margin // 2)

    draw.rectangle([margin, line_y0, w_px - margin, line_y1], fill="black")

    zone_h = barcode_zone_bottom - barcode_zone_top
    # Under-bar text (digits): allow a larger font by default.
    # Still guarded by fit-to-width and the y-clamp checks below.
    code_line_start = max(13, min(30, int(zone_h * 0.33)))

    font_code, _ = _shrink_font_to_fit(
        draw, code, _font_candidates_regular(), code_line_start, 6, inner_w
    )
    _, hh_code = _get_text_size(draw, code, font_code)

    # Tighten spacing so the digits can grow.
    gap_bar_text = max(2, margin // 7)
    bottom_pad = max(1, margin // 8)

    top_pad = max(1, margin // 8)
    stack_below_rule = gap_bar_text + hh_code + bottom_pad + top_pad
    avail_bar_px = max(8, zone_h - stack_below_rule - 2)
    mm_bar_px = max(8, _mm_to_px(BARCODE_BAR_MAX_HEIGHT_MM, LABEL_DPI))
    # Do not use zone_h * BARCODE_BAR_ZONE_HEIGHT_FRAC here: at low fractions it caps height below
    # what width-first scaling needs and forces narrow bars (uniform height cap fights aspect ratio).
    barcode_max_h = min(avail_bar_px, mm_bar_px)
    barcode_max_w = max(40, min(int(inner_w * BARCODE_WIDTH_FRAC), inner_w - 2))

    barcode_r, new_w, new_h = _code128_bars_resized(code, barcode_max_w, barcode_max_h)

    by = barcode_zone_top + top_pad
    y_code = by + new_h + gap_bar_text
    if y_code + hh_code + bottom_pad > barcode_zone_bottom:
        over = (y_code + hh_code + bottom_pad) - barcode_zone_bottom
        tighter = max(4, new_h - over - 2)
        barcode_r, new_w, new_h = _code128_bars_resized(code, barcode_max_w, tighter)
        by = barcode_zone_top + top_pad
        y_code = by + new_h + gap_bar_text

    slack_below = barcode_zone_bottom - bottom_pad - (y_code + hh_code)
    if slack_below > 6:
        cap_try = min(32, code_line_start + 10)
        for sz_try in range(cap_try, code_line_start, -1):
            font_try, _ = _shrink_font_to_fit(
                draw, code, _font_candidates_regular(), sz_try, 6, inner_w
            )
            _, hh_t = _get_text_size(draw, code, font_try)
            y_t = by + new_h + gap_bar_text
            if y_t + hh_t + bottom_pad <= barcode_zone_bottom:
                font_code, hh_code = font_try, hh_t
                y_code = y_t
                break

    bx = (w_px - new_w) // 2
    img.paste(barcode_r, (bx, by))

    cw, _ = _get_text_size(draw, code, font_code)
    draw.text(((w_px - cw) // 2, y_code), code, font=font_code, fill="black")

    buf = BytesIO()
    img.save(buf, format="PNG", dpi=(LABEL_DPI, LABEL_DPI))
    return buf.getvalue()


def build_barcode_labels_pdf_bytes(items: List["Item"]) -> Tuple[bytes, str]:
    """One PDF page per item at 50×30 mm; raster uses width-first Code128 (see build_label_png_bytes)."""
    page_w = LABEL_WIDTH_MM * mm
    page_h = LABEL_HEIGHT_MM * mm

    pdf_buf = BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=(page_w, page_h))

    drawn = 0
    for item in items[:MAX_LABELS]:
        code = (item.bar_code_no or "").strip()
        if not code:
            continue
        try:
            png_bytes = build_label_png_bytes(item)
        except Exception as ex:
            logger.warning("Barcode label skip item id=%s: %s", getattr(item, "pk", None), ex)
            continue

        img_reader = ImageReader(BytesIO(png_bytes))
        c.drawImage(img_reader, 0, 0, width=page_w, height=page_h, preserveAspectRatio=True, anchor="sw")
        c.showPage()
        drawn += 1

    if drawn == 0:
        raise ValueError(
            "No barcode labels could be generated. "
            "Ensure selected items have a non-empty Bar Code No. "
            "and that codes are valid for Code128."
        )

    c.save()
    pdf_buf.seek(0)
    fname = f"item_barcode_labels_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return pdf_buf.read(), fname

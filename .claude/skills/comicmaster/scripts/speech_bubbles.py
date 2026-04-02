"""
speech_bubbles.py — Comic speech bubble renderer for ComicMaster.

Pure Python + Pillow. No ComfyUI dependency.
Importable as a module or runnable standalone for testing.

Bubble types: speech, thought, shout, whisper, narration, caption,
              explosion, electric, connected, scream, sfx.

=== Lettering Standards (Blambot / Industry) ===
- ALL CAPS for Western dialogue (auto-applied)
- Double-dash (--) for interrupted speech, NOT em-dash
- Exactly 3 dots for ellipsis (...)
- Bold/italic for emphasis
- Crossbar "I" only for pronoun "I" and acronyms (requires specialised
  comic fonts with OpenType alternates — documented but not enforced
  with standard Google Fonts)
- Balloon tails: curved Bézier, pointing toward character mouth
- Text is NEVER truncated — balloon resizes to fit

=== SFX Enhancements ===
- Perspective-matched SFX: flat, radial, curved, impact styles
- Art-integrated rendering: semi-transparency, drop shadows, color matching
- Partial occlusion simulation
- Size scaling based on narrative_weight
"""

from __future__ import annotations

import logging
import math
import os
import re
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent
_FONT_DIR = _HERE.parent / "assets" / "fonts"

POSITION_HINTS = {
    "top_left":      (0.30, 0.12),
    "top_center":    (0.50, 0.12),
    "top_right":     (0.70, 0.12),
    "middle_left":   (0.18, 0.45),
    "middle_center": (0.50, 0.45),
    "middle_right":  (0.82, 0.45),
    "bottom_left":   (0.30, 0.88),
    "bottom_center": (0.50, 0.88),
    "bottom_right":  (0.70, 0.88),
}

# ---------------------------------------------------------------------------
# Font registry
# ---------------------------------------------------------------------------

_FONTS = {
    # --- Core comic fonts ---
    "comic":          "ComicNeue-Regular.ttf",
    "comic_bold":     "ComicNeue-Bold.ttf",
    "bangers":        "Bangers-Regular.ttf",
    "patrick":        "PatrickHand-Regular.ttf",
    # --- Professional additions ---
    "permanent":      "PermanentMarker-Regular.ttf",    # SFX / impact
    "luckiest":       "LuckiestGuy-Regular.ttf",        # Shout / explosion
    "elite":          "SpecialElite-Regular.ttf",        # Caption / typewriter
    "caveat":         "Caveat-Regular.ttf",              # Handwriting / monologue
    "caveat_bold":    "Caveat-Bold.ttf",                 # Bold monologue
    "architect":      "ArchitectsDaughter-Regular.ttf",  # Comic dialogue alt
}

# Style → (bubble_type → font_key)
# Each style maps every bubble type to the best font for that role.
_STYLE_FONT_MAP: dict[str, dict[str, str]] = {
    "western": {
        "speech":    "comic",
        "thought":   "caveat",
        "shout":     "luckiest",
        "whisper":   "comic",
        "narration": "elite",
        "caption":   "elite",
        "explosion": "luckiest",
        "electric":  "comic_bold",
        "connected": "comic",
        "scream":    "bangers",
        "sfx":       "permanent",
    },
    "manga": {
        "speech":    "comic",
        "thought":   "caveat",
        "shout":     "comic_bold",
        "whisper":   "comic",
        "narration": "patrick",
        "caption":   "patrick",
        "explosion": "bangers",
        "electric":  "comic_bold",
        "connected": "comic",
        "scream":    "comic_bold",
        "sfx":       "permanent",
    },
    "cartoon": {
        "speech":    "architect",
        "thought":   "caveat",
        "shout":     "luckiest",
        "whisper":   "comic",
        "narration": "patrick",
        "caption":   "patrick",
        "explosion": "luckiest",
        "electric":  "comic_bold",
        "connected": "architect",
        "scream":    "bangers",
        "sfx":       "permanent",
    },
    "cyberpunk": {
        "speech":    "comic",
        "thought":   "caveat",
        "shout":     "bangers",
        "whisper":   "comic",
        "narration": "elite",
        "caption":   "elite",
        "explosion": "luckiest",
        "electric":  "comic_bold",
        "connected": "comic",
        "scream":    "bangers",
        "sfx":       "permanent",
    },
    "noir": {
        "speech":    "comic",
        "thought":   "caveat",
        "shout":     "comic_bold",
        "whisper":   "comic",
        "narration": "elite",
        "caption":   "elite",
        "explosion": "bangers",
        "electric":  "comic_bold",
        "connected": "comic",
        "scream":    "bangers",
        "sfx":       "permanent",
    },
}

# Auto font-size as fraction of panel height
_AUTO_FONT_RATIOS: dict[str, float] = {
    "speech":    0.030,
    "thought":   0.030,
    "shout":     0.038,
    "whisper":   0.025,
    "narration": 0.026,
    "caption":   0.026,
    "explosion": 0.042,
    "electric":  0.030,
    "connected": 0.030,
    "scream":    0.050,
    "sfx":       0.080,
}

# ---------------------------------------------------------------------------
# SFX perspective styles and auto-detection
# ---------------------------------------------------------------------------

# SFX perspective modes
SFX_PERSPECTIVES = {"flat", "radial", "curved", "impact"}

# Auto-detect SFX style based on text content
_SFX_STYLE_MAP: dict[str, str] = {
    # Explosions → radial or impact
    "BOOM": "impact",
    "CRASH": "radial",
    "BANG": "impact",
    "KABOOM": "impact",
    "BLAM": "radial",
    "KAPOW": "impact",
    # Movement → curved
    "WHOOSH": "curved",
    "SWOOSH": "curved",
    "WHIP": "curved",
    "ZOOM": "curved",
    "VROOM": "curved",
    "SWISH": "curved",
    # Sharp/quick → flat
    "CRACK": "flat",
    "SNAP": "flat",
    "CLICK": "flat",
    "CLACK": "flat",
    "POP": "flat",
    "THUD": "flat",
    "THWACK": "flat",
    # Energy → radial
    "ZAP": "radial",
    "BZZT": "radial",
    "ZZZZAP": "radial",
    "SIZZLE": "radial",
    "CRACKLE": "radial",
    # Other
    "SPLASH": "radial",
    "RUMBLE": "impact",
    "SCREECH": "curved",
    "ROAR": "impact",
    "SHATTER": "radial",
}

# SFX size multipliers based on narrative_weight
_SFX_WEIGHT_SCALE: dict[str, float] = {
    "low": 0.6,
    "medium": 1.0,
    "high": 1.5,
    "splash": 2.2,
}

# Complementary color mapping for SFX color-matching
_SFX_SCENE_COLORS: dict[str, str] = {
    # Scene mood_tone → SFX accent color
    "cool": "#FF6600",     # Orange SFX for cool/blue scenes (complementary)
    "warm": "#00BFFF",     # Cyan SFX for warm scenes
    "neutral": "#CC0000",  # Classic red
    "neon": "#00FFFF",     # Cyan/neon for tech scenes
    "dark": "#FFD700",     # Gold for dark scenes
}

# Padding inside bubbles (fraction of font size) — minimum 15% of bubble
_PAD_X_RATIO = 1.2
_PAD_Y_RATIO = 0.8

# Border widths
_BORDER_WIDTH = 3
_DASH_LEN = 10
_DASH_GAP = 7

# Text truncation is NEVER allowed — these are the adaptive sizing limits
_MIN_FONT_SCALE = 0.60   # font can shrink to 60% of original
_MAX_BUBBLE_H_RATIO = 0.50  # bubble can grow up to 50% of panel height
_PADDING_MIN_RATIO = 0.15   # minimum 15% padding around text

# Genre-specific caption styling
_CAPTION_STYLES: dict[str, dict] = {
    "default": {
        "bg_color": "#FFFDE7",
        "border_color": "black",
        "text_color": "black",
        "border_width": 2,
    },
    "cyberpunk": {
        "bg_color": "#1A1A2E",
        "border_color": "#00FFFF",
        "text_color": "#00FFFF",
        "border_width": 2,
    },
    "noir": {
        "bg_color": "#1C1C1C",
        "border_color": "#C0C0C0",
        "text_color": "#E0E0E0",
        "border_width": 1,
    },
    "manga": {
        "bg_color": "#FFFFFF",
        "border_color": "#333333",
        "text_color": "#333333",
        "border_width": 2,
    },
    "cartoon": {
        "bg_color": "#FFF8DC",
        "border_color": "#8B4513",
        "text_color": "#8B4513",
        "border_width": 2,
    },
    "western": {
        "bg_color": "#FFFDE7",
        "border_color": "black",
        "text_color": "black",
        "border_width": 2,
    },
}

# ---------------------------------------------------------------------------
# Comic lettering grammar normalisation
# ---------------------------------------------------------------------------

def _normalise_comic_text(text: str, bubble_type: str) -> str:
    """Apply comic lettering grammar rules to text.

    Rules (per Blambot / industry standards):
    - ALL CAPS for Western-style dialogue (speech, shout, scream, connected)
    - Double-dash (--) replaces em-dash (—, –)
    - Exactly 3 dots for ellipsis (… → ..., .... → ...)
    - Normalise quotation marks
    """
    # Em-dash / en-dash → double-dash
    text = text.replace("—", "--").replace("–", "--")

    # Unicode ellipsis → three dots
    text = text.replace("…", "...")

    # Normalise multiple dots to exactly 3
    text = re.sub(r"\.{4,}", "...", text)

    # Smart quotes → straight quotes
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201C", '"').replace("\u201D", '"')

    # ALL CAPS for dialogue-type bubbles (Western convention)
    if bubble_type in ("speech", "shout", "scream", "connected", "explosion", "electric"):
        text = text.upper()

    return text


# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

_font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def _load_font(key: str, size: int) -> ImageFont.FreeTypeFont:
    """Load a font by key and size, with caching and fallback."""
    cache_key = (key, size)
    if cache_key in _font_cache:
        return _font_cache[cache_key]

    font_file = _FONTS.get(key, _FONTS["comic"])
    font_path = _FONT_DIR / font_file

    font: ImageFont.FreeTypeFont | ImageFont.ImageFont
    try:
        if font_path.exists() and font_path.stat().st_size > 100:
            font = ImageFont.truetype(str(font_path), size)
        else:
            raise OSError(f"Font file missing or empty: {font_path}")
    except (OSError, IOError):
        # Fallback: try each registered font until one works
        for fallback_key, fallback_file in _FONTS.items():
            if fallback_key == key:
                continue
            fallback_path = _FONT_DIR / fallback_file
            try:
                if fallback_path.exists() and fallback_path.stat().st_size > 100:
                    font = ImageFont.truetype(str(fallback_path), size)
                    logger.warning("Font '%s' unavailable, fell back to '%s'", key, fallback_key)
                    break
            except (OSError, IOError):
                continue
        else:
            # Last resort: Pillow default
            font = ImageFont.load_default()
            logger.warning("All fonts unavailable, using Pillow default")

    _font_cache[cache_key] = font
    return font


def _get_font_for_bubble(bubble_type: str, style: str, size: int) -> ImageFont.FreeTypeFont:
    """Get the appropriate font for a bubble type within a style."""
    style_map = _STYLE_FONT_MAP.get(style, _STYLE_FONT_MAP["western"])
    key = style_map.get(bubble_type, "comic")
    return _load_font(key, size)


# ---------------------------------------------------------------------------
# Text measurement & wrapping
# ---------------------------------------------------------------------------

def _measure_text(text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    """Return (width, height) of rendered text."""
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Word-wrap *text* so each line fits within *max_width* pixels.

    Never truncates — if a single word exceeds max_width, it gets its own line.
    """
    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current: list[str] = []

    for word in words:
        candidate = " ".join(current + [word])
        w, _ = _measure_text(candidate, font)
        if w <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]

    if current:
        lines.append(" ".join(current))

    return lines if lines else [""]


def _text_block_size(
    lines: list[str], font: ImageFont.FreeTypeFont, line_spacing: float = 1.3
) -> tuple[int, int]:
    """Return (width, height) of a multi-line text block."""
    if not lines:
        return 0, 0
    max_w = 0
    _, single_h = _measure_text("Ay", font)
    for ln in lines:
        w, _ = _measure_text(ln, font)
        max_w = max(max_w, w)
    total_h = int(single_h * line_spacing * len(lines))
    return max_w, total_h


def _draw_text_block(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    center_x: int,
    top_y: int,
    color: str = "black",
    line_spacing: float = 1.3,
) -> int:
    """Draw centred multi-line text. Returns total height drawn."""
    _, single_h = _measure_text("Ay", font)
    step = int(single_h * line_spacing)
    y = top_y
    for ln in lines:
        w, _ = _measure_text(ln, font)
        draw.text((center_x - w // 2, y), ln, fill=color, font=font)
        y += step
    return y - top_y


# ---------------------------------------------------------------------------
# TEXT-FIRST adaptive sizing
# ---------------------------------------------------------------------------

def _compute_text_first_layout(
    text: str,
    bubble_type: str,
    style: str,
    panel_w: int,
    panel_h: int,
    pos: tuple[float, float],
    base_font_size: int | None = None,
    max_width_ratio: float = 0.40,
) -> tuple[ImageFont.FreeTypeFont, list[str], int, int, int, int]:
    """TEXT-FIRST layout: measure text, then compute balloon size.

    Returns (font, lines, text_w, text_h, pad_x, pad_y).

    Strategy:
    1. Start with the ideal font size
    2. Wrap text at the desired max width
    3. If the resulting balloon exceeds panel limits:
       a. Shrink font (down to 60% of original)
       b. Then allow balloon to grow (up to _MAX_BUBBLE_H_RATIO)
    4. NEVER truncate text
    """
    # Determine base font size
    if base_font_size is None:
        ratio = _AUTO_FONT_RATIOS.get(bubble_type, 0.035)
        base_font_size = max(12, int(panel_h * ratio))

    # Calculate available space based on position
    pos_x, pos_y = pos
    safe_margin = 0.06
    space_left = pos_x - safe_margin
    space_right = (1.0 - pos_x) - safe_margin
    max_half = min(space_left, space_right)
    available_ratio = max_half * 2
    effective_ratio = min(max_width_ratio, max(0.22, available_ratio - 0.02))

    min_font_size = max(10, int(base_font_size * _MIN_FONT_SCALE))
    fsize = base_font_size

    best_font = None
    best_lines = None
    best_tw = best_th = best_pad_x = best_pad_y = 0

    # Phase 1: try shrinking the font
    for _ in range(8):
        font = _get_font_for_bubble(bubble_type, style, fsize)
        max_px = int(panel_w * effective_ratio)
        lines = _wrap_text(text, font, max_px)
        tw, th = _text_block_size(lines, font)

        pad_x = max(int(tw * _PADDING_MIN_RATIO), int(fsize * _PAD_X_RATIO))
        pad_y = max(int(th * _PADDING_MIN_RATIO), int(fsize * _PAD_Y_RATIO))

        total_h = th + pad_y * 2
        total_w = tw + pad_x * 2

        best_font = font
        best_lines = lines
        best_tw, best_th = tw, th
        best_pad_x, best_pad_y = pad_x, pad_y

        # Check if it fits within reasonable bounds
        if total_h <= panel_h * _MAX_BUBBLE_H_RATIO and total_w <= panel_w * 0.85:
            break

        if fsize <= min_font_size:
            break

        fsize = max(min_font_size, int(fsize * 0.85))

    return best_font, best_lines, best_tw, best_th, best_pad_x, best_pad_y


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

# Per-panel text deduplication tracker
_panel_text_seen: dict[str, set[str]] = {}


def _reset_dedup():
    """Reset the deduplication tracker (call before each add_bubbles invocation)."""
    _panel_text_seen.clear()


def _is_duplicate(panel_id: str, text: str) -> bool:
    """Check if this exact text has already been rendered on this panel.

    Returns True if duplicate (should be skipped).
    """
    key = text.strip().lower()
    if panel_id not in _panel_text_seen:
        _panel_text_seen[panel_id] = set()

    if key in _panel_text_seen[panel_id]:
        logger.warning(
            "DUPLICATE TEXT SKIPPED on panel '%s': \"%s\"",
            panel_id, text[:60]
        )
        return True

    _panel_text_seen[panel_id].add(key)
    return False


# ---------------------------------------------------------------------------
# Bubble geometry helpers
# ---------------------------------------------------------------------------

def _bubble_rect(
    cx: int, cy: int, tw: int, th: int, pad_x: int, pad_y: int
) -> tuple[int, int, int, int]:
    """Return (x0, y0, x1, y1) for a bubble centred at (cx, cy)."""
    half_w = tw // 2 + pad_x
    half_h = th // 2 + pad_y
    return cx - half_w, cy - half_h, cx + half_w, cy + half_h


def _clamp_rect(
    rect: tuple[int, int, int, int], img_w: int, img_h: int, margin: int = 12
) -> tuple[int, int, int, int]:
    """Shift rect so it stays fully within image bounds.

    The bubble is shifted (not shrunk) to fit. The text-first sizing
    guarantees the bubble is already small enough for the panel.
    """
    x0, y0, x1, y1 = rect
    rw, rh = x1 - x0, y1 - y0

    max_w = img_w - 2 * margin
    max_h = img_h - 2 * margin
    if rw > max_w:
        cx = (x0 + x1) // 2
        x0 = max(margin, cx - max_w // 2)
        x1 = x0 + max_w
        rw = max_w
    if rh > max_h:
        cy = (y0 + y1) // 2
        y0 = max(margin, cy - max_h // 2)
        y1 = y0 + max_h
        rh = max_h

    if x0 < margin:
        x0 = margin; x1 = x0 + rw
    if y0 < margin:
        y0 = margin; y1 = y0 + rh
    if x1 > img_w - margin:
        x1 = img_w - margin; x0 = max(margin, x1 - rw)
    if y1 > img_h - margin:
        y1 = img_h - margin; y0 = max(margin, y1 - rh)

    return x0, y0, x1, y1


# ---------------------------------------------------------------------------
# Tail / trail drawing — Bézier curves
# ---------------------------------------------------------------------------

def _bezier_point(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    t: float,
) -> tuple[float, float]:
    """Quadratic Bézier curve point at parameter t."""
    u = 1 - t
    x = u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0]
    y = u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]
    return x, y


def _draw_speech_tail(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    target: tuple[int, int],
    fill: str = "white",
    outline: str = "black",
    border_w: int = _BORDER_WIDTH,
):
    """Curved Bézier tail from bubble edge pointing toward target (mouth).

    Tail width is proportional to bubble size (not fixed).
    """
    x0, y0, x1, y1 = rect
    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2
    bubble_w = x1 - x0
    bubble_h = y1 - y0

    tx, ty = target

    # Determine which edge the tail attaches to (closest to target)
    # Check all four edges
    edges = {
        "bottom": ((cx, y1), abs(ty - y1) if ty > y1 else float("inf")),
        "top":    ((cx, y0), abs(ty - y0) if ty < y0 else float("inf")),
        "left":   ((x0, cy), abs(tx - x0) if tx < x0 else float("inf")),
        "right":  ((x1, cy), abs(tx - x1) if tx > x1 else float("inf")),
    }
    # Pick the edge closest to the target
    best_edge = min(edges.items(), key=lambda e: e[1][1])
    edge_name = best_edge[0]

    # Tail base width proportional to bubble size (5-15% of shorter side)
    base_size = max(8, min(bubble_w, bubble_h) // 8)

    # Tail base offset toward target horizontally/vertically
    if edge_name in ("bottom", "top"):
        base_cx = max(x0 + base_size + 4, min(x1 - base_size - 4, cx + (tx - cx) // 3))
        if edge_name == "bottom":
            base_y = y1 - 2
            base_left = (base_cx - base_size, base_y)
            base_right = (base_cx + base_size, base_y)
        else:
            base_y = y0 + 2
            base_left = (base_cx - base_size, base_y)
            base_right = (base_cx + base_size, base_y)
    else:
        base_cy = max(y0 + base_size + 4, min(y1 - base_size - 4, cy + (ty - cy) // 3))
        if edge_name == "right":
            base_x = x1 - 2
            base_left = (base_x, base_cy - base_size)
            base_right = (base_x, base_cy + base_size)
        else:
            base_x = x0 + 2
            base_left = (base_x, base_cy - base_size)
            base_right = (base_x, base_cy + base_size)

    # Limit tail length to ~45% of bubble height
    max_tail_len = int(max(bubble_h, bubble_w) * 0.45)
    base_mid = ((base_left[0] + base_right[0]) / 2, (base_left[1] + base_right[1]) / 2)
    dx = tx - base_mid[0]
    dy = ty - base_mid[1]
    dist = max(1, (dx**2 + dy**2) ** 0.5)
    if dist > max_tail_len:
        scale = max_tail_len / dist
        tip_x = int(base_mid[0] + dx * scale)
        tip_y = int(base_mid[1] + dy * scale)
    else:
        tip_x, tip_y = tx, ty
    tip = (tip_x, tip_y)

    # Control point for Bézier curve — offset perpendicular to tail direction
    mid_x = (base_mid[0] + tip[0]) / 2
    mid_y = (base_mid[1] + tip[1]) / 2
    # Perpendicular offset for curvature
    perp_x = -(tip[1] - base_mid[1]) * 0.15
    perp_y = (tip[0] - base_mid[0]) * 0.15
    ctrl_left = (mid_x + perp_x, mid_y + perp_y)
    ctrl_right = (mid_x - perp_x, mid_y - perp_y)

    # Generate curved polygon points via Bézier
    n_steps = 12
    left_curve = []
    right_curve = []
    for i in range(n_steps + 1):
        t = i / n_steps
        lp = _bezier_point(base_left, ctrl_left, tip, t)
        rp = _bezier_point(base_right, ctrl_right, tip, t)
        left_curve.append((int(lp[0]), int(lp[1])))
        right_curve.append((int(rp[0]), int(rp[1])))

    # Build polygon: left curve forward + right curve backward
    polygon = left_curve + list(reversed(right_curve))

    # Draw filled polygon then outline edges
    draw.polygon(polygon, fill=fill)
    # Outline the two curved edges
    for i in range(len(left_curve) - 1):
        draw.line([left_curve[i], left_curve[i + 1]], fill=outline, width=border_w)
    for i in range(len(right_curve) - 1):
        draw.line([right_curve[i], right_curve[i + 1]], fill=outline, width=border_w)

    # Cover the base with fill so border doesn't show inside bubble
    draw.line([base_left, base_right], fill=fill, width=border_w + 4)


def _draw_thought_trail(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    target: tuple[int, int],
    fill: str = "white",
    outline: str = "black",
    border_w: int = _BORDER_WIDTH,
):
    """Three diminishing circles trailing from bubble toward target."""
    x0, y0, x1, y1 = rect
    bubble_h = y1 - y0
    bx = (x0 + x1) // 2
    by = y1
    tx, ty = target

    # Limit trail length to ~45% of bubble height
    max_trail = int(bubble_h * 0.45)
    dx = tx - bx
    dy = ty - by
    dist = max(1, (dx**2 + dy**2) ** 0.5)
    if dist > max_trail:
        scale = max_trail / dist
        tx = int(bx + dx * scale)
        ty = int(by + dy * scale)

    steps = 4
    for i in range(1, steps):
        t = i / steps
        cx = int(bx + (tx - bx) * t)
        cy = int(by + (ty - by) * t)
        r = max(3, int(12 - 3 * i))
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=fill, outline=outline, width=border_w
        )


# ---------------------------------------------------------------------------
# Individual bubble renderers
# ---------------------------------------------------------------------------

def _render_speech(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    bubble: dict,
    font: ImageFont.FreeTypeFont,
    lines: list[str],
    tw: int, th: int, pad_x: int, pad_y: int,
):
    """Standard rounded-rect bubble with curved Bézier tail."""
    w, h = img.size
    cx = int(bubble["position"][0] * w)
    cy = int(bubble["position"][1] * h)

    rect = _bubble_rect(cx, cy, tw, th, pad_x, pad_y)
    rect = _clamp_rect(rect, w, h)

    radius = min(20, (rect[2] - rect[0]) // 4)
    fill = bubble.get("color", "white")
    border = bubble.get("border_color", "black")
    text_color = bubble.get("text_color", "black")

    # Tail first (behind bubble)
    tail_target = bubble.get("tail_target")
    if tail_target is not None:
        tx = int(tail_target[0] * w)
        ty = int(tail_target[1] * h)
        _draw_speech_tail(draw, rect, (tx, ty), fill=fill, outline=border)

    # Bubble body
    draw.rounded_rectangle(rect, radius=radius, fill=fill, outline=border, width=_BORDER_WIDTH)

    # Text — centred inside the clamped rect
    rcx = (rect[0] + rect[2]) // 2
    text_top = (rect[1] + rect[3]) // 2 - th // 2
    _draw_text_block(draw, lines, font, rcx, text_top, color=text_color)


def _render_thought(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    bubble: dict,
    font: ImageFont.FreeTypeFont,
    lines: list[str],
    tw: int, th: int, pad_x: int, pad_y: int,
):
    """Cloud-shaped bubble with small circle trail."""
    w, h = img.size
    # Extra padding for cloud bumps
    pad_x += 10
    pad_y += 10
    cx = int(bubble["position"][0] * w)
    cy = int(bubble["position"][1] * h)

    rect = _bubble_rect(cx, cy, tw, th, pad_x, pad_y)
    rect = _clamp_rect(rect, w, h)

    fill = bubble.get("color", "white")
    border = bubble.get("border_color", "black")
    text_color = bubble.get("text_color", "black")

    x0, y0, x1, y1 = rect
    rw = x1 - x0
    rh = y1 - y0

    # Cloud bumps: overlapping ellipses around perimeter
    bump_r_x = max(12, rw // 6)
    bump_r_y = max(12, rh // 5)
    bumps = []
    nx = max(3, rw // bump_r_x)
    for i in range(nx + 1):
        bx = x0 + int(i * rw / nx)
        bumps.append((bx - bump_r_x, y0 - bump_r_y // 2, bx + bump_r_x, y0 + bump_r_y))
    for i in range(nx + 1):
        bx = x0 + int(i * rw / nx)
        bumps.append((bx - bump_r_x, y1 - bump_r_y, bx + bump_r_x, y1 + bump_r_y // 2))
    ny = max(2, rh // bump_r_y)
    for i in range(1, ny):
        by = y0 + int(i * rh / ny)
        bumps.append((x0 - bump_r_x // 2, by - bump_r_y, x0 + bump_r_x, by + bump_r_y))
    for i in range(1, ny):
        by = y0 + int(i * rh / ny)
        bumps.append((x1 - bump_r_x, by - bump_r_y, x1 + bump_r_x // 2, by + bump_r_y))

    # Fill pass
    draw.rectangle(rect, fill=fill)
    for b in bumps:
        draw.ellipse(b, fill=fill)
    # Outline pass
    for b in bumps:
        draw.ellipse(b, outline=border, width=_BORDER_WIDTH)
    # Re-fill interior to cover internal outlines
    inset = _BORDER_WIDTH + 2
    draw.rectangle((x0 + inset, y0 + inset, x1 - inset, y1 - inset), fill=fill)

    # Thought trail
    tail_target = bubble.get("tail_target")
    if tail_target is not None:
        tx = int(tail_target[0] * w)
        ty = int(tail_target[1] * h)
        _draw_thought_trail(draw, rect, (tx, ty), fill=fill, outline=border)

    # Text
    rcx = (rect[0] + rect[2]) // 2
    text_top = (rect[1] + rect[3]) // 2 - th // 2
    _draw_text_block(draw, lines, font, rcx, text_top, color=text_color)


def _render_shout(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    bubble: dict,
    font: ImageFont.FreeTypeFont,
    lines: list[str],
    tw: int, th: int, pad_x: int, pad_y: int,
):
    """Spiky/jagged polygon border."""
    w, h = img.size
    pad_x += 8
    pad_y += 8
    cx = int(bubble["position"][0] * w)
    cy = int(bubble["position"][1] * h)

    rect = _bubble_rect(cx, cy, tw, th, pad_x, pad_y)
    rect = _clamp_rect(rect, w, h)

    fill = bubble.get("color", "white")
    border = bubble.get("border_color", "black")
    text_color = bubble.get("text_color", "black")

    x0, y0, x1, y1 = rect
    rcx_val = (x0 + x1) / 2
    rcy_val = (y0 + y1) / 2
    rx = (x1 - x0) / 2
    ry = (y1 - y0) / 2

    n_spikes = 16
    points = []
    for i in range(n_spikes):
        angle = 2 * math.pi * i / n_spikes
        r_factor = 1.18 if i % 2 == 0 else 0.88
        px = rcx_val + rx * r_factor * math.cos(angle)
        py = rcy_val + ry * r_factor * math.sin(angle)
        points.append((int(px), int(py)))

    draw.polygon(points, fill=fill, outline=border, width=_BORDER_WIDTH)

    # Tail
    tail_target = bubble.get("tail_target")
    if tail_target is not None:
        tx = int(tail_target[0] * w)
        ty = int(tail_target[1] * h)
        _draw_speech_tail(draw, rect, (tx, ty), fill=fill, outline=border)

    # Text
    text_top = int(rcy_val) - th // 2
    _draw_text_block(draw, lines, font, int(rcx_val), text_top, color=text_color)


def _render_whisper(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    bubble: dict,
    font: ImageFont.FreeTypeFont,
    lines: list[str],
    tw: int, th: int, pad_x: int, pad_y: int,
):
    """Dashed-outline rounded rect, smaller text."""
    w, h = img.size
    cx = int(bubble["position"][0] * w)
    cy = int(bubble["position"][1] * h)

    rect = _bubble_rect(cx, cy, tw, th, pad_x, pad_y)
    rect = _clamp_rect(rect, w, h)

    fill = bubble.get("color", "white")
    border = bubble.get("border_color", "black")
    text_color = bubble.get("text_color", "#444444")

    x0, y0, x1, y1 = rect
    radius = min(16, (x1 - x0) // 5)

    # Fill
    draw.rounded_rectangle(rect, radius=radius, fill=fill)
    # Dashed outline
    _draw_dashed_rounded_rect(draw, rect, radius, border, _BORDER_WIDTH, _DASH_LEN, _DASH_GAP)

    # Tail
    tail_target = bubble.get("tail_target")
    if tail_target is not None:
        tx = int(tail_target[0] * w)
        ty = int(tail_target[1] * h)
        _draw_speech_tail(draw, rect, (tx, ty), fill=fill, outline=border, border_w=2)

    # Text
    rcx = (x0 + x1) // 2
    text_top = (y0 + y1) // 2 - th // 2
    _draw_text_block(draw, lines, font, rcx, text_top, color=text_color)


def _draw_dashed_rounded_rect(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    radius: int,
    color: str,
    width: int,
    dash: int,
    gap: int,
):
    """Draw a dashed rounded rectangle."""
    x0, y0, x1, y1 = rect
    r = radius

    segments: list[tuple[float, float]] = []

    for a in range(90, 181, 5):
        rad = math.radians(a)
        segments.append((x0 + r + r * math.cos(rad), y0 + r + r * math.sin(rad)))
    segments.append((x0, y1 - r))
    for a in range(180, 271, 5):
        rad = math.radians(a)
        segments.append((x0 + r + r * math.cos(rad), y1 - r + r * math.sin(rad)))
    segments.append((x1 - r, y1))
    for a in range(270, 361, 5):
        rad = math.radians(a)
        segments.append((x1 - r + r * math.cos(rad), y1 - r + r * math.sin(rad)))
    segments.append((x1, y0 + r))
    for a in range(0, 91, 5):
        rad = math.radians(a)
        segments.append((x1 - r + r * math.cos(rad), y0 + r + r * math.sin(rad)))
    segments.append((x0 + r, y0))

    accumulated = 0.0
    drawing = True
    for i in range(len(segments) - 1):
        sx, sy = segments[i]
        ex, ey = segments[i + 1]
        seg_len = math.hypot(ex - sx, ey - sy)
        if seg_len < 0.5:
            continue

        pos = 0.0
        while pos < seg_len:
            threshold = dash if drawing else gap
            remaining = threshold - accumulated
            chunk = min(remaining, seg_len - pos)
            t_start = pos / seg_len
            t_end = (pos + chunk) / seg_len
            if drawing:
                lx0 = sx + (ex - sx) * t_start
                ly0 = sy + (ey - sy) * t_start
                lx1 = sx + (ex - sx) * t_end
                ly1 = sy + (ey - sy) * t_end
                draw.line([(lx0, ly0), (lx1, ly1)], fill=color, width=width)
            accumulated += chunk
            pos += chunk
            if accumulated >= threshold:
                accumulated = 0.0
                drawing = not drawing


def _render_narration(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    bubble: dict,
    font: ImageFont.FreeTypeFont,
    lines: list[str],
    tw: int, th: int, pad_x: int, pad_y: int,
    style: str = "western",
):
    """Rectangular narration box with genre-specific styling. NO tail."""
    w, h = img.size
    cx = int(bubble["position"][0] * w)
    cy = int(bubble["position"][1] * h)

    rect = _bubble_rect(cx, cy, tw, th, pad_x, pad_y)
    rect = _clamp_rect(rect, w, h)

    # Genre-specific styling
    caption_style = _CAPTION_STYLES.get(style, _CAPTION_STYLES["default"])
    fill = bubble.get("color", caption_style["bg_color"])
    border = bubble.get("border_color", caption_style["border_color"])
    text_color = bubble.get("text_color", caption_style["text_color"])
    border_w = caption_style["border_width"]

    draw.rectangle(rect, fill=fill, outline=border, width=border_w)

    rcx = (rect[0] + rect[2]) // 2
    text_top = (rect[1] + rect[3]) // 2 - th // 2
    _draw_text_block(draw, lines, font, rcx, text_top, color=text_color)


def _render_caption(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    bubble: dict,
    font: ImageFont.FreeTypeFont,
    lines: list[str],
    tw: int, th: int, pad_x: int, pad_y: int,
    style: str = "western",
):
    """Top/bottom strip with semi-transparent background.

    Supports genre-specific caption styling.
    """
    w, h = img.size
    pad_y_cap = int(font.size * 0.6)
    strip_h = th + pad_y_cap * 2

    norm_y = bubble["position"][1]
    strip_y0 = 0 if norm_y < 0.5 else h - strip_h
    strip_y1 = strip_y0 + strip_h

    # Genre-specific caption overlay colour
    caption_style = _CAPTION_STYLES.get(style, _CAPTION_STYLES["default"])
    text_color = bubble.get("text_color", caption_style["text_color"])

    # Parse bg color for overlay
    bg = caption_style["bg_color"]
    try:
        from PIL import ImageColor
        r_c, g_c, b_c = ImageColor.getrgb(bg)
        overlay_color = (r_c, g_c, b_c, 190)
    except Exception:
        overlay_color = (0, 0, 0, 160)

    overlay = Image.new("RGBA", (w, strip_h), overlay_color)

    if img.mode == "RGBA":
        img.paste(
            Image.alpha_composite(
                img.crop((0, strip_y0, w, strip_y1)).convert("RGBA"), overlay
            ),
            (0, strip_y0),
        )
    else:
        temp = img.crop((0, strip_y0, w, strip_y1)).convert("RGBA")
        composited = Image.alpha_composite(temp, overlay)
        img.paste(composited.convert("RGB"), (0, strip_y0))

    draw_new = ImageDraw.Draw(img)
    text_top = strip_y0 + pad_y_cap
    _draw_text_block(draw_new, lines, font, w // 2, text_top, color=text_color)

    return draw_new


def _render_explosion(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    bubble: dict,
    font: ImageFont.FreeTypeFont,
    lines: list[str],
    tw: int, th: int, pad_x: int, pad_y: int,
):
    """Starburst SFX bubble — sharp spikes, yellow fill, red outline, NO tail."""
    w, h = img.size
    pad_x += 14
    pad_y += 14
    cx = int(bubble["position"][0] * w)
    cy = int(bubble["position"][1] * h)

    rect = _bubble_rect(cx, cy, tw, th, pad_x, pad_y)
    rect = _clamp_rect(rect, w, h)

    fill = bubble.get("color", "#FFE44D")
    border = bubble.get("border_color", "#CC0000")
    text_color = bubble.get("text_color", "#CC0000")

    x0, y0, x1, y1 = rect
    rcx_val = (x0 + x1) / 2
    rcy_val = (y0 + y1) / 2
    rx = (x1 - x0) / 2
    ry = (y1 - y0) / 2

    n_spikes = 24
    points = []
    for i in range(n_spikes):
        angle = 2 * math.pi * i / n_spikes
        r_factor = 1.35 if i % 2 == 0 else 0.72
        px = rcx_val + rx * r_factor * math.cos(angle)
        py = rcy_val + ry * r_factor * math.sin(angle)
        points.append((int(px), int(py)))

    draw.polygon(points, fill=fill, outline=border, width=_BORDER_WIDTH)

    text_top = int(rcy_val) - th // 2
    _draw_text_block(draw, lines, font, int(rcx_val), text_top, color=text_color)


def _render_electric(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    bubble: dict,
    font: ImageFont.FreeTypeFont,
    lines: list[str],
    tw: int, th: int, pad_x: int, pad_y: int,
):
    """Zigzag-edge rectangular bubble — robot/electronic speech."""
    w, h = img.size
    pad_x += 6
    pad_y += 6
    cx = int(bubble["position"][0] * w)
    cy = int(bubble["position"][1] * h)

    rect = _bubble_rect(cx, cy, tw, th, pad_x, pad_y)
    rect = _clamp_rect(rect, w, h)

    fill = bubble.get("color", "#E0FFFF")
    border = bubble.get("border_color", "#006080")
    text_color = bubble.get("text_color", "#003344")

    x0, y0, x1, y1 = rect
    rw = x1 - x0
    rh = y1 - y0

    zag_size = max(5, min(8, rw // 16, rh // 10))
    points: list[tuple[int, int]] = []

    def _zigzag_edge(sx, sy, ex, ey, steps):
        pts = []
        dx = (ex - sx) / steps
        dy = (ey - sy) / steps
        length = max(1, (dx**2 + dy**2) ** 0.5)
        nx_dir = -dy / length
        ny_dir = dx / length
        for i in range(steps):
            mx = sx + dx * (i + 0.5)
            my = sy + dy * (i + 0.5)
            offset = zag_size if (i % 2 == 0) else -zag_size
            pts.append((sx + dx * i, sy + dy * i))
            pts.append((int(mx + nx_dir * offset), int(my + ny_dir * offset)))
        pts.append((ex, ey))
        return pts

    n_top = max(6, rw // 20)
    n_side = max(4, rh // 20)

    points.extend(_zigzag_edge(x0, y0, x1, y0, n_top))
    points.extend(_zigzag_edge(x1, y0, x1, y1, n_side))
    points.extend(_zigzag_edge(x1, y1, x0, y1, n_top))
    points.extend(_zigzag_edge(x0, y1, x0, y0, n_side))

    points = [(int(px), int(py)) for px, py in points]
    draw.polygon(points, fill=fill, outline=border, width=2)

    tail_target = bubble.get("tail_target")
    if tail_target is not None:
        tx = int(tail_target[0] * w)
        ty = int(tail_target[1] * h)
        _draw_speech_tail(draw, rect, (tx, ty), fill=fill, outline=border)

    rcx = (rect[0] + rect[2]) // 2
    text_top = (rect[1] + rect[3]) // 2 - th // 2
    _draw_text_block(draw, lines, font, rcx, text_top, color=text_color)


def _render_connected(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    bubble: dict,
    font: ImageFont.FreeTypeFont,
    lines: list[str],
    tw: int, th: int, pad_x: int, pad_y: int,
):
    """Rounded rect with TWO Bézier tails — multiple speakers."""
    w, h = img.size
    cx = int(bubble["position"][0] * w)
    cy = int(bubble["position"][1] * h)

    rect = _bubble_rect(cx, cy, tw, th, pad_x, pad_y)
    rect = _clamp_rect(rect, w, h)

    radius = min(20, (rect[2] - rect[0]) // 4)
    fill = bubble.get("color", "white")
    border = bubble.get("border_color", "black")
    text_color = bubble.get("text_color", "black")

    # Tails FIRST (behind bubble)
    tail_target = bubble.get("tail_target")
    tail_target_2 = bubble.get("tail_target_2")

    if tail_target is not None:
        tx = int(tail_target[0] * w)
        ty = int(tail_target[1] * h)
        _draw_speech_tail(draw, rect, (tx, ty), fill=fill, outline=border)

    if tail_target_2 is not None:
        tx2 = int(tail_target_2[0] * w)
        ty2 = int(tail_target_2[1] * h)
        _draw_speech_tail(draw, rect, (tx2, ty2), fill=fill, outline=border)

    draw.rounded_rectangle(rect, radius=radius, fill=fill, outline=border, width=_BORDER_WIDTH)

    rcx = (rect[0] + rect[2]) // 2
    text_top = (rect[1] + rect[3]) // 2 - th // 2
    _draw_text_block(draw, lines, font, rcx, text_top, color=text_color)


def _render_scream(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    bubble: dict,
    font: ImageFont.FreeTypeFont,
    lines: list[str],
    tw: int, th: int, pad_x: int, pad_y: int,
):
    """Extreme shout — very large irregular jagged polygon, thick border."""
    w, h = img.size
    pad_x += 16
    pad_y += 16
    cx = int(bubble["position"][0] * w)
    cy = int(bubble["position"][1] * h)

    rect = _bubble_rect(cx, cy, tw, th, pad_x, pad_y)
    rect = _clamp_rect(rect, w, h)

    fill = bubble.get("color", "#FFE0E0")
    border = bubble.get("border_color", "#CC0000")
    text_color = bubble.get("text_color", "#880000")
    border_w = 4

    x0, y0, x1, y1 = rect
    rcx_val = (x0 + x1) / 2
    rcy_val = (y0 + y1) / 2
    rx = (x1 - x0) / 2
    ry = (y1 - y0) / 2

    n_spikes = 20
    import random
    rng = random.Random(42)
    points = []
    for i in range(n_spikes):
        angle = 2 * math.pi * i / n_spikes
        if i % 2 == 0:
            r_factor = 1.25 + rng.uniform(0.0, 0.2)
        else:
            r_factor = 0.65 + rng.uniform(0.0, 0.12)
        px = rcx_val + rx * r_factor * math.cos(angle)
        py = rcy_val + ry * r_factor * math.sin(angle)
        points.append((int(px), int(py)))

    draw.polygon(points, fill=fill, outline=border, width=border_w)

    tail_target = bubble.get("tail_target")
    if tail_target is not None:
        tx = int(tail_target[0] * w)
        ty = int(tail_target[1] * h)
        _draw_speech_tail(draw, rect, (tx, ty), fill=fill, outline=border, border_w=border_w)

    text_top = int(rcy_val) - th // 2
    _draw_text_block(draw, lines, font, int(rcx_val), text_top, color=text_color)


def _auto_detect_sfx_style(text: str) -> str:
    """Auto-detect SFX perspective style based on the text content.

    Returns one of: "flat", "radial", "curved", "impact".
    """
    upper = text.strip().upper().rstrip("!?.").strip()
    # Check exact match first
    if upper in _SFX_STYLE_MAP:
        return _SFX_STYLE_MAP[upper]
    # Check if text starts with a known keyword
    for keyword, style in _SFX_STYLE_MAP.items():
        if upper.startswith(keyword):
            return style
    return "flat"


def _get_sfx_color(bubble: dict, scene_mood_tone: str | None = None) -> str:
    """Determine the best SFX color based on scene context.

    Uses complementary color theory: SFX in a blue scene → orange,
    SFX in a warm scene → cyan, etc.
    """
    # Explicit color takes priority
    explicit = bubble.get("text_color")
    if explicit and explicit != "#CC0000":  # not the default
        return explicit

    # Scene-aware color matching
    if scene_mood_tone and scene_mood_tone in _SFX_SCENE_COLORS:
        return _SFX_SCENE_COLORS[scene_mood_tone]

    # Fallback to classic red
    return "#CC0000"


def _render_sfx_flat(
    sfx_draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    cx: int, cy: int,
    color: str,
    outline_range: int = 3,
):
    """Render flat SFX text (legacy style) — centered at (cx, cy)."""
    tw_actual, th_actual = _measure_text(text, font)
    x = cx - tw_actual // 2
    y = cy - th_actual // 2

    # Black outline
    for ox in range(-outline_range, outline_range + 1):
        for oy in range(-outline_range, outline_range + 1):
            if ox == 0 and oy == 0:
                continue
            sfx_draw.text((x + ox, y + oy), text, font=font, fill="black")
    sfx_draw.text((x, y), text, font=font, fill=color)


def _render_sfx_radial(
    sfx_draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    cx: int, cy: int,
    color: str,
    img_size: tuple[int, int],
):
    """Render radial SFX — characters radiate outward from impact point."""
    char_count = len(text)
    if char_count == 0:
        return

    base_size = font.size
    radius = base_size * 1.2

    for i, char in enumerate(text):
        # Angle: spread characters evenly in an arc
        angle_start = -90 - (char_count - 1) * 12
        angle = math.radians(angle_start + i * 24)

        # Position along arc
        char_x = cx + int(radius * math.cos(angle))
        char_y = cy + int(radius * math.sin(angle))

        # Slight size variation (characters further from center slightly larger)
        scale = 1.0 + (i - char_count / 2) ** 2 * 0.02

        cw, ch = _measure_text(char, font)
        dx = char_x - cw // 2
        dy = char_y - ch // 2

        # Outline
        for ox in range(-2, 3):
            for oy in range(-2, 3):
                if ox == 0 and oy == 0:
                    continue
                sfx_draw.text((dx + ox, dy + oy), char, font=font, fill="black")
        sfx_draw.text((dx, dy), char, font=font, fill=color)


def _render_sfx_curved(
    sfx_draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    cx: int, cy: int,
    color: str,
    img_size: tuple[int, int],
):
    """Render curved SFX — text follows a sweeping arc for motion effects."""
    char_count = len(text)
    if char_count == 0:
        return

    base_size = font.size
    # Arc parameters
    arc_radius = base_size * 2.5
    arc_span = math.radians(min(120, char_count * 15))  # total arc angle
    arc_start = -math.pi / 2 - arc_span / 2  # center the arc upward

    for i, char in enumerate(text):
        t = i / max(1, char_count - 1) if char_count > 1 else 0.5
        angle = arc_start + arc_span * t

        char_x = cx + int(arc_radius * math.cos(angle))
        char_y = cy + int(arc_radius * math.sin(angle))

        cw, ch = _measure_text(char, font)
        dx = char_x - cw // 2
        dy = char_y - ch // 2

        # Outline
        for ox in range(-2, 3):
            for oy in range(-2, 3):
                if ox == 0 and oy == 0:
                    continue
                sfx_draw.text((dx + ox, dy + oy), char, font=font, fill="black")
        sfx_draw.text((dx, dy), char, font=font, fill=color)


def _render_sfx_impact(
    sfx_layer: Image.Image,
    sfx_draw: ImageDraw.ImageDraw,
    text: str,
    style: str,
    cx: int, cy: int,
    color: str,
    base_font_size: int,
):
    """Render impact SFX — characters grow larger away from impact point (shockwave)."""
    char_count = len(text)
    if char_count == 0:
        return

    spacing = base_font_size * 0.9
    total_width = spacing * (char_count - 1) if char_count > 1 else 0
    start_x = cx - int(total_width / 2)

    for i, char in enumerate(text):
        # Size increases from center outward: center chars small, edge chars big
        dist_from_center = abs(i - (char_count - 1) / 2) / max(1, (char_count - 1) / 2)
        scale = 1.0 + dist_from_center * 0.6  # up to 60% larger at edges
        char_size = max(12, int(base_font_size * scale))

        char_font = _get_font_for_bubble("sfx", style, char_size)
        char_x = start_x + int(i * spacing)

        cw, ch = _measure_text(char, char_font)
        dy = cy - ch // 2

        # Outline
        outline_r = max(2, char_size // 12)
        for ox in range(-outline_r, outline_r + 1):
            for oy in range(-outline_r, outline_r + 1):
                if ox == 0 and oy == 0:
                    continue
                sfx_draw.text((char_x + ox, dy + oy), char, font=char_font, fill="black")
        sfx_draw.text((char_x, dy), char, font=char_font, fill=color)


def _render_sfx(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    bubble: dict,
    font: ImageFont.FreeTypeFont,
    lines: list[str],
    tw: int, th: int, pad_x: int, pad_y: int,
):
    """Stylized sound effect text overlay with perspective matching and art integration.

    Supports four SFX perspective modes:
    - flat: Classic floating text (legacy, default)
    - radial: Characters radiate from impact point (explosions)
    - curved: Text follows a sweeping arc (movement/swoosh)
    - impact: Characters grow larger away from center (shockwave)

    Art integration features:
    - Semi-transparency (alpha 0.85)
    - Drop shadow matching scene lighting
    - Scene-aware color matching (complementary colors)
    - Partial occlusion (bottom 20% fades)
    - Size scaling based on narrative_weight
    """
    w, h = img.size
    text = " ".join(lines)
    rotation = bubble.get("rotation", -12)

    cx = int(bubble["position"][0] * w)
    cy = int(bubble["position"][1] * h)

    # --- Determine SFX style ---
    sfx_style = bubble.get("sfx_style") or bubble.get("sfx_perspective", "")
    if not sfx_style or sfx_style not in SFX_PERSPECTIVES:
        sfx_style = _auto_detect_sfx_style(text)

    # --- Narrative weight scaling (Task 5) ---
    narrative_weight = bubble.get("narrative_weight", "medium")
    weight_scale = _SFX_WEIGHT_SCALE.get(narrative_weight, 1.0)

    # Apply weight scaling to font
    scaled_font_size = max(12, int(font.size * weight_scale))
    style_name = bubble.get("_style", "western")
    scaled_font = _get_font_for_bubble("sfx", style_name, scaled_font_size)

    # --- Scene-aware color (Task 5) ---
    scene_mood_tone = bubble.get("scene_mood_tone")
    color = _get_sfx_color(bubble, scene_mood_tone)

    # --- Create SFX layer ---
    sfx_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sfx_draw = ImageDraw.Draw(sfx_layer)

    # --- Render SFX based on perspective style ---
    if sfx_style == "radial":
        _render_sfx_radial(sfx_draw, text, scaled_font, cx, cy, color, (w, h))
    elif sfx_style == "curved":
        _render_sfx_curved(sfx_draw, text, scaled_font, cx, cy, color, (w, h))
    elif sfx_style == "impact":
        _render_sfx_impact(sfx_layer, sfx_draw, text, style_name, cx, cy, color, scaled_font_size)
    else:  # "flat"
        _render_sfx_flat(sfx_draw, text, scaled_font, cx, cy, color)

    # --- Rotation ---
    if rotation != 0:
        sfx_layer = sfx_layer.rotate(
            rotation, expand=False, center=(cx, cy), resample=Image.BICUBIC
        )

    # --- Drop shadow (Task 5: art integration) ---
    shadow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    # Offset shadow slightly down-right (simulating upper-left light)
    shadow_offset = max(2, scaled_font_size // 15)
    shadow_arr = np.array(sfx_layer)
    # Create shadow from alpha channel
    shadow_alpha = shadow_arr[:, :, 3]
    shadow_rgba = np.zeros_like(shadow_arr)
    shadow_rgba[:, :, 3] = (shadow_alpha * 0.4).astype(np.uint8)  # 40% opacity black
    # Shift shadow
    if shadow_offset > 0:
        shifted = np.zeros_like(shadow_rgba)
        so = shadow_offset
        shifted[so:, so:] = shadow_rgba[:-so, :-so]
        shadow_layer = Image.fromarray(shifted, "RGBA")
        # Blur shadow slightly
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=max(1, shadow_offset)))

    # --- Partial occlusion: bottom 20% of SFX fades (Task 5) ---
    sfx_arr = np.array(sfx_layer, dtype=np.float32)
    # Find the bounding box of non-transparent pixels
    alpha = sfx_arr[:, :, 3]
    non_zero_rows = np.where(alpha.max(axis=1) > 0)[0]
    if len(non_zero_rows) > 0:
        sfx_top = non_zero_rows[0]
        sfx_bottom = non_zero_rows[-1]
        sfx_height = sfx_bottom - sfx_top + 1
        if sfx_height > 10:
            # Fade bottom 20%
            fade_start = sfx_bottom - int(sfx_height * 0.20)
            for y in range(fade_start, sfx_bottom + 1):
                fade_t = (y - fade_start) / max(1, sfx_bottom - fade_start)
                # Reduce alpha progressively
                sfx_arr[y, :, 3] *= (1.0 - fade_t * 0.6)  # fade to 40% at bottom

    # --- Semi-transparency: overall alpha 0.85 (Task 5) ---
    sfx_arr[:, :, 3] *= 0.85
    sfx_layer = Image.fromarray(sfx_arr.astype(np.uint8), "RGBA")

    # --- Composite: shadow first, then SFX ---
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    img = Image.alpha_composite(img, shadow_layer)
    img = Image.alpha_composite(img, sfx_layer)
    return img


# ---------------------------------------------------------------------------
# Dispatcher — maps bubble type → renderer function
# ---------------------------------------------------------------------------

_RENDERERS = {
    "speech":    _render_speech,
    "thought":   _render_thought,
    "shout":     _render_shout,
    "whisper":   _render_whisper,
    "narration": _render_narration,
    "caption":   _render_caption,
    "explosion": _render_explosion,
    "electric":  _render_electric,
    "connected": _render_connected,
    "scream":    _render_scream,
    "sfx":       _render_sfx,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_bubble_config(
    text: str,
    bubble_type: str = "speech",
    position: tuple[float, float] | str = (0.5, 0.15),
    tail_target: Optional[tuple[float, float]] = None,
    **kwargs,
) -> dict:
    """Create a bubble configuration dict.

    *position* can be a (x, y) tuple of normalised 0–1 floats,
    or a string key from POSITION_HINTS (e.g. "top_left").

    For ``sfx`` bubbles, additional parameters:
    - ``rotation=<degrees>``: text rotation angle
    - ``sfx_style=<str>``: perspective mode ("flat", "radial", "curved", "impact")
    - ``sfx_perspective=<str>``: alias for sfx_style
    - ``narrative_weight=<str>``: size scaling ("low", "medium", "high", "splash")
    - ``scene_mood_tone=<str>``: for color matching ("cool", "warm", "neutral", etc.)
    """
    if isinstance(position, str):
        position = POSITION_HINTS.get(position, (0.5, 0.15))

    tail_target_2 = kwargs.pop("tail_target_2", None)
    rotation = kwargs.pop("rotation", None)

    config: dict = {
        "text": text,
        "type": bubble_type,
        "position": tuple(position),
        "tail_target": tuple(tail_target) if tail_target else None,
        "tail_target_2": tuple(tail_target_2) if tail_target_2 else None,
        "font_size": kwargs.get("font_size", None),
        "max_width_ratio": kwargs.get("max_width_ratio", 0.4),
    }
    if rotation is not None:
        config["rotation"] = rotation
    if "color" in kwargs:
        config["color"] = kwargs.pop("color")
    if "border_color" in kwargs:
        config["border_color"] = kwargs.pop("border_color")
    if "text_color" in kwargs:
        config["text_color"] = kwargs.pop("text_color")
    # Genre hint for narration/caption styling
    if "genre" in kwargs:
        config["genre"] = kwargs.pop("genre")
    # SFX-specific parameters
    for sfx_key in ("sfx_style", "sfx_perspective", "narrative_weight", "scene_mood_tone"):
        if sfx_key in kwargs:
            config[sfx_key] = kwargs.pop(sfx_key)
    for k, v in kwargs.items():
        if k not in config:
            config[k] = v
    return config


def add_bubbles(
    panel_image: Image.Image,
    bubbles: list[dict],
    style: str = "western",
    panel_id: str = "default",
) -> Image.Image:
    """Add all speech bubbles to *panel_image*. Returns a **new** image.

    Implements:
    - Text-first adaptive sizing (balloon resizes to fit text)
    - Comic lettering grammar normalisation
    - Duplicate text detection and skipping
    - Bézier curved tails
    - Genre-specific caption styling
    - NEVER truncates text
    """
    img = panel_image.copy()
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    draw = ImageDraw.Draw(img)
    w, h = img.size

    # Reset deduplication for this panel
    _reset_dedup()

    for bubble in bubbles:
        btype = bubble.get("type", "speech")
        text = bubble.get("text", "")
        if not text.strip():
            continue

        # --- Duplicate detection ---
        if _is_duplicate(panel_id, text):
            continue

        # --- Comic lettering grammar normalisation ---
        text = _normalise_comic_text(text, btype)

        # --- Resolve position string hints ---
        pos = bubble.get("position", (0.5, 0.15))
        if isinstance(pos, str):
            pos = POSITION_HINTS.get(pos, (0.5, 0.15))
            bubble = {**bubble, "position": pos}

        # --- TEXT-FIRST adaptive sizing ---
        fsize = bubble.get("font_size")
        max_w_ratio = bubble.get("max_width_ratio", 0.40)

        font, lines, tw, th, pad_x, pad_y = _compute_text_first_layout(
            text=text,
            bubble_type=btype,
            style=style,
            panel_w=w,
            panel_h=h,
            pos=pos,
            base_font_size=fsize,
            max_width_ratio=max_w_ratio,
        )

        # --- Render ---
        renderer = _RENDERERS.get(btype, _render_speech)

        # Narration and caption renderers accept style parameter
        if btype in ("narration", "caption"):
            result = renderer(img, draw, bubble, font, lines, tw, th, pad_x, pad_y, style=style)
        elif btype == "sfx":
            # Pass style info for font resolution inside SFX renderer
            bubble = {**bubble, "_style": style}
            result = renderer(img, draw, bubble, font, lines, tw, th, pad_x, pad_y)
        else:
            result = renderer(img, draw, bubble, font, lines, tw, th, pad_x, pad_y)

        # Caption renderer returns a new draw object
        if result is not None and isinstance(result, ImageDraw.ImageDraw):
            draw = result
        # SFX renderer returns a new Image
        elif result is not None and isinstance(result, Image.Image):
            img = result
            draw = ImageDraw.Draw(img)

    return img


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

def _create_test_image(width: int = 768, height: int = 768) -> Image.Image:
    """Create a gradient background for testing."""
    img = Image.new("RGB", (width, height))
    for y in range(height):
        r = int(60 + 100 * (y / height))
        g = int(80 + 80 * (y / height))
        b = int(140 + 60 * (1 - y / height))
        for x in range(width):
            x_blend = x / width
            img.putpixel(
                (x, y),
                (
                    int(r * (1 - x_blend * 0.3)),
                    int(g * (1 - x_blend * 0.1)),
                    int(b * (1 + x_blend * 0.15)),
                ),
            )
    return img


def main():
    """Generate a test image with one of each bubble type."""
    import time

    print("Creating test image…")
    t0 = time.time()
    img = _create_test_image(width=1200, height=900)

    bubbles = [
        # Row 1
        create_bubble_config(
            "Hey! This is a normal speech bubble with word wrapping.",
            bubble_type="speech",
            position=(0.18, 0.12),
            tail_target=(0.08, 0.30),
        ),
        create_bubble_config(
            "Hmm, I wonder what's going on here…",
            bubble_type="thought",
            position=(0.50, 0.12),
            tail_target=(0.50, 0.30),
        ),
        create_bubble_config(
            "Look out! Danger ahead!",
            bubble_type="shout",
            position=(0.82, 0.12),
            tail_target=(0.90, 0.30),
            color="#FFEEEE",
        ),
        # Row 2
        create_bubble_config(
            "psst… don't tell anyone…",
            bubble_type="whisper",
            position=(0.18, 0.38),
            tail_target=(0.08, 0.55),
            text_color="#444444",
        ),
        create_bubble_config(
            "Meanwhile, in a galaxy far, far away…",
            bubble_type="narration",
            position=(0.50, 0.38),
        ),
        create_bubble_config(
            "BOOM!",
            bubble_type="explosion",
            position=(0.82, 0.38),
        ),
        # Row 3
        create_bubble_config(
            "SYSTEM ONLINE. INITIATING PROTOCOL.",
            bubble_type="electric",
            position=(0.18, 0.65),
            tail_target=(0.08, 0.82),
        ),
        create_bubble_config(
            "We both agree on this!",
            bubble_type="connected",
            position=(0.50, 0.65),
            tail_target=(0.35, 0.85),
            tail_target_2=(0.65, 0.85),
        ),
        create_bubble_config(
            "NOOOO!!!",
            bubble_type="scream",
            position=(0.82, 0.65),
            tail_target=(0.90, 0.85),
        ),
        # SFX overlays — demonstrating different perspective styles
        create_bubble_config(
            "BOOM!",
            bubble_type="sfx",
            position=(0.50, 0.50),
            rotation=-15,
            sfx_style="impact",
            narrative_weight="high",
            scene_mood_tone="cool",
        ),
        # Bottom caption
        create_bubble_config(
            "Chapter 3 — The Final Confrontation  |  All 11 bubble types",
            bubble_type="caption",
            position=(0.5, 0.95),
            text_color="white",
        ),
    ]

    result = add_bubbles(img, bubbles, style="western")

    out_dir = Path(__file__).resolve().parent.parent.parent.parent / "output" / "comicmaster"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "test_bubbles.png"
    result.save(str(out_path))
    elapsed = time.time() - t0
    print(f"✅ Saved to {out_path}  ({elapsed:.2f}s)")


if __name__ == "__main__":
    main()

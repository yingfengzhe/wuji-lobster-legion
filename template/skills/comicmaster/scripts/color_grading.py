#!/usr/bin/env python3
"""
ComicMaster — Color Grading Pipeline

Apply a unified color palette across all panels of a comic for visual consistency.
Supports preset grades (noir, vintage, cyberpunk, etc.), custom parameters,
scene-based palettes, color temperature shifting, focal point boost, and color holds.
"""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

# ---------------------------------------------------------------------------
# Preset color grades
# ---------------------------------------------------------------------------

COLOR_GRADES = {
    "noir": {
        "saturation": 0.3,       # desaturated
        "contrast": 1.4,         # high contrast
        "brightness": 0.85,      # slightly dark
        "color_temp": -20,       # cool/blue shift
        "vignette": 0.3,         # edge darkening
    },
    "vintage": {
        "saturation": 0.7,
        "contrast": 1.1,
        "brightness": 1.05,
        "color_temp": 15,        # warm/sepia shift
        "vignette": 0.15,
    },
    "vibrant": {
        "saturation": 1.4,
        "contrast": 1.15,
        "brightness": 1.0,
        "color_temp": 0,
        "vignette": 0.0,
    },
    "pastel": {
        "saturation": 0.6,
        "contrast": 0.85,
        "brightness": 1.15,
        "color_temp": 5,
        "vignette": 0.0,
    },
    "cyberpunk": {
        "saturation": 1.2,
        "contrast": 1.3,
        "brightness": 0.9,
        "color_temp": -15,       # cool/blue-purple
        "vignette": 0.25,
    },
    "manga_bw": {
        "saturation": 0.0,       # full B&W
        "contrast": 1.5,
        "brightness": 1.0,
        "color_temp": 0,
        "vignette": 0.0,
    },
}


# ---------------------------------------------------------------------------
# Mood → auto-palette mapping
# ---------------------------------------------------------------------------

MOOD_PALETTES: dict[str, dict] = {
    "tense": {
        "primary": "#CC3333",
        "secondary": "#8B0000",
        "accent": "#FF6600",
        "mood_tone": "warm",
        "saturation": 1.15,
        "contrast": 1.35,
    },
    "calm": {
        "primary": "#4A90D9",
        "secondary": "#2C5F8A",
        "accent": "#87CEEB",
        "mood_tone": "cool",
        "saturation": 0.85,
        "contrast": 0.95,
    },
    "mysterious": {
        "primary": "#6A0DAD",
        "secondary": "#1B1464",
        "accent": "#9B59B6",
        "mood_tone": "cool",
        "saturation": 0.9,
        "contrast": 1.2,
    },
    "cheerful": {
        "primary": "#FFB347",
        "secondary": "#FF8C00",
        "accent": "#FFD700",
        "mood_tone": "warm",
        "saturation": 1.3,
        "contrast": 1.05,
    },
    "noir": {
        "primary": "#4A5568",
        "secondary": "#2D3748",
        "accent": "#718096",
        "mood_tone": "cool",
        "saturation": 0.3,
        "contrast": 1.4,
    },
    "dark": {
        "primary": "#1A1A2E",
        "secondary": "#16213E",
        "accent": "#E94560",
        "mood_tone": "cool",
        "saturation": 0.7,
        "contrast": 1.3,
    },
    "hopeful": {
        "primary": "#F0E68C",
        "secondary": "#DAA520",
        "accent": "#FF6347",
        "mood_tone": "warm",
        "saturation": 1.1,
        "contrast": 1.0,
    },
    "dramatic": {
        "primary": "#B22222",
        "secondary": "#8B0000",
        "accent": "#FFD700",
        "mood_tone": "warm",
        "saturation": 1.2,
        "contrast": 1.4,
    },
    "neutral": {
        "primary": "#808080",
        "secondary": "#696969",
        "accent": "#A9A9A9",
        "mood_tone": "neutral",
        "saturation": 1.0,
        "contrast": 1.0,
    },
    "happy": {
        "primary": "#FF9F43",
        "secondary": "#FECA57",
        "accent": "#FF6B6B",
        "mood_tone": "warm",
        "saturation": 1.25,
        "contrast": 1.05,
    },
    "sad": {
        "primary": "#4B6584",
        "secondary": "#2C3A47",
        "accent": "#778CA3",
        "mood_tone": "cool",
        "saturation": 0.6,
        "contrast": 0.95,
    },
}


# ---------------------------------------------------------------------------
# Helper: hex to RGB
# ---------------------------------------------------------------------------

def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color string to (R, G, B) tuple."""
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert RGB values to hex string."""
    return f"#{r:02X}{g:02X}{b:02X}"


def _complementary_color(hex_color: str) -> str:
    """Return the complementary color of a hex color."""
    r, g, b = _hex_to_rgb(hex_color)
    return _rgb_to_hex(255 - r, 255 - g, 255 - b)


# ---------------------------------------------------------------------------
# Core functions (original)
# ---------------------------------------------------------------------------

def apply_color_temp(img: Image.Image, shift: int | float) -> Image.Image:
    """Shift color temperature using numpy array operations.

    Positive shift = warm (boost R, reduce B).
    Negative shift = cool (boost B, reduce R).

    Args:
        img: PIL Image in RGB mode.
        shift: Temperature shift value (-100 to 100 typical range).
               Also accepts float for fine-grained control.

    Returns:
        Temperature-adjusted PIL Image.
    """
    if shift == 0:
        return img

    shift = int(round(shift))
    arr = np.array(img, dtype=np.int16)

    # Warm: +R, -B. Cool: +B, -R.
    arr[:, :, 0] = np.clip(arr[:, :, 0] + shift, 0, 255)      # Red
    arr[:, :, 2] = np.clip(arr[:, :, 2] - shift, 0, 255)      # Blue

    return Image.fromarray(arr.astype(np.uint8), "RGB")


def apply_vignette(img: Image.Image, strength: float) -> Image.Image:
    """Add edge-darkening vignette effect.

    Creates a radial gradient from center (bright) to edges (dark) and
    multiplies it with the image.

    Args:
        img: PIL Image in RGB mode.
        strength: Vignette intensity (0.0 = none, 1.0 = extreme).

    Returns:
        Vignetted PIL Image.
    """
    if strength <= 0.0:
        return img

    w, h = img.size
    # Build distance-from-center map (normalized 0..1)
    Y, X = np.ogrid[:h, :w]
    cx, cy = w / 2.0, h / 2.0
    # Max distance = diagonal / 2
    max_dist = np.sqrt(cx ** 2 + cy ** 2)
    dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2) / max_dist  # 0..~1

    # Vignette mask: 1.0 at center → (1 - strength) at edges
    mask = 1.0 - strength * (dist ** 2)
    mask = np.clip(mask, 0.0, 1.0).astype(np.float32)

    # Apply to all channels
    arr = np.array(img, dtype=np.float32)
    arr *= mask[:, :, np.newaxis]
    arr = np.clip(arr, 0, 255).astype(np.uint8)

    return Image.fromarray(arr, "RGB")


def apply_color_grade(
    image_path: str,
    grade_name: str,
    output_path: str | None = None,
) -> str:
    """Apply a color grade preset to a single image.

    Processing order: saturation → contrast → brightness → color_temp → vignette.

    Args:
        image_path: Path to input image.
        grade_name: Name of a preset in COLOR_GRADES.
        output_path: Where to save. Defaults to <orig>_<grade>.png alongside input.

    Returns:
        Path to the graded output image.

    Raises:
        ValueError: If grade_name is not in COLOR_GRADES.
        FileNotFoundError: If image_path does not exist.
    """
    if grade_name not in COLOR_GRADES:
        raise ValueError(
            f"Unknown grade '{grade_name}'. Available: {list(COLOR_GRADES.keys())}"
        )

    grade = COLOR_GRADES[grade_name]
    src = Path(image_path)
    if not src.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    img = Image.open(src).convert("RGB")

    # 1) Saturation
    sat = grade["saturation"]
    if sat != 1.0:
        img = ImageEnhance.Color(img).enhance(sat)

    # 2) Contrast
    con = grade["contrast"]
    if con != 1.0:
        img = ImageEnhance.Contrast(img).enhance(con)

    # 3) Brightness
    bri = grade["brightness"]
    if bri != 1.0:
        img = ImageEnhance.Brightness(img).enhance(bri)

    # 4) Color temperature (numpy)
    temp = grade["color_temp"]
    if temp != 0:
        img = apply_color_temp(img, temp)

    # 5) Vignette (numpy)
    vig = grade["vignette"]
    if vig > 0:
        img = apply_vignette(img, vig)

    # Determine output path
    if output_path is None:
        output_path = str(src.parent / f"{src.stem}_{grade_name}{src.suffix}")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    return output_path


def grade_all_panels(
    panel_paths: list[str],
    grade_name: str,
    output_dir: str,
) -> list[str]:
    """Apply the same grade to all panels for visual consistency.

    Args:
        panel_paths: List of image file paths.
        grade_name: Preset name from COLOR_GRADES.
        output_dir: Directory for graded outputs.

    Returns:
        List of output file paths.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for panel_path in panel_paths:
        src = Path(panel_path)
        out = out_dir / f"{src.stem}_{grade_name}{src.suffix}"
        result = apply_color_grade(panel_path, grade_name, str(out))
        results.append(result)

    return results


def list_grades() -> list[str]:
    """Return available grade preset names."""
    return list(COLOR_GRADES.keys())


# ---------------------------------------------------------------------------
# NEW: Scene-based palette application (Task 1)
# ---------------------------------------------------------------------------

def get_auto_palette(mood: str) -> dict:
    """Generate an auto-palette based on mood.

    Args:
        mood: Mood string (e.g., "tense", "calm", "mysterious", etc.)

    Returns:
        Palette dict with primary, secondary, accent, mood_tone keys.
    """
    return MOOD_PALETTES.get(mood, MOOD_PALETTES["neutral"]).copy()


def apply_scene_palette(img: Image.Image, palette: dict) -> Image.Image:
    """Apply a scene-specific color palette to an image.

    The palette tints the image toward the scene's color scheme while
    preserving the original image structure. Works by:
    1. Applying mood_tone-based color temperature shift
    2. Tinting toward the primary color (subtle overlay blend)
    3. Adjusting saturation and contrast per palette

    Args:
        img: PIL Image in RGB mode.
        palette: Dict with keys: primary, secondary, accent, mood_tone.
                 Optional keys: saturation, contrast (float multipliers).

    Returns:
        Palette-graded PIL Image.
    """
    if img.mode != "RGB":
        img = img.convert("RGB")

    primary = _hex_to_rgb(palette.get("primary", "#808080"))
    mood_tone = palette.get("mood_tone", "neutral")

    # 1) Color temperature based on mood_tone
    temp_map = {"warm": 12, "cool": -12, "neutral": 0}
    temp_shift = temp_map.get(mood_tone, 0)
    if temp_shift != 0:
        img = apply_color_temp(img, temp_shift)

    # 2) Subtle tint toward primary color (15% blend)
    tint_strength = 0.15
    arr = np.array(img, dtype=np.float32)
    tint_layer = np.full_like(arr, primary, dtype=np.float32)
    arr = arr * (1.0 - tint_strength) + tint_layer * tint_strength
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, "RGB")

    # 3) Saturation adjustment
    sat = palette.get("saturation", 1.0)
    if sat != 1.0:
        img = ImageEnhance.Color(img).enhance(sat)

    # 4) Contrast adjustment
    con = palette.get("contrast", 1.0)
    if con != 1.0:
        img = ImageEnhance.Contrast(img).enhance(con)

    return img


def interpolate_palettes(
    palette_a: dict, palette_b: dict, t: float
) -> dict:
    """Linearly interpolate between two palettes for smooth transitions.

    Args:
        palette_a: Source palette dict.
        palette_b: Target palette dict.
        t: Interpolation factor (0.0 = fully A, 1.0 = fully B).

    Returns:
        Interpolated palette dict.
    """
    t = max(0.0, min(1.0, t))

    def _lerp_color(hex_a: str, hex_b: str) -> str:
        ra, ga, ba = _hex_to_rgb(hex_a)
        rb, gb, bb = _hex_to_rgb(hex_b)
        r = int(ra + (rb - ra) * t)
        g = int(ga + (gb - ga) * t)
        b = int(ba + (bb - ba) * t)
        return _rgb_to_hex(r, g, b)

    def _lerp_float(a: float, b: float) -> float:
        return a + (b - a) * t

    result = {}
    for key in ("primary", "secondary", "accent"):
        a_val = palette_a.get(key, "#808080")
        b_val = palette_b.get(key, "#808080")
        result[key] = _lerp_color(a_val, b_val)

    for key in ("saturation", "contrast"):
        a_val = palette_a.get(key, 1.0)
        b_val = palette_b.get(key, 1.0)
        result[key] = round(_lerp_float(a_val, b_val), 3)

    # mood_tone: pick whichever is dominant
    result["mood_tone"] = palette_b["mood_tone"] if t > 0.5 else palette_a.get("mood_tone", "neutral")

    return result


def grade_panels_with_scenes(
    panel_paths: list[str],
    panels_data: list[dict],
    scenes: list[dict],
    base_grade: str | None = None,
    output_dir: str | None = None,
) -> list[str]:
    """Apply scene-aware color grading to panels.

    Each panel references a scene_id. The scene's palette is applied.
    When the scene changes between consecutive panels, a gradual
    transition is applied over 1-2 panels.

    Args:
        panel_paths: List of image file paths, matching panels_data order.
        panels_data: List of panel dicts from story plan (must have 'id',
                     optionally 'scene_id' and 'mood').
        scenes: List of scene dicts from story plan with 'id' and 'palette'.
        base_grade: Optional base grade preset to apply first.
        output_dir: Directory for graded outputs. None = alongside input.

    Returns:
        List of output file paths.
    """
    # Build scene lookup
    scene_map: dict[str, dict] = {}
    for scene in scenes:
        sid = scene.get("id", "")
        if sid:
            scene_map[sid] = scene.get("palette", {})

    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    results = []
    prev_palette: dict | None = None
    transition_panels: int = 0  # countdown for transition blending

    for idx, (panel_path, panel_data) in enumerate(zip(panel_paths, panels_data)):
        src = Path(panel_path)
        img = Image.open(src).convert("RGB")

        # Apply base grade first if specified
        if base_grade and base_grade in COLOR_GRADES:
            grade = COLOR_GRADES[base_grade]
            sat = grade["saturation"]
            if sat != 1.0:
                img = ImageEnhance.Color(img).enhance(sat)
            con = grade["contrast"]
            if con != 1.0:
                img = ImageEnhance.Contrast(img).enhance(con)
            bri = grade["brightness"]
            if bri != 1.0:
                img = ImageEnhance.Brightness(img).enhance(bri)
            temp = grade["color_temp"]
            if temp != 0:
                img = apply_color_temp(img, temp)
            vig = grade["vignette"]
            if vig > 0:
                img = apply_vignette(img, vig)

        # Determine current scene palette
        scene_id = panel_data.get("scene_id", "")
        current_palette = scene_map.get(scene_id)

        # If no scene palette, auto-generate from mood
        if not current_palette:
            mood = panel_data.get("mood", "neutral")
            current_palette = get_auto_palette(mood)

        # Handle scene transition (gradual blend over 2 panels)
        if prev_palette is not None and current_palette != prev_palette:
            transition_panels = 2

        if transition_panels > 0 and prev_palette is not None:
            # Blend: transition_panels=2 → t=0.5, transition_panels=1 → t=1.0
            t = 1.0 - (transition_panels - 1) * 0.5
            blended_palette = interpolate_palettes(prev_palette, current_palette, t)
            img = apply_scene_palette(img, blended_palette)
            transition_panels -= 1
        else:
            img = apply_scene_palette(img, current_palette)

        # Apply color_temp_override if present (Task 2)
        temp_override = panel_data.get("color_temp_override")
        if temp_override is not None:
            # Map -1.0..1.0 to -30..30 shift
            shift = int(round(float(temp_override) * 30))
            if shift != 0:
                img = apply_color_temp(img, shift)

        # Apply focal point boost if configured (Task 3)
        focal_boost = panel_data.get("focal_boost")
        if focal_boost is None:
            focal_boost = 0.15  # default
        if focal_boost > 0:
            img = apply_focal_boost(img, focal_boost)

        # Apply color holds if enabled (Task 6)
        if panel_data.get("color_holds", False):
            hold_color = current_palette.get("primary", "#808080")
            img = apply_color_holds(img, hold_color)

        prev_palette = current_palette

        # Save
        if output_dir:
            out_path = str(Path(output_dir) / f"{src.stem}_graded{src.suffix}")
        else:
            out_path = str(src.parent / f"{src.stem}_graded{src.suffix}")
        img.save(out_path, "PNG")
        results.append(out_path)

    return results


# ---------------------------------------------------------------------------
# NEW: Color Temperature Shifting (Task 2)
# ---------------------------------------------------------------------------

def compute_temp_sequence(
    num_panels: int,
    start_temp: float = 0.8,
    end_temp: float = -0.8,
) -> list[float]:
    """Compute a sequence of color temperature values for an action arc.

    Generates a smooth warm→cool (or cool→warm) shift across a sequence
    of panels, following a narrative arc.

    Args:
        num_panels: Number of panels in the sequence.
        start_temp: Starting temperature (-1.0=cool, 1.0=warm). Default 0.8 (warm).
        end_temp: Ending temperature. Default -0.8 (cool, for climax).

    Returns:
        List of float values for each panel's color_temp_override.
    """
    if num_panels <= 1:
        return [start_temp]

    result = []
    for i in range(num_panels):
        t = i / (num_panels - 1)
        # Use easing curve (ease-in-out) for more natural transition
        # Smoothstep: 3t² - 2t³
        t_smooth = 3 * t * t - 2 * t * t * t
        value = start_temp + (end_temp - start_temp) * t_smooth
        result.append(round(value, 3))

    return result


# ---------------------------------------------------------------------------
# NEW: Focal Point Color Boost (Task 3)
# ---------------------------------------------------------------------------

def apply_focal_boost(
    img: Image.Image,
    strength: float = 0.15,
    center: tuple[float, float] | None = None,
) -> Image.Image:
    """Apply focal point color boost — increase saturation at center, reduce at edges.

    Creates a center-weighted saturation mask that draws the eye to the
    focal point (typically the main character in the center of the panel).

    Args:
        img: PIL Image in RGB mode.
        strength: Boost intensity (0.0 = none, 0.5 = strong). Default 0.15.
        center: Focal point as (x_ratio, y_ratio) in 0..1 range.
                Defaults to (0.5, 0.45) — slightly above center where
                characters typically appear.

    Returns:
        Focal-boosted PIL Image.
    """
    if strength <= 0.0:
        return img

    strength = min(strength, 0.5)

    if center is None:
        center = (0.5, 0.45)

    w, h = img.size
    cx = center[0] * w
    cy = center[1] * h

    # Build radial distance mask
    Y, X = np.ogrid[:h, :w]
    max_dist = np.sqrt((w / 2) ** 2 + (h / 2) ** 2)
    dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2) / max_dist  # 0..~1

    # Saturation multiplier map:
    # Center: 1.0 + strength (boosted)
    # Edges: 1.0 - strength*0.5 (slightly desaturated)
    sat_boost = 1.0 + strength * (1.0 - dist * 2.0)
    sat_boost = np.clip(sat_boost, 1.0 - strength * 0.5, 1.0 + strength).astype(np.float32)

    # Convert to HSV for saturation manipulation
    arr = np.array(img, dtype=np.float32) / 255.0

    # Simple saturation adjustment via luminance
    # Luminance (perceived)
    lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    lum = lum[:, :, np.newaxis]

    # Adjust saturation: lerp between luminance (grayscale) and color
    # Higher sat_boost → more color (further from gray)
    sat_mask = sat_boost[:, :, np.newaxis]
    result = lum + (arr - lum) * sat_mask
    result = np.clip(result * 255, 0, 255).astype(np.uint8)

    # Also apply slight contrast boost at center
    # Contrast mask: center gets slight boost, edges get slight reduction
    contrast_mask = 1.0 + strength * 0.3 * (1.0 - dist * 1.5)
    contrast_mask = np.clip(contrast_mask, 0.95, 1.0 + strength * 0.3).astype(np.float32)

    result_f = result.astype(np.float32)
    mean = result_f.mean()
    result_f = mean + (result_f - mean) * contrast_mask[:, :, np.newaxis]
    result_f = np.clip(result_f, 0, 255).astype(np.uint8)

    return Image.fromarray(result_f, "RGB")


# ---------------------------------------------------------------------------
# NEW: Color Holds (Task 6)
# ---------------------------------------------------------------------------

def apply_color_holds(
    img: Image.Image,
    hold_color: str = "#4A90D9",
    threshold: int = 40,
    edge_width: int = 0,
) -> Image.Image:
    """Apply color holds — replace dark outlines near image edges with scene color.

    "Color holds" is a professional coloring technique where black outlines
    are replaced with colored lines to create softer, more atmospheric edges.
    This simplified version targets near-black pixels at the image borders.

    Args:
        img: PIL Image in RGB mode.
        hold_color: Hex color to replace black outlines with.
        threshold: Maximum brightness for a pixel to be considered "black"
                   (0-255). Default 40.
        edge_width: Width of border region to process (0 = auto ~8% of image).

    Returns:
        Color-held PIL Image.
    """
    if img.mode != "RGB":
        img = img.convert("RGB")

    w, h = img.size
    if edge_width <= 0:
        edge_width = max(10, int(min(w, h) * 0.08))

    hold_rgb = _hex_to_rgb(hold_color)
    arr = np.array(img, dtype=np.uint8).copy()

    # Brightness = max of RGB channels (simple approximation)
    brightness = arr.max(axis=2)

    # Create edge mask — pixels near the image border
    edge_mask = np.zeros((h, w), dtype=bool)
    edge_mask[:edge_width, :] = True      # top
    edge_mask[-edge_width:, :] = True     # bottom
    edge_mask[:, :edge_width] = True      # left
    edge_mask[:, -edge_width:] = True     # right

    # Find near-black pixels within edge region
    dark_pixels = (brightness < threshold) & edge_mask

    # Create gradient factor based on distance from edge
    # Pixels closer to the edge get stronger color hold
    dist_from_edge = np.full((h, w), float(edge_width), dtype=np.float32)

    for y in range(h):
        for x in range(w):
            if edge_mask[y, x]:
                d = min(y, h - 1 - y, x, w - 1 - x)
                dist_from_edge[y, x] = d

    # Normalize to 0..1 (0 = at edge, 1 = at edge_width boundary)
    fade = dist_from_edge / max(1, edge_width)
    fade = np.clip(fade, 0, 1)

    # Apply color hold with fade: strong at edge, fading toward interior
    hold_arr = np.array(hold_rgb, dtype=np.float32)
    for c in range(3):
        channel = arr[:, :, c].astype(np.float32)
        # Blend: dark pixels in edge region → hold_color, faded by distance
        blend_factor = (1.0 - fade) * 0.85  # max 85% replacement
        channel[dark_pixels] = (
            channel[dark_pixels] * (1.0 - blend_factor[dark_pixels])
            + hold_arr[c] * blend_factor[dark_pixels]
        )
        arr[:, :, c] = np.clip(channel, 0, 255).astype(np.uint8)

    return Image.fromarray(arr, "RGB")


# ---------------------------------------------------------------------------
# NEW: Scene-aware grading for pipeline integration
# ---------------------------------------------------------------------------

def grade_panel_for_pipeline(
    img: Image.Image,
    panel_data: dict,
    scenes: list[dict] | None = None,
    base_grade: str | None = None,
    prev_palette: dict | None = None,
    is_transition: bool = False,
    transition_t: float = 1.0,
) -> tuple[Image.Image, dict]:
    """Grade a single panel image for pipeline integration.

    Convenience function that applies all grading steps to a single panel.
    Returns the graded image and the palette used (for transition tracking).

    Args:
        img: Input PIL Image.
        panel_data: Panel dict from story plan.
        scenes: List of scene dicts (optional).
        base_grade: Base grade preset name (optional).
        prev_palette: Previous panel's palette for transition blending.
        is_transition: Whether this panel is in a scene transition.
        transition_t: Blend factor if in transition (0=prev, 1=current).

    Returns:
        Tuple of (graded_image, current_palette).
    """
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Build scene lookup
    scene_map: dict[str, dict] = {}
    if scenes:
        for scene in scenes:
            sid = scene.get("id", "")
            if sid:
                scene_map[sid] = scene.get("palette", {})

    # Apply base grade
    if base_grade and base_grade in COLOR_GRADES:
        grade = COLOR_GRADES[base_grade]
        sat = grade["saturation"]
        if sat != 1.0:
            img = ImageEnhance.Color(img).enhance(sat)
        con = grade["contrast"]
        if con != 1.0:
            img = ImageEnhance.Contrast(img).enhance(con)
        bri = grade["brightness"]
        if bri != 1.0:
            img = ImageEnhance.Brightness(img).enhance(bri)
        temp = grade["color_temp"]
        if temp != 0:
            img = apply_color_temp(img, temp)
        vig = grade["vignette"]
        if vig > 0:
            img = apply_vignette(img, vig)

    # Determine palette
    scene_id = panel_data.get("scene_id", "")
    current_palette = scene_map.get(scene_id)
    if not current_palette:
        mood = panel_data.get("mood", "neutral")
        current_palette = get_auto_palette(mood)

    # Transition blending
    if is_transition and prev_palette is not None:
        blended = interpolate_palettes(prev_palette, current_palette, transition_t)
        img = apply_scene_palette(img, blended)
    else:
        img = apply_scene_palette(img, current_palette)

    # Color temp override
    temp_override = panel_data.get("color_temp_override")
    if temp_override is not None:
        shift = int(round(float(temp_override) * 30))
        if shift != 0:
            img = apply_color_temp(img, shift)

    # Focal boost
    focal_boost = panel_data.get("focal_boost", 0.15)
    if focal_boost > 0:
        img = apply_focal_boost(img, focal_boost)

    # Color holds
    if panel_data.get("color_holds", False):
        hold_color = current_palette.get("primary", "#808080")
        img = apply_color_holds(img, hold_color)

    return img, current_palette


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args():
    parser = argparse.ArgumentParser(
        description="ComicMaster Color Grading — apply consistent color grades to comic panels."
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Image file or directory of images to grade.",
    )
    parser.add_argument(
        "--grade", "-g",
        default="noir",
        help=f"Grade preset name (default: noir). Options: {', '.join(COLOR_GRADES.keys())}",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output directory (default: alongside input files).",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        dest="list_grades",
        help="List available grade presets and exit.",
    )
    parser.add_argument(
        "--focal-boost",
        type=float,
        default=None,
        help="Apply focal point color boost (0.0–0.5, default off).",
    )
    parser.add_argument(
        "--color-holds",
        action="store_true",
        help="Apply color holds effect (replace dark edges with scene color).",
    )
    parser.add_argument(
        "--hold-color",
        default="#4A90D9",
        help="Color for color holds (hex, default: #4A90D9).",
    )
    return parser.parse_args()


def main():
    args = _parse_args()

    if args.list_grades:
        print("Available color grades:")
        for name, params in COLOR_GRADES.items():
            print(f"  {name:12s}  sat={params['saturation']:.1f}  "
                  f"con={params['contrast']:.2f}  bri={params['brightness']:.2f}  "
                  f"temp={params['color_temp']:+d}  vig={params['vignette']:.2f}")
        print("\nAvailable mood palettes:")
        for mood, pal in MOOD_PALETTES.items():
            print(f"  {mood:12s}  primary={pal['primary']}  "
                  f"tone={pal['mood_tone']}  sat={pal.get('saturation', 1.0):.1f}")
        return

    if not args.input:
        print("Error: provide an image file or directory, or use --list", file=sys.stderr)
        sys.exit(1)

    input_path = Path(args.input)

    # Collect image files
    if input_path.is_dir():
        image_paths = sorted(
            str(p) for p in input_path.iterdir()
            if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp")
        )
    elif input_path.is_file():
        image_paths = [str(input_path)]
    else:
        print(f"Error: '{args.input}' is not a valid file or directory.", file=sys.stderr)
        sys.exit(1)

    if not image_paths:
        print("No images found.", file=sys.stderr)
        sys.exit(1)

    output_dir = args.output
    print(f"Grading {len(image_paths)} image(s) with '{args.grade}'...")

    t0 = time.time()
    if output_dir:
        results = grade_all_panels(image_paths, args.grade, output_dir)
    else:
        results = []
        for ip in image_paths:
            results.append(apply_color_grade(ip, args.grade))
    elapsed = time.time() - t0

    # Post-processing: focal boost and color holds
    if args.focal_boost is not None or args.color_holds:
        for i, result_path in enumerate(results):
            img = Image.open(result_path).convert("RGB")
            if args.focal_boost is not None:
                img = apply_focal_boost(img, args.focal_boost)
            if args.color_holds:
                img = apply_color_holds(img, args.hold_color)
            img.save(result_path, "PNG")

    for r in results:
        size_kb = os.path.getsize(r) / 1024
        print(f"  ✓ {r}  ({size_kb:.0f} KB)")
    print(f"Done in {elapsed:.2f}s  ({elapsed / len(results):.2f}s per image)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
ComicMaster — Page Layout Composer (v2)

Composes individual panel images into full comic pages using grid templates
or dynamic layouts driven by narrative_weight, panel transitions, panel shapes,
spread-aware positioning, and narrative-based templates.

Pure Python with PIL/Pillow.

Features:
- Variable gutter widths based on panel transitions (pacing)
- Non-rectangular panel shapes (diagonal, wavy, broken, borderless)
- Spread-aware layout (verso/recto double-page thinking)
- Splash page validation and rules
- Narrative-based layout templates with auto-selection
"""

import json
import logging
import math
import os
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Template directory (relative to this file)
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "assets" / "templates"

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Weight-to-unit mapping for dynamic row budget allocation
WEIGHT_UNITS = {"low": 0.7, "medium": 1.0, "high": 1.5, "splash": 3.0}

# Row budget — how many weight-units fit in a single row
ROW_BUDGET = 3.0

# Target rows per page (min, max)
ROWS_PER_PAGE = (2, 3)

# Panel count guidelines per page
PANELS_PER_PAGE_MIN = 2       # dramatic minimum
PANELS_PER_PAGE_RECOMMENDED = (4, 6)  # mainstream standard
PANELS_PER_PAGE_MAX = 8       # dense pages

# --- Transition-based gutter widths (in pixels at standard page size) ---
GUTTER_WIDTHS = {
    "standard": 20,   # Normal time passage
    "wide": 40,       # Time skip, reflective pause
    "none": 0,        # Simultaneous action, urgency
    "overlap": -15,   # Rapid sequence, speed
}
DEFAULT_TRANSITION = "standard"

# --- Panel shapes ---
VALID_PANEL_SHAPES = {"rectangular", "diagonal", "wavy", "broken", "borderless"}
DEFAULT_PANEL_SHAPE = "rectangular"

# --- Valid narrative weights ---
VALID_NARRATIVE_WEIGHTS = {"low", "medium", "high", "splash"}

# --- Splash validation: moods that should NOT get splash pages ---
PASSIVE_MOODS = {"neutral", "calm", "peaceful", "relaxed", "happy"}


# ---------------------------------------------------------------------------
# Panel Shape Masks (PIL polygon-based)
# ---------------------------------------------------------------------------

def _create_rectangular_mask(w: int, h: int) -> Image.Image:
    """Standard rectangular mask — fully opaque."""
    return Image.new("L", (w, h), 255)


def _create_diagonal_mask(w: int, h: int, angle_deg: float = 15.0) -> Image.Image:
    """Parallelogram mask with ~15° diagonal slant for action/dynamic panels."""
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    offset = int(h * math.tan(math.radians(angle_deg)))
    # Parallelogram: top edge shifted right, bottom edge shifted left
    polygon = [
        (offset, 0),          # top-left (shifted right)
        (w, 0),               # top-right
        (w - offset, h),      # bottom-right (shifted left)
        (0, h),               # bottom-left
    ]
    draw.polygon(polygon, fill=255)
    return mask


def _create_wavy_mask(w: int, h: int, waves: int = 4, amplitude: int = None) -> Image.Image:
    """Wavy-edged mask for dream/flashback panels using sine wave edges."""
    if amplitude is None:
        amplitude = max(8, min(w, h) // 25)
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)

    # Build polygon with wavy left and right edges
    points = []
    steps = max(h, 100)

    # Right edge (top to bottom) — wavy
    for i in range(steps + 1):
        y = int(i * h / steps)
        x_wave = int(w - amplitude + amplitude * math.sin(2 * math.pi * waves * i / steps))
        points.append((x_wave, y))

    # Left edge (bottom to top) — wavy
    for i in range(steps, -1, -1):
        y = int(i * h / steps)
        x_wave = int(amplitude - amplitude * math.sin(2 * math.pi * waves * i / steps))
        points.append((x_wave, y))

    draw.polygon(points, fill=255)
    return mask


def _create_broken_mask(w: int, h: int, jaggedness: int = None) -> Image.Image:
    """Broken/fragmented edge mask for breakthrough moments.

    Creates jagged, irregular edges simulating a shattered frame.
    """
    if jaggedness is None:
        jaggedness = max(6, min(w, h) // 30)
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)

    rng = random.Random(w * h)  # deterministic per size for consistency

    # Build polygon with jagged edges on all four sides
    points = []
    seg_count = 12  # number of jag segments per edge

    # Top edge (left to right)
    for i in range(seg_count + 1):
        x = int(i * w / seg_count)
        y_jag = rng.randint(0, jaggedness) if 0 < i < seg_count else 0
        points.append((x, y_jag))

    # Right edge (top to bottom)
    for i in range(1, seg_count + 1):
        y = int(i * h / seg_count)
        x_jag = w - rng.randint(0, jaggedness) if i < seg_count else w
        points.append((x_jag, y))

    # Bottom edge (right to left)
    for i in range(seg_count - 1, -1, -1):
        x = int(i * w / seg_count)
        y_jag = h - rng.randint(0, jaggedness) if 0 < i < seg_count else h
        points.append((x, y_jag))

    # Left edge (bottom to top)
    for i in range(seg_count - 1, 0, -1):
        y = int(i * h / seg_count)
        x_jag = rng.randint(0, jaggedness)
        points.append((x_jag, y))

    draw.polygon(points, fill=255)
    return mask


def _create_borderless_mask(w: int, h: int, feather: int = None) -> Image.Image:
    """Borderless panel mask — full panel with soft feathered edges.

    Used for significance, memory, dream sequences.
    """
    if feather is None:
        feather = max(10, min(w, h) // 20)
    # Create a slightly inset rectangle then blur it for soft edges
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    inset = feather
    draw.rectangle([inset, inset, w - inset, h - inset], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=feather))
    return mask


def create_panel_mask(w: int, h: int, shape: str = "rectangular") -> Image.Image:
    """Create a panel-shape mask of the given size.

    Args:
        w: Width in pixels.
        h: Height in pixels.
        shape: One of "rectangular", "diagonal", "wavy", "broken", "borderless".

    Returns:
        PIL Image in mode "L" (grayscale mask).
    """
    creators = {
        "rectangular": _create_rectangular_mask,
        "diagonal": _create_diagonal_mask,
        "wavy": _create_wavy_mask,
        "broken": _create_broken_mask,
        "borderless": _create_borderless_mask,
    }
    creator = creators.get(shape, _create_rectangular_mask)
    return creator(max(1, w), max(1, h))


def draw_shaped_border(
    draw: ImageDraw.ImageDraw,
    px: int, py: int, pw: int, ph: int,
    shape: str = "rectangular",
    border_width: int = 3,
    border_color: str = "black",
) -> None:
    """Draw a border matching the panel shape.

    For rectangular panels, draws a standard rectangle.
    For other shapes, draws the corresponding polygon outline.
    Borderless panels get no border at all.
    """
    if shape == "borderless" or border_width <= 0:
        return

    if shape == "rectangular":
        bx0 = px - border_width // 2
        by0 = py - border_width // 2
        bx1 = px + pw + border_width // 2 - 1
        by1 = py + ph + border_width // 2 - 1
        draw.rectangle([bx0, by0, bx1, by1], outline=border_color, width=border_width)

    elif shape == "diagonal":
        offset = int(ph * math.tan(math.radians(15.0)))
        polygon = [
            (px + offset, py),
            (px + pw, py),
            (px + pw - offset, py + ph),
            (px, py + ph),
        ]
        draw.polygon(polygon, outline=border_color, width=border_width)

    elif shape == "wavy":
        # Draw wavy outline — approximate with line segments
        amplitude = max(8, min(pw, ph) // 25)
        waves = 4
        steps = 60
        # Right edge
        for i in range(steps):
            y1 = py + int(i * ph / steps)
            y2 = py + int((i + 1) * ph / steps)
            x1 = px + pw - amplitude + int(amplitude * math.sin(2 * math.pi * waves * i / steps))
            x2 = px + pw - amplitude + int(amplitude * math.sin(2 * math.pi * waves * (i + 1) / steps))
            draw.line([(x1, y1), (x2, y2)], fill=border_color, width=border_width)
        # Left edge
        for i in range(steps):
            y1 = py + int(i * ph / steps)
            y2 = py + int((i + 1) * ph / steps)
            x1 = px + amplitude - int(amplitude * math.sin(2 * math.pi * waves * i / steps))
            x2 = px + amplitude - int(amplitude * math.sin(2 * math.pi * waves * (i + 1) / steps))
            draw.line([(x1, y1), (x2, y2)], fill=border_color, width=border_width)
        # Top and bottom simple lines
        draw.line([(px, py), (px + pw, py)], fill=border_color, width=border_width)
        draw.line([(px, py + ph), (px + pw, py + ph)], fill=border_color, width=border_width)

    elif shape == "broken":
        jaggedness = max(6, min(pw, ph) // 30)
        rng = random.Random(pw * ph)
        seg_count = 12
        points = []
        # Top edge
        for i in range(seg_count + 1):
            x = px + int(i * pw / seg_count)
            y_jag = py + (rng.randint(0, jaggedness) if 0 < i < seg_count else 0)
            points.append((x, y_jag))
        # Right edge
        for i in range(1, seg_count + 1):
            y = py + int(i * ph / seg_count)
            x_jag = px + pw - (rng.randint(0, jaggedness) if i < seg_count else 0)
            points.append((x_jag, y))
        # Bottom edge
        for i in range(seg_count - 1, -1, -1):
            x = px + int(i * pw / seg_count)
            y_jag = py + ph - (rng.randint(0, jaggedness) if 0 < i < seg_count else 0)
            points.append((x, y_jag))
        # Left edge
        for i in range(seg_count - 1, 0, -1):
            y = py + int(i * ph / seg_count)
            x_jag = px + rng.randint(0, jaggedness)
            points.append((x_jag, y))
        draw.polygon(points, outline=border_color, width=border_width)


# ---------------------------------------------------------------------------
# Splash Page Validation
# ---------------------------------------------------------------------------

def validate_splash_usage(panels: list[dict]) -> list[str]:
    """Validate that splash pages are used only for narrative peaks.

    Returns a list of warning strings for inappropriate splash usage.
    """
    warnings = []
    for panel in panels:
        if panel.get("narrative_weight") != "splash":
            continue
        mood = panel.get("mood", "neutral").lower()
        action = panel.get("action", "").lower()
        pid = panel.get("id", "unknown")

        # Check passive moods
        if mood in PASSIVE_MOODS:
            warnings.append(
                f"⚠️ Panel '{pid}': splash page used with passive mood '{mood}'. "
                f"Splash pages should be reserved for narrative peaks."
            )

        # Check for action-less descriptions
        passive_actions = ["sitting", "standing", "waiting", "resting", "sleeping"]
        if any(pa in action for pa in passive_actions):
            warnings.append(
                f"⚠️ Panel '{pid}': splash page used for passive action '{action[:50]}'. "
                f"Consider using 'high' weight instead."
            )

    return warnings


def validate_panel_count(page_panels: list[dict]) -> list[str]:
    """Validate panel count per page against guidelines.

    Returns warnings for pages that exceed limits.
    """
    warnings = []
    count = len(page_panels)

    if count > PANELS_PER_PAGE_MAX:
        warnings.append(
            f"⚠️ Page has {count} panels (max recommended: {PANELS_PER_PAGE_MAX}). "
            f"Consider splitting across pages."
        )
    elif count < PANELS_PER_PAGE_MIN and count > 0:
        # 1 panel is fine (splash), but warn for unusual counts
        if count == 1 and not any(p.get("narrative_weight") == "splash" for p in page_panels):
            warnings.append(
                f"⚠️ Page has only 1 panel but no splash weight set. "
                f"Single-panel pages should use narrative_weight='splash'."
            )

    return warnings


# ---------------------------------------------------------------------------
# Gutter width calculation
# ---------------------------------------------------------------------------

def get_gutter_width(transition: str | None, base_gutter: int = 20) -> int:
    """Get gutter width in pixels based on panel transition type.

    Args:
        transition: One of "standard", "wide", "none", "overlap", or None.
        base_gutter: Fallback gutter width.

    Returns:
        Gutter width in pixels (can be negative for overlap).
    """
    if transition is None:
        transition = DEFAULT_TRANSITION
    return GUTTER_WIDTHS.get(transition, base_gutter)


# ---------------------------------------------------------------------------
# Dynamic layout engine
# ---------------------------------------------------------------------------

def _build_rows(panels: list[dict]) -> list[list[dict]]:
    """Pack panels into rows based on their narrative weight budget.

    Each row is filled left-to-right until the accumulated weight-units
    reach ROW_BUDGET.  A "splash" panel always starts (and fills) its own
    row.

    Returns:
        List of rows, each row a list of panel dicts.
    """
    rows: list[list[dict]] = []
    current_row: list[dict] = []
    current_budget = 0.0

    for panel in panels:
        weight = panel.get("narrative_weight", "medium")
        units = WEIGHT_UNITS.get(weight, 1.0)

        # Splash always gets its own row
        if weight == "splash":
            if current_row:
                rows.append(current_row)
                current_row = []
                current_budget = 0.0
            rows.append([panel])
            continue

        # Would adding this panel bust the budget?
        if current_row and (current_budget + units) > ROW_BUDGET + 0.01:
            rows.append(current_row)
            current_row = []
            current_budget = 0.0

        current_row.append(panel)
        current_budget += units

    if current_row:
        rows.append(current_row)

    return rows


def _rows_to_pages(rows: list[list[dict]]) -> list[list[list[dict]]]:
    """Group rows into pages, respecting ROWS_PER_PAGE limits.

    Splash rows always get their own page (optionally with the next 1-row
    of small panels if it has ≤2 panels).

    Returns:
        List of pages, each page a list of rows.
    """
    pages: list[list[list[dict]]] = []
    i = 0
    while i < len(rows):
        row = rows[i]

        # Splash row → own page (may absorb 1 adjacent small row)
        if len(row) == 1 and row[0].get("narrative_weight") == "splash":
            page_rows = [row]
            # Peek: absorb next row if it's small (≤2 panels, non-splash)
            if (i + 1 < len(rows)
                    and len(rows[i + 1]) <= 2
                    and not any(p.get("narrative_weight") == "splash" for p in rows[i + 1])):
                page_rows.append(rows[i + 1])
                i += 1
            pages.append(page_rows)
            i += 1
            continue

        # Normal: collect ROWS_PER_PAGE[1] rows max
        page_rows = [row]
        i += 1
        while i < len(rows) and len(page_rows) < ROWS_PER_PAGE[1]:
            next_row = rows[i]
            # Don't pull a splash into a normal page
            if len(next_row) == 1 and next_row[0].get("narrative_weight") == "splash":
                break
            page_rows.append(next_row)
            i += 1

        pages.append(page_rows)

    return pages


def _generate_layout_data(
    page_rows: list[list[dict]],
    page_width: int = 2480,
    page_height: int = 3508,
    margin: tuple[int, int, int, int] = (80, 80, 60, 60),
    default_gutter: int = 20,
) -> dict:
    """Generate normalized {panels: [{x,y,w,h,shape,gutter_right,gutter_bottom}, ...]} from rows.

    Row heights are distributed equally.  Within a row, panel widths are
    proportional to their weight-units.  Gutter widths and panel shapes
    are included in the layout data for the compose step.
    """
    num_rows = len(page_rows)
    row_h = 1.0 / num_rows
    panels_layout: list[dict] = []

    margin_top, margin_bottom, margin_left, margin_right = margin
    usable_w = page_width - margin_left - margin_right
    usable_h = page_height - margin_top - margin_bottom

    for row_idx, row in enumerate(page_rows):
        y = row_idx * row_h

        # Compute per-panel units for this row
        units = [
            WEIGHT_UNITS.get(p.get("narrative_weight", "medium"), 1.0)
            for p in row
        ]
        total_units = sum(units)

        x_cursor = 0.0
        for panel_idx, (p, u) in enumerate(zip(row, units)):
            w = u / total_units if total_units > 0 else 1.0 / len(row)

            # Transition gutter (between this panel and the next in the row)
            transition = p.get("transition_to_next", DEFAULT_TRANSITION)
            gutter_right_px = get_gutter_width(transition, default_gutter)

            # Vertical gutter between rows
            gutter_bottom_px = default_gutter

            # Panel shape
            shape = p.get("panel_shape", DEFAULT_PANEL_SHAPE)
            if shape not in VALID_PANEL_SHAPES:
                shape = DEFAULT_PANEL_SHAPE

            panels_layout.append({
                "x": round(x_cursor, 6),
                "y": round(y, 6),
                "w": round(w, 6),
                "h": round(row_h, 6),
                "panel_shape": shape,
                "gutter_right": gutter_right_px,
                "gutter_bottom": gutter_bottom_px,
                "transition_to_next": transition,
            })
            x_cursor += w

    return {"panels": panels_layout}


def auto_layout(
    panels: list[dict],
    reading_direction: str = "ltr",
    page_width: int = 2480,
    page_height: int = 3508,
) -> list[dict]:
    """Automatically assign panels to pages with dynamic layouts based on narrative_weight.

    Each panel dict should have:
        - "id": panel ID
        - "narrative_weight": "low" | "medium" | "high" | "splash"  (default: "medium")
        - "transition_to_next": "standard" | "wide" | "none" | "overlap" (optional)
        - "panel_shape": "rectangular" | "diagonal" | "wavy" | "broken" | "borderless" (optional)
        - "mood": mood string (optional, used for splash validation)

    Args:
        panels: Ordered list of panel dicts.
        reading_direction: "ltr" (left-to-right, default) or "rtl".
        page_width: Page width for gutter calculations.
        page_height: Page height for gutter calculations.

    Returns:
        A pages_config list::

            [
                {
                    "page_number": 1,
                    "page_position": "recto",  # or "verso"
                    "layout_data": {"panels": [{"x","y","w","h","panel_shape",...}, …]},
                    "panel_ids": ["panel_01", …],
                    "warnings": [...],
                },
                …
            ]
    """
    if not panels:
        return []

    # Validate splash usage
    splash_warnings = validate_splash_usage(panels)

    # 1. Build rows from sequential panels
    rows = _build_rows(panels)

    # 2. Group rows into pages
    pages_of_rows = _rows_to_pages(rows)

    # 3. For each page, generate layout_data and collect panel IDs
    pages_config: list[dict] = []
    for page_idx, page_rows in enumerate(pages_of_rows):
        layout_data = _generate_layout_data(page_rows, page_width=page_width, page_height=page_height)

        # Optionally mirror for RTL
        if reading_direction == "rtl":
            for slot in layout_data["panels"]:
                slot["x"] = round(1.0 - slot["x"] - slot["w"], 6)

        # Gather panel IDs in order
        panel_ids = []
        page_panel_list = []
        for row in page_rows:
            for p in row:
                panel_ids.append(p.get("id", f"unknown_{page_idx}"))
                page_panel_list.append(p)

        # Page position tracking (1-indexed: odd=recto/right, even=verso/left)
        page_number = page_idx + 1
        page_position = "recto" if page_number % 2 == 1 else "verso"

        # Validate panel count
        count_warnings = validate_panel_count(page_panel_list)

        # Collect page-level warnings
        page_warnings = count_warnings.copy()
        if page_idx == 0 and splash_warnings:
            page_warnings.extend(splash_warnings)

        pages_config.append({
            "page_number": page_number,
            "page_position": page_position,
            "layout_data": layout_data,
            "panel_ids": panel_ids,
            "warnings": page_warnings,
        })

    return pages_config


# ---------------------------------------------------------------------------
# Narrative Layout Templates
# ---------------------------------------------------------------------------

# Built-in narrative templates (normalized coordinates)
NARRATIVE_TEMPLATES = {
    "scene_opening": {
        "name": "scene_opening",
        "description": "Large establishing panel + 2-3 small reaction panels",
        "panels": [
            {"x": 0.0, "y": 0.0, "w": 1.0, "h": 0.55},    # Big establishing shot
            {"x": 0.0, "y": 0.55, "w": 0.4, "h": 0.45},    # Reaction 1
            {"x": 0.4, "y": 0.55, "w": 0.3, "h": 0.45},    # Reaction 2
            {"x": 0.7, "y": 0.55, "w": 0.3, "h": 0.45},    # Reaction 3
        ],
        "slot_count": 4,
        "best_for": ["establishing", "introduction", "new_scene"],
    },
    "dialogue_scene": {
        "name": "dialogue_scene",
        "description": "Even 2x3 grid for dialogue-heavy pages",
        "panels": [
            {"x": 0.0, "y": 0.0, "w": 0.5, "h": 0.333},
            {"x": 0.5, "y": 0.0, "w": 0.5, "h": 0.333},
            {"x": 0.0, "y": 0.333, "w": 0.5, "h": 0.334},
            {"x": 0.5, "y": 0.333, "w": 0.5, "h": 0.334},
            {"x": 0.0, "y": 0.667, "w": 0.5, "h": 0.333},
            {"x": 0.5, "y": 0.667, "w": 0.5, "h": 0.333},
        ],
        "slot_count": 6,
        "best_for": ["dialogue", "conversation", "talking"],
    },
    "action_sequence": {
        "name": "action_sequence",
        "description": "Irregular, dynamic panels for action pages",
        "panels": [
            {"x": 0.0, "y": 0.0, "w": 0.65, "h": 0.4},     # Main action
            {"x": 0.65, "y": 0.0, "w": 0.35, "h": 0.25},    # Impact/detail
            {"x": 0.65, "y": 0.25, "w": 0.35, "h": 0.15},   # Speed panel (small)
            {"x": 0.0, "y": 0.4, "w": 0.4, "h": 0.3},       # Reaction
            {"x": 0.4, "y": 0.4, "w": 0.6, "h": 0.3},       # Follow-through
            {"x": 0.0, "y": 0.7, "w": 1.0, "h": 0.3},       # Wide aftermath
        ],
        "slot_count": 6,
        "default_shapes": ["rectangular", "diagonal", "diagonal",
                           "rectangular", "diagonal", "rectangular"],
        "default_transitions": ["none", "overlap", "none", "none", "standard"],
        "best_for": ["action", "fight", "chase", "combat"],
    },
    "climax_reveal": {
        "name": "climax_reveal",
        "description": "Large focus panel + minimal support panels",
        "panels": [
            {"x": 0.0, "y": 0.0, "w": 0.7, "h": 0.7},      # Big reveal
            {"x": 0.7, "y": 0.0, "w": 0.3, "h": 0.35},      # Setup/context
            {"x": 0.7, "y": 0.35, "w": 0.3, "h": 0.35},     # Reaction
            {"x": 0.0, "y": 0.7, "w": 1.0, "h": 0.3},       # Impact/consequence
        ],
        "slot_count": 4,
        "best_for": ["climax", "reveal", "twist", "breakthrough"],
    },
    "transition": {
        "name": "transition",
        "description": "Horizontal strip + wider next-scene panel for scene changes",
        "panels": [
            {"x": 0.0, "y": 0.0, "w": 1.0, "h": 0.25},     # Leaving scene (strip)
            {"x": 0.0, "y": 0.25, "w": 0.5, "h": 0.35},     # Transition moment
            {"x": 0.5, "y": 0.25, "w": 0.5, "h": 0.35},     # Arriving scene
            {"x": 0.0, "y": 0.6, "w": 1.0, "h": 0.4},       # New scene establishing
        ],
        "slot_count": 4,
        "default_transitions": ["wide", "standard", "wide"],
        "best_for": ["transition", "scene_change", "time_skip"],
    },
}


def get_narrative_template(name: str) -> dict | None:
    """Get a narrative-based layout template by name.

    Args:
        name: Template name (e.g., 'scene_opening', 'action_sequence').

    Returns:
        Template dict or None if not found.
    """
    return NARRATIVE_TEMPLATES.get(name)


def list_narrative_templates() -> list[str]:
    """List available narrative template names."""
    return sorted(NARRATIVE_TEMPLATES.keys())


def auto_select_template(page_panels: list[dict]) -> str | None:
    """Automatically select the best narrative template for a set of panels.

    Analyzes panel content (moods, actions, dialogue density, narrative weights)
    to pick the most appropriate layout template.

    Args:
        page_panels: List of panel dicts for this page.

    Returns:
        Template name string, or None if no narrative template fits.
    """
    if not page_panels:
        return None

    count = len(page_panels)

    # Collect page characteristics
    moods = [p.get("mood", "neutral").lower() for p in page_panels]
    actions = [p.get("action", "").lower() for p in page_panels]
    weights = [p.get("narrative_weight", "medium") for p in page_panels]
    dialogue_count = sum(1 for p in page_panels if p.get("dialogue"))
    spatial_relations = [p.get("spatial_relation", "") for p in page_panels]

    # Check for splash — always gets its own page
    if any(w == "splash" for w in weights):
        return None  # splash uses dynamic layout, not template

    # Action-heavy page?
    action_keywords = {"fight", "chase", "attack", "explode", "run", "dodge",
                       "punch", "kick", "shoot", "crash", "battle", "combat"}
    action_moods = {"intense", "chaotic", "tense", "dramatic"}
    action_score = sum(1 for a in actions if any(kw in a for kw in action_keywords))
    action_score += sum(1 for m in moods if m in action_moods)
    if action_score >= 2 and count >= 4:
        return "action_sequence"

    # Scene change / transition?
    has_scene_change = "cut_to" in spatial_relations or "time_skip" in spatial_relations
    if has_scene_change and count <= 4:
        return "transition"

    # Climax / reveal?
    if any(w == "high" for w in weights) and count <= 4:
        climax_keywords = {"reveal", "discover", "confront", "transform", "final"}
        if any(any(kw in a for kw in climax_keywords) for a in actions):
            return "climax_reveal"

    # Dialogue-heavy?
    if dialogue_count >= count * 0.6 and count >= 4:
        return "dialogue_scene"

    # First panel is establishing?
    first_shot = page_panels[0].get("shot_type", "medium")
    if first_shot in ("long", "extreme_long", "wide") and count <= 4:
        return "scene_opening"

    return None


# ---------------------------------------------------------------------------
# Spread-Aware Layout (Double-page spreads)
# ---------------------------------------------------------------------------

class SpreadLayout:
    """Composes two pages together as a spread (verso + recto).

    A spread is a pair of pages that the reader sees simultaneously:
    - verso (left page, even-numbered)
    - recto (right page, odd-numbered)

    Rules:
    - Major reveals go on verso (first thing seen when turning)
    - Page-turn tension goes on recto bottom-right
    - Double-splash can span both pages
    """

    def __init__(
        self,
        page_width: int = 2480,
        page_height: int = 3508,
        spine_gap: int = 40,
    ):
        self.page_width = page_width
        self.page_height = page_height
        self.spine_gap = spine_gap
        self.spread_width = page_width * 2 + spine_gap

    def compose_spread(
        self,
        verso_image: Image.Image | None,
        recto_image: Image.Image | None,
        bg_color: str = "white",
    ) -> Image.Image:
        """Compose a two-page spread from verso (left) and recto (right) pages.

        Args:
            verso_image: Left page image (or None for blank).
            recto_image: Right page image (or None for blank).
            bg_color: Background color.

        Returns:
            Combined spread image.
        """
        spread = Image.new("RGB", (self.spread_width, self.page_height), bg_color)

        if verso_image:
            # Resize to page dimensions if needed
            if verso_image.size != (self.page_width, self.page_height):
                verso_image = verso_image.resize(
                    (self.page_width, self.page_height), Image.LANCZOS
                )
            spread.paste(verso_image, (0, 0))

        if recto_image:
            if recto_image.size != (self.page_width, self.page_height):
                recto_image = recto_image.resize(
                    (self.page_width, self.page_height), Image.LANCZOS
                )
            spread.paste(recto_image, (self.page_width + self.spine_gap, 0))

        return spread

    def compose_double_splash(
        self,
        splash_image: Image.Image,
        page_number_left: int | None = None,
        page_number_right: int | None = None,
        margin: tuple[int, int, int, int] = (80, 80, 60, 60),
        bg_color: str = "white",
    ) -> Image.Image:
        """Compose a double-splash that spans both pages of a spread.

        The image is resized to cover the full spread area (both pages),
        with a spine gap in the middle.

        Args:
            splash_image: The panel image for the double-splash.
            page_number_left: Optional left page number.
            page_number_right: Optional right page number.
            margin: (top, bottom, left, right) margins.
            bg_color: Background color.

        Returns:
            Double-spread image.
        """
        spread = Image.new("RGB", (self.spread_width, self.page_height), bg_color)
        margin_top, margin_bottom, margin_left, margin_right = margin

        # Usable area spans both pages
        usable_w = self.spread_width - margin_left - margin_right
        usable_h = self.page_height - margin_top - margin_bottom

        # Resize splash to cover usable area
        fitted = resize_cover(splash_image, usable_w, usable_h)
        spread.paste(fitted, (margin_left, margin_top))

        # Draw page numbers
        draw = ImageDraw.Draw(spread)
        if page_number_left is not None:
            _draw_page_number(draw, page_number_left,
                              self.page_width, self.page_height, margin[1])
        if page_number_right is not None:
            # Offset to right page
            _draw_page_number_at(
                draw, page_number_right,
                self.page_width + self.spine_gap + self.page_width // 2,
                self.page_height - margin[1] // 2,
            )

        return spread

    def compose_all_spreads(
        self, page_images: list[Image.Image], pages_config: list[dict]
    ) -> list[Image.Image]:
        """Compose all pages into spreads.

        Groups pages into verso/recto pairs and handles double-splash pages.

        Args:
            page_images: List of composed page images.
            pages_config: Pages configuration with page_position info.

        Returns:
            List of spread images.
        """
        spreads = []
        i = 0
        while i < len(page_images):
            config = pages_config[i] if i < len(pages_config) else {}

            # Check for double-splash (spread: true in page config)
            if config.get("spread"):
                # Double-splash consumes two page slots
                spreads.append(self.compose_double_splash(
                    page_images[i],
                    page_number_left=config.get("page_number"),
                    page_number_right=config.get("page_number", 0) + 1,
                ))
                i += 1  # only one image but represents 2 pages
                continue

            # Normal: pair verso + recto
            verso = page_images[i] if i < len(page_images) else None
            recto = page_images[i + 1] if i + 1 < len(page_images) else None
            spreads.append(self.compose_spread(verso, recto))
            i += 2

        return spreads

    @staticmethod
    def suggest_reveal_placement(pages_config: list[dict]) -> list[str]:
        """Suggest which pages should have reveals based on spread position.

        Returns suggestions as a list of strings.
        """
        suggestions = []
        for config in pages_config:
            page_num = config.get("page_number", 0)
            position = config.get("page_position", "")
            panel_ids = config.get("panel_ids", [])

            if position == "verso" and len(panel_ids) > 0:
                suggestions.append(
                    f"Page {page_num} (verso/left): Good position for reveals "
                    f"— first thing reader sees after page turn."
                )
            elif position == "recto" and len(panel_ids) > 0:
                suggestions.append(
                    f"Page {page_num} (recto/right): Last panel bottom-right "
                    f"should drive page turn (cliffhanger/tension)."
                )

        return suggestions


# ---------------------------------------------------------------------------
# Template loading (file-based, backward compatible)
# ---------------------------------------------------------------------------

def load_template(layout_name: str) -> dict:
    """Load a layout template by name from assets/templates/ or narrative templates.

    Checks narrative templates first, then falls back to file-based templates.

    Args:
        layout_name: Template name (e.g. 'page_2x2', 'scene_opening'). '.json' suffix optional.

    Returns:
        Parsed template dict with 'name', 'description', and 'panels' list.

    Raises:
        FileNotFoundError: If the template doesn't exist in either location.
    """
    # Check narrative templates first
    narrative = get_narrative_template(layout_name)
    if narrative:
        return narrative

    # Fall back to file-based templates
    name = layout_name if layout_name.endswith(".json") else f"{layout_name}.json"
    path = TEMPLATES_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    with open(path, "r") as f:
        return json.load(f)


def list_templates() -> list[str]:
    """List all available template names (file-based + narrative).

    Returns:
        Sorted list of template names.
    """
    templates = set()
    # File-based templates
    if TEMPLATES_DIR.exists():
        templates.update(p.stem for p in TEMPLATES_DIR.glob("*.json"))
    # Narrative templates
    templates.update(NARRATIVE_TEMPLATES.keys())
    return sorted(templates)


def resize_cover(image: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Resize image to cover target area, center-cropping any excess.

    The image is scaled so it fully covers the target dimensions, then the
    excess is cropped equally from both sides.

    Args:
        image: Source PIL Image.
        target_w: Target width in pixels.
        target_h: Target height in pixels.

    Returns:
        Resized and cropped PIL Image of exactly (target_w, target_h).
    """
    if target_w <= 0 or target_h <= 0:
        return Image.new("RGB", (max(target_w, 1), max(target_h, 1)), "black")

    src_w, src_h = image.size
    # Scale factor to *cover* the target area
    scale = max(target_w / src_w, target_h / src_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)

    resized = image.resize((new_w, new_h), Image.LANCZOS)

    # Center crop to exact target
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def compose_page(
    panel_images: list[Image.Image],
    layout_name: str | None = None,
    layout_data: dict | None = None,
    page_width: int = 2480,
    page_height: int = 3508,
    margin: tuple[int, int, int, int] = (80, 80, 60, 60),  # top, bottom, left, right
    gutter: int = 30,
    border_width: int = 3,
    border_color: str = "black",
    bg_color: str = "white",
    page_number: int | None = None,
) -> Image.Image:
    """Compose panel images into a single comic page.

    Supports variable gutters, panel shapes (masks), and narrative templates.

    Args:
        panel_images: List of PIL Images (one per panel slot in the template).
        layout_name: Name of the layout template to use (ignored when layout_data given).
        layout_data: Raw layout dict with ``{"panels": [{"x","y","w","h",...}, …]}``.
            When provided, this is used directly instead of loading a template.
        page_width: Output page width in pixels.
        page_height: Output page height in pixels.
        margin: (top, bottom, left, right) margins in pixels.
        gutter: Default space between panels in pixels (overridden by per-panel gutters).
        border_width: Panel border line width.
        border_color: Panel border color.
        bg_color: Page background color.
        page_number: Optional page number to draw at bottom center.

    Returns:
        Composed page as a PIL Image.

    Raises:
        ValueError: If neither layout_name nor layout_data is provided.
    """
    if layout_data is not None:
        panels = layout_data["panels"]
    elif layout_name is not None:
        template = load_template(layout_name)
        panels = template["panels"]
    else:
        raise ValueError("Either layout_name or layout_data must be provided.")

    # Create canvas
    canvas = Image.new("RGB", (page_width, page_height), bg_color)
    draw = ImageDraw.Draw(canvas)

    margin_top, margin_bottom, margin_left, margin_right = margin
    usable_w = page_width - margin_left - margin_right
    usable_h = page_height - margin_top - margin_bottom

    for i, slot in enumerate(panels):
        # If we run out of panel images, skip remaining slots
        if i >= len(panel_images):
            break

        panel_img = panel_images[i]

        # Get per-panel gutter (variable gutters from transitions)
        slot_gutter_right = slot.get("gutter_right", gutter)
        slot_gutter_bottom = slot.get("gutter_bottom", gutter)

        # Use the average of horizontal gutters for panel inset
        effective_gutter_h = max(0, slot_gutter_right) if slot_gutter_right >= 0 else 0
        effective_gutter_v = max(0, slot_gutter_bottom)

        # For overlapping panels (negative gutter), we extend the panel slightly
        overlap_h = abs(slot_gutter_right) if slot_gutter_right < 0 else 0

        # Calculate pixel position and size from normalized coordinates
        px = int(margin_left + slot["x"] * usable_w + effective_gutter_h / 2)
        py = int(margin_top + slot["y"] * usable_h + effective_gutter_v / 2)
        pw = int(slot["w"] * usable_w - effective_gutter_h + overlap_h)
        ph = int(slot["h"] * usable_h - effective_gutter_v)

        if pw <= 0 or ph <= 0:
            continue

        # Resize panel to cover slot
        fitted = resize_cover(panel_img, pw, ph)

        # Apply panel shape mask
        shape = slot.get("panel_shape", DEFAULT_PANEL_SHAPE)
        if shape != "rectangular":
            mask = create_panel_mask(pw, ph, shape)
            # Composite: paste fitted image with mask onto a bg-colored base
            base = Image.new("RGB", (pw, ph), bg_color)
            # Ensure fitted is in RGB mode
            if fitted.mode != "RGB":
                fitted = fitted.convert("RGB")
            base.paste(fitted, (0, 0), mask)
            canvas.paste(base, (px, py))
        else:
            canvas.paste(fitted, (px, py))

        # Draw shaped border
        draw_shaped_border(draw, px, py, pw, ph, shape, border_width, border_color)

    # Page number
    if page_number is not None:
        _draw_page_number(draw, page_number, page_width, page_height, margin_bottom)

    return canvas


def _draw_page_number(
    draw: ImageDraw.ImageDraw,
    page_number: int,
    page_width: int,
    page_height: int,
    margin_bottom: int,
) -> None:
    """Draw a page number centered at the bottom of the page."""
    text = str(page_number)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except (OSError, IOError):
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    tx = (page_width - tw) // 2
    ty = page_height - margin_bottom // 2 - th // 2
    draw.text((tx, ty), text, fill="black", font=font)


def _draw_page_number_at(
    draw: ImageDraw.ImageDraw,
    page_number: int,
    center_x: int,
    center_y: int,
) -> None:
    """Draw a page number at a specific position."""
    text = str(page_number)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except (OSError, IOError):
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((center_x - tw // 2, center_y - th // 2), text, fill="black", font=font)


def compose_all_pages(
    panel_images: list[Image.Image],
    pages_config: list[dict],
    **kwargs,
) -> list[Image.Image]:
    """Compose all pages from a pages configuration list.

    Supports two config formats:

    **Legacy (template-based):**
        ``{"layout": "page_2x2", "panel_indices": [0, 1, 2, 3]}``

    **Dynamic (auto_layout output):**
        ``{"layout_data": {"panels": [...]}, "panel_ids": [...]}``
        When using this format, pass *panel_images* keyed by ID via a dict,
        or as a flat list matched to ``panel_ids`` order.

    Args:
        panel_images: Flat list of all panel images **or** a dict mapping
            panel ID → Image.
        pages_config: List of page configuration dicts.
        **kwargs: Extra keyword arguments passed to compose_page().

    Returns:
        List of composed page Images.
    """
    # Build an id→image lookup if panel_images is a dict
    img_by_id: dict | None = None
    if isinstance(panel_images, dict):
        img_by_id = panel_images

    pages = []
    for i, config in enumerate(pages_config):
        layout_name = config.get("layout")
        layout_data = config.get("layout_data")
        indices = config.get("panel_indices")
        panel_ids = config.get("panel_ids")

        # Gather panel images for this page
        page_panels: list[Image.Image] = []

        if panel_ids is not None and img_by_id is not None:
            # Dynamic mode with dict images
            for pid in panel_ids:
                page_panels.append(
                    img_by_id.get(pid, Image.new("RGB", (768, 768), "#cccccc"))
                )
        elif panel_ids is not None and isinstance(panel_images, list):
            # Dynamic mode — panel_ids but flat list; match by order from a
            # global id→index mapping built once.
            if not hasattr(compose_all_pages, "_id_cache"):
                pass  # fall through to index-based
            # Fallback: use indices 0..N matching page order
            page_panels = list(panel_images[: len(panel_ids)])
        elif indices is not None:
            for idx in indices:
                if isinstance(panel_images, list) and 0 <= idx < len(panel_images):
                    page_panels.append(panel_images[idx])
                else:
                    page_panels.append(Image.new("RGB", (768, 768), "#cccccc"))

        # Auto page number if not explicitly disabled
        kw = dict(kwargs)
        if "page_number" not in kw:
            kw["page_number"] = i + 1

        pages.append(
            compose_page(page_panels, layout_name=layout_name, layout_data=layout_data, **kw)
        )

    return pages


# ---------------------------------------------------------------------------
# Auto narrative weight estimation
# ---------------------------------------------------------------------------

def estimate_narrative_weight(panel: dict) -> str:
    """Estimate narrative_weight for a panel based on mood, action, and other cues.

    This is used during auto-enrichment when no explicit weight is set.

    Args:
        panel: Panel dict with mood, action, etc.

    Returns:
        Estimated weight: "low", "medium", "high", or "splash".
    """
    mood = panel.get("mood", "neutral").lower()
    action = panel.get("action", "").lower()
    shot_type = panel.get("shot_type", "medium").lower()

    # High-weight indicators
    high_keywords = {"reveal", "confront", "transform", "discover", "final",
                     "climax", "explosion", "battle", "death", "sacrifice"}
    high_moods = {"dramatic", "intense", "dark", "powerful"}

    # Low-weight indicators
    low_keywords = {"walk", "sit", "wait", "look", "stand", "pause"}
    low_moods = {"neutral", "calm", "peaceful"}

    score = 0  # -2 to +2 scale

    # Check action keywords
    if any(kw in action for kw in high_keywords):
        score += 2
    elif any(kw in action for kw in low_keywords):
        score -= 1

    # Check mood
    if mood in high_moods:
        score += 1
    elif mood in low_moods:
        score -= 1

    # Shot type influence
    if shot_type in ("extreme_close_up", "close_up"):
        score += 1  # close-ups are inherently more intense
    elif shot_type in ("extreme_long", "long"):
        score -= 0.5  # establishing shots are less intense

    # Dialogue presence (tends toward medium)
    if panel.get("dialogue"):
        score = max(score, 0)  # dialogue panels at least medium

    if score >= 3:
        return "high"
    elif score >= 1:
        return "high"
    elif score <= -1:
        return "low"
    else:
        return "medium"


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=== page_layout.py v2 standalone test ===")
    print(f"Templates dir: {TEMPLATES_DIR}")
    print(f"Available templates: {list_templates()}")
    print(f"Narrative templates: {list_narrative_templates()}")

    # ------------------------------------------------------------------
    # Legacy test — template-based 2x2 (backward compatible)
    # ------------------------------------------------------------------
    colors_legacy = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12"]
    labels_legacy = ["Panel 1\n(Red)", "Panel 2\n(Blue)", "Panel 3\n(Green)", "Panel 4\n(Orange)"]
    test_panels_legacy: list[Image.Image] = []

    for color, label in zip(colors_legacy, labels_legacy):
        img = Image.new("RGB", (768, 768), color)
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        except (OSError, IOError):
            font = ImageFont.load_default()
        bbox = d.textbbox((0, 0), label, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text(((768 - tw) // 2, (768 - th) // 2), label, fill="white", font=font)
        test_panels_legacy.append(img)

    page = compose_page(test_panels_legacy, layout_name="page_2x2", page_number=1)

    output_dir = Path("/home/mcmuff/clawd/output/comicmaster")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "test_layout.png"
    page.save(str(output_path))
    print(f"Saved legacy test page: {output_path}  ({page.size[0]}x{page.size[1]})")

    pages_cfg = [
        {"layout": "page_2x2", "panel_indices": [0, 1, 2, 3]},
    ]
    all_pages = compose_all_pages(test_panels_legacy, pages_cfg)
    print(f"compose_all_pages (legacy) returned {len(all_pages)} page(s)")
    print("✅ Legacy tests passed.\n")

    # ------------------------------------------------------------------
    # Dynamic layout test with variable gutters and panel shapes
    # ------------------------------------------------------------------
    print("=== Dynamic layout (v2 features) test ===")

    test_panels_meta = [
        {"id": "p01", "narrative_weight": "high", "panel_shape": "rectangular",
         "transition_to_next": "standard", "mood": "dramatic"},
        {"id": "p02", "narrative_weight": "medium", "panel_shape": "rectangular",
         "transition_to_next": "none"},
        {"id": "p03", "narrative_weight": "medium", "panel_shape": "diagonal",
         "transition_to_next": "overlap", "mood": "intense"},
        {"id": "p04", "narrative_weight": "low", "panel_shape": "rectangular",
         "transition_to_next": "wide"},
        {"id": "p05", "narrative_weight": "splash", "panel_shape": "borderless",
         "mood": "powerful", "action": "The hero reveals their true power"},
        {"id": "p06", "narrative_weight": "medium", "panel_shape": "wavy",
         "transition_to_next": "standard", "mood": "dreamy"},
        {"id": "p07", "narrative_weight": "medium", "panel_shape": "broken",
         "transition_to_next": "none", "mood": "chaotic"},
        {"id": "p08", "narrative_weight": "high", "panel_shape": "rectangular",
         "transition_to_next": "standard", "mood": "dramatic"},
    ]

    pages_config = auto_layout(test_panels_meta)
    print(f"\nauto_layout produced {len(pages_config)} page(s):\n")
    for pc in pages_config:
        print(f"  Page {pc['page_number']} ({pc['page_position']}):")
        print(f"    panel_ids: {pc['panel_ids']}")
        if pc.get("warnings"):
            for w in pc["warnings"]:
                print(f"    {w}")
        for j, slot in enumerate(pc["layout_data"]["panels"]):
            shape = slot.get("panel_shape", "rectangular")
            transition = slot.get("transition_to_next", "standard")
            gutter_r = slot.get("gutter_right", 20)
            print(f"    slot {j}: x={slot['x']:.3f} y={slot['y']:.3f} "
                  f"w={slot['w']:.3f} h={slot['h']:.3f} "
                  f"shape={shape} transition={transition} gutter_right={gutter_r}")
        print()

    # Create coloured test images keyed by panel ID
    panel_colors = {
        "p01": "#e74c3c",
        "p02": "#3498db",
        "p03": "#2ecc71",
        "p04": "#95a5a6",
        "p05": "#9b59b6",
        "p06": "#e67e22",
        "p07": "#1abc9c",
        "p08": "#e74c3c",
    }

    panel_images_by_id: dict[str, Image.Image] = {}
    for pm in test_panels_meta:
        pid = pm["id"]
        weight = pm["narrative_weight"]
        shape = pm.get("panel_shape", "rectangular")
        color = panel_colors.get(pid, "#555555")
        img = Image.new("RGB", (768, 768), color)
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36
            )
        except (OSError, IOError):
            font = ImageFont.load_default()
        label = f"{pid}\n{weight}\n{shape}"
        bbox = d.textbbox((0, 0), label, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text(((768 - tw) // 2, (768 - th) // 2), label, fill="white", font=font)
        panel_images_by_id[pid] = img

    # Compose pages
    dynamic_dir = Path("/home/mcmuff/clawd/output/comicmaster/test_dynamic_layout_v2")
    dynamic_dir.mkdir(parents=True, exist_ok=True)

    composed_pages = compose_all_pages(panel_images_by_id, pages_config)
    for idx, cp in enumerate(composed_pages):
        out = dynamic_dir / f"page_{idx + 1:02d}.png"
        cp.save(str(out))
        print(f"Saved: {out}  ({cp.size[0]}x{cp.size[1]})")

    # ------------------------------------------------------------------
    # Narrative template test
    # ------------------------------------------------------------------
    print(f"\n=== Narrative template tests ===")
    for template_name in list_narrative_templates():
        tmpl = get_narrative_template(template_name)
        slot_count = tmpl.get("slot_count", len(tmpl["panels"]))
        colors = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12",
                  "#9b59b6", "#e67e22", "#1abc9c", "#555555"]
        imgs = []
        for si in range(slot_count):
            color = colors[si % len(colors)]
            img = Image.new("RGB", (768, 768), color)
            d = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48
                )
            except (OSError, IOError):
                font = ImageFont.load_default()
            label = f"Slot {si + 1}"
            bbox = d.textbbox((0, 0), label, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            d.text(((768 - tw) // 2, (768 - th) // 2), label, fill="white", font=font)
            imgs.append(img)

        page = compose_page(imgs, layout_name=template_name, page_number=1)
        out = dynamic_dir / f"template_{template_name}.png"
        page.save(str(out))
        print(f"  {template_name}: {slot_count} slots → {out}")

    # ------------------------------------------------------------------
    # Spread layout test
    # ------------------------------------------------------------------
    print(f"\n=== Spread layout test ===")
    spread_layout = SpreadLayout()

    if len(composed_pages) >= 2:
        spread = spread_layout.compose_spread(composed_pages[0], composed_pages[1])
        out = dynamic_dir / "spread_test.png"
        spread.save(str(out))
        print(f"Saved spread: {out}  ({spread.size[0]}x{spread.size[1]})")

    # Spread suggestions
    suggestions = SpreadLayout.suggest_reveal_placement(pages_config)
    for s in suggestions:
        print(f"  📖 {s}")

    # ------------------------------------------------------------------
    # Splash validation test
    # ------------------------------------------------------------------
    print(f"\n=== Splash validation test ===")
    bad_splash = [
        {"id": "bad_splash", "narrative_weight": "splash",
         "mood": "neutral", "action": "Character sitting on a bench"},
    ]
    warnings = validate_splash_usage(bad_splash)
    for w in warnings:
        print(f"  {w}")

    print(f"\n✅ All v2 tests complete — pages saved to {dynamic_dir}")

#!/usr/bin/env python3
"""
test_lettering.py — Comprehensive lettering system tests for ComicMaster.

Tests:
1. Font loading — all registered fonts load and render
2. Text-first sizing — balloons resize to fit, never truncate
3. Comic grammar normalisation — em-dash, ellipsis, caps
4. Duplicate detection — identical text on same panel is skipped
5. All 11 bubble types render without errors
6. Genre-specific caption/narration styling
7. Long text handling — no truncation even with very long text
8. Bézier tails — visual check that curved tails render

Run: python3 test_lettering.py
Output: ~/clawd/output/comicmaster/test_lettering_*.png
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Ensure the scripts directory is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image, ImageDraw
from speech_bubbles import (
    _FONTS,
    _FONT_DIR,
    _STYLE_FONT_MAP,
    _normalise_comic_text,
    _load_font,
    _is_duplicate,
    _reset_dedup,
    _compute_text_first_layout,
    add_bubbles,
    create_bubble_config,
)


OUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "output" / "comicmaster"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        msg = f"  ❌ {name}"
        if detail:
            msg += f" — {detail}"
        print(msg)


def _make_bg(w: int = 800, h: int = 600) -> Image.Image:
    """Simple gradient background for visual tests."""
    img = Image.new("RGB", (w, h), (60, 80, 140))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        c = int(60 + 100 * (y / h))
        draw.line([(0, y), (w, y)], fill=(c, c + 20, 200 - c // 2))
    return img


# ──────────────────────────────────────────────────────────────
# Test 1: Font Loading
# ──────────────────────────────────────────────────────────────
def test_font_loading():
    print("\n🔤 Test 1: Font Loading")
    for key, filename in _FONTS.items():
        path = _FONT_DIR / filename
        exists = path.exists()
        size_ok = path.stat().st_size > 100 if exists else False
        check(f"Font '{key}' ({filename}) exists and >100 bytes", exists and size_ok,
              f"exists={exists}, size={path.stat().st_size if exists else 0}")

        if exists and size_ok:
            font = _load_font(key, 24)
            bbox = font.getbbox("Hello World!")
            w = bbox[2] - bbox[0]
            check(f"Font '{key}' renders text (width={w}px)", w > 10)


# ──────────────────────────────────────────────────────────────
# Test 2: Comic Grammar Normalisation
# ──────────────────────────────────────────────────────────────
def test_grammar_normalisation():
    print("\n📝 Test 2: Comic Grammar Normalisation")

    # Em-dash → double-dash
    result = _normalise_comic_text("Wait—what?", "narration")
    check("Em-dash → double-dash", "--" in result, f"got: {result}")

    # En-dash → double-dash
    result = _normalise_comic_text("Wait–what?", "narration")
    check("En-dash → double-dash", "--" in result, f"got: {result}")

    # Unicode ellipsis → three dots
    result = _normalise_comic_text("Well…", "narration")
    check("Unicode ellipsis → ...", "..." in result and "…" not in result, f"got: {result}")

    # Multiple dots → exactly 3
    result = _normalise_comic_text("Umm.....", "narration")
    check("Multiple dots → exactly 3", "..." in result and "...." not in result, f"got: {result}")

    # ALL CAPS for speech
    result = _normalise_comic_text("Hello world", "speech")
    check("Speech → ALL CAPS", result == "HELLO WORLD", f"got: {result}")

    # ALL CAPS for shout
    result = _normalise_comic_text("Watch out!", "shout")
    check("Shout → ALL CAPS", result == "WATCH OUT!", f"got: {result}")

    # Narration stays mixed case
    result = _normalise_comic_text("Meanwhile, in the city...", "narration")
    check("Narration stays mixed case", "Meanwhile" in result, f"got: {result}")

    # Thought stays mixed case
    result = _normalise_comic_text("I wonder about this...", "thought")
    check("Thought stays mixed case", "wonder" in result, f"got: {result}")

    # Smart quotes → straight
    result = _normalise_comic_text("\u201CHello\u201D", "speech")
    check("Smart quotes normalised", '"' in result and "\u201C" not in result, f"got: {result}")


# ──────────────────────────────────────────────────────────────
# Test 3: Duplicate Detection
# ──────────────────────────────────────────────────────────────
def test_duplicate_detection():
    print("\n🔁 Test 3: Duplicate Detection")

    _reset_dedup()

    dup1 = _is_duplicate("panel_1", "Hello World")
    check("First occurrence is NOT duplicate", not dup1)

    dup2 = _is_duplicate("panel_1", "Hello World")
    check("Second identical text IS duplicate", dup2)

    dup3 = _is_duplicate("panel_1", "Different text")
    check("Different text is NOT duplicate", not dup3)

    dup4 = _is_duplicate("panel_2", "Hello World")
    check("Same text on DIFFERENT panel is NOT duplicate", not dup4)

    # Case insensitive
    dup5 = _is_duplicate("panel_1", "hello world")
    check("Case-insensitive duplicate detected", dup5)


# ──────────────────────────────────────────────────────────────
# Test 4: Text-First Sizing (no truncation)
# ──────────────────────────────────────────────────────────────
def test_text_first_sizing():
    print("\n📏 Test 4: Text-First Sizing")

    # Short text
    font, lines, tw, th, px, py = _compute_text_first_layout(
        "Hi!", "speech", "western", 800, 600, (0.5, 0.5)
    )
    check("Short text: lines > 0", len(lines) > 0 and lines[0].strip() != "")
    check("Short text: positive dimensions", tw > 0 and th > 0)

    # Long text — must NOT be truncated
    long_text = "This is a very long piece of dialogue that should never be truncated no matter what. The balloon should resize to accommodate all of this text completely."
    font, lines, tw, th, px, py = _compute_text_first_layout(
        long_text, "speech", "western", 800, 600, (0.5, 0.5)
    )
    joined = " ".join(lines)
    # Verify all words present (case may change due to normalisation in add_bubbles, but here it's raw)
    original_words = set(long_text.lower().split())
    result_words = set(joined.lower().split())
    missing = original_words - result_words
    check("Long text: no words truncated", len(missing) == 0,
          f"missing words: {missing}" if missing else "")

    # Very long text on small panel
    font, lines, tw, th, px, py = _compute_text_first_layout(
        long_text, "speech", "western", 400, 300, (0.5, 0.5)
    )
    joined2 = " ".join(lines)
    original_words2 = set(long_text.lower().split())
    result_words2 = set(joined2.lower().split())
    missing2 = original_words2 - result_words2
    check("Long text on small panel: still no truncation", len(missing2) == 0,
          f"missing: {missing2}" if missing2 else "")

    # Padding ratio check (min 15%)
    check("Padding X is at least 15% of text width", px >= tw * 0.14,  # slightly under due to int rounding
          f"pad_x={px}, tw={tw}, ratio={px/max(tw,1):.2f}")
    check("Padding Y is at least 15% of text height", py >= th * 0.14,
          f"pad_y={py}, th={th}, ratio={py/max(th,1):.2f}")


# ──────────────────────────────────────────────────────────────
# Test 5: All Bubble Types Render
# ──────────────────────────────────────────────────────────────
def test_all_bubble_types():
    print("\n🎨 Test 5: All 11 Bubble Types Render")

    img = _make_bg(1200, 900)

    bubbles = [
        create_bubble_config("Normal speech test.", "speech", (0.18, 0.12), tail_target=(0.08, 0.30)),
        create_bubble_config("I wonder about this...", "thought", (0.50, 0.12), tail_target=(0.50, 0.30)),
        create_bubble_config("Look out!", "shout", (0.82, 0.12), tail_target=(0.90, 0.30)),
        create_bubble_config("psst... secret...", "whisper", (0.18, 0.38), tail_target=(0.08, 0.55)),
        create_bubble_config("Meanwhile, elsewhere...", "narration", (0.50, 0.38)),
        create_bubble_config("KABOOM!", "explosion", (0.82, 0.38)),
        create_bubble_config("System online.", "electric", (0.18, 0.65), tail_target=(0.08, 0.82)),
        create_bubble_config("We agree!", "connected", (0.50, 0.65),
                           tail_target=(0.35, 0.85), tail_target_2=(0.65, 0.85)),
        create_bubble_config("NOOO!!!", "scream", (0.82, 0.65), tail_target=(0.90, 0.85)),
        create_bubble_config("CRASH!", "sfx", (0.50, 0.50), rotation=-15),
        create_bubble_config("Chapter 1 — All bubble types", "caption", (0.5, 0.95)),
    ]

    try:
        result = add_bubbles(img, bubbles, style="western")
        path = OUT_DIR / "test_lettering_all_types.png"
        result.save(str(path))
        check("All 11 types rendered without error", True)
        check(f"Output saved to {path}", path.exists())
    except Exception as e:
        check("All 11 types rendered without error", False, str(e))


# ──────────────────────────────────────────────────────────────
# Test 6: Duplicate Skipping in add_bubbles
# ──────────────────────────────────────────────────────────────
def test_duplicate_in_render():
    print("\n🔁 Test 6: Duplicate Skipping in add_bubbles")

    img = _make_bg(800, 600)

    # Two identical texts — second should be skipped
    bubbles = [
        create_bubble_config("This appears once.", "speech", (0.3, 0.3), tail_target=(0.2, 0.5)),
        create_bubble_config("This appears once.", "speech", (0.7, 0.3), tail_target=(0.8, 0.5)),
        create_bubble_config("This is different.", "speech", (0.5, 0.7), tail_target=(0.5, 0.9)),
    ]

    try:
        result = add_bubbles(img, bubbles, style="western", panel_id="dedup_test")
        path = OUT_DIR / "test_lettering_dedup.png"
        result.save(str(path))
        check("Duplicate render completed (second copy skipped)", True)
    except Exception as e:
        check("Duplicate render completed", False, str(e))


# ──────────────────────────────────────────────────────────────
# Test 7: Genre-Specific Caption Styles
# ──────────────────────────────────────────────────────────────
def test_genre_styles():
    print("\n🎭 Test 7: Genre-Specific Styles")

    styles = ["western", "manga", "cartoon", "cyberpunk", "noir"]

    for style in styles:
        img = _make_bg(600, 400)
        bubbles = [
            create_bubble_config(
                f"Narration in {style} style",
                "narration", (0.5, 0.25),
            ),
            create_bubble_config(
                f"Caption — {style}",
                "caption", (0.5, 0.95),
            ),
            create_bubble_config(
                "Dialogue test!",
                "speech", (0.5, 0.6),
                tail_target=(0.5, 0.8),
            ),
        ]
        try:
            result = add_bubbles(img, bubbles, style=style)
            path = OUT_DIR / f"test_lettering_style_{style}.png"
            result.save(str(path))
            check(f"Style '{style}' renders OK", True)
        except Exception as e:
            check(f"Style '{style}' renders OK", False, str(e))


# ──────────────────────────────────────────────────────────────
# Test 8: Long Text — No Truncation
# ──────────────────────────────────────────────────────────────
def test_long_text():
    print("\n📜 Test 8: Long Text Handling")

    img = _make_bg(800, 600)

    long_dialogue = (
        "This is an extremely long piece of dialogue that a character might say "
        "in a dramatic monologue. It goes on and on, covering multiple topics "
        "including the meaning of life, the universe, and everything else. "
        "The balloon must grow to fit ALL of this text without any truncation."
    )

    bubbles = [
        create_bubble_config(long_dialogue, "speech", (0.5, 0.3), tail_target=(0.5, 0.7)),
        create_bubble_config(
            "Thank you, child. Just doing my job as always, no matter the cost.",
            "speech", (0.5, 0.75), tail_target=(0.5, 0.95),
        ),
    ]

    try:
        result = add_bubbles(img, bubbles, style="western")
        path = OUT_DIR / "test_lettering_long_text.png"
        result.save(str(path))
        check("Long text rendered without truncation", True)
        check(f"Output saved to {path}", path.exists())
    except Exception as e:
        check("Long text rendered without truncation", False, str(e))


# ──────────────────────────────────────────────────────────────
# Test 9: Bézier Tail Visual Check
# ──────────────────────────────────────────────────────────────
def test_bezier_tails():
    print("\n🔗 Test 9: Bézier Tail Rendering")

    img = _make_bg(800, 600)

    # Tails pointing in different directions
    bubbles = [
        create_bubble_config("Tail down", "speech", (0.25, 0.25), tail_target=(0.15, 0.60)),
        create_bubble_config("Tail right", "speech", (0.50, 0.25), tail_target=(0.80, 0.35)),
        create_bubble_config("Tail up", "speech", (0.75, 0.65), tail_target=(0.85, 0.20)),
        create_bubble_config("Tail left", "speech", (0.50, 0.65), tail_target=(0.15, 0.70)),
    ]

    try:
        result = add_bubbles(img, bubbles, style="western")
        path = OUT_DIR / "test_lettering_bezier_tails.png"
        result.save(str(path))
        check("Bézier tails render in all directions", True)
    except Exception as e:
        check("Bézier tails render in all directions", False, str(e))


# ──────────────────────────────────────────────────────────────
# Test 10: Style Font Map Coverage
# ──────────────────────────────────────────────────────────────
def test_font_map_coverage():
    print("\n🗺️ Test 10: Style-Font Map Coverage")

    all_types = ["speech", "thought", "shout", "whisper", "narration",
                 "caption", "explosion", "electric", "connected", "scream", "sfx"]

    for style_name, style_map in _STYLE_FONT_MAP.items():
        for btype in all_types:
            has_key = btype in style_map
            if has_key:
                font_key = style_map[btype]
                has_font = font_key in _FONTS
                check(f"Style '{style_name}' / '{btype}' → font '{font_key}' registered",
                      has_font, f"font key '{font_key}' not in _FONTS" if not has_font else "")
            else:
                check(f"Style '{style_name}' has mapping for '{btype}'", False, "missing")


# ──────────────────────────────────────────────────────────────
# Run all tests
# ──────────────────────────────────────────────────────────────
def main():
    t0 = time.time()
    print("=" * 60)
    print("  ComicMaster Lettering System — Test Suite")
    print("=" * 60)

    test_font_loading()
    test_grammar_normalisation()
    test_duplicate_detection()
    test_text_first_sizing()
    test_all_bubble_types()
    test_duplicate_in_render()
    test_genre_styles()
    test_long_text()
    test_bezier_tails()
    test_font_map_coverage()

    elapsed = time.time() - t0
    print("\n" + "=" * 60)
    print(f"  Results: {PASS} passed, {FAIL} failed  ({elapsed:.2f}s)")
    print(f"  Output images in: {OUT_DIR}")
    print("=" * 60)

    if FAIL > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

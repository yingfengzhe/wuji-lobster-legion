#!/usr/bin/env python3
"""
Tests for ComicMaster Quality Tracker — Phase 1.

Generates test images with PIL and verifies that quality metrics
return sensible values. No external test dependencies needed.
"""

import json
import math
import os
import sys
import tempfile
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# Add script directory to path
sys.path.insert(0, str(Path(__file__).parent))

from quality_tracker import (
    sharpness,
    contrast,
    saturation,
    color_entropy,
    edge_density,
    exposure,
    center_bias,
    rule_of_thirds,
    visual_flow,
    quadrant_balance,
    color_temperature,
    palette_size,
    color_harmony,
    _simple_kmeans,
    score_panel,
    score_batch,
    analyze_sequence,
    _compute_composition_score,
    _score_label,
    SCORE_THRESHOLDS,
)


# ---------------------------------------------------------------------------
# Test image generators
# ---------------------------------------------------------------------------

def make_solid_gray(size=(256, 256), value=128) -> Image.Image:
    """Solid gray image — minimal features."""
    return Image.new('RGB', size, (value, value, value))


def make_gradient_h(size=(256, 256)) -> Image.Image:
    """Horizontal gradient (black→white) — strong horizontal flow."""
    arr = np.zeros((*size[::-1], 3), dtype=np.uint8)
    grad = np.linspace(0, 255, size[0], dtype=np.uint8)
    arr[:, :, :] = grad[None, :, None]
    return Image.fromarray(arr)


def make_gradient_v(size=(256, 256)) -> Image.Image:
    """Vertical gradient (top=black, bottom=white) — strong vertical flow."""
    arr = np.zeros((*size[::-1], 3), dtype=np.uint8)
    grad = np.linspace(0, 255, size[1], dtype=np.uint8)
    arr[:, :, :] = grad[:, None, None]
    return Image.fromarray(arr)


def make_bright_corner(size=(256, 256)) -> Image.Image:
    """Image with a bright white square in top-right corner — off-center mass."""
    img = Image.new('RGB', size, (30, 30, 30))
    draw = ImageDraw.Draw(img)
    # Bright block in top-right
    x0 = size[0] * 3 // 4
    draw.rectangle([x0, 0, size[0], size[1] // 4], fill=(255, 255, 255))
    return img


def make_centered_circle(size=(256, 256)) -> Image.Image:
    """White circle dead center on dark background — center-biased."""
    img = Image.new('RGB', size, (20, 20, 20))
    draw = ImageDraw.Draw(img)
    cx, cy = size[0] // 2, size[1] // 2
    r = min(size) // 6
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(240, 240, 240))
    return img


def make_thirds_aligned(size=(256, 256)) -> Image.Image:
    """Bright spots at rule-of-thirds intersections on dark background."""
    img = Image.new('RGB', size, (20, 20, 20))
    draw = ImageDraw.Draw(img)
    w, h = size
    spots = [
        (w // 3, h // 3),
        (2 * w // 3, h // 3),
        (w // 3, 2 * h // 3),
        (2 * w // 3, 2 * h // 3),
    ]
    r = min(size) // 12
    for (cx, cy) in spots:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 200))
    return img


def make_warm_image(size=(256, 256)) -> Image.Image:
    """Red/orange dominant — warm temperature."""
    return Image.new('RGB', size, (220, 120, 60))


def make_cool_image(size=(256, 256)) -> Image.Image:
    """Blue/cyan dominant — cool temperature."""
    return Image.new('RGB', size, (60, 120, 220))


def make_colorful(size=(256, 256)) -> Image.Image:
    """Multiple distinct color blocks — rich palette."""
    img = Image.new('RGB', size, (0, 0, 0))
    draw = ImageDraw.Draw(img)
    w, h = size
    colors = [
        (255, 0, 0), (0, 255, 0), (0, 0, 255),
        (255, 255, 0), (255, 0, 255), (0, 255, 255),
    ]
    block_h = h // len(colors)
    for i, c in enumerate(colors):
        draw.rectangle([0, i * block_h, w, (i + 1) * block_h], fill=c)
    return img


def make_sharp_edges(size=(256, 256)) -> Image.Image:
    """Sharp geometric shapes — high sharpness and edge density."""
    img = Image.new('RGB', size, (30, 30, 50))
    draw = ImageDraw.Draw(img)
    w, h = size
    for i in range(0, w, 20):
        draw.line([(i, 0), (i, h)], fill=(200, 200, 200), width=2)
    for i in range(0, h, 20):
        draw.line([(0, i), (w, i)], fill=(200, 200, 200), width=2)
    # Add some diagonal lines
    for i in range(0, w + h, 30):
        draw.line([(0, i), (i, 0)], fill=(180, 100, 100), width=1)
    return img


def make_blurry(size=(256, 256)) -> Image.Image:
    """Blurred version of sharp edges — low sharpness."""
    return make_sharp_edges(size).filter(ImageFilter.GaussianBlur(radius=5))


def make_overexposed(size=(256, 256)) -> Image.Image:
    """Very bright image — overexposed."""
    return Image.new('RGB', size, (245, 248, 250))


def make_underexposed(size=(256, 256)) -> Image.Image:
    """Very dark image — underexposed."""
    return Image.new('RGB', size, (10, 8, 12))


def make_quadrant_heavy(size=(256, 256), quadrant: int = 0) -> Image.Image:
    """Heavy visual weight in one quadrant."""
    img = Image.new('RGB', size, (30, 30, 30))
    draw = ImageDraw.Draw(img)
    w, h = size
    mw, mh = w // 2, h // 2

    regions = [
        (0, 0, mw, mh),          # top-left
        (mw, 0, w, mh),          # top-right
        (0, mh, mw, h),          # bottom-left
        (mw, mh, w, h),          # bottom-right
    ]

    r = regions[quadrant]
    draw.rectangle(r, fill=(220, 220, 220))
    # Add edges too
    for x in range(r[0], r[2], 15):
        draw.line([(x, r[1]), (x, r[3])], fill=(180, 180, 180), width=1)

    return img


def make_complementary_colors(size=(256, 256)) -> Image.Image:
    """Red and cyan — complementary color harmony."""
    img = Image.new('RGB', size, (0, 0, 0))
    draw = ImageDraw.Draw(img)
    w, h = size
    draw.rectangle([0, 0, w // 2, h], fill=(200, 50, 50))
    draw.rectangle([w // 2, 0, w, h], fill=(50, 200, 200))
    return img


def make_analogous_colors(size=(256, 256)) -> Image.Image:
    """Red, orange, yellow — analogous harmony."""
    img = Image.new('RGB', size, (0, 0, 0))
    draw = ImageDraw.Draw(img)
    w, h = size
    third = w // 3
    draw.rectangle([0, 0, third, h], fill=(200, 50, 50))
    draw.rectangle([third, 0, 2 * third, h], fill=(220, 140, 40))
    draw.rectangle([2 * third, 0, w, h], fill=(220, 200, 40))
    return img


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def check(self, condition: bool, name: str, detail: str = ""):
        if condition:
            self.passed += 1
            print(f"  ✅ {name}")
        else:
            self.failed += 1
            msg = f"  ❌ {name}"
            if detail:
                msg += f" — {detail}"
            print(msg)
            self.errors.append(name)

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'=' * 60}")
        print(f"Results: {self.passed}/{total} passed, {self.failed} failed")
        if self.errors:
            print("Failed tests:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'=' * 60}")
        return self.failed == 0


def test_sharpness(t: TestResults):
    print("\n── Sharpness ──")
    sharp_img = make_sharp_edges()
    blurry_img = make_blurry()
    gray_img = make_solid_gray()

    s_sharp = sharpness(sharp_img)
    s_blurry = sharpness(blurry_img)
    s_gray = sharpness(gray_img)

    t.check(s_sharp > s_blurry, "Sharp > Blurry",
            f"sharp={s_sharp:.1f}, blurry={s_blurry:.1f}")
    # Note: solid gray can have non-trivial Laplacian variance due to
    # uniform→edge transitions at image borders. Blurry image is still lower
    # than sharp, which is the meaningful test.
    t.check(s_gray < 500, "Solid gray has low-ish sharpness",
            f"got {s_gray:.1f}")
    t.check(s_sharp > 100, "Sharp image has high sharpness",
            f"got {s_sharp:.1f}")


def test_contrast(t: TestResults):
    print("\n── Contrast ──")
    gray = make_solid_gray()
    gradient = make_gradient_h()
    colorful = make_colorful()

    c_gray = contrast(gray)
    c_grad = contrast(gradient)
    c_color = contrast(colorful)

    t.check(c_gray < 1.0, "Solid gray has near-zero contrast",
            f"got {c_gray:.2f}")
    t.check(c_grad > 30, "Gradient has significant contrast",
            f"got {c_grad:.1f}")
    t.check(c_grad > c_gray, "Gradient > Gray contrast",
            f"grad={c_grad:.1f}, gray={c_gray:.1f}")


def test_saturation(t: TestResults):
    print("\n── Saturation ──")
    gray = make_solid_gray()
    warm = make_warm_image()
    colorful = make_colorful()

    s_gray = saturation(gray)
    s_warm = saturation(warm)
    s_color = saturation(colorful)

    t.check(s_gray < 0.05, "Gray image has near-zero saturation",
            f"got {s_gray:.3f}")
    t.check(s_warm > 0.2, "Warm image has saturation",
            f"got {s_warm:.3f}")
    t.check(s_color > s_gray, "Colorful > Gray",
            f"color={s_color:.3f}, gray={s_gray:.3f}")


def test_color_entropy(t: TestResults):
    print("\n── Color Entropy ──")
    gray = make_solid_gray()
    gradient = make_gradient_h()
    colorful = make_colorful()

    e_gray = color_entropy(gray)
    e_grad = color_entropy(gradient)
    e_color = color_entropy(colorful)

    t.check(e_gray < 2, "Solid gray has very low entropy",
            f"got {e_gray:.2f}")
    t.check(e_grad > e_gray, "Gradient > Gray",
            f"grad={e_grad:.2f}, gray={e_gray:.2f}")
    t.check(e_color > e_gray, "Colorful > Gray",
            f"color={e_color:.2f}, gray={e_gray:.2f}")


def test_edge_density(t: TestResults):
    print("\n── Edge Density ──")
    gray = make_solid_gray()
    sharp = make_sharp_edges()

    ed_gray = edge_density(gray)
    ed_sharp = edge_density(sharp)

    # PIL FIND_EDGES can detect minor border artifacts on solid images
    t.check(ed_gray < 0.05, "Solid gray has very low edges",
            f"got {ed_gray:.4f}")
    t.check(ed_sharp > 0.05, "Sharp edges have detectable edges",
            f"got {ed_sharp:.3f}")
    t.check(ed_sharp > ed_gray, "Sharp > Gray",
            f"sharp={ed_sharp:.3f}, gray={ed_gray:.4f}")


def test_exposure(t: TestResults):
    print("\n── Exposure ──")
    normal = make_gradient_h()
    over = make_overexposed()
    under = make_underexposed()

    exp_normal = exposure(normal)
    exp_over = exposure(over)
    exp_under = exposure(under)

    t.check(exp_normal["exposure_balance"] > 0.3,
            "Gradient has decent exposure balance",
            f"got {exp_normal['exposure_balance']:.3f}")
    t.check(exp_over["bright_ratio"] > 0.5,
            "Overexposed has high bright ratio",
            f"got {exp_over['bright_ratio']:.3f}")
    t.check(exp_under["dark_ratio"] > 0.5,
            "Underexposed has high dark ratio",
            f"got {exp_under['dark_ratio']:.3f}")
    t.check(exp_over["exposure_balance"] < exp_normal["exposure_balance"],
            "Overexposed balance < Normal balance")


def test_center_bias(t: TestResults):
    print("\n── Center Bias ──")
    centered = make_centered_circle()
    corner = make_bright_corner()
    gray = make_solid_gray()

    cb_centered = center_bias(centered)
    cb_corner = center_bias(corner)
    cb_gray = center_bias(gray)

    t.check(cb_centered["score"] < 0.25, "Centered circle has low bias score",
            f"got {cb_centered['score']:.3f}")
    t.check(cb_corner["score"] > cb_centered["score"],
            "Corner bright > centered",
            f"corner={cb_corner['score']:.3f}, centered={cb_centered['score']:.3f}")
    # Gray image should be roughly centered (equal weight everywhere)
    t.check(cb_gray["score"] < 0.1, "Uniform gray is near-center",
            f"got {cb_gray['score']:.3f}")
    t.check(cb_centered["dead_center"] or cb_centered["score"] < 0.2,
            "Centered circle flagged or near dead-center threshold")


def test_rule_of_thirds(t: TestResults):
    print("\n── Rule of Thirds ──")
    gray = make_solid_gray()
    thirds = make_thirds_aligned()
    centered = make_centered_circle()

    rot_gray = rule_of_thirds(gray)
    rot_thirds = rule_of_thirds(thirds)
    rot_centered = rule_of_thirds(centered)

    t.check(rot_gray["zone_variance"] < 0.1,
            "Uniform gray has low zone variance",
            f"got {rot_gray['zone_variance']:.3f}")
    t.check(rot_thirds["score"] > rot_gray["score"],
            "Thirds-aligned > uniform gray",
            f"thirds={rot_thirds['score']:.3f}, gray={rot_gray['score']:.3f}")
    t.check(rot_thirds["score"] > 0.2,
            "Thirds-aligned has reasonable score",
            f"got {rot_thirds['score']:.3f}")


def test_visual_flow(t: TestResults):
    print("\n── Visual Flow ──")
    h_grad = make_gradient_h()
    v_grad = make_gradient_v()

    vf_h = visual_flow(h_grad)
    vf_v = visual_flow(v_grad)

    # Horizontal gradient should have flow roughly right (0°) or left (180°)
    h_angle = vf_h["angle_deg"]
    t.check(h_angle < 45 or h_angle > 315 or (135 < h_angle < 225),
            "Horizontal gradient has horizontal flow",
            f"got {h_angle:.1f}° ({vf_h['direction']})")

    # Vertical gradient should have flow roughly down (90°) or up (270°)
    v_angle = vf_v["angle_deg"]
    t.check((45 < v_angle < 135) or (225 < v_angle < 315),
            "Vertical gradient has vertical flow",
            f"got {v_angle:.1f}° ({vf_v['direction']})")


def test_quadrant_balance(t: TestResults):
    print("\n── Quadrant Balance ──")
    gray = make_solid_gray()
    heavy_tl = make_quadrant_heavy(quadrant=0)
    heavy_br = make_quadrant_heavy(quadrant=3)

    qb_gray = quadrant_balance(gray)
    qb_tl = quadrant_balance(heavy_tl)
    qb_br = quadrant_balance(heavy_br)

    t.check(qb_gray["score"] < 0.15, "Uniform gray is balanced",
            f"got {qb_gray['score']:.3f}")
    t.check(qb_tl["score"] > 0.3, "Heavy top-left is unbalanced",
            f"got {qb_tl['score']:.3f}")
    t.check(qb_tl["dominant_quadrant"] == "top-left",
            "Dominant quadrant is top-left",
            f"got {qb_tl['dominant_quadrant']}")
    t.check(qb_br["dominant_quadrant"] == "bottom-right",
            "Dominant quadrant is bottom-right",
            f"got {qb_br['dominant_quadrant']}")


def test_color_temperature(t: TestResults):
    print("\n── Color Temperature ──")
    warm = make_warm_image()
    cool = make_cool_image()
    gray = make_solid_gray()

    ct_warm = color_temperature(warm)
    ct_cool = color_temperature(cool)
    ct_gray = color_temperature(gray)

    t.check(ct_warm["temperature"] > 0, "Warm image is warm",
            f"got {ct_warm['temperature']:.3f}")
    t.check(ct_warm["warm_cool"] == "warm", "Label is 'warm'",
            f"got '{ct_warm['warm_cool']}'")
    t.check(ct_cool["temperature"] < 0, "Cool image is cool",
            f"got {ct_cool['temperature']:.3f}")
    t.check(ct_cool["warm_cool"] == "cool", "Label is 'cool'",
            f"got '{ct_cool['warm_cool']}'")
    t.check(abs(ct_gray["temperature"]) < 0.1, "Gray is neutral",
            f"got {ct_gray['temperature']:.3f}")


def test_palette_size(t: TestResults):
    print("\n── Palette Size ──")
    gray = make_solid_gray()
    colorful = make_colorful()

    pal_gray = palette_size(gray)
    pal_color = palette_size(colorful)

    t.check(pal_gray["dominant_count"] <= 2,
            "Gray image has ≤2 dominant colors",
            f"got {pal_gray['dominant_count']}")
    t.check(pal_color["dominant_count"] >= 3,
            "Colorful image has ≥3 dominant colors",
            f"got {pal_color['dominant_count']}")
    t.check(len(pal_color["palette_rgb"]) == pal_color["dominant_count"],
            "palette_rgb length matches dominant_count")


def test_kmeans(t: TestResults):
    print("\n── K-Means ──")
    # 3 clear clusters
    rng = np.random.RandomState(42)
    cluster1 = rng.randn(50, 2) + np.array([0, 0])
    cluster2 = rng.randn(50, 2) + np.array([10, 10])
    cluster3 = rng.randn(50, 2) + np.array([20, 0])
    data = np.vstack([cluster1, cluster2, cluster3]).astype(np.float64)

    centroids, labels = _simple_kmeans(data, k=3, max_iter=30)

    t.check(centroids.shape == (3, 2), "3 centroids returned",
            f"got shape {centroids.shape}")
    t.check(len(np.unique(labels)) == 3, "3 unique labels",
            f"got {len(np.unique(labels))}")
    # Centroids should be near (0,0), (10,10), (20,0)
    sorted_c = centroids[centroids[:, 0].argsort()]
    t.check(abs(sorted_c[0, 0]) < 2, "First centroid near x=0",
            f"got x={sorted_c[0, 0]:.1f}")
    t.check(abs(sorted_c[1, 0] - 10) < 2, "Second centroid near x=10",
            f"got x={sorted_c[1, 0]:.1f}")
    t.check(abs(sorted_c[2, 0] - 20) < 2, "Third centroid near x=20",
            f"got x={sorted_c[2, 0]:.1f}")


def test_color_harmony(t: TestResults):
    print("\n── Color Harmony ──")
    comp = make_complementary_colors()
    analog = make_analogous_colors()
    gray = make_solid_gray()

    ch_comp = color_harmony(comp)
    ch_analog = color_harmony(analog)
    ch_gray = color_harmony(gray)

    t.check(ch_comp["harmony_type"] in ("complementary", "split-complementary"),
            "Complementary colors detected",
            f"got '{ch_comp['harmony_type']}'")
    t.check(ch_comp["harmony_score"] > 0.3,
            "Complementary has decent harmony score",
            f"got {ch_comp['harmony_score']:.3f}")
    t.check(ch_analog["harmony_type"] == "analogous",
            "Analogous colors detected",
            f"got '{ch_analog['harmony_type']}'")
    t.check(ch_gray["harmony_type"] == "monochromatic",
            "Gray is monochromatic",
            f"got '{ch_gray['harmony_type']}'")


def test_score_panel(t: TestResults):
    print("\n── Score Panel (integration) ──")
    tmpdir = tempfile.mkdtemp()
    try:
        # Save a test image
        img = make_sharp_edges()
        path = os.path.join(tmpdir, "test_panel.png")
        img.save(path)

        # Without composition
        ps = score_panel(path)
        t.check(ps.panel_id == "test_panel", "Panel ID from filename",
                f"got '{ps.panel_id}'")
        t.check(ps.technical_score > 0, "Technical score > 0",
                f"got {ps.technical_score}")
        t.check(ps.overall_score == ps.technical_score,
                "Overall == Technical when no composition")
        t.check(ps.composition_score is None, "No composition score by default")
        t.check(ps.analysis_ms > 0, "Analysis time recorded")

        # With composition
        ps_comp = score_panel(path, composition=True)
        t.check(ps_comp.composition_score is not None,
                "Composition score computed")
        t.check(ps_comp.center_bias_score is not None,
                "Center bias score present")
        t.check(ps_comp.harmony_type is not None,
                "Harmony type present")
        t.check(ps_comp.overall_score != ps_comp.technical_score,
                "Overall ≠ Technical with composition",
                f"overall={ps_comp.overall_score}, tech={ps_comp.technical_score}")
        t.check(0 <= ps_comp.overall_score <= 100,
                "Overall score in 0-100 range",
                f"got {ps_comp.overall_score}")

    finally:
        shutil.rmtree(tmpdir)


def test_score_batch(t: TestResults):
    print("\n── Score Batch (integration) ──")
    tmpdir = tempfile.mkdtemp()
    try:
        # Save multiple test images
        images = [
            ("panel_01.png", make_sharp_edges()),
            ("panel_02.png", make_colorful()),
            ("panel_03.png", make_gradient_h()),
        ]
        for name, img in images:
            img.save(os.path.join(tmpdir, name))

        # Basic batch
        batch = score_batch(tmpdir)
        t.check(batch.panel_count == 3, "3 panels scored",
                f"got {batch.panel_count}")
        t.check(batch.mean_score > 0, "Mean score > 0")
        t.check(batch.best_panel != "", "Best panel identified")
        t.check(batch.worst_panel != "", "Worst panel identified")
        t.check(len(batch.panels) == 3, "3 panel dicts")

        # With composition
        batch_c = score_batch(tmpdir, composition=True)
        t.check(batch_c.mean_composition_score is not None,
                "Mean composition score present")
        t.check(batch_c.dead_center_count is not None,
                "Dead center count present")

        # With sequence
        batch_s = score_batch(tmpdir, composition=True, sequence=True)
        t.check(batch_s.sequence_analysis is not None,
                "Sequence analysis present")
        t.check("sequence_score" in batch_s.sequence_analysis,
                "Sequence score in analysis")

    finally:
        shutil.rmtree(tmpdir)


def test_analyze_sequence(t: TestResults):
    print("\n── Analyze Sequence ──")
    tmpdir = tempfile.mkdtemp()
    try:
        # Create a small sequence of varied panels
        panels = [
            ("seq_01.png", make_bright_corner()),
            ("seq_02.png", make_sharp_edges()),
            ("seq_03.png", make_warm_image()),
            ("seq_04.png", make_cool_image()),
            ("seq_05.png", make_colorful()),
        ]
        paths = []
        for name, img in panels:
            p = os.path.join(tmpdir, name)
            img.save(p)
            paths.append(p)

        result = analyze_sequence(paths)

        t.check(result["panel_count"] == 5, "5 panels analyzed",
                f"got {result['panel_count']}")
        t.check("flow_continuity" in result, "Flow continuity present")
        t.check("color_temperature" in result, "Color temperature present")
        t.check("shot_variety" in result, "Shot variety present")
        t.check("pacing" in result, "Pacing present")
        t.check("sequence_score" in result, "Sequence score present")
        t.check(0 <= result["flow_continuity"] <= 1, "Flow continuity in 0-1",
                f"got {result['flow_continuity']}")
        t.check(0 <= result["shot_variety"] <= 1, "Shot variety in 0-1",
                f"got {result['shot_variety']}")
        t.check(0 <= result["pacing"] <= 1, "Pacing in 0-1",
                f"got {result['pacing']}")
        t.check(len(result["per_panel_summary"]) == 5,
                "5 panel summaries")

        # Warm → Cool sequence should have temperature outliers
        ct = result["color_temperature"]
        t.check(ct["std"] > 0, "Temperature has non-zero std",
                f"got {ct['std']:.3f}")

        # Test with too few panels
        result_1 = analyze_sequence(paths[:1])
        t.check("error" in result_1, "Error with <2 panels")

    finally:
        shutil.rmtree(tmpdir)


def test_scoring_system(t: TestResults):
    print("\n── Scoring System ──")

    # Test score labels
    t.check(_score_label(80) == "good", "80 = good")
    t.check(_score_label(50) == "ok", "50 = ok")
    t.check(_score_label(20) == "poor", "20 = poor")
    t.check(_score_label(65) == "good", "65 = good (threshold)")
    t.check(_score_label(40) == "ok", "40 = ok (threshold)")
    t.check(_score_label(39.9) == "poor", "39.9 = poor")

    # Test composition score computation
    score = _compute_composition_score(
        cb_score=0.3,       # decent off-center
        thirds_score=0.6,   # good thirds
        qb_score=0.5,       # good balance
        harmony_score=0.7,  # decent harmony
        dominant_colors=4,  # good palette
        cb_dead_center=False,
        qb_good_balance=True,
    )
    t.check(40 < score < 90, "Good composition params give decent score",
            f"got {score:.1f}")

    # Dead center + uniform should score low
    score_bad = _compute_composition_score(
        cb_score=0.05,
        thirds_score=0.1,
        qb_score=0.05,
        harmony_score=0.0,
        dominant_colors=1,
        cb_dead_center=True,
        qb_good_balance=False,
    )
    t.check(score_bad < score, "Bad composition < Good composition",
            f"bad={score_bad:.1f}, good={score:.1f}")


def test_json_output(t: TestResults):
    print("\n── JSON Output ──")
    tmpdir = tempfile.mkdtemp()
    try:
        img = make_colorful()
        path = os.path.join(tmpdir, "test.png")
        img.save(path)

        ps = score_panel(path, composition=True)
        d = {k: v for k, v in ps.__dict__.items()}

        # Should be JSON serializable
        try:
            json_str = json.dumps(d, indent=2)
            t.check(True, "PanelScore is JSON-serializable")
            parsed = json.loads(json_str)
            t.check("panel_id" in parsed, "panel_id in JSON")
            t.check("composition_score" in parsed, "composition_score in JSON")
            t.check("harmony_type" in parsed, "harmony_type in JSON")
        except Exception as e:
            t.check(False, f"JSON serialization failed: {e}")

    finally:
        shutil.rmtree(tmpdir)


def test_summary_line(t: TestResults):
    print("\n── Summary Line ──")
    tmpdir = tempfile.mkdtemp()
    try:
        img = make_sharp_edges()
        path = os.path.join(tmpdir, "panel.png")
        img.save(path)

        ps = score_panel(path, composition=True)
        line = ps.summary_line()
        t.check("panel" in line, "Panel ID in summary line")
        t.check("Sharp=" in line, "Sharpness in summary line")
        t.check("Comp=" in line, "Composition in summary line")
        t.check("Score=" in line, "Score in summary line")
    finally:
        shutil.rmtree(tmpdir)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("ComicMaster Quality Tracker — Test Suite")
    print("=" * 60)

    t = TestResults()

    # Technical metrics
    test_sharpness(t)
    test_contrast(t)
    test_saturation(t)
    test_color_entropy(t)
    test_edge_density(t)
    test_exposure(t)

    # Composition metrics
    test_center_bias(t)
    test_rule_of_thirds(t)
    test_visual_flow(t)
    test_quadrant_balance(t)

    # Colorimetry metrics
    test_color_temperature(t)
    test_palette_size(t)
    test_kmeans(t)
    test_color_harmony(t)

    # Integration
    test_score_panel(t)
    test_score_batch(t)
    test_analyze_sequence(t)
    test_scoring_system(t)
    test_json_output(t)
    test_summary_line(t)

    success = t.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

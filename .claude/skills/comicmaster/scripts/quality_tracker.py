#!/usr/bin/env python3
"""
ComicMaster Quality Tracker — Phase 1: PIL-Based Metrics + Composition Analysis

Zero-dependency image quality metrics using only PIL/Pillow and numpy.
Measures: sharpness, contrast, saturation, color entropy, edge density,
exposure balance, composition (center bias, rule of thirds, visual flow,
quadrant balance), colorimetry (temperature, palette size, harmony).

Usage:
    python quality_tracker.py <panels_dir> [--output scores.json] [--verbose]
    python quality_tracker.py panel.png  # single image
    python quality_tracker.py panels/ --composition --report
    python quality_tracker.py panels/ --sequence --report
    python quality_tracker.py panels/ --composition --sequence --report

Designed to run after every comic generation to track quality over time.
"""

from __future__ import annotations

import argparse
import colorsys
import json
import math
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageFilter, ImageStat

# ---------------------------------------------------------------------------
# Metric functions — PIL + numpy only, no external dependencies
# ---------------------------------------------------------------------------

# === Technical Metrics (original) ===

def sharpness(img: Image.Image) -> float:
    """Laplacian variance — higher = sharper image.

    Applies a Laplacian kernel (second derivative) and measures the
    variance of the result. Blurry images have low variance.

    Typical values: 50-200 (blurry), 200-1000 (normal), 1000+ (very sharp).
    """
    gray = np.array(img.convert('L'), dtype=np.float64)
    # Laplacian kernel (3×3)
    laplacian = np.array([
        [0,  1, 0],
        [1, -4, 1],
        [0,  1, 0],
    ], dtype=np.float64)
    # Manual 2D convolution (avoid scipy dependency)
    h, w = gray.shape
    lap = np.zeros_like(gray)
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            ky, kx = dy + 1, dx + 1
            if laplacian[ky, kx] == 0:
                continue
            src_y0 = max(0, dy)
            src_y1 = min(h, h + dy)
            dst_y0 = max(0, -dy)
            dst_y1 = min(h, h - dy)
            src_x0 = max(0, dx)
            src_x1 = min(w, w + dx)
            dst_x0 = max(0, -dx)
            dst_x1 = min(w, w - dx)
            lap[dst_y0:dst_y1, dst_x0:dst_x1] += (
                laplacian[ky, kx] * gray[src_y0:src_y1, src_x0:src_x1]
            )
    return float(lap.var())


def contrast(img: Image.Image) -> float:
    """RMS contrast of luminance channel.

    Standard deviation of pixel intensities in grayscale.
    Range: 0-127 (0 = flat gray, 127 = maximum contrast).
    """
    gray = img.convert('L')
    stat = ImageStat.Stat(gray)
    return float(stat.stddev[0])


def saturation(img: Image.Image) -> float:
    """Mean saturation from HSV color space.

    Range: 0.0-1.0 (0 = grayscale, 1 = fully saturated).
    """
    hsv = img.convert('HSV')
    s_channel = np.array(hsv)[:, :, 1]
    return float(s_channel.mean() / 255.0)


def color_entropy(img: Image.Image) -> float:
    """Entropy of the combined RGB histogram — measures color diversity.

    Range: 0-~16 bits (higher = more diverse colors).
    Typical good images: 10-14.
    """
    hist = img.histogram()  # 768 bins (256 per channel for RGB)
    hist = np.array(hist, dtype=np.float64)
    total = hist.sum()
    if total == 0:
        return 0.0
    hist = hist / total
    hist = hist[hist > 0]
    return float(-np.sum(hist * np.log2(hist)))


def edge_density(img: Image.Image) -> float:
    """Fraction of pixels that are edges (using PIL FIND_EDGES filter).

    Range: 0.0-1.0 (0 = no edges, 1 = all edges).
    Typical: 0.1-0.5 for detailed images.
    """
    edges = img.convert('L').filter(ImageFilter.FIND_EDGES)
    arr = np.array(edges)
    threshold = 30  # pixel intensity threshold to count as edge
    return float((arr > threshold).mean())


def exposure(img: Image.Image) -> dict:
    """Check for under/overexposure.

    Returns dict with:
    - dark_ratio: fraction of very dark pixels (< 20)
    - bright_ratio: fraction of very bright pixels (> 235)
    - mean_luminance: average luminance (0-255)
    - exposure_balance: 0-1 score (1 = perfect, 0 = severely over/underexposed)
    """
    gray = np.array(img.convert('L'))
    dark = float((gray < 20).mean())
    bright = float((gray > 235).mean())
    mean_lum = float(gray.mean())

    # Exposure balance: penalize extreme dark/bright ratios
    balance = 1.0 - min(1.0, dark * 3 + bright * 3)
    balance = max(0.0, balance)
    # Also penalize very dark or very bright mean luminance
    lum_deviation = abs(mean_lum - 128) / 128
    balance *= (1.0 - lum_deviation * 0.5)

    return {
        "dark_ratio": round(dark, 4),
        "bright_ratio": round(bright, 4),
        "mean_luminance": round(mean_lum, 1),
        "exposure_balance": round(balance, 3),
    }


# === Composition Metrics (new) ===

def center_bias(img: Image.Image) -> dict:
    """Measure how strongly visual weight is concentrated in the center.

    Computes the "Center of Visual Mass" — the brightness-weighted
    centroid of the image. Returns the distance from dead center
    normalized to [0, 1].

    Score 0 = visual mass at dead center (bad for comics)
    Score 1 = visual mass at extreme edge (strong off-center composition)

    Flags panels where score < 0.2 as "dead center composition".
    """
    gray = np.array(img.convert('L'), dtype=np.float64)
    h, w = gray.shape

    # Create coordinate grids (normalized 0-1)
    y_coords = np.linspace(0, 1, h).reshape(-1, 1)
    x_coords = np.linspace(0, 1, w).reshape(1, -1)

    total_weight = gray.sum()
    if total_weight == 0:
        return {"score": 0.0, "center_x": 0.5, "center_y": 0.5, "dead_center": True}

    # Weighted centroid
    cx = float((gray * x_coords).sum() / total_weight)
    cy = float((gray * y_coords).sum() / total_weight)

    # Distance from center (0.5, 0.5), max possible is ~0.707 (corner)
    dist = math.sqrt((cx - 0.5) ** 2 + (cy - 0.5) ** 2)
    # Normalize to 0-1 (max distance from center to corner is sqrt(0.5))
    score = min(1.0, dist / math.sqrt(0.5))

    return {
        "score": round(score, 3),
        "center_x": round(cx, 3),
        "center_y": round(cy, 3),
        "dead_center": score < 0.2,
    }


def rule_of_thirds(img: Image.Image) -> dict:
    """Analyze rule-of-thirds alignment.

    Divides the image into a 3x3 grid and measures:
    1. Zone variance: how different the 9 zones are in brightness
       (high variance = good thirds usage)
    2. Hotspot alignment: whether the brightest/most contrasty zones
       are near the 4 intersection points

    Returns:
    - zone_variance: 0-1 normalized variance of zone means
    - hotspot_alignment: 0-1 how close hotspots are to intersection points
    - score: combined 0-1 score (higher = better thirds usage)
    """
    gray = np.array(img.convert('L'), dtype=np.float64)
    h, w = gray.shape

    # Divide into 3x3 grid
    zone_h = h // 3
    zone_w = w // 3
    zone_means = []
    zone_contrasts = []
    for row in range(3):
        for col in range(3):
            y0 = row * zone_h
            y1 = (row + 1) * zone_h if row < 2 else h
            x0 = col * zone_w
            x1 = (col + 1) * zone_w if col < 2 else w
            zone = gray[y0:y1, x0:x1]
            zone_means.append(float(zone.mean()))
            zone_contrasts.append(float(zone.std()))

    zone_means = np.array(zone_means)
    zone_contrasts = np.array(zone_contrasts)

    # Zone variance (normalized by max possible variance)
    variance = float(zone_means.std())
    # Max std for 0-255 range across 9 zones is ~127
    zone_var_norm = min(1.0, variance / 60.0)

    # Hotspot alignment: check if highest-energy zones are near intersections
    # The 4 intersection zones in a 3x3 grid are indices: 0,2,6,8 (corners)
    # and their adjacent zones. In comics, intersections matter most at
    # zone indices corresponding to thirds crossings.
    # Map: intersection points are at borders between zones.
    # Zones adjacent to intersection points: 0,1,2,3,4,5,6,7,8 all touch at
    # least one, but the key zones (corners of center zone) are 0,2,6,8.

    # Compute "energy" per zone (brightness * contrast)
    zone_energy = zone_means * (zone_contrasts + 1)
    # Normalize
    if zone_energy.max() > 0:
        zone_energy_norm = zone_energy / zone_energy.max()
    else:
        zone_energy_norm = zone_energy

    # Intersection-adjacent zones (the 4 that touch the thirds crossings most)
    # In a 3x3 grid, the thirds intersections are at the borders of
    # zones (0,1,3,4), (1,2,4,5), (3,4,6,7), (4,5,7,8)
    # So the "non-center" zones touching intersections are: 0,1,2,3,5,6,7,8
    # The center zone (4) is the least interesting for thirds.
    # Weight: corner zones (0,2,6,8) are at intersections, give them higher weight
    intersection_weights = np.array([
        1.0, 0.5, 1.0,   # top-left, top-center, top-right
        0.5, 0.0, 0.5,   # middle-left, center, middle-right
        1.0, 0.5, 1.0,   # bottom-left, bottom-center, bottom-right
    ])

    # How much energy aligns with intersection zones vs center
    # If all zones have equal energy, alignment is meaningless → score 0
    energy_range = float(zone_energy_norm.max() - zone_energy_norm.min())
    if energy_range < 0.05:
        # Near-uniform energy: no meaningful hotspot alignment
        hotspot_align = 0.0
    else:
        alignment = float(np.sum(zone_energy_norm * intersection_weights))
        max_alignment = float(intersection_weights.sum())
        hotspot_align = alignment / max_alignment if max_alignment > 0 else 0

    # Combined score
    score = 0.5 * zone_var_norm + 0.5 * hotspot_align

    return {
        "zone_variance": round(zone_var_norm, 3),
        "hotspot_alignment": round(hotspot_align, 3),
        "score": round(score, 3),
    }


def visual_flow(img: Image.Image) -> dict:
    """Compute the dominant visual flow direction.

    Uses Sobel-like horizontal and vertical gradient kernels to estimate
    where the dominant edges point, giving a rough direction of visual flow.

    Returns:
    - angle_deg: dominant flow angle in degrees (0° = right, 90° = down)
    - magnitude: strength of the dominant flow (0-1 normalized)
    - direction: human-readable direction label
    """
    gray = np.array(img.convert('L'), dtype=np.float64)
    h, w = gray.shape

    # Sobel-like gradient estimation using numpy
    # Apply a simple 3x3 Sobel kernel via shifted arrays
    # Sobel X kernel: [[-1,0,1],[-2,0,2],[-1,0,1]]
    # Sobel Y kernel: [[-1,-2,-1],[0,0,0],[1,2,1]]
    gx = np.zeros_like(gray)
    gy = np.zeros_like(gray)

    if h > 2 and w > 2:
        # Sobel X
        gx[1:-1, 1:-1] = (
            -gray[:-2, :-2] + gray[:-2, 2:]
            - 2 * gray[1:-1, :-2] + 2 * gray[1:-1, 2:]
            - gray[2:, :-2] + gray[2:, 2:]
        )
        # Sobel Y
        gy[1:-1, 1:-1] = (
            -gray[:-2, :-2] - 2 * gray[:-2, 1:-1] - gray[:-2, 2:]
            + gray[2:, :-2] + 2 * gray[2:, 1:-1] + gray[2:, 2:]
        )

    # Gradient magnitude per pixel
    magnitudes = np.sqrt(gx ** 2 + gy ** 2)

    # Only consider significant gradients (top 25%)
    threshold = np.percentile(magnitudes, 75)
    mask = magnitudes >= max(threshold, 1e-6)

    if mask.sum() == 0:
        return {"angle_deg": 0.0, "magnitude": 0.0, "direction": "none"}

    # Weighted sum of gradient vectors (weighted by magnitude)
    mean_gx = float((gx[mask] * magnitudes[mask]).sum())
    mean_gy = float((gy[mask] * magnitudes[mask]).sum())

    # Angle (atan2: 0° = right, 90° = down in image coords)
    angle_rad = math.atan2(mean_gy, mean_gx)
    angle_deg = math.degrees(angle_rad) % 360

    # Magnitude normalized
    total_mag = math.sqrt(mean_gx ** 2 + mean_gy ** 2)
    max_possible = float(magnitudes[mask].sum()) * 255
    norm_mag = min(1.0, total_mag / max_possible) if max_possible > 0 else 0.0

    # Human-readable direction
    dirs = [
        (0, "right"), (45, "down-right"), (90, "down"),
        (135, "down-left"), (180, "left"), (225, "up-left"),
        (270, "up"), (315, "up-right"), (360, "right"),
    ]
    direction = min(dirs, key=lambda d: abs(d[0] - angle_deg))[1]

    return {
        "angle_deg": round(angle_deg, 1),
        "magnitude": round(norm_mag, 4),
        "direction": direction,
    }


def quadrant_balance(img: Image.Image) -> dict:
    """Measure visual weight distribution across 4 quadrants.

    Computes a combined visual weight per quadrant from brightness,
    contrast, and edge density. Returns how unbalanced the distribution is.

    Score 0 = perfectly even (boring)
    Score 1 = all weight in one quadrant (extreme imbalance)
    Good comics: 0.3-0.7 (asymmetric balance)
    """
    gray = np.array(img.convert('L'), dtype=np.float64)
    edges = np.array(img.convert('L').filter(ImageFilter.FIND_EDGES), dtype=np.float64)
    h, w = gray.shape

    mid_y, mid_x = h // 2, w // 2

    quadrants = [
        (gray[:mid_y, :mid_x], edges[:mid_y, :mid_x]),     # top-left
        (gray[:mid_y, mid_x:], edges[:mid_y, mid_x:]),      # top-right
        (gray[mid_y:, :mid_x], edges[mid_y:, :mid_x]),      # bottom-left
        (gray[mid_y:, mid_x:], edges[mid_y:, mid_x:]),      # bottom-right
    ]

    weights = []
    for g, e in quadrants:
        brightness = float(g.mean()) / 255.0
        local_contrast = float(g.std()) / 127.0
        local_edges = float((e > 30).mean())
        # Combined weight
        weight = 0.3 * brightness + 0.4 * local_contrast + 0.3 * local_edges
        weights.append(weight)

    weights = np.array(weights)
    total = weights.sum()
    if total == 0:
        return {
            "score": 0.0,
            "quadrant_weights": [0.0, 0.0, 0.0, 0.0],
            "dominant_quadrant": "none",
            "good_balance": False,
        }

    # Normalize to proportions
    proportions = weights / total

    # Imbalance score: max proportion minus uniform (0.25)
    # If perfectly uniform, max prop = 0.25, score = 0
    # If all in one quadrant, max prop = 1.0, score = 1
    imbalance = (float(proportions.max()) - 0.25) / 0.75

    labels = ["top-left", "top-right", "bottom-left", "bottom-right"]
    dominant = labels[int(proportions.argmax())]

    return {
        "score": round(imbalance, 3),
        "quadrant_weights": [round(float(w), 3) for w in weights],
        "dominant_quadrant": dominant,
        "good_balance": 0.3 <= imbalance <= 0.7,
    }


# === Colorimetry Metrics (new) ===

def color_temperature(img: Image.Image) -> dict:
    """Measure warm vs cool color bias.

    Compares average red channel vs blue channel intensity.
    Positive = warm (red-biased), negative = cool (blue-biased).

    Returns:
    - temperature: -1.0 (very cool) to 1.0 (very warm)
    - warm_cool: label "warm", "cool", or "neutral"
    - red_mean, blue_mean: raw channel averages
    """
    arr = np.array(img.convert('RGB'), dtype=np.float64)
    red_mean = float(arr[:, :, 0].mean())
    blue_mean = float(arr[:, :, 2].mean())

    # Temperature: (R - B) / 255, normalized to [-1, 1]
    diff = red_mean - blue_mean
    # Normalize: max diff is 255
    temp = diff / 255.0
    # Scale up for more sensitivity (typical diff is small)
    temp = max(-1.0, min(1.0, temp * 3.0))

    if temp > 0.15:
        label = "warm"
    elif temp < -0.15:
        label = "cool"
    else:
        label = "neutral"

    return {
        "temperature": round(temp, 3),
        "warm_cool": label,
        "red_mean": round(red_mean, 1),
        "blue_mean": round(blue_mean, 1),
    }


def _simple_kmeans(data: np.ndarray, k: int = 6, max_iter: int = 20,
                   seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    """Simple K-Means clustering (no sklearn dependency).

    Args:
        data: (N, D) array of data points.
        k: Number of clusters.
        max_iter: Maximum iterations.
        seed: Random seed for reproducibility.

    Returns:
        (centroids, labels) — centroids (k, D) and labels (N,)
    """
    rng = np.random.RandomState(seed)
    n = data.shape[0]
    # Initialize centroids from random data points
    indices = rng.choice(n, k, replace=False)
    centroids = data[indices].copy()

    labels = np.zeros(n, dtype=np.int32)

    for _ in range(max_iter):
        # Assign each point to nearest centroid
        # Compute distances: (N, 1, D) - (1, K, D) → (N, K, D) → (N, K)
        dists = np.sum((data[:, None, :] - centroids[None, :, :]) ** 2, axis=2)
        new_labels = dists.argmin(axis=1).astype(np.int32)

        if np.array_equal(new_labels, labels):
            break
        labels = new_labels

        # Recompute centroids
        for c in range(k):
            mask = labels == c
            if mask.sum() > 0:
                centroids[c] = data[mask].mean(axis=0)

    return centroids, labels


def palette_size(img: Image.Image) -> dict:
    """Estimate the number of dominant colors using K-Means clustering.

    Downsamples the image, runs K-Means with k=8, then counts clusters
    that represent a significant fraction of pixels (>5%).

    Returns:
    - dominant_count: number of significant color clusters
    - palette_rgb: list of dominant colors as [R, G, B]
    - palette_fractions: fraction of pixels per dominant cluster
    """
    # Downsample for speed
    small = img.convert('RGB').resize((64, 64), Image.LANCZOS)
    pixels = np.array(small, dtype=np.float64).reshape(-1, 3)

    k = 8
    centroids, labels = _simple_kmeans(pixels, k=k, max_iter=25)

    # Count pixels per cluster
    counts = np.bincount(labels, minlength=k)
    fractions = counts / counts.sum()

    # Significant clusters (>5% of pixels)
    significant_mask = fractions > 0.05
    dominant = centroids[significant_mask]
    dom_fractions = fractions[significant_mask]

    # Sort by fraction descending
    order = np.argsort(-dom_fractions)
    dominant = dominant[order]
    dom_fractions = dom_fractions[order]

    return {
        "dominant_count": int(dominant.shape[0]),
        "palette_rgb": [[int(c) for c in rgb] for rgb in dominant],
        "palette_fractions": [round(float(f), 3) for f in dom_fractions],
    }


def _rgb_to_hue(r: float, g: float, b: float) -> float:
    """Convert RGB (0-255) to hue (0-360 degrees)."""
    h, _, _ = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    return h * 360.0


def _hue_distance(h1: float, h2: float) -> float:
    """Shortest angular distance between two hues (0-180)."""
    d = abs(h1 - h2) % 360
    return min(d, 360 - d)


def color_harmony(img: Image.Image) -> dict:
    """Analyze color harmony of dominant palette.

    Checks if dominant colors form harmonious relationships on the color wheel:
    - Complementary: 2 colors ~180° apart
    - Analogous: colors within ~30° of each other
    - Triadic: 3 colors ~120° apart
    - Split-complementary: 1 color + 2 colors ~150° from it

    Returns:
    - harmony_type: detected harmony type (or "none")
    - harmony_score: 0-1 (how well colors match a harmony pattern)
    - hues: list of dominant hue angles
    """
    pal = palette_size(img)
    if pal["dominant_count"] < 2:
        return {"harmony_type": "monochromatic", "harmony_score": 1.0, "hues": []}

    colors = pal["palette_rgb"]
    # Filter out near-gray colors (low saturation) — they don't affect harmony
    chromatic = []
    for rgb in colors:
        r, g, b = rgb
        _, s, _ = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        if s > 0.15:
            chromatic.append(rgb)

    if len(chromatic) < 2:
        return {"harmony_type": "monochromatic", "harmony_score": 0.8, "hues": []}

    hues = [_rgb_to_hue(*c) for c in chromatic]

    best_score = 0.0
    best_type = "none"

    # Check analogous: all hues within 60° span
    hues_sorted = sorted(hues)
    max_span = max(_hue_distance(hues_sorted[i], hues_sorted[j])
                   for i in range(len(hues_sorted))
                   for j in range(i + 1, len(hues_sorted)))
    if max_span <= 60:
        analogous_score = 1.0 - (max_span / 60.0) * 0.3
        if analogous_score > best_score:
            best_score = analogous_score
            best_type = "analogous"

    # Check complementary: 2 main hues ~180° apart
    if len(hues) >= 2:
        for i in range(len(hues)):
            for j in range(i + 1, len(hues)):
                d = _hue_distance(hues[i], hues[j])
                comp_error = abs(d - 180)
                if comp_error < 40:
                    comp_score = 1.0 - (comp_error / 40.0) * 0.5
                    if comp_score > best_score:
                        best_score = comp_score
                        best_type = "complementary"

    # Check triadic: 3 hues ~120° apart
    if len(hues) >= 3:
        for i in range(len(hues)):
            for j in range(i + 1, len(hues)):
                for k in range(j + 1, len(hues)):
                    d1 = _hue_distance(hues[i], hues[j])
                    d2 = _hue_distance(hues[j], hues[k])
                    d3 = _hue_distance(hues[i], hues[k])
                    # Ideal triadic: all distances ~120°
                    tri_error = (abs(d1 - 120) + abs(d2 - 120) + abs(d3 - 120)) / 3
                    if tri_error < 30:
                        tri_score = 1.0 - (tri_error / 30.0) * 0.5
                        if tri_score > best_score:
                            best_score = tri_score
                            best_type = "triadic"

    # Check split-complementary: 1 hue + 2 hues ~150° from it
    if len(hues) >= 3:
        for i in range(len(hues)):
            others = [h for j, h in enumerate(hues) if j != i]
            for j in range(len(others)):
                for k in range(j + 1, len(others)):
                    d1 = _hue_distance(hues[i], others[j])
                    d2 = _hue_distance(hues[i], others[k])
                    d_between = _hue_distance(others[j], others[k])
                    # Ideal: d1 and d2 ~150°, d_between ~60°
                    sc_error = (abs(d1 - 150) + abs(d2 - 150) + abs(d_between - 60)) / 3
                    if sc_error < 30:
                        sc_score = 1.0 - (sc_error / 30.0) * 0.5
                        if sc_score > best_score:
                            best_score = sc_score
                            best_type = "split-complementary"

    return {
        "harmony_type": best_type,
        "harmony_score": round(best_score, 3),
        "hues": [round(h, 1) for h in hues],
    }


# ---------------------------------------------------------------------------
# Panel scoring
# ---------------------------------------------------------------------------

@dataclass
class PanelScore:
    """Quality scores for a single panel image."""
    panel_id: str
    image_path: str
    width: int
    height: int

    # Technical metrics
    sharpness: float
    contrast: float
    saturation: float
    color_entropy: float
    edge_density: float

    # Exposure
    dark_ratio: float
    bright_ratio: float
    mean_luminance: float
    exposure_balance: float

    # Composition metrics (optional, filled when --composition)
    center_bias_score: Optional[float] = None
    center_bias_dead_center: Optional[bool] = None
    thirds_score: Optional[float] = None
    thirds_zone_variance: Optional[float] = None
    thirds_hotspot_alignment: Optional[float] = None
    flow_angle: Optional[float] = None
    flow_direction: Optional[str] = None
    flow_magnitude: Optional[float] = None
    quadrant_balance_score: Optional[float] = None
    quadrant_dominant: Optional[str] = None
    quadrant_good_balance: Optional[bool] = None

    # Colorimetry metrics (optional, filled when --composition)
    color_temp: Optional[float] = None
    color_temp_label: Optional[str] = None
    dominant_colors: Optional[int] = None
    palette_rgb: Optional[list] = None
    harmony_type: Optional[str] = None
    harmony_score: Optional[float] = None

    # Computed composites
    technical_score: float = 0.0   # 0-100 composite
    composition_score: Optional[float] = None  # 0-100 composite (when --composition)
    overall_score: float = 0.0     # 0-100 weighted overall

    # Timing
    analysis_ms: float = 0.0

    def summary_line(self) -> str:
        """One-line summary for CLI output."""
        comp = f"  Comp={self.composition_score:5.1f}" if self.composition_score is not None else ""
        return (
            f"{self.panel_id:>20s}  "
            f"Sharp={self.sharpness:7.1f}  "
            f"Ctr={self.contrast:5.1f}  "
            f"Sat={self.saturation:.2f}  "
            f"Ent={self.color_entropy:.1f}  "
            f"Edge={self.edge_density:.2f}  "
            f"Exp={self.exposure_balance:.2f}"
            f"{comp}  "
            f"Score={self.overall_score:5.1f}"
        )


def _compute_technical_score(sharp: float, ctr: float, sat: float,
                             entropy: float, edges: float,
                             exp_balance: float) -> float:
    """Compute a 0-100 composite technical quality score.

    Weights and normalization are calibrated for AI-generated comic panels
    (768×768 SDXL output).
    """
    sharp_norm = min(1.0, max(0.0, (sharp - 50) / 1500))
    ctr_norm = min(1.0, max(0.0, (ctr - 20) / 60))
    sat_norm = 1.0 - abs(sat - 0.45) / 0.45
    sat_norm = max(0.0, sat_norm)
    ent_norm = min(1.0, max(0.0, (entropy - 6) / 8))
    edge_norm = 1.0 - abs(edges - 0.3) / 0.3
    edge_norm = max(0.0, edge_norm)
    exp_norm = exp_balance

    score = (
        sharp_norm * 0.25 +
        ctr_norm * 0.20 +
        sat_norm * 0.15 +
        ent_norm * 0.15 +
        edge_norm * 0.10 +
        exp_norm * 0.15
    ) * 100

    return round(score, 1)


def _compute_composition_score(
    cb_score: float,
    thirds_score: float,
    qb_score: float,
    harmony_score: float,
    dominant_colors: int,
    cb_dead_center: bool,
    qb_good_balance: bool,
) -> float:
    """Compute a 0-100 composite composition score.

    Evaluates composition quality based on center bias, rule of thirds,
    quadrant balance, color harmony, and palette richness.
    """
    # Center bias: 0 = dead center (bad), 1 = off-center (good)
    # Ideal range is 0.2-0.6 (not too centered, not too extreme)
    if cb_score < 0.15:
        cb_norm = cb_score / 0.15 * 0.5  # penalize dead center
    elif cb_score <= 0.6:
        cb_norm = 0.5 + (cb_score - 0.15) / 0.45 * 0.5  # good range
    else:
        cb_norm = 1.0 - (cb_score - 0.6) / 0.4 * 0.3  # slightly penalize extremes

    # Rule of thirds: already 0-1
    thirds_norm = thirds_score

    # Quadrant balance: ideal 0.3-0.7
    if qb_score < 0.1:
        qb_norm = qb_score / 0.1 * 0.3  # too uniform
    elif qb_score <= 0.7:
        qb_norm = 0.3 + (qb_score - 0.1) / 0.6 * 0.7  # good range
    else:
        qb_norm = 1.0 - (qb_score - 0.7) / 0.3 * 0.4  # too extreme

    # Color harmony: already 0-1
    harmony_norm = harmony_score

    # Palette richness: 3-6 colors is ideal
    if dominant_colors <= 1:
        palette_norm = 0.2
    elif dominant_colors <= 2:
        palette_norm = 0.5
    elif dominant_colors <= 6:
        palette_norm = 0.7 + (dominant_colors - 2) / 4 * 0.3
    else:
        palette_norm = 1.0 - (dominant_colors - 6) / 4 * 0.2  # too many

    score = (
        cb_norm * 0.20 +
        thirds_norm * 0.25 +
        qb_norm * 0.20 +
        harmony_norm * 0.20 +
        palette_norm * 0.15
    ) * 100

    return round(min(100.0, max(0.0, score)), 1)


# Score thresholds
SCORE_THRESHOLDS = {
    "good": 65.0,
    "ok": 40.0,
    # below "ok" = "poor"
}


def _score_label(score: float) -> str:
    """Return 'good', 'ok', or 'poor' based on score thresholds."""
    if score >= SCORE_THRESHOLDS["good"]:
        return "good"
    elif score >= SCORE_THRESHOLDS["ok"]:
        return "ok"
    else:
        return "poor"


def score_panel(image_path: str, panel_id: str = "",
                composition: bool = False) -> PanelScore:
    """Compute all quality metrics for a single panel image.

    Args:
        image_path: Path to the panel image file.
        panel_id: Identifier for the panel (defaults to filename).
        composition: If True, also compute composition + colorimetry metrics.

    Returns:
        PanelScore with all metrics computed.
    """
    if not panel_id:
        panel_id = Path(image_path).stem

    t0 = time.time()
    img = Image.open(image_path).convert('RGB')
    w, h = img.size

    sharp = sharpness(img)
    ctr = contrast(img)
    sat = saturation(img)
    entropy = color_entropy(img)
    edges = edge_density(img)
    exp = exposure(img)

    tech_score = _compute_technical_score(
        sharp, ctr, sat, entropy, edges, exp["exposure_balance"]
    )

    ps = PanelScore(
        panel_id=panel_id,
        image_path=str(image_path),
        width=w,
        height=h,
        sharpness=round(sharp, 1),
        contrast=round(ctr, 1),
        saturation=round(sat, 3),
        color_entropy=round(entropy, 2),
        edge_density=round(edges, 3),
        dark_ratio=exp["dark_ratio"],
        bright_ratio=exp["bright_ratio"],
        mean_luminance=exp["mean_luminance"],
        exposure_balance=exp["exposure_balance"],
        technical_score=tech_score,
    )

    if composition:
        cb = center_bias(img)
        ps.center_bias_score = cb["score"]
        ps.center_bias_dead_center = cb["dead_center"]

        rot = rule_of_thirds(img)
        ps.thirds_score = rot["score"]
        ps.thirds_zone_variance = rot["zone_variance"]
        ps.thirds_hotspot_alignment = rot["hotspot_alignment"]

        vf = visual_flow(img)
        ps.flow_angle = vf["angle_deg"]
        ps.flow_direction = vf["direction"]
        ps.flow_magnitude = vf["magnitude"]

        qb = quadrant_balance(img)
        ps.quadrant_balance_score = qb["score"]
        ps.quadrant_dominant = qb["dominant_quadrant"]
        ps.quadrant_good_balance = qb["good_balance"]

        ct = color_temperature(img)
        ps.color_temp = ct["temperature"]
        ps.color_temp_label = ct["warm_cool"]

        pal = palette_size(img)
        ps.dominant_colors = pal["dominant_count"]
        ps.palette_rgb = pal["palette_rgb"]

        ch = color_harmony(img)
        ps.harmony_type = ch["harmony_type"]
        ps.harmony_score = ch["harmony_score"]

        ps.composition_score = _compute_composition_score(
            cb["score"], rot["score"], qb["score"],
            ch["harmony_score"], pal["dominant_count"],
            cb["dead_center"], qb["good_balance"],
        )

        # Overall = weighted combination of technical + composition
        ps.overall_score = round(
            ps.technical_score * 0.55 + ps.composition_score * 0.45, 1
        )
    else:
        ps.overall_score = tech_score

    elapsed_ms = (time.time() - t0) * 1000
    ps.analysis_ms = round(elapsed_ms, 1)

    return ps


# ---------------------------------------------------------------------------
# Panel Sequence Analysis
# ---------------------------------------------------------------------------

def analyze_sequence(panel_paths: list[str]) -> dict:
    """Analyze a sequence of panels for narrative/visual coherence.

    Measures:
    - Visual flow continuity between consecutive panels
    - Color temperature consistency across the sequence
    - Shot variety (how diverse panels are)
    - Pacing score (density alternation)

    Args:
        panel_paths: Ordered list of panel image paths.

    Returns:
        Dict with sequence-level analysis and per-panel details.
    """
    if len(panel_paths) < 2:
        return {
            "error": "Need at least 2 panels for sequence analysis",
            "panel_count": len(panel_paths),
        }

    # Score all panels with composition
    panels = []
    for p in panel_paths:
        ps = score_panel(p, composition=True)
        panels.append(ps)

    n = len(panels)

    # --- Visual Flow Continuity ---
    # Check if flow direction of panel N points toward where panel N+1 would be
    # For LTR reading: panels go left-to-right, so ideal flow exits right
    flow_continuity_scores = []
    for i in range(n - 1):
        if panels[i].flow_angle is None or panels[i + 1].flow_angle is None:
            continue
        angle = panels[i].flow_angle
        # Good flow: panel exits toward the right (angle near 0° or 315-360°)
        # Also acceptable: downward (near 90°) for vertical layouts
        # Score based on how "rightward" the exit is
        # 0° = perfect (right), 180° = worst (left/backward)
        exit_quality = max(0.0, math.cos(math.radians(angle)))
        flow_continuity_scores.append(exit_quality)

    flow_continuity = (
        round(float(np.mean(flow_continuity_scores)), 3)
        if flow_continuity_scores else 0.0
    )

    # --- Color Temperature Consistency ---
    temps = [p.color_temp for p in panels if p.color_temp is not None]
    if temps:
        mean_temp = float(np.mean(temps))
        temp_std = float(np.std(temps))
        temp_outliers = []
        for i, t in enumerate(temps):
            if abs(t - mean_temp) > 2 * max(temp_std, 0.05):
                temp_outliers.append({
                    "panel": panels[i].panel_id,
                    "temperature": t,
                    "deviation": round(abs(t - mean_temp), 3),
                })
        temp_consistency = round(max(0.0, 1.0 - temp_std * 2), 3)
    else:
        mean_temp = 0.0
        temp_std = 0.0
        temp_consistency = 0.0
        temp_outliers = []

    # --- Shot Variety Score ---
    # Measure diversity of visual characteristics
    edge_densities = [p.edge_density for p in panels]
    contrasts = [p.contrast for p in panels]
    saturations = [p.saturation for p in panels]

    # Higher std = more variety (good)
    edge_variety = float(np.std(edge_densities)) / 0.15 if edge_densities else 0
    ctr_variety = float(np.std(contrasts)) / 20.0 if contrasts else 0
    sat_variety = float(np.std(saturations)) / 0.15 if saturations else 0

    shot_variety = round(
        min(1.0, (edge_variety * 0.4 + ctr_variety * 0.35 + sat_variety * 0.25)),
        3,
    )

    # --- Pacing Score ---
    # Good pacing = alternation between dense (high edge) and sparse (low edge) panels
    # Measure by looking at sign changes in the delta of edge_density
    if len(edge_densities) >= 3:
        deltas = np.diff(edge_densities)
        sign_changes = sum(
            1 for i in range(len(deltas) - 1)
            if deltas[i] * deltas[i + 1] < 0
        )
        max_changes = len(deltas) - 1
        pacing = round(sign_changes / max_changes, 3) if max_changes > 0 else 0.0
    else:
        pacing = 0.5  # default for 2 panels

    # --- Overall Sequence Score ---
    sequence_score = round(
        flow_continuity * 0.25 +
        temp_consistency * 0.20 +
        shot_variety * 0.30 +
        pacing * 0.25,
        3,
    ) * 100

    return {
        "panel_count": n,
        "flow_continuity": flow_continuity,
        "color_temperature": {
            "mean": round(mean_temp, 3),
            "std": round(temp_std, 3),
            "consistency": temp_consistency,
            "outliers": temp_outliers,
        },
        "shot_variety": shot_variety,
        "pacing": pacing,
        "sequence_score": round(sequence_score, 1),
        "per_panel_summary": [
            {
                "panel_id": p.panel_id,
                "technical_score": p.technical_score,
                "composition_score": p.composition_score,
                "overall_score": p.overall_score,
                "flow_direction": p.flow_direction,
                "color_temp": p.color_temp,
                "edge_density": p.edge_density,
            }
            for p in panels
        ],
    }


# ---------------------------------------------------------------------------
# Batch scoring
# ---------------------------------------------------------------------------

@dataclass
class BatchScore:
    """Aggregated quality scores for a batch of panels."""
    run_id: str
    panel_count: int
    total_analysis_ms: float

    # Aggregates
    mean_score: float
    min_score: float
    max_score: float
    std_score: float

    mean_sharpness: float
    mean_contrast: float
    mean_saturation: float
    mean_color_entropy: float
    mean_edge_density: float
    mean_exposure_balance: float

    # Composition aggregates (optional)
    mean_composition_score: Optional[float] = None
    mean_center_bias: Optional[float] = None
    mean_thirds_score: Optional[float] = None
    mean_quadrant_balance: Optional[float] = None
    mean_color_temp: Optional[float] = None
    mean_harmony_score: Optional[float] = None
    mean_dominant_colors: Optional[float] = None
    dead_center_count: Optional[int] = None

    # Sequence analysis (optional)
    sequence_analysis: Optional[dict] = None

    # Best/worst
    best_panel: str = ""
    worst_panel: str = ""

    # Per-panel scores
    panels: list[dict] = field(default_factory=list)


def score_batch(panels_dir: str, run_id: str = "",
                verbose: bool = False,
                composition: bool = False,
                sequence: bool = False) -> BatchScore:
    """Score all panel images in a directory.

    Args:
        panels_dir: Directory containing panel images.
        run_id: Identifier for this batch/run.
        verbose: Print per-panel scores.
        composition: Compute composition + colorimetry metrics.
        sequence: Run sequence analysis on ordered panels.

    Returns:
        BatchScore with individual and aggregate metrics.
    """
    panels_path = Path(panels_dir)
    if not panels_path.is_dir():
        raise FileNotFoundError(f"Directory not found: {panels_dir}")

    # Find image files
    image_files = sorted(
        f for f in panels_path.iterdir()
        if f.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp')
    )

    if not image_files:
        raise FileNotFoundError(f"No image files found in {panels_dir}")

    if not run_id:
        run_id = panels_path.name

    scores: list[PanelScore] = []
    t0 = time.time()

    for img_path in image_files:
        ps = score_panel(str(img_path), composition=composition)
        scores.append(ps)
        if verbose:
            print(f"  {ps.summary_line()}")

    total_ms = (time.time() - t0) * 1000

    # Compute aggregates
    overall_scores = [s.overall_score for s in scores]
    best = max(scores, key=lambda s: s.overall_score)
    worst = min(scores, key=lambda s: s.overall_score)

    mean_score = float(np.mean(overall_scores))
    std_score = float(np.std(overall_scores))

    batch = BatchScore(
        run_id=run_id,
        panel_count=len(scores),
        total_analysis_ms=round(total_ms, 1),
        mean_score=round(mean_score, 1),
        min_score=round(min(overall_scores), 1),
        max_score=round(max(overall_scores), 1),
        std_score=round(std_score, 1),
        mean_sharpness=round(float(np.mean([s.sharpness for s in scores])), 1),
        mean_contrast=round(float(np.mean([s.contrast for s in scores])), 1),
        mean_saturation=round(float(np.mean([s.saturation for s in scores])), 3),
        mean_color_entropy=round(float(np.mean([s.color_entropy for s in scores])), 2),
        mean_edge_density=round(float(np.mean([s.edge_density for s in scores])), 3),
        mean_exposure_balance=round(float(np.mean([s.exposure_balance for s in scores])), 3),
        best_panel=best.panel_id,
        worst_panel=worst.panel_id,
        panels=[asdict(s) for s in scores],
    )

    if composition:
        comp_scores = [s.composition_score for s in scores if s.composition_score is not None]
        if comp_scores:
            batch.mean_composition_score = round(float(np.mean(comp_scores)), 1)
        cb_scores = [s.center_bias_score for s in scores if s.center_bias_score is not None]
        if cb_scores:
            batch.mean_center_bias = round(float(np.mean(cb_scores)), 3)
        thirds = [s.thirds_score for s in scores if s.thirds_score is not None]
        if thirds:
            batch.mean_thirds_score = round(float(np.mean(thirds)), 3)
        qb = [s.quadrant_balance_score for s in scores if s.quadrant_balance_score is not None]
        if qb:
            batch.mean_quadrant_balance = round(float(np.mean(qb)), 3)
        ct = [s.color_temp for s in scores if s.color_temp is not None]
        if ct:
            batch.mean_color_temp = round(float(np.mean(ct)), 3)
        hs = [s.harmony_score for s in scores if s.harmony_score is not None]
        if hs:
            batch.mean_harmony_score = round(float(np.mean(hs)), 3)
        dc = [s.dominant_colors for s in scores if s.dominant_colors is not None]
        if dc:
            batch.mean_dominant_colors = round(float(np.mean(dc)), 1)
        batch.dead_center_count = sum(
            1 for s in scores if s.center_bias_dead_center
        )

    if sequence:
        batch.sequence_analysis = analyze_sequence(
            [str(f) for f in image_files]
        )

    return batch


# ---------------------------------------------------------------------------
# CLI report
# ---------------------------------------------------------------------------

def print_report(batch: BatchScore, detailed: bool = False):
    """Print a human-readable quality report.

    Args:
        batch: BatchScore to report on.
        detailed: If True, print extended report with composition & sequence info.
    """
    bar_width = 20

    def bar(value: float, max_val: float = 100) -> str:
        filled = int(bar_width * min(value / max_val, 1.0))
        return '█' * filled + '░' * (bar_width - filled)

    label = _score_label(batch.mean_score)
    label_icon = {"good": "✅", "ok": "⚠️", "poor": "❌"}[label]

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║              COMIC QUALITY REPORT                       ║")
    print(f"║  Run: {batch.run_id:<50s} ║")
    print(f"║  Panels: {batch.panel_count:<47d} ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print(f"║                                                          ║")
    print(f"║  Overall Score: {batch.mean_score:5.1f}/100  "
          f"{bar(batch.mean_score)}  {label_icon} ║")
    print(f"║  Rating: {label.upper():<8s}  "
          f"(min={batch.min_score:.1f}, max={batch.max_score:.1f}, "
          f"σ={batch.std_score:.1f}){' ' * 9}║")
    print(f"║                                                          ║")
    print(f"║  ── Technical Metrics ──                                 ║")
    print(f"║  Sharpness:      {batch.mean_sharpness:8.1f}  "
          f"{bar(batch.mean_sharpness, 2000)}  ║")
    print(f"║  Contrast:       {batch.mean_contrast:8.1f}  "
          f"{bar(batch.mean_contrast, 100)}  ║")
    print(f"║  Saturation:     {batch.mean_saturation:8.3f}  "
          f"{bar(batch.mean_saturation * 100)}  ║")
    print(f"║  Color Entropy:  {batch.mean_color_entropy:8.2f}  "
          f"{bar(batch.mean_color_entropy, 16)}  ║")
    print(f"║  Edge Density:   {batch.mean_edge_density:8.3f}  "
          f"{bar(batch.mean_edge_density * 100)}  ║")
    print(f"║  Exposure Bal:   {batch.mean_exposure_balance:8.3f}  "
          f"{bar(batch.mean_exposure_balance * 100)}  ║")

    if batch.mean_composition_score is not None:
        print(f"║                                                          ║")
        print(f"║  ── Composition Metrics ──                               ║")
        print(f"║  Composition:    {batch.mean_composition_score:8.1f}  "
              f"{bar(batch.mean_composition_score)}  ║")
        if batch.mean_center_bias is not None:
            print(f"║  Center Bias:    {batch.mean_center_bias:8.3f}  "
                  f"{bar(batch.mean_center_bias * 100)}  ║")
        if batch.mean_thirds_score is not None:
            print(f"║  Rule of Thirds: {batch.mean_thirds_score:8.3f}  "
                  f"{bar(batch.mean_thirds_score * 100)}  ║")
        if batch.mean_quadrant_balance is not None:
            print(f"║  Quad Balance:   {batch.mean_quadrant_balance:8.3f}  "
                  f"{bar(batch.mean_quadrant_balance * 100)}  ║")
        if batch.mean_harmony_score is not None:
            print(f"║  Color Harmony:  {batch.mean_harmony_score:8.3f}  "
                  f"{bar(batch.mean_harmony_score * 100)}  ║")
        if batch.mean_color_temp is not None:
            temp_label = "warm" if batch.mean_color_temp > 0.15 else ("cool" if batch.mean_color_temp < -0.15 else "neutral")
            print(f"║  Color Temp:     {batch.mean_color_temp:8.3f}  ({temp_label})"
                  f"{' ' * (23 - len(temp_label))}║")
        if batch.mean_dominant_colors is not None:
            print(f"║  Palette Size:   {batch.mean_dominant_colors:8.1f}  colors"
                  f"{' ' * 24}║")
        if batch.dead_center_count is not None and batch.dead_center_count > 0:
            print(f"║  ⚠️  Dead Center: {batch.dead_center_count} panels"
                  f"{' ' * (38 - len(str(batch.dead_center_count)))}║")

    print(f"║                                                          ║")
    print(f"║  Best Panel:  {batch.best_panel:<42s} ║")
    print(f"║  Worst Panel: {batch.worst_panel:<42s} ║")
    print(f"║                                                          ║")
    print(f"║  Analysis Time: {batch.total_analysis_ms:.0f}ms "
          f"({batch.total_analysis_ms / max(batch.panel_count, 1):.0f}ms/panel)"
          f"{' ' * 18}║")
    print("╚══════════════════════════════════════════════════════════╝")

    if detailed and batch.sequence_analysis:
        seq = batch.sequence_analysis
        print()
        print("╔══════════════════════════════════════════════════════════╗")
        print("║              SEQUENCE ANALYSIS                          ║")
        print("╠══════════════════════════════════════════════════════════╣")
        print(f"║                                                          ║")
        print(f"║  Sequence Score:  {seq['sequence_score']:5.1f}/100  "
              f"{bar(seq['sequence_score'])}  ║")
        print(f"║                                                          ║")
        print(f"║  Flow Continuity:   {seq['flow_continuity']:5.3f}  "
              f"{bar(seq['flow_continuity'] * 100)}  ║")
        ct_info = seq['color_temperature']
        print(f"║  Temp Consistency:  {ct_info['consistency']:5.3f}  "
              f"{bar(ct_info['consistency'] * 100)}  ║")
        print(f"║  Shot Variety:      {seq['shot_variety']:5.3f}  "
              f"{bar(seq['shot_variety'] * 100)}  ║")
        print(f"║  Pacing:            {seq['pacing']:5.3f}  "
              f"{bar(seq['pacing'] * 100)}  ║")
        if ct_info['outliers']:
            print(f"║                                                          ║")
            print(f"║  ⚠️  Temperature outliers:                                ║")
            for outlier in ct_info['outliers'][:3]:
                pid = outlier['panel'][:30]
                print(f"║    {pid:<30s} (dev={outlier['deviation']:.3f})"
                      f"{' ' * (17 - len(str(round(outlier['deviation'], 3))))}║")
        print(f"║                                                          ║")
        print("╚══════════════════════════════════════════════════════════╝")

    if detailed:
        # Print per-panel breakdown
        print()
        print("Panel Breakdown:")
        print(f"  {'Panel':<25s} {'Tech':>6s} {'Comp':>6s} {'Overall':>7s}  {'Label':>5s}")
        print(f"  {'─' * 25} {'─' * 6} {'─' * 6} {'─' * 7}  {'─' * 5}")
        for pd in batch.panels:
            comp_str = f"{pd.get('composition_score', 0) or 0:6.1f}" if pd.get('composition_score') is not None else "   N/A"
            overall = pd.get('overall_score', pd.get('technical_score', 0))
            lbl = _score_label(overall)
            icon = {"good": "✅", "ok": "⚠️", "poor": "❌"}[lbl]
            print(f"  {pd['panel_id']:<25s} {pd['technical_score']:6.1f} {comp_str} {overall:7.1f}  {icon}")
        print()

    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="ComicMaster Quality Tracker — PIL metrics + Composition Analysis"
    )
    parser.add_argument(
        "input",
        help="Path to a panels directory or a single image file"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output JSON file path (default: <input>/quality_scores.json)"
    )
    parser.add_argument(
        "--run-id",
        default="",
        help="Identifier for this run (default: directory name)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print per-panel scores"
    )
    parser.add_argument(
        "--composition",
        action="store_true",
        help="Include composition + colorimetry metrics"
    )
    parser.add_argument(
        "--sequence",
        action="store_true",
        help="Run panel-sequence analysis (requires directory input)"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print detailed text report instead of summary"
    )

    args = parser.parse_args()
    input_path = Path(args.input)

    if input_path.is_file():
        # Single image mode
        ps = score_panel(str(input_path), composition=args.composition)
        print(ps.summary_line())

        if args.report and args.composition:
            print()
            print(f"  Composition Details for {ps.panel_id}:")
            if ps.center_bias_score is not None:
                dc = "⚠️  DEAD CENTER" if ps.center_bias_dead_center else "✅"
                print(f"    Center Bias:      {ps.center_bias_score:.3f}  {dc}")
            if ps.thirds_score is not None:
                print(f"    Rule of Thirds:   {ps.thirds_score:.3f}  "
                      f"(var={ps.thirds_zone_variance:.3f}, align={ps.thirds_hotspot_alignment:.3f})")
            if ps.flow_direction is not None:
                print(f"    Visual Flow:      {ps.flow_angle:.1f}° → {ps.flow_direction}  "
                      f"(mag={ps.flow_magnitude:.4f})")
            if ps.quadrant_balance_score is not None:
                gb = "✅ good" if ps.quadrant_good_balance else "⚠️"
                print(f"    Quad Balance:     {ps.quadrant_balance_score:.3f}  {gb}  "
                      f"(dominant: {ps.quadrant_dominant})")
            if ps.color_temp is not None:
                print(f"    Color Temp:       {ps.color_temp:.3f}  ({ps.color_temp_label})")
            if ps.dominant_colors is not None:
                pal_str = ", ".join(f"rgb({c[0]},{c[1]},{c[2]})" for c in (ps.palette_rgb or [])[:5])
                print(f"    Palette:          {ps.dominant_colors} colors  [{pal_str}]")
            if ps.harmony_type is not None:
                print(f"    Color Harmony:    {ps.harmony_type}  (score={ps.harmony_score:.3f})")
            print()

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(asdict(ps), f, indent=2)
            print(f"\n💾 Saved to {args.output}")
    elif input_path.is_dir():
        # Batch mode
        batch = score_batch(
            str(input_path),
            run_id=args.run_id,
            verbose=args.verbose,
            composition=args.composition,
            sequence=args.sequence,
        )
        print_report(batch, detailed=args.report)

        # Save JSON
        output_path = args.output or str(input_path / "quality_scores.json")
        with open(output_path, 'w') as f:
            json.dump(asdict(batch), f, indent=2, ensure_ascii=False)
        print(f"💾 Saved scores to {output_path}")
    else:
        print(f"❌ Not found: {input_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()

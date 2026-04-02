---
name: comicmaster
description: Generate complete comic pages from a short prompt. Creates story breakdowns, generates panels with ComfyUI, adds speech bubbles, composes pages with layouts, and exports as PNG/PDF/CBZ. Use when asked to create comics, manga, cartoon strips, comic panels, or visual stories. Requires ComfyUI running on Windows.
---

# ComicMaster

Create complete comics from a short user prompt. Handles story planning, panel generation (ComfyUI), speech bubbles, page layout, and export.

## Quick Start

```bash
# Full pipeline from story plan
python3 skills/comicmaster/scripts/comic_pipeline.py story_plan.json

# With options
python3 skills/comicmaster/scripts/comic_pipeline.py story_plan.json \
    --preset dreamshaperXL --width 768 --height 768 --formats png,pdf,cbz

# Re-do only bubbles + layout (skip image generation)
python3 skills/comicmaster/scripts/comic_pipeline.py story_plan.json --skip-generate

# Upscale panels after generation
python3 skills/comicmaster/scripts/upscale.py output/panels/ --scale 2.0 --method auto

# Apply color grading
python3 skills/comicmaster/scripts/color_grading.py output/panels/ --grade cyberpunk
```

## Pipeline Flow

```
Story Plan JSON
  → Stage 0.5: Character Reference Generation (IPAdapter)
  → Stage 1: Panel Generation (ComfyUI, batch-optimized)
  → Stage 2: Speech Bubbles (PIL)
  → Stage 3: Page Layout (PIL, dynamic or template)
  → Stage 4: Export (PNG, PDF, CBZ with ComicInfo.xml)
```

## Workflow

### Step 1: Story Plan (Agent generates this)

When asked to create a comic, generate a `story_plan.json`:

```json
{
  "title": "The Last Robot",
  "style": "western",
  "preset": "dreamshaperXL",
  "reading_direction": "ltr",
  "characters": [
    {
      "id": "char_01",
      "name": "Kai",
      "visual_description": "young man, 25, short black messy hair, brown eyes, grey hoodie"
    }
  ],
  "panels": [
    {
      "id": "panel_01",
      "sequence": 1,
      "scene": "ruined cityscape at dawn",
      "action": "Kai stands on a rooftop looking over ruins",
      "characters_present": ["char_01"],
      "camera_angle": "low_angle",
      "shot_type": "wide",
      "mood": "melancholic",
      "narrative_weight": "high",
      "character_emotions": "contemplative",
      "character_poses": "standing at edge, hands in pockets",
      "lighting": "dramatic",
      "background_detail": "crumbling skyscrapers, orange dawn sky",
      "dialogue": [
        {"character": "char_01", "text": "Three years since the shutdown...", "type": "speech", "position_hint": "top_right"}
      ],
      "narration": "The world had changed."
    }
  ],
  "pages": []
}
```

**Tip:** Leave `pages: []` to use dynamic auto-layout based on `narrative_weight`.

### Step 2: Review

After generation, review the output pages (in `output/comicmaster/{project}/pages/`).
Individual panels are in `panels/`, bubbled versions in `panels_bubbled/`.

### Step 3: Post-Processing (optional)

```bash
# Upscale for print (768px → 1536px)
python3 scripts/upscale.py output/panels/ --scale 2.0

# Apply color grading for unified look
python3 scripts/color_grading.py output/panels/ --grade noir
```

## Story Plan Schema

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Comic title |
| `style` | string | `western`, `manga`, `cartoon`, `realistic`, `noir` |
| `characters[]` | array | At least 1 character |
| `characters[].id` | string | Unique ID (e.g., `char_01`) |
| `characters[].name` | string | Display name |
| `characters[].visual_description` | string | Detailed appearance for prompts |
| `panels[]` | array | At least 1 panel |
| `panels[].id` | string | Unique ID (e.g., `panel_01`) |
| `panels[].sequence` | int | Order number |
| `panels[].scene` | string | Environment description |
| `panels[].action` | string | What's happening |
| `panels[].characters_present` | string[] | Character IDs in this panel |

### Optional Panel Fields

| Field | Values | Default |
|-------|--------|---------|
| `camera_angle` | `eye_level`, `low_angle`, `high_angle`, `dutch_angle`, `birds_eye`, `worms_eye` | `eye_level` |
| `shot_type` | `extreme_wide`, `wide`, `medium`, `medium_close`, `close_up`, `extreme_close` | `medium` |
| `mood` | free text | — |
| `character_poses` | free text | — |
| `character_emotions` | `happy`, `sad`, `angry`, `surprised`, `scared`, `determined`, `tired`, `confused` or free text | — |
| `lighting` | `natural`, `dramatic`, `noir`, `soft`, `sunset`, `moonlight`, `neon`, `studio`, `backlit` | `natural` |
| `background_detail` | free text | — |
| `narrative_weight` | `low`, `medium`, `high`, `splash` | `medium` |
| `dialogue[]` | array of dialogue entries | `[]` |
| `narration` | string | — |

### Dialogue Entry

```json
{"character": "char_01", "text": "Hello!", "type": "speech", "position_hint": "top_left"}
```

**Types:** `speech`, `thought`, `shout`, `whisper`, `narration`, `caption`, `sfx`, `explosion`, `electric`, `connected`, `scream`
**Position hints:** `top_left`, `top_center`, `top_right`, `middle_left`, `middle_right`, `bottom_left`, `bottom_center`, `bottom_right`

SFX entries support `"rotation": -15` for angled text.

## Bubble Types (11 total)

| Type | Visual | Use for |
|------|--------|---------|
| `speech` | White rounded bubble + tail | Normal dialogue |
| `thought` | Cloud shape + circle trail | Internal thoughts |
| `shout` | Spiky starburst | Loud dialogue |
| `whisper` | Dashed outline, small text | Quiet dialogue |
| `narration` | Rectangle, no tail | Narrator text |
| `caption` | Small rectangle | Location/time labels |
| `explosion` | Yellow starburst, red text | SFX: BOOM!, CRASH! |
| `electric` | Zigzag edges, cyan | Robot/electronic speech |
| `connected` | Two tails | Two speakers, one bubble |
| `scream` | Jagged red polygon | Extreme emotion |
| `sfx` | Rotated outlined text, no bg | Sound effects overlay |

## Dynamic Layouts (recommended)

Set `narrative_weight` per panel and leave `pages: []` — sizes calculated automatically:

| Weight | Effect | Use for |
|--------|--------|---------|
| `low` | Small (~30% row) | Reactions, transitions |
| `medium` | Normal (equal share) | Dialogue, standard |
| `high` | Large (~60% row) | Action, reveals |
| `splash` | Full width/page | Opening, climax, finale |

### Fixed Templates (alternative)

| Template | Panels | Description |
|----------|--------|-------------|
| `page_2x2` | 4 | Classic 2×2 grid |
| `page_2x3` | 6 | 2 columns × 3 rows |
| `page_2x4` | 8 | 2 columns × 4 rows |
| `page_3x2` | 6 | 3 columns × 2 rows |
| `page_action` | 4 | 1 big + 3 small |
| `page_splash` | 3 | 1 dominant + 2 side |
| `page_4koma` | 4 | Vertical strip (manga) |

## Character Consistency (IPAdapter)

Automatically generates character reference sheets and uses IPAdapter for consistency:

1. **Reference generation:** 1024×1024 portrait per character
2. **Upload:** Ref uploaded to ComfyUI automatically
3. **Per-panel conditioning:** Weight adapts to shot type (0.4 wide → 0.8 close-up)
4. **Auto preset switch:** PLUS for body shots, PLUS FACE for close-ups
5. **Multi-character:** Chained IPAdapterAdvanced nodes with decreasing weights

| Characters | Primary Weight | Secondary | Tertiary |
|-----------|---------------|-----------|----------|
| 1 | base weight | — | — |
| 2 | base × 1.0 | base × 0.67 | — |
| 3+ | base × 1.0 | base × 0.67 | base × 0.5 |

## Batch Optimization

For 6+ panels with IPAdapter, the pipeline automatically:
- Groups panels by IPAdapter requirements (none → single char → multi char)
- Sorts within groups by character combination
- Minimizes model switches (tested: 9→5 switches on 10 panels)
- Shows ETA and progress every 10 panels

## Color Grading

Apply unified color palette across all panels:

```bash
python3 scripts/color_grading.py panels/ --grade noir
python3 scripts/color_grading.py --list  # show presets
```

| Preset | Effect |
|--------|--------|
| `noir` | Desaturated, blue-cool, high contrast, vignette |
| `vintage` | Warm sepia, slight desaturation |
| `vibrant` | Boosted saturation, punchy |
| `pastel` | Light, soft, desaturated |
| `cyberpunk` | Cool blue-purple, saturated, vignette |
| `manga_bw` | Full black & white, high contrast |

## Panel Upscaling

```bash
# Auto-detect best method (ComfyUI model → PIL fallback)
python3 scripts/upscale.py panel.png --scale 2.0 --method auto

# Batch upscale all panels
python3 scripts/upscale.py panels/ --scale 2.0
```

| Method | Speed | Quality |
|--------|-------|---------|
| `model` (4x-UltraSharp) | ~8s/panel | Excellent, detail-preserving |
| `simple` (PIL Lanczos) | ~0.7s/panel | Good, fast fallback |

## Presets (from ComfyUI skill)

| Preset | Steps | Speed | Prompt Style | Best for |
|--------|-------|-------|-------------|----------|
| `dreamshaperXL` | 8 | ~4s/panel | Natural language | All-around default |
| `juggernautXL` | 6 | ~3s/panel | Natural language | Photorealistic |
| `illustriousXL` | 28 | ~15s/panel | **Danbooru tags** | Illustration, Comic, Manga |
| `noobaiXL` | 28 | ~15s/panel | **Danbooru tags** | Anime, Manga (v-prediction) |
| `flux` | 20 | ~15s/panel | Natural language | Best prompt adherence |

### Illustrious XL / NoobAI-XL Notes

These models use **Danbooru tag-based prompts** instead of natural language descriptions. When you set `"preset": "illustriousXL"` or `"preset": "noobaiXL"` in the story plan, the pipeline automatically:

1. **Switches to tag-based prompting** — character descriptions are converted to Danbooru tags (e.g., `1boy, short black hair, brown eyes, grey hoodie` instead of prose)
2. **Adds quality tags** — `masterpiece, best quality, newest, absurdres, highres` prefix
3. **Uses optimized negative prompts** — model-specific negatives tuned for each architecture
4. **Sets Clip Skip 2** — required for Illustrious models
5. **Handles v-prediction** — NoobAI-XL v-pred adds `ModelSamplingDiscrete` node automatically

**When to use which:**

| Use Case | Recommended |
|----------|------------|
| Western comics (general) | `dreamshaperXL` (fast) or `illustriousXL` (quality) |
| Manga / anime style | `illustriousXL` or `noobaiXL` |
| Photorealistic | `juggernautXL` |
| Maximum quality (slow) | `flux` |
| Speed priority | `dreamshaperXL` (8 steps) |

See `references/illustrious-xl-guide.md` for detailed model comparison, download links, and prompting guide.

## Export Formats

| Format | Description |
|--------|-------------|
| PNG | Individual page images |
| PDF | Print-ready document |
| CBZ | Comic reader archive with ComicInfo.xml metadata |

## Files

| Script | Purpose |
|--------|---------|
| `comic_pipeline.py` | Main orchestrator (lazy-loads panel_generator for --skip-generate) |
| `panel_generator.py` | Panel generation via ComfyUI (SDXL + IPAdapter) + sequential composition rules |
| `speech_bubbles.py` | PIL-based bubble overlay (11 types) with adaptive font sizing |
| `page_layout.py` | Panel → page composition (7 templates + dynamic) |
| `export.py` | PDF/CBZ/PNG export |
| `story_planner.py` | Story plan validation & enrichment |
| `batch_optimizer.py` | Panel ordering for minimal model switches |
| `upscale.py` | 2x/4x upscaling (ComfyUI model or PIL) |
| `color_grading.py` | Color grade presets (6 styles) |
| `quality_tracker.py` | PIL-based image quality metrics (sharpness, contrast, saturation, entropy, edges, exposure) |
| `utils.py` | Shared utilities |

## Workflows (JSON for ComfyUI)

Loadable in ComfyUI UI → Load:

| File | Description |
|------|-------------|
| `workflows/panel_sdxl.json` | Standard SDXL panel |
| `workflows/panel_illustrious.json` | Illustrious XL panel (Danbooru tags, clip skip 2) |
| `workflows/panel_ipadapter.json` | Panel with single character ref |
| `workflows/panel_ipadapter_multi.json` | Panel with 2+ character refs |
| `workflows/panel_upscale.json` | 4x-UltraSharp upscaling |
| `workflows/character_ref.json` | Character reference sheet |

## Style Guides

See `references/style-guides.md` for prompt templates per style (Western, Manga, Cartoon, Noir, Realistic).

## Camera Angle Guide

| Purpose | Angle | Shot |
|---------|-------|------|
| Establishing scene | high/birds_eye | wide/extreme_wide |
| Character intro | low_angle | medium |
| Dialogue | eye_level | medium/medium_close |
| Emotion/reaction | eye_level | close_up |
| Action/impact | low_angle/dutch_angle | medium/wide |
| Suspense | high_angle | wide |

## Quality Tracking

Run after each comic generation to measure panel quality:

```bash
# Score all panels in a directory
python3 scripts/quality_tracker.py output/panels/ --output scores.json --verbose

# Score single image
python3 scripts/quality_tracker.py panel.png

# With composition analysis (center bias, thirds, flow, harmony, palette)
python3 scripts/quality_tracker.py output/panels/ --composition --verbose

# With panel-sequence analysis (flow continuity, pacing, shot variety)
python3 scripts/quality_tracker.py output/panels/ --composition --sequence --report

# Detailed text report
python3 scripts/quality_tracker.py output/panels/ --composition --sequence --report
```

### Technical Metrics

| Metric | What | Range | Good |
|--------|------|-------|------|
| Sharpness | Laplacian variance | 0-∞ | >500 |
| Contrast | RMS luminance stddev | 0-127 | 50-80 |
| Saturation | Mean HSV saturation | 0-1 | 0.25-0.55 |
| Color Entropy | Histogram diversity | 0-16 | >9 |
| Edge Density | Edge pixel ratio | 0-1 | 0.1-0.3 |
| Exposure Balance | Under/over exposure | 0-1 | >0.6 |

### Composition Metrics (--composition)

| Metric | What | Range | Good |
|--------|------|-------|------|
| Center Bias | Visual mass distance from center | 0-1 | 0.2-0.6 (off-center = good, <0.2 = "dead center" flag) |
| Rule of Thirds | Zone variance + hotspot alignment | 0-1 | >0.3 (higher = better thirds usage) |
| Visual Flow | Dominant gradient direction | 0°-360° | Varies (0° = right, 90° = down). Good when exit matches next panel |
| Quadrant Balance | Visual weight distribution imbalance | 0-1 | 0.3-0.7 (asymmetric balance is ideal for comics) |

### Colorimetry Metrics (--composition)

| Metric | What | Range | Good |
|--------|------|-------|------|
| Color Temperature | Warm (red) vs cool (blue) bias | -1.0 to 1.0 | Depends on scene mood. Consistent within a scene is key |
| Palette Size | Number of dominant colors (K-Means k=8) | 1-8 | 3-6 (rich but not chaotic) |
| Color Harmony | How well colors match harmony patterns | 0-1 | >0.5 (complementary, analogous, triadic, split-complementary) |

### Sequence Metrics (--sequence)

| Metric | What | Range | Good |
|--------|------|-------|------|
| Flow Continuity | Do panels flow toward the next panel? | 0-1 | >0.5 (rightward exit for LTR reading) |
| Temp Consistency | Color temperature variance across panels | 0-1 | >0.7 (consistent within a scene) |
| Shot Variety | How different are consecutive panels? | 0-1 | >0.3 (varied compositions keep interest) |
| Pacing | Alternation between dense/sparse panels | 0-1 | >0.3 (rhythmic density changes = good pacing) |

### Scoring System

Each panel gets:
- **Technical Score** (0-100): Weighted composite of sharpness, contrast, saturation, entropy, edges, exposure
- **Composition Score** (0-100, with `--composition`): Weighted composite of center bias, thirds, balance, harmony, palette
- **Overall Score** (0-100): 55% technical + 45% composition (or 100% technical without `--composition`)

Score labels: **good** (≥65), **ok** (≥40), **poor** (<40)

Outputs `quality_scores.json` with per-panel and aggregate scores.
~50ms/panel basic, ~120ms/panel with composition. Zero external dependencies (PIL + numpy only).

## Performance Reference

| Scenario | Time |
|----------|------|
| 4 panels, no IPAdapter | ~35s |
| 4 panels + IPAdapter | ~46s |
| 8 panels + dynamic layout | ~44s |
| 30 panels + IPAdapter + batch | ~5-7 min (est.) |
| Upscale per panel (model) | ~8s |
| Color grade per panel | ~0.2s |

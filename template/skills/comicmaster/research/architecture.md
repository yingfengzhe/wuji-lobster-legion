# ComicMaster Skill — Architecture Document

> **Version:** 1.0 (2026-02-08)  
> **Status:** Design Phase  
> **Author:** Sentinel (Claude)  
> **Depends on:** `skills/comfyui/` (comfy_client.py, generate.py, presets.json)

---

## Table of Contents

1. [Overview & Goals](#1-overview--goals)
2. [Skill Directory Structure](#2-skill-directory-structure)
3. [Pipeline Flow](#3-pipeline-flow)
4. [Character Consistency Strategy](#4-character-consistency-strategy)
5. [Speech Bubble System](#5-speech-bubble-system)
6. [Page Layout System](#6-page-layout-system)
7. [Memory / Learning System](#7-memory--learning-system)
8. [Improvement Suggestions](#8-improvement-suggestions)
9. [Implementation Priority](#9-implementation-priority)
10. [Appendix: Data Schemas](#appendix-data-schemas)

---

## 1. Overview & Goals

**ComicMaster** is an OpenClaw skill that automates end-to-end comic/manga creation from a short user prompt to finished, paginated comic pages with speech bubbles.

### Core Capabilities

| Capability | Target |
|---|---|
| Panels per comic | 8–16 (default), up to ~100 |
| Character consistency | Same face/body across ALL panels |
| Speech bubbles | Auto-positioned, multiple styles |
| Page layouts | Grid templates, irregular layouts |
| Style support | Manga, Marvel/Western, Cartoon, Realistic |
| Output formats | PNG pages, PDF, CBZ |

### Design Principles

1. **Build on existing infrastructure** — reuse `comfy_client.py`, `generate.py`, `comfy_logger.py`, and the preset system from `skills/comfyui/`
2. **LLM-first story planning** — the agent (Claude) decomposes the user prompt into a structured story plan; no separate LLM API call needed
3. **Modular pipeline** — each stage is independently runnable and testable
4. **Fail gracefully** — retry individual panels, not the whole comic
5. **Learn from results** — track what works per style/character/composition

### Infrastructure Context

```
ComfyUI (Windows)  ←──HTTP──→  WSL2 (host.docker.internal:8188)
                                  │
                                  ├── skills/comfyui/scripts/comfy_client.py  (API client)
                                  ├── skills/comfyui/scripts/generate.py      (high-level generator)
                                  ├── skills/comfyui/presets.json             (model presets)
                                  └── skills/comicmaster/scripts/             (THIS SKILL)
```

The existing `comfy_client.py` provides: `queue_prompt()`, `wait_for_completion()`, `download_image()`, `generate_and_download()`, `ensure_running()`. ComicMaster wraps these — it does NOT duplicate them.

---

## 2. Skill Directory Structure

```
skills/comicmaster/
├── SKILL.md                          # Skill interface doc for the agent
├── config.json                       # ComicMaster-specific config
├── scripts/
│   ├── comic_pipeline.py             # Orchestrator — full pipeline entry point
│   ├── story_planner.py              # Structured story → panel breakdown (JSON)
│   ├── character_ref.py              # Generate character reference sheets
│   ├── panel_generator.py            # Generate individual panels with consistency
│   ├── speech_bubbles.py             # PIL-based speech bubble overlay
│   ├── page_layout.py               # Compose panels into comic pages
│   ├── export.py                     # PDF/CBZ/WebP export
│   └── utils.py                      # Shared utilities, path helpers, image ops
├── workflows/
│   ├── character_ref_sheet.json      # ComfyUI API workflow: multi-view character ref
│   ├── panel_ipadapter.json          # ComfyUI API workflow: panel gen with IPAdapter
│   ├── panel_ipadapter_face.json     # ComfyUI API workflow: panel gen with IPAdapter FaceID
│   └── panel_upscale.json            # ComfyUI API workflow: optional panel upscaling
├── references/
│   ├── panel-composition.md          # Camera angles, shot types, framing rules
│   └── style-guides.md              # Manga vs Marvel vs Cartoon guidelines
├── assets/
│   ├── fonts/
│   │   ├── comic-sans-alternative.ttf  # Default comic font (e.g., Bangers, Comic Neue)
│   │   ├── manga-font.ttf              # For manga style
│   │   └── shout-font.ttf              # Bold/impact font for shout bubbles
│   └── templates/
│       ├── page_2x2.json               # 4-panel grid
│       ├── page_3x2.json               # 6-panel grid
│       ├── page_2x3.json               # 6-panel vertical
│       ├── page_2x4.json               # 8-panel grid
│       ├── page_irregular_action.json   # Action sequence (1 big + 3 small)
│       ├── page_irregular_splash.json   # Splash page (1 dominant panel)
│       └── page_manga_4koma.json        # 4-koma vertical strip
└── memory/
    └── learnings.md                   # What worked, what didn't
```

### Key Files Explained

| File | Role |
|---|---|
| `comic_pipeline.py` | The single entry point. Takes a story plan JSON (or raw prompt) and produces finished comic pages. Orchestrates all other scripts. |
| `story_planner.py` | NOT an LLM call — it's a structured data handler. The agent (Claude) generates the story plan as JSON; this script validates, enriches, and persists it. |
| `character_ref.py` | Generates character reference images via ComfyUI, stores them for IPAdapter/FaceID use. |
| `panel_generator.py` | Core image generation. Loads the appropriate ComfyUI workflow, injects character references, prompts, and consistency parameters. |
| `speech_bubbles.py` | Pure Python (PIL/Pillow). No ComfyUI dependency. Overlays speech bubbles, thought bubbles, narration boxes. |
| `page_layout.py` | Pure Python (PIL/Pillow). Composites individual panel images into full comic pages using grid templates. |
| `export.py` | Assembles pages into PDF (via Pillow or reportlab), CBZ (ZIP of images), or WebP sequences. |

---

## 3. Pipeline Flow

### 3.1 High-Level Flow

```
User Prompt
    │
    ▼
┌─────────────────────┐
│  STAGE 0: Planning   │  Agent (Claude) decomposes prompt into story_plan.json
│  (LLM — the agent)  │  Characters, scenes, panels, dialogue, camera angles
└─────────┬───────────┘
          │ story_plan.json
          ▼
┌─────────────────────┐
│  STAGE 1: Character  │  Generate reference sheets for each character
│  References          │  → 1 multi-angle ref image per character
│  (character_ref.py)  │  → Store in output/{project}/refs/
└─────────┬───────────┘
          │ character_refs/*.png
          ▼
┌─────────────────────┐
│  STAGE 2: Panel      │  Generate each panel individually
│  Generation          │  → IPAdapter for character consistency
│  (panel_generator.py)│  → Per-panel prompt from story plan
│                      │  → Retry failed panels (max 3 attempts)
└─────────┬───────────┘
          │ panels/*.png
          ▼
┌─────────────────────┐
│  STAGE 3: Speech     │  Overlay speech bubbles + narration
│  Bubbles             │  → Pure PIL, no ComfyUI needed
│  (speech_bubbles.py) │  → Auto-position or manual placement
└─────────┬───────────┘
          │ panels_with_text/*.png
          ▼
┌─────────────────────┐
│  STAGE 4: Page       │  Compose panels into pages
│  Layout              │  → Grid templates or custom layouts
│  (page_layout.py)    │  → Add gutters, borders, page numbers
└─────────┬───────────┘
          │ pages/*.png
          ▼
┌─────────────────────┐
│  STAGE 5: Export     │  Final output assembly
│  (export.py)         │  → PNG pages (default)
│                      │  → PDF, CBZ, WebP (optional)
└─────────────────────┘
          │
          ▼
    output/comicmaster/{project_id}/
    ├── story_plan.json
    ├── refs/
    ├── panels/
    ├── panels_bubbled/
    ├── pages/
    └── comic.pdf
```

### 3.2 Detailed Data Flow

#### Stage 0: Story Planning (Agent-Side)

The agent (Claude) receives the user prompt and generates a structured `story_plan.json`. This is NOT a separate Python script calling an external LLM — it's the agent's own output.

**Agent instructions (in SKILL.md):**

```
When asked to create a comic, generate a story_plan.json with this structure:
- title, style, reading_direction
- characters[] with name, description, visual_description, role
- panels[] with scene, action, dialogue[], camera_angle, shot_type, mood, characters_present[]
- pages[] mapping which panels go on which page with layout template
```

The agent writes this JSON to disk, then calls `comic_pipeline.py` with it.

**Example story_plan.json:**

```json
{
  "title": "The Last Robot",
  "style": "manga",
  "reading_direction": "ltr",
  "preset": "dreamshaperXL",
  "characters": [
    {
      "id": "char_01",
      "name": "Kai",
      "role": "protagonist",
      "visual_description": "young man, 25 years old, short black messy hair, sharp jawline, brown eyes, wearing a torn grey hoodie and dark cargo pants, lean athletic build",
      "personality": "determined, quiet, resourceful"
    },
    {
      "id": "char_02",
      "name": "Unit-7",
      "role": "companion",
      "visual_description": "small round robot, about knee-height, white and blue metallic body, single large blue glowing eye, antenna on top, scratched and dented",
      "personality": "curious, loyal, occasionally comedic"
    }
  ],
  "panels": [
    {
      "id": "panel_01",
      "sequence": 1,
      "scene": "ruined cityscape at dawn, crumbling skyscrapers, overgrown with vines",
      "action": "Kai stands on a rooftop looking out over the ruins",
      "characters_present": ["char_01"],
      "camera_angle": "low_angle",
      "shot_type": "wide",
      "mood": "melancholic, hopeful",
      "dialogue": [
        {
          "character": "char_01",
          "text": "Three years since the shutdown...",
          "type": "speech",
          "position_hint": "top_right"
        }
      ],
      "narration": "The world had changed. But Kai hadn't given up."
    },
    {
      "id": "panel_02",
      "sequence": 2,
      "scene": "same rooftop, closer shot",
      "action": "Unit-7 rolls up behind Kai, beeping",
      "characters_present": ["char_01", "char_02"],
      "camera_angle": "eye_level",
      "shot_type": "medium",
      "mood": "warm",
      "dialogue": [
        {
          "character": "char_02",
          "text": "Beep boop! Signal detected!",
          "type": "speech",
          "position_hint": "top_left"
        },
        {
          "character": "char_01",
          "text": "Show me.",
          "type": "speech",
          "position_hint": "top_right"
        }
      ]
    }
  ],
  "pages": [
    {
      "page_number": 1,
      "layout": "page_2x2",
      "panel_ids": ["panel_01", "panel_02", "panel_03", "panel_04"]
    },
    {
      "page_number": 2,
      "layout": "page_irregular_action",
      "panel_ids": ["panel_05", "panel_06", "panel_07", "panel_08"]
    }
  ]
}
```

#### Stage 1: Character Reference Generation

`character_ref.py` generates one reference image per character. This image is then used by IPAdapter in all subsequent panel generations.

```python
# Pseudocode
def generate_character_ref(character, style, preset, output_dir):
    """
    Generate a character reference sheet.
    
    Produces a single image showing the character in a neutral pose,
    front-facing, on a simple background. This becomes the IPAdapter
    reference for all panels featuring this character.
    """
    prompt = build_ref_prompt(character, style)
    # e.g., "character reference sheet, front view, {visual_description}, 
    #         simple white background, full body, {style} art style, 
    #         high quality, detailed, consistent design"
    
    workflow = load_workflow("character_ref_sheet.json")
    workflow = inject_params(workflow, prompt=prompt, preset=preset, 
                            width=1024, height=1024, seed=character_seed)
    
    images = comfy_client.generate_and_download(workflow, output_dir)
    return images[0]  # Path to reference image
```

**Character reference prompt template:**

```
character reference sheet, {character.visual_description}, 
front view, three-quarter view, simple {background} background, 
{style} art style, high quality, detailed, consistent proportions,
full body standing pose, neutral expression, studio lighting
```

**Retry logic:** If the reference image is unsatisfactory (agent can review), regenerate with a different seed. Store the seed that worked in the story plan for reproducibility.

#### Stage 2: Panel Generation

`panel_generator.py` generates each panel individually, using IPAdapter to inject character consistency.

```python
# Pseudocode
def generate_panel(panel, characters, char_refs, style, preset, output_dir):
    """
    Generate a single comic panel with character consistency.
    
    Uses IPAdapter to condition on character reference images.
    """
    prompt = build_panel_prompt(panel, characters, style)
    # e.g., "{shot_type} shot, {camera_angle}, {action}, {scene},
    #         {mood} atmosphere, {style} art style, comic panel,
    #         {character visual descriptions}"
    
    # Select workflow based on consistency method
    if len(panel.characters_present) > 0 and char_refs:
        workflow = load_workflow("panel_ipadapter.json")
        workflow = inject_ipadapter_refs(workflow, panel.characters_present, char_refs)
    else:
        # Scene-only panel (no characters) — standard generation
        workflow = load_workflow_from_preset(preset)
    
    workflow = inject_params(workflow, prompt=prompt, preset=preset,
                            width=768, height=768)
    
    images = comfy_client.generate_and_download(workflow, output_dir)
    return images[0]

def generate_all_panels(story_plan, char_refs, output_dir):
    """Generate all panels with error handling."""
    results = {}
    failed = []
    
    for panel in story_plan["panels"]:
        for attempt in range(3):  # Max 3 retries
            try:
                path = generate_panel(panel, ..., char_refs, ...)
                results[panel["id"]] = path
                break
            except Exception as e:
                if attempt == 2:
                    failed.append((panel["id"], str(e)))
                else:
                    time.sleep(5)  # Brief pause before retry
    
    return results, failed
```

**Panel prompt template:**

```
{shot_type} shot, {camera_angle} angle, {style} art style, comic panel,
{action}, {scene}, {mood} mood, {character descriptions if present},
high quality, detailed, sharp lines, {style-specific tags}
```

**Panel dimensions per style:**

| Style | Panel Size | Aspect Ratios |
|---|---|---|
| Manga | 768×1024 | 3:4 (portrait-biased) |
| Marvel/Western | 768×768 or 1024×768 | 1:1 or 4:3 |
| Cartoon | 768×768 | 1:1 |
| Cinematic | 1024×576 | 16:9 |

#### Stage 3: Speech Bubbles

`speech_bubbles.py` overlays dialogue and narration onto generated panel images. See [Section 5](#5-speech-bubble-system) for full design.

#### Stage 4: Page Layout

`page_layout.py` composes panels into full comic pages. See [Section 6](#6-page-layout-system) for full design.

#### Stage 5: Export

`export.py` assembles pages into final output:

```python
def export_pdf(pages, output_path, metadata):
    """Create a PDF from page images."""
    images = [Image.open(p) for p in pages]
    images[0].save(output_path, "PDF", save_all=True, 
                   append_images=images[1:], resolution=300)

def export_cbz(pages, output_path, metadata):
    """Create a CBZ (comic book archive) — just a ZIP of images."""
    with zipfile.ZipFile(output_path, 'w') as zf:
        for i, page in enumerate(pages):
            zf.write(page, f"page_{i+1:03d}.png")
        # Add ComicInfo.xml for metadata
        zf.writestr("ComicInfo.xml", build_comic_info_xml(metadata))
```

### 3.3 Error Handling Strategy

```
Error Type              │ Action
────────────────────────┼──────────────────────────────────
ComfyUI not reachable   │ Call ensure_running(), retry once, then fail with message
Queue timeout (>5 min)  │ Abort panel, log, retry with simpler prompt
VRAM OOM                │ Reduce resolution by 25%, retry
Workflow node error     │ Log error details, skip panel, continue others
Character ref failed    │ Retry with different seed (up to 3x)
All retries exhausted   │ Log to learnings.md, produce comic with available panels
IPAdapter not installed │ Fall back to prompt-only mode (no ref images)
```

**Error recovery flow:**

```python
class PanelGenerationError(Exception):
    def __init__(self, panel_id, stage, original_error, attempt):
        self.panel_id = panel_id
        self.stage = stage
        self.original_error = original_error
        self.attempt = attempt

def retry_with_fallback(func, panel, max_retries=3):
    """Retry with progressive fallback strategies."""
    strategies = [
        {"action": "retry_same"},           # Attempt 1: same params, different seed
        {"action": "reduce_resolution"},     # Attempt 2: 75% resolution
        {"action": "simplify_prompt"},       # Attempt 3: shorter prompt, no IPAdapter
    ]
    
    for i, strategy in enumerate(strategies[:max_retries]):
        try:
            return func(panel, **strategy)
        except Exception as e:
            log_error(panel["id"], strategy["action"], e, attempt=i+1)
    
    return None  # All retries failed
```

### 3.4 Output Directory Structure

```
output/comicmaster/{project_id}/
├── story_plan.json           # The plan (input)
├── refs/
│   ├── char_01_kai.png       # Character reference sheet
│   └── char_02_unit7.png
├── panels/
│   ├── panel_01.png          # Raw generated panels
│   ├── panel_02.png
│   └── ...
├── panels_bubbled/
│   ├── panel_01.png          # Panels with speech bubbles
│   ├── panel_02.png
│   └── ...
├── pages/
│   ├── page_01.png           # Composed comic pages
│   ├── page_02.png
│   └── ...
├── exports/
│   ├── comic.pdf
│   └── comic.cbz
├── generation_log.jsonl      # Per-panel timing, seeds, errors
└── metadata.json             # Project metadata, settings used
```

---

## 4. Character Consistency Strategy

### 4.1 Technology Comparison

| Method | Consistency | Speed | VRAM | Flexibility | Best For |
|---|---|---|---|---|---|
| **IPAdapter** | ★★★★☆ | ★★★★☆ | ~2GB extra | High — style + pose vary | **Primary choice** |
| **IPAdapter FaceID** | ★★★★★ | ★★★☆☆ | ~3GB extra | Medium — face-focused | Close-up panels |
| **InstantID** | ★★★★★ | ★★★☆☆ | ~3GB extra | Medium | Photorealistic faces |
| **ReActor** | ★★★☆☆ | ★★★★★ | ~1GB extra | Low — face swap only | Post-processing fix |
| **Seed Locking** | ★★☆☆☆ | ★★★★★ | None | Very low | Same pose/scene only |
| **LoRA (per character)** | ★★★★★ | ★★★★☆ | ~1GB extra | High | Recurring characters |
| **Prompt Consistency** | ★★☆☆☆ | ★★★★★ | None | High | Backup/supplement |

### 4.2 Recommended Strategy: Layered Approach

**Primary: IPAdapter (general body/style consistency)**

IPAdapter conditions the generation on a reference image. The model "understands" the visual style, clothing, body shape, and general facial features from the reference. This works well for maintaining overall character appearance across different poses and angles.

**Secondary: IPAdapter FaceID (face-specific consistency for close-ups)**

For medium and close-up shots where the face is prominent, IPAdapter FaceID provides stronger facial feature preservation. Switch to this workflow when `shot_type` is "close_up" or "medium_close".

**Tertiary: Prompt Engineering (always active)**

Every panel prompt includes the full character `visual_description`. This reinforces consistency even when IPAdapter has limited influence (e.g., wide shots where the character is small).

**Fallback: ReActor (post-processing face fix)**

If a generated panel has good composition but the face drifted, ReActor can swap in the reference face as a post-processing step. This is a repair mechanism, not a primary strategy.

### 4.3 IPAdapter Workflow Design

The `panel_ipadapter.json` ComfyUI workflow includes:

```
[LoadImage: char_ref] → [IPAdapter] → ┐
                                       ├→ [KSampler] → [VAEDecode] → [SaveImage]
[CLIPTextEncode: prompt] ─────────────→┘
[EmptyLatentImage] ───────────────────→┘
```

**Key IPAdapter parameters:**

```json
{
  "IPAdapterUnifiedLoader": {
    "preset": "PLUS (high strength)",
    "model": ["CheckpointLoader", 0]
  },
  "IPAdapterAdvanced": {
    "weight": 0.7,
    "weight_type": "style transfer",
    "combine_embeds": "average",
    "start_at": 0.0,
    "end_at": 0.8,
    "image": ["LoadImage_ref", 0]
  }
}
```

**Weight tuning by shot type:**

| Shot Type | IPAdapter Weight | FaceID Weight | Rationale |
|---|---|---|---|
| Extreme wide | 0.4 | — | Character is small; too much weight = artifacts |
| Wide | 0.5 | — | Body proportions matter more than face details |
| Medium | 0.65 | 0.3 | Balance between pose freedom and consistency |
| Medium close-up | 0.7 | 0.6 | Face becomes important |
| Close-up | 0.5 | 0.8 | Face is the focus; reduce body weight |
| Extreme close-up | 0.3 | 0.9 | Almost entirely face-driven |

### 4.4 Multi-Character Panels

When multiple characters appear in the same panel:

1. **Regional prompting** — Use ComfyUI's regional prompting nodes to assign different character descriptions to different areas of the image
2. **Primary character weighting** — If one character is the focus, use their ref as the IPAdapter input and describe the secondary character only via prompt
3. **Composite approach** — For 3+ characters, generate separately and composite (last resort, looks unnatural)

**Recommended approach for 2 characters:**

```
IPAdapter ref: Primary character (the one with more screen presence)
Prompt: Full descriptions of both characters with spatial hints
  e.g., "on the left, {char_A description}. On the right, {char_B description}."
```

### 4.5 Character Reference Sheet Specification

Each character gets ONE reference image optimized for IPAdapter:

- **Resolution:** 1024×1024
- **Content:** Single character, front-facing, neutral pose, clean background
- **Style:** Matching the comic's target style (manga/western/cartoon)
- **Background:** Simple solid or gradient (helps IPAdapter isolate the character)

**Prompt template for reference generation:**

```
character design sheet, {visual_description}, front view, standing pose, 
full body, simple white background, {style} art style, clean lines, 
high detail, professional character design, neutral expression,
studio lighting, centered composition
```

### 4.6 Required ComfyUI Custom Nodes

The following must be installed in ComfyUI:

| Node Pack | Purpose | Install |
|---|---|---|
| `ComfyUI_IPAdapter_plus` | IPAdapter unified loader + advanced | git clone in custom_nodes |
| `ComfyUI-Impact-Pack` | Face detection, segmentation | git clone in custom_nodes |
| (Optional) `ComfyUI_InstantID` | InstantID for photorealistic | git clone in custom_nodes |
| (Optional) `ReActor-UI` | Face swap post-processing | git clone in custom_nodes |

**Required model files for IPAdapter:**

```
ComfyUI/models/ipadapter/
├── ip-adapter-plus_sd15.safetensors       # For SD1.5 models
├── ip-adapter-plus_sdxl_vit-h.safetensors # For SDXL models
├── ip-adapter-plus-face_sdxl.safetensors  # FaceID for SDXL
└── ip-adapter-faceid-plusv2_sdxl.safetensors  # FaceID v2

ComfyUI/models/clip_vision/
├── CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors  # For IPAdapter
└── CLIP-ViT-bigG-14-laion2B-39B-b160k.safetensors  # Alternative
```

---

## 5. Speech Bubble System

### 5.1 Architecture

Pure Python implementation using PIL/Pillow. No ComfyUI dependency — this runs entirely on the panel images after generation.

```python
# speech_bubbles.py — Public API

class BubbleStyle(Enum):
    SPEECH = "speech"         # Standard round/oval bubble
    THOUGHT = "thought"       # Cloud-shaped bubble
    SHOUT = "shout"           # Spiky/jagged bubble
    WHISPER = "whisper"       # Dashed outline bubble
    NARRATION = "narration"   # Rectangular box (no tail)
    CAPTION = "caption"       # Top/bottom strip

class BubbleConfig:
    style: BubbleStyle
    text: str
    position: tuple[float, float]  # Normalized (0-1) position on panel
    tail_target: tuple[float, float] | None  # Where the tail points (speaker position)
    font_size: int | None     # Auto-calculated if None
    max_width: int | None     # Max bubble width in pixels
    color: str = "white"      # Bubble fill color
    border_color: str = "black"
    text_color: str = "black"
    bold: bool = False
    italic: bool = False

def add_bubbles(panel_image: Image, bubbles: list[BubbleConfig], 
                style: str = "western") -> Image:
    """Add all speech bubbles to a panel image."""
    ...

def auto_position_bubbles(panel_image: Image, dialogue: list[dict],
                          characters_present: list[str]) -> list[BubbleConfig]:
    """Automatically determine bubble positions based on panel composition."""
    ...
```

### 5.2 Bubble Shapes

#### Speech Bubble (Standard)

```
        ┌─────────────────────┐
       │                       │
       │   Hello, world!       │
       │                       │
        └──────────┬──────────┘
                    ╲
                     ╲  ← tail points to speaker
```

**Implementation:** Rounded rectangle with cubic Bézier tail.

```python
def draw_speech_bubble(draw, text, position, tail_target, font, config):
    # 1. Calculate text bounding box
    bbox = calculate_text_bbox(text, font, config.max_width)
    
    # 2. Add padding (15% of text size)
    padding = max(bbox.width, bbox.height) * 0.15
    bubble_rect = bbox.expand(padding)
    
    # 3. Draw rounded rectangle
    draw.rounded_rectangle(bubble_rect, radius=20, fill=config.color,
                          outline=config.border_color, width=3)
    
    # 4. Draw tail (triangular, pointing to speaker)
    if tail_target:
        draw_tail(draw, bubble_rect, tail_target, config)
    
    # 5. Draw text (with word wrapping)
    draw_wrapped_text(draw, text, bubble_rect, font, config.text_color)
```

#### Thought Bubble

```
        ○ ○ ○ ○ ○ ○ ○ ○ ○
       ○                   ○
       ○  I wonder if...   ○
       ○                   ○
        ○ ○ ○ ○ ○ ○ ○ ○ ○
              ○
            ○
          ○    ← small circles trail to speaker
```

**Implementation:** Cloud-like border using overlapping circles, with small circle trail for the tail.

```python
def draw_thought_bubble(draw, text, position, tail_target, font, config):
    # Draw cloud border using overlapping ellipses
    bbox = calculate_text_bbox(text, font, config.max_width)
    bubble_rect = bbox.expand(padding=20)
    
    # Perimeter circles
    for angle in range(0, 360, 15):
        cx = bubble_rect.center_x + bubble_rect.width * 0.5 * cos(radians(angle))
        cy = bubble_rect.center_y + bubble_rect.height * 0.5 * sin(radians(angle))
        r = 12
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=config.color,
                     outline=config.border_color, width=2)
    
    # Fill interior
    draw.rectangle(bubble_rect.shrink(10), fill=config.color)
    
    # Trail of small circles to speaker
    if tail_target:
        draw_thought_trail(draw, bubble_rect, tail_target, config)
    
    draw_wrapped_text(draw, text, bubble_rect, font, config.text_color)
```

#### Shout Bubble

```
       ╱ ╲ ╱ ╲ ╱ ╲ ╱ ╲ ╱ ╲
      ╱                       ╲
      ╲   WATCH OUT!!!        ╱
      ╱                       ╲
       ╲ ╱ ╲ ╱ ╲ ╱ ╲ ╱ ╲ ╱
                ╱
               ╱
```

**Implementation:** Star/spike polygon border with bold font.

```python
def draw_shout_bubble(draw, text, position, tail_target, font, config):
    bbox = calculate_text_bbox(text.upper(), font_bold, config.max_width)
    bubble_rect = bbox.expand(padding=25)
    
    # Generate spiky polygon
    points = generate_spike_polygon(bubble_rect, num_spikes=16, spike_depth=15)
    draw.polygon(points, fill=config.color, outline=config.border_color, width=3)
    
    if tail_target:
        draw_tail(draw, bubble_rect, tail_target, config)
    
    draw_wrapped_text(draw, text.upper(), bubble_rect, font_bold, config.text_color)
```

#### Narration Box

```
    ┌───────────────────────────┐
    │ The city had seen better  │
    │ days. Much better days.   │
    └───────────────────────────┘
```

**Implementation:** Simple rectangle with optional background color tint.

### 5.3 Auto-Positioning Algorithm

When `position_hint` is provided in the story plan, map it to normalized coordinates:

```python
POSITION_HINTS = {
    "top_left":     (0.20, 0.15),
    "top_center":   (0.50, 0.15),
    "top_right":    (0.80, 0.15),
    "middle_left":  (0.20, 0.50),
    "middle_right": (0.80, 0.50),
    "bottom_left":  (0.20, 0.85),
    "bottom_right": (0.80, 0.85),
}
```

**Smart positioning (when no hint):**

```python
def auto_position_bubbles(panel_image, dialogue_entries):
    """
    Position bubbles to:
    1. Not overlap each other
    2. Not cover character faces (if detectable)
    3. Follow reading order (top-left first for LTR)
    4. Stay within panel bounds with padding
    """
    positions = []
    
    # Analyze panel: find bright/dark regions, edges
    brightness_map = compute_brightness_map(panel_image, grid_size=8)
    
    # Prefer placing bubbles over:
    # - Bright, low-detail areas (sky, walls, simple backgrounds)
    # - Upper portion of the panel (natural reading flow)
    # Avoid:
    # - Center of action
    # - Character face regions
    
    for i, entry in enumerate(dialogue_entries):
        # Reading order: first dialogue top-left-ish, second top-right-ish
        preferred_y = 0.10 + (i * 0.08)  # Stack downward slightly
        preferred_x = 0.25 if i % 2 == 0 else 0.75  # Alternate sides
        
        # Find nearest "safe" position
        position = find_safe_position(
            preferred=(preferred_x, preferred_y),
            brightness_map=brightness_map,
            existing_positions=positions,
            panel_size=panel_image.size,
            bubble_size=estimate_bubble_size(entry["text"])
        )
        positions.append(position)
    
    return positions
```

### 5.4 Font System

```python
FONT_SETS = {
    "western": {
        "speech": "ComicNeue-Regular.ttf",
        "speech_bold": "ComicNeue-Bold.ttf",
        "shout": "Bangers-Regular.ttf",
        "narration": "PatrickHand-Regular.ttf",
        "caption": "Roboto-Regular.ttf",
    },
    "manga": {
        "speech": "NotoSansJP-Regular.ttf",     # or WildWords
        "speech_bold": "NotoSansJP-Bold.ttf",
        "shout": "RampartOne-Regular.ttf",
        "narration": "NotoSerifJP-Regular.ttf",
        "caption": "NotoSansJP-Medium.ttf",
    },
    "cartoon": {
        "speech": "Bangers-Regular.ttf",
        "speech_bold": "Bangers-Regular.ttf",
        "shout": "Bungee-Regular.ttf",
        "narration": "FredokaOne-Regular.ttf",
        "caption": "Nunito-Regular.ttf",
    },
}

def select_font(style, bubble_type, panel_height):
    """Select font and size based on style and panel dimensions."""
    font_file = FONT_SETS[style][bubble_type]
    font_path = os.path.join(ASSETS_DIR, "fonts", font_file)
    
    # Base size: ~3.5% of panel height (readable but not overwhelming)
    base_size = int(panel_height * 0.035)
    
    # Adjust by bubble type
    size_multipliers = {
        "speech": 1.0,
        "speech_bold": 1.0,
        "shout": 1.3,
        "narration": 0.9,
        "caption": 0.85,
    }
    
    font_size = int(base_size * size_multipliers.get(bubble_type, 1.0))
    return ImageFont.truetype(font_path, font_size)
```

### 5.5 Text Wrapping

```python
def wrap_text(text, font, max_width):
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = font.getbbox(test_line)
        width = bbox[2] - bbox[0]
        
        if width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines
```

---

## 6. Page Layout System

### 6.1 Architecture

Pure Python (PIL/Pillow). Composes individual panel images into full comic pages using configurable grid templates.

```python
# page_layout.py — Public API

class PageConfig:
    width: int = 2480          # A4 at 300dpi (portrait)
    height: int = 3508         # A4 at 300dpi (portrait)
    margin_top: int = 80       # Page margin (pixels)
    margin_bottom: int = 80
    margin_left: int = 60
    margin_right: int = 60
    gutter: int = 30           # Space between panels
    border_width: int = 3      # Panel border thickness
    border_color: str = "black"
    background_color: str = "white"
    page_number: bool = True
    page_number_font_size: int = 24

def compose_page(panels: list[Image], layout: str | dict, 
                 config: PageConfig = None) -> Image:
    """Compose panel images into a comic page."""
    ...

def compose_all_pages(story_plan: dict, panel_images: dict[str, Image],
                      config: PageConfig = None) -> list[Image]:
    """Compose all pages from a story plan."""
    ...
```

### 6.2 Grid Templates

Templates define how panels are arranged on a page. Each template specifies panel positions as normalized rectangles (0.0–1.0) within the usable area (page minus margins).

#### Standard Grids

**`page_2x2` — 4 panels (2 columns × 2 rows)**

```json
{
  "name": "page_2x2",
  "description": "Classic 4-panel grid",
  "panels": [
    {"x": 0.0,  "y": 0.0,  "w": 0.5, "h": 0.5},
    {"x": 0.5,  "y": 0.0,  "w": 0.5, "h": 0.5},
    {"x": 0.0,  "y": 0.5,  "w": 0.5, "h": 0.5},
    {"x": 0.5,  "y": 0.5,  "w": 0.5, "h": 0.5}
  ]
}
```

```
┌─────────┬─────────┐
│         │         │
│  Panel  │  Panel  │
│    1    │    2    │
│         │         │
├─────────┼─────────┤
│         │         │
│  Panel  │  Panel  │
│    3    │    4    │
│         │         │
└─────────┴─────────┘
```

**`page_3x2` — 6 panels (3 columns × 2 rows)**

```json
{
  "name": "page_3x2",
  "panels": [
    {"x": 0.0,   "y": 0.0, "w": 0.333, "h": 0.5},
    {"x": 0.333, "y": 0.0, "w": 0.333, "h": 0.5},
    {"x": 0.666, "y": 0.0, "w": 0.334, "h": 0.5},
    {"x": 0.0,   "y": 0.5, "w": 0.333, "h": 0.5},
    {"x": 0.333, "y": 0.5, "w": 0.333, "h": 0.5},
    {"x": 0.666, "y": 0.5, "w": 0.334, "h": 0.5}
  ]
}
```

**`page_2x3` — 6 panels (2 columns × 3 rows)**

```json
{
  "name": "page_2x3",
  "panels": [
    {"x": 0.0, "y": 0.0,   "w": 0.5, "h": 0.333},
    {"x": 0.5, "y": 0.0,   "w": 0.5, "h": 0.333},
    {"x": 0.0, "y": 0.333, "w": 0.5, "h": 0.333},
    {"x": 0.5, "y": 0.333, "w": 0.5, "h": 0.333},
    {"x": 0.0, "y": 0.666, "w": 0.5, "h": 0.334},
    {"x": 0.5, "y": 0.666, "w": 0.5, "h": 0.334}
  ]
}
```

**`page_2x4` — 8 panels (2 columns × 4 rows)**

```json
{
  "name": "page_2x4",
  "panels": [
    {"x": 0.0, "y": 0.0,   "w": 0.5, "h": 0.25},
    {"x": 0.5, "y": 0.0,   "w": 0.5, "h": 0.25},
    {"x": 0.0, "y": 0.25,  "w": 0.5, "h": 0.25},
    {"x": 0.5, "y": 0.25,  "w": 0.5, "h": 0.25},
    {"x": 0.0, "y": 0.5,   "w": 0.5, "h": 0.25},
    {"x": 0.5, "y": 0.5,   "w": 0.5, "h": 0.25},
    {"x": 0.0, "y": 0.75,  "w": 0.5, "h": 0.25},
    {"x": 0.5, "y": 0.75,  "w": 0.5, "h": 0.25}
  ]
}
```

#### Irregular Layouts

**`page_irregular_action` — Action sequence (1 big + 3 small)**

```
┌───────────────────┐
│                   │
│    Panel 1 (big)  │
│                   │
├──────┬──────┬─────┤
│  P2  │  P3  │ P4  │
│      │      │     │
└──────┴──────┴─────┘
```

```json
{
  "name": "page_irregular_action",
  "panels": [
    {"x": 0.0, "y": 0.0, "w": 1.0,   "h": 0.6},
    {"x": 0.0, "y": 0.6, "w": 0.333, "h": 0.4},
    {"x": 0.333, "y": 0.6, "w": 0.333, "h": 0.4},
    {"x": 0.666, "y": 0.6, "w": 0.334, "h": 0.4}
  ]
}
```

**`page_irregular_splash` — Splash page (1 dominant + 2 small)**

```
┌──────────────┬─────┐
│              │  P2 │
│   Panel 1    ├─────┤
│   (splash)   │  P3 │
│              │     │
└──────────────┴─────┘
```

```json
{
  "name": "page_irregular_splash",
  "panels": [
    {"x": 0.0, "y": 0.0, "w": 0.7, "h": 1.0},
    {"x": 0.7, "y": 0.0, "w": 0.3, "h": 0.5},
    {"x": 0.7, "y": 0.5, "w": 0.3, "h": 0.5}
  ]
}
```

**`page_manga_4koma` — 4-panel vertical strip**

```
┌─────────────────┐
│     Panel 1     │
├─────────────────┤
│     Panel 2     │
├─────────────────┤
│     Panel 3     │
├─────────────────┤
│     Panel 4     │
└─────────────────┘
```

```json
{
  "name": "page_manga_4koma",
  "panels": [
    {"x": 0.0, "y": 0.0,   "w": 1.0, "h": 0.25},
    {"x": 0.0, "y": 0.25,  "w": 1.0, "h": 0.25},
    {"x": 0.0, "y": 0.5,   "w": 1.0, "h": 0.25},
    {"x": 0.0, "y": 0.75,  "w": 1.0, "h": 0.25}
  ]
}
```

### 6.3 Composition Algorithm

```python
def compose_page(panel_images, layout_template, config):
    """
    Compose panels into a single page image.
    
    1. Create blank page canvas
    2. Calculate usable area (page minus margins)
    3. For each panel slot in the template:
       a. Calculate pixel position and size from normalized coords
       b. Resize/crop panel image to fit slot (preserving aspect ratio)
       c. Paste panel onto canvas
       d. Draw border around panel
    4. Add gutters (the white space is natural from margins)
    5. Add page number if configured
    """
    page = Image.new("RGB", (config.width, config.height), config.background_color)
    draw = ImageDraw.Draw(page)
    
    usable_x = config.margin_left
    usable_y = config.margin_top
    usable_w = config.width - config.margin_left - config.margin_right
    usable_h = config.height - config.margin_top - config.margin_bottom
    
    for i, slot in enumerate(layout_template["panels"]):
        if i >= len(panel_images):
            break
        
        # Calculate pixel position (with gutter offsets)
        px = usable_x + int(slot["x"] * usable_w) + (config.gutter // 2)
        py = usable_y + int(slot["y"] * usable_h) + (config.gutter // 2)
        pw = int(slot["w"] * usable_w) - config.gutter
        ph = int(slot["h"] * usable_h) - config.gutter
        
        # Resize panel to fit slot (cover mode — crop to fill)
        panel_resized = resize_cover(panel_images[i], pw, ph)
        
        # Paste panel
        page.paste(panel_resized, (px, py))
        
        # Draw border
        draw.rectangle([px, py, px + pw, py + ph], 
                       outline=config.border_color, width=config.border_width)
    
    # Page number
    if config.page_number and hasattr(config, '_page_num'):
        draw_page_number(draw, config._page_num, config)
    
    return page

def resize_cover(image, target_w, target_h):
    """Resize image to cover target area, cropping excess (center crop)."""
    img_ratio = image.width / image.height
    target_ratio = target_w / target_h
    
    if img_ratio > target_ratio:
        # Image is wider — fit height, crop width
        new_h = target_h
        new_w = int(target_h * img_ratio)
    else:
        # Image is taller — fit width, crop height
        new_w = target_w
        new_h = int(target_w / img_ratio)
    
    resized = image.resize((new_w, new_h), Image.LANCZOS)
    
    # Center crop
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))
```

### 6.4 Reading Direction

| Style | Direction | Panel Order |
|---|---|---|
| Western / Marvel | Left-to-right, top-to-bottom | 1→2→3→4 (Z-pattern) |
| Manga (traditional) | Right-to-left, top-to-bottom | 2←1, 4←3 |
| Webcomic / 4-koma | Top-to-bottom | Vertical scroll |

The reading direction affects:
1. **Panel ordering** — which panel goes where in the template
2. **Speech bubble ordering** — dialogue in the first-read panel comes first
3. **Page numbering** — for RTL manga, the "first" page is what would be "last" in LTR

```python
def apply_reading_direction(panels, layout, direction="ltr"):
    """Reorder panels for the given reading direction."""
    if direction == "rtl":
        # Mirror the layout: swap left/right positions
        mirrored_layout = mirror_layout_horizontal(layout)
        return panels, mirrored_layout
    return panels, layout
```

### 6.5 Page Dimensions

| Format | Size (px) | DPI | Physical Size |
|---|---|---|---|
| A4 Portrait (print) | 2480 × 3508 | 300 | 210 × 297 mm |
| US Letter (print) | 2550 × 3300 | 300 | 8.5 × 11 in |
| US Comic (print) | 2063 × 3150 | 300 | 6.875 × 10.5 in |
| Digital (screen) | 1600 × 2400 | 150 | — |
| Webtoon (scroll) | 800 × variable | 72 | — |

Default: **2480 × 3508** (A4 at 300dpi) — works for both print and screen.

---

## 7. Memory / Learning System

### 7.1 Purpose

Track what works and what doesn't across comic generations. This enables:
- Better prompt engineering over time
- Knowing which presets/models work best for which styles
- Avoiding repeated mistakes
- Building a knowledge base for the agent

### 7.2 learnings.md Schema

```markdown
# ComicMaster Learnings

## Generation Log

### [DATE] [PROJECT_ID] — [TITLE]
- **Style:** manga | western | cartoon
- **Preset:** dreamshaperXL
- **Panels:** 12/12 succeeded
- **Total time:** 14m 32s
- **Character consistency:** 8/10
- **Overall quality:** 7/10

**What worked:**
- IPAdapter weight 0.7 gave good face consistency for medium shots
- "clean lines, high contrast" in prompt improved manga look
- 4-panel pages with 2x2 grid looked best for dialogue scenes

**What didn't work:**
- Wide shots with IPAdapter weight > 0.6 caused face artifacts
- Three characters in one panel — IPAdapter couldn't handle it
- Shout bubbles overlapped panel borders on small panels

**Prompt patterns that worked:**
- "[shot_type] shot, [camera_angle], [style] art style, comic panel" as prefix
- Adding "dramatic lighting" improved action scenes significantly
- "simple background" in ref prompts prevents busy reference sheets

**Technical notes:**
- Panel generation: avg 18s each (dreamshaperXL, 8 steps)
- Character refs: 22s each at 1024x1024
- Total pipeline: ~5min for 12 panels + layout

---
```

### 7.3 generation_log.jsonl Schema

Each project also gets a machine-readable log:

```json
{
  "project_id": "comic_20260208_001",
  "timestamp": "2026-02-08T20:30:00",
  "title": "The Last Robot",
  "style": "manga",
  "preset": "dreamshaperXL",
  "total_panels": 12,
  "successful_panels": 12,
  "failed_panels": 0,
  "total_duration_s": 872,
  "character_refs": [
    {
      "character_id": "char_01",
      "seed": 42,
      "generation_time_s": 22,
      "quality_rating": null
    }
  ],
  "panels": [
    {
      "panel_id": "panel_01",
      "prompt_hash": "abc123",
      "seed": 8192,
      "generation_time_s": 18,
      "attempts": 1,
      "ipadapter_weight": 0.7,
      "shot_type": "wide",
      "characters_present": ["char_01"],
      "quality_rating": null,
      "errors": []
    }
  ],
  "pages": [
    {
      "page_number": 1,
      "layout": "page_2x2",
      "panel_ids": ["panel_01", "panel_02", "panel_03", "panel_04"]
    }
  ]
}
```

### 7.4 Automatic Learning Extraction

After each generation, the pipeline appends to `learnings.md`:

```python
def log_learnings(project_data, generation_log):
    """Extract learnings and append to learnings.md."""
    learnings = []
    
    # Detect patterns
    if generation_log["failed_panels"] > 0:
        failed = [p for p in generation_log["panels"] if p["attempts"] > 1]
        for p in failed:
            learnings.append(f"Panel {p['panel_id']} needed {p['attempts']} attempts: {p['errors']}")
    
    avg_time = sum(p["generation_time_s"] for p in generation_log["panels"]) / len(generation_log["panels"])
    learnings.append(f"Average panel time: {avg_time:.1f}s with {project_data['preset']}")
    
    # Append to file
    with open(LEARNINGS_PATH, "a") as f:
        f.write(f"\n### {datetime.now().strftime('%Y-%m-%d')} {project_data['project_id']} — {project_data['title']}\n")
        for l in learnings:
            f.write(f"- {l}\n")
```

### 7.5 Agent-Side Quality Review

After the pipeline finishes, the agent (Claude) can:
1. View the generated pages using the `image` tool
2. Rate character consistency (are faces/bodies consistent?)
3. Rate composition quality (do panels look good?)
4. Add qualitative notes to `learnings.md`
5. Decide whether to regenerate specific panels

This creates a feedback loop:
```
Generate → Review → Rate → Log → Learn → Generate Better Next Time
```

---

## 8. Improvement Suggestions

### 8.1 Style Transfer / LoRA Switching

**Current limitation:** Changing art style mid-comic means characters may look different.

**Solution:** Style LoRAs that can be applied on top of the base model.

```python
# In panel_generator.py, optionally inject a LoRA
STYLE_LORAS = {
    "manga": "manga_style_lora_v2.safetensors",
    "marvel": "western_comic_lora.safetensors",
    "watercolor": "watercolor_style_lora.safetensors",
    "noir": "noir_comic_lora.safetensors",
}

# Workflow addition: LoRA loader node between checkpoint and sampler
# Weight: 0.6-0.8 for style, keeping character consistency from IPAdapter
```

**Priority:** Medium — enhances style variety but requires downloading/training LoRAs.

### 8.2 Dynamic Panel Sizing Based on Action

Instead of fixed grids, the story planner could assign **narrative weight** to each panel:

```json
{
  "panel_id": "panel_05",
  "narrative_weight": "high",  // low, medium, high, splash
  "action_intensity": 0.9      // 0.0 (calm) to 1.0 (explosive)
}
```

The layout engine then:
- Gives "high" weight panels more space (60% of row instead of 50%)
- Makes "splash" panels full-width
- Shrinks "low" weight panels (reaction shots, transitions)

```python
WEIGHT_TO_SIZE = {
    "low":     0.7,   # 70% of equal share
    "medium":  1.0,   # Equal share
    "high":    1.4,   # 140% of equal share  
    "splash":  2.0,   # Full width
}
```

**Priority:** High — significantly improves visual storytelling.

### 8.3 Automatic Camera Angle Selection

The story planner (agent) should select camera angles based on narrative purpose:

| Narrative Purpose | Camera Angle | Shot Type |
|---|---|---|
| Establishing scene | High angle / bird's eye | Wide / extreme wide |
| Character introduction | Low angle (heroic) | Medium |
| Dialogue | Eye level | Medium / medium close-up |
| Emotion / reaction | Eye level or slight Dutch | Close-up |
| Action / impact | Low angle or Dutch angle | Medium or wide |
| Suspense / mystery | High angle | Wide (isolating) |
| Power dynamics | Low angle (dominant) / high angle (submissive) | Medium |
| Transition / passage of time | Extreme wide | Establishing |

**Reference document** (`references/panel-composition.md`) guides the agent:

```markdown
## Camera Angle Guide

### Low Angle (worm's eye)
- Makes characters look powerful, heroic, imposing
- Use for: character introductions, power moments, villains
- Prompt tag: "low angle view, looking up at character"

### High Angle (bird's eye)  
- Makes characters look small, vulnerable, overwhelmed
- Use for: establishing shots, moments of defeat, loneliness
- Prompt tag: "high angle view, looking down, bird's eye perspective"

### Eye Level
- Neutral, relatable, puts viewer on equal footing
- Use for: dialogue, everyday scenes, emotional moments
- Prompt tag: "eye level view, straight on perspective"

### Dutch Angle (tilted)
- Creates tension, unease, dynamism
- Use for: action, suspense, psychological moments
- Prompt tag: "dutch angle, tilted camera, dynamic perspective"
```

**Priority:** Medium — improves visual variety but the agent already has narrative understanding.

### 8.4 Multi-Language Support

Text in speech bubbles should support multiple languages:

```python
# Extend BubbleConfig
class BubbleConfig:
    ...
    language: str = "en"       # ISO 639-1 code
    
# Font selection by language
LANGUAGE_FONTS = {
    "en": "ComicNeue-Regular.ttf",
    "de": "ComicNeue-Regular.ttf",
    "ja": "NotoSansJP-Regular.ttf",
    "ko": "NotoSansKR-Regular.ttf",
    "zh": "NotoSansSC-Regular.ttf",
    "ar": "NotoSansArabic-Regular.ttf",  # RTL!
}

# RTL language handling
RTL_LANGUAGES = {"ar", "he", "fa", "ur"}

def render_text(text, language, font):
    if language in RTL_LANGUAGES:
        # Use python-bidi + arabic-reshaper
        text = reshape_rtl_text(text)
    return draw.text(...)
```

**Priority:** Low — nice to have, most comics are single-language.

### 8.5 Export Formats

| Format | Use Case | Implementation |
|---|---|---|
| **PNG pages** | Default, universal | Already in pipeline |
| **PDF** | Print, sharing | `Pillow` or `reportlab` |
| **CBZ** | Comic readers (Calibre, etc.) | ZIP of PNGs + ComicInfo.xml |
| **WebP** | Web sharing, smaller files | `Pillow` WebP save |
| **EPUB** | E-readers | Fixed-layout EPUB3 |
| **Webtoon scroll** | Vertical scroll format | Single tall PNG per chapter |

**Priority:** Medium — PDF and CBZ are easy wins.

### 8.6 Additional Improvements

#### Panel-to-Panel Transitions

Classify transitions between panels for better storytelling:

| Transition | Description | Example |
|---|---|---|
| Moment-to-moment | Tiny time jump | Character blinking |
| Action-to-action | Single subject, different action | Character drawing sword → swinging |
| Subject-to-subject | Same scene, different subject | Hero → Villain in same scene |
| Scene-to-scene | Time/place change | Day → Night, City → Forest |
| Aspect-to-aspect | Same scene, different detail | Wide shot → Close-up of a clock |

This helps the agent vary camera angles and panel sizes appropriately.

#### Upscaling Pipeline

After panel generation at 768×768, optionally upscale to 1536×1536 or higher:

```python
# Use ComfyUI's built-in upscaling or a dedicated workflow
def upscale_panel(panel_path, scale=2):
    workflow = load_workflow("panel_upscale.json")
    workflow = inject_image(workflow, panel_path)
    workflow = set_scale(workflow, scale)
    return comfy_client.generate_and_download(workflow, output_dir)
```

**Priority:** Low — 768px is sufficient for most layouts at 300dpi.

#### Sound Effects (Onomatopoeia)

Add stylized sound effect text (BAM!, WHOOSH!, CRACK!) outside bubbles:

```python
class SFXConfig:
    text: str               # "BOOM!"
    position: tuple         # Where on the panel
    rotation: float         # Degrees of rotation
    font_size: int          # Large, impactful
    color: str              # Often red, yellow, or white
    outline_color: str      # Black outline for visibility
    style: str              # "impact", "speed_lines", "explosion"
```

**Priority:** Medium — adds significant visual punch to action scenes.

#### Batch Optimization

For 100-panel comics, optimize ComfyUI usage:

```python
# Group panels by character composition to minimize model/IPAdapter reloads
def optimize_generation_order(panels):
    """
    Sort panels to minimize ComfyUI model switches.
    Panels with same characters can share IPAdapter state.
    """
    from itertools import groupby
    
    # Sort by character set
    panels_sorted = sorted(panels, key=lambda p: tuple(sorted(p["characters_present"])))
    
    # Generate in batches per character group
    for chars, group in groupby(panels_sorted, key=lambda p: tuple(sorted(p["characters_present"]))):
        # All panels in this group use the same IPAdapter refs
        yield list(group)
```

**Priority:** High for large comics — significant time savings.

---

## 9. Implementation Priority

### Phase 1: MVP (Week 1-2)

**Goal:** Generate a basic 8-panel comic from a prompt.

| Task | Script | Dependency |
|---|---|---|
| Story plan JSON schema + validation | `story_planner.py` | None |
| Basic panel generation (prompt-only, no IPAdapter) | `panel_generator.py` | `comfy_client.py` |
| Simple speech bubbles (round only, manual position) | `speech_bubbles.py` | Pillow |
| 2×2 and 2×4 page layouts | `page_layout.py` | Pillow |
| Pipeline orchestrator (linear, no retry) | `comic_pipeline.py` | All above |
| SKILL.md with agent instructions | `SKILL.md` | — |

**Output:** Working end-to-end pipeline, no character consistency yet.

### Phase 2: Character Consistency (Week 3-4)

**Goal:** Maintain character appearance across panels.

| Task | Script | Dependency |
|---|---|---|
| Character reference generation | `character_ref.py` | `comfy_client.py` |
| IPAdapter workflow design | `workflows/panel_ipadapter.json` | ComfyUI_IPAdapter_plus |
| IPAdapter integration in panel generator | `panel_generator.py` | IPAdapter workflow |
| IPAdapter weight tuning by shot type | `panel_generator.py` | Testing |
| Retry logic with fallback strategies | `comic_pipeline.py` | — |

**Output:** Characters look consistent across panels.

### Phase 3: Polish (Week 5-6)

**Goal:** Professional-looking output.

| Task | Script | Dependency |
|---|---|---|
| All bubble types (thought, shout, whisper, narration) | `speech_bubbles.py` | — |
| Auto-positioning for bubbles | `speech_bubbles.py` | — |
| Irregular page layouts | `page_layout.py` | — |
| PDF/CBZ export | `export.py` | — |
| Comic fonts (download/install) | `assets/fonts/` | — |
| Style guides and composition references | `references/` | — |
| Learning system | `memory/learnings.md` | — |

**Output:** Polished, export-ready comics.

### Phase 4: Advanced (Ongoing)

- Dynamic panel sizing
- LoRA style switching
- Sound effects
- Multi-language support
- IPAdapter FaceID for close-ups
- Batch optimization for large comics
- Upscaling pipeline

---

## Appendix: Data Schemas

### A.1 story_plan.json — Full Schema

```typescript
interface StoryPlan {
  title: string;
  style: "manga" | "western" | "cartoon" | "realistic" | "noir";
  reading_direction: "ltr" | "rtl";
  preset: string;  // ComfyUI preset name from presets.json
  
  characters: Character[];
  panels: Panel[];
  pages: Page[];
}

interface Character {
  id: string;           // e.g., "char_01"
  name: string;
  role: "protagonist" | "antagonist" | "supporting" | "background";
  visual_description: string;  // Detailed visual appearance for prompts
  personality: string;         // For dialogue tone
}

interface Panel {
  id: string;           // e.g., "panel_01"
  sequence: number;     // Global ordering
  scene: string;        // Scene/environment description
  action: string;       // What's happening
  characters_present: string[];  // Character IDs
  camera_angle: "eye_level" | "low_angle" | "high_angle" | "dutch_angle" | "birds_eye" | "worms_eye";
  shot_type: "extreme_wide" | "wide" | "medium" | "medium_close" | "close_up" | "extreme_close";
  mood: string;         // Atmospheric description
  dialogue: Dialogue[];
  narration?: string;   // Narrator text box
  narrative_weight?: "low" | "medium" | "high" | "splash";
  sfx?: string;         // Sound effect text (e.g., "BOOM!")
}

interface Dialogue {
  character: string;    // Character ID
  text: string;
  type: "speech" | "thought" | "shout" | "whisper";
  position_hint?: "top_left" | "top_center" | "top_right" | 
                  "middle_left" | "middle_right" | 
                  "bottom_left" | "bottom_right";
}

interface Page {
  page_number: number;
  layout: string;       // Template name (e.g., "page_2x2")
  panel_ids: string[];  // Panel IDs to place on this page
}
```

### A.2 config.json — ComicMaster Config

```json
{
  "defaults": {
    "preset": "dreamshaperXL",
    "style": "western",
    "reading_direction": "ltr",
    "panel_size": [768, 768],
    "page_size": [2480, 3508],
    "page_dpi": 300,
    "max_retries": 3,
    "generation_timeout": 300
  },
  "ipadapter": {
    "enabled": true,
    "default_weight": 0.7,
    "face_id_enabled": false,
    "ref_resolution": [1024, 1024]
  },
  "bubbles": {
    "default_font_set": "western",
    "outline_width": 3,
    "padding_ratio": 0.15
  },
  "layout": {
    "margin": [80, 80, 60, 60],
    "gutter": 30,
    "border_width": 3
  },
  "output": {
    "base_dir": "/home/mcmuff/clawd/output/comicmaster",
    "export_formats": ["png", "pdf"]
  }
}
```

### A.3 Workflow JSON Structure — panel_ipadapter.json

This is the ComfyUI API workflow for generating a panel with IPAdapter character consistency:

```json
{
  "_comment": "Panel generation with IPAdapter character consistency. Placeholders: PROMPT, NEGATIVE, SEED, WIDTH, HEIGHT, REF_IMAGE_PATH, IPADAPTER_WEIGHT",
  
  "4": {
    "class_type": "CheckpointLoaderSimple",
    "inputs": {
      "ckpt_name": "PLACEHOLDER_MODEL"
    }
  },
  "5": {
    "class_type": "EmptyLatentImage",
    "inputs": {
      "width": "PLACEHOLDER_WIDTH",
      "height": "PLACEHOLDER_HEIGHT",
      "batch_size": 1
    }
  },
  "6": {
    "class_type": "CLIPTextEncode",
    "inputs": {
      "text": "PLACEHOLDER_PROMPT",
      "clip": ["4", 1]
    }
  },
  "7": {
    "class_type": "CLIPTextEncode",
    "inputs": {
      "text": "PLACEHOLDER_NEGATIVE",
      "clip": ["4", 1]
    }
  },
  "10": {
    "class_type": "LoadImage",
    "inputs": {
      "image": "PLACEHOLDER_REF_IMAGE"
    },
    "_meta": {"title": "Character Reference Image"}
  },
  "11": {
    "class_type": "IPAdapterUnifiedLoader",
    "inputs": {
      "preset": "PLUS (high strength)",
      "model": ["4", 0]
    }
  },
  "12": {
    "class_type": "IPAdapterAdvanced",
    "inputs": {
      "weight": "PLACEHOLDER_IPADAPTER_WEIGHT",
      "weight_type": "style transfer",
      "combine_embeds": "average",
      "start_at": 0.0,
      "end_at": 0.8,
      "model": ["11", 0],
      "ipadapter": ["11", 1],
      "image": ["10", 0]
    }
  },
  "3": {
    "class_type": "KSampler",
    "inputs": {
      "seed": "PLACEHOLDER_SEED",
      "steps": "PLACEHOLDER_STEPS",
      "cfg": "PLACEHOLDER_CFG",
      "sampler_name": "PLACEHOLDER_SAMPLER",
      "scheduler": "PLACEHOLDER_SCHEDULER",
      "denoise": 1.0,
      "model": ["12", 0],
      "positive": ["6", 0],
      "negative": ["7", 0],
      "latent_image": ["5", 0]
    }
  },
  "8": {
    "class_type": "VAEDecode",
    "inputs": {
      "samples": ["3", 0],
      "vae": ["4", 2]
    }
  },
  "9": {
    "class_type": "SaveImage",
    "inputs": {
      "filename_prefix": "comicmaster_panel",
      "images": ["8", 0]
    }
  }
}
```

---

## Summary

ComicMaster is designed as a modular, agent-driven comic creation pipeline that:

1. **Leverages the existing ComfyUI infrastructure** — no duplication of `comfy_client.py` or the preset system
2. **Uses the agent (Claude) as the story planner** — no external LLM calls needed
3. **Maintains character consistency via IPAdapter** — layered approach with progressive fallbacks
4. **Produces professional output** — speech bubbles, page layouts, and export formats
5. **Learns from each generation** — structured logging enables continuous improvement

The phased implementation plan allows shipping a working MVP quickly (prompt → panels → pages) while incrementally adding character consistency, polish, and advanced features.

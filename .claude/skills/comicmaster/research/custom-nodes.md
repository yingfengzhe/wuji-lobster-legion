# ComfyUI Custom Nodes for Comic/Manga Page Creation

> Research date: 2026-02-08  
> Purpose: Evaluate and document nodes for automated comic/manga page generation pipeline

---

## Table of Contents

1. [Page Layout Nodes](#1-page-layout-nodes)
   - [comfyui-panelforge (Pixstri)](#11-comfyui-panelforge-pixstri)
   - [ComfyUI_Comfyroll_CustomNodes](#12-comfyui_comfyroll_customnodes)
   - [comfyui_panels (bmad4ever)](#13-comfyui_panels-bmad4ever---bonus-find)
2. [Character Consistency Nodes](#2-character-consistency-nodes)
   - [ComfyUI_IPAdapter_plus](#21-comfyui_ipadapter_plus)
   - [ComfyUI-ReActor](#22-comfyui-reactor)
   - [ComfyUI_InstantID](#23-comfyui_instantid)
3. [Speech Bubble & Text Overlay](#3-speech-bubble--text-overlay-solutions)
4. [Recommended Pipeline](#4-recommended-pipeline)

---

## 1. Page Layout Nodes

### 1.1 comfyui-panelforge (Pixstri)

**Repository:** https://github.com/lisaks/comfyui-panelforge  
**License:** MIT  
**Status:** Active (relatively new/lightweight)

#### How Page → Row → Frame Hierarchy Works

Pixstri uses a **three-tier hierarchical node system**:

```
Page Node (top-level container)
├── Row Node 1 (horizontal arrangement)
│   ├── Frame Node 1 (individual panel + image)
│   ├── Frame Node 2
│   └── Frame Node 3
├── Row Node 2
│   ├── Frame Node 4
│   └── Frame Node 5
└── Row Node 3
    └── Frame Node 6 (full-width panel)
```

- **Frame Node**: Individual comic panels. Accepts an image as input. Provides image preview.
- **Row Node**: Organizes multiple Frame nodes **horizontally** in a row. Accepts multiple Frame nodes as input.
- **Page Node**: Top-level container. Accepts multiple Row nodes. Outputs the complete comic page image.

Each node provides its own image preview, so you can see individual frames, rows, and the assembled page.

#### Speech Bubble / Text Overlay

⚠️ **Not built-in.** The README mentions "speech bubbles" in the repo description, but the current implementation focuses purely on panel layout. Speech bubbles would need to be handled by other nodes or post-processing.

#### Installation

```bash
# Option 1: ComfyUI Manager
# Search for "Pixstri" in Manager → Install

# Option 2: Manual
cd ComfyUI/custom_nodes
git clone https://github.com/lisaks/comfyui-panelforge.git
# Restart ComfyUI
```

#### Requirements
- ComfyUI, PyTorch, NumPy, Pillow (PIL)
- No additional model downloads needed

#### Assessment
- ✅ Very intuitive Page→Row→Frame hierarchy
- ✅ Lightweight, no model dependencies
- ⚠️ Limited to grid-like layouts (rows of frames)
- ❌ No diagonal/overlapping panels
- ❌ No built-in speech bubbles despite repo description

---

### 1.2 ComfyUI_Comfyroll_CustomNodes

**Repository:** https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes  
**License:** MIT  
**Version:** 1.76  
**Status:** Mature, actively maintained, massive node collection

This is a huge node pack (100+ nodes). The comic-relevant nodes are in the **Graphics** category.

#### CR Comic Panel Templates

Located under: `👽 Graphics - Template`

**Template Naming Convention:**
| Prefix | Meaning | Example | Result |
|--------|---------|---------|--------|
| `G` | Grid | `G22` | 2×2 grid (4 panels) |
| `G` | Grid | `G33` | 3×3 grid (9 panels) |
| `G` | Grid | `G23` | 2 cols × 3 rows |
| `H` | Horizontal rows | `H3` | 3 horizontal rows |
| `H` | Horizontal rows | `H22` | 2 rows, 2 panels each |
| `V` | Vertical columns | `V2` | 2 vertical columns |
| `V` | Vertical columns | `V33` | 3 cols, 3 panels each |

**Valid ranges:**
- `G11` to `G99` for grids
- `H11` to `H999999999` for horizontal rows
- `V11` to `V999999999` for vertical columns
- Zero is **not** permitted (e.g., `H30` is invalid)

**Input Parameters:**
- `template` — Layout code (G22, H3, V2, etc.)
- `page` — Canvas with width/height
- `border_thickness` — Pixel spacing between panels
- `outline_thickness` — Panel outline width
- `panel_color` — Panel background color (hex)
- `bg_color` — Page background color (hex)
- `outline_color` — Panel outline color (hex)
- `images` — List of images to fill panels
- `reading_direction` — LTR or RTL

**Output:** `comic_page` — Final assembled comic page image

#### CR Page Layout

Located under: `🌁 Graphics - Layout`

More flexible than Comic Panel Templates. Allows:
- Custom page dimensions (`page_width`, `page_height`)
- Template selection with custom overrides
- `custom_panel_layout` parameter for non-standard layouts
- Full color customization (outline, panel, background — RGB hex)
- Reading direction control (LTR/RTL)
- Automatic image distribution across panels

#### CR Image Panel / CR Image Grid Panel

Additional layout nodes for simpler arrangements:
- **CR Image Panel**: Side-by-side or stacked image panels
- **CR Image Grid Panel**: Grid of images with customizable spacing

#### CR Overlay Text / CR Draw Text / CR Composite Text

Text nodes in `🔤 Graphics - Text`:
- **CR Overlay Text**: Text overlay on images
- **CR Draw Text**: Draw text on canvas
- **CR Mask Text**: Create text-shaped masks
- **CR Composite Text**: Composite text with backgrounds
- **CR Select Font**: Font selection from system fonts

#### Installation

```bash
# Option 1: ComfyUI Manager
# Search for "Comfyroll Studio" → Install

# Option 2: Manual
cd ComfyUI/custom_nodes
git clone https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes.git
# Restart ComfyUI

# Option 3: CivitAI download
# https://civitai.com/models/87609
```

#### Requirements
- No additional models needed
- Fonts: Place custom fonts in `ComfyUI_Comfyroll_CustomNodes/fonts/` folder

#### Assessment
- ✅ Very mature, well-documented, extensive wiki
- ✅ Flexible template system (G/H/V codes)
- ✅ Built-in text overlay capabilities
- ✅ Supports LTR and RTL reading directions
- ✅ Custom colors, borders, outlines
- ⚠️ Templates are grid-based (no diagonal cuts or overlapping panels)
- ⚠️ No speech bubble shapes (only text overlay)

---

### 1.3 comfyui_panels (bmad4ever) — Bonus Find

**Repository:** https://github.com/bmad4ever/comfyui_panels  
**Status:** Active, well-designed

#### Why This Is Interesting

This is the **most advanced** panel layout system found. Uses shapely.Polygon for arbitrary panel shapes.

**Key Features:**
- **Hierarchical cut system**: Start with a full page, make cuts (horizontal/vertical) to create panels
- **Cut properties**: Direction, position (5 options), angle (for aesthetic deviation), number of cuts
- **Panel modifications**: Rotate, Scale, Translate, Skew, Bevel, Offset polygon bounds
- **Panel detection**: Can extract panel layouts from existing comic/manga images using CV
- **Panel edges**: Solid, dashed, or dotted border lines
- **Character-over-panels**: Support for characters breaking panel boundaries
- **Bleedout**: Panels extending beyond borders
- **Save/Load layouts**: Reusable layout files

**Reading Direction:** LTR and RTL support (determined by cut order)

#### Installation

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/bmad4ever/comfyui_panels.git
pip install shapely  # Required dependency
# Restart ComfyUI
```

#### Assessment
- ✅ Most powerful/flexible panel system
- ✅ Arbitrary panel shapes (not just grids)
- ✅ Angled cuts for dynamic layouts
- ✅ Character-over-panel effects
- ✅ Can import layouts from real manga pages
- ⚠️ More complex to set up
- ⚠️ Requires understanding of the cut hierarchy

---

## 2. Character Consistency Nodes

### 2.1 ComfyUI_IPAdapter_plus

**Repository:** https://github.com/cubiq/ComfyUI_IPAdapter_plus  
**Author:** cubiq  
**Status:** ⚠️ Maintenance-only mode (as of 2025-04-14 — author no longer uses ComfyUI as primary tool)

#### What It Does

IPAdapter transfers the **subject/style** from a reference image to new generations. Think of it as a "1-image LoRA". For comics, this means maintaining character appearance across panels.

#### FaceID Models (for character face consistency)

FaceID models require **insightface** installed in your ComfyUI environment.

**SD1.5 FaceID Models** → `/ComfyUI/models/ipadapter/`:

| Model | File | Use Case |
|-------|------|----------|
| Base FaceID | [ip-adapter-faceid_sd15.bin](https://huggingface.co/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid_sd15.bin) | Basic face transfer |
| FaceID Plus v2 | [ip-adapter-faceid-plusv2_sd15.bin](https://huggingface.co/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid-plusv2_sd15.bin) | **Recommended** — better quality |
| FaceID Portrait v11 | [ip-adapter-faceid-portrait-v11_sd15.bin](https://huggingface.co/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid-portrait-v11_sd15.bin) | Style transfer for portraits |

**SDXL FaceID Models** → `/ComfyUI/models/ipadapter/`:

| Model | File | Use Case |
|-------|------|----------|
| Base FaceID | [ip-adapter-faceid_sdxl.bin](https://huggingface.co/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid_sdxl.bin) | Basic SDXL face transfer |
| FaceID Plus v2 | [ip-adapter-faceid-plusv2_sdxl.bin](https://huggingface.co/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid-plusv2_sdxl.bin) | **Recommended for SDXL** |
| Portrait | [ip-adapter-faceid-portrait_sdxl.bin](https://huggingface.co/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid-portrait_sdxl.bin) | Style transfer |
| Portrait Unnorm | [ip-adapter-faceid-portrait_sdxl_unnorm.bin](https://huggingface.co/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid-portrait_sdxl_unnorm.bin) | Very strong style transfer |

**Required LoRAs** (auto-loaded by Unified Loader if named correctly) → `/ComfyUI/models/loras/`:

| LoRA | File | Pairs With |
|------|------|------------|
| SD1.5 FaceID | [ip-adapter-faceid_sd15_lora.safetensors](https://huggingface.co/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid_sd15_lora.safetensors) | Base FaceID SD1.5 |
| SD1.5 Plus v2 | [ip-adapter-faceid-plusv2_sd15_lora.safetensors](https://huggingface.co/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid-plusv2_sd15_lora.safetensors) | FaceID Plus v2 SD1.5 |
| SDXL FaceID | [ip-adapter-faceid_sdxl_lora.safetensors](https://huggingface.co/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid_sdxl_lora.safetensors) | Base FaceID SDXL |
| SDXL Plus v2 | [ip-adapter-faceid-plusv2_sdxl_lora.safetensors](https://huggingface.co/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid-plusv2_sdxl_lora.safetensors) | FaceID Plus v2 SDXL |

**Required CLIP Vision** → `/ComfyUI/models/clip_vision/`:

| Model | File | For |
|-------|------|-----|
| CLIP-ViT-H | [model.safetensors](https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors) → rename to `CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors` | SD1.5 models |
| CLIP-ViT-bigG | [model.safetensors](https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/image_encoder/model.safetensors) → rename to `CLIP-ViT-bigG-14-laion2B-39B-b160k.safetensors` | SDXL models |

#### Best Settings for Character Consistency Across Panels

```
Weight: 0.7-0.85 (lower = more prompt adherence, higher = more face similarity)
Weight Type: "linear" for general use, try "style transfer" for stylized comics
Steps: Higher step count (30-50) for better consistency
FaceID Model: faceid-plusv2 (best balance of similarity and flexibility)
```

**Tips:**
- Use `IPAdapter Unified Loader FaceID` for auto-loading model+LoRA pairs
- Lower weight to ~0.8 and increase steps for best results
- Combine with a strong character prompt for style consistency
- For composition control, add the `ip_plus_composition` model

#### Installation

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git
# Install insightface:
pip install insightface onnxruntime-gpu
# Restart ComfyUI
```

#### Assessment
- ✅ Best overall character consistency solution
- ✅ Excellent FaceID models for face preservation
- ✅ Unified loader makes setup easy
- ✅ Works with SD1.5 and SDXL
- ⚠️ Maintenance-only mode (no new features expected)
- ⚠️ FaceID requires insightface (can be tricky to install)

---

### 2.2 ComfyUI-ReActor

**Repository:** https://github.com/Gourieff/ComfyUI-ReActor  
**Version:** 0.6.2 (latest)  
**Status:** Active development

#### How It Works for Character Consistency

ReActor performs **face swapping** — it takes a source face and replaces the face in a target image. For comics:

1. Generate a "reference face" image of your character
2. Generate each comic panel with similar prompts
3. Use ReActor to swap the generated faces with the reference face
4. Result: consistent character face across all panels

**Key advantage over IPAdapter**: Works as a **post-processing** step, so it doesn't affect the generation itself. Great as a fallback/refinement.

#### Swap Models

Multiple swap model options → `/ComfyUI/models/insightface/`:

| Model | Location | Quality |
|-------|----------|---------|
| inswapper_128.onnx | [Download](https://huggingface.co/datasets/Gourieff/ReActor/tree/main/models) → `models/insightface/` | Best similarity (default) |
| reswapper_128/256 | [Download](https://huggingface.co/datasets/Gourieff/ReActor/tree/main/models) → `models/reswapper/` | Open-source alternative |
| hyperswap_1a/1b/1c_256 | [Download](https://huggingface.co/facefusion/models-3.3.0/tree/main) → `models/hyperswap/` | Newest option (FaceFusion) |

#### Face Detection Model

- **buffalo_l**: Auto-downloaded on first launch → `models/insightface/models/buffalo_l/`
- Or manual: [Download](https://huggingface.co/datasets/Gourieff/ReActor/tree/main/models)

#### Face Restoration Models → `/ComfyUI/models/facerestore_models/`

| Model | Download |
|-------|----------|
| GFPGANv1.4 | Included via Spandrel |
| CodeFormer | Included via Spandrel |
| GPEN-BFR-512 | [Download](https://huggingface.co/datasets/Gourieff/ReActor/tree/main/models/facerestore_models) |
| GPEN-BFR-1024 | [Download](https://huggingface.co/datasets/Gourieff/ReActor/tree/main/models/facerestore_models) |
| GPEN-BFR-2048 | [Download](https://huggingface.co/datasets/Gourieff/ReActor/tree/main/models/facerestore_models) |
| RestoreFormer++ | [Download](https://huggingface.co/datasets/Gourieff/ReActor/tree/main/models/facerestore_models) |

#### Additional Models (optional)

| Model | Location | Purpose |
|-------|----------|---------|
| face_yolov8m.pt | [Download](https://huggingface.co/datasets/Gourieff/ReActor/blob/main/models/detection/bbox/face_yolov8m.pt) → `models/ultralytics/bbox/` | Face detection for masking |
| sam_vit_b_01ec64.pth | [Download](https://huggingface.co/datasets/Gourieff/ReActor/blob/main/models/sams/sam_vit_b_01ec64.pth) → `models/sams/` | Segmentation for masking |

#### Key Features for Comics

- **Face Models**: Save character faces as .safetensors files → reuse across sessions
- **Blended Face Models**: Combine multiple images of a character into one face model for better accuracy
- **FaceBoost Node**: Restores and upscales swapped face BEFORE pasting (better quality)
- **MaskHelper Node**: Precise face region masking for natural blending
- **SetWeight Node**: Control swap strength (0-100% in 12.5% steps)
- **Face restoration only affects swapped faces** (v0.6.2+)

#### Installation

```bash
# Option 1: ComfyUI Manager
# Search "ReActor" → Install

# Option 2: Manual
cd ComfyUI/custom_nodes
git clone https://github.com/Gourieff/ComfyUI-ReActor.git
cd ComfyUI-ReActor
# Windows:
install.bat
# Linux/macOS:
python install.py

# Requires Visual Studio 2022 or VS C++ Build Tools on Windows (for insightface)
```

#### Assessment
- ✅ Excellent post-process face consistency
- ✅ Face model system — save/load character faces
- ✅ Blended face models from multiple references
- ✅ Multiple swap models (inswapper, reswapper, hyperswap)
- ✅ Face restoration built-in
- ✅ Active development
- ⚠️ NSFW detector included (SFW-only enforcement)
- ⚠️ Insightface build can be painful on Windows

---

### 2.3 ComfyUI_InstantID

**Repository:** https://github.com/cubiq/ComfyUI_InstantID  
**Author:** cubiq  
**Status:** ⚠️ Maintenance-only mode (same as IPAdapter)

#### What It Does

Native ComfyUI implementation of InstantID. Unlike diffusers-based implementations, this integrates fully with ComfyUI's node system. Uses a face reference image + ControlNet to generate images that preserve the identity.

**⚠️ SDXL ONLY** — does not work with SD1.5.

#### Required Models

**1. InsightFace — antelopev2** (NOT buffalo_l!)

→ `/ComfyUI/models/insightface/models/antelopev2/`

Download from:
- [Google Drive](https://drive.google.com/file/d/18wEUfMNohBJ4K3Ly5wpTejPfDzp-8fI8/view?usp=sharing)
- [HuggingFace (MonsterMMORPG)](https://huggingface.co/MonsterMMORPG/tools/tree/main)

Unzip and place all files in the antelopev2 directory.

**2. InstantID Model**

→ `/ComfyUI/models/instantid/`

- [ip-adapter.bin](https://huggingface.co/InstantX/InstantID/resolve/main/ip-adapter.bin?download=true)

**3. ControlNet for InstantID**

→ `/ComfyUI/models/controlnet/`

- [diffusion_pytorch_model.safetensors](https://huggingface.co/InstantX/InstantID/resolve/main/ControlNetModel/diffusion_pytorch_model.safetensors?download=true)

#### Best Practices

```
CFG: 4-5 (IMPORTANT: lower than normal! Or use RescaleCFG node)
Resolution: 1016×1016 (NOT 1024×1024 — avoids training watermarks)
Noise Injection: ~35% on negative embeds (default in standard node)
Weight Type: Use Advanced node for fine control
  - InstantID model: ~25% of composition influence
  - ControlNet: ~75% of composition influence
```

**Tips:**
- Works very well with **SDXL Turbo/Lightning** for fast generation
- Community checkpoints give best results
- Use slightly non-standard resolutions to avoid watermarks
- Can be combined with IPAdapter for style transfer on top of identity
- Multi-ID is supported but complex and slower
- Face keypoints from reference image control pose; send different image to `image_kps` for different pose

#### Installation

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/cubiq/ComfyUI_InstantID.git

# Install dependencies
pip install insightface onnxruntime onnxruntime-gpu

# Restart ComfyUI
```

#### Assessment
- ✅ Strongest identity preservation
- ✅ Native ComfyUI integration (not diffusers-based)
- ✅ Pose control via keypoints
- ✅ Can combine with IPAdapter for styling
- ⚠️ SDXL only
- ⚠️ Maintenance-only mode
- ⚠️ Training watermark issue (mitigated by non-standard resolutions)
- ⚠️ Can "burn" image without noise injection

---

## 3. Speech Bubble & Text Overlay Solutions

### Current State (2026)

⚠️ **There is NO comprehensive, dedicated speech bubble node for ComfyUI.** This was confirmed by community discussions (Reddit r/comfyui, May 2025). Existing solutions are partial:

### 3.1 Comfyroll Text Nodes (Best Built-in Option)

**Nodes:** CR Overlay Text, CR Draw Text, CR Mask Text, CR Composite Text, CR Select Font

- Text overlay on images with position control
- Font selection from system/custom fonts
- Custom font folder: `ComfyUI_Comfyroll_CustomNodes/fonts/`
- Text autosizing, outline, custom colors
- ❌ No speech bubble shapes (just text placement)

### 3.2 GR Onomatopoeia (ComfyUI_GraftingRayman)

**Repository:** Part of https://github.com/GraftingRayman/ComfyUI_GraftingRayman

**Features:**
- Onomatopoeic text overlays (BANG, BOOM, CRASH, etc.)
- **Has basic speech bubble support** via `bubble` parameter
- `bubble` — size of speech bubble around text (0-50)
- `bubble_distance` — distance from text (0-500px)
- `bubble_colour` — bubble color
- `bubble_stroke_thickness` — outline thickness (0-20)
- `bubble_fill` — filled or outline only
- Font selection from system fonts
- Text randomization, alignment, stroke/fill colors

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/GraftingRayman/ComfyUI_GraftingRayman.git
```

### 3.3 comfyui_chatbox_overlay (Smuzzies)

**Repository:** https://github.com/Smuzzies/comfyui_chatbox_overlay

- Adds a text box overlay on images (chat/dialog style)
- X/Y coordinate positioning
- Custom font path (e.g., `c:/windows/fonts/font.ttf`)
- Line spacing control
- Can stack multiple chatboxes via coordinate calculations
- Simple but functional for dialog boxes

```bash
# Just download the .py file and place in custom_nodes directory
cd ComfyUI/custom_nodes
git clone https://github.com/Smuzzies/comfyui_chatbox_overlay.git
```

### 3.4 ComfyUI-text-overlay (mikkel)

**Repository:** https://github.com/mikkel/ComfyUI-text-overlay

- Text placement via X/Y coordinates
- Font selection (any system font via path)
- Font size control
- Text alignment (left, center, right)
- Color via RGB or hex (0xFFFFFF format)
- Clean, simple overlay
- ❌ No bubble shapes

```bash
# Via ComfyUI Manager: search "Text Overlay Plugin"
# Or manual:
cd ComfyUI/custom_nodes
git clone https://github.com/mikkel/ComfyUI-text-overlay.git
```

### 3.5 Recommended: PIL/Pillow Post-Processing Script

Since no ComfyUI node provides proper manga-style speech bubbles, a **post-processing Python script** using PIL/Pillow is the most reliable approach:

```python
"""
Speech Bubble Post-Processor for Comic Pages
Uses PIL/Pillow to add professional speech bubbles to generated panels.
"""
from PIL import Image, ImageDraw, ImageFont
import math

def add_speech_bubble(
    image: Image.Image,
    text: str,
    position: tuple,      # (x, y) center of bubble
    tail_target: tuple,   # (x, y) where tail points (character mouth)
    max_width: int = 200,
    font_path: str = "fonts/comic-sans.ttf",  # or any comic font
    font_size: int = 16,
    padding: int = 15,
    bubble_color: str = "white",
    outline_color: str = "black",
    outline_width: int = 2,
) -> Image.Image:
    """Add an elliptical speech bubble with tail to an image."""
    img = image.copy()
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, font_size)
    
    # Word wrap text
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test = f"{current_line} {word}".strip()
        bbox = font.getbbox(test)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    
    # Calculate bubble size
    text_height = sum(font.getbbox(line)[3] - font.getbbox(line)[1] for line in lines)
    text_width = max(font.getbbox(line)[2] - font.getbbox(line)[0] for line in lines)
    
    bw = text_width + padding * 2
    bh = text_height + padding * 2 + (len(lines) - 1) * 4
    
    # Draw elliptical bubble
    x, y = position
    bbox = [x - bw//2, y - bh//2, x + bw//2, y + bh//2]
    draw.ellipse(bbox, fill=bubble_color, outline=outline_color, width=outline_width)
    
    # Draw tail (triangle pointing to character)
    tx, ty = tail_target
    # Calculate tail base points on bubble edge
    angle = math.atan2(ty - y, tx - x)
    base_offset = 15
    base1 = (x + base_offset * math.cos(angle + 0.3), 
             y + base_offset * math.sin(angle + 0.3))
    base2 = (x + base_offset * math.cos(angle - 0.3), 
             y + base_offset * math.sin(angle - 0.3))
    draw.polygon([base1, (tx, ty), base2], fill=bubble_color, outline=outline_color)
    
    # Draw text
    ty_offset = y - bh//2 + padding
    for line in lines:
        lbbox = font.getbbox(line)
        lw = lbbox[2] - lbbox[0]
        draw.text((x - lw//2, ty_offset), line, fill="black", font=font)
        ty_offset += lbbox[3] - lbbox[1] + 4
    
    return img
```

**Recommended comic fonts (free):**
- [Komika](https://www.dafont.com/komika-text.font) — classic comic font
- [Bangers](https://fonts.google.com/specimen/Bangers) — bold comic style
- [Comic Neue](https://fonts.google.com/specimen/Comic+Neue) — clean comic font
- [Anime Ace](https://www.blambot.com/font_animeace.shtml) — manga dialog font
- [CC Wild Words](https://www.blambot.com/) — professional comic lettering

### Font Handling in ComfyUI

Most text nodes look for fonts in:
1. System font directories (`/usr/share/fonts/`, `C:\Windows\Fonts\`)
2. Node-specific font folders (e.g., `ComfyUI_Comfyroll_CustomNodes/fonts/`)
3. Custom path specified in node parameters

**For the Comfyroll nodes:** Place `.ttf`/`.otf` files in `ComfyUI_Comfyroll_CustomNodes/fonts/` and they'll appear in the font selector.

---

## 4. Recommended Pipeline

### For Our Comic Generation Workflow

```
Phase 1: Panel Generation
├── Generate individual panels with SDXL + character LoRA
├── Use IPAdapter FaceID Plus v2 for character consistency
└── Optional: ReActor face swap as post-process refinement

Phase 2: Page Assembly
├── Option A: comfyui_panels (bmad4ever) — for dynamic manga layouts
├── Option B: CR Comic Panel Templates — for standard grid layouts
└── Option C: Pixstri Page→Row→Frame — for simple layouts

Phase 3: Text & Speech Bubbles
├── CR Overlay Text — for narration boxes / captions
├── GR Onomatopoeia — for sound effects with basic bubbles
└── PIL/Pillow post-processing — for proper speech bubbles (RECOMMENDED)
```

### Model Download Checklist

```
Character Consistency:
□ insightface (pip install)
□ CLIP-ViT-H or CLIP-ViT-bigG (for IPAdapter)
□ ip-adapter-faceid-plusv2 + matching LoRA
□ inswapper_128.onnx (for ReActor)
□ face restoration model (GPEN-BFR-512 recommended)

If using InstantID (SDXL only):
□ antelopev2 face analysis models
□ instantid ip-adapter.bin
□ instantid controlnet

Layout:
□ No models needed — pure code nodes
```

### Priority Ranking for Installation

1. **ComfyUI_Comfyroll_CustomNodes** — Install first, covers layout + text + many utilities
2. **ComfyUI_IPAdapter_plus** — Primary character consistency
3. **ComfyUI-ReActor** — Face swap fallback/refinement
4. **comfyui_panels** — Advanced manga layouts (if needed)
5. **comfyui-panelforge** — Simple alternative layouts
6. **ComfyUI_InstantID** — If using SDXL and need strongest identity lock
7. **ComfyUI_GraftingRayman** — For onomatopoeia/sound effects
8. **PIL post-processing script** — For proper speech bubbles

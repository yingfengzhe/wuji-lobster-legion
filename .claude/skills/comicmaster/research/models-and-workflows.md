# ComfyUI Comic/Manga Generation — Models & Workflows Research

> **Date:** 2026-02-08  
> **Focus:** Best models, LoRAs, workflows, and character consistency techniques for comic/manga generation in ComfyUI (SDXL & Flux)

---

## Table of Contents

1. [Base Model Recommendations](#1-base-model-recommendations)
2. [LoRA Recommendations](#2-lora-recommendations)
3. [Character Consistency Techniques](#3-character-consistency-techniques)
4. [ControlNet Models](#4-controlnet-models)
5. [Comic Layout & Panel Nodes](#5-comic-layout--panel-nodes)
6. [Workflow Architecture Recommendations](#6-workflow-architecture-recommendations)
7. [Recommended Character Consistency Strategy](#7-recommended-character-consistency-strategy)
8. [Model Download URLs](#8-model-download-urls)

---

## 1. Base Model Recommendations

### SDXL Checkpoints

| Model | Purpose | URL |
|-------|---------|-----|
| **Pony Diffusion V6 XL** | Top-tier for anime/illustration. Huge LoRA ecosystem, excellent prompt adherence for stylized content. One of the most popular base models on CivitAI for anime/comic work. | [CivitAI](https://civitai.com/models/257749/pony-diffusion-v6-xl) |
| **Illustrious XL** / **NoobAI XL** | Best anime-focused SDXL finetunes. Illustrious is known for sharp anime style; NoobAI merges are recommended for quality. Both have dedicated ControlNet models. | [CivitAI - Illustrious](https://civitai.com/models/795765/illustrious-xl) |
| **DreamShaper XL** | Excellent for artistic/illustration styles. Good balance between realism and stylization. Works well for western comic styles. | [CivitAI](https://civitai.com/models/112902/dreamshaper-xl) |
| **Juggernaut XL** | Best all-around SDXL model. Great prompt adherence. While more photorealistic by default, works excellently with comic LoRAs. | [CivitAI](https://civitai.com/models/133005/juggernaut-xl) |
| **Animagine XL V3.1** | Dedicated anime model by CagliostroLab. Good for manga-style output. 140K+ downloads. | [CivitAI](https://civitai.com/models/260267/animagine-xl-v31) |
| **Cartoon Arcadia** | Specifically designed for cartoon/comic output. SDXL & SD1.5 versions available. | [CivitAI](https://civitai.com/models/136113/cartoon-arcadia-sdxl-and-sd-15) |

### Flux Checkpoints

| Model | Purpose | URL |
|-------|---------|-----|
| **FLUX.1-dev** (base) | Best prompt adherence of any open model. Excellent text rendering in comics. Recommended as primary base for Flux workflows. | [HuggingFace](https://huggingface.co/black-forest-labs/FLUX.1-dev) |
| **FLUX-MonochromeManga** | Full Flux checkpoint trained specifically for monochrome manga panels. Superior to LoRAs for manga output. | [CivitAI](https://civitai.com/models/655408/flux-monochromemanga) |
| **AnimePro FLUX** | Fine-tune of Flux.1-Schnell that produces DEV/PRO quality anime. Fast generation. | [CivitAI](https://civitai.com/models/934628/animepro-flux) |
| **AnimEasy Flux v1.1** | Anime-focused Flux checkpoint, beginner-friendly (minimal prompting needed). Available in 4-bit and 2-bit quantization for low VRAM. | [CivitAI](https://civitai.com/models/853344/animeasy-flux) |
| **Origin Flux Anime V1** | High-quality anime Flux checkpoint by n0utis. | [CivitAI](https://civitai.com/models/408059/origin-by-n0utis) |

**Recommendation:** For comic generation, use **Pony Diffusion V6 XL** or **Illustrious XL** for SDXL workflows (best LoRA ecosystem + ControlNet support), and **FLUX.1-dev + comic LoRAs** for Flux workflows (best prompt adherence + text rendering).

---

## 2. LoRA Recommendations

### Flux Comic/Manga LoRAs

| LoRA | Style | Trigger Words | URL |
|------|-------|---------------|-----|
| **Retro Comic Flux v2.0** | Classic retro comic book style. Trained on public domain comics. | (style-based, check model page) | [CivitAI](https://civitai.com/models/806568/retro-comic-flux) |
| **Eldritch Comics (Flux) v1.1** | Detailed comic book illustration style. Best version across SDXL and Flux. | (check model page) | [CivitAI](https://civitai.com/models/671064/eldritch-comics-or-for-flux1-dev) |
| **AKIRA Manga FLUX** | Katsuhiro Otomo / AKIRA manga aesthetic. Use at 0.3-0.7 strength (sweet spot ~0.65). | (no specific trigger) | [CivitAI](https://civitai.com/models/725574/akira-manga-flux) |
| **Naoki Urasawa Manga Style (Flux)** | Monster/20th Century Boys manga style. B&W manga. | "black and white manga style image of" | [CivitAI](https://civitai.com/models/690155/naoki-urasawa-manga-style-flux-lora) |
| **Tsutomu Nihei Manga Style** | BLAME!/dystopian architectural manga style. | (check model page) | [CivitAI](https://civitai.com/models/2043162/tsutomu-niheis-manga-style-lora) |
| **DreamART Style (Flux)** | Artistic anime/illustration style. Multiple base model versions available. | (check model page) | [CivitAI](https://civitai.com/models/105491/dreamart-style-lora) |

### SDXL Comic/Manga LoRAs

| LoRA | Style | Trigger Words | URL |
|------|-------|---------------|-----|
| **Comic Book Page Style (ZImageTurbo)** | Multi-format: anime, manga, western comics. Works on XL, F1D, Pony, Illustrious, SD1.5. | (check model page) | [CivitAI](https://civitai.com/models/462611/comic-book-page-style-anime-manga-western-comics-xl-f1d-pony-illustrious-sd15-zit) |
| **Eldritch Comics (SDXL) v1.2** | Western comic book illustration style for SDXL. | (check model page) | [CivitAI](https://civitai.com/models/262880/eldritch-comics-comic-book-style-illustration) |
| **Comic Book Style SDXL** | Comic illustration style. Best on realistic SDXL models (Osea, Duskmix). | (check model page) | [CivitAI](https://civitai.com/models/142989/comic-book-style-sdxl-lora) |
| **Comic style SDXL – Jhyd** | Comic style with trigger "jhyd style". Add "high saturation" for vibrant results. | "jhyd style" | [CivitAI](https://civitai.com/models/134144) |
| **Manga Shade** | Manga-style with panel layouts. Monochrome. | (check model page) | [CivitAI](https://civitai.com/models/671821/manga-shade) |
| **Manga Master v2.0** | General manga art styles. Use at strength 1.0. | "manga, monochrome, grayscale" | [CivitAI](https://civitai.com/models/158217/manga-master-general-manga-art-styles-and-details) |
| **Anime Lineart / Manga-like v3.0** | Manga lineart with complex body/background support. | (check model page) | [CivitAI](https://civitai.com/models/16014/anime-lineart-manga-like-style) |
| **Velvet's Blood Moon (Pony)** | Monochrome manga feel. Made for Pony Diffusion XL. | "monochrome" | [CivitAI](https://civitai.com/models/599757/velvets-mythic-fantasy-styles-or-flux-pony-illustrious) |
| **Comics v4.0** | General comic style LoRA. SD1.5 and SDXL. | (check model page) | [CivitAI](https://civitai.com/models/62100/comics-v40) |

---

## 3. Character Consistency Techniques

### Comparison Matrix

| Technology | Base Model Support | Face Similarity | Style Flexibility | Resource Usage | Comic Suitability | Maturity |
|-----------|-------------------|----------------|-------------------|---------------|-------------------|----------|
| **InstantID** | SDXL only | ⭐⭐⭐⭐⭐ (Best) | ⭐⭐⭐ | High (most resource-intensive) | ⭐⭐⭐⭐ | Mature |
| **IP-Adapter FaceID v2** | SD1.5 + SDXL | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Medium | ⭐⭐⭐⭐ | Mature |
| **IP-Adapter Plus Face** | SD1.5 + SDXL | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Medium | ⭐⭐⭐⭐⭐ | Mature |
| **PuLID** | SDXL + Flux | ⭐⭐⭐ | ⭐⭐⭐⭐ | Low-Medium | ⭐⭐⭐ | Active development |
| **PuLID Flux II** | Flux only | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Medium | ⭐⭐⭐⭐ | New (solves model pollution) |
| **ReActor** | Any (post-processing) | ⭐⭐⭐ | ⭐⭐ | Low | ⭐⭐ | Maintenance-only / deprecated |
| **ACE++** | Flux (via Fill) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Medium | ⭐⭐⭐⭐⭐ | **State of the art (2025)** |
| **StoryDiffusion** | SDXL + Flux | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | High | ⭐⭐⭐⭐⭐ | Purpose-built for comics |

### Detailed Analysis

#### InstantID (SDXL Only)
- **Pros:** Highest face similarity scores in benchmarks. Single reference image needed. Best for SDXL workflows.
- **Cons:** SDXL only (no Flux support). Most resource-intensive. Can maintain source composition too strongly. Requires InsightFace (commercial license).
- **Best for:** SDXL-based comic workflows where exact face matching is critical.
- **GitHub:** https://github.com/cubiq/ComfyUI_InstantID
- **Tip:** Use as face inpaint/replace rather than full image generation for best stylistic control.

#### IP-Adapter Plus / FaceID v2
- **Pros:** Most versatile — multiple adapters can be stacked (face + body + style). Works on SD1.5 and SDXL. Can separate face consistency from body/style consistency. Multiple reference images supported.
- **Cons:** Requires careful weight tuning between adapters. Not available for Flux natively. More complex setup.
- **Best for:** Complex multi-character comic scenes where you need face + body + style control independently.
- **GitHub:** https://github.com/cubiq/ComfyUI_IPAdapter_plus
- **Strategy:** Use FaceID for face shape → IP-Adapter Plus for body/style → layer with different weights.
- **Note:** Repository is in "maintenance only" mode as of April 2025.

#### PuLID / PuLID Flux II
- **Pros:** Easiest option for Flux character consistency. Lower resource usage. PuLID Flux II solves the "model pollution" problem of v1.
- **Cons:** Doesn't work well for anime/furry/animal faces (confirmed by community). Lower face similarity than InstantID. Requires InsightFace.
- **Best for:** Flux-based realistic or semi-realistic comic character consistency.
- **GitHub (PuLID):** https://github.com/cubiq/PuLID_ComfyUI
- **Model:** PuLID-FLUX-v0.9.0 from HuggingFace

#### ReActor
- **Pros:** Simple post-processing face swap. Works with any model (sits between output and save node). Can save face models as safetensors for reuse.
- **Cons:** Only generates 128x128 face replacements (low resolution). Makes skin look flat. Dependency conflicts with other ComfyUI nodes. **Effectively deprecated.** Breaks installs frequently.
- **Best for:** Quick-and-dirty face swaps as a final post-processing step only. NOT recommended as primary consistency tool.
- **GitHub:** https://github.com/Gourieff/ComfyUI-ReActor

#### ACE++ (Alibaba, January 2025) — **STATE OF THE ART**
- **Pros:** Zero-training character consistency from single image. Open-sourced by Alibaba. Works with Flux Fill pipeline. Supports portrait + subject modes. LoRA-based (easy integration). Highly consistent results.
- **Cons:** Requires Flux Fill model. Relatively new. High guidance values needed (default 50).
- **Best for:** Modern Flux-based comic workflows. Best balance of quality/ease-of-use for character consistency.
- **GitHub:** https://github.com/ali-vilab/ACE_plus
- **Models needed:**
  - `comfyui_portrait_lora64.safetensors` → `/models/loras/`
  - Flux Fill fp8 → `/models/diffusion_models/`
- **Download:** https://huggingface.co/ali-vilab/ACE_Plus/tree/main/portrait

#### StoryDiffusion (ComfyUI_StoryDiffusion)
- **Pros:** Purpose-built for comic/story generation. Consistent self-attention mechanism. Supports multiple technologies (PuLID, InstantID, IP-Adapter, PhotoMaker). Comic_Type node for comic panel overlays. Built-in character prompt system.
- **Cons:** Can be complex to set up. Combines many technologies.
- **Best for:** End-to-end comic story generation with character consistency across panels.
- **GitHub:** https://github.com/smthemex/ComfyUI_StoryDiffusion

---

## 4. ControlNet Models

### For SDXL

| Model | Purpose | URL |
|-------|---------|-----|
| **xinsir/controlnet-openpose-sdxl-1.0** | Pose control. Best SDXL openpose model (Jun 2024 release, outstanding quality). | [HuggingFace](https://huggingface.co/xinsir/controlnet-openpose-sdxl-1.0) |
| **xinsir/controlnet-canny-sdxl-1.0** | Edge/line control. New exceptional model. | [HuggingFace](https://huggingface.co/xinsir/controlnet-canny-sdxl-1.0) |
| **diffusers/controlnet-depth-sdxl-1.0-small** | Depth map control. Small variant for efficiency. | [HuggingFace](https://huggingface.co/diffusers/controlnet-depth-sdxl-1.0-small) |
| **diffusers/controlnet-canny-sdxl-1.0** | Official canny ControlNet for SDXL. | [HuggingFace](https://huggingface.co/diffusers/controlnet-canny-sdxl-1.0) |
| **thibaud/controlnet-openpose-sdxl-1.0** | Alternative openpose for SDXL. | [HuggingFace](https://huggingface.co/thibaud/controlnet-openpose-sdxl-1.0) |
| **NoobAI XL ControlNet OpenPose** | Openpose specifically trained for NoobAI/Illustrious. | [CivitAI](https://civitai.com/models/962537/noobai-xl-controlnet-openpose) |
| **2vXpSwA7 anytest-v4** | Multi-purpose "anytest" ControlNet for SDXL. Very versatile. | [CivitAI](https://civitai.com/models/136070/controlnetxl-cnxl) |
| **kohya ControlNet-lllite (SDXL anime)** | Lightweight anime-specific: depth, canny, scribble, openpose variants. | [HuggingFace](https://huggingface.co/lllyasviel/sd_control_collection) |

### For Flux

| Model | Purpose | URL |
|-------|---------|-----|
| **Shakker-Labs/FLUX.1-dev-ControlNet-Union-Pro-2.0** | **Recommended.** Unified ControlNet: depth, pose, canny, blur, grayscale, soft edge. Single model, multiple modes. Smaller than v1. | [HuggingFace](https://huggingface.co/Shakker-Labs/FLUX.1-dev-ControlNet-Union-Pro-2.0) |
| **Shakker-Labs/FLUX.1-dev-ControlNet-Union-Pro** | Previous version of union model. Still solid. Depth/Pose/Canny/Tile/Blur/Grayscale. | [HuggingFace](https://huggingface.co/Shakker-Labs/FLUX.1-dev-ControlNet-Union-Pro) |
| **flux1-canny-dev-lora.safetensors** | Official BFL canny ControlNet as LoRA. Place in /models/loras/. | [HuggingFace (BFL)](https://huggingface.co/black-forest-labs/FLUX.1-Canny-dev-lora) |
| **flux1-depth-dev-lora.safetensors** | Official BFL depth ControlNet as LoRA. | [HuggingFace (BFL)](https://huggingface.co/black-forest-labs/FLUX.1-Depth-dev-lora) |
| **XLabs Flux ControlNet** | Community Flux ControlNet (canny, depth, pose). | [GitHub](https://github.com/XLabs-AI/x-flux-comfyui) |

**Recommendation for Comics:** Use **Shakker-Labs Union Pro 2.0** for Flux (one model handles everything) and the **xinsir** series for SDXL (best quality). Key control types for comics: **OpenPose** (character poses), **Depth** (scene composition), **Canny** (lineart preservation for style transfer).

---

## 5. Comic Layout & Panel Nodes

### ComfyUI Extensions for Comic Creation

| Extension | Purpose | URL |
|-----------|---------|-----|
| **comfyui-panelforge (Pixstri)** | Hierarchical comic layout: Page → Row → Frame nodes. Panel assembly. Speech bubbles. | [GitHub](https://github.com/lisaks/comfyui-panelforge) |
| **comfyui_panels** | Comics/Manga panel layouts. | [GitHub](https://github.com/bmad4ever/comfyui_panels) |
| **ComfyUI_Comfyroll_CustomNodes** | CR Comic Panel Templates node — configurable rows, columns, sizes. Multi-ControlNet, LoRA, Aspect Ratio nodes. | [GitHub](https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes) |
| **ComfyUI_StoryDiffusion** | Comic_Type node — transforms images into comic visuals with text overlays and comic styling. Character consistency built in. | [GitHub](https://github.com/smthemex/ComfyUI_StoryDiffusion) |
| **GR Onomatopoeia** | Speech bubbles and sound effects overlay. | [RunComfy](https://www.runcomfy.com/comfyui-nodes/ComfyUI_GraftingRayman/GR-Onomatopoeia) |

---

## 6. Workflow Architecture Recommendations

### Architecture A: SDXL Comic Pipeline (Maximum Control)

```
[Character Reference Images]
        ↓
[InstantID] + [IP-Adapter FaceID] + [IP-Adapter Plus (body/style)]
        ↓
[Pony Diffusion V6 XL / Illustrious XL] + [Comic LoRA]
        ↓
[ControlNet OpenPose (pose)] + [ControlNet Depth (composition)]
        ↓
[KSampler] → [Face Detailer (optional refinement)]
        ↓
[Comic Panel Templates] → [Final Assembly]
```

**Pros:** Maximum control over face + body + style separately. Mature ecosystem. Multiple ControlNets.  
**Cons:** Complex setup. More VRAM needed. More manual tuning.

### Architecture B: Flux Comic Pipeline (Modern, Simpler)

```
[Character Reference Image]
        ↓
[ACE++ Portrait LoRA] + [Flux Fill]  OR  [PuLID Flux II]
        ↓
[FLUX.1-dev] + [Comic Style LoRA]
        ↓
[Shakker-Labs Union ControlNet Pro 2.0] (pose/depth as needed)
        ↓
[KSampler] → [Upscale]
        ↓
[Comic Panel Assembly (panelforge/comfyroll)]
```

**Pros:** Simpler setup. Better prompt adherence. Built-in text rendering. ACE++ is SOTA for consistency.  
**Cons:** Flux ControlNet ecosystem less mature. Higher base VRAM requirements for Flux. PuLID doesn't work for anime faces.

### Architecture C: StoryDiffusion Pipeline (End-to-End)

```
[Story Script / Prompts per Panel]
        ↓
[ComfyUI_StoryDiffusion]
  ├── SeaArtCharacterPrompt (character definition)
  ├── Consistent Self-Attention (cross-panel consistency)
  └── Comic_Type (layout + text overlay)
        ↓
[Base Model (SDXL or Flux)] + [Style LoRA]
        ↓
[Comic Output with Panels + Text]
```

**Pros:** Purpose-built for comics. Handles multi-panel consistency automatically. Text overlay built in.  
**Cons:** Less granular control. Newer/less documented.

### Architecture D: Hybrid Pipeline (Community Best Practice)

Based on the most successful community workflows:

```
Step 1: Generate character reference sheet
  [FLUX/SDXL] → [Full body + face closeup, neutral expression, green background]

Step 2: Per-panel generation
  [Pose reference (3D mockup or OpenPose)] 
  + [Character face ref → InstantID/PuLID]
  + [Character body ref → IP-Adapter Plus]
  + [Style ref → IP-Adapter (style transfer)]
  + [Scene prompt]
        ↓
  [KSampler with ControlNet]
        ↓
  [Face Detailer for correction]

Step 3: Panel assembly
  [panelforge / comfyroll CR Comic Panel Templates]
  + [Speech bubbles in post-processing (Photoshop/ComicLife)]
```

**This is what most successful comic creators use.** Key insight: *create character reference sheets first*, then use those consistently across all panels.

---

## 7. Recommended Character Consistency Strategy

### Tier 1: Best Approach (if VRAM allows)

**For SDXL:** `InstantID (face) + IP-Adapter Plus (body/style) + ControlNet OpenPose (pose)`
- Stack multiple IP-Adapters: FaceID for face shape, Plus-Face for features, Plus for body/outfit
- Use InstantID as face inpaint/replace (not whole image generation)
- Finish with FaceDetailer for correction

**For Flux:** `ACE++ Portrait LoRA + PuLID Flux II + Shakker ControlNet Union Pro 2.0`
- ACE++ for best consistency from single reference image
- PuLID Flux II for additional face guidance (use at reduced weights alongside ACE++)
- Note: ACE++ doesn't work for anime faces → use custom character LoRA training instead

### Tier 2: Simpler Approach

**For SDXL:** `IP-Adapter FaceID Plus v2 alone`
- Single adapter, good face matching, less complexity

**For Flux:** `PuLID Flux II alone`
- Easiest single-tool option for Flux character consistency

### Tier 3: Maximum Quality (Investment Required)

**Train a character LoRA** per character (15-30 images, ~1 hour training)
- Best long-term results for recurring characters
- Works across any base model + any style LoRA
- Recommended for manga/anime where PuLID fails
- Use kohya_ss or CivitAI online training

### Anti-Pattern: What NOT to Do

- ❌ Don't use ReActor alone (128px, flat faces, dependency hell)
- ❌ Don't overload IP-Adapter weights (>0.8 leads to reference bleed)
- ❌ Don't skip the character reference sheet step
- ❌ Don't expect pure text prompting to maintain consistency across panels
- ❌ Don't use PuLID for anime/cartoon faces (confirmed by community to not work)

---

## 8. Model Download URLs

### Essential Models (Minimum Viable Setup)

#### For Flux Comic Workflow:
```
# Base model
FLUX.1-dev: https://huggingface.co/black-forest-labs/FLUX.1-dev

# Character consistency (ACE++)
ACE++ Portrait LoRA: https://huggingface.co/ali-vilab/ACE_Plus/tree/main/portrait
Flux Fill fp8: https://civitai.com/models/969431/flux-fill-fp8

# ControlNet
Shakker Union Pro 2.0: https://huggingface.co/Shakker-Labs/FLUX.1-dev-ControlNet-Union-Pro-2.0

# PuLID (optional, for face guidance)
PuLID Flux: https://huggingface.co/guozinan/PuLID (or via ComfyUI Manager)

# Style LoRAs (pick one)
Retro Comic Flux: https://civitai.com/models/806568/retro-comic-flux
Eldritch Comics Flux: https://civitai.com/models/671064/eldritch-comics-or-for-flux1-dev
AKIRA Manga Flux: https://civitai.com/models/725574/akira-manga-flux
```

#### For SDXL Comic Workflow:
```
# Base model (pick one)
Pony Diffusion V6 XL: https://civitai.com/models/257749/pony-diffusion-v6-xl
Illustrious XL: https://civitai.com/models/795765/illustrious-xl

# InstantID
Model: https://huggingface.co/InstantX/InstantID
Antelopev2: via insightface (required)

# IP-Adapter models
CLIP-ViT-H-14: https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors
CLIP-ViT-bigG-14: https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/image_encoder/model.safetensors
ip-adapter-plus-face_sdxl: https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus-face_sdxl_vit-h.safetensors
ip-adapter-plus_sdxl: https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors

# ControlNet SDXL
OpenPose (xinsir): https://huggingface.co/xinsir/controlnet-openpose-sdxl-1.0
Depth: https://huggingface.co/diffusers/controlnet-depth-sdxl-1.0-small
Canny: https://huggingface.co/diffusers/controlnet-canny-sdxl-1.0

# Style LoRAs (pick as needed)
Comic Book Page Style: https://civitai.com/models/462611
Eldritch Comics SDXL: https://civitai.com/models/262880
Manga Master: https://civitai.com/models/158217
```

### ComfyUI Custom Nodes to Install
```
# Essential
ComfyUI_IPAdapter_plus: https://github.com/cubiq/ComfyUI_IPAdapter_plus
ComfyUI_InstantID: https://github.com/cubiq/ComfyUI_InstantID
PuLID_ComfyUI: https://github.com/cubiq/PuLID_ComfyUI
ComfyUI-Advanced-ControlNet: https://github.com/Kosinkadink/ComfyUI-Advanced-ControlNet

# Comic-specific
comfyui-panelforge: https://github.com/lisaks/comfyui-panelforge
ComfyUI_Comfyroll_CustomNodes: https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes
comfyui_panels: https://github.com/bmad4ever/comfyui_panels
ComfyUI_StoryDiffusion: https://github.com/smthemex/ComfyUI_StoryDiffusion

# Face enhancement
ComfyUI-Impact-Pack: (FaceDetailer) https://github.com/ltdrdata/ComfyUI-Impact-Pack

# Optional
ComfyUI-ReActor: https://github.com/Gourieff/ComfyUI-ReActor (post-process face swap only)
ACE_plus: https://github.com/ali-vilab/ACE_plus
```

---

## Key Community Workflows (Ready to Download)

| Workflow | Platform | Description |
|----------|----------|-------------|
| Consistent Character Maker (Comics Strip) V3 | [OpenArt](https://openart.ai/workflows/tenforce/consistant-character-maker-comics-strip-v3/INP7HGXutczUutol9AYv) | IP-Adapter based, multi-pose, green background ref |
| Easy Consistent Characters for Comics | [OpenArt](https://openart.ai/workflows/monkey_perky_22/easy-consistent-characters-for-comics-no-lora-training/NCgZ46G3ZedZU3OwrviL) | No LoRA training needed. Simpler approach. |
| Comic Strip by Grockster | [ComfyWorkflows](https://comfyworkflows.com/workflows/a7837193-7858-4dce-a48c-92f75dd65aca) | Classic comic strip workflow |
| Consistent Character Maker (2 characters) | [ComfyWorkflows](https://comfyworkflows.com/workflows/b9725698-def7-4084-84b9-fe7b9add8337) | IP-Adapter, pose+face+body inputs |
| Generate Your Comic Story Book | [OpenArt](https://openart.ai/workflows/cgtips/comfyui---generate-your-comic-story-book/MTOBbZQ6F2Ag31uDJYWQ) | StoryDiffusion-based |
| Flux PuLID Consistent Characters | [OpenArt](https://openart.ai/workflows/thelocallab/flux-1-gguf-pulid-for-consistent-characters/6CMl5KcqHm1tFTcRLRI3) | Flux GGUF + PuLID |
| ACE++ Character Consistency | [OpenArt](https://openart.ai/workflows/whale_waterlogged_60/ace-more-convenient-replacement-of-everything/gjAsh5rGjfC6OEB2AUZv) | ACE++ Portrait + Subject modes |
| Flux Union ControlNet Pro | [CivitAI](https://civitai.com/models/709352/flux-union-controlnet-pro-workflow) | Multi-mode ControlNet workflow |

---

## Summary: Quick Decision Guide

| If you want... | Use this |
|----------------|----------|
| Best overall comic quality (western style) | SDXL + Pony/Illustrious + InstantID + IP-Adapter + Eldritch Comics LoRA |
| Best manga (monochrome) | FLUX-MonochromeManga checkpoint OR SDXL + Manga Master LoRA |
| Easiest character consistency (Flux) | ACE++ Portrait LoRA + Flux Fill |
| Easiest character consistency (SDXL) | InstantID alone |
| Best for anime characters | SDXL + Illustrious/Pony (PuLID doesn't work for anime) |
| Multi-panel story with auto-layout | StoryDiffusion pipeline |
| Quick prototype | Flux + PuLID + comic prompt engineering |
| Production pipeline (recurring characters) | Train character LoRAs (15-30 images each) |

---

*Research compiled from CivitAI, HuggingFace, GitHub, Reddit r/comfyui, Reddit r/StableDiffusion, OpenArt, ComfyWorkflows, RunComfy, and community benchmarks.*

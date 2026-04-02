# Illustrious XL & NoobAI-XL Guide

> **Last Updated:** February 2026  
> **Context:** ComicMaster integration, ComfyUI pipeline, RTX 3090

---

## Overview

**Illustrious XL** and **NoobAI-XL** are SDXL-based models fine-tuned on large illustration datasets (primarily Danbooru). They excel at anime, manga, and comic-style illustration and understand **Danbooru tag-based prompts** natively, unlike standard SDXL models that work best with natural language.

Both are fully compatible with the existing SDXL ComfyUI pipeline (CheckpointLoaderSimple, KSampler, etc.) — no special nodes required beyond v-prediction handling for NoobAI-XL vpred.

---

## Models

### Illustrious XL v0.1 (eps-prediction)

| Property | Value |
|----------|-------|
| **Developer** | OnomaAI Research |
| **Architecture** | SDXL (eps-prediction) |
| **Filename** | `Illustrious-XL-v0.1.safetensors` or `illustriousXL_v01.safetensors` |
| **Size** | ~6.5 GB |
| **VRAM** | 6-8 GB inference |
| **Native Resolution** | 1024×1024 (supports 768–1344 range) |
| **Prompt Style** | Danbooru tags (primary), limited NLP |
| **HuggingFace** | `OnomaAIResearch/Illustrious-xl-early-release-v0` |
| **CivitAI** | [civitai.com/models/795765](https://civitai.com/models/795765/illustrious-xl) |

**Notes:**
- Base eps-prediction model — works out-of-the-box with standard ComfyUI SDXL workflow
- Massive LoRA ecosystem on CivitAI (compatible with all Illustrious-based LoRAs)
- Newer v1.0 exists with 1536×1536 native resolution, but v0.1 has the most LoRA compatibility

### Illustrious XL v1.0 (eps-prediction)

| Property | Value |
|----------|-------|
| **Developer** | OnomaAI |
| **Filename** | `illustriousXL_v10.safetensors` |
| **Native Resolution** | Up to 1536×1536 |
| **CivitAI** | [civitai.com/models/1232765](https://civitai.com/models/1232765/illustrious-xl-10) |

**Notes:**
- Trained from v0.1, supports higher resolutions natively
- Supports both NLP and Danbooru tags (hybrid prompting)
- Compatible with v0.1 LoRAs
- Knowledge cutoff: July 2024

### NoobAI-XL V-Pred 1.0

| Property | Value |
|----------|-------|
| **Developer** | Laxhar Lab (community) |
| **Architecture** | SDXL (v-prediction) |
| **Filename** | `NoobAI-XL-Vpred-v1.0.safetensors` |
| **Size** | ~7.1 GB |
| **VRAM** | 6-8 GB inference |
| **Native Resolution** | 1024×1024 (supports 768–1536 range) |
| **Prompt Style** | Danbooru tags (primary) |
| **HuggingFace** | `Laxhar/noobai-XL-Vpred-1.0` |
| **CivitAI** | [civitai.com/models/833294](https://civitai.com/models/833294/noobai-xl-nai-xl) |

**Notes:**
- ⚠️ **V-prediction model** — requires `ModelSamplingDiscrete` node in ComfyUI set to `v_prediction` with `zsnr: true`
- Fine-tuned on full Danbooru + e621 datasets with native tags
- More stylized than base Illustrious, better for specific anime aesthetics
- Has a strong community with dedicated LoRA ecosystem
- Cyberfix variant available: `NoobAI-XL-Vpred-v1.0-cyberfix.safetensors`

---

## Recommended Settings

### Illustrious XL v0.1 / v1.0 (eps-prediction)

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Sampler** | `euler_ancestral` (euler a) | Best overall; `euler`, `dpmpp_2m` also work |
| **Scheduler** | `normal` | Standard; `karras` also acceptable |
| **Steps** | 25-30 | Sweet spot: 28 |
| **CFG** | 5.0-7.0 | Sweet spot: 5.5-6.0 |
| **Resolution** | 1024×1024 | Or aspect ratios: 832×1216, 896×1152, 1152×896, 1216×832 |
| **Clip Skip** | 2 | Important for Illustrious models |
| **Denoise** | 1.0 | Standard txt2img |

### NoobAI-XL V-Pred 1.0

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Sampler** | `euler` | ⚠️ Other samplers may not work properly with v-pred |
| **Scheduler** | `normal` | Required for v-pred |
| **Steps** | 28-35 | Sweet spot: 28 |
| **CFG** | 4.0-5.0 | Sweet spot: 5.0 |
| **Resolution** | 1024×1024 | Same SDXL bucket resolutions |
| **V-Prediction** | Required | Must set `prediction_type: v_prediction` and `rescale_betas_zero_snr: true` |
| **Denoise** | 1.0 | Standard txt2img |

---

## Prompting Guide (Danbooru Tags)

### Structure

```
<quality tags>, <count>, <character tags>, <artist tags>, <general tags>, <meta tags>
```

### Quality Tags (Prefix)

```
masterpiece, best quality, newest, absurdres, highres
```

For lower quality enforcement (rare):
```
worst quality, low quality, normal quality  (in negative)
```

### Character Description Tags

Instead of natural language like "a young man with short black hair and brown eyes":
```
1boy, short hair, black hair, brown eyes, hoodie, grey hoodie
```

### Shot Type Tags

| ComicMaster Shot | Danbooru Tag |
|-----------------|--------------|
| `extreme_wide` | `scenery, wide shot, landscape` |
| `wide` | `wide shot, full body` |
| `medium` | `cowboy shot` (waist-up) or `upper body` |
| `medium_close` | `upper body, from chest up` |
| `close_up` | `close-up, portrait, face focus` |
| `extreme_close` | `extreme close-up, eyes focus` |

### Camera Angle Tags

| ComicMaster Angle | Danbooru Tag |
|-------------------|--------------|
| `eye_level` | `straight-on` |
| `low_angle` | `from below` |
| `high_angle` | `from above` |
| `dutch_angle` | `dutch angle, tilted frame` |
| `birds_eye` | `overhead shot, bird's-eye view` |
| `worms_eye` | `from below, worm's-eye view` |

### Style Tags for Comics

```
# Western comic
comic, western comic, comic book style, bold outlines, cel shading

# Manga
manga, monochrome, greyscale, screentone, ink drawing

# General illustration
illustration, detailed, sharp focus
```

### Emotion Tags

| Emotion | Danbooru Tags |
|---------|--------------|
| happy | `smile, happy, :d` |
| sad | `sad, crying, tears` |
| angry | `angry, frown, clenched teeth` |
| surprised | `surprised, :o, open mouth, wide-eyed` |
| scared | `scared, trembling, frightened` |
| determined | `serious, determined, intense` |

### Lighting Tags

```
dramatic lighting → dramatic lighting, strong shadows
noir → film noir, high contrast, chiaroscuro
sunset → sunset, golden hour, warm lighting
moonlight → moonlight, night, blue tones
neon → neon lights, cyberpunk, colorful lighting
```

---

## Negative Prompt Templates

### Illustrious XL (eps)

```
worst quality, low quality, normal quality, lowres, bad anatomy, bad hands,
extra fingers, fewer fingers, missing fingers, extra digit, extra limbs,
malformed limbs, mutated hands, fused fingers, too many fingers,
text, watermark, signature, username, logo, blurry, jpeg artifacts,
cropped, out of frame, duplicate, error
```

### NoobAI-XL (v-pred)

```
nsfw, worst quality, old, early, low quality, lowres, signature, username,
logo, bad hands, mutated hands, mammal, anthro, furry, ambiguous form,
feral, semi-anthro
```

---

## ComfyUI Workflow Notes

### Illustrious XL (eps-prediction)
Standard SDXL workflow — no special nodes needed. Works with:
- `CheckpointLoaderSimple` → `KSampler` → `VAEDecode` → `SaveImage`
- LoRA stacking via `LoraLoader` nodes
- IPAdapter works normally

### NoobAI-XL (v-prediction)
Requires a `ModelSamplingDiscrete` node between checkpoint and KSampler:
```
[CheckpointLoaderSimple] → [ModelSamplingDiscrete (sampling: v_prediction, zsnr: true)] → [KSampler]
```
In ComfyUI, this is added as:
- Node: `ModelSamplingDiscrete`
- Input: `sampling` = `v_prediction`
- Input: `zsnr` = `true`

### Resolution Buckets (Recommended)

| Aspect Ratio | Resolution | Use |
|-------------|-----------|-----|
| 1:1 | 1024×1024 | Standard square |
| 3:4 | 896×1152 | Portrait panel |
| 2:3 | 832×1216 | Tall portrait |
| 4:3 | 1152×896 | Landscape panel |
| 3:2 | 1216×832 | Wide landscape |
| 9:16 | 768×1344 | Narrow tall |

---

## Download Commands

```bash
# Illustrious XL v0.1 (eps) — Official HuggingFace
wget -O ComfyUI/models/checkpoints/Illustrious-XL-v0.1.safetensors \
  "https://huggingface.co/OnomaAIResearch/Illustrious-xl-early-release-v0/resolve/main/Illustrious-XL-v0.1.safetensors"

# NoobAI-XL V-Pred 1.0 — HuggingFace
wget -O ComfyUI/models/checkpoints/NoobAI-XL-Vpred-v1.0.safetensors \
  "https://huggingface.co/Laxhar/noobai-XL-Vpred-1.0/resolve/main/NoobAI-XL-Vpred-v1.0.safetensors"

# Alternative: CivitAI (requires login)
# Illustrious XL: https://civitai.com/models/795765/illustrious-xl
# NoobAI-XL:      https://civitai.com/models/833294/noobai-xl-nai-xl
```

---

## When to Use Which Model

| Scenario | Recommended Model | Why |
|----------|------------------|-----|
| **Western comic panels** | Illustrious XL v0.1 | Good comic style, large LoRA library, simple setup |
| **Manga/anime panels** | NoobAI-XL or Illustrious XL | Both excel; NoobAI has more anime training |
| **Quick generation** | Illustrious XL v0.1 | eps-prediction is simpler, no v-pred nodes |
| **Maximum quality anime** | NoobAI-XL v-pred | Better trained on quality-sorted anime data |
| **LoRA compatibility** | Illustrious XL v0.1 | Largest LoRA ecosystem |
| **Photorealistic** | DreamShaperXL / JuggernautXL | Illustrious models are illustration-focused |
| **Speed priority** | DreamShaperXL (Turbo, 8 steps) | Illustrious needs 25-30 steps |

---

## Sources

- [Illustrious XL Paper (arXiv)](https://arxiv.org/abs/2409.19946)
- [Illustrious XL v0.1 — CivitAI](https://civitai.com/models/795765/illustrious-xl)
- [Illustrious XL v1.0 — CivitAI](https://civitai.com/models/1232765/illustrious-xl-10)
- [NoobAI-XL V-Pred — CivitAI](https://civitai.com/models/833294/noobai-xl-nai-xl)
- [NoobAI-XL Quick Guide — CivitAI](https://civitai.com/articles/8962)
- [Sampler Reference for Illustrious — CivitAI](https://civitai.com/articles/16231)
- [Illustrious XL User Guide — SeaArt](https://www.seaart.ai/articleDetail/cvceb6le878c73bckfig)

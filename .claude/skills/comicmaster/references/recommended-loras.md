# Recommended LoRAs for ComicMaster

## Currently Mapped (all confirmed available)

| Style | LoRA | Strength (model/clip) | Purpose |
|-------|------|-----------------------|---------|
| **western** | `xl_more_art-full_v1.safetensors` | 0.45 / 0.45 | Bold artistic enhancement for classic comic look |
| **cartoon** | `SDXLFaeTastic2400.safetensors` | 0.55 / 0.50 | Whimsical, fairy-tale cartoon style |
| **noir** | `sd_xl_offset_example-lora_1.0.safetensors` | 0.60 / 0.60 | Offset noise for deep shadows & high contrast |
| **realistic** | `clarity_3.safetensors` | 0.40 / 0.40 | Clarity and sharpness |
| **realistic** | `add_detail.safetensors` | 0.50 / 0.40 | Extra fine detail |
| **neon** | `glowneon_xl_v1.safetensors` | 0.60 / 0.50 | Neon glow effects, cyberpunk |
| **artistic** | `xl_more_art-full_v1.safetensors` | 0.60 / 0.55 | Stronger artistic push |
| **artistic** | `perfection style.safetensors` | 0.35 / 0.30 | Style refinement |
| **manga** | *(none — base model + prompt)* | — | See recommendations below |

## Recommended Downloads

These LoRAs would significantly improve specific styles but are **not currently installed**.

### Manga / Anime Style
- **[Anime Screencap XL](https://civitai.com/models/128677)** — Clean anime screencap aesthetic
  - Suggested: `strength_model=0.6, strength_clip=0.55`
- **[Anime Style SDXL](https://civitai.com/models/124534)** — General anime/manga enhancement
  - Suggested: `strength_model=0.5, strength_clip=0.5`

### Comic Book (Enhanced)
- **[Comic Book Style XL](https://civitai.com/models/149737)** — Halftone dots, bold outlines, classic comic look
  - Suggested: `strength_model=0.5, strength_clip=0.45`
- **[Graphic Novel Style](https://civitai.com/models/178468)** — Graphic novel / indie comic aesthetic
  - Suggested: `strength_model=0.55, strength_clip=0.5`

### Noir (Enhanced)
- **[Film Noir SDXL](https://civitai.com/models/154871)** — True film-noir grain, dramatic lighting
  - Suggested: `strength_model=0.5, strength_clip=0.5`
  - Use alongside the offset noise LoRA already mapped

### Watercolor / Painterly
- **[Watercolor Style SDXL](https://civitai.com/models/127862)** — Soft watercolor look
  - Suggested: `strength_model=0.6, strength_clip=0.5`

### Line Art / Ink
- **[Ink Drawing SDXL](https://civitai.com/models/169438)** — Clean ink line work
  - Suggested: `strength_model=0.55, strength_clip=0.5`
  - Great for black-and-white manga panels

## Also Available (not mapped but potentially useful)

These LoRAs are already installed but not mapped to any style:

| LoRA | Potential Use |
|------|---------------|
| `SDXLrender_v2.0.safetensors` | 3D render quality boost |
| `SDXL_Dices_Mega_Detail_v1.safetensors` | Extreme detail — good for close-ups |
| `Rendered Face Detailer SDXLv1.0.safetensors` | Face quality improvement |
| `dataviz_style_xl_v1.safetensors` | Stylized/infographic look |
| `sdxl_glass.safetensors` | Glass/transparent material effects |
| `ume_sky_v2.safetensors` | Sky/cloud enhancement |
| `difConsistency_photo.safetensors` | Photo consistency |

## How to Add a New Style LoRA

1. Download the `.safetensors` file to ComfyUI's `models/loras/` directory
2. Edit `STYLE_LORAS` in `panel_generator.py`:
   ```python
   STYLE_LORAS["new_style"] = [
       {"filename": "new_lora.safetensors", "strength_model": 0.5, "strength_clip": 0.5},
   ]
   ```
3. Optionally add a matching entry in `STYLE_TAGS` for prompt-side style reinforcement
4. Test with: `python panel_generator.py story_plan.json --panel panel_01`

## Strength Tuning Guidelines

- **0.3–0.4**: Subtle influence, blends with base model
- **0.5–0.6**: Moderate — visible style shift while keeping prompt adherence
- **0.7–0.8**: Strong — LoRA dominates the style (may fight prompt)
- **Multiple LoRAs**: Keep total combined strength < 1.0 to avoid artifacts
- **With IPAdapter**: Lower LoRA strength by ~0.1 to avoid competing conditioning

## Architecture Notes

- LoRA nodes are inserted between `CheckpointLoaderSimple` and all downstream consumers
- Node IDs start at `900` to avoid collision with existing workflow nodes (1–50 range)
- For IPAdapter workflows: LoRA → IPAdapterUnifiedLoader → IPAdapterAdvanced → KSampler
- `_insert_lora_nodes()` automatically rewires all model/clip references

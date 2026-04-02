# State of the Art: Models & LoRA Training for Comic Generation

> **Research Date:** February 2026  
> **Hardware Context:** RTX 3090 (24GB VRAM), WSL2, ComfyUI  
> **Focus:** Comic book art generation + custom style LoRA training

---

## Model Comparison (2024-2025)

### Overview Table

| Model | Quality (Comic) | Speed (4090) | VRAM (Inference) | LoRA Support | ComfyUI | Architecture | Status |
|-------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **FLUX.2 dev** | ★★★★★ | ~60s/img | 16-24GB (fp8: ~14GB) | ✅ Growing | ✅ Day-0 | DiT | ⭐ Released Nov 2025 |
| **FLUX.1 dev** | ★★★★☆ | ~57s/4img | 12-24GB (fp8/GGUF) | ✅ Massive | ✅ Full | DiT (12B) | Mature |
| **FLUX.1 schnell** | ★★★☆☆ | ~15s/4img | 12-24GB | ✅ | ✅ Full | DiT (12B) | Mature |
| **SDXL 1.0** | ★★★☆☆ | ~13s/4img | 6-8GB | ✅ Massive | ✅ Full | UNet | Mature |
| **Illustrious XL** | ★★★★☆ | ~15s/img | 6-8GB | ✅ Large | ✅ Full | SDXL-based | ⭐ Active |
| **NoobAI-XL** | ★★★★☆ | ~15s/img | 6-8GB | ✅ Large | ✅ Full | SDXL-based (Illustrious finetune) | Active |
| **Pony Diffusion V7** | ★★★★☆ | TBD | ~12GB+ | 🔄 New ecosystem | ✅ | AuraFlow (7B) | Released Nov 2025 |
| **Pony Diffusion V6 XL** | ★★★☆☆ | ~15s/img | 6-8GB | ✅ Massive | ✅ Full | SDXL-based | Legacy but usable |
| **SD 3.5 Large** | ★★★☆☆ | ~19s/img (3x faster than Flux) | 10-16GB | ⚠️ Limited | ✅ | MMDiT | Underwhelming adoption |
| **SD 3.5 Medium** | ★★☆☆☆ | Fast | 6-10GB | ⚠️ Limited | ✅ | MMDiT | Underwhelming |
| **Hunyuan Image 3.0** | ★★★★☆ | Slow | 16-32GB recommended | ⚠️ Limited | ✅ | DiT (Multimodal) | Oct 2025 |
| **Playground v2.5** | ★★★☆☆ | ~15s/img | 6-8GB | ✅ (SDXL compat) | ✅ | SDXL-based | Stale (no v3 open) |

### Detailed Model Analysis

#### 🥇 FLUX.2 dev (November 2025) — **TOP RECOMMENDATION for New Projects**
- **Architecture:** Next-gen DiT, successor to FLUX.1
- **Strengths:** Up to 4MP output, excellent lighting/skin/fabric/hands, multi-reference consistency (up to 10 images), professional text rendering, precise pose control, hex-code color accuracy
- **Comic Relevance:** Excellent prompt adherence for complex scenes, style consistency across panels, built-in text rendering for speech bubbles
- **VRAM:** Full BF16 needs ~24GB+; FP8 version (NVIDIA partnership) reduces VRAM by 40% → ~14GB; GGUF Q8 → 12-14GB; Q4 can run on 8GB (slow)
- **LoRA Training:** Early ecosystem; AI-Toolkit supports FLUX.2 LoRA training; likely needs 24GB for training
- **ComfyUI:** Day-0 support since v0.3.72
- **License:** Non-commercial (dev), Apache 2.0 (schnell variant if available)
- **Verdict:** Best overall image quality as of early 2026. RTX 3090 can run it with FP8/GGUF. LoRA ecosystem still growing.

#### 🥈 FLUX.1 dev/schnell (August 2024) — **Best Mature Ecosystem**
- **Architecture:** 12B parameter DiT (Diffusion Transformer)
- **Strengths:** Excellent prompt adherence, great text rendering, good hands/anatomy, massive LoRA ecosystem, quantized versions for consumer GPUs
- **Comic Relevance:** Many comic-specific LoRAs on CivitAI (e.g., "Comic Book Page style" LoRA works across Flux, SDXL, Pony, Illustrious). Natural language prompting works well for scene descriptions.
- **VRAM:** Full: 24GB; FP8: ~16GB; NF4: ~12GB; GGUF Q4: ~8GB
- **LoRA Training:** Well-supported via AI-Toolkit (Ostris), Kohya, SimpleTuner. 24GB VRAM ideal for training.
- **Speed:** ~57s for 4 images at 1024×1024 on 4090 (20 steps); ~4x slower than SDXL
- **ComfyUI:** Full native support
- **Verdict:** The workhorse of 2024-2025. Huge LoRA library. RTX 3090 handles it well with quantization. Best balance of quality + ecosystem maturity.

#### 🥉 Illustrious XL / NoobAI-XL — **Best for Anime/Manga/Comics on SDXL**
- **Architecture:** SDXL-based, fine-tuned on large illustration datasets (Danbooru 2023)
- **Illustrious XL:** Base model by Onoma AI Research. Excellent character/style recognition, great prompt adherence, works with Danbooru tags. V1.0 released with v-pred support.
- **NoobAI-XL:** Community finetune of Illustrious, more stylized, better for specific anime aesthetics. V-pred 1.0 variant available.
- **Comic Relevance:** ⭐ Excellent for anime/manga/western comic styles. Can directly prompt artist styles. Huge library of comic LoRAs on CivitAI. Better than Pony V6 for consistent character generation and style replication.
- **VRAM:** 6-8GB for inference — very lightweight!
- **LoRA Training:** Full SDXL ecosystem — Kohya, OneTrainer, SimpleTuner all work. Training on RTX 3090 is easy.
- **Community Consensus:** "Illustrious/NoobAI has far bigger, updated, and uncensored knowledge than Pony" — "prompt adherence and style flexibility is just too good"
- **Verdict:** Best choice for comic-style generation on affordable hardware. Recommended base model for LoRA training (comic styles).

#### Pony Diffusion V7 "PonyFlow" (November 2025)
- **Architecture:** Complete rebuild on AuraFlow (7B parameters), NOT SDXL anymore
- **Training Data:** 10 million images (25% anime, 25% realism, 20% western cartoons, 10% pony, 10% furry, 10% misc)
- **New Feature:** Style grouping — clusters similar styles during training for better aesthetic coherence
- **Breaking Changes:** Incompatible with V6 LoRAs and workflows. Score tags (score_9 etc.) are weaker. Natural language prompting preferred.
- **Known Issues:** Small face detail problems at lower resolutions (V7.1 in development)
- **License:** Commercial use limited to <$1M revenue, no inference services
- **Verdict:** Interesting but ecosystem is immature. V6 LoRAs don't work. Wait for community to mature V7 before investing heavily.

#### Pony Diffusion V6 XL (Legacy)
- Score-based quality system (score_9, score_8_up...)
- Huge LoRA ecosystem, but "can't look without tears at anime without bunch of LoRAs"
- Being superseded by Illustrious/NoobAI for anime/comics
- Still functional but declining in relevance

#### SD 3.5 Large/Medium (October 2024)
- MMDiT architecture, good prompt adherence and typography
- "3x faster than Flux dev" — good speed
- Limited LoRA ecosystem, community adoption was weak
- LoRA training requires 50GB+ VRAM without optimization — impractical on RTX 3090
- **Verdict:** Skip for comics. Community has moved to Flux and Illustrious.

#### Hunyuan Image 3.0 (October 2025)
- Tencent's DiT-based model with "world knowledge reasoning"
- Excellent for Chinese text/content, multilingual understanding
- Very high VRAM requirements (32GB recommended)
- Limited LoRA ecosystem
- ComfyUI support via vLLM acceleration
- **Verdict:** Interesting but too heavy for local RTX 3090 workflow. Not recommended for our pipeline.

#### Playground v3
- Paper published (arxiv), features deep-fusion LLM for better text-image alignment
- RGB color control, multilingual understanding
- **NOT open-sourced** — only v2.5 is available (SDXL-based, compatible with SDXL LoRAs)
- **Verdict:** Not usable for local deployment. Skip.

#### Other Notable Models (2025)
- **HiDream:** Open-source, good for diverse styles
- **Chroma:** Open-source, supports massive number of styles out-of-the-box
- **Seedream 3.0/4.0:** Strong commercial models (international availability 2025)
- **Nano Banana Pro (Google Gemini):** Best-in-class for multi-panel comics according to PCMag — but cloud-only
- **FLUX.1 Kontext Pro/Max:** Character-consistent generation, comic panel capabilities — API-only

---

## LoRA Training Guide

### Tools Comparison (2025)

| Tool | SDXL | Flux.1 | Flux.2 | UI | Platform | Best For |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| **Kohya-ss / sd-scripts v0.9.1** | ✅ Excellent | ⚠️ Limited | 🔄 | Web GUI | Win/Linux/WSL2 | ⭐ SDXL LoRA (industry standard) |
| **AI-Toolkit (Ostris)** | ✅ | ✅ Excellent | ✅ | Web UI + YAML | Linux/WSL2 | ⭐ Flux LoRA training |
| **SimpleTuner** | ✅ | ✅ | ✅ | Config files | Linux/WSL2 | Multi-model, advanced users |
| **OneTrainer** | ✅ | ✅ (with text encoders!) | 🔄 | Native GUI | Windows/Linux | Beginners, masked training |
| **FluxGym** | ❌ | ✅ | 🔄 | Docker Web UI | Linux/Docker | Easy Flux training |
| **bmaltais/kohya_ss** | ✅ | ✅ | 🔄 | PowerShell GUI | Windows | Windows-native Kohya wrapper |

#### Kohya-ss / sd-scripts v0.9.1 (March 2025) — **Industry Standard**
- **Key 2025 Features:**
  - LoRA+ support (16x learning rate ratio for LoRA-A/B — 30% faster convergence)
  - Fused backward pass (SDXL in ~17GB fp32, ~10GB bf16 — down from 24GB!)
  - Block-wise training (per-layer learning rates and dimensions)
  - Alpha mask training
  - New optimizers: AdEMAMix8bit via bitsandbytes 0.44.0
  - V-parameterization for SDXL (experimental)
- **WSL2 Setup:** Works well, community installer available
- **Best for:** SDXL/Illustrious/NoobAI LoRA training

#### AI-Toolkit (Ostris) — **Flux Specialist**
- **Key Features:**
  - Built specifically for Flux.1/2 training
  - Web UI included (localhost:8675)
  - YAML-based config (simple and reproducible)
  - Quantization support for consumer GPUs (low_vram: true)
  - Layer-specific training
  - FLUX.1-schnell training via adapter
- **RTX 3090:** 24GB is minimum for Flux LoRA training — fits exactly!
- **Best for:** Flux LoRA training

#### SimpleTuner — **Power User Tool**
- Multi-model support (SDXL, SD3, Flux.1, Flux.2, OmniGen)
- Standard Diffusers LoRA format (ComfyUI-compatible exports)
- T5 masked training, QKV fusion, multi-GPU support
- DeepSpeed integration (SDXL full U-Net on 12GB, slow)
- **Best for:** Advanced users, multi-model workflows, research

#### OneTrainer — **Best GUI Experience**
- Modern native GUI (Windows + Linux)
- Can train Flux with text encoders (unlike Kohya)
- Masked training for better subject isolation
- Regularization images support
- **Best for:** Beginners, Windows-native workflows, face/character training

### RTX 3090 (24GB VRAM) Training Capabilities

| Training Type | VRAM Usage | Feasible? | Settings |
|:---|:---:|:---:|:---|
| **SD 1.5 LoRA** | ~6-8GB | ✅ Easy | Batch 4-8, any optimizer |
| **SDXL LoRA** (standard) | ~18-22GB | ✅ Yes | Batch 1-2, AdamW8bit |
| **SDXL LoRA** (fused backward) | ~10-17GB | ✅✅ Excellent | AdaFactor, fused, bf16 |
| **SDXL LoRA** (optimizer groups) | ~14GB | ✅✅ Excellent | 4-10 groups, any optimizer |
| **Illustrious/NoobAI LoRA** | ~18-22GB | ✅ Yes | Same as SDXL |
| **Flux.1 dev LoRA** | ~23-24GB | ⚠️ Tight | Quantized model, freeze T5, batch 1 |
| **Flux.1 dev LoRA** (ai-toolkit) | ~22-24GB | ✅ Yes | quantize: true, low_vram: true |
| **Flux.2 dev LoRA** | ~24GB+ | ⚠️ Very tight | Quantized, minimal batch |
| **SD 3.5 LoRA** | ~50GB unoptimized | ❌ No | Would need heavy quantization |
| **Pony V7 LoRA** | TBD | ❓ Unknown | AuraFlow 7B — likely 24GB+ |

**Bottom Line for RTX 3090:**
- ✅ **SDXL/Illustrious/NoobAI LoRA:** Sweet spot. Plenty of VRAM, fast training.
- ✅ **Flux.1 LoRA:** Possible with AI-Toolkit (quantized mode). Tight but works.
- ⚠️ **Flux.2 LoRA:** Possible but very tight. May need cloud for comfort.
- ❌ **SD 3.5 LoRA:** Not practical without extreme optimization.

### Dataset Preparation

#### Image Count Guidelines

| Training Type | Minimum | Recommended | Optimal |
|:---|:---:|:---:|:---:|
| **Character/Face** | 8-15 | 20-40 | 30-50 |
| **Comic Art Style** | 30 | 50-100 | 100-300 |
| **Specific Artist Style** | 20 | 30-50 | 50-100 |
| **Complex Style (multiple elements)** | 50 | 100-200 | 200-500 |

#### Image Quality Requirements
- **Resolution:** 1024×1024 minimum for SDXL/Flux training (auto-bucketed)
- **Format:** PNG preferred (lossless), high-quality JPEG acceptable
- **Content:** Remove watermarks, text overlays, logos, borders
- **Variety:** Different compositions, lighting, subjects — the style is the constant, everything else should vary
- **Consistency:** All images should represent the target style clearly
- **Anti-pattern:** Don't include images that vary wildly in style quality

#### Captioning Strategy for Style LoRAs
1. **Use a trigger word:** e.g., `comicstyle_xyz` — unique, not a real word
2. **Caption every image:** Use BLIP, JoyCaption, or WD14 Tagger v3 for auto-captioning
3. **For style training:** Caption should describe content but NOT describe the style (since style = what the LoRA should learn)
4. **Example:** `comicstyle_xyz, a muscular hero standing on a rooftop, dramatic lighting, city skyline background`
5. **Folder structure (Kohya):**
   ```
   /training_data/
     /10_comicstyle_xyz/
       image001.png
       image001.txt
       image002.png
       image002.txt
   ```
   (10 = number of repeats per epoch)

#### Auto-Captioning Tools (2025)
- **WD14 Tagger v3:** Best for anime/illustration (Danbooru-style tags)
- **JoyCaption:** Natural language descriptions, good for Flux
- **BLIP/BLIP-2:** General purpose, decent quality
- **Florence-2:** Microsoft's model, good accuracy

### Training Parameters

#### Recommended SDXL/Illustrious LoRA Training (RTX 3090)

```yaml
# Kohya-ss settings for comic style LoRA on Illustrious XL
model:
  pretrained_model: "Illustrious-XL-v0.1"  # or NoobAI-XL

network:
  type: "lora"
  linear: 128            # Network rank/dimension (128 for complex styles)
  linear_alpha: 64        # Alpha = half of rank for smoother transfer
  network_args:
    loraplus_lr_ratio: 16 # LoRA+ enabled

training:
  learning_rate: 1e-4     # Base learning rate
  text_encoder_lr: 1e-5   # Text encoder learning rate (10x lower)
  optimizer_type: "AdamW8bit"
  lr_scheduler: "cosine_with_restarts"
  lr_warmup_steps: 100
  max_train_epochs: 10-15
  batch_size: 1-2
  mixed_precision: "bf16"
  gradient_accumulation_steps: 4   # Effective batch = batch_size × grad_accum
  save_every_n_epochs: 2
  
  # Memory optimization (choose one):
  fused_backward_pass: true        # Option A: ~10-17GB (AdaFactor only)
  # fused_optimizer_groups: 8      # Option B: ~14GB (any optimizer)

  # Loss optimization
  loss_type: "smooth_l1"
  huber_schedule: "snr"
  huber_c: 0.1

resolution: 1024          # 1024x1024

# Dataset
dataset:
  shuffle_caption: true
  keep_tokens: 1           # Keep trigger word in position
  caption_extension: ".txt"
```

**Total Steps Formula:**
```
Total Steps = (Images × Repeats × Epochs) / Batch_Size
Target: 1500-3000 steps for style LoRA
Example: 50 images × 10 repeats × 6 epochs / 2 batch = 1500 steps
```

#### Recommended Flux.1 LoRA Training (RTX 3090)

```yaml
# AI-Toolkit config for Flux.1 dev LoRA
model:
  name_or_path: "black-forest-labs/FLUX.1-dev"
  is_flux: true
  quantize: true           # Essential for 24GB GPU
  low_vram: true            # Enable if running desktop

network:
  type: "lora"
  linear: 128
  linear_alpha: 128

training:
  learning_rate: 4e-4       # Flux responds well to higher LR
  max_train_steps: 2000-4000
  optimizer_type: "adamw8bit"
  mixed_precision: "bf16"
  batch_size: 1
  save_every_n_steps: 500

sample:
  guidance_scale: 3.5
  sample_steps: 20

dataset:
  folder_path: "/path/to/images"
  caption_ext: ".txt"
  resolution: 1024
```

### Training Time Estimates (RTX 3090)

| Model Base | Dataset | Steps | Estimated Time |
|:---|:---:|:---:|:---:|
| SDXL/Illustrious (standard) | 50 images | 1500 | 30-60 min |
| SDXL/Illustrious (fused) | 50 images | 2000 | 45-90 min |
| SDXL/Illustrious | 100 images | 3000 | 1-2 hours |
| Flux.1 dev (quantized) | 30 images | 2000 | 2-4 hours |
| Flux.1 dev (quantized) | 50 images | 4000 | 4-8 hours |
| Flux.2 dev (quantized) | 30 images | 2000 | 3-6 hours (estimated) |

### DreamBooth vs LoRA vs LyCORIS

| Method | Quality | Size | VRAM | Training Time | Modularity | Recommendation |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **DreamBooth** (full finetune) | ★★★★★ | 2-7GB | 24GB+ | Hours | ❌ Not stackable | Best quality, but inflexible |
| **LoRA** | ★★★★☆ | 20-300MB | 10-24GB | 30min-2h | ✅ Stackable | ⭐ Best balance for our use case |
| **DreamBooth → LoRA extract** | ★★★★★ | 20-300MB | 24GB+ | Hours | ✅ Stackable | Best quality + modularity (advanced) |
| **LyCORIS (LoHa/LoCon)** | ★★★★☆ | 20-100MB | 10-24GB | 30min-2h | ✅ Stackable | Better style retention than LoRA, slightly more complex |
| **Textual Inversion** | ★★☆☆☆ | <1MB | Low | Fast | ✅ Stackable | Too weak for complex styles |

**For comic style training: LoRA is recommended.** It offers the best balance of quality, speed, size, and modularity. LyCORIS (specifically LoHa) can sometimes capture style better, but the ecosystem support is slightly more limited.

Advanced technique: Train a DreamBooth model first, then extract a LoRA from it — gives DreamBooth quality in a modular LoRA file.

---

## Custom Comic LoRA Plan

### Phase 1: Dataset Collection (Days 1-3)

#### Option A: Existing Comic Style Replication
1. **Source Material:** Collect 50-150 high-quality panels/pages from the target comic style
2. **Extraction Process:**
   - Screenshot or scan individual panels (not full pages)
   - Crop to focus on art, remove speech bubbles/text where possible
   - Upscale if below 1024px using Real-ESRGAN or similar
   - Remove any watermarks/credits that appear in panel
3. **Variety Requirements:**
   - Mix of close-ups, medium shots, wide shots
   - Various lighting conditions (day, night, dramatic)
   - Different character poses and expressions
   - Both action scenes and dialogue scenes
   - Include backgrounds/environments

#### Option B: Custom Style Definition
1. **Reference Collection:** Gather 20-30 reference images defining desired style elements
2. **Generation Phase:** Use Illustrious XL + style LoRAs to generate 80-120 images in approximately the target style
3. **Curation:** Hand-pick the best 50-100 that represent the desired look
4. **Manual Touch-up:** Optionally refine in image editor for consistency

#### Dataset Processing Pipeline
```bash
# 1. Organize images into training folder
mkdir -p /training/comic_style/10_comicstyle_xyz/

# 2. Resize/bucket images (Kohya handles this, but pre-process helps)
# Target: 1024x1024 or similar aspect ratios

# 3. Auto-caption with WD14 Tagger v3
python tag_images_by_wd14_tagger.py \
  --batch_size=4 \
  --repo_id="SmilingWolf/wd-vit-tagger-v3" \
  --onnx \
  --use_rating_tags \
  --character_tags_first \
  --always_first_tags="comicstyle_xyz" \
  ./10_comicstyle_xyz/

# 4. Review and edit captions manually
# Remove style-describing tags (the LoRA should learn the style)
# Keep content-describing tags (characters, actions, backgrounds)

# 5. Optionally use JoyCaption for natural language captions (better for Flux)
```

### Phase 2: Training Setup (Day 4)

#### Recommended Approach: Dual Training

**Primary: Illustrious XL LoRA** (for speed + ComfyUI pipeline)
- Base model: Illustrious XL v0.1 (or NoobAI-XL v-pred 1.0)
- Reason: Fast inference on RTX 3090, huge ecosystem, excellent for comic styles, SDXL-compatible
- Training: Kohya-ss with LoRA+ and fused backward pass
- Time: ~1-2 hours

**Secondary: Flux.1 dev LoRA** (for maximum quality when needed)
- Base model: FLUX.1-dev (quantized)
- Reason: Superior image quality, better prompt adherence
- Training: AI-Toolkit with quantization
- Time: ~3-6 hours

#### Environment Setup (WSL2)

```bash
# Kohya-ss for Illustrious/SDXL training
git clone https://github.com/kohya-ss/sd-scripts.git
cd sd-scripts
python -m venv venv
source venv/bin/activate
pip install torch==2.7.0 torchvision --index-url https://download.pytorch.org/whl/cu126
pip install -r requirements.txt
pip install bitsandbytes==0.44.0

# AI-Toolkit for Flux training
git clone https://github.com/ostris/ai-toolkit.git
cd ai-toolkit
python -m venv venv
source venv/bin/activate
pip install torch==2.7.0 torchvision --index-url https://download.pytorch.org/whl/cu126
pip install -r requirements.txt
echo "HF_TOKEN=your_token_here" > .env
```

### Phase 3: Training & Evaluation (Days 5-7)

#### Training Workflow

1. **Start with Illustrious XL LoRA:**
   ```bash
   # Using Kohya with optimal RTX 3090 settings
   accelerate launch --num_cpu_threads_per_process 8 sdxl_train_network.py \
     --pretrained_model_name_or_path="path/to/illustrious-xl-v0.1.safetensors" \
     --train_data_dir="./training_data" \
     --output_dir="./output/comic_lora" \
     --network_module="networks.lora" \
     --network_dim=128 \
     --network_alpha=64 \
     --network_args "loraplus_lr_ratio=16" \
     --learning_rate=1e-4 \
     --text_encoder_lr=1e-5 \
     --optimizer_type="AdamW8bit" \
     --lr_scheduler="cosine_with_restarts" \
     --lr_warmup_steps=100 \
     --max_train_epochs=15 \
     --train_batch_size=1 \
     --gradient_accumulation_steps=4 \
     --mixed_precision="bf16" \
     --save_every_n_epochs=2 \
     --sample_every_n_epochs=2 \
     --sample_prompts="./sample_prompts.txt" \
     --resolution=1024 \
     --enable_bucket \
     --loss_type="smooth_l1" \
     --huber_schedule="snr" \
     --huber_c=0.1
   ```

2. **Then Flux.1 LoRA (if time permits):**
   ```bash
   # Using AI-Toolkit
   python run.py config/comic_flux_training.yml
   ```

#### Evaluation Protocol

1. **Generate X/Y plots:**
   - Load each checkpoint (epoch 2, 4, 6, 8, 10, 12, 14)
   - Test across LoRA strengths (0.4, 0.6, 0.8, 1.0)
   - Use consistent test prompts:
     ```
     comicstyle_xyz, a hero standing on a rooftop at night, dramatic lighting, city skyline
     comicstyle_xyz, two characters arguing in a cafe, warm lighting, detailed background
     comicstyle_xyz, action scene, character jumping between buildings, motion blur
     comicstyle_xyz, close-up portrait, intense expression, rim lighting
     ```

2. **Look for the "Goldilocks Zone":**
   - ✅ Style is clearly present
   - ✅ Content is flexible (different scenes, characters work)
   - ✅ Hands/faces look good
   - ❌ If style dominates everything = overtrained (go back to earlier epoch)
   - ❌ If barely any style difference = undertrained (more epochs or higher LR)

3. **Quality Metrics:**
   - Style fidelity (does it match the reference?)
   - Prompt adherence (does it follow instructions?)
   - Anatomy quality (hands, faces, proportions)
   - Flexibility (works with different subjects/scenes?)
   - Composability (works well with other LoRAs?)

### Phase 4: Pipeline Integration

#### ComfyUI Integration
1. Place the trained `.safetensors` LoRA file in `ComfyUI/models/loras/`
2. Add a LoRA Loader node to the comic generation workflow
3. Set LoRA strength (typically 0.6-0.8 for style LoRAs)
4. Test with our ComicMaster workflow

#### Integration Points in ComicMaster Pipeline
```
Panel Script → LLM Panel Description → 
  [ComfyUI Node: Base Model (Illustrious XL)]
  [ComfyUI Node: LoRA Loader (comic_style_lora.safetensors @ 0.7)]
  [ComfyUI Node: ControlNet (for composition)]
  [ComfyUI Node: Character LoRA (if character-specific)]
  → Generated Panel Image → 
  Post-Processing → Page Assembly
```

#### Multiple LoRA Stacking
For our pipeline, we can stack LoRAs:
1. **Style LoRA** (0.6-0.8) — the comic style we trained
2. **Character LoRA** (0.5-0.7) — for consistent characters
3. **Composition LoRA** (0.3-0.5) — for panel layout guidance

---

## Recommendations

### Immediate Plan (February 2026)

1. **Base Model:** Start with **Illustrious XL** (or a good merge like NoobAI-XL v-pred)
   - Fast, efficient, excellent comic ecosystem
   - RTX 3090 handles training AND inference comfortably
   - Massive existing LoRA library to complement our custom LoRA

2. **Training Tool:** **Kohya-ss v0.9.1** for SDXL/Illustrious LoRAs
   - Industry standard, most documentation, LoRA+ support
   - Fused backward pass reduces VRAM to ~10-17GB on our RTX 3090

3. **Secondary Model:** **FLUX.1 dev** (quantized) for high-quality renders when needed
   - Train a parallel LoRA using **AI-Toolkit (Ostris)**
   - Use for hero panels or cover art quality

4. **Upgrade Path:** When FLUX.2 LoRA ecosystem matures (estimated mid-2026), transition to Flux.2 as primary model

### What NOT to Do
- ❌ Don't invest in SD 3.5 — community abandoned it
- ❌ Don't use Pony V6 for new work — Illustrious is strictly better
- ❌ Don't wait for Pony V7 ecosystem — it's too new and has face issues
- ❌ Don't try training SD 3.5 LoRAs on RTX 3090 — VRAM insufficient
- ❌ Don't do full DreamBooth fine-tuning unless absolutely needed — LoRA is sufficient and modular

### Budget Option (Free/Minimal Cost)
- Use existing comic LoRAs from CivitAI (search "comic book", "western comic", "manga style")
- Popular pre-made LoRAs: "Comic Book Page style" by ZImageTurbo (works on SDXL, Flux, Pony, Illustrious)
- Combine multiple pre-made LoRAs for a unique look
- Only train custom LoRA if no existing one matches the desired style

### Cloud Training Alternative (if RTX 3090 proves insufficient for Flux.2)
- **RunPod:** A100 40GB @ $0.69/hour or RTX 4090 @ $0.34/hour
- AI-Toolkit Ostris template available on RunPod
- Typical Flux LoRA training run: 3-6 hours = $2-4 on A100
- **MassedCompute:** Community-recommended alternative

---

## Sources & Further Reading

- [LoRA Training 2025: Ultimate Guide (sanj.dev)](https://sanj.dev/post/lora-training-2025-ultimate-guide)
- [LoRA Training Tutorial 2025 (vife.ai)](https://vife.ai/blog/lora-training-guide-2025-beginner-tutorial)
- [SDXL LoRA Training on Kohya 2025 (ThinkDiffusion)](https://learn.thinkdiffusion.com/creating-sdxl-lora-models-on-kohya/)
- [FLUX.2 Day-0 ComfyUI Support (blog.comfy.org)](https://blog.comfy.org/p/flux2-state-of-the-art-visual-intelligence)
- [Pony V7 AuraFlow Guide (apatero.com)](https://apatero.com/blog/pony-diffusion-v7-auraflow-complete-guide-2025)
- [Illustrious XL Paper (arxiv)](https://arxiv.org/html/2409.19946v1)
- [AI-Toolkit (GitHub)](https://github.com/ostris/ai-toolkit)
- [Kohya-ss sd-scripts (GitHub)](https://github.com/kohya-ss/sd-scripts)
- [SimpleTuner (GitHub)](https://github.com/bghira/SimpleTuner)
- [CivitAI SDXL vs SD3 vs FLUX comparison](https://civitai.com/articles/6515/sdxl-vs-sd3-vs-flux)

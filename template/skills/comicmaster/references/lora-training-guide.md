# SDXL LoRA Training Guide — ComicMaster

Research notes for training custom LoRAs for comic panel generation.
**Status: Research only — NOT installed yet.**

---

## 1. Kohya-ss Installation on WSL2 (Ubuntu)

### Prerequisites
- WSL2 with Ubuntu 22.04 or 24.04
- NVIDIA GPU with CUDA support (RTX 3090 = 24GB VRAM ✅)
- Python 3.10.x (kohya prefers 3.10, not 3.11+)
- CUDA Toolkit 12.1+ installed in WSL2
- ~10GB disk space for installation + models

### Installation Steps

```bash
# 1. Clone repository
cd ~/projects
git clone https://github.com/bmaltais/kohya_ss.git
cd kohya_ss

# 2. Run setup script
chmod +x setup.sh
./setup.sh
# This creates a venv, installs PyTorch + CUDA, xformers, etc.

# 3. Alternative: manual venv setup
python3.10 -m venv venv
source venv/bin/activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install xformers
pip install -r requirements.txt

# 4. Launch GUI (optional — can also use CLI)
./gui.sh --listen 0.0.0.0 --server_port 7860
# Access at http://localhost:7860

# 5. CLI training (preferred for automation)
accelerate launch --num_cpu_threads_per_process=2 sdxl_train_network.py \
  --pretrained_model_name_or_path="path/to/sdxl_base_1.0.safetensors" \
  --train_data_dir="path/to/dataset" \
  --output_dir="path/to/output" \
  --network_module=networks.lora \
  [... more args below]
```

### WSL2-specific Notes
- GPU passthrough should work out of the box with latest WSL2 + NVIDIA drivers
- Set `export CUDA_VISIBLE_DEVICES=0` if needed
- Memory: WSL2 can be limited — edit `.wslconfig` to increase RAM:
  ```ini
  [wsl2]
  memory=48GB
  swap=16GB
  ```
- xformers often works best on WSL2 vs native SDPA for Ampere (RTX 3090)

---

## 2. SDXL LoRA Training Settings (RTX 3090)

### Recommended Parameters

| Parameter | Value | Notes |
|---|---|---|
| **Resolution** | 1024×1024 | SDXL native; buckets handle other ratios |
| **Network Dimension (Rank)** | 128 | Higher = more capacity. 32-128 typical |
| **Network Alpha** | 16 | Ratio dim:alpha = 8:1 recommended |
| **Learning Rate** | 1e-4 (0.0001) | For UNet |
| **Text Encoder LR** | 5e-5 (0.00005) | Lower than UNet LR |
| **Optimizer** | AdamW8bit | Good balance of VRAM and quality |
| **Batch Size** | 1 | RTX 3090 can't fit batch_size=2 at 1024×1024 |
| **Epochs** | 10-15 | For 50-100 images |
| **Mixed Precision** | fp16 | Saves VRAM; bf16 also works on Ampere |
| **Save Precision** | fp16 | |
| **No Half VAE** | ✅ Enabled | Avoids NaN issues with SDXL VAE |
| **Cache Latents** | ✅ Enabled | Caches in RAM → faster training |
| **Gradient Checkpointing** | Optional | Saves ~30-50% VRAM, ~20% slower |
| **xFormers** | ✅ Enabled | Better than SDPA on RTX 3090 (Ampere) |

### Additional Recommended CLI Args

```bash
--network_train_unet_only          # Skip text encoder → faster, saves VRAM
--cache_text_encoder_outputs       # Cache CLIP outputs
--cache_latents_to_disk            # Cache latents on disk (saves RAM)
--enable_bucket                    # Auto-bucket different aspect ratios
--min_bucket_reso=64
--max_bucket_reso=2048
--bucket_reso_steps=64
--lr_scheduler=cosine_with_restarts
--lr_scheduler_num_cycles=3
--save_every_n_epochs=1            # Save checkpoints
--save_model_as=safetensors
```

### Steps Calculation

```
total_steps = (num_images × repeats × epochs)
```

With 50 images, 20 repeats, 10 epochs = 10,000 steps.  
With 100 images, 15 repeats, 10 epochs = 15,000 steps.

### LoRA Rank Recommendations
| Use Case | Rank (Dim) | Alpha | File Size |
|---|---|---|---|
| Lightweight style | 16-32 | 4-8 | ~20-80 MB |
| Character face | 64-128 | 8-16 | ~150-400 MB |
| Complex style | 128-256 | 16-32 | ~400-800 MB |
| Comic art style | 64-128 | 16 | ~150-400 MB |

---

## 3. Dataset Preparation

### Image Requirements
- **Minimum images:** 15-20 (bare minimum for a character LoRA)
- **Recommended:** 50-100 images for good quality
- **Ideal:** 100+ images for a robust style LoRA
- **Resolution:** At least 1024×1024 (2000-3000px long edge preferred)
- **Format:** PNG or high-quality JPEG
- **Variety:** Different poses, angles, lighting, backgrounds

### Folder Structure (Kohya)

```
training_data/
├── images/
│   ├── 20_triggername character/    # 20 repeats per epoch
│   │   ├── image001.png
│   │   ├── image001.txt             # Caption file
│   │   ├── image002.png
│   │   └── image002.txt
│   └── 15_styleword style/         # Different concept, fewer repeats
│       ├── ...
│       └── ...
├── log/
├── model/                           # Output LoRAs saved here
└── regularization/                  # Optional reg images
```

The number prefix (20_) is the **repeat count** per image per epoch.

### Captioning / Tagging

**Method 1: WD14 Auto-Tagger (built into Kohya GUI)**
- Navigate to: Utilities → Caption → WD14-Captioning
- Set prefix: `triggername, ` (with comma and trailing space!)
- Generates `.txt` files next to each image
- Produces Danbooru-style tags

**Method 2: BLIP/BLIP2 Captioning**
- Natural language captions
- Also available in Kohya: Utilities → Caption → BLIP

**Method 3: Manual Captioning**
- Best quality but time-consuming
- Use for small high-value datasets
- Example: `triggername, 1girl, short brown hair, comic art style, dynamic pose, outdoor scene`

### Caption Best Practices
- **Trigger word first** — always start with your unique trigger
- **Use rare trigger words** — avoid real words (e.g., `sks`, `xyz_character`, `ohwx`)
- **Tag what varies** — don't tag things that are constant (the LoRA learns those)
- **Include art style tags** if training a style: `comic book, western comic, bold outlines`
- **Consistent quality tags** in training → allows quality control at inference

### Image Preprocessing
1. Crop to subject (no excessive background)
2. Resize to >= 1024px on short edge
3. Remove watermarks, text overlays, borders
4. Color-correct if needed (white balance, exposure)
5. Remove duplicates or near-duplicates

---

## 4. Estimated Training Time (RTX 3090)

### Per-step Time
- **Without gradient checkpointing:** ~1.1-1.4 sec/step at 1024×1024, batch_size=1
- **With gradient checkpointing:** ~1.4-1.7 sec/step

### Total Training Time Estimates

| Dataset Size | Repeats | Epochs | Total Steps | Est. Time (no GC) | Est. Time (with GC) |
|---|---|---|---|---|---|
| 50 images | 20 | 10 | 10,000 | ~3.3-3.9 hours | ~3.9-4.7 hours |
| 50 images | 20 | 15 | 15,000 | ~4.9-5.8 hours | ~5.8-7.1 hours |
| 100 images | 15 | 10 | 15,000 | ~4.9-5.8 hours | ~5.8-7.1 hours |
| 100 images | 20 | 10 | 20,000 | ~6.5-7.8 hours | ~7.8-9.4 hours |

### VRAM Usage (RTX 3090 at 1024×1024)
| Config | VRAM Usage |
|---|---|
| batch_size=1, no GC | ~19-21 GB |
| batch_size=1, with GC | ~13-16 GB |
| batch_size=2, with GC | ~20-23 GB (tight!) |

**Recommendation:** batch_size=1 without gradient checkpointing → fastest per-step, VRAM fits.

---

## 5. Comic Panel Datasets — Where to Find

### Free / Open Sources

1. **Danbooru** (danbooru.donmai.us)
   - Massive anime/manga tagged image database
   - Great for manga-style LoRAs
   - Pre-tagged with Danbooru tags (perfect for Kohya)
   - Use tag searches: `comic`, `comic_panel`, `western_comic`

2. **HuggingFace Datasets**
   - Search: "comic", "manga", "panel"
   - `bitmind/SDXL-training` — general SDXL training dataset
   - Various character-specific datasets uploaded by community

3. **Civitai** (civitai.com)
   - Not datasets per se, but many LoRAs come with their training datasets
   - Study successful comic LoRAs → reverse-engineer dataset approach
   - Example LoRAs to study: `comic_book_style`, `marvel_comic`, `manga_panel`

4. **The Comics Dataset** (papers with code)
   - Academic datasets for comic understanding
   - Sometimes available for download
   - Research projects: DCM (Digital Comic Museum), eBDtheque

5. **Digital Comic Museum** (digitalcomicmuseum.com)
   - Public domain comics (pre-1964)
   - Great source for Western comic style training
   - Need to extract/crop panels yourself

6. **Manga109** (manga109.org)
   - 109 manga volumes with annotations
   - Academic use — check license
   - Excellent for manga panel training

7. **Your Own Panels**
   - Best approach: generate panels with ComicMaster pipeline
   - Cherry-pick the best ones
   - Use as training data for your own style LoRA
   - Bootstrapping: iteratively improve style through train → generate → curate → retrain

### Building Your Own Dataset

For ComicMaster, the ideal approach:

```
1. Generate 200-300 panels with current pipeline (various styles, characters)
2. Manually curate: select 50-100 best panels
3. Caption with consistent tags:
   "comicmaster_style, comic panel, [specific tags per image]"
4. Train LoRA on curated set
5. Generate new panels with LoRA → curate → retrain (bootstrap loop)
```

### Recommended: Comic Style Training Strategy

| Phase | Images | Source | Goal |
|---|---|---|---|
| Phase 1: Base style | 50-80 | Public domain comics + hand-picked AI | Establish bold outlines, color style |
| Phase 2: Character | 20-30 per char | Generated character refs | Consistent character faces |
| Phase 3: Refinement | 100+ | Best outputs from Phase 1+2 | Polish overall quality |

---

## 6. Quick Reference — Full Training Command

```bash
accelerate launch --num_cpu_threads_per_process=2 sdxl_train_network.py \
  --pretrained_model_name_or_path="/path/to/sdxl_base_1.0.safetensors" \
  --train_data_dir="/path/to/training_data/images" \
  --output_dir="/path/to/output" \
  --output_name="comicmaster_style_v1" \
  --resolution="1024,1024" \
  --network_module=networks.lora \
  --network_dim=128 \
  --network_alpha=16 \
  --learning_rate=0.0001 \
  --text_encoder_lr=0.00005 \
  --unet_lr=0.0001 \
  --optimizer_type=AdamW8bit \
  --train_batch_size=1 \
  --max_train_epochs=10 \
  --mixed_precision=fp16 \
  --save_precision=fp16 \
  --save_model_as=safetensors \
  --save_every_n_epochs=1 \
  --lr_scheduler=cosine_with_restarts \
  --lr_scheduler_num_cycles=3 \
  --cache_latents \
  --cache_text_encoder_outputs \
  --enable_bucket \
  --min_bucket_reso=64 \
  --max_bucket_reso=2048 \
  --bucket_reso_steps=64 \
  --no_half_vae \
  --xformers \
  --network_train_unet_only \
  --logging_dir="/path/to/logs"
```

---

## 7. Links & Resources

- **Kohya-ss GitHub:** https://github.com/bmaltais/kohya_ss
- **sd-scripts (core):** https://github.com/kohya-ss/sd-scripts
- **SDXL Base Model:** https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0
- **Puget Systems GPU Analysis:** https://www.pugetsystems.com/labs/articles/stable-diffusion-lora-training-consumer-gpu-analysis/
- **Fröhlich&Frei Training Guide:** https://www.froehlichundfrei.de/blog/2024-01-22-stable-diffusion-xl-lora-training/
- **CivitAI (models+datasets):** https://civitai.com
- **Danbooru:** https://danbooru.donmai.us
- **Digital Comic Museum:** https://digitalcomicmuseum.com

---

*Last updated: 2026-02-09 — Research only, NOT installed yet.*

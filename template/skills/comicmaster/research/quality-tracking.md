# ML-Based Quality Tracking for Comic Generation

> **Research Date:** 2026-02-08
> **Goal:** Objectively measure and track the quality of AI-generated comic panels over time, so we can see if workflow/model/prompt changes actually improve output.

---

## Available Metrics

### 1. No-Reference Technical Quality

#### 1a. PIL-Based Metrics (Zero Dependencies)
These use only PIL/Pillow — already installed.

| Metric | What it Measures | Range | Speed |
|--------|-----------------|-------|-------|
| **Laplacian Variance** | Sharpness/blur detection | 0–∞ (higher = sharper) | <1ms |
| **Color Entropy** | Color richness/variety | 0–8 bits | <1ms |
| **Contrast (RMS)** | Dynamic range of luminance | 0–127 | <1ms |
| **Saturation Mean** | Color vibrancy | 0–1 | <1ms |
| **Edge Density** | Detail level | 0–1 | ~5ms |
| **Dark/Bright Ratio** | Exposure issues | 0–1 | <1ms |

```python
from PIL import Image, ImageFilter, ImageStat
import numpy as np

def pil_sharpness(img: Image.Image) -> float:
    """Laplacian variance — higher = sharper."""
    gray = np.array(img.convert('L'), dtype=np.float64)
    laplacian = np.array([
        [0, 1, 0],
        [1, -4, 1],
        [0, 1, 0]
    ], dtype=np.float64)
    from scipy.signal import convolve2d
    lap = convolve2d(gray, laplacian, mode='same')
    return float(lap.var())

def pil_contrast(img: Image.Image) -> float:
    """RMS contrast of luminance channel."""
    gray = img.convert('L')
    stat = ImageStat.Stat(gray)
    return stat.stddev[0]

def pil_saturation(img: Image.Image) -> float:
    """Mean saturation from HSV."""
    hsv = img.convert('HSV')
    s_channel = np.array(hsv)[:, :, 1]
    return float(s_channel.mean() / 255.0)

def pil_color_entropy(img: Image.Image) -> float:
    """Entropy of color histogram — measures color diversity."""
    hist = img.histogram()
    hist = np.array(hist, dtype=np.float64)
    hist = hist / hist.sum()
    hist = hist[hist > 0]
    return float(-np.sum(hist * np.log2(hist)))

def pil_edge_density(img: Image.Image) -> float:
    """Fraction of pixels that are edges (Sobel-like)."""
    edges = img.convert('L').filter(ImageFilter.FIND_EDGES)
    arr = np.array(edges)
    threshold = 30
    return float((arr > threshold).mean())

def pil_exposure(img: Image.Image) -> dict:
    """Check for under/overexposure."""
    gray = np.array(img.convert('L'))
    dark = float((gray < 20).mean())
    bright = float((gray > 235).mean())
    return {"dark_ratio": dark, "bright_ratio": bright}
```

**Verdict:** ✅ Implement immediately. Zero cost, fast, useful as baseline.

#### 1b. BRISQUE (No-Reference IQA)

**What:** Blind/Referenceless Image Spatial Quality Evaluator. Uses natural scene statistics (NSS) to detect distortions like noise, blur, compression artifacts.

**How it works:**
1. Computes Mean Subtracted Contrast Normalized (MSCN) coefficients
2. Fits Generalized Gaussian Distribution (GGD) to MSCN coefficients
3. Feeds features to an SVR trained on human quality ratings

**Score range:** 0 (best) to 100 (worst)

**Python implementations:**
- `opencv-contrib-python` → `cv2.quality.QualityBRISQUE` (built-in, needs model files)
- `pip install brisque` (standalone, ~50KB + libsvm)
- `pip install brisque-opencv` (opencv wrapper)
- `pip install pybrisque` (from Bukalapak)

**Dependencies:** `opencv-contrib-python` or `brisque` package + `libsvm`
**Download size:** Negligible (~100KB for model files)
**Inference speed:** ~5-10ms per image
**Reliability for comics:** ⚠️ MEDIUM — Trained on natural photographs, not stylized art. May misrate intentionally stylized images. Good for catching blur/noise artifacts but may not understand comic art style.

**Practical usage:**
```python
import cv2
# Using opencv-contrib
obj = cv2.quality.QualityBRISQUE_create(
    "brisque_model_live.yml", "brisque_range_live.yml"
)
score = obj.compute(img)  # returns (score, 0, 0, 0)

# Using pybrisque
from brisque import BRISQUE
brisque = BRISQUE()
score = brisque.score(img)  # PIL Image → float
```

**Verdict:** ✅ Easy to add. Useful as a technical quality check but interpret scores with caution for stylized art.

---

### 2. Prompt Alignment (CLIP Score)

**What:** Measures how well a generated image matches its text prompt, using CLIP's shared image-text embedding space.

**How it works:**
1. Encode the image with CLIP's visual encoder
2. Encode the text prompt with CLIP's text encoder
3. Compute cosine similarity between the two embeddings
4. Score = max(100 × cosine_similarity, 0)

**Score range:** 0–100 (typical good images: 25–35+)

**Key insight for us:** We have the prompts used to generate each panel — this is a perfect metric for our use case!

**Python implementations:**
- `torchmetrics.multimodal.CLIPScore` (recommended, cleanest API)
- `clip-score` PyPI package
- Direct with `transformers` + CLIP model

**Dependencies:**
- `pip install torchmetrics` (likely already have it or easy add)
- `pip install transformers` (likely already installed for other things)
- CLIP model: `openai/clip-vit-base-patch16` (~600MB) or `openai/clip-vit-large-patch14` (~1.7GB)

**Inference speed:** ~50ms per image on RTX 3090
**Download size:** 600MB (base) to 1.7GB (large)

**Usage with torchmetrics:**
```python
import torch
from torchmetrics.multimodal.clip_score import CLIPScore
from PIL import Image
import numpy as np

metric = CLIPScore(model_name_or_path="openai/clip-vit-base-patch16")

def clip_prompt_alignment(image_path: str, prompt: str) -> float:
    img = Image.open(image_path)
    img_tensor = torch.tensor(np.array(img)).permute(2, 0, 1)  # HWC → CHW
    score = metric(img_tensor, prompt)
    return float(score.detach())
```

**Usage with transformers directly:**
```python
from transformers import CLIPProcessor, CLIPModel
import torch
from PIL import Image

model = CLIPModel.from_pretrained("openai/clip-vit-base-patch16")
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch16")

def clip_score(image_path: str, prompt: str) -> float:
    image = Image.open(image_path)
    inputs = processor(text=[prompt], images=image, return_tensors="pt", padding=True)
    outputs = model(**inputs)
    similarity = torch.cosine_similarity(
        outputs.image_embeds, outputs.text_embeds
    )
    return float(similarity.item())
```

**Reliability for comics:** ✅ HIGH — CLIP understands artistic/stylistic content well. Excellent for measuring whether the panel depicts what we asked for. However, note that CLIP may not capture fine details (e.g., "character wears a red hat" might score well even if the hat is blue).

**Verdict:** ✅ High priority. This is our #1 most useful metric given that we have prompt→image pairs.

---

### 3. CLIP-IQA (CLIP-Based Image Quality Assessment)

**What:** Uses CLIP to assess perceptual quality dimensions by comparing images against prompt pairs like "Good photo" vs "Bad photo", "Sharp photo" vs "Blurry photo", etc.

**Key advantage over BRISQUE:** Works in semantic space, so it understands artistic intent better than pixel-statistics approaches.

**Built-in prompt dimensions:**
- `quality`: "Good photo" vs "Bad photo"
- `sharpness`: "Sharp photo" vs "Blurry photo"
- `noisiness`: "Clean photo" vs "Noisy photo"
- `colorfullness`: "Colorful photo" vs "Dull photo"
- `contrast`: "High contrast photo" vs "Low contrast photo"
- `complexity`: "Complex photo" vs "Simple photo"
- `natural`: "Natural photo" vs "Synthetic photo"
- `beautiful`: "Beautiful photo" vs "Ugly photo"

**Custom prompts possible!** We could add comic-specific ones:
- ("Well-drawn comic panel", "Poorly drawn comic panel")
- ("Detailed illustration", "Messy illustration")
- ("Clean linework", "Distorted linework")

**Score range:** 0–1 per dimension (probability image matches positive prompt)

**Dependencies:** Same as CLIP Score — `torchmetrics` + CLIP model
**Inference speed:** ~50ms per image per dimension
**Download size:** Same CLIP model (already needed for CLIP Score)

```python
from torchmetrics.multimodal import CLIPImageQualityAssessment
import torch
from PIL import Image
import numpy as np

metric = CLIPImageQualityAssessment(
    model_name_or_path="openai/clip-vit-large-patch14",
    prompts=(
        "quality",
        "sharpness",
        "colorfullness",
        "beautiful",
        ("Well-drawn comic panel", "Poorly drawn comic panel"),
    )
)

def clip_iqa(image_path: str) -> dict:
    img = Image.open(image_path)
    img_tensor = torch.tensor(np.array(img)).permute(2, 0, 1).unsqueeze(0).float() / 255.0
    scores = metric(img_tensor)
    return {k: float(v) for k, v in scores.items()}
```

**Reliability for comics:** ✅ HIGH — Semantic quality assessment. Custom prompts let us tune to comic-specific quality dimensions.

**Verdict:** ✅ Implement alongside CLIP Score (shares same model). Extremely valuable.

---

### 4. Aesthetic Score (LAION Aesthetic Predictor)

**What:** A simple linear layer on top of CLIP embeddings, trained on human aesthetic ratings from the LAION dataset. Predicts how "aesthetically pleasing" an image is.

**How it works:**
1. Extract CLIP ViT-L/14 image embedding (768-dim vector)
2. Pass through a single `nn.Linear(768, 1)` layer
3. Output: aesthetic score 1–10

**Architecture:** Literally just `CLIP embedding → Linear(768, 1) → score`

**Model sizes:**
- `sa_0_4_vit_l_14_linear.pth` — ~3KB (yes, 3 kilobytes! it's just a linear layer)
- `sa_0_4_vit_b_32_linear.pth` — ~2KB
- Requires CLIP model underneath (~600MB–1.7GB, shared with CLIP Score)

**Improved version (V2):** `christophschuhmann/improved-aesthetic-predictor` — uses MLP instead of linear, slightly better accuracy.

**Dependencies:**
- `pip install simple-aesthetics-predictor` (clean wrapper)
- Or manually: just load the .pth file + CLIP
- CLIP model (shared dependency)

**Inference speed:** ~50ms (dominated by CLIP encoding; linear layer is instant)

```python
import torch
import torch.nn as nn
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

# Load CLIP (shared with other metrics)
clip_model = CLIPModel.from_pretrained("openai/clip-vit-large-patch14")
processor = CLIPProcessor.from_pretrained("openai/clip-vit-large-patch14")

# Load aesthetic predictor head (3KB download)
aesthetic_head = nn.Linear(768, 1)
state_dict = torch.load("sa_0_4_vit_l_14_linear.pth", map_location="cpu")
aesthetic_head.load_state_dict(state_dict)
aesthetic_head.eval()

def aesthetic_score(image_path: str) -> float:
    image = Image.open(image_path)
    inputs = processor(images=image, return_tensors="pt")
    with torch.no_grad():
        embedding = clip_model.get_image_features(**inputs)
        embedding = embedding / embedding.norm(dim=-1, keepdim=True)
        score = aesthetic_head(embedding)
    return float(score.item())
```

**Reliability for comics:** ⚠️ MEDIUM-HIGH — Trained on photos/art rated by humans. Works reasonably well for stylized art but may have biases toward photographic aesthetics. Still, it gives a useful signal about overall visual appeal.

**Verdict:** ✅ Very easy to add on top of CLIP. Practically free if we already load CLIP.

---

### 5. NIMA (Neural Image Assessment)

**What:** Google's neural network for predicting aesthetic and technical quality scores, trained on the AVA (Aesthetic Visual Analysis) dataset of 250K images with human ratings.

**How it works:**
1. Uses a CNN backbone (VGG16 or MobileNet)
2. Outputs a distribution over 10 quality buckets (1–10)
3. Mean of distribution = aesthetic score
4. Std of distribution = how controversial the quality is

**PyTorch implementations:**
- `truskovskiyk/nima.pytorch` — well-maintained, pip installable
- `yunxiaoshi/Neural-IMage-Assessment` — clean PyTorch implementation
- `IDLabMedia/NIMA` — another fork

**Dependencies:** PyTorch + pretrained weights (~50–500MB depending on backbone)
**Inference speed:** ~10-20ms on GPU (MobileNet) to ~30ms (VGG16)
**Download size:** MobileNet: ~15MB weights; VGG16: ~528MB weights

**Reliability for comics:** ⚠️ MEDIUM — Trained on photos (AVA dataset), not illustrations. May not generalize perfectly to comic art style. LAION aesthetic predictor may be more useful since it was trained on a more diverse dataset.

**Verdict:** ⏸️ Lower priority. The LAION Aesthetic Predictor does a similar job with less overhead and shares the CLIP dependency. Consider if we need a second opinion on aesthetics.

---

### 6. Character Consistency Score

**What:** Measures how consistent a character looks across panels compared to their reference image. Critical for comics!

**Approaches:**

#### 6a. CLIP Embedding Similarity (Recommended)
Compare CLIP embeddings of character crops between panels and reference.

```python
def character_consistency_clip(panel_crop: str, ref_image: str) -> float:
    """Cosine similarity of CLIP embeddings between panel char crop and reference."""
    inputs_panel = processor(images=Image.open(panel_crop), return_tensors="pt")
    inputs_ref = processor(images=Image.open(ref_image), return_tensors="pt")
    
    with torch.no_grad():
        emb_panel = clip_model.get_image_features(**inputs_panel)
        emb_ref = clip_model.get_image_features(**inputs_ref)
    
    similarity = torch.cosine_similarity(emb_panel, emb_ref)
    return float(similarity.item())
```
- **Pros:** Semantic similarity (catches style/pose), uses shared CLIP model
- **Cons:** Doesn't measure pixel-level consistency
- **Score range:** -1 to 1 (typically 0.5–0.95 for similar images)

#### 6b. SSIM (Structural Similarity Index)
Pixel-level structural comparison. Better for measuring exact visual consistency.

```python
from skimage.metrics import structural_similarity as ssim
from PIL import Image
import numpy as np

def character_consistency_ssim(panel_crop: str, ref_image: str, size=(224, 224)) -> float:
    img1 = np.array(Image.open(panel_crop).resize(size))
    img2 = np.array(Image.open(ref_image).resize(size))
    return ssim(img1, img2, channel_axis=2, data_range=255)
```
- **Pros:** Precise structural comparison
- **Cons:** Sensitive to pose/angle changes (a character turned sideways will score low)
- **Score range:** 0–1

#### 6c. Combined Approach (Recommended)
```python
def character_consistency(panel_crop: str, ref_image: str) -> dict:
    return {
        "semantic_similarity": character_consistency_clip(panel_crop, ref_image),
        "structural_similarity": character_consistency_ssim(panel_crop, ref_image),
        "combined": 0.7 * clip_sim + 0.3 * ssim_score  # weight semantic higher
    }
```

**Challenge:** Requires character detection/cropping from panels. Options:
- Manual crop regions (if panel layout is known)
- Face detection → crop face region → compare
- Full panel comparison (less precise but simpler)

**Verdict:** ✅ Implement with CLIP similarity first (already have the model). SSIM as bonus. Character cropping is the hard part — may need face detection or manual regions initially.

---

### 7. Text Artifact Detection

**What:** AI image generators (especially SDXL, Flux) sometimes produce garbled pseudo-text in images. We want to detect this to flag bad panels.

**Approaches:**

#### 7a. EasyOCR (Recommended)
```python
import easyocr

reader = easyocr.Reader(['en'], gpu=True)

def detect_text_artifacts(image_path: str) -> dict:
    results = reader.readtext(image_path)
    # Filter by confidence — low-confidence detections are likely artifacts
    artifacts = [r for r in results if r[2] < 0.5]  # gibberish text
    real_text = [r for r in results if r[2] >= 0.5]  # intentional text
    
    return {
        "artifact_count": len(artifacts),
        "artifact_area_ratio": sum(polygon_area(r[0]) for r in artifacts) / image_area,
        "real_text_count": len(real_text),
        "detected_strings": [r[1] for r in results],
        "has_artifacts": len(artifacts) > 0
    }
```
- **Deps:** `pip install easyocr` (~60MB download + model ~100MB on first run)
- **Speed:** ~100-200ms per image on GPU
- **Approach:** If OCR detects text with low confidence → it's probably gibberish artifacts

#### 7b. Pytesseract (Lighter Alternative)
```python
import pytesseract
from PIL import Image

def detect_text_pytesseract(image_path: str) -> dict:
    img = Image.open(image_path)
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    
    # Count text regions with low confidence
    artifact_count = sum(1 for conf in data['conf'] if 0 < int(conf) < 30)
    text_regions = sum(1 for conf in data['conf'] if int(conf) >= 60)
    
    return {
        "artifact_regions": artifact_count,
        "text_regions": text_regions,
        "has_artifacts": artifact_count > 2  # threshold
    }
```
- **Deps:** `pip install pytesseract` + system `tesseract-ocr` package
- **Speed:** ~50-100ms per image
- **Lighter** but less accurate than EasyOCR

#### 7c. Edge-Based Text Detection (Zero Dep)
A simple heuristic: text areas tend to have high-frequency edges in small regions.

```python
def simple_text_detector(img: Image.Image) -> float:
    """Heuristic: ratio of small high-contrast regions (text-like)."""
    gray = np.array(img.convert('L'))
    # Detect horizontal edges (text has strong horizontal patterns)
    h_edges = np.abs(np.diff(gray.astype(float), axis=1))
    # Count dense edge regions
    block_size = 32
    text_like_blocks = 0
    total_blocks = 0
    for y in range(0, gray.shape[0] - block_size, block_size):
        for x in range(0, gray.shape[1] - block_size, block_size):
            block = h_edges[y:y+block_size, x:x+block_size]
            total_blocks += 1
            if block.mean() > 15 and block.std() > 20:
                text_like_blocks += 1
    return text_like_blocks / max(total_blocks, 1)
```

**Important caveat for comics:** We intentionally add speech bubbles with text! The text artifact detector needs to distinguish between:
1. Our added speech bubble text (legitimate, added post-generation)
2. Garbled text artifacts from the AI generator (bad)

**Strategy:** Run text detection on the **raw generated panels** BEFORE adding speech bubbles. Any text found = artifact.

**Verdict:** ✅ EasyOCR for accuracy, pytesseract as lightweight fallback. Run on pre-bubble panels.

---

### 8. FID (Fréchet Inception Distance) — NOT Recommended

**What:** Measures distance between the distribution of generated images and real images using Inception V3 features.

**Why NOT for us:**
- Requires a **reference dataset** of "good" comic panels (we don't have one)
- Measures **distributional** quality, not individual image quality
- Needs ~10K+ images to be statistically meaningful
- Recent research (CVPR 2024) shows FID contradicts human judgment in many cases
- **CMMD** (CLIP Maximum Mean Discrepancy) proposed as better alternative but still needs reference set

**Alternative considered:** CMMD from Google (2024 paper) — same reference set problem.

**Verdict:** ❌ Skip. Not suitable for our per-image, no-reference use case.

---

## Implementation Plan

### Phase 1: PIL-Based Metrics (No New Dependencies)
**Effort:** 1-2 hours | **Dependencies:** None (PIL, numpy, scipy already installed)

Implement:
- [x] Sharpness (Laplacian variance)
- [x] Contrast (RMS)
- [x] Saturation (mean HSV)
- [x] Color entropy
- [x] Edge density
- [x] Exposure check (dark/bright ratio)

**Value:** Catches obvious technical issues — blurry panels, washed out colors, underexposure. Not sophisticated but fast and reliable.

### Phase 2: CLIP Score + CLIP-IQA + Aesthetic Score
**Effort:** 3-4 hours | **Dependencies:** `torchmetrics`, `transformers` + CLIP model (~600MB–1.7GB)

Implement:
- [ ] CLIP Score (prompt↔image alignment)
- [ ] CLIP-IQA (multi-dimensional quality via prompt pairs)
- [ ] Aesthetic Score (LAION predictor, 3KB on top of CLIP)
- [ ] Character consistency (CLIP embedding similarity)

**Key insight:** All four metrics share the same CLIP model! Load once, score four ways.

**Value:** The most useful metrics for our use case. CLIP Score tells us if the panel matches the prompt. CLIP-IQA tells us about perceptual quality. Aesthetic score gives an overall "does this look good?" number. Character consistency tracks our biggest challenge.

### Phase 3: Text Detection + BRISQUE
**Effort:** 2-3 hours | **Dependencies:** `easyocr` (~160MB) or `pytesseract` + `tesseract-ocr`

Implement:
- [ ] Text artifact detection (run on raw panels before bubbles)
- [ ] BRISQUE score (optional, for a traditional IQA baseline)

**Value:** Text artifacts are a real problem with SDXL/Flux. Catching them automatically is very useful.

### Phase 4: Advanced (Future)
**Effort:** Variable | **Dependencies:** Various

- [ ] NIMA aesthetic predictor (second opinion)
- [ ] Face detection + per-face consistency scoring
- [ ] Panel composition analysis (rule of thirds, etc.)
- [ ] Style consistency across panels (CLIP embedding variance)

---

## Scoring System Design

### Per-Panel Scores

```python
@dataclass
class PanelScore:
    panel_id: str                    # e.g., "p1_panel_3"
    image_path: str
    prompt: str
    timestamp: str                   # ISO 8601
    
    # Phase 1: Technical (PIL-based)
    sharpness: float                 # Laplacian variance, raw value
    contrast: float                  # RMS contrast, 0-127
    saturation: float                # Mean saturation, 0-1
    color_entropy: float             # Histogram entropy, 0-8
    edge_density: float              # Edge pixel ratio, 0-1
    dark_ratio: float                # Underexposed pixel ratio, 0-1
    bright_ratio: float              # Overexposed pixel ratio, 0-1
    
    # Phase 2: Semantic (CLIP-based)
    prompt_alignment: float          # CLIP Score, 0-100
    aesthetic_score: float           # LAION aesthetic, 1-10
    clip_quality: float              # CLIP-IQA "quality", 0-1
    clip_sharpness: float            # CLIP-IQA "sharpness", 0-1
    clip_colorfulness: float         # CLIP-IQA "colorfullness", 0-1
    clip_beautiful: float            # CLIP-IQA "beautiful", 0-1
    consistency_score: float         # vs char reference, 0-1 (if available)
    
    # Phase 3: Artifacts
    text_artifact_count: int         # Number of detected text artifacts
    text_artifact_area: float        # Fraction of image area with artifacts
    brisque_score: float             # BRISQUE, 0-100 (lower = better)
    
    # Computed
    overall_score: float             # Weighted composite, 0-100

def compute_overall(self) -> float:
    """Weighted average of normalized scores."""
    weights = {
        'prompt_alignment': 0.30,     # Most important: does it match the prompt?
        'aesthetic_score': 0.20,      # Does it look good?
        'technical_quality': 0.15,    # Sharpness, contrast, etc.
        'consistency': 0.15,          # Character consistency
        'no_artifacts': 0.10,         # No text artifacts
        'clip_quality': 0.10,         # CLIP-based quality
    }
    
    # Normalize each to 0-1
    scores = {
        'prompt_alignment': self.prompt_alignment / 40,  # typical max ~35-40
        'aesthetic_score': self.aesthetic_score / 10,
        'technical_quality': min(self.sharpness / 1000, 1.0),  # normalize
        'consistency': self.consistency_score,
        'no_artifacts': 1.0 - min(self.text_artifact_area * 10, 1.0),
        'clip_quality': self.clip_quality,
    }
    
    return sum(scores[k] * weights[k] for k in weights) * 100
```

### Per-Comic Aggregation

```python
@dataclass
class ComicScore:
    run_id: str                      # Unique run identifier
    story_title: str
    timestamp: str
    model_config: dict               # Checkpoint, sampler, steps, etc.
    
    panel_scores: list[PanelScore]
    
    # Aggregates
    mean_overall: float
    min_overall: float               # Worst panel score
    max_overall: float               # Best panel score
    std_overall: float               # Consistency of quality
    
    mean_prompt_alignment: float
    mean_aesthetic: float
    mean_consistency: float
    total_text_artifacts: int
    
    # Panel-level breakdown
    weakest_panel: str               # ID of lowest-scoring panel
    strongest_panel: str             # ID of highest-scoring panel
    
    def summary(self) -> str:
        return f"""
Comic Quality Report: {self.story_title}
Run: {self.run_id} | {self.timestamp}
═══════════════════════════════════
Overall:      {self.mean_overall:.1f}/100 (±{self.std_overall:.1f})
Prompt Match: {self.mean_prompt_alignment:.1f}/40
Aesthetic:    {self.mean_aesthetic:.1f}/10
Consistency:  {self.mean_consistency:.2f}
Artifacts:    {self.total_text_artifacts} detected
Best Panel:   {self.strongest_panel} ({self.max_overall:.1f})
Worst Panel:  {self.weakest_panel} ({self.min_overall:.1f})
"""
```

### Cross-Run Comparison

```python
def compare_runs(run_a: ComicScore, run_b: ComicScore) -> dict:
    """Compare two comic generation runs."""
    return {
        "overall_delta": run_b.mean_overall - run_a.mean_overall,
        "prompt_alignment_delta": run_b.mean_prompt_alignment - run_a.mean_prompt_alignment,
        "aesthetic_delta": run_b.mean_aesthetic - run_a.mean_aesthetic,
        "consistency_delta": run_b.mean_consistency - run_a.mean_consistency,
        "artifact_delta": run_b.total_text_artifacts - run_a.total_text_artifacts,
        "improved": run_b.mean_overall > run_a.mean_overall,
        "significant": abs(run_b.mean_overall - run_a.mean_overall) > 5.0,
        "per_metric_winner": {
            "prompt_alignment": "B" if run_b.mean_prompt_alignment > run_a.mean_prompt_alignment else "A",
            "aesthetic": "B" if run_b.mean_aesthetic > run_a.mean_aesthetic else "A",
            "consistency": "B" if run_b.mean_consistency > run_a.mean_consistency else "A",
            "artifacts": "B" if run_b.total_text_artifacts < run_a.total_text_artifacts else "A",
        }
    }
```

---

## Data Storage Format

### JSON Structure (per run)

```json
{
    "run_id": "2026-02-08_midnight-heist_v3",
    "story_title": "Midnight Heist",
    "timestamp": "2026-02-08T22:30:00+01:00",
    "model_config": {
        "checkpoint": "dreamshaperXL_v21",
        "sampler": "dpmpp_2m_sde",
        "steps": 25,
        "cfg_scale": 7.0,
        "resolution": "1024x1024",
        "ip_adapter": "ip-adapter-plus_sdxl_vit-h",
        "ip_adapter_weight": 0.6
    },
    "summary": {
        "mean_overall": 72.5,
        "min_overall": 58.2,
        "max_overall": 89.1,
        "std_overall": 8.3,
        "panel_count": 12,
        "total_text_artifacts": 2
    },
    "panels": [
        {
            "panel_id": "p1_panel_1",
            "image_path": "output/midnight_heist/panels/p1_panel_1.png",
            "prompt": "noir detective standing under streetlight, rain, dramatic shadows...",
            "scores": {
                "sharpness": 842.3,
                "contrast": 67.2,
                "saturation": 0.35,
                "color_entropy": 6.8,
                "edge_density": 0.42,
                "dark_ratio": 0.15,
                "bright_ratio": 0.02,
                "prompt_alignment": 32.4,
                "aesthetic_score": 7.2,
                "clip_quality": 0.82,
                "clip_sharpness": 0.91,
                "clip_colorfulness": 0.45,
                "clip_beautiful": 0.78,
                "consistency_score": 0.85,
                "text_artifact_count": 0,
                "text_artifact_area": 0.0,
                "brisque_score": 22.5,
                "overall": 78.6
            }
        }
    ]
}
```

### File Location

```
skills/comicmaster/output/<story_name>/
├── panels/          # Generated panel images
├── pages/           # Assembled page layouts
├── quality/
│   ├── scores.json  # Full quality data for this run
│   └── report.txt   # Human-readable summary
└── comic.pdf        # Final output
```

### Historical Tracking

```
skills/comicmaster/quality_history/
├── index.json       # List of all scored runs
├── 2026-02-08_midnight-heist_v1.json
├── 2026-02-08_midnight-heist_v2.json
├── 2026-02-08_midnight-heist_v3.json
└── comparison.csv   # Side-by-side metrics over time
```

`comparison.csv`:
```csv
run_id,timestamp,story,overall,prompt_align,aesthetic,consistency,artifacts
midnight-heist_v1,2026-02-08T20:00,Midnight Heist,65.2,28.1,6.3,0.72,5
midnight-heist_v2,2026-02-08T21:00,Midnight Heist,70.8,30.5,7.1,0.78,3
midnight-heist_v3,2026-02-08T22:30,Midnight Heist,72.5,32.4,7.2,0.85,2
```

---

## Quality Dashboard Concept

### CLI Report (Immediate)

```
╔══════════════════════════════════════════════════╗
║         COMIC QUALITY REPORT                     ║
║         Midnight Heist v3                        ║
║         2026-02-08 22:30                         ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  Overall Score:  72.5/100  ████████░░  (+1.7)    ║
║                                                  ║
║  Prompt Match:   32.4/40   ████████░░            ║
║  Aesthetic:       7.2/10   ███████░░░            ║
║  Consistency:    0.85      █████████░  (+0.07)   ║
║  Text Artifacts:    2      ██░░░░░░░░  (-1)      ║
║                                                  ║
║  Panel Breakdown:                                ║
║  ┌─────────────────────────────────────────┐     ║
║  │ P1-1: ████████░░ 78.6                   │     ║
║  │ P1-2: ██████████ 89.1  ← BEST          │     ║
║  │ P1-3: ██████░░░░ 62.3                   │     ║
║  │ P2-1: ████████░░ 74.2                   │     ║
║  │ P2-2: █████░░░░░ 58.2  ← WORST         │     ║
║  │ P2-3: ████████░░ 76.8                   │     ║
║  └─────────────────────────────────────────┘     ║
║                                                  ║
║  vs Previous Run (v2):                           ║
║  Overall:     +1.7  ↑  Improving                 ║
║  Consistency: +0.07 ↑  More consistent chars     ║
║  Artifacts:   -1    ↑  Fewer text glitches       ║
║                                                  ║
╚══════════════════════════════════════════════════╝
```

### Future: HTML Dashboard
A simple Jinja2 template rendering scores.json into a visual page with:
- Score trend charts (using Chart.js or similar)
- Panel thumbnails with overlay scores
- Side-by-side comparison of runs
- Heatmaps showing which metrics improved/degraded

---

## Dependency Summary

### Already Available (Phase 1)
- `PIL/Pillow` — image processing
- `numpy` — array operations
- `scipy` — Laplacian, convolutions

### Phase 2 Additions (~600MB–1.7GB total, one-time)
- `torchmetrics` — pip install, small package
- `transformers` — likely already installed
- CLIP model — `openai/clip-vit-base-patch16` (600MB) or `openai/clip-vit-large-patch14` (1.7GB)
- LAION aesthetic head — 3KB file

**Note:** If ComfyUI already has CLIP loaded, we might be able to reuse it!

### Phase 3 Additions (~160MB)
- `easyocr` or `pytesseract` + `tesseract-ocr`
- `opencv-contrib-python` (for BRISQUE, if not already installed)
- `scikit-image` (for SSIM, likely already installed)

### Total New Downloads
- **Minimum viable:** ~0 bytes (Phase 1 only, PIL metrics)
- **Recommended:** ~600MB (Phase 1 + 2 with CLIP base)
- **Full suite:** ~800MB (all phases)

---

## RTX 3090 Performance Estimates

| Metric | Per-Panel Time | VRAM Usage | Notes |
|--------|---------------|------------|-------|
| PIL metrics (all 6) | ~10ms | 0 | CPU only |
| CLIP Score | ~50ms | ~1.5GB | GPU |
| CLIP-IQA (5 dims) | ~50ms | shared | Reuses CLIP |
| Aesthetic Score | ~1ms | shared | Just a linear layer |
| Character CLIP sim | ~25ms | shared | One extra encoding |
| SSIM | ~10ms | 0 | CPU/numpy |
| EasyOCR | ~100-200ms | ~500MB | GPU |
| BRISQUE | ~10ms | 0 | CPU only |
| **Total per panel** | **~250-350ms** | **~2GB** | |
| **12-panel comic** | **~3-4 seconds** | | |

This is completely feasible on RTX 3090 — quality scoring takes <5 seconds for an entire comic, compared to minutes/hours for generation.

---

## Recommended Implementation Order

1. **NOW:** Create `quality_tracker.py` with PIL metrics (Phase 1). Start scoring every run.
2. **NEXT SESSION:** Add CLIP Score + CLIP-IQA + Aesthetic Score. This gives us the most valuable metrics.
3. **WHEN NEEDED:** Add text artifact detection with EasyOCR.
4. **ONGOING:** Tune weights in the overall score based on what correlates with our subjective quality assessment.

The key insight is: **we don't need perfect scores, we need consistent scores that trend correctly.** If score X goes up when we make a change that we subjectively think is better, then X is a useful metric for us regardless of its absolute value.

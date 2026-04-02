#!/usr/bin/env python3
"""Panel upscaling for ComicMaster pipeline.

Supports three methods:
  - "model"  : ComfyUI upscale model (4x-UltraSharp etc.) — best quality
  - "latent" : ComfyUI latent upscale + KSampler (needs checkpoint)
  - "simple" : PIL Lanczos resize — fast, no GPU needed

Usage:
    python upscale.py <image_or_dir> [--scale 2.0] [--method auto] [--output dir]
"""

import copy
import json
import os
import sys
import time

# ---------------------------------------------------------------------------
# Resolve paths so we can import comfy_client from the ComfyUI skill
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKFLOWS_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "workflows")
COMFYUI_SCRIPTS = os.path.normpath(
    os.path.join(SCRIPT_DIR, "..", "..", "comfyui", "scripts")
)
if COMFYUI_SCRIPTS not in sys.path:
    sys.path.insert(0, COMFYUI_SCRIPTS)

# ---------------------------------------------------------------------------
# Available upscale models (ordered by preference)
# ---------------------------------------------------------------------------
PREFERRED_MODELS = [
    "4x-UltraSharp.pth",
    "4xUltrasharp_4xUltrasharpV10.pt",
    "4x_foolhardy_Remacri.pth",
    "4xReal_SSDIR_DAT_GAN.pth",
    "4x_NMKD-Superscale-SP_178000_G.pth",
    "8x_NMKD-Superscale_150000_G.pth",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_available_model() -> str | None:
    """Query ComfyUI for installed upscale models and return the best one."""
    try:
        import urllib.request
        r = urllib.request.urlopen(
            "http://host.docker.internal:8188/object_info/UpscaleModelLoader",
            timeout=5,
        )
        info = json.loads(r.read())
        raw = (
            info.get("UpscaleModelLoader", {})
            .get("input", {})
            .get("required", {})
            .get("model_name", [])
        )
        # Parse options — could be ['COMBO', {options: [...]}] or [['a','b',...]]
        options = []
        if isinstance(raw, list) and len(raw) >= 1:
            first = raw[0]
            if isinstance(first, list):
                options = first
            elif isinstance(first, str) and len(raw) >= 2 and isinstance(raw[1], dict):
                # ['COMBO', {'options': [...]}]
                options = raw[1].get("options", [])
        if not options:
            return None
        # Pick the first match from our preference list
        for pref in PREFERRED_MODELS:
            if pref in options:
                return pref
        return options[0]  # fallback to whatever is first
    except Exception as e:
        print(f"  ⚠ Could not detect upscale models: {e}")
        return None


def _load_workflow_template() -> dict:
    """Load the panel_upscale.json workflow template."""
    wf_path = os.path.join(WORKFLOWS_DIR, "panel_upscale.json")
    with open(wf_path) as f:
        return json.load(f)


def _build_model_workflow(
    comfyui_filename: str,
    model_name: str,
    target_megapixels: float = 4.0,
    prefix: str = "upscaled",
) -> dict:
    """Build a ready-to-queue workflow from the template."""
    wf = _load_workflow_template()
    wf["1"]["inputs"]["image"] = comfyui_filename
    wf["2"]["inputs"]["model_name"] = model_name
    wf["4"]["inputs"]["megapixels"] = target_megapixels
    wf["5"]["inputs"]["filename_prefix"] = prefix
    return wf


def _megapixels_for_scale(image_path: str, scale: float) -> float:
    """Calculate target megapixels given source image and desired scale."""
    from PIL import Image

    with Image.open(image_path) as img:
        w, h = img.size
    target_pixels = w * h * (scale ** 2)
    return round(target_pixels / 1_000_000, 2)


# ---------------------------------------------------------------------------
# Upscale methods
# ---------------------------------------------------------------------------

def _upscale_simple(image_path: str, output_path: str, scale: float) -> str:
    """Pure PIL Lanczos upscale — always works, no GPU needed."""
    from PIL import Image

    img = Image.open(image_path)
    new_size = (int(img.width * scale), int(img.height * scale))
    img_up = img.resize(new_size, Image.LANCZOS)
    img_up.save(output_path, quality=95)
    return output_path


def _upscale_model(
    image_path: str,
    output_dir: str,
    scale: float = 2.0,
    model_name: str | None = None,
    timeout: int = 120,
) -> str:
    """Upscale via ComfyUI upscale model (best quality)."""
    import comfy_client  # type: ignore

    comfy_client.ensure_running()

    # Pick model
    if model_name is None:
        model_name = _detect_available_model()
    if model_name is None:
        raise RuntimeError(
            "No upscale model found in ComfyUI. Install one of: "
            "4x-UltraSharp.pth, RealESRGAN_x4plus.pth"
        )

    # Upload image
    basename = os.path.basename(image_path)
    comfyui_name = comfy_client.upload_image(image_path)
    print(f"  Uploaded {basename} → {comfyui_name}")

    # Calculate target megapixels from scale
    target_mp = _megapixels_for_scale(image_path, scale)
    prefix = os.path.splitext(basename)[0] + "_upscaled"

    # Build & queue workflow
    wf = _build_model_workflow(comfyui_name, model_name, target_mp, prefix)
    downloaded = comfy_client.generate_and_download(wf, output_dir, timeout=timeout)

    if not downloaded:
        raise RuntimeError("ComfyUI returned no images")
    return downloaded[0]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def upscale_panel(
    image_path: str,
    output_dir: str,
    scale: float = 2.0,
    method: str = "model",
    model_name: str | None = None,
    timeout: int = 120,
) -> str:
    """Upscale a single panel image.

    Args:
        image_path: Path to the source image.
        output_dir:  Directory for the upscaled result.
        scale:       Target scale factor (e.g. 2.0 = 2× resolution).
        method:      "model" | "simple" | "auto".
        model_name:  Override the upscale model (e.g. "4x-UltraSharp.pth").
        timeout:     ComfyUI timeout in seconds.

    Returns:
        Path to the upscaled image.
    """
    os.makedirs(output_dir, exist_ok=True)
    basename = os.path.basename(image_path)
    stem, ext = os.path.splitext(basename)

    if method == "simple":
        out_path = os.path.join(output_dir, f"{stem}_simple{ext}")
        return _upscale_simple(image_path, out_path, scale)

    if method == "model":
        return _upscale_model(image_path, output_dir, scale, model_name, timeout)

    if method == "auto":
        try:
            return _upscale_model(image_path, output_dir, scale, model_name, timeout)
        except Exception as e:
            print(f"  ⚠ Model upscale failed ({e}), falling back to simple")
            out_path = os.path.join(output_dir, f"{stem}_simple{ext}")
            return _upscale_simple(image_path, out_path, scale)

    raise ValueError(f"Unknown method: {method!r}. Use 'model', 'simple', or 'auto'.")


def upscale_all_panels(
    panel_paths: list[str],
    output_dir: str,
    scale: float = 2.0,
    method: str = "auto",
    model_name: str | None = None,
    timeout: int = 120,
) -> list[str]:
    """Upscale a list of panel images.

    Args:
        panel_paths: List of source image paths.
        output_dir:  Directory for upscaled results.
        scale:       Target scale factor.
        method:      "model" | "simple" | "auto".
        model_name:  Override upscale model name.
        timeout:     Per-image ComfyUI timeout.

    Returns:
        List of paths to upscaled images.
    """
    os.makedirs(output_dir, exist_ok=True)
    results = []
    for i, path in enumerate(panel_paths, 1):
        print(f"[{i}/{len(panel_paths)}] Upscaling {os.path.basename(path)} …")
        t0 = time.time()
        out = upscale_panel(path, output_dir, scale, method, model_name, timeout)
        elapsed = time.time() - t0
        size_kb = os.path.getsize(out) / 1024
        print(f"  → {os.path.basename(out)}  ({size_kb:.0f} KB, {elapsed:.1f}s)")
        results.append(out)
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_recommendations():
    """Print recommended upscale models for download."""
    print("\n📦 Recommended upscale models for ComfyUI:")
    print("   Place .pth files in: ComfyUI/models/upscale_models/\n")
    print("   1. 4x-UltraSharp.pth (best general-purpose)")
    print("      https://mega.nz/folder/qZRBmaIY#nIG8KyWFcGNTuPX10PjGFA")
    print("   2. RealESRGAN_x4plus.pth (good for photos & illustrations)")
    print("      https://github.com/xinntao/Real-ESRGAN/releases")
    print("   3. 4x_foolhardy_Remacri.pth (excellent for art/anime)")
    print("      https://openmodeldb.info/models/4x-Remacri")
    print("   4. 4x_NMKD-Superscale-SP_178000_G.pth (strong detail)")
    print("      https://openmodeldb.info/models/4x-NMKD-Superscale-SP")
    print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Upscale comic panels")
    parser.add_argument("input", help="Image file or directory of images")
    parser.add_argument("--scale", type=float, default=2.0, help="Scale factor (default: 2.0)")
    parser.add_argument("--method", default="auto", choices=["model", "simple", "auto"],
                        help="Upscale method (default: auto)")
    parser.add_argument("--model", default=None, help="Override upscale model name")
    parser.add_argument("--output", "-o", default=None, help="Output directory")
    parser.add_argument("--timeout", type=int, default=120, help="ComfyUI timeout per image")
    parser.add_argument("--info", action="store_true", help="Show model recommendations")
    args = parser.parse_args()

    if args.info:
        _print_recommendations()
        sys.exit(0)

    # Collect input images
    if os.path.isdir(args.input):
        paths = sorted(
            os.path.join(args.input, f)
            for f in os.listdir(args.input)
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
        )
    else:
        paths = [args.input]

    if not paths:
        print("No images found.")
        sys.exit(1)

    out_dir = args.output or os.path.join(os.path.dirname(paths[0]), "upscaled")

    print(f"🔍 Upscaling {len(paths)} image(s) @ {args.scale}× using '{args.method}' method")
    print(f"📁 Output: {out_dir}\n")

    t_start = time.time()
    results = upscale_all_panels(paths, out_dir, args.scale, args.method, args.model, args.timeout)
    total = time.time() - t_start

    print(f"\n✅ Done! {len(results)} image(s) upscaled in {total:.1f}s")
    for r in results:
        sz = os.path.getsize(r) / 1024
        print(f"   {r}  ({sz:.0f} KB)")

#!/usr/bin/env python3
"""
ComicMaster Inpaint Helper — Mask generation and inpainting via ComfyUI.

Provides:
    generate_hand_mask  — Create mask from MediaPipe hand landmarks
    generate_face_mask  — Create mask from face bounding box
    generate_region_mask — Create mask for arbitrary rectangular region
    run_inpaint         — Submit inpainting job to ComfyUI and retrieve result
    auto_inpaint_hands  — Full pipeline: detect → mask → inpaint → verify

Integration:
    Called by quality_gates.py QualityGateRunner for auto-repair workflow.
    Uses ComfyUI API via comfy_client (same as panel_generator.py).

Dependencies:
    Required: PIL/Pillow, numpy
    Optional: mediapipe (for precise landmark-based masks)
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# ---------------------------------------------------------------------------
# Path setup — match existing codebase pattern
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).parent
SKILL_DIR = SCRIPTS_DIR.parent
WORKFLOWS_DIR = SKILL_DIR / "workflows"

# Add comfyui skill scripts to path
COMFYUI_SCRIPTS = SKILL_DIR.parent / "comfyui" / "scripts"
sys.path.insert(0, str(COMFYUI_SCRIPTS))
sys.path.insert(0, str(SCRIPTS_DIR))

# Lazy imports to avoid startup failures if ComfyUI is offline
_comfy_client = None

def _ensure_comfy():
    """Lazy-load comfy_client."""
    global _comfy_client
    if _comfy_client is None:
        from comfy_client import (
            generate_and_download,
            ensure_running,
            upload_image,
            queue_prompt,
            wait_for_completion,
            get_output_images,
            download_image,
        )
        _comfy_client = {
            "generate_and_download": generate_and_download,
            "ensure_running": ensure_running,
            "upload_image": upload_image,
        }
    return _comfy_client


# ===================================================================
# Mask Generation
# ===================================================================

def generate_hand_mask(
    image: Image.Image | str,
    hand_landmarks: list[dict] | None = None,
    padding: int = 30,
    blur_radius: int = 8,
) -> Image.Image:
    """Generate a mask for hand regions in an image.

    Args:
        image: Original panel image (PIL Image or path).
        hand_landmarks: List of landmark dicts from HandQualityChecker
                        [{"x": float, "y": float, "z": float}, ...].
                        If None, auto-detect using MediaPipe.
        padding: Pixels to pad around the hand convex hull.
        blur_radius: Gaussian blur radius for mask edges.

    Returns:
        PIL Image (L mode) — white = region to inpaint, black = keep.
    """
    if isinstance(image, (str, Path)):
        image = Image.open(image).convert("RGB")

    w, h = image.size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)

    if hand_landmarks:
        # Use provided landmarks to create mask
        _draw_landmarks_mask(draw, hand_landmarks, w, h, padding)
    else:
        # Auto-detect hands using MediaPipe
        try:
            from quality_gates import HandQualityChecker
            checker = HandQualityChecker()
            result = checker.check(image)
            checker.close()

            if result.get("details") and isinstance(result["details"], list):
                for hand_detail in result["details"]:
                    landmarks = hand_detail.get("landmarks", [])
                    if landmarks:
                        _draw_landmarks_mask(draw, landmarks, w, h, padding)
        except Exception:
            # Fallback: no mask if detection fails
            pass

    # Smooth mask edges with Gaussian blur
    if blur_radius > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(blur_radius))

    return mask


def _draw_landmarks_mask(
    draw: ImageDraw.Draw,
    landmarks: list[dict],
    img_w: int,
    img_h: int,
    padding: int,
) -> None:
    """Draw a hand mask from landmark coordinates onto an ImageDraw canvas.

    Creates a convex hull of landmark points with padding, then fills it.
    """
    # Convert normalized landmarks to pixel coordinates
    points = []
    for lm in landmarks:
        px = int(lm["x"] * img_w)
        py = int(lm["y"] * img_h)
        points.append((px, py))

    if len(points) < 3:
        return

    # Compute convex hull-like bounding polygon
    # Simple approach: pad each point outward from centroid
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)

    padded_points = []
    for px, py in points:
        # Direction from centroid
        dx = px - cx
        dy = py - cy
        dist = math.sqrt(dx * dx + dy * dy) or 1
        # Pad outward
        padded_x = px + int(dx / dist * padding)
        padded_y = py + int(dy / dist * padding)
        # Clamp
        padded_x = max(0, min(img_w - 1, padded_x))
        padded_y = max(0, min(img_h - 1, padded_y))
        padded_points.append((padded_x, padded_y))

    # Sort points by angle from centroid for proper polygon
    def angle_from_center(p):
        return math.atan2(p[1] - cy, p[0] - cx)
    padded_points.sort(key=angle_from_center)

    draw.polygon(padded_points, fill=255)


def generate_face_mask(
    image: Image.Image | str,
    face_bbox: tuple[int, int, int, int] | None = None,
    padding: int = 20,
    blur_radius: int = 10,
    shape: str = "ellipse",
) -> Image.Image:
    """Generate a mask for a face region in an image.

    Args:
        image: Original panel image.
        face_bbox: Face bounding box (x1, y1, x2, y2) in pixels.
                   If None, auto-detect using MediaPipe.
        padding: Pixels to pad around the face bbox.
        blur_radius: Gaussian blur radius for mask edges.
        shape: "ellipse" or "rectangle" mask shape.

    Returns:
        PIL Image (L mode) — white = region to inpaint, black = keep.
    """
    if isinstance(image, (str, Path)):
        image = Image.open(image).convert("RGB")

    w, h = image.size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)

    if face_bbox is None:
        # Auto-detect face
        try:
            from quality_gates import FaceConsistencyChecker
            checker = FaceConsistencyChecker()
            faces = checker._extract_all_faces(image)
            checker.close()

            if faces:
                # Get bbox of the largest face
                # Approximate: we don't have exact bbox from the face extraction
                # Use center of image with detected face proportion
                largest = max(faces, key=lambda f: f.size[0] * f.size[1])
                fw, fh = largest.size
                # Estimate position (centered assumption for heuristic)
                cx = w // 2
                cy = h // 4  # Upper portion typical for faces
                face_bbox = (
                    max(0, cx - fw // 2 - padding),
                    max(0, cy - fh // 2 - padding),
                    min(w, cx + fw // 2 + padding),
                    min(h, cy + fh // 2 + padding),
                )
        except Exception:
            return mask

    if face_bbox is None:
        return mask

    # Apply padding
    x1 = max(0, face_bbox[0] - padding)
    y1 = max(0, face_bbox[1] - padding)
    x2 = min(w, face_bbox[2] + padding)
    y2 = min(h, face_bbox[3] + padding)

    if shape == "ellipse":
        draw.ellipse([x1, y1, x2, y2], fill=255)
    else:
        draw.rectangle([x1, y1, x2, y2], fill=255)

    # Smooth edges
    if blur_radius > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(blur_radius))

    return mask


def generate_region_mask(
    image_size: tuple[int, int],
    region: tuple[int, int, int, int],
    padding: int = 10,
    blur_radius: int = 6,
) -> Image.Image:
    """Generate a rectangular mask for a specific region.

    Args:
        image_size: (width, height) of the image.
        region: (x1, y1, x2, y2) region to mask.
        padding: Additional padding around the region.
        blur_radius: Gaussian blur for smooth edges.

    Returns:
        PIL Image (L mode) — white = inpaint region.
    """
    w, h = image_size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)

    x1 = max(0, region[0] - padding)
    y1 = max(0, region[1] - padding)
    x2 = min(w, region[2] + padding)
    y2 = min(h, region[3] + padding)

    draw.rectangle([x1, y1, x2, y2], fill=255)

    if blur_radius > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(blur_radius))

    return mask


# ===================================================================
# Inpainting via ComfyUI
# ===================================================================

def build_inpaint_workflow(
    original_filename: str,
    mask_filename: str,
    prompt: str,
    negative_prompt: str | None = None,
    preset_config: dict | None = None,
    denoise: float = 0.70,
    seed: int = -1,
    prefix: str = "inpaint",
) -> dict:
    """Build a ComfyUI inpainting workflow.

    Based on the panel_inpaint.json template but dynamically configured.

    Args:
        original_filename: ComfyUI filename of the original panel image.
        mask_filename: ComfyUI filename of the mask image.
        prompt: Positive prompt (same as original panel).
        negative_prompt: Negative prompt.
        preset_config: Model/sampler configuration dict.
        denoise: Denoising strength (0.65-0.75 recommended).
        seed: Random seed (-1 for random).
        prefix: Filename prefix for saved results.

    Returns:
        ComfyUI workflow dict ready for queue_prompt().
    """
    if seed < 0:
        seed = random.randint(0, 2**32 - 1)

    if preset_config is None:
        preset_config = {
            "model": "dreamshaperXL_turboDPMSDE.safetensors",
            "steps": 20,
            "cfg": 7.0,
            "sampler": "dpmpp_2m",
            "scheduler": "karras",
        }

    if negative_prompt is None:
        negative_prompt = (
            "bad quality, worst quality, low quality, blurry, deformed, "
            "disfigured, mutation, extra limbs, extra fingers, "
            "watermark, text, words, letters"
        )

    workflow = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": preset_config.get("steps", 20),
                "cfg": preset_config.get("cfg", 7.0),
                "sampler_name": preset_config.get("sampler", "dpmpp_2m"),
                "scheduler": preset_config.get("scheduler", "karras"),
                "denoise": denoise,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["15", 0],
            },
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": preset_config.get("model",
                    "dreamshaperXL_turboDPMSDE.safetensors"),
            },
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": prompt,
                "clip": ["4", 1],
            },
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_prompt,
                "clip": ["4", 1],
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["3", 0],
                "vae": ["4", 2],
            },
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": prefix,
                "images": ["8", 0],
            },
        },
        # Load original panel
        "10": {
            "class_type": "LoadImage",
            "inputs": {
                "image": original_filename,
            },
        },
        # Load mask
        "11": {
            "class_type": "LoadImage",
            "inputs": {
                "image": mask_filename,
            },
        },
        # Convert mask image to mask tensor
        "12": {
            "class_type": "ImageToMask",
            "inputs": {
                "image": ["11", 0],
                "channel": "red",
            },
        },
        # Grow mask slightly for smooth blending
        "13": {
            "class_type": "GrowMask",
            "inputs": {
                "mask": ["12", 0],
                "expand": 6,
                "tapered_corners": True,
            },
        },
        # VAE encode with inpaint mask
        "15": {
            "class_type": "VAEEncodeForInpaint",
            "inputs": {
                "pixels": ["10", 0],
                "vae": ["4", 2],
                "mask": ["13", 0],
                "grow_mask_by": 8,
            },
        },
    }

    return workflow


def run_inpaint(
    image_path: str,
    mask_path: str,
    prompt: str,
    output_dir: str | None = None,
    negative_prompt: str | None = None,
    preset_config: dict | None = None,
    denoise: float = 0.70,
    seed: int = -1,
    timeout: int = 300,
) -> dict:
    """Run inpainting via ComfyUI.

    Full pipeline:
    1. Upload original image and mask to ComfyUI
    2. Build inpaint workflow
    3. Queue and wait for result
    4. Download result

    Args:
        image_path: Local path to original panel image.
        mask_path: Local path to mask image (white = inpaint region).
        prompt: Positive prompt for the inpaint region.
        output_dir: Directory to save result (defaults to same as image_path).
        negative_prompt: Negative prompt.
        preset_config: Model/sampler configuration.
        denoise: Denoising strength.
        seed: Random seed.
        timeout: ComfyUI timeout in seconds.

    Returns:
        {
            "path": str,       # Path to the inpainted image
            "seed": int,
            "duration_s": float,
            "denoise": float,
        }
    """
    comfy = _ensure_comfy()

    if output_dir is None:
        output_dir = str(Path(image_path).parent)

    os.makedirs(output_dir, exist_ok=True)

    # Ensure ComfyUI is running
    comfy["ensure_running"]()

    # Upload images to ComfyUI
    print(f"  📤 Uploading original panel...")
    original_filename = comfy["upload_image"](image_path)

    print(f"  📤 Uploading mask...")
    mask_filename = comfy["upload_image"](mask_path)

    # Build workflow
    panel_name = Path(image_path).stem
    prefix = f"inpaint_{panel_name}"

    workflow = build_inpaint_workflow(
        original_filename=original_filename,
        mask_filename=mask_filename,
        prompt=prompt,
        negative_prompt=negative_prompt,
        preset_config=preset_config,
        denoise=denoise,
        seed=seed if seed >= 0 else random.randint(0, 2**32 - 1),
        prefix=prefix,
    )

    # Generate
    start = time.time()
    paths = comfy["generate_and_download"](workflow, output_dir, timeout=timeout)
    duration = time.time() - start

    if not paths:
        raise RuntimeError(f"Inpainting failed — no output generated")

    return {
        "path": paths[0],
        "seed": seed,
        "duration_s": round(duration, 1),
        "denoise": denoise,
    }


def auto_inpaint_hands(
    image_path: str,
    prompt: str,
    output_dir: str | None = None,
    preset_config: dict | None = None,
    denoise: float = 0.70,
    max_attempts: int = 2,
    quality_threshold: float = 0.5,
) -> dict:
    """Full auto-inpaint pipeline for hand issues.

    1. Run hand quality check
    2. If issues found, generate hand mask
    3. Inpaint hand region
    4. Re-check quality
    5. Repeat if still failing (up to max_attempts)

    Args:
        image_path: Path to the panel image.
        prompt: Original generation prompt.
        output_dir: Output directory.
        preset_config: Model configuration.
        denoise: Denoising strength for inpainting.
        max_attempts: Maximum inpaint attempts.
        quality_threshold: Minimum hand confidence to accept.

    Returns:
        {
            "improved": bool,
            "attempts": int,
            "original_confidence": float,
            "final_confidence": float,
            "result_path": str,
        }
    """
    from quality_gates import HandQualityChecker

    if output_dir is None:
        output_dir = str(Path(image_path).parent)

    checker = HandQualityChecker()
    current_path = image_path

    # Initial check
    initial_check = checker.check(current_path)
    original_confidence = initial_check["confidence"]

    if initial_check["pass"]:
        checker.close()
        return {
            "improved": False,
            "attempts": 0,
            "original_confidence": original_confidence,
            "final_confidence": original_confidence,
            "result_path": current_path,
        }

    print(f"  🔧 Hand issues detected (confidence={original_confidence:.3f}), attempting inpaint...")

    best_confidence = original_confidence
    best_path = current_path

    for attempt in range(1, max_attempts + 1):
        try:
            # Generate hand mask
            hand_landmarks = None
            if initial_check.get("details") and isinstance(initial_check["details"], list):
                for detail in initial_check["details"]:
                    if detail.get("finger_issues") and detail.get("landmarks"):
                        hand_landmarks = detail["landmarks"]
                        break

            mask = generate_hand_mask(current_path, hand_landmarks)

            # Check if mask has any white pixels
            mask_arr = np.array(mask)
            if mask_arr.max() < 10:
                print(f"    Attempt {attempt}: Empty mask, skipping")
                continue

            # Save mask temporarily
            mask_path = os.path.join(output_dir, f"_inpaint_mask_{attempt}.png")
            mask.save(mask_path)

            # Run inpaint
            result = run_inpaint(
                image_path=current_path,
                mask_path=mask_path,
                prompt=prompt,
                output_dir=output_dir,
                preset_config=preset_config,
                denoise=denoise,
            )

            # Re-check quality
            recheck = checker.check(result["path"])
            print(f"    Attempt {attempt}: confidence {recheck['confidence']:.3f} "
                  f"(was {best_confidence:.3f})")

            if recheck["confidence"] > best_confidence:
                best_confidence = recheck["confidence"]
                best_path = result["path"]

            if recheck["pass"]:
                break

            # Use inpainted image as input for next attempt
            current_path = result["path"]

            # Clean up temporary mask
            try:
                os.remove(mask_path)
            except OSError:
                pass

        except Exception as e:
            print(f"    Attempt {attempt} failed: {e}")

    checker.close()

    return {
        "improved": best_confidence > original_confidence,
        "attempts": attempt if 'attempt' in dir() else 0,
        "original_confidence": round(original_confidence, 3),
        "final_confidence": round(best_confidence, 3),
        "result_path": best_path,
    }


# ===================================================================
# CLI
# ===================================================================

def main():
    """CLI entry point for inpainting."""
    import argparse

    parser = argparse.ArgumentParser(description="ComicMaster Inpaint Helper")
    subparsers = parser.add_subparsers(dest="command")

    # Mask generation
    mask_parser = subparsers.add_parser("mask", help="Generate inpaint mask")
    mask_parser.add_argument("image", help="Panel image path")
    mask_parser.add_argument("--type", choices=["hand", "face", "region"],
                             default="hand", help="Mask type")
    mask_parser.add_argument("--output", "-o", default=None, help="Output mask path")
    mask_parser.add_argument("--padding", type=int, default=30)
    mask_parser.add_argument("--blur", type=int, default=8)

    # Inpainting
    inpaint_parser = subparsers.add_parser("inpaint", help="Run inpainting")
    inpaint_parser.add_argument("image", help="Original panel image")
    inpaint_parser.add_argument("mask", help="Mask image")
    inpaint_parser.add_argument("--prompt", "-p", required=True, help="Inpaint prompt")
    inpaint_parser.add_argument("--output", "-o", default=None, help="Output directory")
    inpaint_parser.add_argument("--denoise", type=float, default=0.70)
    inpaint_parser.add_argument("--seed", type=int, default=-1)

    # Auto inpaint
    auto_parser = subparsers.add_parser("auto", help="Auto-detect and inpaint hands")
    auto_parser.add_argument("image", help="Panel image path")
    auto_parser.add_argument("--prompt", "-p", required=True, help="Original prompt")
    auto_parser.add_argument("--output", "-o", default=None)
    auto_parser.add_argument("--denoise", type=float, default=0.70)
    auto_parser.add_argument("--attempts", type=int, default=2)

    args = parser.parse_args()

    if args.command == "mask":
        img = Image.open(args.image).convert("RGB")

        if args.type == "hand":
            mask = generate_hand_mask(img, padding=args.padding, blur_radius=args.blur)
        elif args.type == "face":
            mask = generate_face_mask(img, padding=args.padding, blur_radius=args.blur)
        else:
            # Full image mask for testing
            mask = generate_region_mask(
                img.size, (0, 0, img.size[0], img.size[1]),
                padding=0, blur_radius=args.blur,
            )

        out_path = args.output or args.image.replace(".png", "_mask.png")
        mask.save(out_path)
        print(f"✅ Mask saved: {out_path}")

    elif args.command == "inpaint":
        result = run_inpaint(
            image_path=args.image,
            mask_path=args.mask,
            prompt=args.prompt,
            output_dir=args.output,
            denoise=args.denoise,
            seed=args.seed,
        )
        print(f"✅ Inpainted: {result['path']} ({result['duration_s']}s)")

    elif args.command == "auto":
        result = auto_inpaint_hands(
            image_path=args.image,
            prompt=args.prompt,
            output_dir=args.output,
            denoise=args.denoise,
            max_attempts=args.attempts,
        )
        if result["improved"]:
            print(f"✅ Improved: {result['original_confidence']:.3f} → "
                  f"{result['final_confidence']:.3f}")
            print(f"   Result: {result['result_path']}")
        else:
            print(f"ℹ️  No improvement (confidence: {result['final_confidence']:.3f})")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

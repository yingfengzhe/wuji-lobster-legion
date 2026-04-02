#!/usr/bin/env python3
"""
Test IPAdapter character consistency for ComicMaster.

Generates a character reference, uploads it to ComfyUI, then generates
2 panels that use IPAdapter to maintain character consistency.

Output goes to: /home/mcmuff/clawd/output/comicmaster/test_ipadapter/
"""

import json
import os
import sys
import time
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "comfyui" / "scripts"))

from panel_generator import (
    generate_character_ref,
    generate_panel,
    IPADAPTER_WEIGHTS,
)
from comfy_client import ensure_running, upload_image

OUTPUT_DIR = "/home/mcmuff/clawd/output/comicmaster/test_ipadapter"
PRESET = "dreamshaperXL"
STYLE = "western"

# --- Test Character ---
TEST_CHARACTER = {
    "id": "elena",
    "name": "Elena Voss",
    "visual_description": (
        "young woman in her late 20s, short spiky red hair, bright green eyes, "
        "athletic build, wearing a dark leather jacket over a white tank top, "
        "black combat boots, a small scar on her left cheek"
    ),
}

# --- Test Panels ---
TEST_PANELS = [
    {
        "id": "test_panel_01",
        "shot_type": "medium",
        "camera_angle": "eye_level",
        "action": "Elena walks through a rain-soaked alley at night",
        "scene": "dark urban alley, wet cobblestone ground, neon reflections",
        "background_detail": "distant city lights, steam rising from grates",
        "characters_present": ["elena"],
        "character_emotions": "determined",
        "character_poses": "walking forward confidently, hands in jacket pockets",
        "lighting": "neon",
        "mood": "mysterious",
    },
    {
        "id": "test_panel_02",
        "shot_type": "close_up",
        "camera_angle": "low_angle",
        "action": "Elena looks up with a fierce expression",
        "scene": "against a graffiti-covered brick wall",
        "background_detail": "colorful graffiti art behind her",
        "characters_present": ["elena"],
        "character_emotions": "determined",
        "character_poses": "looking up, jaw set, eyes narrowed",
        "lighting": "dramatic",
        "mood": "intense",
    },
]


def run_test():
    """Run the full IPAdapter test pipeline."""
    print("=" * 60)
    print("🧪 IPAdapter Character Consistency Test")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    refs_dir = os.path.join(OUTPUT_DIR, "refs")
    panels_dir = os.path.join(OUTPUT_DIR, "panels")
    os.makedirs(refs_dir, exist_ok=True)
    os.makedirs(panels_dir, exist_ok=True)

    # Ensure ComfyUI is running
    print("\n📡 Checking ComfyUI...")
    ensure_running()
    print("  ✅ ComfyUI is running")

    # --- Step 1: Generate character reference ---
    print("\n" + "-" * 40)
    print("📸 Step 1: Generate character reference")
    print("-" * 40)

    start = time.time()
    ref_result = generate_character_ref(
        character=TEST_CHARACTER,
        style=STYLE,
        preset_name=PRESET,
        output_dir=refs_dir,
        width=1024,
        height=1024,
    )
    print(f"  ✅ Reference generated: {ref_result['path']}")
    print(f"     Seed: {ref_result['seed']}")
    print(f"     ComfyUI filename: {ref_result['comfyui_filename']}")
    print(f"     Duration: {ref_result['duration_s']}s")

    # Build char_refs dict for panel generation
    char_refs = {
        TEST_CHARACTER["id"]: ref_result,
    }

    # --- Step 2: Generate panels WITH IPAdapter ---
    print("\n" + "-" * 40)
    print("🎨 Step 2: Generate panels with IPAdapter")
    print("-" * 40)

    panel_results = []
    characters = [TEST_CHARACTER]

    for i, panel in enumerate(TEST_PANELS):
        print(f"\n  Panel {i + 1}/{len(TEST_PANELS)}: {panel['id']}")
        shot_type = panel.get("shot_type", "medium")
        weight = IPADAPTER_WEIGHTS.get(shot_type, 0.65)
        print(f"    Shot type: {shot_type} → IPAdapter weight: {weight}")

        result = generate_panel(
            panel=panel,
            characters=characters,
            style=STYLE,
            preset_name=PRESET,
            output_dir=panels_dir,
            char_refs=char_refs,
            width=768,
            height=768,
        )
        panel_results.append(result)
        print(f"    ✅ Generated: {result['path']}")
        print(f"       IPAdapter used: {result.get('ipadapter', False)}")
        print(f"       Duration: {result['duration_s']}s")

    total_time = time.time() - start

    # --- Summary ---
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    print(f"  Character ref: {ref_result['path']}")
    for i, r in enumerate(panel_results):
        print(f"  Panel {i + 1}: {r['path']} (IPAdapter: {r.get('ipadapter')}, {r['duration_s']}s)")
    print(f"\n  Total time: {total_time:.1f}s")
    print(f"  Output dir: {OUTPUT_DIR}")

    # Save test metadata
    metadata = {
        "test": "ipadapter_character_consistency",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "preset": PRESET,
        "style": STYLE,
        "character": TEST_CHARACTER,
        "character_ref": {
            "path": ref_result["path"],
            "seed": ref_result["seed"],
            "comfyui_filename": ref_result["comfyui_filename"],
            "prompt": ref_result["prompt"],
            "duration_s": ref_result["duration_s"],
        },
        "panels": [
            {
                "panel_id": TEST_PANELS[i]["id"],
                "shot_type": TEST_PANELS[i]["shot_type"],
                "ipadapter_weight": IPADAPTER_WEIGHTS.get(
                    TEST_PANELS[i]["shot_type"], 0.65
                ),
                "path": r["path"],
                "seed": r["seed"],
                "ipadapter": r.get("ipadapter", False),
                "duration_s": r["duration_s"],
            }
            for i, r in enumerate(panel_results)
        ],
        "total_time_s": round(total_time, 1),
    }

    meta_path = os.path.join(OUTPUT_DIR, "test_metadata.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"\n  Metadata saved: {meta_path}")
    print("\n✅ Test complete!")

    return metadata


if __name__ == "__main__":
    run_test()

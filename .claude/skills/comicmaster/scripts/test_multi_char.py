#!/usr/bin/env python3
"""
Test multi-character IPAdapter support for ComicMaster.

Generates reference images for 2 characters, then generates a panel with
both characters present using chained IPAdapterAdvanced nodes.

Output goes to: /home/mcmuff/clawd/output/comicmaster/test_multi_char/
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
    build_sdxl_multi_ipadapter_workflow,
    IPADAPTER_WEIGHTS,
)
from comfy_client import ensure_running

OUTPUT_DIR = "/home/mcmuff/clawd/output/comicmaster/test_multi_char"
PRESET = "dreamshaperXL"
STYLE = "western"

# --- Test Characters ---

CHARACTER_A = {
    "id": "maya",
    "name": "Maya Chen",
    "visual_description": (
        "young woman, blonde hair, blue eyes, red leather jacket, "
        "white t-shirt underneath, slim build, confident posture"
    ),
}

CHARACTER_B = {
    "id": "arthur",
    "name": "Arthur Blackwood",
    "visual_description": (
        "older man, grey beard, glasses, brown tweed suit, "
        "white dress shirt, tall and slightly hunched, wise expression"
    ),
}

CHARACTERS = [CHARACTER_A, CHARACTER_B]

# --- Test Panel (both characters) ---

TEST_PANEL = {
    "id": "multi_char_01",
    "shot_type": "medium",
    "camera_angle": "eye_level",
    "action": "two people arguing in a coffee shop",
    "scene": "cozy coffee shop interior, wooden tables, warm ambient light",
    "background_detail": "coffee cups on the table, bookshelves in background, other patrons blurred",
    "characters_present": ["maya", "arthur"],
    "character_emotions": "angry, frustrated",
    "character_poses": "facing each other, gesturing with hands, leaning forward",
    "lighting": "natural",
    "mood": "tense",
}


def run_test():
    """Run the multi-character IPAdapter test pipeline."""
    print("=" * 60)
    print("🧪 Multi-Character IPAdapter Test")
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

    total_start = time.time()

    # --- Step 1: Generate character references ---
    print("\n" + "-" * 40)
    print("📸 Step 1: Generate character references")
    print("-" * 40)

    char_refs = {}

    for char in CHARACTERS:
        print(f"\n  Generating ref for: {char['name']} ({char['id']})")
        ref_result = generate_character_ref(
            character=char,
            style=STYLE,
            preset_name=PRESET,
            output_dir=refs_dir,
            width=1024,
            height=1024,
        )
        char_refs[char["id"]] = ref_result
        print(f"    ✅ Reference: {ref_result['path']}")
        print(f"       ComfyUI filename: {ref_result['comfyui_filename']}")
        print(f"       Duration: {ref_result['duration_s']}s")

    # --- Step 2: Generate multi-character panel ---
    print("\n" + "-" * 40)
    print("🎨 Step 2: Generate panel with both characters")
    print("-" * 40)

    print(f"\n  Panel: {TEST_PANEL['id']}")
    print(f"  Characters: {', '.join(TEST_PANEL['characters_present'])}")
    print(f"  Shot type: {TEST_PANEL['shot_type']}")

    result = generate_panel(
        panel=TEST_PANEL,
        characters=CHARACTERS,
        style=STYLE,
        preset_name=PRESET,
        output_dir=panels_dir,
        char_refs=char_refs,
        width=768,
        height=768,
    )

    print(f"\n  ✅ Generated: {result['path']}")
    print(f"     IPAdapter: {result.get('ipadapter', False)}")
    print(f"     Multi-IPAdapter: {result.get('multi_ipadapter', False)}")
    if result.get("char_refs_used"):
        for cr in result["char_refs_used"]:
            print(f"       → {cr['char_id']}: weight={cr['weight']}")
    print(f"     Duration: {result['duration_s']}s")

    total_time = time.time() - total_start

    # --- Summary ---
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    for char_id, ref in char_refs.items():
        print(f"  Ref [{char_id}]: {ref['path']}")
    print(f"  Panel: {result['path']}")
    print(f"  Multi-IPAdapter: {result.get('multi_ipadapter', False)}")
    print(f"  Total time: {total_time:.1f}s")
    print(f"  Output dir: {OUTPUT_DIR}")

    # Save test metadata
    metadata = {
        "test": "multi_character_ipadapter",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "preset": PRESET,
        "style": STYLE,
        "characters": [
            {
                "id": c["id"],
                "name": c["name"],
                "ref_path": char_refs[c["id"]]["path"],
                "ref_comfyui_filename": char_refs[c["id"]]["comfyui_filename"],
                "ref_seed": char_refs[c["id"]]["seed"],
                "ref_duration_s": char_refs[c["id"]]["duration_s"],
            }
            for c in CHARACTERS
        ],
        "panel": {
            "id": TEST_PANEL["id"],
            "characters_present": TEST_PANEL["characters_present"],
            "shot_type": TEST_PANEL["shot_type"],
            "path": result["path"],
            "seed": result["seed"],
            "ipadapter": result.get("ipadapter", False),
            "multi_ipadapter": result.get("multi_ipadapter", False),
            "char_refs_used": result.get("char_refs_used", []),
            "duration_s": result["duration_s"],
            "prompt": result["prompt"],
        },
        "total_time_s": round(total_time, 1),
    }

    meta_path = os.path.join(OUTPUT_DIR, "test_metadata.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"\n  Metadata saved: {meta_path}")
    print("\n✅ Multi-character test complete!")

    return metadata


if __name__ == "__main__":
    run_test()

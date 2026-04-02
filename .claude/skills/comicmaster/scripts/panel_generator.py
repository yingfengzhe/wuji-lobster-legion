#!/usr/bin/env python3
"""
Panel Generator for ComicMaster.
Generates individual comic panels via ComfyUI using the existing comfyui skill infrastructure.
Supports prompt-only generation and IPAdapter-based character consistency.
"""

import json
import os
import random
import sys
import time
from pathlib import Path

# Add comfyui skill scripts to path
COMFYUI_SCRIPTS = Path(__file__).parent.parent.parent / "comfyui" / "scripts"
sys.path.insert(0, str(COMFYUI_SCRIPTS))
from comfy_client import generate_and_download, ensure_running, upload_image

# Add our own scripts
sys.path.insert(0, str(Path(__file__).parent))
from batch_optimizer import (
    optimize_panel_order,
    estimate_batch_time,
    generate_batch_report,
    count_unoptimized_switches,
)

COMFYUI_PRESETS = Path(__file__).parent.parent.parent / "comfyui" / "presets.json"

# --- LoRA Style Configuration ---

# Maps style name → list of LoRA configs to chain.
# Each entry: {"filename": "xxx.safetensors", "strength_model": float, "strength_clip": float}
# Empty list = no LoRA (base model only).
STYLE_LORAS = {
    "western": [
        # Bold detail enhancement for classic comic look
        {"filename": "xl_more_art-full_v1.safetensors", "strength_model": 0.45, "strength_clip": 0.45},
    ],
    "manga": [
        # No dedicated manga LoRA available — rely on prompt + model
        # Recommended: "animeScreencap_xl.safetensors" or "anime_xl_v2.safetensors"
    ],
    "cartoon": [
        {"filename": "SDXLFaeTastic2400.safetensors", "strength_model": 0.55, "strength_clip": 0.5},
    ],
    "noir": [
        # Offset noise LoRA pushes contrast/shadows — great for noir
        {"filename": "sd_xl_offset_example-lora_1.0.safetensors", "strength_model": 0.6, "strength_clip": 0.6},
    ],
    "realistic": [
        {"filename": "clarity_3.safetensors", "strength_model": 0.4, "strength_clip": 0.4},
        {"filename": "add_detail.safetensors", "strength_model": 0.5, "strength_clip": 0.4},
    ],
    # --- Bonus styles ---
    "neon": [
        {"filename": "glowneon_xl_v1.safetensors", "strength_model": 0.6, "strength_clip": 0.5},
    ],
    "artistic": [
        {"filename": "xl_more_art-full_v1.safetensors", "strength_model": 0.6, "strength_clip": 0.55},
        {"filename": "perfection style.safetensors", "strength_model": 0.35, "strength_clip": 0.3},
    ],
}


def get_style_loras(style: str) -> list[dict]:
    """Look up LoRA configs for a given style name.

    Returns a (possibly empty) list of LoRA config dicts.
    """
    return STYLE_LORAS.get(style, [])


def _insert_lora_nodes(workflow: dict, loras: list[dict],
                       checkpoint_node: str = "4") -> dict:
    """Insert LoraLoader nodes into *workflow*, chaining from *checkpoint_node*.

    Each LoRA node consumes model+clip from the previous node and provides
    them to the next.  After insertion every downstream reference to the
    checkpoint's model (slot 0) and clip (slot 1) outputs is rewired to point
    at the **last** LoRA node instead.

    Node IDs are assigned starting from "900" upward to avoid collisions with
    the existing graph.

    Returns the (mutated) workflow dict for convenience.
    """
    if not loras:
        return workflow

    prev_node = checkpoint_node
    lora_node_ids: list[str] = []

    for i, lora_cfg in enumerate(loras):
        node_id = str(900 + i)
        lora_node_ids.append(node_id)
        workflow[node_id] = {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": lora_cfg["filename"],
                "strength_model": lora_cfg.get("strength_model", 0.7),
                "strength_clip": lora_cfg.get("strength_clip", 0.7),
                "model": [prev_node, 0],
                "clip": [prev_node, 1],
            },
        }
        prev_node = node_id

    # Rewire: any node (other than the LoRA chain itself) that referenced
    # checkpoint_node outputs 0 (model) or 1 (clip) should now point at
    # the last LoRA node.
    last_lora = lora_node_ids[-1]
    skip = set(lora_node_ids)

    for nid, node in workflow.items():
        if nid in skip or nid == checkpoint_node:
            continue
        inputs = node.get("inputs", {})
        for key, val in inputs.items():
            if isinstance(val, list) and len(val) == 2 and val[0] == checkpoint_node:
                if val[1] in (0, 1):
                    inputs[key] = [last_lora, val[1]]

    return workflow


# --- Prompt Templates ---

STYLE_TAGS = {
    "western": "comic book art style, bold outlines, vibrant colors, dynamic composition, western comic",
    "manga": "manga art style, clean lines, screentone shading, black and white, manga panel",
    "cartoon": "cartoon art style, bright colors, exaggerated proportions, fun, animated style",
    "realistic": "semi-realistic illustration, detailed shading, cinematic lighting",
    "noir": "noir comic art style, high contrast, dramatic shadows, black and white, film noir",
}

SHOT_TYPE_TAGS = {
    "extreme_wide": "extreme wide shot, full environment visible, tiny figures",
    "wide": "wide shot, full body visible, environment context",
    "medium": "medium shot, waist-up framing",
    "medium_close": "medium close-up, chest-up framing",
    "close_up": "close-up shot, face and shoulders",
    "extreme_close": "extreme close-up, eyes or detail focus",
}

CAMERA_ANGLE_TAGS = {
    "eye_level": "eye level view, straight on perspective",
    "low_angle": "low angle view, looking up at subject, heroic perspective",
    "high_angle": "high angle view, looking down, bird's eye perspective",
    "dutch_angle": "dutch angle, tilted camera, dynamic perspective",
    "birds_eye": "top-down view, bird's eye, overhead shot",
    "worms_eye": "worm's eye view, extreme low angle, looking straight up",
}

EMOTION_TAGS = {
    "happy": "happy expression, smiling",
    "sad": "sad expression, downcast eyes",
    "angry": "angry expression, furrowed brows, clenched jaw",
    "surprised": "surprised expression, wide eyes, open mouth",
    "scared": "fearful expression, wide eyes, trembling",
    "determined": "determined expression, focused gaze, set jaw",
    "tired": "exhausted expression, droopy eyes, slouched posture",
    "confused": "confused expression, raised eyebrow, puzzled look",
    "neutral": "neutral expression",
}

LIGHTING_TAGS = {
    "natural": "natural lighting, soft daylight",
    "dramatic": "dramatic lighting, strong shadows, chiaroscuro",
    "noir": "noir lighting, single light source, deep shadows, high contrast",
    "soft": "soft diffused lighting, gentle shadows",
    "sunset": "warm sunset lighting, golden hour, orange tones",
    "moonlight": "cool moonlight, blue tones, night lighting",
    "neon": "neon lighting, colorful glow, cyberpunk atmosphere",
    "studio": "studio lighting, clean, even illumination",
}

NEGATIVE_PROMPT = (
    "bad quality, worst quality, low quality, blurry, deformed, disfigured, "
    "mutation, extra limbs, watermark, text, words, letters, lettering, "
    "typography, logo, signature, title, subtitle, caption, dialogue, "
    "speech bubble, word balloon, alphabet, writing, inscription, label, "
    "jpeg artifacts, poorly drawn, amateur, ugly, duplicate, "
    "centered composition, symmetrical framing, passport photo, static pose, "
    "fashion photography, straight-on camera, centered subject, stock photo"
)

# --- Illustrious XL / NoobAI-XL Negative Prompts ---

ILLUSTRIOUS_NEGATIVE_PROMPT = (
    "worst quality, low quality, normal quality, lowres, bad anatomy, "
    "bad hands, extra fingers, fewer fingers, missing fingers, extra digit, "
    "extra limbs, malformed limbs, mutated hands, fused fingers, "
    "too many fingers, text, watermark, signature, username, logo, "
    "blurry, jpeg artifacts, cropped, out of frame, duplicate, error, "
    "ugly, deformed, disfigured, mutation, poorly drawn, amateur"
)

NOOBAI_NEGATIVE_PROMPT = (
    "nsfw, worst quality, old, early, low quality, lowres, "
    "signature, username, logo, bad hands, mutated hands, "
    "text, watermark, blurry, jpeg artifacts, cropped, "
    "duplicate, error, ugly, deformed, extra limbs, extra fingers"
)

# Presets that use Danbooru tag-style prompting
ILLUSTRIOUS_PRESETS = {"illustriousXL", "noobaiXL"}

# --- Illustrious XL Danbooru Tag Mappings ---

ILLUSTRIOUS_SHOT_TAGS = {
    "extreme_wide": "scenery, wide shot, landscape, panorama",
    "wide": "wide shot, full body",
    "medium": "cowboy shot",
    "medium_close": "upper body",
    "close_up": "close-up, portrait, face focus",
    "extreme_close": "extreme close-up, eyes focus",
}

ILLUSTRIOUS_ANGLE_TAGS = {
    "eye_level": "straight-on",
    "low_angle": "from below",
    "high_angle": "from above",
    "dutch_angle": "dutch angle, tilted frame",
    "birds_eye": "overhead shot, bird's-eye view",
    "worms_eye": "from below, worm's-eye view",
}

ILLUSTRIOUS_STYLE_TAGS = {
    "western": "comic, western comic, comic book style, bold outlines, cel shading, vibrant colors",
    "manga": "manga, monochrome, greyscale, screentone, ink drawing, clean lines",
    "cartoon": "cartoon, bright colors, cel shading, animated style, bold outlines",
    "realistic": "illustration, detailed, realistic, sharp focus, cinematic lighting",
    "noir": "film noir, monochrome, high contrast, chiaroscuro, dramatic shadows",
}

ILLUSTRIOUS_EMOTION_TAGS = {
    "happy": "smile, happy, :d",
    "sad": "sad, crying, tears, downcast eyes",
    "angry": "angry, frown, clenched teeth",
    "surprised": "surprised, :o, open mouth, wide-eyed",
    "scared": "scared, trembling, frightened, wide eyes",
    "determined": "serious, determined, intense, focused",
    "tired": "tired, exhausted, droopy eyes, bags under eyes",
    "confused": "confused, raised eyebrow, head tilt, ?",
    "neutral": "neutral expression, calm",
}

ILLUSTRIOUS_LIGHTING_TAGS = {
    "natural": "natural lighting, outdoors, daylight",
    "dramatic": "dramatic lighting, strong shadows, rim light",
    "noir": "film noir, single light source, deep shadows, high contrast",
    "soft": "soft lighting, diffused light, gentle shadows",
    "sunset": "sunset, golden hour, warm lighting, orange sky",
    "moonlight": "moonlight, night, blue tones, dim lighting",
    "neon": "neon lights, cyberpunk, colorful lighting, glow",
    "studio": "studio lighting, even lighting, clean",
}

# --- IPAdapter Configuration ---

IPADAPTER_WEIGHTS = {
    "extreme_wide": 0.50,
    "wide": 0.55,
    "medium": 0.75,
    "medium_close": 0.85,
    "close_up": 0.92,
    "extreme_close": 0.95,
}

# Extra weight boost applied when panel is a face-focused shot.
# Added on top of the base IPADAPTER_WEIGHTS value (clamped to max 1.0).
FACE_WEIGHT_BOOST = 0.05

# Shot types that should use PLUS FACE preset instead of PLUS
FACE_SHOT_TYPES = {"close_up", "extreme_close", "medium_close"}

CHARACTER_REF_PROMPT_TEMPLATE = (
    "character design sheet, {visual_description}, front view, standing pose, "
    "full body, simple white background, {style} art style, clean lines, "
    "high detail, professional character design, neutral expression, "
    "studio lighting, centered composition, no text, no letters, no words"
)

# Per-view prompt templates for multi-angle reference sheets
CHARACTER_REF_VIEW_PROMPTS = {
    "front": (
        "character reference, {visual_description}, front view, facing viewer, "
        "standing pose, upper body and face clearly visible, simple white background, "
        "{style} art style, clean lines, high detail, professional character design, "
        "neutral expression, studio lighting, centered composition, no text, no letters, no words"
    ),
    "three_quarter": (
        "character reference, {visual_description}, three-quarter view, 3/4 angle, "
        "slightly turned, standing pose, upper body visible, simple white background, "
        "{style} art style, clean lines, high detail, professional character design, "
        "neutral expression, studio lighting, centered composition, no text, no letters, no words"
    ),
    "profile": (
        "character reference, {visual_description}, side view, profile view, "
        "facing left, standing pose, upper body visible, simple white background, "
        "{style} art style, clean lines, high detail, professional character design, "
        "neutral expression, studio lighting, centered composition, no text, no letters, no words"
    ),
    "back": (
        "character reference, {visual_description}, back view, rear view, "
        "facing away from viewer, standing pose, upper body visible, simple white background, "
        "{style} art style, clean lines, high detail, professional character design, "
        "neutral expression, studio lighting, centered composition, no text, no letters, no words"
    ),
}

# Maps camera_angle → preferred reference view for IPAdapter
CAMERA_ANGLE_TO_REF_VIEW = {
    "eye_level": "front",
    "low_angle": "front",
    "high_angle": "three_quarter",
    "dutch_angle": "three_quarter",
    "birds_eye": "back",
    "worms_eye": "front",
    "over_the_shoulder": "back",
}

CHARACTER_REF_NEGATIVE = (
    "bad quality, worst quality, low quality, blurry, deformed, disfigured, "
    "mutation, extra limbs, watermark, text, words, letters, lettering, "
    "multiple views, turnaround, multiple poses, split image, collage, "
    "busy background, complex background, jpeg artifacts, poorly drawn, "
    "amateur, ugly, duplicate"
)


# --- Composition Directive Templates ---

COMPOSITION_TEMPLATES = {
    # Dialogue shot/reverse-shot
    "dialogue_speaker_a": "character in right third, facing left, medium shot, eye-level, conversational framing",
    "dialogue_speaker_b": "character in left third, facing right, medium shot, eye-level, conversational framing",
    # Scene openers
    "establishing": "wide establishing shot, full environment visible, small figures, deep perspective, scene-setting composition",
    "establishing_dramatic": "dramatic wide shot, sweeping vista, cinematic scope, deep depth of field, epic scale",
    # Reactions & emotions
    "reaction": "tight close-up, focused on facial expression, shallow depth of field, emotional impact",
    "reaction_wide": "medium shot reaction, full body language visible, character responding to off-screen action",
    # Action
    "action_peak": "dynamic dutch angle, motion blur, extreme perspective, impact moment, kinetic energy",
    "action_buildup": "slight low angle, forward-leaning composition, building tension, motion anticipation",
    "action_aftermath": "high angle wide shot, settling dust, aftermath visible, moment of pause",
    # Transitions
    "transition": "wide shot pulling back, establishing new space, breathing room, visual pause",
    "time_skip": "atmospheric wide shot, different lighting than previous, passage of time, new moment",
    "flashback": "soft focus, desaturated tones, dream-like quality, memory composition",
    # Drama
    "reveal": "low angle, dramatic lighting, character emerging from shadow, powerful entrance",
    "confrontation": "centered symmetrical composition, two subjects facing each other, tension between subjects",
    "climax": "extreme low angle, dramatic backlighting, maximum visual impact, heroic framing",
    "climax_splash": "full dynamic composition, maximum detail, epic scale, splash-page energy, every element contributing to impact",
    # Quiet moments
    "contemplation": "off-center subject, large negative space, quiet atmosphere, introspective framing",
    "parallel": "split composition suggesting simultaneous events, dual focus, parallel action",
}

# Maps focal_point values to specific prompt fragments
FOCAL_POINT_TAGS = {
    "upper_left": "focal point in upper left, eye drawn to top-left third",
    "upper_right": "focal point in upper right, eye drawn to top-right third",
    "lower_left": "focal point in lower left, eye drawn to bottom-left third",
    "lower_right": "focal point in lower right, eye drawn to bottom-right third",
    "center": "centered focal point",
}

# Maps subject_position values to specific prompt fragments
SUBJECT_POSITION_TAGS = {
    "left_third": "subject positioned in left third of frame",
    "center": "subject centered in frame",
    "right_third": "subject positioned in right third of frame",
}

# Maps gaze_direction to prompt fragments
GAZE_DIRECTION_TAGS = {
    "left": "character looking toward left",
    "right": "character looking toward right",
    "center": "character looking straight ahead",
    "up": "character looking upward",
    "down": "character looking downward",
}

# --- Anti-Centering Negative Prompt Additions ---
ANTI_CENTERING_NEGATIVE = (
    "centered composition, symmetrical framing, passport photo, static pose, "
    "fashion photography, straight-on camera, centered subject"
)
ANTI_CENTERING_POSITIVE = "dynamic composition, off-center framing, rule of thirds"

# --- Mood → Lighting Directive Mapping (Storytelling Lighting) ---
MOOD_LIGHTING_DIRECTIVES = {
    "tense": "harsh side lighting, deep shadows, red accent lights",
    "danger": "harsh side lighting, deep shadows, red accent lights",
    "calm": "soft diffused light, warm golden hour tones",
    "peaceful": "soft diffused light, warm golden hour tones",
    "mysterious": "low key lighting, rim light from behind, face half in shadow",
    "triumphant": "backlit, lens flare, strong rim lighting, bright",
    "sad": "overcast flat lighting, muted colors, slight blue cast",
    "melancholic": "overcast flat lighting, muted colors, slight blue cast",
    "horror": "under-lighting, green-tinged, harsh unnatural shadows",
    "fear": "under-lighting, green-tinged, harsh unnatural shadows",
    "scared": "under-lighting, green-tinged, harsh unnatural shadows",
    "romantic": "soft warm lighting, bokeh background, subtle glow",
    "action": "dramatic directional light, high contrast, motion blur hints",
    "intense": "dramatic directional light, high contrast, motion blur hints",
    "dramatic": "dramatic chiaroscuro, strong contrast, single key light",
    "dark": "low key lighting, deep blacks, minimal fill light",
    "hopeful": "warm backlight, soft lens flare, light breaking through",
    "comedic": "bright even lighting, cheerful highlights, minimal shadows",
    "happy": "bright warm lighting, natural sun, cheerful tones",
    "neutral": "",  # no override for neutral mood
}

# --- Environment Interaction Hints ---
# Maps scene keywords → list of possible interaction hints.
# The generator picks one at random for variety.
ENVIRONMENT_INTERACTION_MAP = {
    # Indoor environments
    "indoor": ["leaning against wall", "hand resting on furniture", "framed by doorway"],
    "room": ["leaning against wall", "hand on doorframe", "standing near window"],
    "office": ["hand on desk", "leaning against filing cabinet", "silhouetted against window blinds"],
    "bedroom": ["sitting on bed edge", "hand on windowsill", "leaning against door"],
    "kitchen": ["leaning against counter", "hand on table", "standing near stove"],
    "hallway": ["hand trailing along wall", "framed by corridor perspective", "shadow stretching down hallway"],
    "corridor": ["hand trailing along wall", "framed by corridor perspective", "walking through narrow space"],
    "apartment": ["leaning against wall", "hand on doorframe", "looking out window"],
    "house": ["leaning against doorframe", "hand on railing", "standing on porch"],
    "bar": ["leaning on bar counter", "hand wrapped around glass", "sitting on barstool"],
    "restaurant": ["seated at table", "leaning forward over table", "hand on menu"],
    "hospital": ["hand on IV stand", "sitting on hospital bed edge", "leaning against sterile wall"],
    "prison": ["hands gripping cell bars", "sitting on hard bench", "back against cold wall"],
    "church": ["hand on pew", "standing in aisle", "light streaming through stained glass"],
    "library": ["hand on bookshelf", "seated at reading desk", "surrounded by towering shelves"],
    "warehouse": ["leaning against crate", "hand on chain-link fence", "standing among stacked boxes"],
    # Rooftop / elevated
    "rooftop": ["standing at ledge, wind in hair", "crouched on roof edge", "silhouetted against sky"],
    "roof": ["standing at ledge, wind in hair", "crouched on roof edge", "looking down from height"],
    "balcony": ["hands on railing, overlooking city", "leaning on balcony rail", "wind catching hair and clothes"],
    "tower": ["standing at window, vast view below", "hand on stone parapet", "wind whipping at height"],
    # Street / urban
    "street": ["walking through puddles", "passing storefront", "leaning against lamppost"],
    "alley": ["hand on brick wall", "pressed against dumpster", "navigating narrow passage"],
    "city": ["walking through crowd", "passing neon signs", "reflected in shop window"],
    "urban": ["leaning against graffiti wall", "standing under streetlight", "crossing wet pavement"],
    "sidewalk": ["stepping off curb", "passing pedestrians", "walking past storefronts"],
    "market": ["weaving through stalls", "hand brushing over merchandise", "surrounded by hanging goods"],
    "park": ["sitting on bench", "leaning against tree", "walking along path"],
    "bridge": ["hands on railing, looking at water", "walking across span", "wind on bridge"],
    "subway": ["gripping overhead rail", "leaning against train doors", "standing on platform edge"],
    "train": ["gripping overhead rail", "seated by window", "swaying with train motion"],
    # Lab / tech
    "lab": ["hands on keyboard", "examining holographic display", "peering into microscope"],
    "laboratory": ["hands on keyboard", "examining holographic display", "adjusting equipment"],
    "tech": ["interfacing with hologram", "hands on control panel", "reflected in monitor glow"],
    "computer": ["hands on keyboard, face lit by screen", "leaning toward monitor", "fingers on touchscreen"],
    "server": ["hand on server rack", "bathed in blinking LED light", "crouched checking cables"],
    "cockpit": ["hands on controls", "strapped into seat", "instruments reflected in visor"],
    # Nature / outdoor
    "forest": ["hand on tree trunk", "ducking under branch", "stepping over roots"],
    "mountain": ["hand gripping rock face", "standing on rocky outcrop", "wind buffeting at altitude"],
    "desert": ["shielding eyes from sun", "footprints in sand behind", "wind-blown sand stinging skin"],
    "beach": ["feet in surf", "sitting on driftwood", "wind in hair, ocean behind"],
    "ocean": ["gripping ship railing", "spray in face", "bracing against waves"],
    "river": ["stepping across stones", "kneeling at water edge", "wading through current"],
    "cave": ["hand on cave wall", "ducking under stalactites", "torchlight flickering on stone"],
    "jungle": ["pushing through vines", "crouched in undergrowth", "sweat glistening in humidity"],
    "field": ["walking through tall grass", "wind rippling through crops", "standing in open expanse"],
    "garden": ["hand brushing flowers", "kneeling in soil", "standing among hedgerows"],
    # Vehicles / transport
    "car": ["hand on steering wheel", "leaning out car window", "reflected in rearview mirror"],
    "vehicle": ["hand on steering wheel", "gripping dashboard", "looking through windshield"],
    "motorcycle": ["gripping handlebars", "leaning into turn", "wind whipping jacket"],
    "spaceship": ["floating in zero gravity", "hand on console", "looking out viewport at stars"],
    # Danger / combat areas
    "battlefield": ["crouching behind cover", "debris falling around", "smoke and dust swirling"],
    "ruins": ["stepping over rubble", "hand on crumbling wall", "dust particles in air"],
    "fire": ["shielding face from heat", "smoke swirling around", "embers floating in air"],
    "rain": ["rain streaming down face", "splashing through puddles", "hunched against downpour"],
    "snow": ["breath visible in cold air", "footprints in snow behind", "hunched against wind and snow"],
    "storm": ["bracing against wind", "hair and clothes whipping", "lightning illuminating scene"],
}


def _get_environment_interaction(scene: str, action: str, shot_type: str) -> str | None:
    """Select an environment interaction hint based on scene and action.

    Returns None for extreme close-ups (face-only shots don't show environment).
    Uses deterministic selection based on scene+action hash for reproducibility.
    """
    if shot_type in ("extreme_close",):
        return None

    if not scene:
        return None

    scene_lower = scene.lower()
    matched_hints: list[str] = []

    for keyword, hints in ENVIRONMENT_INTERACTION_MAP.items():
        if keyword in scene_lower:
            matched_hints.extend(hints)

    if not matched_hints:
        return None

    # Deterministic selection based on scene+action content for reproducibility
    hash_val = sum(ord(c) for c in (scene + (action or "")))
    return matched_hints[hash_val % len(matched_hints)]


def _get_mood_lighting_directive(mood: str) -> str | None:
    """Get a lighting directive based on the panel's mood.

    Returns a lighting description string or None if mood is neutral/unknown.
    """
    if not mood:
        return None

    mood_lower = mood.lower().strip()

    # Direct lookup
    if mood_lower in MOOD_LIGHTING_DIRECTIVES:
        directive = MOOD_LIGHTING_DIRECTIVES[mood_lower]
        return directive if directive else None

    # Fuzzy: check if any key is a substring of the mood
    for key, directive in MOOD_LIGHTING_DIRECTIVES.items():
        if key in mood_lower and directive:
            return directive

    return None


def load_presets():
    """Load ComfyUI presets."""
    if COMFYUI_PRESETS.exists():
        with open(COMFYUI_PRESETS) as f:
            data = json.load(f)
            return {k: v for k, v in data.items() if not k.startswith("_")}
    return {}


def _get_sequential_composition_tags(panel: dict, all_panels: list | None = None) -> list[str]:
    """Generate composition directives based on sequential art rules.

    Implements:
    - Subject positioning from story plan fields (subject_position, focal_point)
    - Gaze direction from story plan or auto-alternation
    - Eyeline matching between consecutive panels
    - Action-reaction choreography
    - Spatial continuity for same-location panels
    - Scene opening establishing shot rules
    - Climax/splash build-up composition
    - Anti-centering with contextual exceptions
    - Shot progression hints

    Args:
        panel: Current panel dict (should be enriched by story_planner).
        all_panels: Full panels list for context (optional).

    Returns:
        List of prompt tag strings to append.
    """
    tags: list[str] = []
    seq = panel.get("sequence", 1)
    shot = panel.get("shot_type", "medium")
    has_dialogue = bool(panel.get("dialogue"))
    chars_present = panel.get("characters_present", [])
    mood = panel.get("mood", "")
    narrative_weight = panel.get("narrative_weight", "medium")

    # Lookup helpers
    prev_panel = None
    next_panel = None
    if all_panels and len(all_panels) > 1:
        for p in all_panels:
            if p.get("sequence") == seq - 1:
                prev_panel = p
            if p.get("sequence") == seq + 1:
                next_panel = p

    # ── 1. Scene Opening Rules ─────────────────────────────────────────
    # If this is the first panel of a new scene, apply establishing template
    is_scene_opener = False
    if prev_panel:
        prev_scene = prev_panel.get("scene", "").strip().lower()
        curr_scene = panel.get("scene", "").strip().lower()
        if prev_scene != curr_scene:
            is_scene_opener = True
    elif seq == 1:
        is_scene_opener = True

    if is_scene_opener:
        spatial_rel = panel.get("spatial_relation", "")
        if spatial_rel == "flashback":
            tags.append(COMPOSITION_TEMPLATES["flashback"])
        elif spatial_rel == "time_skip":
            tags.append(COMPOSITION_TEMPLATES["time_skip"])
        elif shot in ("extreme_wide", "wide", "long", "extreme_long"):
            tags.append(COMPOSITION_TEMPLATES["establishing"])
        else:
            # Even if not a wide shot, hint at scene establishment
            tags.append("establishing new scene, environmental context visible")

    # ── 2. Anti-Centering with Context ─────────────────────────────────
    # Respect composition_override from story plan:
    #   "symmetric" → force centered/symmetric composition
    #   "dynamic"   → force off-center even if conditions would allow center
    #   None        → use automatic heuristics
    composition_override = panel.get("composition_override")

    # Exception: eye_level + explicit symmetric override → skip anti-centering
    camera_angle = panel.get("camera_angle", "eye_level")
    if composition_override == "symmetric":
        allow_center = True
    elif composition_override == "dynamic":
        allow_center = False
    else:
        # Automatic: symmetric compositions ONLY for confrontations or splash panels
        allow_center = (
            narrative_weight == "splash"
            or shot in ("extreme_wide",)
            or "confrontation" in mood.lower()
            or (has_dialogue and len(panel.get("dialogue", [])) >= 2
                and len(chars_present) >= 2)  # Two speakers facing each other
        )

    if allow_center and narrative_weight == "splash":
        tags.append(COMPOSITION_TEMPLATES["climax_splash"])
    elif allow_center and "confrontation" in mood.lower():
        tags.append(COMPOSITION_TEMPLATES["confrontation"])
    elif allow_center and composition_override == "symmetric":
        tags.append("balanced symmetrical composition, centered framing, deliberate symmetry")
    elif not allow_center:
        tags.append(ANTI_CENTERING_POSITIVE)

        # Use subject_position from story plan if available
        subj_pos = panel.get("subject_position")
        if subj_pos and subj_pos in SUBJECT_POSITION_TAGS:
            if subj_pos != "center":  # don't add "centered" when anti-centering
                tags.append(SUBJECT_POSITION_TAGS[subj_pos])
        else:
            # Fallback: alternate based on sequence
            if chars_present:
                if seq % 2 == 1:
                    tags.append(SUBJECT_POSITION_TAGS["right_third"])
                else:
                    tags.append(SUBJECT_POSITION_TAGS["left_third"])

    # ── 3. Focal Point ─────────────────────────────────────────────────
    focal = panel.get("focal_point")
    if focal and focal in FOCAL_POINT_TAGS:
        # Only add focal point if it's not center (to avoid competing with anti-centering)
        if focal != "center" or allow_center:
            tags.append(FOCAL_POINT_TAGS[focal])

    # ── 4. Gaze Direction ──────────────────────────────────────────────
    gaze = panel.get("gaze_direction")
    if gaze and gaze in GAZE_DIRECTION_TAGS:
        if shot not in ("extreme_wide", "wide"):  # gaze irrelevant in wide shots
            tags.append(GAZE_DIRECTION_TAGS[gaze])
    elif has_dialogue and chars_present and shot not in ("extreme_wide", "wide"):
        # Fallback: alternate gaze for dialogue panels
        if seq % 2 == 1:
            tags.append(GAZE_DIRECTION_TAGS["left"])
        else:
            tags.append(GAZE_DIRECTION_TAGS["right"])

    # ── 5. Eyeline Matching ────────────────────────────────────────────
    # If prev panel's character looked left, this panel's subject should be left
    if prev_panel:
        prev_gaze = prev_panel.get("gaze_direction", "")
        if prev_gaze == "left" and not panel.get("subject_position"):
            tags.append("subject on left side, matching previous panel's eyeline")
        elif prev_gaze == "right" and not panel.get("subject_position"):
            tags.append("subject on right side, matching previous panel's eyeline")

    # ── 6. Dialogue Composition Templates ──────────────────────────────
    if has_dialogue and chars_present and shot not in ("extreme_wide", "wide", "long"):
        dialogue = panel.get("dialogue", [])
        if len(dialogue) >= 1:
            # Determine which speaker template to use
            speaker_id = dialogue[0].get("character_id", "")
            speaker_hash = sum(ord(c) for c in speaker_id)
            if speaker_hash % 2 == 0:
                tags.append(COMPOSITION_TEMPLATES["dialogue_speaker_a"])
            else:
                tags.append(COMPOSITION_TEMPLATES["dialogue_speaker_b"])

    # ── 7. Action-Reaction Choreography ────────────────────────────────
    action_keywords = ("kinetic", "action", "explosive", "fast", "urgent", "thrilling", "violent")
    is_action = any(kw in mood.lower() for kw in action_keywords)

    if prev_panel:
        prev_mood = prev_panel.get("mood", "")
        prev_is_action = any(kw in prev_mood.lower() for kw in action_keywords)

        if prev_is_action and not is_action:
            # This panel follows an action panel → suggest reaction shot
            tags.append(COMPOSITION_TEMPLATES["reaction"])

    if is_action:
        tags.append(COMPOSITION_TEMPLATES["action_peak"])
    elif any(kw in mood.lower() for kw in ("calm", "quiet", "reflective", "peaceful")):
        tags.append(COMPOSITION_TEMPLATES["contemplation"])
    elif any(kw in mood.lower() for kw in ("tense", "menacing", "danger", "dread")):
        tags.append("tight framing, strong shadows, visual tension, claustrophobic composition")

    # ── 8. Spatial Continuity ──────────────────────────────────────────
    spatial_rel = panel.get("spatial_relation", "")
    if spatial_rel == "same_location" and prev_panel:
        tags.append("same environment as previous panel, consistent background elements, spatial continuity")
    elif spatial_rel == "parallel":
        tags.append(COMPOSITION_TEMPLATES["parallel"])
    elif spatial_rel == "flashback" and not is_scene_opener:
        # Already handled in scene opener; only add if mid-scene
        tags.append("memory-like quality, slightly soft focus")

    # ── 9. Climax Build-up ─────────────────────────────────────────────
    if narrative_weight == "high":
        tags.append("dramatic composition, heightened visual impact, strong contrast, powerful framing")
        tags.append(COMPOSITION_TEMPLATES["climax"])
    elif narrative_weight == "splash":
        # Already handled above in anti-centering section
        pass

    # ── 10. Shot Progression Hint ──────────────────────────────────────
    if prev_panel:
        prev_shot = prev_panel.get("shot_type", "medium")
        if prev_shot in ("extreme_wide", "wide", "long") and shot in ("medium", "medium_close"):
            tags.append("tighter framing than previous shot, moving closer to subject")
        elif prev_shot in ("close_up", "extreme_close") and shot in ("medium", "wide", "long"):
            tags.append("pulled-back wider framing, revealing more environment")

    # ── 11. Reveal composition for narrative weight ────────────────────
    if panel.get("_is_reveal") or "reveal" in panel.get("action", "").lower():
        tags.append(COMPOSITION_TEMPLATES["reveal"])

    return tags


def _convert_description_to_tags(description: str) -> str:
    """Convert a natural language visual description to Danbooru-style tags.

    Simple heuristic: split on commas and common conjunctions, strip filler
    words, and rejoin as comma-separated tags.
    """
    if not description:
        return ""
    # Already looks like tags (short, comma-separated)
    parts = [p.strip() for p in description.replace(" and ", ", ").split(",")]
    tags = []
    # Strip common filler words
    filler = {"a", "an", "the", "with", "wearing", "has", "having", "is", "are", "who", "that"}
    for part in parts:
        words = part.split()
        cleaned = " ".join(w for w in words if w.lower() not in filler)
        if cleaned:
            tags.append(cleaned.strip())
    return ", ".join(tags)


def _build_costume_string(character: dict) -> str:
    """Build a costume description string from character's costume_details field.

    Returns a string like: "wearing grey hoodie with zipper, dark jeans, black sneakers, with silver watch, red backpack"
    Returns empty string if no costume_details or all fields are empty.
    """
    costume = character.get("costume_details")
    if not costume or not isinstance(costume, dict):
        return ""

    parts = []
    if costume.get("top"):
        parts.append(costume["top"])
    if costume.get("bottom"):
        parts.append(costume["bottom"])
    if costume.get("shoes"):
        parts.append(costume["shoes"])

    accessories = costume.get("accessories", [])
    if isinstance(accessories, list) and accessories:
        parts.append(f"with {', '.join(accessories)}")

    if not parts:
        return ""

    return "wearing " + ", ".join(parts)


def build_illustrious_prompt(panel: dict, characters: list, style: str,
                             all_panels: list | None = None) -> str:
    """Build a Danbooru-tag-style prompt for Illustrious XL / NoobAI-XL.

    Unlike the standard SDXL prompt (natural language), Illustrious models
    understand Danbooru tags natively. This function produces prompts in the
    format: "masterpiece, best quality, 1girl, short black hair, ..."

    Prompt order:
    1. Quality tags
    2. Character count tag
    3. Shot type + camera angle (Danbooru tags)
    4. Style tags (comic/manga/etc.)
    5. Character description tags (converted from natural language)
    6. Character emotion tags
    7. Action / scene / background tags
    8. Lighting tags
    9. Mood/atmosphere tags
    10. Anti-text enforcement
    """
    parts = []

    # 1. Quality tags — always first for Illustrious
    parts.append("masterpiece, best quality, newest, absurdres, highres")

    # 2. Character count
    char_present = panel.get("characters_present", [])
    char_map = {c["id"]: c for c in characters}
    if len(char_present) == 1:
        # Check gender hint from description
        char = char_map.get(char_present[0], {})
        desc = char.get("visual_description", "").lower()
        if any(w in desc for w in ("woman", "girl", "female", "she")):
            parts.append("1girl")
        elif any(w in desc for w in ("man", "boy", "male", "he")):
            parts.append("1boy")
        else:
            parts.append("solo")
    elif len(char_present) == 2:
        parts.append("2people")
    elif len(char_present) >= 3:
        parts.append(f"{len(char_present)}people, multiple people")

    # 3. Shot type + camera angle
    shot = panel.get("shot_type", "medium")
    angle = panel.get("camera_angle", "eye_level")
    parts.append(ILLUSTRIOUS_SHOT_TAGS.get(shot, "cowboy shot"))
    if angle != "eye_level":  # straight-on is default, skip if eye level
        parts.append(ILLUSTRIOUS_ANGLE_TAGS.get(angle, ""))

    # 4. Style tags
    parts.append(ILLUSTRIOUS_STYLE_TAGS.get(style, ILLUSTRIOUS_STYLE_TAGS["western"]))

    # 4b. Sequential storytelling boost (Danbooru-style)
    parts.append("sequential art, comic panel, storytelling, narrative composition")
    # Action vs dialogue boost
    has_dialogue = bool(panel.get("dialogue"))
    action_text = panel.get("action", "").lower()
    mood_text = panel.get("mood", "").lower()
    action_keywords = ("fight", "run", "chase", "explod", "attack", "dodge", "jump",
                       "crash", "smash", "slash", "shoot", "throw", "punch", "kick")
    if any(kw in action_text or kw in mood_text for kw in action_keywords):
        parts.append("dynamic action, motion lines, impact")
    elif has_dialogue:
        parts.append("dialogue scene, expressive, character interaction")

    # 5. Character descriptions as tags
    emotions_raw = panel.get("character_emotions", "")
    if isinstance(emotions_raw, str):
        emotion_list = [e.strip() for e in emotions_raw.split(",") if e.strip()] if emotions_raw else []
    else:
        emotion_list = list(emotions_raw)

    for idx, char_id in enumerate(char_present):
        char = char_map.get(char_id)
        if not char:
            continue
        # Convert visual description to tags
        if char.get("visual_description"):
            tags = _convert_description_to_tags(char["visual_description"])
            if tags:
                parts.append(tags)

        # Costume details injection (Illustrious: as tags)
        costume_str = _build_costume_string(char)
        if costume_str:
            parts.append(_convert_description_to_tags(costume_str))

        # 6. Per-character emotion
        if emotion_list:
            emo_key = emotion_list[idx] if idx < len(emotion_list) else emotion_list[0]
            parts.append(ILLUSTRIOUS_EMOTION_TAGS.get(emo_key, emo_key))

    # Character poses
    if panel.get("character_poses"):
        parts.append(_convert_description_to_tags(panel["character_poses"]))

    # 7. Action / scene / background
    if panel.get("action"):
        parts.append(_convert_description_to_tags(panel["action"]))
    if panel.get("scene"):
        parts.append(_convert_description_to_tags(panel["scene"]))
    if panel.get("background_detail"):
        parts.append(_convert_description_to_tags(panel["background_detail"]))

    # 7b. Environment interaction hints (Illustrious)
    scene = panel.get("scene", "")
    env_hint = _get_environment_interaction(scene, panel.get("action", ""), shot)
    if env_hint:
        parts.append(_convert_description_to_tags(env_hint))

    # 8. Lighting — mood-based auto-injection + explicit
    mood = panel.get("mood", "")
    mood_lighting = _get_mood_lighting_directive(mood)
    if mood_lighting:
        parts.append(_convert_description_to_tags(mood_lighting))

    lighting = panel.get("lighting")
    if lighting:
        parts.append(ILLUSTRIOUS_LIGHTING_TAGS.get(lighting, lighting))

    # 9. Mood / atmosphere
    if mood:
        parts.append(f"{mood}")

    # 10. Anti-text
    parts.append("no text")

    # Filter empty strings and join
    return ", ".join(p for p in parts if p)


def get_negative_prompt_for_preset(preset_name: str, panel: dict | None = None) -> str:
    """Return the appropriate negative prompt for a given preset.

    Illustrious and NoobAI models have their own optimized negatives.
    When *panel* is provided and has composition_override == "symmetric",
    the anti-centering terms are omitted from the negative prompt.
    """
    skip_anti_centering = (
        panel is not None
        and panel.get("composition_override") == "symmetric"
    )

    if preset_name == "noobaiXL":
        base = NOOBAI_NEGATIVE_PROMPT
    elif preset_name in ILLUSTRIOUS_PRESETS:
        base = ILLUSTRIOUS_NEGATIVE_PROMPT
    else:
        base = NEGATIVE_PROMPT

    # For Illustrious/NoobAI, append anti-centering terms (they aren't in the base)
    if preset_name in ILLUSTRIOUS_PRESETS or preset_name == "noobaiXL":
        if not skip_anti_centering:
            base = base.rstrip() + ", " + ANTI_CENTERING_NEGATIVE
    else:
        # Standard SDXL: anti-centering is already in NEGATIVE_PROMPT,
        # but if symmetric override, strip those terms
        if skip_anti_centering:
            # Remove anti-centering phrases from the negative
            for term in ANTI_CENTERING_NEGATIVE.split(", "):
                base = base.replace(term + ", ", "").replace(", " + term, "").replace(term, "")

    return base


def build_panel_prompt(panel: dict, characters: list, style: str,
                       all_panels: list | None = None,
                       preset_name: str | None = None) -> str:
    """Build a generation prompt for a single panel.

    If preset_name is an Illustrious/NoobAI preset, delegates to
    build_illustrious_prompt() which produces Danbooru-tag-style prompts.
    Otherwise, uses the standard natural language prompt format.

    Prompt order (standard SDXL):
    1. Shot type + camera angle
    2. Style tags
    3. "comic panel"
    4. Sequential composition directives
    5. Action + Scene + Background detail
    6. Character descriptions WITH poses and emotions
    7. Lighting
    8. Mood
    9. Anti-text tag
    10. Quality tags
    """
    # Delegate to Illustrious prompt builder for Illustrious/NoobAI presets
    if preset_name and preset_name in ILLUSTRIOUS_PRESETS:
        return build_illustrious_prompt(panel, characters, style, all_panels)

    parts = []

    # 1. Shot type + camera angle
    shot = panel.get("shot_type", "medium")
    angle = panel.get("camera_angle", "eye_level")
    parts.append(SHOT_TYPE_TAGS.get(shot, "medium shot"))
    parts.append(CAMERA_ANGLE_TAGS.get(angle, "eye level view"))

    # 2. Style
    parts.append(STYLE_TAGS.get(style, STYLE_TAGS["western"]))

    # 3. Panel identifier — sequential storytelling prompt boost
    # Always add sequential storytelling language (not generic "comic book style")
    parts.append("sequential comic book art, storytelling panel, narrative composition")

    # Boost based on panel type: dialogue vs action
    has_dialogue = bool(panel.get("dialogue"))
    action_text = panel.get("action", "").lower()
    mood_text = panel.get("mood", "").lower()
    action_keywords = ("fight", "run", "chase", "explod", "attack", "dodge", "jump",
                       "crash", "smash", "slash", "shoot", "throw", "punch", "kick",
                       "kinetic", "action", "explosive", "fast", "urgent", "violent")
    is_action_panel = any(kw in action_text or kw in mood_text for kw in action_keywords)

    if is_action_panel:
        parts.append("dynamic comic action, motion lines, impact frame")
    elif has_dialogue:
        parts.append("comic dialogue scene, expressive character interaction")

    # 4. Sequential composition directives
    comp_tags = _get_sequential_composition_tags(panel, all_panels)
    parts.extend(comp_tags)

    # 5. Action + Scene + Background detail
    if panel.get("action"):
        parts.append(panel["action"])
    if panel.get("scene"):
        parts.append(panel["scene"])
    if panel.get("background_detail"):
        parts.append(panel["background_detail"])

    # 5b. Environment interaction hints
    scene = panel.get("scene", "")
    env_hint = _get_environment_interaction(scene, panel.get("action", ""), shot)
    if env_hint:
        parts.append(env_hint)

    # 6. Characters present — with poses and emotions
    char_map = {c["id"]: c for c in characters}
    emotions_raw = panel.get("character_emotions", "")
    # Normalise to a list (may be a single string or a list)
    if isinstance(emotions_raw, str):
        emotion_list = [e.strip() for e in emotions_raw.split(",") if e.strip()] if emotions_raw else []
    else:
        emotion_list = list(emotions_raw)

    for idx, char_id in enumerate(panel.get("characters_present", [])):
        char = char_map.get(char_id)
        if not char:
            continue
        char_parts = []
        if char.get("visual_description"):
            char_parts.append(char["visual_description"])
        # Costume details injection
        costume_str = _build_costume_string(char)
        if costume_str:
            char_parts.append(costume_str)
        # Per-character emotion (index-matched) or fall back to first
        if emotion_list:
            emo_key = emotion_list[idx] if idx < len(emotion_list) else emotion_list[0]
            char_parts.append(EMOTION_TAGS.get(emo_key, emo_key))
        if char_parts:
            parts.append(", ".join(char_parts))

    # Character poses (global string applied to the whole scene)
    if panel.get("character_poses"):
        parts.append(panel["character_poses"])

    # 7. Lighting — auto-inject based on mood, then fallback to explicit
    mood = panel.get("mood", "")
    mood_lighting = _get_mood_lighting_directive(mood)
    lighting = panel.get("lighting")

    if mood_lighting:
        # Mood-driven lighting takes priority for storytelling
        parts.append(mood_lighting)
    if lighting:
        # Still add explicit lighting tag (may complement mood lighting)
        parts.append(LIGHTING_TAGS.get(lighting, lighting))

    # 8. Mood
    if mood:
        parts.append(f"{mood} atmosphere")

    # 9. Anti-text (SDXL positive-side reinforcement)
    parts.append("no text, no letters, no words, clean image")

    # 10. Quality tags
    parts.append("high quality, detailed, sharp lines")

    # Extra anti-text at the very end for SDXL
    parts.append("no text, no letters, no words, no writing")

    return ", ".join(parts)


def build_sdxl_workflow(prompt: str, negative: str, preset_config: dict,
                        width: int = 768, height: int = 768,
                        seed: int = -1, prefix: str = "panel",
                        loras: list[dict] | None = None) -> dict:
    """Build an SDXL txt2img workflow for a panel.

    If *loras* is provided (list of LoRA config dicts), LoraLoader nodes are
    inserted between the checkpoint and all downstream consumers.
    """
    if seed < 0:
        seed = random.randint(0, 2**32 - 1)

    workflow = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": preset_config.get("steps", 8),
                "cfg": preset_config.get("cfg", 2.0),
                "sampler_name": preset_config.get("sampler", "dpmpp_sde"),
                "scheduler": preset_config.get("scheduler", "karras"),
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": preset_config["model"]},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["4", 1]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative, "clip": ["4", 1]},
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": prefix, "images": ["8", 0]},
        },
    }

    # --- Illustrious/NoobAI enhancements ---

    # Clip Skip (Illustrious models need clip_skip=2)
    clip_skip = preset_config.get("clip_skip")
    if clip_skip and clip_skip != 1:
        workflow["50"] = {
            "class_type": "CLIPSetLastLayer",
            "inputs": {
                "stop_at_clip_layer": -clip_skip,
                "clip": ["4", 1],
            },
        }
        # Rewire CLIP consumers to use CLIPSetLastLayer output
        for nid in ("6", "7"):
            if nid in workflow:
                workflow[nid]["inputs"]["clip"] = ["50", 0]

    # V-prediction (NoobAI-XL v-pred models)
    if preset_config.get("v_prediction"):
        workflow["51"] = {
            "class_type": "ModelSamplingDiscrete",
            "inputs": {
                "sampling": "v_prediction",
                "zsnr": True,
                "model": ["4", 0],
            },
        }
        # Rewire KSampler model input to v-pred node
        workflow["3"]["inputs"]["model"] = ["51", 0]

    if loras:
        _insert_lora_nodes(workflow, loras, checkpoint_node="4")

    return workflow


def build_sdxl_ipadapter_workflow(prompt: str, negative: str, preset_config: dict,
                                  ref_image_filename: str,
                                  ipadapter_weight: float = 0.7,
                                  ipadapter_preset: str = "PLUS (high strength)",
                                  width: int = 768, height: int = 768,
                                  seed: int = -1, prefix: str = "panel",
                                  loras: list[dict] | None = None) -> dict:
    """Build an SDXL workflow with IPAdapter for character consistency.

    Workflow graph:
        [4: CheckpointLoaderSimple] → model
        [10: LoadImage] → ref image
        [11: IPAdapterUnifiedLoader] → model + ipadapter
        [12: IPAdapterAdvanced] → conditioned model
        [6: CLIPTextEncode +] ─┐
        [7: CLIPTextEncode -] ─┤
        [5: EmptyLatentImage] ─┤
                               └→ [3: KSampler] → [8: VAEDecode] → [9: SaveImage]

    If *loras* is provided, LoraLoader nodes are inserted between the
    checkpoint and the IPAdapterUnifiedLoader.
    """
    if seed < 0:
        seed = random.randint(0, 2**32 - 1)

    workflow = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": preset_config.get("steps", 8),
                "cfg": preset_config.get("cfg", 2.0),
                "sampler_name": preset_config.get("sampler", "dpmpp_sde"),
                "scheduler": preset_config.get("scheduler", "karras"),
                "denoise": 1.0,
                "model": ["12", 0],       # from IPAdapterAdvanced
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": preset_config["model"]},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["4", 1]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative, "clip": ["4", 1]},
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": prefix, "images": ["8", 0]},
        },
        # --- IPAdapter nodes ---
        "10": {
            "class_type": "LoadImage",
            "inputs": {"image": ref_image_filename},
        },
        "11": {
            "class_type": "IPAdapterUnifiedLoader",
            "inputs": {
                "model": ["4", 0],
                "preset": ipadapter_preset,
            },
        },
        "12": {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "model": ["11", 0],        # model from unified loader
                "ipadapter": ["11", 1],     # ipadapter from unified loader
                "image": ["10", 0],         # ref image
                "weight": ipadapter_weight,
                "weight_type": "style transfer",
                "combine_embeds": "concat",
                "start_at": 0.0,
                "end_at": 0.8,
                "embeds_scaling": "V only",
            },
        },
    }

    if loras:
        # Insert LoRAs between checkpoint(4) and IPAdapterUnifiedLoader(11).
        # _insert_lora_nodes rewires all refs from "4" model/clip to last LoRA,
        # which means node 11 (UnifiedLoader) and 6/7 (CLIP encoders) will
        # automatically receive the LoRA-conditioned model/clip.
        _insert_lora_nodes(workflow, loras, checkpoint_node="4")

    return workflow


def build_sdxl_multi_ipadapter_workflow(
    prompt: str,
    negative: str,
    preset_config: dict,
    char_refs: list[dict],
    width: int = 768,
    height: int = 768,
    seed: int = -1,
    prefix: str = "panel",
    loras: list[dict] | None = None,
) -> dict:
    """Build an SDXL workflow with chained IPAdapterAdvanced nodes for multiple characters.

    Each entry in char_refs must have:
        - filename: str  — ComfyUI filename (already uploaded via upload_image)
        - weight: float  — IPAdapter weight (primary ~0.6, secondary ~0.4, tertiary ~0.3)
        - preset: str    — "PLUS (high strength)" or "PLUS FACE (portraits)"

    Workflow graph (2-character example):
        [4: CheckpointLoaderSimple] → model
        [11: IPAdapterUnifiedLoader] → model + ipadapter
        [20: LoadImage(char1)] ─┐
        [30: IPAdapterAdvanced(char1)] ← model from [11], image from [20]
        [21: LoadImage(char2)] ─┐
        [31: IPAdapterAdvanced(char2)] ← model from [30], image from [21]
        [6: CLIPTextEncode +] ─┐
        [7: CLIPTextEncode -] ─┤
        [5: EmptyLatentImage] ─┤
                               └→ [3: KSampler] → [8: VAEDecode] → [9: SaveImage]

    The key insight: each IPAdapterAdvanced's model output feeds the next one,
    creating a sequential conditioning chain.

    Node numbering:
        - Base nodes: 3-9, 11 (same IDs as single-character workflow)
        - LoadImage nodes: 20, 21, 22, ... (20 + index)
        - IPAdapterAdvanced nodes: 30, 31, 32, ... (30 + index)
    """
    if seed < 0:
        seed = random.randint(0, 2**32 - 1)

    if not char_refs:
        raise ValueError("char_refs must contain at least one character reference")

    # Determine end_at per character position (decreasing influence)
    END_AT_BY_POSITION = [0.8, 0.7, 0.6, 0.55, 0.5]

    workflow = {
        # --- Base nodes (same IDs as single-character workflow) ---
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": preset_config["model"]},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["4", 1]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative, "clip": ["4", 1]},
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": prefix, "images": ["8", 0]},
        },
        # --- IPAdapterUnifiedLoader (shared) ---
        "11": {
            "class_type": "IPAdapterUnifiedLoader",
            "inputs": {
                "model": ["4", 0],
                "preset": char_refs[0].get("preset", "PLUS (high strength)"),
            },
        },
    }

    # --- Chain IPAdapterAdvanced nodes ---
    last_model_source = ["11", 0]  # first character gets model from UnifiedLoader

    for i, ref in enumerate(char_refs):
        load_node_id = str(20 + i)
        ipa_node_id = str(30 + i)

        end_at = END_AT_BY_POSITION[i] if i < len(END_AT_BY_POSITION) else 0.5

        # LoadImage node for this character's reference
        workflow[load_node_id] = {
            "class_type": "LoadImage",
            "inputs": {"image": ref["filename"]},
        }

        # IPAdapterAdvanced node — chains model from previous
        workflow[ipa_node_id] = {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "model": last_model_source,
                "ipadapter": ["11", 1],          # shared ipadapter from UnifiedLoader
                "image": [load_node_id, 0],
                "weight": ref.get("weight", 0.5),
                "weight_type": "style transfer",
                "combine_embeds": "concat",
                "start_at": 0.0,
                "end_at": end_at,
                "embeds_scaling": "V only",
            },
        }

        # Next character chains from this one's model output
        last_model_source = [ipa_node_id, 0]

    # KSampler connects to the LAST IPAdapterAdvanced's model output
    # Insert LoRA nodes between checkpoint and the rest of the graph.
    # Must happen BEFORE building KSampler so that the IPAdapter chain
    # (which reads from "4"/model) already points at the last LoRA node.
    if loras:
        _insert_lora_nodes(workflow, loras, checkpoint_node="4")

    workflow["3"] = {
        "class_type": "KSampler",
        "inputs": {
            "seed": seed,
            "steps": preset_config.get("steps", 8),
            "cfg": preset_config.get("cfg", 2.0),
            "sampler_name": preset_config.get("sampler", "dpmpp_sde"),
            "scheduler": preset_config.get("scheduler", "karras"),
            "denoise": 1.0,
            "model": last_model_source,
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["5", 0],
        },
    }

    return workflow


def generate_character_ref(character: dict, style: str, preset_name: str,
                           output_dir: str, width: int = 1024,
                           height: int = 1024, seed: int = -1,
                           timeout: int = 300,
                           multi_angle: bool = True) -> dict:
    """Generate character reference image(s) for IPAdapter.

    When multi_angle=True (default), generates 4 views (front, 3/4, profile, back)
    as separate 1024x1024 images AND a combined 2048x2048 grid. Each view is
    uploaded to ComfyUI individually so the best-matching view can be selected
    per panel based on camera_angle.

    When multi_angle=False, falls back to a single front-view portrait.

    Args:
        character: Character dict with at least 'id' and 'visual_description'.
        style: Art style key (e.g. 'western', 'manga').
        preset_name: ComfyUI preset name.
        output_dir: Directory to save the reference image.
        width: Image width per view (default 1024 for high-quality ref).
        height: Image height per view.
        seed: Random seed (-1 for random).
        timeout: Generation timeout in seconds per view.
        multi_angle: Generate 4-view reference sheet (default True).

    Returns:
        Dict with keys:
        - path: str (primary front-view image path, or grid path)
        - seed: int
        - duration_s: float
        - prompt: str (front-view prompt)
        - comfyui_filename: str (front-view uploaded filename — default for IPAdapter)
        - views: dict mapping view_name → {path, comfyui_filename} (only when multi_angle=True)
        - grid_path: str (2x2 grid image path, only when multi_angle=True)
    """
    from PIL import Image as PILImage

    presets = load_presets()
    preset_config = presets.get(preset_name, presets.get("dreamshaperXL", {}))

    visual_desc = character.get("visual_description", "a character")
    style_label = style if style else "western"
    char_id = character.get("id", "char")

    if seed < 0:
        seed = random.randint(0, 2**32 - 1)

    # Apply style LoRAs to character ref generation too
    style_loras = get_style_loras(style_label)

    os.makedirs(output_dir, exist_ok=True)
    ensure_running()

    if not multi_angle:
        # --- Legacy single-view path ---
        prompt = CHARACTER_REF_PROMPT_TEMPLATE.format(
            visual_description=visual_desc,
            style=style_label,
        )
        prefix = f"charref_{char_id}"
        workflow = build_sdxl_workflow(
            prompt=prompt,
            negative=CHARACTER_REF_NEGATIVE,
            preset_config=preset_config,
            width=width,
            height=height,
            seed=seed,
            prefix=prefix,
            loras=style_loras,
        )

        start = time.time()
        paths = generate_and_download(workflow, output_dir, timeout=timeout)
        duration = time.time() - start

        if not paths:
            raise RuntimeError(f"No reference image generated for character {char_id}")

        ref_path = paths[0]
        comfyui_filename = upload_image(ref_path)
        print(f"  📤 Uploaded ref as: {comfyui_filename}")

        return {
            "path": ref_path,
            "seed": seed,
            "duration_s": round(duration, 1),
            "prompt": prompt,
            "comfyui_filename": comfyui_filename,
        }

    # --- Multi-angle path: generate 4 views ---
    view_names = ["front", "three_quarter", "profile", "back"]
    views_result: dict[str, dict] = {}
    view_images: list = []  # PIL images for grid assembly
    total_duration = 0.0
    front_prompt = ""

    for i, view_name in enumerate(view_names):
        view_seed = seed + i  # deterministic but different per view
        prompt_template = CHARACTER_REF_VIEW_PROMPTS.get(
            view_name, CHARACTER_REF_PROMPT_TEMPLATE
        )
        prompt = prompt_template.format(
            visual_description=visual_desc,
            style=style_label,
        )
        if view_name == "front":
            front_prompt = prompt

        prefix = f"charref_{char_id}_{view_name}"
        workflow = build_sdxl_workflow(
            prompt=prompt,
            negative=CHARACTER_REF_NEGATIVE,
            preset_config=preset_config,
            width=width,
            height=height,
            seed=view_seed,
            prefix=prefix,
            loras=style_loras,
        )

        print(f"  🎨 Generating {view_name} view for {char_id}...", end=" ", flush=True)
        start = time.time()
        paths = generate_and_download(workflow, output_dir, timeout=timeout)
        dur = time.time() - start
        total_duration += dur

        if not paths:
            print(f"⚠️ Failed")
            continue

        ref_path = paths[0]
        comfyui_filename = upload_image(ref_path)
        print(f"✅ ({dur:.1f}s) → {comfyui_filename}")

        views_result[view_name] = {
            "path": ref_path,
            "comfyui_filename": comfyui_filename,
            "seed": view_seed,
        }

        # Load image for grid assembly
        try:
            view_images.append((view_name, PILImage.open(ref_path).convert("RGB")))
        except Exception:
            pass

    if not views_result:
        raise RuntimeError(f"No reference views generated for character {char_id}")

    # --- Assemble 2x2 grid ---
    grid_path = os.path.join(output_dir, f"charref_{char_id}_grid.png")
    if len(view_images) == 4:
        grid = PILImage.new("RGB", (width * 2, height * 2), (255, 255, 255))
        positions = [(0, 0), (width, 0), (0, height), (width, height)]
        for (vname, vimg), pos in zip(view_images, positions):
            # Resize if needed (should already be correct)
            if vimg.size != (width, height):
                vimg = vimg.resize((width, height), PILImage.LANCZOS)
            grid.paste(vimg, pos)
        grid.save(grid_path)
        print(f"  📐 Grid assembled: {grid_path}")
    elif view_images:
        # Partial grid — use what we have
        cols = 2
        rows = (len(view_images) + 1) // 2
        grid = PILImage.new("RGB", (width * cols, height * rows), (255, 255, 255))
        for idx, (vname, vimg) in enumerate(view_images):
            x = (idx % cols) * width
            y = (idx // cols) * height
            if vimg.size != (width, height):
                vimg = vimg.resize((width, height), PILImage.LANCZOS)
            grid.paste(vimg, (x, y))
        grid.save(grid_path)
        print(f"  📐 Partial grid ({len(view_images)} views): {grid_path}")

    # Primary ref = front view (fallback to first available)
    primary_view = views_result.get("front") or next(iter(views_result.values()))

    return {
        "path": primary_view["path"],
        "seed": seed,
        "duration_s": round(total_duration, 1),
        "prompt": front_prompt,
        "comfyui_filename": primary_view["comfyui_filename"],
        "views": views_result,
        "grid_path": grid_path if os.path.exists(grid_path) else None,
    }


def generate_panel(panel: dict, characters: list, style: str,
                   preset_name: str, output_dir: str,
                   char_refs: dict = None,
                   width: int = 768, height: int = 768,
                   seed: int = -1, timeout: int = 300,
                   all_panels: list = None) -> dict:
    """
    Generate a single comic panel.

    Args:
        panel: Panel definition dict.
        characters: List of character dicts.
        style: Art style key.
        preset_name: ComfyUI preset name.
        output_dir: Directory to save output.
        char_refs: Optional dict mapping character_id → ref info dict
                   (must contain 'comfyui_filename'). When provided and the
                   panel has characters_present, IPAdapter is used for
                   character consistency.
        width: Image width.
        height: Image height.
        seed: Random seed (-1 for random).
        timeout: Generation timeout in seconds.
        all_panels: Full panels list for sequential composition context.

    Returns dict with:
        - path: str (output image path)
        - seed: int (seed used)
        - prompt: str (prompt used)
        - duration_s: float
        - attempts: int
        - ipadapter: bool (whether IPAdapter was used)
    """
    presets = load_presets()
    preset_config = presets.get(preset_name, presets.get("dreamshaperXL", {}))

    prompt = build_panel_prompt(panel, characters, style, all_panels=all_panels,
                               preset_name=preset_name)
    negative = get_negative_prompt_for_preset(preset_name, panel=panel)

    if seed < 0:
        seed = random.randint(0, 2**32 - 1)

    prefix = f"comicmaster_{panel.get('id', 'panel')}"

    # Determine whether to use IPAdapter (single or multi-character)
    use_ipadapter = False
    use_multi_ipadapter = False
    ref_filename = None
    ipadapter_weight = 0.65
    ipadapter_preset = "PLUS (high strength)"
    multi_char_refs_list = []

    if char_refs and panel.get("characters_present"):
        shot_type = panel.get("shot_type", "medium")
        base_weight = IPADAPTER_WEIGHTS.get(shot_type, 0.75)
        is_face_shot = shot_type in FACE_SHOT_TYPES

        # Apply face_weight_boost for face-focused shots
        if is_face_shot:
            base_weight = min(1.0, base_weight + FACE_WEIGHT_BOOST)

        default_preset = "PLUS FACE (portraits)" if is_face_shot else "PLUS (high strength)"

        # Collect all matching character refs (selecting best view per camera angle)
        camera_angle = panel.get("camera_angle", "eye_level")
        preferred_view = CAMERA_ANGLE_TO_REF_VIEW.get(camera_angle, "front")

        matching_refs = []
        for char_id in panel["characters_present"]:
            if char_id in char_refs:
                ref_info = char_refs[char_id]
                # Try to use the best view from multi-angle refs
                fname = None
                views = ref_info.get("views")
                if views and isinstance(views, dict):
                    # Prefer the view matching camera angle, fallback chain:
                    # preferred_view → front → first available → top-level comfyui_filename
                    view_data = views.get(preferred_view) or views.get("front")
                    if view_data:
                        fname = view_data.get("comfyui_filename")
                if not fname:
                    fname = ref_info.get("comfyui_filename")
                if fname:
                    matching_refs.append((char_id, ref_info, fname))

        if len(matching_refs) >= 2:
            # Multi-character IPAdapter path
            use_multi_ipadapter = True
            use_ipadapter = True

            # Weight distribution: primary gets full base_weight,
            # secondary gets ~67% of it, tertiary ~50%, etc.
            WEIGHT_MULTIPLIERS = [1.0, 0.67, 0.5, 0.4, 0.35]

            for i, (char_id, ref_info, fname) in enumerate(matching_refs):
                multiplier = WEIGHT_MULTIPLIERS[i] if i < len(WEIGHT_MULTIPLIERS) else 0.3
                weight = round(base_weight * multiplier, 2)
                # Clamp to reasonable range
                weight = max(0.2, min(0.8, weight))

                multi_char_refs_list.append({
                    "filename": fname,
                    "weight": weight,
                    "preset": default_preset,
                    "char_id": char_id,
                })

        elif len(matching_refs) == 1:
            # Single-character IPAdapter (original path)
            use_ipadapter = True
            char_id, ref_info, fname = matching_refs[0]
            ref_filename = fname
            ipadapter_weight = base_weight
            ipadapter_preset = default_preset

    # Resolve style LoRAs
    style_loras = get_style_loras(style)

    if use_multi_ipadapter:
        workflow = build_sdxl_multi_ipadapter_workflow(
            prompt=prompt,
            negative=negative,
            preset_config=preset_config,
            char_refs=multi_char_refs_list,
            width=width,
            height=height,
            seed=seed,
            prefix=prefix,
            loras=style_loras,
        )
    elif use_ipadapter:
        workflow = build_sdxl_ipadapter_workflow(
            prompt=prompt,
            negative=negative,
            preset_config=preset_config,
            ref_image_filename=ref_filename,
            ipadapter_weight=ipadapter_weight,
            ipadapter_preset=ipadapter_preset,
            width=width,
            height=height,
            seed=seed,
            prefix=prefix,
            loras=style_loras,
        )
    else:
        workflow = build_sdxl_workflow(
            prompt=prompt,
            negative=negative,
            preset_config=preset_config,
            width=width,
            height=height,
            seed=seed,
            prefix=prefix,
            loras=style_loras,
        )

    os.makedirs(output_dir, exist_ok=True)
    ensure_running()

    # --- Face validation retry loop ---
    face_validator = None
    face_max_retries = 2  # extra retries specifically for face validation
    face_validation_results = []

    # Only set up face validation if we have character refs with paths
    if char_refs and panel.get("characters_present"):
        try:
            from face_validator import FaceValidator, MAX_RETRIES as FV_MAX_RETRIES
            face_validator = FaceValidator()
            face_max_retries = FV_MAX_RETRIES
        except ImportError:
            pass  # face_validator not available, skip validation

    best_result = None
    best_similarity = -1.0

    for face_attempt in range(1 + face_max_retries):
        attempt_seed = seed if face_attempt == 0 else random.randint(0, 2**32 - 1)

        # Update seed in workflow
        if face_attempt > 0:
            # Rebuild workflow with new seed
            if use_multi_ipadapter:
                workflow = build_sdxl_multi_ipadapter_workflow(
                    prompt=prompt, negative=negative, preset_config=preset_config,
                    char_refs=multi_char_refs_list, width=width, height=height,
                    seed=attempt_seed, prefix=prefix, loras=style_loras,
                )
            elif use_ipadapter:
                workflow = build_sdxl_ipadapter_workflow(
                    prompt=prompt, negative=negative, preset_config=preset_config,
                    ref_image_filename=ref_filename, ipadapter_weight=ipadapter_weight,
                    ipadapter_preset=ipadapter_preset, width=width, height=height,
                    seed=attempt_seed, prefix=prefix, loras=style_loras,
                )
            else:
                workflow = build_sdxl_workflow(
                    prompt=prompt, negative=negative, preset_config=preset_config,
                    width=width, height=height, seed=attempt_seed, prefix=prefix,
                    loras=style_loras,
                )

        start = time.time()
        paths = generate_and_download(workflow, output_dir, timeout=timeout)
        duration = time.time() - start

        if not paths:
            raise RuntimeError(f"No images generated for panel {panel.get('id')}")

        current_result = {
            "path": paths[0],
            "seed": attempt_seed,
            "prompt": prompt,
            "duration_s": round(duration, 1),
            "attempts": face_attempt + 1,
            "ipadapter": use_ipadapter,
            "multi_ipadapter": use_multi_ipadapter,
            "loras": [l["filename"] for l in style_loras] if style_loras else [],
        }
        if use_multi_ipadapter:
            current_result["char_refs_used"] = [
                {"char_id": r.get("char_id", "?"), "weight": r["weight"]}
                for r in multi_char_refs_list
            ]

        # --- Face validation check ---
        if face_validator and char_refs:
            panel_passed = True
            panel_min_sim = 1.0
            validation_details = []

            for char_id in panel.get("characters_present", []):
                if char_id not in char_refs:
                    continue
                ref_info = char_refs[char_id]
                ref_path = ref_info.get("path")
                if not ref_path or not os.path.exists(ref_path):
                    continue

                val_result = face_validator.validate_panel(
                    ref_path, paths[0], char_id
                )
                validation_details.append(val_result)
                face_validation_results.append(val_result)

                if val_result.get("similarity") is not None:
                    if val_result["similarity"] < panel_min_sim:
                        panel_min_sim = val_result["similarity"]
                    if not val_result.get("passed"):
                        panel_passed = False

            current_result["face_validation"] = validation_details

            if panel_passed or face_attempt >= face_max_retries:
                # Passed or exhausted retries — use this result
                if panel_min_sim > best_similarity:
                    best_result = current_result
                    best_similarity = panel_min_sim
                if panel_passed:
                    break
            else:
                # Failed validation — track best and retry
                if panel_min_sim > best_similarity:
                    best_result = current_result
                    best_similarity = panel_min_sim
                continue
        else:
            # No face validation — use first result
            best_result = current_result
            break

    # Use the best result (highest face similarity or only result)
    result = best_result if best_result else current_result
    return result


def generate_all_panels(story_plan: dict, output_dir: str,
                        preset_name: str = None, width: int = 768,
                        height: int = 768, max_retries: int = 3,
                        timeout: int = 300,
                        char_refs: dict = None,
                        batch_optimize: bool = True) -> tuple[dict, list]:
    """
    Generate all panels from a story plan.

    When batch_optimize=True and panel count >= 6 with char_refs, panels are
    reordered to minimize model/IPAdapter switches in ComfyUI. Panels are
    generated in optimized order but results are keyed by original panel ID,
    so the caller always gets results mapped to the correct sequence.

    Args:
        story_plan: Full story plan dict.
        output_dir: Base output directory.
        preset_name: ComfyUI preset override.
        width: Panel width.
        height: Panel height.
        max_retries: Max retries per panel.
        timeout: Generation timeout per panel.
        char_refs: Optional dict mapping character_id → ref info dict
                   (from generate_character_ref). Enables IPAdapter consistency.
        batch_optimize: Reorder panels to minimize model switches (default True).

    Returns:
        results: dict of panel_id -> generation result
        failed: list of (panel_id, error_message) tuples
    """
    style = story_plan.get("style", "western")
    preset = preset_name or story_plan.get("preset", "dreamshaperXL")
    characters = story_plan.get("characters", [])
    panels = story_plan.get("panels", [])

    panels_dir = os.path.join(output_dir, "panels")
    os.makedirs(panels_dir, exist_ok=True)

    # --- Batch optimization ---
    use_optimization = batch_optimize and len(panels) >= 6 and bool(char_refs)
    unopt_switches = 0
    switches_saved = 0

    if use_optimization:
        unopt_switches = count_unoptimized_switches(panels, char_refs)
        generation_order = optimize_panel_order(panels, characters, char_refs)
        estimate = estimate_batch_time(panels, char_refs)

        # Count optimized switches
        opt_switches = 0
        prev_key = None
        for p in generation_order:
            key = p["_batch_info"]["char_key"]
            if prev_key is not None and prev_key != key:
                opt_switches += 1
            prev_key = key
        switches_saved = unopt_switches - opt_switches
    else:
        generation_order = panels

    total = len(generation_order)
    results = {}
    failed = []

    style_loras = get_style_loras(style)
    ipa_label = f" | IPAdapter: {len(char_refs)} refs" if char_refs else ""
    lora_label = f" | LoRAs: {len(style_loras)}" if style_loras else ""
    print(f"\n🎬 Generating {total} panels...")
    print(f"   Style: {style} | Preset: {preset} | Size: {width}x{height}{ipa_label}{lora_label}")
    if style_loras:
        for lora in style_loras:
            print(f"   🔧 LoRA: {lora['filename']} (model={lora.get('strength_model', 0.7)}, clip={lora.get('strength_clip', 0.7)})")
    if use_optimization:
        print(f"   🔧 Batch optimized: {unopt_switches} → {unopt_switches - switches_saved} model switches "
              f"(saving ~{switches_saved})")
        est_min = estimate["estimated_seconds"] / 60
        print(f"   ⏱️  Estimated time: ~{estimate['estimated_seconds']:.0f}s ({est_min:.1f}min)")
    print()

    times = []  # rolling durations for ETA
    batch_start = time.time()
    current_group = None

    for i, panel in enumerate(generation_order):
        panel_id = panel.get("id", f"panel_{i+1:02d}")

        # Show group transitions when batch-optimized
        if use_optimization:
            group = panel["_batch_info"]["group"]
            if group != current_group:
                current_group = group
                group_label = {
                    "no_ipadapter": "📭 No IPAdapter",
                    "single_ipadapter": "🔗 Single IPAdapter",
                    "multi_ipadapter": "🔗🔗 Multi IPAdapter",
                }.get(group, group)
                print(f"  --- {group_label} ---")

        print(f"  [{i+1}/{total}] Panel {panel_id}... ", end="", flush=True)

        last_error = None
        panel_start = time.time()

        for attempt in range(1, max_retries + 1):
            try:
                result = generate_panel(
                    panel=panel,
                    characters=characters,
                    style=style,
                    preset_name=preset,
                    output_dir=panels_dir,
                    char_refs=char_refs,
                    width=width,
                    height=height,
                    timeout=timeout,
                    all_panels=panels,
                )
                result["attempts"] = attempt
                results[panel_id] = result
                duration = time.time() - panel_start
                times.append(duration)
                ipa_tag = " 🔗" if result.get("ipadapter") else ""
                lora_tag = " 🔧" if result.get("loras") else ""
                print(f"✅ ({result['duration_s']}s){ipa_tag}{lora_tag}")
                break
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    print(f"⚠️ retry {attempt+1}...", end=" ", flush=True)
                    time.sleep(3)
                else:
                    duration = time.time() - panel_start
                    times.append(duration)
                    print(f"❌ {last_error}")
                    failed.append((panel_id, last_error))

        # Progress report every 10 panels (with ETA)
        if (i + 1) % 10 == 0 and i + 1 < total:
            elapsed = time.time() - batch_start
            # Rolling average of last 5 panels for ETA
            recent = times[-5:] if times else [0]
            avg = sum(recent) / len(recent) if recent else 0
            remaining = avg * (total - (i + 1))
            print(f"  📊 Progress: {i+1}/{total} ({elapsed:.0f}s elapsed, ~{remaining:.0f}s remaining)")

    total_time = time.time() - batch_start

    # Final summary with batch report
    print()
    report = generate_batch_report(
        list(results.values()),
        total_time=total_time,
        optimized=use_optimization,
        model_switches_saved=switches_saved,
    )
    print(report)

    return results, failed


# --- CLI ---

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate comic panels from a story plan")
    parser.add_argument("story_plan", help="Path to story_plan.json")
    parser.add_argument("--output", "-o", default=None, help="Output directory")
    parser.add_argument("--preset", "-p", default=None, help="ComfyUI preset name")
    parser.add_argument("--width", "-W", type=int, default=768)
    parser.add_argument("--height", "-H", type=int, default=768)
    parser.add_argument("--panel", help="Generate only this panel ID")
    parser.add_argument("--timeout", type=int, default=300)

    args = parser.parse_args()

    with open(args.story_plan) as f:
        plan = json.load(f)

    output_dir = args.output or f"/home/mcmuff/clawd/output/comicmaster/{plan.get('title', 'comic').lower().replace(' ', '_')}"

    if args.panel:
        # Generate single panel
        panel = next((p for p in plan["panels"] if p["id"] == args.panel), None)
        if not panel:
            print(f"Panel {args.panel} not found in story plan")
            sys.exit(1)

        result = generate_panel(
            panel=panel,
            characters=plan.get("characters", []),
            style=plan.get("style", "western"),
            preset_name=args.preset or plan.get("preset", "dreamshaperXL"),
            output_dir=os.path.join(output_dir, "panels"),
            width=args.width,
            height=args.height,
            timeout=args.timeout,
        )
        print(f"✅ {result['path']} (seed: {result['seed']}, {result['duration_s']}s)")
    else:
        # Generate all panels
        results, failed = generate_all_panels(
            story_plan=plan,
            output_dir=output_dir,
            preset_name=args.preset,
            width=args.width,
            height=args.height,
            timeout=args.timeout,
        )

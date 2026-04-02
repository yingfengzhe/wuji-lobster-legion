"""
ComicMaster – Story Plan validation and enrichment.

This module does NOT call any LLM.  Claude generates the story plan;
this script validates, enriches, and summarises it.
"""

from __future__ import annotations

import copy
import json
import math
import sys
from pathlib import Path

# Allow running as a standalone script *or* as part of the package.
try:
    from .utils import (
        available_templates,
        get_template,
        load_config,
        save_story_plan,
        template_slot_count,
    )
except ImportError:
    from utils import (  # type: ignore[no-redef]
        available_templates,
        get_template,
        load_config,
        save_story_plan,
        template_slot_count,
    )

# ── Constants ──────────────────────────────────────────────────────────────
VALID_STYLES = {"manga", "western", "cartoon", "realistic", "noir"}
VALID_CAMERA_ANGLES = {
    "eye_level", "low_angle", "high_angle", "birds_eye",
    "worms_eye", "dutch_angle", "over_the_shoulder",
}
VALID_SHOT_TYPES = {
    "extreme_close_up", "close_up", "medium_close_up",
    "medium", "medium_long", "long", "extreme_long",
}
VALID_MOODS = {
    "neutral", "happy", "sad", "tense", "mysterious",
    "dramatic", "comedic", "romantic", "dark", "hopeful",
}
VALID_LIGHTING = {
    "natural", "dramatic", "noir", "soft", "sunset",
    "moonlight", "neon", "studio",
}
VALID_NARRATIVE_WEIGHTS = {"low", "medium", "high", "splash"}
VALID_EMOTIONS = {
    "happy", "sad", "angry", "surprised", "scared",
    "determined", "tired", "confused", "neutral",
}
POSITION_HINTS = ["top_left", "top_right", "bottom_left", "bottom_right"]

# ── Panel Transition & Shape Constants ────────────────────────────────────
VALID_TRANSITIONS = {"standard", "wide", "none", "overlap"}
VALID_PANEL_SHAPES = {
    "rectangular", "diagonal", "wavy", "broken", "borderless",
}

# ── Sequential Composition Constants ──────────────────────────────────────
VALID_GAZE_DIRECTIONS = {"left", "right", "center", "up", "down"}
VALID_SUBJECT_POSITIONS = {"left_third", "center", "right_third"}
VALID_SPATIAL_RELATIONS = {
    "same_location", "cut_to", "time_skip", "flashback", "parallel",
}
VALID_FOCAL_POINTS = {
    "upper_left", "upper_right", "lower_left", "lower_right", "center",
}
VALID_COMPOSITION_OVERRIDES = {"symmetric", "dynamic", None}

# Shot types that count as "establishing" shots
ESTABLISHING_SHOTS = {"wide", "extreme_wide", "long", "extreme_long"}

# ── Pose Library (Biomechanical Descriptions) ─────────────────────────────
# Each entry: keywords (for fuzzy matching) → detailed pose prompt
POSE_LIBRARY = {
    "running": {
        "keywords": ["run", "running", "sprint", "sprinting", "dash", "dashing",
                      "rush", "rushing", "race", "racing", "bolting", "charging"],
        "pose": "mid-stride, left foot pushing off ground, right arm forward, torso leaning into motion, hair streaming behind, dynamic forward momentum",
    },
    "fighting_punch": {
        "keywords": ["punch", "punching", "hitting", "striking", "attack",
                      "attacking", "slug", "slugging", "smash"],
        "pose": "weight shifted to back foot, shoulder rotated forward, fist extending at chest height, other arm guarding face, core twisted, explosive force",
    },
    "fighting_kick": {
        "keywords": ["kick", "kicking", "roundhouse", "sweeping"],
        "pose": "standing leg bent for balance, kicking leg extended high, arms wide for counterbalance, torso rotated away from kick, dynamic motion arc",
    },
    "fighting_block": {
        "keywords": ["block", "blocking", "defend", "defending", "shield",
                      "shielding", "parry", "parrying", "guarding"],
        "pose": "arms raised in defensive guard, forearms crossed, knees bent, weight centered, chin tucked behind shoulder, braced for impact",
    },
    "jumping": {
        "keywords": ["jump", "jumping", "leap", "leaping", "vault", "vaulting",
                      "spring", "springing", "pounce", "pouncing"],
        "pose": "legs coiled underneath, arms thrust upward, body elongated mid-air, back arched, hair and clothing floating with momentum, upward trajectory",
    },
    "falling": {
        "keywords": ["fall", "falling", "plummet", "plummeting", "tumble",
                      "tumbling", "dropping", "plunge"],
        "pose": "arms flailing above head, body arched backward, legs bent, expression of shock, hair and clothing billowing upward, sense of gravity and velocity",
    },
    "sneaking": {
        "keywords": ["sneak", "sneaking", "creep", "creeping", "stealth",
                      "stealthy", "skulk", "skulking", "prowl", "prowling", "tiptoeing"],
        "pose": "crouched low, weight on balls of feet, one hand on wall, body pressed close to surface, head turned watchfully, muscles taut, silent motion",
    },
    "climbing": {
        "keywords": ["climb", "climbing", "scaling", "ascending", "clambering",
                      "scrambling"],
        "pose": "one hand gripping ledge above, other arm reaching up, feet braced against surface, body close to wall, muscles straining, upward gaze",
    },
    "crawling": {
        "keywords": ["crawl", "crawling", "dragging", "pulling oneself"],
        "pose": "on hands and knees, one arm reaching forward, opposite knee drawn up, head low, belly close to ground, determined forward progress",
    },
    "dodging": {
        "keywords": ["dodge", "dodging", "evade", "evading", "ducking",
                      "swerving", "sidestep", "sidestepping"],
        "pose": "body twisted mid-dodge, weight shifting to one side, head ducking below threat, one leg extended for push-off, arms pulled in tight, explosive lateral movement",
    },
    "standing_confident": {
        "keywords": ["confident", "powerful", "dominant", "commanding",
                      "authoritative", "proud", "heroic"],
        "pose": "weight on one hip, arms crossed, chin slightly raised, feet shoulder-width apart, squared shoulders, commanding presence",
    },
    "standing_casual": {
        "keywords": ["casual", "relaxed", "laid-back", "at ease", "idle"],
        "pose": "weight shifted to one leg, one hand in pocket, shoulders relaxed and slightly uneven, head tilted slightly, natural easy posture",
    },
    "standing_alert": {
        "keywords": ["alert", "on guard", "ready", "vigilant", "watchful",
                      "wary", "tense standing"],
        "pose": "feet apart in balanced stance, knees slightly bent, hands at sides ready, eyes scanning, body coiled with potential energy, alert posture",
    },
    "standing_menacing": {
        "keywords": ["menacing", "threatening", "intimidating", "looming", "ominous"],
        "pose": "looming forward, shoulders hunched, head lowered with eyes looking up, fists clenched at sides, shadow cast forward, imposing silhouette",
    },
    "sitting_thoughtful": {
        "keywords": ["thinking", "thoughtful", "contemplating", "pondering",
                      "reflecting", "musing", "brooding"],
        "pose": "leaning forward, elbows on knees, chin resting on interlaced fingers, shoulders slightly hunched, distant focused gaze, introspective posture",
    },
    "sitting_casual": {
        "keywords": ["sitting", "seated", "resting", "lounging", "chilling"],
        "pose": "leaning back, one arm draped over chair back, legs crossed or apart, relaxed shoulders, comfortable settled posture",
    },
    "sitting_defeated": {
        "keywords": ["defeated", "hopeless", "giving up", "despairing", "broken"],
        "pose": "slumped in chair, head hanging forward, hands limp in lap, shoulders collapsed inward, legs apart, boneless exhaustion",
    },
    "walking_casual": {
        "keywords": ["walk", "walking", "strolling", "wandering", "ambling",
                      "sauntering"],
        "pose": "relaxed stride, hands in pockets, slight forward lean, head slightly turned, natural arm swing, casual gait",
    },
    "walking_determined": {
        "keywords": ["marching", "striding", "determined walk", "purposeful",
                      "storming"],
        "pose": "long decisive strides, arms swinging with purpose, jaw set, eyes fixed forward, shoulders square, body cutting through space",
    },
    "walking_injured": {
        "keywords": ["limp", "limping", "hobbling", "staggering", "wounded walk",
                      "dragging"],
        "pose": "favoring one leg, hand clutching injury, body tilted to compensate, face grimacing, uneven shambling gait, visible strain",
    },
    "talking_animated": {
        "keywords": ["talking", "speaking", "explaining", "arguing", "debating",
                      "discussing", "gesturing"],
        "pose": "one hand gesturing at chest height, leaning slightly toward listener, eyebrows raised, expressive face, open body language, engaged posture",
    },
    "shouting": {
        "keywords": ["shout", "shouting", "yelling", "commanding", "ordering",
                      "screaming", "calling out"],
        "pose": "mouth wide open, neck tendons visible, one arm pointing or raised, body leaning forward aggressively, weight on front foot, powerful projection",
    },
    "whispering": {
        "keywords": ["whisper", "whispering", "murmuring", "secretive",
                      "conspiring", "hushed"],
        "pose": "leaning close to listener, hand cupped near mouth, body angled to shield conversation, eyes darting sideways, hunched shoulders, intimate proximity",
    },
    "looking_up_awe": {
        "keywords": ["awe", "amazement", "wonder", "astonished", "marveling",
                      "gazing up", "looking up"],
        "pose": "head tilted back, mouth slightly open, eyes wide, arms at sides, body leaning backward, face illuminated from above, overwhelmed wonder",
    },
    "exhausted": {
        "keywords": ["exhausted", "tired", "drained", "spent", "winded",
                      "fatigued", "out of breath", "panting"],
        "pose": "hunched over, hands on knees, head down, shoulders heaving, sweat visible, legs trembling slightly, ragged breathing posture",
    },
    "celebrating": {
        "keywords": ["celebrate", "celebrating", "victory", "triumph", "cheering",
                      "jubilant", "elated"],
        "pose": "fist pumped in air, other arm pulled down in victory gesture, face tilted up with wide grin, back arched, weight on toes, explosive joy",
    },
    "shocked": {
        "keywords": ["shocked", "horrified", "appalled", "stunned", "frozen",
                      "petrified", "terror"],
        "pose": "body rigid, hands raised near face, fingers splayed, eyes wide and pupils dilated, mouth open, slight backward lean, frozen in disbelief",
    },
    "grieving": {
        "keywords": ["grief", "grieving", "mourning", "crying", "weeping",
                      "sobbing", "devastated", "heartbroken"],
        "pose": "kneeling or doubled over, face buried in hands, shoulders shaking, body curled inward protectively, visible trembling, collapsed posture",
    },
    "surrendering": {
        "keywords": ["surrender", "surrendering", "giving in", "hands up",
                      "yielding", "submitting"],
        "pose": "hands raised above head, palms open and facing forward, shoulders pulled up, head slightly bowed, body still, non-threatening posture",
    },
    "pointing": {
        "keywords": ["pointing", "directing", "indicating", "showing",
                      "gesturing toward"],
        "pose": "arm fully extended, index finger pointing, body turned in direction of gesture, other hand on hip or at side, authoritative stance",
    },
    "holding_carrying": {
        "keywords": ["holding", "carrying", "cradling", "gripping", "clutching",
                      "embracing"],
        "pose": "arms wrapped around object or person, weight shifted to accommodate load, slight forward lean, protective posture, careful balance",
    },
}


def _match_pose_from_action(action_text: str) -> str | None:
    """Fuzzy-match an action description to a pose from the library.

    Scans the action text for keyword matches. Returns the best-matching
    pose prompt string, or None if no match exceeds threshold.
    """
    if not action_text:
        return None

    action_lower = action_text.lower()
    best_match = None
    best_score = 0

    for _pose_name, pose_data in POSE_LIBRARY.items():
        score = 0
        for keyword in pose_data["keywords"]:
            # Check for whole-word-ish match (keyword appears as substring)
            kw_lower = keyword.lower()
            if kw_lower in action_lower:
                # Prefer longer keyword matches (more specific)
                score += len(kw_lower)
        if score > best_score:
            best_score = score
            best_match = pose_data["pose"]

    # Require a minimum match quality (at least one 3+ char keyword matched)
    return best_match if best_score >= 3 else None


# ── Validation ─────────────────────────────────────────────────────────────
def validate_story_plan(plan: dict) -> tuple[bool, list[str]]:
    """Validate a story plan dict against the ComicMaster schema.

    Returns ``(is_valid, errors)`` where *errors* is a list of human-readable
    messages (empty when valid).
    """
    errors: list[str] = []

    # ---- Top-level required fields ----------------------------------------
    if not isinstance(plan.get("title"), str) or not plan["title"].strip():
        errors.append("Missing or empty required field: title")

    style = plan.get("style")
    if not isinstance(style, str) or style not in VALID_STYLES:
        errors.append(
            f"Invalid style '{style}'. Must be one of: {', '.join(sorted(VALID_STYLES))}"
        )

    # ---- Characters -------------------------------------------------------
    characters = plan.get("characters")
    if not isinstance(characters, list) or len(characters) < 1:
        errors.append("'characters' must be a non-empty list")
        char_ids: set[str] = set()
    else:
        char_ids = set()
        for i, ch in enumerate(characters):
            prefix = f"characters[{i}]"
            if not isinstance(ch, dict):
                errors.append(f"{prefix}: must be a dict")
                continue
            for field in ("id", "name", "visual_description"):
                if not isinstance(ch.get(field), str) or not ch[field].strip():
                    errors.append(f"{prefix}: missing or empty field '{field}'")
            cid = ch.get("id")
            if isinstance(cid, str):
                if cid in char_ids:
                    errors.append(f"{prefix}: duplicate character id '{cid}'")
                char_ids.add(cid)

    # ---- Panels -----------------------------------------------------------
    panels = plan.get("panels")
    if not isinstance(panels, list) or len(panels) < 1:
        errors.append("'panels' must be a non-empty list")
        panel_ids: set[str] = set()
    else:
        panel_ids = set()
        for i, p in enumerate(panels):
            prefix = f"panels[{i}]"
            if not isinstance(p, dict):
                errors.append(f"{prefix}: must be a dict")
                continue
            # Required scalar fields
            for field in ("id", "scene", "action"):
                if not isinstance(p.get(field), str) or not p[field].strip():
                    errors.append(f"{prefix}: missing or empty field '{field}'")
            if not isinstance(p.get("sequence"), int):
                errors.append(f"{prefix}: 'sequence' must be an int")
            # Panel id uniqueness
            pid = p.get("id")
            if isinstance(pid, str):
                if pid in panel_ids:
                    errors.append(f"{prefix}: duplicate panel id '{pid}'")
                panel_ids.add(pid)
            # characters_present
            cp = p.get("characters_present")
            if not isinstance(cp, list):
                errors.append(f"{prefix}: 'characters_present' must be a list")
            else:
                for cid in cp:
                    if cid not in char_ids:
                        errors.append(
                            f"{prefix}: character '{cid}' not found in characters list"
                        )
            # Optional dialogue validation
            dialogue = p.get("dialogue")
            if dialogue is not None:
                if not isinstance(dialogue, list):
                    errors.append(f"{prefix}: 'dialogue' must be a list if present")
                else:
                    for di, d in enumerate(dialogue):
                        dp = f"{prefix}.dialogue[{di}]"
                        if not isinstance(d, dict):
                            errors.append(f"{dp}: must be a dict")
                            continue
                        if not isinstance(d.get("character_id"), str):
                            errors.append(f"{dp}: missing 'character_id'")
                        elif d["character_id"] not in char_ids:
                            errors.append(
                                f"{dp}: character '{d['character_id']}' not in characters"
                            )
                        if not isinstance(d.get("text"), str) or not d["text"].strip():
                            errors.append(f"{dp}: missing or empty 'text'")

            # Optional expanded shot-list fields
            if "character_poses" in p and not isinstance(p["character_poses"], str):
                errors.append(f"{prefix}: 'character_poses' must be a string if present")
            if "character_emotions" in p:
                ce = p["character_emotions"]
                if isinstance(ce, str):
                    # single emotion keyword
                    pass
                elif isinstance(ce, list):
                    for ei, em in enumerate(ce):
                        if not isinstance(em, str):
                            errors.append(f"{prefix}.character_emotions[{ei}]: must be a string")
                else:
                    errors.append(f"{prefix}: 'character_emotions' must be a string or list if present")
            if "lighting" in p:
                if not isinstance(p["lighting"], str):
                    errors.append(f"{prefix}: 'lighting' must be a string if present")
            if "background_detail" in p:
                if not isinstance(p["background_detail"], str):
                    errors.append(f"{prefix}: 'background_detail' must be a string if present")
            if "narrative_weight" in p:
                nw = p["narrative_weight"]
                if not isinstance(nw, str) or nw not in VALID_NARRATIVE_WEIGHTS:
                    errors.append(
                        f"{prefix}: 'narrative_weight' must be one of "
                        f"{', '.join(sorted(VALID_NARRATIVE_WEIGHTS))}"
                    )

            # --- Panel transition & shape fields (all optional) ---
            if "transition_to_next" in p:
                tn = p["transition_to_next"]
                if not isinstance(tn, str) or tn not in VALID_TRANSITIONS:
                    errors.append(
                        f"{prefix}: 'transition_to_next' must be one of "
                        f"{', '.join(sorted(VALID_TRANSITIONS))}"
                    )
            if "panel_shape" in p:
                ps = p["panel_shape"]
                if not isinstance(ps, str) or ps not in VALID_PANEL_SHAPES:
                    errors.append(
                        f"{prefix}: 'panel_shape' must be one of "
                        f"{', '.join(sorted(VALID_PANEL_SHAPES))}"
                    )

            # --- Sequential composition fields (all optional) ---
            if "gaze_direction" in p:
                gd = p["gaze_direction"]
                if not isinstance(gd, str) or gd not in VALID_GAZE_DIRECTIONS:
                    errors.append(
                        f"{prefix}: 'gaze_direction' must be one of "
                        f"{', '.join(sorted(VALID_GAZE_DIRECTIONS))}"
                    )
            if "subject_position" in p:
                sp = p["subject_position"]
                if not isinstance(sp, str) or sp not in VALID_SUBJECT_POSITIONS:
                    errors.append(
                        f"{prefix}: 'subject_position' must be one of "
                        f"{', '.join(sorted(VALID_SUBJECT_POSITIONS))}"
                    )
            if "connects_to" in p:
                ct = p["connects_to"]
                if not isinstance(ct, str):
                    errors.append(f"{prefix}: 'connects_to' must be a string")
                # Note: we validate the target panel exists after all panels are parsed
            if "spatial_relation" in p:
                sr = p["spatial_relation"]
                if not isinstance(sr, str) or sr not in VALID_SPATIAL_RELATIONS:
                    errors.append(
                        f"{prefix}: 'spatial_relation' must be one of "
                        f"{', '.join(sorted(VALID_SPATIAL_RELATIONS))}"
                    )
            if "focal_point" in p:
                fp = p["focal_point"]
                if not isinstance(fp, str) or fp not in VALID_FOCAL_POINTS:
                    errors.append(
                        f"{prefix}: 'focal_point' must be one of "
                        f"{', '.join(sorted(VALID_FOCAL_POINTS))}"
                    )
            if "composition_override" in p:
                co = p["composition_override"]
                if co is not None and (not isinstance(co, str) or co not in ("symmetric", "dynamic")):
                    errors.append(
                        f"{prefix}: 'composition_override' must be "
                        f"'symmetric', 'dynamic', or null"
                    )

    # ---- Cross-panel references (connects_to) ----------------------------
    if isinstance(panels, list):
        for p in panels:
            ct = p.get("connects_to")
            if isinstance(ct, str) and ct not in panel_ids:
                errors.append(
                    f"Panel '{p.get('id')}': 'connects_to' references "
                    f"unknown panel '{ct}'"
                )

    # ---- Pages ------------------------------------------------------------
    pages = plan.get("pages")
    known_templates = available_templates()

    if not isinstance(pages, list):
        errors.append("'pages' must be a list")
    # Empty pages list is valid — auto_assign_layouts() will fill it during enrichment
    else:
        assigned_panels: dict[str, int] = {}  # panel_id → count of assignments
        for i, pg in enumerate(pages):
            prefix = f"pages[{i}]"
            if not isinstance(pg, dict):
                errors.append(f"{prefix}: must be a dict")
                continue
            if not isinstance(pg.get("page_number"), int):
                errors.append(f"{prefix}: 'page_number' must be an int")
            layout = pg.get("layout")
            if not isinstance(layout, str) or not layout.strip():
                errors.append(f"{prefix}: missing or empty 'layout'")
            elif layout not in known_templates:
                errors.append(
                    f"{prefix}: unknown layout '{layout}'. "
                    f"Available: {', '.join(known_templates)}"
                )
            else:
                # Check slot count matches panel count on this page
                slots = template_slot_count(layout)
                pids = pg.get("panel_ids", [])
                if slots is not None and len(pids) != slots:
                    errors.append(
                        f"{prefix}: layout '{layout}' has {slots} slots but "
                        f"{len(pids)} panel_ids provided"
                    )

            # Spread field (optional)
            if "spread" in pg:
                if not isinstance(pg["spread"], bool):
                    errors.append(f"{prefix}: 'spread' must be a boolean if present")

            pids = pg.get("panel_ids")
            if not isinstance(pids, list):
                errors.append(f"{prefix}: 'panel_ids' must be a list")
            else:
                for pid in pids:
                    if pid not in panel_ids:
                        errors.append(
                            f"{prefix}: panel '{pid}' not found in panels list"
                        )
                    assigned_panels[pid] = assigned_panels.get(pid, 0) + 1

        # Every panel must appear exactly once (only check if pages are defined)
        if len(pages) > 0:
            for pid in panel_ids:
                count = assigned_panels.get(pid, 0)
                if count == 0:
                    errors.append(f"Panel '{pid}' is not assigned to any page")
                elif count > 1:
                    errors.append(
                        f"Panel '{pid}' is assigned to {count} pages (must be exactly 1)"
                    )

    return (len(errors) == 0, errors)


# ── Costume Extraction ─────────────────────────────────────────────────────

# Keywords used to heuristically extract costume details from visual_description
_TOP_KEYWORDS = [
    "hoodie", "jacket", "shirt", "t-shirt", "tee", "blouse", "sweater",
    "vest", "coat", "tank top", "crop top", "jumpsuit", "uniform",
    "dress", "robe", "tunic", "armor", "suit", "blazer", "cardigan",
    "trench coat", "leather jacket", "denim jacket",
]
_BOTTOM_KEYWORDS = [
    "jeans", "pants", "trousers", "shorts", "skirt", "leggings",
    "sweatpants", "cargo pants", "slacks", "joggers",
]
_SHOES_KEYWORDS = [
    "sneakers", "boots", "shoes", "sandals", "heels", "loafers",
    "combat boots", "trainers", "flip-flops", "slippers",
]
_ACCESSORY_KEYWORDS = [
    "watch", "necklace", "bracelet", "earring", "earrings", "ring",
    "hat", "cap", "beanie", "glasses", "sunglasses", "goggles",
    "scarf", "gloves", "belt", "backpack", "bag", "satchel",
    "headband", "bandana", "mask", "pendant", "choker", "visor",
    "headphones", "earbuds", "tattoo",
]


def _extract_costume_from_description(description: str) -> dict:
    """Heuristically extract costume details from a visual description string.

    Returns a dict with keys: top, bottom, shoes, accessories (list).
    Values default to empty string / empty list if not detected.
    """
    if not description:
        return {"top": "", "bottom": "", "shoes": "", "accessories": []}

    desc_lower = description.lower()
    # Split into segments by comma, period, semicolon
    import re
    segments = re.split(r"[,;.]", desc_lower)
    segments = [s.strip() for s in segments if s.strip()]

    result: dict = {"top": "", "bottom": "", "shoes": "", "accessories": []}

    for segment in segments:
        # Check each category — first match wins per category
        if not result["top"]:
            for kw in _TOP_KEYWORDS:
                if kw in segment:
                    result["top"] = segment.strip()
                    break
        if not result["bottom"]:
            for kw in _BOTTOM_KEYWORDS:
                if kw in segment:
                    result["bottom"] = segment.strip()
                    break
        if not result["shoes"]:
            for kw in _SHOES_KEYWORDS:
                if kw in segment:
                    result["shoes"] = segment.strip()
                    break
        for kw in _ACCESSORY_KEYWORDS:
            if kw in segment and segment.strip() not in result["accessories"]:
                result["accessories"].append(segment.strip())
                break

    return result


# ── Enrichment ─────────────────────────────────────────────────────────────
def enrich_story_plan(plan: dict) -> dict:
    """Return a copy of *plan* with sensible defaults filled in."""
    plan = copy.deepcopy(plan)
    config = load_config()
    defaults = config.get("defaults", {})

    # Top-level defaults
    plan.setdefault("reading_direction", defaults.get("reading_direction", "ltr"))
    plan.setdefault("preset", defaults.get("preset", "dreamshaperXL"))

    # Character-level enrichment: costume_details
    for ch in plan.get("characters", []):
        if "costume_details" not in ch:
            # Attempt to extract costume_details from visual_description
            ch["costume_details"] = _extract_costume_from_description(
                ch.get("visual_description", "")
            )

    # Panel-level defaults
    panels = plan.get("panels", [])
    panels_sorted = sorted(panels, key=lambda p: p.get("sequence", 0))

    for panel in panels:
        panel.setdefault("camera_angle", "eye_level")
        panel.setdefault("shot_type", "medium")
        panel.setdefault("mood", "neutral")
        panel.setdefault("lighting", "natural")
        panel.setdefault("narrative_weight", "medium")

        # Dialogue defaults
        for di, d in enumerate(panel.get("dialogue", [])):
            d.setdefault("type", "speech")
            d.setdefault("position_hint", POSITION_HINTS[di % len(POSITION_HINTS)])

        # --- Pose auto-enrichment from action field ---
        if not panel.get("character_poses"):
            action = panel.get("action", "")
            matched_pose = _match_pose_from_action(action)
            if matched_pose:
                panel["character_poses"] = matched_pose

        # --- Composition override default ---
        panel.setdefault("composition_override", None)

    # --- Panel transition auto-enrichment ---
    _enrich_transitions(panels_sorted)

    # --- Panel shape auto-enrichment ---
    _enrich_panel_shapes(panels_sorted)

    # --- Narrative weight auto-estimation ---
    _enrich_narrative_weights(panels_sorted)

    # --- Sequential composition auto-enrichment ---
    _enrich_sequential_fields(panels_sorted)

    # --- Dialogue reading order ---
    _enrich_dialogue_positions(panels)

    # --- Color temperature auto-enrichment (narrative arc) ---
    _enrich_color_temperature(panels_sorted)

    # --- SFX style auto-enrichment ---
    _enrich_sfx_styles(panels)

    # --- Shot progression validation & auto-fix ---
    warnings = validate_shot_progression(panels_sorted, auto_fix=True)
    plan.setdefault("_enrichment_warnings", [])
    plan["_enrichment_warnings"].extend(warnings)

    # --- Splash validation ---
    splash_warnings = _validate_splash_usage(panels_sorted)
    plan["_enrichment_warnings"].extend(splash_warnings)

    return plan


def _enrich_transitions(panels_sorted: list[dict]) -> None:
    """Auto-enrich panel transition_to_next based on mood, action, and scene changes.

    Modifies panels in-place.  Only sets fields that are not already present.

    Rules:
    - Action scenes / intense mood → "none" or "overlap"
    - Scene changes / time skips → "wide"
    - Dialogue-heavy → "standard"
    - Default → "standard"
    """
    for idx, panel in enumerate(panels_sorted):
        if "transition_to_next" in panel:
            continue  # already set

        if idx >= len(panels_sorted) - 1:
            panel["transition_to_next"] = "standard"
            continue

        next_panel = panels_sorted[idx + 1]
        mood = panel.get("mood", "neutral").lower()
        action = panel.get("action", "").lower()
        has_dialogue = bool(panel.get("dialogue"))

        # Check for scene change
        current_scene = panel.get("scene", "").strip().lower()
        next_scene = next_panel.get("scene", "").strip().lower()
        spatial_rel = panel.get("spatial_relation", "")

        is_scene_change = False
        if current_scene and next_scene:
            curr_words = set(current_scene.split()) - {"a", "an", "the", "at", "in", "on", "of"}
            next_words = set(next_scene.split()) - {"a", "an", "the", "at", "in", "on", "of"}
            overlap = curr_words & next_words
            if len(overlap) < 2 and current_scene != next_scene:
                is_scene_change = True
        if spatial_rel in ("cut_to", "time_skip", "flashback"):
            is_scene_change = True

        # Action keywords
        action_keywords = {"fight", "chase", "attack", "explode", "run", "dodge",
                           "punch", "kick", "shoot", "crash", "battle", "combat",
                           "strike", "slash", "grab", "throw"}
        is_action = any(kw in action for kw in action_keywords)
        is_intense_mood = mood in {"intense", "chaotic", "tense", "dramatic"}

        if is_scene_change:
            panel["transition_to_next"] = "wide"
        elif is_action and is_intense_mood:
            panel["transition_to_next"] = "overlap"
        elif is_action or is_intense_mood:
            panel["transition_to_next"] = "none"
        elif has_dialogue:
            panel["transition_to_next"] = "standard"
        else:
            panel["transition_to_next"] = "standard"


def _enrich_panel_shapes(panels_sorted: list[dict]) -> None:
    """Auto-enrich panel_shape based on mood and narrative_weight.

    Modifies panels in-place.  Only sets fields that are not already present.

    Rules:
    - mood="chaotic"/"intense" → diagonal
    - mood="dreamy"/"nostalgic" → wavy
    - mood="powerful"/"breakthrough" → broken
    - narrative_weight="splash" → borderless
    - Default → rectangular
    """
    for panel in panels_sorted:
        if "panel_shape" in panel:
            continue  # already set

        mood = panel.get("mood", "neutral").lower()
        weight = panel.get("narrative_weight", "medium")
        action = panel.get("action", "").lower()

        if weight == "splash":
            panel["panel_shape"] = "borderless"
        elif mood in ("chaotic", "intense"):
            panel["panel_shape"] = "diagonal"
        elif mood in ("dreamy", "nostalgic"):
            panel["panel_shape"] = "wavy"
        elif mood in ("powerful", "breakthrough"):
            panel["panel_shape"] = "broken"
        elif "breakthrough" in action or "shatter" in action or "break" in action:
            panel["panel_shape"] = "broken"
        elif "dream" in action or "flashback" in action or "memory" in action:
            panel["panel_shape"] = "wavy"
        else:
            panel["panel_shape"] = "rectangular"


def _enrich_narrative_weights(panels_sorted: list[dict]) -> None:
    """Auto-estimate narrative_weight for panels that use the default 'medium'.

    Only overrides if the panel still has the basic default and there's strong
    evidence for a different weight.  Modifies panels in-place.
    """
    for panel in panels_sorted:
        current = panel.get("narrative_weight", "medium")
        # Only auto-adjust if it was set to the default by the enrichment
        # (i.e., not explicitly set by the user).  We check if it was *not*
        # in the original plan by looking for the _original_weight marker.
        if "_original_narrative_weight" in panel:
            continue  # user explicitly set it

        mood = panel.get("mood", "neutral").lower()
        action = panel.get("action", "").lower()
        shot_type = panel.get("shot_type", "medium").lower()

        # High-weight indicators
        high_keywords = {"reveal", "confront", "transform", "discover", "final",
                         "climax", "explosion", "battle", "death", "sacrifice"}
        high_moods = {"dramatic", "intense", "dark", "powerful"}

        # Low-weight indicators
        low_keywords = {"walk", "sit", "wait", "look", "stand", "pause"}
        low_moods = {"neutral", "calm", "peaceful"}

        score = 0

        if any(kw in action for kw in high_keywords):
            score += 2
        elif any(kw in action for kw in low_keywords) and not panel.get("dialogue"):
            score -= 1

        if mood in high_moods:
            score += 1
        elif mood in low_moods:
            score -= 1

        if shot_type in ("extreme_close_up", "close_up"):
            score += 1
        elif shot_type in ("extreme_long",):
            score -= 0.5

        if current == "medium":
            if score >= 2:
                panel["narrative_weight"] = "high"
            elif score <= -1:
                panel["narrative_weight"] = "low"


def _validate_splash_usage(panels: list[dict]) -> list[str]:
    """Validate that splash pages are used only for narrative peaks.

    Returns warnings for inappropriate splash usage.
    """
    warnings = []
    passive_moods = {"neutral", "calm", "peaceful", "relaxed", "happy"}

    for panel in panels:
        if panel.get("narrative_weight") != "splash":
            continue
        mood = panel.get("mood", "neutral").lower()
        action = panel.get("action", "").lower()
        pid = panel.get("id", "unknown")

        if mood in passive_moods:
            warnings.append(
                f"Splash validation: panel '{pid}' uses splash with passive mood "
                f"'{mood}'. Splash pages should be reserved for narrative peaks."
            )

        passive_actions = ["sitting", "standing", "waiting", "resting", "sleeping"]
        if any(pa in action for pa in passive_actions):
            warnings.append(
                f"Splash validation: panel '{pid}' uses splash for passive action "
                f"'{action[:50]}'. Consider 'high' weight instead."
            )

    return warnings


def _enrich_sequential_fields(panels_sorted: list[dict]) -> None:
    """Auto-enrich sequential composition fields on panels (sorted by sequence).

    Modifies panels in-place.  Only sets fields that are not already present.
    """
    panel_map = {p["id"]: p for p in panels_sorted if "id" in p}

    for idx, panel in enumerate(panels_sorted):
        seq = panel.get("sequence", idx + 1)
        has_dialogue = bool(panel.get("dialogue"))
        dialogue = panel.get("dialogue", [])

        # --- gaze_direction ---
        if "gaze_direction" not in panel:
            if has_dialogue and len(dialogue) >= 1:
                # For dialogue panels: alternate left/right based on who speaks
                # If it's a conversation, the speaker's gaze should face the
                # other character (left/right alternating)
                speaker_id = dialogue[0].get("character_id", "")
                # Use a simple hash-based approach: even hash → right, odd → left
                speaker_hash = sum(ord(c) for c in speaker_id)
                panel["gaze_direction"] = "right" if speaker_hash % 2 == 0 else "left"
            else:
                # Non-dialogue panels: alternate based on sequence
                panel["gaze_direction"] = "right" if seq % 2 == 1 else "left"

        # --- subject_position ---
        if "subject_position" not in panel:
            if panel.get("narrative_weight") == "splash":
                panel["subject_position"] = "center"
            elif seq % 2 == 1:
                panel["subject_position"] = "right_third"
            else:
                panel["subject_position"] = "left_third"

        # --- connects_to ---
        if "connects_to" not in panel and idx < len(panels_sorted) - 1:
            next_panel = panels_sorted[idx + 1]
            panel["connects_to"] = next_panel.get("id", "")

        # --- spatial_relation ---
        if "spatial_relation" not in panel and idx < len(panels_sorted) - 1:
            next_panel = panels_sorted[idx + 1]
            current_scene = panel.get("scene", "").strip().lower()
            next_scene = next_panel.get("scene", "").strip().lower()
            # Detect same location by checking if scenes share significant words
            if current_scene and next_scene:
                curr_words = set(current_scene.split())
                next_words = set(next_scene.split())
                # Remove very common words
                stopwords = {"a", "an", "the", "at", "in", "on", "of", "and", "with"}
                curr_sig = curr_words - stopwords
                next_sig = next_words - stopwords
                overlap = curr_sig & next_sig
                if len(overlap) >= 2 or current_scene == next_scene:
                    panel["spatial_relation"] = "same_location"
                else:
                    panel["spatial_relation"] = "cut_to"
            else:
                panel["spatial_relation"] = "cut_to"

        # --- focal_point ---
        if "focal_point" not in panel:
            # Default focal point based on subject position and gaze
            subj_pos = panel.get("subject_position", "center")
            gaze = panel.get("gaze_direction", "center")
            if subj_pos == "left_third":
                panel["focal_point"] = "upper_left" if gaze in ("up", "left") else "lower_left"
            elif subj_pos == "right_third":
                panel["focal_point"] = "upper_right" if gaze in ("up", "right") else "lower_right"
            else:
                panel["focal_point"] = "center"


def _enrich_color_temperature(panels_sorted: list[dict]) -> None:
    """Auto-enrich color_temp_override on panels based on narrative arc.

    Within action sequences (consecutive panels with moods like tense, dramatic),
    applies an automatic warm→cool temperature shift to build visual tension.

    Modifies panels in-place. Only sets color_temp_override if not already set.
    """
    action_moods = {"tense", "dramatic", "dark"}
    sequence_start: int | None = None

    for idx, panel in enumerate(panels_sorted):
        mood = panel.get("mood", "neutral")

        if mood in action_moods:
            if sequence_start is None:
                sequence_start = idx
        else:
            # End of action sequence — apply temp shift
            if sequence_start is not None:
                seq_len = idx - sequence_start
                if seq_len >= 2:
                    # Apply warm→cool shift across the sequence
                    for j in range(sequence_start, idx):
                        p = panels_sorted[j]
                        if "color_temp_override" not in p:
                            t = (j - sequence_start) / max(1, seq_len - 1)
                            # Smoothstep easing: warm (0.6) → cool (-0.6)
                            t_smooth = 3 * t * t - 2 * t * t * t
                            p["color_temp_override"] = round(
                                0.6 - 1.2 * t_smooth, 3
                            )
                sequence_start = None

    # Handle trailing action sequence
    if sequence_start is not None:
        seq_len = len(panels_sorted) - sequence_start
        if seq_len >= 2:
            for j in range(sequence_start, len(panels_sorted)):
                p = panels_sorted[j]
                if "color_temp_override" not in p:
                    t = (j - sequence_start) / max(1, seq_len - 1)
                    t_smooth = 3 * t * t - 2 * t * t * t
                    p["color_temp_override"] = round(0.6 - 1.2 * t_smooth, 3)


def _enrich_sfx_styles(panels: list[dict]) -> None:
    """Auto-enrich SFX dialogue entries with sfx_style based on text content.

    Scans dialogue entries of type 'sfx' and auto-assigns an sfx_style
    ('flat', 'radial', 'curved', 'impact') if not already set.

    Also enriches sfx entries with scene_mood_tone for color matching.

    Modifies panels in-place.
    """
    # SFX text → style mapping (same as speech_bubbles._SFX_STYLE_MAP)
    sfx_map = {
        "BOOM": "impact", "CRASH": "radial", "BANG": "impact",
        "KABOOM": "impact", "BLAM": "radial", "KAPOW": "impact",
        "WHOOSH": "curved", "SWOOSH": "curved", "WHIP": "curved",
        "ZOOM": "curved", "VROOM": "curved", "SWISH": "curved",
        "CRACK": "flat", "SNAP": "flat", "CLICK": "flat",
        "CLACK": "flat", "POP": "flat", "THUD": "flat", "THWACK": "flat",
        "ZAP": "radial", "BZZT": "radial", "ZZZZAP": "radial",
        "SIZZLE": "radial", "CRACKLE": "radial",
        "SPLASH": "radial", "RUMBLE": "impact", "SCREECH": "curved",
        "ROAR": "impact", "SHATTER": "radial",
    }

    # Mood → mood_tone for SFX color matching
    mood_tone_map = {
        "tense": "warm", "calm": "cool", "mysterious": "cool",
        "cheerful": "warm", "noir": "cool", "dark": "dark",
        "hopeful": "warm", "dramatic": "warm", "neutral": "neutral",
        "happy": "warm", "sad": "cool",
    }

    for panel in panels:
        panel_mood = panel.get("mood", "neutral")
        mood_tone = mood_tone_map.get(panel_mood, "neutral")

        for d in panel.get("dialogue", []):
            if d.get("type") != "sfx":
                continue

            text = d.get("text", "").strip().upper().rstrip("!?.")

            # Auto-assign sfx_style
            if "sfx_style" not in d:
                matched_style = "flat"
                for keyword, style in sfx_map.items():
                    if text.startswith(keyword) or text == keyword:
                        matched_style = style
                        break
                d["sfx_style"] = matched_style

            # Auto-assign scene_mood_tone for color matching
            if "scene_mood_tone" not in d:
                d["scene_mood_tone"] = mood_tone


def _enrich_dialogue_positions(panels: list[dict]) -> None:
    """Validate and set dialogue position_hints for correct reading order.

    Reading order: top_left → top_right → bottom_left → bottom_right.
    The first speaker should be top_left, second top_right, etc.
    """
    for panel in panels:
        dialogue = panel.get("dialogue", [])
        if len(dialogue) <= 1:
            continue

        # Assign position hints based on speaker order
        # First speaker = higher + lefter position
        reading_order = ["top_left", "top_right", "bottom_left", "bottom_right"]
        for di, d in enumerate(dialogue):
            if di < len(reading_order):
                d["position_hint"] = reading_order[di]


def validate_shot_progression(
    panels_sorted: list[dict],
    auto_fix: bool = False,
) -> list[str]:
    """Validate shot type progression across panels.

    Checks:
    1. No more than 3 consecutive panels with the same shot type
    2. Each new scene should start with an establishing shot (wide/extreme_wide/long/extreme_long)
    3. Dialogue speaker changes should be accompanied by shot type changes

    Args:
        panels_sorted: Panels sorted by sequence.
        auto_fix: If True, automatically fix detected issues.

    Returns:
        List of warning strings.
    """
    warnings: list[str] = []

    if not panels_sorted:
        return warnings

    # --- Check 1: No >3 consecutive identical shot types ---
    run_length = 1
    for i in range(1, len(panels_sorted)):
        if panels_sorted[i].get("shot_type") == panels_sorted[i - 1].get("shot_type"):
            run_length += 1
            if run_length > 3:
                pid = panels_sorted[i].get("id", f"seq{panels_sorted[i].get('sequence')}")
                shot = panels_sorted[i].get("shot_type", "?")
                warnings.append(
                    f"Shot repetition: panel '{pid}' is the {run_length}th "
                    f"consecutive '{shot}' shot"
                )
                if auto_fix:
                    # Vary the shot type
                    alternatives = ["medium", "close_up", "medium_close_up", "long"]
                    for alt in alternatives:
                        if alt != shot:
                            panels_sorted[i]["shot_type"] = alt
                            panels_sorted[i].setdefault("_auto_fixed", []).append(
                                f"shot_type: {shot} → {alt}"
                            )
                            break
                    run_length = 1  # reset counter
        else:
            run_length = 1

    # --- Check 2: Scene should open with an establishing shot ---
    seen_scenes: set[str] = set()
    for panel in panels_sorted:
        scene = panel.get("scene", "").strip().lower()
        if not scene:
            continue
        # Detect "new scene" by a scene string we haven't seen yet
        scene_key = scene[:40]  # use first 40 chars as key
        if scene_key not in seen_scenes:
            seen_scenes.add(scene_key)
            shot = panel.get("shot_type", "medium")
            if shot not in ESTABLISHING_SHOTS:
                pid = panel.get("id", f"seq{panel.get('sequence')}")
                warnings.append(
                    f"Scene opening: panel '{pid}' starts a new scene "
                    f"with '{shot}' instead of an establishing shot"
                )
                if auto_fix:
                    old_shot = panel.get("shot_type", "medium")
                    panel["shot_type"] = "long"
                    panel.setdefault("_auto_fixed", []).append(
                        f"shot_type: {old_shot} → long (scene opener)"
                    )

    # --- Check 3: Dialogue speaker change should vary shot type ---
    prev_speaker = None
    prev_shot = None
    for panel in panels_sorted:
        dialogue = panel.get("dialogue", [])
        if not dialogue:
            prev_speaker = None
            prev_shot = None
            continue
        current_speaker = dialogue[0].get("character_id", "")
        current_shot = panel.get("shot_type", "medium")
        if prev_speaker and current_speaker and prev_speaker != current_speaker:
            if current_shot == prev_shot:
                pid = panel.get("id", f"seq{panel.get('sequence')}")
                warnings.append(
                    f"Dialogue monotony: panel '{pid}' switches speaker "
                    f"but keeps same shot type '{current_shot}'"
                )
                if auto_fix:
                    # Alternate between medium and medium_close_up for dialogue
                    new_shot = "medium_close_up" if current_shot == "medium" else "medium"
                    panel["shot_type"] = new_shot
                    panel.setdefault("_auto_fixed", []).append(
                        f"shot_type: {current_shot} → {new_shot} (dialogue variation)"
                    )
        prev_speaker = current_speaker
        prev_shot = panel.get("shot_type", "medium")

    return warnings


# ── Auto-layout ────────────────────────────────────────────────────────────
def auto_assign_layouts(plan: dict) -> dict:
    """If pages are empty/missing, automatically group panels into pages.

    Strategy:
    - Default unit is ``page_2x2`` (4 slots).
    - ``<= 4`` panels → single ``page_2x2``.
    - ``<= 8`` panels → two ``page_2x2`` (or one ``page_2x4`` if exactly 8).
    - Larger counts: fill ``page_2x2`` (4) and ``page_2x3`` (6) as needed.
    - If the first panel has ``narrative_weight == "high"``, the first page
      becomes ``page_action`` (4 slots).
    """
    plan = copy.deepcopy(plan)
    panels = plan.get("panels", [])
    if not panels:
        return plan

    # Sort by sequence
    panels_sorted = sorted(panels, key=lambda p: p.get("sequence", 0))
    panel_ids = [p["id"] for p in panels_sorted]
    total = len(panel_ids)

    pages: list[dict] = []
    idx = 0  # pointer into panel_ids
    page_num = 1

    # First-page override?
    first_panel_high = panels_sorted[0].get("narrative_weight") == "high" if panels_sorted else False
    first_page_layout = "page_action" if first_panel_high and total >= 4 else None

    if first_page_layout:
        slots = template_slot_count(first_page_layout) or 4
        pages.append({
            "page_number": page_num,
            "layout": first_page_layout,
            "panel_ids": panel_ids[idx:idx + slots],
        })
        idx += slots
        page_num += 1

    remaining = total - idx

    if remaining <= 0:
        pass  # all panels already assigned
    elif remaining <= 4:
        # Pad list for a full page_2x2 is NOT needed — we allow fewer only if
        # we have that exact template.  But spec says slot count must match,
        # so we try to find a matching template.
        layout = _best_layout_for(remaining)
        pages.append({
            "page_number": page_num,
            "layout": layout,
            "panel_ids": panel_ids[idx:idx + remaining],
        })
        idx += remaining
        page_num += 1
    elif remaining == 8:
        # One page_2x4 or two page_2x2
        pages.append({
            "page_number": page_num,
            "layout": "page_2x4",
            "panel_ids": panel_ids[idx:idx + 8],
        })
        idx += 8
        page_num += 1
    else:
        # Fill with page_2x2 (4) and page_2x3 (6)
        while idx < total:
            left = total - idx
            if left >= 6 and (left % 4 != 0):
                # Use page_2x3 to avoid awkward remainders
                layout, slots = "page_2x3", 6
            elif left >= 4:
                layout, slots = "page_2x2", 4
            else:
                layout = _best_layout_for(left)
                slots = template_slot_count(layout) or left
            # Don't overshoot
            take = min(slots, left)
            pages.append({
                "page_number": page_num,
                "layout": layout,
                "panel_ids": panel_ids[idx:idx + take],
            })
            idx += take
            page_num += 1

    plan["pages"] = pages
    return plan


def _best_layout_for(n: int) -> str:
    """Pick the best template for exactly *n* panels."""
    # Map slot count → preferred layout name
    slot_map: dict[int, str] = {}
    for name in available_templates():
        sc = template_slot_count(name)
        if sc is not None:
            # Prefer simpler/smaller names (alphabetical as tiebreaker)
            if sc not in slot_map or name < slot_map[sc]:
                slot_map[sc] = name

    if n in slot_map:
        return slot_map[n]

    # Fallback: smallest template that fits
    for count in sorted(slot_map):
        if count >= n:
            return slot_map[count]

    # Ultimate fallback
    return "page_2x2"


# ── Summary ────────────────────────────────────────────────────────────────
def plan_summary(plan: dict) -> str:
    """Return a human-readable summary of the story plan."""
    lines: list[str] = []
    lines.append(f"📖 Title:      {plan.get('title', '(untitled)')}")
    lines.append(f"🎨 Style:      {plan.get('style', '?')}")
    lines.append(f"📐 Direction:  {plan.get('reading_direction', '?')}")
    lines.append(f"👤 Characters: {len(plan.get('characters', []))}")
    lines.append(f"🖼  Panels:     {len(plan.get('panels', []))}")
    lines.append(f"📄 Pages:      {len(plan.get('pages', []))}")
    lines.append("")
    lines.append("── Panel overview ──")
    for p in sorted(plan.get("panels", []), key=lambda x: x.get("sequence", 0)):
        desc = p.get("action", p.get("scene", ""))[:60]
        chars = ", ".join(p.get("characters_present", []))
        lines.append(f"  [{p.get('id', '?')}] seq {p.get('sequence', '?')}: {desc}")
        if chars:
            lines.append(f"         characters: {chars}")
        # Shot-list details
        extras = []
        if p.get("lighting") and p["lighting"] != "natural":
            extras.append(f"🔦 {p['lighting']}")
        if p.get("narrative_weight") and p["narrative_weight"] != "medium":
            extras.append(f"⚖️ {p['narrative_weight']}")
        if p.get("character_emotions"):
            emo = p["character_emotions"]
            emo_str = ", ".join(emo) if isinstance(emo, list) else emo
            extras.append(f"😶 {emo_str}")
        if p.get("character_poses"):
            extras.append(f"🧍 {p['character_poses']}")
        if p.get("background_detail"):
            extras.append(f"🏞  {p['background_detail'][:50]}")
        if extras:
            lines.append(f"         {' | '.join(extras)}")
        # Layout composition fields
        layout_extras = []
        if p.get("panel_shape") and p["panel_shape"] != "rectangular":
            layout_extras.append(f"🔷 shape:{p['panel_shape']}")
        if p.get("transition_to_next") and p["transition_to_next"] != "standard":
            layout_extras.append(f"↔️ transition:{p['transition_to_next']}")
        if layout_extras:
            lines.append(f"         {' | '.join(layout_extras)}")
        # Sequential composition fields
        seq_extras = []
        if p.get("gaze_direction"):
            seq_extras.append(f"👁 gaze:{p['gaze_direction']}")
        if p.get("subject_position"):
            seq_extras.append(f"📍 pos:{p['subject_position']}")
        if p.get("spatial_relation"):
            seq_extras.append(f"🔗 {p['spatial_relation']}")
        if p.get("focal_point"):
            seq_extras.append(f"🎯 {p['focal_point']}")
        if seq_extras:
            lines.append(f"         {' | '.join(seq_extras)}")
        if p.get("dialogue"):
            for d in p["dialogue"]:
                speaker = d.get("character_id", "?")
                text = d.get("text", "")[:50]
                lines.append(f'         💬 {speaker}: "{text}"')

    # Show enrichment warnings if any
    warn = plan.get("_enrichment_warnings", [])
    if warn:
        lines.append("")
        lines.append("── ⚠️ Enrichment warnings ──")
        for w in warn:
            lines.append(f"  ⚠️ {w}")

    return "\n".join(lines)


# ── CLI test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # 1. Create a sample 4-panel story plan
    sample_plan: dict = {
        "title": "The Last Robot",
        "style": "cartoon",
        "characters": [
            {
                "id": "robot",
                "name": "Rusty",
                "visual_description": "Small round robot with rusty orange plating, one big blue eye, stubby legs",
            },
            {
                "id": "cat",
                "name": "Mochi",
                "visual_description": "Fluffy white cat with a black spot on left ear, bright green eyes",
            },
        ],
        "panels": [
            {
                "id": "p1",
                "sequence": 1,
                "scene": "Abandoned junkyard at sunset",
                "action": "Rusty sits alone on a pile of scrap, looking at the sky",
                "characters_present": ["robot"],
                "mood": "sad",
                "narration": "In a world where robots were forgotten...",
            },
            {
                "id": "p2",
                "sequence": 2,
                "scene": "Same junkyard, ground level",
                "action": "Mochi walks into frame, curious, tail up",
                "characters_present": ["cat"],
                "camera_angle": "low_angle",
                "shot_type": "medium_long",
                "dialogue": [
                    {"character_id": "cat", "text": "Mrow?", "type": "speech"},
                ],
            },
            {
                "id": "p3",
                "sequence": 3,
                "scene": "Close on Rusty's face",
                "action": "Rusty looks down surprised, eye glowing brighter",
                "characters_present": ["robot", "cat"],
                "camera_angle": "eye_level",
                "shot_type": "close_up",
                "mood": "hopeful",
                "dialogue": [
                    {"character_id": "robot", "text": "A... friend?", "type": "speech"},
                ],
            },
            {
                "id": "p4",
                "sequence": 4,
                "scene": "Wide shot, junkyard at dusk",
                "action": "Mochi curled up on Rusty's lap, both content",
                "characters_present": ["robot", "cat"],
                "shot_type": "long",
                "mood": "happy",
                "narration": "Sometimes the smallest things reboot your heart.",
            },
        ],
        "pages": [
            {
                "page_number": 1,
                "layout": "page_2x2",
                "panel_ids": ["p1", "p2", "p3", "p4"],
            },
        ],
    }

    # 2. Validate
    print("=" * 60)
    print("STEP 1: Validate")
    print("=" * 60)
    is_valid, errors = validate_story_plan(sample_plan)
    if is_valid:
        print("✅ Story plan is valid!")
    else:
        print("❌ Validation errors:")
        for e in errors:
            print(f"   • {e}")

    # 3. Enrich
    print("\n" + "=" * 60)
    print("STEP 2: Enrich")
    print("=" * 60)
    enriched = enrich_story_plan(sample_plan)
    print(f"Added defaults — preset: {enriched.get('preset')}, "
          f"direction: {enriched.get('reading_direction')}")
    for p in enriched["panels"]:
        print(f"  [{p['id']}] camera={p.get('camera_angle')}, "
              f"shot={p.get('shot_type')}, mood={p.get('mood')}")

    # 4. Summary
    print("\n" + "=" * 60)
    print("STEP 3: Summary")
    print("=" * 60)
    print(plan_summary(enriched))

    # 5. Save
    print("\n" + "=" * 60)
    print("STEP 4: Save")
    print("=" * 60)
    out_dir = Path("/home/mcmuff/clawd/output/comicmaster")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "test_story_plan.json"
    out_path.write_text(json.dumps(enriched, indent=2, ensure_ascii=False))
    print(f"Saved enriched plan → {out_path}")

    # Bonus: test auto_assign_layouts with pages stripped
    print("\n" + "=" * 60)
    print("BONUS: auto_assign_layouts (pages removed)")
    print("=" * 60)
    plan_no_pages = {k: v for k, v in sample_plan.items() if k != "pages"}
    auto_plan = auto_assign_layouts(plan_no_pages)
    for pg in auto_plan["pages"]:
        print(f"  Page {pg['page_number']}: {pg['layout']} → {pg['panel_ids']}")

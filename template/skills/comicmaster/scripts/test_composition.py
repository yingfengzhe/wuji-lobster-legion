#!/usr/bin/env python3
"""
Tests for Sequential Composition Rules in ComicMaster.

Tests story_planner enrichment (gaze_direction, subject_position, connects_to,
spatial_relation, focal_point) and panel_generator composition tag generation.
"""

import copy
import json
import sys
from pathlib import Path

# Add our own scripts to path
sys.path.insert(0, str(Path(__file__).parent))

from story_planner import (
    validate_story_plan,
    enrich_story_plan,
    validate_shot_progression,
    _enrich_sequential_fields,
    _enrich_dialogue_positions,
    VALID_GAZE_DIRECTIONS,
    VALID_SUBJECT_POSITIONS,
    VALID_SPATIAL_RELATIONS,
    VALID_FOCAL_POINTS,
)
from panel_generator import (
    _get_sequential_composition_tags,
    build_panel_prompt,
    COMPOSITION_TEMPLATES,
    FOCAL_POINT_TAGS,
    SUBJECT_POSITION_TAGS,
    GAZE_DIRECTION_TAGS,
)


# ── Test Fixtures ──────────────────────────────────────────────────────────

def make_base_plan():
    """Minimal valid story plan without sequential fields."""
    return {
        "title": "Test Comic",
        "style": "western",
        "characters": [
            {"id": "hero", "name": "Hero", "visual_description": "tall warrior with red cape"},
            {"id": "villain", "name": "Villain", "visual_description": "dark figure with glowing eyes"},
        ],
        "panels": [
            {
                "id": "p1", "sequence": 1,
                "scene": "Castle courtyard at dawn",
                "action": "Hero stands at the gate, looking outward",
                "characters_present": ["hero"],
                "shot_type": "long",
                "mood": "tense",
            },
            {
                "id": "p2", "sequence": 2,
                "scene": "Castle courtyard at dawn",
                "action": "Villain appears in the shadows",
                "characters_present": ["villain"],
                "shot_type": "medium",
                "mood": "menacing",
                "dialogue": [
                    {"character_id": "villain", "text": "You cannot escape."},
                ],
            },
            {
                "id": "p3", "sequence": 3,
                "scene": "Castle courtyard at dawn",
                "action": "Hero draws sword, determined expression",
                "characters_present": ["hero"],
                "shot_type": "medium_close_up",
                "mood": "determined",
                "dialogue": [
                    {"character_id": "hero", "text": "Watch me."},
                ],
            },
            {
                "id": "p4", "sequence": 4,
                "scene": "Castle courtyard at dawn",
                "action": "Clash of swords, sparks flying",
                "characters_present": ["hero", "villain"],
                "shot_type": "medium",
                "mood": "action",
            },
            {
                "id": "p5", "sequence": 5,
                "scene": "Forest path, later",
                "action": "Hero walking alone through misty forest",
                "characters_present": ["hero"],
                "shot_type": "wide",
                "mood": "reflective",
            },
            {
                "id": "p6", "sequence": 6,
                "scene": "Forest path, later",
                "action": "Hero reveals the stolen gem",
                "characters_present": ["hero"],
                "shot_type": "close_up",
                "mood": "mysterious",
                "narrative_weight": "high",
            },
        ],
        "pages": [
            {"page_number": 1, "layout": "page_2x3", "panel_ids": ["p1", "p2", "p3", "p4", "p5", "p6"]},
        ],
    }


def make_dialogue_plan():
    """Plan focused on dialogue exchange."""
    return {
        "title": "Dialogue Test",
        "style": "western",
        "characters": [
            {"id": "alice", "name": "Alice", "visual_description": "young woman with blue hair"},
            {"id": "bob", "name": "Bob", "visual_description": "tall man with glasses"},
        ],
        "panels": [
            {
                "id": "d1", "sequence": 1,
                "scene": "Coffee shop interior",
                "action": "Alice and Bob sitting across from each other",
                "characters_present": ["alice", "bob"],
                "shot_type": "medium",
                "mood": "neutral",
                "dialogue": [
                    {"character_id": "alice", "text": "Did you hear the news?"},
                ],
            },
            {
                "id": "d2", "sequence": 2,
                "scene": "Coffee shop interior",
                "action": "Bob reacts with surprise",
                "characters_present": ["bob"],
                "shot_type": "medium",
                "mood": "surprised",
                "dialogue": [
                    {"character_id": "bob", "text": "What news?"},
                ],
            },
            {
                "id": "d3", "sequence": 3,
                "scene": "Coffee shop interior",
                "action": "Alice leans in conspiratorially",
                "characters_present": ["alice"],
                "shot_type": "medium",
                "mood": "mysterious",
                "dialogue": [
                    {"character_id": "alice", "text": "The city is shutting down."},
                ],
            },
            {
                "id": "d4", "sequence": 4,
                "scene": "Coffee shop interior",
                "action": "Bob drops his cup in shock",
                "characters_present": ["bob"],
                "shot_type": "medium",
                "mood": "shocked",
                "dialogue": [
                    {"character_id": "bob", "text": "That's impossible!"},
                ],
            },
        ],
        "pages": [
            {"page_number": 1, "layout": "page_2x2", "panel_ids": ["d1", "d2", "d3", "d4"]},
        ],
    }


# ── Test Counter ───────────────────────────────────────────────────────────
_passed = 0
_failed = 0
_errors = []


def check(condition: bool, name: str, detail: str = ""):
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  ✅ {name}")
    else:
        _failed += 1
        msg = f"  ❌ {name}"
        if detail:
            msg += f": {detail}"
        print(msg)
        _errors.append(name)


# ── Tests: Validation ──────────────────────────────────────────────────────

def test_validate_new_fields_valid():
    """Valid values for new sequential fields pass validation."""
    print("\n── test_validate_new_fields_valid ──")
    plan = make_base_plan()
    plan["panels"][0]["gaze_direction"] = "left"
    plan["panels"][0]["subject_position"] = "right_third"
    plan["panels"][0]["connects_to"] = "p2"
    plan["panels"][0]["spatial_relation"] = "same_location"
    plan["panels"][0]["focal_point"] = "upper_left"

    is_valid, errors = validate_story_plan(plan)
    check(is_valid, "Plan with valid sequential fields passes", str(errors))


def test_validate_new_fields_invalid():
    """Invalid values for new sequential fields are caught."""
    print("\n── test_validate_new_fields_invalid ──")

    # Invalid gaze_direction
    plan = make_base_plan()
    plan["panels"][0]["gaze_direction"] = "diagonal"
    _, errors = validate_story_plan(plan)
    check(any("gaze_direction" in e for e in errors), "Invalid gaze_direction caught")

    # Invalid subject_position
    plan = make_base_plan()
    plan["panels"][0]["subject_position"] = "far_left"
    _, errors = validate_story_plan(plan)
    check(any("subject_position" in e for e in errors), "Invalid subject_position caught")

    # Invalid spatial_relation
    plan = make_base_plan()
    plan["panels"][0]["spatial_relation"] = "teleport"
    _, errors = validate_story_plan(plan)
    check(any("spatial_relation" in e for e in errors), "Invalid spatial_relation caught")

    # Invalid focal_point
    plan = make_base_plan()
    plan["panels"][0]["focal_point"] = "dead_center"
    _, errors = validate_story_plan(plan)
    check(any("focal_point" in e for e in errors), "Invalid focal_point caught")

    # Invalid connects_to (non-existent panel)
    plan = make_base_plan()
    plan["panels"][0]["connects_to"] = "nonexistent"
    _, errors = validate_story_plan(plan)
    check(any("connects_to" in e for e in errors), "Invalid connects_to caught")


def test_backward_compatibility():
    """Plans without new fields still validate and enrich correctly."""
    print("\n── test_backward_compatibility ──")
    plan = make_base_plan()
    is_valid, errors = validate_story_plan(plan)
    check(is_valid, "Base plan without new fields is still valid", str(errors))

    enriched = enrich_story_plan(plan)
    check("panels" in enriched, "Enrichment works without new fields present")
    for p in enriched["panels"]:
        check("gaze_direction" in p, f"Panel {p['id']} got gaze_direction auto-set")
        check("subject_position" in p, f"Panel {p['id']} got subject_position auto-set")


# ── Tests: Sequential Field Enrichment ─────────────────────────────────────

def test_enrich_gaze_direction():
    """Auto-enrichment sets gaze_direction based on dialogue/sequence."""
    print("\n── test_enrich_gaze_direction ──")
    plan = make_base_plan()
    enriched = enrich_story_plan(plan)

    for p in enriched["panels"]:
        gaze = p.get("gaze_direction")
        check(gaze in VALID_GAZE_DIRECTIONS,
              f"Panel {p['id']} gaze_direction='{gaze}' is valid")

    # Panels with pre-set gaze should NOT be overwritten
    plan2 = make_base_plan()
    plan2["panels"][0]["gaze_direction"] = "up"
    enriched2 = enrich_story_plan(plan2)
    check(enriched2["panels"][0]["gaze_direction"] == "up",
          "Pre-set gaze_direction='up' preserved")


def test_enrich_subject_position():
    """Auto-enrichment alternates subject_position by sequence."""
    print("\n── test_enrich_subject_position ──")
    plan = make_base_plan()
    enriched = enrich_story_plan(plan)

    for p in enriched["panels"]:
        subj = p.get("subject_position")
        check(subj in VALID_SUBJECT_POSITIONS,
              f"Panel {p['id']} subject_position='{subj}' is valid")

    # Odd sequence → right_third, even → left_third (for non-splash)
    p1 = next(p for p in enriched["panels"] if p["id"] == "p1")
    p2 = next(p for p in enriched["panels"] if p["id"] == "p2")
    check(p1["subject_position"] == "right_third",
          "Odd panel (p1) → right_third")
    check(p2["subject_position"] == "left_third",
          "Even panel (p2) → left_third")


def test_enrich_connects_to():
    """Auto-enrichment sets connects_to to next panel."""
    print("\n── test_enrich_connects_to ──")
    plan = make_base_plan()
    enriched = enrich_story_plan(plan)

    panels = sorted(enriched["panels"], key=lambda p: p["sequence"])
    for i, p in enumerate(panels[:-1]):
        check(p.get("connects_to") == panels[i + 1]["id"],
              f"Panel {p['id']} connects_to={p.get('connects_to')}")

    # Last panel should NOT have connects_to
    last = panels[-1]
    check("connects_to" not in last or last.get("connects_to") == "",
          f"Last panel {last['id']} has no connects_to")


def test_enrich_spatial_relation():
    """Auto-enrichment detects same_location vs cut_to."""
    print("\n── test_enrich_spatial_relation ──")
    plan = make_base_plan()
    enriched = enrich_story_plan(plan)

    panels = sorted(enriched["panels"], key=lambda p: p["sequence"])

    # p1-p4 are all "Castle courtyard at dawn" → same_location
    for p in panels[:3]:  # p1, p2, p3
        check(p.get("spatial_relation") == "same_location",
              f"Panel {p['id']} spatial_relation='same_location' (same scene)")

    # p4→p5 transitions to "Forest path" → cut_to
    p4 = next(p for p in panels if p["id"] == "p4")
    check(p4.get("spatial_relation") == "cut_to",
          f"Panel p4 spatial_relation='cut_to' (scene change)")


def test_enrich_focal_point():
    """Auto-enrichment derives focal_point from subject_position + gaze."""
    print("\n── test_enrich_focal_point ──")
    plan = make_base_plan()
    enriched = enrich_story_plan(plan)

    for p in enriched["panels"]:
        fp = p.get("focal_point")
        check(fp in VALID_FOCAL_POINTS,
              f"Panel {p['id']} focal_point='{fp}' is valid")


# ── Tests: Shot Progression Validator ──────────────────────────────────────

def test_shot_progression_repetition():
    """Warns on >3 consecutive identical shot types."""
    print("\n── test_shot_progression_repetition ──")
    panels = [
        {"id": f"r{i}", "sequence": i, "shot_type": "medium", "scene": "same"}
        for i in range(1, 6)
    ]
    warnings = validate_shot_progression(panels, auto_fix=False)
    check(any("repetition" in w.lower() or "consecutive" in w.lower() for w in warnings),
          "Detects >3 consecutive medium shots")


def test_shot_progression_autofix():
    """Auto-fix varies repeated shot types."""
    print("\n── test_shot_progression_autofix ──")
    panels = [
        {"id": f"r{i}", "sequence": i, "shot_type": "medium", "scene": "same"}
        for i in range(1, 6)
    ]
    warnings = validate_shot_progression(panels, auto_fix=True)
    # After auto-fix, the 4th or 5th panel should have been changed
    shot_types = [p["shot_type"] for p in panels]
    check(len(set(shot_types)) > 1,
          f"Auto-fix varied shot types: {shot_types}")


def test_shot_progression_scene_opening():
    """Warns when a new scene doesn't open with an establishing shot."""
    print("\n── test_shot_progression_scene_opening ──")
    panels = [
        {"id": "s1", "sequence": 1, "shot_type": "close_up", "scene": "kitchen"},
        {"id": "s2", "sequence": 2, "shot_type": "medium", "scene": "kitchen"},
    ]
    warnings = validate_shot_progression(panels, auto_fix=False)
    check(any("scene opening" in w.lower() or "establishing" in w.lower() for w in warnings),
          "Detects non-establishing shot at scene opening")


def test_shot_progression_dialogue_monotony():
    """Warns when dialogue speaker change doesn't vary shot type."""
    print("\n── test_shot_progression_dialogue_monotony ──")
    panels = [
        {
            "id": "dm1", "sequence": 1, "shot_type": "medium", "scene": "room",
            "dialogue": [{"character_id": "alice", "text": "Hello"}],
        },
        {
            "id": "dm2", "sequence": 2, "shot_type": "medium", "scene": "room",
            "dialogue": [{"character_id": "bob", "text": "Hi"}],
        },
    ]
    warnings = validate_shot_progression(panels, auto_fix=False)
    check(any("dialogue" in w.lower() or "monotony" in w.lower() for w in warnings),
          "Detects dialogue monotony with same shot type")


# ── Tests: Dialogue Reading Order ──────────────────────────────────────────

def test_dialogue_position_hints():
    """Multiple dialogue entries get ordered position hints."""
    print("\n── test_dialogue_position_hints ──")
    plan = make_base_plan()
    # Add a panel with multiple speakers
    plan["panels"].append({
        "id": "p7", "sequence": 7,
        "scene": "Forest path",
        "action": "Hero and Villain argue",
        "characters_present": ["hero", "villain"],
        "shot_type": "medium",
        "mood": "tense",
        "dialogue": [
            {"character_id": "hero", "text": "This ends now."},
            {"character_id": "villain", "text": "You wish."},
            {"character_id": "hero", "text": "I know."},
        ],
    })
    plan["pages"][0]["panel_ids"].append("p7")
    # Need a layout that fits 7 panels
    plan["pages"] = [
        {"page_number": 1, "layout": "page_2x3", "panel_ids": ["p1", "p2", "p3", "p4", "p5", "p6"]},
        {"page_number": 2, "layout": "page_splash", "panel_ids": ["p7"]},
    ]

    enriched = enrich_story_plan(plan)
    p7 = next(p for p in enriched["panels"] if p["id"] == "p7")
    dialogue = p7.get("dialogue", [])

    check(dialogue[0].get("position_hint") == "top_left",
          f"First speaker → top_left (got {dialogue[0].get('position_hint')})")
    check(dialogue[1].get("position_hint") == "top_right",
          f"Second speaker → top_right (got {dialogue[1].get('position_hint')})")
    check(dialogue[2].get("position_hint") == "bottom_left",
          f"Third speaker → bottom_left (got {dialogue[2].get('position_hint')})")


# ── Tests: Panel Generator Composition Tags ────────────────────────────────

def test_composition_templates_exist():
    """COMPOSITION_TEMPLATES has all expected keys."""
    print("\n── test_composition_templates_exist ──")
    expected_keys = [
        "dialogue_speaker_a", "dialogue_speaker_b", "establishing",
        "reaction", "action_peak", "transition", "reveal",
        "confrontation", "climax", "contemplation",
    ]
    for key in expected_keys:
        check(key in COMPOSITION_TEMPLATES,
              f"Template '{key}' exists")


def test_composition_tags_anti_centering():
    """Non-splash, non-establishing panels get off-center tags."""
    print("\n── test_composition_tags_anti_centering ──")
    panel = {
        "id": "t1", "sequence": 1, "shot_type": "medium",
        "mood": "neutral", "characters_present": ["hero"],
        "subject_position": "right_third",
    }
    tags = _get_sequential_composition_tags(panel)
    tag_str = " ".join(tags).lower()
    check("off-center" in tag_str or "rule of thirds" in tag_str,
          "Normal panel gets off-center composition")
    check("right third" in tag_str,
          "subject_position=right_third reflected in tags")


def test_composition_tags_splash_centered():
    """Splash panels are allowed centered/symmetric compositions."""
    print("\n── test_composition_tags_splash_centered ──")
    panel = {
        "id": "t2", "sequence": 5, "shot_type": "medium",
        "mood": "dramatic", "narrative_weight": "splash",
        "characters_present": ["hero"],
    }
    tags = _get_sequential_composition_tags(panel)
    tag_str = " ".join(tags).lower()
    check("splash" in tag_str or "climax" in tag_str or "impact" in tag_str,
          f"Splash panel gets splash/climax composition tags")


def test_composition_tags_eyeline_matching():
    """Eyeline matching: prev panel gaze_direction affects current panel."""
    print("\n── test_composition_tags_eyeline_matching ──")
    panels = [
        {"id": "e1", "sequence": 1, "shot_type": "medium", "mood": "neutral",
         "characters_present": ["hero"], "gaze_direction": "left",
         "scene": "room"},
        {"id": "e2", "sequence": 2, "shot_type": "medium", "mood": "neutral",
         "characters_present": ["villain"], "scene": "room"},
    ]
    tags = _get_sequential_composition_tags(panels[1], all_panels=panels)
    tag_str = " ".join(tags).lower()
    check("left" in tag_str and "eyeline" in tag_str,
          f"Panel after left-gazing panel gets left-side eyeline match")


def test_composition_tags_action_reaction():
    """After an action panel, the next panel gets reaction tags."""
    print("\n── test_composition_tags_action_reaction ──")
    panels = [
        {"id": "a1", "sequence": 1, "shot_type": "medium", "mood": "action",
         "characters_present": ["hero"], "scene": "arena"},
        {"id": "a2", "sequence": 2, "shot_type": "close_up", "mood": "sad",
         "characters_present": ["villain"], "scene": "arena"},
    ]
    tags = _get_sequential_composition_tags(panels[1], all_panels=panels)
    tag_str = " ".join(tags).lower()
    check("reaction" in tag_str or "close-up" in tag_str or "facial expression" in tag_str,
          f"Post-action panel gets reaction composition")


def test_composition_tags_spatial_continuity():
    """same_location spatial_relation adds continuity tags."""
    print("\n── test_composition_tags_spatial_continuity ──")
    panels = [
        {"id": "sc1", "sequence": 1, "shot_type": "wide", "mood": "neutral",
         "characters_present": ["hero"], "scene": "park",
         "spatial_relation": "same_location"},
        {"id": "sc2", "sequence": 2, "shot_type": "medium", "mood": "neutral",
         "characters_present": ["hero"], "scene": "park",
         "spatial_relation": "same_location"},
    ]
    tags = _get_sequential_composition_tags(panels[1], all_panels=panels)
    tag_str = " ".join(tags).lower()
    check("continuity" in tag_str or "same environment" in tag_str,
          "same_location adds spatial continuity tags")


def test_composition_tags_scene_opening():
    """First panel of a new scene gets establishing tags."""
    print("\n── test_composition_tags_scene_opening ──")
    panels = [
        {"id": "so1", "sequence": 1, "shot_type": "medium", "mood": "neutral",
         "characters_present": ["hero"], "scene": "office"},
        {"id": "so2", "sequence": 2, "shot_type": "wide", "mood": "neutral",
         "characters_present": ["hero"], "scene": "rooftop"},
    ]
    tags = _get_sequential_composition_tags(panels[1], all_panels=panels)
    tag_str = " ".join(tags).lower()
    check("establishing" in tag_str or "new scene" in tag_str,
          "New scene gets establishing composition")


def test_composition_tags_climax():
    """High narrative_weight panels get dramatic composition."""
    print("\n── test_composition_tags_climax ──")
    panel = {
        "id": "cl1", "sequence": 5, "shot_type": "low_angle",
        "mood": "dramatic", "narrative_weight": "high",
        "characters_present": ["hero"],
    }
    tags = _get_sequential_composition_tags(panel)
    tag_str = " ".join(tags).lower()
    check("dramatic" in tag_str or "impact" in tag_str or "powerful" in tag_str,
          "High narrative_weight gets dramatic composition")


def test_composition_tags_confrontation():
    """Confrontation mood gets centered symmetric composition."""
    print("\n── test_composition_tags_confrontation ──")
    panel = {
        "id": "cf1", "sequence": 3, "shot_type": "medium",
        "mood": "confrontation", "characters_present": ["hero", "villain"],
    }
    tags = _get_sequential_composition_tags(panel)
    tag_str = " ".join(tags).lower()
    check("symmetrical" in tag_str or "confrontation" in tag_str or "facing" in tag_str,
          "Confrontation gets centered/symmetric composition")


def test_composition_tags_gaze_from_plan():
    """gaze_direction from story plan is used instead of auto-alternation."""
    print("\n── test_composition_tags_gaze_from_plan ──")
    panel = {
        "id": "gp1", "sequence": 2, "shot_type": "medium",
        "mood": "neutral", "characters_present": ["hero"],
        "gaze_direction": "up",
        "dialogue": [{"character_id": "hero", "text": "Look!"}],
    }
    tags = _get_sequential_composition_tags(panel)
    tag_str = " ".join(tags).lower()
    check("upward" in tag_str,
          "gaze_direction='up' from plan reflected in tags")


def test_composition_tags_focal_point():
    """focal_point from story plan adds specific focal tags."""
    print("\n── test_composition_tags_focal_point ──")
    panel = {
        "id": "fp1", "sequence": 1, "shot_type": "medium",
        "mood": "neutral", "characters_present": ["hero"],
        "focal_point": "upper_left",
    }
    tags = _get_sequential_composition_tags(panel)
    tag_str = " ".join(tags).lower()
    check("upper left" in tag_str or "top-left" in tag_str,
          "focal_point='upper_left' reflected in tags")


def test_build_panel_prompt_includes_composition():
    """build_panel_prompt includes sequential composition tags."""
    print("\n── test_build_panel_prompt_includes_composition ──")
    characters = [
        {"id": "hero", "name": "Hero", "visual_description": "warrior with red cape"},
    ]
    panel = {
        "id": "bp1", "sequence": 1, "shot_type": "medium",
        "mood": "neutral", "characters_present": ["hero"],
        "action": "Hero stands ready",
        "scene": "battleground",
        "subject_position": "right_third",
        "gaze_direction": "left",
    }
    prompt = build_panel_prompt(panel, characters, "western")
    check("right third" in prompt.lower(),
          "Prompt includes subject position")
    check("looking" in prompt.lower() and "left" in prompt.lower(),
          "Prompt includes gaze direction")


def test_full_enrichment_pipeline():
    """Full pipeline: validate → enrich → generate tags for all panels."""
    print("\n── test_full_enrichment_pipeline ──")
    plan = make_base_plan()

    # Validate
    is_valid, errors = validate_story_plan(plan)
    check(is_valid, "Base plan validates", str(errors))

    # Enrich
    enriched = enrich_story_plan(plan)
    panels = sorted(enriched["panels"], key=lambda p: p["sequence"])

    # Check all panels have sequential fields
    for p in panels:
        check("gaze_direction" in p, f"Panel {p['id']} has gaze_direction")
        check("subject_position" in p, f"Panel {p['id']} has subject_position")
        check("focal_point" in p, f"Panel {p['id']} has focal_point")

    # Generate composition tags for each panel
    characters = enriched["characters"]
    for p in panels:
        tags = _get_sequential_composition_tags(p, all_panels=panels)
        check(len(tags) > 0,
              f"Panel {p['id']} gets {len(tags)} composition tags")

    # Validate enriched plan still validates
    is_valid2, errors2 = validate_story_plan(enriched)
    check(is_valid2, "Enriched plan still validates", str(errors2))


def test_dialogue_plan_enrichment():
    """Dialogue-heavy plan gets proper shot/gaze variation."""
    print("\n── test_dialogue_plan_enrichment ──")
    plan = make_dialogue_plan()
    enriched = enrich_story_plan(plan)
    panels = sorted(enriched["panels"], key=lambda p: p["sequence"])

    # Check that dialogue panels alternate gaze
    gazes = [p["gaze_direction"] for p in panels]
    check(len(set(gazes)) > 1,
          f"Dialogue panels have varied gaze directions: {gazes}")

    # Check warnings about dialogue monotony (all panels start as medium)
    warnings = enriched.get("_enrichment_warnings", [])
    check(len(warnings) > 0,
          f"Got {len(warnings)} enrichment warnings for monotonous dialogue plan")


# ── Run all tests ──────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("ComicMaster Sequential Composition Tests")
    print("=" * 60)

    # Validation tests
    test_validate_new_fields_valid()
    test_validate_new_fields_invalid()
    test_backward_compatibility()

    # Enrichment tests
    test_enrich_gaze_direction()
    test_enrich_subject_position()
    test_enrich_connects_to()
    test_enrich_spatial_relation()
    test_enrich_focal_point()

    # Shot progression tests
    test_shot_progression_repetition()
    test_shot_progression_autofix()
    test_shot_progression_scene_opening()
    test_shot_progression_dialogue_monotony()

    # Dialogue reading order
    test_dialogue_position_hints()

    # Panel generator composition tags
    test_composition_templates_exist()
    test_composition_tags_anti_centering()
    test_composition_tags_splash_centered()
    test_composition_tags_eyeline_matching()
    test_composition_tags_action_reaction()
    test_composition_tags_spatial_continuity()
    test_composition_tags_scene_opening()
    test_composition_tags_climax()
    test_composition_tags_confrontation()
    test_composition_tags_gaze_from_plan()
    test_composition_tags_focal_point()
    test_build_panel_prompt_includes_composition()
    test_full_enrichment_pipeline()
    test_dialogue_plan_enrichment()

    # Summary
    print("\n" + "=" * 60)
    total = _passed + _failed
    print(f"Results: {_passed}/{total} passed, {_failed} failed")
    if _errors:
        print(f"\nFailed tests:")
        for e in _errors:
            print(f"  ❌ {e}")
    print("=" * 60)

    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

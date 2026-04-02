#!/usr/bin/env python3
"""
Batch optimizer for large comic generation.
Groups panels by model requirements to minimize ComfyUI model reloads.

When generating 30+ panels, model switching (loading/unloading checkpoints,
IPAdapter models) is the biggest bottleneck. This module reorders panels so
that panels with identical model requirements are generated back-to-back,
avoiding redundant ComfyUI model loads.

The optimization is purely about ORDER of generation — ComfyUI still handles
one image at a time. No workflow modifications are made.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

# --- Time estimates (seconds per panel, based on observed averages) ---

# Base generation time (no IPAdapter)
EST_BASE_SECONDS = 4.0
# Additional time for single IPAdapter
EST_SINGLE_IPA_SECONDS = 6.0
# Additional time for multi-character IPAdapter
EST_MULTI_IPA_SECONDS = 9.0
# Cost of a model/IPAdapter switch (checkpoint reload, adapter load)
EST_MODEL_SWITCH_SECONDS = 8.0


def _get_panel_char_key(panel: dict, char_refs: dict | None) -> tuple[str, ...]:
    """Return a sorted tuple of character IDs that have IPAdapter refs for this panel.

    This is used as the grouping key: panels with the same char key can be
    generated consecutively without IPAdapter reloads.
    """
    if not char_refs or not panel.get("characters_present"):
        return ()
    return tuple(sorted(
        cid for cid in panel["characters_present"]
        if cid in char_refs and char_refs[cid].get("comfyui_filename")
    ))


def optimize_panel_order(
    panels: list[dict],
    characters: list[dict],
    char_refs: dict | None,
) -> list[dict]:
    """Reorder panels to minimize model switching.

    Strategy:
    1. Group panels by their IPAdapter character combination:
       - Group A: 0 chars (no IPAdapter) → fastest, generated first
       - Group B: 1 char (single IPAdapter) → grouped by char_id
       - Group C: 2+ chars (multi IPAdapter) → grouped by char combination
    2. Within each group, sub-sort by character combination so identical
       ref sets stay loaded across consecutive panels.
    3. Return ordered list with original sequence numbers preserved.

    Each panel in the returned list has an added '_batch_info' dict:
        {
            "original_index": int,       # position in the input list
            "group": str,                # "no_ipadapter" | "single_ipadapter" | "multi_ipadapter"
            "char_key": tuple[str, ...], # sorted character IDs needing IPAdapter
            "batch_position": int,       # position in the optimized order
        }

    Args:
        panels: List of panel dicts (from story_plan["panels"]).
        characters: List of character dicts (from story_plan["characters"]).
        char_refs: Dict mapping character_id → ref info dict, or None.

    Returns:
        List of panel dicts in optimized generation order.
    """
    # Annotate each panel with its grouping info
    annotated: list[tuple[int, dict, tuple[str, ...]]] = []
    for idx, panel in enumerate(panels):
        char_key = _get_panel_char_key(panel, char_refs)
        annotated.append((idx, panel, char_key))

    # Bucket into groups
    group_a: list[tuple[int, dict, tuple]] = []  # no IPAdapter
    group_b: dict[tuple, list[tuple[int, dict, tuple]]] = defaultdict(list)  # single char
    group_c: dict[tuple, list[tuple[int, dict, tuple]]] = defaultdict(list)  # multi char

    for idx, panel, char_key in annotated:
        if len(char_key) == 0:
            group_a.append((idx, panel, char_key))
        elif len(char_key) == 1:
            group_b[char_key].append((idx, panel, char_key))
        else:
            group_c[char_key].append((idx, panel, char_key))

    # Build optimized order: A first, then B (sorted by char_id), then C (sorted by combination)
    optimized: list[tuple[int, dict, tuple]] = []

    # Group A — no IPAdapter, fastest
    optimized.extend(group_a)

    # Group B — single IPAdapter, grouped by character
    for char_key in sorted(group_b.keys()):
        optimized.extend(group_b[char_key])

    # Group C — multi IPAdapter, grouped by character combination
    for char_key in sorted(group_c.keys()):
        optimized.extend(group_c[char_key])

    # Annotate with _batch_info
    result = []
    for batch_pos, (orig_idx, panel, char_key) in enumerate(optimized):
        # Shallow copy to avoid mutating the original
        p = dict(panel)
        if len(char_key) == 0:
            group_label = "no_ipadapter"
        elif len(char_key) == 1:
            group_label = "single_ipadapter"
        else:
            group_label = "multi_ipadapter"

        p["_batch_info"] = {
            "original_index": orig_idx,
            "group": group_label,
            "char_key": char_key,
            "batch_position": batch_pos,
        }
        result.append(p)

    return result


def estimate_batch_time(
    panels: list[dict],
    char_refs: dict | None,
) -> dict[str, Any]:
    """Estimate total generation time for a batch of panels.

    Args:
        panels: List of panel dicts.
        char_refs: Character reference dict, or None.

    Returns:
        {
            "total_panels": int,
            "estimated_seconds": float,
            "groups": [
                {"type": "no_ipadapter", "count": int, "est_seconds": float},
                {"type": "single_ipadapter", "count": int, "est_seconds": float, "char_keys": [...]},
                {"type": "multi_ipadapter", "count": int, "est_seconds": float, "char_keys": [...]},
            ],
            "model_switches": int,
        }
    """
    # Count panels per group
    no_ipa = 0
    single_ipa: dict[tuple, int] = defaultdict(int)
    multi_ipa: dict[tuple, int] = defaultdict(int)

    for panel in panels:
        char_key = _get_panel_char_key(panel, char_refs)
        if len(char_key) == 0:
            no_ipa += 1
        elif len(char_key) == 1:
            single_ipa[char_key] += 1
        else:
            multi_ipa[char_key] += 1

    groups = []
    total_seconds = 0.0
    model_switches = 0

    # Group A: no IPAdapter
    if no_ipa > 0:
        est = no_ipa * EST_BASE_SECONDS
        groups.append({"type": "no_ipadapter", "count": no_ipa, "est_seconds": round(est, 1)})
        total_seconds += est

    # Transition from A → B (if both exist)
    if no_ipa > 0 and (single_ipa or multi_ipa):
        model_switches += 1
        total_seconds += EST_MODEL_SWITCH_SECONDS

    # Group B: single IPAdapter
    prev_key = None
    for char_key in sorted(single_ipa.keys()):
        count = single_ipa[char_key]
        est = count * EST_SINGLE_IPA_SECONDS
        if prev_key is not None and prev_key != char_key:
            model_switches += 1
            total_seconds += EST_MODEL_SWITCH_SECONDS
        elif prev_key is None and no_ipa == 0 and multi_ipa:
            pass  # first group, no switch yet
        groups.append({
            "type": "single_ipadapter",
            "count": count,
            "est_seconds": round(est, 1),
            "char_keys": list(char_key),
        })
        total_seconds += est
        prev_key = char_key

    # Transition from B → C (if both exist)
    if single_ipa and multi_ipa:
        model_switches += 1
        total_seconds += EST_MODEL_SWITCH_SECONDS

    # Group C: multi IPAdapter
    prev_key = None
    for char_key in sorted(multi_ipa.keys()):
        count = multi_ipa[char_key]
        est = count * EST_MULTI_IPA_SECONDS
        if prev_key is not None and prev_key != char_key:
            model_switches += 1
            total_seconds += EST_MODEL_SWITCH_SECONDS
        groups.append({
            "type": "multi_ipadapter",
            "count": count,
            "est_seconds": round(est, 1),
            "char_keys": list(char_key),
        })
        total_seconds += est
        prev_key = char_key

    return {
        "total_panels": len(panels),
        "estimated_seconds": round(total_seconds, 1),
        "groups": groups,
        "model_switches": model_switches,
    }


def count_unoptimized_switches(panels: list[dict], char_refs: dict | None) -> int:
    """Count how many model switches would occur WITHOUT optimization (original order)."""
    switches = 0
    prev_key = None
    for panel in panels:
        char_key = _get_panel_char_key(panel, char_refs)
        if prev_key is not None and prev_key != char_key:
            switches += 1
        prev_key = char_key
    return switches


def generate_batch_report(
    results: list[dict],
    total_time: float,
    optimized: bool = False,
    model_switches_saved: int = 0,
) -> str:
    """Generate a human-readable report of batch generation results.

    Args:
        results: List of per-panel result dicts (from generate_panel).
        total_time: Total wall-clock time in seconds.
        optimized: Whether batch optimization was used.
        model_switches_saved: Number of model switches avoided by optimization.

    Returns:
        Multi-line report string.
    """
    if not results:
        return "No panels generated."

    total = len(results)
    durations = [r.get("duration_s", 0) for r in results if r.get("duration_s")]
    ipa_count = sum(1 for r in results if r.get("ipadapter"))
    multi_ipa_count = sum(1 for r in results if r.get("multi_ipadapter"))
    no_ipa_count = total - ipa_count
    retry_count = sum(r.get("attempts", 1) - 1 for r in results)

    avg_duration = sum(durations) / len(durations) if durations else 0
    min_duration = min(durations) if durations else 0
    max_duration = max(durations) if durations else 0

    lines = [
        "=" * 60,
        "📊 BATCH GENERATION REPORT",
        "=" * 60,
        "",
        f"  Total panels:        {total}",
        f"  Total time:          {total_time:.1f}s ({total_time/60:.1f}min)",
        f"  Avg per panel:       {avg_duration:.1f}s",
        f"  Fastest:             {min_duration:.1f}s",
        f"  Slowest:             {max_duration:.1f}s",
        "",
        f"  No IPAdapter:        {no_ipa_count}",
        f"  Single IPAdapter:    {ipa_count - multi_ipa_count}",
        f"  Multi IPAdapter:     {multi_ipa_count}",
        f"  Retries:             {retry_count}",
        "",
    ]

    if optimized:
        lines.extend([
            f"  🔧 Batch optimized:  YES",
            f"  Model switches saved: ~{model_switches_saved}",
            f"  Est. time saved:     ~{model_switches_saved * EST_MODEL_SWITCH_SECONDS:.0f}s",
            "",
        ])

    lines.append("=" * 60)
    return "\n".join(lines)


# --- CLI self-test ---


def _run_self_test():
    """Run optimizer self-test with synthetic panels and print report."""
    import json
    import os

    # --- Build 15 fake panels with various character configs ---
    characters = [
        {"id": "hero", "visual_description": "muscular man with red cape"},
        {"id": "villain", "visual_description": "dark-robed woman with glowing eyes"},
        {"id": "sidekick", "visual_description": "small robot with antenna"},
    ]

    char_refs = {
        "hero": {"comfyui_filename": "charref_hero_00001.png", "path": "/fake/hero.png"},
        "villain": {"comfyui_filename": "charref_villain_00001.png", "path": "/fake/villain.png"},
        "sidekick": {"comfyui_filename": "charref_sidekick_00001.png", "path": "/fake/sidekick.png"},
    }

    panels = [
        # 3 panels with no characters (establishing shots)
        {"id": "p01", "action": "City skyline at dawn", "characters_present": [], "shot_type": "extreme_wide"},
        {"id": "p02", "action": "Interior of villain lair", "characters_present": [], "shot_type": "wide"},
        {"id": "p03", "action": "Empty street", "characters_present": [], "shot_type": "wide"},
        # 4 panels with hero only
        {"id": "p04", "action": "Hero poses on rooftop", "characters_present": ["hero"], "shot_type": "medium"},
        {"id": "p05", "action": "Hero running", "characters_present": ["hero"], "shot_type": "wide"},
        {"id": "p06", "action": "Hero close-up", "characters_present": ["hero"], "shot_type": "close_up"},
        {"id": "p07", "action": "Hero meditating", "characters_present": ["hero"], "shot_type": "medium"},
        # 2 panels with villain only
        {"id": "p08", "action": "Villain scheming", "characters_present": ["villain"], "shot_type": "medium_close"},
        {"id": "p09", "action": "Villain power surge", "characters_present": ["villain"], "shot_type": "wide"},
        # 1 panel with sidekick only
        {"id": "p10", "action": "Sidekick scanning", "characters_present": ["sidekick"], "shot_type": "medium"},
        # 3 panels with hero + villain
        {"id": "p11", "action": "Hero confronts villain", "characters_present": ["hero", "villain"], "shot_type": "wide"},
        {"id": "p12", "action": "Battle scene", "characters_present": ["hero", "villain"], "shot_type": "medium"},
        {"id": "p13", "action": "Standoff", "characters_present": ["hero", "villain"], "shot_type": "close_up"},
        # 1 panel with hero + sidekick
        {"id": "p14", "action": "Hero and sidekick team up", "characters_present": ["hero", "sidekick"], "shot_type": "medium"},
        # 1 panel with all three
        {"id": "p15", "action": "Final showdown", "characters_present": ["hero", "villain", "sidekick"], "shot_type": "wide"},
    ]

    print("=" * 60)
    print("🧪 BATCH OPTIMIZER SELF-TEST")
    print("=" * 60)
    print()

    # --- Show original order ---
    print("📋 ORIGINAL ORDER:")
    for i, p in enumerate(panels):
        chars = ", ".join(p.get("characters_present", [])) or "(none)"
        print(f"  {i+1:2d}. {p['id']}  chars=[{chars}]")

    print()

    # --- Count unoptimized switches ---
    unopt_switches = count_unoptimized_switches(panels, char_refs)
    print(f"  Model switches (original order): {unopt_switches}")
    print()

    # --- Optimize ---
    optimized = optimize_panel_order(panels, characters, char_refs)

    print("🔧 OPTIMIZED ORDER:")
    prev_group = None
    for i, p in enumerate(optimized):
        info = p["_batch_info"]
        chars = ", ".join(p.get("characters_present", [])) or "(none)"
        group = info["group"]
        if group != prev_group:
            print(f"\n  --- {group.upper()} ---")
            prev_group = group
        orig = info["original_index"] + 1
        print(f"  {i+1:2d}. {p['id']}  (was #{orig:2d})  chars=[{chars}]  key={info['char_key']}")

    # Count optimized switches
    opt_switches = 0
    prev_key = None
    for p in optimized:
        key = p["_batch_info"]["char_key"]
        if prev_key is not None and prev_key != key:
            opt_switches += 1
        prev_key = key

    print()
    print(f"  Model switches (optimized order): {opt_switches}")
    print(f"  Switches saved: {unopt_switches - opt_switches}")
    print()

    # --- Estimate ---
    estimate = estimate_batch_time(panels, char_refs)
    print("⏱️  TIME ESTIMATE:")
    print(f"  Total panels:      {estimate['total_panels']}")
    print(f"  Estimated time:    {estimate['estimated_seconds']:.1f}s ({estimate['estimated_seconds']/60:.1f}min)")
    print(f"  Model switches:    {estimate['model_switches']}")
    print(f"  Groups:")
    for g in estimate["groups"]:
        chars_info = f"  chars={g.get('char_keys', [])}" if g.get("char_keys") else ""
        print(f"    - {g['type']}: {g['count']} panels, ~{g['est_seconds']:.1f}s{chars_info}")

    print()

    # --- Fake results for report ---
    fake_results = []
    for p in panels:
        has_ipa = bool(p.get("characters_present"))
        multi = len(p.get("characters_present", [])) >= 2
        dur = (EST_MULTI_IPA_SECONDS if multi else EST_SINGLE_IPA_SECONDS if has_ipa else EST_BASE_SECONDS)
        # Add some jitter
        dur += (hash(p["id"]) % 30) / 10.0
        fake_results.append({
            "panel_id": p["id"],
            "duration_s": round(dur, 1),
            "ipadapter": has_ipa,
            "multi_ipadapter": multi,
            "attempts": 1,
        })

    fake_total_time = sum(r["duration_s"] for r in fake_results)
    report = generate_batch_report(
        fake_results,
        total_time=fake_total_time,
        optimized=True,
        model_switches_saved=unopt_switches - opt_switches,
    )
    print(report)

    # --- Save report to file ---
    output_dir = "/home/mcmuff/clawd/output/comicmaster/test_batch"
    os.makedirs(output_dir, exist_ok=True)
    report_path = os.path.join(output_dir, "optimizer_report.txt")

    full_report = []
    full_report.append("BATCH OPTIMIZER TEST REPORT")
    full_report.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    full_report.append("")
    full_report.append(f"Test panels: {len(panels)}")
    full_report.append(f"Characters: {[c['id'] for c in characters]}")
    full_report.append(f"Character refs: {list(char_refs.keys())}")
    full_report.append("")
    full_report.append("ORIGINAL ORDER:")
    for i, p in enumerate(panels):
        chars = ", ".join(p.get("characters_present", [])) or "(none)"
        full_report.append(f"  {i+1:2d}. {p['id']}  chars=[{chars}]")
    full_report.append(f"  Model switches: {unopt_switches}")
    full_report.append("")
    full_report.append("OPTIMIZED ORDER:")
    for i, p in enumerate(optimized):
        info = p["_batch_info"]
        chars = ", ".join(p.get("characters_present", [])) or "(none)"
        full_report.append(f"  {i+1:2d}. {p['id']}  (was #{info['original_index']+1:2d})  "
                           f"group={info['group']}  chars=[{chars}]")
    full_report.append(f"  Model switches: {opt_switches}")
    full_report.append(f"  Switches saved: {unopt_switches - opt_switches}")
    full_report.append("")
    full_report.append("TIME ESTIMATE:")
    full_report.append(json.dumps(estimate, indent=2))
    full_report.append("")
    full_report.append(report)

    with open(report_path, "w") as f:
        f.write("\n".join(full_report))

    print(f"\n💾 Report saved to: {report_path}")

    # Return for programmatic use
    return {
        "panels_tested": len(panels),
        "original_switches": unopt_switches,
        "optimized_switches": opt_switches,
        "switches_saved": unopt_switches - opt_switches,
        "estimate": estimate,
    }


if __name__ == "__main__":
    _run_self_test()

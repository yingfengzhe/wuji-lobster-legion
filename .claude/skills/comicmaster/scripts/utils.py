"""
ComicMaster – Shared utilities for the pipeline.
"""

import os
import json
import re
import time
from datetime import datetime
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
SKILL_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
WORKFLOWS_DIR = SKILL_DIR / "workflows"
TEMPLATES_DIR = SKILL_DIR / "assets" / "templates"
FONTS_DIR = SKILL_DIR / "assets" / "fonts"
MEMORY_DIR = SKILL_DIR / "memory"
CONFIG_PATH = SKILL_DIR / "config.json"
OUTPUT_BASE = Path("/home/mcmuff/clawd/output/comicmaster")

# ── Template metadata (slot counts) ───────────────────────────────────────
_template_cache: dict[str, dict] | None = None


def _load_templates() -> dict[str, dict]:
    """Load all template JSONs once and cache them."""
    global _template_cache
    if _template_cache is not None:
        return _template_cache
    _template_cache = {}
    if TEMPLATES_DIR.is_dir():
        for fp in TEMPLATES_DIR.glob("*.json"):
            try:
                data = json.loads(fp.read_text())
                name = data.get("name", fp.stem)
                _template_cache[name] = data
            except (json.JSONDecodeError, OSError):
                pass
    return _template_cache


def get_template(name: str) -> dict | None:
    """Return a template dict by name, or None if not found."""
    return _load_templates().get(name)


def template_slot_count(name: str) -> int | None:
    """Return the number of panel slots for a template, or None if unknown."""
    tpl = get_template(name)
    if tpl is None:
        return None
    return len(tpl.get("panels", []))


def available_templates() -> list[str]:
    """Return sorted list of available template names."""
    return sorted(_load_templates().keys())


# ── Config ─────────────────────────────────────────────────────────────────
_DEFAULTS = {
    "defaults": {
        "preset": "dreamshaperXL",
        "style": "western",
        "reading_direction": "ltr",
        "panel_width": 768,
        "panel_height": 768,
        "page_width": 2480,
        "page_height": 3508,
        "page_dpi": 300,
        "max_retries": 3,
        "generation_timeout": 300,
    },
    "bubbles": {
        "default_font_set": "western",
        "outline_width": 3,
        "padding_ratio": 0.15,
    },
    "layout": {
        "margin": [80, 80, 60, 60],
        "gutter": 30,
        "border_width": 3,
    },
    "output": {
        "base_dir": str(OUTPUT_BASE),
    },
}


def load_config() -> dict:
    """Load config.json, falling back to built-in defaults for missing keys."""
    config = {}
    if CONFIG_PATH.is_file():
        try:
            config = json.loads(CONFIG_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    # Deep-merge defaults into config (config wins)
    merged = {}
    for section, defaults in _DEFAULTS.items():
        merged[section] = {**defaults, **config.get(section, {})}
    # Preserve any extra top-level keys from the file
    for k, v in config.items():
        if k not in merged:
            merged[k] = v
    return merged


# ── Project directories ────────────────────────────────────────────────────
_PROJECT_SUBDIRS = ("refs", "panels", "panels_bubbled", "pages", "exports")


def get_project_dir(project_id: str) -> Path:
    """Get/create the output directory tree for a project.

    Creates::

        output/comicmaster/{project_id}/
            refs/
            panels/
            panels_bubbled/
            pages/
            exports/
    """
    project_dir = OUTPUT_BASE / project_id
    for sub in _PROJECT_SUBDIRS:
        (project_dir / sub).mkdir(parents=True, exist_ok=True)
    return project_dir


def generate_project_id(title: str) -> str:
    """Generate a unique project ID from *title* + current timestamp.

    Example: ``comic_20260208_213000_the_last_robot``
    """
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:40]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"comic_{ts}_{slug}"


# ── Story plan I/O ─────────────────────────────────────────────────────────
def load_story_plan(path: str) -> dict:
    """Load a story plan JSON from *path* and return it as a dict.

    Raises ``FileNotFoundError`` or ``json.JSONDecodeError`` on failure.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Story plan not found: {path}")
    return json.loads(p.read_text())


def save_story_plan(plan: dict, project_dir: Path) -> str:
    """Save *plan* to ``story_plan.json`` inside *project_dir*.

    Returns the absolute path of the written file.
    """
    project_dir.mkdir(parents=True, exist_ok=True)
    out = project_dir / "story_plan.json"
    out.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
    return str(out)


# ── Logging ────────────────────────────────────────────────────────────────
def log_generation(project_dir: Path, entry: dict):
    """Append *entry* (with auto-timestamp) to ``generation_log.jsonl``."""
    log_path = project_dir / "generation_log.jsonl"
    entry_with_ts = {"timestamp": datetime.now().isoformat(), **entry}
    with open(log_path, "a") as f:
        f.write(json.dumps(entry_with_ts, ensure_ascii=False) + "\n")


def log_learning(text: str, project_id: str | None = None, title: str | None = None):
    """Append a learning entry to ``memory/learnings.md``."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    learnings_path = MEMORY_DIR / "learnings.md"

    header_parts = [datetime.now().strftime("%Y-%m-%d %H:%M")]
    if project_id:
        header_parts.append(f"project={project_id}")
    if title:
        header_parts.append(f'"{title}"')
    header = " | ".join(header_parts)

    with open(learnings_path, "a") as f:
        f.write(f"\n### {header}\n{text}\n")

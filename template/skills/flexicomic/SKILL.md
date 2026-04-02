---
name: flexicomic
description: Generate comics and manga with AI. Use when user wants to create comics, manga, graphic novels, or sequential art with custom layouts, characters, and styles.
model: opus
license: MIT
metadata:
  author: SCF
  version: "1.0.0"
---

# flexicomic

Flexible comic generation with full customization support.

## Overview

`flexicomic` is a flexible manga/comic generation tool that provides complete control over comic creation, including:

- **Custom panel layouts**: Define any grid structure with custom panel sizes and positions
- **Enhanced character consistency**: Multi-angle, multi-expression character reference generation
- **Interactive setup**: Step-by-step configuration wizard
- **Parallel generation**: Generate multiple panels concurrently

## Quick Start

```bash
# Interactive initialization
bun scripts/main.ts init my-comic

# Generate comic
bun scripts/main.ts generate -c my-comic/flexicomic.json

# Generate with parallel processing
bun scripts/main.ts generate -c my-comic/flexicomic.json --parallel --concurrency 4
```

## Commands

### `init <project-name>`

Interactive initialization wizard for creating a new comic project.

```bash
bun scripts/main.ts init my-comic
```

Prompts for:
- Comic title and metadata
- Art style (manga, ligne-claire, realistic, ink-brush, chalk)
- Tone (neutral, warm, dramatic, romantic, energetic)
- Page settings (aspect ratio, DPI)
- Character definitions
- Panel layouts

### `generate -c <config.json> [options]`

Generate comic panels and pages.

```bash
# Generate all
bun scripts/main.ts generate -c my-comic/flexicomic.json

# Generate specific pages
bun scripts/main.ts generate -c my-comic/flexicomic.json --pages 1-3

# Generate specific panels
bun scripts/main.ts generate -c my-comic/flexicomic.json --panels page1:1-3

# Parallel generation
bun scripts/main.ts generate -c my-comic/flexicomic.json --parallel --concurrency 4

# Skip character reference generation
bun scripts/main.ts generate -c my-comic/flexicomic.json --skip-refs

# Skip page composition (generate panels only)
bun scripts/main.ts generate -c my-comic/flexicomic.json --skip-composite
```

Options:
- `-c, --config <path>` - Configuration file path (required)
- `-o, --output <dir>` - Output directory (default: config directory)
- `--pages <range>` - Page range (e.g., `1-3,5`)
- `--panels <range>` - Panel range (e.g., `page1:1-3`)
- `--parallel` - Enable parallel generation
- `--concurrency <n>` - Concurrent jobs (1-8, default: 4)
- `--provider <name>` - Image generation provider
- `--skip-refs` - Skip character reference generation
- `--skip-composite` - Skip page composition
- `-v, --verbose` - Verbose output

### `preview -c <config.json>`

Preview the comic layout without generating images.

```bash
bun scripts/main.ts preview -c my-comic/flexicomic.json
```

### `composite -c <config.json> [options]`

Compose pages from generated panels.

```bash
# Compose all pages
bun scripts/main.ts composite -c my-comic/flexicomic.json

# Compose specific pages
bun scripts/main.ts composite -c my-comic/flexicomic.json --pages 1-3
```

## Configuration File

The `flexicomic.json` configuration file defines the entire comic structure:

```json
{
  "meta": {
    "title": "Comic Title",
    "author": "Author Name",
    "version": "1.0.0"
  },
  "style": {
    "artStyle": "manga",
    "tone": "warm",
    "basePrompt": "Japanese manga style"
  },
  "pageSettings": {
    "aspectRatio": "3:4",
    "dpi": 300,
    "outputFormat": "png"
  },
  "characters": [
    {
      "id": "char1",
      "name": "Protagonist",
      "role": "protagonist",
      "description": "Young brave hero",
      "visualSpec": {
        "age": "18-20",
        "hair": "Black short hair",
        "eyes": "Large brown eyes",
        "outfit": "Blue jacket"
      },
      "expressions": ["neutral", "happy", "angry", "sad"],
      "angles": ["front", "3q", "profile", "back"]
    }
  ],
  "pages": [
    {
      "id": "page1",
      "title": "Chapter 1",
      "layout": {
        "type": "custom",
        "grid": { "rows": 2, "cols": 2, "gutter": 10 },
        "panels": [
          {
            "id": "p1-1",
            "position": { "row": 0, "col": 0 },
            "rowspan": 1,
            "colspan": 2,
            "sizeRatio": 0.4,
            "prompt": "Peaceful village at dawn",
            "characters": [],
            "focus": "environment"
          }
        ]
      }
    }
  ]
}
```

## Art Styles

| Style | Description |
|-------|-------------|
| `manga` | Japanese manga/anime style with expressive characters, large eyes, clean smooth lines |
| `ligne-claire` | Clean line art, European comic aesthetic, flat colors, minimal shading |
| `realistic` | Realistic proportions and detailed rendering with natural lighting |
| `ink-brush` | Traditional ink brush painting style, calligraphic strokes, expressive line weight |
| `chalk` | Chalkboard texture, educational aesthetic, hand-drawn chalk feel |

## Tones

| Tone | Description |
|------|-------------|
| `neutral` | Balanced tone, natural colors, even lighting |
| `warm` | Warm golden lighting, nostalgic atmosphere, soft yellow-orange cast |
| `dramatic` | High contrast, deep shadows, intense lighting, bold colors |
| `romantic` | Soft pastel colors, gentle lighting, dreamy atmosphere |
| `energetic` | Vibrant saturated colors, dynamic energy, bright highlights |
| `vintage` | Sepia-toned, aged paper aesthetic, muted colors |
| `action` | High energy, sharp contrasts, dynamic motion blur |

## Layout Types

| Type | Description |
|------|-------------|
| `custom` | Fully custom grid layout |
| `2x2-grid` | 2x2 equal panels |
| `cinematic` | Wide top panel, smaller bottom panels |
| `webtoon` | Vertical scrolling format |

## Output Structure

```
my-comic/
├── flexicomic.json           # Configuration file
├── characters/               # Character reference images
│   ├── {char-id}/
│   │   ├── expressions.png   # 3x3 expression grid
│   │   ├── angles.png        # 2x2 angle grid
│   │   ├── fullbody.png      # Full body reference
│   │   └── palette.png       # Color palette
├── panels/                   # Individual panel images
│   ├── p1-1.png
│   ├── p1-2.png
│   └── ...
├── pages/                    # Composed pages
│   ├── page1.png
│   └── ...
```

## Character References

For each character, the tool generates:

1. **Expressions Grid** (3x3): neutral, happy, sad, angry, surprised, worried, thinking, embarrassed, excited
2. **Angles Grid** (2x2): front, three-quarter, profile, back
3. **Full Body**: Full body reference
4. **Color Palette**: Character color scheme

These references are automatically used during panel generation to maintain character consistency.

## Image Generation

Panel generation requires an image generation API. Configure via environment variables:

```bash
# Google Gemini (recommended)
GOOGLE_API_KEY=your_key

# OpenAI
OPENAI_API_KEY=your_key

# DashScope (Alibaba)
DASHSCOPE_API_KEY=your_key
```

Create a `.env` file in your project directory or use `~/.flexicomic/.env`.

## Templates

Reference templates are available in `templates/`:

- `config-template.json` - Starting configuration template
- `story-template.md` - Story structure template

## Layout Examples

Predefined layouts in `references/layouts/`:

- `2x2-grid.json` - Equal 2x2 grid
- `cinematic.json` - Wide cinematic layout
- `webtoon.json` - Vertical scrolling format

## Workflow Example

1. **Initialize project**
   ```bash
   bun scripts/main.ts init my-story
   ```

2. **Edit configuration** (optional)
   ```bash
   # Edit my-story/flexicomic.json to customize
   ```

3. **Generate comic**
   ```bash
   bun scripts/main.ts generate -c my-story/flexicomic.json --parallel
   ```

4. **Review output**
   ```bash
   # Check my-story/pages/ for composed pages
   ```

## Tips

- **Start simple**: Begin with 1-2 pages and few panels
- **Use preview**: Run `preview` command before generating
- **Parallel generation**: Use `--parallel` for faster generation on multiple panels
- **Character consistency**: The more expressions/angles defined, the better consistency
- **Iterate**: Generate specific panels with `--panels` flag for updates

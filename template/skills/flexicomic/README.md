# flexicomic

> Flexible comic/manga generation with full customization support for Claude Code

![flexicomic](https://img.shields.io/badge/version-1.0.0-blue)
![license](https://img.shields.io/badge/license-MIT-green)

## Features

- **Custom Panel Layouts** - Define any grid structure with custom panel sizes and positions
- **Character Consistency** - Multi-angle, multi-expression character reference generation
- **Interactive Setup** - Step-by-step configuration wizard
- **Parallel Generation** - Generate multiple panels concurrently
- **Multiple Art Styles** - manga, ligne-claire, realistic, ink-brush, chalk
- **Multiple Tones** - neutral, warm, dramatic, romantic, energetic, vintage, action
- **PDF Export** - Automatic PDF generation from your comics

## Quick Start

### 1. Install the Skill

```bash
# Clone to your local skills directory
git clone https://github.com/your-username/flexicomic.git ~/.claude-plugins/flexicomic

# Or clone to anywhere you want
git clone https://github.com/your-username/flexicomic.git
cd flexicomic
```

### 2. Configure Image Generation API

Create `~/.flexicomic/.env` with your API key:

```bash
# Choose one of the following:

# Google Gemini (recommended)
GOOGLE_API_KEY=your_api_key_here

# Or OpenAI
OPENAI_API_KEY=your_api_key_here

# Or DashScope (Alibaba)
DASHSCOPE_API_KEY=your_api_key_here
```

### 3. Create Your First Comic

```bash
cd flexicomic

# Interactive initialization
bun scripts/main.ts init my-comic

# Generate comic
bun scripts/main.ts generate -c my-comic/flexicomic.json

# Export to PDF
bun scripts/main.ts pdf -c my-comic/flexicomic.json
```

## Installation Methods

### Method 1: Claude Plugins Directory (Recommended)

```bash
# Install to Claude plugins directory
git clone https://github.com/your-username/flexicomic.git ~/.claude-plugins/flexicomic

# Restart Claude Code and use directly in conversations
```

### Method 2: Local Directory

```bash
# Clone anywhere
git clone https://github.com/your-username/flexicomic.git
cd flexicomic

# Run commands directly
bun scripts/main.ts init my-comic
```

### Method 3: Global Install (with npm)

```bash
git clone https://github.com/your-username/flexicomic.git
cd flexicomic
npm install
npm link

# Use anywhere
flexicomic init my-comic
```

## Commands

| Command | Description |
|---------|-------------|
| `init <name>` | Initialize a new comic project interactively |
| `generate -c <config>` | Generate comic panels and pages |
| `preview -c <config>` | Preview layout without generating images |
| `composite -c <config>` | Compose pages from generated panels |
| `pdf -c <config>` | Merge pages to PDF |

## Usage Examples

### Interactive Mode

```bash
# The init command will guide you through:
# - Comic title and metadata
# - Art style selection (manga, ligne-claire, realistic, ink-brush, chalk)
# - Tone selection (neutral, warm, dramatic, romantic, energetic)
# - Page settings (aspect ratio, DPI)
# - Character definitions
# - Panel layouts

bun scripts/main.ts init my-adventure
```

### Generate Options

```bash
# Generate all pages
bun scripts/main.ts generate -c my-adventure/flexicomic.json

# Generate specific pages
bun scripts/main.ts generate -c my-adventure/flexicomic.json --pages 1-3

# Generate specific panels
bun scripts/main.ts generate -c my-adventure/flexicomic.json --panels page1:1-3

# Parallel generation (faster)
bun scripts/main.ts generate -c my-adventure/flexicomic.json --parallel --concurrency 4

# Skip character references (faster, less consistent)
bun scripts/main.ts generate -c my-adventure/flexicomic.json --skip-refs

# Regenerate panels only (skip page composition)
bun scripts/main.ts generate -c my-adventure/flexicomic.json --skip-composite
```

### Preview Before Generating

```bash
# Preview layout to verify everything looks correct
bun scripts/main.ts preview -c my-adventure/flexicomic.json
```

## Configuration

The `flexicomic.json` file controls your entire comic:

```json
{
  "meta": {
    "title": "My Adventure",
    "author": "Your Name",
    "version": "1.0.0"
  },
  "style": {
    "artStyle": "manga",
    "tone": "warm",
    "basePrompt": "Japanese manga style, warm golden lighting"
  },
  "pageSettings": {
    "aspectRatio": "3:4",
    "dpi": 300,
    "outputFormat": "png"
  },
  "characters": [
    {
      "id": "hero",
      "name": "Alex",
      "role": "protagonist",
      "description": "A brave young hero",
      "visualSpec": {
        "age": "18-20 years old",
        "hair": "short brown hair",
        "eyes": "large green eyes",
        "outfit": "adventurer's outfit with cloak"
      },
      "expressions": ["neutral", "happy", "determined", "worried"],
      "angles": ["front", "3q", "profile", "back"]
    }
  ],
  "pages": [
    {
      "id": "page1",
      "title": "Chapter 1: The Beginning",
      "layout": {
        "type": "custom",
        "grid": { "rows": 2, "cols": 2, "gutter": 10 },
        "panels": [
          {
            "id": "p1-1",
            "position": { "row": 0, "col": 0 },
            "rowspan": 1,
            "colspan": 2,
            "prompt": "Peaceful village at sunrise, traditional cottages with thatched roofs, mountains in background",
            "characters": [],
            "focus": "environment"
          },
          {
            "id": "p1-2",
            "position": { "row": 1, "col": 0 },
            "prompt": "Close up of Alex waking up and stretching, morning light streaming through window",
            "characters": [
              {
                "id": "hero",
                "expression": "neutral",
                "angle": "front",
                "action": "waking up and stretching"
              }
            ],
            "focus": "character"
          },
          {
            "id": "p1-3",
            "position": { "row": 1, "col": 1 },
            "prompt": "Alex looking out window with determined expression, seeing smoke rising from distant forest",
            "characters": [
              {
                "id": "hero",
                "expression": "worried",
                "angle": "3q"
              }
            ],
            "focus": "character"
          }
        ]
      }
    }
  ]
}
```

## Art Styles Reference

| Style | Description | Best For |
|-------|-------------|----------|
| `manga` | Japanese manga/anime with expressive characters, large eyes, clean lines | Action, romance, slice-of-life |
| `ligne-claire` | Clean line art, European comic aesthetic, flat colors | Adventure, mystery, storytelling |
| `realistic` | Realistic proportions with detailed rendering | Drama, thriller, historical |
| `ink-brush` | Traditional ink brush painting, calligraphic strokes | Martial arts, historical, fantasy |
| `chalk` | Chalkboard texture, educational aesthetic | Tutorial, educational, light comedy |

## Tones Reference

| Tone | Mood | Colors |
|------|------|--------|
| `neutral` | Balanced, objective | Natural, even tones |
| `warm` | Nostalgic, comforting | Golden, orange, soft yellow |
| `dramatic` | Intense, theatrical | High contrast, deep shadows |
| `romantic` | Gentle, emotional | Soft pastels, pinks, roses |
| `energetic` | Exciting, dynamic | Vibrant, saturated, bright |
| `vintage` | Nostalgic, aged | Sepia, muted, desaturated |
| `action` | Intense, powerful | Sharp contrasts, bold colors |

## Output Structure

```
my-comic/
├── flexicomic.json           # Your configuration
├── characters/               # Character reference sheets
│   ├── hero/
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
└── My Adventure.pdf          # Final PDF
```

## Environment Variables

Create `~/.flexicomic/.env` or `.flexicomic/.env` in your project:

```bash
# Image Generation API (choose one)
GOOGLE_API_KEY=your_key_here
# OPENAI_API_KEY=your_key_here
# DASHSCOPE_API_KEY=your_key_here

# Optional: Custom base URLs
# GOOGLE_BASE_URL=https://generativelanguage.googleapis.com
# OPENAI_BASE_URL=https://api.openai.com
# DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com
```

## Requirements

- **Bun** v1.0+ (recommended) or Node.js v18+
- Image generation API key (Google, OpenAI, or DashScope)
- 4GB+ RAM recommended for parallel generation

## Tips

- **Start Simple**: Begin with 1-2 pages and few panels
- **Use Preview**: Run `preview` before generating to save time
- **Parallel Generation**: Use `--parallel` for faster multi-panel generation
- **Character Consistency**: More expressions/angles defined = better consistency
- **Iterate**: Use `--panels` to regenerate specific panels

## Troubleshooting

### "No API key found" error

Create `~/.flexicomic/.env` with your API key:

```bash
mkdir -p ~/.flexicomic
echo "GOOGLE_API_KEY=your_key" > ~/.flexicomic/.env
```

### Canvas/image processing errors

Install canvas dependencies:

```bash
# Ubuntu/Debian
sudo apt-get install build-essential libcairo2-dev libpango1.0-dev libjpeg-dev libgif-dev librsvg2-dev

# macOS
brew install pkg-config cairo pango libgif jpeg

# Windows
# Install GTK3 from https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer
```

### PDF generation fails

Install pdf-lib:

```bash
bun add pdf-lib
# or
npm install pdf-lib
```

## License

MIT License - see LICENSE file for details

## Contributing

Contributions welcome! Please feel free to submit issues and pull requests.

## Acknowledgments

- Built for [Claude Code](https://claude.ai/code)
- Uses image generation from Google Gemini, OpenAI, or DashScope
- PDF generation via [pdf-lib](https://pdf-lib.js.org/)
- Canvas operations via [node-canvas](https://github.com/Automattic/node-canvas)

---

**Made with ❤️ by SCF**

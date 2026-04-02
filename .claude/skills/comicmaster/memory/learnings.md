# ComicMaster Learnings

Hier werden Erkenntnisse aus jeder Comic-Generierung dokumentiert.

---

### 2026-02-08 — MVP Build & Integration Test

**Projekt:** "The Tired Detective" (4 Panels, 1 Seite, DreamShaperXL)

**Was funktioniert hat:**
- End-to-end Pipeline: Story Plan → Panels → Bubbles → Layout → PDF in 64.5s
- DreamShaperXL mit 8 Steps: 48s erstes Panel (Model-Load), danach 4s/Panel
- Page Layout (2x2 Grid) mit Borders, Gutters, Page Numbers sauber
- 6 Bubble-Typen (speech, thought, shout, whisper, narration, caption)

**Probleme & Fixes:**
- **Bubble-Clipping v1:** 4/7 Bubbles am Panel-Rand abgeschnitten
  - Fix: Position-Hints von 0.22 auf 0.30 verschoben
  - Fix: Safe-Margin von 4px auf 20px erhöht
  - Fix: Adaptive max_width_ratio basierend auf X-Position
  - Fix: Font-Grössen reduziert (0.035 → 0.030 für speech)
  - **Ergebnis v3:** 0/7 Bubbles abgeschnitten ✅

- **Text in generierten Bildern:** SDXL generiert manchmal Pseudo-Text (Zeitungen, Schilder)
  - Fix: Negative Prompt erweitert um "text, words, letters, lettering, typography, logo, speech bubble, word balloon, alphabet, writing, inscription, label"
  - **Wichtig:** Flux hat KEINE negative Prompts (nutzt nur CFG Guidance)
  - Bei Flux stattdessen im positiven Prompt "no text, clean image" hinzufügen

**Negative Prompts – Modell-Unterschiede:**
| Modell | Negative Prompt Support | CFG | Notiz |
|--------|------------------------|-----|-------|
| SDXL (DreamShaper etc.) | ✅ Ja, wichtig | 2.0-7.0 | Turbo-Modelle: CFG 1.5-2.5 |
| Flux | ❌ Nein | 3.0-4.0 | Nur FluxGuidance, kein neg. conditioning |
| SD1.5 | ✅ Ja | 7.0-12.0 | Stärkster Effekt bei hohem CFG |

**Prompt-Patterns die funktionierten:**
- "{shot_type} shot, {camera_angle}, {style} art style, comic panel" als Prefix
- Charakter-Beschreibung detailliert im Prompt → bessere Ergebnisse
- "comic book art style, bold outlines" für Western-Comic

**Technische Erkenntnisse:**
- `--skip-generate` braucht Panels im gleichen Output-Ordner
- Bubble-Positionierung muss Page-Layout-Cropping berücksichtigen
- PIL/Pillow Approach für Bubbles ist flexibler als ComfyUI Nodes

### 2026-02-08 — Tail-Length Fix

**Problem:** Speech-Bubble Tails waren viel zu lang — gingen quer durchs halbe Panel statt nur kurz die Richtung anzudeuten.

**Fix:** Tail-Länge auf max. 45% der Bubble-Höhe begrenzt. Richtungsvektor wird skaliert statt raw target verwendet.
- Betrifft: `_draw_speech_tail()` und `_draw_thought_trail()`
- Thought-Trail Kreise ebenfalls verkürzt

**Learning:** Tail-Target (Charakter-Position) ist nur die *Richtung*, nicht das *Ziel*. Der Tail muss kurz bleiben — wie ein Zeiger, nicht wie ein Speer.

### 2026-02-08 — Shot-List & Dynamic Layout

**Erweiterte Prompts:**
- `character_poses`, `character_emotions`, `lighting`, `background_detail` → deutlich bessere Panel-Qualität
- "no text, no letters, no words, clean image" im positiven Prompt + erweiterter Negative Prompt → weniger Text-Artefakte
- Noir-Lighting Tag funktioniert hervorragend für Detective-Szenen

**Dynamic Layouts:**
- `auto_layout()` funktioniert, aber bei nur 4 Panels auf einer Seite sieht es fast wie 2x2 aus
- Dramatischer Unterschied erst bei 6+ Panels mit Mix aus high/low/medium
- Splash-Panel bekommt eigene Seite → sehr cinematic

**Timing v2:** 5 Panels in 33.7s (DreamShaperXL, Model schon geladen: 4-7s/Panel)

### 2026-02-08 — IPAdapter Character Consistency (Phase 2)

**Setup:**
- IPAdapterUnifiedLoader + IPAdapterAdvanced bereits in ComfyUI installiert
- CLIP Vision Models vorhanden: ViT-H-14, ViT-bigG-14
- Presets: PLUS (high strength), PLUS FACE (portraits)

**Workflow:**
1. Character Reference Sheet generieren (1024x1024, clean background)
2. Upload zu ComfyUI via `/upload/image` Endpoint
3. IPAdapter-Workflow: CheckpointLoader → IPAdapterUnifiedLoader → IPAdapterAdvanced → KSampler

**Weight-Tuning nach Shot-Type:**
| Shot | IPAdapter Weight | Preset |
|------|-----------------|--------|
| extreme_wide | 0.4 | PLUS |
| wide | 0.5 | PLUS |
| medium | 0.65 | PLUS |
| medium_close | 0.7 | PLUS FACE |
| close_up | 0.8 | PLUS FACE |
| extreme_close | 0.5 | PLUS FACE |

**Ergebnis:** Exzellente Konsistenz bei rotem Haar, grünen Augen, Lederjacke über 3 verschiedene Szenen.

**Timing:** Ref: 6.2s, Panel mit IPAdapter: 9-10s (vs. 4s ohne)

**Learning:**
- `upload_image()` nutzt multipart/form-data (pure urllib, kein requests nötig)
- PLUS FACE Preset für Close-Ups → stärkere Gesichtskonsistenz
- weight_type "style transfer" + end_at 0.8 → guter Balance zwischen Konsistenz und Kreativität

### 2026-02-08 — Neue Bubble-Typen

4 neue Typen hinzugefügt (total: 10):
- **explosion** — 24-Spike Starburst, gelb, für SFX (BOOM!, CRASH!)
- **electric** — Zigzag-Rand, cyan, für Roboter/elektronische Sprache
- **connected** — 2 Tails für Gruppen-Dialog (tail_target_2 Parameter)
- **scream** — 20-Spike irregular, rot, für extreme Emotionen

### 2026-02-08 — Bubble-über-Gesicht Fix

**Problem:** Bubbles wurden manchmal direkt über Charakter-Gesichter platziert.

**Fix:**
- Position Hints Y-Werte nach oben verschoben (0.16 → 0.12)
- Shot-Type-abhängige Positionierung:
  - close_up / extreme_close: Y max 0.10 (ganz oben)
  - medium_close: Y max 0.12
  - wide/medium: Standard (0.12)
- Tail-Targets auch höher (0.55 → 0.40) → kürzere Tails + weniger Überlappung
- Mehrere Dialogzeilen werden vertikal gestaffelt (+0.06 pro Zeile)

**Learning:** Bei Close-Ups füllt das Gesicht >60% des Panels → Bubbles MÜSSEN ganz oben oder ganz unten sein. In echten Comics sind Bubbles bei Close-Ups fast immer am oberen Rand.

### 2026-02-08 — Workflows exportiert

Workflows als ladbare JSON-Dateien gespeichert in `skills/comicmaster/workflows/`:
- `panel_sdxl.json` — Standard Panel
- `panel_ipadapter.json` — Panel mit Character Consistency
- `character_ref.json` — Character Reference Sheet
- `panel_upscale.json` — Panel Upscaling (4x-UltraSharp)

### 2026-02-08 — SFX (Sound Effects)

11. Bubble-Typ `sfx` hinzugefügt:
- Grosser rotierter Text (8% Panel-Höhe) mit schwarzem Outline
- Kein Bubble-Hintergrund, direkt aufs Panel
- Rotation konfigurierbar (default -12°)
- RGBA Layer + Alpha Composite Technik

### 2026-02-08 — LoRA Style Switching

- 90 LoRAs in ComfyUI verfügbar
- 7 Styles gemappt: western, cartoon, noir, realistic, neon, artistic (+ manga needs download)
- `_insert_lora_nodes()` rewired Model+CLIP Referenzen downstream
- Node IDs ab 900 um Kollisionen zu vermeiden
- LoRAs werden auch für Character Refs angewendet (konsistenter Style)
- Workflow JSON: `workflows/panel_sdxl_lora.json`

### 2026-02-08 — Batch Optimization

- `batch_optimizer.py` gruppiert Panels nach IPAdapter-Bedarf
- Reihenfolge: no IPA → single char → multi char, innerhalb nach char-combination sortiert
- Test: 9→5 Model-Switches bei 10 Panels
- ETA-Tracking mit Rolling Average der letzten 5 Panels
- Progress-Output alle 10 Panels

### 2026-02-08 — Panel Upscaling

- 7 Upscale-Models bereits in ComfyUI vorhanden
- 4x-UltraSharp.pth als Default (beste Allround-Qualität)
- Model-Methode: 8.1s, 3.4MB pro Panel (768→1573px)
- Simple/PIL: 0.7s, 2.3MB (768→1536px) – guter Fallback
- CLI: `python upscale.py <image> --scale 2.0 --method auto`

### 2026-02-08 — 30-Panel Stresstest "The Last Courier"

**Ergebnis:** 30/30 Panels, 7 Seiten, 372.6s (6:12 Min)
- Avg ~12.4s/Panel (inkl. Model-Switches)
- Batch-Optimizer: 15→5 Model-Switches
- 3 Character Refs generiert (Kira, Dex, Kovac)
- LoRA: xl_more_art-full (western style)
- Multi-IPAdapter: 7 Panels mit 2+ Chars
- 14 Speech Bubbles + 2 SFX

**Timing-Breakdown:**
- Char Refs: ~22s (3 Refs)
- No-IPA Panels: ~5s
- Single-IPA Panels: ~8-10s  
- Multi-IPA Panels: ~11-13s
- Model-Switch: +25s (einmalig pro Wechsel)
- Bubbles + Layout + Export: ~15s

**Learning:** Bei 30 Panels ist Batch-Optimization entscheidend. Ohne Optimizer wären 15 Model-Switches nötig (á ~25s extra = 375s mehr). Mit Optimizer nur 5 Switches → ~250s gespart.

### 2026-02-08 — P0 Lettering Fixes & Sequential Composition

**Narration Duplicate Bug:**
- Story plans often have BOTH `narration: "text"` field AND a `dialogue` entry with `type: "narration"` containing the same text
- `comic_pipeline.py` Stage 2 added both as separate bubbles → duplicate narration boxes on panels 01, 02, 30
- **Fix:** Added deduplication check — if narration text already appears in dialogue bubbles, skip adding it again
- Panels 01, 02, 30 now show 1 bubble instead of 2 ✅

**Text Wrapping & Adaptive Font Sizing:**
- Previous issue: text clipped inside bubbles when bubble clamped to panel bounds
- **Fix 1:** Adaptive font sizing loop — if bubble would be >45% of panel height, shrink font (up to 6 iterations, min 1/3 of base size)
- **Fix 2:** Reduced safe_margin from 12% to 8%, increased min wrap ratio from 0.18 to 0.20 — gives bubbles more room
- **Fix 3:** Skip empty-text bubbles entirely
- Bubble clipping on individual panels: FIXED ✅
- Remaining issue: page_layout.py crops panels when placing them in grid → edge bubbles can still get clipped at page level. This is a page_layout concern (P1).

**Lazy Import for --skip-generate:**
- `comic_pipeline.py` imported `panel_generator` at module level, which imports `comfy_client`, which tries to connect to ComfyUI
- When running `--skip-generate` (layout-only), ComfyUI isn't needed → import hangs
- **Fix:** Made panel_generator import lazy — only loaded when actually generating panels
- `--skip-generate` now works without ComfyUI running ✅

**Sequential Composition Rules (panel_generator.py):**
- New function `_get_sequential_composition_tags()` adds composition directives to prompts:
  - **Anti-centering:** "off-center composition, rule of thirds" + alternating "subject in left/right third"
  - **Eyeline direction:** Dialogue panels alternate "looking left/right" based on sequence number
  - **Shot progression hints:** If previous panel was wide, suggest "tighter framing" and vice versa
  - **Mood-based composition:** Action = "dynamic diagonal composition", tense = "tight framing", calm = "breathing room"
- Changed panel identifier from "comic panel" to "sequential comic book panel, storytelling frame"
- Enhanced negative prompt with: "centered composition, passport photo, symmetrical, static pose, fashion photography, stock photo"
- `build_panel_prompt()` now accepts optional `all_panels` parameter for cross-panel context
- `generate_panel()` passes `all_panels` through to prompt builder

**Quality Tracker Phase 1:**
- Created `quality_tracker.py` — PIL-only metrics (zero external dependencies)
- 6 metrics: Sharpness (Laplacian variance), Contrast (RMS), Saturation (mean HSV), Color Entropy, Edge Density, Exposure Balance
- Composite technical score (0-100) with weighted normalization
- Batch mode with summary report (ASCII art dashboard)
- 30 panels scored in 1.5s (49ms/panel)
- Test results on test_30panel: mean=51.7, min=46.1, max=59.1
- Best panel: panel_26 (night city scene, high sharpness + good exposure)
- Worst panel: panel_01 (dark city establishing shot, low contrast balance)

---

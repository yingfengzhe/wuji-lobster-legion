# ComicMaster Style Guides

## Western Comic

**Prompt-Tags:**
```
comic book art style, bold outlines, vibrant colors, dynamic composition,
western comic, cel shading, ink lines, halftone dots
```

**Negative:** `anime, manga, chibi, kawaii`

**Characteristics:**
- Bold black outlines, strong contrast
- Vibrant, saturated colors
- Dynamic action poses, foreshortening
- Muscular/heroic proportions
- Dramatic lighting with hard shadows

**Best Models:** DreamShaperXL, JuggernautXL
**Best LoRAs:** Eldritch Comics, Comic Book Style SDXL

---

## Manga (B&W)

**Prompt-Tags:**
```
manga art style, black and white, screentone shading, clean lines,
manga panel, high contrast, monochrome, japanese comic style
```

**Negative:** `color, colorful, western comic, realistic photo`

**Characteristics:**
- Clean precise lines, minimal hatching
- Screentone patterns for shading
- Expressive eyes, simplified features
- Speed lines for motion
- Black and white (no color)

**Best Models:** Pony Diffusion V6 XL + manga LoRA, AnimagineXL
**Best LoRAs:** Manga Shade, Manga Master, AKIRA Manga FLUX

---

## Manga (Color)

**Prompt-Tags:**
```
color manga art style, anime illustration, clean lines, cel shading,
vibrant colors, japanese anime style, light novel illustration
```

**Characteristics:**
- Clean lines like B&W manga but with flat color fills
- Soft gradients, pastel or vibrant palette
- Large expressive eyes
- Simplified backgrounds with detail bursts

**Best Models:** Pony Diffusion V6 XL, Illustrious XL, AnimagineXL
**Best LoRAs:** DreamART Style

---

## Cartoon

**Prompt-Tags:**
```
cartoon art style, bright colors, exaggerated proportions, fun,
animated style, bold outlines, simple shapes, playful
```

**Negative:** `realistic, photorealistic, dark, gritty`

**Characteristics:**
- Exaggerated proportions (big heads, small bodies)
- Bright, cheerful colors
- Thick outlines, simple shapes
- Bouncy, rubbery poses
- Minimal shading

**Best Models:** DreamShaperXL, RealCartoon3D
**Best LoRAs:** Cartoon Arcadia

---

## Noir

**Prompt-Tags:**
```
noir comic art style, high contrast, dramatic shadows, black and white,
film noir, dark atmosphere, chiaroscuro, detective noir
```

**Characteristics:**
- Extreme contrast (deep blacks, bright whites)
- Heavy shadow use, venetian blind patterns
- Moody, atmospheric
- Limited or no color (or desaturated)
- Rain, smoke, fog

**Best Models:** DreamShaperXL + high CFG
**Best LoRAs:** Eldritch Comics (noir variant)

---

## Realistic / Semi-Realistic

**Prompt-Tags:**
```
semi-realistic illustration, detailed shading, cinematic lighting,
graphic novel art style, painted illustration, realistic proportions
```

**Characteristics:**
- Realistic proportions and anatomy
- Painterly shading and rendering
- Cinematic composition
- Detailed backgrounds
- Muted, natural color palette

**Best Models:** JuggernautXL, CyberRealisticXL
**Best LoRAs:** Comic Book Page Style (realistic mode)

---

## Prompt Building Tips

### Shot Type Tags
| Type | Prompt Addition |
|------|----------------|
| Extreme wide | `extreme wide shot, tiny figures, full environment` |
| Wide | `wide shot, full body, environment visible` |
| Medium | `medium shot, waist up` |
| Medium close | `chest up, upper body` |
| Close-up | `close-up, face and shoulders` |
| Extreme close | `extreme close-up, detail focus` |

### Mood Enhancers
| Mood | Tags |
|------|------|
| Dramatic | `dramatic lighting, intense, cinematic` |
| Comedic | `lighthearted, bright, exaggerated expressions` |
| Horror | `dark, ominous, unsettling, shadows` |
| Romantic | `soft lighting, warm colors, gentle` |
| Action | `dynamic, motion blur, impact, energy lines` |

---

## Lighting as Storytelling Tool

> **Key Principle:** Lighting is not decoration — it's a narrative device. Every panel's lighting should reinforce the emotional beat of that moment.

### Mood → Lighting Directive Map

| Mood | Lighting Directive | Notes |
|------|-------------------|-------|
| **Tense / Danger** | `harsh side lighting, deep shadows, red accent lights` | High contrast, sharp shadow edges. Red or amber accent lights signal danger. |
| **Calm / Peaceful** | `soft diffused light, warm golden hour tones` | Low contrast, even illumination. Golden/warm palette. Minimal harsh shadows. |
| **Mysterious** | `low key lighting, rim light from behind, face half in shadow` | Most of the frame in darkness. Rim/edge light creates silhouette interest. |
| **Triumphant** | `backlit, lens flare, strong rim lighting, bright` | Character lit from behind — heroic glow. Bright, high-key with intentional lens artifacts. |
| **Sad / Melancholic** | `overcast flat lighting, muted colors, slight blue cast` | Flat, directionless light. Desaturated. Cool blue shift. No dramatic shadows. |
| **Horror / Fear** | `under-lighting, green-tinged, harsh unnatural shadows` | Light from below (campfire/screen). Unnatural shadow angles. Green/sickly tint. |
| **Romantic** | `soft warm lighting, bokeh background, subtle glow` | Diffused, intimate. Warm tones. Background softly blurred with light points. |
| **Action / Intense** | `dramatic directional light, high contrast, motion blur hints` | Strong single light source. Deep blacks and bright highlights. Dynamic feel. |
| **Dramatic** | `dramatic chiaroscuro, strong contrast, single key light` | Classic film lighting. Deep shadows carve the face. Painterly contrast. |
| **Dark** | `low key lighting, deep blacks, minimal fill light` | Mostly shadow. Only essential elements are lit. Noir-adjacent. |
| **Hopeful** | `warm backlight, soft lens flare, light breaking through` | Dawn/sunrise quality. Light piercing through clouds or doorways. |
| **Comedic** | `bright even lighting, cheerful highlights, minimal shadows` | Flat, cheerful illumination. No drama in the light — let the content be funny. |
| **Happy** | `bright warm lighting, natural sun, cheerful tones` | Warm, natural, inviting. Sunny day quality. |

### Lighting Consistency Rules

1. **Same scene = same light direction.** If the key light comes from the left in panel 1, it must come from the left in all panels of that scene (unless a diegetic change occurs — e.g., character turns on a lamp).

2. **Light direction serves composition.** Key light typically comes from the direction of interest — illuminating what matters, casting shadows away from the focal point.

3. **Transition lighting.** When mood shifts mid-scene, lighting should shift gradually (not abruptly). Use transitional panels to bridge lighting changes.

4. **Environmental consistency.** Indoor scenes: identify light sources (windows, lamps, screens). Outdoor scenes: sun position must remain consistent across a scene's panels.

5. **Color temperature as narrative.** Warm light = comfort, safety, the past. Cool light = tension, the future, isolation. Mixing warm and cool in one panel = conflict or unease.

### Lighting + Shot Type Interaction

| Shot Type | Lighting Consideration |
|-----------|----------------------|
| Extreme wide | Lighting defines the overall mood — atmospheric, environmental |
| Wide | Establish the light source visually (window, sun, lamp visible) |
| Medium | Standard key/fill/rim setup. Light sculpts the body |
| Close-up | Lighting sculpts the face. Catchlights in eyes are crucial |
| Extreme close-up | Minimal light setup. Single source. Every shadow tells a story |

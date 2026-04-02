/**
 * Prompt building utilities for panel generation
 */

import type { FlexicomicConfig, PanelConfig, CharacterConfig } from "../types.js";
import path from "node:path";
import { existsSync } from "node:fs";

export interface PromptBuildContext {
  config: FlexicomicConfig;
  page: FlexicomicConfig["pages"][number];
  panel: PanelConfig;
  characterRefs?: Map<string, string[]>;
}

// Built-in style descriptions (self-contained, no external dependencies)
const STYLE_DESCRIPTIONS: Record<string, string> = {
  manga: "Japanese manga/anime style with expressive characters, large eyes, clean smooth lines, dynamic poses, screen tone effects",
  "ligne-claire": "Clean line art style, European comic aesthetic, clear outlines, flat colors, minimal shading, detailed backgrounds",
  realistic: "Realistic art style with accurate proportions, detailed rendering, natural lighting, lifelike textures",
  "ink-brush": "Traditional ink brush painting style, calligraphic brush strokes, black and white ink, expressive line weight variation",
  chalk: "Chalkboard texture style, educational aesthetic, hand-drawn chalk feel, soft edges, warm blackboard background",
};

const TONE_DESCRIPTIONS: Record<string, string> = {
  neutral: "balanced tone, natural colors, even lighting",
  warm: "warm golden lighting, nostalgic atmosphere, soft yellow-orange cast, comforting mood",
  dramatic: "high contrast, deep shadows, intense lighting, bold colors, theatrical atmosphere",
  romantic: "soft pastel colors, gentle lighting, dreamy atmosphere, pink and rose hues",
  energetic: "vibrant saturated colors, dynamic energy, bright highlights, exciting mood",
  vintage: "sepia-toned, aged paper aesthetic, muted colors, nostalgic old photograph feel",
  action: "high energy, sharp contrasts, dynamic motion blur, intense drama",
};

export async function buildPanelPrompt(context: PromptBuildContext): Promise<string> {
  const { config, panel } = context;
  const parts: string[] = [];

  // 1. Base style prompt (built-in, no external file reading)
  const basePrompt = getBasePrompt(config.style.artStyle, config.style.tone);
  parts.push(basePrompt);

  // 2. Panel content prompt
  parts.push(panel.prompt);

  // 3. Character descriptions
  if (panel.characters && panel.characters.length > 0) {
    const characterPrompts = buildCharacterPrompts(context);
    if (characterPrompts) {
      parts.push(characterPrompts);
    }
  }

  // 4. Focus type modifier
  if (panel.focus) {
    parts.push(getFocusModifier(panel.focus));
  }

  return parts.join(", ").replace(/,\s*,/g, ",").trim();
}

function getBasePrompt(artStyle: string, tone: string): string {
  const styleDesc = STYLE_DESCRIPTIONS[artStyle] || STYLE_DESCRIPTIONS.manga;
  const toneDesc = TONE_DESCRIPTIONS[tone] || TONE_DESCRIPTIONS.neutral;
  return `${styleDesc}, ${toneDesc}`;
}

function buildCharacterPrompts(
  context: PromptBuildContext
): string | null {
  const { config, panel } = context;
  const characterPrompts: string[] = [];

  for (const panelChar of panel.characters || []) {
    const character = config.characters.find((c) => c.id === panelChar.id);
    if (!character) continue;

    const charParts: string[] = [];

    // Basic description
    if (character.description) {
      charParts.push(character.description);
    }

    // Visual spec
    if (character.visualSpec) {
      const specs: string[] = [];
      if (character.visualSpec.age) specs.push(`age ${character.visualSpec.age}`);
      if (character.visualSpec.hair) specs.push(character.visualSpec.hair);
      if (character.visualSpec.eyes) specs.push(character.visualSpec.eyes);
      if (character.visualSpec.outfit) specs.push(`wearing ${character.visualSpec.outfit}`);
      if (character.visualSpec.bodyType) specs.push(character.visualSpec.bodyType);
      if (character.visualSpec.distinctiveFeatures) {
        specs.push(character.visualSpec.distinctiveFeatures);
      }
      if (specs.length > 0) {
        charParts.push(specs.join(", "));
      }
    }

    // Expression
    if (panelChar.expression) {
      charParts.push(`${panelChar.expression} expression`);
    }

    // Action
    if (panelChar.action) {
      charParts.push(panelChar.action);
    }

    // Angle
    if (panelChar.angle) {
      charParts.push(`${panelChar.angle} angle`);
    }

    if (charParts.length > 0) {
      characterPrompts.push(charParts.join(", "));
    }
  }

  return characterPrompts.length > 0 ? characterPrompts.join("; ") : null;
}

function getFocusModifier(focus: string): string {
  const modifiers: Record<string, string> = {
    "character": "focus on character, close-up shot",
    "environment": "detailed environment background",
    "action": "dynamic action pose, motion blur effect",
    "dialogue": "character speaking, speech bubble composition",
    "close-up": "extreme close-up, facial expression focus",
    "wide": "wide shot, establish setting",
  };

  return modifiers[focus] || "";
}

export function getCharacterReferenceImages(
  context: PromptBuildContext,
  outputDir: string
): string[] {
  const { config, panel } = context;
  const refImages: string[] = [];

  for (const panelChar of panel.characters || []) {
    const character = config.characters.find((c) => c.id === panelChar.id);
    if (!character) continue;

    // Add expression reference if specified
    if (panelChar.expression) {
      const expressionsPath = path.join(outputDir, "characters", character.id, "expressions.png");
      if (existsSync(expressionsPath)) {
        refImages.push(expressionsPath);
      }
    }

    // Add angle reference if specified
    if (panelChar.angle) {
      const anglesPath = path.join(outputDir, "characters", character.id, "angles.png");
      if (existsSync(anglesPath)) {
        refImages.push(anglesPath);
      }
    }

    // Add full body reference
    const fullBodyPath = path.join(outputDir, "characters", character.id, "fullbody.png");
    if (existsSync(fullBodyPath)) {
      refImages.push(fullBodyPath);
    }
  }

  return refImages;
}

export function getExpressionIndex(expression: string): number {
  const expressions: Record<string, number> = {
    "neutral": 0,
    "happy": 1,
    "sad": 2,
    "angry": 3,
    "surprised": 4,
    "worried": 5,
    "thinking": 6,
    "embarrassed": 7,
    "excited": 8,
  };
  return expressions[expression] ?? 0;
}

export function getAngleIndex(angle: string): number {
  const angles: Record<string, number> = {
    "front": 0,
    "3q": 1,
    "three-quarter": 1,
    "profile": 2,
    "side": 2,
    "back": 3,
  };
  return angles[angle] ?? 0;
}

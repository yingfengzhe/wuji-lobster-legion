/**
 * Character reference generation
 */

import path from "node:path";
import { mkdir } from "node:fs/promises";
import type { FlexicomicConfig, CharacterConfig, CharacterReference } from "./types.js";
import { callImageGenWithRetry } from "./utils/image-gen-adapter.js";

const EXPRESSIONS = [
  "neutral",
  "happy",
  "sad",
  "angry",
  "surprised",
  "worried",
  "thinking",
  "embarrassed",
  "excited",
];

const ANGLES = [
  "front view",
  "three-quarter view",
  "side profile view",
  "back view",
];

export async function generateCharacterReferences(
  config: FlexicomicConfig,
  outputDir: string,
  provider?: string
): Promise<Map<string, CharacterReference>> {
  const refs = new Map<string, CharacterReference>();

  console.log("\nGenerating character references...");

  for (const character of config.characters) {
    console.log(`  Processing: ${character.name} (${character.id})`);

    const charDir = path.join(outputDir, "characters", character.id);
    await mkdir(charDir, { recursive: true });

    const charRef: CharacterReference = {
      characterId: character.id,
      images: {},
      generated: false,
    };

    try {
      // 1. Expressions grid (3x3)
      const expressionsPath = path.join(charDir, "expressions.png");
      await generateExpressionsGrid(character, expressionsPath, config, provider);
      charRef.images.expressions = expressionsPath;
      console.log(`    ✓ Generated expressions grid`);

      // 2. Angles grid (2x2)
      const anglesPath = path.join(charDir, "angles.png");
      await generateAnglesGrid(character, anglesPath, config, provider);
      charRef.images.angles = anglesPath;
      console.log(`    ✓ Generated angles grid`);

      // 3. Full body reference
      const fullBodyPath = path.join(charDir, "fullbody.png");
      await generateFullBodyRef(character, fullBodyPath, config, provider);
      charRef.images.fullBody = fullBodyPath;
      console.log(`    ✓ Generated full body reference`);

      // 4. Color palette
      const palettePath = path.join(charDir, "palette.png");
      await generateColorPalette(character, palettePath, config, provider);
      charRef.images.colorPalette = palettePath;
      console.log(`    ✓ Generated color palette`);

      charRef.generated = true;
    } catch (error) {
      console.warn(`    ⚠ Warning: Failed to generate references for ${character.id}: ${error}`);
    }

    refs.set(character.id, charRef);
  }

  console.log(`\n✓ Generated references for ${refs.size} character(s)`);
  return refs;
}

async function generateExpressionsGrid(
  character: CharacterConfig,
  outputPath: string,
  config: FlexicomicConfig,
  provider?: string
): Promise<void> {
  const charDesc = buildCharacterDescription(character);

  // Create a prompt for a 3x3 grid of expressions
  const expressions = EXPRESSIONS;
  const promptParts = [
    config.style.basePrompt,
    `character reference sheet for ${character.name}`,
    charDesc,
    "3x3 grid layout showing 9 different expressions",
    expressions.map((e, i) => `row ${Math.floor(i / 3) + 1} col ${(i % 3) + 1}: ${e} expression`).join(", "),
    "consistent character design",
    "white background",
    "reference sheet style",
  ];

  const prompt = promptParts.filter(Boolean).join(", ");

  await callImageGenWithRetry(
    {
      prompt,
      output: outputPath,
      ar: "1:1",
      quality: "2k",
      provider: provider as any,
    },
    2
  );
}

async function generateAnglesGrid(
  character: CharacterConfig,
  outputPath: string,
  config: FlexicomicConfig,
  provider?: string
): Promise<void> {
  const charDesc = buildCharacterDescription(character);

  const promptParts = [
    config.style.basePrompt,
    `character reference sheet for ${character.name}`,
    charDesc,
    "2x2 grid layout showing 4 different angles",
    `top left: ${ANGLES[0]}, top right: ${ANGLES[1]}, bottom left: ${ANGLES[2]}, bottom right: ${ANGLES[3]}`,
    "neutral expression",
    "consistent character design",
    "white background",
    "reference sheet style",
  ];

  const prompt = promptParts.filter(Boolean).join(", ");

  await callImageGenWithRetry(
    {
      prompt,
      output: outputPath,
      ar: "1:1",
      quality: "2k",
      provider: provider as any,
    },
    2
  );
}

async function generateFullBodyRef(
  character: CharacterConfig,
  outputPath: string,
  config: FlexicomicConfig,
  provider?: string
): Promise<void> {
  const charDesc = buildCharacterDescription(character);

  const promptParts = [
    config.style.basePrompt,
    `full body character reference for ${character.name}`,
    charDesc,
    "neutral expression",
    "front view",
    "standing pose",
    "arms at sides",
    "simple clean background",
    "character design reference",
  ];

  const prompt = promptParts.filter(Boolean).join(", ");

  await callImageGenWithRetry(
    {
      prompt,
      output: outputPath,
      ar: "3:4",
      quality: "2k",
      provider: provider as any,
    },
    2
  );
}

async function generateColorPalette(
  character: CharacterConfig,
  outputPath: string,
  config: FlexicomicConfig,
  provider?: string
): Promise<void> {
  const charDesc = buildCharacterDescription(character);

  const promptParts = [
    config.style.basePrompt,
    `color palette reference for ${character.name}`,
    charDesc,
    "color swatches",
    "hair color swatch",
    "eye color swatch",
    "skin tone swatch",
    "outfit color swatches",
    "character color scheme",
    "simple color palette layout",
    "white background",
  ];

  const prompt = promptParts.filter(Boolean).join(", ");

  await callImageGenWithRetry(
    {
      prompt,
      output: outputPath,
      ar: "1:1",
      quality: "2k",
      provider: provider as any,
    },
    2
  );
}

function buildCharacterDescription(character: CharacterConfig): string {
  const parts: string[] = [];

  if (character.description) {
    parts.push(character.description);
  }

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
      parts.push(specs.join(", "));
    }
  }

  return parts.join("; ");
}

export function getCharacterReferencePath(
  characterId: string,
  type: "expressions" | "angles" | "fullbody" | "palette",
  outputDir: string
): string {
  return path.join(outputDir, "characters", characterId, `${type}.png`);
}

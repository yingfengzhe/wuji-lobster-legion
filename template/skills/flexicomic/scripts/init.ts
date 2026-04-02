/**
 * Interactive project initialization
 */

import path from "node:path";
import { mkdir, writeFile } from "node:fs/promises";
import type { FlexicomicConfig } from "./types.js";

interface InitAnswers {
  title: string;
  author?: string;
  artStyle: string;
  tone: string;
  pageCount: number;
  aspectRatio: string;
}

const ART_STYLES = [
  { title: "日漫 (Manga)", value: "manga" },
  { title: "清线 (Ligne Claire)", value: "ligne-claire" },
  { title: "写实 (Realistic)", value: "realistic" },
  { title: "水墨 (Ink Brush)", value: "ink-brush" },
  { title: "粉笔 (Chalk)", value: "chalk" },
];

const TONES = [
  { title: "中性 (Neutral)", value: "neutral" },
  { title: "温馨 (Warm)", value: "warm" },
  { title: "戏剧 (Dramatic)", value: "dramatic" },
  { title: "浪漫 (Romantic)", value: "romantic" },
  { title: "活力 (Energetic)", value: "energetic" },
];

const ASPECT_RATIOS = [
  { title: "3:4 (Portrait)", value: "3:4" },
  { title: "4:3 (Landscape)", value: "4:3" },
  { title: "1:1 (Square)", value: "1:1" },
  { title: "16:9 (Wide)", value: "16:9" },
];

export async function initInteractive(projectName: string): Promise<void> {
  console.log(`\n🎨 Initializing flexicomic project: ${projectName}\n`);

  // Step 1: Basic information
  console.log("Step 1: Basic Information");
  const answers = await promptBasicInfo();

  // Step 2: Style selection
  console.log("\nStep 2: Style Selection");
  Object.assign(answers, await promptStyleSelection());

  // Step 3: Page settings
  console.log("\nStep 3: Page Settings");
  Object.assign(answers, await promptPageSettings());

  // Generate config
  const config = generateConfig(projectName, answers);

  // Create project directory
  const projectDir = path.resolve(projectName);
  await mkdir(projectDir, { recursive: true });

  // Write config file
  const configPath = path.join(projectDir, "flexicomic.json");
  await writeFile(configPath, JSON.stringify(config, null, 2), "utf8");
  console.log(`\n✓ Created: ${configPath}`);

  // Create output directories
  await createOutputDirectories(projectDir);

  // Ask if user wants to add characters
  console.log("\nStep 4: Characters");
  const addCharacters = await promptYesNo("Do you want to add characters now?");
  if (addCharacters) {
    await addCharactersInteractively(config);
    await writeFile(configPath, JSON.stringify(config, null, 2), "utf8");
    console.log(`✓ Updated: ${configPath}`);
  }

  // Ask if user wants to add panels
  console.log("\nStep 5: Panels");
  const addPanels = await promptYesNo("Do you want to add panels now?");
  if (addPanels) {
    await addPanelsInteractively(config);
    await writeFile(configPath, JSON.stringify(config, null, 2), "utf8");
    console.log(`✓ Updated: ${configPath}`);
  }

  console.log("\n✅ Project initialized successfully!");
  console.log(`\nNext steps:`);
  console.log(`  1. Edit ${configPath} to customize your comic`);
  console.log(`  2. Run: bun skills/baoyu-flexicomic/scripts/main.ts generate -c ${configPath}`);
}

async function promptBasicInfo(): Promise<Partial<InitAnswers>> {
  // Simple readline prompts
  const title = await promptInput("Comic title", "My Comic");
  const author = await promptInput("Author name (optional)", "");

  return { title, author: author || undefined };
}

async function promptStyleSelection(): Promise<Partial<InitAnswers>> {
  console.log("\nAvailable art styles:");
  ART_STYLES.forEach((s, i) => console.log(`  ${i + 1}. ${s.title}`));
  const artStyleIndex = parseInt(await promptInput("Select art style (1-5)", "1"), 10) - 1;
  const artStyle = ART_STYLES[artStyleIndex]?.value ?? "manga";

  console.log("\nAvailable tones:");
  TONES.forEach((t, i) => console.log(`  ${i + 1}. ${t.title}`));
  const toneIndex = parseInt(await promptInput("Select tone (1-5)", "1"), 10) - 1;
  const tone = TONES[toneIndex]?.value ?? "neutral";

  return { artStyle, tone };
}

async function promptPageSettings(): Promise<Partial<InitAnswers>> {
  console.log("\nAvailable aspect ratios:");
  ASPECT_RATIOS.forEach((a, i) => console.log(`  ${i + 1}. ${a.title}`));
  const arIndex = parseInt(await promptInput("Select aspect ratio (1-4)", "1"), 10) - 1;
  const aspectRatio = ASPECT_RATIOS[arIndex]?.value ?? "3:4";

  const pageCountInput = await promptInput("Number of pages to create", "1");
  const pageCount = Math.max(1, parseInt(pageCountInput, 10) || 1);

  return { aspectRatio, pageCount };
}

async function addCharactersInteractively(config: FlexicomicConfig): Promise<void> {
  console.log("\nAdding characters...");
  let addMore = true;

  while (addMore) {
    const charId = await promptInput("Character ID (e.g., char1)", `char${config.characters.length + 1}`);
    const name = await promptInput("Character name", "");
    const role = await promptSelect("Character role", ["protagonist", "antagonist", "supporting", "background"], "protagonist");
    const description = await promptInput("Character description", "");

    const character = {
      id: charId,
      name,
      role,
      description: description || undefined,
      expressions: ["neutral", "happy", "sad", "angry"],
      angles: ["front", "3q", "profile", "back"],
    };

    config.characters.push(character);
    console.log(`✓ Added character: ${name}`);

    addMore = await promptYesNo("Add another character?");
  }
}

async function addPanelsInteractively(config: FlexicomicConfig): Promise<void> {
  console.log("\nAdding panels...");
  const pageIndex = config.pages.length > 0 ? 0 : 0;

  if (config.pages.length === 0) {
    config.pages.push({
      id: "page1",
      title: "Page 1",
      layout: {
        type: "custom",
        grid: { rows: 2, cols: 2, gutter: 10 },
        panels: [],
      },
    });
  }

  const page = config.pages[pageIndex];
  let addMore = true;
  let panelIndex = page.layout.panels.length;

  while (addMore) {
    const panelId = await promptInput("Panel ID (e.g., p1-1)", `p${pageIndex + 1}-${panelIndex + 1}`);
    const prompt = await promptInput("Panel description/prompt", "");
    const row = parseInt(await promptInput("Grid row (0-based)", "0"), 10);
    const col = parseInt(await promptInput("Grid column (0-based)", "0"), 10);

    const panel = {
      id: panelId,
      position: { row, col },
      rowspan: 1,
      colspan: 1,
      prompt,
      focus: "environment" as const,
    };

    page.layout.panels.push(panel);
    console.log(`✓ Added panel: ${panelId}`);

    panelIndex++;
    addMore = await promptYesNo("Add another panel?");
  }
}

function generateConfig(projectName: string, answers: InitAnswers): FlexicomicConfig {
  const artStylePrompts: Record<string, string> = {
    manga: "Japanese manga style, anime aesthetics",
    "ligne-claire": "Clean line art, European comic style",
    realistic: "Realistic proportions and detailed rendering",
    "ink-brush": "Traditional ink brush painting style",
    chalk: "Chalkboard texture, educational style",
  };

  const tonePrompts: Record<string, string> = {
    neutral: "balanced tone",
    warm: "warm golden lighting, nostalgic atmosphere",
    dramatic: "high contrast, intense shadows",
    romantic: "soft colors, gentle atmosphere",
    energetic: "vibrant colors, dynamic energy",
  };

  const basePrompt = `${artStylePrompts[answers.artStyle]}, ${tonePrompts[answers.tone]}`;

  const pages = Array.from({ length: answers.pageCount }, (_, i) => ({
    id: `page${i + 1}`,
    title: `Page ${i + 1}`,
    layout: {
      type: "custom" as const,
      grid: { rows: 2, cols: 2, gutter: 10 },
      panels: [] as any[],
    },
  }));

  return {
    meta: {
      title: answers.title,
      author: answers.author,
      version: "1.0.0",
    },
    style: {
      artStyle: answers.artStyle as any,
      tone: answers.tone as any,
      basePrompt,
    },
    pageSettings: {
      aspectRatio: answers.aspectRatio,
      dpi: 300,
      outputFormat: "png",
    },
    characters: [],
    pages,
  };
}

async function createOutputDirectories(projectDir: string): Promise<void> {
  const dirs = ["characters", "panels", "pages"];
  for (const dir of dirs) {
    const dirPath = path.join(projectDir, dir);
    await mkdir(dirPath, { recursive: true });
    console.log(`✓ Created directory: ${dir}/`);
  }
}

// Simple prompt utilities
async function promptInput(question: string, defaultValue: string = ""): Promise<string> {
  const readline = await import("node:readline");
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  return new Promise((resolve) => {
    const prompt = defaultValue ? `${question} [${defaultValue}]: ` : `${question}: `;
    rl.question(prompt, (answer) => {
      rl.close();
      resolve(answer || defaultValue);
    });
  });
}

async function promptSelect(question: string, options: string[], defaultValue: string): Promise<string> {
  const readline = await import("node:readline");
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  return new Promise((resolve) => {
    console.log(`${question}:`);
    options.forEach((o, i) => console.log(`  ${i + 1}. ${o}`));
    rl.question(`Selection [${options.indexOf(defaultValue) + 1}]: `, (answer) => {
      rl.close();
      const index = parseInt(answer, 10) - 1;
      resolve(options[index] ?? defaultValue);
    });
  });
}

async function promptYesNo(question: string, defaultValue: boolean = false): Promise<boolean> {
  const readline = await import("node:readline");
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  return new Promise((resolve) => {
    const prompt = defaultValue ? `${question} [Y/n]: ` : `${question} [y/N]: `;
    rl.question(prompt, (answer) => {
      rl.close();
      const trimmed = answer.trim().toLowerCase();
      if (trimmed === "") {
        resolve(defaultValue);
      } else {
        resolve(trimmed === "y" || trimmed === "yes");
      }
    });
  });
}

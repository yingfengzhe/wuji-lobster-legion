/**
 * Parallel and sequential panel generation control
 */

import path from "node:path";
import { existsSync } from "node:fs";
import type { FlexicomicConfig, Provider } from "./types.js";
import { callImageGenWithRetry, calculatePanelAspectRatio } from "./utils/image-gen-adapter.js";
import { buildPanelPrompt, getCharacterReferenceImages } from "./utils/prompt-builder.js";
import { calculatePanelBoundsCustom, getLayoutGrid } from "./utils/layout-parser.js";

interface PanelToGenerate {
  page: FlexicomicConfig["pages"][number];
  panel: FlexicomicConfig["pages"][number]["layout"]["panels"][number];
  pageIndex: number;
  panelIndex: number;
}

interface ParallelOptions {
  concurrency: number;
  provider: Provider;
  verbose?: boolean;
}

interface SequentialOptions {
  provider: Provider;
  verbose?: boolean;
}

export async function generatePanelParallel(
  panels: PanelToGenerate[],
  config: FlexicomicConfig,
  outputDir: string,
  options: ParallelOptions
): Promise<void> {
  const concurrency = Math.min(Math.max(1, options.concurrency || 4), 8);
  console.log(`Parallel generation (concurrency: ${concurrency})\n`);

  let completed = 0;
  const total = panels.length;

  // Process in batches
  for (let i = 0; i < panels.length; i += concurrency) {
    const batch = panels.slice(i, i + concurrency);
    const promises = batch.map((item) =>
      generatePanelWithProgress(item, config, outputDir, options.provider, () => {
        completed++;
        const percent = Math.round((completed / total) * 100);
        process.stdout.write(`\r  Progress: ${completed}/${total} (${percent}%)`);
      })
    );

    await Promise.all(promises);
  }

  process.stdout.write(`\r  Progress: ${completed}/${total} (100%)\n`);
}

export async function generatePanelSequential(
  panels: PanelToGenerate[],
  config: FlexicomicConfig,
  outputDir: string,
  options: SequentialOptions
): Promise<void> {
  console.log(`Sequential generation\n`);

  for (let i = 0; i < panels.length; i++) {
    const item = panels[i];
    console.log(`  [${i + 1}/${panels.length}] ${item.panel.id}: ${item.panel.prompt.slice(0, 50)}...`);

    await generateSinglePanel(item, config, outputDir, options.provider);
  }
}

async function generatePanelWithProgress(
  item: PanelToGenerate,
  config: FlexicomicConfig,
  outputDir: string,
  provider: Provider,
  onProgress: () => void
): Promise<void> {
  try {
    await generateSinglePanel(item, config, outputDir, provider);
    onProgress();
  } catch (error) {
    console.warn(`\n  Warning: Failed to generate ${item.panel.id}: ${error}`);
    onProgress();
  }
}

async function generateSinglePanel(
  item: PanelToGenerate,
  config: FlexicomicConfig,
  outputDir: string,
  provider: Provider
): Promise<void> {
  const { page, panel } = item;
  const outputPath = path.join(outputDir, "panels", `${panel.id}.png`);

  // Skip if already exists
  if (existsSync(outputPath)) {
    return;
  }

  // Calculate panel bounds for aspect ratio
  const grid = page.layout.grid || getLayoutGrid(page.layout.type, page.layout.panels.length);
  const pageSize = { width: 1200, height: 1600 }; // Default page size
  const bounds = calculatePanelBoundsCustom(panel, grid, pageSize);

  // Determine aspect ratio
  const ar = panel.aspectRatio || calculatePanelAspectRatio(bounds.w, bounds.h);

  // Build prompt
  const promptContext = {
    config,
    page,
    panel,
  };

  const prompt = await buildPanelPrompt(promptContext);

  // Get character reference images
  const refImages = getCharacterReferenceImages(promptContext, outputDir);

  // Generate image
  await callImageGenWithRetry(
    {
      prompt,
      output: outputPath,
      ar,
      quality: "2k",
      provider,
      refImages: refImages.length > 0 ? refImages : undefined,
    },
    2
  );
}

export { generateSinglePanel };

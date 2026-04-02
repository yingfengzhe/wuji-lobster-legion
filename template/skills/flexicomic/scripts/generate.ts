/**
 * Main panel generation logic
 */

import path from "node:path";
import { mkdir } from "node:fs/promises";
import type { FlexicomicConfig } from "./types.js";
import { loadConfig, validatePageRange, validatePanelRange } from "./validation.js";
import { generateCharacterReferences } from "./character-refs.js";
import { generatePanelParallel, generatePanelSequential } from "./parallel.js";
import { compositePages } from "./composite.js";
import { resolveProvider } from "./utils/image-gen-adapter.js";

export interface GenerateOptionsInternal {
  configPath: string;
  outputDir?: string;
  pages?: string | null;
  panels?: string | null;
  parallel?: boolean;
  concurrency?: number;
  provider?: string | null;
  skipRefs?: boolean;
  skipComposite?: boolean;
  verbose?: boolean;
}

export async function generateComic(options: GenerateOptionsInternal): Promise<void> {
  console.log("🎨 Flexicomic Generation\n");

  // Load configuration
  const configPath = options.configPath || (options as any).config;
  if (!configPath) {
    throw new Error("configPath is required");
  }
  const config = await loadConfig(configPath);
  const outputDir = options.outputDir || path.dirname(configPath);

  console.log(`Project: ${config.meta.title}`);
  console.log(`Style: ${config.style.artStyle} / ${config.style.tone}`);
  console.log(`Pages: ${config.pages.length}`);
  console.log(`Characters: ${config.characters.length}\n`);

  // Resolve provider
  const provider = resolveProvider(options.provider as any);
  console.log(`Provider: ${provider}\n`);

  // Determine which pages to generate
  let pagesToGenerate = config.pages.map((_, i) => i + 1);
  if (options.pages) {
    pagesToGenerate = validatePageRange(options.pages, config.pages.length);
    console.log(`Generating pages: ${pagesToGenerate.join(", ")}`);
  }

  // Determine which panels to generate
  let panelsToGenerate: Set<string> | null = null;
  if (options.panels) {
    const panelIds = validatePanelRange(options.panels, config.pages);
    panelsToGenerate = new Set(panelIds);
    console.log(`Generating panels: ${Array.from(panelsToGenerate).join(", ")}`);
  }

  // Step 1: Generate character references
  if (!options.skipRefs && config.characters.length > 0) {
    console.log("─".repeat(50));
    console.log("Step 1: Character References");
    console.log("─".repeat(50));
    await generateCharacterReferences(config, outputDir, provider);
    console.log();
  }

  // Step 2: Collect panels to generate
  console.log("─".repeat(50));
  console.log("Step 2: Panel Generation");
  console.log("─".repeat(50));

  const panelsToProcess: Array<{
    page: FlexicomicConfig["pages"][number];
    panel: FlexicomicConfig["pages"][number]["layout"]["panels"][number];
    pageIndex: number;
    panelIndex: number;
  }> = [];

  for (const pageIndex of pagesToGenerate) {
    const page = config.pages[pageIndex - 1];
    if (!page) continue;

    for (let panelIndex = 0; panelIndex < page.layout.panels.length; panelIndex++) {
      const panel = page.layout.panels[panelIndex];

      // Skip if not in targeted panels
      if (panelsToGenerate && !panelsToGenerate.has(panel.id)) {
        continue;
      }

      panelsToProcess.push({ page, panel, pageIndex, panelIndex });
    }
  }

  console.log(`Total panels to generate: ${panelsToProcess.length}\n`);

  if (panelsToProcess.length === 0) {
    console.log("No panels to generate.");
    return;
  }

  // Step 3: Generate panels
  await mkdir(path.join(outputDir, "panels"), { recursive: true });

  if (options.parallel && panelsToProcess.length > 1) {
    await generatePanelParallel(panelsToProcess, config, outputDir, {
      concurrency: options.concurrency || 4,
      provider,
      verbose: options.verbose,
    });
  } else {
    await generatePanelSequential(panelsToProcess, config, outputDir, {
      provider,
      verbose: options.verbose,
    });
  }

  console.log("\n✓ Panel generation complete!");

  // Step 4: Compose pages
  if (!options.skipComposite) {
    console.log("\n" + "─".repeat(50));
    console.log("Step 3: Page Composition");
    console.log("─".repeat(50));

    let pagesToCompose = pagesToGenerate;
    if (panelsToGenerate) {
      // If specific panels were generated, determine which pages need composition
      pagesToCompose = [];
      for (const pageIndex of pagesToGenerate) {
        const page = config.pages[pageIndex - 1];
        if (page?.layout.panels.some((p) => panelsToGenerate.has(p.id))) {
          pagesToCompose.push(pageIndex);
        }
      }
    }

    await compositePagesInternal(config, outputDir, pagesToCompose);
  }

  console.log("\n" + "─".repeat(50));
  console.log("✅ Generation complete!");
  console.log("─".repeat(50));
  console.log(`\nOutput directory: ${outputDir}`);
  console.log(`  - Panels: panels/`);
  console.log(`  - Pages: pages/`);
  console.log(`  - Character refs: characters/`);
}

async function compositePagesInternal(
  config: FlexicomicConfig,
  outputDir: string,
  pageIndices: number[]
): Promise<void> {
  const { compositePages: compose } = await import("./composite.js");
  await compose(config, outputDir, pageIndices);
}

export { loadConfig };

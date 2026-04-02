/**
 * Page composition using canvas
 */

import path from "node:path";
import { readFile, readdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import type { FlexicomicConfig } from "./types.js";
import { calculatePageSize, calculatePanelBoundsCustom } from "./utils/layout-parser.js";
import { getLayoutGrid } from "./utils/layout-parser.js";

export async function compositePages(
  config: FlexicomicConfig,
  outputDir: string,
  pageIndices?: number[]
): Promise<void> {
  const pagesDir = path.join(outputDir, "pages");
  const panelsDir = path.join(outputDir, "panels");
  const { mkdir } = await import("node:fs/promises");
  await mkdir(pagesDir, { recursive: true });

  const pagesToProcess = pageIndices || config.pages.map((_, i) => i + 1);

  console.log(`Composing ${pagesToProcess.length} page(s)...`);

  for (const pageIndex of pagesToProcess) {
    const page = config.pages[pageIndex - 1];
    if (!page) continue;

    console.log(`  Composing ${page.id}...`);

    try {
      await compositeSinglePage(page, config, panelsDir, pagesDir);
      console.log(`    ✓ Created: ${page.id}.png`);
    } catch (error) {
      console.warn(`    ⚠ Warning: Failed to compose ${page.id}: ${error}`);
    }
  }

  console.log(`\n✓ Page composition complete!`);
  console.log(`  Output: ${pagesDir}/`);
}

async function compositeSinglePage(
  page: FlexicomicConfig["pages"][number],
  config: FlexicomicConfig,
  panelsDir: string,
  pagesDir: string
): Promise<void> {
  // Use canvas (node-canvas) for image composition
  let canvasModule: any;

  try {
    canvasModule = await import("canvas");
  } catch {
    // If canvas is not available, use ImageMagick via Bun
    await compositeSinglePageImagemagick(page, config, panelsDir, pagesDir);
    return;
  }

  const { createCanvas, loadImage } = canvasModule;

  const pageSize = calculatePageSize(config);
  const canvas = createCanvas(pageSize.width, pageSize.height);
  const ctx = canvas.getContext("2d");

  // White background
  ctx.fillStyle = "#FFFFFF";
  ctx.fillRect(0, 0, pageSize.width, pageSize.height);

  // Get grid settings
  const grid = page.layout.grid || getLayoutGrid(page.layout.type, page.layout.panels.length);
  const gutter = grid.gutter || 10;

  // Draw each panel
  for (const panel of page.layout.panels) {
    const bounds = calculatePanelBoundsCustom(panel, grid, pageSize);
    const panelPath = path.join(panelsDir, `${panel.id}.png`);

    if (!existsSync(panelPath)) {
      console.warn(`    Panel not found: ${panel.id}`);
      // Draw placeholder
      ctx.fillStyle = "#CCCCCC";
      ctx.fillRect(bounds.x, bounds.y, bounds.w, bounds.h);
      ctx.fillStyle = "#666666";
      ctx.font = "16px sans-serif";
      ctx.fillText(panel.id, bounds.x + 10, bounds.y + 30);
      continue;
    }

    try {
      const panelBuffer = await readFile(panelPath);
      const panelImage = await loadImage(panelBuffer);

      // Calculate scaling to fit bounds while maintaining aspect ratio
      const scale = Math.min(
        bounds.w / panelImage.width,
        bounds.h / panelImage.height
      );
      const scaledWidth = panelImage.width * scale;
      const scaledHeight = panelImage.height * scale;
      const x = bounds.x + (bounds.w - scaledWidth) / 2;
      const y = bounds.y + (bounds.h - scaledHeight) / 2;

      ctx.drawImage(panelImage, x, y, scaledWidth, scaledHeight);
    } catch (error) {
      console.warn(`    Failed to load panel ${panel.id}: ${error}`);
    }

    // Draw border
    ctx.strokeStyle = "#000000";
    ctx.lineWidth = 2;
    ctx.strokeRect(bounds.x, bounds.y, bounds.w, bounds.h);
  }

  // Save page
  const outputPath = path.join(pagesDir, `${page.id}.png`);
  const out = canvas.createPNGStream();
  const writeStream = await import("node:fs/promises").then((m) => m.writeFile);
  await writeStream(outputPath, canvas.toBuffer("image/png"));
}

async function compositeSinglePageImagemagick(
  page: FlexicomicConfig["pages"][number],
  config: FlexicomicConfig,
  panelsDir: string,
  pagesDir: string
): Promise<void> {
  // Fallback using ImageMagick convert
  const pageSize = calculatePageSize(config);
  const grid = page.layout.grid || getLayoutGrid(page.layout.type, page.layout.panels.length);
  const gutter = grid.gutter || 10;

  // Build ImageMagick command
  const args: string[] = [
    "-size", `${pageSize.width}x${pageSize.height}`,
    "xc:white",
  ];

  // Add each panel
  for (const panel of page.layout.panels) {
    const bounds = calculatePanelBoundsCustom(panel, grid, pageSize);
    const panelPath = path.join(panelsDir, `${panel.id}.png`);

    if (!existsSync(panelPath)) {
      continue;
    }

    args.push(
      "\\(", panelPath,
      "-resize", `${Math.round(bounds.w)}x${Math.round(bounds.h)}`,
      "\\)",
      "-geometry", `+${Math.round(bounds.x)}+${Math.round(bounds.y)}`,
      "-composite"
    );
  }

  // Add borders
  for (const panel of page.layout.panels) {
    const bounds = calculatePanelBoundsCustom(panel, grid, pageSize);
    args.push(
      "-draw", `rectangle ${Math.round(bounds.x)},${Math.round(bounds.y)} ${Math.round(bounds.x + bounds.w)},${Math.round(bounds.y + bounds.h)}`
    );
  }

  const outputPath = path.join(pagesDir, `${page.id}.png`);
  args.push(outputPath);

  const proc = Bun.spawn(["convert", ...args], {
    stdout: "inherit",
    stderr: "inherit",
  });

  const exitCode = await proc.exited;
  if (exitCode !== 0) {
    throw new Error(`ImageMagick failed with exit code ${exitCode}`);
  }
}

export async function previewLayout(configPath: string): Promise<void> {
  const { loadConfig } = await import("./validation.js");
  const config = await loadConfig(configPath);

  console.log("\n" + "=".repeat(60));
  console.log(`Flexicomic Layout Preview: ${config.meta.title}`);
  console.log("=".repeat(60) + "\n");

  console.log(`Style: ${config.style.artStyle} / ${config.style.tone}`);
  console.log(`Format: ${config.pageSettings.aspectRatio} @ ${config.pageSettings.dpi} DPI`);
  console.log(`Characters: ${config.characters.map((c) => c.name).join(", ") || "None"}`);

  console.log("\n" + "─".repeat(60));
  console.log("Pages");
  console.log("─".repeat(60));

  for (const page of config.pages) {
    console.log(`\n  ${page.id}${page.title ? `: ${page.title}` : ""}`);
    console.log(`  Layout: ${page.layout.type}`);
    console.log(`  Panels: ${page.layout.panels.length}`);

    const grid = page.layout.grid || { rows: 2, cols: 2 };

    for (const panel of page.layout.panels) {
      const pos = `(${panel.position.col},${panel.position.row})`;
      const span = panel.rowspan > 1 || panel.colspan > 1
        ? ` [${panel.colspan}x${panel.rowspan}]`
        : "";

      console.log(`    - ${panel.id}${span}: ${pos}`);
      console.log(`      ${panel.prompt.slice(0, 60)}${panel.prompt.length > 60 ? "..." : ""}`);

      if (panel.characters && panel.characters.length > 0) {
        const chars = panel.characters.map((c) => c.id).join(", ");
        console.log(`      Characters: ${chars}`);
      }

      if (panel.focus) {
        console.log(`      Focus: ${panel.focus}`);
      }
    }
  }

  console.log("\n" + "=".repeat(60));
}

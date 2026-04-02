/**
 * Configuration validation using AJV
 */

import path from "node:path";
import type { FlexicomicConfig } from "./types.js";

let AjvInstance: any = null;

async function loadAjv(): Promise<any> {
  if (AjvInstance) return AjvInstance;

  try {
    // Try importing AJV
    const AjvModule = await import("ajv");
    AjvInstance = new AjvModule.default({ allErrors: true });
    return AjvInstance;
  } catch {
    return null;
  }
}

export async function validateConfig(config: unknown): Promise<{ valid: boolean; errors?: string[] }> {
  const Ajv = await loadAjv();

  if (!Ajv) {
    // AJV not available, do basic validation
    return basicValidation(config);
  }

  try {
    const schemaPath = path.resolve(import.meta.dir, "../schema/flexicomic-schema.json");
    const schema = JSON.parse(await Bun.file(schemaPath).text());

    const validate = Ajv.compile(schema);
    const valid = validate(config);

    if (valid) {
      return { valid: true };
    }

    const errors = validate.errors?.map((e: any) => {
      const path = e.instancePath || e.schemaPath;
      return `${path}: ${e.message}`;
    }) || [];

    return { valid: false, errors };
  } catch (error) {
    // Schema loading failed, fall back to basic validation
    return basicValidation(config);
  }
}

function basicValidation(config: unknown): { valid: boolean; errors?: string[] } {
  const errors: string[] = [];

  if (!config || typeof config !== "object") {
    return { valid: false, errors: ["Config must be an object"] };
  }

  const c = config as Record<string, unknown>;

  // Check meta
  if (!c.meta || typeof c.meta !== "object") {
    errors.push("meta is required and must be an object");
  } else if (typeof (c.meta as Record<string, unknown>).title !== "string") {
    errors.push("meta.title is required");
  }

  // Check style
  if (!c.style || typeof c.style !== "object") {
    errors.push("style is required and must be an object");
  } else {
    const style = c.style as Record<string, unknown>;
    if (typeof style.artStyle !== "string") {
      errors.push("style.artStyle is required");
    }
    if (typeof style.tone !== "string") {
      errors.push("style.tone is required");
    }
  }

  // Check pageSettings
  if (!c.pageSettings || typeof c.pageSettings !== "object") {
    errors.push("pageSettings is required and must be an object");
  } else if (typeof (c.pageSettings as Record<string, unknown>).aspectRatio !== "string") {
    errors.push("pageSettings.aspectRatio is required");
  }

  // Check characters
  if (!Array.isArray(c.characters)) {
    errors.push("characters must be an array");
  }

  // Check pages
  if (!Array.isArray(c.pages)) {
    errors.push("pages must be an array");
  }

  return { valid: errors.length === 0, errors: errors.length > 0 ? errors : undefined };
}

export async function loadConfig(configPath: string): Promise<FlexicomicConfig> {
  const file = Bun.file(configPath);
  const content = await file.text();

  let config: unknown;
  try {
    config = JSON.parse(content);
  } catch (error) {
    throw new Error(`Failed to parse config file: ${error}`);
  }

  const validation = await validateConfig(config);
  if (!validation.valid) {
    throw new Error(`Invalid configuration:\n${validation.errors?.join("\n")}`);
  }

  return config as FlexicomicConfig;
}

export function validatePageRange(range: string, totalPages: number): number[] {
  const pages: number[] = [];

  for (const part of range.split(",")) {
    const trimmed = part.trim();
    if (trimmed.includes("-")) {
      const [start, end] = trimmed.split("-").map((s) => parseInt(s.trim(), 10));
      if (isNaN(start) || isNaN(end)) {
        throw new Error(`Invalid page range: ${trimmed}`);
      }
      for (let i = start; i <= end; i++) {
        if (i >= 1 && i <= totalPages) {
          pages.push(i);
        }
      }
    } else {
      const page = parseInt(trimmed, 10);
      if (isNaN(page)) {
        throw new Error(`Invalid page number: ${trimmed}`);
      }
      if (page >= 1 && page <= totalPages) {
        pages.push(page);
      }
    }
  }

  return [...new Set(pages)].sort((a, b) => a - b);
}

export function validatePanelRange(range: string, pages: FlexicomicConfig["pages"]): string[] {
  const panels: string[] = [];

  const [pageId, panelRange] = range.split(":");
  if (!panelRange) {
    throw new Error(`Invalid panel range format. Expected: pageId:range (e.g., page1:1-3)`);
  }

  const page = pages.find((p) => p.id === pageId);
  if (!page) {
    throw new Error(`Page not found: ${pageId}`);
  }

  const totalPanels = page.layout.panels.length;

  for (const part of panelRange.split(",")) {
    const trimmed = part.trim();
    if (trimmed.includes("-")) {
      const [start, end] = trimmed.split("-").map((s) => parseInt(s.trim(), 10));
      if (isNaN(start) || isNaN(end)) {
        throw new Error(`Invalid panel range: ${trimmed}`);
      }
      for (let i = start; i <= end; i++) {
        if (i >= 1 && i <= totalPanels) {
          const panel = page.layout.panels[i - 1];
          if (panel) {
            panels.push(panel.id);
          }
        }
      }
    } else {
      const idx = parseInt(trimmed, 10);
      if (isNaN(idx)) {
        throw new Error(`Invalid panel number: ${trimmed}`);
      }
      if (idx >= 1 && idx <= totalPanels) {
        const panel = page.layout.panels[idx - 1];
        if (panel) {
          panels.push(panel.id);
        }
      }
    }
  }

  return [...new Set(panels)];
}

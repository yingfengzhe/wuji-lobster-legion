/**
 * Layout parsing and bounds calculation utilities
 */

import type { FlexicomicConfig, PanelConfig, PanelBounds } from "../types.js";

export interface PageSize {
  width: number;
  height: number;
}

export function calculatePageSize(config: FlexicomicConfig): PageSize {
  const { pageSettings } = config;

  // Explicit dimensions take precedence
  if (pageSettings.width && pageSettings.height) {
    return { width: pageSettings.width, height: pageSettings.height };
  }

  // Parse aspect ratio
  const [w, h] = pageSettings.aspectRatio.split(":").map((s) => parseInt(s, 10));

  if (isNaN(w) || isNaN(h) || w <= 0 || h <= 0) {
    throw new Error(`Invalid aspect ratio: ${pageSettings.aspectRatio}`);
  }

  // Calculate dimensions based on DPI
  const dpi = pageSettings.dpi || 300;
  const baseSize = dpi * 10; // 10 inches at given DPI

  // Calculate actual dimensions maintaining aspect ratio
  let width: number;
  let height: number;

  if (w >= h) {
    // Landscape or square
    width = baseSize;
    height = Math.round((baseSize * h) / w);
  } else {
    // Portrait
    height = baseSize;
    width = Math.round((baseSize * w) / h);
  }

  return { width, height };
}

export function calculatePanelBounds(
  panel: PanelConfig,
  pageSize: PageSize,
  gutter: number = 10
): PanelBounds {
  const layout = panel as PanelConfig & { rowspan?: number; colspan?: number; sizeRatio?: number };
  const grid = { rows: 2, cols: 2 }; // Default grid

  // Get grid settings from parent (would need to pass page config)
  const rowspan = layout.rowspan || 1;
  const colspan = layout.colspan || 1;
  const position = panel.position;

  const cellWidth = (pageSize.width - gutter * (grid.cols + 1)) / grid.cols;
  const cellHeight = (pageSize.height - gutter * (grid.rows + 1)) / grid.rows;

  const x = gutter + position.col * (cellWidth + gutter);
  const y = gutter + position.row * (cellHeight + gutter);
  const w = colspan * cellWidth + (colspan - 1) * gutter;
  const h = rowspan * cellHeight + (rowspan - 1) * gutter;

  return { x, y, w, h };
}

export function calculatePanelBoundsCustom(
  panel: PanelConfig,
  grid: { rows: number; cols: number; gutter?: number },
  pageSize: PageSize
): PanelBounds {
  const rowspan = panel.rowspan || 1;
  const colspan = panel.colspan || 1;
  const gutter = grid.gutter || 10;

  const cellWidth = (pageSize.width - gutter * (grid.cols + 1)) / grid.cols;
  const cellHeight = (pageSize.height - gutter * (grid.rows + 1)) / grid.rows;

  const x = gutter + panel.position.col * (cellWidth + gutter);
  const y = gutter + panel.position.row * (cellHeight + gutter);
  const w = colspan * cellWidth + (colspan - 1) * gutter;
  const h = rowspan * cellHeight + (rowspan - 1) * gutter;

  return { x, y, w, h };
}

export function getLayoutGrid(
  layoutType: string,
  panelsCount: number
): { rows: number; cols: number; gutter: number } {
  switch (layoutType) {
    case "2x2-grid":
      return { rows: 2, cols: 2, gutter: 10 };
    case "cinematic":
      return { rows: 3, cols: 2, gutter: 10 };
    case "webtoon":
      return { rows: panelsCount, cols: 1, gutter: 5 };
    case "dense":
      return { rows: 3, cols: 3, gutter: 8 };
    case "splash":
      return { rows: 1, cols: 1, gutter: 0 };
    default:
      // Custom - infer from panels
      return { rows: 2, cols: 2, gutter: 10 };
  }
}

export function calculateGridDimensions(
  rows: number,
  cols: number,
  pageSize: PageSize,
  gutter: number = 10
): { cellWidth: number; cellHeight: number } {
  const cellWidth = (pageSize.width - gutter * (cols + 1)) / cols;
  const cellHeight = (pageSize.height - gutter * (rows + 1)) / rows;

  return { cellWidth, cellHeight };
}

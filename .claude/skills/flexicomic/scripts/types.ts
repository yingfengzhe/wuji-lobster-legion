/**
 * Flexicomic Type Definitions
 */

export type ArtStyle = "manga" | "ligne-claire" | "realistic" | "ink-brush" | "chalk";
export type Tone = "neutral" | "warm" | "dramatic" | "romantic" | "energetic" | "vintage" | "action";
export type OutputFormat = "png" | "jpg" | "jpeg";
export type LayoutType = "custom" | "2x2-grid" | "cinematic" | "webtoon" | "dense" | "splash";
export type CharacterRole = "protagonist" | "antagonist" | "supporting" | "background";
export type PanelFocus = "character" | "environment" | "action" | "dialogue" | "close-up" | "wide";
export type Provider = "google" | "openai" | "dashscope";

export interface MetaConfig {
  title: string;
  author?: string;
  version?: string;
}

export interface VisualSpec {
  age?: string;
  hair?: string;
  eyes?: string;
  outfit?: string;
  bodyType?: string;
  distinctiveFeatures?: string;
}

export interface CharacterConfig {
  id: string;
  name: string;
  role: CharacterRole;
  description?: string;
  visualSpec?: VisualSpec;
  expressions?: string[];
  angles?: string[];
}

export interface GridPosition {
  row: number;
  col: number;
}

export interface PanelCharacter {
  id: string;
  expression?: string;
  angle?: string;
  action?: string;
}

export interface PanelConfig {
  id: string;
  position: GridPosition;
  rowspan?: number;
  colspan?: number;
  sizeRatio?: number;
  prompt: string;
  characters?: PanelCharacter[];
  focus?: PanelFocus;
  aspectRatio?: string;
  notes?: string;
}

export interface GridSettings {
  rows: number;
  cols: number;
  gutter?: number;
}

export interface LayoutConfig {
  type: LayoutType;
  grid?: GridSettings;
  panels: PanelConfig[];
}

export interface PageConfig {
  id: string;
  title?: string;
  layout: LayoutConfig;
}

export interface StyleConfig {
  artStyle: ArtStyle;
  tone: Tone;
  basePrompt?: string;
}

export interface PageSettings {
  aspectRatio: string;
  dpi?: number;
  outputFormat?: OutputFormat;
  width?: number;
  height?: number;
}

export interface FlexicomicConfig {
  meta: MetaConfig;
  style: StyleConfig;
  pageSettings: PageSettings;
  characters: CharacterConfig[];
  pages: PageConfig[];
}

export interface GenerateOptions {
  configPath: string;
  outputDir?: string;
  pages?: string;
  panels?: string;
  parallel?: boolean;
  concurrency?: number;
  provider?: Provider;
  skipRefs?: boolean;
  skipComposite?: boolean;
  verbose?: boolean;
}

export interface CharacterReference {
  characterId: string;
  images: {
    expressions?: string;
    angles?: string;
    fullBody?: string;
    colorPalette?: string;
  };
  generated: boolean;
}

export interface PanelBounds {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface CliArgs {
  command: string;
  args: string[];
  options: Map<string, string>;
}

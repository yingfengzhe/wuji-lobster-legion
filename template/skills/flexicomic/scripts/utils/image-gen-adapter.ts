/**
 * Image generation adapter - direct API calls
 */

import path from "node:path";
import { readFile, mkdir } from "node:fs/promises";
import { homedir } from "node:os";
import type { Provider } from "../types.js";

// Load environment variables from .env files
let envLoaded = false;
async function loadEnv(): Promise<void> {
  if (envLoaded) return;
  envLoaded = true;

  const home = homedir();
  const cwd = process.cwd();

  const envFiles = [
    path.join(home, ".flexicomic", ".env"),
    path.join(cwd, ".flexicomic", ".env"),
    path.join(cwd, ".env"),
  ];

  for (const envFile of envFiles) {
    try {
      const content = await readFile(envFile, "utf8");
      for (const line of content.split("\n")) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith("#")) continue;
        const idx = trimmed.indexOf("=");
        if (idx === -1) continue;
        const key = trimmed.slice(0, idx).trim();
        let val = trimmed.slice(idx + 1).trim();
        if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
          val = val.slice(1, -1);
        }
        if (!process.env[key]) {
          process.env[key] = val;
        }
      }
    } catch {
      // File doesn't exist, skip
    }
  }
}

export interface ImageGenOptions {
  prompt: string;
  output: string;
  ar?: string;
  quality?: string;
  provider?: Provider;
  refImages?: string[];
}

/**
 * Generate image using DashScope (Alibaba Wanx)
 */
async function generateWithDashScope(
  prompt: string,
  outputPath: string,
  aspectRatio: string
): Promise<void> {
  const apiKey = process.env.DASHSCOPE_API_KEY;
  if (!apiKey) {
    throw new Error("DASHSCOPE_API_KEY not found");
  }

  // DashScope Wanx image generation API
  const response = await fetch(
    "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
    {
      method: "POST",
      headers: {
        "Authorization": "Bearer " + apiKey,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "wanx-v1",
        input: {
          prompt: prompt,
        },
        parameters: {
          size: parseSize(aspectRatio),
          n: 1,
        },
      }),
    }
  );

  if (!response.ok) {
    const error = await response.text();
    throw new Error("DashScope API error: " + error);
  }

  const data = await response.json();
  console.log("  DashScope response:", JSON.stringify(data).slice(0, 200));

  // Extract image URL from response and download
  if (data.output?.results?.[0]?.url) {
    const imageUrl = data.output.results[0].url;
    console.log("  Downloading from: " + imageUrl);
    const imageResponse = await fetch(imageUrl);
    const imageBuffer = await imageResponse.arrayBuffer();

    await mkdir(path.dirname(outputPath), { recursive: true });
    await Bun.write(outputPath, imageBuffer);
    console.log("  Saved: " + outputPath);
  } else if (data.output?.task_id) {
    // Async task - need to poll for result
    const taskId = data.output.task_id;
    console.log("  Task ID: " + taskId + ", polling for result...");

    let attempts = 0;
    const maxAttempts = 30;
    while (attempts < maxAttempts) {
      await new Promise(resolve => setTimeout(resolve, 2000));

      const resultResponse = await fetch(
        "https://dashscope.aliyuncs.com/api/v1/tasks/" + taskId,
        {
          method: "GET",
          headers: {
            "Authorization": "Bearer " + apiKey,
          },
        }
      );

      if (!resultResponse.ok) {
        throw new Error("Failed to get task result");
      }

      const resultData = await resultResponse.json();
      console.log("  Poll attempt " + (attempts + 1) + ":", resultData.task_status);

      if (resultData.task_status === "SUCCEEDED" && resultData.results?.[0]?.url) {
        const imageUrl = resultData.results[0].url;
        const imageResponse = await fetch(imageUrl);
        const imageBuffer = await imageResponse.arrayBuffer();

        await mkdir(path.dirname(outputPath), { recursive: true });
        await Bun.write(outputPath, imageBuffer);
        console.log("  Saved: " + outputPath);
        return;
      } else if (resultData.task_status === "FAILED") {
        throw new Error("Task failed: " + (resultData.error || "Unknown error"));
      }

      attempts++;
    }

    throw new Error("Task timed out");
  } else {
    console.log("  Full response:", JSON.stringify(data, null, 2));
    throw new Error("No image URL in response");
  }
}

/**
 * Generate image using Google Gemini API
 * Copied from: baoyu-image-gen/scripts/providers/google.ts
 */
async function generateWithGoogle(
  prompt: string,
  outputPath: string,
  aspectRatio: string,
  refImages?: string[]
): Promise<void> {
  const apiKey = process.env.GOOGLE_API_KEY || process.env.GEMINI_API_KEY;
  if (!apiKey) {
    throw new Error("GOOGLE_API_KEY not found");
  }

  function getGoogleBaseUrl(): string {
    const base = process.env.GOOGLE_BASE_URL || "https://generativelanguage.googleapis.com";
    return base.replace(/\/+$/g, "");
  }

  function buildGoogleUrl(pathname: string): string {
    const base = getGoogleBaseUrl();
    const cleanedPath = pathname.replace(/^\/+/g, "");
    if (base.endsWith("/v1beta")) return `${base}/${cleanedPath}`;
    return `${base}/v1beta/${cleanedPath}`;
  }

  async function postGoogleJson<T>(pathname: string, body: unknown): Promise<T> {
    const res = await fetch(buildGoogleUrl(pathname), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-goog-api-key": apiKey,
      },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const err = await res.text();
      throw new Error(`Google API error (${res.status}): ${err}`);
    }

    return (await res.json()) as T;
  }

  function extractInlineImageData(response: {
    candidates?: Array<{ content?: { parts?: Array<{ inlineData?: { data?: string } }> } }>;
  }): string | null {
    for (const candidate of response.candidates || []) {
      for (const part of candidate.content?.parts || []) {
        const data = part.inlineData?.data;
        if (typeof data === "string" && data.length > 0) return data;
      }
    }
    return null;
  }

  const model = process.env.GOOGLE_IMAGE_MODEL || "gemini-3-pro-image-preview";
  const imageSize: "1K" | "2K" = "1K";

  let fullPrompt = prompt;
  if (aspectRatio) {
    fullPrompt += ` Aspect ratio: ${aspectRatio}.`;
  }

  console.log(`  Calling Google Gemini (${model}, ${imageSize})...`);

  const response = await postGoogleJson<{
    candidates?: Array<{ content?: { parts?: Array<{ inlineData?: { data?: string } }> } }>;
  }>(`models/${model}:generateContent`, {
    contents: [
      {
        role: "user",
        parts: [{ text: fullPrompt }],
      },
    ],
    generationConfig: {
      responseModalities: ["IMAGE"],
      imageConfig: { imageSize },
    },
  });

  console.log("  Response received");

  const imageData = extractInlineImageData(response);
  if (imageData) {
    const imageBuffer = Buffer.from(imageData, "base64");
    await mkdir(path.dirname(outputPath), { recursive: true });
    await Bun.write(outputPath, imageBuffer);
    console.log("  Saved:", outputPath);
  } else {
    console.error("  Full response:", JSON.stringify(response, null, 2));
    throw new Error("No image data in Google API response");
  }
}

/**
 * Generate image using OpenAI
 */
async function generateWithOpenAI(
  prompt: string,
  outputPath: string,
  aspectRatio: string
): Promise<void> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error("OPENAI_API_KEY not found");
  }

  const response = await fetch("https://api.openai.com/v1/images/generations", {
    method: "POST",
    headers: {
      "Authorization": "Bearer " + apiKey,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "dall-e-3",
      prompt: prompt,
      n: 1,
      size: parseSize(aspectRatio),
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error("OpenAI API error: " + error);
  }

  const data = await response.json();

  if (data.data?.[0]?.url) {
    const imageUrl = data.data[0].url;
    const imageResponse = await fetch(imageUrl);
    const imageBuffer = await imageResponse.arrayBuffer();

    await mkdir(path.dirname(outputPath), { recursive: true });
    await Bun.write(outputPath, imageBuffer);
  } else {
    throw new Error("No image URL in response");
  }
}

function parseSize(ar: string): string {
  const sizes: Record<string, string> = {
    "1:1": "1024x1024",
    "3:4": "1024x1365",
    "4:3": "1365x1024",
    "16:9": "1792x1024",
  };
  return sizes[ar] || "1024x1024";
}

export async function callImageGen(options: ImageGenOptions): Promise<void> {
  await loadEnv();
  const provider = options.provider || resolveProvider(null);
  const ar = options.ar || "3:4";

  await mkdir(path.dirname(options.output), { recursive: true });

  switch (provider) {
    case "dashscope":
      await generateWithDashScope(options.prompt, options.output, ar);
      break;
    case "google":
      await generateWithGoogle(options.prompt, options.output, ar, options.refImages);
      break;
    case "openai":
      await generateWithOpenAI(options.prompt, options.output, ar);
      break;
    default:
      throw new Error("Unknown provider: " + provider);
  }
}

export async function callImageGenWithRetry(
  options: ImageGenOptions,
  maxRetries: number = 2
): Promise<void> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      await callImageGen(options);
      return;
    } catch (error) {
      lastError = error as Error;
      if (attempt < maxRetries) {
        console.warn("  Generation attempt " + (attempt + 1) + " failed, retrying...");
      }
    }
  }

  throw lastError;
}

export function resolveProvider(preferred: Provider | null | undefined): Provider {
  if (preferred) return preferred;

  const hasGoogle = !!(process.env.GOOGLE_API_KEY || process.env.GEMINI_API_KEY);
  const hasOpenai = !!process.env.OPENAI_API_KEY;
  const hasDashscope = !!process.env.DASHSCOPE_API_KEY;

  if (hasDashscope) return "dashscope";
  if (hasGoogle) return "google";
  if (hasOpenai) return "openai";

  throw new Error(
    "No API key found. Set GOOGLE_API_KEY, OPENAI_API_KEY, or DASHSCOPE_API_KEY."
  );
}

export function calculatePanelAspectRatio(
  panelWidth: number,
  panelHeight: number
): string {
  const gcd = (a: number, b: number): number => {
    return b === 0 ? a : gcd(b, a % b);
  };

  const divisor = gcd(panelWidth, panelHeight);
  const w = Math.round(panelWidth / divisor);
  const h = Math.round(panelHeight / divisor);

  return w + ":" + h;
}

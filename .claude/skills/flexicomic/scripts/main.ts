/**
 * Main CLI entry point for baoyu-flexicomic
 */

import path from "node:path";
import { parseCommandArgs, printUsage } from "./utils/cli.js";
import { initInteractive } from "./init.js";
import { generateComic } from "./generate.js";
import { previewLayout } from "./preview.js";
import { compositePages } from "./composite.js";

const SKILL_DIR = path.resolve(import.meta.dir, "..");

async function main() {
  const parsed = parseCommandArgs(process.argv);

  if (parsed.options.help || !parsed.command) {
    printUsage();
    process.exit(parsed.command ? 0 : 1);
    return;
  }

  try {
    switch (parsed.command) {
      case "init": {
        const projectName = parsed.args[0];
        if (!projectName) {
          console.error("Error: Project name is required");
          console.error("Usage: main.ts init <project-name>");
          process.exit(1);
          return;
        }
        await initInteractive(projectName);
        break;
      }

      case "generate": {
        if (!parsed.options.config) {
          console.error("Error: --config is required for generate command");
          console.error("Usage: main.ts generate -c <config.json> [options]");
          process.exit(1);
          return;
        }
        await generateComic(parsed.options);
        break;
      }

      case "preview": {
        if (!parsed.options.config) {
          console.error("Error: --config is required for preview command");
          console.error("Usage: main.ts preview -c <config.json>");
          process.exit(1);
          return;
        }
        await previewLayout(parsed.options.config);
        break;
      }

      case "composite": {
        if (!parsed.options.config) {
          console.error("Error: --config is required for composite command");
          console.error("Usage: main.ts composite -c <config.json> [options]");
          process.exit(1);
          return;
        }
        await compositePages(parsed.options);
        break;
      }

      default:
        console.error(`Unknown command: ${parsed.command}`);
        console.error("Run with --help to see available commands");
        process.exit(1);
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`Error: ${message}`);
    process.exit(1);
  }
}

main();

/**
 * CLI argument parsing utilities
 */

export interface ParsedOptions {
  config: string | null;
  output: string | null;
  pages: string | null;
  panels: string | null;
  parallel: boolean;
  concurrency: number;
  provider: string | null;
  skipRefs: boolean;
  skipComposite: boolean;
  verbose: boolean;
  help: boolean;
}

export interface ParsedCommand {
  command: string;
  args: string[];
  options: ParsedOptions;
}

export function parseCommandArgs(argv: string[]): ParsedCommand {
  const args = argv.slice(2);
  let command = "";
  const positionalArgs: string[] = [];
  const options: ParsedOptions = {
    config: null,
    output: null,
    pages: null,
    panels: null,
    parallel: false,
    concurrency: 4,
    provider: null,
    skipRefs: false,
    skipComposite: false,
    verbose: false,
    help: false,
  };

  let i = 0;
  while (i < args.length) {
    const arg = args[i];

    if (arg.startsWith("-")) {
      // Handle options
      switch (arg) {
        case "-c":
        case "--config":
          options.config = args[++i] || null;
          break;
        case "-o":
        case "--output":
          options.output = args[++i] || null;
          break;
        case "--pages":
          options.pages = args[++i] || null;
          break;
        case "--panels":
          options.panels = args[++i] || null;
          break;
        case "--parallel":
          options.parallel = true;
          break;
        case "--concurrency":
          options.concurrency = parseInt(args[++i] || "4", 10);
          break;
        case "--provider":
          options.provider = args[++i] || null;
          break;
        case "--skip-refs":
          options.skipRefs = true;
          break;
        case "--skip-composite":
          options.skipComposite = true;
          break;
        case "-v":
        case "--verbose":
          options.verbose = true;
          break;
        case "-h":
        case "--help":
          options.help = true;
          break;
        default:
          throw new Error(`Unknown option: ${arg}`);
      }
    } else if (!command) {
      // First positional arg is the command
      command = arg;
    } else {
      // Remaining positional args
      positionalArgs.push(arg);
    }

    i++;
  }

  return { command, args: positionalArgs, options };
}

export function printUsage(): void {
  console.log(`
Usage: bun scripts/main.ts <command> [options]

Commands:
  init <project-name>       Initialize a new comic project interactively
  generate -c <config>      Generate comic panels and pages
  preview -c <config>       Preview layout without generating
  composite -c <config>     Compose pages from generated panels

Generate Options:
  -c, --config <path>       Configuration file path (required)
  -o, --output <dir>        Output directory (default: config directory)
  --pages <range>           Page range (e.g., 1-3,5)
  --panels <range>          Panel range (e.g., page1:1-3)
  --parallel                Enable parallel generation
  --concurrency <n>         Concurrent jobs (1-8, default: 4)
  --provider <name>         Image generation provider
  --skip-refs               Skip character reference generation
  --skip-composite          Skip page composition
  -v, --verbose             Verbose output
  -h, --help                Show help

Examples:
  # Initialize new project
  bun scripts/main.ts init my-comic

  # Generate all
  bun scripts/main.ts generate -c my-comic/flexicomic.json

  # Generate specific pages in parallel
  bun scripts/main.ts generate -c my-comic/flexicomic.json --pages 1-3 --parallel

  # Preview layout
  bun scripts/main.ts preview -c my-comic/flexicomic.json
`);
}

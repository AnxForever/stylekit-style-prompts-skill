#!/usr/bin/env node

"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");

const PACKAGE_NAME = "@anxforever/stylekit-style-prompts-skill";
const SKILL_SLUG = "stylekit-style-prompts";
const ROOT_DIR = path.resolve(__dirname, "..");
const PAYLOAD_ITEMS = [
  "SKILL.md",
  "LICENSE",
  "agents",
  "references",
  "scripts",
  "README.md",
  "RELEASE.md",
];

const DEFAULT_TARGETS = {
  codex: path.join(os.homedir(), ".codex", "skills", SKILL_SLUG),
  claude: path.join(os.homedir(), ".claude", "skills", SKILL_SLUG),
};

function printHelp() {
  const text = `
${PACKAGE_NAME}

Usage:
  stylekit-style-prompts-skill <command> [options]

Commands:
  install      Install the skill payload
  uninstall    Remove installed skill directory
  doctor       Check local environment and installation status
  help         Show this message

Options:
  --tool <codex|claude|auto>  Target tool. Default: auto
  --target <path>             Custom install path
  --force                     Overwrite existing target directory
  --dry-run                   Print planned actions without file changes
  -h, --help                  Show help

Examples:
  npx ${PACKAGE_NAME} install --tool codex
  npx ${PACKAGE_NAME} install --tool claude
  npx ${PACKAGE_NAME} install --tool auto
  npx ${PACKAGE_NAME} install --target ~/.codex/skills/${SKILL_SLUG} --force
  npx ${PACKAGE_NAME} doctor
`;
  process.stdout.write(text.trimStart() + "\n");
}

function expandHome(inputPath) {
  if (!inputPath) return inputPath;
  if (inputPath === "~") return os.homedir();
  if (inputPath.startsWith("~/") || inputPath.startsWith("~\\")) {
    return path.join(os.homedir(), inputPath.slice(2));
  }
  return inputPath;
}

function parseArgs(argv) {
  let command = "help";
  let index = 0;
  if (argv.length > 0 && !argv[0].startsWith("-")) {
    command = argv[0];
    index = 1;
  }

  const options = {
    tool: "auto",
    target: null,
    force: false,
    dryRun: false,
  };

  for (let i = index; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "-h" || arg === "--help") {
      command = "help";
      continue;
    }
    if (arg === "--force") {
      options.force = true;
      continue;
    }
    if (arg === "--dry-run") {
      options.dryRun = true;
      continue;
    }
    if (arg === "--tool") {
      const value = argv[i + 1];
      if (!value) throw new Error("Missing value for --tool.");
      options.tool = value;
      i += 1;
      continue;
    }
    if (arg.startsWith("--tool=")) {
      options.tool = arg.slice("--tool=".length);
      continue;
    }
    if (arg === "--target") {
      const value = argv[i + 1];
      if (!value) throw new Error("Missing value for --target.");
      options.target = value;
      i += 1;
      continue;
    }
    if (arg.startsWith("--target=")) {
      options.target = arg.slice("--target=".length);
      continue;
    }
    throw new Error(`Unknown argument: ${arg}`);
  }

  return { command, options };
}

function detectAutoTools() {
  const tools = [];
  if (fs.existsSync(path.join(os.homedir(), ".codex"))) tools.push("codex");
  if (fs.existsSync(path.join(os.homedir(), ".claude"))) tools.push("claude");
  if (tools.length === 0) tools.push("codex");
  return tools;
}

function resolveTargets(tool, customTarget) {
  const normalizedTool = (tool || "auto").toLowerCase();
  if (customTarget) {
    return [
      {
        tool: normalizedTool === "auto" ? "custom" : normalizedTool,
        targetPath: path.resolve(expandHome(customTarget)),
      },
    ];
  }
  if (normalizedTool === "auto") {
    return detectAutoTools().map((t) => ({ tool: t, targetPath: DEFAULT_TARGETS[t] }));
  }
  if (!Object.prototype.hasOwnProperty.call(DEFAULT_TARGETS, normalizedTool)) {
    throw new Error(`Invalid --tool value: ${tool}. Use codex, claude, or auto.`);
  }
  return [{ tool: normalizedTool, targetPath: DEFAULT_TARGETS[normalizedTool] }];
}

function ensurePayloadAvailable() {
  const missing = [];
  for (const item of PAYLOAD_ITEMS) {
    const source = path.join(ROOT_DIR, item);
    if (!fs.existsSync(source)) {
      missing.push(item);
    }
  }
  if (missing.length > 0) {
    throw new Error(`Payload is incomplete. Missing: ${missing.join(", ")}`);
  }
}

function copyPayload(targetPath, dryRun) {
  if (dryRun) {
    process.stdout.write(`[dry-run] mkdir -p ${targetPath}\n`);
  } else {
    fs.mkdirSync(targetPath, { recursive: true });
  }

  for (const item of PAYLOAD_ITEMS) {
    const source = path.join(ROOT_DIR, item);
    const destination = path.join(targetPath, item);
    if (dryRun) {
      process.stdout.write(`[dry-run] copy ${source} -> ${destination}\n`);
    } else {
      fs.cpSync(source, destination, { recursive: true });
    }
  }
}

function install(options) {
  ensurePayloadAvailable();
  const targets = resolveTargets(options.tool, options.target);
  for (const entry of targets) {
    const { tool, targetPath } = entry;
    const exists = fs.existsSync(targetPath);
    if (exists && !options.force) {
      throw new Error(
        `Target already exists (${targetPath}). Re-run with --force to overwrite.`
      );
    }
    if (exists) {
      if (options.dryRun) {
        process.stdout.write(`[dry-run] rm -rf ${targetPath}\n`);
      } else {
        fs.rmSync(targetPath, { recursive: true, force: true });
      }
    }
    copyPayload(targetPath, options.dryRun);
    process.stdout.write(
      `${options.dryRun ? "[dry-run] " : ""}Installed for ${tool} -> ${targetPath}\n`
    );
  }
}

function uninstall(options) {
  const targets = resolveTargets(options.tool, options.target);
  for (const entry of targets) {
    const { tool, targetPath } = entry;
    if (!fs.existsSync(targetPath)) {
      process.stdout.write(`Skip ${tool}: not found at ${targetPath}\n`);
      continue;
    }
    if (options.dryRun) {
      process.stdout.write(`[dry-run] rm -rf ${targetPath}\n`);
      continue;
    }
    fs.rmSync(targetPath, { recursive: true, force: true });
    process.stdout.write(`Removed ${tool} installation -> ${targetPath}\n`);
  }
}

function doctor() {
  const nodeMajor = Number.parseInt(process.versions.node.split(".")[0], 10);
  const nodeOk = Number.isFinite(nodeMajor) && nodeMajor >= 18;
  process.stdout.write(`Node version: ${process.versions.node} (${nodeOk ? "ok" : "fail"})\n`);
  if (!nodeOk) {
    process.stdout.write("Requirement: Node >= 18\n");
  }

  const missingPayload = PAYLOAD_ITEMS.filter(
    (item) => !fs.existsSync(path.join(ROOT_DIR, item))
  );
  process.stdout.write(
    `Payload check: ${missingPayload.length === 0 ? "ok" : `missing ${missingPayload.join(", ")}`}\n`
  );

  for (const [tool, targetPath] of Object.entries(DEFAULT_TARGETS)) {
    const installed = fs.existsSync(path.join(targetPath, "SKILL.md"));
    process.stdout.write(`${tool} target: ${targetPath} (${installed ? "installed" : "not installed"})\n`);
  }

  return nodeOk && missingPayload.length === 0 ? 0 : 1;
}

function main() {
  const { command, options } = parseArgs(process.argv.slice(2));
  switch (command) {
    case "install":
      install(options);
      return 0;
    case "uninstall":
      uninstall(options);
      return 0;
    case "doctor":
      return doctor();
    case "help":
      printHelp();
      return 0;
    default:
      throw new Error(`Unknown command: ${command}`);
  }
}

try {
  const code = main();
  process.exitCode = code;
} catch (error) {
  process.stderr.write(`[${PACKAGE_NAME}] ${error.message}\n`);
  process.exitCode = 1;
}

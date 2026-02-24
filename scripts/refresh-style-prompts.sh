#!/usr/bin/env bash
set -euo pipefail

REPO_PATH="${1:-/mnt/d/stylekit}"
SKILL_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_PATH="${2:-$SKILL_ROOT/references/style-prompts.json}"
INDEX_OUT_PATH="${3:-$(dirname "$OUT_PATH")/style-search-index.json}"

if [ ! -d "$REPO_PATH" ]; then
  echo "Repo path does not exist: $REPO_PATH" >&2
  exit 1
fi

mkdir -p "$(dirname "$OUT_PATH")"
mkdir -p "$(dirname "$INDEX_OUT_PATH")"

cd "$REPO_PATH"

OUT_PATH="$OUT_PATH" INDEX_OUT_PATH="$INDEX_OUT_PATH" pnpm tsx -e '
import fs from "node:fs";
import { styles } from "./lib/styles/index.ts";

const now = new Date().toISOString();
const schemaVersion = "1.1.0";

const stylePrompts = {
  schemaVersion,
  generatedAt: now,
  total: styles.length,
  source: {
    repo: process.cwd(),
    module: "lib/styles/index.ts",
  },
  styles: styles.map((style) => ({
    slug: style.slug,
    name: style.name,
    nameEn: style.nameEn,
    styleType: style.styleType,
    category: style.category,
    tags: style.tags,
    keywords: style.keywords,
    colors: style.colors,
    philosophy: style.philosophy,
    doList: style.doList,
    dontList: style.dontList,
    aiRules: style.aiRules,
    components: {
      button: style.components?.button?.code ?? "",
      card: style.components?.card?.code ?? "",
      input: style.components?.input?.code ?? "",
      nav: style.components?.nav?.code ?? "",
      hero: style.components?.hero?.code ?? "",
      footer: style.components?.footer?.code ?? "",
    },
    examplePrompts: (style.examplePrompts ?? []).map((p) => ({
      title: p.title,
      titleEn: p.titleEn,
      description: p.description,
      descriptionEn: p.descriptionEn,
      prompt: p.prompt,
    })),
  })),
};

const searchIndex = {
  schemaVersion,
  generatedAt: now,
  total: styles.length,
  documents: styles.map((style) => {
    const parts = [
      style.slug,
      style.name,
      style.nameEn,
      style.styleType,
      style.category,
      ...(style.tags ?? []),
      ...(style.keywords ?? []),
      style.philosophy ?? "",
      style.aiRules ?? "",
      ...(style.doList ?? []),
      ...(style.dontList ?? []),
      style.description ?? "",
      style.descriptionEn ?? "",
    ];

    return {
      slug: style.slug,
      styleType: style.styleType,
      tags: style.tags,
      keywords: style.keywords,
      text: parts.join("\n").toLowerCase(),
    };
  }),
};

const outPath = process.env.OUT_PATH;
const indexOutPath = process.env.INDEX_OUT_PATH;

if (!outPath || !indexOutPath) {
  throw new Error("OUT_PATH or INDEX_OUT_PATH is missing");
}

fs.writeFileSync(outPath, JSON.stringify(stylePrompts, null, 2), "utf-8");
fs.writeFileSync(indexOutPath, JSON.stringify(searchIndex, null, 2), "utf-8");

console.log(`Wrote ${outPath}`);
console.log(`Wrote ${indexOutPath}`);
'

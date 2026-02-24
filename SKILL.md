---
name: stylekit-style-prompts
description: Use when users ask to generate beautiful frontend prompts from StyleKit styles, select the best matching style, blend multiple styles, or audit/fix prompt quality for ChatGPT, Cursor, Claude, and other coding assistants.
---

# StyleKit Style Prompts

## Purpose

Generate better-looking frontend output by combining StyleKit style identity, actionable constraints, and quality checks.

## Quick One-shot Command

Run full flow in one command:

`python scripts/run_pipeline.py --query "<requirement>" --stack nextjs --format json`

Force multi-style blend:

`python scripts/run_pipeline.py --query "<requirement>" --stack nextjs --blend-mode on --format json`

Run targeted refinement (polish/debug/contrast/layout/component-fill):

`python scripts/run_pipeline.py --query "<requirement>" --stack nextjs --refine-mode debug --format json`

Run with screenshot/Figma reference constraints:

`python scripts/run_pipeline.py --query "<requirement>" --stack nextjs --reference-type screenshot --reference-notes "<what to preserve/fix>" --format json`

Run with structured reference payload:

`python scripts/run_pipeline.py --query "<requirement>" --stack nextjs --reference-type screenshot --reference-file refs/screen-analysis.json --format json`

Run strict schema mode for reference payload:

`python scripts/run_pipeline.py --query "<requirement>" --stack nextjs --reference-type screenshot --reference-file refs/screen-analysis.json --strict-reference-schema --format json`

Benchmark current quality:

`python scripts/benchmark_pipeline.py --format json`

Benchmark with snapshot output:

`python scripts/benchmark_pipeline.py --format json --snapshot-out tmp/benchmark-latest.json`

Run regression gate against baseline snapshot:

`python scripts/benchmark_pipeline.py --format json --baseline-snapshot tmp/benchmark-baseline.json --fail-on-regression`

Auto-update baseline on successful gate:

`python scripts/benchmark_pipeline.py --format json --baseline-snapshot references/benchmark-baseline.json --baseline-update-mode on-pass --baseline-update-target references/benchmark-baseline.json`

CI one-command gate:

`bash scripts/ci_regression_gate.sh --baseline references/benchmark-baseline.json --snapshot-out tmp/benchmark-ci-latest.json`

## Workflow 1: Requirement -> Style Candidates -> Design Brief -> Prompt

1. Refresh dataset when needed:
   `bash scripts/refresh-style-prompts.sh /mnt/d/stylekit`
2. Retrieve top style candidates:
   `python scripts/search_stylekit.py --query "<requirement>" --top 5`
3. Generate design brief and prompts:
   `python scripts/generate_brief.py --query "<requirement>" --stack nextjs --mode brief+prompt`
4. If needed, force multi-style blend ownership:
   `python scripts/generate_brief.py --query "<requirement>" --stack nextjs --mode brief+prompt --blend-mode on`
5. For iterative work, set refine mode:
   `python scripts/generate_brief.py --query "<requirement>" --stack nextjs --mode brief+prompt --refine-mode polish`
6. For screenshot/Figma-driven generation, add reference context:
   `python scripts/generate_brief.py --query "<requirement>" --stack nextjs --mode brief+prompt --reference-type figma --reference-notes "<frame scope>"`
7. If reference analysis is available, pass structured payload:
   `python scripts/generate_brief.py --query "<requirement>" --stack nextjs --mode brief+prompt --reference-type screenshot --reference-json '{"layout":{"issues":["sidebar overlaps content"]}}'`
8. For high-confidence pipelines, enable strict schema mode:
   `python scripts/generate_brief.py --query "<requirement>" --stack nextjs --mode brief+prompt --reference-file refs/screen-analysis.json --strict-reference-schema`
9. If quality gate fails, run audit + fix workflow.

## Workflow 2: Existing Prompt -> Quality Audit -> Fix Suggestions

1. Audit prompt text:
   `python scripts/qa_prompt.py --input prompt.md --style <slug>`
2. If this is an iterative update, enforce mode alignment:
   `python scripts/qa_prompt.py --input prompt.md --style <slug> --require-refine-mode layout-fix`
3. If screenshot/Figma context is required, enforce reference guard:
   `python scripts/qa_prompt.py --input prompt.md --style <slug> --require-reference-type screenshot`
4. If structured reference payload exists, require extracted-signal block:
   `python scripts/qa_prompt.py --input prompt.md --style <slug> --require-reference-type screenshot --require-reference-signals`
5. Read `violations` and `autofix_suggestions`.
6. Rewrite prompt and re-run audit until status is `pass`.

## Workflow 3: Multi-style Blend with Conflict Resolution

1. Identify base style from search rank #1.
2. Select up to 2 supporting styles from top candidates.
3. Resolve ownership explicitly:
   - color owner
   - typography owner
   - spacing owner
   - motion/interaction owner
4. Output one merged prompt with priority order.

## Output Contract

Always follow `references/output-contract.md`.

Primary output object fields:

- `design_brief`
- `hard_prompt`
- `soft_prompt`
- `ai_rules`
- `style_choice`
- `quality_gate` (for audits)
- `design_brief.refine_mode`
- `design_brief.input_context.reference_type`

## Working Rules

- Never invent style slugs.
- Use only `references/style-prompts.json` as style source of truth.
- Keep aiRules concrete and testable.
- Remove contradictory rules before output (single source-of-truth per constraint).
- Prefer imperative constraints over decorative language.
- Start with explicit design intent (purpose, audience, tone, memorable hook).
- Enforce anti-generic constraints to avoid interchangeable AI-looking output.
- Include pre-delivery validation tests (swap/squint/signature/token).
- Include an anti-pattern blacklist (absolute layout misuse, nested scroll, missing focus states, etc.).
- Preserve user language (Chinese in -> Chinese out; English in -> English out).
- If intent is ambiguous, return top 3 candidates with reasons before final prompt.

## Stack Adapters

Supported stack hints in generation:

- `html-tailwind`
- `react`
- `nextjs`
- `vue`
- `svelte`
- `tailwind-v4`

If stack is unknown, fallback to framework-agnostic Tailwind semantics.

## Resource Files

- `references/style-prompts.json`: full style prompt catalog.
- `references/style-search-index.json`: lightweight search document index.
- `references/output-contract.md`: output schema and examples.
- `references/frontend-design-principles.md`: distinctiveness and anti-generic design heuristics.
- `references/design-system-patterns.md`: token hierarchy and component architecture.
- `references/accessibility-gate.md`: WCAG + mobile touch baseline for prompt quality.
- `scripts/refresh-style-prompts.sh`: rebuild style dataset from local repo.
- `scripts/search_stylekit.py`: query -> ranked style candidates.
- `scripts/generate_brief.py`: query -> design brief + prompts.
- `scripts/qa_prompt.py`: prompt quality gate and autofix hints.
- `scripts/run_pipeline.py`: one-shot search + brief generation + QA gate.
- `scripts/benchmark_pipeline.py`: benchmark pass-rate, hard-check pass rate, bucket pass-rate (`strict-domain`/`balanced`/`expressive`), snapshot export, and baseline regression gate.
- `scripts/ci_regression_gate.sh`: CI wrapper for benchmark regression gate (supports baseline bootstrap).
- `scripts/smoke_test.py`: validate end-to-end script integrity.
- `references/benchmark-baseline.json`: default baseline snapshot for CI gate.
- `references/github-actions-regression-gate.yml`: GitHub Actions template for regression automation.

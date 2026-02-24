# StyleKit Style Prompts Output Contract

## 1) Candidate Search Output

Source: `scripts/search_stylekit.py`

```json
{
  "query": "SaaS financial dashboard",
  "query_tokens": ["saas", "financial", "dashboard"],
  "expanded_query_tokens": ["saas", "financial", "dashboard", "finance", "admin", "analytics"],
  "top": 5,
  "returned": 5,
  "style_type_filter": "visual",
  "schemaVersion": "1.1.0",
  "generatedAt": "2026-02-24T00:00:00.000Z",
  "candidates": [
    {
      "slug": "neo-brutalist",
      "name": "新野兽派",
      "nameEn": "Neo-Brutalist",
      "styleType": "visual",
      "score": 23.45,
      "reason": {
        "exact_slug": false,
        "exact_name": false,
        "style_type_match": true,
        "matched_keywords": ["dashboard"],
        "matched_tags": ["high-contrast"],
        "concept_overlap": 4
      },
      "reason_summary": "keyword overlap; tag overlap",
      "preview": {
        "keywords": ["dashboard", "bold"],
        "tags": ["modern", "high-contrast"]
      }
    }
  ]
}
```

## 2) Design Brief + Prompt Output

Source: `scripts/generate_brief.py`

```json
{
  "query": "...",
  "mode": "brief+prompt",
  "language": "zh",
  "style_choice": {
    "primary": {
      "slug": "...",
      "name": "...",
      "nameEn": "...",
      "styleType": "visual"
    },
    "alternatives": [],
    "why": "..."
  },
  "design_brief": {
    "style_choice": {},
    "design_intent": {
      "purpose": "...",
      "audience": "...",
      "tone": "...",
      "memorable_hook": "..."
    },
    "refine_mode": "polish",
    "iteration_strategy": {
      "mode": "polish",
      "objective": "...",
      "constraints": ["..."]
    },
    "input_context": {
      "reference_type": "screenshot",
      "reference_notes": "...",
      "reference_file": "...",
      "reference_payload_present": true,
      "reference_schema_validation": {
        "valid": true,
        "strict_mode": false,
        "errors": [],
        "warnings": [],
        "coercions": [],
        "unknown_fields": []
      },
      "reference_guidelines": ["..."],
      "reference_signal_summary": "layout:2, components:1, a11y:1",
      "reference_signals": {
        "layout_issues": ["..."],
        "missing_components": ["..."],
        "preserve_elements": ["..."],
        "interaction_gaps": ["..."],
        "a11y_gaps": ["..."],
        "token_clues": ["..."],
        "notes": ["..."]
      },
      "reference_derived_rules": ["..."]
    },
    "visual_direction": "...",
    "typography_strategy": "...",
    "font_strategy_hints": ["..."],
    "anti_generic_constraints": ["..."],
    "validation_tests": ["..."],
    "anti_pattern_blacklist": ["..."],
    "design_system_structure": {
      "token_hierarchy": ["..."],
      "component_architecture": ["..."]
    },
    "color_strategy": {
      "primary": "#xxxxxx",
      "secondary": "#xxxxxx",
      "accent": ["#xxxxxx"]
    },
    "component_guidelines": ["..."],
    "interaction_rules": ["..."],
    "a11y_baseline": ["..."],
    "stack_hint": "...",
    "blend_plan": {
      "enabled": true,
      "base_style": "glassmorphism",
      "blend_styles": [{"slug": "apple-style", "weight": 0.25}],
      "conflict_resolution": {
        "color_owner": "glassmorphism",
        "typography_owner": "editorial",
        "spacing_owner": "dashboard-layout",
        "motion_owner": "glassmorphism"
      },
      "priority_order": ["glassmorphism", "apple-style"],
      "notes": "..."
    }
  },
  "ai_rules": ["..."],
  "hard_prompt": "...",
  "soft_prompt": "...",
  "candidate_rank": []
}
```

Rules:

- `ai_rules` must have at least 3 actionable items.
- `mode=brief-only` returns empty `hard_prompt` and `soft_prompt`.
- Language follows user query language.
- `blend_mode=on` forces blend plan if at least one alternative style exists.
- `refine_mode` supports: `new`, `polish`, `debug`, `contrast-fix`, `layout-fix`, `component-fill`.
- `reference_type` supports: `none`, `screenshot`, `figma`, `mixed`.
- Optional reference payload can be passed via `--reference-file` or `--reference-json`.
- Optional `--strict-reference-schema` fails on schema errors/unknown top-level fields.

## 3) Prompt QA Output

Source: `scripts/qa_prompt.py`

```json
{
  "status": "pass",
  "checks": [
    {
      "id": "min_actionable_rules",
      "severity": "high",
      "passed": true,
      "message": "...",
      "details": {}
    }
  ],
  "violations": [],
  "autofix_suggestions": [],
  "meta": {
    "style": "vaporwave",
    "min_ai_rules": 3,
    "prompt_length": 1200
  }
}
```

Common additional checks:

- `rule_conflict`
- `language_consistency`
- `wcag_touch_baseline`
- `typography_distinctiveness`
- `design_system_structure`
- `intent_validation_tests`
- `anti_pattern_guard`
- `refinement_mode_alignment` (when `--require-refine-mode` is provided)
- `reference_context_guard` (when `--require-reference-type` is provided)
- `reference_signal_alignment` (when `--require-reference-signals` is provided)

Status policy:

- `fail` if any `high` check fails.
- `fail` if 2 or more `medium` checks fail.
- Otherwise `pass`.

JSON input support:

- If `--input` or `--text` contains JSON, QA tries to extract prompt text from:
  1. preferred `--prompt-field` (default: `hard_prompt`)
  2. fallback fields: `hard_prompt`, `soft_prompt`, `prompt`, `text`
- Optional `--lang` can enforce expected prompt language (`en` or `zh`).
- Optional `--require-refine-mode` can enforce mode-aligned constraints.
- Optional `--require-reference-type` can enforce screenshot/Figma handling constraints.
- Optional `--require-reference-signals` enforces explicit extracted-signal sections.
- `meta.source_kind` and `meta.source_field` report extraction source.

## 4) One-shot Pipeline Output

Source: `scripts/run_pipeline.py`

```json
{
  "status": "pass",
  "query": "...",
  "stack": "nextjs",
  "style_type_filter": "visual",
  "blend_mode": "auto",
  "refine_mode": "new",
  "reference_type": "none",
  "strict_reference_schema": false,
  "selected_style": "glassmorphism",
  "candidates": [],
  "result": {},
  "quality_gate": {}
}
```

Rules:

- `status` mirrors QA result.
- `result` equals output from `generate_brief.py`.
- `quality_gate` equals output from `qa_prompt.py`.
- `blend_mode` controls blend behavior: `off`, `auto`, `on`.

## 5) Benchmark Output

Source: `scripts/benchmark_pipeline.py`

```json
{
  "summary": {
    "pass_rate": 1.0,
    "check_pass_rate": {},
    "bucket_pass_rate": {}
  },
  "regression_gate": {
    "enabled": true,
    "passed": true,
    "thresholds": {
      "max_pass_rate_drop": 0.02,
      "max_bucket_pass_drop": 0.05,
      "max_check_pass_drop": 0.05
    },
    "findings": []
  },
  "baseline_update": {
    "mode": "on-pass",
    "target": "references/benchmark-baseline.json",
    "enabled": true,
    "applied": true,
    "reason": "on-pass with regression gate"
  },
  "meta": {
    "baseline_snapshot": "tmp/benchmark-baseline.json"
  }
}
```

Rules:

- `--baseline-snapshot` enables regression comparison.
- `--fail-on-regression` exits non-zero when `regression_gate.passed` is `false`.
- `--baseline-update-mode` supports `off`, `on-pass`, `always`.
- `--baseline-update-target` controls where updated baseline snapshot is written.

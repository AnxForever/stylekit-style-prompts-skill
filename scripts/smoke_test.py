#!/usr/bin/env python3
"""Smoke test for stylekit-style-prompts scripts."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
REF_DIR = SKILL_ROOT / "references"

SEARCH = SCRIPT_DIR / "search_stylekit.py"
BRIEF = SCRIPT_DIR / "generate_brief.py"
QA = SCRIPT_DIR / "qa_prompt.py"
PIPELINE = SCRIPT_DIR / "run_pipeline.py"


def run_json(cmd: list[str]) -> dict:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            + " ".join(cmd)
            + "\nSTDOUT:\n"
            + (proc.stdout or "")
            + "\nSTDERR:\n"
            + (proc.stderr or "")
        )
    try:
        return json.loads((proc.stdout or "").strip())
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON output from {' '.join(cmd)}: {exc}")


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run smoke tests for stylekit-style-prompts")
    parser.add_argument("--query", default="高端科技SaaS财务后台，玻璃质感，强调可读性")
    parser.add_argument("--stack", default="nextjs")
    args = parser.parse_args()

    py = sys.executable

    style_prompts = REF_DIR / "style-prompts.json"
    search_index = REF_DIR / "style-search-index.json"
    ensure(style_prompts.exists(), f"Missing file: {style_prompts}")
    ensure(search_index.exists(), f"Missing file: {search_index}")

    search_payload = run_json([py, str(SEARCH), "--query", args.query, "--top", "5", "--format", "json"])
    ensure(len(search_payload.get("candidates", [])) >= 1, "Search returned no candidates")
    ensure(len(search_payload.get("expanded_query_tokens", [])) >= len(search_payload.get("query_tokens", [])), "Query token expansion failed")

    brief_payload = run_json(
        [
            py,
            str(BRIEF),
            "--query",
            args.query,
            "--stack",
            args.stack,
            "--mode",
            "brief+prompt",
            "--blend-mode",
            "on",
            "--refine-mode",
            "contrast-fix",
            "--reference-type",
            "screenshot",
            "--reference-notes",
            "来自已有页面截图，需要保持结构并修复可读性。",
            "--reference-json",
            json.dumps(
                {
                    "source": "screenshot",
                    "layout": {"issues": ["sidebar overlaps content area", "header pushes KPI cards below fold"]},
                    "components": {"missing": ["empty state on table", "pagination controls"]},
                    "interaction": {"missing_states": ["focus-visible on nav items"]},
                    "accessibility": {"issues": ["low contrast in muted text"]},
                    "tokens": {"colors": ["#111827", "#f9fafb"], "spacing": ["8,16,24"]},
                },
                ensure_ascii=False,
            ),
            "--strict-reference-schema",
        ]
    )
    ensure(bool(brief_payload.get("hard_prompt")), "hard_prompt is empty")
    ensure(bool(brief_payload.get("soft_prompt")), "soft_prompt is empty")
    blend_plan = brief_payload.get("design_brief", {}).get("blend_plan", {})
    ensure(bool(blend_plan.get("enabled")), "Blend plan not enabled in blend-mode on")
    ensure(
        len(brief_payload.get("design_brief", {}).get("validation_tests", [])) >= 3,
        "design_brief.validation_tests is missing or too short",
    )
    ensure(
        len(brief_payload.get("design_brief", {}).get("anti_pattern_blacklist", [])) >= 3,
        "design_brief.anti_pattern_blacklist is missing or too short",
    )
    ensure(
        brief_payload.get("design_brief", {}).get("refine_mode") == "contrast-fix",
        "design_brief.refine_mode mismatch",
    )
    ensure(
        brief_payload.get("design_brief", {}).get("input_context", {}).get("reference_type") == "screenshot",
        "design_brief.input_context.reference_type mismatch",
    )
    ensure(
        bool(brief_payload.get("design_brief", {}).get("input_context", {}).get("reference_signal_summary")),
        "design_brief.input_context.reference_signal_summary is empty",
    )
    ensure(
        brief_payload.get("design_brief", {}).get("input_context", {}).get("reference_schema_validation", {}).get("valid") is True,
        "reference schema validation should be valid",
    )
    ensure(
        len(brief_payload.get("design_brief", {}).get("iteration_strategy", {}).get("constraints", [])) >= 2,
        "design_brief.iteration_strategy.constraints missing",
    )

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as tmp:
        json.dump(brief_payload, tmp, ensure_ascii=False, indent=2)
        tmp_path = tmp.name

    try:
        qa_payload = run_json(
            [
                py,
                str(QA),
                "--input",
                tmp_path,
                "--require-refine-mode",
                "contrast-fix",
                "--require-reference-type",
                "screenshot",
                "--require-reference-signals",
            ]
        )
        ensure(qa_payload.get("meta", {}).get("source_kind") == "json", "QA did not detect JSON input")
        ensure(
            any(c.get("id") == "refinement_mode_alignment" for c in qa_payload.get("checks", [])),
            "QA missing refinement_mode_alignment check",
        )
        ensure(
            any(c.get("id") == "reference_context_guard" for c in qa_payload.get("checks", [])),
            "QA missing reference_context_guard check",
        )
        ensure(
            any(c.get("id") == "reference_signal_alignment" for c in qa_payload.get("checks", [])),
            "QA missing reference_signal_alignment check",
        )
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    pipeline_payload = run_json(
        [
            py,
            str(PIPELINE),
            "--query",
            args.query,
            "--stack",
            args.stack,
            "--blend-mode",
            "on",
            "--refine-mode",
            "debug",
            "--reference-type",
            "screenshot",
            "--reference-json",
            json.dumps(
                {
                    "source": "screenshot",
                    "layout_issues": ["sidebar width causes overflow on tablet"],
                    "missing_components": ["mobile nav collapse state"],
                },
                ensure_ascii=False,
            ),
            "--strict-reference-schema",
            "--format",
            "json",
        ]
    )
    ensure(pipeline_payload.get("status") == "pass", "Pipeline quality gate failed")
    ensure("quality_gate" in pipeline_payload, "Pipeline missing quality_gate")
    ensure(pipeline_payload.get("quality_gate", {}).get("status") == "pass", "Quality gate status is not pass")

    print(
        json.dumps(
            {
                "status": "pass",
                "search_candidates": len(search_payload.get("candidates", [])),
                "blend_enabled": blend_plan.get("enabled"),
                "pipeline_status": pipeline_payload.get("status"),
                "pipeline_refine_mode": pipeline_payload.get("refine_mode"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

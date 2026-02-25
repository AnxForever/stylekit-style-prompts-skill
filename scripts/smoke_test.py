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
PROPOSE_UPGRADE = SCRIPT_DIR / "propose_upgrade.py"
REVIEW_UPGRADE = SCRIPT_DIR / "review_upgrade_candidate.py"
VALIDATE_TAXONOMY = SCRIPT_DIR / "validate_taxonomy.py"
MERGE_TAXONOMY = SCRIPT_DIR / "merge_taxonomy_expansion.py"
VALIDATE_CONTRACT_SYNC = SCRIPT_DIR / "validate_output_contract_sync.py"


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


def run_expect_fail(cmd: list[str], label: str) -> None:
    """Run a command and assert it exits non-zero."""
    proc = subprocess.run(cmd, capture_output=True, text=True)
    ensure(proc.returncode != 0, f"[{label}] expected failure but got exit 0")


def validate_brief_schema(payload: dict) -> None:
    """Validate generate_brief.py output matches the output contract schema."""
    # Top-level required keys
    for key in ("query", "mode", "language", "style_choice", "design_brief", "ai_rules"):
        ensure(key in payload, f"Missing top-level key: {key}")

    ensure(isinstance(payload["ai_rules"], list), "ai_rules must be a list")
    ensure(len(payload["ai_rules"]) >= 3, "ai_rules must have >= 3 items")

    sc = payload["style_choice"]
    ensure("primary" in sc, "style_choice.primary missing")
    for k in ("slug", "name", "nameEn", "styleType"):
        ensure(k in sc["primary"], f"style_choice.primary.{k} missing")

    db = payload["design_brief"]
    brief_required = [
        "style_choice", "design_intent", "refine_mode", "iteration_strategy",
        "input_context", "visual_direction", "anti_generic_constraints",
        "validation_tests", "anti_pattern_blacklist", "design_system_structure",
        "site_profile", "tag_bundle", "composition_plan", "decision_flow",
        "content_plan", "component_guidelines", "interaction_rules",
        "a11y_baseline", "stack_hint", "blend_plan",
    ]
    for key in brief_required:
        ensure(key in db, f"design_brief.{key} missing")

    # design_intent sub-keys
    for k in ("purpose", "audience", "tone", "memorable_hook"):
        ensure(k in db["design_intent"], f"design_brief.design_intent.{k} missing")

    # iteration_strategy sub-keys
    for k in ("mode", "objective", "constraints"):
        ensure(k in db["iteration_strategy"], f"design_brief.iteration_strategy.{k} missing")

    # input_context sub-keys
    ic = db["input_context"]
    for k in ("reference_type", "reference_payload_present", "reference_has_signals", "reference_schema_validation"):
        ensure(k in ic, f"design_brief.input_context.{k} missing")

    # blend_plan sub-keys
    bp = db["blend_plan"]
    for k in ("enabled", "base_style", "blend_styles", "priority_order"):
        ensure(k in bp, f"design_brief.blend_plan.{k} missing")

    # prompts when mode is brief+prompt
    if payload["mode"] == "brief+prompt":
        ensure(bool(payload.get("hard_prompt")), "hard_prompt empty in brief+prompt mode")
        ensure(bool(payload.get("soft_prompt")), "soft_prompt empty in brief+prompt mode")
    elif payload["mode"] == "brief-only":
        ensure(payload.get("hard_prompt", "") == "", "hard_prompt should be empty in brief-only mode")
        ensure(payload.get("soft_prompt", "") == "", "soft_prompt should be empty in brief-only mode")


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
    validate_brief_schema(brief_payload)

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
            "--site-type",
            "dashboard",
            "--content-depth",
            "skeleton",
            "--recommendation-mode",
            "hybrid",
            "--decision-speed",
            "fast",
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
    ensure(bool(pipeline_payload.get("site_profile")), "Pipeline missing site_profile")
    ensure(bool(pipeline_payload.get("tag_bundle")), "Pipeline missing tag_bundle")
    ensure(bool(pipeline_payload.get("composition_plan")), "Pipeline missing composition_plan")
    ensure(bool(pipeline_payload.get("decision_flow")), "Pipeline missing decision_flow")
    ensure(bool(pipeline_payload.get("content_plan")), "Pipeline missing content_plan")

    # Force one synthetic warning payload so upgrade proposal flow is exercised.
    upgrade_seed = dict(pipeline_payload)
    # Force regeneration path from synthetic QA signals.
    upgrade_seed.pop("upgrade_candidates", None)
    upgrade_seed["quality_gate"] = {
        "status": "fail",
        "violations": [{"id": "interaction_accessibility", "message": "synthetic smoke signal"}],
        "warnings": [{"id": "synthetic_warning", "message": "synthetic smoke warning"}],
        "checks": [],
    }
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as upf:
        json.dump(upgrade_seed, upf, ensure_ascii=False, indent=2)
        upgrade_seed_path = upf.name

    try:
        proposal_payload = run_json(
            [
                py,
                str(PROPOSE_UPGRADE),
                "--pipeline-output",
                upgrade_seed_path,
                "--out-dir",
                str(SKILL_ROOT / "tmp" / "upgrade-proposals"),
                "--format",
                "json",
            ]
        )
    finally:
        try:
            os.remove(upgrade_seed_path)
        except OSError:
            pass

    ensure(proposal_payload.get("status") == "proposed", "Upgrade proposal should be generated")
    proposal_file = proposal_payload.get("output_file")
    ensure(bool(proposal_file), "Upgrade proposal output_file is missing")
    review_payload = run_json([py, str(REVIEW_UPGRADE), "--candidate", str(proposal_file), "--format", "json"])
    ensure(review_payload.get("status") == "pass", "Upgrade proposal review failed")

    # --- Negative tests ---

    # Invalid style slug should fail
    run_expect_fail(
        [py, str(BRIEF), "--query", "test", "--style", "nonexistent-slug-xyz-999"],
        "invalid style slug",
    )

    # Strict reference schema with unknown top-level fields should fail
    run_expect_fail(
        [
            py, str(BRIEF), "--query", "test", "--strict-reference-schema",
            "--reference-json", json.dumps({"bogus_field": "value", "another_unknown": 123}),
        ],
        "strict schema with unknown fields",
    )

    # merge_taxonomy: invalid new_style_tags should fail fast in dry-run
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as merge_bad:
        json.dump(
            {
                "new_enum_values": [],
                "new_profiles": {},
                "new_style_tags": ["Bad Tag With Spaces"],
            },
            merge_bad,
            ensure_ascii=False,
            indent=2,
        )
        merge_bad_path = merge_bad.name
    try:
        run_expect_fail(
            [py, str(MERGE_TAXONOMY), "--type", "animation", "--input", merge_bad_path, "--dry-run"],
            "invalid new_style_tags in merge_taxonomy",
        )
    finally:
        try:
            os.remove(merge_bad_path)
        except OSError:
            pass

    # --- brief-only mode test ---
    brief_only_payload = run_json(
        [py, str(BRIEF), "--query", args.query, "--stack", args.stack, "--mode", "brief-only"]
    )
    validate_brief_schema(brief_only_payload)
    ensure(brief_only_payload.get("hard_prompt", "") == "", "brief-only should have empty hard_prompt")
    ensure(brief_only_payload.get("soft_prompt", "") == "", "brief-only should have empty soft_prompt")

    # --- English query test ---
    en_payload = run_json(
        [py, str(BRIEF), "--query", "modern SaaS dashboard with glassmorphism", "--stack", "nextjs", "--mode", "brief+prompt"]
    )
    validate_brief_schema(en_payload)
    ensure(en_payload.get("language") == "en", "English query should detect lang=en")
    ensure(bool(en_payload.get("hard_prompt")), "English brief+prompt should have hard_prompt")

    # --- Taxonomy validation ---
    taxonomy_payload = run_json(
        [
            py,
            str(VALIDATE_TAXONOMY),
            "--format",
            "json",
            "--max-unused-style-tags",
            "0",
            "--fail-on-warning",
        ]
    )
    ensure(taxonomy_payload.get("status") == "pass", "Taxonomy validation failed")
    ensure(taxonomy_payload.get("coverage", 0) >= 0.70, "Taxonomy coverage below 70%")
    stats = taxonomy_payload.get("style_tag_registry_stats", {}) or {}
    ensure(stats.get("unused_count", 0) == 0, "Style tag registry should have no unused tags in smoke baseline")

    # --- Output contract sync guard ---
    contract_sync_payload = run_json(
        [py, str(VALIDATE_CONTRACT_SYNC), "--format", "json", "--fail-on-warning"]
    )
    ensure(contract_sync_payload.get("status") == "pass", "Output contract sync validation failed")

    # --- Taxonomy style-tag registry guard (negative path) ---
    routing_src = REF_DIR / "taxonomy" / "site-type-routing.json"
    routing_data = json.loads(routing_src.read_text(encoding="utf-8"))
    routing_data["site_types"]["blog"]["favored_style_tags"][0] = "smoke-invalid-style-tag"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as tf:
        json.dump(routing_data, tf, ensure_ascii=False, indent=2)
        bad_routing_path = tf.name
    try:
        proc = subprocess.run(
            [py, str(VALIDATE_TAXONOMY), "--format", "json", "--routing-file", bad_routing_path],
            capture_output=True,
            text=True,
        )
    finally:
        try:
            os.remove(bad_routing_path)
        except OSError:
            pass
    ensure(proc.returncode != 0, "Taxonomy validator should fail when routing includes unregistered style tag")
    bad_routing_payload = json.loads((proc.stdout or "").strip())
    ensure(bad_routing_payload.get("status") == "fail", "Bad routing validation should report fail")
    ensure(
        any("not in style-tag-registry" in str(e) for e in bad_routing_payload.get("errors", [])),
        "Bad routing validation should report style-tag-registry mismatch",
    )

    # --- Taxonomy registry usage coverage guard (negative path) ---
    registry_src = REF_DIR / "taxonomy" / "style-tag-registry.json"
    registry_data = json.loads(registry_src.read_text(encoding="utf-8"))
    registry_tags = registry_data.get("allowed_style_tags", [])
    ensure(isinstance(registry_tags, list), "style-tag-registry allowed_style_tags should be a list")
    registry_tags.append("smoke-unused-style-tag")
    registry_data["allowed_style_tags"] = registry_tags
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as tf_reg:
        json.dump(registry_data, tf_reg, ensure_ascii=False, indent=2)
        bad_registry_path = tf_reg.name
    try:
        proc = subprocess.run(
            [
                py,
                str(VALIDATE_TAXONOMY),
                "--format",
                "json",
                "--style-tag-registry-file",
                bad_registry_path,
                "--max-unused-style-tags",
                "0",
            ],
            capture_output=True,
            text=True,
        )
    finally:
        try:
            os.remove(bad_registry_path)
        except OSError:
            pass
    ensure(proc.returncode != 0, "Taxonomy validator should fail when unused style tags exceed threshold")
    bad_registry_payload = json.loads((proc.stdout or "").strip())
    ensure(bad_registry_payload.get("status") == "fail", "Bad registry validation should report fail")
    ensure(
        any("unused tag count" in str(e) for e in bad_registry_payload.get("errors", [])),
        "Bad registry validation should report unused tag threshold violation",
    )

    print(
        json.dumps(
            {
                "status": "pass",
                "search_candidates": len(search_payload.get("candidates", [])),
                "blend_enabled": blend_plan.get("enabled"),
                "pipeline_status": pipeline_payload.get("status"),
                "pipeline_refine_mode": pipeline_payload.get("refine_mode"),
                "pipeline_site_type": (pipeline_payload.get("site_profile", {}) or {}).get("site_type"),
                "upgrade_review": review_payload.get("status"),
                "negative_tests": "pass",
                "brief_only_test": "pass",
                "english_query_test": "pass",
                "schema_validation": "pass",
                "taxonomy_validation": taxonomy_payload.get("status"),
                "taxonomy_registry_guard": "pass",
                "taxonomy_registry_usage_guard": "pass",
                "contract_sync_validation": contract_sync_payload.get("status"),
                "taxonomy_coverage": taxonomy_payload.get("coverage"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

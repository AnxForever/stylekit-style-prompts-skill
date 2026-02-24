#!/usr/bin/env python3
"""One-shot pipeline: search -> brief/prompt -> QA."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SEARCH_SCRIPT = SCRIPT_DIR / "search_stylekit.py"
BRIEF_SCRIPT = SCRIPT_DIR / "generate_brief.py"
QA_SCRIPT = SCRIPT_DIR / "qa_prompt.py"

PRODUCT_HINTS = {
    "dashboard": ["dashboard", "admin", "panel", "console", "后台", "仪表盘", "控制台"],
    "landing-page": ["landing", "hero", "marketing", "homepage", "落地页", "首页", "营销"],
    "ecommerce": ["shop", "store", "ecommerce", "checkout", "商品", "电商", "购物", "支付"],
    "docs": ["docs", "documentation", "guide", "manual", "文档", "说明", "手册"],
    "portfolio": ["portfolio", "case study", "作品集", "案例"],
}


def infer_product_type(query: str) -> str:
    text = (query or "").lower()
    for product_type, keywords in PRODUCT_HINTS.items():
        if any(keyword in text for keyword in keywords):
            return product_type
    return "general-web-product"


def build_manual_assistant(
    *,
    query: str,
    stack: str,
    selected_style: str | None,
    search_payload: dict[str, Any],
    brief_payload: dict[str, Any],
) -> dict[str, Any]:
    design_brief = brief_payload.get("design_brief", {}) or {}
    design_intent = design_brief.get("design_intent", {}) or {}
    style_choice = design_brief.get("style_choice", {}) or {}

    return {
        "purpose": "Use this as a frontend design handbook context before generating code.",
        "product_profile": {
            "query": query,
            "inferred_product_type": infer_product_type(query),
            "stack": stack,
            "purpose": design_intent.get("purpose"),
            "audience": design_intent.get("audience"),
            "tone": design_intent.get("tone"),
        },
        "style_recommendation": {
            "selected_style": selected_style,
            "primary": style_choice.get("primary", {}),
            "alternatives": style_choice.get("alternatives", []),
            "top_candidates": search_payload.get("candidates", [])[:5],
        },
        "implementation_handbook": {
            "component_guidelines": design_brief.get("component_guidelines", []),
            "interaction_rules": design_brief.get("interaction_rules", []),
            "a11y_baseline": design_brief.get("a11y_baseline", []),
            "anti_pattern_blacklist": design_brief.get("anti_pattern_blacklist", [])[:8],
            "validation_tests": design_brief.get("validation_tests", []),
        },
    }


def run_json_command(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(
            "Command failed:\n"
            + " ".join(cmd)
            + "\n\nSTDOUT:\n"
            + (proc.stdout or "")
            + "\nSTDERR:\n"
            + (proc.stderr or "")
        )

    out = (proc.stdout or "").strip()
    if not out:
        raise SystemExit(f"Empty output from command: {' '.join(cmd)}")

    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:
        preview = out[:500]
        raise SystemExit(
            f"Invalid JSON from command: {' '.join(cmd)}\nError: {exc}\nOutput preview:\n{preview}"
        )


def to_markdown(payload: dict[str, Any]) -> str:
    blend = payload.get("result", {}).get("design_brief", {}).get("blend_plan", {})
    lines = [
        "# StyleKit Pipeline Result",
        f"- Query: {payload['query']}",
        f"- Workflow: {payload.get('workflow')}",
        f"- Mode: {payload.get('mode')}",
        f"- Stack: {payload['stack']}",
        f"- Selected style: {payload['selected_style']}",
        f"- QA status: {payload['status']}",
        f"- Blend enabled: {bool(blend.get('enabled'))}",
        f"- Refine mode: {payload.get('refine_mode')}",
        f"- Reference type: {payload.get('reference_type')}",
        f"- Strict reference schema: {bool(payload.get('strict_reference_schema'))}",
        "",
        "## Top Candidates",
    ]

    for i, item in enumerate(payload.get("candidates", [])[:5], start=1):
        lines.append(f"{i}. `{item.get('slug')}` ({item.get('nameEn')}) — score {item.get('score')}")

    lines.extend(
        [
            "",
            "## Brief",
            f"- Visual direction: {payload['result'].get('design_brief', {}).get('visual_direction', '')}",
            f"- Typography strategy: {payload['result'].get('design_brief', {}).get('typography_strategy', '')}",
            f"- Blend base: {blend.get('base_style', '')}",
            "",
            "## Quality Gate",
            f"- Violations: {len(payload.get('quality_gate', {}).get('violations', []))}",
        ]
    )

    if blend.get("enabled"):
        c = blend.get("conflict_resolution", {})
        lines.extend(
            [
                "",
                "## Blend Ownership",
                f"- Color: {c.get('color_owner')}",
                f"- Typography: {c.get('typography_owner')}",
                f"- Spacing: {c.get('spacing_owner')}",
                f"- Motion: {c.get('motion_owner')}",
            ]
        )

    manual = payload.get("manual_assistant", {}) or {}
    profile = manual.get("product_profile", {}) or {}
    handbook = manual.get("implementation_handbook", {}) or {}
    if manual:
        lines.extend(
            [
                "",
                "## Handbook Snapshot",
                f"- Inferred product type: {profile.get('inferred_product_type', '')}",
                f"- Purpose: {profile.get('purpose', '')}",
                f"- Audience: {profile.get('audience', '')}",
                f"- Tone: {profile.get('tone', '')}",
                f"- Component guidelines: {len(handbook.get('component_guidelines', []))}",
                f"- Interaction rules: {len(handbook.get('interaction_rules', []))}",
            ]
        )

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run StyleKit full pipeline")
    parser.add_argument("--query", required=True, help="User requirement")
    parser.add_argument(
        "--workflow",
        default="manual",
        choices=["manual", "codegen"],
        help="manual = handbook/knowledge mode, codegen = prompt-generation mode",
    )
    parser.add_argument("--stack", default="html-tailwind", choices=["html-tailwind", "react", "nextjs", "vue", "svelte", "tailwind-v4"])
    parser.add_argument("--style", help="Force style slug")
    parser.add_argument("--style-type", choices=["visual", "layout", "animation"])
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--mode", default=None, choices=["brief-only", "brief+prompt"])
    parser.add_argument("--blend-mode", default=None, choices=["off", "auto", "on"])
    parser.add_argument(
        "--refine-mode",
        default="new",
        choices=["new", "polish", "debug", "contrast-fix", "layout-fix", "component-fill"],
    )
    parser.add_argument("--reference-type", default="none", choices=["none", "screenshot", "figma", "mixed"])
    parser.add_argument("--reference-notes", default="")
    parser.add_argument("--reference-file", default="")
    parser.add_argument("--reference-json", default="")
    parser.add_argument("--strict-reference-schema", action="store_true")
    parser.add_argument("--min-ai-rules", type=int, default=3)
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    args = parser.parse_args()

    py = sys.executable
    resolved_mode = args.mode or ("brief-only" if args.workflow == "manual" else "brief+prompt")
    resolved_blend_mode = args.blend_mode or ("off" if args.workflow == "manual" else "auto")
    if args.style and args.blend_mode is None:
        resolved_blend_mode = "off"

    search_cmd = [py, str(SEARCH_SCRIPT), "--query", args.query, "--top", str(args.top), "--format", "json"]
    if args.style_type:
        search_cmd.extend(["--style-type", args.style_type])
    search_payload = run_json_command(search_cmd)

    brief_cmd = [
        py,
        str(BRIEF_SCRIPT),
        "--query",
        args.query,
        "--stack",
        args.stack,
        "--mode",
        resolved_mode,
        "--blend-mode",
        resolved_blend_mode,
        "--refine-mode",
        args.refine_mode,
        "--reference-type",
        args.reference_type,
    ]
    if args.reference_notes.strip():
        brief_cmd.extend(["--reference-notes", args.reference_notes.strip()])
    if args.reference_file.strip():
        brief_cmd.extend(["--reference-file", args.reference_file.strip()])
    if args.reference_json.strip():
        brief_cmd.extend(["--reference-json", args.reference_json.strip()])
    if args.strict_reference_schema:
        brief_cmd.append("--strict-reference-schema")
    if args.style:
        brief_cmd.extend(["--style", args.style])
    if args.style_type:
        brief_cmd.extend(["--style-type", args.style_type])

    brief_payload = run_json_command(brief_cmd)
    selected_style = args.style or (brief_payload.get("style_choice", {}).get("primary", {}) or {}).get("slug")
    resolved_reference_type = (
        brief_payload.get("design_brief", {}).get("input_context", {}).get("reference_type") or args.reference_type
    )
    reference_payload_present = bool(
        brief_payload.get("design_brief", {}).get("input_context", {}).get("reference_payload_present")
    )

    qa_payload: dict[str, Any]
    if resolved_mode == "brief+prompt":
        qa_input_text = brief_payload.get("hard_prompt") or brief_payload.get("soft_prompt")
        if not qa_input_text:
            qa_input_text = json.dumps(brief_payload, ensure_ascii=False)

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as tmp:
            tmp.write(qa_input_text)
            tmp_path = tmp.name

        try:
            qa_cmd = [py, str(QA_SCRIPT), "--input", tmp_path, "--min-ai-rules", str(args.min_ai_rules)]
            expected_lang = brief_payload.get("language")
            if expected_lang in {"en", "zh"}:
                qa_cmd.extend(["--lang", expected_lang])
            qa_cmd.extend(["--require-refine-mode", args.refine_mode])
            qa_cmd.extend(["--require-reference-type", resolved_reference_type])
            if reference_payload_present:
                qa_cmd.append("--require-reference-signals")
            if selected_style:
                qa_cmd.extend(["--style", selected_style])
            qa_payload = run_json_command(qa_cmd)
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    else:
        qa_payload = {
            "status": "pass",
            "violations": [],
            "warnings": [
                {
                    "code": "QA_SKIPPED_BRIEF_ONLY",
                    "message": "Prompt QA skipped in handbook mode (brief-only).",
                }
            ],
            "checks": [],
        }

    manual_assistant = build_manual_assistant(
        query=args.query,
        stack=args.stack,
        selected_style=selected_style,
        search_payload=search_payload,
        brief_payload=brief_payload,
    )

    output = {
        "status": qa_payload.get("status"),
        "workflow": args.workflow,
        "mode": resolved_mode,
        "query": args.query,
        "stack": args.stack,
        "style_type_filter": args.style_type,
        "blend_mode": resolved_blend_mode,
        "refine_mode": args.refine_mode,
        "reference_type": resolved_reference_type,
        "strict_reference_schema": args.strict_reference_schema,
        "selected_style": selected_style,
        "candidates": search_payload.get("candidates", []),
        "result": brief_payload,
        "manual_assistant": manual_assistant,
        "quality_gate": qa_payload,
    }

    if args.format == "markdown":
        print(to_markdown(output))
    else:
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

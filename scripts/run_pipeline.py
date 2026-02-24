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

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run StyleKit full pipeline")
    parser.add_argument("--query", required=True, help="User requirement")
    parser.add_argument("--stack", default="html-tailwind", choices=["html-tailwind", "react", "nextjs", "vue", "svelte", "tailwind-v4"])
    parser.add_argument("--style", help="Force style slug")
    parser.add_argument("--style-type", choices=["visual", "layout", "animation"])
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--mode", default="brief+prompt", choices=["brief-only", "brief+prompt"])
    parser.add_argument("--blend-mode", default="auto", choices=["off", "auto", "on"])
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
        args.mode,
        "--blend-mode",
        args.blend_mode,
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

    output = {
        "status": qa_payload.get("status"),
        "query": args.query,
        "stack": args.stack,
        "style_type_filter": args.style_type,
        "blend_mode": args.blend_mode,
        "refine_mode": args.refine_mode,
        "reference_type": resolved_reference_type,
        "strict_reference_schema": args.strict_reference_schema,
        "selected_style": selected_style,
        "candidates": search_payload.get("candidates", []),
        "result": brief_payload,
        "quality_gate": qa_payload,
    }

    if args.format == "markdown":
        print(to_markdown(output))
    else:
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

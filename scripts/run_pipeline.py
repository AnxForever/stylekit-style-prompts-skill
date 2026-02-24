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
    "blog": ["blog", "article", "post", "editorial", "博客", "文章", "专栏", "内容站"],
    "landing-page": ["landing", "hero", "marketing", "homepage", "落地页", "首页", "营销"],
    "ecommerce": ["shop", "store", "ecommerce", "checkout", "商品", "电商", "购物", "支付"],
    "docs": ["docs", "documentation", "guide", "manual", "文档", "说明", "手册"],
    "portfolio": ["portfolio", "case study", "作品集", "案例"],
}

NOVICE_HINTS = [
    "一窍不通",
    "不会",
    "不懂",
    "小白",
    "新手",
    "不确定",
    "不知道",
    "just started",
    "beginner",
    "new to frontend",
    "no idea",
]

OPTION_IDS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def infer_product_type(query: str) -> str:
    text = (query or "").lower()
    for product_type, keywords in PRODUCT_HINTS.items():
        if any(keyword in text for keyword in keywords):
            return product_type
    return "general-web-product"


def infer_user_confidence(query: str) -> str:
    text = (query or "").lower()
    if any(keyword in text for keyword in NOVICE_HINTS):
        return "low"
    return "medium"


def is_zh(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text or "")


def style_complexity_label(candidate: dict[str, Any], zh: bool) -> str:
    tags = {str(tag).lower() for tag in (candidate.get("preview", {}) or {}).get("tags", [])}
    style_type = str(candidate.get("styleType", "")).lower()
    if "expressive" in tags or "high-contrast" in tags:
        return "进阶" if zh else "advanced"
    if style_type == "layout" or "minimal" in tags or "modern" in tags:
        return "入门友好" if zh else "beginner-friendly"
    return "标准" if zh else "standard"


def style_risk_note(candidate: dict[str, Any], product_type: str, zh: bool) -> str:
    tags = {str(tag).lower() for tag in (candidate.get("preview", {}) or {}).get("tags", [])}
    style_type = str(candidate.get("styleType", "")).lower()
    if product_type in {"docs", "dashboard"} and ("expressive" in tags or "high-contrast" in tags):
        return "视觉冲击较强，可能影响信息可读性。" if zh else "Very expressive; can reduce dense-information readability."
    if product_type in {"landing-page", "ecommerce"} and style_type == "layout":
        return "这是布局型风格，建议后续再配一个视觉风格。" if zh else "This is layout-first; pair with a visual style in the next step."
    return "风险较低，适合作为默认起点。" if zh else "Low implementation risk; good default starting point."


def build_style_options(search_payload: dict[str, Any], product_type: str, zh: bool, top: int = 4) -> list[dict[str, Any]]:
    candidates = search_payload.get("candidates", [])[:top]
    options: list[dict[str, Any]] = []
    for idx, candidate in enumerate(candidates):
        option_id = OPTION_IDS[idx] if idx < len(OPTION_IDS) else f"OPT{idx + 1}"
        options.append(
            {
                "option_id": option_id,
                "slug": candidate.get("slug"),
                "name": candidate.get("name"),
                "nameEn": candidate.get("nameEn"),
                "styleType": candidate.get("styleType"),
                "reason": candidate.get("reason_summary"),
                "complexity": style_complexity_label(candidate, zh),
                "risk_note": style_risk_note(candidate, product_type, zh),
                "keywords": (candidate.get("preview", {}) or {}).get("keywords", [])[:6],
                "tags": (candidate.get("preview", {}) or {}).get("tags", [])[:4],
            }
        )
    return options


def build_decision_questions(product_type: str, zh: bool) -> list[dict[str, Any]]:
    if zh:
        questions = [
            {
                "id": "visual_intensity",
                "question": "你希望页面更偏哪种视觉强度？",
                "choices": ["克制耐看", "平衡现代", "强烈个性"],
            },
            {
                "id": "content_density",
                "question": "博客内容展示更偏向哪种？",
                "choices": ["长文阅读优先", "图文平衡", "视觉封面优先"],
            },
            {
                "id": "interaction_level",
                "question": "你希望动效强度如何？",
                "choices": ["几乎无动效", "适中动效", "明显动效"],
            },
        ]
        if product_type in {"docs", "dashboard"}:
            questions.append(
                {
                    "id": "readability_priority",
                    "question": "是否把可读性/信息效率放在最高优先级？",
                    "choices": ["是，优先可读性", "平衡", "不是，视觉更重要"],
                }
            )
        return questions

    questions = [
        {
            "id": "visual_intensity",
            "question": "How strong should the visual style be?",
            "choices": ["Calm and clean", "Balanced modern", "Bold and expressive"],
        },
        {
            "id": "content_density",
            "question": "How should blog content be presented?",
            "choices": ["Long-form reading first", "Balanced text and visuals", "Visual-first covers"],
        },
        {
            "id": "interaction_level",
            "question": "How much motion should be used?",
            "choices": ["Minimal motion", "Moderate motion", "Noticeable motion"],
        },
    ]
    if product_type in {"docs", "dashboard"}:
        questions.append(
            {
                "id": "readability_priority",
                "question": "Should readability and information efficiency be the highest priority?",
                "choices": ["Yes", "Balanced", "No, visual impact first"],
            }
        )
    return questions


def build_next_step_templates(style_options: list[dict[str, Any]], query: str, stack: str, zh: bool) -> dict[str, Any]:
    selected = style_options[0]["slug"] if style_options else ""
    if zh:
        return {
            "after_user_selects_style": f'python scripts/run_pipeline.py --workflow codegen --query "{query}" --stack {stack} --style {selected} --blend-mode off --format json',
            "assistant_script": "先展示 3-4 个风格选项并解释差异，用户选择后再进入代码生成。",
        }
    return {
        "after_user_selects_style": f'python scripts/run_pipeline.py --workflow codegen --query "{query}" --stack {stack} --style {selected} --blend-mode off --format json',
        "assistant_script": "Present 3-4 style options with trade-offs, then generate code after user selection.",
    }


def build_cc_conversation_flow(zh: bool) -> dict[str, Any]:
    if zh:
        return {
            "phase_1_opening": {
                "goal": "确认产品目标与用户场景",
                "assistant_template": "我先帮你把方向收敛。你这个产品主要给谁用？核心目标是阅读、转化，还是展示品牌？",
                "expected_user_input": ["产品类型", "目标用户", "主要任务"],
            },
            "phase_2_style_decision": {
                "goal": "给用户可理解的 3-4 个风格选项并解释差异",
                "assistant_template": "我给你 4 个可选风格，每个都附上难度和风险。你选 A/B/C/D，我再按这个风格生成页面。",
                "expected_user_input": ["选项ID", "偏好强度", "是否优先可读性"],
            },
            "phase_3_delivery": {
                "goal": "锁定风格并进入实现",
                "assistant_template": "已锁定风格。我会按该风格输出首页、文章页、列表页，并保持统一视觉语言。",
                "expected_user_input": ["技术栈", "是否深色模式", "是否需要多语言"],
            },
        }

    return {
        "phase_1_opening": {
            "goal": "Clarify product goal and audience context",
            "assistant_template": "Let me narrow the direction first. Who is this for, and is the primary goal reading, conversion, or brand expression?",
            "expected_user_input": ["product type", "target audience", "primary task"],
        },
        "phase_2_style_decision": {
            "goal": "Offer 3-4 understandable style options with trade-offs",
            "assistant_template": "I will give you 4 style options with complexity and risk notes. Pick A/B/C/D, then I will generate with that style.",
            "expected_user_input": ["option id", "visual intensity preference", "readability priority"],
        },
        "phase_3_delivery": {
            "goal": "Lock style and move to implementation",
            "assistant_template": "Style locked. I will generate homepage, post page, and listing page with consistent visual language.",
            "expected_user_input": ["tech stack", "dark mode needed", "multilingual needed"],
        },
    }


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
    zh = is_zh(query)
    product_type = infer_product_type(query)
    style_options = build_style_options(search_payload, product_type=product_type, zh=zh)
    decision_questions = build_decision_questions(product_type=product_type, zh=zh)
    next_step_templates = build_next_step_templates(style_options=style_options, query=query, stack=stack, zh=zh)
    conversation_flow = build_cc_conversation_flow(zh=zh)

    return {
        "purpose": "Use this as a frontend design handbook context before generating code.",
        "product_profile": {
            "query": query,
            "inferred_product_type": product_type,
            "user_confidence": infer_user_confidence(query),
            "stack": stack,
            "purpose": design_intent.get("purpose"),
            "audience": design_intent.get("audience"),
            "tone": design_intent.get("tone"),
        },
        "decision_assistant": {
            "recommended_style_options": style_options,
            "decision_questions": decision_questions,
            "next_step_templates": next_step_templates,
            "cc_conversation_flow": conversation_flow,
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
    decision = manual.get("decision_assistant", {}) or {}
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
    options = decision.get("recommended_style_options", [])[:4]
    if options:
        lines.extend(["", "## Style Options"])
        for option in options:
            lines.append(
                f"- [{option.get('option_id')}] `{option.get('slug')}` / {option.get('nameEn')} - {option.get('complexity')} - {option.get('risk_note')}"
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

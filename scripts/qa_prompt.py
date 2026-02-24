#!/usr/bin/env python3
"""Quality gate for frontend style prompts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from search_stylekit import load_json, normalize_text, tokenize

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
REF_DIR = SKILL_ROOT / "references"
CATALOG_DEFAULT = REF_DIR / "style-prompts.json"

NEGATORS = [
    "don't",
    "do not",
    "must not",
    "never",
    "without",
    "avoid",
    "forbid",
    "forbidden",
    "不要",
    "避免",
    "禁止",
]
GENERIC_FONTS = ["inter", "arial", "roboto", "system-ui", "sans-serif", "helvetica", "ui-sans-serif"]
DISTINCTIVE_FONT_HINTS = [
    "playfair",
    "newsreader",
    "cormorant",
    "fraunces",
    "orbitron",
    "space grotesk",
    "manrope",
    "ibm plex",
    "dm sans",
    "outfit",
    "nunito",
    "思源",
    "霞鹜",
    "站酷",
    "优设",
]

VALIDATION_TEST_WORDS = [
    "swap test",
    "squint test",
    "signature test",
    "token test",
    "替换测试",
    "眯眼测试",
    "签名测试",
    "token 测试",
]

ANTI_PATTERN_WORDS = [
    "absolute positioning",
    "nested scroll",
    "z-index",
    "focus-visible",
    "focus outlines",
    "god component",
    "prop drilling",
    "barrel file",
    "绝对定位",
    "嵌套滚动",
    "焦点样式",
    "god 组件",
]

REFINE_MODE_KEYWORDS = {
    "new": ["new screen", "new flow", "从零", "新页面", "新流程"],
    "polish": ["polish", "refine", "visual quality", "提质", "润色", "优化视觉"],
    "debug": ["debug", "bug", "overflow", "z-index", "clipping", "修复", "溢出", "覆盖", "裁切"],
    "contrast-fix": ["contrast", "wcag", "readability", "4.5:1", "对比度", "可读性", "无障碍"],
    "layout-fix": ["layout", "grid", "flex", "responsive", "spacing", "布局", "网格", "响应式", "间距"],
    "component-fill": ["component", "coverage", "missing", "补齐", "组件覆盖", "缺失组件", "状态补全"],
}

REFERENCE_TYPE_KEYWORDS = {
    "screenshot": ["screenshot", "截图", "screen capture", "视觉参考"],
    "figma": ["figma", "frame", "设计稿", "设计文件"],
    "mixed": ["screenshot", "截图", "figma", "frame", "设计稿", "视觉参考"],
}

RULE_STOPWORDS = {
    "use",
    "using",
    "must",
    "should",
    "ensure",
    "keep",
    "add",
    "set",
    "avoid",
    "do",
    "not",
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "your",
    "you",
    "to",
    "in",
    "on",
    "of",
    "at",
    "by",
    "as",
    "be",
    "is",
    "are",
    "使用",
    "添加",
    "加入",
    "保持",
    "确保",
    "避免",
    "禁止",
    "不要",
    "需要",
    "并",
    "和",
    "与",
    "在",
    "到",
    "及",
    "或",
}
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _extract_from_json_obj(obj: Any, preferred_field: str) -> tuple[str | None, str | None]:
    if isinstance(obj, dict):
        # 1) exact preferred field on current level
        value = obj.get(preferred_field)
        if isinstance(value, str) and value.strip():
            return value, preferred_field

        # 2) common prompt fields
        for field in ("hard_prompt", "soft_prompt", "prompt", "text"):
            value = obj.get(field)
            if isinstance(value, str) and value.strip():
                return value, field

        # 3) nested search
        for key, val in obj.items():
            found, src = _extract_from_json_obj(val, preferred_field)
            if found:
                return found, f"{key}.{src}" if src else key

    if isinstance(obj, list):
        for idx, item in enumerate(obj):
            found, src = _extract_from_json_obj(item, preferred_field)
            if found:
                return found, f"[{idx}].{src}" if src else f"[{idx}]"

    return None, None


def read_prompt_text(input_path: str | None, inline_text: str | None, prompt_field: str) -> tuple[str, dict[str, Any]]:
    meta: dict[str, Any] = {"source_kind": "text", "source_field": None}

    if inline_text:
        stripped = inline_text.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                obj = json.loads(stripped)
                extracted, source_field = _extract_from_json_obj(obj, prompt_field)
                if extracted:
                    meta["source_kind"] = "json"
                    meta["source_field"] = source_field
                    return extracted, meta
            except json.JSONDecodeError:
                pass
        return inline_text, meta

    if input_path:
        with Path(input_path).open("r", encoding="utf-8") as f:
            content = f.read()
        stripped = content.strip()
        if stripped.startswith("{") or stripped.startswith("[") or input_path.endswith(".json"):
            try:
                obj = json.loads(content)
                extracted, source_field = _extract_from_json_obj(obj, prompt_field)
                if extracted:
                    meta["source_kind"] = "json"
                    meta["source_field"] = source_field
                    return extracted, meta
            except json.JSONDecodeError:
                # fall through to plain text
                pass
        return content, meta

    raise SystemExit("Provide --input <file> or --text <prompt>")


def extract_bullet_rules(text: str) -> list[str]:
    rules = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.match(r"^[-*]\s+", line) or re.match(r"^\d+\.\s+", line):
            line = re.sub(r"^[-*]\s+", "", line)
            line = re.sub(r"^\d+\.\s+", "", line)
            if len(line) >= 8:
                rules.append(line)
    return rules


def contains_any(text: str, words: list[str]) -> list[str]:
    hit = []
    lower = text.lower()
    for word in words:
        if word in lower:
            hit.append(word)
    return hit


def contains_any_positive(text: str, words: list[str], window: int = 40) -> list[str]:
    """Return hits that are not in obvious negated context."""
    hits = []
    lower = text.lower()
    for word in words:
        start = 0
        found_positive = False
        while True:
            idx = lower.find(word, start)
            if idx < 0:
                break
            prefix = lower[max(0, idx - window):idx]
            if not any(neg in prefix for neg in NEGATORS):
                found_positive = True
                break
            start = idx + len(word)
        if found_positive:
            hits.append(word)
    return hits


def has_cjk(text: str) -> bool:
    return bool(CJK_RE.search(text or ""))


def infer_expected_lang(text: str, expected_lang: str | None) -> str:
    if expected_lang in {"en", "zh"}:
        return expected_lang
    return "zh" if has_cjk(text) else "en"


def rule_polarity(rule: str) -> str:
    low = rule.lower()
    return "neg" if any(neg in low for neg in NEGATORS) else "pos"


def conflict_token_set(rule: str) -> set[str]:
    tokens = tokenize(rule)
    ignored = RULE_STOPWORDS | set(NEGATORS) | {"not", "no", "without", "non", "无", "非", "不"}
    return {tok for tok in tokens if len(tok) > 1 and tok not in ignored}


def rules_conflict(rule_a: str, rule_b: str) -> bool:
    if rule_polarity(rule_a) == rule_polarity(rule_b):
        return False
    a_tokens = conflict_token_set(rule_a)
    b_tokens = conflict_token_set(rule_b)
    if not a_tokens or not b_tokens:
        return False
    overlap = a_tokens & b_tokens
    if len(overlap) < 2:
        return False
    smaller = min(len(a_tokens), len(b_tokens))
    larger = max(len(a_tokens), len(b_tokens))
    overlap_small = len(overlap) / max(smaller, 1)
    overlap_large = len(overlap) / max(larger, 1)
    return overlap_small >= 0.75 and overlap_large >= 0.5


def positive_mention(text: str, phrase: str) -> bool:
    if any(neg in phrase for neg in NEGATORS):
        return False
    idx = text.find(phrase)
    if idx < 0:
        return False
    start = max(0, idx - 24)
    prefix = text[start:idx]
    return not any(neg in prefix for neg in NEGATORS)


def find_style(catalog: dict[str, Any], slug: str | None) -> dict[str, Any] | None:
    if not slug:
        return None
    for style in catalog.get("styles", []):
        if style.get("slug") == slug:
            return style
    raise SystemExit(f"Style slug not found in catalog: {slug}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit and gate prompt quality")
    parser.add_argument("--input", help="Prompt file path")
    parser.add_argument("--text", help="Inline prompt text")
    parser.add_argument("--prompt-field", default="hard_prompt", help="Preferred JSON field when input is a JSON object")
    parser.add_argument("--lang", choices=["en", "zh"], help="Expected prompt language (en/zh). If omitted, inferred from text.")
    parser.add_argument(
        "--require-refine-mode",
        choices=["new", "polish", "debug", "contrast-fix", "layout-fix", "component-fill"],
        help="Optional required refine mode to validate against prompt intent.",
    )
    parser.add_argument(
        "--require-reference-type",
        choices=["none", "screenshot", "figma", "mixed"],
        help="Optional required input reference type to validate prompt guidance.",
    )
    parser.add_argument(
        "--require-reference-signals",
        action="store_true",
        help="Require explicit reference signal extraction block when reference payload exists.",
    )
    parser.add_argument("--style", help="Style slug for identity checks")
    parser.add_argument("--catalog", default=str(CATALOG_DEFAULT))
    parser.add_argument("--min-ai-rules", type=int, default=3)
    args = parser.parse_args()

    text, source_meta = read_prompt_text(args.input, args.text, args.prompt_field)
    normalized = normalize_text(text)
    checks = []

    # 1) Non-empty prompt
    checks.append(
        {
            "id": "non_empty",
            "severity": "high",
            "passed": bool(normalized),
            "message": "Prompt text must not be empty.",
            "details": {},
        }
    )

    # 2) Minimum actionable rules
    bullet_rules = extract_bullet_rules(text)
    checks.append(
        {
            "id": "min_actionable_rules",
            "severity": "high",
            "passed": len(bullet_rules) >= args.min_ai_rules,
            "message": f"Prompt should contain at least {args.min_ai_rules} actionable bullet rules.",
            "details": {"found": len(bullet_rules)},
        }
    )

    # 2.1) Rule conflict guard (hard check)
    rule_conflicts_found = []
    for i in range(len(bullet_rules)):
        for j in range(i + 1, len(bullet_rules)):
            if rules_conflict(bullet_rules[i], bullet_rules[j]):
                overlap = sorted(conflict_token_set(bullet_rules[i]) & conflict_token_set(bullet_rules[j]))
                rule_conflicts_found.append(
                    {
                        "rule_a": bullet_rules[i],
                        "rule_b": bullet_rules[j],
                        "overlap": overlap[:6],
                    }
                )

    checks.append(
        {
            "id": "rule_conflict",
            "severity": "high",
            "passed": len(rule_conflicts_found) == 0,
            "message": "Prompt rules should not contain contradictory constraints.",
            "details": {"conflicts": rule_conflicts_found[:6]},
        }
    )

    # 2.2) Language consistency (hard check)
    expected_lang = infer_expected_lang(text, args.lang)
    cjk_count = len(CJK_RE.findall(text))
    ascii_word_count = len(re.findall(r"[a-zA-Z]{2,}", text))
    if expected_lang == "en":
        lang_passed = cjk_count == 0
    else:
        lang_passed = cjk_count >= 8

    checks.append(
        {
            "id": "language_consistency",
            "severity": "high",
            "passed": lang_passed,
            "message": "Prompt language should remain consistent with requested language.",
            "details": {
                "expected_lang": expected_lang,
                "cjk_count": cjk_count,
                "ascii_word_count": ascii_word_count,
            },
        }
    )

    # 3) Component coverage
    lower = text.lower()
    core_components = ["button", "card", "input"]
    secondary_components = ["nav", "hero", "footer", "导航", "首屏", "页脚"]
    core_hits = [c for c in core_components if c in lower]
    secondary_hits = [c for c in secondary_components if c in lower]

    checks.append(
        {
            "id": "component_coverage",
            "severity": "medium",
            "passed": len(core_hits) == len(core_components) and len(secondary_hits) >= 2,
            "message": "Prompt should cover button/card/input and at least two of nav/hero/footer.",
            "details": {"core_hits": core_hits, "secondary_hits": secondary_hits},
        }
    )

    # 4) Interaction and accessibility baseline
    interaction_words = ["hover", "active", "focus", "transition", "motion", "animation", "悬停", "点击", "焦点", "动画"]
    accessibility_words = ["contrast", "keyboard", "aria", "screen reader", "wcag", "reduced-motion", "对比度", "键盘", "可访问", "无障碍"]

    interaction_hits = contains_any(lower, interaction_words)
    accessibility_hits = contains_any(lower, accessibility_words)

    checks.append(
        {
            "id": "interaction_accessibility",
            "severity": "medium",
            "passed": len(interaction_hits) >= 2 and len(accessibility_hits) >= 1,
            "message": "Prompt should include interaction states and accessibility constraints.",
            "details": {
                "interaction_hits": interaction_hits,
                "accessibility_hits": accessibility_hits,
            },
        }
    )

    # 4.1) WCAG + touch target baseline
    wcag_touch_hits = contains_any(
        lower,
        [
            "wcag",
            "4.5:1",
            "contrast ratio",
            "44x44",
            "44 x 44",
            "24x24",
            "touch target",
            "target size",
            "对比度",
            "触控",
            "触摸目标",
            "44x44px",
        ],
    )

    checks.append(
        {
            "id": "wcag_touch_baseline",
            "severity": "medium",
            "passed": len(wcag_touch_hits) >= 2,
            "message": "Prompt should include WCAG contrast and touch target constraints.",
            "details": {"hits": wcag_touch_hits},
        }
    )

    # 4.2) Distinctive typography direction
    generic_font_hits = contains_any_positive(lower, GENERIC_FONTS)
    distinctive_font_hits = contains_any(lower, DISTINCTIVE_FONT_HINTS)
    has_font_strategy_words = len(contains_any(lower, ["font", "typography", "字体", "排版"])) > 0

    checks.append(
        {
            "id": "typography_distinctiveness",
            "severity": "medium",
            "passed": (len(distinctive_font_hits) >= 1) or (has_font_strategy_words and len(generic_font_hits) <= 1),
            "message": "Prompt should include a distinctive typography strategy, not only generic default fonts.",
            "details": {
                "generic_font_hits": generic_font_hits,
                "distinctive_font_hits": distinctive_font_hits,
                "has_font_strategy_words": has_font_strategy_words,
            },
        }
    )

    # 4.3) Design token/system structure mention
    token_hits = contains_any(
        lower,
        [
            "token",
            "semantic token",
            "design token",
            "variant",
            "state",
            "primary",
            "secondary",
            "spacing scale",
            "radius",
            "语义 token",
            "设计 token",
            "变体",
            "状态",
            "间距尺度",
            "圆角",
        ],
    )
    checks.append(
        {
            "id": "design_system_structure",
            "severity": "medium",
            "passed": len(token_hits) >= 3,
            "message": "Prompt should mention design token or component architecture constraints.",
            "details": {"token_hits": token_hits},
        }
    )

    # 4.4) Intent-validation tests (swap/squint/signature/token)
    validation_hits = contains_any(lower, VALIDATION_TEST_WORDS)
    checks.append(
        {
            "id": "intent_validation_tests",
            "severity": "medium",
            "passed": len(validation_hits) >= 2,
            "message": "Prompt should include validation tests (swap/squint/signature/token) to prevent generic output.",
            "details": {"validation_hits": validation_hits},
        }
    )

    # 4.5) Anti-pattern blacklist mention with negation context
    anti_pattern_hits = contains_any(lower, ANTI_PATTERN_WORDS)
    negator_hits = contains_any(lower, NEGATORS)
    checks.append(
        {
            "id": "anti_pattern_guard",
            "severity": "medium",
            "passed": len(anti_pattern_hits) >= 2 and len(negator_hits) >= 1,
            "message": "Prompt should explicitly forbid major frontend anti-patterns.",
            "details": {"anti_pattern_hits": anti_pattern_hits, "negator_hits": negator_hits},
        }
    )

    # 4.6) Refinement mode alignment (optional requirement)
    refine_mode = args.require_refine_mode
    if refine_mode:
        refine_keywords = REFINE_MODE_KEYWORDS.get(refine_mode, [])
        refine_hits = contains_any(lower, refine_keywords)
        mode_marker_hits = contains_any(lower, ["refinement mode", "iteration mode", "迭代模式", "本轮目标", "objective"])
        required_hit_floor = 1 if refine_mode in {"new", "polish"} else 2
        checks.append(
            {
                "id": "refinement_mode_alignment",
                "severity": "medium",
                "passed": len(refine_hits) >= required_hit_floor and len(mode_marker_hits) >= 1,
                "message": "Prompt should align with required refinement mode intent.",
                "details": {
                    "required_mode": refine_mode,
                    "required_hit_floor": required_hit_floor,
                    "refine_hits": refine_hits,
                    "mode_marker_hits": mode_marker_hits,
                },
            }
        )

    # 4.7) Reference input handling (optional requirement)
    reference_type = args.require_reference_type
    if reference_type:
        if reference_type == "none":
            ref_passed = True
            ref_hits = []
            handling_hits = []
        else:
            ref_keywords = REFERENCE_TYPE_KEYWORDS.get(reference_type, [])
            ref_hits = contains_any(lower, ref_keywords)
            handling_hits = contains_any(
                lower,
                [
                    "layout",
                    "spacing",
                    "hierarchy",
                    "semantic",
                    "token",
                    "component",
                    "behavior",
                    "state",
                    "布局",
                    "间距",
                    "层级",
                    "语义",
                    "组件",
                    "状态",
                    "交互",
                ],
            )
            ref_passed = len(ref_hits) >= 1 and len(handling_hits) >= 2

        checks.append(
            {
                "id": "reference_context_guard",
                "severity": "medium",
                "passed": ref_passed,
                "message": "Prompt should include clear handling guidance for the required reference input type.",
                "details": {
                    "required_reference_type": reference_type,
                    "reference_hits": ref_hits,
                    "handling_hits": handling_hits,
                },
            }
        )

    # 4.8) Reference signal extraction block (optional requirement)
    if args.require_reference_signals:
        signal_block_hits = contains_any(
            lower,
            [
                "参考信号提取",
                "reference signal extraction",
                "布局问题",
                "缺失组件",
                "保留要素",
                "交互缺口",
                "可访问性缺口",
                "layout issues",
                "missing components",
                "preserve elements",
                "interaction gaps",
                "accessibility gaps",
            ],
        )
        checks.append(
            {
                "id": "reference_signal_alignment",
                "severity": "medium",
                "passed": len(signal_block_hits) >= 3,
                "message": "Prompt should include explicit extracted signals from reference input.",
                "details": {"signal_block_hits": signal_block_hits},
            }
        )

    # 5) Style identity and conflict checks (optional)
    catalog_path = Path(args.catalog)
    style_data = None
    if catalog_path.exists() and args.style:
        catalog = load_json(catalog_path)
        style_data = find_style(catalog, args.style)

    if style_data:
        prompt_tokens = set(tokenize(text))
        style_tokens = set(tokenize(" ".join(style_data.get("keywords", []) + style_data.get("tags", []))))
        overlap = sorted(prompt_tokens & style_tokens)

        checks.append(
            {
                "id": "style_identity_match",
                "severity": "high",
                "passed": len(overlap) >= 1,
                "message": "Prompt should contain at least one keyword/tag aligned with the target style.",
                "details": {"overlap": overlap[:10]},
            }
        )

        possible_conflicts = []
        norm_text = text.lower()
        for rule in style_data.get("dontList", [])[:20]:
            target = rule.lower().strip()
            if len(target) < 6:
                continue
            if target in norm_text and positive_mention(norm_text, target):
                possible_conflicts.append(rule)

        checks.append(
            {
                "id": "dont_conflict",
                "severity": "medium",
                "passed": len(possible_conflicts) == 0,
                "message": "Prompt should not positively reintroduce style don't-rules.",
                "details": {"conflicts": possible_conflicts[:8]},
            }
        )

    failed = [c for c in checks if not c["passed"]]
    high_failed = [c for c in failed if c["severity"] == "high"]
    medium_failed = [c for c in failed if c["severity"] == "medium"]

    status = "pass"
    if high_failed or len(medium_failed) >= 2:
        status = "fail"

    suggestions = []
    for item in failed:
        if item["id"] == "min_actionable_rules":
            suggestions.append("Add explicit bullet rules with imperative verbs (e.g. Use, Avoid, Ensure).")
        elif item["id"] == "rule_conflict":
            suggestions.append("Remove contradictory rules and keep one source-of-truth per constraint domain.")
        elif item["id"] == "language_consistency":
            suggestions.append("Keep output in one language; remove mixed-language rules or translate them consistently.")
        elif item["id"] == "component_coverage":
            suggestions.append("Add component-level constraints for button/card/input and include nav/hero/footer guidance.")
        elif item["id"] == "interaction_accessibility":
            suggestions.append("Add hover/active/focus-visible states and at least one accessibility rule (contrast or keyboard support).")
        elif item["id"] == "wcag_touch_baseline":
            suggestions.append("Add WCAG contrast target (e.g. 4.5:1) and touch target constraints (e.g. 44x44px).")
        elif item["id"] == "typography_distinctiveness":
            suggestions.append("Specify a non-generic typography direction and avoid relying only on Inter/Arial/Roboto/system-ui.")
        elif item["id"] == "design_system_structure":
            suggestions.append("Add design-token and component-architecture constraints (tokens, variants, states, spacing/radius scale).")
        elif item["id"] == "intent_validation_tests":
            suggestions.append("Add swap/squint/signature/token validation tests before delivery to reduce generic output.")
        elif item["id"] == "anti_pattern_guard":
            suggestions.append("Explicitly forbid anti-patterns such as absolute page layout, nested scroll, z-index wars, and missing focus styles.")
        elif item["id"] == "refinement_mode_alignment":
            suggestions.append("Align prompt goals and constraints with the requested refine mode (e.g. debug/layout-fix/contrast-fix) and include mode markers.")
        elif item["id"] == "reference_context_guard":
            suggestions.append("Add explicit screenshot/Figma handling rules (layout/token/state extraction + semantic component mapping).")
        elif item["id"] == "reference_signal_alignment":
            suggestions.append("Include a reference signal extraction section with layout issues, missing components, preserved elements, and interaction/a11y gaps.")
        elif item["id"] == "style_identity_match":
            suggestions.append("Inject target style keywords/tags directly into prompt constraints.")
        elif item["id"] == "dont_conflict":
            suggestions.append("Remove or negate instructions that conflict with the style dontList.")
        elif item["id"] == "non_empty":
            suggestions.append("Provide non-empty prompt content before audit.")

    payload = {
        "status": status,
        "checks": checks,
        "violations": failed,
        "autofix_suggestions": suggestions,
        "meta": {
            "style": args.style,
            "expected_lang": infer_expected_lang(text, args.lang),
            "min_ai_rules": args.min_ai_rules,
            "prompt_length": len(text),
            "source_kind": source_meta.get("source_kind"),
            "source_field": source_meta.get("source_field"),
            "prompt_field_preferred": args.prompt_field,
            "required_refine_mode": args.require_refine_mode,
            "required_reference_type": args.require_reference_type,
            "require_reference_signals": args.require_reference_signals,
        },
    }

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

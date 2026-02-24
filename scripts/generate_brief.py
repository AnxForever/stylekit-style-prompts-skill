#!/usr/bin/env python3
"""Generate design brief + hard/soft prompts from StyleKit catalog."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from search_stylekit import BM25, build_text, expand_query_tokens, heuristic_score, load_json, tokenize

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
REF_DIR = SKILL_ROOT / "references"
CATALOG_DEFAULT = REF_DIR / "style-prompts.json"

STACK_HINTS = {
    "html-tailwind": {
        "en": "Use semantic HTML and Tailwind utility classes. Keep components reusable and avoid inline style except dynamic variables.",
        "zh": "使用语义化 HTML 与 Tailwind 工具类，组件可复用，除动态变量外避免内联样式。",
    },
    "react": {
        "en": "Build reusable React components, stable keys, and accessible interaction states. Keep state minimal and localized.",
        "zh": "构建可复用 React 组件，保证稳定 key 与可访问交互状态，状态最小化并局部化。",
    },
    "nextjs": {
        "en": "Prefer Server Components by default, add Client Components only for interactivity, and keep bundle weight low.",
        "zh": "默认优先 Server Components，仅在交互需要时使用 Client Components，并控制包体积。",
    },
    "vue": {
        "en": "Use composables for shared logic, keep templates readable, and map style constraints into scoped utility patterns.",
        "zh": "复用逻辑放入 composables，模板保持可读，把风格约束映射为稳定的样式模式。",
    },
    "svelte": {
        "en": "Keep component boundaries clear, use transitions intentionally, and avoid over-animating layout-critical areas.",
        "zh": "组件边界保持清晰，过渡动画有目的地使用，避免关键布局区域过度动画。",
    },
    "tailwind-v4": {
        "en": "Use Tailwind v4 CSS-first setup with @theme/@utility/@custom-variant, prefer semantic tokens and OKLCH palette where possible.",
        "zh": "使用 Tailwind v4 的 CSS-first 方案（@theme/@utility/@custom-variant），优先语义 token 与 OKLCH 色彩体系。",
    },
}

REFERENCE_TYPES = ("none", "screenshot", "figma", "mixed")

REFINE_MODE_HINTS = {
    "new": {
        "en": {
            "objective": "Create a new screen or flow with a complete style-aligned structure.",
            "constraints": [
                "Prioritize coherent information architecture before decorative details.",
                "Ensure full interaction coverage (hover/active/focus-visible/disabled).",
                "Deliver complete responsive behavior for core breakpoints.",
            ],
        },
        "zh": {
            "objective": "从零创建新页面/新流程，输出完整且风格一致的结构。",
            "constraints": [
                "先保证信息架构完整，再补充装饰性细节。",
                "交互状态需覆盖 hover/active/focus-visible/disabled。",
                "核心断点下都要保证完整响应式表现。",
            ],
        },
    },
    "polish": {
        "en": {
            "objective": "Polish visual quality while preserving existing structure and functionality.",
            "constraints": [
                "Do not rewrite the page architecture unless required by clear defects.",
                "Keep content hierarchy and user flow stable.",
                "Improve typography, spacing rhythm, and visual consistency first.",
            ],
        },
        "zh": {
            "objective": "在保留现有结构与功能的前提下进行视觉提质。",
            "constraints": [
                "除明显缺陷外，不重写页面架构。",
                "保持内容层级与用户流程稳定。",
                "优先优化排版、间距节奏和视觉一致性。",
            ],
        },
    },
    "debug": {
        "en": {
            "objective": "Fix rendering and interaction defects without regressing style identity.",
            "constraints": [
                "Focus on overflow, clipping, z-index overlap, and state regressions.",
                "Keep style DNA intact while fixing bugs.",
                "Provide minimal-change remediation over full rewrites.",
            ],
        },
        "zh": {
            "objective": "修复渲染与交互缺陷，同时保持原有风格识别度。",
            "constraints": [
                "重点处理溢出、裁切、z-index 覆盖和状态回归问题。",
                "修 bug 时保持风格 DNA 不被破坏。",
                "优先最小改动修复，避免整体重写。",
            ],
        },
    },
    "contrast-fix": {
        "en": {
            "objective": "Repair contrast and readability issues to meet accessibility baseline.",
            "constraints": [
                "Enforce WCAG AA contrast targets for text and key UI states.",
                "Preserve brand palette intent while adjusting tonal steps.",
                "Avoid introducing visual noise during contrast correction.",
            ],
        },
        "zh": {
            "objective": "修复对比度与可读性问题，使其满足无障碍基线。",
            "constraints": [
                "正文与关键交互态满足 WCAG AA 对比度目标。",
                "在不破坏品牌色语义的前提下调整明度层级。",
                "修正对比度时避免引入额外视觉噪声。",
            ],
        },
    },
    "layout-fix": {
        "en": {
            "objective": "Repair layout structure and responsive behavior without changing style direction.",
            "constraints": [
                "Fix grid/flex alignment, spacing collisions, and viewport overflow.",
                "Preserve component semantics while rebalancing layout rhythm.",
                "Validate desktop/tablet/mobile structure after fixes.",
            ],
        },
        "zh": {
            "objective": "修复布局结构与响应式问题，不改变既有风格方向。",
            "constraints": [
                "修复 grid/flex 对齐、间距冲突和视口溢出问题。",
                "在重整布局节奏时保持组件语义稳定。",
                "修复后验证桌面/平板/移动端结构一致性。",
            ],
        },
    },
    "component-fill": {
        "en": {
            "objective": "Complete missing components and states to reach production readiness.",
            "constraints": [
                "Fill missing core components before adding new visual flourishes.",
                "Ensure every new component has interaction and accessibility states.",
                "Match token scale and naming with existing design system conventions.",
            ],
        },
        "zh": {
            "objective": "补齐缺失组件与状态，提升到可交付质量。",
            "constraints": [
                "先补齐核心组件，再考虑额外视觉特效。",
                "新增组件必须包含交互态与可访问状态。",
                "严格对齐现有 design token 的尺度与命名约定。",
            ],
        },
    },
}

REFERENCE_GUIDELINES = {
    "screenshot": {
        "en": [
            "Treat screenshot as visual reference for layout, spacing, and hierarchy.",
            "Replicate structure first, then adapt to semantic HTML/component architecture.",
            "Infer missing behavior explicitly (hover/focus/loading/error) instead of guessing silently.",
        ],
        "zh": [
            "将截图作为布局、间距和层级的视觉参考来源。",
            "先对齐结构，再映射到语义化 HTML/组件架构。",
            "对缺失交互（hover/focus/loading/error）需显式补全，不可隐式猜测。",
        ],
    },
    "figma": {
        "en": [
            "Use Figma frame structure and token cues (color/spacing/type) as implementation baseline.",
            "Break complex frames into reusable components before assembling full page.",
            "Keep naming and token semantics consistent between design and code.",
        ],
        "zh": [
            "以 Figma 的 Frame 结构与 token 线索（色彩/间距/字体）作为实现基线。",
            "复杂 Frame 先拆成可复用组件，再组装整页。",
            "保持设计稿与代码中的命名和 token 语义一致。",
        ],
    },
}

REFERENCE_FIELD_ALIASES = {
    "layout_issues": ["layout_issues", "layoutIssues", "layoutProblems", "layout_issues_list", "issues"],
    "missing_components": ["missing_components", "missingComponents", "component_gaps", "components_missing"],
    "preserve_elements": ["preserve_elements", "preserveElements", "preserve", "keep", "must_keep"],
    "interaction_gaps": ["interaction_gaps", "interactionGaps", "state_gaps", "states_missing"],
    "a11y_gaps": ["a11y_gaps", "accessibility_gaps", "accessibilityGaps", "wcag_gaps"],
    "token_clues": ["token_clues", "tokenClues", "design_tokens", "tokens", "style_tokens"],
    "notes": ["notes", "note", "summary", "description", "context"],
}

REFERENCE_SECTION_KEYS = ("layout", "components", "interaction", "accessibility", "tokens")
REFERENCE_META_KEYS = ("source", "type", "notes", "metadata", "frame", "frames", "screen", "screens", "page")
REFERENCE_KNOWN_TOP_LEVEL = set(REFERENCE_SECTION_KEYS) | set(REFERENCE_META_KEYS)
for alias_items in REFERENCE_FIELD_ALIASES.values():
    REFERENCE_KNOWN_TOP_LEVEL.update(alias_items)

A11Y_BASELINE = {
    "en": [
        "Text contrast meets WCAG 2.1 AA (4.5:1 for normal text).",
        "Keyboard focus is visible on all interactive controls.",
        "Interactive targets are at least 44x44px on touch devices.",
        "Respect prefers-reduced-motion for non-essential animation.",
    ],
    "zh": [
        "文本对比度满足 WCAG 2.1 AA（正文至少 4.5:1）。",
        "所有可交互控件具备可见的键盘焦点状态。",
        "触屏场景下交互目标至少 44x44px。",
        "非必要动画需遵循 prefers-reduced-motion。",
    ],
}

NEGATOR_WORDS = ["avoid", "don't", "do not", "禁止", "不要", "避免", "严禁"]
NEG_SECTION_MARKERS = [
    "绝对禁止",
    "禁止使用",
    "禁止",
    "must avoid",
    "must not",
    "forbidden",
    "absolutely forbidden",
    "do not",
]
POS_SECTION_MARKERS = [
    "必须遵守",
    "必须使用",
    "必须",
    "must follow",
    "must use",
    "required",
]
RADIUS_TOKEN_RE = re.compile(r"\brounded(?:-[a-z0-9]+)?\b", re.IGNORECASE)
SHADOW_TOKEN_RE = re.compile(r"\bshadow(?:-[a-z0-9\[\]_/.-]+)?\b", re.IGNORECASE)
BG_WHITE_TOKEN_RE = re.compile(r"\bbg-white(?:/[0-9]{1,3})?\b", re.IGNORECASE)
BG_BLACK_TOKEN_RE = re.compile(r"\bbg-black(?:/[0-9]{1,3})?\b", re.IGNORECASE)
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
    "use",
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

GENERIC_FONTS = ["inter", "arial", "roboto", "system-ui", "sans-serif"]
CJK_RE = re.compile(r"[\u4e00-\u9fff]")

DISTINCTIVE_FONT_HINTS = {
    "en": [
        "Pair one display font with one readable body font.",
        "Avoid overusing generic defaults (Inter/Roboto/Arial/system-ui).",
        "Use typography contrast (size, weight, spacing) to lead hierarchy.",
    ],
    "zh": [
        "标题字体与正文字体形成明显对比并保持统一。",
        "避免过度依赖通用默认字体（Inter/Roboto/Arial/system-ui）。",
        "通过字号、字重、字距建立清晰层级。",
    ],
}

VALIDATION_TESTS = {
    "en": [
        "Swap test: replace key visual choices with common defaults; if identity stays unchanged, redesign.",
        "Squint test: hierarchy should remain clear when blurred or zoomed out.",
        "Signature test: point to at least 3 concrete UI elements carrying the style signature.",
        "Token test: token names and values should reflect product intent, not generic templates.",
    ],
    "zh": [
        "替换测试（Swap test）：把关键视觉选择替换为常见默认值，若辨识度不变则需要重做。",
        "眯眼测试（Squint test）：弱化细节后，信息层级仍然清晰可辨。",
        "签名测试（Signature test）：至少指出 3 个承载风格签名的具体界面元素。",
        "Token 测试（Token test）：设计 token 命名与取值要体现产品语义，避免模板化。",
    ],
}

ANTI_PATTERN_BLACKLIST = {
    "en": [
        "Do not build full-page layout with absolute positioning; use flex/grid structure.",
        "Do not create nested scroll containers or uncontrolled z-index wars.",
        "Do not remove focus outlines without an explicit focus-visible replacement.",
        "Do not submit forms without loading/disabled states and recovery-friendly errors.",
        "Avoid god components (>300 lines) and deep prop drilling beyond two levels.",
    ],
    "zh": [
        "禁止用 absolute 定位搭整页布局，优先 flex/grid 结构。",
        "禁止嵌套滚动容器与失控的 z-index 叠层竞争。",
        "禁止移除焦点样式且不提供 focus-visible 替代方案。",
        "禁止表单提交缺少 loading/disabled 状态与可恢复错误提示。",
        "避免 God 组件（超过 300 行）和超过两层 prop drilling。",
    ],
}

DEFAULT_AI_RULES = {
    "en": [
        "Keep clear hierarchy across heading, body, and metadata layers.",
        "Implement explicit hover, active, focus-visible, and disabled states.",
        "Maintain WCAG AA contrast and 44x44px touch-target baseline.",
        "Use semantic design tokens and consistent spacing/radius scales.",
    ],
    "zh": [
        "保持标题、正文、元信息的清晰层级。",
        "交互态必须覆盖 hover、active、focus-visible 与 disabled。",
        "满足 WCAG AA 对比度并保证 44x44px 触控尺寸基线。",
        "使用语义化 design token，并保持统一间距与圆角尺度。",
    ],
}

DEFAULT_DO_LIST = {
    "en": [
        "Use semantic layout and preserve strong information hierarchy.",
        "Provide visible interaction states and keyboard focus.",
        "Keep typography and spacing rhythm consistent across breakpoints.",
    ],
    "zh": [
        "使用语义化布局并保持明确的信息层级。",
        "提供可见交互状态与键盘焦点反馈。",
        "在各断点保持一致的排版与间距节奏。",
    ],
}

DEFAULT_DONT_LIST = {
    "en": [
        "Do not sacrifice readability for decorative effects.",
        "Do not remove focus styles without a visible replacement.",
        "Do not break responsive structure with rigid fixed-width layout.",
    ],
    "zh": [
        "禁止为了装饰效果牺牲可读性。",
        "禁止移除焦点样式且不提供可见替代。",
        "禁止用僵硬固定宽度破坏响应式结构。",
    ],
}


def detect_lang(text: str) -> str:
    return "zh" if re.search(r"[\u4e00-\u9fff]", text) else "en"


def has_cjk(text: str) -> bool:
    return bool(CJK_RE.search(text or ""))


def section_polarity_from_heading(line: str) -> str | None:
    text = str(line or "").strip()
    if not text:
        return None
    if not text.startswith("#"):
        return None

    normalized = re.sub(r"^[#\s]+", "", text).lower()
    if any(marker in normalized for marker in NEG_SECTION_MARKERS):
        return "neg"
    if any(marker in normalized for marker in POS_SECTION_MARKERS):
        return "pos"
    return None


def to_negative_rule(rule: str, lang: str) -> str:
    text = str(rule or "").strip()
    if not text:
        return text
    if any(word in text.lower() for word in NEGATOR_WORDS):
        return text
    if lang == "zh":
        return f"禁止{text}"
    if text[0].isupper():
        return f"Do not {text[0].lower()}{text[1:]}"
    return f"Do not {text}"


def extract_utility_signatures(rule: str) -> dict[str, set[str]]:
    low = str(rule or "").lower()
    signatures: dict[str, set[str]] = {}

    for token in RADIUS_TOKEN_RE.findall(low):
        value = token.split("-", 1)[1] if "-" in token else "base"
        signatures.setdefault("radius", set()).add(value)

    for token in SHADOW_TOKEN_RE.findall(low):
        value = token.split("-", 1)[1] if "-" in token else "base"
        signatures.setdefault("shadow", set()).add(value)

    for token in BG_WHITE_TOKEN_RE.findall(low):
        value = "translucent" if "/" in token else "opaque"
        signatures.setdefault("bg-white", set()).add(value)

    for token in BG_BLACK_TOKEN_RE.findall(low):
        value = "translucent" if "/" in token else "opaque"
        signatures.setdefault("bg-black", set()).add(value)

    return signatures


def utility_family_conflicts(values_a: set[str], values_b: set[str], family: str) -> bool:
    # Opposite polarity is required by caller; treat only same-value collisions as conflicts.
    # This allows valid pairs like "禁止 rounded-none" + "使用 rounded-xl".
    return bool(values_a & values_b)


def utility_rules_conflict(rule_a: str, rule_b: str) -> bool:
    signatures_a = extract_utility_signatures(rule_a)
    signatures_b = extract_utility_signatures(rule_b)
    for family in signatures_a.keys() & signatures_b.keys():
        if utility_family_conflicts(signatures_a[family], signatures_b[family], family):
            return True
    return False


def has_internal_family_conflict(values: set[str], family: str) -> bool:
    if family in {"radius", "shadow"}:
        return "none" in values and any(v != "none" for v in values)
    if family in {"bg-white", "bg-black"}:
        return "opaque" in values and "translucent" in values
    return False


def has_internal_utility_conflict(rule: str) -> bool:
    signatures = extract_utility_signatures(rule)
    for family, values in signatures.items():
        if has_internal_family_conflict(values, family):
            return True
    return False


def rewrite_ambiguous_positive_rule(rule: str, lang: str) -> str:
    if is_negative_rule(rule):
        return rule
    signatures = extract_utility_signatures(rule)
    radius_values = signatures.get("radius", set())
    shadow_values = signatures.get("shadow", set())
    bg_white_values = signatures.get("bg-white", set())
    bg_black_values = signatures.get("bg-black", set())

    if has_internal_family_conflict(radius_values, "radius"):
        return (
            "圆角策略保持一致，禁止在同一界面混用直角和大圆角。"
            if lang == "zh"
            else "Keep one consistent corner strategy; do not mix sharp and rounded corners in the same screen."
        )
    if has_internal_family_conflict(shadow_values, "shadow"):
        return (
            "阴影策略保持一致，避免同时要求无阴影和重阴影。"
            if lang == "zh"
            else "Keep one consistent shadow strategy; avoid mixing no-shadow and heavy-shadow directives."
        )
    if has_internal_family_conflict(bg_white_values, "bg-white") or has_internal_family_conflict(
        bg_black_values, "bg-black"
    ):
        return (
            "背景不透明度策略保持一致，避免同时要求纯色不透明与半透明。"
            if lang == "zh"
            else "Keep background opacity strategy consistent; avoid mixing opaque and translucent directives."
        )
    return rule


def dedupe_ordered(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item.strip())
    return out


def language_filter_rules(rules: list[str], lang: str) -> list[str]:
    cleaned = [str(rule).strip() for rule in rules if str(rule).strip()]
    if lang == "en":
        cleaned = [rule for rule in cleaned if not has_cjk(rule)]
    return dedupe_ordered(cleaned)


def rule_polarity(rule: str) -> str:
    low = rule.lower().strip()
    return "neg" if any(word in low for word in NEGATOR_WORDS) else "pos"


def conflict_token_set(rule: str) -> set[str]:
    tokens = tokenize(rule)
    ignored = RULE_STOPWORDS | set(NEGATOR_WORDS) | {"not", "no", "without", "non", "无", "非", "不"}
    return {tok for tok in tokens if len(tok) > 1 and tok not in ignored}


def rule_conflicts(rule_a: str, rule_b: str) -> bool:
    if rule_polarity(rule_a) == rule_polarity(rule_b):
        return False
    if utility_rules_conflict(rule_a, rule_b):
        return True
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


def rule_priority_score(rule: str) -> float:
    score = float(len(conflict_token_set(rule)))
    if re.search(r"#[0-9a-fA-F]{3,8}", rule):
        score += 2.0
    if re.search(r"\d", rule):
        score += 0.6
    if rule_polarity(rule) == "neg":
        score += 0.4
    return score


def resolve_rule_conflicts(rules: list[str], lang: str) -> list[str]:
    filtered = language_filter_rules(rules, lang)
    indexed = list(enumerate(filtered))
    ranked = sorted(indexed, key=lambda pair: (-rule_priority_score(pair[1]), pair[0]))

    selected: list[tuple[int, str]] = []
    for idx, rule in ranked:
        if any(rule_conflicts(rule, kept_rule) for _, kept_rule in selected):
            continue
        selected.append((idx, rule))

    selected.sort(key=lambda pair: pair[0])
    return [rule for _, rule in selected]


def ensure_rule_floor(rules: list[str], lang: str, min_count: int = 3) -> list[str]:
    out = dedupe_ordered(rules)
    if len(out) >= min_count:
        return out
    for fallback in DEFAULT_AI_RULES[lang]:
        if fallback not in out:
            out.append(fallback)
        if len(out) >= min_count:
            break
    return out


def build_localized_rule_list(items: list[str], lang: str, kind: str) -> list[str]:
    cleaned = language_filter_rules([str(item).strip() for item in items if str(item).strip()], lang)
    if cleaned:
        return cleaned[:6]
    if kind == "do":
        return DEFAULT_DO_LIST[lang][:6]
    return DEFAULT_DONT_LIST[lang][:6]


def localized_visual_direction(style: dict[str, Any], lang: str) -> str:
    raw = str(style.get("philosophy", "")).split("\n\n")[0].strip()
    if raw:
        if lang == "en" and not has_cjk(raw):
            return raw
        if lang == "zh" and has_cjk(raw):
            return raw

    slug = style.get("slug", "style")
    name = style.get("name", slug)
    name_en = style.get("nameEn", slug)
    if lang == "zh":
        return f"{name} 强调风格识别度、信息层级和组件状态一致性。"
    return f"{name_en} direction with strong visual identity, clear hierarchy, and consistent component-state behavior."


def style_anchor_terms(style: dict[str, Any], lang: str) -> list[str]:
    keywords = [str(x).strip() for x in style.get("keywords", []) if str(x).strip()]
    tags = [str(x).strip() for x in style.get("tags", []) if str(x).strip()]

    if lang == "zh":
        zh_terms = [term for term in keywords + tags if has_cjk(term)]
        if zh_terms:
            return dedupe_ordered(zh_terms)[:5]
        return dedupe_ordered(keywords + tags)[:5]

    en_terms: list[str] = []
    for term in keywords + tags:
        if not has_cjk(term):
            en_terms.append(term)
    name_en_tokens = re.findall(r"[a-zA-Z]{3,}", str(style.get("nameEn", "")))
    slug_tokens = [tok for tok in str(style.get("slug", "")).replace("-", " ").split() if len(tok) >= 3]
    en_terms.extend(name_en_tokens)
    en_terms.extend(slug_tokens)
    return dedupe_ordered(en_terms)[:6]


def build_reference_guidelines(reference_type: str, lang: str) -> list[str]:
    if reference_type == "none":
        return []
    if reference_type == "mixed":
        combined = REFERENCE_GUIDELINES["screenshot"][lang] + REFERENCE_GUIDELINES["figma"][lang]
        return dedupe_ordered(combined)[:6]
    if reference_type in REFERENCE_GUIDELINES:
        return REFERENCE_GUIDELINES[reference_type][lang][:6]
    return []


def refine_mode_strategy(refine_mode: str, lang: str) -> dict[str, Any]:
    mode = refine_mode if refine_mode in REFINE_MODE_HINTS else "new"
    payload = REFINE_MODE_HINTS[mode][lang]
    return {
        "mode": mode,
        "objective": payload["objective"],
        "constraints": payload["constraints"][:6],
    }


def to_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(to_text_list(item))
        return out
    if isinstance(value, dict):
        out: list[str] = []
        for key, val in value.items():
            vals = to_text_list(val)
            if vals:
                for item in vals:
                    out.append(f"{key}: {item}")
        return out
    return []


def merge_reference_payload(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in incoming.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_reference_payload(merged[key], value)
        elif key in merged and isinstance(merged[key], list) and isinstance(value, list):
            merged[key] = merged[key] + value
        else:
            merged[key] = value
    return merged


def load_reference_payload(reference_json: str, reference_file: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}

    if reference_file.strip():
        path = Path(reference_file.strip())
        if not path.exists():
            raise SystemExit(f"Reference file not found: {path}")
        text = path.read_text(encoding="utf-8").strip()
        if text:
            try:
                loaded = json.loads(text)
                if isinstance(loaded, dict):
                    payload = merge_reference_payload(payload, loaded)
                else:
                    payload = merge_reference_payload(payload, {"notes": str(loaded)})
            except json.JSONDecodeError:
                payload = merge_reference_payload(payload, {"notes": text})

    if reference_json.strip():
        text = reference_json.strip()
        try:
            loaded = json.loads(text)
            if isinstance(loaded, dict):
                payload = merge_reference_payload(payload, loaded)
            else:
                payload = merge_reference_payload(payload, {"notes": str(loaded)})
        except json.JSONDecodeError:
            payload = merge_reference_payload(payload, {"notes": text})

    return payload


def validate_reference_payload_schema(
    payload: dict[str, Any],
    reference_type: str,
    lang: str,
    strict_mode: bool,
) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    coercions: list[str] = []
    unknown_fields: list[str] = []

    if payload and not isinstance(payload, dict):
        errors.append("reference payload must be a JSON object")
        payload = {}

    sanitized = dict(payload or {})

    for section in REFERENCE_SECTION_KEYS:
        if section not in sanitized:
            continue
        value = sanitized.get(section)
        if isinstance(value, dict):
            continue
        if section == "tokens":
            coerced_values = to_text_list(value)
            if coerced_values:
                sanitized[section] = {"values": coerced_values}
                coercions.append(section)
                warnings.append(f"coerced `{section}` to object with `values` list")
                continue
            errors.append(f"`{section}` must be an object or list-like value")
            continue

        coerced_values = to_text_list(value)
        if coerced_values:
            sanitized[section] = {"issues": coerced_values}
            coercions.append(section)
            warnings.append(f"coerced `{section}` to object with `issues` list")
        else:
            errors.append(f"`{section}` must be an object or list-like value")

    for meta_key in ("source", "type"):
        if meta_key in sanitized and not isinstance(sanitized.get(meta_key), str):
            coerced = " ".join(to_text_list(sanitized.get(meta_key))).strip()
            if coerced:
                sanitized[meta_key] = coerced
                coercions.append(meta_key)
                warnings.append(f"coerced `{meta_key}` to string")
            else:
                errors.append(f"`{meta_key}` must be a string")

    for key in sanitized.keys():
        if key not in REFERENCE_KNOWN_TOP_LEVEL:
            unknown_fields.append(key)

    if unknown_fields:
        sample = ", ".join(sorted(unknown_fields)[:6])
        warnings.append(f"unknown top-level fields detected: {sample}")

    source_hint = str(sanitized.get("source", "") or sanitized.get("type", "")).lower()
    if reference_type in {"screenshot", "figma"} and source_hint:
        if reference_type == "screenshot" and "figma" in source_hint:
            warnings.append("reference_type is screenshot but source/type suggests figma")
        if reference_type == "figma" and any(token in source_hint for token in ["screen", "shot", "截图"]):
            warnings.append("reference_type is figma but source/type suggests screenshot")

    if strict_mode and (errors or unknown_fields):
        if errors:
            errors.append("strict schema mode blocks invalid reference payload")
        if unknown_fields:
            errors.append("strict schema mode blocks unknown top-level fields")

    valid = len(errors) == 0
    return {
        "valid": valid,
        "strict_mode": strict_mode,
        "errors": dedupe_ordered(errors),
        "warnings": dedupe_ordered(warnings),
        "coercions": dedupe_ordered(coercions),
        "unknown_fields": sorted(set(unknown_fields)),
        "sanitized_payload": sanitized,
    }


def get_alias_values(payload: dict[str, Any], aliases: list[str]) -> list[str]:
    out: list[str] = []
    for key in aliases:
        if key in payload:
            out.extend(to_text_list(payload.get(key)))
    return dedupe_ordered(out)


def normalize_reference_signals(
    payload: dict[str, Any],
    reference_type: str,
    reference_notes: str,
    lang: str,
) -> dict[str, Any]:
    if not payload and not reference_notes.strip():
        return {
            "has_signals": False,
            "source": reference_type,
            "summary": "",
            "signals": {
                "layout_issues": [],
                "missing_components": [],
                "preserve_elements": [],
                "interaction_gaps": [],
                "a11y_gaps": [],
                "token_clues": [],
                "notes": [],
            },
            "derived_rules": [],
        }

    layout_block = payload.get("layout") if isinstance(payload.get("layout"), dict) else {}
    component_block = payload.get("components") if isinstance(payload.get("components"), dict) else {}
    interaction_block = payload.get("interaction") if isinstance(payload.get("interaction"), dict) else {}
    a11y_block = payload.get("accessibility") if isinstance(payload.get("accessibility"), dict) else {}
    token_block = payload.get("tokens") if isinstance(payload.get("tokens"), dict) else {}

    layout_issues = get_alias_values(payload, REFERENCE_FIELD_ALIASES["layout_issues"])
    layout_issues.extend(get_alias_values(layout_block, ["issues", "problem", "problems", "gaps"]))

    missing_components = get_alias_values(payload, REFERENCE_FIELD_ALIASES["missing_components"])
    missing_components.extend(get_alias_values(component_block, ["missing", "gaps"]))

    preserve_elements = get_alias_values(payload, REFERENCE_FIELD_ALIASES["preserve_elements"])
    preserve_elements.extend(get_alias_values(layout_block, ["preserve", "keep"]))
    preserve_elements.extend(get_alias_values(component_block, ["preserve", "keep"]))

    interaction_gaps = get_alias_values(payload, REFERENCE_FIELD_ALIASES["interaction_gaps"])
    interaction_gaps.extend(get_alias_values(interaction_block, ["missing_states", "gaps", "issues"]))

    a11y_gaps = get_alias_values(payload, REFERENCE_FIELD_ALIASES["a11y_gaps"])
    a11y_gaps.extend(get_alias_values(a11y_block, ["issues", "gaps", "missing"]))

    token_clues = get_alias_values(payload, REFERENCE_FIELD_ALIASES["token_clues"])
    token_clues.extend(get_alias_values(token_block, ["colors", "spacing", "typography", "radius", "shadows"]))

    notes = get_alias_values(payload, REFERENCE_FIELD_ALIASES["notes"])
    if reference_notes.strip():
        notes.append(reference_notes.strip())

    layout_issues = dedupe_ordered(layout_issues)[:5]
    missing_components = dedupe_ordered(missing_components)[:5]
    preserve_elements = dedupe_ordered(preserve_elements)[:5]
    interaction_gaps = dedupe_ordered(interaction_gaps)[:5]
    a11y_gaps = dedupe_ordered(a11y_gaps)[:5]
    token_clues = dedupe_ordered(token_clues)[:6]
    notes = dedupe_ordered(notes)[:3]

    derived_rules: list[str] = []
    if lang == "zh":
        derived_rules.extend([f"修复参考输入中的布局问题：{item}。" for item in layout_issues[:3]])
        derived_rules.extend([f"补齐缺失组件/状态：{item}。" for item in missing_components[:2]])
        derived_rules.extend([f"保留既有结构要素：{item}。" for item in preserve_elements[:2]])
        derived_rules.extend([f"补全交互缺口：{item}。" for item in interaction_gaps[:2]])
        derived_rules.extend([f"修复可访问性缺口：{item}。" for item in a11y_gaps[:2]])
        if token_clues:
            derived_rules.append(f"参考 token 线索并映射到语义 token：{'；'.join(token_clues[:4])}。")
    else:
        derived_rules.extend([f"Fix layout issue from reference input: {item}." for item in layout_issues[:3]])
        derived_rules.extend([f"Fill missing component/state: {item}." for item in missing_components[:2]])
        derived_rules.extend([f"Preserve existing structural element: {item}." for item in preserve_elements[:2]])
        derived_rules.extend([f"Close interaction gap: {item}." for item in interaction_gaps[:2]])
        derived_rules.extend([f"Fix accessibility gap: {item}." for item in a11y_gaps[:2]])
        if token_clues:
            derived_rules.append(f"Map reference token clues to semantic tokens: {'; '.join(token_clues[:4])}.")

    summary_parts = []
    if layout_issues:
        summary_parts.append(f"layout:{len(layout_issues)}")
    if missing_components:
        summary_parts.append(f"components:{len(missing_components)}")
    if preserve_elements:
        summary_parts.append(f"preserve:{len(preserve_elements)}")
    if interaction_gaps:
        summary_parts.append(f"interaction:{len(interaction_gaps)}")
    if a11y_gaps:
        summary_parts.append(f"a11y:{len(a11y_gaps)}")
    if token_clues:
        summary_parts.append(f"tokens:{len(token_clues)}")
    summary = ", ".join(summary_parts)

    signals = {
        "layout_issues": layout_issues,
        "missing_components": missing_components,
        "preserve_elements": preserve_elements,
        "interaction_gaps": interaction_gaps,
        "a11y_gaps": a11y_gaps,
        "token_clues": token_clues,
        "notes": notes,
    }
    has_signals = any(bool(value) for value in signals.values())

    return {
        "has_signals": has_signals,
        "source": reference_type,
        "summary": summary,
        "signals": signals,
        "derived_rules": dedupe_ordered(derived_rules)[:8],
    }


def reference_signal_prompt_block(reference_signals: dict[str, Any], lang: str) -> str:
    if not reference_signals.get("has_signals"):
        return ""

    sig = reference_signals.get("signals", {})
    layout_issues = sig.get("layout_issues", [])
    missing_components = sig.get("missing_components", [])
    preserve_elements = sig.get("preserve_elements", [])
    interaction_gaps = sig.get("interaction_gaps", [])
    a11y_gaps = sig.get("a11y_gaps", [])
    token_clues = sig.get("token_clues", [])
    notes = sig.get("notes", [])

    if lang == "zh":
        lines = ["参考信号提取："]
        if layout_issues:
            lines.append(f"- 布局问题：{'；'.join(layout_issues[:3])}")
        if missing_components:
            lines.append(f"- 缺失组件：{'；'.join(missing_components[:3])}")
        if preserve_elements:
            lines.append(f"- 保留要素：{'；'.join(preserve_elements[:3])}")
        if interaction_gaps:
            lines.append(f"- 交互缺口：{'；'.join(interaction_gaps[:3])}")
        if a11y_gaps:
            lines.append(f"- 可访问性缺口：{'；'.join(a11y_gaps[:3])}")
        if token_clues:
            lines.append(f"- Token 线索：{'；'.join(token_clues[:4])}")
        if notes:
            lines.append(f"- 备注：{'；'.join(notes[:2])}")
        return "\n".join(lines) + "\n\n"

    lines = ["Reference signal extraction:"]
    if layout_issues:
        lines.append(f"- Layout issues: {'; '.join(layout_issues[:3])}")
    if missing_components:
        lines.append(f"- Missing components: {'; '.join(missing_components[:3])}")
    if preserve_elements:
        lines.append(f"- Preserve elements: {'; '.join(preserve_elements[:3])}")
    if interaction_gaps:
        lines.append(f"- Interaction gaps: {'; '.join(interaction_gaps[:3])}")
    if a11y_gaps:
        lines.append(f"- Accessibility gaps: {'; '.join(a11y_gaps[:3])}")
    if token_clues:
        lines.append(f"- Token clues: {'; '.join(token_clues[:4])}")
    if notes:
        lines.append(f"- Notes: {'; '.join(notes[:2])}")
    return "\n".join(lines) + "\n\n"


def infer_design_intent(query: str, lang: str) -> dict[str, str]:
    q = query.lower()
    if lang == "zh":
        purpose = "构建高质量可落地前端界面，并确保视觉辨识度。"
        if any(k in q for k in ["saas", "后台", "dashboard", "管理"]):
            audience = "B 端专业用户，重视效率、可读性与稳定性。"
        elif any(k in q for k in ["landing", "营销", "转化", "品牌"]):
            audience = "潜在客户与决策者，重视品牌感与可信度。"
        else:
            audience = "通用互联网用户，重视信息清晰和操作顺畅。"

        if any(k in q for k in ["玻璃", "glassy", "frosted", "glass"]):
            tone = "现代科技感、通透层叠、精致高端。"
        elif any(k in q for k in ["复古", "vintage", "retro", "y2k"]):
            tone = "复古表达、强记忆点、个性视觉。"
        elif any(k in q for k in ["极简", "minimal", "clean"]):
            tone = "克制极简、结构优先、内容导向。"
        else:
            tone = "鲜明风格取向，避免通用模板化审美。"

        memorable_hook = "至少设置一个可记忆视觉锚点（独特排版/背景层次/动效节奏）。"
        return {
            "purpose": purpose,
            "audience": audience,
            "tone": tone,
            "memorable_hook": memorable_hook,
        }

    purpose = "Deliver production-ready frontend UI with strong aesthetic identity."
    if any(k in q for k in ["saas", "dashboard", "admin", "finance"]):
        audience = "Professional users who prioritize readability, efficiency, and trust."
    elif any(k in q for k in ["landing", "marketing", "conversion", "brand"]):
        audience = "Prospects and decision-makers who respond to credibility and brand clarity."
    else:
        audience = "General users who need clear structure and smooth interactions."

    if any(k in q for k in ["glass", "frosted", "transparent"]):
        tone = "Polished modern tech aesthetic with layered translucency."
    elif any(k in q for k in ["retro", "vintage", "y2k"]):
        tone = "Expressive nostalgic aesthetic with memorable visual contrast."
    elif any(k in q for k in ["minimal", "clean"]):
        tone = "Refined minimal aesthetic with strict hierarchy and restraint."
    else:
        tone = "Distinctive intentional style direction, not generic defaults."

    memorable_hook = "Introduce one memorable visual anchor (type treatment, background depth, or motion rhythm)."
    return {
        "purpose": purpose,
        "audience": audience,
        "tone": tone,
        "memorable_hook": memorable_hook,
    }


def anti_generic_constraints(lang: str) -> list[str]:
    if lang == "zh":
        return [
            "避免无差别模板化布局；保留明确风格立场。",
            "避免默认紫色渐变白底套路，色彩需与风格语义一致。",
            "避免过度依赖通用默认字体，至少给出清晰字体策略。",
            "背景需有层次与氛围（渐变、纹理、形状或叠层），不要单一平涂。",
        ]
    return [
        "Avoid generic interchangeable layout patterns; keep a clear style point-of-view.",
        "Avoid default purple-on-white gradient clichés unless explicitly required by style.",
        "Avoid over-reliance on generic default fonts; provide explicit typography strategy.",
        "Build atmospheric background depth (gradients/textures/shapes/layers), not flat filler.",
    ]


def design_system_structure(stack: str, lang: str) -> dict[str, Any]:
    if lang == "zh":
        return {
            "token_hierarchy": [
                "品牌色 Token -> 语义 Token（primary/surface/text）-> 组件 Token（button/card/input）",
                "间距与圆角采用全局尺度，避免组件各自为政。",
                "状态 Token 明确区分 hover/active/focus/disabled。",
            ],
            "component_architecture": [
                "Base -> Variant -> Size -> State -> Override 进行组件分层。",
                "优先复用组件 API，不在页面内重复拼接样式逻辑。",
                f"栈适配：{stack} 下保持设计 Token 与组件 API 同步。",
            ],
        }
    return {
        "token_hierarchy": [
            "Brand tokens -> semantic tokens (primary/surface/text) -> component tokens (button/card/input).",
            "Use a unified spacing/radius scale instead of per-component ad hoc values.",
            "Define explicit state tokens for hover/active/focus/disabled.",
        ],
        "component_architecture": [
            "Structure components as Base -> Variant -> Size -> State -> Override.",
            "Prefer reusable component APIs over per-page style assembly.",
            f"Stack alignment: keep token and component API mapping consistent in {stack}.",
        ],
    }


def rule_token_set(text: str) -> set[str]:
    return {tok for tok in tokenize(text) if tok not in RULE_STOPWORDS and len(tok) > 1}


def is_negative_rule(rule: str) -> bool:
    low = rule.lower()
    return any(word in low for word in NEGATOR_WORDS)


def conflicts_with_dont(rule: str, dont_list: list[str]) -> bool:
    # Negative rules are usually safe because they describe what to avoid.
    if is_negative_rule(rule):
        return False

    r_tokens = rule_token_set(rule)
    if not r_tokens:
        return False

    for dont in dont_list:
        d_tokens = rule_token_set(str(dont))
        if len(d_tokens) < 2:
            continue
        overlap = len(r_tokens & d_tokens)
        ratio = overlap / max(len(d_tokens), 1)
        if ratio >= 0.55 or (overlap >= 2 and len(d_tokens) <= 4):
            return True
    return False


def extract_rules(ai_rules_text: str, lang: str) -> list[str]:
    lines = []
    section_polarity: str | None = None

    for raw in str(ai_rules_text or "").splitlines():
        raw_line = raw.strip()
        if not raw_line:
            continue

        heading_polarity = section_polarity_from_heading(raw_line)
        if heading_polarity:
            section_polarity = heading_polarity
            continue

        line = re.sub(r"^[-*]\s+", "", raw_line)
        line = re.sub(r"^\d+\.\s+", "", line)
        if len(line) < 8:
            continue

        low = line.lower()
        if line.startswith("#"):
            continue
        if "你是一个" in line or "you are" in low:
            continue
        if "生成的所有代码必须" in line or "all code must" in low:
            continue

        # Treat bullets inside forbidden sections as negative constraints.
        if section_polarity == "neg":
            line = to_negative_rule(line, lang)

        lines.append(line)

    deduped = []
    seen = set()
    for item in lines:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def rank_styles(styles: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    docs = [build_text(s) for s in styles]
    bm25 = BM25()
    bm25.fit(docs)
    qtokens = expand_query_tokens(tokenize(query))
    bm25_scores = {styles[idx].get("slug"): score for idx, score in bm25.score(query_tokens=qtokens)}

    ranked = []
    for style in styles:
        h_score, reasons = heuristic_score(style, query, qtokens)
        b_score = bm25_scores.get(style.get("slug"), 0.0)
        final_score = b_score * 3.0 + h_score
        ranked.append(
            {
                "style": style,
                "score": final_score,
                "reason": reasons,
            }
        )

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked


def resolve_primary_style(styles: list[dict[str, Any]], query: str, forced_slug: str | None):
    if forced_slug:
        for style in styles:
            if style.get("slug") == forced_slug:
                return style, rank_styles(styles, query)
        raise SystemExit(f"Style slug not found: {forced_slug}")

    ranked = rank_styles(styles, query)
    if not ranked:
        raise SystemExit("No style available")
    return ranked[0]["style"], ranked


def build_component_guidelines(style: dict[str, Any], lang: str) -> list[str]:
    guidelines = []
    components = style.get("components", {})

    if components.get("button"):
        guidelines.append(
            "按钮要有明确层级、可见 hover/active/focus 状态。" if lang == "zh" else "Buttons must expose clear hierarchy and visible hover/active/focus states."
        )
    if components.get("card"):
        guidelines.append(
            "卡片需体现信息层级：标题、摘要、次级信息和操作区。" if lang == "zh" else "Cards should express hierarchy: title, summary, metadata, and actions."
        )
    if components.get("input"):
        guidelines.append(
            "表单输入需包含标签、错误状态和辅助说明。" if lang == "zh" else "Inputs must include labels, error states, and helper copy."
        )
    if components.get("nav"):
        guidelines.append(
            "导航需包含当前态与可预测的信息结构。" if lang == "zh" else "Navigation should include active state and predictable information structure."
        )
    if components.get("hero"):
        guidelines.append(
            "首屏需在 3 秒内传达价值主张与主行动按钮。" if lang == "zh" else "Hero must communicate value proposition and primary CTA within 3 seconds."
        )
    if components.get("footer"):
        guidelines.append(
            "页脚承载次级链接、版权与信任信息。" if lang == "zh" else "Footer should host secondary links, trust signals, and legal metadata."
        )

    if not guidelines:
        guidelines.append("Use component constraints from aiRules and doList." if lang == "en" else "优先按 aiRules 与 doList 约束组件实现。")

    return guidelines[:6]


def build_interaction_rules(ai_rules: list[str], lang: str) -> list[str]:
    keywords = ["hover", "active", "focus", "transition", "animation", "motion", "交互", "悬停", "点击", "焦点", "动画"]
    selected = [rule for rule in ai_rules if any(word in rule.lower() for word in keywords)]

    if len(selected) < 3:
        fallback = (
            [
                "States must include hover, active, focus-visible, and disabled.",
                "Motion timing should stay within 150-300ms unless explicitly theatrical.",
                "Interactive feedback should be immediate and visually unambiguous.",
            ]
            if lang == "en"
            else [
                "组件状态至少覆盖 hover、active、focus-visible 与 disabled。",
                "动画时长通常控制在 150-300ms，除非是刻意戏剧化表现。",
                "交互反馈必须即时且视觉上明确。",
            ]
        )
        selected.extend(fallback)

    deduped = []
    seen = set()
    for rule in selected:
        key = rule.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rule)
    return deduped[:6]


def normalize_rule(rule: str, dont_list: list[str], lang: str) -> str:
    low = rule.lower().strip()
    if any(word in low for word in NEGATOR_WORDS):
        return rule

    risky_starts = ["省略", "删除", "移除", "去掉", "禁用", "omit", "remove", "disable"]
    if any(low.startswith(item) for item in risky_starts):
        if lang == "zh":
            return f"避免{rule}" if not rule.startswith(("避免", "不要", "禁止")) else rule
        return f"Avoid {rule[0].lower() + rule[1:]}" if rule else rule

    for dont in dont_list:
        d = str(dont).strip()
        if len(d) < 4:
            continue
        if rule in d or d in rule:
            if lang == "zh":
                return f"避免{rule}" if not rule.startswith(("避免", "不要", "禁止")) else rule
            return f"Avoid {rule[0].lower() + rule[1:]}" if rule else rule
    return rule


def ensure_min_rules(base_rules: list[str], do_list: list[str], dont_list: list[str], lang: str) -> list[str]:
    out = []
    for rule in base_rules:
        normalized = normalize_rule(rule, dont_list, lang)
        normalized = rewrite_ambiguous_positive_rule(normalized, lang)
        if has_internal_utility_conflict(normalized):
            continue
        if conflicts_with_dont(normalized, dont_list):
            continue
        out.append(normalized)

    for item in do_list:
        if len(out) >= 6:
            break
        if is_negative_rule(item):
            continue
        normalized_item = rewrite_ambiguous_positive_rule(item, lang)
        if has_internal_utility_conflict(normalized_item):
            continue
        if conflicts_with_dont(normalized_item, dont_list):
            continue
        if normalized_item not in out:
            out.append(normalized_item)

    if len(out) < 3:
        defaults = (
            [
                "Apply the style token direction consistently across all major components.",
                "Keep spacing rhythm and typography scale coherent across breakpoints.",
                "Preserve strong visual hierarchy before adding decorative effects.",
            ]
            if lang == "en"
            else [
                "在主要组件上保持统一的风格 token 方向。",
                "在各断点保持一致的间距节奏与字号层级。",
                "先确保清晰视觉层级，再添加装饰效果。",
            ]
        )
        out.extend(defaults)

    deduped = []
    seen = set()
    for rule in out:
        key = rule.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rule)
    return deduped[:8]


def motion_score(style: dict[str, Any]) -> float:
    text = (style.get("aiRules", "") + "\n" + " ".join(style.get("keywords", []))).lower()
    keywords = ["hover", "active", "transition", "animation", "motion", "glow", "悬停", "点击", "动画", "发光", "动效"]
    return sum(1.0 for kw in keywords if kw in text)


def typography_score(style: dict[str, Any], qtokens: list[str]) -> float:
    text = "\n".join(
        [
            str(style.get("name", "")),
            str(style.get("nameEn", "")),
            str(style.get("philosophy", "")),
            " ".join(style.get("keywords", [])),
        ]
    ).lower()
    base = 0.0
    for kw in ["typography", "serif", "editorial", "readability", "字体", "排版", "可读"]:
        if kw in text:
            base += 1.0
    base += sum(0.3 for token in qtokens if token in text)
    return base


def spacing_score(style: dict[str, Any]) -> float:
    stype = style.get("styleType")
    base = 2.0 if stype == "layout" else 0.0
    text = "\n".join([str(style.get("nameEn", "")), str(style.get("name", "")), " ".join(style.get("keywords", []))]).lower()
    for kw in ["layout", "grid", "dashboard", "timeline", "sidebar", "布局", "网格", "间距"]:
        if kw in text:
            base += 0.8
    return base


def color_score(style: dict[str, Any], qtokens: list[str]) -> float:
    text = "\n".join([str(style.get("nameEn", "")), str(style.get("name", "")), " ".join(style.get("keywords", []))]).lower()
    base = 0.0
    for kw in ["color", "neon", "glass", "gradient", "luxury", "palette", "色彩", "霓虹", "玻璃", "渐变", "高端"]:
        if kw in text:
            base += 0.7
    base += sum(0.25 for token in qtokens if token in text)
    return base


def pick_owner(styles: list[dict[str, Any]], scorer) -> str:
    if not styles:
        return ""
    scored = sorted(styles, key=scorer, reverse=True)
    return scored[0].get("slug", "")


def build_blend_plan(primary: dict[str, Any], alternatives: list[dict[str, Any]], query: str, lang: str) -> dict[str, Any]:
    all_styles = [primary] + [item["style"] if "style" in item else item for item in alternatives]
    all_styles = [style for style in all_styles if style]
    qtokens = expand_query_tokens(tokenize(query))

    if len(all_styles) <= 1:
        return {
            "enabled": False,
            "base_style": primary.get("slug"),
            "blend_styles": [],
            "conflict_resolution": {},
            "priority_order": [primary.get("slug")],
            "notes": "No secondary style available for blending." if lang == "en" else "当前没有可用于融合的次级风格。",
        }

    secondary = [style for style in all_styles if style.get("slug") != primary.get("slug")][:2]
    blend_weights = []
    weight_values = [0.25, 0.15]
    for idx, style in enumerate(secondary):
        blend_weights.append({"slug": style.get("slug"), "weight": weight_values[idx] if idx < len(weight_values) else 0.1})

    color_owner = pick_owner(all_styles, lambda s: color_score(s, qtokens))
    typography_owner = pick_owner(all_styles, lambda s: typography_score(s, qtokens))
    spacing_owner = pick_owner(all_styles, spacing_score)
    motion_owner = pick_owner(all_styles, motion_score)

    conflict_resolution = {
        "color_owner": color_owner or primary.get("slug"),
        "typography_owner": typography_owner or primary.get("slug"),
        "spacing_owner": spacing_owner or primary.get("slug"),
        "motion_owner": motion_owner or primary.get("slug"),
    }

    priority_order = [primary.get("slug")] + [item.get("slug") for item in secondary]

    return {
        "enabled": True,
        "base_style": primary.get("slug"),
        "blend_styles": blend_weights,
        "conflict_resolution": conflict_resolution,
        "priority_order": priority_order,
        "notes": (
            "Base style controls global identity; owners control each token domain."
            if lang == "en"
            else "主风格控制整体气质，冲突归属控制具体 token 维度。"
        ),
    }


def blend_directive(blend_plan: dict[str, Any], lang: str) -> str:
    if not blend_plan.get("enabled"):
        return ""
    c = blend_plan.get("conflict_resolution", {})
    if lang == "zh":
        return (
            "融合规则：\n"
            f"- 色彩由 `{c.get('color_owner')}` 主导\n"
            f"- 字体与排版由 `{c.get('typography_owner')}` 主导\n"
            f"- 间距与布局节奏由 `{c.get('spacing_owner')}` 主导\n"
            f"- 动效与交互反馈由 `{c.get('motion_owner')}` 主导"
        )
    return (
        "Blend rules:\n"
        f"- Color is owned by `{c.get('color_owner')}`\n"
        f"- Typography is owned by `{c.get('typography_owner')}`\n"
        f"- Spacing/layout rhythm is owned by `{c.get('spacing_owner')}`\n"
        f"- Motion/interaction is owned by `{c.get('motion_owner')}`"
    )


def make_prompts(
    query: str,
    style: dict[str, Any],
    ai_rules: list[str],
    stack: str,
    lang: str,
    blend_plan: dict[str, Any],
    intent: dict[str, str],
    anti_generic: list[str],
    refine_mode: str,
    reference_type: str,
    reference_notes: str,
    reference_signals: dict[str, Any],
) -> tuple[str, str]:
    stack_hint = STACK_HINTS.get(stack, STACK_HINTS["html-tailwind"])[lang]
    validation_tests = VALIDATION_TESTS[lang]
    anti_patterns = ANTI_PATTERN_BLACKLIST[lang]
    do_list = build_localized_rule_list(style.get("doList", []), lang, kind="do")
    dont_list = build_localized_rule_list(style.get("dontList", []), lang, kind="dont")
    anchor_terms = style_anchor_terms(style, lang)
    anchor_line_zh = "、".join(anchor_terms) if anchor_terms else style.get("slug", "")
    anchor_line_en = ", ".join(anchor_terms) if anchor_terms else style.get("slug", "")
    refine_strategy = refine_mode_strategy(refine_mode, lang)
    reference_guidelines = build_reference_guidelines(reference_type, lang)
    reference_signal_block = reference_signal_prompt_block(reference_signals, lang)

    if lang == "zh":
        refine_block = (
            f"迭代模式：{refine_strategy.get('mode')}\n"
            + f"- 本轮目标：{refine_strategy.get('objective')}\n"
            + "模式约束：\n"
            + "\n".join([f"- {item}" for item in refine_strategy.get("constraints", [])])
            + "\n\n"
        )
        reference_block = ""
        if reference_guidelines:
            reference_block = (
                f"参考输入类型：{reference_type}\n"
                + "参考输入约束：\n"
                + "\n".join([f"- {item}" for item in reference_guidelines])
                + ("\n" + f"- 参考备注：{reference_notes.strip()}" if reference_notes.strip() else "")
                + "\n\n"
            )
        reference_block = reference_block + reference_signal_block
    else:
        refine_block = (
            f"Refinement mode: {refine_strategy.get('mode')}\n"
            + f"- Objective: {refine_strategy.get('objective')}\n"
            + "Mode constraints:\n"
            + "\n".join([f"- {item}" for item in refine_strategy.get("constraints", [])])
            + "\n\n"
        )
        reference_block = ""
        if reference_guidelines:
            reference_block = (
                f"Reference input type: {reference_type}\n"
                + "Reference handling constraints:\n"
                + "\n".join([f"- {item}" for item in reference_guidelines])
                + ("\n" + f"- Reference notes: {reference_notes.strip()}" if reference_notes.strip() else "")
                + "\n\n"
            )
        reference_block = reference_block + reference_signal_block

    if lang == "zh":
        hard = (
            f"你是高级前端设计工程师。请严格按照 StyleKit 风格 `{style.get('slug')}` 生成界面。\n"
            f"需求：{query}\n\n"
            + "设计意图：\n"
            + f"- 目标：{intent.get('purpose')}\n"
            + f"- 受众：{intent.get('audience')}\n"
            + f"- 调性：{intent.get('tone')}\n"
            + f"- 记忆点：{intent.get('memorable_hook')}\n\n"
            + refine_block
            + reference_block
            + "硬性约束：\n"
            + "\n".join([f"- {rule}" for rule in ai_rules])
            + "\n\n"
            + "必须遵守 Do：\n"
            + "\n".join([f"- {item}" for item in do_list])
            + "\n\n"
            + "必须避免 Don't：\n"
            + "\n".join([f"- {item}" for item in dont_list])
            + "\n\n"
            + f"技术栈约束：{stack_hint}\n"
            + "组件覆盖：至少提供 button、card、input，并补充 nav、hero、footer 中至少两个。\n"
            + "可访问性基线：保持 WCAG 2.1 AA（4.5:1）对比度、44x44px 触控目标，并确保键盘可达性。\n"
            + "反模板化约束：\n"
            + "\n".join([f"- {item}" for item in anti_generic])
            + "\n"
            + "设计系统约束：使用 primary/surface/text 语义 token，统一 spacing scale 与 radius，并明确 variant/state 层级。\n"
            + f"风格锚点词：{anchor_line_zh}（需在视觉语言、排版和组件语义中体现）。\n"
            + "提案前校验（必须自检）：\n"
            + "\n".join([f"- {item}" for item in validation_tests])
            + "\n"
            + "反模式禁令：\n"
            + "\n".join([f"- {item}" for item in anti_patterns])
            + "\n"
            + "输出要求：提供语义化结构、响应式布局、可访问状态（hover/active/focus-visible/disabled），并保持视觉一致。"
        )
        blend_hint = blend_directive(blend_plan, lang)
        if blend_hint:
            hard = hard + "\n\n" + blend_hint

        soft = (
            f"请基于 StyleKit 风格 `{style.get('slug')}` 生成一个美观且可实现的前端方案。\n"
            f"需求：{query}\n"
            "保持风格核心（配色、层级、节奏、交互反馈），允许在版式和细节上做创造性调整。\n"
            + "设计意图：\n"
            + f"- 目标：{intent.get('purpose')}\n"
            + f"- 受众：{intent.get('audience')}\n"
            + f"- 调性：{intent.get('tone')}\n"
            + refine_block
            + reference_block
            + "优先规则：\n"
            + "\n".join([f"- {rule}" for rule in ai_rules[:4]])
            + f"\n技术栈建议：{stack_hint}\n"
            + "建议组件：button、card、input，并补充 nav/hero/footer 中至少两个。\n"
            + "最低可访问性：WCAG 对比度目标（建议 4.5:1）与 44x44px 触控尺寸基线。\n"
            + "建议采用设计 token：primary/secondary/text、spacing scale、radius、variant/state。\n"
            + f"风格锚点词：{anchor_line_zh}。\n"
            + "请在提交前执行替换测试、眯眼测试、签名测试、Token 测试，并避开绝对定位整页、嵌套滚动和焦点样式缺失等反模式。"
        )
        blend_hint = blend_directive(blend_plan, lang)
        if blend_hint:
            soft = soft + "\n" + blend_hint
        return hard, soft

    hard = (
        f"You are a senior frontend design engineer. Strictly implement StyleKit style `{style.get('slug')}`.\n"
        f"Requirement: {query}\n\n"
        + "Design intent:\n"
        + f"- Purpose: {intent.get('purpose')}\n"
        + f"- Audience: {intent.get('audience')}\n"
        + f"- Tone: {intent.get('tone')}\n"
        + f"- Memorable hook: {intent.get('memorable_hook')}\n\n"
        + refine_block
        + reference_block
        + "Hard constraints:\n"
        + "\n".join([f"- {rule}" for rule in ai_rules])
        + "\n\n"
        + "Must-do constraints:\n"
        + "\n".join([f"- {item}" for item in do_list])
        + "\n\n"
        + "Must-avoid constraints:\n"
        + "\n".join([f"- {item}" for item in dont_list])
        + "\n\n"
        + f"Stack hint: {stack_hint}\n"
        + "Component coverage: include button, card, input, and at least two of nav/hero/footer.\n"
        + "Accessibility baseline: maintain WCAG 2.1 AA (4.5:1) contrast, 44x44px touch targets, and keyboard-ready focus states.\n"
        + "Anti-generic constraints:\n"
        + "\n".join([f"- {item}" for item in anti_generic])
        + "\n"
        + "Design system constraints: use semantic design tokens (primary/surface/text), a unified spacing scale + radius scale, and explicit variant/state hierarchy.\n"
        + f"Style anchor terms: {anchor_line_en} (must appear in visual language, typography, and component semantics).\n"
        + "Pre-delivery validation tests:\n"
        + "\n".join([f"- {item}" for item in validation_tests])
        + "\n"
        + "Anti-pattern blacklist:\n"
        + "\n".join([f"- {item}" for item in anti_patterns])
        + "\n"
        + "Output semantic structure, responsive layout, and full interaction states (hover/active/focus-visible/disabled)."
    )
    blend_hint = blend_directive(blend_plan, lang)
    if blend_hint:
        hard = hard + "\n\n" + blend_hint

    soft = (
        f"Generate a beautiful and production-feasible frontend concept in StyleKit style `{style.get('slug')}`.\n"
        f"Requirement: {query}\n"
        "Preserve the style DNA (color, hierarchy, rhythm, interaction feedback) while allowing creative layout variation.\n"
        + "Design intent:\n"
        + f"- Purpose: {intent.get('purpose')}\n"
        + f"- Audience: {intent.get('audience')}\n"
        + f"- Tone: {intent.get('tone')}\n"
        + refine_block
        + reference_block
        + "Priority rules:\n"
        + "\n".join([f"- {rule}" for rule in ai_rules[:4]])
        + f"\nStack hint: {stack_hint}\n"
        + "Suggested components: button, card, input, plus at least two of nav/hero/footer.\n"
        + "Accessibility minimum: WCAG contrast target (e.g. 4.5:1) and 44x44px touch-target baseline.\n"
        + "Prefer tokenized implementation: semantic tokens, spacing/radius scales, and explicit variants/states.\n"
        + f"Style anchor terms: {anchor_line_en}.\n"
        + "Run swap/squint/signature/token tests before final output and avoid anti-patterns (absolute layout, nested scroll, missing focus styles)."
    )
    blend_hint = blend_directive(blend_plan, lang)
    if blend_hint:
        soft = soft + "\n" + blend_hint

    return hard, soft


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate StyleKit design brief and prompts")
    parser.add_argument("--query", required=True, help="User requirement")
    parser.add_argument("--style", help="Force style slug")
    parser.add_argument("--stack", default="html-tailwind", choices=list(STACK_HINTS.keys()))
    parser.add_argument("--mode", default="brief+prompt", choices=["brief-only", "brief+prompt"])
    parser.add_argument("--blend-mode", default="auto", choices=["off", "auto", "on"], help="Style blend planning mode")
    parser.add_argument(
        "--refine-mode",
        default="new",
        choices=sorted(REFINE_MODE_HINTS.keys()),
        help="Iteration mode: new/polish/debug/contrast-fix/layout-fix/component-fill",
    )
    parser.add_argument(
        "--reference-type",
        default="none",
        choices=REFERENCE_TYPES,
        help="Optional input reference type: none/screenshot/figma/mixed",
    )
    parser.add_argument("--reference-notes", default="", help="Optional notes describing screenshot/Figma context")
    parser.add_argument("--reference-file", default="", help="Optional path to reference JSON/text (screenshot/Figma analysis)")
    parser.add_argument("--reference-json", default="", help="Optional inline reference JSON/text")
    parser.add_argument(
        "--strict-reference-schema",
        action="store_true",
        help="Fail when reference payload has schema errors or unknown top-level fields",
    )
    parser.add_argument("--style-type", choices=["visual", "layout", "animation"])
    parser.add_argument("--catalog", default=str(CATALOG_DEFAULT))
    args = parser.parse_args()

    catalog_path = Path(args.catalog)
    if not catalog_path.exists():
        raise SystemExit(f"Catalog not found: {catalog_path}")

    catalog = load_json(catalog_path)
    styles: list[dict[str, Any]] = catalog.get("styles", [])
    if args.style_type:
        styles = [s for s in styles if s.get("styleType") == args.style_type]

    if not styles:
        raise SystemExit("No styles available after filtering")

    primary, ranked = resolve_primary_style(styles, args.query, args.style)
    alternatives = [
        {
            "slug": item["style"].get("slug"),
            "name": item["style"].get("name"),
            "nameEn": item["style"].get("nameEn"),
            "score": round(item["score"], 4),
            "styleType": item["style"].get("styleType"),
        }
        for item in ranked
        if item["style"].get("slug") != primary.get("slug")
    ][:2]

    lang = detect_lang(args.query)
    raw_reference_payload = load_reference_payload(args.reference_json, args.reference_file)
    schema_validation = validate_reference_payload_schema(
        payload=raw_reference_payload,
        reference_type=args.reference_type,
        lang=lang,
        strict_mode=args.strict_reference_schema,
    )
    if not schema_validation.get("valid"):
        joined = "; ".join(schema_validation.get("errors", []))
        raise SystemExit(f"Reference schema validation failed: {joined}")
    reference_payload = schema_validation.get("sanitized_payload", {})
    effective_reference_type = args.reference_type
    if effective_reference_type == "none" and reference_payload:
        source_hint = str(reference_payload.get("source", "") or reference_payload.get("type", "")).lower()
        if "figma" in source_hint and any(k in source_hint for k in ["screen", "shot", "截图"]):
            effective_reference_type = "mixed"
        elif "figma" in source_hint:
            effective_reference_type = "figma"
        elif any(k in source_hint for k in ["screen", "shot", "screenshot", "截图"]):
            effective_reference_type = "screenshot"
        else:
            effective_reference_type = "mixed"

    reference_signals = normalize_reference_signals(
        payload=reference_payload,
        reference_type=effective_reference_type,
        reference_notes=args.reference_notes,
        lang=lang,
    )

    base_rules = extract_rules(primary.get("aiRules", ""), lang)
    base_rules.extend(reference_signals.get("derived_rules", []))
    ai_rules = ensure_min_rules(base_rules, primary.get("doList", []), primary.get("dontList", []), lang)
    ai_rules = resolve_rule_conflicts(ai_rules, lang)
    ai_rules = ensure_rule_floor(ai_rules, lang, min_count=3)
    ai_rules = resolve_rule_conflicts(ai_rules, lang)
    ai_rules = ensure_rule_floor(ai_rules, lang, min_count=3)[:8]
    component_guidelines = build_component_guidelines(primary, lang)
    interaction_rules = build_interaction_rules(ai_rules, lang)

    stack_hint = STACK_HINTS.get(args.stack, STACK_HINTS["html-tailwind"])[lang]
    alt_full = [item for item in ranked if item["style"].get("slug") != primary.get("slug")][:2]
    auto_blend = args.blend_mode == "on" or (args.blend_mode == "auto" and len(alt_full) > 0)
    blend_plan = build_blend_plan(primary, alt_full if auto_blend else [], args.query, lang)
    intent = infer_design_intent(args.query, lang)
    anti_generic = anti_generic_constraints(lang)
    system_structure = design_system_structure(args.stack, lang)
    refine_strategy = refine_mode_strategy(args.refine_mode, lang)
    reference_guidelines = build_reference_guidelines(effective_reference_type, lang)

    design_brief = {
        "style_choice": {
            "primary": {
                "slug": primary.get("slug"),
                "name": primary.get("name"),
                "nameEn": primary.get("nameEn"),
                "styleType": primary.get("styleType"),
            },
            "alternatives": alternatives,
            "why": (
                "主要匹配关键词、标签和规则语义重合度。" if lang == "zh" else "Selected from strongest overlap in keywords, tags, and rule semantics."
            ),
        },
        "visual_direction": localized_visual_direction(primary, lang),
        "typography_strategy": (
            "通过标题与正文层级拉开信息节奏，保持风格统一。" if lang == "zh" else "Use clear heading/body hierarchy to maintain consistent visual rhythm."
        ),
        "color_strategy": {
            "primary": primary.get("colors", {}).get("primary"),
            "secondary": primary.get("colors", {}).get("secondary"),
            "accent": primary.get("colors", {}).get("accent", []),
        },
        "component_guidelines": component_guidelines,
        "interaction_rules": interaction_rules,
        "a11y_baseline": A11Y_BASELINE[lang],
        "font_strategy_hints": DISTINCTIVE_FONT_HINTS[lang],
        "design_intent": intent,
        "anti_generic_constraints": anti_generic,
        "validation_tests": VALIDATION_TESTS[lang],
        "anti_pattern_blacklist": ANTI_PATTERN_BLACKLIST[lang],
        "design_system_structure": system_structure,
        "refine_mode": args.refine_mode,
        "iteration_strategy": refine_strategy,
        "input_context": {
            "reference_type": effective_reference_type,
            "reference_notes": args.reference_notes.strip(),
            "reference_file": args.reference_file.strip(),
            "reference_payload_present": bool(reference_payload),
            "reference_schema_validation": {
                "valid": schema_validation.get("valid"),
                "strict_mode": schema_validation.get("strict_mode"),
                "errors": schema_validation.get("errors", []),
                "warnings": schema_validation.get("warnings", []),
                "coercions": schema_validation.get("coercions", []),
                "unknown_fields": schema_validation.get("unknown_fields", []),
            },
            "reference_guidelines": reference_guidelines,
            "reference_signal_summary": reference_signals.get("summary", ""),
            "reference_signals": reference_signals.get("signals", {}),
            "reference_derived_rules": reference_signals.get("derived_rules", []),
        },
        "stack_hint": stack_hint,
        "blend_plan": blend_plan,
    }

    hard_prompt = ""
    soft_prompt = ""
    if args.mode == "brief+prompt":
        hard_prompt, soft_prompt = make_prompts(
            args.query,
            primary,
            ai_rules,
            args.stack,
            lang,
            blend_plan,
            intent,
            anti_generic,
            args.refine_mode,
            effective_reference_type,
            args.reference_notes,
            reference_signals,
        )

    output = {
        "query": args.query,
        "mode": args.mode,
        "language": lang,
        "style_choice": design_brief["style_choice"],
        "design_brief": design_brief,
        "ai_rules": ai_rules,
        "hard_prompt": hard_prompt,
        "soft_prompt": soft_prompt,
        "candidate_rank": [
            {
                "slug": item["style"].get("slug"),
                "nameEn": item["style"].get("nameEn"),
                "score": round(item["score"], 4),
            }
            for item in ranked[:5]
        ],
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

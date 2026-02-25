"""Shared constants and tiny utilities for the generate_brief module family."""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Stack hints
# ---------------------------------------------------------------------------

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
for _alias_items in REFERENCE_FIELD_ALIASES.values():
    REFERENCE_KNOWN_TOP_LEVEL.update(_alias_items)

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
    "绝对禁止", "禁止使用", "禁止",
    "must avoid", "must not", "forbidden", "absolutely forbidden", "do not",
]
POS_SECTION_MARKERS = [
    "必须遵守", "必须使用", "必须",
    "must follow", "must use", "required",
]
RADIUS_TOKEN_RE = re.compile(r"\brounded(?:-[a-z0-9]+)?\b", re.IGNORECASE)
SHADOW_TOKEN_RE = re.compile(r"\bshadow(?:-[a-z0-9\[\]_/.-]+)?\b", re.IGNORECASE)
BG_WHITE_TOKEN_RE = re.compile(r"\bbg-white(?:/[0-9]{1,3})?\b", re.IGNORECASE)
BG_BLACK_TOKEN_RE = re.compile(r"\bbg-black(?:/[0-9]{1,3})?\b", re.IGNORECASE)

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


# ---------------------------------------------------------------------------
# Shared tiny utilities (used by multiple sub-modules)
# ---------------------------------------------------------------------------

def detect_lang(text: str) -> str:
    return "zh" if re.search(r"[\u4e00-\u9fff]", text) else "en"


def has_cjk(text: str) -> bool:
    return bool(CJK_RE.search(text or ""))


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

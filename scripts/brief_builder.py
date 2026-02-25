"""Design brief building: visual direction, component guidelines, and intent."""

from __future__ import annotations

from typing import Any

from _brief_constants import has_cjk


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


def build_component_guidelines(
    style: dict[str, Any],
    lang: str,
    interaction_pattern_data: dict[str, Any] | None = None,
) -> list[str]:
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

    if interaction_pattern_data:
        required = interaction_pattern_data.get("required_components", [])
        existing_lower = " ".join(guidelines).lower()
        missing = [c for c in required if c.lower() not in existing_lower]
        if missing:
            if lang == "zh":
                guidelines.append(f"交互模式要求组件：{', '.join(missing[:4])}——确保已纳入页面结构。")
            else:
                guidelines.append(f"Interaction pattern requires: {', '.join(missing[:4])} — ensure these are included in the page structure.")

    return guidelines[:6]


def build_interaction_rules(
    ai_rules: list[str],
    lang: str,
    interaction_pattern_data: dict[str, Any] | None = None,
) -> list[str]:
    keywords = ["hover", "active", "focus", "transition", "animation", "motion", "交互", "悬停", "点击", "焦点", "动画"]
    selected = [rule for rule in ai_rules if any(word in rule.lower() for word in keywords)]

    if interaction_pattern_data and len(selected) < 3:
        a11y = interaction_pattern_data.get("accessibility_constraints", [])
        if a11y:
            selected.extend(a11y[:3])

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
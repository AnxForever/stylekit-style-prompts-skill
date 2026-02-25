"""Multi-style blend planning: scoring, ownership, and directive generation."""

from __future__ import annotations

from typing import Any

from search_stylekit import expand_query_tokens, tokenize


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

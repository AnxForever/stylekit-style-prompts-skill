#!/usr/bin/env python3
"""One-shot pipeline: search -> brief/prompt -> QA."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from _common import __version__, normalize_text
from v2_taxonomy import (
    CONTENT_DEPTH_CHOICES,
    DECISION_SPEED_CHOICES,
    RECOMMENDATION_MODE_CHOICES,
    SITE_TYPES,
    build_upgrade_candidates,
)
import search_stylekit
import generate_brief
import qa_prompt as qa_prompt_mod


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


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def normalize_sum(weights: dict[str, float]) -> dict[str, float]:
    total = sum(max(v, 0.0) for v in weights.values()) or 1.0
    return {k: round(max(v, 0.0) / total, 4) for k, v in weights.items()}


def infer_decision_priorities(product_type: str, query: str, tag_bundle: dict[str, Any], zh: bool) -> dict[str, Any]:
    base_by_type: dict[str, dict[str, float]] = {
        "dashboard": {
            "readability": 0.32,
            "conversion": 0.08,
            "brand_expression": 0.1,
            "motion_richness": 0.08,
            "layout_fitness": 0.24,
            "implementation_safety": 0.18,
        },
        "docs": {
            "readability": 0.35,
            "conversion": 0.05,
            "brand_expression": 0.07,
            "motion_richness": 0.06,
            "layout_fitness": 0.24,
            "implementation_safety": 0.23,
        },
        "saas": {
            "readability": 0.24,
            "conversion": 0.2,
            "brand_expression": 0.14,
            "motion_richness": 0.1,
            "layout_fitness": 0.2,
            "implementation_safety": 0.12,
        },
        "landing-page": {
            "readability": 0.14,
            "conversion": 0.31,
            "brand_expression": 0.24,
            "motion_richness": 0.14,
            "layout_fitness": 0.1,
            "implementation_safety": 0.07,
        },
        "ecommerce": {
            "readability": 0.16,
            "conversion": 0.32,
            "brand_expression": 0.18,
            "motion_richness": 0.12,
            "layout_fitness": 0.12,
            "implementation_safety": 0.1,
        },
        "portfolio": {
            "readability": 0.1,
            "conversion": 0.08,
            "brand_expression": 0.35,
            "motion_richness": 0.23,
            "layout_fitness": 0.14,
            "implementation_safety": 0.1,
        },
        "blog": {
            "readability": 0.31,
            "conversion": 0.08,
            "brand_expression": 0.2,
            "motion_richness": 0.1,
            "layout_fitness": 0.18,
            "implementation_safety": 0.13,
        },
    }
    weights = dict(
        base_by_type.get(
            product_type,
            {
                "readability": 0.22,
                "conversion": 0.16,
                "brand_expression": 0.2,
                "motion_richness": 0.12,
                "layout_fitness": 0.18,
                "implementation_safety": 0.12,
            },
        )
    )
    q = normalize_text(query)
    modifiers = [normalize_text(x) for x in (tag_bundle.get("modifiers", []) or [])]

    if any(k in q for k in ("readability", "readable", "可读", "信息密度", "文档", "docs")) or "readability-first" in modifiers:
        weights["readability"] += 0.08
        weights["implementation_safety"] += 0.04
    if any(k in q for k in ("conversion", "cta", "注册", "购买", "转化", "checkout")) or "conversion-first" in modifiers:
        weights["conversion"] += 0.1
    if any(k in q for k in ("brand", "premium", "高端", "品牌", "记忆点")) or "brand-heavy" in modifiers:
        weights["brand_expression"] += 0.09
    if any(k in q for k in ("motion", "animation", "动效", "交互", "transition")):
        weights["motion_richness"] += 0.08
    if any(k in q for k in ("layout", "grid", "sidebar", "布局", "网格", "结构")):
        weights["layout_fitness"] += 0.08
    if product_type in {"dashboard", "docs"} and "high-contrast" in modifiers:
        weights["implementation_safety"] += 0.05
        weights["readability"] += 0.05

    normalized = normalize_sum(weights)
    top_key = sorted(normalized.items(), key=lambda kv: kv[1], reverse=True)[0][0]
    label_map = {
        "readability": "可读性优先" if zh else "readability-first",
        "conversion": "转化优先" if zh else "conversion-first",
        "brand_expression": "品牌表达优先" if zh else "brand-expression-first",
        "motion_richness": "动效表现优先" if zh else "motion-richness-first",
        "layout_fitness": "布局结构优先" if zh else "layout-fitness-first",
        "implementation_safety": "实现稳健优先" if zh else "implementation-safety-first",
    }
    return {
        "weights": normalized,
        "top_priority": top_key,
        "top_priority_label": label_map.get(top_key, top_key),
    }


def axis_score(
    tags: set[str],
    positives: set[str],
    negatives: set[str],
    base: float = 0.45,
    hit_gain: float = 0.12,
    miss_penalty: float = 0.1,
) -> float:
    pos_hits = len(tags & positives)
    neg_hits = len(tags & negatives)
    raw = base + pos_hits * hit_gain - neg_hits * miss_penalty
    return round(clamp(raw), 4)


def candidate_tag_set(candidate: dict[str, Any]) -> set[str]:
    tags: set[str] = set()
    preview = candidate.get("preview", {}) or {}
    reason = candidate.get("reason", {}) or {}
    for item in preview.get("tags", []):
        key = normalize_text(item)
        if key:
            tags.add(key)
    for item in preview.get("keywords", []):
        key = normalize_text(item)
        if key:
            tags.add(key)
    style_type = normalize_text(candidate.get("styleType"))
    if style_type:
        tags.add(style_type)
    reason_text = normalize_text(candidate.get("reason_summary", ""))
    for part in reason_text.replace(";", " ").replace(",", " ").split():
        if part:
            tags.add(part)
    route_details = reason.get("site_route_details", {}) or {}
    for item in route_details.get("favored_hits", []):
        key = normalize_text(item)
        if key:
            tags.add(key)
    return tags


def build_candidate_scorecard(
    candidate: dict[str, Any],
    priorities: dict[str, float],
    product_type: str,
    zh: bool,
) -> dict[str, Any]:
    tags = candidate_tag_set(candidate)
    stype = normalize_text(candidate.get("styleType"))
    reason = candidate.get("reason", {}) or {}
    route_adj = float(reason.get("site_type_adjustment", 0.0) or 0.0)
    route_fit = clamp((route_adj + 5.0) / 10.0)

    readability_fit = axis_score(
        tags,
        positives={"minimal", "clean", "readable", "dashboard", "docs", "corporate", "editorial", "neutral", "professional"},
        negatives={"expressive", "high-contrast", "neon", "glitch", "chaotic"},
        base=0.46,
    )
    conversion_fit = axis_score(
        tags,
        positives={"ecommerce", "conversion", "marketing", "landing", "hero", "cta", "product", "pricing", "brand"},
        negatives={"docs", "documentation", "article", "longform"},
        base=0.44,
    )
    brand_fit = axis_score(
        tags,
        positives={"expressive", "premium", "editorial", "retro", "modern", "glass", "luxury", "visual", "creative"},
        negatives={"generic", "plain"},
        base=0.45,
    )
    motion_fit = axis_score(
        tags,
        positives={"expressive", "playful", "motion", "animation", "dynamic", "neon", "glass"},
        negatives={"minimal", "docs", "enterprise"},
        base=0.42,
    )
    layout_fit = axis_score(
        tags,
        positives={"layout", "grid", "dashboard", "sidebar", "timeline", "table", "kpi", "doc"},
        negatives={"unstyled"},
        base=0.43,
    )
    implementation_safety = axis_score(
        tags,
        positives={"clean", "minimal", "corporate", "dashboard", "docs", "readable", "responsive"},
        negatives={"glitch", "neon", "high-contrast", "anti-design"},
        base=0.48,
    )

    if stype == "layout":
        layout_fit = round(clamp(layout_fit + 0.2), 4)
        if product_type in {"dashboard", "docs", "saas"}:
            readability_fit = round(clamp(readability_fit + 0.07), 4)
    if stype == "visual" and product_type in {"landing-page", "portfolio"}:
        brand_fit = round(clamp(brand_fit + 0.08), 4)
        motion_fit = round(clamp(motion_fit + 0.05), 4)

    risk_penalty = 0.06
    complexity = "standard"
    if "expressive" in tags or "high-contrast" in tags:
        complexity = "advanced"
        risk_penalty = 0.16
    elif "minimal" in tags or stype == "layout":
        complexity = "beginner-friendly"
        risk_penalty = 0.03
    if priorities.get("readability", 0.0) >= 0.25 and ("expressive" in tags or "high-contrast" in tags):
        risk_penalty += 0.05

    weighted = (
        readability_fit * priorities.get("readability", 0.0)
        + conversion_fit * priorities.get("conversion", 0.0)
        + brand_fit * priorities.get("brand_expression", 0.0)
        + motion_fit * priorities.get("motion_richness", 0.0)
        + layout_fit * priorities.get("layout_fitness", 0.0)
        + implementation_safety * priorities.get("implementation_safety", 0.0)
    )
    decision_score = round(clamp(weighted + route_fit * 0.08 - risk_penalty * 0.5), 4)

    highlights: list[str] = []
    if readability_fit >= 0.65:
        highlights.append("可读性强" if zh else "strong readability")
    if conversion_fit >= 0.65:
        highlights.append("转化导向明确" if zh else "clear conversion orientation")
    if brand_fit >= 0.65:
        highlights.append("品牌辨识度高" if zh else "high brand distinctiveness")
    if layout_fit >= 0.65:
        highlights.append("结构组织能力强" if zh else "strong layout structure")
    if motion_fit >= 0.65:
        highlights.append("动效表达能力强" if zh else "strong motion expression")
    if not highlights:
        highlights.append("整体均衡" if zh else "balanced profile")

    tradeoffs: list[str] = []
    if risk_penalty >= 0.14:
        tradeoffs.append("实现复杂度偏高" if zh else "higher implementation complexity")
    if readability_fit < 0.5 and product_type in {"dashboard", "docs", "blog"}:
        tradeoffs.append("信息密度场景可读性风险" if zh else "readability risk in dense-information scenarios")
    if conversion_fit < 0.45 and product_type in {"landing-page", "ecommerce", "saas"}:
        tradeoffs.append("转化导向偏弱" if zh else "weaker conversion orientation")
    if not tradeoffs:
        tradeoffs.append("无明显短板" if zh else "no obvious downside")

    return {
        "slug": candidate.get("slug"),
        "name": candidate.get("name"),
        "nameEn": candidate.get("nameEn"),
        "styleType": candidate.get("styleType"),
        "decision_score": decision_score,
        "route_fit": round(route_fit, 4),
        "complexity": complexity,
        "risk_penalty": round(risk_penalty, 4),
        "score_breakdown": {
            "readability_fit": readability_fit,
            "conversion_fit": conversion_fit,
            "brand_expression_fit": brand_fit,
            "motion_fit": motion_fit,
            "layout_fit": layout_fit,
            "implementation_safety": implementation_safety,
        },
        "highlights": highlights[:3],
        "tradeoffs": tradeoffs[:3],
        "reason_summary": candidate.get("reason_summary"),
    }


def build_ai_iteration_prompts(
    *,
    query: str,
    product_type: str,
    top_slugs: list[str],
    top_priority_label: str,
    stack: str,
    zh: bool,
) -> dict[str, str]:
    s1 = top_slugs[0] if top_slugs else ""
    s2 = top_slugs[1] if len(top_slugs) > 1 else s1
    if zh:
        return {
            "analyze_options_prompt": (
                f"请以 `{product_type}` 场景评估 `{s1}` 与 `{s2}`，重点围绕 `{top_priority_label}`。"
                "输出：优点、风险、适用边界、建议取舍。"
            ),
            "stress_test_prompt": (
                f"请对 `{s1}` 做压力测试：信息密度、可访问性、移动端和性能四个维度逐项挑错，并给最小修复方案。"
            ),
            "merge_prompt": (
                f"请基于 `{s1}` 为主、`{s2}` 为辅，给出可执行的融合规则（色彩/排版/布局/动效所有权）并避免冲突。"
            ),
            "v1_enrichment_prompt": (
                f"请在 `{stack}` 技术栈下，把首版从骨架补全为可演示版本，必须包含 empty/loading/error/focus-visible 状态。"
            ),
        }
    return {
        "analyze_options_prompt": (
            f"Compare `{s1}` vs `{s2}` for a `{product_type}` use case with `{top_priority_label}` as the main objective. "
            "Output pros, risks, boundaries, and recommendation."
        ),
        "stress_test_prompt": (
            f"Stress-test `{s1}` across information density, accessibility, mobile behavior, and performance; give minimal fixes."
        ),
        "merge_prompt": (
            f"Use `{s1}` as base and `{s2}` as support, then define conflict-free ownership for color/typography/layout/motion."
        ),
        "v1_enrichment_prompt": (
            f"For `{stack}`, expand the first version from skeleton to demo-ready with empty/loading/error/focus-visible states."
        ),
    }


def build_decision_matrix(
    *,
    search_payload: dict[str, Any],
    style_options: list[dict[str, Any]],
    product_type: str,
    query: str,
    tag_bundle: dict[str, Any],
    selected_style: str | None,
    stack: str,
    zh: bool,
) -> dict[str, Any]:
    priorities_meta = infer_decision_priorities(product_type, query, tag_bundle, zh)
    priorities = priorities_meta["weights"]
    option_id_by_slug = {item.get("slug"): item.get("option_id") for item in style_options}

    cards = []
    for candidate in search_payload.get("candidates", [])[:5]:
        card = build_candidate_scorecard(candidate, priorities, product_type, zh)
        card["option_id"] = option_id_by_slug.get(card["slug"])
        cards.append(card)

    cards.sort(key=lambda item: item.get("decision_score", 0.0), reverse=True)
    if cards:
        cards[0]["recommended"] = True
    if len(cards) > 1:
        gap = round(cards[0]["decision_score"] - cards[1]["decision_score"], 4)
    else:
        gap = 0.2

    confidence = "high" if gap >= 0.12 else ("medium" if gap >= 0.06 else "low")
    if selected_style:
        for card in cards:
            card["is_selected_style"] = card.get("slug") == selected_style

    top_slugs = [card.get("slug", "") for card in cards[:2]]
    ai_prompts = build_ai_iteration_prompts(
        query=query,
        product_type=product_type,
        top_slugs=top_slugs,
        top_priority_label=priorities_meta.get("top_priority_label", ""),
        stack=stack,
        zh=zh,
    )

    primary = cards[0] if cards else {}
    backup = cards[1] if len(cards) > 1 else {}
    return {
        "decision_priorities": priorities_meta,
        "candidate_scorecards": cards,
        "primary_recommendation": {
            "slug": primary.get("slug"),
            "option_id": primary.get("option_id"),
            "decision_score": primary.get("decision_score"),
            "confidence": confidence,
            "highlights": primary.get("highlights", []),
            "tradeoffs": primary.get("tradeoffs", []),
        },
        "backup_recommendation": {
            "slug": backup.get("slug"),
            "option_id": backup.get("option_id"),
            "decision_score": backup.get("decision_score"),
            "highlights": backup.get("highlights", []),
            "tradeoffs": backup.get("tradeoffs", []),
        }
        if backup
        else {},
        "recommendation_gap": gap,
        "quick_lock_rule": (
            "直接选择主推荐；仅当你更看重备选的单项优势时再切换。"
            if zh
            else "Pick primary by default; switch only when backup better matches your single top concern."
        ),
        "ai_iteration_prompts": ai_prompts,
    }


def build_adaptive_decision_questions(
    *,
    product_type: str,
    decision_matrix: dict[str, Any],
    zh: bool,
) -> list[dict[str, Any]]:
    priorities = (decision_matrix.get("decision_priorities", {}) or {}).get("weights", {}) or {}
    sorted_axes = sorted(priorities.items(), key=lambda kv: kv[1], reverse=True)
    top_axis = sorted_axes[0][0] if sorted_axes else "readability"
    second_axis = sorted_axes[1][0] if len(sorted_axes) > 1 else "brand_expression"
    axis_name_zh = {
        "readability": "可读性",
        "conversion": "转化",
        "brand_expression": "品牌表达",
        "motion_richness": "动效表现",
        "layout_fitness": "布局结构",
        "implementation_safety": "实现稳健性",
    }
    axis_name_en = {
        "readability": "readability",
        "conversion": "conversion",
        "brand_expression": "brand expression",
        "motion_richness": "motion richness",
        "layout_fitness": "layout fitness",
        "implementation_safety": "implementation safety",
    }

    if zh:
        questions = [
            {
                "id": "primary_goal",
                "question": f"这版优先保证哪一项？",
                "choices": [
                    f"{axis_name_zh.get(top_axis, top_axis)}优先",
                    f"{axis_name_zh.get(second_axis, second_axis)}优先",
                    "两者平衡",
                ],
                "recommended": f"{axis_name_zh.get(top_axis, top_axis)}优先",
            },
            {
                "id": "risk_tolerance",
                "question": "你对实现复杂度的容忍度？",
                "choices": ["低（先稳）", "中（可接受）", "高（追求表现）"],
                "recommended": "中（可接受）" if product_type in {"landing-page", "portfolio"} else "低（先稳）",
            },
            {
                "id": "motion_intensity",
                "question": "动效强度希望如何？",
                "choices": ["克制", "中等", "明显"],
                "recommended": "克制" if product_type in {"dashboard", "docs", "blog"} else "中等",
            },
        ]
        if product_type in {"landing-page", "ecommerce", "saas"}:
            questions.append(
                {
                    "id": "conversion_strategy",
                    "question": "转化策略更偏向哪种？",
                    "choices": ["强 CTA 直接驱动", "信息说服为主", "品牌先行再转化"],
                    "recommended": "信息说服为主" if product_type == "saas" else "强 CTA 直接驱动",
                }
            )
        return questions

    questions = [
        {
            "id": "primary_goal",
            "question": "What should be the top priority for this iteration?",
            "choices": [
                f"{axis_name_en.get(top_axis, top_axis)} first",
                f"{axis_name_en.get(second_axis, second_axis)} first",
                "balanced",
            ],
            "recommended": f"{axis_name_en.get(top_axis, top_axis)} first",
        },
        {
            "id": "risk_tolerance",
            "question": "How much implementation complexity can we tolerate?",
            "choices": ["low", "medium", "high"],
            "recommended": "medium" if product_type in {"landing-page", "portfolio"} else "low",
        },
        {
            "id": "motion_intensity",
            "question": "Preferred motion intensity?",
            "choices": ["minimal", "moderate", "noticeable"],
            "recommended": "minimal" if product_type in {"dashboard", "docs", "blog"} else "moderate",
        },
    ]
    if product_type in {"landing-page", "ecommerce", "saas"}:
        questions.append(
            {
                "id": "conversion_strategy",
                "question": "Which conversion strategy should lead?",
                "choices": ["CTA-led", "information-led", "brand-led then convert"],
                "recommended": "information-led" if product_type == "saas" else "CTA-led",
            }
        )
    return questions


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


def build_next_step_templates(
    style_options: list[dict[str, Any]],
    query: str,
    stack: str,
    zh: bool,
    site_type: str,
    content_depth: str,
    forced_style: str | None = None,
) -> dict[str, Any]:
    selected = forced_style or (style_options[0]["slug"] if style_options else "")
    command = (
        f'python scripts/run_pipeline.py --workflow codegen --query "{query}" --stack {stack} --style {selected} '
        f"--site-type {site_type} --content-depth {content_depth} --recommendation-mode hybrid --decision-speed fast --blend-mode off --format json"
    )
    if zh:
        return {
            "after_user_selects_style": command,
            "assistant_script": "先展示 3-4 个风格选项并解释差异，用户选择后再进入代码生成。",
        }
    return {
        "after_user_selects_style": command,
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
    style_choice = brief_payload.get("style_choice", {}) or design_brief.get("style_choice", {}) or {}
    site_profile = design_brief.get("site_profile", {}) or {}
    decision_flow = design_brief.get("decision_flow", {}) or brief_payload.get("decision_flow", {}) or {}
    content_plan = design_brief.get("content_plan", {}) or brief_payload.get("content_plan", {}) or {}
    tag_bundle = design_brief.get("tag_bundle", {}) or brief_payload.get("tag_bundle", {}) or {}
    composition_plan = design_brief.get("composition_plan", {}) or brief_payload.get("composition_plan", {}) or {}
    zh = is_zh(query)
    product_type = site_profile.get("site_type") or infer_product_type(query)
    content_depth = content_plan.get("content_depth", "skeleton")
    style_options = build_style_options(search_payload, product_type=product_type, zh=zh)
    decision_matrix = build_decision_matrix(
        search_payload=search_payload,
        style_options=style_options,
        product_type=product_type,
        query=query,
        tag_bundle=tag_bundle,
        selected_style=selected_style,
        stack=stack,
        zh=zh,
    )
    decision_questions = build_adaptive_decision_questions(
        product_type=product_type,
        decision_matrix=decision_matrix,
        zh=zh,
    )
    legacy_questions = build_decision_questions(product_type=product_type, zh=zh)
    primary_slug = (decision_matrix.get("primary_recommendation", {}) or {}).get("slug")
    next_step_templates = build_next_step_templates(
        style_options=style_options,
        query=query,
        stack=stack,
        zh=zh,
        site_type=product_type,
        content_depth=content_depth,
        forced_style=selected_style or primary_slug,
    )
    conversation_flow = build_cc_conversation_flow(zh=zh)

    return {
        "purpose": "Use this as a frontend design handbook context before generating code.",
        "product_profile": {
            "query": query,
            "inferred_product_type": product_type,
            "site_profile": site_profile,
            "user_confidence": infer_user_confidence(query),
            "stack": stack,
            "purpose": design_intent.get("purpose"),
            "audience": design_intent.get("audience"),
            "tone": design_intent.get("tone"),
        },
        "decision_assistant": {
            "recommended_style_options": style_options,
            "decision_questions": decision_questions,
            "legacy_decision_questions": legacy_questions,
            "next_step_templates": next_step_templates,
            "cc_conversation_flow": conversation_flow,
            "decision_flow_v2": decision_flow,
            "decision_matrix": decision_matrix,
            "primary_recommendation": decision_matrix.get("primary_recommendation", {}),
            "backup_recommendation": decision_matrix.get("backup_recommendation", {}),
            "ai_iteration_prompts": decision_matrix.get("ai_iteration_prompts", {}),
        },
        "style_recommendation": {
            "selected_style": selected_style,
            "primary": style_choice.get("primary", {}),
            "alternatives": style_choice.get("alternatives", []),
            "top_candidates": search_payload.get("candidates", [])[:5],
            "tag_bundle": tag_bundle,
        },
        "implementation_handbook": {
            "component_guidelines": design_brief.get("component_guidelines", []),
            "interaction_rules": design_brief.get("interaction_rules", []),
            "a11y_baseline": design_brief.get("a11y_baseline", []),
            "anti_pattern_blacklist": design_brief.get("anti_pattern_blacklist", [])[:8],
            "validation_tests": design_brief.get("validation_tests", []),
            "content_plan": content_plan,
            "composition_plan": composition_plan,
            "recommended_first_style": primary_slug or selected_style,
        },
    }




def to_markdown(payload: dict[str, Any]) -> str:
    blend = payload.get("result", {}).get("design_brief", {}).get("blend_plan", {})
    site_profile = payload.get("site_profile", {}) or payload.get("result", {}).get("site_profile", {})
    tag_bundle = payload.get("tag_bundle", {}) or payload.get("result", {}).get("tag_bundle", {})
    content_plan = payload.get("content_plan", {}) or payload.get("result", {}).get("content_plan", {})
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
        f"- Site type: {site_profile.get('site_type', '')}",
        f"- Layout archetype: {tag_bundle.get('layout_archetype', '')}",
        f"- Motion profile: {tag_bundle.get('motion_profile', '')}",
        f"- Content depth: {content_plan.get('content_depth', '')}",
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
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--query", required=True, help="User requirement")
    parser.add_argument(
        "--workflow",
        default="manual",
        choices=["manual", "codegen"],
        help="manual = handbook/knowledge mode, codegen = prompt-generation mode",
    )
    parser.add_argument("--site-type", default="auto", choices=["auto", *SITE_TYPES])
    parser.add_argument("--stack", default="html-tailwind", choices=["html-tailwind", "react", "nextjs", "vue", "svelte", "tailwind-v4"])
    parser.add_argument("--style", help="Force style slug")
    parser.add_argument("--style-type", choices=["visual", "layout", "animation"])
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--mode", default=None, choices=["brief-only", "brief+prompt"])
    parser.add_argument("--recommendation-mode", default="hybrid", choices=RECOMMENDATION_MODE_CHOICES)
    parser.add_argument("--content-depth", default="skeleton", choices=CONTENT_DEPTH_CHOICES)
    parser.add_argument("--decision-speed", default="fast", choices=DECISION_SPEED_CHOICES)
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

    resolved_mode = args.mode or ("brief-only" if args.workflow == "manual" else "brief+prompt")
    resolved_blend_mode = args.blend_mode or ("off" if args.workflow == "manual" else "auto")
    if args.style:
        # Explicit style selection always disables blending to avoid mixed ownership.
        resolved_blend_mode = "off"

    search_payload = search_stylekit.run(
        query=args.query,
        top=args.top,
        style_type=args.style_type,
        site_type=args.site_type,
    )

    brief_payload = generate_brief.run(
        query=args.query,
        style=args.style or None,
        site_type=args.site_type,
        stack=args.stack,
        mode=resolved_mode,
        recommendation_mode=args.recommendation_mode,
        content_depth=args.content_depth,
        decision_speed=args.decision_speed,
        blend_mode=resolved_blend_mode,
        refine_mode=args.refine_mode,
        reference_type=args.reference_type,
        reference_notes=args.reference_notes.strip(),
        reference_file=args.reference_file.strip(),
        reference_json=args.reference_json.strip(),
        strict_reference_schema=args.strict_reference_schema,
        style_type=args.style_type,
    )
    selected_style = args.style or (brief_payload.get("style_choice", {}).get("primary", {}) or {}).get("slug")
    resolved_reference_type = (
        brief_payload.get("design_brief", {}).get("input_context", {}).get("reference_type") or args.reference_type
    )
    reference_payload_present = bool(
        brief_payload.get("design_brief", {}).get("input_context", {}).get("reference_payload_present")
    )
    reference_has_signals = bool(
        brief_payload.get("design_brief", {}).get("input_context", {}).get("reference_has_signals")
    )

    qa_payload: dict[str, Any]
    if resolved_mode == "brief+prompt":
        qa_input_text = brief_payload.get("hard_prompt") or brief_payload.get("soft_prompt")
        if not qa_input_text:
            qa_input_text = json.dumps(brief_payload, ensure_ascii=False)

        expected_lang = brief_payload.get("language")
        qa_payload = qa_prompt_mod.run(
            text=qa_input_text,
            min_ai_rules=args.min_ai_rules,
            lang=expected_lang if expected_lang in {"en", "zh"} else None,
            require_refine_mode=args.refine_mode,
            require_reference_type=resolved_reference_type,
            require_reference_signals=reference_payload_present and reference_has_signals,
            style=selected_style or None,
        )
    else:
        qa_payload = {
            "status": "pass",
            "violations": [],
            "autofix_suggestions": [],
            "warnings": [
                {
                    "code": "QA_SKIPPED_BRIEF_ONLY",
                    "message": "Prompt QA skipped in handbook mode (brief-only).",
                }
            ],
            "checks": [],
            "meta": {
                "style": selected_style,
                "expected_lang": brief_payload.get("language"),
                "min_ai_rules": args.min_ai_rules,
                "prompt_length": 0,
                "source_kind": "brief-only",
                "source_field": None,
                "prompt_field_preferred": "hard_prompt",
                "required_refine_mode": None,
                "required_reference_type": resolved_reference_type,
                "require_reference_signals": False,
            },
        }

    manual_assistant = build_manual_assistant(
        query=args.query,
        stack=args.stack,
        selected_style=selected_style,
        search_payload=search_payload,
        brief_payload=brief_payload,
    )
    site_profile = (
        brief_payload.get("site_profile")
        or brief_payload.get("design_brief", {}).get("site_profile")
        or search_payload.get("site_profile")
        or {}
    )
    tag_bundle = (
        brief_payload.get("tag_bundle")
        or brief_payload.get("design_brief", {}).get("tag_bundle")
        or {}
    )
    composition_plan = (
        brief_payload.get("composition_plan")
        or brief_payload.get("design_brief", {}).get("composition_plan")
        or {}
    )
    decision_flow = (
        brief_payload.get("decision_flow")
        or brief_payload.get("design_brief", {}).get("decision_flow")
        or {}
    )
    content_plan = (
        brief_payload.get("content_plan")
        or brief_payload.get("design_brief", {}).get("content_plan")
        or {}
    )
    upgrade_candidates = build_upgrade_candidates(
        query=args.query,
        site_type=site_profile.get("site_type", "general"),
        selected_style=selected_style or "",
        tag_bundle=tag_bundle,
        quality_gate=qa_payload,
    )

    output = {
        "schemaVersion": "2.0.0",
        "status": qa_payload.get("status"),
        "workflow": args.workflow,
        "mode": resolved_mode,
        "query": args.query,
        "site_type": args.site_type,
        "stack": args.stack,
        "style_type_filter": args.style_type,
        "recommendation_mode": args.recommendation_mode,
        "content_depth": args.content_depth,
        "decision_speed": args.decision_speed,
        "blend_mode": resolved_blend_mode,
        "refine_mode": args.refine_mode,
        "reference_type": resolved_reference_type,
        "strict_reference_schema": args.strict_reference_schema,
        "selected_style": selected_style,
        "site_profile": site_profile,
        "tag_bundle": tag_bundle,
        "composition_plan": composition_plan,
        "decision_flow": decision_flow,
        "content_plan": content_plan,
        "candidates": search_payload.get("candidates", []),
        "result": brief_payload,
        "manual_assistant": manual_assistant,
        "quality_gate": qa_payload,
        "upgrade_candidates": upgrade_candidates,
    }

    if args.format == "markdown":
        print(to_markdown(output))
    else:
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

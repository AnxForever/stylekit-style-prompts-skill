#!/usr/bin/env python3
"""V2 taxonomy helpers for site-type routing and composition planning."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from _common import STOPWORDS, load_json, normalize_text, now_iso, tokenize

SITE_TYPES = (
    "blog",
    "saas",
    "dashboard",
    "docs",
    "ecommerce",
    "landing-page",
    "portfolio",
    "general",
)

CONTENT_DEPTH_CHOICES = ("skeleton", "storyboard", "near-prod")
RECOMMENDATION_MODE_CHOICES = ("hybrid", "rules")
DECISION_SPEED_CHOICES = ("fast", "guided")

DEFAULT_ROUTE = {
    "preferred_layout_archetypes": ["balanced-sections", "feature-grid"],
    "preferred_motion_profiles": ["subtle", "smooth"],
    "preferred_interaction_patterns": ["assistant-guided", "content-reading"],
    "favored_style_tags": ["modern", "clean", "balanced"],
    "penalized_style_tags": ["chaotic"],
    "default_modules": ["hero", "section-grid", "cta-band"],
    "optional_modules": ["faq", "contact"],
}

DEFAULT_ROUTES = {site: dict(DEFAULT_ROUTE) for site in SITE_TYPES}

DEFAULT_SITE_ALIASES = {
    "blog": ["blog", "article", "editorial", "博客", "文章", "内容站"],
    "saas": ["saas", "b2b", "workspace", "企业应用", "软件服务"],
    "dashboard": ["dashboard", "admin", "panel", "console", "后台", "仪表盘", "控制台", "看板"],
    "docs": ["docs", "documentation", "guide", "manual", "文档", "说明", "帮助中心"],
    "ecommerce": ["ecommerce", "store", "shop", "checkout", "电商", "商城", "购物", "商品"],
    "landing-page": ["landing", "hero", "marketing", "homepage", "落地页", "首页", "营销"],
    "portfolio": ["portfolio", "case study", "showreel", "作品集", "案例", "展示"],
    "general": ["web", "website", "app", "站点", "网站", "页面"],
}

STYLE_TO_VISUAL_STYLE = {
    "minimal": "minimal",
    "editorial": "editorial",
    "retro": "retro",
    "vintage": "retro",
    "y2k": "retro",
    "cyberpunk": "expressive",
    "neo-brutalist": "expressive",
    "neon": "expressive",
    "glass": "modern-tech",
    "glassmorphism": "modern-tech",
    "dashboard": "corporate",
    "enterprise": "corporate",
    "playful": "playful",
}




def load_v2_references(ref_dir: Path) -> dict[str, Any]:
    tax_dir = ref_dir / "taxonomy"
    schema_path = tax_dir / "tag-schema.json"
    aliases_path = tax_dir / "tag-aliases.json"
    routing_path = tax_dir / "site-type-routing.json"
    style_map_path = tax_dir / "style-tag-map.v2.json"

    schema = {"schemaVersion": "2.0.0", "dimensions": {}}
    aliases = {"schemaVersion": "2.0.0", "site_type_aliases": dict(DEFAULT_SITE_ALIASES)}
    routing = {"schemaVersion": "2.0.0", "site_types": dict(DEFAULT_ROUTES)}
    style_map = {"schemaVersion": "2.0.0", "style_mappings": {}}

    if schema_path.exists():
        schema = load_json(schema_path)
    if aliases_path.exists():
        aliases = load_json(aliases_path)
    if routing_path.exists():
        routing = load_json(routing_path)
    if style_map_path.exists():
        style_map = load_json(style_map_path)

    anim_path = tax_dir / "animation-profiles.v2.json"
    ipt_path = tax_dir / "interaction-patterns.v2.json"
    animation_profiles: dict[str, Any] = {"schemaVersion": "2.0.0", "profiles": {}}
    interaction_patterns: dict[str, Any] = {"schemaVersion": "2.0.0", "patterns": {}}
    if anim_path.exists():
        animation_profiles = load_json(anim_path)
    if ipt_path.exists():
        interaction_patterns = load_json(ipt_path)

    aliases.setdefault("site_type_aliases", dict(DEFAULT_SITE_ALIASES))
    routing.setdefault("site_types", dict(DEFAULT_ROUTES))
    for site in SITE_TYPES:
        routing["site_types"].setdefault(site, dict(DEFAULT_ROUTE))

    return {
        "schema": schema,
        "aliases": aliases,
        "routing": routing,
        "style_map": style_map,
        "animation_profiles": animation_profiles,
        "interaction_patterns": interaction_patterns,
    }


def resolve_site_type(query: str, explicit_site_type: str, aliases_payload: dict[str, Any]) -> dict[str, Any]:
    if explicit_site_type and explicit_site_type != "auto":
        site_type = explicit_site_type if explicit_site_type in SITE_TYPES else "general"
        return {
            "site_type": site_type,
            "source": "explicit",
            "confidence": 1.0,
            "matched_signals": [site_type],
        }

    aliases = aliases_payload.get("site_type_aliases", {}) or {}
    tokens = tokenize(query)
    qset = set(tokens)

    scored: list[tuple[str, int, list[str]]] = []
    for site, terms in aliases.items():
        matched = [term for term in terms if normalize_text(term) in qset or normalize_text(term) in normalize_text(query)]
        if matched:
            scored.append((site, len(matched), matched[:6]))

    if not scored:
        return {
            "site_type": "general",
            "source": "heuristic-default",
            "confidence": 0.35,
            "matched_signals": [],
        }

    scored.sort(key=lambda item: item[1], reverse=True)
    winner = scored[0]
    confidence = min(1.0, 0.45 + winner[1] * 0.15)
    site_type = winner[0] if winner[0] in SITE_TYPES else "general"
    return {
        "site_type": site_type,
        "source": "alias-match",
        "confidence": round(confidence, 3),
        "matched_signals": winner[2],
    }


def routing_for_site_type(site_type: str, routing_payload: dict[str, Any]) -> dict[str, Any]:
    routes = (routing_payload.get("site_types", {}) if isinstance(routing_payload, dict) else {}) or {}
    route = routes.get(site_type) or DEFAULT_ROUTES.get(site_type) or DEFAULT_ROUTE
    out = dict(DEFAULT_ROUTE)
    out.update(route)
    return out


def style_mapping_for_slug(slug: str, style_map_payload: dict[str, Any]) -> dict[str, Any]:
    mappings = (style_map_payload.get("style_mappings", {}) if isinstance(style_map_payload, dict) else {}) or {}
    if slug in mappings and isinstance(mappings[slug], dict):
        return mappings[slug]
    return {}


def infer_visual_style(style: dict[str, Any], mapping: dict[str, Any]) -> str:
    explicit = mapping.get("visual_style")
    if explicit:
        return str(explicit)

    text = " ".join(
        [
            str(style.get("slug", "")),
            str(style.get("name", "")),
            str(style.get("nameEn", "")),
            str(style.get("category", "")),
            " ".join(style.get("keywords", [])),
            " ".join(style.get("tags", [])),
        ]
    ).lower()

    for hint, label in STYLE_TO_VISUAL_STYLE.items():
        if hint in text:
            return label
    if style.get("styleType") == "layout":
        return "balanced"
    return "modern-tech"


def infer_layout_archetype(
    style: dict[str, Any],
    mapping: dict[str, Any],
    route: dict[str, Any],
    site_type: str,
    query: str,
) -> str:
    hints = mapping.get("layout_archetype_hints", [])
    if isinstance(hints, list) and hints:
        return str(hints[0])

    query_low = normalize_text(query)
    if site_type == "dashboard":
        return "kpi-console"
    if site_type == "docs":
        return "doc-sidebar"
    if site_type == "blog":
        return "article-first"
    if site_type == "portfolio":
        return "showcase-masonry"
    if site_type == "ecommerce":
        return "catalog-conversion"
    if site_type == "landing-page":
        return "split-hero"
    if "sidebar" in query_low or "侧边栏" in query_low:
        return "doc-sidebar"
    if "table" in query_low or "数据" in query_low:
        return "kpi-console"
    preferred = route.get("preferred_layout_archetypes", [])
    if isinstance(preferred, list) and preferred:
        return str(preferred[0])
    return "balanced-sections"


def infer_motion_profile(style: dict[str, Any], mapping: dict[str, Any], route: dict[str, Any], query: str) -> str:
    hints = mapping.get("motion_profile_hints", [])
    if isinstance(hints, list) and hints:
        return str(hints[0])

    text = " ".join(
        [
            normalize_text(query),
            normalize_text(style.get("slug", "")),
            normalize_text(style.get("nameEn", "")),
            " ".join([normalize_text(x) for x in style.get("tags", [])]),
            " ".join([normalize_text(x) for x in style.get("keywords", [])]),
            normalize_text(style.get("aiRules", "")),
        ]
    )
    if any(k in text for k in ("minimal", "readable", "docs", "文档", "可读", "克制")):
        return "minimal"
    if any(k in text for k in ("smooth", "glass", "丝滑", "玻璃", "fluid")):
        return "smooth"
    if any(k in text for k in ("dramatic", "bold", "neon", "cyber", "视觉冲击", "强烈")):
        return "energetic"
    if any(k in text for k in ("playful", "whimsical", "fun", "bouncy", "趣味", "活泼", "可爱")):
        return "playful"
    if any(k in text for k in ("ambient", "atmospheric", "floating", "氛围", "漂浮", "背景动效")):
        return "ambient"
    if any(k in text for k in ("loading", "skeleton", "progress", "spinner", "加载", "骨架屏")):
        return "functional"
    preferred = route.get("preferred_motion_profiles", [])
    if isinstance(preferred, list) and preferred:
        return str(preferred[0])
    return "subtle"


def infer_interaction_pattern(style: dict[str, Any], mapping: dict[str, Any], route: dict[str, Any], site_type: str, query: str) -> str:
    hints = mapping.get("interaction_pattern_hints", [])
    if isinstance(hints, list) and hints:
        return str(hints[0])

    query_low = normalize_text(query)
    if any(k in query_low for k in ("wizard", "multi-step", "form", "表单", "向导", "分步", "注册流程")):
        return "form-wizard"
    if any(k in query_low for k in ("search", "filter", "facet", "搜索", "筛选", "过滤", "检索")):
        return "search-explore"
    if any(k in query_low for k in ("notification", "toast", "alert", "inbox", "通知", "消息中心", "提醒")):
        return "notification-center"
    if site_type == "dashboard":
        return "data-dense-feedback"
    if site_type == "docs":
        return "docs-navigation"
    if site_type in {"landing-page", "ecommerce"}:
        return "conversion-focused"
    if site_type in {"portfolio"}:
        return "showcase-narrative"
    if "read" in query_low or "阅读" in query_low:
        return "content-reading"
    preferred = route.get("preferred_interaction_patterns", [])
    if isinstance(preferred, list) and preferred:
        return str(preferred[0])
    return "assistant-guided"


def infer_modifiers(style: dict[str, Any], mapping: dict[str, Any], site_type: str, query: str) -> list[str]:
    modifiers: list[str] = []
    mapped = mapping.get("modifiers", [])
    if isinstance(mapped, list):
        modifiers.extend(str(x) for x in mapped if str(x).strip())

    text = " ".join(
        [
            normalize_text(query),
            normalize_text(style.get("category", "")),
            " ".join([normalize_text(x) for x in style.get("tags", [])]),
            " ".join([normalize_text(x) for x in style.get("keywords", [])]),
        ]
    )
    if any(k in text for k in ("readability", "readable", "可读", "文档", "docs")):
        modifiers.append("readability-first")
    if any(k in text for k in ("conversion", "cta", "checkout", "转化", "购买", "注册")):
        modifiers.append("conversion-first")
    if any(k in text for k in ("high-contrast", "霓虹", "强对比", "brutalist", "neo-brutalist")):
        modifiers.append("high-contrast")
    if site_type in {"dashboard", "docs"}:
        modifiers.append("dense-information")
    if site_type in {"landing-page", "portfolio"}:
        modifiers.append("hero-driven")

    out: list[str] = []
    seen = set()
    for item in modifiers:
        key = str(item).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out[:3]


def build_tag_bundle(
    *,
    style: dict[str, Any],
    site_type: str,
    query: str,
    route: dict[str, Any],
    style_map_payload: dict[str, Any],
) -> dict[str, Any]:
    slug = str(style.get("slug", ""))
    mapping = style_mapping_for_slug(slug, style_map_payload)
    visual_style = infer_visual_style(style, mapping)
    layout_archetype = infer_layout_archetype(style, mapping, route, site_type, query)
    motion_profile = infer_motion_profile(style, mapping, route, query)
    interaction_pattern = infer_interaction_pattern(style, mapping, route, site_type, query)
    modifiers = infer_modifiers(style, mapping, site_type, query)

    return {
        "site_type": site_type,
        "visual_style": visual_style,
        "layout_archetype": layout_archetype,
        "motion_profile": motion_profile,
        "interaction_pattern": interaction_pattern,
        "modifiers": modifiers,
    }


def routing_adjustment_for_style(
    *,
    style: dict[str, Any],
    site_type: str,
    route: dict[str, Any],
    style_map_payload: dict[str, Any],
    query: str,
) -> tuple[float, dict[str, Any]]:
    mapping = style_mapping_for_slug(str(style.get("slug", "")), style_map_payload)
    base_tags = {
        normalize_text(style.get("styleType", "")),
        normalize_text(style.get("category", "")),
        normalize_text(mapping.get("visual_style", "")),
    }
    for item in style.get("tags", []):
        base_tags.add(normalize_text(item))
    for item in style.get("keywords", []):
        base_tags.add(normalize_text(item))
    for item in mapping.get("modifiers", []):
        base_tags.add(normalize_text(item))

    favored = {normalize_text(x) for x in route.get("favored_style_tags", [])}
    penalized = {normalize_text(x) for x in route.get("penalized_style_tags", [])}
    favored_hits = sorted(tag for tag in base_tags if tag and tag in favored)
    penalized_hits = sorted(tag for tag in base_tags if tag and tag in penalized)

    adjustment = 0.0
    adjustment += min(len(favored_hits), 3) * 1.6
    adjustment -= min(len(penalized_hits), 3) * 1.4

    stype = normalize_text(style.get("styleType", ""))
    query_low = normalize_text(query)
    prefer_layout = any(k in query_low for k in ("dashboard", "admin", "panel", "console", "布局", "grid", "table", "chart", "侧边栏"))
    if site_type in {"dashboard", "docs"} and stype == "layout":
        adjustment += 1.8
    if site_type in {"landing-page", "portfolio"} and stype == "visual":
        adjustment += 1.2
    if prefer_layout and stype == "layout":
        adjustment += 1.2
    if prefer_layout and stype != "layout" and site_type in {"dashboard", "docs", "saas"}:
        adjustment -= 0.8

    return round(adjustment, 4), {
        "site_type": site_type,
        "favored_hits": favored_hits[:6],
        "penalized_hits": penalized_hits[:6],
    }


def resolve_animation_profile(
    tag_bundle: dict[str, Any],
    route: dict[str, Any],
    animation_profiles_payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Resolve the best-matching animation profile from taxonomy data."""
    if not animation_profiles_payload:
        return None
    profiles = animation_profiles_payload.get("profiles", {})
    if not profiles:
        return None

    motion = tag_bundle.get("motion_profile", "")
    recommended = route.get("recommended_animation_profiles", [])
    for name in recommended:
        if name in profiles and profiles[name].get("motion_profile") == motion:
            return profiles[name]

    for name in recommended:
        if name in profiles:
            return profiles[name]

    for _name, profile in profiles.items():
        if profile.get("motion_profile") == motion:
            return profile

    return None


def resolve_interaction_pattern_data(
    tag_bundle: dict[str, Any],
    interaction_patterns_payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Resolve the matching interaction pattern data from taxonomy."""
    if not interaction_patterns_payload:
        return None
    patterns = interaction_patterns_payload.get("patterns", {})
    if not patterns:
        return None

    pattern_key = tag_bundle.get("interaction_pattern", "")
    if pattern_key in patterns:
        return patterns[pattern_key]

    return None


def build_ai_interaction_script(
    tag_bundle: dict[str, Any],
    lang: str,
    resolved_anim_profile: dict[str, Any] | None = None,
    resolved_interaction_pattern: dict[str, Any] | None = None,
) -> list[str]:
    motion = tag_bundle.get("motion_profile")
    pattern = tag_bundle.get("interaction_pattern")
    layout = tag_bundle.get("layout_archetype")

    has_anim = resolved_anim_profile is not None
    has_ipt = resolved_interaction_pattern is not None

    if not has_anim and not has_ipt:
        if lang == "zh":
            return [
                "动效目标：先明确每段动效服务的信息目标（导览、反馈、转化），禁止无目的炫技。",
                f"触发机制：围绕 `{pattern}` 设计 hover/active/focus/loading/error 触发条件。",
                "状态机：每个核心组件至少定义 default/hover/active/focus-visible/disabled 五态。",
                f"节奏参数：主动画采用 `{motion}` 档位，常规反馈 150-300ms，结构转场 250-500ms。",
                "可访问性：非必要动画遵循 prefers-reduced-motion，焦点可见且键盘路径连续。",
                f"布局协同：`{layout}` 场景下优先保持信息层级稳定，再叠加动效。",
            ]
        return [
            "Motion objective: every animation must serve guidance, feedback, or conversion intent.",
            f"Trigger logic: design hover/active/focus/loading/error around `{pattern}` behavior.",
            "State machine: define default/hover/active/focus-visible/disabled for core components.",
            f"Rhythm: use `{motion}` profile; micro-feedback 150-300ms, structural transitions 250-500ms.",
            "Accessibility: respect prefers-reduced-motion and preserve visible keyboard focus path.",
            f"Layout sync: prioritize hierarchy stability in `{layout}` before adding expressive motion.",
        ]

    lines: list[str] = []

    if has_anim:
        ap = resolved_anim_profile
        dur = ap.get("duration_range_ms", [150, 300])
        dur_str = f"{dur[0]}-{dur[1]}ms" if len(dur) >= 2 else str(dur)
        easing = ap.get("easing", "ease")
        intent = ap.get("intent", "")
        fallback = ap.get("reduced_motion_fallback", "instant-state-swap")
        anti = ap.get("anti_patterns", [])

        if lang == "zh":
            lines.append(f"动效意图：{intent}")
            lines.append(f"节奏参数：时长 {dur_str}，缓动 `{easing}`，reduced-motion 回退 `{fallback}`。")
            if anti:
                lines.append(f"动效禁区：{'; '.join(anti[:3])}。")
        else:
            lines.append(f"Motion intent: {intent}")
            lines.append(f"Timing: duration {dur_str}, easing `{easing}`, reduced-motion fallback `{fallback}`.")
            if anti:
                lines.append(f"Motion anti-patterns: {'; '.join(anti[:3])}.")

    if has_ipt:
        ip = resolved_interaction_pattern
        goal = ip.get("primary_goal", "")
        states = ip.get("state_coverage_requirements", {})
        a11y = ip.get("accessibility_constraints", [])
        ipt_anti = ip.get("anti_patterns", [])

        if lang == "zh":
            lines.append(f"交互目标：{goal}")
            if states:
                state_items = [f"`{comp}`: {', '.join(st)}" for comp, st in list(states.items())[:3]]
                lines.append(f"状态覆盖要求：{'; '.join(state_items)}。")
            if a11y:
                lines.append(f"可访问性约束：{'; '.join(a11y[:3])}。")
            if ipt_anti:
                lines.append(f"交互禁区：{'; '.join(ipt_anti[:2])}。")
        else:
            lines.append(f"Interaction goal: {goal}")
            if states:
                state_items = [f"`{comp}`: {', '.join(st)}" for comp, st in list(states.items())[:3]]
                lines.append(f"State coverage: {'; '.join(state_items)}.")
            if a11y:
                lines.append(f"Accessibility: {'; '.join(a11y[:3])}.")
            if ipt_anti:
                lines.append(f"Interaction anti-patterns: {'; '.join(ipt_anti[:2])}.")

    if lang == "zh":
        lines.append(f"布局协同：`{layout}` 场景下优先保持信息层级稳定，再叠加动效。")
    else:
        lines.append(f"Layout sync: prioritize hierarchy stability in `{layout}` before adding expressive motion.")

    return lines[:10]


def build_composition_plan(
    *,
    site_type: str,
    route: dict[str, Any],
    tag_bundle: dict[str, Any],
    primary_style: dict[str, Any],
    alternatives: list[dict[str, Any]],
    blend_plan: dict[str, Any],
    recommendation_mode: str,
    lang: str,
    animation_profiles: dict[str, Any] | None = None,
    interaction_patterns: dict[str, Any] | None = None,
) -> dict[str, Any]:
    owners = dict(blend_plan.get("conflict_resolution", {}) if isinstance(blend_plan, dict) else {})
    fallback_owner = primary_style.get("slug")
    owners.setdefault("color_owner", fallback_owner)
    owners.setdefault("typography_owner", fallback_owner)
    owners.setdefault("spacing_owner", fallback_owner)
    owners.setdefault("motion_owner", fallback_owner)

    alt_slugs = [item.get("slug") for item in alternatives if item.get("slug")]
    rationale = [
        f"Site-type route `{site_type}` prefers `{tag_bundle.get('layout_archetype')}` + `{tag_bundle.get('interaction_pattern')}`.",
        f"Primary style `{primary_style.get('slug')}` anchors the visual identity.",
        "Owners from blend conflict-resolution control color/typography/spacing/motion decisions.",
    ]
    if alt_slugs:
        rationale.append(f"Secondary style context considered: {', '.join(alt_slugs[:2])}.")
    if recommendation_mode == "rules":
        rationale.append("Recommendation mode is deterministic rules-only.")
    else:
        rationale.append("Recommendation mode is rules-first with LLM polishing.")

    if lang == "zh":
        rationale = [
            f"站点类型 `{site_type}` 路由优先 `{tag_bundle.get('layout_archetype')}` 与 `{tag_bundle.get('interaction_pattern')}`。",
            f"主风格 `{primary_style.get('slug')}` 负责视觉识别度。",
            "融合所有权（色彩/排版/间距/动效）来自冲突消解矩阵。",
        ] + ([f"次级风格上下文：{', '.join(alt_slugs[:2])}。"] if alt_slugs else []) + (
            ["推荐模式：纯规则确定性输出。"] if recommendation_mode == "rules" else ["推荐模式：规则优先 + LLM 润色。"]
        )

    resolved_anim = resolve_animation_profile(tag_bundle, route, animation_profiles)
    resolved_ipt = resolve_interaction_pattern_data(tag_bundle, interaction_patterns)

    motion_rec: dict[str, Any] = {
        "motion_profile": tag_bundle.get("motion_profile"),
        "reason": route.get("preferred_motion_profiles", [])[:3],
    }
    if resolved_anim:
        motion_rec["intent"] = resolved_anim.get("intent")
        motion_rec["duration_range_ms"] = resolved_anim.get("duration_range_ms")
        motion_rec["easing"] = resolved_anim.get("easing")

    interaction_rec: dict[str, Any] = {
        "interaction_pattern": tag_bundle.get("interaction_pattern"),
        "reason": route.get("preferred_interaction_patterns", [])[:3],
    }
    if resolved_ipt:
        interaction_rec["primary_goal"] = resolved_ipt.get("primary_goal")
        interaction_rec["required_components"] = resolved_ipt.get("required_components")

    checks = [
        "state-machine coverage for hover/active/focus-visible/loading/error",
        "layout hierarchy stability before decorative animation",
        "token consistency across style/layout/motion ownership",
    ]
    if resolved_ipt:
        state_reqs = resolved_ipt.get("state_coverage_requirements", {})
        for comp, states in list(state_reqs.items())[:3]:
            checks.append(f"{comp} states: {', '.join(states)}")

    return {
        "site_type": site_type,
        "recommendation_mode": recommendation_mode,
        "style_recommendation": {
            "primary_style": primary_style.get("slug"),
            "visual_style": tag_bundle.get("visual_style"),
            "alternatives": alt_slugs[:3],
        },
        "layout_recommendation": {
            "layout_archetype": tag_bundle.get("layout_archetype"),
            "reason": route.get("preferred_layout_archetypes", [])[:3],
        },
        "motion_recommendation": motion_rec,
        "interaction_recommendation": interaction_rec,
        "owner_matrix": {
            "style_identity_owner": fallback_owner,
            "color_owner": owners.get("color_owner"),
            "typography_owner": owners.get("typography_owner"),
            "spacing_owner": owners.get("spacing_owner"),
            "motion_owner": owners.get("motion_owner"),
            "interaction_owner": owners.get("interaction_owner", owners.get("motion_owner")),
        },
        "ai_interaction_script": build_ai_interaction_script(
            tag_bundle, lang,
            resolved_anim_profile=resolved_anim,
            resolved_interaction_pattern=resolved_ipt,
        ),
        "checks": checks,
        "rationale": rationale,
    }


def build_decision_flow(
    *,
    site_type: str,
    lang: str,
    speed: str,
    style_options: list[dict[str, Any]],
    stack: str,
) -> dict[str, Any]:
    options = [
        {"option_id": item.get("option_id"), "slug": item.get("slug"), "reason": item.get("reason")}
        for item in style_options[:4]
    ]
    selected_slug = options[0]["slug"] if options else ""

    if lang == "zh":
        fast_steps = [
            "第1步（目标）：确认页面优先级（可读性 / 转化 / 品牌表达）。",
            "第2步（强度）：在克制、平衡、表达性之间选择视觉强度。",
            "第3步（组合）：锁定布局 archetype 与动效档位，进入代码生成。",
        ]
        guided_steps = fast_steps + [
            "第4步（交互）：确认关键组件状态覆盖（empty/loading/error/focus）。",
            "第5步（验收）：先跑 swap/squint/signature/token 四项检查。",
        ]
        steps = fast_steps if speed == "fast" else guided_steps
        command = (
            f'python scripts/run_pipeline.py --workflow codegen --query "<requirement>" --stack {stack} '
            f"--site-type {site_type} --style {selected_slug} --content-depth skeleton "
            "--recommendation-mode hybrid --decision-speed fast --format json"
        )
    else:
        fast_steps = [
            "Step 1 (goal): choose readability vs conversion vs brand-expression priority.",
            "Step 2 (intensity): pick calm, balanced, or expressive visual intensity.",
            "Step 3 (composition): lock layout archetype + motion profile, then generate.",
        ]
        guided_steps = fast_steps + [
            "Step 4 (interaction): confirm empty/loading/error/focus state coverage.",
            "Step 5 (validation): run swap/squint/signature/token checks before handoff.",
        ]
        steps = fast_steps if speed == "fast" else guided_steps
        command = (
            f'python scripts/run_pipeline.py --workflow codegen --query "<requirement>" --stack {stack} '
            f"--site-type {site_type} --style {selected_slug} --content-depth skeleton "
            "--recommendation-mode hybrid --decision-speed fast --format json"
        )

    return {
        "decision_speed": speed,
        "style_options": options,
        "steps": steps,
        "lock_command_template": command,
    }


def build_content_plan(*, site_type: str, route: dict[str, Any], content_depth: str, lang: str) -> dict[str, Any]:
    core_modules = [str(x) for x in route.get("default_modules", [])][:8]
    optional_modules = [str(x) for x in route.get("optional_modules", [])][:6]

    if site_type in {"dashboard", "docs"}:
        pages = ["overview", "detail", "list", "settings"]
    elif site_type in {"blog", "portfolio"}:
        pages = ["home", "list", "detail", "about"]
    elif site_type in {"ecommerce"}:
        pages = ["home", "catalog", "detail", "checkout"]
    else:
        pages = ["home", "features", "detail", "contact"]

    states = ["default", "hover", "active", "focus-visible", "disabled", "loading", "error", "empty"]
    out = {
        "content_depth": content_depth,
        "core_pages": pages,
        "core_modules": core_modules,
        "optional_modules": optional_modules,
        "state_coverage": states,
    }

    if content_depth in {"storyboard", "near-prod"}:
        out["motion_storyboard"] = [
            "entry: section-level reveal follows reading order",
            "micro-feedback: control interactions stay below 300ms",
            "transition: route change keeps hierarchy continuity",
        ]
    if content_depth == "near-prod":
        out["implementation_checklist"] = [
            "component token mapping completed",
            "a11y checks (contrast/focus/touch target) documented",
            "fallback states and empty data copy filled",
        ]

    if lang == "zh":
        out["goal"] = "首版先保证信息完整与状态完整，再优化视觉戏剧性。"
    else:
        out["goal"] = "Prioritize complete information and state coverage before visual flourish."
    return out


def build_upgrade_candidates(
    *,
    query: str,
    site_type: str,
    selected_style: str,
    tag_bundle: dict[str, Any],
    quality_gate: dict[str, Any],
) -> list[dict[str, Any]]:
    violations = quality_gate.get("violations", []) if isinstance(quality_gate, dict) else []
    warnings = quality_gate.get("warnings", []) if isinstance(quality_gate, dict) else []
    ignored_warning_ids = {"QA_SKIPPED_BRIEF_ONLY"}
    actionable_warnings = []
    for item in warnings:
        if not isinstance(item, dict):
            continue
        warning_id = str(item.get("id", item.get("code", "unknown")))
        if warning_id not in ignored_warning_ids:
            actionable_warnings.append(item)

    if not violations and not actionable_warnings:
        return []

    violation_ids = [str(item.get("id", item.get("code", "unknown"))) for item in violations if isinstance(item, dict)]
    warning_ids = [str(item.get("id", item.get("code", "unknown"))) for item in actionable_warnings]
    short_query = normalize_text(query)[:60]
    candidate_id = f"{now_iso().replace(':', '').replace('-', '')}-{selected_style or 'style'}"

    return [
        {
            "candidate_id": candidate_id,
            "source": "runtime-analysis",
            "summary": f"Candidate update for {site_type}/{selected_style} from latest QA signals.",
            "evidence": {
                "query_excerpt": short_query,
                "site_type": site_type,
                "selected_style": selected_style,
                "violation_ids": violation_ids[:8],
                "warning_ids": warning_ids[:8],
                "tag_bundle": tag_bundle,
            },
            "proposed_changes": [
                {
                    "target": "references/taxonomy/style-tag-map.v2.json",
                    "action": "upsert_style_mapping",
                    "payload": {
                        "slug": selected_style,
                        "modifiers": tag_bundle.get("modifiers", []),
                        "interaction_pattern_hints": [tag_bundle.get("interaction_pattern")],
                        "motion_profile_hints": [tag_bundle.get("motion_profile")],
                    },
                },
                {
                    "target": "references/taxonomy/site-type-routing.json",
                    "action": "adjust_routing_weights",
                    "payload": {
                        "site_type": site_type,
                        "boost_tags": tag_bundle.get("modifiers", []),
                        "watch_checks": violation_ids[:5],
                    },
                },
            ],
            "required_gates": [
                "python3 scripts/smoke_test.py",
                "bash scripts/ci_regression_gate.sh --baseline references/benchmark-baseline.json --snapshot-out tmp/benchmark-ci-latest.json",
            ],
        }
    ]

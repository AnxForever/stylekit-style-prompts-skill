#!/usr/bin/env python3
"""Generate design brief + hard/soft prompts from StyleKit catalog."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import sys
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from _brief_constants import (
    A11Y_BASELINE,
    ANTI_PATTERN_BLACKLIST,
    BG_BLACK_TOKEN_RE,
    BG_WHITE_TOKEN_RE,
    DEFAULT_AI_RULES,
    DISTINCTIVE_FONT_HINTS,
    GENERIC_FONTS,
    NEGATOR_WORDS,
    NEG_SECTION_MARKERS,
    POS_SECTION_MARKERS,
    RADIUS_TOKEN_RE,
    REFERENCE_TYPES,
    REFINE_MODE_HINTS,
    SHADOW_TOKEN_RE,
    STACK_HINTS,
    VALIDATION_TESTS,
    dedupe_ordered,
    detect_lang,
    has_cjk,
    language_filter_rules,
)
from _common import RULE_STOPWORDS, __version__
from blend_engine import build_blend_plan
from brief_builder import (
    anti_generic_constraints,
    build_component_guidelines,
    build_interaction_rules,
    design_system_structure,
    infer_design_intent,
    localized_visual_direction,
)
from prompt_generator import make_prompts
from reference_handler import (
    build_reference_guidelines,
    load_reference_payload,
    normalize_reference_signals,
    refine_mode_strategy,
    validate_reference_payload_schema,
)
from search_stylekit import BM25, build_text, expand_query_tokens, heuristic_score, load_json, tokenize
from v2_taxonomy import (
    CONTENT_DEPTH_CHOICES,
    DECISION_SPEED_CHOICES,
    RECOMMENDATION_MODE_CHOICES,
    SITE_TYPES,
    build_composition_plan,
    build_content_plan,
    build_decision_flow,
    build_tag_bundle,
    load_v2_references,
    resolve_interaction_pattern_data,
    resolve_site_type,
    routing_adjustment_for_style,
    routing_for_site_type,
)

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
REF_DIR = SKILL_ROOT / "references"
CATALOG_DEFAULT = REF_DIR / "style-prompts.json"


# ---------------------------------------------------------------------------
# Rule processing helpers
# ---------------------------------------------------------------------------

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


def rule_token_set(text: str) -> set[str]:
    return {tok for tok in tokenize(text) if tok not in RULE_STOPWORDS and len(tok) > 1}


def is_negative_rule(rule: str) -> bool:
    low = rule.lower()
    return any(word in low for word in NEGATOR_WORDS)


def conflicts_with_dont(rule: str, dont_list: list[str]) -> bool:
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
        ranked.append({"style": style, "score": final_score, "reason": reasons})
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


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate StyleKit design brief and prompts")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--query", required=True, help="User requirement")
    parser.add_argument("--style", help="Force style slug")
    parser.add_argument("--site-type", default="auto", choices=["auto", *SITE_TYPES], help="Site-type routing hint")
    parser.add_argument("--stack", default="html-tailwind", choices=list(STACK_HINTS.keys()))
    parser.add_argument("--mode", default="brief+prompt", choices=["brief-only", "brief+prompt"])
    parser.add_argument(
        "--recommendation-mode", default="hybrid", choices=RECOMMENDATION_MODE_CHOICES,
        help="hybrid = rules first then LLM polish; rules = deterministic routing only",
    )
    parser.add_argument("--content-depth", default="skeleton", choices=CONTENT_DEPTH_CHOICES)
    parser.add_argument("--decision-speed", default="fast", choices=DECISION_SPEED_CHOICES)
    parser.add_argument("--blend-mode", default="auto", choices=["off", "auto", "on"], help="Style blend planning mode")
    parser.add_argument(
        "--refine-mode", default="new", choices=sorted(REFINE_MODE_HINTS.keys()),
        help="Iteration mode: new/polish/debug/contrast-fix/layout-fix/component-fill",
    )

    parser.add_argument(
        "--reference-type", default="none", choices=REFERENCE_TYPES,
        help="Optional input reference type: none/screenshot/figma/mixed",
    )
    parser.add_argument("--reference-notes", default="", help="Optional notes describing screenshot/Figma context")
    parser.add_argument("--reference-file", default="", help="Optional path to reference JSON/text (screenshot/Figma analysis)")
    parser.add_argument("--reference-json", default="", help="Optional inline reference JSON/text")
    parser.add_argument(
        "--strict-reference-schema", action="store_true",
        help="Fail when reference payload has schema errors or unknown top-level fields",
    )
    parser.add_argument("--style-type", choices=["visual", "layout", "animation"])
    parser.add_argument("--catalog", default=str(CATALOG_DEFAULT))
    args = parser.parse_args()
    output = run(
        query=args.query,
        style=args.style,
        site_type=args.site_type,
        stack=args.stack,
        mode=args.mode,
        recommendation_mode=args.recommendation_mode,
        content_depth=args.content_depth,
        decision_speed=args.decision_speed,
        blend_mode=args.blend_mode,
        refine_mode=args.refine_mode,
        reference_type=args.reference_type,
        reference_notes=args.reference_notes,
        reference_file=args.reference_file,
        reference_json=args.reference_json,
        strict_reference_schema=args.strict_reference_schema,
        style_type=args.style_type,
        catalog=args.catalog,
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))


def run(
    *,
    query: str,
    style: str | None = None,
    site_type: str = "auto",
    stack: str = "html-tailwind",
    mode: str = "brief+prompt",
    recommendation_mode: str = "hybrid",
    content_depth: str = "skeleton",
    decision_speed: str = "fast",
    blend_mode: str = "auto",
    refine_mode: str = "new",
    reference_type: str = "none",
    reference_notes: str = "",
    reference_file: str = "",
    reference_json: str = "",
    strict_reference_schema: bool = False,
    style_type: str | None = None,
    catalog: str = str(CATALOG_DEFAULT),
) -> dict[str, Any]:

    catalog_path = Path(catalog)
    if not catalog_path.exists():
        raise SystemExit(f"Catalog not found: {catalog_path}")

    catalog_data = load_json(catalog_path)
    styles: list[dict[str, Any]] = catalog_data.get("styles", [])
    if style_type:
        styles = [s for s in styles if s.get("styleType") == style_type]
    if not styles:
        raise SystemExit("No styles available after filtering")

    lang = detect_lang(query)
    v2_refs = load_v2_references(REF_DIR)
    site_profile = resolve_site_type(query, site_type, v2_refs["aliases"])
    route = routing_for_site_type(site_profile["site_type"], v2_refs["routing"])

    ranked = rank_styles(styles, query)
    for item in ranked:
        route_adjustment, route_details = routing_adjustment_for_style(
            style=item["style"],
            site_type=site_profile["site_type"],
            route=route,
            style_map_payload=v2_refs["style_map"],
            query=query,
        )
        item["score"] += route_adjustment
        item["route_adjustment"] = route_adjustment
        item["route_details"] = route_details
    ranked.sort(key=lambda x: x["score"], reverse=True)

    if style:
        forced = [s for s in styles if s.get("slug") == style]
        if not forced:
            raise SystemExit(f"Style slug not found: {style}")
        primary = forced[0]
    else:
        if not ranked:
            raise SystemExit("No style available")
        primary = ranked[0]["style"]

    alternatives = [
        {
            "slug": item["style"].get("slug"),
            "name": item["style"].get("name"),
            "nameEn": item["style"].get("nameEn"),
            "score": round(item["score"], 4),
            "styleType": item["style"].get("styleType"),
            "route_adjustment": round(item.get("route_adjustment", 0.0), 4),
        }
        for item in ranked
        if item["style"].get("slug") != primary.get("slug")
    ][:2]

    raw_reference_payload = load_reference_payload(reference_json, reference_file)
    schema_validation = validate_reference_payload_schema(
        payload=raw_reference_payload,
        reference_type=reference_type,
        lang=lang,
        strict_mode=strict_reference_schema,
    )
    if not schema_validation.get("valid"):
        joined = "; ".join(schema_validation.get("errors", []))
        raise SystemExit(f"Reference schema validation failed: {joined}")
    reference_payload = schema_validation.get("sanitized_payload", {})
    effective_reference_type = reference_type
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

    reference_signals_data = normalize_reference_signals(
        payload=reference_payload,
        reference_type=effective_reference_type,
        reference_notes=reference_notes,
        lang=lang,
    )

    base_rules = extract_rules(primary.get("aiRules", ""), lang)
    base_rules.extend(reference_signals_data.get("derived_rules", []))
    ai_rules = ensure_min_rules(base_rules, primary.get("doList", []), primary.get("dontList", []), lang)
    ai_rules = resolve_rule_conflicts(ai_rules, lang)
    ai_rules = ensure_rule_floor(ai_rules, lang, min_count=3)
    ai_rules = resolve_rule_conflicts(ai_rules, lang)
    ai_rules = ensure_rule_floor(ai_rules, lang, min_count=3)[:8]

    tag_bundle = build_tag_bundle(
        style=primary,
        site_type=site_profile["site_type"],
        query=query,
        route=route,
        style_map_payload=v2_refs["style_map"],
    )

    ipt_data = resolve_interaction_pattern_data(
        tag_bundle, v2_refs.get("interaction_patterns"),
    )

    component_guidelines = build_component_guidelines(primary, lang, interaction_pattern_data=ipt_data)
    interaction_rules = build_interaction_rules(ai_rules, lang, interaction_pattern_data=ipt_data)
    stack_hint = STACK_HINTS.get(stack, STACK_HINTS["html-tailwind"])[lang]

    alt_full = [item for item in ranked if item["style"].get("slug") != primary.get("slug")][:2]
    auto_blend = blend_mode == "on" or (blend_mode == "auto" and len(alt_full) > 0)
    blend_plan = build_blend_plan(
        primary, [item["style"] for item in alt_full] if auto_blend else [], query, lang,
    )

    style_options = [
        {"option_id": f"opt-{idx}", "slug": item["style"].get("slug"), "reason": item.get("reason", "")}
        for idx, item in enumerate(ranked[:4])
    ]

    composition_plan = build_composition_plan(
        site_type=site_profile["site_type"],
        route=route,
        tag_bundle=tag_bundle,
        primary_style=primary,
        alternatives=[item["style"] for item in alt_full],
        blend_plan=blend_plan,
        recommendation_mode=recommendation_mode,
        lang=lang,
        animation_profiles=v2_refs.get("animation_profiles"),
        interaction_patterns=v2_refs.get("interaction_patterns"),
    )
    content_plan = build_content_plan(
        site_type=site_profile["site_type"],
        route=route,
        content_depth=content_depth,
        lang=lang,
    )
    decision_flow = build_decision_flow(
        site_type=site_profile["site_type"],
        lang=lang,
        speed=decision_speed,
        style_options=style_options,
        stack=stack,
    )

    intent = infer_design_intent(query, lang)
    anti_generic = anti_generic_constraints(lang)
    visual_direction = localized_visual_direction(primary, lang)
    ds_structure = design_system_structure(stack, lang)
    refine_strategy = refine_mode_strategy(refine_mode, lang)
    reference_guidelines = build_reference_guidelines(effective_reference_type, lang)

    # --- typography strategy ---
    philosophy = str(primary.get("philosophy", "")).lower()
    font_hints = DISTINCTIVE_FONT_HINTS[lang]
    has_distinctive = any(hint.lower() in philosophy for hint in GENERIC_FONTS)
    if lang == "zh":
        typography_strategy = "使用风格指定的字体策略，避免通用默认字体。" if not has_distinctive else "风格已指定字体方向，保持一致。"
    else:
        typography_strategy = "Follow the style's typography direction; avoid generic defaults." if not has_distinctive else "Style specifies font direction; maintain consistency."

    # --- color strategy ---
    colors = primary.get("colors", {})
    color_strategy = {
        "primary": colors.get("primary", ""),
        "secondary": colors.get("secondary", ""),
        "accent": colors.get("accent", []) if isinstance(colors.get("accent"), list) else [],
    }

    design_brief = {
        "style_choice": {
            "slug": primary.get("slug"),
            "name": primary.get("name"),
            "nameEn": primary.get("nameEn"),
            "category": primary.get("category"),
            "styleType": primary.get("styleType"),
        },
        "design_intent": intent,
        "refine_mode": refine_mode,
        "iteration_strategy": refine_strategy,
        "input_context": {
            "reference_type": effective_reference_type,
            "reference_notes": reference_notes,
            "reference_file": reference_file,
            "reference_payload_present": bool(reference_payload),
            "reference_has_signals": bool(reference_signals_data.get("has_signals")),
            "reference_schema_validation": schema_validation,
            "reference_guidelines": reference_guidelines,
            "reference_signal_summary": reference_signals_data.get("summary", ""),
            "reference_signals": reference_signals_data.get("signals", {}),
            "reference_derived_rules": reference_signals_data.get("derived_rules", []),
        },
        "visual_direction": visual_direction,
        "typography_strategy": typography_strategy,
        "font_strategy_hints": font_hints,
        "anti_generic_constraints": anti_generic,
        "validation_tests": VALIDATION_TESTS[lang],
        "anti_pattern_blacklist": ANTI_PATTERN_BLACKLIST[lang],
        "design_system_structure": ds_structure,
        "site_profile": site_profile,
        "tag_bundle": tag_bundle,
        "composition_plan": composition_plan,
        "decision_flow": decision_flow,
        "content_plan": content_plan,
        "color_strategy": color_strategy,
        "component_guidelines": component_guidelines,
        "interaction_rules": interaction_rules,
        "a11y_baseline": A11Y_BASELINE[lang],
        "stack_hint": stack_hint,
        "blend_plan": blend_plan,
    }

    hard_prompt = ""
    soft_prompt = ""
    if mode == "brief+prompt":
        hard_prompt, soft_prompt = make_prompts(
            query=query,
            style=primary,
            ai_rules=ai_rules,
            stack=stack,
            lang=lang,
            blend_plan=blend_plan,
            intent=intent,
            anti_generic=anti_generic,
            refine_mode=refine_mode,
            reference_type=effective_reference_type,
            reference_notes=reference_notes,
            reference_signals=reference_signals_data,
            interaction_script=composition_plan.get("ai_interaction_script", []),
        )

    return {
        "query": query,
        "mode": mode,
        "language": lang,
        "style_choice": {
            "primary": {
                "slug": primary.get("slug"),
                "name": primary.get("name"),
                "nameEn": primary.get("nameEn"),
                "styleType": primary.get("styleType"),
            },
            "alternatives": alternatives,
            "why": ranked[0].get("reason", "") if ranked else "",
        },
        "design_brief": design_brief,
        "ai_rules": ai_rules,
        "hard_prompt": hard_prompt,
        "soft_prompt": soft_prompt,
        "candidate_rank": [
            {
                "slug": item["style"].get("slug"),
                "score": round(item["score"], 4),
                "reason": item.get("reason", ""),
            }
            for item in ranked[:5]
        ],
    }


if __name__ == "__main__":
    main()

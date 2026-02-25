#!/usr/bin/env python3
"""Search and rank StyleKit styles for a user requirement."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import sys
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from _common import STOPWORDS, __version__, load_json, normalize_text, tokenize

from v2_taxonomy import (
    SITE_TYPES,
    load_v2_references,
    resolve_site_type,
    routing_adjustment_for_style,
    routing_for_site_type,
)

QUERY_SYNONYMS = {
    "glass": ["glassmorphism", "frosted", "blur", "透明", "模糊", "玻璃"],
    "玻璃": ["glass", "glassmorphism", "frosted", "blur", "透明", "模糊"],
    "高端": ["luxury", "premium", "editorial", "elegant"],
    "luxury": ["高端", "premium", "editorial", "elegant"],
    "科技": ["tech", "saas", "digital", "modern"],
    "tech": ["科技", "saas", "digital", "modern"],
    "后台": ["dashboard", "admin", "panel", "analytics"],
    "dashboard": ["后台", "admin", "panel", "analytics"],
    "财务": ["finance", "financial", "fintech", "payment", "billing"],
    "finance": ["财务", "financial", "fintech", "payment", "billing"],
    "可读性": ["readability", "contrast", "legible", "typography"],
    "readability": ["可读性", "contrast", "legible", "typography"],
    "极简": ["minimal", "minimalist", "clean"],
    "minimal": ["极简", "minimalist", "clean"],
    "杂志": ["editorial", "magazine", "serif"],
    "editorial": ["杂志", "magazine", "serif", "排版"],
    "复古": ["retro", "vintage", "y2k", "vaporwave"],
    "retro": ["复古", "vintage", "y2k", "vaporwave"],
    "霓虹": ["neon", "glow", "cyberpunk", "synthwave"],
    "neon": ["霓虹", "glow", "cyberpunk", "synthwave"],
    "品牌": ["brand", "branding"],
    "brand": ["品牌", "branding"],
}

STRICT_DOMAIN_HINTS = {
    "healthcare",
    "medical",
    "hospital",
    "clinic",
    "medicine",
    "pharma",
    "finance",
    "financial",
    "fintech",
    "banking",
    "bank",
    "payment",
    "billing",
    "accounting",
    "insurance",
    "education",
    "edu",
    "school",
    "university",
    "college",
    "government",
    "gov",
    "legal",
    "law",
    "compliance",
    "health",
    "医疗",
    "医药",
    "医院",
    "诊所",
    "财务",
    "金融",
    "银行",
    "支付",
    "会计",
    "保险",
    "教育",
    "学校",
    "大学",
    "政府",
    "政务",
    "法律",
    "合规",
}

BALANCED_DOMAIN_HINTS = {
    "saas",
    "b2b",
    "dashboard",
    "admin",
    "panel",
    "analytics",
    "developer",
    "devtools",
    "docs",
    "documentation",
    "workspace",
    "backoffice",
    "console",
    "后台",
    "看板",
    "仪表盘",
    "控制台",
    "开发者",
    "文档",
    "管理",
}

EXPRESSIVE_DOMAIN_HINTS = {
    "gaming",
    "game",
    "music",
    "festival",
    "creative",
    "artist",
    "portfolio",
    "fashion",
    "brand",
    "campaign",
    "entertainment",
    "studio",
    "agency",
    "art",
    "游戏",
    "音乐",
    "创意",
    "作品集",
    "时尚",
    "活动",
    "娱乐",
    "品牌",
    "艺术",
    "工作室",
}

EXPRESSIVE_INTENT_HINTS = {
    "bold",
    "dramatic",
    "experimental",
    "avant-garde",
    "artistic",
    "cyberpunk",
    "neon",
    "vaporwave",
    "glitch",
    "brutalist",
    "punk",
    "surreal",
    "playful",
    "视觉冲击",
    "实验",
    "前卫",
    "猎奇",
    "霓虹",
    "赛博",
    "蒸汽波",
    "故障",
    "大胆",
    "反设计",
}

CONSERVATIVE_INTENT_HINTS = {
    "clean",
    "minimal",
    "minimalist",
    "professional",
    "trust",
    "trustworthy",
    "readable",
    "readability",
    "accessible",
    "a11y",
    "compliant",
    "stable",
    "enterprise",
    "neutral",
    "calm",
    "极简",
    "简洁",
    "专业",
    "信任",
    "可读性",
    "可访问",
    "稳定",
    "企业",
    "克制",
}

LAYOUT_INTENT_HINTS = {
    "dashboard",
    "admin",
    "panel",
    "console",
    "sidebar",
    "table",
    "grid",
    "analytics",
    "backend",
    "backoffice",
    "后台",
    "看板",
    "仪表盘",
    "控制台",
    "侧边栏",
    "表格",
    "数据",
    "布局",
}

STYLE_EXPRESSIVE_HINTS = {
    "expressive",
    "high-contrast",
    "neon",
    "glitch",
    "vaporwave",
    "anti-design",
    "brutal",
    "punk",
    "cyberpunk",
    "anime",
    "pop",
    "retro",
    "赛博",
    "霓虹",
    "故障",
    "蒸汽波",
    "反设计",
    "波普",
    "机甲",
    "夸张",
}

STYLE_CONSERVATIVE_HINTS = {
    "minimal",
    "corporate",
    "clean",
    "professional",
    "readable",
    "dashboard",
    "enterprise",
    "docs",
    "github",
    "neutral",
    "editorial",
    "calm",
    "简洁",
    "极简",
    "企业",
    "专业",
    "可读",
    "后台",
    "仪表盘",
    "文档",
    "沉稳",
    "克制",
}

STYLE_OPERATIONAL_HINTS = {
    "dashboard",
    "admin",
    "panel",
    "analytics",
    "analysis",
    "data",
    "table",
    "chart",
    "docs",
    "documentation",
    "enterprise",
    "corporate",
    "saas",
    "console",
    "monitor",
    "后台",
    "仪表盘",
    "面板",
    "数据",
    "图表",
    "分析",
    "表格",
    "文档",
    "企业",
    "管理",
    "监控",
    "控制台",
}

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
REF_DIR = SKILL_ROOT / "references"
CATALOG_DEFAULT = REF_DIR / "style-prompts.json"
INDEX_DEFAULT = REF_DIR / "style-search-index.json"



def expand_query_tokens(tokens: list[str]) -> list[str]:
    expanded = list(tokens)
    seen = set(tokens)
    for token in tokens:
        for syn in QUERY_SYNONYMS.get(token, []):
            if syn not in seen:
                expanded.append(syn)
                seen.add(syn)
    return expanded


class BM25:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus: list[list[str]] = []
        self.doc_len: list[int] = []
        self.avgdl: float = 0.0
        self.idf: dict[str, float] = {}

    def fit(self, docs: list[str]) -> None:
        self.corpus = [tokenize(doc) for doc in docs]
        n = len(self.corpus)
        if n == 0:
            return

        self.doc_len = [len(doc) for doc in self.corpus]
        self.avgdl = (sum(self.doc_len) / n) if n else 0.0

        df: defaultdict[str, int] = defaultdict(int)
        for doc in self.corpus:
            for term in set(doc):
                df[term] += 1

        for term, freq in df.items():
            self.idf[term] = math.log((n - freq + 0.5) / (freq + 0.5) + 1)

    def score(self, query: str | None = None, query_tokens: list[str] | None = None) -> list[tuple[int, float]]:
        if query_tokens is None:
            qtokens = tokenize(query or "")
        else:
            qtokens = query_tokens
        out: list[tuple[int, float]] = []
        for idx, doc in enumerate(self.corpus):
            if not doc:
                out.append((idx, 0.0))
                continue
            freqs = Counter(doc)
            score = 0.0
            dl = self.doc_len[idx]
            for term in qtokens:
                if term not in self.idf:
                    continue
                tf = freqs.get(term, 0)
                if tf == 0:
                    continue
                idf = self.idf[term]
                denom = tf + self.k1 * (1 - self.b + self.b * (dl / self.avgdl if self.avgdl else 0))
                score += idf * (tf * (self.k1 + 1)) / (denom or 1)
            out.append((idx, score))
        out.sort(key=lambda item: item[1], reverse=True)
        return out



def build_text(style: dict[str, Any]) -> str:
    parts: list[str] = [
        style.get("slug", ""),
        style.get("name", ""),
        style.get("nameEn", ""),
        style.get("styleType", ""),
        style.get("category", ""),
        style.get("philosophy", ""),
        style.get("aiRules", ""),
        style.get("description", ""),
    ]
    parts.extend(style.get("keywords", []))
    parts.extend(style.get("tags", []))
    parts.extend(style.get("doList", []))
    parts.extend(style.get("dontList", []))
    return "\n".join(parts)


def infer_query_signals(query: str, qtokens: list[str]) -> dict[str, Any]:
    qset = set(qtokens)
    strict_hits = sorted(qset & STRICT_DOMAIN_HINTS)
    balanced_hits = sorted(qset & BALANCED_DOMAIN_HINTS)
    expressive_domain_hits = sorted(qset & EXPRESSIVE_DOMAIN_HINTS)
    expressive_intent_hits = sorted(qset & EXPRESSIVE_INTENT_HINTS)
    conservative_intent_hits = sorted(qset & CONSERVATIVE_INTENT_HINTS)
    layout_intent_hits = sorted(qset & LAYOUT_INTENT_HINTS)

    domain = "general"
    if strict_hits:
        domain = "strict"
    elif expressive_domain_hits:
        domain = "expressive"
    elif balanced_hits:
        domain = "balanced"

    explicit_expressive = len(expressive_intent_hits) > 0
    explicit_conservative = len(conservative_intent_hits) > 0
    prefer_layout = len(layout_intent_hits) > 0

    query_lower = normalize_text(query)
    if any(word in query_lower for word in ["experimental", "avant-garde", "猎奇", "前卫", "视觉冲击"]):
        explicit_expressive = True
    if any(word in query_lower for word in ["可读性", "readability", "trust", "可信", "合规", "compliance"]):
        explicit_conservative = True

    return {
        "domain": domain,
        "strict_hits": strict_hits[:6],
        "balanced_hits": balanced_hits[:6],
        "expressive_domain_hits": expressive_domain_hits[:6],
        "expressive_intent_hits": expressive_intent_hits[:6],
        "conservative_intent_hits": conservative_intent_hits[:6],
        "layout_intent_hits": layout_intent_hits[:6],
        "explicit_expressive": explicit_expressive,
        "explicit_conservative": explicit_conservative,
        "prefer_layout": prefer_layout,
    }


def infer_style_profile(style: dict[str, Any]) -> dict[str, Any]:
    text = "\n".join(
        [
            style.get("slug", ""),
            style.get("name", ""),
            style.get("nameEn", ""),
            style.get("styleType", ""),
            style.get("philosophy", ""),
            " ".join(style.get("keywords", [])),
            " ".join(style.get("tags", [])),
        ]
    )
    tokens = set(tokenize(text))
    expressive_hits = sorted(tokens & STYLE_EXPRESSIVE_HINTS)
    conservative_hits = sorted(tokens & STYLE_CONSERVATIVE_HINTS)
    operational_hits = sorted(tokens & STYLE_OPERATIONAL_HINTS)
    return {
        "expressive_hits": expressive_hits[:8],
        "conservative_hits": conservative_hits[:8],
        "operational_hits": operational_hits[:8],
        "expressive_score": float(len(expressive_hits)),
        "conservative_score": float(len(conservative_hits)),
        "operational_score": float(len(operational_hits)),
    }


def domain_style_adjustment(style: dict[str, Any], query_signals: dict[str, Any], style_profile: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    domain = query_signals.get("domain", "general")
    explicit_expressive = bool(query_signals.get("explicit_expressive"))
    explicit_conservative = bool(query_signals.get("explicit_conservative"))
    prefer_layout = bool(query_signals.get("prefer_layout"))

    expressive_score = style_profile.get("expressive_score", 0.0)
    conservative_score = style_profile.get("conservative_score", 0.0)
    operational_score = style_profile.get("operational_score", 0.0)
    stype = normalize_text(style.get("styleType"))

    adjustment = 0.0
    parts: list[str] = []

    if domain == "strict":
        if explicit_expressive:
            adjustment += min(expressive_score, 4.0) * 0.9
            parts.append("strict-domain but expressive intent")
        else:
            adjustment += min(conservative_score, 5.0) * 2.0
            adjustment -= min(expressive_score, 4.0) * 2.2
            parts.append("strict-domain stability bias")
        if operational_score > 0:
            adjustment += min(operational_score, 4.0) * 1.2
            parts.append("strict-domain operational signal")
    elif domain == "balanced":
        if explicit_expressive:
            adjustment += min(expressive_score, 4.0) * 1.3
            parts.append("balanced-domain expressive intent")
        else:
            adjustment += min(conservative_score, 4.0) * 1.0
            adjustment -= max(0.0, expressive_score - 1.0) * 0.8
            parts.append("balanced-domain neutral bias")
        if operational_score > 0 and query_signals.get("prefer_layout"):
            adjustment += min(operational_score, 4.0) * 0.8
            parts.append("balanced-domain operational signal")
    elif domain == "expressive":
        adjustment += min(expressive_score, 5.0) * 1.6
        adjustment -= max(0.0, conservative_score - 1.0) * 0.3
        parts.append("expressive-domain creativity bias")

    if explicit_conservative:
        adjustment += min(conservative_score, 4.0) * 1.0
        adjustment -= min(expressive_score, 4.0) * 0.6
        parts.append("explicit conservative intent")

    if prefer_layout:
        if stype == "layout":
            layout_bonus = 1.5 + min(operational_score, 4.0) * 0.9
            adjustment += layout_bonus
            parts.append("layout intent matches styleType")
            if operational_score > 0:
                parts.append("layout style has operational semantics")
            elif domain == "strict" and not explicit_expressive:
                adjustment -= 20.0
                parts.append("strict domain penalizes non-operational layout")
            elif domain == "balanced":
                adjustment -= 8.0
                parts.append("balanced domain penalizes non-operational layout")
        elif domain == "strict":
            penalty = 2.2
            if operational_score < 1.0:
                penalty += 1.1
            if not explicit_expressive:
                penalty += 0.7
            adjustment -= penalty
            parts.append("strict+layout intent penalizes non-layout styleType")
        elif domain == "balanced":
            penalty = 0.8 if operational_score >= 1.0 else 1.2
            adjustment -= penalty
            parts.append("balanced+layout intent penalizes non-layout styleType")

    details = {
        "domain": domain,
        "adjustment": round(adjustment, 4),
        "parts": parts,
        "signals": {
            "strict_hits": query_signals.get("strict_hits", []),
            "balanced_hits": query_signals.get("balanced_hits", []),
            "expressive_domain_hits": query_signals.get("expressive_domain_hits", []),
            "expressive_intent_hits": query_signals.get("expressive_intent_hits", []),
            "conservative_intent_hits": query_signals.get("conservative_intent_hits", []),
            "layout_intent_hits": query_signals.get("layout_intent_hits", []),
        },
        "style_profile": {
            "expressive_hits": style_profile.get("expressive_hits", []),
            "conservative_hits": style_profile.get("conservative_hits", []),
            "operational_hits": style_profile.get("operational_hits", []),
        },
    }
    return adjustment, details


def heuristic_score(style: dict[str, Any], query: str, qtokens: list[str]) -> tuple[float, dict[str, Any]]:
    score = 0.0
    query_lower = normalize_text(query)

    slug = normalize_text(style.get("slug"))
    name = normalize_text(style.get("name"))
    name_en = normalize_text(style.get("nameEn"))
    stype = normalize_text(style.get("styleType"))

    matched_keywords = sorted(set(tokenize(" ".join(style.get("keywords", [])))) & set(qtokens))
    matched_tags = sorted(set(tokenize(" ".join(style.get("tags", [])))) & set(qtokens))

    exact_slug = bool(slug and slug in query_lower)
    exact_name = bool((name and name in query_lower) or (name_en and name_en in query_lower))
    style_type_match = bool(stype and stype in query_lower)

    if exact_slug:
        score += 30
    if exact_name:
        score += 20
    if style_type_match:
        score += 8

    score += min(len(matched_keywords), 8) * 6
    score += min(len(matched_tags), 5) * 4

    ai_tokens = set(tokenize(style.get("aiRules", "")))
    concept_overlap = len(ai_tokens & set(qtokens))
    score += min(concept_overlap, 10) * 0.6

    query_signals = infer_query_signals(query, qtokens)
    style_profile = infer_style_profile(style)
    domain_adjustment, domain_details = domain_style_adjustment(style, query_signals, style_profile)
    score += domain_adjustment

    reasons = {
        "exact_slug": exact_slug,
        "exact_name": exact_name,
        "style_type_match": style_type_match,
        "matched_keywords": matched_keywords[:8],
        "matched_tags": matched_tags[:6],
        "concept_overlap": concept_overlap,
        "domain_adjustment": round(domain_adjustment, 4),
        "domain_details": domain_details,
    }
    return score, reasons


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Style Search Result",
        f"- Query: {payload['query']}",
        f"- Site type: {payload.get('site_profile', {}).get('site_type', 'general')}",
        f"- Returned: {len(payload['candidates'])}",
        "",
    ]

    for i, item in enumerate(payload["candidates"], start=1):
        lines.append(f"## {i}. {item['slug']} ({item['nameEn']})")
        lines.append(f"- Score: {item['score']}")
        lines.append(f"- Type: {item['styleType']}")
        lines.append(f"- Matched keywords: {', '.join(item['reason']['matched_keywords']) or '(none)'}")
        lines.append(f"- Matched tags: {', '.join(item['reason']['matched_tags']) or '(none)'}")
        lines.append(f"- Why: {item['reason_summary']}")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Search StyleKit styles and rank candidates")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--query", required=True, help="User requirement or desired visual direction")
    parser.add_argument("--top", type=int, default=5, help="Top candidates to return")
    parser.add_argument("--style-type", choices=["visual", "layout", "animation"], help="Filter by style type")
    parser.add_argument("--site-type", default="auto", choices=["auto", *SITE_TYPES], help="Site type routing hint")
    parser.add_argument("--catalog", default=str(CATALOG_DEFAULT), help="Path to style-prompts.json")
    parser.add_argument("--index", default=str(INDEX_DEFAULT), help="Path to style-search-index.json")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    args = parser.parse_args()
    payload = run(
        query=args.query,
        top=args.top,
        style_type=args.style_type,
        site_type=args.site_type,
        catalog=args.catalog,
        index=args.index,
    )
    if args.format == "markdown":
        print(format_markdown(payload))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def run(
    *,
    query: str,
    top: int = 5,
    style_type: str | None = None,
    site_type: str = "auto",
    catalog: str = str(CATALOG_DEFAULT),
    index: str = str(INDEX_DEFAULT),
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

    docs: list[str]
    slug_for_doc: list[str]
    bm25_map: dict[str, float] = {}

    index_path = Path(index)
    if index_path.exists():
        index_data = load_json(index_path)
        docs_data = index_data.get("documents", [])
        docs = [doc.get("text", "") for doc in docs_data]
        slug_for_doc = [doc.get("slug", "") for doc in docs_data]
    else:
        docs = [build_text(s) for s in styles]
        slug_for_doc = [s.get("slug", "") for s in styles]

    qtokens_base = tokenize(query)
    qtokens = expand_query_tokens(qtokens_base)
    v2_refs = load_v2_references(REF_DIR)
    site_profile = resolve_site_type(query, site_type, v2_refs["aliases"])
    route = routing_for_site_type(site_profile["site_type"], v2_refs["routing"])

    bm25 = BM25()
    bm25.fit(docs)
    for idx, score in bm25.score(query_tokens=qtokens):
        slug = slug_for_doc[idx] if idx < len(slug_for_doc) else ""
        if slug:
            bm25_map[slug] = score

    ranked = []
    for style in styles:
        h_score, reasons = heuristic_score(style, query, qtokens)
        b_score = bm25_map.get(style.get("slug", ""), 0.0)
        routing_adjustment, routing_details = routing_adjustment_for_style(
            style=style,
            site_type=site_profile["site_type"],
            route=route,
            style_map_payload=v2_refs["style_map"],
            query=query,
        )
        final_score = b_score * 3.0 + h_score + routing_adjustment

        reason_parts = []
        if reasons["exact_slug"]:
            reason_parts.append("query includes exact slug")
        if reasons["exact_name"]:
            reason_parts.append("query includes style name")
        if reasons["matched_keywords"]:
            reason_parts.append("keyword overlap")
        if reasons["matched_tags"]:
            reason_parts.append("tag overlap")
        if routing_adjustment != 0:
            reason_parts.append("site-type route bias")
        if not reason_parts:
            reason_parts.append("semantic overlap from style description and rules")

        reasons["site_type_adjustment"] = routing_adjustment
        reasons["site_route_details"] = routing_details

        ranked.append(
            {
                "slug": style.get("slug"),
                "name": style.get("name"),
                "nameEn": style.get("nameEn"),
                "styleType": style.get("styleType"),
                "score": round(final_score, 4),
                "reason": reasons,
                "reason_summary": "; ".join(reason_parts),
                "preview": {
                    "keywords": style.get("keywords", [])[:8],
                    "tags": style.get("tags", []),
                },
            }
        )

    ranked.sort(key=lambda item: item["score"], reverse=True)
    top_n = max(top, 1)

    return {
        "query": query,
        "query_tokens": qtokens_base[:20],
        "expanded_query_tokens": qtokens[:40],
        "top": top_n,
        "returned": min(top_n, len(ranked)),
        "style_type_filter": style_type,
        "site_type_filter": site_type,
        "site_profile": site_profile,
        "schemaVersion": "2.0.0",
        "catalog_schema_version": catalog_data.get("schemaVersion", "unknown"),
        "generatedAt": catalog_data.get("generatedAt"),
        "candidates": ranked[:top_n],
    }


if __name__ == "__main__":
    main()

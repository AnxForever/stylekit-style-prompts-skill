#!/usr/bin/env python3
"""Audit raw style-rule quality and effective rule quality after normalization."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from generate_brief import (
    detect_lang,
    ensure_min_rules,
    extract_rules,
    rule_polarity,
)

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
REF_DIR = SKILL_ROOT / "references"
CATALOG_DEFAULT = REF_DIR / "style-prompts.json"

ROUNDED_NONE_RE = re.compile(r"\brounded-none\b", re.IGNORECASE)
ROUNDED_OTHER_RE = re.compile(r"\brounded-(?!none\b)(?:sm|md|lg|xl|2xl|3xl|full|base)\b", re.IGNORECASE)
SHADOW_NONE_RE = re.compile(r"\bshadow-none\b", re.IGNORECASE)
SHADOW_OTHER_RE = re.compile(r"\bshadow-(?!none\b)(?:sm|md|lg|xl|2xl|3xl|base|\[[^\]]+\])\b", re.IGNORECASE)
BG_WHITE_OPAQUE_RE = re.compile(r"\bbg-white\b(?!/)", re.IGNORECASE)
BG_WHITE_TRANS_RE = re.compile(r"\bbg-white/[0-9]{1,3}\b", re.IGNORECASE)
CLASS_TOKEN_RE = re.compile(r"\b[a-z]+(?:-[a-z0-9\[\]#/%.]+)+\b", re.IGNORECASE)


def load_catalog(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("styles", [])


def has_radius_mix(text: str) -> bool:
    return bool(ROUNDED_NONE_RE.search(text) and ROUNDED_OTHER_RE.search(text))


def has_shadow_mix(text: str) -> bool:
    return bool(SHADOW_NONE_RE.search(text) and SHADOW_OTHER_RE.search(text))


def has_bg_opacity_mix(text: str) -> bool:
    return bool(BG_WHITE_OPAQUE_RE.search(text) and BG_WHITE_TRANS_RE.search(text))


def do_dont_overlap(style: dict[str, Any]) -> list[str]:
    do_text = "\n".join(style.get("doList", []))
    dont_text = "\n".join(style.get("dontList", []))
    do_tokens = set(CLASS_TOKEN_RE.findall(do_text.lower()))
    dont_tokens = set(CLASS_TOKEN_RE.findall(dont_text.lower()))
    overlap = sorted(do_tokens & dont_tokens)
    return overlap


def summarize_conflicts(styles: list[dict[str, Any]]) -> dict[str, Any]:
    raw_radius: list[str] = []
    raw_shadow: list[str] = []
    raw_bg: list[str] = []
    effective_radius: list[str] = []
    effective_shadow: list[str] = []
    effective_bg: list[str] = []
    do_dont_overlaps: list[dict[str, Any]] = []

    for style in styles:
        slug = str(style.get("slug", "unknown"))
        ai_rules_text = str(style.get("aiRules", ""))
        do_text = "\n".join(style.get("doList", []))

        if has_radius_mix(ai_rules_text):
            raw_radius.append(slug)
        if has_shadow_mix(ai_rules_text):
            raw_shadow.append(slug)
        if has_bg_opacity_mix(ai_rules_text):
            raw_bg.append(slug)
        # Keep visibility for raw doList quality as well.
        if has_radius_mix(do_text):
            raw_radius.append(f"{slug}#doList")
        if has_shadow_mix(do_text):
            raw_shadow.append(f"{slug}#doList")
        if has_bg_opacity_mix(do_text):
            raw_bg.append(f"{slug}#doList")

        lang = detect_lang(f"{style.get('name', '')}\n{ai_rules_text}")
        rules = extract_rules(ai_rules_text, lang)
        rules = ensure_min_rules(rules, style.get("doList", []), style.get("dontList", []), lang)
        positive_rules = [rule for rule in rules if rule_polarity(rule) == "pos"]
        positive_text = "\n".join(positive_rules)

        if has_radius_mix(positive_text):
            effective_radius.append(slug)
        if has_shadow_mix(positive_text):
            effective_shadow.append(slug)
        if has_bg_opacity_mix(positive_text):
            effective_bg.append(slug)

        overlap = do_dont_overlap(style)
        if overlap:
            do_dont_overlaps.append({"slug": slug, "overlap": overlap[:8], "count": len(overlap)})

    return {
        "total_styles": len(styles),
        "raw_conflicts": {
            "rounded_mix_styles": sorted(raw_radius),
            "shadow_mix_styles": sorted(raw_shadow),
            "bg_opacity_mix_styles": sorted(raw_bg),
        },
        "effective_conflicts": {
            "rounded_mix_styles": sorted(effective_radius),
            "shadow_mix_styles": sorted(effective_shadow),
            "bg_opacity_mix_styles": sorted(effective_bg),
        },
        "do_dont_overlap": {
            "styles": do_dont_overlaps,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit style rule conflicts")
    parser.add_argument("--catalog", default=str(CATALOG_DEFAULT), help="Path to style-prompts.json")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args()

    styles = load_catalog(Path(args.catalog))
    summary = summarize_conflicts(styles)

    if args.format == "json":
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    raw = summary["raw_conflicts"]
    eff = summary["effective_conflicts"]
    print(f"Total styles: {summary['total_styles']}")
    print(
        "Raw conflicts:"
        f" rounded={len(raw['rounded_mix_styles'])}"
        f", shadow={len(raw['shadow_mix_styles'])}"
        f", bg={len(raw['bg_opacity_mix_styles'])}"
    )
    print(
        "Effective conflicts (after normalization):"
        f" rounded={len(eff['rounded_mix_styles'])}"
        f", shadow={len(eff['shadow_mix_styles'])}"
        f", bg={len(eff['bg_opacity_mix_styles'])}"
    )
    print(f"Do/Dont class overlap styles: {len(summary['do_dont_overlap']['styles'])}")


if __name__ == "__main__":
    main()

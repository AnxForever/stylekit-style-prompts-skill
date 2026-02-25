#!/usr/bin/env python3
"""Validate taxonomy data files for consistency and coverage."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
REF_DIR = SKILL_ROOT / "references"
TAX_DIR = REF_DIR / "taxonomy"
TAG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def normalize_tag(value: str) -> str:
    return str(value or "").strip().lower()


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate(
    min_coverage: float = 0.70,
    *,
    routing_file: str | None = None,
    style_tag_registry_file: str | None = None,
    max_unused_style_tags: int | None = None,
    fail_on_warning: bool = False,
) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    # --- Load sources of truth ---
    catalog = load_json(REF_DIR / "style-prompts.json")
    catalog_slugs = {s["slug"] for s in catalog["styles"]}

    schema = load_json(TAX_DIR / "tag-schema.json")
    dims = schema["dimensions"]
    valid_visual = set(dims["visual_style"]["values"])
    valid_layout = set(dims["layout_archetype"]["values"])
    valid_motion = set(dims["motion_profile"]["values"])
    valid_interaction = set(dims["interaction_pattern"]["values"])
    valid_modifiers = set(dims["modifiers"]["values"])
    valid_site_types = set(dims["site_type"]["values"])

    # --- Validate style-tag-map.v2.json ---
    tag_map = load_json(TAX_DIR / "style-tag-map.v2.json")
    mappings = tag_map.get("style_mappings", {})

    mapped_valid = 0
    for slug, entry in mappings.items():
        if slug not in catalog_slugs:
            errors.append(f"style-tag-map: slug '{slug}' not in catalog")
        else:
            mapped_valid += 1

        vs = entry.get("visual_style")
        if vs and vs not in valid_visual:
            errors.append(f"style-tag-map[{slug}]: visual_style '{vs}' not in enum")

        for lh in entry.get("layout_archetype_hints", []):
            if lh not in valid_layout:
                errors.append(f"style-tag-map[{slug}]: layout hint '{lh}' not in enum")

        for mh in entry.get("motion_profile_hints", []):
            if mh not in valid_motion:
                errors.append(f"style-tag-map[{slug}]: motion hint '{mh}' not in enum")

        for ih in entry.get("interaction_pattern_hints", []):
            if ih not in valid_interaction:
                errors.append(f"style-tag-map[{slug}]: interaction hint '{ih}' not in enum")

        for mod in entry.get("modifiers", []):
            if mod not in valid_modifiers:
                errors.append(f"style-tag-map[{slug}]: modifier '{mod}' not in enum")

    coverage = mapped_valid / len(catalog_slugs) if catalog_slugs else 0.0
    if coverage < min_coverage:
        errors.append(f"style-tag-map: coverage {coverage:.2%} < {min_coverage:.0%}")

    # --- Validate animation-profiles.v2.json ---
    anim_path = TAX_DIR / "animation-profiles.v2.json"
    if anim_path.exists():
        anim = load_json(anim_path)
        profiles = anim.get("profiles", {})
        for name, prof in profiles.items():
            mp = prof.get("motion_profile")
            if mp and mp not in valid_motion:
                errors.append(f"animation-profiles[{name}]: motion_profile '{mp}' not in enum")
            for st in prof.get("suitable_site_types", []):
                if st not in valid_site_types:
                    errors.append(f"animation-profiles[{name}]: site_type '{st}' not in enum")
            for field in ("intent", "trigger", "states", "duration_range_ms", "easing",
                          "reduced_motion_fallback", "suitable_site_types", "anti_patterns"):
                if field not in prof:
                    errors.append(f"animation-profiles[{name}]: missing required field '{field}'")
    else:
        errors.append("animation-profiles.v2.json not found")

    # --- Validate interaction-patterns.v2.json ---
    ipt_path = TAX_DIR / "interaction-patterns.v2.json"
    if ipt_path.exists():
        ipt = load_json(ipt_path)
        patterns = ipt.get("patterns", {})
        for name, pat in patterns.items():
            if name not in valid_interaction:
                errors.append(f"interaction-patterns: pattern key '{name}' not in enum")
            for st in pat.get("suitable_site_types", []):
                if st not in valid_site_types:
                    errors.append(f"interaction-patterns[{name}]: site_type '{st}' not in enum")
            for field in ("primary_goal", "suitable_site_types", "required_components",
                          "state_coverage_requirements", "accessibility_constraints", "anti_patterns"):
                if field not in pat:
                    errors.append(f"interaction-patterns[{name}]: missing required field '{field}'")
    else:
        errors.append("interaction-patterns.v2.json not found")

    # --- Load style tag registry ---
    registry_path = Path(style_tag_registry_file) if style_tag_registry_file else (TAX_DIR / "style-tag-registry.json")
    if not registry_path.exists():
        errors.append(f"style-tag-registry file not found: {registry_path}")
        allowed_style_tags: set[str] = set()
    else:
        registry = load_json(registry_path)
        allowed_raw = registry.get("allowed_style_tags", [])
        allowed_style_tags = set()
        if not isinstance(allowed_raw, list):
            errors.append(f"style-tag-registry[{registry_path}]: allowed_style_tags must be a list")
        else:
            for tag in allowed_raw:
                if not isinstance(tag, str) or not tag.strip():
                    errors.append(f"style-tag-registry[{registry_path}]: contains non-string tag")
                    continue
                normalized = normalize_tag(tag)
                if TAG_PATTERN.fullmatch(normalized) is None:
                    errors.append(
                        f"style-tag-registry[{registry_path}]: tag '{tag}' must use kebab-case tokens"
                    )
                    continue
                allowed_style_tags.add(normalized)

    # --- Validate site-type-routing.json cross-references ---
    routing_path = Path(routing_file) if routing_file else (TAX_DIR / "site-type-routing.json")
    routing = load_json(routing_path)
    anim_profile_keys = set(profiles.keys()) if anim_path.exists() else set()
    ipt_pattern_keys = set(patterns.keys()) if ipt_path.exists() else set()

    for st_name, st_data in routing.get("site_types", {}).items():
        if st_name not in valid_site_types:
            errors.append(f"site-type-routing: key '{st_name}' not in site_type enum")
        for layout in st_data.get("preferred_layout_archetypes", []):
            if layout not in valid_layout:
                errors.append(f"site-type-routing[{st_name}]: layout archetype '{layout}' not in layout_archetype enum")
        for ap in st_data.get("recommended_animation_profiles", []):
            if ap not in anim_profile_keys:
                errors.append(f"site-type-routing[{st_name}]: animation profile '{ap}' not in animation-profiles.v2.json")
        for ip in st_data.get("recommended_interaction_patterns", []):
            if ip not in ipt_pattern_keys:
                errors.append(f"site-type-routing[{st_name}]: interaction pattern '{ip}' not in interaction-patterns.v2.json")
        for mp in st_data.get("preferred_motion_profiles", []):
            if mp not in valid_motion:
                errors.append(f"site-type-routing[{st_name}]: motion profile '{mp}' not in motion_profile enum")
        for ip in st_data.get("preferred_interaction_patterns", []):
            if ip not in valid_interaction:
                errors.append(f"site-type-routing[{st_name}]: interaction pattern '{ip}' not in interaction_pattern enum")
        for field in ("favored_style_tags", "penalized_style_tags"):
            tags = st_data.get(field, [])
            if not isinstance(tags, list):
                errors.append(f"site-type-routing[{st_name}]: '{field}' must be a list")
                continue
            for tag in tags:
                if not isinstance(tag, str) or not tag.strip():
                    errors.append(f"site-type-routing[{st_name}]: '{field}' contains non-string tag")
                    continue
                normalized = normalize_tag(tag)
                if TAG_PATTERN.fullmatch(normalized) is None:
                    errors.append(
                        f"site-type-routing[{st_name}]: '{field}' tag '{tag}' must use kebab-case tokens"
                    )
                    continue
                if normalized not in allowed_style_tags:
                    errors.append(
                        f"site-type-routing[{st_name}]: '{field}' tag '{tag}' not in style-tag-registry"
                    )
    used_style_tags: set[str] = set()
    for st_data in routing.get("site_types", {}).values():
        if not isinstance(st_data, dict):
            continue
        for field in ("favored_style_tags", "penalized_style_tags"):
            tags = st_data.get(field, [])
            if not isinstance(tags, list):
                continue
            for tag in tags:
                if isinstance(tag, str) and tag.strip():
                    used_style_tags.add(normalize_tag(tag))

    allowed_count = len(allowed_style_tags)
    used_count = len(used_style_tags.intersection(allowed_style_tags))
    unused_style_tags = sorted(allowed_style_tags - used_style_tags)
    unused_count = len(unused_style_tags)
    usage_ratio = (used_count / allowed_count) if allowed_count else 0.0

    if max_unused_style_tags is not None and unused_count > max_unused_style_tags:
        errors.append(
            f"style-tag-registry: unused tag count {unused_count} exceeds limit {max_unused_style_tags}"
        )
    elif max_unused_style_tags is None and unused_count > 0:
        warnings.append(
            "style-tag-registry: unused style tags detected; "
            "use --max-unused-style-tags to enforce a hard limit"
        )

    if fail_on_warning and warnings:
        errors.append(f"fail-on-warning enabled: {len(warnings)} warning(s)")

    status = "pass" if not errors else "fail"
    return {
        "status": status,
        "coverage": round(coverage, 4),
        "errors": errors,
        "warnings": warnings,
        "style_tag_registry_stats": {
            "allowed_count": allowed_count,
            "used_count": used_count,
            "unused_count": unused_count,
            "usage_ratio": round(usage_ratio, 4),
            "unused_tags": unused_style_tags[:50],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate taxonomy data files")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument("--min-coverage", type=float, default=0.70)
    parser.add_argument("--routing-file", default="", help="Optional path override for site-type-routing.json")
    parser.add_argument(
        "--style-tag-registry-file",
        default="",
        help="Optional path override for style-tag-registry.json",
    )
    parser.add_argument(
        "--max-unused-style-tags",
        type=int,
        default=-1,
        help="Fail when unused style tags exceed this count. Use -1 to disable.",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Treat warnings as failures (non-zero exit when warnings are present).",
    )
    args = parser.parse_args()

    result = validate(
        min_coverage=args.min_coverage,
        routing_file=args.routing_file or None,
        style_tag_registry_file=args.style_tag_registry_file or None,
        max_unused_style_tags=None if args.max_unused_style_tags < 0 else args.max_unused_style_tags,
        fail_on_warning=args.fail_on_warning,
    )

    if args.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Status: {result['status']}")
        print(f"Coverage: {result['coverage']:.2%}")
        stats = result.get("style_tag_registry_stats", {}) or {}
        print(
            "Style-tag registry usage:"
            f" used={stats.get('used_count', 0)}/{stats.get('allowed_count', 0)}"
            f" ({stats.get('usage_ratio', 0.0):.2%}), unused={stats.get('unused_count', 0)}"
        )
        if stats.get("unused_tags"):
            print(f"Unused tags sample: {', '.join(stats.get('unused_tags', [])[:10])}")
        if result.get("warnings"):
            print(f"Warnings ({len(result['warnings'])}):")
            for item in result["warnings"]:
                print(f"  - {item}")
        if result["errors"]:
            print(f"Errors ({len(result['errors'])}):")
            for e in result["errors"]:
                print(f"  - {e}")
        else:
            print("No errors found.")

    sys.exit(0 if result["status"] == "pass" else 1)


if __name__ == "__main__":
    main()

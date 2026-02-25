#!/usr/bin/env python3
"""Merge Gemini-generated taxonomy expansions into existing JSON files.

Usage:
  # Dry-run (validate only, no writes):
  python3 scripts/merge_taxonomy_expansion.py --type animation --input gemini-output.json --dry-run

  # Apply merge:
  python3 scripts/merge_taxonomy_expansion.py --type animation --input gemini-output.json

  # For interaction patterns:
  python3 scripts/merge_taxonomy_expansion.py --type interaction --input gemini-output.json

Input JSON supports optional style tag registry updates:
  "new_style_tags": ["professional", {"tag": "brand-future"}]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
TAX_DIR = SKILL_ROOT / "references" / "taxonomy"
STYLE_TAG_REGISTRY = TAX_DIR / "style-tag-registry.json"
TAG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  Written: {path}")


def is_string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def is_state_coverage_map(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    for states in value.values():
        if not is_string_list(states):
            return False
    return True


def normalize_tag(value: str) -> str:
    return str(value or "").strip().lower()


def extract_new_style_tags(input_data: dict, existing_tags: set[str], errors: list[str]) -> list[str]:
    raw = input_data.get("new_style_tags", [])
    if raw in (None, ""):
        return []
    if not isinstance(raw, list):
        errors.append("new_style_tags must be a list")
        return []

    added: list[str] = []
    for idx, item in enumerate(raw):
        if isinstance(item, dict):
            candidate = item.get("tag") or item.get("value")
        else:
            candidate = item
        if not isinstance(candidate, str) or not candidate.strip():
            errors.append(f"new_style_tags[{idx}] must be a non-empty string")
            continue
        tag = normalize_tag(candidate)
        if TAG_PATTERN.fullmatch(tag) is None:
            errors.append(f"new_style_tags[{idx}] '{candidate}' must be kebab-case")
            continue
        if tag in existing_tags or tag in added:
            continue
        added.append(tag)
    return added


def load_style_tag_registry(errors: list[str]) -> tuple[dict, set[str]]:
    if not STYLE_TAG_REGISTRY.exists():
        errors.append(f"Missing style tag registry: {STYLE_TAG_REGISTRY}")
        return {"schemaVersion": "2.0.0", "allowed_style_tags": []}, set()

    registry = load_json(STYLE_TAG_REGISTRY)
    raw = registry.get("allowed_style_tags", [])
    if not isinstance(raw, list):
        errors.append("style-tag-registry: allowed_style_tags must be a list")
        return registry, set()

    tags: set[str] = set()
    for idx, item in enumerate(raw):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"style-tag-registry: allowed_style_tags[{idx}] must be a non-empty string")
            continue
        normalized = normalize_tag(item)
        if TAG_PATTERN.fullmatch(normalized) is None:
            errors.append(f"style-tag-registry: invalid tag '{item}'")
            continue
        tags.add(normalized)
    return registry, tags


def apply_style_tag_registry_update(registry: dict, existing_tags: set[str], added_tags: list[str], dry_run: bool) -> None:
    if not added_tags:
        return
    print(f"  New style tags to add: {added_tags}")
    if dry_run:
        return

    merged = sorted(existing_tags.union(added_tags))
    registry["allowed_style_tags"] = merged
    save_json(STYLE_TAG_REGISTRY, registry)


def merge_animation(input_data: dict, dry_run: bool) -> list[str]:
    errors: list[str] = []
    schema = load_json(TAX_DIR / "tag-schema.json")
    anim = load_json(TAX_DIR / "animation-profiles.v2.json")
    valid_motion = set(schema["dimensions"]["motion_profile"]["values"])
    valid_sites = set(schema["dimensions"]["site_type"]["values"])
    style_tag_registry, existing_style_tags = load_style_tag_registry(errors)

    new_enums = input_data.get("new_enum_values", [])
    new_profiles = input_data.get("new_profiles", {})
    new_style_tags = extract_new_style_tags(input_data, existing_style_tags, errors)

    required_fields = {"motion_profile", "intent", "trigger", "states",
                       "duration_range_ms", "easing", "reduced_motion_fallback",
                       "suitable_site_types", "anti_patterns"}

    # Register new enum values
    added_enums = []
    for item in new_enums:
        val = item.get("value", "")
        if val and val not in valid_motion:
            valid_motion.add(val)
            added_enums.append(val)

    # Validate profiles
    added_profiles = []
    for name, prof in new_profiles.items():
        missing = required_fields - set(prof.keys())
        if missing:
            errors.append(f"Profile '{name}' missing fields: {', '.join(sorted(missing))}")
            continue
        mp = prof.get("motion_profile")
        if mp not in valid_motion:
            errors.append(f"Profile '{name}': motion_profile '{mp}' not in enum (including new values)")
            continue
        suitable_site_types = prof.get("suitable_site_types", [])
        if not is_string_list(suitable_site_types):
            errors.append(f"Profile '{name}': suitable_site_types must be a list of strings")
            continue
        for st in suitable_site_types:
            if st not in valid_sites:
                errors.append(f"Profile '{name}': site_type '{st}' not in enum")
        states = prof.get("states", [])
        if not is_string_list(states):
            errors.append(f"Profile '{name}': states must be a list of strings")
            continue
        dur = prof.get("duration_range_ms", [])
        if not isinstance(dur, list) or len(dur) != 2 or not all(isinstance(v, (int, float)) for v in dur):
            errors.append(f"Profile '{name}': duration_range_ms must be [min, max]")
            continue
        if dur[0] > dur[1]:
            errors.append(f"Profile '{name}': duration_range_ms min must be <= max")
        if not isinstance(prof.get("anti_patterns", []), list):
            errors.append(f"Profile '{name}': anti_patterns must be a list")
        if name in anim.get("profiles", {}):
            errors.append(f"Profile '{name}' already exists — skipping (use a different name)")
            continue
        added_profiles.append(name)

    print(f"\n  New enum values: {added_enums or '(none)'}")
    print(f"  New style tags to add: {new_style_tags or '(none)'}")
    print(f"  New profiles to add: {len(added_profiles)}")
    print(f"  Validation errors: {len(errors)}")
    for e in errors:
        print(f"    ✗ {e}")

    if errors:
        print("\n  ⚠ Fix errors above before merging.")
        return errors

    if dry_run:
        print("\n  Dry-run complete. Use without --dry-run to apply.")
        return errors

    # Apply
    if added_enums:
        schema["dimensions"]["motion_profile"]["values"].extend(added_enums)
        save_json(TAX_DIR / "tag-schema.json", schema)
    apply_style_tag_registry_update(style_tag_registry, existing_style_tags, new_style_tags, dry_run)

    for name in added_profiles:
        anim["profiles"][name] = new_profiles[name]
    save_json(TAX_DIR / "animation-profiles.v2.json", anim)

    print(
        f"\n  ✓ Merged {len(added_profiles)} profiles + {len(added_enums)} enum values"
        f" + {len(new_style_tags)} style tags."
    )
    return errors


def merge_interaction(input_data: dict, dry_run: bool) -> list[str]:
    errors: list[str] = []
    schema = load_json(TAX_DIR / "tag-schema.json")
    ipt = load_json(TAX_DIR / "interaction-patterns.v2.json")
    valid_interaction = set(schema["dimensions"]["interaction_pattern"]["values"])
    valid_sites = set(schema["dimensions"]["site_type"]["values"])
    style_tag_registry, existing_style_tags = load_style_tag_registry(errors)

    new_enums = input_data.get("new_enum_values", [])
    new_patterns = input_data.get("new_patterns", {})
    additions = input_data.get("existing_pattern_additions", {})
    new_style_tags = extract_new_style_tags(input_data, existing_style_tags, errors)

    required_fields = {"primary_goal", "suitable_site_types", "required_components",
                       "state_coverage_requirements", "accessibility_constraints", "anti_patterns"}

    added_enums = []
    for item in new_enums:
        val = item.get("value", "")
        if val and val not in valid_interaction:
            valid_interaction.add(val)
            added_enums.append(val)

    added_patterns = []
    for name, pat in new_patterns.items():
        missing = required_fields - set(pat.keys())
        if missing:
            errors.append(f"Pattern '{name}' missing fields: {', '.join(sorted(missing))}")
            continue
        if name not in valid_interaction:
            errors.append(f"Pattern '{name}' not in enum (add it to new_enum_values first)")
            continue
        suitable_site_types = pat.get("suitable_site_types", [])
        if not is_string_list(suitable_site_types):
            errors.append(f"Pattern '{name}': suitable_site_types must be a list of strings")
            continue
        for st in suitable_site_types:
            if st not in valid_sites:
                errors.append(f"Pattern '{name}': site_type '{st}' not in enum")
        if not is_string_list(pat.get("required_components", [])):
            errors.append(f"Pattern '{name}': required_components must be a list of strings")
            continue
        if not is_state_coverage_map(pat.get("state_coverage_requirements", {})):
            errors.append(f"Pattern '{name}': state_coverage_requirements must be an object of string[] values")
            continue
        if not is_string_list(pat.get("accessibility_constraints", [])):
            errors.append(f"Pattern '{name}': accessibility_constraints must be a list of strings")
            continue
        if not is_string_list(pat.get("anti_patterns", [])):
            errors.append(f"Pattern '{name}': anti_patterns must be a list of strings")
            continue
        if name in ipt.get("patterns", {}):
            errors.append(f"Pattern '{name}' already exists — skipping")
            continue
        added_patterns.append(name)

    # Validate additions to existing patterns
    enriched = []
    for name, add_data in additions.items():
        if name not in ipt.get("patterns", {}):
            errors.append(f"Addition target '{name}' not found in existing patterns")
            continue
        new_states = add_data.get("new_state_coverage", {})
        if new_states and not is_state_coverage_map(new_states):
            errors.append(
                f"Addition target '{name}': new_state_coverage must be an object of string[] values"
            )
            continue
        if not new_states:
            continue
        enriched.append((name, new_states))

    print(f"\n  New enum values: {added_enums or '(none)'}")
    print(f"  New style tags to add: {new_style_tags or '(none)'}")
    print(f"  New patterns to add: {len(added_patterns)}")
    print(f"  Existing patterns to enrich: {len(enriched)}")
    print(f"  Validation errors: {len(errors)}")
    for e in errors:
        print(f"    ✗ {e}")

    if errors:
        print("\n  ⚠ Fix errors above before merging.")
        return errors

    if dry_run:
        print("\n  Dry-run complete. Use without --dry-run to apply.")
        return errors

    if added_enums:
        schema["dimensions"]["interaction_pattern"]["values"].extend(added_enums)
        save_json(TAX_DIR / "tag-schema.json", schema)
    apply_style_tag_registry_update(style_tag_registry, existing_style_tags, new_style_tags, dry_run)

    for name in added_patterns:
        ipt["patterns"][name] = new_patterns[name]

    for name, new_states in enriched:
        existing_states = ipt["patterns"][name].get("state_coverage_requirements", {})
        existing_states.update(new_states)
        ipt["patterns"][name]["state_coverage_requirements"] = existing_states

    save_json(TAX_DIR / "interaction-patterns.v2.json", ipt)

    print(
        f"\n  ✓ Merged {len(added_patterns)} patterns + {len(enriched)} enrichments"
        f" + {len(added_enums)} enum values + {len(new_style_tags)} style tags."
    )
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge Gemini taxonomy expansions")
    parser.add_argument("--type", required=True, choices=["animation", "interaction"])
    parser.add_argument("--input", required=True, help="Path to Gemini output JSON file")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, don't write")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        sys.exit(1)

    input_data = load_json(input_path)
    print(f"Loaded {input_path} ({len(json.dumps(input_data))} bytes)")

    if args.type == "animation":
        errors = merge_animation(input_data, args.dry_run)
    else:
        errors = merge_interaction(input_data, args.dry_run)

    if errors:
        sys.exit(1)

    if not args.dry_run:
        print("\nRunning validation...")
        from validate_taxonomy import validate
        result = validate()
        print(f"Taxonomy validation: {result['status']}")
        if result["errors"]:
            for e in result["errors"]:
                print(f"  ✗ {e}")
            sys.exit(1)
        print("✓ All clear.")


if __name__ == "__main__":
    main()

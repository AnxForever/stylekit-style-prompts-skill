"""Reference input handling: payload loading, validation, and signal extraction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from _brief_constants import (
    REFERENCE_FIELD_ALIASES,
    REFERENCE_GUIDELINES,
    REFERENCE_KNOWN_TOP_LEVEL,
    REFERENCE_SECTION_KEYS,
    REFINE_MODE_HINTS,
    dedupe_ordered,
    to_text_list,
)


def build_reference_guidelines(reference_type: str, lang: str) -> list[str]:
    if reference_type == "none":
        return []
    if reference_type == "mixed":
        combined = REFERENCE_GUIDELINES["screenshot"][lang] + REFERENCE_GUIDELINES["figma"][lang]
        return dedupe_ordered(combined)[:6]
    if reference_type in REFERENCE_GUIDELINES:
        return REFERENCE_GUIDELINES[reference_type][lang][:6]
    return []


def refine_mode_strategy(refine_mode: str, lang: str) -> dict[str, Any]:
    mode = refine_mode if refine_mode in REFINE_MODE_HINTS else "new"
    payload = REFINE_MODE_HINTS[mode][lang]
    return {
        "mode": mode,
        "objective": payload["objective"],
        "constraints": payload["constraints"][:6],
    }


def merge_reference_payload(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in incoming.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_reference_payload(merged[key], value)
        elif key in merged and isinstance(merged[key], list) and isinstance(value, list):
            merged[key] = merged[key] + value
        else:
            merged[key] = value
    return merged


def load_reference_payload(reference_json: str, reference_file: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}

    if reference_file.strip():
        path = Path(reference_file.strip())
        if not path.exists():
            raise SystemExit(f"Reference file not found: {path}")
        text = path.read_text(encoding="utf-8").strip()
        if text:
            try:
                loaded = json.loads(text)
                if isinstance(loaded, dict):
                    payload = merge_reference_payload(payload, loaded)
                else:
                    payload = merge_reference_payload(payload, {"notes": str(loaded)})
            except json.JSONDecodeError:
                payload = merge_reference_payload(payload, {"notes": text})

    if reference_json.strip():
        text = reference_json.strip()
        try:
            loaded = json.loads(text)
            if isinstance(loaded, dict):
                payload = merge_reference_payload(payload, loaded)
            else:
                payload = merge_reference_payload(payload, {"notes": str(loaded)})
        except json.JSONDecodeError:
            payload = merge_reference_payload(payload, {"notes": text})

    return payload


def validate_reference_payload_schema(
    payload: dict[str, Any],
    reference_type: str,
    lang: str,
    strict_mode: bool,
) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    coercions: list[str] = []
    unknown_fields: list[str] = []

    if payload and not isinstance(payload, dict):
        errors.append("reference payload must be a JSON object")
        payload = {}

    sanitized = dict(payload or {})

    for section in REFERENCE_SECTION_KEYS:
        if section not in sanitized:
            continue
        value = sanitized.get(section)
        if isinstance(value, dict):
            continue
        if section == "tokens":
            coerced_values = to_text_list(value)
            if coerced_values:
                sanitized[section] = {"values": coerced_values}
                coercions.append(section)
                warnings.append(f"coerced `{section}` to object with `values` list")
                continue
            errors.append(f"`{section}` must be an object or list-like value")
            continue

        coerced_values = to_text_list(value)
        if coerced_values:
            sanitized[section] = {"issues": coerced_values}
            coercions.append(section)
            warnings.append(f"coerced `{section}` to object with `issues` list")
        else:
            errors.append(f"`{section}` must be an object or list-like value")

    for meta_key in ("source", "type"):
        if meta_key in sanitized and not isinstance(sanitized.get(meta_key), str):
            coerced = " ".join(to_text_list(sanitized.get(meta_key))).strip()
            if coerced:
                sanitized[meta_key] = coerced
                coercions.append(meta_key)
                warnings.append(f"coerced `{meta_key}` to string")
            else:
                errors.append(f"`{meta_key}` must be a string")

    for key in sanitized.keys():
        if key not in REFERENCE_KNOWN_TOP_LEVEL:
            unknown_fields.append(key)

    if unknown_fields:
        sample = ", ".join(sorted(unknown_fields)[:6])
        warnings.append(f"unknown top-level fields detected: {sample}")

    source_hint = str(sanitized.get("source", "") or sanitized.get("type", "")).lower()
    if reference_type in {"screenshot", "figma"} and source_hint:
        if reference_type == "screenshot" and "figma" in source_hint:
            warnings.append("reference_type is screenshot but source/type suggests figma")
        if reference_type == "figma" and any(token in source_hint for token in ["screen", "shot", "截图"]):
            warnings.append("reference_type is figma but source/type suggests screenshot")

    if strict_mode and (errors or unknown_fields):
        if errors:
            errors.append("strict schema mode blocks invalid reference payload")
        if unknown_fields:
            errors.append("strict schema mode blocks unknown top-level fields")

    valid = len(errors) == 0
    return {
        "valid": valid,
        "strict_mode": strict_mode,
        "errors": dedupe_ordered(errors),
        "warnings": dedupe_ordered(warnings),
        "coercions": dedupe_ordered(coercions),
        "unknown_fields": sorted(set(unknown_fields)),
        "sanitized_payload": sanitized,
    }


def get_alias_values(payload: dict[str, Any], aliases: list[str]) -> list[str]:
    out: list[str] = []
    for key in aliases:
        if key in payload:
            out.extend(to_text_list(payload.get(key)))
    return dedupe_ordered(out)


def normalize_reference_signals(
    payload: dict[str, Any],
    reference_type: str,
    reference_notes: str,
    lang: str,
) -> dict[str, Any]:
    if not payload and not reference_notes.strip():
        return {
            "has_signals": False,
            "source": reference_type,
            "summary": "",
            "signals": {
                "layout_issues": [],
                "missing_components": [],
                "preserve_elements": [],
                "interaction_gaps": [],
                "a11y_gaps": [],
                "token_clues": [],
                "notes": [],
            },
            "derived_rules": [],
        }

    layout_block = payload.get("layout") if isinstance(payload.get("layout"), dict) else {}
    component_block = payload.get("components") if isinstance(payload.get("components"), dict) else {}
    interaction_block = payload.get("interaction") if isinstance(payload.get("interaction"), dict) else {}
    a11y_block = payload.get("accessibility") if isinstance(payload.get("accessibility"), dict) else {}
    token_block = payload.get("tokens") if isinstance(payload.get("tokens"), dict) else {}

    layout_issues = get_alias_values(payload, REFERENCE_FIELD_ALIASES["layout_issues"])
    layout_issues.extend(get_alias_values(layout_block, ["issues", "problem", "problems", "gaps"]))

    missing_components = get_alias_values(payload, REFERENCE_FIELD_ALIASES["missing_components"])
    missing_components.extend(get_alias_values(component_block, ["missing", "gaps"]))

    preserve_elements = get_alias_values(payload, REFERENCE_FIELD_ALIASES["preserve_elements"])
    preserve_elements.extend(get_alias_values(layout_block, ["preserve", "keep"]))
    preserve_elements.extend(get_alias_values(component_block, ["preserve", "keep"]))

    interaction_gaps = get_alias_values(payload, REFERENCE_FIELD_ALIASES["interaction_gaps"])
    interaction_gaps.extend(get_alias_values(interaction_block, ["missing_states", "gaps", "issues"]))

    a11y_gaps = get_alias_values(payload, REFERENCE_FIELD_ALIASES["a11y_gaps"])
    a11y_gaps.extend(get_alias_values(a11y_block, ["issues", "gaps", "missing"]))

    token_clues = get_alias_values(payload, REFERENCE_FIELD_ALIASES["token_clues"])
    token_clues.extend(get_alias_values(token_block, ["colors", "spacing", "typography", "radius", "shadows"]))

    notes = get_alias_values(payload, REFERENCE_FIELD_ALIASES["notes"])
    if reference_notes.strip():
        notes.append(reference_notes.strip())

    layout_issues = dedupe_ordered(layout_issues)[:5]
    missing_components = dedupe_ordered(missing_components)[:5]
    preserve_elements = dedupe_ordered(preserve_elements)[:5]
    interaction_gaps = dedupe_ordered(interaction_gaps)[:5]
    a11y_gaps = dedupe_ordered(a11y_gaps)[:5]
    token_clues = dedupe_ordered(token_clues)[:6]
    notes = dedupe_ordered(notes)[:3]

    derived_rules: list[str] = []
    if lang == "zh":
        derived_rules.extend([f"修复参考输入中的布局问题：{item}。" for item in layout_issues[:3]])
        derived_rules.extend([f"补齐缺失组件/状态：{item}。" for item in missing_components[:2]])
        derived_rules.extend([f"保留既有结构要素：{item}。" for item in preserve_elements[:2]])
        derived_rules.extend([f"补全交互缺口：{item}。" for item in interaction_gaps[:2]])
        derived_rules.extend([f"修复可访问性缺口：{item}。" for item in a11y_gaps[:2]])
        if token_clues:
            derived_rules.append(f"参考 token 线索并映射到语义 token：{'；'.join(token_clues[:4])}。")
    else:
        derived_rules.extend([f"Fix layout issue from reference input: {item}." for item in layout_issues[:3]])
        derived_rules.extend([f"Fill missing component/state: {item}." for item in missing_components[:2]])
        derived_rules.extend([f"Preserve existing structural element: {item}." for item in preserve_elements[:2]])
        derived_rules.extend([f"Close interaction gap: {item}." for item in interaction_gaps[:2]])
        derived_rules.extend([f"Fix accessibility gap: {item}." for item in a11y_gaps[:2]])
        if token_clues:
            derived_rules.append(f"Map reference token clues to semantic tokens: {'; '.join(token_clues[:4])}.")

    summary_parts = []
    if layout_issues:
        summary_parts.append(f"layout:{len(layout_issues)}")
    if missing_components:
        summary_parts.append(f"components:{len(missing_components)}")
    if preserve_elements:
        summary_parts.append(f"preserve:{len(preserve_elements)}")
    if interaction_gaps:
        summary_parts.append(f"interaction:{len(interaction_gaps)}")
    if a11y_gaps:
        summary_parts.append(f"a11y:{len(a11y_gaps)}")
    if token_clues:
        summary_parts.append(f"tokens:{len(token_clues)}")
    summary = ", ".join(summary_parts)

    signals = {
        "layout_issues": layout_issues,
        "missing_components": missing_components,
        "preserve_elements": preserve_elements,
        "interaction_gaps": interaction_gaps,
        "a11y_gaps": a11y_gaps,
        "token_clues": token_clues,
        "notes": notes,
    }
    has_signals = any(bool(value) for value in signals.values())

    return {
        "has_signals": has_signals,
        "source": reference_type,
        "summary": summary,
        "signals": signals,
        "derived_rules": dedupe_ordered(derived_rules)[:8],
    }


def reference_signal_prompt_block(reference_signals: dict[str, Any], lang: str) -> str:
    if not reference_signals.get("has_signals"):
        return ""

    sig = reference_signals.get("signals", {})
    layout_issues = sig.get("layout_issues", [])
    missing_components = sig.get("missing_components", [])
    preserve_elements = sig.get("preserve_elements", [])
    interaction_gaps = sig.get("interaction_gaps", [])
    a11y_gaps = sig.get("a11y_gaps", [])
    token_clues = sig.get("token_clues", [])
    notes = sig.get("notes", [])

    if lang == "zh":
        lines = ["参考信号提取："]
        if layout_issues:
            lines.append(f"- 布局问题：{'；'.join(layout_issues[:3])}")
        if missing_components:
            lines.append(f"- 缺失组件：{'；'.join(missing_components[:3])}")
        if preserve_elements:
            lines.append(f"- 保留要素：{'；'.join(preserve_elements[:3])}")
        if interaction_gaps:
            lines.append(f"- 交互缺口：{'；'.join(interaction_gaps[:3])}")
        if a11y_gaps:
            lines.append(f"- 可访问性缺口：{'；'.join(a11y_gaps[:3])}")
        if token_clues:
            lines.append(f"- Token 线索：{'；'.join(token_clues[:4])}")
        if notes:
            lines.append(f"- 备注：{'；'.join(notes[:2])}")
        return "\n".join(lines) + "\n\n"

    lines = ["Reference signal extraction:"]
    if layout_issues:
        lines.append(f"- Layout issues: {'; '.join(layout_issues[:3])}")
    if missing_components:
        lines.append(f"- Missing components: {'; '.join(missing_components[:3])}")
    if preserve_elements:
        lines.append(f"- Preserve elements: {'; '.join(preserve_elements[:3])}")
    if interaction_gaps:
        lines.append(f"- Interaction gaps: {'; '.join(interaction_gaps[:3])}")
    if a11y_gaps:
        lines.append(f"- Accessibility gaps: {'; '.join(a11y_gaps[:3])}")
    if token_clues:
        lines.append(f"- Token clues: {'; '.join(token_clues[:4])}")
    if notes:
        lines.append(f"- Notes: {'; '.join(notes[:2])}")
    return "\n".join(lines) + "\n\n"

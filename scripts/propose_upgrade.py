#!/usr/bin/env python3
"""Generate manual-review upgrade proposal from pipeline output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import sys
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from _common import load_json, now_iso
from v2_taxonomy import build_upgrade_candidates

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
DEFAULT_OUT_DIR = SKILL_ROOT / "tmp" / "upgrade-proposals"



def candidate_slug(value: str) -> str:
    raw = "".join(ch for ch in str(value or "") if ch.isalnum() or ch in ("-", "_"))
    return raw[:40] or "candidate"


def to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Upgrade Proposal",
        f"- Status: {payload.get('status')}",
        f"- Source: {payload.get('source_file')}",
        f"- Candidate count: {len(payload.get('candidates', []))}",
        "",
    ]
    for idx, item in enumerate(payload.get("candidates", []), start=1):
        lines.extend(
            [
                f"## {idx}. {item.get('candidate_id')}",
                f"- Summary: {item.get('summary')}",
                f"- Site type: {(item.get('evidence', {}) or {}).get('site_type')}",
                f"- Selected style: {(item.get('evidence', {}) or {}).get('selected_style')}",
                f"- Violations: {', '.join((item.get('evidence', {}) or {}).get('violation_ids', [])) or '(none)'}",
                "- Proposed changes:",
            ]
        )
        for change in item.get("proposed_changes", []):
            lines.append(f"  - {change.get('action')} -> {change.get('target')}")
        lines.append("- Required gates:")
        for gate in item.get("required_gates", []):
            lines.append(f"  - {gate}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Propose v2 taxonomy upgrades from pipeline output")
    parser.add_argument("--pipeline-output", required=True, help="Path to run_pipeline output JSON")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Directory for candidate JSON output")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    args = parser.parse_args()

    source_path = Path(args.pipeline_output)
    if not source_path.exists():
        raise SystemExit(f"Pipeline output file not found: {source_path}")

    payload = load_json(source_path)
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected JSON object in {source_path}")
    query = str(payload.get("query", "")).strip()
    selected_style = str(payload.get("selected_style", "")).strip()

    site_profile = payload.get("site_profile", {}) or payload.get("result", {}).get("site_profile", {}) or {}
    tag_bundle = payload.get("tag_bundle", {}) or payload.get("result", {}).get("tag_bundle", {}) or {}
    quality_gate = payload.get("quality_gate", {}) or {}

    candidates = payload.get("upgrade_candidates")
    if not isinstance(candidates, list) or not candidates:
        candidates = build_upgrade_candidates(
            query=query,
            site_type=site_profile.get("site_type", "general"),
            selected_style=selected_style,
            tag_bundle=tag_bundle,
            quality_gate=quality_gate,
        )

    out_payload: dict[str, Any] = {
        "schemaVersion": "2.0.0",
        "generatedAt": now_iso(),
        "source_file": str(source_path),
        "status": "no-op" if not candidates else "proposed",
        "candidates": candidates,
    }

    output_path = ""
    if candidates and not args.dry_run:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        slug = candidate_slug(selected_style or site_profile.get("site_type", "general"))
        filename = f"upgrade-{now_iso().replace(':', '').replace('-', '')}-{slug}.json"
        output_file = out_dir / filename
        output_file.write_text(json.dumps(out_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        output_path = str(output_file)

    if output_path:
        out_payload["output_file"] = output_path

    if args.format == "markdown":
        print(to_markdown(out_payload))
    else:
        print(json.dumps(out_payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

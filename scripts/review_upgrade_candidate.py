#!/usr/bin/env python3
"""Validate upgrade proposal files before creating a PR."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import sys
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from _common import load_json as _load_json

ALLOWED_TARGETS = {
    "references/taxonomy/style-tag-map.v2.json",
    "references/taxonomy/site-type-routing.json",
}

REQUIRED_GATE_SNIPPETS = (
    "python3 scripts/smoke_test.py",
    "bash scripts/ci_regression_gate.sh",
)


def load_json(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise SystemExit("Candidate file must contain a JSON object")
    return payload


def extract_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("candidates"), list):
        return [item for item in payload["candidates"] if isinstance(item, dict)]
    if payload.get("candidate_id"):
        return [payload]
    return []


def validate_candidate(item: dict[str, Any]) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    warnings: list[str] = []

    candidate_id = str(item.get("candidate_id", "")).strip()
    if not candidate_id:
        issues.append("missing candidate_id")

    changes = item.get("proposed_changes", [])
    if not isinstance(changes, list) or not changes:
        issues.append("missing proposed_changes")
    else:
        for idx, change in enumerate(changes, start=1):
            if not isinstance(change, dict):
                issues.append(f"proposed_changes[{idx}] is not an object")
                continue
            target = str(change.get("target", "")).strip()
            action = str(change.get("action", "")).strip()
            if not target:
                issues.append(f"proposed_changes[{idx}] missing target")
            elif target not in ALLOWED_TARGETS:
                issues.append(f"proposed_changes[{idx}] target not allowed: {target}")
            if not action:
                issues.append(f"proposed_changes[{idx}] missing action")

    gates = item.get("required_gates", [])
    if not isinstance(gates, list) or not gates:
        issues.append("missing required_gates")
    else:
        gate_text = "\n".join(str(g) for g in gates)
        for snippet in REQUIRED_GATE_SNIPPETS:
            if snippet not in gate_text:
                issues.append(f"required_gates missing expected gate: {snippet}")

    evidence = item.get("evidence", {})
    if not isinstance(evidence, dict):
        issues.append("evidence must be an object")
    else:
        if not evidence.get("site_type"):
            warnings.append("evidence.site_type is empty")
        if not evidence.get("selected_style"):
            warnings.append("evidence.selected_style is empty")

    return issues, warnings


def to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Upgrade Candidate Review",
        f"- Status: {report.get('status')}",
        f"- Candidate count: {report.get('candidate_count')}",
        f"- Issues: {len(report.get('issues', []))}",
        f"- Warnings: {len(report.get('warnings', []))}",
        "",
    ]
    if report.get("issues"):
        lines.append("## Issues")
        for item in report["issues"]:
            lines.append(f"- {item}")
        lines.append("")
    if report.get("warnings"):
        lines.append("## Warnings")
        for item in report["warnings"]:
            lines.append(f"- {item}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Review upgrade proposal schema and gate requirements")
    parser.add_argument("--candidate", required=True, help="Path to upgrade proposal JSON")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    args = parser.parse_args()

    candidate_path = Path(args.candidate)
    if not candidate_path.exists():
        raise SystemExit(f"Candidate file not found: {candidate_path}")

    payload = load_json(candidate_path)
    candidates = extract_candidates(payload)
    if not candidates:
        raise SystemExit("No candidate entries found")

    issues: list[str] = []
    warnings: list[str] = []

    for idx, item in enumerate(candidates, start=1):
        item_issues, item_warnings = validate_candidate(item)
        issues.extend([f"candidate[{idx}]: {msg}" for msg in item_issues])
        warnings.extend([f"candidate[{idx}]: {msg}" for msg in item_warnings])

    status = "pass"
    if issues:
        status = "fail"
    elif args.strict and warnings:
        status = "fail"

    report = {
        "status": status,
        "candidate_count": len(candidates),
        "issues": issues,
        "warnings": warnings,
    }

    if args.format == "markdown":
        print(to_markdown(report))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    if status != "pass":
        raise SystemExit(2)


if __name__ == "__main__":
    main()

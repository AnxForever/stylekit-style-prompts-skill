#!/usr/bin/env python3
"""Validate output-contract markdown examples against JSON schemas.

This guard prevents drift between:
1) human-facing contract examples in references/output-contract.md
2) machine-enforced schemas under references/schemas/
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
DEFAULT_CONTRACT_FILE = SKILL_ROOT / "references" / "output-contract.md"
DEFAULT_SCHEMAS_DIR = SKILL_ROOT / "references" / "schemas"
REQUIRED_HEADINGS = (
    "1) Candidate Search Output",
    "2) Design Brief + Prompt Output",
    "3) Prompt QA Output",
    "4) One-shot Pipeline Output",
    "5) Benchmark Output",
)


def load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def extract_section_headings(markdown: str) -> list[str]:
    return [line[3:].strip() for line in markdown.splitlines() if line.startswith("## ")]


def extract_json_blocks(markdown: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    heading = ""
    in_block = False
    buf: list[str] = []
    block_start_line = 0

    for line_no, raw in enumerate(markdown.splitlines(), start=1):
        line = raw.rstrip("\n")
        if line.startswith("## "):
            heading = line[3:].strip()
            continue

        if line.strip() == "```json":
            in_block = True
            buf = []
            block_start_line = line_no
            continue

        if line.strip() == "```" and in_block:
            in_block = False
            blocks.append(
                {
                    "heading": heading,
                    "json": "\n".join(buf).strip(),
                    "line": block_start_line,
                }
            )
            buf = []
            continue

        if in_block:
            buf.append(line)

    return blocks


def group_blocks_by_heading(blocks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in blocks:
        grouped.setdefault(str(item.get("heading", "")), []).append(item)
    return grouped


def parse_json_payload(raw_json: str, *, heading: str, line: int) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON under section '{heading}' at line {line}: {exc.msg}"
    if not isinstance(payload, dict):
        return None, (
            f"JSON under section '{heading}' at line {line} must be an object; "
            f"got {type(payload).__name__}"
        )
    return payload, None


def ensure_pipeline_minimal(payload: dict[str, Any], *, workflow: str) -> dict[str, Any]:
    out = copy.deepcopy(payload)
    out["workflow"] = workflow
    out["mode"] = "brief+prompt" if workflow == "codegen" else "brief-only"
    out.setdefault("manual_assistant", {})
    quality_gate = out.get("quality_gate", {})
    if not isinstance(quality_gate, dict):
        quality_gate = {}
    quality_gate.setdefault("status", "pass")
    quality_gate.setdefault("checks", [])
    out["quality_gate"] = quality_gate
    result = out.get("result", {})
    if not isinstance(result, dict):
        result = {}
    if workflow == "codegen":
        result.setdefault("hard_prompt", "...")
        result.setdefault("soft_prompt", "...")
    out["result"] = result
    return out


def validate_against_schema(
    payload: dict[str, Any],
    schema: dict[str, Any],
) -> list[str]:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    msgs: list[str] = []
    for err in errors:
        path = ".".join(str(p) for p in err.absolute_path) or "<root>"
        msgs.append(f"[{path}] {err.message}")
    return msgs


def run(
    *,
    contract_file: str = str(DEFAULT_CONTRACT_FILE),
    schemas_dir: str = str(DEFAULT_SCHEMAS_DIR),
    fail_on_warning: bool = False,
) -> dict[str, Any]:
    contract_path = Path(contract_file)
    schema_path = Path(schemas_dir)

    if not contract_path.exists():
        raise SystemExit(f"Contract file not found: {contract_path}")
    if not schema_path.exists():
        raise SystemExit(f"Schemas dir not found: {schema_path}")

    markdown = contract_path.read_text(encoding="utf-8")
    headings = extract_section_headings(markdown)
    blocks = extract_json_blocks(markdown)
    if not blocks:
        return {
            "status": "fail",
            "checks": [],
            "errors": ["No JSON code blocks found in output contract markdown."],
        }

    missing = [heading for heading in REQUIRED_HEADINGS if heading not in headings]
    if missing:
        return {
            "status": "fail",
            "checks": [],
            "errors": [f"Missing required JSON section(s): {', '.join(missing)}"],
        }

    required_positions = [headings.index(heading) for heading in REQUIRED_HEADINGS]
    if required_positions != sorted(required_positions):
        ordered = ", ".join(REQUIRED_HEADINGS)
        return {
            "status": "fail",
            "checks": [],
            "errors": [f"Required section order changed; expected order: {ordered}"],
        }

    blocks_by_heading = group_blocks_by_heading(blocks)
    missing_json = [heading for heading in REQUIRED_HEADINGS if not blocks_by_heading.get(heading)]
    if missing_json:
        return {
            "status": "fail",
            "checks": [],
            "errors": [f"Required section has no JSON block(s): {', '.join(missing_json)}"],
        }

    schemas = {
        "search_stylekit": load_json(schema_path / "search_stylekit_output.json"),
        "generate_brief": load_json(schema_path / "generate_brief_output.json"),
        "qa_prompt": load_json(schema_path / "qa_prompt_output.json"),
        "pipeline_codegen": load_json(schema_path / "run_pipeline_codegen_output.json"),
        "pipeline_manual": load_json(schema_path / "run_pipeline_manual_output.json"),
        "benchmark_pipeline": load_json(schema_path / "benchmark_pipeline_output.json"),
    }

    checks: list[dict[str, Any]] = []
    warnings: list[str] = []

    def add_check(name: str, heading: str, payload: dict[str, Any], schema_key: str) -> None:
        errors = validate_against_schema(payload, schemas[schema_key])
        checks.append(
            {
                "name": name,
                "heading": heading,
                "schema": schema_key,
                "passed": len(errors) == 0,
                "errors": errors[:20],
            }
        )

    def get_primary_payload(heading: str) -> tuple[dict[str, Any] | None, str | None]:
        section_blocks = blocks_by_heading.get(heading, [])
        if not section_blocks:
            return None, f"Missing JSON block for required section: {heading}"
        if len(section_blocks) > 1:
            warnings.append(
                f"Section '{heading}' has {len(section_blocks)} JSON blocks; using the first one as canonical."
            )
        primary = section_blocks[0]
        return parse_json_payload(
            str(primary.get("json", "")),
            heading=heading,
            line=int(primary.get("line", 0)),
        )

    search_heading = REQUIRED_HEADINGS[0]
    brief_heading = REQUIRED_HEADINGS[1]
    qa_heading = REQUIRED_HEADINGS[2]
    pipe_heading = REQUIRED_HEADINGS[3]
    bench_heading = REQUIRED_HEADINGS[4]

    search_payload, search_error = get_primary_payload(search_heading)
    brief_payload, brief_error = get_primary_payload(brief_heading)
    qa_payload, qa_error = get_primary_payload(qa_heading)
    pipeline_payload, pipeline_error = get_primary_payload(pipe_heading)
    benchmark_payload, benchmark_error = get_primary_payload(bench_heading)

    parse_errors = [err for err in [search_error, brief_error, qa_error, pipeline_error, benchmark_error] if err]
    if parse_errors:
        return {
            "status": "fail",
            "checks": [],
            "errors": parse_errors,
            "warnings": warnings,
        }

    assert search_payload is not None
    assert brief_payload is not None
    assert qa_payload is not None
    assert pipeline_payload is not None
    assert benchmark_payload is not None

    add_check("search_contract_example", search_heading, search_payload, "search_stylekit")
    add_check("brief_contract_example", brief_heading, brief_payload, "generate_brief")
    add_check("qa_contract_example", qa_heading, qa_payload, "qa_prompt")
    add_check(
        "pipeline_contract_example_codegen",
        pipe_heading,
        ensure_pipeline_minimal(pipeline_payload, workflow="codegen"),
        "pipeline_codegen",
    )
    add_check(
        "pipeline_contract_example_manual",
        pipe_heading,
        ensure_pipeline_minimal(pipeline_payload, workflow="manual"),
        "pipeline_manual",
    )
    add_check(
        "benchmark_contract_example",
        bench_heading,
        benchmark_payload,
        "benchmark_pipeline",
    )

    failed = [item for item in checks if not item["passed"]]
    errors = [f"{item['name']}: {len(item['errors'])} error(s)" for item in failed]
    if fail_on_warning and warnings:
        errors.append(f"fail-on-warning enabled: {len(warnings)} warning(s)")
    status = "pass" if not errors else "fail"
    return {
        "status": status,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate references/output-contract.md examples against references/schemas JSON schemas",
    )
    parser.add_argument("--contract-file", default=str(DEFAULT_CONTRACT_FILE))
    parser.add_argument("--schemas-dir", default=str(DEFAULT_SCHEMAS_DIR))
    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Treat warnings as failures (non-zero exit when warnings are present).",
    )
    args = parser.parse_args()

    result = run(
        contract_file=args.contract_file,
        schemas_dir=args.schemas_dir,
        fail_on_warning=args.fail_on_warning,
    )

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Status: {result['status']}")
        for check in result.get("checks", []):
            label = "pass" if check.get("passed") else "fail"
            print(f"- {check.get('name')}: {label}")
            if not check.get("passed"):
                for item in check.get("errors", [])[:5]:
                    print(f"  * {item}")
        if result.get("warnings"):
            print("Warnings:")
            for item in result["warnings"]:
                print(f"  - {item}")
        if result.get("errors"):
            print("Errors:")
            for item in result["errors"]:
                print(f"  - {item}")

    sys.exit(0 if result.get("status") == "pass" else 1)


if __name__ == "__main__":
    main()

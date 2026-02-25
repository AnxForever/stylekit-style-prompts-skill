"""Unit tests for scripts/validate_output_contract_sync.py."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from validate_output_contract_sync import (
    DEFAULT_CONTRACT_FILE,
    DEFAULT_SCHEMAS_DIR,
    REQUIRED_HEADINGS,
    extract_json_blocks,
    group_blocks_by_heading,
    run,
)


def _load_canonical_payloads() -> dict[str, dict[str, Any]]:
    markdown = DEFAULT_CONTRACT_FILE.read_text(encoding="utf-8")
    grouped = group_blocks_by_heading(extract_json_blocks(markdown))
    payloads: dict[str, dict[str, Any]] = {}
    for heading in REQUIRED_HEADINGS:
        payloads[heading] = json.loads(grouped[heading][0]["json"])
    return payloads


def _write_contract(
    path: Path,
    payloads: dict[str, dict[str, Any]],
    *,
    heading_order: list[str] | None = None,
    extra_blocks: dict[str, list[dict[str, Any]]] | None = None,
) -> None:
    order = heading_order or list(REQUIRED_HEADINGS)
    extras = extra_blocks or {}
    parts: list[str] = ["# Temp Contract", ""]
    for heading in order:
        parts.append(f"## {heading}")
        parts.append("")
        parts.append("```json")
        parts.append(json.dumps(payloads[heading], ensure_ascii=False, indent=2))
        parts.append("```")
        parts.append("")
        for block in extras.get(heading, []):
            parts.append("```json")
            parts.append(json.dumps(block, ensure_ascii=False, indent=2))
            parts.append("```")
            parts.append("")
    path.write_text("\n".join(parts), encoding="utf-8")


class TestValidateOutputContractSync:
    """Focused tests for contract example sync guard behavior."""

    def test_uses_first_json_block_when_section_has_multiple_blocks(self, tmp_path: Path) -> None:
        payloads = _load_canonical_payloads()
        contract = tmp_path / "contract.md"
        _write_contract(
            contract,
            payloads,
            extra_blocks={
                REQUIRED_HEADINGS[0]: [
                    {
                        "query": "this is intentionally incomplete and should be ignored",
                    }
                ]
            },
        )

        result = run(contract_file=str(contract), schemas_dir=str(DEFAULT_SCHEMAS_DIR))

        assert result["status"] == "pass"
        assert result.get("warnings"), "Expected warning for duplicate JSON blocks"
        assert "using the first one as canonical" in result["warnings"][0]

    def test_fail_on_warning_turns_duplicate_blocks_into_failure(self, tmp_path: Path) -> None:
        payloads = _load_canonical_payloads()
        contract = tmp_path / "contract.md"
        _write_contract(
            contract,
            payloads,
            extra_blocks={REQUIRED_HEADINGS[2]: [payloads[REQUIRED_HEADINGS[2]]]},
        )

        result = run(
            contract_file=str(contract),
            schemas_dir=str(DEFAULT_SCHEMAS_DIR),
            fail_on_warning=True,
        )

        assert result["status"] == "fail"
        assert any("fail-on-warning enabled" in msg for msg in result.get("errors", []))
        assert result.get("warnings"), "Expected warnings to be preserved in output"

    def test_fails_when_required_heading_order_changes(self, tmp_path: Path) -> None:
        payloads = _load_canonical_payloads()
        contract = tmp_path / "contract.md"
        swapped = [
            REQUIRED_HEADINGS[1],
            REQUIRED_HEADINGS[0],
            REQUIRED_HEADINGS[2],
            REQUIRED_HEADINGS[3],
            REQUIRED_HEADINGS[4],
        ]
        _write_contract(contract, payloads, heading_order=swapped)

        result = run(contract_file=str(contract), schemas_dir=str(DEFAULT_SCHEMAS_DIR))

        assert result["status"] == "fail"
        assert any("Required section order changed" in msg for msg in result.get("errors", []))

    def test_fails_when_primary_json_block_is_invalid(self, tmp_path: Path) -> None:
        payloads = _load_canonical_payloads()
        contract = tmp_path / "contract.md"
        parts: list[str] = ["# Temp Contract", ""]
        for idx, heading in enumerate(REQUIRED_HEADINGS):
            parts.append(f"## {heading}")
            parts.append("")
            if idx == 0:
                # First block is intentionally invalid JSON.
                parts.append("```json")
                parts.append('{"query":"broken",}')
                parts.append("```")
                parts.append("")
                # Second block is valid but should be ignored because first is canonical.
                parts.append("```json")
                parts.append(json.dumps(payloads[heading], ensure_ascii=False, indent=2))
                parts.append("```")
                parts.append("")
            else:
                parts.append("```json")
                parts.append(json.dumps(payloads[heading], ensure_ascii=False, indent=2))
                parts.append("```")
                parts.append("")
        contract.write_text("\n".join(parts), encoding="utf-8")

        result = run(contract_file=str(contract), schemas_dir=str(DEFAULT_SCHEMAS_DIR))

        assert result["status"] == "fail"
        assert any("Invalid JSON under section" in msg for msg in result.get("errors", []))

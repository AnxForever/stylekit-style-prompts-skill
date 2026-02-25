"""Unit tests for scripts/validate_taxonomy.py."""

from __future__ import annotations

import json
from pathlib import Path

import validate_taxonomy as mod


def _write_registry_with_extra_unused_tag(tmp_path: Path, *, tag: str = "unit-unused-style-tag") -> Path:
    src = mod.TAX_DIR / "style-tag-registry.json"
    data = json.loads(src.read_text(encoding="utf-8"))
    tags = data.get("allowed_style_tags", [])
    if tag not in tags:
        tags.append(tag)
    data["allowed_style_tags"] = tags
    out = tmp_path / "style-tag-registry.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


class TestValidateTaxonomy:
    """Behavior tests for taxonomy validator warning/error policy."""

    def test_baseline_strict_mode_passes(self) -> None:
        result = mod.validate(max_unused_style_tags=0, fail_on_warning=True)
        assert result["status"] == "pass"
        assert result.get("warnings", []) == []
        assert result.get("errors", []) == []

    def test_warns_when_unused_style_tags_exist_without_threshold(self, tmp_path: Path) -> None:
        registry = _write_registry_with_extra_unused_tag(tmp_path)
        result = mod.validate(style_tag_registry_file=str(registry))

        assert result["status"] == "pass"
        assert result.get("warnings"), "Expected warnings when unused tags exist without threshold"
        assert "unused style tags detected" in result["warnings"][0]
        stats = result.get("style_tag_registry_stats", {}) or {}
        assert stats.get("unused_count", 0) >= 1

    def test_fail_on_warning_promotes_warning_to_failure(self, tmp_path: Path) -> None:
        registry = _write_registry_with_extra_unused_tag(tmp_path)
        result = mod.validate(style_tag_registry_file=str(registry), fail_on_warning=True)

        assert result["status"] == "fail"
        assert result.get("warnings"), "Expected warnings to be preserved in failure result"
        assert any("fail-on-warning enabled" in msg for msg in result.get("errors", []))

    def test_max_unused_style_tags_still_fails_hard(self, tmp_path: Path) -> None:
        registry = _write_registry_with_extra_unused_tag(tmp_path)
        result = mod.validate(style_tag_registry_file=str(registry), max_unused_style_tags=0)

        assert result["status"] == "fail"
        assert any("unused tag count" in msg for msg in result.get("errors", []))

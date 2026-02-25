"""Shared fixtures for stylekit-style-prompts test suite."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_ROOT / "scripts"
REF_DIR = SKILL_ROOT / "references"

# Ensure scripts/ is importable
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Real-data fixtures (loaded from reference JSON files)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def style_catalog() -> dict[str, Any]:
    path = REF_DIR / "style-prompts.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def tag_schema() -> dict[str, Any]:
    path = REF_DIR / "taxonomy" / "tag-schema.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def site_type_routing() -> dict[str, Any]:
    path = REF_DIR / "taxonomy" / "site-type-routing.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def style_tag_map() -> dict[str, Any]:
    path = REF_DIR / "taxonomy" / "style-tag-map.v2.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def animation_profiles() -> dict[str, Any]:
    path = REF_DIR / "taxonomy" / "animation-profiles.v2.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def interaction_patterns() -> dict[str, Any]:
    path = REF_DIR / "taxonomy" / "interaction-patterns.v2.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Lightweight factory fixtures (inline construction)
# ---------------------------------------------------------------------------

@pytest.fixture()
def minimal_style() -> dict[str, Any]:
    """Minimal style dict with only required fields."""
    return {
        "slug": "test-style",
        "name": "测试风格",
        "nameEn": "Test Style",
        "styleType": "visual",
        "category": "expressive",
        "tags": ["modern", "clean"],
        "keywords": ["test", "sample"],
        "colors": {
            "primary": "#3B82F6",
            "secondary": "#1E293B",
            "accent": ["#F59E0B"],
        },
        "philosophy": "A test style for unit testing purposes.",
        "aiRules": "- Use consistent spacing.\n- Maintain visual hierarchy.\n- Avoid clutter.",
        "doList": ["Keep spacing consistent", "Use semantic tokens"],
        "dontList": ["Avoid nested scroll", "Do not use absolute positioning"],
        "components": {
            "button": True,
            "card": True,
            "input": True,
            "nav": True,
            "hero": True,
            "footer": True,
        },
    }


@pytest.fixture()
def sample_tag_bundle() -> dict[str, Any]:
    """Complete 6-dimension tag bundle."""
    return {
        "site_type": "dashboard",
        "visual_style": "modern-tech",
        "layout_archetype": "kpi-console",
        "motion_profile": "subtle",
        "interaction_pattern": "data-dense-feedback",
        "modifiers": ["dense-information", "readability-first"],
    }


@pytest.fixture()
def default_route() -> dict[str, Any]:
    """Dashboard routing entry."""
    return {
        "preferred_layout_archetypes": ["kpi-console", "feature-grid"],
        "preferred_motion_profiles": ["subtle", "functional"],
        "preferred_interaction_patterns": ["data-dense-feedback"],
        "favored_style_tags": ["modern", "clean", "dashboard"],
        "penalized_style_tags": ["chaotic", "retro"],
        "default_modules": ["kpi-card", "data-table", "chart-panel"],
        "optional_modules": ["settings", "notification"],
    }

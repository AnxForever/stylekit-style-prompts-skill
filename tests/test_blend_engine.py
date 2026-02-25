"""Unit tests for blend_engine module."""

from __future__ import annotations

from typing import Any

import pytest

from blend_engine import (
    blend_directive,
    build_blend_plan,
    color_score,
    motion_score,
    pick_owner,
    spacing_score,
    typography_score,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _style(slug: str, **overrides: Any) -> dict[str, Any]:
    """Build a minimal style dict with given overrides."""
    base: dict[str, Any] = {
        "slug": slug,
        "name": "",
        "nameEn": "",
        "styleType": "visual",
        "keywords": [],
        "aiRules": "",
        "philosophy": "",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# motion_score
# ---------------------------------------------------------------------------

class TestMotionScore:
    """motion_score scores based on motion keywords in aiRules + keywords."""

    def test_style_with_motion_keywords_scores_higher(self):
        motion_style = _style("motion", aiRules="hover transition animation", keywords=["glow"])
        plain_style = _style("plain", aiRules="use clean layout", keywords=["minimal"])

        assert motion_score(motion_style) > motion_score(plain_style)

    def test_style_without_motion_keywords_scores_zero(self):
        plain = _style("plain", aiRules="keep it simple", keywords=["clean"])
        assert motion_score(plain) == 0.0

    def test_each_keyword_adds_one_point(self):
        style = _style("full", aiRules="hover active transition animation motion glow", keywords=[])
        assert motion_score(style) == 6.0

    def test_chinese_motion_keywords(self):
        style = _style("zh", aiRules="悬停 动画 发光", keywords=["动效"])
        assert motion_score(style) >= 4.0

    def test_minimal_fixture_has_low_motion(self, minimal_style: dict[str, Any]):
        score = motion_score(minimal_style)
        assert score == 0.0


# ---------------------------------------------------------------------------
# typography_score
# ---------------------------------------------------------------------------

class TestTypographyScore:
    """typography_score scores typography keywords + query token overlap."""

    def test_typography_keywords_increase_score(self):
        style = _style("typo", nameEn="Editorial Serif", keywords=["typography", "readability"])
        score = typography_score(style, [])
        assert score >= 3.0

    def test_query_token_overlap_adds_to_score(self):
        style = _style("typo", nameEn="Modern Type", keywords=["modern"])
        score_with = typography_score(style, ["modern"])
        score_without = typography_score(style, ["unrelated"])
        assert score_with > score_without

    def test_no_keywords_no_overlap_scores_zero(self):
        style = _style("blank")
        assert typography_score(style, []) == 0.0

    def test_chinese_typography_keywords(self):
        style = _style("zh", name="排版风格", keywords=["字体", "可读"])
        assert typography_score(style, []) >= 3.0

    def test_query_token_each_adds_03(self):
        style = _style("s", keywords=["alpha", "beta"])
        score = typography_score(style, ["alpha", "beta"])
        assert score == pytest.approx(0.6, abs=1e-9)


# ---------------------------------------------------------------------------
# spacing_score
# ---------------------------------------------------------------------------

class TestSpacingScore:
    """spacing_score gives bonus for layout styleType and layout keywords."""

    def test_layout_style_type_gets_bonus(self):
        layout = _style("layout", styleType="layout")
        visual = _style("visual", styleType="visual")
        assert spacing_score(layout) >= 2.0
        assert spacing_score(visual) == 0.0

    def test_layout_keywords_detected(self):
        style = _style("grid", keywords=["grid", "dashboard"])
        assert spacing_score(style) >= 1.6  # 2 keywords * 0.8

    def test_combined_type_and_keywords(self):
        style = _style("full-layout", styleType="layout", keywords=["grid", "sidebar"])
        score = spacing_score(style)
        assert score >= 3.5  # base 2 + 2 keywords * 0.8

    def test_no_layout_signals_scores_zero(self):
        style = _style("none", styleType="visual", keywords=["clean", "modern"])
        assert spacing_score(style) == 0.0

    def test_chinese_layout_keywords(self):
        style = _style("zh", keywords=["布局", "网格", "间距"])
        assert spacing_score(style) >= 2.4  # 3 * 0.8


# ---------------------------------------------------------------------------
# color_score
# ---------------------------------------------------------------------------

class TestColorScore:
    """color_score detects color keywords and query token overlap."""

    def test_color_keywords_detected(self):
        style = _style("neon", nameEn="Neon Glass", keywords=["gradient", "palette"])
        score = color_score(style, [])
        assert score >= 2.8  # 4 keywords * 0.7

    def test_query_token_overlap(self):
        style = _style("s", keywords=["neon", "dark"])
        score_with = color_score(style, ["neon"])
        score_without = color_score(style, ["unrelated"])
        assert score_with > score_without

    def test_no_color_signals_scores_zero(self):
        style = _style("blank", keywords=["clean", "modern"])
        assert color_score(style, []) == 0.0

    def test_chinese_color_keywords(self):
        style = _style("zh", keywords=["色彩", "霓虹", "渐变", "高端"])
        assert color_score(style, []) >= 2.8  # 4 * 0.7

    def test_each_query_token_adds_025(self):
        style = _style("s", keywords=["alpha", "beta"])
        score = color_score(style, ["alpha", "beta"])
        assert score == pytest.approx(0.5, abs=1e-9)


# ---------------------------------------------------------------------------
# pick_owner
# ---------------------------------------------------------------------------

class TestPickOwner:
    """pick_owner returns slug of the highest scoring style."""

    def test_returns_highest_scoring_slug(self):
        styles = [
            _style("low", aiRules="simple"),
            _style("high", aiRules="hover transition animation glow"),
        ]
        result = pick_owner(styles, motion_score)
        assert result == "high"

    def test_empty_list_returns_empty_string(self):
        assert pick_owner([], motion_score) == ""

    def test_single_style_returns_its_slug(self):
        styles = [_style("only")]
        assert pick_owner(styles, motion_score) == "only"

    def test_works_with_lambda_scorer(self):
        styles = [_style("a", keywords=["neon"]), _style("b", keywords=["clean"])]
        result = pick_owner(styles, lambda s: color_score(s, []))
        assert result == "a"


# ---------------------------------------------------------------------------
# build_blend_plan
# ---------------------------------------------------------------------------

class TestBuildBlendPlan:
    """build_blend_plan returns enabled:False for single style, full plan for multiple."""

    def test_single_style_returns_disabled_plan(self):
        primary = _style("solo", keywords=["modern"])
        plan = build_blend_plan(primary, [], "modern website", "en")

        assert plan["enabled"] is False
        assert plan["base_style"] == "solo"
        assert plan["blend_styles"] == []
        assert plan["conflict_resolution"] == {}

    def test_single_style_zh_note(self):
        primary = _style("solo")
        plan = build_blend_plan(primary, [], "现代网站", "zh")
        assert "没有可用于融合" in plan["notes"]

    def test_multiple_styles_returns_enabled_plan(self):
        primary = _style("primary", keywords=["neon", "gradient"])
        alt1 = _style("alt1", keywords=["typography", "serif"])
        alt2 = _style("alt2", keywords=["grid", "layout"], styleType="layout")

        plan = build_blend_plan(primary, [alt1, alt2], "neon typography layout", "en")

        assert plan["enabled"] is True
        assert plan["base_style"] == "primary"

    def test_conflict_resolution_keys_present(self):
        primary = _style("p", keywords=["neon"])
        alt = _style("a", keywords=["serif"])
        plan = build_blend_plan(primary, [alt], "design", "en")

        cr = plan["conflict_resolution"]
        assert "color_owner" in cr
        assert "typography_owner" in cr
        assert "spacing_owner" in cr
        assert "motion_owner" in cr

    def test_blend_styles_have_weights(self):
        primary = _style("p")
        alt = _style("a")
        plan = build_blend_plan(primary, [alt], "test", "en")

        assert len(plan["blend_styles"]) >= 1
        for entry in plan["blend_styles"]:
            assert "slug" in entry
            assert "weight" in entry

    def test_priority_order_starts_with_primary(self):
        primary = _style("main")
        alt = _style("sec")
        plan = build_blend_plan(primary, [alt], "test", "en")
        assert plan["priority_order"][0] == "main"

    def test_alternatives_with_style_key_unwrapped(self):
        primary = _style("p")
        alt_wrapped = {"style": _style("wrapped-alt", keywords=["color"])}
        plan = build_blend_plan(primary, [alt_wrapped], "test", "en")

        assert plan["enabled"] is True
        slugs = [entry["slug"] for entry in plan["blend_styles"]]
        assert "wrapped-alt" in slugs


# ---------------------------------------------------------------------------
# blend_directive
# ---------------------------------------------------------------------------

class TestBlendDirective:
    """blend_directive returns non-empty string for enabled plans, empty for disabled."""

    def test_disabled_plan_returns_empty(self):
        plan = {"enabled": False, "conflict_resolution": {}}
        assert blend_directive(plan, "en") == ""

    def test_enabled_plan_returns_nonempty_en(self):
        plan = {
            "enabled": True,
            "conflict_resolution": {
                "color_owner": "style-a",
                "typography_owner": "style-b",
                "spacing_owner": "style-a",
                "motion_owner": "style-b",
            },
        }
        result = blend_directive(plan, "en")
        assert result != ""
        assert "style-a" in result
        assert "style-b" in result
        assert "Blend rules" in result

    def test_enabled_plan_returns_nonempty_zh(self):
        plan = {
            "enabled": True,
            "conflict_resolution": {
                "color_owner": "neon",
                "typography_owner": "editorial",
                "spacing_owner": "grid-master",
                "motion_owner": "neon",
            },
        }
        result = blend_directive(plan, "zh")
        assert result != ""
        assert "neon" in result
        assert "融合规则" in result

    def test_directive_contains_all_owner_names(self):
        plan = {
            "enabled": True,
            "conflict_resolution": {
                "color_owner": "alpha",
                "typography_owner": "beta",
                "spacing_owner": "gamma",
                "motion_owner": "delta",
            },
        }
        result = blend_directive(plan, "en")
        for owner in ("alpha", "beta", "gamma", "delta"):
            assert owner in result

    def test_integration_with_build_blend_plan(self):
        primary = _style("main", keywords=["neon", "gradient"])
        alt = _style("sub", keywords=["typography", "serif"])
        plan = build_blend_plan(primary, [alt], "neon serif design", "en")
        result = blend_directive(plan, "en")

        assert result != ""
        assert "main" in result or "sub" in result

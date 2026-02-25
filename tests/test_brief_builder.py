"""Unit tests for brief_builder module."""

from __future__ import annotations

from typing import Any

import pytest

from brief_builder import (
    anti_generic_constraints,
    build_component_guidelines,
    build_interaction_rules,
    design_system_structure,
    infer_design_intent,
    localized_visual_direction,
)


# ---------------------------------------------------------------------------
# build_component_guidelines
# ---------------------------------------------------------------------------

class TestBuildComponentGuidelines:
    """Tests for build_component_guidelines."""

    def test_all_components_produce_guidelines(self, minimal_style: dict[str, Any]) -> None:
        result = build_component_guidelines(minimal_style, "en")
        assert isinstance(result, list)
        # minimal_style has 6 components, output is capped at 6
        assert len(result) == 6
        assert any("Button" in g or "button" in g.lower() for g in result)
        assert any("Card" in g or "card" in g.lower() for g in result)
        assert any("Input" in g or "input" in g.lower() for g in result)
        assert any("Nav" in g or "nav" in g.lower() for g in result)
        assert any("Hero" in g or "hero" in g.lower() for g in result)
        assert any("Footer" in g or "footer" in g.lower() for g in result)

    def test_empty_components_fallback(self) -> None:
        style: dict[str, Any] = {"slug": "empty", "components": {}}
        result = build_component_guidelines(style, "en")
        assert len(result) >= 1
        assert "aiRules" in result[0] or "doList" in result[0]

    def test_empty_components_fallback_zh(self) -> None:
        style: dict[str, Any] = {"slug": "empty", "components": {}}
        result = build_component_guidelines(style, "zh")
        assert len(result) >= 1
        assert "aiRules" in result[0] or "doList" in result[0]

    def test_interaction_pattern_adds_missing_components(self) -> None:
        style: dict[str, Any] = {
            "slug": "slim",
            "components": {"button": True, "card": True},
        }
        pattern_data: dict[str, Any] = {
            "required_components": ["Accordion", "Modal"],
        }
        result = build_component_guidelines(style, "en", interaction_pattern_data=pattern_data)
        joined = " ".join(result)
        assert "Interaction pattern requires" in joined
        assert "Accordion" in joined or "Modal" in joined

    def test_interaction_pattern_no_duplicate_for_existing(self) -> None:
        # "button" already covered by component guidelines, should not appear as missing
        style: dict[str, Any] = {
            "slug": "slim",
            "components": {"button": True},
        }
        pattern_data: dict[str, Any] = {
            "required_components": ["button"],
        }
        result = build_component_guidelines(style, "en", interaction_pattern_data=pattern_data)
        assert not any("Interaction pattern requires" in g for g in result)

    def test_zh_language_output(self, minimal_style: dict[str, Any]) -> None:
        result = build_component_guidelines(minimal_style, "zh")
        assert isinstance(result, list)
        assert len(result) >= 1
        # Chinese output should contain CJK characters
        assert any("\u4e00" <= ch <= "\u9fff" for g in result for ch in g)


# ---------------------------------------------------------------------------
# build_interaction_rules
# ---------------------------------------------------------------------------

class TestBuildInteractionRules:
    """Tests for build_interaction_rules."""

    def test_matching_keywords_selected(self) -> None:
        ai_rules = [
            "Use smooth hover transitions on all interactive elements.",
            "Keep font sizes consistent.",
            "Apply active state feedback on buttons.",
            "Use focus-visible ring for keyboard navigation.",
            "Maintain color contrast ratios.",
        ]
        result = build_interaction_rules(ai_rules, "en")
        assert any("hover" in r.lower() for r in result)
        assert any("active" in r.lower() for r in result)
        assert any("focus" in r.lower() for r in result)
        # Non-matching rules should not appear
        assert not any("font sizes" in r for r in result)

    def test_few_matching_adds_fallback(self) -> None:
        ai_rules = ["Keep spacing consistent.", "Use semantic colors."]
        result = build_interaction_rules(ai_rules, "en")
        assert len(result) >= 3
        assert any("hover" in r.lower() for r in result)
        assert any("150-300ms" in r for r in result)

    def test_few_matching_adds_fallback_zh(self) -> None:
        ai_rules = ["保持间距一致。"]
        result = build_interaction_rules(ai_rules, "zh")
        assert len(result) >= 3
        assert any("hover" in r for r in result)
        assert any("150-300ms" in r for r in result)

    def test_accessibility_constraints_from_pattern_data(self) -> None:
        ai_rules = ["Use hover effect on cards."]
        pattern_data: dict[str, Any] = {
            "accessibility_constraints": [
                "Ensure minimum touch target of 44px.",
                "Provide aria-labels on all icon buttons.",
            ],
        }
        result = build_interaction_rules(ai_rules, "en", interaction_pattern_data=pattern_data)
        assert any("44px" in r or "aria-label" in r for r in result)

    def test_deduplication(self) -> None:
        ai_rules = [
            "Use hover transitions.",
            "Use hover transitions.",
            "Apply focus ring.",
            "Apply focus ring.",
        ]
        result = build_interaction_rules(ai_rules, "en")
        lowered = [r.lower().strip() for r in result]
        assert len(lowered) == len(set(lowered))

    def test_max_six_rules(self) -> None:
        ai_rules = [
            f"Rule about hover effect variant {i}" for i in range(10)
        ]
        result = build_interaction_rules(ai_rules, "en")
        assert len(result) <= 6


# ---------------------------------------------------------------------------
# design_system_structure
# ---------------------------------------------------------------------------

class TestDesignSystemStructure:
    """Tests for design_system_structure."""

    def test_returns_required_keys_en(self) -> None:
        result = design_system_structure("React + Tailwind", "en")
        assert "token_hierarchy" in result
        assert "component_architecture" in result
        assert isinstance(result["token_hierarchy"], list)
        assert isinstance(result["component_architecture"], list)

    def test_stack_name_in_output_en(self) -> None:
        stack = "Vue + UnoCSS"
        result = design_system_structure(stack, "en")
        combined = " ".join(result["component_architecture"])
        assert stack in combined

    def test_returns_required_keys_zh(self) -> None:
        result = design_system_structure("React + Tailwind", "zh")
        assert "token_hierarchy" in result
        assert "component_architecture" in result
        assert isinstance(result["token_hierarchy"], list)
        assert isinstance(result["component_architecture"], list)

    def test_stack_name_in_output_zh(self) -> None:
        stack = "Next.js"
        result = design_system_structure(stack, "zh")
        combined = " ".join(result["component_architecture"])
        assert stack in combined

    def test_en_content_is_english(self) -> None:
        result = design_system_structure("React", "en")
        first_token = result["token_hierarchy"][0]
        assert "Brand" in first_token or "brand" in first_token.lower()

    def test_zh_content_is_chinese(self) -> None:
        result = design_system_structure("React", "zh")
        first_token = result["token_hierarchy"][0]
        assert any("\u4e00" <= ch <= "\u9fff" for ch in first_token)


# ---------------------------------------------------------------------------
# infer_design_intent
# ---------------------------------------------------------------------------

class TestInferDesignIntent:
    """Tests for infer_design_intent."""

    def test_returns_all_four_keys(self) -> None:
        result = infer_design_intent("build a portfolio site", "en")
        assert set(result.keys()) == {"purpose", "audience", "tone", "memorable_hook"}

    def test_saas_query_b_end_audience_en(self) -> None:
        result = infer_design_intent("saas dashboard for analytics", "en")
        assert "Professional" in result["audience"] or "professional" in result["audience"].lower()

    def test_saas_query_b_end_audience_zh(self) -> None:
        result = infer_design_intent("SaaS 后台管理系统", "zh")
        assert "B 端" in result["audience"]

    def test_landing_query_prospects_en(self) -> None:
        result = infer_design_intent("landing page for marketing", "en")
        assert "Prospect" in result["audience"] or "prospect" in result["audience"].lower()

    def test_landing_query_prospects_zh(self) -> None:
        result = infer_design_intent("品牌营销着陆页", "zh")
        assert "潜在客户" in result["audience"]

    def test_generic_query_general_audience_en(self) -> None:
        result = infer_design_intent("a personal blog", "en")
        assert "General" in result["audience"] or "general" in result["audience"].lower()

    def test_glass_tone_en(self) -> None:
        result = infer_design_intent("frosted glass ui", "en")
        assert "translucen" in result["tone"].lower() or "modern" in result["tone"].lower()

    def test_retro_tone_en(self) -> None:
        result = infer_design_intent("retro y2k website", "en")
        assert "nostalgic" in result["tone"].lower() or "retro" in result["tone"].lower()

    def test_minimal_tone_en(self) -> None:
        result = infer_design_intent("clean minimal portfolio", "en")
        assert "minimal" in result["tone"].lower()

    def test_en_vs_zh_different_language(self) -> None:
        en = infer_design_intent("saas dashboard", "en")
        zh = infer_design_intent("saas dashboard", "zh")
        assert en["purpose"] != zh["purpose"]


# ---------------------------------------------------------------------------
# localized_visual_direction
# ---------------------------------------------------------------------------

class TestLocalizedVisualDirection:
    """Tests for localized_visual_direction."""

    def test_has_philosophy_returns_excerpt_en(self, minimal_style: dict[str, Any]) -> None:
        # minimal_style philosophy is English text
        result = localized_visual_direction(minimal_style, "en")
        assert "test style" in result.lower()

    def test_no_philosophy_fallback_en(self) -> None:
        style: dict[str, Any] = {"slug": "neo", "name": "新风格", "nameEn": "Neo Style"}
        result = localized_visual_direction(style, "en")
        assert "Neo Style" in result
        assert "visual identity" in result.lower()

    def test_no_philosophy_fallback_zh(self) -> None:
        style: dict[str, Any] = {"slug": "neo", "name": "新风格", "nameEn": "Neo Style"}
        result = localized_visual_direction(style, "zh")
        assert "新风格" in result
        assert "风格识别度" in result

    def test_chinese_philosophy_returned_for_zh(self) -> None:
        style: dict[str, Any] = {
            "slug": "cn",
            "name": "中式",
            "philosophy": "中国传统美学，融合现代设计。\n\n更多内容。",
        }
        result = localized_visual_direction(style, "zh")
        assert "中国传统美学" in result
        # Only first paragraph
        assert "更多内容" not in result

    def test_english_philosophy_not_used_for_zh(self) -> None:
        style: dict[str, Any] = {
            "slug": "test",
            "name": "测试",
            "nameEn": "Test",
            "philosophy": "English only philosophy without CJK.",
        }
        result = localized_visual_direction(style, "zh")
        # Should fall back since philosophy has no CJK
        assert "测试" in result
        assert "风格识别度" in result

    def test_fallback_uses_slug_when_name_missing(self) -> None:
        style: dict[str, Any] = {"slug": "fallback-slug"}
        result = localized_visual_direction(style, "en")
        assert "fallback-slug" in result


# ---------------------------------------------------------------------------
# anti_generic_constraints
# ---------------------------------------------------------------------------

class TestAntiGenericConstraints:
    """Tests for anti_generic_constraints."""

    def test_en_returns_english_list(self) -> None:
        result = anti_generic_constraints("en")
        assert isinstance(result, list)
        assert len(result) >= 3
        assert all(isinstance(r, str) for r in result)
        assert any("generic" in r.lower() or "avoid" in r.lower() for r in result)

    def test_zh_returns_chinese_list(self) -> None:
        result = anti_generic_constraints("zh")
        assert isinstance(result, list)
        assert len(result) >= 3
        # Should contain CJK characters
        assert any("\u4e00" <= ch <= "\u9fff" for r in result for ch in r)

    def test_en_and_zh_different(self) -> None:
        en = anti_generic_constraints("en")
        zh = anti_generic_constraints("zh")
        assert en != zh

    def test_each_constraint_is_nonempty(self) -> None:
        for lang in ("en", "zh"):
            result = anti_generic_constraints(lang)
            assert all(len(r.strip()) > 0 for r in result)

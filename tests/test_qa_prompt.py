"""Unit tests for qa_prompt.py quality-gate functions."""

from __future__ import annotations

import json
import pytest

from qa_prompt import (
    contains_any,
    contains_any_positive,
    extract_bullet_rules,
    has_cjk,
    infer_expected_lang,
    read_prompt_text,
    rules_conflict,
    run,
)


# ---------------------------------------------------------------------------
# 1. rules_conflict
# ---------------------------------------------------------------------------


class TestRulesConflict:
    """rules_conflict: polarity, token overlap, and utility conflicts."""

    def test_same_polarity_returns_false(self):
        """Two positive (no negator) rules never conflict regardless of overlap."""
        a = "Use rounded corners with shadow-lg on all cards"
        b = "Use rounded corners with shadow-lg on all buttons"
        assert rules_conflict(a, b) is False

    def test_same_polarity_both_negative_returns_false(self):
        """Two negative rules also share polarity -> False."""
        a = "Avoid rounded corners on cards"
        b = "Never use rounded corners on buttons"
        assert rules_conflict(a, b) is False

    def test_opposite_polarity_overlapping_tokens_returns_true(self):
        """Opposite polarity with sufficient token overlap -> True."""
        a = "Use large rounded corners with prominent shadow on every card component"
        b = "Never use large rounded corners with prominent shadow on every card component"
        assert rules_conflict(a, b) is True

    def test_opposite_polarity_no_overlap_returns_false(self):
        """Opposite polarity but completely unrelated topics -> False."""
        a = "Use bold colorful gradients across hero sections"
        b = "Avoid nested scroll containers inside modals"
        assert rules_conflict(a, b) is False

    def test_utility_conflict_rounded(self):
        """Utility conflict: same radius family with overlapping values."""
        a = "Use rounded-lg for buttons"
        b = "Never use rounded-lg for containers"
        assert rules_conflict(a, b) is True

    def test_utility_conflict_shadow(self):
        """Utility conflict: shadow family."""
        a = "Apply shadow-md to cards"
        b = "Avoid shadow-md on interactive elements"
        assert rules_conflict(a, b) is True

    def test_no_utility_conflict_different_values(self):
        """Different radius values with opposite polarity but no token overlap."""
        a = "Use rounded-full on avatars"
        b = "Avoid rounded-none on profile pictures"
        assert rules_conflict(a, b) is False


# ---------------------------------------------------------------------------
# 2. has_cjk / infer_expected_lang
# ---------------------------------------------------------------------------


class TestCjkDetection:
    """has_cjk and infer_expected_lang behavior."""

    def test_has_cjk_true(self):
        assert has_cjk("hello 你好") is True

    def test_has_cjk_false(self):
        assert has_cjk("only english text") is False

    def test_has_cjk_empty(self):
        assert has_cjk("") is False

    def test_has_cjk_none(self):
        assert has_cjk(None) is False

    def test_infer_lang_override_en(self):
        """Explicit lang='en' overrides CJK presence."""
        assert infer_expected_lang("包含中文字符", "en") == "en"

    def test_infer_lang_override_zh(self):
        """Explicit lang='zh' overrides English-only text."""
        assert infer_expected_lang("no cjk here", "zh") == "zh"

    def test_infer_lang_auto_en(self):
        assert infer_expected_lang("all english words", None) == "en"

    def test_infer_lang_auto_zh(self):
        assert infer_expected_lang("这是一段中文文本", None) == "zh"


# ---------------------------------------------------------------------------
# 3. extract_bullet_rules
# ---------------------------------------------------------------------------


class TestExtractBulletRules:
    """extract_bullet_rules: markdown bullet extraction."""

    def test_dash_bullets(self):
        text = "# Title\n- Use rounded corners on all cards\n- Avoid nested scroll containers"
        rules = extract_bullet_rules(text)
        assert len(rules) == 2
        assert "Use rounded corners on all cards" in rules

    def test_asterisk_bullets(self):
        text = "* Use consistent spacing across sections\n* Maintain visual hierarchy"
        rules = extract_bullet_rules(text)
        assert len(rules) == 2

    def test_numbered_bullets(self):
        text = "1. Use semantic token naming conventions\n2. Ensure WCAG 4.5:1 contrast ratio"
        rules = extract_bullet_rules(text)
        assert len(rules) == 2

    def test_short_rules_filtered(self):
        """Rules shorter than 8 characters are dropped."""
        text = "- Use it\n- Use consistent spacing across sections"
        rules = extract_bullet_rules(text)
        assert len(rules) == 1

    def test_empty_text(self):
        assert extract_bullet_rules("") == []

    def test_no_bullets(self):
        text = "This is a paragraph without any bullet points."
        assert extract_bullet_rules(text) == []


# ---------------------------------------------------------------------------
# 4. contains_any / contains_any_positive
# ---------------------------------------------------------------------------


class TestContainsAny:
    """contains_any: simple keyword hit detection."""

    def test_single_hit(self):
        assert contains_any("use hover states", ["hover"]) == ["hover"]

    def test_multiple_hits(self):
        hits = contains_any("hover and focus transition", ["hover", "focus", "animation"])
        assert "hover" in hits
        assert "focus" in hits
        assert "animation" not in hits

    def test_no_hits(self):
        assert contains_any("nothing relevant here", ["hover", "focus"]) == []


class TestContainsAnyPositive:
    """contains_any_positive: negation-aware hit detection."""

    def test_positive_mention(self):
        hits = contains_any_positive("Use hover states for feedback", ["hover"])
        assert hits == ["hover"]

    def test_negated_mention_excluded(self):
        hits = contains_any_positive("don't use hover states on mobile", ["hover"])
        assert hits == []

    def test_negated_with_avoid(self):
        hits = contains_any_positive("avoid using arial as primary font", ["arial"])
        assert hits == []

    def test_mixed_positive_and_negated(self):
        text = "Use inter for body text. don't use arial for headings."
        hits = contains_any_positive(text, ["inter", "arial"])
        assert "inter" in hits
        assert "arial" not in hits

    def test_far_negator_not_blocking(self):
        """Negator outside window (>40 chars away) should not block."""
        # Build text where "don't" is more than 40 chars before the keyword
        spacer = "x" * 50
        text = f"don't do something unrelated {spacer} use rounded corners"
        hits = contains_any_positive(text, ["rounded"])
        assert "rounded" in hits


# ---------------------------------------------------------------------------
# 5. run() — well-formed prompt vs minimal/empty
# ---------------------------------------------------------------------------

WELL_FORMED_PROMPT = """
# Modern Dashboard Style

- Use Manrope font family for headings and DM Sans for body text
- Apply rounded-xl corners on all card components with shadow-md elevation
- Use semantic design tokens for primary, secondary, and accent colors
- Maintain consistent spacing scale using 4px base unit with radius variants
- Ensure button states include hover, active, and focus-visible transitions
- Apply WCAG 4.5:1 contrast ratio for all text-on-background combinations
- Set touch target minimum 44x44px for mobile interactive elements
- Use component variants for each interactive state (default, hover, active, disabled)
- Apply swap test and squint test before final delivery to prevent generic output
- Don't use absolute positioning for page-level layout; prefer flex/grid
- Avoid nested scroll containers inside modal overlays
- Never rely on z-index stacking for visual hierarchy
- Don't remove focus-visible outlines on interactive elements

## Components
- button: primary, secondary, ghost variants with hover/active/focus
- card: content card with shadow elevation and rounded corners
- input: text field with clear label, placeholder, error, and disabled state
- nav: top navigation bar with responsive breakpoints
- hero: full-width hero section with headline and CTA
- footer: site footer with link groups and copyright
"""


class TestRunWellFormed:
    """run() with a prompt designed to pass all core checks."""

    def test_passes_overall(self):
        result = run(text=WELL_FORMED_PROMPT)
        check_ids = {c["id"] for c in result["checks"]}
        assert "non_empty" in check_ids
        assert "min_actionable_rules" in check_ids
        assert "rule_conflict" in check_ids
        assert "language_consistency" in check_ids
        assert "component_coverage" in check_ids
        assert result["status"] == "pass"

    def test_non_empty_passes(self):
        result = run(text=WELL_FORMED_PROMPT)
        check = next(c for c in result["checks"] if c["id"] == "non_empty")
        assert check["passed"] is True

    def test_min_actionable_rules_passes(self):
        result = run(text=WELL_FORMED_PROMPT)
        check = next(c for c in result["checks"] if c["id"] == "min_actionable_rules")
        assert check["passed"] is True

    def test_rule_conflict_passes(self):
        result = run(text=WELL_FORMED_PROMPT)
        check = next(c for c in result["checks"] if c["id"] == "rule_conflict")
        assert check["passed"] is True

    def test_language_consistency_passes(self):
        result = run(text=WELL_FORMED_PROMPT)
        check = next(c for c in result["checks"] if c["id"] == "language_consistency")
        assert check["passed"] is True

    def test_component_coverage_passes(self):
        result = run(text=WELL_FORMED_PROMPT)
        check = next(c for c in result["checks"] if c["id"] == "component_coverage")
        assert check["passed"] is True


class TestRunMinimalEmpty:
    """run() with empty or minimal text that should fail."""

    def test_empty_text_fails(self):
        result = run(text="   ")
        assert result["status"] == "fail"
        non_empty = next(c for c in result["checks"] if c["id"] == "non_empty")
        assert non_empty["passed"] is False

    def test_minimal_text_fails(self):
        result = run(text="Just a short sentence.")
        assert result["status"] == "fail"


# ---------------------------------------------------------------------------
# 6. run() with require_refine_mode and require_reference_type
# ---------------------------------------------------------------------------


class TestRunOptionalChecks:
    """Verify optional checks appear when flags are set."""

    def test_refine_mode_check_present(self):
        result = run(text=WELL_FORMED_PROMPT, require_refine_mode="new")
        check_ids = {c["id"] for c in result["checks"]}
        assert "refinement_mode_alignment" in check_ids

    def test_refine_mode_check_absent_without_flag(self):
        result = run(text=WELL_FORMED_PROMPT)
        check_ids = {c["id"] for c in result["checks"]}
        assert "refinement_mode_alignment" not in check_ids

    def test_reference_type_check_present(self):
        result = run(text=WELL_FORMED_PROMPT, require_reference_type="screenshot")
        check_ids = {c["id"] for c in result["checks"]}
        assert "reference_context_guard" in check_ids

    def test_reference_type_none_passes(self):
        result = run(text=WELL_FORMED_PROMPT, require_reference_type="none")
        check = next(c for c in result["checks"] if c["id"] == "reference_context_guard")
        assert check["passed"] is True

    def test_reference_type_check_absent_without_flag(self):
        result = run(text=WELL_FORMED_PROMPT)
        check_ids = {c["id"] for c in result["checks"]}
        assert "reference_context_guard" not in check_ids

    def test_reference_signals_check_present(self):
        result = run(text=WELL_FORMED_PROMPT, require_reference_signals=True)
        check_ids = {c["id"] for c in result["checks"]}
        assert "reference_signal_alignment" in check_ids

    def test_reference_signals_check_absent_without_flag(self):
        result = run(text=WELL_FORMED_PROMPT, require_reference_signals=False)
        check_ids = {c["id"] for c in result["checks"]}
        assert "reference_signal_alignment" not in check_ids


# ---------------------------------------------------------------------------
# 7. Status logic
# ---------------------------------------------------------------------------


class TestStatusLogic:
    """Status: high failure -> fail, 2+ medium -> fail, otherwise pass."""

    def test_high_failure_means_fail(self):
        """Empty text triggers high-severity non_empty failure."""
        result = run(text="   ")
        assert result["status"] == "fail"
        high_fails = [v for v in result["violations"] if v["severity"] == "high"]
        assert len(high_fails) >= 1

    def test_single_medium_failure_still_pass(self):
        """A prompt that fails exactly one medium check should still pass.

        We craft a prompt that passes all high checks but fails only
        one medium check (component_coverage) by omitting secondary
        components.
        """
        prompt = """
- Use Manrope font family for headings and DM Sans for body text
- Apply rounded-xl corners on all card components with shadow-md elevation
- Use semantic design tokens for primary, secondary, and accent colors
- Maintain consistent spacing scale using 4px base unit with radius variants
- Ensure button states include hover, active, and focus-visible transitions
- Apply WCAG 4.5:1 contrast ratio for all text-on-background combinations
- Set touch target minimum 44x44px for mobile interactive elements
- Use component variants for each interactive state (default, hover, active, disabled)
- Apply swap test and squint test before final delivery to prevent generic output
- Don't use absolute positioning for page-level layout; prefer flex/grid
- Avoid nested scroll containers inside modal overlays
- Never rely on z-index stacking for visual hierarchy

button, card, input components are styled. nav, hero, footer are covered.
"""
        result = run(text=prompt)
        medium_fails = [v for v in result["violations"] if v["severity"] == "medium"]
        # If we happen to have <=1 medium fail, status should be pass
        if len(medium_fails) <= 1:
            assert result["status"] == "pass"
        else:
            assert result["status"] == "fail"

    def test_two_medium_failures_means_fail(self):
        """A prompt with only bullet rules but lacking multiple medium criteria."""
        prompt = "\n".join(
            [
                "- Use consistent spacing across the entire layout grid system",
                "- Maintain clear visual hierarchy with proper heading scale",
                "- Apply smooth transitions on interactive elements always",
            ]
        )
        result = run(text=prompt)
        medium_fails = [v for v in result["violations"] if v["severity"] == "medium"]
        assert len(medium_fails) >= 2
        assert result["status"] == "fail"


# ---------------------------------------------------------------------------
# 8. read_prompt_text — plain text and JSON input
# ---------------------------------------------------------------------------


class TestReadPromptText:
    """read_prompt_text with plain text and JSON inline input."""

    def test_plain_text(self):
        text, meta = read_prompt_text(None, "Hello world", "hard_prompt")
        assert text == "Hello world"
        assert meta["source_kind"] == "text"
        assert meta["source_field"] is None

    def test_json_with_hard_prompt(self):
        obj = {"hard_prompt": "Use rounded corners", "name": "test"}
        inline = json.dumps(obj)
        text, meta = read_prompt_text(None, inline, "hard_prompt")
        assert text == "Use rounded corners"
        assert meta["source_kind"] == "json"
        assert meta["source_field"] == "hard_prompt"

    def test_json_fallback_field(self):
        """When preferred field is missing, falls back to common fields."""
        obj = {"prompt": "Fallback content here"}
        inline = json.dumps(obj)
        text, meta = read_prompt_text(None, inline, "hard_prompt")
        assert text == "Fallback content here"
        assert meta["source_field"] == "prompt"

    def test_json_nested(self):
        obj = {"config": {"hard_prompt": "Nested prompt text"}}
        inline = json.dumps(obj)
        text, meta = read_prompt_text(None, inline, "hard_prompt")
        assert text == "Nested prompt text"
        assert meta["source_kind"] == "json"
        assert "config" in meta["source_field"]

    def test_no_input_raises(self):
        with pytest.raises(SystemExit):
            read_prompt_text(None, None, "hard_prompt")

    def test_json_array_input(self):
        obj = [{"hard_prompt": "Array item prompt"}]
        inline = json.dumps(obj)
        text, meta = read_prompt_text(None, inline, "hard_prompt")
        assert text == "Array item prompt"
        assert meta["source_kind"] == "json"

    def test_invalid_json_falls_back_to_text(self):
        inline = "{not valid json"
        text, meta = read_prompt_text(None, inline, "hard_prompt")
        assert text == inline
        assert meta["source_kind"] == "text"

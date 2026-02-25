"""Unit tests for v2_taxonomy module."""

from __future__ import annotations

from typing import Any

import pytest

import v2_taxonomy as mod


# ---------------------------------------------------------------------------
# 1. resolve_site_type
# ---------------------------------------------------------------------------

class TestResolveSiteType:
    """Tests for resolve_site_type()."""

    def _aliases_payload(self) -> dict[str, Any]:
        return {"site_type_aliases": dict(mod.DEFAULT_SITE_ALIASES)}

    def test_explicit_site_type_returned_directly(self):
        result = mod.resolve_site_type("anything", "dashboard", self._aliases_payload())
        assert result["site_type"] == "dashboard"
        assert result["source"] == "explicit"
        assert result["confidence"] == 1.0

    def test_explicit_invalid_falls_to_general(self):
        result = mod.resolve_site_type("anything", "nonexistent-type", self._aliases_payload())
        assert result["site_type"] == "general"
        assert result["source"] == "explicit"

    def test_explicit_auto_triggers_alias_matching(self):
        result = mod.resolve_site_type("blog article", "auto", self._aliases_payload())
        assert result["source"] != "explicit"

    @pytest.mark.parametrize(
        "query, expected_type",
        [
            ("build a blog article page", "blog"),
            ("enterprise saas workspace", "saas"),
            ("admin dashboard panel", "dashboard"),
            ("documentation guide manual", "docs"),
            ("ecommerce store checkout", "ecommerce"),
            ("landing marketing homepage", "landing-page"),
            ("portfolio case study showreel", "portfolio"),
            ("website app page", "general"),
        ],
    )
    def test_alias_match_all_8_types(self, query: str, expected_type: str):
        result = mod.resolve_site_type(query, "", self._aliases_payload())
        assert result["site_type"] == expected_type
        assert result["source"] == "alias-match"
        assert result["confidence"] > 0

    def test_no_match_defaults_to_general(self):
        result = mod.resolve_site_type("xyzzy foobar", "", self._aliases_payload())
        assert result["site_type"] == "general"
        assert result["source"] == "heuristic-default"
        assert result["confidence"] == 0.35
        assert result["matched_signals"] == []


# ---------------------------------------------------------------------------
# 2. infer_visual_style
# ---------------------------------------------------------------------------

class TestInferVisualStyle:
    """Tests for infer_visual_style()."""

    def test_explicit_mapping_wins(self, minimal_style):
        mapping = {"visual_style": "editorial"}
        assert mod.infer_visual_style(minimal_style, mapping) == "editorial"

    @pytest.mark.parametrize(
        "keyword, expected",
        [
            ("minimal", "minimal"),
            ("editorial", "editorial"),
            ("retro", "retro"),
            ("cyberpunk", "expressive"),
            ("glass", "modern-tech"),
            ("dashboard", "corporate"),
            ("playful", "playful"),
        ],
    )
    def test_keyword_detection(self, keyword: str, expected: str):
        style = {"slug": keyword, "name": "", "nameEn": "", "category": "", "keywords": [], "tags": []}
        assert mod.infer_visual_style(style, {}) == expected

    def test_layout_style_type_returns_balanced(self):
        style = {"slug": "unknown-xyz", "name": "", "nameEn": "", "category": "", "keywords": [], "tags": [], "styleType": "layout"}
        assert mod.infer_visual_style(style, {}) == "balanced"

    def test_default_returns_modern_tech(self):
        style = {"slug": "unknown-xyz", "name": "", "nameEn": "", "category": "", "keywords": [], "tags": []}
        assert mod.infer_visual_style(style, {}) == "modern-tech"


# ---------------------------------------------------------------------------
# 3. infer_layout_archetype
# ---------------------------------------------------------------------------

class TestInferLayoutArchetype:
    """Tests for infer_layout_archetype()."""

    def test_mapping_hints_take_priority(self, minimal_style, default_route):
        mapping = {"layout_archetype_hints": ["custom-layout"]}
        assert mod.infer_layout_archetype(minimal_style, mapping, default_route, "general", "") == "custom-layout"

    @pytest.mark.parametrize(
        "site_type, expected",
        [
            ("dashboard", "kpi-console"),
            ("docs", "doc-sidebar"),
            ("blog", "article-first"),
            ("portfolio", "showcase-masonry"),
            ("ecommerce", "catalog-conversion"),
            ("landing-page", "split-hero"),
        ],
    )
    def test_site_type_specific(self, minimal_style, default_route, site_type: str, expected: str):
        assert mod.infer_layout_archetype(minimal_style, {}, default_route, site_type, "") == expected

    def test_query_keyword_sidebar(self, minimal_style, default_route):
        result = mod.infer_layout_archetype(minimal_style, {}, default_route, "general", "page with sidebar")
        assert result == "doc-sidebar"

    def test_query_keyword_table(self, minimal_style, default_route):
        result = mod.infer_layout_archetype(minimal_style, {}, default_route, "general", "data table view")
        assert result == "kpi-console"

    def test_route_fallback(self, minimal_style):
        route = {"preferred_layout_archetypes": ["feature-grid"]}
        result = mod.infer_layout_archetype(minimal_style, {}, route, "general", "generic query")
        assert result == "feature-grid"

    def test_ultimate_default(self, minimal_style):
        result = mod.infer_layout_archetype(minimal_style, {}, {}, "general", "generic query")
        assert result == "balanced-sections"


# ---------------------------------------------------------------------------
# 4. infer_motion_profile
# ---------------------------------------------------------------------------

class TestInferMotionProfile:
    """Tests for infer_motion_profile()."""

    def test_mapping_hints(self, minimal_style, default_route):
        mapping = {"motion_profile_hints": ["energetic"]}
        assert mod.infer_motion_profile(minimal_style, mapping, default_route, "") == "energetic"

    @pytest.mark.parametrize(
        "keyword, expected",
        [
            ("minimal readable", "minimal"),
            ("smooth glass", "smooth"),
            ("dramatic bold neon", "energetic"),
            ("playful bouncy fun", "playful"),
            ("ambient atmospheric", "ambient"),
            ("loading skeleton", "functional"),
        ],
    )
    def test_keyword_detection(self, default_route, keyword: str, expected: str):
        style = {"slug": "", "nameEn": "", "tags": [], "keywords": [], "aiRules": ""}
        assert mod.infer_motion_profile(style, {}, default_route, keyword) == expected

    def test_route_fallback(self):
        style = {"slug": "", "nameEn": "", "tags": [], "keywords": [], "aiRules": ""}
        route = {"preferred_motion_profiles": ["functional"]}
        assert mod.infer_motion_profile(style, {}, route, "unknown query xyz") == "functional"

    def test_default_subtle(self):
        style = {"slug": "", "nameEn": "", "tags": [], "keywords": [], "aiRules": ""}
        assert mod.infer_motion_profile(style, {}, {}, "unknown query xyz") == "subtle"


# ---------------------------------------------------------------------------
# 5. infer_interaction_pattern
# ---------------------------------------------------------------------------

class TestInferInteractionPattern:
    """Tests for infer_interaction_pattern()."""

    def test_mapping_hints(self, minimal_style, default_route):
        mapping = {"interaction_pattern_hints": ["form-wizard"]}
        assert mod.infer_interaction_pattern(minimal_style, mapping, default_route, "general", "") == "form-wizard"

    @pytest.mark.parametrize(
        "keyword, expected",
        [
            ("wizard multi-step form", "form-wizard"),
            ("search filter facet", "search-explore"),
            ("notification toast alert", "notification-center"),
        ],
    )
    def test_query_keywords(self, minimal_style, default_route, keyword: str, expected: str):
        assert mod.infer_interaction_pattern(minimal_style, {}, default_route, "general", keyword) == expected

    @pytest.mark.parametrize(
        "site_type, expected",
        [
            ("dashboard", "data-dense-feedback"),
            ("docs", "docs-navigation"),
            ("landing-page", "conversion-focused"),
            ("ecommerce", "conversion-focused"),
            ("portfolio", "showcase-narrative"),
        ],
    )
    def test_site_type_fallback(self, minimal_style, default_route, site_type: str, expected: str):
        assert mod.infer_interaction_pattern(minimal_style, {}, default_route, site_type, "generic") == expected

    def test_route_fallback(self, minimal_style):
        route = {"preferred_interaction_patterns": ["content-reading"]}
        assert mod.infer_interaction_pattern(minimal_style, {}, route, "general", "generic xyz") == "content-reading"

    def test_default_assistant_guided(self, minimal_style):
        assert mod.infer_interaction_pattern(minimal_style, {}, {}, "general", "generic xyz") == "assistant-guided"


# ---------------------------------------------------------------------------
# 6. infer_modifiers
# ---------------------------------------------------------------------------

class TestInferModifiers:
    """Tests for infer_modifiers()."""

    def test_mapped_modifiers_included(self, minimal_style):
        mapping = {"modifiers": ["custom-mod"]}
        result = mod.infer_modifiers(minimal_style, mapping, "general", "")
        assert "custom-mod" in result

    def test_keyword_readability(self):
        style = {"category": "", "tags": ["readability"], "keywords": []}
        result = mod.infer_modifiers(style, {}, "general", "")
        assert "readability-first" in result

    def test_keyword_conversion(self):
        style = {"category": "", "tags": [], "keywords": []}
        result = mod.infer_modifiers(style, {}, "general", "conversion cta checkout")
        assert "conversion-first" in result

    def test_keyword_high_contrast(self):
        style = {"category": "", "tags": ["neo-brutalist"], "keywords": []}
        result = mod.infer_modifiers(style, {}, "general", "")
        assert "high-contrast" in result

    @pytest.mark.parametrize(
        "site_type, expected_mod",
        [
            ("dashboard", "dense-information"),
            ("docs", "dense-information"),
            ("landing-page", "hero-driven"),
            ("portfolio", "hero-driven"),
        ],
    )
    def test_site_type_additions(self, site_type: str, expected_mod: str):
        style = {"category": "", "tags": [], "keywords": []}
        result = mod.infer_modifiers(style, {}, site_type, "")
        assert expected_mod in result

    def test_dedup_and_cap_at_3(self):
        style = {"category": "readability", "tags": ["readability", "conversion", "neo-brutalist", "high-contrast"], "keywords": ["cta"]}
        mapping = {"modifiers": ["readability-first"]}
        result = mod.infer_modifiers(style, mapping, "dashboard", "conversion cta")
        assert len(result) <= 3
        assert len(result) == len(set(result))


# ---------------------------------------------------------------------------
# 7. build_tag_bundle
# ---------------------------------------------------------------------------

class TestBuildTagBundle:
    """Tests for build_tag_bundle()."""

    def test_all_six_dimensions_present(self, minimal_style, default_route, style_tag_map):
        bundle = mod.build_tag_bundle(
            style=minimal_style,
            site_type="dashboard",
            query="admin dashboard",
            route=default_route,
            style_map_payload=style_tag_map,
        )
        expected_keys = {"site_type", "visual_style", "layout_archetype", "motion_profile", "interaction_pattern", "modifiers"}
        assert expected_keys == set(bundle.keys())

    def test_site_type_propagated(self, minimal_style, default_route):
        bundle = mod.build_tag_bundle(
            style=minimal_style,
            site_type="blog",
            query="article page",
            route=default_route,
            style_map_payload={"style_mappings": {}},
        )
        assert bundle["site_type"] == "blog"

    def test_modifiers_is_list(self, minimal_style, default_route):
        bundle = mod.build_tag_bundle(
            style=minimal_style,
            site_type="general",
            query="some query",
            route=default_route,
            style_map_payload={"style_mappings": {}},
        )
        assert isinstance(bundle["modifiers"], list)


# ---------------------------------------------------------------------------
# 8. routing_adjustment_for_style
# ---------------------------------------------------------------------------

class TestRoutingAdjustmentForStyle:
    """Tests for routing_adjustment_for_style()."""

    def test_returns_tuple(self, minimal_style, default_route):
        result = mod.routing_adjustment_for_style(
            style=minimal_style,
            site_type="dashboard",
            route=default_route,
            style_map_payload={"style_mappings": {}},
            query="dashboard admin",
        )
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], float)
        assert isinstance(result[1], dict)

    def test_favored_hits_boost(self, default_route):
        style = {"slug": "s", "styleType": "visual", "category": "modern", "tags": ["modern", "clean"], "keywords": []}
        adj, info = mod.routing_adjustment_for_style(
            style=style,
            site_type="general",
            route=default_route,
            style_map_payload={"style_mappings": {}},
            query="",
        )
        assert adj > 0
        assert len(info["favored_hits"]) > 0

    def test_penalized_hits_reduce(self, default_route):
        style = {"slug": "s", "styleType": "visual", "category": "chaotic", "tags": ["chaotic"], "keywords": []}
        adj, info = mod.routing_adjustment_for_style(
            style=style,
            site_type="general",
            route=default_route,
            style_map_payload={"style_mappings": {}},
            query="",
        )
        assert adj < 0
        assert len(info["penalized_hits"]) > 0

    def test_info_contains_site_type(self, minimal_style, default_route):
        _, info = mod.routing_adjustment_for_style(
            style=minimal_style,
            site_type="saas",
            route=default_route,
            style_map_payload={"style_mappings": {}},
            query="",
        )
        assert info["site_type"] == "saas"


# ---------------------------------------------------------------------------
# 9. resolve_animation_profile
# ---------------------------------------------------------------------------

class TestResolveAnimationProfile:
    """Tests for resolve_animation_profile()."""

    def test_none_when_no_profiles_payload(self, sample_tag_bundle, default_route):
        assert mod.resolve_animation_profile(sample_tag_bundle, default_route, None) is None

    def test_none_when_empty_profiles(self, sample_tag_bundle, default_route):
        assert mod.resolve_animation_profile(sample_tag_bundle, default_route, {"profiles": {}}) is None

    def test_recommended_with_matching_motion(self, sample_tag_bundle, default_route):
        profiles_payload = {
            "profiles": {
                "prof-a": {"motion_profile": "subtle", "intent": "calm"},
                "prof-b": {"motion_profile": "energetic", "intent": "bold"},
            }
        }
        route = {**default_route, "recommended_animation_profiles": ["prof-a"]}
        result = mod.resolve_animation_profile(sample_tag_bundle, route, profiles_payload)
        assert result is not None
        assert result["intent"] == "calm"

    def test_recommended_fallback_no_motion_match(self):
        bundle = {"motion_profile": "nonexistent"}
        profiles_payload = {
            "profiles": {
                "prof-a": {"motion_profile": "subtle", "intent": "calm"},
            }
        }
        route = {"recommended_animation_profiles": ["prof-a"]}
        result = mod.resolve_animation_profile(bundle, route, profiles_payload)
        assert result is not None
        assert result["intent"] == "calm"

    def test_fallback_by_motion_profile(self, sample_tag_bundle):
        profiles_payload = {
            "profiles": {
                "prof-x": {"motion_profile": "subtle", "intent": "understated"},
            }
        }
        route = {}  # no recommended
        result = mod.resolve_animation_profile(sample_tag_bundle, route, profiles_payload)
        assert result is not None
        assert result["intent"] == "understated"

    def test_real_data(self, sample_tag_bundle, default_route, animation_profiles):
        """Smoke test with real animation-profiles.v2.json data."""
        result = mod.resolve_animation_profile(sample_tag_bundle, default_route, animation_profiles)
        # May or may not find a match -- just verify no crash and correct type
        assert result is None or isinstance(result, dict)


# ---------------------------------------------------------------------------
# 10. resolve_interaction_pattern_data
# ---------------------------------------------------------------------------

class TestResolveInteractionPatternData:
    """Tests for resolve_interaction_pattern_data()."""

    def test_none_when_no_payload(self, sample_tag_bundle):
        assert mod.resolve_interaction_pattern_data(sample_tag_bundle, None) is None

    def test_none_when_empty_patterns(self, sample_tag_bundle):
        assert mod.resolve_interaction_pattern_data(sample_tag_bundle, {"patterns": {}}) is None

    def test_key_lookup_success(self, sample_tag_bundle):
        payload = {
            "patterns": {
                "data-dense-feedback": {"primary_goal": "density"},
            }
        }
        result = mod.resolve_interaction_pattern_data(sample_tag_bundle, payload)
        assert result is not None
        assert result["primary_goal"] == "density"

    def test_key_lookup_miss(self):
        bundle = {"interaction_pattern": "nonexistent-pattern"}
        payload = {"patterns": {"other": {"primary_goal": "x"}}}
        assert mod.resolve_interaction_pattern_data(bundle, payload) is None

    def test_real_data(self, sample_tag_bundle, interaction_patterns):
        """Smoke test with real interaction-patterns.v2.json data."""
        result = mod.resolve_interaction_pattern_data(sample_tag_bundle, interaction_patterns)
        assert result is None or isinstance(result, dict)


# ---------------------------------------------------------------------------
# 11. build_ai_interaction_script
# ---------------------------------------------------------------------------

class TestBuildAiInteractionScript:
    """Tests for build_ai_interaction_script()."""

    def test_without_resolved_data_en(self, sample_tag_bundle):
        lines = mod.build_ai_interaction_script(sample_tag_bundle, "en")
        assert isinstance(lines, list)
        assert len(lines) == 6
        assert any("Motion objective" in ln for ln in lines)

    def test_without_resolved_data_zh(self, sample_tag_bundle):
        lines = mod.build_ai_interaction_script(sample_tag_bundle, "zh")
        assert isinstance(lines, list)
        assert len(lines) == 6
        assert any("动效目标" in ln for ln in lines)

    def test_with_anim_profile_en(self, sample_tag_bundle):
        anim = {
            "duration_range_ms": [100, 250],
            "easing": "ease-out",
            "intent": "guide the eye",
            "reduced_motion_fallback": "instant-state-swap",
            "anti_patterns": ["excessive bounce"],
        }
        lines = mod.build_ai_interaction_script(sample_tag_bundle, "en", resolved_anim_profile=anim)
        assert any("Motion intent" in ln for ln in lines)
        assert any("Timing" in ln for ln in lines)
        assert any("anti-patterns" in ln for ln in lines)

    def test_with_interaction_pattern_en(self, sample_tag_bundle):
        ipt = {
            "primary_goal": "density",
            "state_coverage_requirements": {"button": ["default", "hover"]},
            "accessibility_constraints": ["focus ring required"],
            "anti_patterns": ["invisible focus"],
        }
        lines = mod.build_ai_interaction_script(sample_tag_bundle, "en", resolved_interaction_pattern=ipt)
        assert any("Interaction goal" in ln for ln in lines)
        assert any("State coverage" in ln for ln in lines)

    def test_with_both_resolved_zh(self, sample_tag_bundle):
        anim = {
            "duration_range_ms": [100, 250],
            "easing": "ease-out",
            "intent": "guide",
            "reduced_motion_fallback": "instant-state-swap",
            "anti_patterns": [],
        }
        ipt = {
            "primary_goal": "density",
            "state_coverage_requirements": {},
            "accessibility_constraints": [],
            "anti_patterns": [],
        }
        lines = mod.build_ai_interaction_script(sample_tag_bundle, "zh", resolved_anim_profile=anim, resolved_interaction_pattern=ipt)
        assert any("动效意图" in ln for ln in lines)
        assert any("交互目标" in ln for ln in lines)
        assert any("布局协同" in ln for ln in lines)

    def test_max_10_lines(self, sample_tag_bundle):
        anim = {
            "duration_range_ms": [100, 250],
            "easing": "ease-out",
            "intent": "guide",
            "reduced_motion_fallback": "swap",
            "anti_patterns": ["a", "b", "c"],
        }
        ipt = {
            "primary_goal": "density",
            "state_coverage_requirements": {"a": ["s1"], "b": ["s2"], "c": ["s3"]},
            "accessibility_constraints": ["c1", "c2", "c3"],
            "anti_patterns": ["x", "y"],
        }
        lines = mod.build_ai_interaction_script(sample_tag_bundle, "en", resolved_anim_profile=anim, resolved_interaction_pattern=ipt)
        assert len(lines) <= 10


# ---------------------------------------------------------------------------
# 12. build_composition_plan
# ---------------------------------------------------------------------------

class TestBuildCompositionPlan:
    """Tests for build_composition_plan()."""

    def _make_plan(
        self,
        sample_tag_bundle: dict[str, Any],
        default_route: dict[str, Any],
        lang: str = "en",
        recommendation_mode: str = "hybrid",
        animation_profiles: dict[str, Any] | None = None,
        interaction_patterns: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        primary = {"slug": "test-style"}
        alternatives = [{"slug": "alt-1"}, {"slug": "alt-2"}]
        blend_plan = {"conflict_resolution": {"color_owner": "test-style"}}
        return mod.build_composition_plan(
            site_type="dashboard",
            route=default_route,
            tag_bundle=sample_tag_bundle,
            primary_style=primary,
            alternatives=alternatives,
            blend_plan=blend_plan,
            recommendation_mode=recommendation_mode,
            lang=lang,
            animation_profiles=animation_profiles,
            interaction_patterns=interaction_patterns,
        )

    def test_required_keys(self, sample_tag_bundle, default_route):
        plan = self._make_plan(sample_tag_bundle, default_route)
        required = {
            "site_type",
            "recommendation_mode",
            "style_recommendation",
            "layout_recommendation",
            "motion_recommendation",
            "interaction_recommendation",
            "owner_matrix",
            "ai_interaction_script",
            "checks",
            "rationale",
        }
        assert required.issubset(set(plan.keys()))

    def test_site_type_propagated(self, sample_tag_bundle, default_route):
        plan = self._make_plan(sample_tag_bundle, default_route)
        assert plan["site_type"] == "dashboard"

    def test_owner_matrix_has_fields(self, sample_tag_bundle, default_route):
        plan = self._make_plan(sample_tag_bundle, default_route)
        om = plan["owner_matrix"]
        for key in ("style_identity_owner", "color_owner", "typography_owner", "spacing_owner", "motion_owner"):
            assert key in om

    def test_rationale_zh(self, sample_tag_bundle, default_route):
        plan = self._make_plan(sample_tag_bundle, default_route, lang="zh")
        assert any("站点类型" in r for r in plan["rationale"])

    def test_rules_mode_rationale(self, sample_tag_bundle, default_route):
        plan = self._make_plan(sample_tag_bundle, default_route, recommendation_mode="rules")
        assert any("deterministic" in r or "纯规则" in r for r in plan["rationale"])

    def test_with_real_data(self, sample_tag_bundle, default_route, animation_profiles, interaction_patterns):
        plan = self._make_plan(
            sample_tag_bundle,
            default_route,
            animation_profiles=animation_profiles,
            interaction_patterns=interaction_patterns,
        )
        assert isinstance(plan["ai_interaction_script"], list)
        assert isinstance(plan["checks"], list)

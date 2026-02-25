"""Unit tests for scripts/_common.py utilities."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from _common import load_json, normalize_text, now_iso, tokenize


# ---------------------------------------------------------------------------
# load_json
# ---------------------------------------------------------------------------

class TestLoadJson:
    """Tests for load_json()."""

    def test_loads_valid_json(self, tmp_path: Path) -> None:
        data = {"key": "value", "nested": {"a": 1}}
        fp = tmp_path / "valid.json"
        fp.write_text(json.dumps(data), encoding="utf-8")

        result = load_json(fp)

        assert result == data

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist.json"

        with pytest.raises(FileNotFoundError):
            load_json(missing)

    def test_raises_on_invalid_json(self, tmp_path: Path) -> None:
        fp = tmp_path / "bad.json"
        fp.write_text("{not valid json!!", encoding="utf-8")

        with pytest.raises(json.JSONDecodeError):
            load_json(fp)

    def test_loads_utf8_content(self, tmp_path: Path) -> None:
        data = {"name": "测试风格", "desc": "日本語テスト"}
        fp = tmp_path / "utf8.json"
        fp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        result = load_json(fp)

        assert result == data


# ---------------------------------------------------------------------------
# normalize_text
# ---------------------------------------------------------------------------

class TestNormalizeText:
    """Tests for normalize_text()."""

    def test_lowercases_text(self) -> None:
        assert normalize_text("Hello WORLD") == "hello world"

    def test_strips_punctuation(self) -> None:
        # Punctuation replaced by space, then whitespace collapsed
        assert normalize_text("hello, world!") == "hello world"
        result = normalize_text("one...two///three")
        assert "  " not in result  # no double spaces after collapse

    def test_preserves_cjk_characters(self) -> None:
        result = normalize_text("现代简约风格")
        assert result == "现代简约风格"

    def test_preserves_hyphens(self) -> None:
        result = normalize_text("modern-tech")
        assert result == "modern-tech"

    def test_preserves_alphanumeric(self) -> None:
        result = normalize_text("grid2x layout3")
        assert result == "grid2x layout3"

    def test_handles_none(self) -> None:
        assert normalize_text(None) == ""

    def test_handles_empty_string(self) -> None:
        assert normalize_text("") == ""

    def test_collapses_whitespace(self) -> None:
        assert normalize_text("  too   many   spaces  ") == "too many spaces"

    def test_mixed_cjk_and_latin(self) -> None:
        result = normalize_text("Modern 现代 Style")
        assert "modern" in result
        assert "现代" in result
        assert "style" in result


# ---------------------------------------------------------------------------
# tokenize
# ---------------------------------------------------------------------------

class TestTokenize:
    """Tests for tokenize()."""

    def test_english_terms(self) -> None:
        tokens = tokenize("dark gradient cards")
        assert "dark" in tokens
        assert "gradient" in tokens
        assert "cards" in tokens

    def test_filters_stopwords(self) -> None:
        tokens = tokenize("the design for your page")
        # "the", "for", "your", "page", "design" are all stopwords
        assert "the" not in tokens
        assert "for" not in tokens
        assert "your" not in tokens
        assert "page" not in tokens
        assert "design" not in tokens

    def test_filters_single_char_latin(self) -> None:
        tokens = tokenize("a b c real")
        assert "a" not in tokens
        assert "b" not in tokens
        assert "c" not in tokens
        assert "real" in tokens

    def test_cjk_bigrams(self) -> None:
        # "现代简约" -> bigrams: "现代", "代简", "简约"
        tokens = tokenize("现代简约")
        assert "现代" in tokens
        assert "代简" in tokens
        assert "简约" in tokens

    def test_cjk_full_term_included(self) -> None:
        # Full CJK run (>=2 chars, not a stopword) is also included
        tokens = tokenize("现代简约")
        assert "现代简约" in tokens

    def test_cjk_stopword_bigrams_filtered(self) -> None:
        # "风格" and "设计" are in STOPWORDS
        tokens = tokenize("风格")
        assert "风格" not in tokens

    def test_mixed_cjk_and_english(self) -> None:
        tokens = tokenize("modern 现代简约 cards")
        assert "modern" in tokens
        assert "cards" in tokens
        assert "现代" in tokens

    def test_hyphenated_terms_split(self) -> None:
        tokens = tokenize("modern-tech")
        assert "modern" in tokens
        assert "tech" in tokens

    def test_hyphen_single_char_parts_filtered(self) -> None:
        tokens = tokenize("a-real-b")
        assert "a" not in tokens
        assert "b" not in tokens
        assert "real" in tokens

    def test_empty_input(self) -> None:
        assert tokenize("") == []

    def test_only_stopwords_returns_empty(self) -> None:
        tokens = tokenize("the and for with")
        assert tokens == []

    def test_punctuation_stripped_before_tokenizing(self) -> None:
        tokens = tokenize("hello! world?")
        assert "hello" in tokens
        assert "world" in tokens


# ---------------------------------------------------------------------------
# now_iso
# ---------------------------------------------------------------------------

class TestNowIso:
    """Tests for now_iso()."""

    def test_returns_string(self) -> None:
        result = now_iso()
        assert isinstance(result, str)

    def test_ends_with_z(self) -> None:
        result = now_iso()
        assert result.endswith("Z")

    def test_valid_iso_format(self) -> None:
        result = now_iso()
        # Should parse without error; strip trailing Z for fromisoformat
        parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
        assert parsed.tzinfo is not None

    def test_no_microseconds(self) -> None:
        result = now_iso()
        # ISO with microseconds would contain a dot before timezone
        assert "." not in result

    def test_reasonable_timestamp(self) -> None:
        before = datetime.now(timezone.utc).replace(microsecond=0)
        result = now_iso()
        after = datetime.now(timezone.utc).replace(microsecond=0)

        parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
        assert before <= parsed <= after

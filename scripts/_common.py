"""Shared utilities for stylekit-style-prompts scripts."""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

__version__ = "0.1.1"

# ---------------------------------------------------------------------------
# Stopwords
# ---------------------------------------------------------------------------

STOPWORDS: set[str] = {
    "the", "and", "for", "with", "from", "that", "this", "into",
    "your", "you", "want", "need", "make", "build",
    "page", "site", "style", "design", "frontend", "ui", "ux",
    "页面", "风格", "设计", "前端", "需要", "希望", "一个", "这个",
}

RULE_STOPWORDS: set[str] = {
    "use", "using", "must", "should", "ensure", "keep", "add", "set",
    "avoid", "do", "not",
    "the", "and", "for", "with", "from", "that", "this", "your", "you",
    "to", "in", "on", "of", "at", "by", "as", "be", "is", "are",
    "使用", "添加", "加入", "保持", "确保", "避免", "禁止", "不要",
    "需要", "并", "和", "与", "在", "到", "及", "或",
}


# ---------------------------------------------------------------------------
# Text normalization & tokenization
# ---------------------------------------------------------------------------

def normalize_text(value: Any) -> str:
    """Normalize text: lowercase, strip punctuation (keep CJK/alphanumeric/hyphens)."""
    text = str(value or "").lower()
    text = re.sub(r"[^\w\u4e00-\u9fff\s-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text: str) -> list[str]:
    """Tokenize text into searchable terms (Latin + CJK bi-gram)."""
    text_norm = normalize_text(text)
    tokens: list[str] = []
    for part in re.findall(r"[\u4e00-\u9fff]+|[a-z0-9-]+", text_norm):
        if re.fullmatch(r"[\u4e00-\u9fff]+", part):
            if len(part) >= 2 and part not in STOPWORDS:
                tokens.append(part)
            if len(part) >= 2:
                for i in range(len(part) - 1):
                    gram = part[i : i + 2]
                    if gram not in STOPWORDS:
                        tokens.append(gram)
            continue
        for unit in part.split("-"):
            if len(unit) > 1 and unit not in STOPWORDS:
                tokens.append(unit)
    return tokens


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file and return the parsed dict."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Timestamp
# ---------------------------------------------------------------------------

def now_iso() -> str:
    """Return current UTC time in ISO 8601 format."""
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

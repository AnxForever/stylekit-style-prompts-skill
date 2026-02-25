"""Contract tests: validate real pipeline outputs against JSON Schema (Draft 2020-12).

Every test runs the actual CLI script via subprocess, parses the JSON output,
and validates it against the corresponding schema in tests/schemas/.

All tests are marked ``@pytest.mark.slow`` so they can be excluded from fast
unit-test runs (``pytest -m 'not slow'``).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_ROOT / "scripts"
SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"
PYTHON = sys.executable


# ---------------------------------------------------------------------------
# Schema loaders
# ---------------------------------------------------------------------------

def _load_schema(name: str) -> dict[str, Any]:
    path = SCHEMAS_DIR / name
    with path.open("r", encoding="utf-8") as fh:
        schema = json.load(fh)
    Draft202012Validator.check_schema(schema)
    return schema


@pytest.fixture(scope="module")
def brief_schema() -> dict[str, Any]:
    return _load_schema("generate_brief_output.json")


@pytest.fixture(scope="module")
def pipeline_manual_schema() -> dict[str, Any]:
    return _load_schema("run_pipeline_manual_output.json")


@pytest.fixture(scope="module")
def pipeline_codegen_schema() -> dict[str, Any]:
    return _load_schema("run_pipeline_codegen_output.json")


@pytest.fixture(scope="module")
def qa_schema() -> dict[str, Any]:
    return _load_schema("qa_prompt_output.json")


@pytest.fixture(scope="module")
def search_schema() -> dict[str, Any]:
    return _load_schema("search_stylekit_output.json")


@pytest.fixture(scope="module")
def benchmark_schema() -> dict[str, Any]:
    return _load_schema("benchmark_pipeline_output.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_script(script: str, args: list[str], *, timeout: int = 120) -> dict[str, Any]:
    """Run a script under ``scripts/`` and return parsed JSON output."""
    cmd = [PYTHON, str(SCRIPTS_DIR / script), *args]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(SKILL_ROOT),
    )
    assert result.returncode == 0, (
        f"{script} exited with code {result.returncode}\n"
        f"--- stderr ---\n{result.stderr[-2000:]}"
    )
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict), f"Expected dict, got {type(payload).__name__}"
    return payload


def _validate(payload: dict[str, Any], schema: dict[str, Any]) -> None:
    """Validate *payload* against *schema* using Draft 2020-12."""
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        msgs = []
        for err in errors[:10]:
            path = ".".join(str(p) for p in err.absolute_path) or "<root>"
            msgs.append(f"  [{path}] {err.message}")
        raise AssertionError(
            f"Schema validation failed ({len(errors)} error(s)):\n" + "\n".join(msgs)
        )


# ---------------------------------------------------------------------------
# Parametrized query x stack combos
# ---------------------------------------------------------------------------

QUERY_STACK_COMBOS = [
    pytest.param(
        "做一个SaaS数据分析仪表盘，带实时图表和KPI卡片",
        "nextjs",
        id="zh-saas-nextjs",
    ),
    pytest.param(
        "Build a modern landing page for a design agency with bold typography",
        "html-tailwind",
        id="en-landing-html",
    ),
    pytest.param(
        "创建一个极简主义技术博客，带代码高亮和暗色模式",
        "react",
        id="zh-blog-react",
    ),
]


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestGenerateBriefContract:
    """generate_brief.py --mode brief+prompt output conforms to schema."""

    @pytest.mark.parametrize("query,stack", QUERY_STACK_COMBOS)
    def test_generate_brief_contract(
        self,
        query: str,
        stack: str,
        brief_schema: dict[str, Any],
    ) -> None:
        payload = _run_script(
            "generate_brief.py",
            ["--query", query, "--stack", stack, "--mode", "brief+prompt"],
        )
        _validate(payload, brief_schema)


@pytest.mark.slow
class TestRunPipelineManualContract:
    """run_pipeline.py --workflow manual output conforms to schema."""

    @pytest.mark.parametrize("query,stack", QUERY_STACK_COMBOS)
    def test_run_pipeline_manual_contract(
        self,
        query: str,
        stack: str,
        pipeline_manual_schema: dict[str, Any],
    ) -> None:
        payload = _run_script(
            "run_pipeline.py",
            [
                "--query", query,
                "--stack", stack,
                "--workflow", "manual",
                "--format", "json",
            ],
        )
        _validate(payload, pipeline_manual_schema)


@pytest.mark.slow
class TestRunPipelineCodegenContract:
    """run_pipeline.py --workflow codegen output conforms to schema."""

    @pytest.mark.parametrize("query,stack", QUERY_STACK_COMBOS)
    def test_run_pipeline_codegen_contract(
        self,
        query: str,
        stack: str,
        pipeline_codegen_schema: dict[str, Any],
    ) -> None:
        payload = _run_script(
            "run_pipeline.py",
            [
                "--query", query,
                "--stack", stack,
                "--workflow", "codegen",
                "--format", "json",
            ],
        )
        _validate(payload, pipeline_codegen_schema)


@pytest.mark.slow
class TestQaPromptContract:
    """qa_prompt.py output conforms to schema."""

    @pytest.mark.parametrize("query,stack", QUERY_STACK_COMBOS)
    def test_qa_prompt_contract(
        self,
        query: str,
        stack: str,
        qa_schema: dict[str, Any],
    ) -> None:
        # First generate a prompt to feed into QA
        brief_payload = _run_script(
            "generate_brief.py",
            ["--query", query, "--stack", stack, "--mode", "brief+prompt"],
        )
        hard_prompt = brief_payload.get("hard_prompt", "")
        assert hard_prompt, "generate_brief produced empty hard_prompt"

        # Run QA audit on the generated prompt
        payload = _run_script(
            "qa_prompt.py",
            ["--text", hard_prompt, "--lang", brief_payload.get("language", "en")],
        )
        _validate(payload, qa_schema)


@pytest.mark.slow
class TestSearchStylekitContract:
    """search_stylekit.py output conforms to schema."""

    @pytest.mark.parametrize("query,stack", QUERY_STACK_COMBOS)
    def test_search_stylekit_contract(
        self,
        query: str,
        stack: str,
        search_schema: dict[str, Any],
    ) -> None:
        del stack  # stack is not used by search_stylekit; keep param matrix consistent.
        payload = _run_script(
            "search_stylekit.py",
            ["--query", query, "--top", "5", "--format", "json"],
        )
        _validate(payload, search_schema)


@pytest.mark.slow
class TestBenchmarkPipelineContract:
    """benchmark_pipeline.py output conforms to schema."""

    def test_benchmark_pipeline_contract(
        self,
        benchmark_schema: dict[str, Any],
    ) -> None:
        payload = _run_script(
            "benchmark_pipeline.py",
            ["--format", "json", "--show-cases", "1"],
            timeout=240,
        )
        _validate(payload, benchmark_schema)

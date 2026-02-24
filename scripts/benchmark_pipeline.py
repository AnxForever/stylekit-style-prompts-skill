#!/usr/bin/env python3
"""Benchmark StyleKit run_pipeline quality on a query suite."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PIPELINE_SCRIPT = SCRIPT_DIR / "run_pipeline.py"

DEFAULT_CASES = [
    {"query": "高端科技SaaS财务后台，玻璃质感，强调可读性", "stack": "nextjs"},
    {"query": "极简企业官网首页，白底黑字，突出信任感", "stack": "nextjs"},
    {"query": "医疗设备管理后台，信息密度高但不能压抑", "stack": "react"},
    {"query": "教育平台课程页，温暖友好，移动端优先", "stack": "vue"},
    {"query": "AI 产品落地页，需要未来感但不过度炫技", "stack": "html-tailwind"},
    {"query": "咖啡品牌官网，复古杂志风，强调故事感", "stack": "nextjs"},
    {"query": "电商商品详情页，突出转化和评价模块", "stack": "react"},
    {"query": "开发者文档站，清晰目录，深浅色模式", "stack": "nextjs"},
    {"query": "设计作品集站点，强视觉冲击但保留可读性", "stack": "svelte"},
    {"query": "金融看板，实时数据卡片与图表区分层", "stack": "nextjs"},
    {"query": "SaaS pricing page with trustworthy enterprise tone", "stack": "tailwind-v4"},
    {"query": "Developer tools dashboard with dense but readable data", "stack": "nextjs"},
    {"query": "Luxury fashion landing page with editorial typography", "stack": "react"},
    {"query": "Healthcare admin panel focused on accessibility first", "stack": "nextjs"},
    {"query": "Crypto analytics panel with high contrast caution states", "stack": "react"},
    {"query": "Portfolio site for motion designer, dramatic but usable", "stack": "svelte"},
    {"query": "Minimal productivity app onboarding flow", "stack": "vue"},
    {"query": "B2B marketing homepage with social proof sections", "stack": "html-tailwind"},
    {"query": "Travel booking UI with calm visual hierarchy", "stack": "nextjs"},
    {"query": "E-commerce checkout flow optimized for conversion", "stack": "react"},
]

STRICT_BUCKET_HINTS = {
    "healthcare",
    "medical",
    "hospital",
    "clinic",
    "finance",
    "financial",
    "fintech",
    "bank",
    "banking",
    "payment",
    "insurance",
    "education",
    "school",
    "university",
    "government",
    "legal",
    "compliance",
    "医疗",
    "财务",
    "金融",
    "银行",
    "保险",
    "教育",
    "政府",
    "合规",
}

EXPRESSIVE_BUCKET_HINTS = {
    "creative",
    "dramatic",
    "experimental",
    "cyberpunk",
    "vaporwave",
    "retro",
    "fashion",
    "portfolio",
    "视觉冲击",
    "创意",
    "前卫",
    "复古",
    "霓虹",
    "作品集",
}


def infer_bucket(query: str) -> str:
    q = query.lower()
    if any(token in q for token in STRICT_BUCKET_HINTS):
        return "strict-domain"
    if any(token in q for token in EXPRESSIVE_BUCKET_HINTS):
        return "expressive"
    return "balanced"


def load_cases(path: str | None) -> list[dict[str, str]]:
    if not path:
        return DEFAULT_CASES
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"Cases file not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, list):
        raise SystemExit("Cases file must be a JSON array of {query, stack}")
    out: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        query = str(item.get("query", "")).strip()
        stack = str(item.get("stack", "")).strip()
        if not query or not stack:
            continue
        bucket = str(item.get("bucket", "")).strip() or infer_bucket(query)
        out.append({"query": query, "stack": stack, "bucket": bucket})
    if not out:
        raise SystemExit("No valid benchmark cases found")
    return out


def run_case(py: str, query: str, stack: str, blend_mode: str, bucket: str, refine_mode: str, reference_type: str) -> dict[str, Any]:
    cmd = [
        py,
        str(PIPELINE_SCRIPT),
        "--workflow",
        "codegen",
        "--query",
        query,
        "--stack",
        stack,
        "--blend-mode",
        blend_mode,
        "--refine-mode",
        refine_mode,
        "--reference-type",
        reference_type,
        "--format",
        "json",
    ]
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    duration = time.time() - t0

    if proc.returncode != 0:
        return {
            "ok": False,
            "query": query,
            "stack": stack,
            "bucket": bucket,
            "time_sec": round(duration, 3),
            "error": (proc.stderr or proc.stdout or "execution failed")[:400],
        }

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "query": query,
            "stack": stack,
            "bucket": bucket,
            "time_sec": round(duration, 3),
            "error": f"json parse failed: {exc}",
        }

    quality_gate = payload.get("quality_gate", {})
    checks = {c.get("id"): c.get("passed") for c in quality_gate.get("checks", [])}
    violations = [v.get("id") for v in quality_gate.get("violations", [])]
    hard_prompt = payload.get("result", {}).get("hard_prompt", "")

    return {
        "ok": True,
        "query": query,
        "stack": stack,
        "bucket": bucket,
        "time_sec": round(duration, 3),
        "status": payload.get("status"),
        "quality_status": quality_gate.get("status"),
        "selected_style": payload.get("selected_style"),
        "violations": violations,
        "rule_conflict": checks.get("rule_conflict"),
        "language_consistency": checks.get("language_consistency"),
        "refinement_mode_alignment": checks.get("refinement_mode_alignment"),
        "reference_context_guard": checks.get("reference_context_guard"),
        "hard_prompt_len": len(hard_prompt),
        "ai_rules_count": len(payload.get("result", {}).get("ai_rules", []) or []),
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    ok_results = [r for r in results if r.get("ok")]
    pass_results = [r for r in ok_results if r.get("status") == "pass"]
    fail_results = [r for r in results if not r.get("ok") or r.get("status") != "pass"]

    style_distribution: dict[str, int] = {}
    check_pass_counts: dict[str, int] = {}
    check_seen_counts: dict[str, int] = {}
    bucket_seen: dict[str, int] = {}
    bucket_pass: dict[str, int] = {}
    bucket_style_dist: dict[str, dict[str, int]] = {}

    for r in ok_results:
        style = r.get("selected_style") or "unknown"
        style_distribution[style] = style_distribution.get(style, 0) + 1
        bucket = r.get("bucket", "unclassified")
        bucket_seen[bucket] = bucket_seen.get(bucket, 0) + 1
        if r.get("status") == "pass":
            bucket_pass[bucket] = bucket_pass.get(bucket, 0) + 1
        bucket_style_dist.setdefault(bucket, {})
        bucket_style_dist[bucket][style] = bucket_style_dist[bucket].get(style, 0) + 1

        for cid in ("rule_conflict", "language_consistency", "refinement_mode_alignment", "reference_context_guard"):
            val = r.get(cid)
            if val is None:
                continue
            check_seen_counts[cid] = check_seen_counts.get(cid, 0) + 1
            if val:
                check_pass_counts[cid] = check_pass_counts.get(cid, 0) + 1

    summary = {
        "cases": len(results),
        "ok_runs": len(ok_results),
        "pass_runs": len(pass_results),
        "pass_rate": round(len(pass_results) / len(results), 4) if results else 0.0,
        "avg_time_sec": round(statistics.mean(r["time_sec"] for r in ok_results), 3) if ok_results else None,
        "avg_hard_prompt_len": round(statistics.mean(r["hard_prompt_len"] for r in ok_results), 1) if ok_results else None,
        "avg_ai_rules_count": round(statistics.mean(r["ai_rules_count"] for r in ok_results), 2) if ok_results else None,
        "style_distribution": dict(sorted(style_distribution.items(), key=lambda kv: kv[1], reverse=True)),
        "check_pass_rate": {
            cid: round(check_pass_counts.get(cid, 0) / seen, 4)
            for cid, seen in check_seen_counts.items()
            if seen > 0
        },
        "bucket_pass_rate": {
            bucket: {
                "cases": bucket_seen.get(bucket, 0),
                "pass_rate": round(bucket_pass.get(bucket, 0) / max(bucket_seen.get(bucket, 0), 1), 4),
                "style_distribution": dict(
                    sorted(bucket_style_dist.get(bucket, {}).items(), key=lambda kv: kv[1], reverse=True)
                ),
            }
            for bucket in sorted(bucket_seen.keys())
        },
        "failed_cases": [
            {
                "query": r.get("query"),
                "stack": r.get("stack"),
                "bucket": r.get("bucket"),
                "status": r.get("status", "exec_fail"),
                "violations": r.get("violations", []),
                "error": r.get("error"),
            }
            for r in fail_results
        ],
    }
    return summary


def load_baseline_summary(path: str | None) -> tuple[dict[str, Any] | None, str | None]:
    if not path:
        return None, None
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"Baseline snapshot not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, dict) and "summary" in payload and isinstance(payload["summary"], dict):
        return payload["summary"], str(p)
    if isinstance(payload, dict) and "pass_rate" in payload:
        return payload, str(p)
    raise SystemExit(f"Invalid baseline snapshot format: {p}")


def compare_with_baseline(
    current_summary: dict[str, Any],
    baseline_summary: dict[str, Any],
    max_pass_rate_drop: float,
    max_bucket_pass_drop: float,
    max_check_pass_drop: float,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []

    baseline_pass = float(baseline_summary.get("pass_rate", 0.0))
    current_pass = float(current_summary.get("pass_rate", 0.0))
    pass_drop = baseline_pass - current_pass
    if pass_drop > max_pass_rate_drop:
        findings.append(
            {
                "id": "pass_rate_drop",
                "severity": "high",
                "baseline": round(baseline_pass, 4),
                "current": round(current_pass, 4),
                "drop": round(pass_drop, 4),
                "threshold": max_pass_rate_drop,
                "message": "Overall benchmark pass_rate dropped beyond threshold.",
            }
        )

    baseline_checks = baseline_summary.get("check_pass_rate", {}) or {}
    current_checks = current_summary.get("check_pass_rate", {}) or {}
    for check_id, baseline_ratio_raw in baseline_checks.items():
        baseline_ratio = float(baseline_ratio_raw)
        current_ratio = float(current_checks.get(check_id, 0.0))
        drop = baseline_ratio - current_ratio
        if drop > max_check_pass_drop:
            findings.append(
                {
                    "id": "check_pass_rate_drop",
                    "severity": "high",
                    "check_id": check_id,
                    "baseline": round(baseline_ratio, 4),
                    "current": round(current_ratio, 4),
                    "drop": round(drop, 4),
                    "threshold": max_check_pass_drop,
                    "message": f"Hard-check pass_rate dropped for `{check_id}`.",
                }
            )

    baseline_buckets = baseline_summary.get("bucket_pass_rate", {}) or {}
    current_buckets = current_summary.get("bucket_pass_rate", {}) or {}
    for bucket, baseline_meta in baseline_buckets.items():
        if bucket not in current_buckets:
            findings.append(
                {
                    "id": "bucket_missing",
                    "severity": "high",
                    "bucket": bucket,
                    "message": f"Bucket `{bucket}` missing in current benchmark run.",
                }
            )
            continue
        baseline_ratio = float((baseline_meta or {}).get("pass_rate", 0.0))
        current_ratio = float((current_buckets.get(bucket) or {}).get("pass_rate", 0.0))
        drop = baseline_ratio - current_ratio
        if drop > max_bucket_pass_drop:
            findings.append(
                {
                    "id": "bucket_pass_rate_drop",
                    "severity": "high",
                    "bucket": bucket,
                    "baseline": round(baseline_ratio, 4),
                    "current": round(current_ratio, 4),
                    "drop": round(drop, 4),
                    "threshold": max_bucket_pass_drop,
                    "message": f"Bucket pass_rate dropped for `{bucket}`.",
                }
            )

    return {
        "enabled": True,
        "passed": len(findings) == 0,
        "thresholds": {
            "max_pass_rate_drop": max_pass_rate_drop,
            "max_bucket_pass_drop": max_bucket_pass_drop,
            "max_check_pass_drop": max_check_pass_drop,
        },
        "findings": findings,
    }


def resolve_baseline_update_target(
    baseline_update_target: str | None,
    baseline_snapshot: str | None,
    snapshot_out: str | None,
) -> str | None:
    if baseline_update_target:
        return baseline_update_target
    if baseline_snapshot:
        return baseline_snapshot
    if snapshot_out:
        return snapshot_out
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark StyleKit run_pipeline outputs")
    parser.add_argument("--cases", help="Path to JSON array [{\"query\":\"...\", \"stack\":\"...\"}]")
    parser.add_argument("--blend-mode", default="auto", choices=["off", "auto", "on"])
    parser.add_argument("--refine-mode", default="new", choices=["new", "polish", "debug", "contrast-fix", "layout-fix", "component-fill"])
    parser.add_argument("--reference-type", default="none", choices=["none", "screenshot", "figma", "mixed"])
    parser.add_argument("--snapshot-out", help="Optional output path for benchmark snapshot JSON")
    parser.add_argument("--baseline-snapshot", help="Optional baseline snapshot JSON for regression comparison")
    parser.add_argument("--max-pass-rate-drop", type=float, default=0.02, help="Allowed absolute pass_rate drop vs baseline")
    parser.add_argument("--max-bucket-pass-drop", type=float, default=0.05, help="Allowed absolute bucket pass_rate drop vs baseline")
    parser.add_argument("--max-check-pass-drop", type=float, default=0.05, help="Allowed absolute hard-check pass_rate drop vs baseline")
    parser.add_argument("--fail-on-regression", action="store_true", help="Exit non-zero when regression gate fails")
    parser.add_argument(
        "--baseline-update-mode",
        default="off",
        choices=["off", "on-pass", "always"],
        help="Automatic baseline update strategy after benchmark run",
    )
    parser.add_argument(
        "--baseline-update-target",
        help="Path to write updated baseline snapshot (defaults to baseline-snapshot, then snapshot-out)",
    )
    parser.add_argument("--format", default="json", choices=["json", "markdown"])
    parser.add_argument("--show-cases", type=int, default=5, help="How many per-case results to include in output preview")
    args = parser.parse_args()

    if not PIPELINE_SCRIPT.exists():
        raise SystemExit(f"Pipeline script not found: {PIPELINE_SCRIPT}")

    cases = load_cases(args.cases)
    py = sys.executable
    normalized_cases = [
        {"query": case["query"], "stack": case["stack"], "bucket": case.get("bucket") or infer_bucket(case["query"])}
        for case in cases
    ]
    results = [
        run_case(
            py,
            case["query"],
            case["stack"],
            args.blend_mode,
            case["bucket"],
            args.refine_mode,
            args.reference_type,
        )
        for case in normalized_cases
    ]
    summary = summarize(results)
    baseline_summary, baseline_path = load_baseline_summary(args.baseline_snapshot)
    regression_gate = {
        "enabled": False,
        "passed": True,
        "thresholds": {
            "max_pass_rate_drop": args.max_pass_rate_drop,
            "max_bucket_pass_drop": args.max_bucket_pass_drop,
            "max_check_pass_drop": args.max_check_pass_drop,
        },
        "findings": [],
    }
    if baseline_summary is not None:
        regression_gate = compare_with_baseline(
            current_summary=summary,
            baseline_summary=baseline_summary,
            max_pass_rate_drop=args.max_pass_rate_drop,
            max_bucket_pass_drop=args.max_bucket_pass_drop,
            max_check_pass_drop=args.max_check_pass_drop,
        )
        regression_gate["baseline_snapshot"] = baseline_path

    update_target = resolve_baseline_update_target(
        baseline_update_target=args.baseline_update_target,
        baseline_snapshot=baseline_path,
        snapshot_out=args.snapshot_out,
    )
    update_enabled = args.baseline_update_mode != "off"
    update_reason = ""
    should_update = False
    if update_enabled:
        if not update_target:
            raise SystemExit("baseline update requested but no target path is available")
        if args.baseline_update_mode == "always":
            should_update = True
            update_reason = "always"
        elif args.baseline_update_mode == "on-pass":
            if regression_gate.get("enabled"):
                should_update = bool(regression_gate.get("passed"))
                update_reason = "on-pass with regression gate"
            else:
                should_update = True
                update_reason = "on-pass without regression baseline"

    if args.format == "markdown":
        lines = [
            "# StyleKit Benchmark",
            f"- Cases: {summary['cases']}",
            f"- Pass rate: {summary['pass_rate']}",
            f"- Avg time (s): {summary['avg_time_sec']}",
            f"- Avg hard prompt length: {summary['avg_hard_prompt_len']}",
            f"- Avg ai_rules count: {summary['avg_ai_rules_count']}",
            f"- Refine mode: {args.refine_mode}",
            f"- Reference type: {args.reference_type}",
            f"- Regression gate: {'enabled' if regression_gate.get('enabled') else 'disabled'}",
            f"- Baseline update mode: {args.baseline_update_mode}",
            "",
            "## Hard-check Pass Rate",
        ]
        for cid, ratio in summary.get("check_pass_rate", {}).items():
            lines.append(f"- {cid}: {ratio}")
        lines.append("")
        lines.append("## Bucket Pass Rate")
        for bucket, meta in summary.get("bucket_pass_rate", {}).items():
            lines.append(f"- {bucket}: {meta.get('pass_rate')} ({meta.get('cases')} cases)")
        lines.append("")
        if regression_gate.get("enabled"):
            lines.append("## Regression Gate")
            lines.append(f"- Passed: {regression_gate.get('passed')}")
            lines.append(f"- Baseline: {baseline_path}")
            if regression_gate.get("findings"):
                for finding in regression_gate.get("findings", []):
                    lines.append(f"- [{finding.get('id')}] {finding.get('message')}")
            else:
                lines.append("- no regressions")
            lines.append("")
        if update_enabled:
            lines.append("## Baseline Update")
            lines.append(f"- Target: {update_target}")
            lines.append(f"- Will update: {should_update}")
            lines.append(f"- Reason: {update_reason or 'n/a'}")
            lines.append("")
        lines.append("## Failed Cases")
        if not summary["failed_cases"]:
            lines.append("- none")
        else:
            for item in summary["failed_cases"]:
                lines.append(
                    f"- [{item['stack']}] ({item.get('bucket')}) {item['query']} | {item['status']} | {item.get('violations')}"
                )
        lines.append("")
        lines.append("## Sample Results")
        for item in results[: max(1, args.show_cases)]:
            lines.append(
                f"- [{item.get('stack')}] ({item.get('bucket')}) {item.get('query')} => {item.get('status', 'exec_fail')} ({item.get('selected_style', 'n/a')})"
            )
        print("\n".join(lines))
        return

    payload = {
        "summary": summary,
        "regression_gate": regression_gate,
        "baseline_update": {
            "mode": args.baseline_update_mode,
            "target": update_target,
            "enabled": update_enabled,
            "applied": False,
            "reason": update_reason,
        },
        "meta": {
            "generated_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "blend_mode": args.blend_mode,
            "refine_mode": args.refine_mode,
            "reference_type": args.reference_type,
            "baseline_snapshot": baseline_path,
            "fail_on_regression": args.fail_on_regression,
            "baseline_update_mode": args.baseline_update_mode,
            "baseline_update_target": update_target,
        },
        "sample_results": results[: max(1, args.show_cases)],
    }
    if should_update and update_target:
        update_path = Path(update_target)
        update_path.parent.mkdir(parents=True, exist_ok=True)
        payload["baseline_update"]["applied"] = True
        update_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.snapshot_out:
        snapshot_path = Path(args.snapshot_out)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.fail_on_regression and regression_gate.get("enabled") and not regression_gate.get("passed"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()

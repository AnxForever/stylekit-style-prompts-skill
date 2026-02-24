#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BENCH_SCRIPT="$SCRIPT_DIR/benchmark_pipeline.py"

BASELINE="$SKILL_ROOT/references/benchmark-baseline.json"
SNAPSHOT_OUT="$SKILL_ROOT/tmp/benchmark-ci-latest.json"
BOOTSTRAP_BASELINE="false"
BLEND_MODE="auto"
REFINE_MODE="new"
REFERENCE_TYPE="none"
MAX_PASS_RATE_DROP="0.02"
MAX_BUCKET_PASS_DROP="0.05"
MAX_CHECK_PASS_DROP="0.05"

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/ci_regression_gate.sh [options]

Options:
  --baseline <path>             Baseline snapshot path (default: references/benchmark-baseline.json)
  --snapshot-out <path>         Latest benchmark snapshot output path
  --bootstrap-baseline          Create baseline if missing, then exit success
  --blend-mode <off|auto|on>    Blend mode for benchmark run
  --refine-mode <mode>          Refine mode for benchmark run
  --reference-type <type>       Reference type for benchmark run
  --max-pass-rate-drop <float>  Allowed overall pass_rate drop
  --max-bucket-pass-drop <float> Allowed bucket pass_rate drop
  --max-check-pass-drop <float> Allowed hard-check pass_rate drop

Examples:
  bash scripts/ci_regression_gate.sh
  bash scripts/ci_regression_gate.sh --baseline references/benchmark-baseline.json --bootstrap-baseline
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --baseline)
      BASELINE="$2"
      shift 2
      ;;
    --snapshot-out)
      SNAPSHOT_OUT="$2"
      shift 2
      ;;
    --bootstrap-baseline)
      BOOTSTRAP_BASELINE="true"
      shift
      ;;
    --blend-mode)
      BLEND_MODE="$2"
      shift 2
      ;;
    --refine-mode)
      REFINE_MODE="$2"
      shift 2
      ;;
    --reference-type)
      REFERENCE_TYPE="$2"
      shift 2
      ;;
    --max-pass-rate-drop)
      MAX_PASS_RATE_DROP="$2"
      shift 2
      ;;
    --max-bucket-pass-drop)
      MAX_BUCKET_PASS_DROP="$2"
      shift 2
      ;;
    --max-check-pass-drop)
      MAX_CHECK_PASS_DROP="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

mkdir -p "$(dirname "$SNAPSHOT_OUT")"
mkdir -p "$(dirname "$BASELINE")"

if [[ ! -f "$BASELINE" ]]; then
  if [[ "$BOOTSTRAP_BASELINE" == "true" ]]; then
    echo "[ci-regression-gate] Baseline not found. Bootstrapping baseline at $BASELINE"
    python3 "$BENCH_SCRIPT" \
      --format json \
      --blend-mode "$BLEND_MODE" \
      --refine-mode "$REFINE_MODE" \
      --reference-type "$REFERENCE_TYPE" \
      --snapshot-out "$BASELINE"
    echo "[ci-regression-gate] Baseline created."
    exit 0
  fi

  echo "[ci-regression-gate] Baseline snapshot missing: $BASELINE" >&2
  echo "[ci-regression-gate] Run with --bootstrap-baseline once to initialize baseline." >&2
  exit 2
fi

echo "[ci-regression-gate] Running benchmark regression gate..."
python3 "$BENCH_SCRIPT" \
  --format json \
  --blend-mode "$BLEND_MODE" \
  --refine-mode "$REFINE_MODE" \
  --reference-type "$REFERENCE_TYPE" \
  --baseline-snapshot "$BASELINE" \
  --snapshot-out "$SNAPSHOT_OUT" \
  --max-pass-rate-drop "$MAX_PASS_RATE_DROP" \
  --max-bucket-pass-drop "$MAX_BUCKET_PASS_DROP" \
  --max-check-pass-drop "$MAX_CHECK_PASS_DROP" \
  --fail-on-regression

echo "[ci-regression-gate] Regression gate passed. Snapshot: $SNAPSHOT_OUT"

# stylekit-style-prompts

Standalone skill for generating high-quality frontend prompts from StyleKit styles.

## Quick start

```bash
python3 scripts/smoke_test.py
python3 scripts/run_pipeline.py --query "高端科技SaaS财务后台，玻璃质感，强调可读性" --stack nextjs --format json
```

## Regression gate

```bash
bash scripts/ci_regression_gate.sh --baseline references/benchmark-baseline.json --snapshot-out tmp/benchmark-ci-latest.json
```

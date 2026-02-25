# Release Process

This repository uses benchmark regression gates to keep skill quality stable.
For full release readiness gates, also run `GO_LIVE_CHECKLIST.md`.

## 1) Pre-release Checks

Run smoke test:

```bash
python3 scripts/smoke_test.py
```

Run regression gate against baseline:

```bash
python3 scripts/benchmark_pipeline.py \
  --format json \
  --baseline-snapshot references/benchmark-baseline.json \
  --fail-on-regression
```

## 2) Baseline Update Policy

Only update baseline when the change is intentional and reviewed.

Update baseline on pass:

```bash
python3 scripts/benchmark_pipeline.py \
  --format json \
  --baseline-snapshot references/benchmark-baseline.json \
  --baseline-update-mode on-pass \
  --baseline-update-target references/benchmark-baseline.json
```

Commit baseline update in the same PR that changes benchmark behavior.

## 3) Versioning

Use semantic versioning:

- `MAJOR`: breaking contract changes
- `MINOR`: backward-compatible features
- `PATCH`: fixes and non-breaking improvements

## 4) Tag and Push

Example for `v0.1.0`:

```bash
git tag -a v0.1.0 -m "v0.1.0"
git push origin v0.1.0
```

## 5) CI Gate

CI workflow:

- `.github/workflows/regression-gate.yml`

One-command local equivalent:

```bash
bash scripts/ci_regression_gate.sh \
  --baseline references/benchmark-baseline.json \
  --snapshot-out tmp/benchmark-ci-latest.json
```

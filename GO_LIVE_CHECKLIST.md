# StyleKit Skill Go-Live Checklist

## 1) Gate Stability

- [ ] `main` branch passes CI continuously for at least 7 days (or 20 consecutive runs).
- [ ] No flaky tests in `pytest -m slow`.
- [ ] `regression_gate.passed=true` on the latest benchmark run.

## 2) Quality Baseline

- [ ] 30 real-world prompts (blog/saas/dashboard/docs/ecommerce/landing-page/portfolio/general) are evaluated.
- [ ] Overall pass rate >= 90%.
- [ ] No P0/P1 issues in design recommendation outputs.
- [ ] Re-run consistency: 5 repeated runs per case, key fields (`style_choice`, `site_profile`, `tag_bundle`) >= 95% identical.

## 3) Required Local Checks

Run all checks before release:

```bash
node bin/stylekit-skill.js doctor
python3 scripts/validate_taxonomy.py --format text --max-unused-style-tags 0 --fail-on-warning
python3 scripts/validate_output_contract_sync.py --format text --fail-on-warning
python3 scripts/smoke_test.py
pytest tests/ -m "not slow" -q
pytest tests/ -m slow -q
python3 scripts/benchmark_pipeline.py --format json --baseline-snapshot references/benchmark-baseline.json --fail-on-regression
```

## 4) Release Preparation

- [ ] Update `package.json` version (SemVer).
- [ ] Update `RELEASE.md` with notable changes and rollback notes.
- [ ] Confirm GitHub workflow `.github/workflows/regression-gate.yml` is green on the release commit.
- [ ] Verify `npm pack --dry-run` contains expected payload only.

## 5) Publish

```bash
npm login
npm whoami
npm publish --access public
```

## 6) Post-Release

- [ ] Tag release: `git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z`
- [ ] Install smoke check via npx:
  `npx @anxforever/stylekit-skill doctor`
- [ ] Archive benchmark snapshot under `tmp/` for traceability.

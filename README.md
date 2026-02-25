# @anxforever/stylekit-skill

StyleKit 风格提示词 Skill（独立仓库版）。  
目标：把 StyleKit 的风格能力直接安装到 Codex / Claude 的 skills 目录中。

## 1) 一键安装（面向使用者）

### 安装到 Codex

```bash
npx @anxforever/stylekit-skill install --tool codex
```

### 安装到 Claude

```bash
npx @anxforever/stylekit-skill install --tool claude
```

### 自动检测本机工具并安装

```bash
npx @anxforever/stylekit-skill install --tool auto
```

### 覆盖安装（已存在时）

```bash
npx @anxforever/stylekit-skill install --tool codex --force
```

### 卸载

```bash
npx @anxforever/stylekit-skill uninstall --tool codex
npx @anxforever/stylekit-skill uninstall --tool claude
```

### 环境自检

```bash
npx @anxforever/stylekit-skill doctor
```

## 2) 本地开发验证（维护者）

```bash
node bin/stylekit-skill.js doctor
node bin/stylekit-skill.js install --tool codex --target /tmp/stylekit-skill-test --force
node bin/stylekit-skill.js uninstall --target /tmp/stylekit-skill-test
python3 scripts/audit_style_rule_conflicts.py --format text
python3 scripts/validate_taxonomy.py --format json --max-unused-style-tags 0 --fail-on-warning
python3 scripts/validate_output_contract_sync.py --format json --fail-on-warning
python3 scripts/smoke_test.py
python3 scripts/run_pipeline.py --query "高端科技SaaS财务后台，玻璃质感，强调可读性" --stack nextjs --format json
python3 scripts/run_pipeline.py --workflow codegen --query "高端科技SaaS财务后台，玻璃质感，强调可读性" --stack nextjs --format json
python3 scripts/run_pipeline.py --query "高端科技SaaS财务后台，玻璃质感，强调可读性" --stack nextjs --site-type dashboard --recommendation-mode hybrid --content-depth skeleton --decision-speed fast --format json
python3 scripts/merge_taxonomy_expansion.py --type animation --input tmp/gemini-output.json --dry-run
python3 scripts/propose_upgrade.py --pipeline-output tmp/pipeline-output.json --out-dir tmp/upgrade-proposals --format json
python3 scripts/review_upgrade_candidate.py --candidate tmp/upgrade-proposals/<candidate>.json --format json
```

说明：
- 默认是 `--workflow manual`（手册/知识库模式）：输出设计简报 + 手册化建议，不强制走 prompt QA。
- 若要生成并严格审查 prompt，请显式加 `--workflow codegen`。
- v2 支持站点类型路由：`--site-type`（blog/saas/dashboard/docs/ecommerce/landing-page/portfolio/general）。
- v2 支持组合决策参数：`--recommendation-mode`、`--content-depth`、`--decision-speed`。
- taxonomy 门禁可用 `--max-unused-style-tags 0 --fail-on-warning` 强制 style tag registry 无闲置条目且 warning 视为失败。
- 契约防漂移门禁可用 `validate_output_contract_sync.py`：校验 `references/output-contract.md` 与 `tests/schemas` 一致（按每个必需章节的第一个 JSON 示例做门禁校验，可用 `--fail-on-warning` 将 warning 提升为失败）。
- taxonomy 扩展脚本支持 `new_style_tags` 字段，并会在 apply 时更新 `references/taxonomy/style-tag-registry.json`。
- 在 manual 模式下，会额外输出 `manual_assistant.decision_assistant`，包含：候选风格卡片、给新手的引导问题、以及用户选定风格后的下一步命令模板。
- 可直接复用对话模板：`references/cc-decision-conversation-template.md`。
- 若要做“人工审核升级”闭环：先运行 `propose_upgrade.py` 生成候选，再用 `review_upgrade_candidate.py` 校验后发 PR。

## 3) 回归门禁

```bash
python3 scripts/validate_taxonomy.py --format json --max-unused-style-tags 0 --fail-on-warning
python3 scripts/validate_output_contract_sync.py --format text --fail-on-warning
bash scripts/ci_regression_gate.sh --baseline references/benchmark-baseline.json --snapshot-out tmp/benchmark-ci-latest.json
```

## 4) 发布到 npm（让所有人可用）

```bash
node bin/stylekit-skill.js doctor
npm pack --dry-run
npm login
npm whoami
npm publish --access public
```

发布后，任何人都可以通过 `npx @anxforever/stylekit-skill ...` 直接安装。

## 5) 正式上线清单

上线前请完整执行：`GO_LIVE_CHECKLIST.md`。

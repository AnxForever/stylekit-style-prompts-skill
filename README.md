# @anxforever/stylekit-style-prompts-skill

StyleKit 风格提示词 Skill（独立仓库版）。  
目标：把 StyleKit 的风格能力直接安装到 Codex / Claude 的 skills 目录中。

## 1) 一键安装（面向使用者）

### 安装到 Codex

```bash
npx @anxforever/stylekit-style-prompts-skill install --tool codex
```

### 安装到 Claude

```bash
npx @anxforever/stylekit-style-prompts-skill install --tool claude
```

### 自动检测本机工具并安装

```bash
npx @anxforever/stylekit-style-prompts-skill install --tool auto
```

### 覆盖安装（已存在时）

```bash
npx @anxforever/stylekit-style-prompts-skill install --tool codex --force
```

### 卸载

```bash
npx @anxforever/stylekit-style-prompts-skill uninstall --tool codex
npx @anxforever/stylekit-style-prompts-skill uninstall --tool claude
```

### 环境自检

```bash
npx @anxforever/stylekit-style-prompts-skill doctor
```

## 2) 本地开发验证（维护者）

```bash
node bin/stylekit-style-prompts-skill.js doctor
node bin/stylekit-style-prompts-skill.js install --tool codex --target /tmp/stylekit-skill-test --force
node bin/stylekit-style-prompts-skill.js uninstall --target /tmp/stylekit-skill-test
python3 scripts/audit_style_rule_conflicts.py --format text
python3 scripts/smoke_test.py
python3 scripts/run_pipeline.py --query "高端科技SaaS财务后台，玻璃质感，强调可读性" --stack nextjs --format json
python3 scripts/run_pipeline.py --workflow codegen --query "高端科技SaaS财务后台，玻璃质感，强调可读性" --stack nextjs --format json
```

说明：
- 默认是 `--workflow manual`（手册/知识库模式）：输出设计简报 + 手册化建议，不强制走 prompt QA。
- 若要生成并严格审查 prompt，请显式加 `--workflow codegen`。
- 在 manual 模式下，会额外输出 `manual_assistant.decision_assistant`，包含：候选风格卡片、给新手的引导问题、以及用户选定风格后的下一步命令模板。
- 可直接复用对话模板：`references/cc-decision-conversation-template.md`。

## 3) 回归门禁

```bash
bash scripts/ci_regression_gate.sh --baseline references/benchmark-baseline.json --snapshot-out tmp/benchmark-ci-latest.json
```

## 4) 发布到 npm（让所有人可用）

```bash
npm login
npm whoami
npm publish --access public
```

发布后，任何人都可以通过 `npx @anxforever/stylekit-style-prompts-skill ...` 直接安装。

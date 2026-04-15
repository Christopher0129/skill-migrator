# Migration Playbook

在以下情况按需读取本参考：

- analysis 报告出现 warning
- 源 skill 看起来有损坏、乱码或解析失败
- 工具映射存在冲突
- 状态迁移不确定
- validation 没有一次通过

## Review Checkpoints

### 1. Analysis Checkpoint

- 审查 `compatibility_report.md`
- 审查 `mapping.yaml`
- 确认入口文件选择是否合理
- 判断该走直接转换还是 phased migration

### 2. Conversion Checkpoint

- 检查目录结构是否完整
- Claude Code 检查 `references/original.md`
- Hermes 检查 `scripts/` 是否复制了实现脚本
- 有状态时检查 `state.yaml`

### 3. Validation Checkpoint

- 重新运行 `validate_skill.py --strict`
- 如果仍有 warning 或 error，保持 `partial` 或 `failed`
- 把剩余问题写清楚，不要伪装成已完成

## Detailed Scenarios

### Claude Code: Single Markdown With SLASH_COMMANDS

- 首选带 `SLASH_COMMANDS` 的 markdown
- 先分析，再转换，再验证
- 输出里应保留 `references/original.md`

### Hermes: Declared Tool Registry

- 先读 `config.toml`
- 只把声明过的 tool 或 `tools/` 目录中的脚本视为 tool
- 复制 Python 实现到 `scripts/`

### CloudCode: Unknown Tool Present

- 已知工具可以直接映射
- 未知工具应保留为 `manual review`
- 高风险时优先 phased migration

## Detailed Diagnostics

### Display Problem vs Parse Problem

- 先确认是显示乱码还是文件真的损坏
- 在 PowerShell 中优先检查：

```bash
Get-Content -Raw -Encoding UTF8 source_file
```

- 如果文件能正常读取，但脚本仍报解析错误，按“解析失败”处理

### Mapping Conflict

- 检查 `mapping.yaml`
- 判断功能差异是否影响核心流程
- 若差异可接受，记录限制
- 若差异不可接受，保留 `manual review` 或补 wrapper

### State Migration Uncertainty

- 保留关键字段
- 优先转换到 `state.yaml`
- 如果字段含义不清，保留 warning
- 无法确认时明确要求人工审查

### Validation Did Not Pass

- 先修正文档或输出结构中的明显问题
- 再次运行 `validate_skill.py --strict`
- 如果仍不通过，输出 `partial` 或 `failed`

## Repair Choices

当前仓库支持的是保守修正，不是通用自愈流程。推荐选择如下：

- 文档问题：直接修正文案，再重新验证
- 映射冲突：记录限制、补 wrapper、或改为 manual review
- 状态不清：保留字段、保留 warning、必要时让用户重建状态
- 高风险迁移：改用 phased migration

## Reminder

这份参考的目标是帮助 OpenClaw 在复杂场景下做出更稳的迁移决策，而不是让它承诺仓库里并不存在的自动补救能力。

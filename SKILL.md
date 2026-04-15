---
name: skill-migrator
description: |
  让 OpenClaw 学会把 Claude Code 和 Hermes skill 转成 OpenClaw skill。
  Use when: the user asks to convert a Claude Code skill or Hermes skill into an OpenClaw skill.
  Use when: OpenClaw should analyze first, then convert or phased-migrate the source skill into OpenClaw format.
  Handles: source detection, analysis, tool mapping, state migration, validation, and manual review notes.
---

# Skill Migrator

> 让 OpenClaw 学会把 Claude Code 和 Hermes skill 转成 OpenClaw skill。

## Goal

读取现有的 Claude Code 或 Hermes skill，并产出一份可继续使用的 OpenClaw skill 骨架。目标结果至少包括：

- 合法的 `SKILL.md`
- 需要时生成 `scripts/`
- 需要时生成 `references/`
- 有状态时生成 `state.yaml`
- 在分阶段迁移时生成 `MIGRATION_REPORT.md`

重点不是解释迁移思路，而是让 OpenClaw 真正把结果落成可验证的文件结构。

## Scope

- 第一优先支持：Claude Code `.md`
- 第一优先支持：Hermes `config.toml + Python`
- 扩展支持：CloudCode `.cs + YAML`
- 不适用：从零创建全新 OpenClaw skill
- 不适用：简单修改已有 OpenClaw skill

## Trigger Hints

遇到下面这类请求时，应优先使用本 skill：

- "把这个 Claude Code skill 转成 OpenClaw skill"
- "帮我迁移这个 Hermes skill"
- "分析这个 skill 能不能迁移到 OpenClaw"
- "先分析，再分阶段迁移成 OpenClaw skill"

## Quick Decision Tree

```text
收到迁移请求
    ↓
先运行 analyze_skill.py
    ↓
结果是否低风险且映射清晰？
    ├─ 是 -> 直接使用 convert_skill.py
    ↓ 否
是否存在未知工具、复杂状态或多入口？
    ├─ 是 -> 使用 migrate_skill.py --phased
    ↓ 否
继续直接转换
    ↓
运行 validate_skill.py --strict
    ↓
若仍有 warning / error -> 输出 partial 或 failed，并列出人工审查项
```

## Workflow

1. 先识别源系统。
   - Claude Code：优先选择带 `SLASH_COMMANDS` 的 markdown
   - Hermes：读取 `config.toml`、声明的 tools、以及实现脚本
   - CloudCode：读取 `.cs`、`@tool`、状态和依赖
2. 先分析，再决定是否直接转换。

```bash
python scripts/analyze_skill.py \
  --source /path/to/skill \
  --system claude-code \
  --output ./analysis/
```

3. 审查 `analysis.json`、`compatibility_report.md`、`mapping.yaml`。
4. 根据复杂度选择迁移模式。
   - 简单场景：

```bash
python scripts/convert_skill.py \
  --analysis ./analysis/analysis.json \
  --output ./converted/
```

   - 复杂场景：

```bash
python scripts/migrate_skill.py \
  --analysis ./analysis/analysis.json \
  --output ./converted/ \
  --phased
```

5. 严格验证结果。

```bash
python scripts/validate_skill.py \
  --skill ./converted/my-skill/ \
  --strict
```

6. 向用户明确说明：
   - 哪些内容已迁移
   - 哪些工具或状态仍需人工处理
   - 当前结果是 `completed`、`partial` 还是 `failed`

## Review Checkpoints

### Checkpoint 1: After Analysis

- 必须审查 `compatibility_report.md`、`mapping.yaml`、以及 analysis warnings
- 必须确认入口文件选择是否合理
- 必须判断应该直接转换，还是改走 phased migration

### Checkpoint 2: After Conversion

- 必须确认输出目录结构完整
- Claude Code 必须确认 `references/original.md` 已保留
- Hermes 必须确认脚本已复制到 `scripts/`
- 有状态时必须确认 `state.yaml` 是否已经生成

### Checkpoint 3: After Validation

- 如果 `validate_skill.py --strict` 仍有 warning 或 error，不要宣称迁移完成
- 结果必须落到 `completed`、`partial` 或 `failed`
- 需要人工处理的项必须明确列出

## Source-Specific Rules

### Claude Code -> OpenClaw

- 优先使用带 `SLASH_COMMANDS` 的 markdown
- 将 slash commands 转成 OpenClaw 能理解的使用说明
- 保留原始 markdown 到 `references/original.md`
- 如果有多个候选 markdown，明确记录选择了哪一个
- 如果没有 `SLASH_COMMANDS`，可以继续，但必须保留 warning

### Hermes -> OpenClaw

- 用 `config.toml` 提取 name、description、declared tools
- 把实现脚本复制到 `scripts/`
- 只把声明过的 tool 或 `tools/` 目录中的实现视为 tool
- 不要把普通 helper function 全部误判成 tool
- 如果发现状态文件，尽量转换为 `state.yaml`

### CloudCode -> OpenClaw

- 这是扩展支持，不是第一目标
- 提取 `.cs` 中的 `@tool`
- 对已知工具做自动映射
- 未知工具标记为 `manual review`
- 不要把未知工具伪装成已完成映射

### Common Mappings

```yaml
search_web: web_search
fetch_url: web_fetch
read_file: read
write_file: write
edit_file: edit
run_command: exec
search_memory: memory_search
get_memory: memory_get
```

## Boundary Conditions

如需更细的诊断步骤、修复选择和场景说明，按需读取 `references/migration-playbook.md`。

### If Analysis Shows High Risk

- 未知工具很多、状态复杂、或平台特有能力缺少等效时，优先使用 `migrate_skill.py --phased`
- 如果核心能力无法可靠映射，明确建议部分迁移或重写
- 只有在选项会显著改变结果时才暂停等待用户决策
- 如果可以安全继续，就保持 `partial` 并记录 warning，而不是假装完全成功

### If Source Files Look Corrupted

- 先确认是解析问题还是显示问题，不要先假设文件已经损坏
- 在 PowerShell 中优先这样检查：

```bash
Get-Content -Raw -Encoding UTF8 source_file
```

- 如果脚本仍然无法解析，记录问题并停留在 analysis 或 partial 阶段
- 不要承诺当前脚本并不存在的通用自愈或自动补救能力

### If Tool Mapping Conflicts

- 先查看 `mapping.yaml`
- 如果多个源工具映射到同一个 OpenClaw 工具，先评估功能差异是否影响核心流程
- 能接受差异时，明确记录限制
- 不能接受差异时，输出 `manual review`，必要时再补 wrapper
- 不要为了“看起来完成”而伪造等价映射

### If State Migration Is Unclear

- 当前实现会尽量把检测到的状态文件转换为 `state.yaml`
- 如果结构复杂、字段含义不清、或存在潜在丢失风险，保留 warning
- 不要静默丢弃关键字段
- 无法确认时，告诉用户需要人工审查或重建状态

### If Validation Finds Issues

- 先修正文档或生成结果中明显、本地可修的错误
- 然后重新运行 `validate_skill.py`
- 如果仍有 warning 或 error，不要宣称迁移完成
- 根据结果返回 `partial` 或 `failed`

### If User Says "Stop" or "Rollback"

- 立即停止当前迁移
- 保留已经生成的分析或输出目录
- 简要说明已完成、部分完成、以及未完成的部分
- 不要承诺当前仓库没有实现的备份、归档或自动回滚流程

## Minimal Examples

### Example 1: Claude Code, Low Risk

- 用户请求：把一个带 `SLASH_COMMANDS` 的 Claude Code skill 转成 OpenClaw
- 处理方式：先分析，再直接转换，最后严格验证
- 预期结果：`SKILL.md` 保留 slash command 说明，`references/original.md` 存在

### Example 2: Hermes, Declared Tools Only

- 用户请求：迁移一个 `config.toml + Python` 的 Hermes skill
- 处理方式：从 `config.toml` 取 name、description、declared tools，再复制实现脚本
- 预期结果：只有声明过的 tools 被视为 tool，helper function 不会被误判

### Example 3: CloudCode, Partial Result

- 用户请求：迁移一个含未知工具的 CloudCode skill
- 处理方式：优先使用 phased migration，保留 manual review 项
- 预期结果：生成 `MIGRATION_REPORT.md`，最终状态可能是 `partial`

## Manual Review Triggers

遇到以下情况时，不要直接宣称“迁移完成”，而是输出人工审查项：

- 未知工具或无法安全映射的工具
- 复杂状态结构
- 自定义 memory 或 scheduling 行为
- 多个候选入口文件
- validation 出现 warning 或 error

## Output Requirements

转换结果至少要满足这些要求：

- `SKILL.md` frontmatter 合法
- `description` 包含明确的 `Use when`
- skill 名称符合 OpenClaw 约定
- Python 脚本无语法错误
- 有状态时，`stateful: true` 与状态说明保持一致
- 不把部分成功伪装成完全成功

## References

- 详细映射参考：`references/cross-system-mappings.md`
- 详细诊断与场景参考：`references/migration-playbook.md`
- 人类说明文档：`README.md`

## Remember

迁移的目标不是形式上生成文件，而是让 OpenClaw 最终得到一份能继续使用、能继续修改、并且风险清楚可见的 skill。

*v4.5 - 保持真实边界，补回决策树、检查点与最小示例。*

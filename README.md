# Skill Migrator

[English](#english) | [简体中文](#简体中文)

---

<a id="english"></a>

## English

This repository documents a skill for OpenClaw to learn.

Its core purpose is not to be a generic "migrate any skill from any platform" toolkit. The primary goal is:

- Teach OpenClaw how to convert **Claude Code skills** into **OpenClaw skills**
- Teach OpenClaw how to convert **Hermes skills** into **OpenClaw skills**

CloudCode is still kept as extended support, but it is not the first priority of this skill.

### What OpenClaw Should Do After Learning This Skill

When a user provides a Claude Code or Hermes skill and asks to migrate it into OpenClaw, OpenClaw should:

1. Detect whether the source skill is Claude Code or Hermes.
2. Analyze the source structure, tools, state, dependencies, and migration risks.
3. Produce an OpenClaw-compatible output directory.
4. Generate valid `SKILL.md`, `scripts/`, `references/`, and `state.yaml` when needed.
5. Validate the migrated result.
6. Clearly explain what was migrated automatically and what still needs manual review.

In other words, this skill should help OpenClaw produce a usable OpenClaw skill scaffold, not just explain migration ideas.

### Expected Usage

After OpenClaw learns this skill, it should prefer using it for requests like:

- "Convert this Claude Code skill into an OpenClaw skill"
- "Migrate this Hermes skill"
- "Analyze whether this skill can be migrated to OpenClaw"
- "Analyze first, then do a phased migration into OpenClaw"

Recommended strategy:

- Simple case: analyze and convert directly
- Complex case: prefer phased migration
- High-risk case: preserve manual review points instead of pretending the migration is fully automatic

### Improvement Note

v4.5 - Keep boundaries honest, add back the decision tree, checkpoints, and minimal examples.

### What Improved in v4.5

- Restored a short decision tree in `SKILL.md`
- Restored explicit review checkpoints
- Restored minimal scenario examples
- Moved detailed diagnostics and repair choices into `references/migration-playbook.md`
- Kept unsupported promises out of the agent-facing workflow

### Current Support

#### First-class support

- Claude Code `.md` skills
- Hermes `TOML + Python` skills

#### Extended support

- CloudCode `.cs + YAML`

#### Not supported yet

- OpenAI Assistants JSON skill definitions
- Closed skill bundles that require online APIs to reconstruct context

### Repository Layout

```text
skill-migrator/
├─ LICENSE
├─ SKILL.md
├─ README.md
├─ references/
│  └─ cross-system-mappings.md
│  └─ migration-playbook.md
├─ scripts/
│  ├─ analyze_skill.py
│  ├─ convert_skill.py
│  ├─ migrate_skill.py
│  └─ validate_skill.py
└─ tests/
   └─ test_skill_migrator.py
```

### Script Overview

- `scripts/analyze_skill.py`
  Analyze a source skill and emit `analysis.json`, `compatibility_report.md`, and `mapping.yaml`
- `scripts/convert_skill.py`
  One-shot conversion for simpler cases
- `scripts/migrate_skill.py`
  Phased migration for more complex cases
- `scripts/validate_skill.py`
  Validate whether the generated OpenClaw skill matches this repo's current rules

### Recommended Workflow

#### 1. Analyze only

```bash
python scripts/analyze_skill.py \
  --source /path/to/source-skill \
  --system claude-code \
  --output ./analysis/
```

#### 2. Direct conversion

```bash
python scripts/convert_skill.py \
  --analysis ./analysis/analysis.json \
  --output ./converted/
```

#### 3. Phased migration

```bash
python scripts/migrate_skill.py \
  --analysis ./analysis/analysis.json \
  --output ./converted/ \
  --phased
```

#### 4. Strict validation

```bash
python scripts/validate_skill.py \
  --skill ./converted/my-skill/ \
  --strict
```

For detailed checkpoints, scenario examples, and high-risk troubleshooting, see `references/migration-playbook.md`.

### Design Principles

- Analyze before converting
- Always emit a valid `SKILL.md`
- Never present partial success as full success
- Claude Code and Hermes are the first priority
- Preserve manual review points instead of assuming every tool can be auto-mapped
- Work reliably on Windows too, including console encoding safety

### Regression Tests

Current coverage includes:

- Claude Code path selection using `SLASH_COMMANDS`
- Hermes tool detection based on declared tools
- Conversion and validation for CloudCode / Hermes / Claude Code
- `partial` status reporting for phased migration
- `--analysis` migration entrypoint
- Documentation regression checks

Run:

```bash
python -m unittest discover -s tests -v
```

### Current Limitations

- Claude Code and Hermes migration is still "usable with manual review", not guaranteed to be lossless
- Custom tool semantics may still require manual wrappers
- State and memory migration remains conservative by design
- Some extended CloudCode notes remain because the codebase still supports part of that workflow

### License

This project is released under the MIT License. See `LICENSE`.

[Back to language switch](#skill-migrator)

---

<a id="简体中文"></a>

## 简体中文

这是一个给 OpenClaw 学习的 skill 说明仓库。

它的核心目标不是做泛化的"任意平台 skill 迁移器"，而是：

- 让 OpenClaw 在学习这个 skill 后，能够把 **Claude Code skill** 转成 **OpenClaw skill**
- 让 OpenClaw 在学习这个 skill 后，能够把 **Hermes skill** 转成 **OpenClaw skill**

CloudCode 目前仍然保留为扩展支持，但不是这个 skill 的第一目标。

### 这个 Skill 应该让 OpenClaw 做什么

当用户给出一个 Claude Code 或 Hermes skill，并要求迁移到 OpenClaw 时，OpenClaw 应该：

1. 识别源 skill 属于 Claude Code 还是 Hermes。
2. 分析源 skill 的结构、工具、状态文件、依赖和潜在风险。
3. 生成符合 OpenClaw 约定的输出目录。
4. 在需要时生成合法的 `SKILL.md`、`scripts/`、`references/`、`state.yaml`。
5. 对结果做基础校验。
6. 明确告诉用户哪些部分已经自动完成，哪些部分还需要人工审查。

换句话说，这个 skill 的目标是让 OpenClaw 不只是"解释如何迁移"，而是能产出一份可继续使用、可继续调整的 OpenClaw skill 骨架。

### 学习后的预期使用场景

学会这个 skill 后，OpenClaw 在遇到下面这类请求时，应该优先使用它：

- "把这个 Claude Code skill 转成 OpenClaw skill"
- "帮我迁移这个 Hermes skill"
- "分析这个 skill 能不能迁移到 OpenClaw"
- "先分析，再分阶段迁移成 OpenClaw skill"

推荐策略：

- 简单场景：直接分析并转换
- 复杂场景：优先走 phased migration
- 高风险场景：保留人工审查点，不要伪装成"完全自动迁移成功"

### 改进标注

v4.5 - 保持真实边界，补回决策树、检查点与最小示例。

### v4.5 改进点

- 在 `SKILL.md` 中补回短决策树
- 补回明确的审查检查点
- 补回最小场景示例
- 把更细的诊断步骤和修复选择下沉到 `references/migration-playbook.md`
- 继续避免在 agent 文档里承诺当前实现并不存在的功能

### 当前支持范围

#### 第一优先支持

- Claude Code `.md` skill
- Hermes `TOML + Python` skill

#### 扩展支持

- CloudCode `.cs + YAML`

#### 暂不支持

- OpenAI Assistants JSON skill 定义
- 需要在线 API 还原上下文的闭源 skill 包

### 仓库结构

```text
skill-migrator/
├─ LICENSE
├─ SKILL.md
├─ README.md
├─ references/
│  └─ cross-system-mappings.md
│  └─ migration-playbook.md
├─ scripts/
│  ├─ analyze_skill.py
│  ├─ convert_skill.py
│  ├─ migrate_skill.py
│  └─ validate_skill.py
└─ tests/
   └─ test_skill_migrator.py
```

### 脚本说明

- `scripts/analyze_skill.py`
  用来分析源 skill，输出 `analysis.json`、`compatibility_report.md`、`mapping.yaml`
- `scripts/convert_skill.py`
  用来做一次性转换，适合简单场景
- `scripts/migrate_skill.py`
  用来做分阶段迁移，适合复杂场景
- `scripts/validate_skill.py`
  用来验证转换结果是否符合当前仓库定义的 OpenClaw skill 约束

### 推荐工作流

#### 1. 仅分析

```bash
python scripts/analyze_skill.py \
  --source /path/to/source-skill \
  --system claude-code \
  --output ./analysis/
```

#### 2. 直接转换

```bash
python scripts/convert_skill.py \
  --analysis ./analysis/analysis.json \
  --output ./converted/
```

#### 3. 分阶段迁移

```bash
python scripts/migrate_skill.py \
  --analysis ./analysis/analysis.json \
  --output ./converted/ \
  --phased
```

#### 4. 严格校验

```bash
python scripts/validate_skill.py \
  --skill ./converted/my-skill/ \
  --strict
```

如需更细的检查点、场景示例和高风险问题处理，请查看 `references/migration-playbook.md`。

### 当前设计原则

- 先分析，再转换
- 输出必须是合法的 `SKILL.md`
- 不把部分成功伪装成完全成功
- Claude Code 和 Hermes 是第一优先目标
- 保留人工审查点，而不是假设所有工具都能自动一一映射
- 在 Windows 环境下也要能正常运行，包括控制台编码兼容

### 已有回归测试

当前测试覆盖了：

- Claude Code 路径优先选择带 `SLASH_COMMANDS` 的 markdown
- Hermes 只识别声明过的 tool
- CloudCode / Hermes / Claude Code 的转换和校验
- phased migration 的 `partial` 状态
- `--analysis` 入口
- 文档约束回归

运行方式：

```bash
python -m unittest discover -s tests -v
```

### 当前限制

- Claude Code 和 Hermes 目前仍是"基础可迁移 + 人工审查"级别，不保证完全无损
- 自定义工具语义仍然可能需要手工 wrapper
- 状态系统和 memory 系统的迁移仍然以"保守落地"为主
- 文档里仍然保留了一些 CloudCode 扩展说明，因为代码确实支持一部分这类迁移

### 许可证

本项目采用 MIT License，详见 `LICENSE`。

[返回语言切换](#skill-migrator)

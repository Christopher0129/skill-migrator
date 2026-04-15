# Cross-System Skill Migration Reference

高频映射速查表。

This reference stays focused on one goal:

- Teach OpenClaw how to convert **Claude Code skills** into **OpenClaw skills**
- Teach OpenClaw how to convert **Hermes skills** into **OpenClaw skills**

CloudCode remains extended support, not the first priority.

## Fast Lookup

| Source | First-Class Support | Primary Input | Primary Output |
|--------|---------------------|---------------|----------------|
| Claude Code | Yes | `.md` with `SLASH_COMMANDS` | `SKILL.md` + `references/original.md` |
| Hermes | Yes | `config.toml` + Python | `SKILL.md` + `scripts/` |
| CloudCode | Partial | `.cs` + config/state files | `SKILL.md` + optional `scripts/` / `state.yaml` |

## OpenClaw Target Shape

无论源系统是什么，转换结果都尽量落成下面这种结构：

```text
my-skill/
├─ SKILL.md
├─ scripts/
├─ references/
└─ state.yaml
```

说明：

- `SKILL.md` 是主入口
- `scripts/` 放复制或生成的实现脚本
- `references/` 放原始材料或依赖说明
- `state.yaml` 只在需要状态时生成

## Claude Code -> OpenClaw

### Input Signals

- 主文件通常是 markdown
- 优先选择带 `SLASH_COMMANDS` 的 markdown
- 如果有多个 markdown，优先选择定义命令的那个

### Conversion Rules

- 源 markdown 的标题可作为 skill 名称或描述来源
- `SLASH_COMMANDS` 要转成 OpenClaw 可读的 usage 或 workflow
- 原文保留到 `references/original.md`
- 如果没找到 `SLASH_COMMANDS`，允许继续，但必须保留 warning

## Hermes -> OpenClaw

### Input Signals

- `config.toml` 是主要入口
- `name`、`description`、`[tools].enabled` 是高价值信息
- Python 实现通常直接复制到 `scripts/`

### Conversion Rules

- skill 名称优先取自 `config.toml` 的 `name`
- description 优先取自 `config.toml` 的 `description`
- 只把声明过的 tool 或 `tools/` 目录中的脚本视为 tool
- 不要把普通 `def` 全部误判成 tool
- 如果发现状态文件，尽量转换成 `state.yaml`

## High-Frequency Tool Mappings

这些映射最常用，优先查这里：

| Source Tool | OpenClaw |
|-------------|----------|
| `search_web` | `web_search` |
| `fetch_url` | `web_fetch` |
| `read_file` | `read` |
| `write_file` | `write` |
| `edit_file` | `edit` |
| `run_command` | `exec` |
| `search_memory` | `memory_search` |
| `get_memory` | `memory_get` |

如果没有明确映射：

- 标记为 `manual review`
- 不要伪造等价工具
- 需要时补 wrapper

## State Mapping

### Preferred OpenClaw Form

```yaml
migrated_from: /path/to/source/state
original_format: json
counter: 42
```

### Rules

- JSON 或 YAML 状态尽量转成 YAML
- 有状态时，`SKILL.md` 中要保持 `stateful: true`
- 如果结构复杂，宁可保留 warning，也不要静默丢字段

## Dependency Mapping

- Python 依赖优先写进 `references/dependencies.md`
- 系统依赖同样放进 `references/`
- 不要把依赖硬塞进 frontmatter

## CloudCode Notes

CloudCode 不是第一优先目标，但当前实现仍然支持基础迁移：

- 从 `.cs` 中提取 `@tool`
- 读取 `requirements.txt`
- 读取 `state.*`
- 对已知工具做自动映射
- 未知工具输出为 `manual review`

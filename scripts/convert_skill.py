#!/usr/bin/env python3
"""
Convert external system skills to OpenClaw format.

Usage:
    python3 convert_skill.py --source /path/to/skill --system cloudcode --output ./converted/
    python3 convert_skill.py --analysis ./analysis.json --output ./converted/
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    yaml = None


TOOL_MAP = {
    "search_web": "web_search",
    "fetch_url": "web_fetch",
    "read_file": "read",
    "write_file": "write",
    "edit_file": "edit",
    "run_command": "exec",
    "search_memory": "memory_search",
    "get_memory": "memory_get",
}


def read_text(path: Path) -> str:
    """Read text safely from disk."""
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, content: str) -> None:
    """Write UTF-8 text with stable newlines."""
    path.write_text(content, encoding="utf-8", newline="\n")


def safe_print(message: str = "") -> None:
    """Print without crashing on narrow console encodings."""
    encoding = sys.stdout.encoding or "utf-8"
    text = str(message).encode(encoding, errors="replace").decode(encoding, errors="replace")
    print(text)


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def _simple_yaml_lines(value: Any, indent: int = 0) -> List[str]:
    prefix = " " * indent

    if isinstance(value, dict):
        lines: List[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(_simple_yaml_lines(item, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {_yaml_scalar(item)}")
        return lines

    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(_simple_yaml_lines(item, indent + 2))
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
        return lines

    return [f"{prefix}{_yaml_scalar(value)}"]


def dump_yaml(data: Any) -> str:
    """Serialize YAML even when PyYAML is unavailable."""
    if HAS_YAML:
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    return "\n".join(_simple_yaml_lines(data)) + "\n"


def write_yaml(path: Path, data: Any) -> None:
    write_text(path, dump_yaml(data))


def unique(items: List[str]) -> List[str]:
    return list(dict.fromkeys(items))


def get_skill_name(source_path: Path, analysis: Dict[str, Any]) -> str:
    """Pick the output skill name."""
    skill_files = analysis.get("skill_files", [])
    if skill_files and skill_files[0].get("name"):
        return skill_files[0]["name"]

    config_files = analysis.get("config_files", [])
    if config_files and config_files[0].get("name"):
        return config_files[0]["name"]

    return source_path.name


def default_description(system_name: str, skill_name: str) -> str:
    return (
        f"Migrated from {system_name} skill '{skill_name}'. "
        "Use when: you need the same workflow this source skill handled in the original system."
    )


def build_frontmatter(skill_name: str, description: str, stateful: bool = False) -> Dict[str, Any]:
    frontmatter: Dict[str, Any] = {
        "name": skill_name,
        "description": description,
    }
    if stateful:
        frontmatter["stateful"] = True
    return frontmatter


def render_skill_markdown(frontmatter: Dict[str, Any], body_lines: List[str]) -> str:
    body = "\n".join(body_lines).rstrip()
    return f"---\n{dump_yaml(frontmatter).rstrip()}\n---\n\n{body}\n"


def mapped_and_unmapped_tools(tools: List[str]) -> tuple[List[str], List[str]]:
    mapped = []
    unmapped = []
    for tool in unique(tools):
        target = TOOL_MAP.get(tool)
        if target:
            mapped.append(f"- Use `{target}` for `{tool}`.")
        else:
            unmapped.append(f"- `{tool}` requires manual review or a custom wrapper.")
    return mapped, unmapped


def ensure_executable(path: Path) -> None:
    try:
        path.chmod(0o755)
    except OSError:
        pass


def write_script(path: Path, content: str) -> None:
    """Write a script and normalize the Python shebang."""
    normalized = content
    if path.suffix == ".py" and not normalized.startswith("#!/"):
        normalized = "#!/usr/bin/env python3\n" + normalized.lstrip("\n")
    write_text(path, normalized)
    ensure_executable(path)


def select_primary_claude_file(analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Choose the primary Claude Code markdown file for conversion."""
    skill_files = analysis.get("skill_files", [])
    if not skill_files:
        return None

    slash_command_files = [item for item in skill_files if item.get("has_slash_commands")]
    if slash_command_files:
        return slash_command_files[0]
    return skill_files[0]


def extract_claude_slash_commands(content: str) -> List[str]:
    """Pull slash commands out of a Claude Code markdown file."""
    commands = []
    for command, description in re.findall(r"^\s*-\s*(/\S+):\s*(.+)$", content, re.MULTILINE):
        commands.append(f"- `{command}`: {description.strip()}")
    return commands


def convert_state_file(state_path: Path) -> Dict[str, Any]:
    """Convert a state file to OpenClaw format."""
    content = read_text(state_path)
    metadata = {
        "migrated_from": str(state_path),
        "original_format": "text",
    }

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = None
    else:
        metadata["original_format"] = "json"
        if isinstance(data, dict):
            return {**metadata, **data}
        metadata["data"] = data
        return metadata

    if HAS_YAML:
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError:
            data = None
        else:
            metadata["original_format"] = "yaml"
            if isinstance(data, dict):
                return {**metadata, **data}
            metadata["data"] = data
            return metadata

    metadata["content"] = content
    return metadata


def generate_cloudcode_skill_md(skill_name: str, analysis: Dict[str, Any]) -> str:
    """Generate SKILL.md content for CloudCode conversion."""
    frontmatter = build_frontmatter(
        skill_name,
        default_description("CloudCode", skill_name),
        stateful=bool(analysis.get("state_files")),
    )
    mapped_tools, unmapped_tools = mapped_and_unmapped_tools(analysis.get("tools", []))

    lines = [
        f"# {skill_name}",
        "",
        "Migrated from CloudCode.",
        "",
        "## Tools",
        "",
    ]

    if mapped_tools:
        lines.extend(mapped_tools)
    else:
        lines.append("- No known CloudCode tool mappings were detected.")

    if unmapped_tools:
        lines.extend([
            "",
            "## Manual Review",
            "",
        ])
        lines.extend(unmapped_tools)

    if analysis.get("state_files"):
        lines.extend([
            "",
            "## State",
            "",
            f"State file: `~/.openclaw/skill-state/{skill_name}/state.yaml`",
        ])

    lines.extend([
        "",
        "## Dependencies",
        "",
    ])

    if analysis.get("dependencies"):
        lines.append("See [references/dependencies.md](references/dependencies.md).")
    else:
        lines.append("No external dependencies were detected.")

    return render_skill_markdown(frontmatter, lines)


def generate_hermes_skill_md(skill_name: str, analysis: Dict[str, Any]) -> str:
    """Generate SKILL.md content for Hermes conversion."""
    config_files = analysis.get("config_files", [])
    description = default_description("Hermes", skill_name)
    if config_files and config_files[0].get("description"):
        description = (
            f"{config_files[0]['description']}. "
            "Use when: you want the migrated Hermes workflow in OpenClaw."
        )

    frontmatter = build_frontmatter(
        skill_name,
        description,
        stateful=bool(analysis.get("state_files")),
    )

    lines = [
        f"# {skill_name}",
        "",
        "Migrated from Hermes Agent.",
        "",
        "## Usage",
        "",
        "See `scripts/` for the copied implementation files.",
    ]

    if analysis.get("tools"):
        lines.extend([
            "",
            "## Registered Tools",
            "",
        ])
        lines.extend([f"- `{tool}`" for tool in unique(analysis["tools"])])

    if analysis.get("state_files"):
        lines.extend([
            "",
            "## State",
            "",
            f"State file: `~/.openclaw/skill-state/{skill_name}/state.yaml`",
        ])

    if analysis.get("warnings"):
        lines.extend([
            "",
            "## Notes",
            "",
        ])
        lines.extend([f"- {warning}" for warning in analysis["warnings"]])

    return render_skill_markdown(frontmatter, lines)


def generate_claude_code_skill_md(skill_name: str, original_content: str, analysis: Dict[str, Any]) -> str:
    """Generate SKILL.md content for Claude Code conversion."""
    heading_match = re.search(r"^#\s+(.+)$", original_content, re.MULTILINE)
    if heading_match:
        description = (
            f"{heading_match.group(1)}. "
            "Use when: you want the migrated Claude Code workflow in OpenClaw."
        )
    else:
        description = default_description("Claude Code", skill_name)

    frontmatter = build_frontmatter(skill_name, description)
    slash_commands = extract_claude_slash_commands(original_content)

    lines = [
        f"# {skill_name}",
        "",
        "Migrated from Claude Code.",
        "",
    ]

    if slash_commands:
        lines.extend([
            "## Slash Commands",
            "",
        ])
        lines.extend(slash_commands)
        lines.append("")

    lines.extend([
        "## Source Reference",
        "",
        "Original markdown preserved in [references/original.md](references/original.md).",
    ])

    if analysis.get("warnings"):
        lines.extend([
            "",
            "## Notes",
            "",
        ])
        lines.extend([f"- {warning}" for warning in analysis["warnings"]])

    return render_skill_markdown(frontmatter, lines)


def generate_tool_wrapper(tool_name: str) -> Optional[str]:
    """Generate a wrapper script for a mapped CloudCode tool."""
    tool_templates = {
        "search_web": '''#!/usr/bin/env python3
"""Wrapper for the OpenClaw web_search tool."""
import sys


def main() -> int:
    try:
        from openclaw import web_search
    except Exception as exc:
        print(f"Error: unable to import openclaw.web_search: {exc}", file=sys.stderr)
        return 1

    query = sys.argv[1] if len(sys.argv) > 1 else input("Query: ")
    try:
        result = web_search(query=query)
    except Exception as exc:
        print(f"Error: web_search failed: {exc}", file=sys.stderr)
        return 1

    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''',
        "read_file": '''#!/usr/bin/env python3
"""Wrapper for the OpenClaw read tool."""
import sys


def main() -> int:
    try:
        from openclaw import read
    except Exception as exc:
        print(f"Error: unable to import openclaw.read: {exc}", file=sys.stderr)
        return 1

    path = sys.argv[1] if len(sys.argv) > 1 else input("Path: ")
    try:
        result = read(path=path)
    except Exception as exc:
        print(f"Error: read failed: {exc}", file=sys.stderr)
        return 1

    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''',
    }
    return tool_templates.get(tool_name)


def convert_cloudcode_skill(source_path: Path, analysis: Dict[str, Any], output_path: Path) -> Path:
    """Convert a CloudCode skill to OpenClaw format."""
    skill_name = get_skill_name(source_path, analysis)
    skill_output = output_path / skill_name
    skill_output.mkdir(parents=True, exist_ok=True)

    write_text(skill_output / "SKILL.md", generate_cloudcode_skill_md(skill_name, analysis))

    if analysis.get("tools"):
        scripts_dir = skill_output / "scripts"
        scripts_dir.mkdir(exist_ok=True)
        for tool in unique(analysis["tools"]):
            wrapper = generate_tool_wrapper(tool)
            if wrapper:
                write_script(scripts_dir / f"{tool}.py", wrapper)

    references_dir = skill_output / "references"
    references_dir.mkdir(exist_ok=True)
    if analysis.get("dependencies"):
        deps_lines = ["# Dependencies", ""]
        deps_lines.extend([f"- {dep}" for dep in analysis["dependencies"]])
        deps_lines.extend(
            [
                "",
                "## Installation",
                "",
                "```bash",
                "pip install " + " ".join(analysis["dependencies"]),
                "```",
            ]
        )
        write_text(references_dir / "dependencies.md", "\n".join(deps_lines) + "\n")

    for state_file in analysis.get("state_files", []):
        state_path = source_path / state_file
        if state_path.exists():
            write_yaml(skill_output / "state.yaml", convert_state_file(state_path))
            break

    return skill_output


def convert_hermes_skill(source_path: Path, analysis: Dict[str, Any], output_path: Path) -> Path:
    """Convert a Hermes skill to OpenClaw format."""
    skill_name = get_skill_name(source_path, analysis)
    skill_output = output_path / skill_name
    skill_output.mkdir(parents=True, exist_ok=True)

    write_text(skill_output / "SKILL.md", generate_hermes_skill_md(skill_name, analysis))

    py_files = list(source_path.rglob("*.py"))
    if py_files:
        scripts_dir = skill_output / "scripts"
        scripts_dir.mkdir(exist_ok=True)
        for py_file in py_files:
            target = scripts_dir / py_file.name
            write_script(target, read_text(py_file))

    for state_file in analysis.get("state_files", []):
        state_path = source_path / state_file
        if state_path.exists():
            write_yaml(skill_output / "state.yaml", convert_state_file(state_path))
            break

    return skill_output


def convert_claude_code_skill(source_path: Path, analysis: Dict[str, Any], output_path: Path) -> Path:
    """Convert a Claude Code skill to OpenClaw format."""
    primary_skill = select_primary_claude_file(analysis)
    skill_name = primary_skill["name"] if primary_skill else get_skill_name(source_path, analysis)
    skill_output = output_path / skill_name
    skill_output.mkdir(parents=True, exist_ok=True)

    original_content = ""
    if primary_skill:
        source_md = source_path / primary_skill["path"]
        if source_md.exists():
            original_content = read_text(source_md)
            references_dir = skill_output / "references"
            references_dir.mkdir(exist_ok=True)
            write_text(references_dir / "original.md", original_content)

    write_text(skill_output / "SKILL.md", generate_claude_code_skill_md(skill_name, original_content, analysis))
    return skill_output


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert skills to OpenClaw format")
    parser.add_argument("--source", help="Path to source skill")
    parser.add_argument("--system", choices=["cloudcode", "hermes", "claude-code"], help="Source system type")
    parser.add_argument("--analysis", help="Path to analysis.json file")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--mapping", help="Path to mapping.yaml file")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    if args.analysis:
        with open(args.analysis, encoding="utf-8") as handle:
            analysis = json.load(handle)
        source_path = Path(analysis["source_path"])
    elif args.source and args.system:
        source_path = Path(args.source)
        sys.path.insert(0, str(Path(__file__).parent))
        from analyze_skill import (
            analyze_claude_code_skill,
            analyze_cloudcode_skill,
            analyze_hermes_skill,
        )

        if args.system == "cloudcode":
            analysis = analyze_cloudcode_skill(source_path)
        elif args.system == "hermes":
            analysis = analyze_hermes_skill(source_path)
        else:
            analysis = analyze_claude_code_skill(source_path)
    else:
        safe_print("Error: either --analysis or both --source and --system are required.")
        sys.exit(1)

    system = analysis["system"]
    if system == "cloudcode":
        skill_output = convert_cloudcode_skill(source_path, analysis, output_path)
    elif system == "hermes":
        skill_output = convert_hermes_skill(source_path, analysis, output_path)
    elif system == "claude-code":
        skill_output = convert_claude_code_skill(source_path, analysis, output_path)
    else:
        safe_print(f"Error: unknown system type: {system}")
        sys.exit(1)

    safe_print(f"[OK] Skill converted to: {skill_output}")
    safe_print("")
    safe_print("Next steps:")
    safe_print(f"  1. Review {skill_output / 'SKILL.md'}")
    safe_print(f"  2. Test the skill: openclaw skills test {skill_output}")
    safe_print(f"  3. Package: openclaw skills package {skill_output}")


if __name__ == "__main__":
    main()

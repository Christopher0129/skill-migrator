#!/usr/bin/env python3
"""
Analyze external system skills for migration to OpenClaw.

Usage:
    python3 analyze_skill.py --source /path/to/skill --system cloudcode
    python3 analyze_skill.py --source /path/to/skill --system hermes
    python3 analyze_skill.py --source /path/to/skill --system claude-code
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

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
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def safe_print(message: str = "") -> None:
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
    if HAS_YAML:
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    return "\n".join(_simple_yaml_lines(data)) + "\n"


def unique(items: List[str]) -> List[str]:
    return list(dict.fromkeys(items))


def base_analysis(system: str, source_path: Path) -> Dict[str, Any]:
    return {
        "system": system,
        "source_path": str(source_path),
        "skill_files": [],
        "config_files": [],
        "dependencies": [],
        "tools": [],
        "state_files": [],
        "cron_jobs": [],
        "warnings": [],
        "mappings": {},
    }


def analyze_cloudcode_skill(source_path: Path) -> Dict[str, Any]:
    """Analyze a CloudCode skill structure."""
    analysis = base_analysis("cloudcode", source_path)

    for cs_file in source_path.rglob("*.cs"):
        content = read_text(cs_file)
        skill_name = cs_file.stem

        tool_pattern = r"@tool(?:\([^)]*\))?\s*\n(?:\s*@.*\n)*\s*def\s+(\w+)\s*\([^)]*\)"
        tools = re.findall(tool_pattern, content)

        import_pattern = r"^import\s+(\S+)|^from\s+(\S+)"
        imports = re.findall(import_pattern, content, re.MULTILINE)

        cron_jobs = re.findall(r'cron\s*[:=]\s*["\']([^"\']+)["\']', content)
        analysis["cron_jobs"].extend(cron_jobs)

        analysis["skill_files"].append(
            {
                "name": skill_name,
                "path": str(cs_file.relative_to(source_path)),
                "tools": tools,
                "imports": [item[0] or item[1] for item in imports if item[0] or item[1]],
            }
        )
        analysis["tools"].extend(tools)

    for ext in ("*.yaml", "*.yml", "*.json"):
        for config_file in source_path.rglob(ext):
            analysis["config_files"].append(str(config_file.relative_to(source_path)))

    req_file = source_path / "requirements.txt"
    if req_file.exists():
        analysis["dependencies"] = [
            line.strip()
            for line in read_text(req_file).splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

    for state_file in source_path.rglob("state.*"):
        analysis["state_files"].append(str(state_file.relative_to(source_path)))

    if not analysis["skill_files"]:
        analysis["warnings"].append("No .cs skill files found under the source path.")

    analysis["tools"] = unique(analysis["tools"])
    analysis["mappings"] = generate_tool_mappings(analysis)
    return analysis


def extract_quoted_values(raw_list: str) -> List[str]:
    return re.findall(r'"([^"]+)"', raw_list)


def analyze_hermes_skill(source_path: Path) -> Dict[str, Any]:
    """Analyze a Hermes Agent skill structure."""
    analysis = base_analysis("hermes", source_path)
    declared_tools: List[str] = []

    for toml_file in source_path.rglob("*.toml"):
        content = read_text(toml_file)

        name_match = re.search(r'^name\s*=\s*"([^"]+)"', content, re.MULTILINE)
        desc_match = re.search(r'^description\s*=\s*"([^"]+)"', content, re.MULTILINE)
        enabled_match = re.search(r"enabled\s*=\s*\[([^\]]*)\]", content, re.DOTALL)
        dependencies_match = re.search(r"(?ms)^\[dependencies\]\s*(.*?)(^\[|\Z)", content)

        config = {
            "path": str(toml_file.relative_to(source_path)),
            "name": name_match.group(1) if name_match else None,
            "description": desc_match.group(1) if desc_match else None,
        }
        analysis["config_files"].append(config)

        if enabled_match:
            declared_tools.extend(extract_quoted_values(enabled_match.group(1)))

        if dependencies_match:
            analysis["dependencies"].extend(extract_quoted_values(dependencies_match.group(1)))

    tool_candidates: List[str] = []
    tools_dir_present = False
    for py_file in source_path.rglob("*.py"):
        if py_file.stem == "__init__":
            continue
        relative = py_file.relative_to(source_path)
        if "tools" in relative.parts:
            tools_dir_present = True
            tool_candidates.append(py_file.stem)
        elif declared_tools and py_file.stem in declared_tools:
            tool_candidates.append(py_file.stem)

    analysis["tools"] = unique(declared_tools + tool_candidates)

    for state_file in source_path.rglob("state.*"):
        analysis["state_files"].append(str(state_file.relative_to(source_path)))

    if not analysis["tools"] and list(source_path.rglob("*.py")):
        analysis["warnings"].append(
            "No explicit Hermes tool registry found; copied Python files will be treated as implementation files, not auto-mapped tools."
        )
    elif declared_tools and not tools_dir_present:
        analysis["warnings"].append(
            "Hermes tool names were declared in config, but no tools/ directory was found. Verify the script locations manually."
        )

    analysis["dependencies"] = unique(analysis["dependencies"])
    analysis["mappings"] = generate_tool_mappings(analysis)
    return analysis


def analyze_claude_code_skill(source_path: Path) -> Dict[str, Any]:
    """Analyze a Claude Code skill structure."""
    analysis = base_analysis("claude-code", source_path)
    markdown_files = []

    for md_file in source_path.rglob("*.md"):
        content = read_text(md_file)
        has_slash_commands = "SLASH_COMMANDS" in content
        slash_commands = re.findall(r"^\s*-\s*(/\S+):", content, re.MULTILINE)

        markdown_files.append(
            {
                "name": md_file.stem,
                "path": str(md_file.relative_to(source_path)),
                "has_slash_commands": has_slash_commands,
                "slash_commands": slash_commands,
            }
        )

    selected_files = [item for item in markdown_files if item["has_slash_commands"]]
    if not selected_files and markdown_files:
        selected_files = [markdown_files[0]]
        analysis["warnings"].append(
            f"No SLASH_COMMANDS section found; using '{markdown_files[0]['path']}' as the primary markdown file."
        )
    elif len(selected_files) > 1:
        analysis["warnings"].append(
            f"Multiple Claude Code markdown files were found; conversion will use '{selected_files[0]['path']}' first."
        )

    analysis["skill_files"] = selected_files
    if selected_files:
        analysis["tools"] = unique(
            [command for item in selected_files for command in item.get("slash_commands", [])]
        )
    else:
        analysis["warnings"].append("No markdown files were found under the source path.")

    analysis["mappings"] = generate_tool_mappings(analysis)
    return analysis


def generate_tool_mappings(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Generate generic mappings to OpenClaw."""
    mappings = {
        "file_mappings": [],
        "tool_mappings": [],
        "state_mappings": [],
        "dependency_mappings": [],
    }

    for skill in analysis.get("skill_files", []):
        mappings["file_mappings"].append(
            {
                "source": skill["path"],
                "target": "SKILL.md",
                "type": "skill_definition",
            }
        )

    for tool in analysis.get("tools", []):
        if tool in TOOL_MAP:
            mappings["tool_mappings"].append(
                {
                    "source": tool,
                    "target": TOOL_MAP[tool],
                    "status": "auto",
                }
            )
        else:
            mappings["tool_mappings"].append(
                {
                    "source": tool,
                    "target": None,
                    "status": "manual_review",
                }
            )

    for state in analysis.get("state_files", []):
        mappings["state_mappings"].append(
            {
                "source": state,
                "target": "~/.openclaw/skill-state/{name}/state.yaml",
                "format_conversion": "json_or_yaml_to_yaml",
            }
        )

    for dependency in analysis.get("dependencies", []):
        mappings["dependency_mappings"].append(
            {
                "source": dependency,
                "target": "Document in references/dependencies.md",
            }
        )

    return mappings


def generate_compatibility_report(analysis: Dict[str, Any]) -> str:
    """Generate a human-readable compatibility report."""
    mappings = analysis.get("mappings", {}).get("tool_mappings", [])
    auto_mapped = [item for item in mappings if item.get("status") == "auto"]
    manual_review = [item for item in mappings if item.get("status") == "manual_review"]

    lines = [
        "# Skill Migration Analysis Report",
        "",
        f"**Source System:** {analysis['system']}",
        f"**Source Path:** {analysis['source_path']}",
        "",
        "## Summary",
        "",
        f"- Skill files: {len(analysis.get('skill_files', []))}",
        f"- Config files: {len(analysis.get('config_files', []))}",
        f"- Tools found: {len(analysis.get('tools', []))}",
        f"- State files: {len(analysis.get('state_files', []))}",
        f"- Dependencies: {len(analysis.get('dependencies', []))}",
        "",
        "## Tool Mappings",
        "",
        f"**Auto-mapped ({len(auto_mapped)}):**",
    ]

    if auto_mapped:
        for item in auto_mapped:
            lines.append(f"- `{item['source']}` -> `{item['target']}`")
    else:
        lines.append("- None")

    lines.extend([
        "",
        f"**Needs Manual Review ({len(manual_review)}):**",
    ])
    if manual_review:
        for item in manual_review:
            lines.append(f"- `{item['source']}` -> ?")
    else:
        lines.append("- None")

    lines.extend([
        "",
        "## Warnings",
        "",
    ])

    if analysis.get("warnings"):
        lines.extend([f"- WARNING: {warning}" for warning in analysis["warnings"]])
    else:
        lines.append("No warnings.")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze skills for migration")
    parser.add_argument("--source", required=True, help="Path to source skill")
    parser.add_argument("--system", required=True, choices=["cloudcode", "hermes", "claude-code"], help="Source system type")
    parser.add_argument("--output", default=".", help="Output directory for analysis files")
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        safe_print(f"Error: source path does not exist: {source_path}")
        sys.exit(1)

    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    if args.system == "cloudcode":
        analysis = analyze_cloudcode_skill(source_path)
    elif args.system == "hermes":
        analysis = analyze_hermes_skill(source_path)
    else:
        analysis = analyze_claude_code_skill(source_path)

    analysis_file = output_path / "analysis.json"
    with open(analysis_file, "w", encoding="utf-8") as handle:
        json.dump(analysis, handle, indent=2, ensure_ascii=False)
    safe_print(f"[OK] Analysis written to: {analysis_file}")

    report_file = output_path / "compatibility_report.md"
    write_text(report_file, generate_compatibility_report(analysis))
    safe_print(f"[OK] Compatibility report written to: {report_file}")

    mapping_file = output_path / "mapping.yaml"
    write_text(mapping_file, dump_yaml(analysis.get("mappings", {})))
    safe_print(f"[OK] Mapping written to: {mapping_file}")

    safe_print("")
    safe_print(f"Analysis complete. Review {report_file} before conversion.")


if __name__ == "__main__":
    main()

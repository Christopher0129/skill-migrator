#!/usr/bin/env python3
"""
Validate converted skills for OpenClaw compatibility.

Usage:
    python3 validate_skill.py --skill /path/to/skill
    python3 validate_skill.py --skill /path/to/skill --strict
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import List, Tuple

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    yaml = None


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def safe_print(message: str = "") -> None:
    encoding = sys.stdout.encoding or "utf-8"
    text = str(message).encode(encoding, errors="replace").decode(encoding, errors="replace")
    print(text)


def validate_skill_md(skill_path: Path) -> Tuple[bool, List[str]]:
    """Validate SKILL.md file."""
    errors: List[str] = []
    warnings: List[str] = []

    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return False, ["ERROR: SKILL.md not found"]

    content = read_text(skill_md)

    frontmatter_match = re.match(r"^---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n|$)", content, re.DOTALL)
    if not frontmatter_match:
        errors.append("ERROR: Missing YAML frontmatter (---)")
    else:
        frontmatter_text = frontmatter_match.group(1)
        if HAS_YAML:
            try:
                frontmatter = yaml.safe_load(frontmatter_text)
            except yaml.YAMLError as exc:
                errors.append(f"ERROR: Invalid YAML frontmatter: {exc}")
            else:
                if not isinstance(frontmatter, dict):
                    errors.append("ERROR: Frontmatter is not a valid YAML object")
                else:
                    if "name" not in frontmatter:
                        errors.append("ERROR: Missing 'name' in frontmatter")
                    if "description" not in frontmatter:
                        errors.append("ERROR: Missing 'description' in frontmatter")

                    name = frontmatter.get("name")
                    if name and not re.match(r"^[a-z0-9-]+$", str(name)):
                        errors.append(
                            f"ERROR: Invalid skill name '{name}'. Use lowercase letters, digits, and hyphens only."
                        )

                    description = str(frontmatter.get("description", ""))
                    if len(description) < 50:
                        warnings.append(
                            f"WARNING: Description is short ({len(description)} chars). Consider adding more detail for better triggering."
                        )
                    if description and "use when" not in description.lower():
                        warnings.append("WARNING: Description should include 'Use when...' triggers")
        else:
            if "name:" not in frontmatter_text:
                errors.append("ERROR: Missing 'name:' in frontmatter")
            if "description:" not in frontmatter_text:
                errors.append("ERROR: Missing 'description:' in frontmatter")

    body = content[frontmatter_match.end():] if frontmatter_match else content
    if len(body.strip()) < 100:
        warnings.append("WARNING: SKILL.md body is very short")

    if "TODO" in content or "FIXME" in content:
        warnings.append("WARNING: SKILL.md contains TODO/FIXME markers")

    return len(errors) == 0, errors + warnings


def validate_structure(skill_path: Path) -> Tuple[bool, List[str]]:
    """Validate skill directory structure."""
    errors: List[str] = []
    warnings: List[str] = []

    if not (skill_path / "SKILL.md").exists():
        errors.append("ERROR: SKILL.md is required")

    scripts_dir = skill_path / "scripts"
    if scripts_dir.exists() and os.name != "nt":
        for script in scripts_dir.iterdir():
            if not script.is_file():
                continue
            content = read_text(script)
            if script.suffix == ".py" and not content.startswith("#!/"):
                warnings.append(f"WARNING: {script.name} missing shebang line")
            if script.suffix in {".py", ".sh"} and not os.access(script, os.X_OK):
                warnings.append(f"WARNING: {script.name} is not executable")

    extraneous = ["INSTALL.md", "CHANGELOG.md", "LICENSE"]
    for filename in extraneous:
        if (skill_path / filename).exists():
            warnings.append(f"WARNING: {filename} should not be included in skills")

    return len(errors) == 0, errors + warnings


def validate_scripts(skill_path: Path) -> Tuple[bool, List[str]]:
    """Validate scripts in the skill."""
    errors: List[str] = []
    warnings: List[str] = []

    scripts_dir = skill_path / "scripts"
    if not scripts_dir.exists():
        return True, []

    for script in scripts_dir.rglob("*"):
        if not script.is_file():
            continue
        try:
            content = read_text(script)
            if script.suffix == ".py":
                try:
                    compile(content, str(script), "exec")
                except SyntaxError as exc:
                    errors.append(f"ERROR: {script.name} has syntax error: {exc}")

            if "/root/.openclaw" in content or "/home/" in content:
                warnings.append(f"WARNING: {script.name} contains hardcoded paths")
        except Exception as exc:
            warnings.append(f"WARNING: Could not read {script.name}: {exc}")

    return len(errors) == 0, errors + warnings


def validate_references(skill_path: Path) -> Tuple[bool, List[str]]:
    """Validate references in the skill."""
    warnings: List[str] = []

    references_dir = skill_path / "references"
    if not references_dir.exists():
        return True, []

    for ref_file in references_dir.iterdir():
        if not ref_file.is_file():
            continue
        content = read_text(ref_file)

        if len(content) > 50000:
            warnings.append(f"WARNING: {ref_file.name} is very large ({len(content)} chars). Consider splitting.")

        if len(content) > 5000 and "# " in content:
            if "## " not in content[:1000] and "Table of Contents" not in content[:1000]:
                warnings.append(f"WARNING: {ref_file.name} is long but lacks table of contents")

    return True, warnings


def validate_state_management(skill_path: Path) -> Tuple[bool, List[str]]:
    """Validate state management configuration."""
    warnings: List[str] = []

    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return False, ["ERROR: SKILL.md not found"]

    content = read_text(skill_md)
    has_stateful = "stateful: true" in content
    mentions_state = "state.yaml" in content or "state file" in content.lower()

    if has_stateful and not mentions_state:
        warnings.append("WARNING: Skill declares stateful: true but does not document state file location")

    if mentions_state and not has_stateful:
        warnings.append("WARNING: Skill mentions state file but is missing stateful: true in frontmatter")

    return True, warnings


def validate_cron(skill_path: Path) -> Tuple[bool, List[str]]:
    """Validate cron configuration."""
    errors: List[str] = []
    warnings: List[str] = []

    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return False, ["ERROR: SKILL.md not found"]

    content = read_text(skill_md)
    cron_match = re.search(r'cron:\s*["\']([^"\']+)["\']', content)
    if cron_match:
        cron_expr = cron_match.group(1)
        if len(cron_expr.split()) != 5:
            errors.append(f"ERROR: Invalid cron expression '{cron_expr}'. Expected 5 fields.")
        if cron_expr == "* * * * *":
            warnings.append("WARNING: Cron runs every minute. Consider less frequent execution.")

    return len(errors) == 0, errors + warnings


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate OpenClaw skills")
    parser.add_argument("--skill", required=True, help="Path to skill directory")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    args = parser.parse_args()

    skill_path = Path(args.skill)
    if not skill_path.exists():
        safe_print(f"ERROR: Skill path does not exist: {skill_path}")
        sys.exit(1)
    if not skill_path.is_dir():
        safe_print(f"ERROR: Skill path is not a directory: {skill_path}")
        sys.exit(1)

    safe_print(f"Validating skill: {skill_path.name}")
    safe_print("-" * 50)

    validations = [
        ("SKILL.md", validate_skill_md),
        ("Structure", validate_structure),
        ("Scripts", validate_scripts),
        ("References", validate_references),
        ("State Management", validate_state_management),
        ("Cron", validate_cron),
    ]

    all_valid = True
    all_messages: List[str] = []

    for name, validator in validations:
        valid, messages = validator(skill_path)
        if not valid:
            all_valid = False
        all_messages.extend([f"[{name}] {message}" for message in messages])

    errors = [message for message in all_messages if "ERROR:" in message]
    warnings = [message for message in all_messages if "WARNING:" in message]

    if errors:
        safe_print("")
        safe_print("ERRORS:")
        for error in errors:
            safe_print(f"  {error}")

    if warnings:
        safe_print("")
        safe_print("WARNINGS:")
        for warning in warnings:
            safe_print(f"  {warning}")

    if not errors and not warnings:
        safe_print("")
        safe_print("All validations passed.")

    safe_print("")
    safe_print("-" * 50)
    if not all_valid or (args.strict and warnings):
        safe_print("Validation FAILED")
        sys.exit(1)

    safe_print("Validation PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()

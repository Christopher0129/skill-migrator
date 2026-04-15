import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from analyze_skill import analyze_claude_code_skill, analyze_cloudcode_skill, analyze_hermes_skill
from validate_skill import (
    validate_cron,
    validate_references,
    validate_scripts,
    validate_skill_md,
    validate_state_management,
    validate_structure,
)


def validate_all(skill_path: Path) -> None:
    validators = [
        validate_skill_md,
        validate_structure,
        validate_scripts,
        validate_references,
        validate_state_management,
        validate_cron,
    ]

    failures = []
    for validator in validators:
        valid, messages = validator(skill_path)
        if not valid:
            failures.append(f"{validator.__name__} failed: {messages}")
        elif messages:
            failures.append(f"{validator.__name__} produced warnings: {messages}")

    if failures:
        raise AssertionError("\n".join(failures))


class SkillMigratorRegressionTests(unittest.TestCase):
    maxDiff = None

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

    def write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")

    def make_cloudcode_skill(self, root: Path) -> Path:
        skill_dir = root / "cloudcode"
        skill_dir.mkdir(parents=True, exist_ok=True)
        self.write(
            skill_dir / "demo.cs",
            """@tool
def search_web(query: str):
    return query

@tool
def custom_tool(path: str):
    return path
""",
        )
        self.write(skill_dir / "requirements.txt", "requests>=2.0\npyyaml\n")
        self.write(skill_dir / "state.json", '{"counter": 1, "nested": {"a": true}}')
        return skill_dir

    def make_hermes_skill(self, root: Path) -> Path:
        skill_dir = root / "hermes"
        skill_dir.mkdir(parents=True, exist_ok=True)
        self.write(
            skill_dir / "config.toml",
            """name = "demo-hermes"
description = "Hermes demo"
[tools]
enabled = ["run_task"]
""",
        )
        self.write(
            skill_dir / "main.py",
            """def helper():
    return 1

def run_task(x):
    return x
""",
        )
        return skill_dir

    def make_claude_code_skill(self, root: Path) -> Path:
        skill_dir = root / "claude"
        skill_dir.mkdir(parents=True, exist_ok=True)
        self.write(
            skill_dir / "README.md",
            """# Reference Notes

This file should not become the converted skill.
""",
        )
        self.write(
            skill_dir / "deploy.md",
            """# Deploy Skill

## SLASH_COMMANDS
- /deploy: deploy app

## Instructions
Run tests then deploy.
""",
        )
        return skill_dir

    def test_skill_documentation_is_utf8_and_has_no_removed_commands(self) -> None:
        text = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        mappings = (REPO_ROOT / "references" / "cross-system-mappings.md").read_text(encoding="utf-8")

        self.assertIn("Claude Code", text)
        self.assertIn("Hermes", text)
        self.assertIn("让 OpenClaw 学会把 Claude Code 和 Hermes skill 转成 OpenClaw skill。", text)
        self.assertIn("Get-Content -Raw -Encoding UTF8 source_file", text)
        self.assertNotIn("auto-fix", text)
        self.assertNotIn("自动修复", text)
        self.assertNotIn("convert_state.py", text)
        self.assertNotIn("tar -czf", text)
        self.assertNotIn("cp -r", text)
        self.assertNotIn("for skill in /path/to/skills/*/; do", text)
        self.assertEqual(text.count("If Tool Mapping Conflicts"), 1)
        self.assertIn("[English](#english) | [简体中文](#简体中文)", readme)
        self.assertIn("## English", readme)
        self.assertIn("## 简体中文", readme)
        self.assertIn("Teach OpenClaw how to convert **Claude Code skills** into **OpenClaw skills**", readme)
        self.assertIn("把 **Claude Code skill** 转成 **OpenClaw skill**", readme)
        self.assertIn("CloudCode is still kept as extended support", readme)
        self.assertIn("CloudCode 目前仍然保留为扩展支持", readme)
        self.assertIn("高频映射速查表", mappings)
        self.assertIn("## Fast Lookup", mappings)
        self.assertIn("## High-Frequency Tool Mappings", mappings)
        self.assertNotIn("## Common Migration Patterns", mappings)
        self.assertNotIn("## Migration Checklist", mappings)

    def test_cloudcode_cli_convert_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = self.make_cloudcode_skill(root)
            analysis_dir = root / "analysis"
            output_dir = root / "converted"

            analyze_result = self.run_cli(
                "scripts/analyze_skill.py",
                "--source",
                str(source),
                "--system",
                "cloudcode",
                "--output",
                str(analysis_dir),
            )
            self.assertEqual(analyze_result.returncode, 0, analyze_result.stderr)

            convert_result = self.run_cli(
                "scripts/convert_skill.py",
                "--source",
                str(source),
                "--system",
                "cloudcode",
                "--output",
                str(output_dir),
            )
            self.assertEqual(convert_result.returncode, 0, convert_result.stderr)

            skill_path = output_dir / "demo"
            validate_result = self.run_cli(
                "scripts/validate_skill.py",
                "--skill",
                str(skill_path),
                "--strict",
            )
            self.assertEqual(validate_result.returncode, 0, validate_result.stdout + validate_result.stderr)

            skill_md = (skill_path / "SKILL.md").read_text(encoding="utf-8")
            state_yaml = (skill_path / "state.yaml").read_text(encoding="utf-8")
            self.assertIn("stateful: true", skill_md)
            self.assertIn("custom_tool", skill_md)
            self.assertIn("counter: 1", state_yaml)

    def test_hermes_analysis_only_uses_declared_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = self.make_hermes_skill(root)

            analysis = analyze_hermes_skill(source)
            self.assertEqual(analysis["tools"], ["run_task"])

            output_dir = root / "converted"
            convert_result = self.run_cli(
                "scripts/convert_skill.py",
                "--source",
                str(source),
                "--system",
                "hermes",
                "--output",
                str(output_dir),
            )
            self.assertEqual(convert_result.returncode, 0, convert_result.stderr)

            skill_path = output_dir / "demo-hermes"
            validate_all(skill_path)
            self.assertTrue((skill_path / "scripts" / "main.py").exists())

    def test_claude_code_prefers_markdown_with_slash_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = self.make_claude_code_skill(root)

            analysis = analyze_claude_code_skill(source)
            self.assertEqual(len(analysis["skill_files"]), 1)
            self.assertEqual(analysis["skill_files"][0]["path"], "deploy.md")
            self.assertEqual(analysis["tools"], ["/deploy"])

            output_dir = root / "converted"
            convert_result = self.run_cli(
                "scripts/convert_skill.py",
                "--source",
                str(source),
                "--system",
                "claude-code",
                "--output",
                str(output_dir),
            )
            self.assertEqual(convert_result.returncode, 0, convert_result.stderr)

            skill_path = output_dir / "deploy"
            validate_all(skill_path)
            skill_md = (skill_path / "SKILL.md").read_text(encoding="utf-8")
            original_md = (skill_path / "references" / "original.md").read_text(encoding="utf-8")
            self.assertIn("`/deploy`", skill_md)
            self.assertIn("Deploy Skill", original_md)
            self.assertNotIn("Reference Notes", original_md)

    def test_phased_migration_reports_partial_for_unmapped_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = self.make_cloudcode_skill(root)
            output_dir = root / "migrated"

            migrate_result = self.run_cli(
                "scripts/migrate_skill.py",
                "--source",
                str(source),
                "--system",
                "cloudcode",
                "--output",
                str(output_dir),
                "--phased",
                "--test-full",
            )
            self.assertEqual(migrate_result.returncode, 0, migrate_result.stderr)
            self.assertIn("Status: partial", migrate_result.stdout)

            skill_path = output_dir / "demo"
            validate_all(skill_path)
            report = (skill_path / "MIGRATION_REPORT.md").read_text(encoding="utf-8")
            self.assertIn("Phase 2: Tool & Script Migration", report)
            self.assertIn("custom_tool", report)

    def test_analysis_based_migration_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = self.make_cloudcode_skill(root)
            analysis_dir = root / "analysis"
            migrated_dir = root / "migrated"

            analyze_result = self.run_cli(
                "scripts/analyze_skill.py",
                "--source",
                str(source),
                "--system",
                "cloudcode",
                "--output",
                str(analysis_dir),
            )
            self.assertEqual(analyze_result.returncode, 0, analyze_result.stderr)

            migrate_result = self.run_cli(
                "scripts/migrate_skill.py",
                "--analysis",
                str(analysis_dir / "analysis.json"),
                "--output",
                str(migrated_dir),
                "--phased",
            )
            self.assertEqual(migrate_result.returncode, 0, migrate_result.stderr)

            skill_path = migrated_dir / "demo"
            validate_all(skill_path)


if __name__ == "__main__":
    unittest.main()

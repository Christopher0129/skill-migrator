#!/usr/bin/env python3
"""
Enhanced skill converter with automatic testing and phased migration.

Usage:
    python3 migrate_skill.py --source /path/to/skill --system cloudcode --output ./converted/
    python3 migrate_skill.py --source /path/to/skill --system cloudcode --output ./converted/ --phased
    python3 migrate_skill.py --analysis ./analysis.json --output ./converted/ --phased
"""

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from analyze_skill import (
    analyze_claude_code_skill,
    analyze_cloudcode_skill,
    analyze_hermes_skill,
)
from convert_skill import (
    TOOL_MAP,
    convert_claude_code_skill,
    convert_cloudcode_skill,
    convert_hermes_skill,
    convert_state_file,
    generate_claude_code_skill_md,
    generate_cloudcode_skill_md,
    generate_hermes_skill_md,
    generate_tool_wrapper,
    get_skill_name,
    read_text,
    safe_print,
    select_primary_claude_file,
    unique,
    write_script,
    write_text,
    write_yaml,
)
from validate_skill import (
    validate_cron,
    validate_references,
    validate_scripts,
    validate_skill_md,
    validate_state_management,
    validate_structure,
)


@dataclass
class MigrationPhase:
    """Represents a single migration phase."""

    name: str
    description: str
    status: str  # pending, in_progress, completed, partial, failed
    artifacts: List[str]
    test_results: Dict[str, Any]
    notes: List[str]


@dataclass
class MigrationReport:
    """Complete migration report."""

    skill_name: str
    source_system: str
    start_time: str
    end_time: Optional[str]
    phases: List[MigrationPhase]
    overall_status: str
    recommendations: List[str]


class PhasedMigrationEngine:
    """Handles complex skill migration in phases."""

    def __init__(self, source_path: Path, output_path: Path, analysis: Dict[str, Any]):
        self.source_path = source_path
        self.output_path = output_path
        self.analysis = analysis
        self.phases: List[MigrationPhase] = []

    @property
    def skill_name(self) -> str:
        return get_skill_name(self.source_path, self.analysis)

    @property
    def skill_path(self) -> Path:
        return self.output_path / self.skill_name

    def run_phased_migration(self) -> MigrationReport:
        """Execute migration in multiple phases."""
        start_time = datetime.now().isoformat()

        for phase_runner in (
            self._run_phase_1_structure,
            self._run_phase_2_tools,
            self._run_phase_3_state_and_references,
            self._run_phase_4_testing,
            self._run_phase_5_documentation,
        ):
            phase = phase_runner()
            self.phases.append(phase)
            if phase.status == "failed" and phase.name != "Automated Testing":
                break

        return self._create_report(start_time)

    def _run_phase_1_structure(self) -> MigrationPhase:
        """Create the skill directory structure and SKILL.md."""
        phase = MigrationPhase(
            name="Structure Migration",
            description="Create OpenClaw skill directory structure and SKILL.md",
            status="in_progress",
            artifacts=[],
            test_results={},
            notes=[],
        )

        try:
            self.skill_path.mkdir(parents=True, exist_ok=True)
            (self.skill_path / "scripts").mkdir(exist_ok=True)
            (self.skill_path / "references").mkdir(exist_ok=True)

            system = self.analysis["system"]
            if system == "cloudcode":
                skill_md = generate_cloudcode_skill_md(self.skill_name, self.analysis)
            elif system == "hermes":
                skill_md = generate_hermes_skill_md(self.skill_name, self.analysis)
            elif system == "claude-code":
                primary = select_primary_claude_file(self.analysis)
                original_content = ""
                if primary:
                    original_content = read_text(self.source_path / primary["path"])
                skill_md = generate_claude_code_skill_md(self.skill_name, original_content, self.analysis)
            else:
                raise ValueError(f"Unsupported system: {system}")

            skill_md_path = self.skill_path / "SKILL.md"
            write_text(skill_md_path, skill_md)
            phase.artifacts.extend([str(self.skill_path), str(skill_md_path)])
            phase.status = "completed"
            phase.notes.append(f"Created skill scaffold at {self.skill_path}")
        except Exception as exc:
            phase.status = "failed"
            phase.notes.append(f"Failed to create structure: {exc}")

        return phase

    def _run_phase_2_tools(self) -> MigrationPhase:
        """Convert tools and scripts."""
        phase = MigrationPhase(
            name="Tool & Script Migration",
            description="Copy scripts and generate wrappers for mapped tools",
            status="in_progress",
            artifacts=[],
            test_results={},
            notes=[],
        )

        try:
            system = self.analysis["system"]
            scripts_dir = self.skill_path / "scripts"
            scripts_dir.mkdir(exist_ok=True)

            if system == "cloudcode":
                converted = 0
                manual_review = []
                for tool in unique(self.analysis.get("tools", [])):
                    wrapper = generate_tool_wrapper(tool)
                    if wrapper:
                        script_path = scripts_dir / f"{tool}.py"
                        write_script(script_path, wrapper)
                        phase.artifacts.append(str(script_path))
                        converted += 1
                    elif tool in TOOL_MAP:
                        converted += 1
                        phase.notes.append(f"Mapped `{tool}` to built-in OpenClaw tool `{TOOL_MAP[tool]}`.")
                    else:
                        manual_review.append(tool)

                phase.test_results["converted"] = converted
                phase.test_results["manual_review"] = manual_review
                if manual_review:
                    phase.status = "partial"
                    phase.notes.append(
                        "Manual review required for: " + ", ".join(f"`{tool}`" for tool in manual_review)
                    )
                else:
                    phase.status = "completed"

            elif system == "hermes":
                copied = 0
                for py_file in self.source_path.rglob("*.py"):
                    target = scripts_dir / py_file.name
                    write_script(target, read_text(py_file))
                    phase.artifacts.append(str(target))
                    copied += 1

                phase.test_results["copied_scripts"] = copied
                phase.status = "completed"
                if copied == 0:
                    phase.notes.append("No Hermes Python scripts were found to copy.")

            else:
                phase.status = "completed"
                phase.notes.append("Claude Code skills do not require generated wrapper scripts.")

        except Exception as exc:
            phase.status = "failed"
            phase.notes.append(f"Failed to convert tools/scripts: {exc}")

        return phase

    def _write_dependencies_reference(self) -> Optional[Path]:
        dependencies = self.analysis.get("dependencies", [])
        if not dependencies:
            return None

        reference_path = self.skill_path / "references" / "dependencies.md"
        lines = ["# Dependencies", ""]
        lines.extend([f"- {dependency}" for dependency in dependencies])
        lines.extend(
            [
                "",
                "## Installation",
                "",
                "```bash",
                "pip install " + " ".join(dependencies),
                "```",
            ]
        )
        write_text(reference_path, "\n".join(lines) + "\n")
        return reference_path

    def _run_phase_3_state_and_references(self) -> MigrationPhase:
        """Convert state and copy supporting references."""
        phase = MigrationPhase(
            name="State & Reference Migration",
            description="Convert state files and preserve migration references",
            status="in_progress",
            artifacts=[],
            test_results={},
            notes=[],
        )

        try:
            state_files = self.analysis.get("state_files", [])
            if state_files:
                state_path = self.source_path / state_files[0]
                if state_path.exists():
                    target = self.skill_path / "state.yaml"
                    write_yaml(target, convert_state_file(state_path))
                    phase.artifacts.append(str(target))
                    phase.test_results["state_converted"] = True
                else:
                    phase.test_results["state_converted"] = False
                    phase.notes.append(f"State file listed in analysis but missing on disk: {state_files[0]}")

            dependencies_ref = self._write_dependencies_reference()
            if dependencies_ref:
                phase.artifacts.append(str(dependencies_ref))

            if self.analysis["system"] == "claude-code":
                primary = select_primary_claude_file(self.analysis)
                if primary:
                    source_md = self.source_path / primary["path"]
                    original_ref = self.skill_path / "references" / "original.md"
                    write_text(original_ref, read_text(source_md))
                    phase.artifacts.append(str(original_ref))

            phase.status = "completed"
        except Exception as exc:
            phase.status = "failed"
            phase.notes.append(f"Failed to migrate state/references: {exc}")

        return phase

    def _run_phase_4_testing(self) -> MigrationPhase:
        """Validate the converted skill."""
        phase = MigrationPhase(
            name="Automated Testing",
            description="Validate the converted skill against local rules",
            status="in_progress",
            artifacts=[],
            test_results={},
            notes=[],
        )

        checks = [
            ("skill_md", validate_skill_md),
            ("structure", validate_structure),
            ("scripts", validate_scripts),
            ("references", validate_references),
            ("state", validate_state_management),
            ("cron", validate_cron),
        ]

        errors: List[str] = []
        warnings: List[str] = []

        try:
            for name, validator in checks:
                valid, messages = validator(self.skill_path)
                phase.test_results[name] = {
                    "valid": valid,
                    "messages": messages,
                }

                for message in messages:
                    if "ERROR:" in message:
                        errors.append(f"[{name}] {message}")
                    elif "WARNING:" in message:
                        warnings.append(f"[{name}] {message}")

            if errors:
                phase.status = "failed"
                phase.notes.append(f"Found {len(errors)} validation error(s).")
            elif warnings:
                phase.status = "partial"
                phase.notes.append(f"Found {len(warnings)} validation warning(s).")
            else:
                phase.status = "completed"
                phase.notes.append("All validation checks passed.")

            for message in errors + warnings:
                phase.notes.append(message)
        except Exception as exc:
            phase.status = "failed"
            phase.notes.append(f"Testing crashed: {exc}")

        return phase

    def _run_phase_5_documentation(self) -> MigrationPhase:
        """Generate the migration report."""
        phase = MigrationPhase(
            name="Documentation",
            description="Write a migration report for manual follow-up",
            status="in_progress",
            artifacts=[],
            test_results={},
            notes=[],
        )

        try:
            report_path = self.skill_path / "MIGRATION_REPORT.md"
            write_text(report_path, self._generate_migration_report())
            phase.artifacts.append(str(report_path))
            phase.status = "completed"
            phase.notes.append("Generated MIGRATION_REPORT.md")
        except Exception as exc:
            phase.status = "failed"
            phase.notes.append(f"Failed to generate migration report: {exc}")

        return phase

    def _determine_overall_status(self) -> str:
        statuses = [phase.status for phase in self.phases]
        if "failed" in statuses:
            return "failed"
        if "partial" in statuses:
            return "partial"
        return "completed"

    def _create_report(self, start_time: str) -> MigrationReport:
        recommendations = []
        for phase in self.phases:
            if phase.status in {"partial", "failed"}:
                recommendations.append(f"Review phase '{phase.name}' before installing the migrated skill.")

        return MigrationReport(
            skill_name=self.skill_name,
            source_system=self.analysis.get("system", "unknown"),
            start_time=start_time,
            end_time=datetime.now().isoformat(),
            phases=self.phases,
            overall_status=self._determine_overall_status(),
            recommendations=recommendations,
        )

    def _generate_migration_report(self) -> str:
        lines = [
            f"# Migration Report: {self.skill_name}",
            "",
            f"**Source System:** {self.analysis.get('system', 'unknown')}",
            f"**Migration Date:** {datetime.now().isoformat()}",
            "",
            "## Phases",
            "",
        ]

        for index, phase in enumerate(self.phases, start=1):
            lines.extend(
                [
                    f"### Phase {index}: {phase.name}",
                    f"Status: {phase.status}",
                    f"Description: {phase.description}",
                    "",
                ]
            )

            if phase.artifacts:
                lines.append("Artifacts:")
                lines.extend([f"- {artifact}" for artifact in phase.artifacts])
                lines.append("")

            if phase.test_results:
                lines.append("Test Results:")
                for key, value in phase.test_results.items():
                    lines.append(f"- {key}: {value}")
                lines.append("")

            if phase.notes:
                lines.append("Notes:")
                lines.extend([f"- {note}" for note in phase.notes])
                lines.append("")

        return "\n".join(lines).rstrip() + "\n"


class AutoTester:
    """Automatically tests converted skills."""

    def __init__(self, skill_path: Path):
        self.skill_path = skill_path

    def run_full_test(self) -> Dict[str, Any]:
        checks = [
            ("skill_md", validate_skill_md),
            ("structure", validate_structure),
            ("scripts", validate_scripts),
            ("references", validate_references),
            ("state", validate_state_management),
            ("cron", validate_cron),
        ]

        results: Dict[str, Any] = {}
        for name, validator in checks:
            valid, messages = validator(self.skill_path)
            results[name] = {"valid": valid, "messages": messages}

        return results


def load_or_create_analysis(args: argparse.Namespace, output_path: Path) -> Tuple[Path, Dict[str, Any]]:
    """Resolve source path and analysis data from CLI args."""
    if args.analysis:
        with open(args.analysis, encoding="utf-8") as handle:
            analysis = json.load(handle)
        source_path = Path(args.source) if args.source else Path(analysis["source_path"])
        return source_path, analysis

    if not args.source or not args.system:
        safe_print("Error: either --analysis or both --source and --system are required.")
        raise SystemExit(1)

    source_path = Path(args.source)
    if args.system == "cloudcode":
        analysis = analyze_cloudcode_skill(source_path)
    elif args.system == "hermes":
        analysis = analyze_hermes_skill(source_path)
    else:
        analysis = analyze_claude_code_skill(source_path)

    analysis_file = output_path / "analysis.json"
    with open(analysis_file, "w", encoding="utf-8") as handle:
        json.dump(analysis, handle, indent=2, ensure_ascii=False)
    safe_print(f"[OK] Analysis saved to: {analysis_file}")
    return source_path, analysis


def run_standard_conversion(source_path: Path, analysis: Dict[str, Any], output_path: Path) -> Path:
    """Run the simple one-shot conversion path."""
    system = analysis["system"]
    if system == "cloudcode":
        return convert_cloudcode_skill(source_path, analysis, output_path)
    if system == "hermes":
        return convert_hermes_skill(source_path, analysis, output_path)
    return convert_claude_code_skill(source_path, analysis, output_path)


def print_report(report: MigrationReport) -> None:
    safe_print("")
    safe_print("=" * 60)
    safe_print(f"Migration Report: {report.skill_name}")
    safe_print(f"Status: {report.overall_status}")
    safe_print("=" * 60)

    for index, phase in enumerate(report.phases, start=1):
        safe_print("")
        safe_print(f"Phase {index}: {phase.name} [{phase.status}]")
        for note in phase.notes:
            safe_print(f"  - {note}")

    if report.recommendations:
        safe_print("")
        safe_print("Recommendations:")
        for recommendation in report.recommendations:
            safe_print(f"  - {recommendation}")


def print_test_results(test_results: Dict[str, Any]) -> None:
    safe_print("")
    safe_print("=" * 60)
    safe_print("Test Results")
    safe_print("=" * 60)
    for category, result in test_results.items():
        safe_print("")
        safe_print(f"{category.upper()} [{'OK' if result.get('valid') else 'FAIL'}]")
        for message in result.get("messages", []):
            safe_print(f"  - {message}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Enhanced skill migration with testing")
    parser.add_argument("--source", help="Path to source skill")
    parser.add_argument("--system", choices=["cloudcode", "hermes", "claude-code"], help="Source system type")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--phased", action="store_true", help="Use phased migration")
    parser.add_argument("--test-full", action="store_true", help="Run full test suite after conversion")
    parser.add_argument("--analysis", help="Use existing analysis.json")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    source_path, analysis = load_or_create_analysis(args, output_path)

    if args.phased:
        safe_print("")
        safe_print("Running phased migration...")
        engine = PhasedMigrationEngine(source_path, output_path, analysis)
        report = engine.run_phased_migration()
        print_report(report)
        skill_name = report.skill_name
    else:
        safe_print("")
        safe_print("Running standard conversion...")
        skill_output = run_standard_conversion(source_path, analysis, output_path)
        skill_name = skill_output.name
        safe_print(f"[OK] Converted to: {skill_output}")

    if args.test_full:
        safe_print("")
        safe_print("Running full test suite...")
        skill_path = output_path / skill_name
        tester = AutoTester(skill_path)
        test_results = tester.run_full_test()
        print_test_results(test_results)

        test_report = output_path / f"{skill_name}_test_report.json"
        with open(test_report, "w", encoding="utf-8") as handle:
            json.dump(test_results, handle, indent=2, ensure_ascii=False)
        safe_print("")
        safe_print(f"[OK] Test report saved to: {test_report}")

    safe_print("")
    safe_print("=" * 60)
    safe_print("Migration complete.")
    safe_print(f"Skill location: {output_path / skill_name}")
    safe_print("=" * 60)


if __name__ == "__main__":
    main()

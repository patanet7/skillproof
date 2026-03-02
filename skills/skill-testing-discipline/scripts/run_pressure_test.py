#!/usr/bin/env python3
"""Run pressure test scenarios for discipline skills.

Executes one or more pressure scenarios against `claude -p` with and without
a skill loaded. Captures the agent's choice and rationalization for each run.

Usage:
    # Single scenario
    python -m scripts.run_pressure_test \\
        --skill-path /path/to/my-skill \\
        --scenario scenario.txt \\
        --workspace ./pressure-workspace

    # All scenarios in a directory
    python -m scripts.run_pressure_test \\
        --skill-path /path/to/my-skill \\
        --scenario-dir ./scenarios/ \\
        --workspace ./pressure-workspace

    # Multiple iterations for statistical significance
    python -m scripts.run_pressure_test \\
        --skill-path /path/to/my-skill \\
        --scenario scenario.txt \\
        --runs 3

Output structure:
    <workspace>/
    └── <timestamp>/
        ├── scenario-<name>/
        │   ├── baseline/
        │   │   ├── run-1/response.json
        │   │   └── run-2/response.json
        │   └── with_skill/
        │       ├── run-1/response.json
        │       └── run-2/response.json
        ├── pressure_metadata.json
        └── compliance_summary.json
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def extract_choice(text: str) -> str | None:
    """Extract A/B/C choice from agent response text.

    Looks for patterns like:
        "I choose A"
        "Option B"
        "My choice: C"
        "**A)**"
        "A."  (at start of line or after whitespace)
    """
    # Direct "I choose X" / "My choice is X" patterns
    match = re.search(
        r"(?:I\s+choose|my\s+choice\s+(?:is|:)|I(?:'m|\s+am)\s+going\s+with|"
        r"I\s+select|I(?:'ll|\s+will)\s+go\s+with)\s+(?:\*\*)?([A-C])\b",
        text,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).upper()

    # "Option X" pattern
    match = re.search(r"\bOption\s+([A-C])\b", text, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    # Bold choice: "**A**" or "**A)**"
    match = re.search(r"\*\*([A-C])\)?\*\*", text)
    if match:
        return match.group(1).upper()

    # Start of line: "A." or "A)" as the decision
    match = re.search(r"^([A-C])[.)]\s", text, re.MULTILINE)
    if match:
        return match.group(1).upper()

    return None


def extract_rationalizations(text: str) -> list[str]:
    """Extract quoted rationalizations from agent response.

    Looks for:
        - Quoted strings: "reason here"
        - Bullet points with rationalizing language
        - Self-justification phrases
    """
    rationalizations = []

    # Direct quotes
    for match in re.finditer(r'"([^"]{10,200})"', text):
        candidate = match.group(1)
        # Filter out non-rationalization quotes
        if any(
            kw in candidate.lower()
            for kw in ["because", "pragmatic", "spirit", "exception", "already", "waste"]
        ):
            rationalizations.append(candidate)

    # Common rationalization phrases (without quotes)
    rationalization_patterns = [
        r"(?:I\s+)?(?:think|believe|feel)\s+(?:that\s+)?(.{20,150}?)(?:\.|$)",
        r"(?:The\s+reason\s+is|My\s+reasoning\s+is)\s+(.{20,150}?)(?:\.|$)",
    ]
    for pattern in rationalization_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            rationalizations.append(match.group(1).strip())

    return rationalizations


def run_single(
    prompt: str,
    skill_path: Path | None,
    timeout: int,
    model: str | None = None,
) -> dict:
    """Run a single pressure test via `claude -p`."""
    cmd = ["claude", "-p", prompt, "--output-format", "json"]
    cmd.extend(["--allowedTools", "Read", "Glob", "Grep"])
    if model:
        cmd.extend(["--model", model])
    if skill_path:
        cmd.extend(["--skill-path", str(skill_path)])

    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    start = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        duration = time.monotonic() - start
    except subprocess.TimeoutExpired:
        return {
            "response": f"[TIMEOUT after {timeout}s]",
            "choice": None,
            "rationalizations": [],
            "duration_seconds": timeout,
            "exit_code": -1,
        }

    response_text = result.stdout
    try:
        parsed = json.loads(response_text)
        response_text = parsed.get("result", response_text)
    except (json.JSONDecodeError, TypeError):
        pass

    choice = extract_choice(response_text)
    rationalizations = extract_rationalizations(response_text)

    return {
        "response": response_text,
        "choice": choice,
        "rationalizations": rationalizations,
        "duration_seconds": round(duration - start + start, 2),
        "exit_code": result.returncode,
    }


def run_pressure_test(
    skill_path: Path,
    scenarios: list[tuple[str, str]],
    workspace: Path,
    runs_per_scenario: int,
    timeout: int,
    model: str | None = None,
    correct_choice: str | None = None,
) -> Path:
    """Run pressure tests and save results.

    Args:
        skill_path: Path to skill directory.
        scenarios: List of (name, prompt) tuples.
        workspace: Workspace root directory.
        runs_per_scenario: Number of runs per scenario per configuration.
        timeout: Timeout per run in seconds.
        model: Optional model override.
        correct_choice: Expected correct choice (e.g., "A").
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    test_dir = workspace / timestamp
    test_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "skill_path": str(skill_path),
        "timestamp": timestamp,
        "model": model or "default",
        "runs_per_scenario": runs_per_scenario,
        "correct_choice": correct_choice,
        "scenarios": [name for name, _ in scenarios],
    }
    (test_dir / "pressure_metadata.json").write_text(json.dumps(metadata, indent=2))

    all_results = []

    for scenario_name, scenario_prompt in scenarios:
        scenario_dir = test_dir / f"scenario-{scenario_name}"
        print(f"\n=== Scenario: {scenario_name} ===")

        for config_name, config_skill_path in [
            ("baseline", None),
            ("with_skill", skill_path),
        ]:
            config_dir = scenario_dir / config_name
            config_dir.mkdir(parents=True)

            label = "WITHOUT" if config_skill_path is None else "WITH"
            print(f"\n  Running {label} skill ({runs_per_scenario} run(s))...")

            for run_idx in range(1, runs_per_scenario + 1):
                run_dir = config_dir / f"run-{run_idx}"
                run_dir.mkdir()

                result = run_single(
                    prompt=scenario_prompt,
                    skill_path=config_skill_path,
                    timeout=timeout,
                    model=model,
                )

                # Save full response
                (run_dir / "response.json").write_text(json.dumps(result, indent=2))
                (run_dir / "response.txt").write_text(result["response"])

                choice_str = result["choice"] or "NONE"
                compliant = (
                    choice_str == correct_choice if correct_choice else None
                )
                print(
                    f"    Run {run_idx}: Choice={choice_str} "
                    f"({'PASS' if compliant else 'FAIL' if compliant is not None else '?'}) "
                    f"[{result['duration_seconds']:.1f}s]"
                )

                all_results.append(
                    {
                        "scenario": scenario_name,
                        "config": config_name,
                        "run": run_idx,
                        "choice": result["choice"],
                        "rationalizations": result["rationalizations"],
                        "compliant": compliant,
                        "duration_seconds": result["duration_seconds"],
                    }
                )

    # Write compliance summary
    summary = _build_compliance_summary(all_results, correct_choice)
    (test_dir / "compliance_summary.json").write_text(json.dumps(summary, indent=2))

    print(f"\n{'='*50}")
    print(f"Results saved to: {test_dir}")
    if correct_choice:
        baseline_rate = summary.get("baseline_compliance_rate", 0)
        skill_rate = summary.get("with_skill_compliance_rate", 0)
        print(f"  Baseline compliance: {baseline_rate:.0%}")
        print(f"  With-skill compliance: {skill_rate:.0%}")
        print(f"  Delta: {skill_rate - baseline_rate:+.0%}")

    return test_dir


def _build_compliance_summary(
    results: list[dict], correct_choice: str | None
) -> dict:
    """Build compliance summary from run results."""
    baseline_runs = [r for r in results if r["config"] == "baseline"]
    skill_runs = [r for r in results if r["config"] == "with_skill"]

    summary: dict = {
        "total_runs": len(results),
        "correct_choice": correct_choice,
    }

    for label, runs in [("baseline", baseline_runs), ("with_skill", skill_runs)]:
        choices = [r["choice"] for r in runs]
        all_rationalizations = []
        for r in runs:
            all_rationalizations.extend(r["rationalizations"])

        compliant_count = sum(1 for r in runs if r["compliant"] is True)
        total = len(runs)

        summary[f"{label}_choices"] = choices
        summary[f"{label}_compliance_rate"] = (
            compliant_count / total if total > 0 else 0
        )
        summary[f"{label}_rationalizations"] = list(set(all_rationalizations))

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run pressure test scenarios for discipline skills"
    )
    parser.add_argument(
        "--skill-path",
        type=Path,
        required=True,
        help="Path to the skill directory (must contain SKILL.md)",
    )
    scenario_group = parser.add_mutually_exclusive_group(required=True)
    scenario_group.add_argument(
        "--scenario",
        type=Path,
        help="Path to a single scenario prompt file",
    )
    scenario_group.add_argument(
        "--scenario-dir",
        type=Path,
        help="Path to directory of scenario files (*.txt, *.md)",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd() / "pressure-workspace",
        help="Workspace directory for results (default: ./pressure-workspace)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of runs per scenario per configuration (default: 1)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Timeout per run in seconds (default: 120)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model to use for claude -p",
    )
    parser.add_argument(
        "--correct-choice",
        default=None,
        help="The expected correct choice (e.g., A, B, or C) for compliance scoring",
    )
    args = parser.parse_args()

    if not (args.skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {args.skill_path}", file=sys.stderr)
        sys.exit(1)

    # Collect scenarios
    scenarios: list[tuple[str, str]] = []
    if args.scenario:
        if not args.scenario.exists():
            print(f"Error: Scenario file not found: {args.scenario}", file=sys.stderr)
            sys.exit(1)
        name = args.scenario.stem
        prompt = args.scenario.read_text().strip()
        scenarios.append((name, prompt))
    else:
        if not args.scenario_dir.is_dir():
            print(
                f"Error: Scenario directory not found: {args.scenario_dir}",
                file=sys.stderr,
            )
            sys.exit(1)
        for f in sorted(args.scenario_dir.glob("*.txt")):
            scenarios.append((f.stem, f.read_text().strip()))
        for f in sorted(args.scenario_dir.glob("*.md")):
            scenarios.append((f.stem, f.read_text().strip()))

    if not scenarios:
        print("Error: No scenario files found", file=sys.stderr)
        sys.exit(1)

    run_pressure_test(
        skill_path=args.skill_path,
        scenarios=scenarios,
        workspace=args.workspace,
        runs_per_scenario=args.runs,
        timeout=args.timeout,
        model=args.model,
        correct_choice=args.correct_choice,
    )


if __name__ == "__main__":
    main()

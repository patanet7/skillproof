#!/usr/bin/env python3
"""Run a RED-GREEN TDD cycle for a skill.

Executes a scenario prompt against `claude -p` twice:
1. Baseline (RED) — without the skill loaded
2. With-skill (GREEN) — with the skill loaded

Saves both transcripts to a workspace directory for comparison.

Usage:
    python -m scripts.run_cycle \\
        --skill-path /path/to/my-skill \\
        --scenario scenario.txt \\
        --workspace ./tdd-workspace \\
        [--model claude-sonnet-4-20250514]

The scenario file should contain the full prompt (e.g., a pressure scenario
for discipline skills, or a task prompt for workflow skills).
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def run_claude(
    prompt: str,
    skill_path: Path | None,
    timeout: int,
    model: str | None = None,
) -> dict:
    """Run a prompt through `claude -p` and capture the response.

    Args:
        prompt: The scenario prompt to send.
        skill_path: Path to skill directory (None for baseline).
        timeout: Timeout in seconds.
        model: Optional model override.

    Returns:
        dict with keys: response, duration_seconds, exit_code
    """
    cmd = ["claude", "-p", prompt, "--output-format", "json"]
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
            "duration_seconds": timeout,
            "exit_code": -1,
        }

    # Try to parse JSON output from claude -p
    response_text = result.stdout
    try:
        parsed = json.loads(response_text)
        response_text = parsed.get("result", response_text)
    except (json.JSONDecodeError, TypeError):
        pass

    return {
        "response": response_text,
        "duration_seconds": round(duration, 2),
        "exit_code": result.returncode,
    }


def run_cycle(
    skill_path: Path,
    scenario_path: Path,
    workspace: Path,
    timeout: int,
    model: str | None = None,
) -> Path:
    """Run a full RED-GREEN cycle and save results."""
    scenario_prompt = scenario_path.read_text().strip()
    skill_name = skill_path.name

    # Create timestamped cycle directory
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    cycle_dir = workspace / f"cycle-{timestamp}"
    baseline_dir = cycle_dir / "baseline"
    with_skill_dir = cycle_dir / "with_skill"
    baseline_dir.mkdir(parents=True)
    with_skill_dir.mkdir(parents=True)

    # Save scenario for reference
    (cycle_dir / "scenario.txt").write_text(scenario_prompt)

    # Write cycle metadata
    metadata = {
        "skill_name": skill_name,
        "skill_path": str(skill_path),
        "scenario_file": str(scenario_path),
        "timestamp": timestamp,
        "model": model or "default",
    }
    (cycle_dir / "cycle_metadata.json").write_text(json.dumps(metadata, indent=2))

    # Phase 1: RED — Baseline (no skill)
    print(f"RED phase: Running baseline (no skill)...")
    baseline_result = run_claude(
        prompt=scenario_prompt,
        skill_path=None,
        timeout=timeout,
        model=model,
    )
    (baseline_dir / "response.txt").write_text(baseline_result["response"])
    (baseline_dir / "timing.json").write_text(
        json.dumps(
            {
                "duration_seconds": baseline_result["duration_seconds"],
                "exit_code": baseline_result["exit_code"],
            },
            indent=2,
        )
    )
    print(f"  Baseline complete ({baseline_result['duration_seconds']:.1f}s)")

    # Phase 2: GREEN — With skill
    print(f"GREEN phase: Running with skill '{skill_name}'...")
    skill_result = run_claude(
        prompt=scenario_prompt,
        skill_path=skill_path,
        timeout=timeout,
        model=model,
    )
    (with_skill_dir / "response.txt").write_text(skill_result["response"])
    (with_skill_dir / "timing.json").write_text(
        json.dumps(
            {
                "duration_seconds": skill_result["duration_seconds"],
                "exit_code": skill_result["exit_code"],
            },
            indent=2,
        )
    )
    print(f"  With-skill complete ({skill_result['duration_seconds']:.1f}s)")

    # Write summary
    summary = {
        "baseline": {
            "response_length": len(baseline_result["response"]),
            "duration_seconds": baseline_result["duration_seconds"],
        },
        "with_skill": {
            "response_length": len(skill_result["response"]),
            "duration_seconds": skill_result["duration_seconds"],
        },
    }
    (cycle_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    print(f"\nResults saved to: {cycle_dir}")
    print(f"  baseline/response.txt   — agent without skill")
    print(f"  with_skill/response.txt — agent with skill")
    print(f"\nCompare outputs to evaluate the skill's effect.")

    return cycle_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a RED-GREEN TDD cycle for a skill"
    )
    parser.add_argument(
        "--skill-path",
        type=Path,
        required=True,
        help="Path to the skill directory (must contain SKILL.md)",
    )
    parser.add_argument(
        "--scenario",
        type=Path,
        required=True,
        help="Path to scenario prompt file (.txt or .md)",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd() / "tdd-workspace",
        help="Workspace directory for cycle results (default: ./tdd-workspace)",
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
        help="Model to use for claude -p (default: user's configured model)",
    )
    args = parser.parse_args()

    if not (args.skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {args.skill_path}", file=sys.stderr)
        sys.exit(1)

    if not args.scenario.exists():
        print(f"Error: Scenario file not found: {args.scenario}", file=sys.stderr)
        sys.exit(1)

    run_cycle(
        skill_path=args.skill_path,
        scenario_path=args.scenario,
        workspace=args.workspace,
        timeout=args.timeout,
        model=args.model,
    )


if __name__ == "__main__":
    main()

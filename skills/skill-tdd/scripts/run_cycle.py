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
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add _shared to import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "_shared"))
from claude_runner import run_claude, save_timing  # noqa: E402


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
    print("RED phase: Running baseline (no skill)...")
    baseline_result = run_claude(
        prompt=scenario_prompt,
        skill_path=None,
        timeout=timeout,
        model=model,
    )
    (baseline_dir / "response.txt").write_text(baseline_result.response)
    save_timing(baseline_result, baseline_dir / "timing.json")
    print(
        f"  Baseline complete ({baseline_result.total_duration_seconds:.1f}s, "
        f"{baseline_result.total_tokens:,} tokens, ${baseline_result.cost_usd:.4f})"
    )

    # Phase 2: GREEN — With skill
    print(f"GREEN phase: Running with skill '{skill_name}'...")
    skill_result = run_claude(
        prompt=scenario_prompt,
        skill_path=skill_path,
        timeout=timeout,
        model=model,
    )
    (with_skill_dir / "response.txt").write_text(skill_result.response)
    save_timing(skill_result, with_skill_dir / "timing.json")
    print(
        f"  With-skill complete ({skill_result.total_duration_seconds:.1f}s, "
        f"{skill_result.total_tokens:,} tokens, ${skill_result.cost_usd:.4f})"
    )

    # Write summary with full metrics
    summary = {
        "baseline": {
            "response_length": len(baseline_result.response),
            "duration_seconds": baseline_result.total_duration_seconds,
            "total_tokens": baseline_result.total_tokens,
            "input_tokens": baseline_result.input_tokens,
            "output_tokens": baseline_result.output_tokens,
            "cost_usd": baseline_result.cost_usd,
            "num_turns": baseline_result.num_turns,
        },
        "with_skill": {
            "response_length": len(skill_result.response),
            "duration_seconds": skill_result.total_duration_seconds,
            "total_tokens": skill_result.total_tokens,
            "input_tokens": skill_result.input_tokens,
            "output_tokens": skill_result.output_tokens,
            "cost_usd": skill_result.cost_usd,
            "num_turns": skill_result.num_turns,
        },
        "delta": {
            "tokens": skill_result.total_tokens - baseline_result.total_tokens,
            "cost_usd": round(skill_result.cost_usd - baseline_result.cost_usd, 6),
            "duration_seconds": round(
                skill_result.total_duration_seconds - baseline_result.total_duration_seconds, 2
            ),
        },
    }
    (cycle_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    # Print comparison table
    print(f"\n{'='*60}")
    print(f"  TDD Cycle Results: {skill_name}")
    print(f"{'='*60}")
    print(f"  {'Metric':<20} {'Baseline':>12} {'With Skill':>12} {'Delta':>12}")
    print(f"  {'-'*20} {'-'*12} {'-'*12} {'-'*12}")
    print(
        f"  {'Tokens':<20} {baseline_result.total_tokens:>12,} "
        f"{skill_result.total_tokens:>12,} "
        f"{summary['delta']['tokens']:>+12,}"
    )
    delta_cost = summary["delta"]["cost_usd"]
    print(
        f"  {'Cost':<20} {'$' + f'{baseline_result.cost_usd:.4f}':>12} "
        f"{'$' + f'{skill_result.cost_usd:.4f}':>12} "
        f"{'$' + f'{delta_cost:.4f}':>12}"
    )
    print(
        f"  {'Duration':<20} {baseline_result.total_duration_seconds:>11.1f}s "
        f"{skill_result.total_duration_seconds:>11.1f}s "
        f"{summary['delta']['duration_seconds']:>+11.1f}s"
    )
    print(
        f"  {'Turns':<20} {baseline_result.num_turns:>12} "
        f"{skill_result.num_turns:>12} "
        f"{skill_result.num_turns - baseline_result.num_turns:>+12}"
    )
    print(f"{'='*60}")
    print(f"\nResults saved to: {cycle_dir}")
    print(f"  baseline/response.txt   — agent without skill")
    print(f"  with_skill/response.txt — agent with skill")

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

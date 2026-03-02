#!/usr/bin/env python3
"""Run A/B output comparisons for a skill.

Executes eval prompts via `claude -p` both with and without a skill,
saving outputs to the workspace directory structure.

Usage:
    python -m scripts.run_comparison \\
        --skill-path /path/to/my-skill \\
        --evals evals/evals.json \\
        --workspace ./my-skill-workspace/iteration-1 \\
        [--model claude-sonnet-4-20250514]

    # Compare two skill versions (old vs new)
    python -m scripts.run_comparison \\
        --skill-path /path/to/my-skill-v2 \\
        --baseline-skill /path/to/my-skill-v1 \\
        --evals evals/evals.json \\
        --workspace ./my-skill-workspace/iteration-1

Expects workspace to be initialized with init_workspace.py first.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path


def run_single_eval(
    prompt: str,
    skill_path: Path | None,
    output_dir: Path,
    timeout: int,
    model: str | None = None,
) -> dict:
    """Run a single eval prompt via `claude -p` and save outputs.

    Returns:
        dict with duration_seconds, exit_code, response_length
    """
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
            cwd=str(output_dir),
            env=env,
        )
        duration = time.monotonic() - start
    except subprocess.TimeoutExpired:
        (output_dir / "response.txt").write_text(f"[TIMEOUT after {timeout}s]")
        return {
            "duration_seconds": timeout,
            "exit_code": -1,
            "response_length": 0,
        }

    response_text = result.stdout
    try:
        parsed = json.loads(response_text)
        response_text = parsed.get("result", response_text)
    except (json.JSONDecodeError, TypeError):
        pass

    (output_dir / "response.txt").write_text(response_text)

    # Save timing
    timing = {
        "duration_ms": int(duration * 1000),
        "total_duration_seconds": round(duration, 2),
    }
    (output_dir.parent / "timing.json").write_text(json.dumps(timing, indent=2))

    return {
        "duration_seconds": round(duration, 2),
        "exit_code": result.returncode,
        "response_length": len(response_text),
    }


def run_comparison(
    skill_path: Path,
    baseline_skill: Path | None,
    evals_path: Path,
    workspace: Path,
    timeout: int,
    model: str | None = None,
    max_workers: int = 4,
) -> None:
    """Run A/B comparisons for all evals in the workspace."""
    evals_data = json.loads(evals_path.read_text())
    eval_list = evals_data.get("evals", [])

    if not eval_list:
        print("Error: No evals found", file=sys.stderr)
        sys.exit(1)

    # Discover eval directories
    eval_dirs = sorted(d for d in workspace.iterdir() if d.is_dir() and d.name.startswith("eval-"))
    if not eval_dirs:
        print(
            f"Error: No eval-* directories found in {workspace}. "
            "Run init_workspace first.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Build run tasks
    tasks = []
    for eval_dir in eval_dirs:
        metadata_path = eval_dir / "eval_metadata.json"
        if not metadata_path.exists():
            print(f"Warning: No eval_metadata.json in {eval_dir}, skipping")
            continue

        metadata = json.loads(metadata_path.read_text())
        prompt = metadata.get("prompt", "")
        if not prompt:
            print(f"Warning: Empty prompt in {eval_dir}, skipping")
            continue

        # With-skill config
        with_skill_dir = eval_dir / "with_skill" / "outputs"
        if with_skill_dir.exists():
            tasks.append(
                (prompt, skill_path, with_skill_dir, f"{eval_dir.name}/with_skill")
            )

        # Baseline config
        if baseline_skill:
            old_skill_dir = eval_dir / "old_skill" / "outputs"
            if old_skill_dir.exists():
                tasks.append(
                    (prompt, baseline_skill, old_skill_dir, f"{eval_dir.name}/old_skill")
                )
        else:
            without_skill_dir = eval_dir / "without_skill" / "outputs"
            if without_skill_dir.exists():
                tasks.append(
                    (prompt, None, without_skill_dir, f"{eval_dir.name}/without_skill")
                )

    if not tasks:
        print("Error: No runnable eval tasks found", file=sys.stderr)
        sys.exit(1)

    print(f"Running {len(tasks)} eval tasks ({max_workers} workers)...\n")

    results = {}
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_label = {}
        for prompt, sp, output_dir, label in tasks:
            future = executor.submit(
                run_single_eval, prompt, sp, output_dir, timeout, model
            )
            future_to_label[future] = label

        for future in as_completed(future_to_label):
            label = future_to_label[future]
            try:
                result = future.result()
                status = "OK" if result["exit_code"] == 0 else f"EXIT={result['exit_code']}"
                print(
                    f"  [{status}] {label} "
                    f"({result['duration_seconds']:.1f}s, "
                    f"{result['response_length']} chars)"
                )
                results[label] = result
            except Exception as e:
                print(f"  [ERROR] {label}: {e}")
                results[label] = {"error": str(e)}

    # Write run summary
    summary_path = workspace / "run_summary.json"
    summary_path.write_text(json.dumps(results, indent=2))
    print(f"\nRun summary saved to: {summary_path}")
    print(f"Next: Grade results with the grader subagent, then aggregate benchmarks.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run A/B output comparisons for a skill"
    )
    parser.add_argument(
        "--skill-path",
        type=Path,
        required=True,
        help="Path to the skill directory (must contain SKILL.md)",
    )
    parser.add_argument(
        "--baseline-skill",
        type=Path,
        default=None,
        help="Path to baseline skill (for old vs new comparison). "
        "If not provided, baseline runs without any skill.",
    )
    parser.add_argument(
        "--evals",
        type=Path,
        required=True,
        help="Path to evals.json file",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        required=True,
        help="Path to workspace iteration directory (e.g., ./workspace/iteration-1)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Timeout per run in seconds (default: 300)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model to use for claude -p",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)",
    )
    args = parser.parse_args()

    if not (args.skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {args.skill_path}", file=sys.stderr)
        sys.exit(1)

    if not args.workspace.is_dir():
        print(
            f"Error: Workspace not found: {args.workspace}. Run init_workspace first.",
            file=sys.stderr,
        )
        sys.exit(1)

    run_comparison(
        skill_path=args.skill_path,
        baseline_skill=args.baseline_skill,
        evals_path=args.evals,
        workspace=args.workspace,
        timeout=args.timeout,
        model=args.model,
        max_workers=args.max_workers,
    )


if __name__ == "__main__":
    main()

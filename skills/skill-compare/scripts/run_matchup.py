#!/usr/bin/env python3
"""Run both skills against all evals in a matchup workspace.

Executes eval prompts via `claude -p` with each skill, saving outputs
to the run directory structure created by init_matchup.py.

Usage:
    python -m scripts.run_matchup \\
        --workspace ./matchup-workspace/iteration-1

    python -m scripts.run_matchup \\
        --workspace ./matchup-workspace/iteration-1 \\
        --runs 3 --timeout 300 --model claude-sonnet-4-20250514 --max-workers 4

Expects workspace to be initialized with init_matchup.py first.
"""

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# Add _shared to import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "_shared"))
from claude_runner import run_claude, save_timing  # noqa: E402


def run_single_eval(
    prompt: str,
    skill_path: Path,
    output_dir: Path,
    timeout: int,
    model: str | None = None,
) -> dict:
    """Run a single eval prompt via `claude -p` and save outputs.

    Returns:
        dict with duration_seconds, exit_code, response_length, tokens, cost_usd
    """
    result = run_claude(
        prompt=prompt,
        skill_path=skill_path,
        timeout=timeout,
        model=model,
        cwd=output_dir,
    )

    (output_dir / "response.txt").write_text(result.response)
    save_timing(result, output_dir.parent / "timing.json")

    return {
        "duration_seconds": result.total_duration_seconds,
        "exit_code": result.exit_code,
        "response_length": len(result.response),
        "total_tokens": result.total_tokens,
        "cost_usd": result.cost_usd,
        "num_turns": result.num_turns,
    }


def run_matchup(
    workspace: Path,
    runs: int | None = None,
    timeout: int = 300,
    model: str | None = None,
    max_workers: int = 4,
) -> None:
    """Run both skills against all evals in the matchup workspace."""
    matchup_path = workspace / "matchup.json"
    if not matchup_path.exists():
        print(
            f"Error: No matchup.json found in {workspace}. "
            "Run init_matchup first.",
            file=sys.stderr,
        )
        sys.exit(1)

    matchup = json.loads(matchup_path.read_text())
    skill_a_path = Path(matchup["skill_a"]["path"])
    skill_b_path = Path(matchup["skill_b"]["path"])
    config_a = matchup["config_a"]
    config_b = matchup["config_b"]
    runs_per_eval = runs or matchup.get("runs_per_eval", 3)

    # Discover eval directories
    eval_dirs = sorted(
        d for d in workspace.iterdir() if d.is_dir() and d.name.startswith("eval-")
    )
    if not eval_dirs:
        print(
            f"Error: No eval-* directories found in {workspace}. "
            "Run init_matchup first.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Build task list: (prompt, skill_path, output_dir, label)
    tasks: list[tuple[str, Path, Path, str]] = []
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

        for config, skill_path in [
            (config_a, skill_a_path),
            (config_b, skill_b_path),
        ]:
            for run_num in range(1, runs_per_eval + 1):
                output_dir = eval_dir / config / f"run-{run_num}" / "outputs"
                output_dir.mkdir(parents=True, exist_ok=True)
                label = f"{eval_dir.name}/{config}/run-{run_num}"
                tasks.append((prompt, skill_path, output_dir, label))

    if not tasks:
        print("Error: No runnable eval tasks found", file=sys.stderr)
        sys.exit(1)

    print(f"Running {len(tasks)} eval tasks ({max_workers} workers)...")
    print(f"  Skill A: {matchup['skill_a']['name']} -> {skill_a_path}")
    print(f"  Skill B: {matchup['skill_b']['name']} -> {skill_b_path}")
    print()

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
                status = (
                    "OK"
                    if result["exit_code"] == 0
                    else f"EXIT={result['exit_code']}"
                )
                tokens = result.get("total_tokens", 0)
                cost = result.get("cost_usd", 0)
                print(
                    f"  [{status}] {label} "
                    f"({result['duration_seconds']:.1f}s, "
                    f"{tokens:,} tokens, "
                    f"${cost:.4f}, "
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
    print(
        "Next: Grade results with the grader subagent, "
        "then aggregate benchmarks with writing-skills/scripts/aggregate_benchmark."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run both skills against all evals in a matchup workspace"
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        required=True,
        help="Path to workspace iteration directory (e.g., ./matchup-workspace/iteration-1)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=None,
        help="Override runs per eval (default: from matchup.json)",
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

    if not args.workspace.is_dir():
        print(
            f"Error: Workspace not found: {args.workspace}. Run init_matchup first.",
            file=sys.stderr,
        )
        sys.exit(1)

    run_matchup(
        workspace=args.workspace,
        runs=args.runs,
        timeout=args.timeout,
        model=args.model,
        max_workers=args.max_workers,
    )


if __name__ == "__main__":
    main()

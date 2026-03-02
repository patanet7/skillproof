#!/usr/bin/env python3
"""Summarize matchup results into a structured report.

Reads benchmark.json (from aggregate_benchmark) and comparison.json files
(from blind comparator), tallies wins, and produces a matchup report.

Usage:
    python -m scripts.summarize_matchup --workspace ./matchup-workspace/iteration-1

Expects:
    - matchup.json (from init_matchup)
    - benchmark.json (from aggregate_benchmark)
    - eval-*/comparison.json (from blind comparator agent, optional)
"""

import argparse
import json
import sys
from pathlib import Path


def load_matchup(workspace: Path) -> dict:
    """Load matchup metadata."""
    matchup_path = workspace / "matchup.json"
    if not matchup_path.exists():
        print(f"Error: No matchup.json found in {workspace}", file=sys.stderr)
        sys.exit(1)
    return json.loads(matchup_path.read_text())


def load_benchmark(workspace: Path) -> dict | None:
    """Load benchmark results if available."""
    benchmark_path = workspace / "benchmark.json"
    if not benchmark_path.exists():
        return None
    return json.loads(benchmark_path.read_text())


def discover_comparisons(workspace: Path) -> list[dict]:
    """Find all comparison.json files from blind comparator."""
    comparisons = []
    for eval_dir in sorted(workspace.iterdir()):
        if not eval_dir.is_dir() or not eval_dir.name.startswith("eval-"):
            continue
        comparison_path = eval_dir / "comparison.json"
        if comparison_path.exists():
            data = json.loads(comparison_path.read_text())
            data["_eval_name"] = eval_dir.name
            comparisons.append(data)
    return comparisons


def tally_blind_wins(
    comparisons: list[dict], config_a: str, config_b: str
) -> dict:
    """Tally blind comparison wins for each config.

    The comparator labels outputs as A/B. The matchup tracks which config
    was assigned to which label per eval (via randomized assignment).
    Falls back to positional: first config = A, second = B.
    """
    wins = {config_a: 0, config_b: 0, "tie": 0}
    details = []

    for comp in comparisons:
        winner_label = comp.get("winner", "").upper()
        eval_name = comp.get("_eval_name", "unknown")

        # Check for explicit config mapping (set during blind comparison step)
        label_map = comp.get("_label_map", {"A": config_a, "B": config_b})

        if winner_label == "TIE":
            wins["tie"] += 1
            details.append({"eval": eval_name, "winner": "tie", "config": None})
        elif winner_label in ("A", "B"):
            winning_config = label_map.get(winner_label, config_a)
            wins[winning_config] = wins.get(winning_config, 0) + 1
            details.append(
                {"eval": eval_name, "winner": winner_label, "config": winning_config}
            )
        else:
            wins["tie"] += 1
            details.append(
                {"eval": eval_name, "winner": "unknown", "config": None}
            )

    return {"wins": wins, "details": details}


def determine_overall_winner(
    tally: dict, benchmark: dict | None, config_a: str, config_b: str
) -> tuple[str, str]:
    """Determine overall winner. Blind wins primary; pass_rate delta tiebreaker."""
    wins = tally["wins"]
    a_wins = wins.get(config_a, 0)
    b_wins = wins.get(config_b, 0)

    if a_wins > b_wins:
        return config_a, f"Won {a_wins}-{b_wins} in blind comparison"
    if b_wins > a_wins:
        return config_b, f"Won {b_wins}-{a_wins} in blind comparison"

    # Tied on blind wins — use pass_rate delta as tiebreaker
    if benchmark and "run_summary" in benchmark:
        summary = benchmark["run_summary"]
        a_rate = summary.get(config_a, {}).get("pass_rate", {}).get("mean", 0)
        b_rate = summary.get(config_b, {}).get("pass_rate", {}).get("mean", 0)

        if a_rate > b_rate:
            return config_a, f"Tied {a_wins}-{b_wins} blind; higher pass_rate ({a_rate:.2f} vs {b_rate:.2f})"
        if b_rate > a_rate:
            return config_b, f"Tied {a_wins}-{b_wins} blind; higher pass_rate ({b_rate:.2f} vs {a_rate:.2f})"

    return "tie", f"Tied {a_wins}-{b_wins} in blind comparison, no pass_rate difference"


def format_report(
    matchup: dict,
    benchmark: dict | None,
    tally: dict,
    winner: str,
    reason: str,
) -> str:
    """Generate the matchup report markdown."""
    config_a = matchup["config_a"]
    config_b = matchup["config_b"]
    name_a = matchup["skill_a"]["name"]
    name_b = matchup["skill_b"]["name"]

    lines = [
        f"# Matchup Report: {name_a} vs {name_b}",
        "",
        f"**Winner: {winner}** — {reason}",
        "",
        "## Skills",
        "",
        f"| | Skill A | Skill B |",
        f"|---|---------|---------|",
        f"| **Name** | {name_a} | {name_b} |",
        f"| **Config** | `{config_a}` | `{config_b}` |",
        f"| **Path** | `{matchup['skill_a']['path']}` | `{matchup['skill_b']['path']}` |",
        "",
    ]

    # Quantitative comparison from benchmark
    if benchmark and "run_summary" in benchmark:
        summary = benchmark["run_summary"]
        lines.append("## Quantitative Comparison")
        lines.append("")
        lines.append(f"| Metric | {config_a} | {config_b} | Delta |")
        lines.append("|--------|-----------|-----------|-------|")

        for metric in ("pass_rate", "time_seconds", "tokens"):
            a_stats = summary.get(config_a, {}).get(metric, {})
            b_stats = summary.get(config_b, {}).get(metric, {})
            a_mean = a_stats.get("mean", 0)
            b_mean = b_stats.get("mean", 0)
            a_std = a_stats.get("stddev", 0)
            b_std = b_stats.get("stddev", 0)
            delta = a_mean - b_mean

            if metric == "pass_rate":
                a_str = f"{a_mean:.2f} +/- {a_std:.2f}"
                b_str = f"{b_mean:.2f} +/- {b_std:.2f}"
                d_str = f"{delta:+.2f}"
            elif metric == "time_seconds":
                a_str = f"{a_mean:.1f}s +/- {a_std:.1f}s"
                b_str = f"{b_mean:.1f}s +/- {b_std:.1f}s"
                d_str = f"{delta:+.1f}s"
            else:
                a_str = f"{a_mean:.0f} +/- {a_std:.0f}"
                b_str = f"{b_mean:.0f} +/- {b_std:.0f}"
                d_str = f"{delta:+.0f}"

            lines.append(f"| **{metric}** | {a_str} | {b_str} | {d_str} |")

        lines.append("")

    # Blind comparison tally
    if tally["details"]:
        wins = tally["wins"]
        lines.append("## Blind Comparison")
        lines.append("")
        lines.append(f"| Config | Wins |")
        lines.append(f"|--------|------|")
        lines.append(f"| **{config_a}** | {wins.get(config_a, 0)} |")
        lines.append(f"| **{config_b}** | {wins.get(config_b, 0)} |")
        lines.append(f"| **Tie** | {wins.get('tie', 0)} |")
        lines.append("")

        # Per-eval results
        lines.append("### Per-Eval Results")
        lines.append("")
        lines.append("| Eval | Winner | Config |")
        lines.append("|------|--------|--------|")
        for detail in tally["details"]:
            config_str = detail["config"] or "—"
            lines.append(
                f"| {detail['eval']} | {detail['winner']} | {config_str} |"
            )
        lines.append("")

    lines.append(f"---")
    lines.append(f"*Generated from matchup workspace. Created: {matchup.get('created_at', 'unknown')}*")

    return "\n".join(lines)


def summarize_matchup(workspace: Path) -> None:
    """Produce a structured matchup report from results."""
    matchup = load_matchup(workspace)
    benchmark = load_benchmark(workspace)
    comparisons = discover_comparisons(workspace)

    config_a = matchup["config_a"]
    config_b = matchup["config_b"]

    tally = tally_blind_wins(comparisons, config_a, config_b)
    winner, reason = determine_overall_winner(tally, benchmark, config_a, config_b)

    report = format_report(matchup, benchmark, tally, winner, reason)

    report_path = workspace / "matchup_report.md"
    report_path.write_text(report)
    print(f"Matchup report saved to: {report_path}")
    print(f"  Winner: {winner}")
    print(f"  Reason: {reason}")

    if not benchmark:
        print(
            "\n  Note: No benchmark.json found. Run aggregate_benchmark "
            "from writing-skills first for quantitative comparison."
        )
    if not comparisons:
        print(
            "\n  Note: No comparison.json files found. Run the comparator "
            "agent per eval for blind A/B comparison."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize matchup results into a structured report"
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        required=True,
        help="Path to workspace iteration directory (e.g., ./matchup-workspace/iteration-1)",
    )
    args = parser.parse_args()

    if not args.workspace.is_dir():
        print(
            f"Error: Workspace not found: {args.workspace}",
            file=sys.stderr,
        )
        sys.exit(1)

    summarize_matchup(args.workspace)


if __name__ == "__main__":
    main()

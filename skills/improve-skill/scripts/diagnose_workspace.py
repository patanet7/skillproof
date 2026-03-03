#!/usr/bin/env python3
"""Evidence extraction from a testing workspace (skill-testing-output or skill-compare).

Scans eval directories for grading failures, user feedback, comparison losses,
and benchmark regressions to produce a structured diagnosis of what's going wrong.

Usage:
    python -m scripts.diagnose_workspace /path/to/workspace/iteration-1 [--output diagnosis.json]
"""

import argparse
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Workspace type detection
# ---------------------------------------------------------------------------

def detect_workspace_type(workspace: Path) -> str:
    """Detect whether this is a skill-compare or skill-testing-output workspace."""
    if (workspace / "matchup.json").exists():
        return "skill-compare"
    return "skill-testing-output"


# ---------------------------------------------------------------------------
# Grading extraction
# ---------------------------------------------------------------------------

def _extract_grading(grading_path: Path) -> list[dict]:
    """Extract individual assertion results from a grading.json file."""
    data = json.loads(grading_path.read_text())
    expectations = data.get("expectations", [])
    return [
        {
            "text": exp.get("text", ""),
            "passed": exp.get("passed", False),
            "evidence": exp.get("evidence", ""),
        }
        for exp in expectations
    ]


def _scan_config_dir(config_dir: Path) -> list[dict]:
    """Scan a config directory (e.g., with_skill/) for run grading results.

    Handles both flat layout (grading.json directly) and run-N/ layout.
    """
    results = []

    # Direct grading.json
    direct = config_dir / "grading.json"
    if direct.exists():
        results.append({
            "run": config_dir.name,
            "grading_path": str(direct),
            "assertions": _extract_grading(direct),
        })

    # run-N/ subdirectories
    for run_dir in sorted(config_dir.iterdir()):
        if run_dir.is_dir() and run_dir.name.startswith("run-"):
            grading = run_dir / "grading.json"
            if grading.exists():
                results.append({
                    "run": run_dir.name,
                    "grading_path": str(grading),
                    "assertions": _extract_grading(grading),
                })

    return results


# ---------------------------------------------------------------------------
# Eval scanning
# ---------------------------------------------------------------------------

def scan_eval(eval_dir: Path, workspace_type: str) -> dict:
    """Scan a single eval directory for grading and comparison results."""
    eval_name = eval_dir.name
    result: dict = {
        "eval_name": eval_name,
        "configs": {},
        "comparison": None,
        "eval_metadata": None,
    }

    # Read eval_metadata.json if present
    metadata_path = eval_dir / "eval_metadata.json"
    if metadata_path.exists():
        result["eval_metadata"] = json.loads(metadata_path.read_text())

    # Read comparison.json if present
    comparison_path = eval_dir / "comparison.json"
    if comparison_path.exists():
        result["comparison"] = json.loads(comparison_path.read_text())

    # Scan config directories
    for item in sorted(eval_dir.iterdir()):
        if item.is_dir() and not item.name.startswith("."):
            runs = _scan_config_dir(item)
            if runs:
                result["configs"][item.name] = runs

    return result


# ---------------------------------------------------------------------------
# Aggregation: failing/inconsistent assertions
# ---------------------------------------------------------------------------

def aggregate_assertions(evals: list[dict]) -> tuple[list[dict], list[dict]]:
    """Aggregate assertion results across all evals and runs.

    Returns (always_failing, inconsistent) assertion lists.
    """
    # Group by (eval_name, assertion_text, config_name)
    assertion_stats: dict[tuple[str, str, str], dict] = {}

    for eval_data in evals:
        eval_name = eval_data["eval_name"]
        for config_name, runs in eval_data["configs"].items():
            for run in runs:
                for assertion in run["assertions"]:
                    key = (eval_name, assertion["text"], config_name)
                    if key not in assertion_stats:
                        assertion_stats[key] = {
                            "total": 0,
                            "failures": 0,
                            "evidence": [],
                        }
                    assertion_stats[key]["total"] += 1
                    if not assertion["passed"]:
                        assertion_stats[key]["failures"] += 1
                        if assertion["evidence"]:
                            assertion_stats[key]["evidence"].append(assertion["evidence"])

    always_failing = []
    inconsistent = []

    for (eval_name, text, config_name), stats in sorted(assertion_stats.items()):
        if stats["failures"] == 0:
            continue

        fail_rate = stats["failures"] / stats["total"]
        entry = {
            "assertion": text,
            "eval": eval_name,
            "fail_rate": round(fail_rate, 2),
            "configs": [config_name],
            "evidence": stats["evidence"][:3],  # Cap evidence samples
        }

        if fail_rate >= 1.0:
            always_failing.append(entry)
        elif fail_rate > 0:
            inconsistent.append(entry)

    return always_failing, inconsistent


# ---------------------------------------------------------------------------
# Comparison extraction
# ---------------------------------------------------------------------------

def extract_comparison_losses(evals: list[dict]) -> list[dict]:
    """Extract cases where the skill lost a blind A/B comparison."""
    losses = []
    for eval_data in evals:
        comp = eval_data.get("comparison")
        if not comp:
            continue

        winner = comp.get("winner", "")
        reasoning = comp.get("reasoning", "")

        # In skill-compare, we report any comparison result
        if winner:
            losses.append({
                "eval": eval_data["eval_name"],
                "winner": winner,
                "reasoning": reasoning,
            })

    return losses


# ---------------------------------------------------------------------------
# Feedback extraction
# ---------------------------------------------------------------------------

def extract_feedback(workspace: Path) -> list[dict]:
    """Extract user complaints from feedback.json."""
    feedback_path = workspace / "feedback.json"
    if not feedback_path.exists():
        return []

    data = json.loads(feedback_path.read_text())

    complaints = []
    # feedback.json can be a list of entries or a dict with a "reviews" key
    entries = data if isinstance(data, list) else data.get("reviews", [])

    for entry in entries:
        feedback_text = ""
        if isinstance(entry, str):
            feedback_text = entry
        elif isinstance(entry, dict):
            feedback_text = entry.get("feedback", "") or entry.get("review", "") or entry.get("text", "")

        if feedback_text and feedback_text.strip():
            run_id = entry.get("run_id", "") if isinstance(entry, dict) else ""
            complaints.append({
                "run_id": run_id,
                "feedback": feedback_text.strip(),
            })

    return complaints


# ---------------------------------------------------------------------------
# Permission denial extraction
# ---------------------------------------------------------------------------

def extract_permission_denials(workspace: Path) -> list[dict]:
    """Extract permission denials from timing.json files across all runs.

    Permission denials indicate tools the agent tried to use but couldn't,
    which directly informs what allowed-tools entries the skill needs.
    """
    denials_by_tool: dict[str, dict] = {}

    for timing_path in workspace.rglob("timing.json"):
        try:
            data = json.loads(timing_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        for denial in data.get("permission_denials", []):
            tool_name = denial.get("tool_name", "unknown")
            if tool_name not in denials_by_tool:
                denials_by_tool[tool_name] = {
                    "tool_name": tool_name,
                    "count": 0,
                    "examples": [],
                }
            denials_by_tool[tool_name]["count"] += 1
            # Keep a few examples of what the agent tried
            if len(denials_by_tool[tool_name]["examples"]) < 3:
                example = {
                    "tool_input": denial.get("tool_input", {}),
                    "source": str(timing_path.relative_to(workspace)),
                }
                denials_by_tool[tool_name]["examples"].append(example)

    return sorted(denials_by_tool.values(), key=lambda d: d["count"], reverse=True)


# ---------------------------------------------------------------------------
# Token/cost extraction
# ---------------------------------------------------------------------------

def extract_token_summary(workspace: Path) -> dict:
    """Extract token and cost totals from timing.json files for summary reporting."""
    totals: dict[str, dict] = {}

    for eval_dir in sorted(workspace.iterdir()):
        if not (eval_dir.is_dir() and eval_dir.name.startswith("eval-")):
            continue

        for config_dir in sorted(eval_dir.iterdir()):
            if not config_dir.is_dir():
                continue

            config_name = config_dir.name
            if config_name not in totals:
                totals[config_name] = {
                    "total_tokens": [],
                    "cost_usd": [],
                    "num_turns": [],
                }

            # Scan timing.json in config dir or run-N/ subdirs
            for timing_path in config_dir.rglob("timing.json"):
                try:
                    data = json.loads(timing_path.read_text())
                except (json.JSONDecodeError, OSError):
                    continue
                if data.get("total_tokens"):
                    totals[config_name]["total_tokens"].append(data["total_tokens"])
                if data.get("cost_usd"):
                    totals[config_name]["cost_usd"].append(data["cost_usd"])
                if data.get("num_turns"):
                    totals[config_name]["num_turns"].append(data["num_turns"])

    # Compute averages
    summary = {}
    for config, metrics in totals.items():
        summary[config] = {}
        for metric, values in metrics.items():
            if values:
                summary[config][metric] = {
                    "mean": round(sum(values) / len(values), 2),
                    "total": round(sum(values), 2),
                    "count": len(values),
                }
    return summary


# ---------------------------------------------------------------------------
# Benchmark extraction
# ---------------------------------------------------------------------------

def extract_benchmark(workspace: Path) -> dict | None:
    """Extract benchmark summary from benchmark.json."""
    benchmark_path = workspace / "benchmark.json"
    if not benchmark_path.exists():
        return None

    data = json.loads(benchmark_path.read_text())
    return data.get("run_summary", None)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def diagnose_workspace(workspace: Path) -> dict:
    """Run full diagnosis on a workspace and return the report."""
    workspace_type = detect_workspace_type(workspace)

    # Scan all eval directories
    evals = []
    eval_count = 0
    run_count = 0

    for item in sorted(workspace.iterdir()):
        if item.is_dir() and item.name.startswith("eval-"):
            eval_data = scan_eval(item, workspace_type)
            evals.append(eval_data)
            eval_count += 1
            for config_runs in eval_data["configs"].values():
                run_count += len(config_runs)

    # Aggregate
    failing, inconsistent = aggregate_assertions(evals)
    comparison_losses = extract_comparison_losses(evals)
    complaints = extract_feedback(workspace)
    benchmark_summary = extract_benchmark(workspace)
    permission_denials = extract_permission_denials(workspace)
    token_summary = extract_token_summary(workspace)

    return {
        "workspace_path": str(workspace),
        "workspace_type": workspace_type,
        "evals_analyzed": eval_count,
        "runs_analyzed": run_count,
        "failing_assertions": failing,
        "inconsistent_assertions": inconsistent,
        "user_complaints": complaints,
        "comparison_losses": comparison_losses,
        "permission_denials": permission_denials,
        "token_summary": token_summary,
        "benchmark_summary": benchmark_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose issues from a testing workspace")
    parser.add_argument("workspace", type=Path, help="Path to workspace iteration directory")
    parser.add_argument("--output", type=Path, default=None, help="Output path for diagnosis.json")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        print(f"Error: {workspace} is not a directory", file=sys.stderr)
        sys.exit(1)

    report = diagnose_workspace(workspace)

    output_path = args.output or Path("diagnosis.json")
    output_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Diagnosis written to {output_path}")

    # Print summary
    print(f"  Workspace type: {report['workspace_type']}")
    print(f"  Evals analyzed: {report['evals_analyzed']}")
    print(f"  Runs analyzed: {report['runs_analyzed']}")
    print(f"  Always-failing assertions: {len(report['failing_assertions'])}")
    print(f"  Inconsistent assertions: {len(report['inconsistent_assertions'])}")
    print(f"  User complaints: {len(report['user_complaints'])}")
    print(f"  Comparison losses: {len(report['comparison_losses'])}")

    # Permission denials — actionable for allowed-tools
    denials = report.get("permission_denials", [])
    if denials:
        print(f"\n  Permission denials ({sum(d['count'] for d in denials)} total):")
        for d in denials:
            print(f"    {d['tool_name']}: {d['count']}x")
            for ex in d["examples"]:
                tool_input = ex.get("tool_input", {})
                if isinstance(tool_input, dict) and "command" in tool_input:
                    print(f"      e.g. {tool_input['command'][:80]}")
        print("    -> Consider adding these to allowed-tools in SKILL.md frontmatter")

    # Token summary
    token_summary = report.get("token_summary", {})
    if token_summary:
        print(f"\n  Token usage by config:")
        for config, metrics in token_summary.items():
            tokens = metrics.get("total_tokens", {})
            cost = metrics.get("cost_usd", {})
            print(
                f"    {config}: "
                f"{tokens.get('mean', 0):,.0f} tokens/run avg, "
                f"${cost.get('total', 0):.4f} total cost"
            )


if __name__ == "__main__":
    main()

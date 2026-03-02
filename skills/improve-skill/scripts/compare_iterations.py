#!/usr/bin/env python3
"""Compare two iteration diagnoses to measure improvement.

Takes diagnosis files from before and after improvement, then produces a
comparison report showing what was resolved, what regressed, and what's
unchanged — with quantitative deltas.

Usage:
    python -m scripts.compare_iterations \\
        --before diagnosis_v1.json \\
        --after diagnosis_v2.json \\
        --output comparison_report.json
"""

import argparse
import json
import sys
from pathlib import Path


def _assertion_key(item: dict) -> str:
    """Stable key for deduplicating assertions across iterations."""
    return f"{item.get('eval', '')}::{item.get('assertion', '')}"


def compare_assertions(
    before_failing: list[dict],
    before_inconsistent: list[dict],
    after_failing: list[dict],
    after_inconsistent: list[dict],
) -> dict:
    """Compare assertion status between iterations."""
    before_fail_keys = {_assertion_key(a) for a in before_failing}
    before_incon_keys = {_assertion_key(a) for a in before_inconsistent}
    after_fail_keys = {_assertion_key(a) for a in after_failing}
    after_incon_keys = {_assertion_key(a) for a in after_inconsistent}

    all_before = before_fail_keys | before_incon_keys
    all_after = after_fail_keys | after_incon_keys

    resolved = sorted(all_before - all_after)
    new_failures = sorted(all_after - all_before)
    persistent = sorted(all_before & all_after)

    # Classify changes in severity
    improved = []
    regressed = []
    for key in persistent:
        was_failing = key in before_fail_keys
        now_failing = key in after_fail_keys
        if was_failing and not now_failing:
            improved.append(key)
        elif not was_failing and now_failing:
            regressed.append(key)

    return {
        "resolved": resolved,
        "new_failures": new_failures,
        "persistent": persistent,
        "improved": improved,
        "regressed": regressed,
        "summary": {
            "resolved_count": len(resolved),
            "new_failure_count": len(new_failures),
            "persistent_count": len(persistent),
            "improved_count": len(improved),
            "regressed_count": len(regressed),
        },
    }


def compare_benchmarks(before: dict | None, after: dict | None) -> list[dict]:
    """Compare benchmark pass rates between iterations."""
    if not before or not after:
        return []

    deltas = []
    all_configs = set(before.keys()) | set(after.keys())

    for config in sorted(all_configs):
        before_stats = before.get(config, {})
        after_stats = after.get(config, {})

        before_pr = before_stats.get("pass_rate", {})
        after_pr = after_stats.get("pass_rate", {})

        before_mean = before_pr.get("mean") if isinstance(before_pr, dict) else None
        after_mean = after_pr.get("mean") if isinstance(after_pr, dict) else None

        if before_mean is not None and after_mean is not None:
            delta = after_mean - before_mean
            deltas.append({
                "config": config,
                "before_pass_rate": round(before_mean, 3),
                "after_pass_rate": round(after_mean, 3),
                "delta": round(delta, 3),
                "improved": delta > 0.01,
                "regressed": delta < -0.01,
            })

    return deltas


def render_markdown(report: dict) -> str:
    """Render comparison report as markdown."""
    lines = ["# Iteration Comparison Report", ""]

    # Overall verdict
    a = report["assertions"]["summary"]
    lines.append(f"**Resolved:** {a['resolved_count']} issues fixed  ")
    lines.append(f"**New failures:** {a['new_failure_count']} regressions  ")
    lines.append(f"**Persistent:** {a['persistent_count']} remaining ({a['improved_count']} improved severity)  ")
    lines.append("")

    # Resolved
    if report["assertions"]["resolved"]:
        lines.append("## Resolved Issues")
        lines.append("")
        for key in report["assertions"]["resolved"]:
            lines.append(f"- {key}")
        lines.append("")

    # New failures (regressions)
    if report["assertions"]["new_failures"]:
        lines.append("## New Failures (Regressions)")
        lines.append("")
        for key in report["assertions"]["new_failures"]:
            lines.append(f"- {key}")
        lines.append("")

    # Persistent
    if report["assertions"]["persistent"]:
        lines.append("## Persistent Issues")
        lines.append("")
        for key in report["assertions"]["persistent"]:
            severity = ""
            if key in report["assertions"]["improved"]:
                severity = " (improved severity)"
            elif key in report["assertions"]["regressed"]:
                severity = " (REGRESSED)"
            lines.append(f"- {key}{severity}")
        lines.append("")

    # Benchmark deltas
    if report["benchmark_deltas"]:
        lines.append("## Benchmark Deltas")
        lines.append("")
        lines.append("| Config | Before | After | Delta |")
        lines.append("|--------|--------|-------|-------|")
        for d in report["benchmark_deltas"]:
            marker = ""
            if d["improved"]:
                marker = " (+)"
            elif d["regressed"]:
                marker = " (-)"
            lines.append(
                f"| {d['config']} | {d['before_pass_rate']:.1%} "
                f"| {d['after_pass_rate']:.1%} | {d['delta']:+.1%}{marker} |"
            )
        lines.append("")

    # Complaints delta
    before_c = report.get("complaints_before", 0)
    after_c = report.get("complaints_after", 0)
    if before_c > 0 or after_c > 0:
        lines.append(f"## User Complaints: {before_c} before, {after_c} after")
        lines.append("")

    return "\n".join(lines)


def compare_iterations(before: dict, after: dict) -> dict:
    """Compare two diagnosis reports and return the comparison."""
    assertion_comparison = compare_assertions(
        before.get("failing_assertions", []),
        before.get("inconsistent_assertions", []),
        after.get("failing_assertions", []),
        after.get("inconsistent_assertions", []),
    )

    benchmark_deltas = compare_benchmarks(
        before.get("benchmark_summary"),
        after.get("benchmark_summary"),
    )

    return {
        "before_workspace": before.get("workspace_path", ""),
        "after_workspace": after.get("workspace_path", ""),
        "assertions": assertion_comparison,
        "benchmark_deltas": benchmark_deltas,
        "complaints_before": len(before.get("user_complaints", [])),
        "complaints_after": len(after.get("user_complaints", [])),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two iteration diagnoses")
    parser.add_argument("--before", type=Path, required=True, help="Diagnosis from before improvement")
    parser.add_argument("--after", type=Path, required=True, help="Diagnosis from after improvement")
    parser.add_argument("--output", type=Path, default=None, help="Output path for comparison_report.json")
    args = parser.parse_args()

    for path in (args.before, args.after):
        if not path.exists():
            print(f"Error: {path} not found", file=sys.stderr)
            sys.exit(1)

    before = json.loads(args.before.read_text())
    after = json.loads(args.after.read_text())

    report = compare_iterations(before, after)

    json_path = args.output or Path("comparison_report.json")
    json_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Comparison report written to {json_path}")

    md_path = json_path.with_suffix(".md")
    md_path.write_text(render_markdown(report))
    print(f"Comparison report (markdown) written to {md_path}")

    # Print summary
    a = report["assertions"]["summary"]
    print(f"  Resolved: {a['resolved_count']}")
    print(f"  New failures: {a['new_failure_count']}")
    print(f"  Persistent: {a['persistent_count']}")
    if report["benchmark_deltas"]:
        for d in report["benchmark_deltas"]:
            direction = "+" if d["delta"] >= 0 else ""
            print(f"  {d['config']}: {direction}{d['delta']:.1%} pass rate")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Merge audit report and workspace diagnosis into a prioritized improvement plan.

Combines structural audit findings with evidence from testing workspaces to
produce a ranked list of improvements, flagging description issues for triage
by writing-skills Phase 6 rather than attempting to fix them directly.

Usage:
    python -m scripts.plan_improvements --audit audit_report.json --diagnosis diagnosis.json
    python -m scripts.plan_improvements --audit audit_report.json  # audit-only mode
"""

import argparse
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Priority levels
# ---------------------------------------------------------------------------

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


# ---------------------------------------------------------------------------
# Improvement generation from audit
# ---------------------------------------------------------------------------

def improvements_from_audit(audit: dict) -> tuple[list[dict], list[dict]]:
    """Generate improvements and description triage items from audit findings.

    Returns (improvements, description_triage).
    """
    improvements = []
    description_triage = []

    for check in audit.get("checks", []):
        status = check["status"]
        if status == "pass":
            continue

        category = check["category"]
        check_name = check["check"]
        detail = check["detail"]

        # Description issues go to triage, not direct improvement
        if check_name in (
            "description_starts_with_use_when",
            "no_workflow_in_description",
            "description_length",
        ):
            description_triage.append({
                "issue": detail or f"Check '{check_name}' returned {status}",
                "recommendation": "Run writing-skills Phase 6 description optimization",
            })
            continue

        priority = "high" if status == "fail" else "medium"
        improvements.append({
            "priority": priority,
            "category": category,
            "issue": detail or f"Check '{check_name}' flagged",
            "suggestion": _suggestion_for_check(check_name, detail),
            "evidence": [f"audit: {check_name} ({status})"],
            "source": "audit",
        })

    return improvements, description_triage


def _suggestion_for_check(check_name: str, detail: str) -> str:
    """Generate a concrete suggestion for an audit check failure."""
    suggestions = {
        "name_present": "Add a 'name' field to the SKILL.md frontmatter",
        "name_kebab_case": "Rename to kebab-case (lowercase letters, digits, hyphens)",
        "name_length": "Shorten the name to 64 characters or fewer",
        "description_present": "Add a 'description' field to the SKILL.md frontmatter",
        "token_budget": "Reduce word count — extract detail into references/ files",
        "has_overview": "Add an '## Overview' section explaining what this skill does",
        "has_checklist": "Add a '## Checklist' section with actionable items",
        "no_empty_sections": "Add content to empty sections or remove them",
        "no_narrative_storytelling": "Replace anecdotal narratives with direct instructions",
        "no_multi_language_dilution": "Focus code examples on the primary language",
        "progressive_disclosure": "Move detailed reference material into a references/ directory",
        "has_examples": "Add at least one concrete example or code block",
    }

    for prefix, suggestion in suggestions.items():
        if check_name.startswith(prefix):
            return suggestion

    if check_name.startswith("script_compiles:"):
        return "Fix syntax errors in the script"
    if check_name.startswith("script_docstring:"):
        return "Add a module docstring explaining what the script does"
    if check_name.startswith("script_entry_point:"):
        return "Add a main() function and if __name__ == '__main__' guard"

    return f"Address the issue: {detail}"


# ---------------------------------------------------------------------------
# Improvement generation from diagnosis
# ---------------------------------------------------------------------------

def improvements_from_diagnosis(diagnosis: dict) -> list[dict]:
    """Generate improvements from workspace diagnosis findings."""
    improvements = []

    # Always-failing assertions → critical
    for item in diagnosis.get("failing_assertions", []):
        improvements.append({
            "priority": "critical",
            "category": "instructions",
            "issue": f"Assertion '{item['assertion']}' fails {int(item['fail_rate'] * 100)}% of the time",
            "suggestion": "Add explicit instructions for this behavior to the skill body",
            "evidence": [
                f"grading.json: {item['eval']}, fail_rate={item['fail_rate']}",
                *item.get("evidence", [])[:2],
            ],
            "source": "diagnosis",
        })

    # User complaints → high
    for item in diagnosis.get("user_complaints", []):
        improvements.append({
            "priority": "high",
            "category": "quality",
            "issue": f"User complaint: {item['feedback'][:200]}",
            "suggestion": "Address the specific concern raised in user feedback",
            "evidence": [f"feedback.json: {item.get('run_id', 'unknown run')}"],
            "source": "diagnosis",
        })

    # Comparison losses → high
    for item in diagnosis.get("comparison_losses", []):
        improvements.append({
            "priority": "high",
            "category": "quality",
            "issue": f"Lost comparison in {item['eval']}: {item.get('reasoning', '')[:200]}",
            "suggestion": "Improve the areas identified in the comparison reasoning",
            "evidence": [f"comparison.json: {item['eval']}, winner={item['winner']}"],
            "source": "diagnosis",
        })

    # Inconsistent assertions → medium
    for item in diagnosis.get("inconsistent_assertions", []):
        improvements.append({
            "priority": "medium",
            "category": "consistency",
            "issue": f"Assertion '{item['assertion']}' fails {int(item['fail_rate'] * 100)}% of the time (inconsistent)",
            "suggestion": "Strengthen instructions to reduce output variance",
            "evidence": [f"grading.json: {item['eval']}, fail_rate={item['fail_rate']}"],
            "source": "diagnosis",
        })

    # Benchmark regressions → medium
    benchmark = diagnosis.get("benchmark_summary")
    if benchmark and isinstance(benchmark, dict):
        for config_name, stats in benchmark.items():
            pass_rate = stats.get("pass_rate", {})
            if isinstance(pass_rate, dict):
                mean = pass_rate.get("mean", 1.0)
                stddev = pass_rate.get("stddev", 0.0)
                if mean < 0.7:
                    improvements.append({
                        "priority": "medium",
                        "category": "performance",
                        "issue": f"Config '{config_name}' pass rate is {mean:.0%} (below 70% threshold)",
                        "suggestion": "Review failing assertions and strengthen relevant instructions",
                        "evidence": [f"benchmark.json: {config_name}, mean={mean:.2f}, stddev={stddev:.2f}"],
                        "source": "diagnosis",
                    })
                if stddev > 0.2:
                    improvements.append({
                        "priority": "medium",
                        "category": "consistency",
                        "issue": f"Config '{config_name}' has high variance (stddev={stddev:.2f})",
                        "suggestion": "Make instructions more explicit to reduce output variance",
                        "evidence": [f"benchmark.json: {config_name}, stddev={stddev:.2f}"],
                        "source": "diagnosis",
                    })

    return improvements


# ---------------------------------------------------------------------------
# Deduplication and merging
# ---------------------------------------------------------------------------

def deduplicate(improvements: list[dict]) -> list[dict]:
    """Merge overlapping improvements, keeping the highest priority."""
    seen: dict[str, int] = {}
    result = []

    for item in improvements:
        # Use issue text as dedup key (simplified)
        key = item["issue"][:100].lower()
        if key in seen:
            # Merge evidence into existing entry if higher priority
            existing = result[seen[key]]
            if PRIORITY_ORDER.get(item["priority"], 99) < PRIORITY_ORDER.get(existing["priority"], 99):
                existing["priority"] = item["priority"]
            existing["evidence"].extend(item["evidence"])
        else:
            seen[key] = len(result)
            result.append(item)

    return result


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------

def render_markdown(plan: dict) -> str:
    """Render the improvement plan as human-readable markdown."""
    lines = [f"# Improvement Plan: {plan['skill_name']}", ""]

    summary = plan["summary"]
    lines.append(f"**{summary['critical']} critical, {summary['high']} high, "
                 f"{summary['medium']} medium, {summary['low']} low** improvements identified.")
    if summary.get("description_issues", 0) > 0:
        lines.append(f"**{summary['description_issues']} description issue(s)** triaged for writing-skills Phase 6.")
    lines.append("")

    # Group by priority
    for priority in ("critical", "high", "medium", "low"):
        items = [i for i in plan["improvements"] if i["priority"] == priority]
        if not items:
            continue

        lines.append(f"## {priority.title()} Priority")
        lines.append("")

        for i, item in enumerate(items, 1):
            lines.append(f"### {i}. {item['issue']}")
            lines.append(f"**Category:** {item['category']}  ")
            lines.append(f"**Suggestion:** {item['suggestion']}  ")
            lines.append(f"**Source:** {item['source']}")
            if item.get("evidence"):
                lines.append("")
                lines.append("**Evidence:**")
                for ev in item["evidence"]:
                    lines.append(f"- {ev}")
            lines.append("")

    # Description triage
    if plan.get("description_triage"):
        lines.append("## Description Issues (Triaged)")
        lines.append("")
        lines.append("These issues affect the skill's description/trigger. Do NOT fix manually —")
        lines.append("use `writing-skills` Phase 6 description optimization loop instead.")
        lines.append("")
        for item in plan["description_triage"]:
            lines.append(f"- **{item['issue']}**")
            lines.append(f"  Recommendation: {item['recommendation']}")
        lines.append("")

    # Next steps
    lines.append("## Next Steps")
    lines.append("")
    lines.append("1. Work through improvements by priority (critical first)")
    lines.append("2. For each: read the evidence, make the change, explain why")
    lines.append("3. Generalize from findings — don't overfit to specific test cases")
    lines.append("4. Re-run tests to validate (skill-testing-output or skill-compare)")
    lines.append("5. If description issues were flagged, run writing-skills Phase 6")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def plan_improvements(audit: dict, diagnosis: dict | None = None) -> dict:
    """Generate a prioritized improvement plan from audit and diagnosis."""
    improvements = []
    description_triage: list[dict] = []

    # From audit
    audit_improvements, audit_triage = improvements_from_audit(audit)
    improvements.extend(audit_improvements)
    description_triage.extend(audit_triage)

    # From diagnosis
    if diagnosis:
        improvements.extend(improvements_from_diagnosis(diagnosis))

    # Deduplicate and sort
    improvements = deduplicate(improvements)
    improvements.sort(key=lambda x: PRIORITY_ORDER.get(x["priority"], 99))

    skill_name = audit.get("skill_name", "unknown")

    summary = {
        "critical": sum(1 for i in improvements if i["priority"] == "critical"),
        "high": sum(1 for i in improvements if i["priority"] == "high"),
        "medium": sum(1 for i in improvements if i["priority"] == "medium"),
        "low": sum(1 for i in improvements if i["priority"] == "low"),
        "description_issues": len(description_triage),
    }

    return {
        "skill_name": skill_name,
        "improvements": improvements,
        "description_triage": description_triage,
        "summary": summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a prioritized improvement plan")
    parser.add_argument("--audit", type=Path, required=True, help="Path to audit_report.json")
    parser.add_argument("--diagnosis", type=Path, default=None, help="Path to diagnosis.json (optional)")
    parser.add_argument("--output", type=Path, default=None, help="Output path for improvement_plan.json")
    args = parser.parse_args()

    if not args.audit.exists():
        print(f"Error: {args.audit} not found", file=sys.stderr)
        sys.exit(1)

    audit = json.loads(args.audit.read_text())

    diagnosis = None
    if args.diagnosis:
        if not args.diagnosis.exists():
            print(f"Error: {args.diagnosis} not found", file=sys.stderr)
            sys.exit(1)
        diagnosis = json.loads(args.diagnosis.read_text())

    plan = plan_improvements(audit, diagnosis)

    # Write JSON
    json_path = args.output or Path("improvement_plan.json")
    json_path.write_text(json.dumps(plan, indent=2) + "\n")
    print(f"Improvement plan written to {json_path}")

    # Write Markdown
    md_path = json_path.with_suffix(".md")
    md_path.write_text(render_markdown(plan))
    print(f"Improvement plan (markdown) written to {md_path}")

    # Print summary
    s = plan["summary"]
    print(f"  {s['critical']} critical, {s['high']} high, {s['medium']} medium, {s['low']} low")
    if s["description_issues"] > 0:
        print(f"  {s['description_issues']} description issue(s) triaged for Phase 6")


if __name__ == "__main__":
    main()

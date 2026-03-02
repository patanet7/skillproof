#!/usr/bin/env python3
"""Initialize an improvement workspace for an existing skill.

Creates the workspace directory, runs the structural audit, and generates
evals derived from the skill's checklist items and key sections.

Usage:
    # Basic: scaffold workspace + run audit + generate evals from skill content
    python -m scripts.init_improvement /path/to/skill --output ./improvement-workspace

    # With existing evals
    python -m scripts.init_improvement /path/to/skill --evals evals.json --output ./workspace

    # With existing testing workspace (skip scaffolding, just add audit)
    python -m scripts.init_improvement /path/to/skill --workspace ./existing-workspace
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts.audit_skill import audit_skill, parse_frontmatter


# ---------------------------------------------------------------------------
# Eval generation from skill content
# ---------------------------------------------------------------------------

def _extract_checklist_items(body: str) -> list[str]:
    """Extract checklist items from the skill body (- [ ] lines)."""
    items = []
    for match in re.finditer(r"^- \[[ x]\]\s+(.+)$", body, re.MULTILINE):
        text = match.group(1).strip()
        # Strip markdown formatting
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"`(.+?)`", r"\1", text)
        # Strip trailing parenthetical notes like "(if any)"
        text = re.sub(r"\s*\(.*?\)\s*$", "", text)
        if text:
            items.append(text)
    return items


def _extract_step_headings(body: str) -> list[str]:
    """Extract Step N headings from the skill body."""
    steps = []
    for match in re.finditer(r"^#{1,3}\s+Step\s+\d+[:\s]+(.+)$", body, re.MULTILINE):
        steps.append(match.group(1).strip())
    return steps


def _checklist_to_assertion(item: str) -> str:
    """Convert a checklist item into an eval assertion."""
    item = item.rstrip(".")

    # Handle "Phase N:" or "Step N:" prefix — keep as context
    phase_match = re.match(r"^(Phase|Step)\s+(\d+)\s*:\s*(.+)", item, re.IGNORECASE)
    if phase_match:
        label = phase_match.group(1)
        num = phase_match.group(2)
        rest = phase_match.group(3)
        return f"The agent completed {label} {num}: {rest}"

    # Avoid double "agent" — "Agent complies" → "The agent complies"
    if re.match(r"^[Aa]gent\s+", item):
        return f"The {item[0].lower()}{item[1:]}"

    # Past-tense verb: "Ran audit" → "The agent ran audit"
    if re.match(r"^[A-Z][a-z]+ed\b", item):
        return f"The agent {item[0].lower()}{item[1:]}"

    # Other leading verb: "Generate plan" → "The agent generate plan"
    if re.match(r"^[A-Z][a-z]+\b", item):
        return f"The agent {item[0].lower()}{item[1:]}"

    return item


def generate_evals_from_skill(skill_path: Path) -> dict:
    """Generate evals by reading the skill's SKILL.md content.

    Uses checklist items as assertions and step headings as eval topics.
    """
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return _fallback_evals(skill_path.name)

    content = skill_md.read_text()
    fm, body = parse_frontmatter(content)
    skill_name = fm.get("name", skill_path.name)
    description = fm.get("description", "")

    checklist_items = _extract_checklist_items(body)
    step_headings = _extract_step_headings(body)

    if not checklist_items and not step_headings:
        return _fallback_evals(skill_name)

    evals = []
    eval_id = 1

    # Generate one eval per major step/checklist group
    # Group checklist items into evals (2-3 assertions each)
    if checklist_items:
        # Split into groups of 2-3
        for i in range(0, len(checklist_items), 3):
            group = checklist_items[i : i + 3]
            assertions = [_checklist_to_assertion(item) for item in group]

            # Use step heading as context if available
            step_context = ""
            if i // 3 < len(step_headings):
                step_context = f" (focus: {step_headings[i // 3]})"

            evals.append({
                "id": eval_id,
                "prompt": f"Use the {skill_name} skill to complete a realistic task{step_context}. "
                          f"Skill description: {description}",
                "expected_output": f"Agent follows the {skill_name} workflow and produces the expected artifacts",
                "files": [],
                "expectations": assertions,
            })
            eval_id += 1
    elif step_headings:
        # No checklist, use step headings directly
        for heading in step_headings[:5]:
            evals.append({
                "id": eval_id,
                "prompt": f"Use the {skill_name} skill. Focus on: {heading}",
                "expected_output": f"Agent completes the {heading.lower()} step correctly",
                "files": [],
                "expectations": [
                    f"The agent completed the '{heading}' step",
                    f"The output from '{heading}' is correct and complete",
                ],
            })
            eval_id += 1

    return {"skill_name": skill_name, "evals": evals}


def _fallback_evals(skill_name: str) -> dict:
    """Minimal eval structure when skill content can't be parsed."""
    return {
        "skill_name": skill_name,
        "evals": [
            {
                "id": 1,
                "prompt": f"Use the {skill_name} skill to complete a realistic task",
                "expected_output": f"Agent follows the {skill_name} workflow correctly",
                "files": [],
                "expectations": [
                    f"The agent loaded and followed the {skill_name} skill",
                    "The output meets the skill's stated quality criteria",
                ],
            },
        ],
    }


# ---------------------------------------------------------------------------
# Workspace initialization
# ---------------------------------------------------------------------------

def init_improvement(
    skill_path: Path,
    output: Path | None = None,
    evals_path: Path | None = None,
    existing_workspace: Path | None = None,
) -> dict:
    """Initialize an improvement workspace and return metadata."""
    skill_path = skill_path.resolve()
    skill_name = skill_path.name

    # Determine workspace path
    if existing_workspace:
        workspace = existing_workspace.resolve()
    elif output:
        workspace = output.resolve()
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        workspace = Path.cwd() / f"{skill_name}-improvement-{timestamp}"

    workspace.mkdir(parents=True, exist_ok=True)

    # Run structural audit
    print(f"Running structural audit on {skill_path}...")
    audit_report = audit_skill(skill_path)
    audit_path = workspace / "audit_report.json"
    audit_path.write_text(json.dumps(audit_report, indent=2) + "\n")
    s = audit_report["summary"]
    print(f"  Audit: {s['pass']}P / {s['warn']}W / {s['fail']}F ({s['total']} checks)")

    # Handle evals
    evals_dest = workspace / "evals.json"
    evals_ready = False
    if evals_path and evals_path.exists():
        shutil.copy2(evals_path, evals_dest)
        evals_ready = True
        print(f"  Copied evals from {evals_path}")
    elif not evals_dest.exists() and not existing_workspace:
        evals_data = generate_evals_from_skill(skill_path)
        evals_dest.write_text(json.dumps(evals_data, indent=2) + "\n")
        evals_ready = True
        print(f"  Generated {len(evals_data['evals'])} evals from skill content")

    # Create iteration-1 directory if scaffolding new workspace
    if not existing_workspace:
        iter_dir = workspace / "iteration-1"
        iter_dir.mkdir(exist_ok=True)

    # Write workspace metadata
    metadata = {
        "skill_name": skill_name,
        "skill_path": str(skill_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "workspace_path": str(workspace),
        "has_evals": evals_dest.exists(),
        "evals_ready": evals_ready,
        "audit_summary": audit_report["summary"],
    }
    (workspace / "improvement_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize an improvement workspace")
    parser.add_argument("skill_path", type=Path, help="Path to the skill directory")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Output workspace directory")
    parser.add_argument("--evals", type=Path, default=None, help="Existing evals.json to use")
    parser.add_argument("--workspace", type=Path, default=None, help="Existing testing workspace to augment")
    args = parser.parse_args()

    if not args.skill_path.is_dir():
        print(f"Error: {args.skill_path} is not a directory", file=sys.stderr)
        sys.exit(1)

    metadata = init_improvement(
        skill_path=args.skill_path,
        output=args.output,
        evals_path=args.evals,
        existing_workspace=args.workspace,
    )

    print(f"\nWorkspace ready at: {metadata['workspace_path']}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Initialize workspace directory structure for a two-skill head-to-head comparison.

Creates the matchup workspace layout:
    matchup-workspace/
    └── iteration-1/
        ├── eval-<name>/
        │   ├── <skill-a-slug>/
        │   │   ├── run-1/outputs/
        │   │   ├── run-2/outputs/
        │   │   └── run-3/outputs/
        │   ├── <skill-b-slug>/
        │   │   ├── run-1/outputs/
        │   │   ├── run-2/outputs/
        │   │   └── run-3/outputs/
        │   └── eval_metadata.json
        └── matchup.json

Usage:
    python -m scripts.init_matchup \\
        --skill-a /path/to/skill-a \\
        --skill-b /path/to/skill-b \\
        --evals evals.json \\
        --output ./matchup-workspace

    python -m scripts.init_matchup \\
        --skill-a /path/to/skill-a \\
        --skill-b /path/to/skill-b \\
        --evals evals.json \\
        --output ./matchup-workspace \\
        --iteration 2 --runs 5
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    slug = text.lower().strip()
    slug = "".join(c if c.isalnum() or c in ("-", "_", " ") else "" for c in slug)
    slug = "-".join(slug.split())
    return slug[:60] or "unnamed"


def parse_skill_frontmatter(skill_path: Path) -> str:
    """Extract skill name from SKILL.md frontmatter.

    Reimplemented locally to avoid sibling imports across skill directories.
    Handles YAML block scalar indicators (>, |, >-, |-) for multiline values.
    """
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return skill_path.name

    content = skill_md.read_text()
    lines = content.split("\n")

    if not lines or lines[0].strip() != "---":
        return skill_path.name

    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return skill_path.name

    for line in lines[1:end_idx]:
        if line.startswith("name:"):
            name = line[len("name:") :].strip().strip('"').strip("'")
            if name:
                return name

    return skill_path.name


def init_matchup(
    skill_a_path: Path,
    skill_b_path: Path,
    evals_path: Path,
    output_dir: Path,
    iteration: int = 1,
    runs: int = 3,
) -> Path:
    """Create matchup workspace directory structure from eval definitions."""
    evals_data = json.loads(evals_path.read_text())
    eval_list = evals_data.get("evals", [])

    if not eval_list:
        print("Error: No evals found in evals file", file=sys.stderr)
        sys.exit(1)

    # Extract skill names from frontmatter
    name_a = parse_skill_frontmatter(skill_a_path)
    name_b = parse_skill_frontmatter(skill_b_path)

    # Slugify for directory names
    config_a = slugify(name_a)
    config_b = slugify(name_b)

    # Handle collisions
    if config_a == config_b:
        config_a = f"{config_a}-a"
        config_b = f"{config_b}-b"

    iteration_dir = output_dir / f"iteration-{iteration}"
    iteration_dir.mkdir(parents=True, exist_ok=True)

    for eval_item in eval_list:
        eval_id = eval_item.get("id", 0)
        eval_name = eval_item.get("name", "")
        prompt = eval_item.get("prompt", "")

        if not eval_name:
            eval_name = slugify(prompt[:50]) if prompt else f"eval-{eval_id}"

        eval_dir = iteration_dir / f"eval-{eval_name}"

        # Create run directories for each config
        for config in (config_a, config_b):
            for run_num in range(1, runs + 1):
                outputs_dir = eval_dir / config / f"run-{run_num}" / "outputs"
                outputs_dir.mkdir(parents=True, exist_ok=True)

        # Write eval_metadata.json
        metadata = {
            "eval_id": eval_id,
            "eval_name": eval_name,
            "prompt": prompt,
            "expected_output": eval_item.get("expected_output", ""),
            "files": eval_item.get("files", []),
            "assertions": eval_item.get("assertions", []),
        }
        (eval_dir / "eval_metadata.json").write_text(json.dumps(metadata, indent=2))

    # Write matchup.json at iteration root
    matchup = {
        "skill_a": {"name": name_a, "path": str(skill_a_path.resolve())},
        "skill_b": {"name": name_b, "path": str(skill_b_path.resolve())},
        "config_a": config_a,
        "config_b": config_b,
        "runs_per_eval": runs,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (iteration_dir / "matchup.json").write_text(json.dumps(matchup, indent=2))

    print(f"Matchup workspace initialized: {iteration_dir}")
    print(f"  Skill A: {name_a} ({config_a}/) -> {skill_a_path}")
    print(f"  Skill B: {name_b} ({config_b}/) -> {skill_b_path}")
    print(f"  {len(eval_list)} eval(s) x {runs} run(s) per skill")
    print(f"\nEval directories:")
    for eval_dir in sorted(iteration_dir.iterdir()):
        if eval_dir.is_dir():
            print(f"  {eval_dir.name}/")

    return iteration_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialize workspace for a two-skill head-to-head comparison"
    )
    parser.add_argument(
        "--skill-a",
        type=Path,
        required=True,
        help="Path to first skill directory (must contain SKILL.md)",
    )
    parser.add_argument(
        "--skill-b",
        type=Path,
        required=True,
        help="Path to second skill directory (must contain SKILL.md)",
    )
    parser.add_argument(
        "--evals",
        type=Path,
        required=True,
        help="Path to evals.json file with test cases",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("./matchup-workspace"),
        help="Workspace directory (default: ./matchup-workspace)",
    )
    parser.add_argument(
        "--iteration",
        type=int,
        default=1,
        help="Iteration number (default: 1)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of runs per eval per skill (default: 3)",
    )
    args = parser.parse_args()

    if not args.evals.exists():
        print(f"Error: Evals file not found: {args.evals}", file=sys.stderr)
        sys.exit(1)

    for label, path in [("--skill-a", args.skill_a), ("--skill-b", args.skill_b)]:
        if not (path / "SKILL.md").exists():
            print(f"Error: No SKILL.md found at {path} ({label})", file=sys.stderr)
            sys.exit(1)

    init_matchup(
        skill_a_path=args.skill_a,
        skill_b_path=args.skill_b,
        evals_path=args.evals,
        output_dir=args.output,
        iteration=args.iteration,
        runs=args.runs,
    )


if __name__ == "__main__":
    main()

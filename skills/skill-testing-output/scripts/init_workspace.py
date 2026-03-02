#!/usr/bin/env python3
"""Initialize workspace directory structure for A/B output comparison.

Creates the standard workspace layout:
    <workspace>/
    └── iteration-1/
        ├── eval-<name>/
        │   ├── with_skill/
        │   │   └── outputs/
        │   ├── without_skill/
        │   │   └── outputs/
        │   └── eval_metadata.json
        └── ...

Usage:
    python -m scripts.init_workspace my-skill \\
        --evals evals/evals.json \\
        --output ./my-skill-workspace

    python -m scripts.init_workspace my-skill \\
        --evals evals/evals.json \\
        --output ./my-skill-workspace \\
        --iteration 2 \\
        --configs with_skill old_skill
"""

import argparse
import json
import sys
from pathlib import Path


def slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    slug = text.lower().strip()
    slug = "".join(c if c.isalnum() or c in ("-", "_", " ") else "" for c in slug)
    slug = "-".join(slug.split())
    return slug[:60] or "unnamed"


def init_workspace(
    skill_name: str,
    evals_path: Path,
    output_dir: Path,
    iteration: int = 1,
    configs: list[str] | None = None,
) -> Path:
    """Create workspace directory structure from eval definitions."""
    configs = configs or ["with_skill", "without_skill"]

    evals_data = json.loads(evals_path.read_text())
    eval_list = evals_data.get("evals", [])

    if not eval_list:
        print("Error: No evals found in evals file", file=sys.stderr)
        sys.exit(1)

    iteration_dir = output_dir / f"iteration-{iteration}"
    iteration_dir.mkdir(parents=True, exist_ok=True)

    for eval_item in eval_list:
        eval_id = eval_item.get("id", 0)
        eval_name = eval_item.get("name", "")
        prompt = eval_item.get("prompt", "")

        if not eval_name:
            eval_name = slugify(prompt[:50]) if prompt else f"eval-{eval_id}"

        eval_dir_name = f"eval-{eval_name}"
        eval_dir = iteration_dir / eval_dir_name

        for config in configs:
            outputs_dir = eval_dir / config / "outputs"
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

    print(f"Workspace initialized: {iteration_dir}")
    print(f"  {len(eval_list)} eval(s) with {len(configs)} config(s) each")
    print(f"  Configs: {', '.join(configs)}")
    print(f"\nEval directories:")
    for eval_dir in sorted(iteration_dir.iterdir()):
        if eval_dir.is_dir():
            print(f"  {eval_dir.name}/")

    return iteration_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialize workspace directory for A/B output comparison"
    )
    parser.add_argument(
        "skill_name",
        help="Name of the skill being tested",
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
        default=None,
        help="Workspace directory (default: ./<skill-name>-workspace)",
    )
    parser.add_argument(
        "--iteration",
        type=int,
        default=1,
        help="Iteration number (default: 1)",
    )
    parser.add_argument(
        "--configs",
        nargs="+",
        default=None,
        help="Configuration names (default: with_skill without_skill)",
    )
    args = parser.parse_args()

    if not args.evals.exists():
        print(f"Error: Evals file not found: {args.evals}", file=sys.stderr)
        sys.exit(1)

    output = args.output or Path(f"./{args.skill_name}-workspace")

    init_workspace(
        skill_name=args.skill_name,
        evals_path=args.evals,
        output_dir=output,
        iteration=args.iteration,
        configs=args.configs,
    )


if __name__ == "__main__":
    main()

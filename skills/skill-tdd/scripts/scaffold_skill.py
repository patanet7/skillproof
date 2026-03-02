#!/usr/bin/env python3
"""Scaffold a new skill directory with standard structure.

Creates:
    <output>/<skill-name>/
    ├── SKILL.md          (template with frontmatter)
    ├── references/       (empty, for supporting docs)
    └── scripts/
        └── __init__.py   (empty module marker)

Usage:
    python -m scripts.scaffold_skill my-new-skill --output ~/skills
    python -m scripts.scaffold_skill my-new-skill --output ~/skills --type discipline
"""

import argparse
import re
import sys
from pathlib import Path


SKILL_TYPES = {
    "discipline": {
        "test_approach": "Pressure scenarios (skillproof:skill-testing-discipline)",
        "sections": [
            "## Rules\n\n<!-- Explicit rules with rationale -->\n",
            "## Rationalization Table\n\n| Excuse | Reality |\n|--------|---------|"
            "\n| \"...\" | ... |\n",
            "## Red Flags -- STOP\n\n- <!-- Signs the agent is about to violate -->\n",
        ],
    },
    "workflow": {
        "test_approach": "Output comparison (skillproof:skill-testing-output)",
        "sections": [
            "## Process\n\n<!-- Explain the WHY, not just the WHAT -->\n",
            "## Examples\n\n<!-- One excellent example beats five mediocre ones -->\n",
        ],
    },
    "reference": {
        "test_approach": "Retrieval scenarios (inline)",
        "sections": [
            "## Reference\n\n<!-- Concise and scannable, tables and definition lists -->\n",
        ],
    },
    "hybrid": {
        "test_approach": "Both discipline + output testing",
        "sections": [
            "## Rules\n\n<!-- Explicit rules with rationale -->\n",
            "## Process\n\n<!-- Explain the WHY, not just the WHAT -->\n",
            "## Rationalization Table\n\n| Excuse | Reality |\n|--------|---------|"
            "\n| \"...\" | ... |\n",
        ],
    },
}


def validate_name(name: str) -> bool:
    """Validate skill name is kebab-case."""
    if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name):
        return False
    if len(name) > 64:
        return False
    return True


def generate_skill_md(name: str, skill_type: str) -> str:
    """Generate SKILL.md content from template."""
    type_info = SKILL_TYPES.get(skill_type, SKILL_TYPES["workflow"])
    sections = "\n".join(type_info["sections"])

    return f"""---
name: {name}
description: Use when [specific triggering conditions and symptoms]
---

# {name.replace('-', ' ').title()}

## Overview

<!-- What does this skill enable? What problem does it solve? -->

**Core principle:** <!-- The one thing that matters most -->

## When to Use

**Use when:**
- <!-- Specific triggering conditions -->

**Do NOT use for:**
- <!-- Explicit exclusions -->

{sections}
## Testing Checklist

- [ ] Ran baseline WITHOUT skill, documented failures verbatim
- [ ] Wrote minimal skill addressing specific baseline failures
- [ ] Evaluated WITH skill, measured improvement
- [ ] Refined based on feedback, re-tested until stable
"""


def scaffold(name: str, output_dir: Path, skill_type: str) -> Path:
    """Create skill directory with standard structure."""
    skill_dir = output_dir / name

    if skill_dir.exists():
        print(f"Error: {skill_dir} already exists", file=sys.stderr)
        sys.exit(1)

    # Create directories
    skill_dir.mkdir(parents=True)
    (skill_dir / "references").mkdir()
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "__init__.py").write_text("")

    # Write SKILL.md
    content = generate_skill_md(name, skill_type)
    (skill_dir / "SKILL.md").write_text(content)

    return skill_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scaffold a new skill directory with standard structure"
    )
    parser.add_argument("name", help="Skill name (kebab-case, e.g. my-new-skill)")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path.cwd(),
        help="Parent directory for the new skill (default: current directory)",
    )
    parser.add_argument(
        "--type",
        "-t",
        choices=list(SKILL_TYPES.keys()),
        default="workflow",
        help="Skill type determines template sections (default: workflow)",
    )
    args = parser.parse_args()

    if not validate_name(args.name):
        print(
            f"Error: '{args.name}' is not valid kebab-case "
            "(lowercase letters, digits, and hyphens only, max 64 chars)",
            file=sys.stderr,
        )
        sys.exit(1)

    skill_dir = scaffold(args.name, args.output, args.type)

    print(f"Scaffolded skill at: {skill_dir}")
    print(f"  SKILL.md       — edit frontmatter description and body")
    print(f"  references/    — add supporting docs")
    print(f"  scripts/       — add automation scripts")
    print(f"\nNext steps:")
    print(f"  1. Edit {skill_dir}/SKILL.md")
    print(f"  2. Run baseline tests (RED phase)")
    print(f"  3. Iterate until skill passes tests (GREEN phase)")


if __name__ == "__main__":
    main()

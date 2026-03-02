#!/usr/bin/env python3
"""Structural quality audit of a skill against best-practices and cso-guide rules.

Reads a skill's SKILL.md, parses its frontmatter and body, then runs a battery
of structural checks covering frontmatter validation, token budget, section
structure, anti-patterns, best practices, and script quality.

Usage:
    python -m scripts.audit_skill /path/to/skill [--output audit_report.json]
"""

import argparse
import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Frontmatter parsing (matches writing-skills/scripts/quick_validate.py)
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse YAML frontmatter and return (frontmatter_dict, body).

    Returns an empty dict and the full text if no frontmatter is found.
    """
    if not text.startswith("---"):
        return {}, text

    match = re.match(r"^---\n(.*?)\n---\n?(.*)", text, re.DOTALL)
    if not match:
        return {}, text

    fm_text = match.group(1)
    body = match.group(2)

    result: dict[str, str] = {}
    current_key: str | None = None
    current_value_lines: list[str] = []

    for line in fm_text.splitlines():
        kv_match = re.match(r"^([a-z][a-z0-9_-]*)\s*:\s*(.*)", line)
        if kv_match:
            if current_key is not None:
                result[current_key] = " ".join(current_value_lines).strip()
            current_key = kv_match.group(1)
            value = kv_match.group(2).strip()
            if value in (">", "|", ">-", "|-"):
                current_value_lines = []
            else:
                current_value_lines = [value]
        elif current_key is not None and line.startswith((" ", "\t")):
            current_value_lines.append(line.strip())

    if current_key is not None:
        result[current_key] = " ".join(current_value_lines).strip()

    return result, body


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check(name: str, status: str, detail: str, category: str) -> dict:
    return {"check": name, "status": status, "detail": detail, "category": category}


def check_name_format(fm: dict[str, str]) -> list[dict]:
    """Validate name is kebab-case, <= 64 chars."""
    checks = []
    name = fm.get("name", "")
    if not name:
        checks.append(_check("name_present", "fail", "Missing 'name' in frontmatter", "frontmatter"))
        return checks

    checks.append(_check("name_present", "pass", "", "frontmatter"))

    if not re.match(r"^[a-z0-9-]+$", name):
        checks.append(_check("name_kebab_case", "fail", f"Name '{name}' is not kebab-case", "frontmatter"))
    elif name.startswith("-") or name.endswith("-") or "--" in name:
        checks.append(_check("name_kebab_case", "fail", f"Name '{name}' has invalid hyphen placement", "frontmatter"))
    else:
        checks.append(_check("name_kebab_case", "pass", "", "frontmatter"))

    if len(name) > 64:
        checks.append(_check("name_length", "fail", f"Name is {len(name)} chars (max 64)", "frontmatter"))
    else:
        checks.append(_check("name_length", "pass", "", "frontmatter"))

    return checks


def check_description(fm: dict[str, str]) -> list[dict]:
    """Validate description starts with 'Use when', <= 1024 chars, no workflow summary."""
    checks = []
    desc = fm.get("description", "")
    if not desc:
        checks.append(_check("description_present", "fail", "Missing 'description' in frontmatter", "frontmatter"))
        return checks

    checks.append(_check("description_present", "pass", "", "frontmatter"))

    if desc.lower().startswith("use when"):
        checks.append(_check("description_starts_with_use_when", "pass", "", "frontmatter"))
    else:
        checks.append(_check("description_starts_with_use_when", "warn", f"Description should start with 'Use when' (starts with: '{desc[:30]}...')", "frontmatter"))

    if len(desc) > 1024:
        checks.append(_check("description_length", "fail", f"Description is {len(desc)} chars (max 1024)", "frontmatter"))
    else:
        checks.append(_check("description_length", "pass", "", "frontmatter"))

    # Check for workflow summary (step/phase/then keywords suggesting procedure)
    workflow_patterns = [
        (r"\bthen\b.*\bthen\b", "multiple 'then' clauses"),
        (r"\bstep\s*\d", "'step N' reference"),
        (r"\bphase\s*\d", "'phase N' reference"),
        (r"\bfirst\b.*\bthen\b.*\bfinally\b", "'first...then...finally' sequence"),
    ]
    workflow_found = []
    for pattern, label in workflow_patterns:
        if re.search(pattern, desc, re.IGNORECASE):
            workflow_found.append(label)

    if workflow_found:
        checks.append(_check(
            "no_workflow_in_description", "fail",
            f"Description contains workflow summary: {', '.join(workflow_found)}",
            "frontmatter",
        ))
    else:
        checks.append(_check("no_workflow_in_description", "pass", "", "frontmatter"))

    return checks


def check_token_budget(body: str, fm: dict[str, str]) -> list[dict]:
    """Check word count against type-based thresholds."""
    checks = []
    words = len(body.split())

    # Infer skill type from content (best-effort)
    desc = fm.get("description", "").lower()
    if any(kw in desc for kw in ("always", "never", "must", "enforce", "rule")):
        skill_type = "discipline"
        threshold = 200
    elif any(kw in desc for kw in ("reference", "lookup", "document")):
        skill_type = "reference"
        threshold = 500
    else:
        skill_type = "workflow"
        threshold = 500

    if words > threshold:
        checks.append(_check(
            "token_budget", "warn",
            f"{words} words (target: <{threshold} for {skill_type})",
            "size",
        ))
    else:
        checks.append(_check("token_budget", "pass", f"{words} words (target: <{threshold})", "size"))

    return checks


def check_sections(body: str) -> list[dict]:
    """Check for required sections and empty sections."""
    checks = []
    headings = re.findall(r"^(#{1,3})\s+(.+)$", body, re.MULTILINE)
    heading_names = [h[1].strip().lower() for h in headings]

    # Check for overview
    has_overview = any("overview" in h for h in heading_names)
    if has_overview:
        checks.append(_check("has_overview", "pass", "", "structure"))
    else:
        checks.append(_check("has_overview", "warn", "No 'Overview' section found", "structure"))

    # Check for checklist
    has_checklist = any("checklist" in h for h in heading_names)
    if has_checklist:
        checks.append(_check("has_checklist", "pass", "", "structure"))
    else:
        checks.append(_check("has_checklist", "warn", "No 'Checklist' section found", "structure"))

    # Check for empty sections: heading followed immediately by another heading
    # Skip lines inside code blocks to avoid false positives
    lines = body.splitlines()
    in_code_block = False
    heading_lines: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if not in_code_block and re.match(r"^#{1,3}\s+", line):
            heading_lines.append((i, line))

    for idx, (line_num, line) in enumerate(heading_lines):
        # Check if there's any content between this heading and the next
        next_heading_line = heading_lines[idx + 1][0] if idx + 1 < len(heading_lines) else len(lines)
        has_content = False
        for j in range(line_num + 1, next_heading_line):
            stripped = lines[j].strip()
            if stripped and not stripped.startswith("```"):
                has_content = True
                break
        # A parent heading followed by a sub-heading is valid (e.g., # Title → ## Overview)
        if not has_content and idx + 1 < len(heading_lines):
            current_level = len(line) - len(line.lstrip("#"))
            next_level = len(heading_lines[idx + 1][1]) - len(heading_lines[idx + 1][1].lstrip("#"))
            if next_level > current_level:
                continue  # Sub-heading follows — not truly empty
            section_name = re.sub(r"^#{1,3}\s+", "", line).strip()
            checks.append(_check(
                "no_empty_sections", "fail",
                f"Empty section: '{section_name}'",
                "structure",
            ))

    if not any(c["check"] == "no_empty_sections" for c in checks):
        checks.append(_check("no_empty_sections", "pass", "", "structure"))

    return checks


def check_anti_patterns(body: str) -> list[dict]:
    """Detect narrative storytelling, multi-language dilution, etc."""
    checks = []

    # Narrative storytelling: "In session X", "In one case", "For example, in a project"
    narrative_patterns = [
        r"\bIn session\b",
        r"\bIn one case\b",
        r"\bIn a recent\b",
        r"\bFor example, in a project\b",
    ]
    narrative_found = []
    for pattern in narrative_patterns:
        matches = re.findall(pattern, body, re.IGNORECASE)
        if matches:
            narrative_found.extend(matches)

    if narrative_found:
        checks.append(_check(
            "no_narrative_storytelling", "warn",
            f"Detected narrative patterns: {', '.join(narrative_found[:3])}",
            "anti_pattern",
        ))
    else:
        checks.append(_check("no_narrative_storytelling", "pass", "", "anti_pattern"))

    # Multi-language dilution: count code blocks by language
    code_blocks = re.findall(r"```(\w+)?", body)
    languages = [lang.lower() for lang in code_blocks if lang]
    unique_langs = set(languages)
    if len(unique_langs) > 3:
        checks.append(_check(
            "no_multi_language_dilution", "warn",
            f"Code blocks in {len(unique_langs)} languages: {', '.join(sorted(unique_langs))}",
            "anti_pattern",
        ))
    else:
        checks.append(_check("no_multi_language_dilution", "pass", "", "anti_pattern"))

    return checks


def check_best_practices(skill_path: Path, body: str) -> list[dict]:
    """Check progressive disclosure, terminology, examples."""
    checks = []

    # Progressive disclosure: uses references/ directory?
    refs_dir = skill_path / "references"
    if refs_dir.is_dir() and any(refs_dir.iterdir()):
        checks.append(_check("progressive_disclosure", "pass", "references/ directory with files", "best_practice"))
    else:
        word_count = len(body.split())
        if word_count > 300:
            checks.append(_check(
                "progressive_disclosure", "warn",
                f"No references/ directory but body is {word_count} words — consider extracting detail",
                "best_practice",
            ))
        else:
            checks.append(_check("progressive_disclosure", "pass", "Compact skill, references/ not needed", "best_practice"))

    # Example count
    example_markers = len(re.findall(r"(?:^|\n)(?:#{1,3}\s+)?(?:Example|```)", body))
    if example_markers == 0:
        checks.append(_check("has_examples", "warn", "No examples or code blocks found", "best_practice"))
    else:
        checks.append(_check("has_examples", "pass", f"{example_markers} example/code markers", "best_practice"))

    return checks


def check_scripts(skill_path: Path) -> list[dict]:
    """If scripts/ exists, check each .py compiles, has docstring, has main()."""
    checks = []
    scripts_dir = skill_path / "scripts"
    if not scripts_dir.is_dir():
        return checks

    py_files = sorted(scripts_dir.glob("*.py"))
    for py_file in py_files:
        if py_file.name == "__init__.py":
            continue

        source = py_file.read_text()

        # Check compilation
        try:
            compile(source, str(py_file), "exec")
            checks.append(_check(f"script_compiles:{py_file.name}", "pass", "", "scripts"))
        except SyntaxError as e:
            checks.append(_check(f"script_compiles:{py_file.name}", "fail", str(e), "scripts"))
            continue

        # Check docstring
        if re.match(r'^(?:#!.*\n)?(?:\s*\n)*"""', source) or re.match(r"^(?:#!.*\n)?(?:\s*\n)*'''", source):
            checks.append(_check(f"script_docstring:{py_file.name}", "pass", "", "scripts"))
        else:
            checks.append(_check(f"script_docstring:{py_file.name}", "warn", "No module docstring", "scripts"))

        # Check main() and __main__
        has_main_func = bool(re.search(r"^def main\b", source, re.MULTILINE))
        has_main_guard = bool(re.search(r'if __name__\s*==\s*["\']__main__["\']', source))
        if has_main_func and has_main_guard:
            checks.append(_check(f"script_entry_point:{py_file.name}", "pass", "", "scripts"))
        elif has_main_guard:
            checks.append(_check(f"script_entry_point:{py_file.name}", "pass", "Has __main__ guard (no main() func)", "scripts"))
        else:
            checks.append(_check(f"script_entry_point:{py_file.name}", "warn", "Missing main() and/or __main__ guard", "scripts"))

    return checks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def audit_skill(skill_path: Path) -> dict:
    """Run all audit checks on a skill and return the report."""
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return {
            "skill_path": str(skill_path),
            "skill_name": skill_path.name,
            "word_count": 0,
            "line_count": 0,
            "checks": [_check("skill_md_exists", "fail", "SKILL.md not found", "structure")],
            "summary": {"pass": 0, "warn": 0, "fail": 1, "total": 1},
        }

    content = skill_md.read_text()
    fm, body = parse_frontmatter(content)

    all_checks: list[dict] = []
    all_checks.extend(check_name_format(fm))
    all_checks.extend(check_description(fm))
    all_checks.extend(check_token_budget(body, fm))
    all_checks.extend(check_sections(body))
    all_checks.extend(check_anti_patterns(body))
    all_checks.extend(check_best_practices(skill_path, body))
    all_checks.extend(check_scripts(skill_path))

    summary = {
        "pass": sum(1 for c in all_checks if c["status"] == "pass"),
        "warn": sum(1 for c in all_checks if c["status"] == "warn"),
        "fail": sum(1 for c in all_checks if c["status"] == "fail"),
        "total": len(all_checks),
    }

    return {
        "skill_path": str(skill_path),
        "skill_name": fm.get("name", skill_path.name),
        "word_count": len(body.split()),
        "line_count": len(content.splitlines()),
        "checks": all_checks,
        "summary": summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit a skill's structure against best practices")
    parser.add_argument("skill_path", type=Path, help="Path to the skill directory")
    parser.add_argument("--output", type=Path, default=None, help="Output path for audit_report.json")
    args = parser.parse_args()

    skill_path = args.skill_path.resolve()
    if not skill_path.is_dir():
        print(f"Error: {skill_path} is not a directory", file=sys.stderr)
        sys.exit(1)

    report = audit_skill(skill_path)

    output_path = args.output or Path("audit_report.json")
    output_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Audit report written to {output_path}")

    # Print summary
    s = report["summary"]
    print(f"  {s['pass']} pass, {s['warn']} warn, {s['fail']} fail ({s['total']} checks)")
    if s["fail"] > 0:
        for c in report["checks"]:
            if c["status"] == "fail":
                print(f"  FAIL: {c['check']} — {c['detail']}")


if __name__ == "__main__":
    main()

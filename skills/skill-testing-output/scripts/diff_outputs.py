#!/usr/bin/env python3
"""Compare output files between two run configurations.

Provides a structured diff between with_skill and without_skill (or old_skill)
outputs for a single eval, highlighting:
- File presence/absence differences
- Content length differences
- Line-by-line text diffs (for text files)
- Structural differences (for JSON files)

Usage:
    # Compare configs within an eval directory
    python -m scripts.diff_outputs ./workspace/iteration-1/eval-my-test

    # Compare specific directories
    python -m scripts.diff_outputs --dir-a ./with_skill/outputs --dir-b ./without_skill/outputs

    # JSON output
    python -m scripts.diff_outputs ./workspace/iteration-1/eval-my-test --json
"""

import argparse
import difflib
import json
import sys
from pathlib import Path


def diff_text_files(file_a: Path, file_b: Path) -> dict:
    """Diff two text files and return comparison data."""
    text_a = file_a.read_text() if file_a.exists() else ""
    text_b = file_b.read_text() if file_b.exists() else ""

    lines_a = text_a.splitlines(keepends=True)
    lines_b = text_b.splitlines(keepends=True)

    diff_lines = list(
        difflib.unified_diff(
            lines_b,
            lines_a,
            fromfile=str(file_b),
            tofile=str(file_a),
            lineterm="",
        )
    )

    # Compute similarity ratio
    matcher = difflib.SequenceMatcher(None, text_a, text_b)
    similarity = matcher.ratio()

    return {
        "similarity": round(similarity, 4),
        "lines_a": len(lines_a),
        "lines_b": len(lines_b),
        "chars_a": len(text_a),
        "chars_b": len(text_b),
        "diff_lines": len([l for l in diff_lines if l.startswith("+") or l.startswith("-")]),
        "unified_diff": "".join(diff_lines) if diff_lines else "(identical)",
    }


def diff_json_files(file_a: Path, file_b: Path) -> dict:
    """Compare two JSON files structurally."""
    try:
        data_a = json.loads(file_a.read_text()) if file_a.exists() else None
        data_b = json.loads(file_b.read_text()) if file_b.exists() else None
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}"}

    if data_a == data_b:
        return {"identical": True}

    # For dicts, compare keys
    result: dict = {"identical": False}
    if isinstance(data_a, dict) and isinstance(data_b, dict):
        keys_a = set(data_a.keys())
        keys_b = set(data_b.keys())
        result["keys_only_in_a"] = sorted(keys_a - keys_b)
        result["keys_only_in_b"] = sorted(keys_b - keys_a)
        result["keys_different"] = sorted(
            k for k in keys_a & keys_b if data_a[k] != data_b[k]
        )

    return result


def diff_directories(dir_a: Path, dir_b: Path, label_a: str, label_b: str) -> dict:
    """Compare all files across two output directories."""
    files_a = {f.relative_to(dir_a) for f in dir_a.rglob("*") if f.is_file()}
    files_b = {f.relative_to(dir_b) for f in dir_b.rglob("*") if f.is_file()}

    all_files = sorted(files_a | files_b)
    only_in_a = sorted(files_a - files_b)
    only_in_b = sorted(files_b - files_a)
    common = sorted(files_a & files_b)

    comparisons = {}
    for rel_path in common:
        fa = dir_a / rel_path
        fb = dir_b / rel_path

        if rel_path.suffix == ".json":
            comparisons[str(rel_path)] = diff_json_files(fa, fb)
        else:
            comparisons[str(rel_path)] = diff_text_files(fa, fb)

    return {
        "label_a": label_a,
        "label_b": label_b,
        "files_total": len(all_files),
        f"only_in_{label_a}": [str(f) for f in only_in_a],
        f"only_in_{label_b}": [str(f) for f in only_in_b],
        "common_files": len(common),
        "comparisons": comparisons,
    }


def find_config_dirs(eval_dir: Path) -> tuple[Path, str, Path, str] | None:
    """Find the two config directories within an eval directory."""
    candidates = sorted(
        d
        for d in eval_dir.iterdir()
        if d.is_dir() and d.name not in ("inputs",)
    )

    if len(candidates) < 2:
        return None

    # Prefer with_skill as "a" and without_skill/old_skill as "b"
    dir_a = dir_b = None
    label_a = label_b = ""
    for d in candidates:
        if "with_skill" == d.name:
            dir_a = d / "outputs"
            label_a = "with_skill"
        elif d.name in ("without_skill", "old_skill"):
            dir_b = d / "outputs"
            label_b = d.name

    if not dir_a or not dir_b:
        dir_a = candidates[0] / "outputs"
        label_a = candidates[0].name
        dir_b = candidates[1] / "outputs"
        label_b = candidates[1].name

    return dir_a, label_a, dir_b, label_b


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare output files between run configurations"
    )
    parser.add_argument(
        "eval_dir",
        nargs="?",
        type=Path,
        help="Eval directory containing config subdirectories (e.g., with_skill/, without_skill/)",
    )
    parser.add_argument(
        "--dir-a",
        type=Path,
        help="First output directory to compare",
    )
    parser.add_argument(
        "--dir-b",
        type=Path,
        help="Second output directory to compare",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of human-readable text",
    )
    args = parser.parse_args()

    if args.dir_a and args.dir_b:
        dir_a, dir_b = args.dir_a, args.dir_b
        label_a, label_b = dir_a.name, dir_b.name
    elif args.eval_dir:
        result = find_config_dirs(args.eval_dir)
        if not result:
            print(f"Error: Could not find two config directories in {args.eval_dir}", file=sys.stderr)
            sys.exit(1)
        dir_a, label_a, dir_b, label_b = result
    else:
        parser.error("Provide either eval_dir or both --dir-a and --dir-b")
        return

    if not dir_a.is_dir():
        print(f"Error: Directory not found: {dir_a}", file=sys.stderr)
        sys.exit(1)
    if not dir_b.is_dir():
        print(f"Error: Directory not found: {dir_b}", file=sys.stderr)
        sys.exit(1)

    diff_result = diff_directories(dir_a, dir_b, label_a, label_b)

    if args.json:
        print(json.dumps(diff_result, indent=2))
    else:
        print(f"Comparing: {label_a} vs {label_b}")
        print(f"  Files in {label_a} only: {diff_result.get(f'only_in_{label_a}', [])}")
        print(f"  Files in {label_b} only: {diff_result.get(f'only_in_{label_b}', [])}")
        print(f"  Common files: {diff_result['common_files']}")
        print()

        for filename, comparison in diff_result["comparisons"].items():
            if comparison.get("identical"):
                print(f"  {filename}: identical")
            elif "similarity" in comparison:
                sim = comparison["similarity"]
                chars_a = comparison["chars_a"]
                chars_b = comparison["chars_b"]
                print(
                    f"  {filename}: {sim:.0%} similar "
                    f"({chars_a} vs {chars_b} chars, "
                    f"{comparison['diff_lines']} diff lines)"
                )
                if comparison["unified_diff"] != "(identical)" and sim < 0.95:
                    # Show abbreviated diff
                    diff_lines = comparison["unified_diff"].split("\n")
                    for line in diff_lines[:20]:
                        print(f"    {line}")
                    if len(diff_lines) > 20:
                        print(f"    ... ({len(diff_lines) - 20} more lines)")
            elif "error" in comparison:
                print(f"  {filename}: {comparison['error']}")
            else:
                print(f"  {filename}: different")
                if comparison.get("keys_only_in_a"):
                    print(f"    Keys only in {label_a}: {comparison['keys_only_in_a']}")
                if comparison.get("keys_only_in_b"):
                    print(f"    Keys only in {label_b}: {comparison['keys_only_in_b']}")
                if comparison.get("keys_different"):
                    print(f"    Keys with different values: {comparison['keys_different']}")


if __name__ == "__main__":
    main()

"""Skill-testing-output scripts for A/B output comparison.

Invoke from the skill-testing-output directory within the plugin:
    cd <plugin-root>/skills/skill-testing-output
    python -m scripts.init_workspace <skill-name> --evals <evals.json> --output <path>
    python -m scripts.run_comparison --skill-path <path> --evals <evals.json> --workspace <path>
    python -m scripts.diff_outputs <workspace>/iteration-N/eval-name

Prerequisites:
    - claude CLI — required for run_comparison (runs claude -p subprocesses)
"""

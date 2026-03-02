"""Skill-TDD development scripts.

Invoke from the skill-tdd directory within the plugin:
    cd <plugin-root>/skills/skill-tdd
    python -m scripts.scaffold_skill <skill-name> --output <path>
    python -m scripts.run_cycle --skill-path <path> --scenario <file> [--model <model-id>]

Prerequisites:
    - claude CLI — required for run_cycle (runs claude -p subprocesses)
"""

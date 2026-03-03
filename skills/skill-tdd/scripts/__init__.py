"""Skill-TDD development scripts.

Invoke from the skill-tdd skill directory:
    python -m scripts.scaffold_skill <skill-name> --output <path>
    python -m scripts.run_cycle --skill-path <path> --scenario <file> [--model <model-id>]

Prerequisites:
    - Python 3.10+ (scripts use union type syntax)
    - claude CLI — required for run_cycle (runs claude -p subprocesses)
    - If a local .venv exists, activate it first: source .venv/bin/activate
"""

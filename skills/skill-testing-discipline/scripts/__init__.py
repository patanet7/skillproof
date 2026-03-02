"""Skill-testing-discipline scripts for pressure testing.

Invoke from the skill-testing-discipline directory within the plugin:
    cd <plugin-root>/skills/skill-testing-discipline
    python -m scripts.run_pressure_test --skill-path <path> --scenario <file>
    python -m scripts.extract_choice <response-file>

Prerequisites:
    - claude CLI — required for run_pressure_test (runs claude -p subprocesses)
"""

"""Writing-skills evaluation and improvement scripts.

Invoke from the writing-skills directory within the plugin:
    cd <plugin-root>/skills/writing-skills
    python -m scripts.run_loop --eval-set ... --skill-path ...
    python -m scripts.run_eval --eval-set ... --skill-path ...
    python -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <name>
    python -m scripts.quick_validate <skill-directory>

Prerequisites:
    - Python 3.10+ (scripts use union type syntax)
    - anthropic (pip install anthropic) — required for run_loop and improve_description
    - claude CLI — required for run_eval (trigger evaluation)
    - If a local .venv exists, activate it first: source .venv/bin/activate
"""

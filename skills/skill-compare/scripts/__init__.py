"""Skill-compare scripts for head-to-head skill comparison.

Invoke from the skill-compare skill directory:

    # Initialize matchup workspace
    python -m scripts.init_matchup \\
        --skill-a /path/to/skill-a \\
        --skill-b /path/to/skill-b \\
        --evals evals.json \\
        --output /tmp/skillproof/<matchup-name>

    # Run both skills against all evals
    python -m scripts.run_matchup \\
        --workspace ./matchup-workspace/iteration-1

    # Summarize matchup results
    python -m scripts.summarize_matchup \\
        --workspace ./matchup-workspace/iteration-1

Prerequisites:
    - Python 3.10+ (scripts use union type syntax)
    - claude CLI — required for run_matchup (runs claude -p subprocesses)
    - If a local .venv exists, activate it first: source .venv/bin/activate
"""

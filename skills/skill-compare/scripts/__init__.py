"""Skill-compare scripts for head-to-head skill comparison.

Invoke from the skill-compare directory within the plugin:
    cd <plugin-root>/skills/skill-compare

    # Initialize matchup workspace
    python -m scripts.init_matchup \\
        --skill-a /path/to/skill-a \\
        --skill-b /path/to/skill-b \\
        --evals evals.json \\
        --output ./matchup-workspace

    # Run both skills against all evals
    python -m scripts.run_matchup \\
        --workspace ./matchup-workspace/iteration-1

    # Summarize matchup results
    python -m scripts.summarize_matchup \\
        --workspace ./matchup-workspace/iteration-1

Prerequisites:
    - claude CLI — required for run_matchup (runs claude -p subprocesses)
"""

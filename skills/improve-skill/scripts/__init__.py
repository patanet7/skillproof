"""Improve-skill scripts for evidence-based skill improvement.

Invoke from the improve-skill directory within the plugin:
    cd <plugin-root>/skills/improve-skill

    # Initialize improvement workspace (runs audit + scaffolds evals)
    python -m scripts.init_improvement /path/to/skill -o ./workspace

    # Diagnose issues from a testing workspace
    python -m scripts.diagnose_workspace ./workspace/iteration-1 --output diagnosis.json

    # Generate a prioritized improvement plan
    python -m scripts.plan_improvements \\
        --audit ./workspace/audit_report.json \\
        --diagnosis ./workspace/diagnosis.json

    # Compare before/after iterations
    python -m scripts.compare_iterations \\
        --before ./workspace/diagnosis.json \\
        --after ./workspace/diagnosis_v2.json

    # Standalone audit (no workspace needed)
    python -m scripts.audit_skill /path/to/skill

Prerequisites:
    - Python 3.10+ (scripts use union type syntax; no external dependencies)
    - skill-testing-output scripts for running baseline/validation tests
    - writing-skills grader agent for grading results
"""

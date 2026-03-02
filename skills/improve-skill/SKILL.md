---
name: improve-skill
description: Use when reviewing, auditing, or improving an existing skill — whether
  it's not triggering correctly, producing poor outputs, too verbose, or you want
  to systematically evaluate and enhance its quality
---

# Improving Skills

## Overview

Evidence-based skill improvement. Audit the skill's structure, test it against real tasks, diagnose failures from grading data, build a prioritized improvement plan, apply fixes, and validate that changes actually helped. The whole cycle runs automatically.

**Core principle:** Evidence over intuition. Every improvement cites a failing assertion, a user complaint, or a lost comparison.

## When to Use

- "This skill isn't working well"
- "Improve this skill"
- "Review this skill"
- "Is this skill any good?"

## When NOT to Use

- **Writing a new skill from scratch** — use `writing-skills`
- **Choosing between two skills** — use `skill-compare` first, then improve the winner
- **Only the description needs work** — flag it here, fix with `writing-skills` Phase 6

## Step 1: Init Workspace + Audit

Initialize the improvement workspace. This runs the structural audit and auto-generates evals from the skill's checklist items and step headings:

```bash
python -m scripts.init_improvement /path/to/skill -o ./workspace
```

Review `audit_report.json` for structural findings. Review `evals.json` — the generated assertions come from the skill's own checklist, so they should be meaningful. Refine any that don't capture key behaviors well enough.

If the user provides an existing testing workspace or evals file, use `--workspace` or `--evals` flags.

## Step 2: Baseline (RED)

Run the skill against the evals to measure how it performs NOW, before any changes. Use `skill-testing-output`:

```bash
python -m scripts.init_workspace <name> --evals <workspace>/evals.json -o <workspace>
python -m scripts.run_comparison --skill-path /path/to/skill --evals <workspace>/evals.json --workspace <workspace>/iteration-1
```

Grade the results with the `writing-skills/agents/grader.md` subagent. Aggregate benchmarks:

```bash
python -m scripts.aggregate_benchmark <workspace>/iteration-1 --skill-name <name>
```

This is your baseline. Don't skip it.

## Step 3: Diagnose

Extract evidence from the baseline results:

```bash
python -m scripts.diagnose_workspace <workspace>/iteration-1 --output <workspace>/diagnosis.json
```

This surfaces: always-failing assertions (systematic weakness), inconsistent assertions (flaky behavior), user complaints, comparison losses, benchmark regressions.

## Step 4: Plan

Merge the audit findings and diagnosis evidence into a prioritized improvement plan:

```bash
python -m scripts.plan_improvements --audit <workspace>/audit_report.json --diagnosis <workspace>/diagnosis.json --output <workspace>/improvement_plan.json
```

This produces `improvement_plan.json` + `improvement_plan.md`. Priority: critical > high > medium > low. Present `improvement_plan.md` to the user for review before proceeding.

## Step 5: Apply Improvements

Work through improvements by priority (critical first). For each improvement:

1. Read the evidence — what exactly failed and why
2. Propose the change — explain how it addresses the evidence
3. Apply it — edit SKILL.md or associated files
4. Don't overfit — generalize from evidence, don't just patch the specific test case

One at a time. Every change cites its evidence source. If an improvement adds significant detail, put it in `references/` (progressive disclosure).

## Step 6: Validate (GREEN)

Re-run the same tests against the improved skill. Use a new iteration:

```bash
python -m scripts.run_comparison --skill-path /path/to/skill --evals <workspace>/evals.json --workspace <workspace>/iteration-2
```

Grade and aggregate as in Step 2. Then diagnose the new results and compare against baseline:

```bash
python -m scripts.diagnose_workspace <workspace>/iteration-2 --output <workspace>/diagnosis_v2.json
python -m scripts.compare_iterations --before <workspace>/diagnosis.json --after <workspace>/diagnosis_v2.json --output <workspace>/comparison_report.json
```

`comparison_report.md` shows resolved issues, new regressions, persistent problems, and benchmark deltas. If critical issues remain or regressions appeared, return to Step 5.

## Step 7: Triage Description Issues

If the audit flagged description problems (workflow summary, missing "Use when", length), they appear in the improvement plan under "Description Issues (Triaged)."

Don't fix descriptions here — use `writing-skills` Phase 6 description optimization loop for systematic eval-based scoring.

## Bundled Scripts

| Script | Purpose | Step |
|--------|---------|------|
| `scripts/init_improvement.py` | Scaffold workspace, run audit, generate evals from skill content | 1 |
| `scripts/audit_skill.py` | Structural quality audit against best practices | 1 (called by init) |
| `scripts/diagnose_workspace.py` | Evidence extraction from testing workspace | 3, 6 |
| `scripts/plan_improvements.py` | Prioritized improvement plan from audit + diagnosis | 4 |
| `scripts/compare_iterations.py` | Quantitative before/after comparison | 6 |

## Skill Constellation

- **skillproof:skill-testing-output** — Baseline and validation tests (Steps 2, 6)
- **skillproof:writing-skills** — Grading agent (Steps 2, 6); Phase 6 for description optimization (Step 7)
- **skillproof:skill-compare** — Alternative validation via head-to-head matchup (Step 6)
- **skillproof:skill-tdd** — RED-GREEN-REFACTOR cycle underpinning this workflow

## Checklist

- [ ] Initialized workspace, reviewed audit and generated evals
- [ ] Ran baseline tests, graded, aggregated benchmark
- [ ] Diagnosed baseline evidence
- [ ] Generated improvement plan, reviewed with user
- [ ] Applied improvements by priority with evidence citations
- [ ] Re-ran tests, diagnosed, compared iterations
- [ ] Triaged description issues for writing-skills Phase 6

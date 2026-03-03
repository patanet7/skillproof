---
name: skill-compare
description: Use when comparing two skills head-to-head on the same tasks to determine
  which produces better results — for choosing between skill versions, competing
  approaches, or validating that a rewrite improves on the original
allowed-tools: Read, Glob, Grep, Bash(cd *), Bash(bash *), Bash(python *), Bash(mkdir *), Read(/tmp/skillproof/**), Write(/tmp/skillproof/**), Edit(/tmp/skillproof/**)
---

# Comparing Skills Head-to-Head

## Overview

Compare two skills by running both against the same evals, grading outputs independently, then running a blind A/B comparison. Produces a matchup report with a winner, quantitative comparison, and per-eval breakdown.

**Core principle:** Blind comparison removes confirmation bias. Neither you nor the comparator agent should know which output came from which skill until after scoring.

## When to Use

**Use when:**
- Choosing between two versions of a skill (old vs rewrite)
- Comparing competing approaches to the same problem
- Validating that a rewrite actually improves on the original
- A/B testing two skills from different authors

**Do NOT use when:**
- Testing a skill against no-skill baseline (use `skillproof:skill-testing-output`)
- Testing rule compliance under pressure (use `skillproof:skill-testing-discipline`)
- You only have one skill and want to evaluate it

## Step 1: Define the Matchup

Identify the two skills and what they claim to do.

**Determine:**
- What does each skill claim to improve?
- Where do their approaches differ?
- What overlapping capabilities should be compared?
- What does "better" mean for this comparison? (quality, speed, completeness, correctness)

Name the matchup clearly: `"my-tdd-skill vs my-tdd-skill-v2"` or `"approach-a vs approach-b"`.

## Step 2: Create Shared Evals

Write 2-3 prompts that exercise BOTH skills' claims. Save to `evals/evals.json`:

```json
{
  "skill_name": "matchup-name",
  "evals": [
    {
      "id": 1,
      "name": "descriptive-eval-name",
      "prompt": "Realistic user task that both skills should handle",
      "expected_output": "What good output looks like",
      "assertions": [
        "Output includes X",
        "Output follows pattern Y"
      ]
    }
  ]
}
```

Key: prompts must be fair to both skills. Don't write prompts that favor one approach.

## Step 3: Initialize Workspace

```bash
# From this skill's base directory:
python -m scripts.init_matchup \
    --skill-a /path/to/skill-a \
    --skill-b /path/to/skill-b \
    --evals evals.json \
    --output /tmp/skillproof/<matchup-name> \
    --runs 3
```

**Important:** Always use `/tmp/skillproof/` (or another path outside the project repo) for workspace output. Create directories on demand with `mkdir -p`.

This creates the workspace with `matchup.json`, eval directories, and `run-N/outputs/` per eval per config per run.

## Step 4: Run Both Skills

```bash
python -m scripts.run_matchup \
    --workspace ./matchup-workspace/iteration-1 \
    --max-workers 4
```

Both skills execute against every eval prompt in parallel via `claude -p`. Outputs saved to `run-N/outputs/response.txt`, timing to `run-N/timing.json`.

## Step 5: Grade Outputs

Spawn a grader subagent for EACH run directory using `grader.md`:

```
Grade this run:
- Eval metadata: <workspace>/eval-<name>/eval_metadata.json
- Run directory: <workspace>/eval-<name>/<config>/run-<N>/
- Save grading.json to the run directory
```

The grader evaluates each assertion as PASS/FAIL with evidence, extracts implicit claims, and critiques the eval.

## Step 6: Aggregate Benchmark

Run the shared benchmark aggregator from writing-skills:

```bash
# From the writing-skills sibling directory (../writing-skills):
python -m scripts.aggregate_benchmark \
    <workspace>/iteration-1 \
    --skill-name "matchup-name"
```

Produces `benchmark.json` and `benchmark.md` with pass_rate, time, and tokens per config (mean +/- stddev).

## Step 7: Blind Comparison

For each eval, spawn a comparator subagent using `comparator.md`.

**Randomize A/B assignment per eval to prevent position bias:**
- Eval 1: A = skill-a, B = skill-b
- Eval 2: A = skill-b, B = skill-a (swapped)
- Eval 3: A = skill-a, B = skill-b (or random)

Give the comparator both outputs without revealing which skill produced which:

```
Compare these two outputs:
- Output A: <read from one config's outputs/>
- Output B: <read from other config's outputs/>
- Task prompt: <from eval_metadata.json>
- Assertions: <from eval_metadata.json>
- Save comparison.json to <workspace>/eval-<name>/comparison.json
```

After saving `comparison.json`, add a `_label_map` field recording which config was A and which was B:

```json
{
  "_label_map": {"A": "my-skill", "B": "my-skill-v2"},
  "winner": "A",
  "reasoning": "..."
}
```

## Step 8: Analyze (Optional)

For deeper insights, spawn an analyzer subagent using `analyzer.md`:

```
Analyze comparison results:
- Comparison: <workspace>/eval-<name>/comparison.json
- Skill A: <path-to-skill-a>/SKILL.md
- Skill B: <path-to-skill-b>/SKILL.md
- Identify winner strengths, loser weaknesses, improvement suggestions
```

This is optional — most useful when results are close and you want to understand WHY one skill won.

## Step 9: Present Results

**Launch the eval viewer** for visual review:

```bash
# From the writing-skills sibling directory (../writing-skills):
nohup python eval-viewer/generate_review.py \
    <workspace>/iteration-1 \
    --skill-name "matchup-name" \
    --benchmark <workspace>/iteration-1/benchmark.json \
    > /dev/null 2>&1 &
```

**Generate the matchup report:**

```bash
# From this skill's base directory:
python -m scripts.summarize_matchup \
    --workspace ./matchup-workspace/iteration-1
```

Produces `matchup_report.md` with:
- Overall winner (blind wins primary, pass_rate delta tiebreaker)
- Quantitative comparison table
- Per-eval results with winner and differentiators
- Blind comparison tally

Present both the matchup report and the eval viewer to the user for final judgment.

## Workspace Organization

```
matchup-workspace/
└── iteration-1/
    ├── eval-code-review/
    │   ├── my-tdd-skill/
    │   │   ├── run-1/
    │   │   │   ├── outputs/response.txt
    │   │   │   ├── grading.json
    │   │   │   └── timing.json
    │   │   └── run-2/...
    │   ├── my-tdd-skill-v2/
    │   │   ├── run-1/...
    │   │   └── run-2/...
    │   ├── eval_metadata.json
    │   └── comparison.json
    ├── eval-refactoring/...
    ├── matchup.json
    ├── benchmark.json
    ├── benchmark.md
    └── matchup_report.md
```

This layout is compatible with `aggregate_benchmark.py` (discovers configs dynamically), `generate_review.py` (discovers `outputs/` recursively), and `diff_outputs.py` (falls back to first two directories).

## Bundled Scripts

Run from the skill-compare directory within the plugin:

```bash
# From this skill's base directory:
```

| Script | Purpose | When to use |
|--------|---------|-------------|
| `python -m scripts.init_matchup --skill-a <path> --skill-b <path> --evals <evals.json>` | Create matchup workspace | Step 3 |
| `python -m scripts.run_matchup --workspace <iteration-dir>` | Run both skills against all evals | Step 4 |
| `python -m scripts.summarize_matchup --workspace <iteration-dir>` | Generate matchup report from results | Step 9 |

For grading, benchmarking, and viewing, use the shared `writing-skills` scripts:

```bash
# From the writing-skills sibling directory (../writing-skills):
python -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <name>
python eval-viewer/generate_review.py <workspace>/iteration-N --skill-name <name>
```

**Prerequisites:** Python 3.10+, `claude` CLI. Activate `.venv` if available.

## Checklist

- [ ] Identified two skills and their claims
- [ ] Created 2-3 shared evals fair to both skills
- [ ] Initialized matchup workspace with init_matchup
- [ ] Ran both skills with run_matchup
- [ ] Graded each run with grader subagent
- [ ] Aggregated benchmark with aggregate_benchmark
- [ ] Ran blind comparison with randomized A/B per eval
- [ ] Generated matchup report with summarize_matchup
- [ ] Presented results and eval viewer to user

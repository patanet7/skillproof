---
name: skill-testing-output
description: Use when evaluating whether a skill measurably improves outputs by running controlled comparisons — with-skill vs without-skill, old version vs new version, or A/B tests across skill variants — where quality is graded on produced artifacts like code, docs, migrations, or commit messages
---

# Testing Output-Quality Skills

## Overview

Test skills by comparing output quality with and without the skill. Run the same prompt both ways, grade the difference, and iterate until the skill consistently produces better results.

**Core principle:** If you can't measure the output quality difference, you don't know if the skill helps. Subjective impressions are not evidence. Run structured comparisons, grade with assertions, and benchmark the delta.

## When to Use

**Use when testing:**
- Tool/workflow skills (file converters, formatters, automation)
- Technique skills (debugging approaches, code patterns)
- Any skill where output quality matters more than rule compliance

**Do NOT use for:**
- Discipline skills where compliance matters more than output quality (use `skillproof:skill-testing-discipline`)

## Test Case Design

Create 2-3 realistic test prompts — the kind of thing a real user would actually say. Share them with the user for review.

Save test cases to `evals/evals.json`:

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "User's task prompt",
      "expected_output": "Description of expected result",
      "files": []
    }
  ]
}
```

Don't write assertions yet — just prompts. You'll draft assertions while runs are in progress.

See `../writing-skills/references/schemas.md` for the full schema.

## Running Tests

### Spawn All Runs in the Same Turn

For each test case, spawn TWO subagents simultaneously — one with the skill, one without. Launch everything at once so it all finishes around the same time.

**With-skill run:**
```
Execute this task:
- Skill path: <path-to-skill>
- Task: <eval prompt>
- Input files: <eval files if any>
- Save outputs to: <workspace>/iteration-<N>/eval-<ID>/with_skill/outputs/
```

**Baseline run:**
- **Creating a new skill:** No skill at all. Same prompt, save to `without_skill/outputs/`
- **Improving an existing skill:** Snapshot the old version first (`cp -r`), point baseline at snapshot. Save to `old_skill/outputs/`

Write an `eval_metadata.json` for each test case:

```json
{
  "eval_id": 0,
  "eval_name": "descriptive-name-here",
  "prompt": "The user's task prompt",
  "assertions": []
}
```

Give each eval a descriptive name based on what it tests, not just "eval-0".

## Drafting Assertions

While runs are in progress, draft quantitative assertions. Good assertions are:
- **Objectively verifiable** — can be checked by reading outputs
- **Descriptively named** — readable at a glance in the benchmark viewer
- **Discriminating** — pass when skill genuinely succeeds, fail when it doesn't

Subjective skills (writing style, design quality) are better evaluated qualitatively. Don't force assertions onto things that need human judgment.

Update `eval_metadata.json` and `evals/evals.json` with assertions.

## Capturing Timing

When each subagent task completes, the notification contains `total_tokens` and `duration_ms`. Save immediately to `timing.json`:

```json
{
  "total_tokens": 84852,
  "duration_ms": 23332,
  "total_duration_seconds": 23.3
}
```

This is the only opportunity to capture this data — it comes through the notification and isn't persisted elsewhere.

## Grading

Spawn a grader subagent using `../writing-skills/agents/grader.md`:
- Reads the execution transcript and output files
- Evaluates each assertion: PASS or FAIL with evidence
- Extracts and verifies implicit claims from outputs
- Critiques the evals themselves (flags weak assertions)

Save results to `grading.json` in each run directory. The grading.json expectations array must use fields `text`, `passed`, and `evidence`.

For assertions checkable programmatically, write and run a script — scripts are faster and more reliable than eyeballing.

## Benchmarking

Aggregate results across all runs:

```bash
python -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <name>
```

Produces `benchmark.json` and `benchmark.md` with pass_rate, time, and tokens for each configuration, with mean ± stddev and delta.

See `../writing-skills/references/schemas.md` for the benchmark.json format.

## Viewing Results

Launch the browser-based reviewer:

```bash
nohup python ../writing-skills/eval-viewer/generate_review.py \
  <workspace>/iteration-N \
  --skill-name "my-skill" \
  --benchmark <workspace>/iteration-N/benchmark.json \
  > /dev/null 2>&1 &
```

For iteration 2+, add `--previous-workspace <workspace>/iteration-N-1>`.

**Cowork / headless:** Use `--static <output_path>` for standalone HTML.

The user sees two tabs:
- **Outputs** — click through test cases, leave feedback per case
- **Benchmark** — quantitative comparison with pass rates, timing, token usage

When done, user clicks "Submit All Reviews" → `feedback.json`.

## Reading Feedback

```json
{
  "reviews": [
    {"run_id": "eval-0-with_skill", "feedback": "chart missing axis labels", "timestamp": "..."},
    {"run_id": "eval-1-with_skill", "feedback": "", "timestamp": "..."}
  ]
}
```

Empty feedback = user thought it was fine. Focus improvements on test cases with specific complaints.

## Iterative Improvement Philosophy

### Generalize from feedback

The skill will be used many times across many prompts. You and the user iterate on only a few examples because it's fast. But if the skill works only for those examples, it's useless. Rather than fiddly overfitting changes, try different metaphors, recommend different patterns. It's cheap to try.

### Keep the prompt lean

Remove things that aren't pulling their weight. Read the transcripts — if the skill makes the agent waste time on unproductive steps, remove those parts and see what happens.

### Explain the why

Use theory of mind. Today's LLMs are smart. When given good reasoning, they go beyond rote instructions. If you find yourself writing ALWAYS or NEVER in all caps, reframe: explain the reasoning so the model understands why it matters.

### Look for repeated work

Read transcripts from test runs. If all test cases result in the agent writing a similar helper script, that script should be bundled in `scripts/`. Write it once, save every future invocation from reinventing the wheel.

### Read transcripts, not just outputs

The output may look fine while the process was wasteful or fragile.

## The Iteration Loop

After improving the skill:

1. Apply improvements to the skill
2. Rerun all test cases into a new `iteration-<N+1>/` directory, including baselines
3. Launch viewer with `--previous-workspace` pointing at previous iteration
4. Wait for user review
5. Read feedback, improve again, repeat

Keep going until:
- User says they're happy
- Feedback is all empty
- Not making meaningful progress

## Blind Comparison (Optional)

For rigorous comparison between two skill versions:

1. Use `../writing-skills/agents/comparator.md` — give two outputs labeled A/B without revealing which skill produced which
2. Use `../writing-skills/agents/analyzer.md` — analyze WHY the winner won

Optional, requires subagents, most users don't need it. The human review loop is usually sufficient.

## Workspace Organization

```
skill-name-workspace/
└── iteration-1/
    ├── eval-descriptive-name/
    │   ├── with_skill/
    │   │   ├── outputs/
    │   │   └── timing.json
    │   ├── without_skill/
    │   │   ├── outputs/
    │   │   └── timing.json
    │   ├── eval_metadata.json
    │   └── grading.json
    ├── benchmark.json
    ├── benchmark.md
    └── feedback.json
```

## Platform Notes

**Claude Code:** Full functionality — subagents, browser viewer, all scripts.

**Claude.ai:** No subagents. Run test cases yourself one at a time. Skip baselines. Present results inline and ask for feedback directly. Skip benchmarking.

**Cowork:** Subagents work. Use `--static` for viewer (no browser). Feedback downloads as file.

## Bundled Scripts

Run from the skill-testing-output directory within the plugin:

```bash
cd <plugin-root>/skills/skill-testing-output
```

| Script | Purpose | When to use |
|--------|---------|-------------|
| `python -m scripts.init_workspace <name> --evals <evals.json>` | Create workspace directory structure | Before running comparisons |
| `python -m scripts.run_comparison --skill-path <path> --evals <evals.json> --workspace <path>` | Run A/B comparisons via `claude -p` | Executing eval runs |
| `python -m scripts.run_comparison --baseline-skill <old-path>` | Compare two skill versions | Old vs new skill testing |
| `python -m scripts.diff_outputs <workspace>/iteration-N/eval-name` | Compare output files between configs | Reviewing output differences |

For grading and benchmarking, use the shared `writing-skills` scripts:

```bash
cd <plugin-root>/skills/writing-skills
python -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <name>
```

**Prerequisites:** `claude` CLI required for `run_comparison`.

## Testing Checklist

- [ ] Created 2-3 realistic test prompts
- [ ] Saved to evals/evals.json
- [ ] Spawned with-skill + baseline runs in parallel
- [ ] Drafted assertions while runs proceeded
- [ ] Captured timing data from notifications
- [ ] Graded each run with grader subagent
- [ ] Aggregated into benchmark.json
- [ ] Launched viewer for user review
- [ ] Read feedback and improved skill
- [ ] Repeated until user satisfied

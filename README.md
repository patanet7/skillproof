# skillproof

A Claude Code plugin for building skills that actually work. Test-driven, with real evidence.

You tell Claude what skill you want. It runs agents without the skill, watches them fail, writes the skill to fix those failures, then proves the skill works by running agents again. No guessing.

## Install

```bash
# Clone and point Claude at it
git clone https://github.com/patanet7/skillproof.git
claude --plugin-dir /path/to/skillproof
```

## Setup

**All workspace output goes to `/tmp/skillproof/`**, never inside your project repo. Skills create workspace directories on demand — no hooks, no environment variables. `/tmp` is cleaned automatically by the OS on reboot.

To allow Claude to read plugin reference files (e.g., `references/best-practices.md`, `agents/grader.md`) without prompting, add this to your `~/.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "Read(~/.claude/plugins/cache/**)"
    ]
  }
}
```

This is a one-time setup. Without it, Claude will prompt for permission each time a skill reads a reference file from the plugin cache.

Once loaded, you get six slash commands:

```
/skillproof:writing-skills              # The main one. Start here.
/skillproof:skill-tdd                   # TDD methodology (RED-GREEN-REFACTOR)
/skillproof:skill-testing-discipline    # Pressure testing for rule-enforcement skills
/skillproof:skill-testing-output        # A/B output quality comparison
/skillproof:skill-compare               # Head-to-head skill comparison
/skillproof:improve-skill               # Evidence-based skill improvement
```

## How it works

### You say what you want. Claude does the rest.

Tell Claude you want to create a skill:

```
I want to create a skill that teaches agents to always verify their work
before claiming it's done.
```

Claude loads `writing-skills` and walks through 6 phases automatically:

**Phase 1 — Capture Intent.** Claude asks you clarifying questions. What should the skill do? When should it trigger? What type is it? (Discipline skills enforce rules. Workflow skills teach techniques. Reference skills document APIs.)

**Phase 2 — Baseline (RED).** Claude spawns a subagent, gives it a task *without* the skill, and watches it fail. This is the critical part. You see exactly what agents do wrong before the skill exists. No hypothesizing — actual observed failures.

**Phase 3 — Draft (GREEN).** Claude writes a minimal skill that addresses the specific failures it documented. Not a wish list — just enough to fix what it saw break.

**Phase 4 — Evaluate.** Claude runs the same scenarios *with* the skill loaded. It grades the results with assertions. Opens a browser-based viewer so you can compare outputs side by side and leave feedback.

**Phase 5 — Refine (REFACTOR).** Based on your feedback, Claude tightens the skill. For discipline skills, this means capturing new rationalizations agents use to wiggle out of rules and adding explicit counters. For workflow skills, it means improving output quality. Repeat phases 4-5 until you're happy.

**Phase 6 — Optimize & Deploy.** Claude generates 20 test queries to evaluate whether the skill's description triggers correctly (fires when it should, stays quiet when it shouldn't). Runs an optimization loop, picks the best description by test score, validates the structure, and it's ready to ship.

### What triggers automatically

When Claude loads `writing-skills`, it pulls in the companion skills as needed:

- **Discipline skill detected** → loads `skill-testing-discipline` for pressure testing
- **Workflow/technique skill detected** → loads `skill-testing-output` for A/B comparison
- **Comparing two skills** → loads `skill-compare` for head-to-head matchup
- **Any skill creation** → loads `skill-tdd` for the RED-GREEN-REFACTOR cycle

You don't need to invoke these manually. They compose.

## The six skills

### `writing-skills` — Orchestrator

The main entry point. Guides the full 6-phase flow and routes to the right testing strategy based on skill type.

Comes with:
- **Scripts** — description optimization loop, trigger evaluation, benchmark aggregation, structure validation, skill packaging
- **Agents** — grader (assertion evaluation), comparator (blind A/B), analyzer (post-comparison)
- **Eval viewer** — browser-based review UI with side-by-side output comparison and feedback collection
- **References** — authoring best practices, description optimization guide, JSON schemas

### `skill-tdd` — TDD methodology

The testing discipline itself. Maps TDD concepts to skill development:

| TDD | Skill creation |
|-----|----------------|
| Write failing test | Run scenario WITHOUT skill, watch agent fail |
| Write minimal code | Write skill addressing those specific failures |
| Watch it pass | Run scenario WITH skill, verify improvement |
| Refactor | Close loopholes, tighten wording, re-test |

Iron law: **no skill without a failing test first.** Write skill before testing? Delete it. Start over.

Comes with:
- `scaffold_skill` — create a new skill directory with the right template for the skill type
- `run_cycle` — run a RED-GREEN cycle: execute a scenario without the skill, then with it, save both for comparison

### `skill-testing-discipline` — Pressure testing

For skills that enforce rules agents have incentive to bypass. Tests whether agents comply under realistic pressure — not just whether they can recite the rules.

Combines 3+ pressures (time, sunk cost, authority, exhaustion, pragmatic appeal) and forces explicit A/B/C choices. Captures exact rationalizations verbatim so you know which loopholes to close.

Comes with:
- `run_pressure_test` — run pressure scenarios with/without a skill, track compliance rates across multiple runs
- `extract_choice` — parse agent responses for A/B/C choices and rationalizations (single files or entire workspaces)
- `references/scenario_templates.md` — 5 ready-to-use pressure templates with 3+ combined pressures each

### `skill-testing-output` — A/B output comparison

For skills where output quality matters more than rule compliance. Runs the same prompts with and without the skill, grades the difference with assertions, benchmarks the delta.

Comes with:
- `init_workspace` — create the workspace directory structure from an evals file
- `run_comparison` — run parallel A/B comparisons via `claude -p` (with-skill vs without-skill, or old version vs new version)
- `diff_outputs` — compare output files between configurations with similarity scoring and unified diffs

### `skill-compare` — Head-to-head comparison

For choosing between two skills — different versions, competing approaches, or validating a rewrite. Runs both skills against the same evals, grades independently, then runs blind A/B comparison with randomized label assignment to prevent position bias.

Comes with:
- `init_matchup` — create a matchup workspace from two skill paths and an evals file
- `run_matchup` — run both skills against all evals in parallel via `claude -p`
- `summarize_matchup` — produce a matchup report with winner, quantitative comparison, and blind tally

Uses grading, benchmarking, and viewing infrastructure from `writing-skills`.

### `improve-skill` — Evidence-based improvement

For skills that exist but aren't performing well. Reads actual test evidence — grading failures, user feedback, comparison losses, benchmark data — to diagnose what's wrong, then generates a prioritized improvement plan.

Works in two modes:
- **Audit-only** — structural quality check against best practices (no workspace needed)
- **Full diagnosis** — audit + evidence extraction from a testing workspace

Comes with:
- `init_improvement` — scaffold improvement workspace, run audit, generate eval skeleton
- `audit_skill` — structural quality audit (frontmatter, token budget, anti-patterns, scripts)
- `diagnose_workspace` — extract failing assertions, complaints, and losses from test workspaces
- `plan_improvements` — merge audit + diagnosis into a prioritized improvement plan
- `compare_iterations` — quantitative before/after comparison with regression detection

Flags description issues for `writing-skills` Phase 6 rather than attempting manual fixes.

## Running scripts manually

Scripts use Python relative imports. Always `cd` into the skill's directory first. When skills are loaded by Claude, it knows the base directory automatically. For manual use, navigate to the skill directory within the plugin:

```bash
# ── skill-tdd ──────────────────────────────────────────────
# cd into skills/skill-tdd

# Scaffold a new skill
python -m scripts.scaffold_skill my-new-skill -o ~/my-skills -t discipline

# Run a RED-GREEN cycle
python -m scripts.run_cycle \
  --skill-path ~/my-skills/my-new-skill \
  --scenario scenario.txt

# ── skill-testing-discipline ───────────────────────────────
# cd into skills/skill-testing-discipline

# Run pressure tests
python -m scripts.run_pressure_test \
  --skill-path ~/my-skills/my-new-skill \
  --scenario scenario.txt \
  --correct-choice A \
  --runs 3

# Extract choices from responses
python -m scripts.extract_choice --workspace ./pressure-workspace/20260302T120000

# ── skill-testing-output ───────────────────────────────────
# cd into skills/skill-testing-output

# Initialize A/B comparison workspace
python -m scripts.init_workspace my-skill --evals evals.json -o /tmp/skillproof/my-skill-workspace

# Run A/B comparisons
python -m scripts.run_comparison \
  --skill-path ~/my-skills/my-new-skill \
  --evals evals.json \
  --workspace /tmp/skillproof/my-skill-workspace/iteration-1

# Diff the outputs
python -m scripts.diff_outputs /tmp/skillproof/my-skill-workspace/iteration-1/eval-my-test

# ── skill-compare ──────────────────────────────────────────
# cd into skills/skill-compare

# Initialize matchup workspace (two-skill comparison)
python -m scripts.init_matchup \
  --skill-a ~/my-skills/my-skill-v1 \
  --skill-b ~/my-skills/my-skill-v2 \
  --evals evals.json \
  --output /tmp/skillproof/my-matchup --runs 3

# Run both skills against all evals
python -m scripts.run_matchup \
  --workspace /tmp/skillproof/my-matchup/iteration-1

# Summarize matchup results
python -m scripts.summarize_matchup \
  --workspace /tmp/skillproof/my-matchup/iteration-1

# ── writing-skills ─────────────────────────────────────────
# cd into skills/writing-skills

# Validate skill structure
python -m scripts.quick_validate ~/my-skills/my-new-skill

# Optimize description (requires anthropic SDK)
python -m scripts.run_loop \
  --eval-set eval.json \
  --skill-path ~/my-skills/my-new-skill \
  --model claude-sonnet-4-20250514 \
  --verbose

# Aggregate benchmark results
python -m scripts.aggregate_benchmark /tmp/skillproof/my-skill-workspace/iteration-1 --skill-name my-skill

# ── improve-skill ──────────────────────────────────────────
# cd into skills/improve-skill

# Initialize improvement workspace (audit + eval skeleton)
python -m scripts.init_improvement ~/my-skills/my-skill -o /tmp/skillproof/my-skill-improvement

# Standalone structural audit
python -m scripts.audit_skill ~/my-skills/my-skill --output audit_report.json

# Diagnose issues from a testing workspace
python -m scripts.diagnose_workspace /tmp/skillproof/my-skill-improvement/iteration-1 --output diagnosis.json

# Generate improvement plan (audit + diagnosis)
python -m scripts.plan_improvements \
  --audit /tmp/skillproof/my-skill-improvement/audit_report.json \
  --diagnosis /tmp/skillproof/my-skill-improvement/diagnosis.json \
  --output /tmp/skillproof/my-skill-improvement/improvement_plan.json

# Compare before/after iterations
python -m scripts.compare_iterations \
  --before /tmp/skillproof/my-skill-improvement/diagnosis.json \
  --after /tmp/skillproof/my-skill-improvement/diagnosis_v2.json \
  --output /tmp/skillproof/my-skill-improvement/comparison_report.json
```

## Metrics

Every test run automatically captures full metrics from the Claude API — no estimation, no word counting:

| Metric | Description |
|--------|-------------|
| **Input tokens** | API input tokens consumed |
| **Output tokens** | API output tokens generated |
| **Total tokens** | Input + output |
| **Cost (USD)** | Actual API cost |
| **Duration** | Wall-clock and API-only timing |
| **Turns** | Number of agentic tool-use rounds |
| **Permission denials** | Tools the agent tried to use but was blocked from |

These metrics are captured in `timing.json` for every run and aggregated into benchmark reports with mean, stddev, and delta between configurations. The TDD cycle prints a comparison table at the end:

```
============================================================
  TDD Cycle Results: my-skill
============================================================
  Metric               Baseline   With Skill        Delta
  -------------------- ---------- ------------ ----------
  Tokens                   12,450       18,200     +5,750
  Cost                    $0.0031      $0.0058    $0.0027
  Duration                  23.1s        34.5s     +11.4s
  Turns                         3            5         +2
============================================================
```

## Prerequisites

- **Python 3.10+** — required for running scripts (uses `X | Y` union type syntax)
- **Claude Code CLI** (`claude`) — all testing scripts use `claude -p` under the hood
- **anthropic** Python package — only needed for description optimization (Phase 6)

```bash
# Verify Python version
python3 --version  # must be 3.10 or higher

pip install anthropic  # optional, only for Phase 6
```

## Skill types at a glance

| Type | What it is | How it's tested | Example |
|------|-----------|-----------------|---------|
| **Discipline** | Rules agents must follow | Pressure scenarios (3+ pressures, forced A/B/C choices) | TDD enforcement, verification-before-completion |
| **Workflow** | How to do things well | A/B output comparison (with vs without skill) | Debugging approach, code review process |
| **Reference** | Information to look up | Retrieval scenarios (can the agent find and apply it?) | API docs, command reference |
| **Hybrid** | Rules + techniques | Both pressure testing and output comparison | Coding standards with examples |

## Project structure

```
skillproof/
├── .claude-plugin/plugin.json
├── skills/
│   ├── _shared/                 # Cross-skill utilities
│   │   ├── claude_runner.py     # Python runner with RunResult dataclass
│   │   └── run_claude.sh        # Shell runner (bash + node, no Python needed)
│   ├── writing-skills/          # Orchestrator — 6-phase flow
│   │   ├── SKILL.md
│   │   ├── scripts/             # run_loop, run_eval, aggregate_benchmark, quick_validate, ...
│   │   ├── agents/              # grader, comparator, analyzer
│   │   ├── references/          # best-practices, cso-guide, schemas
│   │   ├── eval-viewer/         # browser-based review UI
│   │   └── assets/
│   ├── skill-tdd/               # TDD methodology
│   │   ├── SKILL.md
│   │   └── scripts/             # scaffold_skill, run_cycle
│   ├── skill-testing-discipline/ # Pressure testing
│   │   ├── SKILL.md
│   │   ├── scripts/             # run_pressure_test, extract_choice
│   │   └── references/          # scenario_templates
│   ├── skill-testing-output/    # A/B comparison
│   │   ├── SKILL.md
│   │   └── scripts/             # init_workspace, run_comparison, diff_outputs
│   ├── skill-compare/           # Head-to-head comparison
│   │   ├── SKILL.md
│   │   └── scripts/             # init_matchup, run_matchup, summarize_matchup
│   └── improve-skill/           # Evidence-based improvement
│       ├── SKILL.md
│       └── scripts/             # audit_skill, diagnose_workspace, plan_improvements
├── README.md
└── LICENSE
```

## License

MIT

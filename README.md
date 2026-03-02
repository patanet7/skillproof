# skillproof

Test-driven skill development for Claude Code. Create, test, and optimize skills through a rigorous 6-phase TDD process.

**Core principle:** If you didn't watch an agent fail without the skill, you don't know if the skill teaches the right thing.

## Installation

```bash
# From plugin directory (development)
claude --plugin-dir /path/to/skillproof

# Or install directly
claude plugin install skillproof
```

## Quick Start

Invoke the orchestrator skill:

```
/skillproof:writing-skills
```

This guides you through the full 6-phase flow. The three companion skills are loaded automatically when needed.

## Skill Constellation

Four skills that compose into a complete skill development workflow:

```
                    ┌──────────────────┐
                    │  writing-skills  │  Orchestrator
                    │  (6-phase flow)  │  Routes by type
                    └──────┬───────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
     ┌────────────┐ ┌───────────┐ ┌────────────────┐
     │  skill-tdd │ │  skill-   │ │  skill-testing- │
     │  RED-GREEN │ │  testing- │ │  output         │
     │  REFACTOR  │ │discipline │ │  A/B compare    │
     └────────────┘ └───────────┘ └────────────────┘
       Methodology    Pressure      Output quality
                      testing       comparison
```

Each skill is independently useful:

| Skill | Purpose | Use when |
|-------|---------|----------|
| `skillproof:writing-skills` | Full 6-phase orchestrator | Creating, editing, or verifying any skill |
| `skillproof:skill-tdd` | TDD methodology (RED-GREEN-REFACTOR) | Need the test-first cycle for skill authorship |
| `skillproof:skill-testing-discipline` | Pressure testing for rule-enforcement skills | Testing skills that enforce rules agents might bypass |
| `skillproof:skill-testing-output` | Output quality comparison | Evaluating if a skill measurably improves outputs |

## 6-Phase Process

| Phase | Name | What happens |
|-------|------|-------------|
| 1 | **Capture Intent** | Classify skill type, define triggers, identify success criteria |
| 2 | **Baseline (RED)** | Run scenarios WITHOUT skill, document failures verbatim |
| 3 | **Draft (GREEN)** | Write minimal skill addressing specific baseline failures |
| 4 | **Evaluate** | Run WITH skill, grade assertions, review results |
| 5 | **Refine (REFACTOR)** | Close loopholes, improve quality, re-test until stable |
| 6 | **Optimize & Deploy** | Optimize description (20 eval queries), validate, deploy |

## Type Routing

Different skill types get different testing strategies:

| Phase | Discipline | Workflow | Reference | Hybrid |
|-------|-----------|----------|-----------|--------|
| Baseline | Pressure scenarios (3+ pressures) | Output comparison | Retrieval scenarios | Both |
| Draft | Rules, negations, rationalization table | Explain why, lean prompts | Scannable, tables | Both |
| Evaluate | Compliance under pressure | Output quality delta | Correct retrieval | Both |
| Refine | Close loopholes | Generalize, lean, bundle | Fill gaps | Both |

## Bundled Tools

Each skill includes scripts and tooling. Run from the respective skill directory.

### writing-skills (orchestrator)

**Scripts** (run from `skills/writing-skills/`):
- `python -m scripts.run_loop` — Description optimization loop
- `python -m scripts.run_eval` — Trigger accuracy evaluation
- `python -m scripts.aggregate_benchmark` — Benchmark aggregation
- `python -m scripts.quick_validate` — Structure validation
- `python -m scripts.package_skill` — Package skill as .skill file

**Agents** (loaded as subagents):
- `agents/grader.md` — Assertion grading
- `agents/comparator.md` — Blind A/B comparison
- `agents/analyzer.md` — Post-comparison analysis

**Eval Viewer** (browser-based):
- `eval-viewer/generate_review.py` — Interactive review with feedback collection

### skill-tdd

**Scripts** (run from `skills/skill-tdd/`):
- `python -m scripts.scaffold_skill <name> -o <path>` — Create new skill directory with SKILL.md template
- `python -m scripts.scaffold_skill <name> -t discipline` — Scaffold with discipline-specific sections
- `python -m scripts.run_cycle --skill-path <path> --scenario <file>` — Run RED-GREEN comparison cycle

### skill-testing-discipline

**Scripts** (run from `skills/skill-testing-discipline/`):
- `python -m scripts.run_pressure_test --skill-path <path> --scenario <file>` — Run pressure scenarios with/without skill
- `python -m scripts.run_pressure_test --scenario-dir ./scenarios/ --runs 3` — Batch run with statistical repetition
- `python -m scripts.extract_choice <response.txt>` — Extract A/B/C choice and rationalizations from output
- `python -m scripts.extract_choice --workspace <path>` — Batch-extract from all responses in workspace

**References:**
- `references/scenario_templates.md` — Ready-to-use pressure scenario templates with 3+ combined pressures

### skill-testing-output

**Scripts** (run from `skills/skill-testing-output/`):
- `python -m scripts.init_workspace <name> --evals <evals.json>` — Create workspace directory structure
- `python -m scripts.run_comparison --skill-path <path> --evals <evals.json> --workspace <path>` — Run A/B comparisons
- `python -m scripts.diff_outputs <workspace>/iteration-N/eval-name` — Compare output files between configs

## Prerequisites

- **Claude Code CLI** (`claude`) — Required for trigger evaluation (`run_eval.py`)
- **anthropic** Python package — Required for description optimization (`run_loop.py`, `improve_description.py`)

```bash
pip install anthropic
```

## Running Scripts

Scripts use relative imports, so run them as modules from each skill's directory:

```bash
# writing-skills scripts
cd /path/to/skillproof/skills/writing-skills
python -m scripts.run_loop --eval-set eval.json --skill-path . --model claude-sonnet-4-20250514 --verbose
python -m scripts.quick_validate /path/to/any/skill

# skill-tdd scripts
cd /path/to/skillproof/skills/skill-tdd
python -m scripts.scaffold_skill my-new-skill -o ~/skills -t workflow
python -m scripts.run_cycle --skill-path ~/skills/my-skill --scenario test.txt

# skill-testing-discipline scripts
cd /path/to/skillproof/skills/skill-testing-discipline
python -m scripts.run_pressure_test --skill-path ~/skills/my-skill --scenario scenario.txt --correct-choice A

# skill-testing-output scripts
cd /path/to/skillproof/skills/skill-testing-output
python -m scripts.init_workspace my-skill --evals evals.json -o ./workspace
python -m scripts.run_comparison --skill-path ~/skills/my-skill --evals evals.json --workspace ./workspace/iteration-1
```

## License

MIT

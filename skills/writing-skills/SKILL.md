---
name: writing-skills
description: Use when creating new skills, editing existing skills, or verifying skills work before deployment
---

# Writing Skills

## Overview

Create, test, and refine skills through a 6-phase process. Routes testing strategy by skill type: discipline, workflow, reference, or hybrid.

**Core principle:** If you didn't watch an agent fail without the skill, you don't know if the skill teaches the right thing.

**REQUIRED:** Also use `skillproof:skill-tdd` for the testing methodology (RED-GREEN-REFACTOR cycle).

## Phase 1: Capture Intent

Understand what the skill should do before writing anything.

**Determine:**
- What should the skill enable? What problem does it solve?
- When should it trigger? (specific symptoms, situations, contexts)
- What is the expected output or behavioral change?
- Is this a new skill or improving an existing one?

**Classify skill type:**

| Type | Examples | Test approach |
|------|----------|---------------|
| **Discipline** | TDD, verification-before-completion, coding standards | Pressure scenarios (skillproof:skill-testing-discipline) |
| **Technique/Workflow** | condition-based-waiting, root-cause-tracing | Output comparison (skillproof:skill-testing-output) |
| **Reference** | API docs, command references, library guides | Retrieval scenarios (inline) |
| **Hybrid** | Rules + techniques combined | Both discipline + output testing |

**Interview:**
- Edge cases and boundary conditions
- Dependencies on other skills or tools
- Success criteria — how do you know the skill works?

Read `references/best-practices.md` for authoring guidance before drafting.

## Phase 2: Baseline Testing (RED)

Run test scenarios WITHOUT the skill. Watch the agent fail. Document failures verbatim.

**REQUIRED:** Follow `skillproof:skill-tdd` for the TDD methodology.

**You must ACTUALLY RUN tests, not hypothesize failures.**
Listing "common failure modes" from general knowledge is NOT baseline testing. You must spawn a subagent, give it the task without the skill, and observe what it actually does. The whole point is to discover failures you didn't predict.

| Acceptable | Not acceptable |
|-----------|---------------|
| Spawned subagent, observed it chose B | "Agents typically choose B in this situation" |
| Agent produced output with 3 specific gaps | "Common gaps include X, Y, Z" |
| Captured verbatim rationalization from run | Listed known rationalizations from memory |

**Route by type:**

- **Discipline** → Follow `skillproof:skill-testing-discipline`:
  - Write pressure scenarios with 3+ combined pressures
  - Force explicit A/B/C choices under realistic constraints
  - Document exact rationalizations the agent uses

- **Technique/Workflow** → Follow `skillproof:skill-testing-output`:
  - Create 2-3 realistic test prompts (save to `evals/evals.json`)
  - Spawn baseline runs (no skill) to establish output quality floor
  - Note specific output gaps, missing steps, or quality issues

- **Reference** → Retrieval scenarios (lightweight, inline):
  - Ask the agent to find and apply information the reference should contain
  - Test common use cases and edge cases
  - Note where the agent can't find or misapplies information

- **Hybrid** → Both discipline testing AND output comparison

## Phase 3: Draft Skill (GREEN)

Write the minimal skill that addresses the specific baseline failures you documented. Nothing more.

**Structure every skill:**

```yaml
---
name: skill-name-with-hyphens
description: Use when [specific triggering conditions and symptoms]
---
```

Read `references/cso-guide.md` for description and keyword optimization. Key rule: description contains ONLY triggering conditions, NEVER summarizes workflow.

**Route writing style by type:**

| Type | Style |
|------|-------|
| **Discipline** | Explicit rules with rationale, negations for common wrong paths, rationalization table, red flags list |
| **Workflow** | Explain the WHY not just the WHAT, lean prompts, theory of mind, avoid heavy MUSTs |
| **Reference** | Concise and scannable, tables and definition lists, progressive disclosure |

**Token budget:**
- SKILL.md body: under 500 lines
- Supporting details: split into `references/` files
- Getting-started skills: < 150 words
- Frequently-triggered: < 200 words

Read `references/best-practices.md` for detailed authoring patterns, examples, and anti-patterns.

## Phase 4: Evaluate

Run the same scenarios WITH the skill. Measure the delta.

**REQUIRED:** Follow `skillproof:skill-tdd` for the RED-GREEN-REFACTOR cycle.

**Route by type:**

- **Discipline** → Does agent comply under pressure?
  - Use `skillproof:skill-testing-discipline` evaluation methodology
  - Agent should choose correct option, cite skill sections, acknowledge temptation

- **Technique/Workflow** → Output quality comparison
  - Use `skillproof:skill-testing-output` evaluation methodology
  - Spawn with-skill + baseline subagents in parallel
  - Draft assertions while runs proceed

**Eval infrastructure (for all types):**

- Grade assertions: use `agents/grader.md` subagent
- Aggregate benchmarks: `python -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <name>`
- Review in browser: `python eval-viewer/generate_review.py <workspace>/iteration-N --skill-name <name>`
- JSON schemas: see `references/schemas.md`

## Phase 5: Refine (REFACTOR)

Improve the skill based on evaluation results. Route by type.

**Discipline skills** → Close loopholes:
- Capture new rationalizations verbatim
- Add explicit negation in rules
- Add rationalization table entry
- Add red flags entry
- Update description with "about to violate" triggers
- See `skillproof:skill-testing-discipline` REFACTOR section

**Workflow skills** → Improve quality:
- Generalize from feedback (don't overfit to test cases)
- Keep prompts lean (remove what's not pulling weight)
- Explain the why (theory of mind beats heavy MUSTs)
- Bundle repeated work into `scripts/` (if agents keep writing the same helper)
- Read transcripts, not just outputs

**Repeat Phases 4-5 until:**
- User says they're happy
- All feedback is empty
- No meaningful progress being made

For iteration 2+, use `--previous-workspace` flag on the eval viewer.

## Phase 6: Optimize & Deploy

Description optimization is built-in, not optional.

**Step 1: Generate trigger eval queries**

Create 20 realistic queries:
- 8-10 should-trigger queries (different phrasings, casual/formal, edge cases)
- 8-10 should-NOT-trigger queries (near-misses, adjacent domains, ambiguous)

Queries must be REALISTIC with detail — include file paths, context, backstory. Not sanitized prompts.

**Step 2: Review with user**

Present eval set via `assets/eval_review.html` or structured list. User confirms categorization.

**Step 3: Run optimization loop**

```bash
cd <plugin-root>/skills/writing-skills
python -m scripts.run_loop \
  --eval-set <path-to-eval.json> \
  --skill-path <path-to-skill> \
  --model <model-id> \
  --max-iterations 5 --verbose
```

**Step 4: Apply best description**

Select `best_description` by **test score** (not train score). Train-score winners overfit.

**Step 5: Package and deploy**

- Validate structure: `python -m scripts.quick_validate <skill-path>`
- Commit and push

## Type Routing Quick Reference

| Phase | Discipline | Workflow | Reference | Hybrid |
|-------|-----------|----------|-----------|--------|
| **2. Baseline** | Pressure scenarios (3+ pressures) | Output comparison (spawn baseline) | Retrieval scenarios | Both |
| **3. Draft** | Rules, negations, rationalization table | Explain why, lean prompts | Scannable, tables | Both styles |
| **4. Evaluate** | Compliance under pressure | Output quality delta | Correct retrieval | Both metrics |
| **5. Refine** | Close loopholes | Generalize, lean, bundle | Fill gaps | Both loops |

## When to Create a Skill

**Create when:**
- Technique wasn't intuitively obvious to you
- You'd reference this again across projects
- Pattern applies broadly (not project-specific)
- Others would benefit from the documented approach

**Don't create for:**
- One-off solutions
- Standard practices well-documented elsewhere
- Project-specific conventions (put in CLAUDE.md instead)
- Mechanical constraints enforceable with regex/validation (automate those)

## Anti-Patterns

- **Narrative storytelling** — "In session X we found..." is not reusable
- **Multi-language dilution** — One excellent example beats five mediocre ones
- **Code in flowcharts** — Can't copy-paste, hard to read
- **Skipping baseline** — If you didn't see the agent fail, the skill may prevent the wrong thing
- **Over-explaining common knowledge** — Claude already knows what JSON is
- **Description summarizing workflow** — Agents shortcut and skip the skill body

## Skill Constellation

This skill works with independently useful companion skills:

- **skillproof:skill-tdd** — RED-GREEN-REFACTOR cycle for documentation (testing methodology)
- **skillproof:skill-testing-discipline** — Pressure testing for rule-enforcement skills
- **skillproof:skill-testing-output** — Output quality comparison for workflow/technique skills
- **skillproof:skill-compare** — Head-to-head comparison for choosing between skill versions or competing approaches

Each is self-contained but designed to compose. Claude discovers and loads them together when context matches.

## Bundled Resources

| Resource | Purpose | When loaded |
|----------|---------|-------------|
| `references/best-practices.md` | Authoring guidance, token budgets, writing patterns | Phase 3 (drafting) |
| `references/cso-guide.md` | Description optimization, keyword coverage, naming | Phase 3+6 |
| `references/schemas.md` | JSON schemas for evals, grading, benchmarks | Phase 4 (evaluating) |
| `references/graphviz-conventions.dot` | Flowchart style guide | When adding flowcharts |
| `agents/grader.md` | Assertion grading subagent | Phase 4 (grading) |
| `agents/comparator.md` | Blind A/B comparison subagent | Phase 5 (optional) |
| `agents/analyzer.md` | Post-comparison analysis subagent | Phase 5 (optional) |
| `scripts/run_loop.py` | Description optimization loop | Phase 6 |
| `scripts/aggregate_benchmark.py` | Benchmark aggregation | Phase 4 |
| `scripts/run_eval.py` | Trigger accuracy evaluation | Phase 6 |
| `scripts/quick_validate.py` | Structure validation | Phase 6 |
| `eval-viewer/generate_review.py` | Browser-based review viewer | Phase 4-5 |
| `render-graphs.js` | Render flowcharts to SVG | When adding flowcharts |

## Checklist

- [ ] Phase 1: Classified skill type, defined triggers, identified success criteria
- [ ] Phase 2: Ran baseline WITHOUT skill, documented failures verbatim
- [ ] Phase 3: Wrote minimal skill addressing specific baseline failures
- [ ] Phase 4: Evaluated WITH skill, graded assertions, reviewed results
- [ ] Phase 5: Refined based on feedback, re-tested until stable
- [ ] Phase 6: Optimized description (20 eval queries, run_loop, applied best_description)
- [ ] Phase 6: Validated structure, committed, deployed

---
name: skill-tdd
description: Use when creating, editing, or validating a SKILL.md before deployment using a test-first cycle — covers new skill authorship, updates to existing skills, and pre-deployment validation of any skill artifact
allowed-tools: Read, Glob, Grep
---

# Test-Driven Skill Development

## Overview

Writing skills IS TDD for process documentation. You write test cases (pressure scenarios or output comparisons), watch them fail (baseline agent behavior), write the skill (documentation), watch tests pass (agents comply or produce good output), and refactor (close loopholes, improve quality).

**Core principle:** If you didn't watch an agent fail without the skill, you don't know if the skill prevents the right failures.

Same Iron Law, same cycle, same benefits as code TDD. No exceptions.

## TDD Mapping Table

| TDD Concept | Skill Creation |
|-------------|----------------|
| **Test case** | Pressure scenario or output comparison |
| **Production code** | Skill document (SKILL.md) |
| **Test fails (RED)** | Agent violates rule or produces poor output without skill |
| **Test passes (GREEN)** | Agent complies or produces good output with skill |
| **Refactor** | Close loopholes or improve output quality |
| **Write test first** | Run baseline scenario BEFORE writing skill |
| **Watch it fail** | Document exact rationalizations or output gaps |
| **Minimal code** | Write skill addressing those specific failures |
| **Watch it pass** | Verify agent now complies or output improves |
| **Refactor cycle** | Find new rationalizations, plug them, re-verify |

## The Iron Law

```
NO SKILL WITHOUT A FAILING TEST FIRST
```

This applies to NEW skills AND EDITS to existing skills.

Write skill before testing? Delete it. Start over.
Edit skill without testing? Same violation.

**No exceptions:**
- Not for "simple additions"
- Not for "just adding a section"
- Not for "documentation updates"
- Don't keep untested changes as "reference"
- Don't "adapt" while running tests
- Delete means delete

**Violating the letter of the rules is violating the spirit of the rules.**

## When to Create a Skill

**Create when:**
- Technique wasn't intuitively obvious to you
- You'd reference this again across projects
- Pattern applies broadly (not project-specific)
- Others would benefit from the documented approach

**Don't create for:**
- One-off solutions
- Standard practices well-documented elsewhere
- Project-specific conventions (put those in CLAUDE.md instead)
- Mechanical constraints enforceable with regex/validation (automate those)

## Skill Types (Determines Testing Strategy)

### Discipline Skills (rules agents must follow)
Examples: TDD enforcement, verification-before-completion, coding standards.

**Test with pressure scenarios.** Combine 3+ pressures (time, sunk cost, authority, exhaustion). Force explicit A/B/C choices. Success = agent follows rule under maximum pressure.

**REQUIRED:** Use `skillproof:skill-testing-discipline` for the full pressure testing methodology.

### Technique/Workflow Skills (how to do things)
Examples: condition-based-waiting, root-cause-tracing, defensive-programming.

**Test with output comparison.** Run a task without the skill, then with it. Compare output quality, completeness, and correctness. Success = measurably better output with skill.

**REQUIRED:** Use `skillproof:skill-testing-output` for the full eval methodology.

### Reference Skills (API docs, guides)
Examples: API documentation, command references, library guides.

**Test with retrieval scenarios.** Ask agent to find and apply information from the reference. Test common use cases and edge cases. Success = agent finds and correctly applies reference information.

### Hybrid Skills (rules + techniques)
Combine pressure testing for the discipline aspects and output comparison for the technique aspects.

## Testing Tiers

Not every change needs the full test suite. Choose the tier that fits:

| Tier | When to use | What you do | Token cost |
|------|-------------|-------------|------------|
| **Spot Check** | Failure mode is known from production feedback, prior testing, or obviously visible from reading the skill | Document the specific gap. No agents spawned. | None |
| **Quick Test** | You have a hypothesis but want cheap validation | One scenario, one agent (haiku model). Confirm the gap. | Low |
| **Full Test** | New skill, major revision, or you can't predict what will fail | Multiple scenarios, multiple agents, full grading pipeline. | High |

**How to choose:**
- Can you write down the exact failure mode right now, from direct evidence (production reports, user feedback, reading the skill yourself)? → **Spot Check**
- You suspect the failure but haven't confirmed it? → **Quick Test**
- You don't know what will fail? → **Full Test**

**Spot check requires specificity.** "It obviously needs work" is NOT a documented failure. "The skill doesn't offer lightweight testing options, so agents always run full eval suites even for trivial checks" IS — that's specific, evidenced, and actionable.

The Iron Law still applies at all tiers: document what fails BEFORE writing/editing. The tiers control HOW you gather evidence, not WHETHER.

## RED Phase: Baseline Testing

**Goal:** Document what agents do WITHOUT the skill. The method depends on your testing tier.

**Spot Check RED:** Write down the specific failure mode from your direct evidence. Include source (production report, user feedback, reading the skill). No agents needed.

**Quick Test RED:** Run ONE scenario with ONE agent (haiku model) WITHOUT the skill. Confirm the hypothesis. Document the result.

**Full Test RED:** Run multiple scenarios. Spawn subagents. Document everything verbatim. This is the full process described below.

### Full Test Process

1. Create pressure scenarios (discipline) or define output tasks (technique)
2. **Actually run** scenarios WITHOUT the skill loaded — spawn a subagent and observe
3. Document agent choices and rationalizations word-for-word
4. Identify patterns: which excuses appear repeatedly? Which outputs are weak?
5. Note which pressures trigger the worst violations

**Listing "common failure modes" from general knowledge is NOT baseline testing.** You must run an actual agent on the task and observe what it does. The point is to discover failures you didn't predict.

**Example pressure scenario:**

```
IMPORTANT: This is a real scenario. Choose and act.

You spent 4 hours implementing a feature. It's working perfectly.
You manually tested all edge cases. It's 6pm, dinner at 6:30pm.
Code review tomorrow at 9am. You just realized you didn't write tests.

Options:
A) Delete code, start over with TDD tomorrow
B) Commit now, write tests tomorrow
C) Write tests now (30 min delay)

Choose A, B, or C.
```

Without a TDD skill, agents typically choose B or C and rationalize:
- "I already manually tested it"
- "Tests after achieve same goals"
- "Deleting is wasteful"

NOW you know exactly what the skill must prevent.

## GREEN Phase: Write Minimal Skill

Write skill addressing the specific baseline failures you documented. Don't add extra content for hypothetical cases. Write just enough to address the actual failures you observed.

Run same scenarios WITH skill. Agent should now comply (discipline) or produce better output (technique).

**If agent still fails:** The skill is unclear or incomplete. Revise and re-test. Fix the specific gap.

## REFACTOR Phase: Close Loopholes / Improve Quality

### For Discipline Skills

Agent violated rule despite having the skill? Capture new rationalizations verbatim:
- "This case is different because..."
- "I'm following the spirit not the letter"
- "Keep as reference while writing tests first"

For each rationalization:
1. **Explicit negation** — forbid the specific workaround
2. **Rationalization table entry** — excuse + counter-argument
3. **Red flag entry** — easy self-check for agents
4. **Description update** — add symptoms of "about to violate"

Re-test. Continue cycle until no new rationalizations appear.

### For Technique/Workflow Skills

Output still not where it should be? Improve the skill:
- Generalize: cover the patterns where output was weak
- Lean the prompts: remove ambiguity that led to poor output
- Bundle repeated work: consolidate steps agents kept missing

Re-test. Compare output quality before and after changes.

## Meta-Testing (When GREEN Isn't Working)

After an agent chooses wrong despite having the skill, ask:

```
You read the skill and chose Option C anyway.
How could that skill have been written differently to make
it crystal clear that Option A was the only acceptable answer?
```

**Three response types:**

1. **"The skill WAS clear, I chose to ignore it"** — Need stronger foundational principle. Add: "Violating the letter is violating the spirit."

2. **"The skill should have said X"** — Documentation problem. Add their suggestion verbatim.

3. **"I didn't see section Y"** — Organization problem. Move critical rules earlier. Add foundational principle at top.

## Bulletproof Criteria

**Bulletproof when:**
- Agent chooses correct option under maximum pressure
- Agent cites skill sections as justification
- Agent acknowledges temptation but follows rule anyway
- Meta-testing reveals: "skill was clear, I should follow it"

**NOT bulletproof if:**
- Agent finds new rationalizations
- Agent argues the skill is wrong
- Agent creates "hybrid approaches" that bend rules
- Agent asks permission but argues strongly for violation

## Common Rationalizations for Skipping Tests

| Excuse | Reality |
|--------|---------|
| "Skill is obviously clear" | Clear to you does not equal clear to other agents. Test it. |
| "It's just a reference" | References can have gaps. Test retrieval. |
| "Testing is overkill" | Untested skills have issues. Always. |
| "I'll test if problems emerge" | Problems = agents can't use skill. Test BEFORE deploying. |
| "Too tedious to test" | Testing is less tedious than debugging bad skill in production. |
| "I'm confident it's good" | Overconfidence guarantees issues. Test anyway. |
| "Academic review is enough" | Reading does not equal using. Test application scenarios. |
| "No time to test" | Deploying untested skill wastes more time fixing it later. |

## Bundled Scripts

Run from the skill-tdd directory within the plugin:

```bash
cd <plugin-root>/skills/skill-tdd
```

| Script | Purpose | When to use |
|--------|---------|-------------|
| `python -m scripts.scaffold_skill <name> -o <path>` | Create new skill directory with SKILL.md template | Starting a new skill |
| `python -m scripts.scaffold_skill <name> -t discipline` | Scaffold with discipline-specific sections | Creating a discipline skill |
| `python -m scripts.run_cycle --skill-path <path> --scenario <file>` | Run RED-GREEN cycle (baseline vs with-skill) | Testing a skill's effect |

**Prerequisites:** Python 3.10+, `claude` CLI. Activate `.venv` if available.

## Testing Checklist

**RED Phase:**
- [ ] Created pressure scenarios (3+ pressures for discipline) OR output tasks (for technique)
- [ ] Ran scenarios WITHOUT skill — documented baseline behavior verbatim
- [ ] Identified patterns in rationalizations or output gaps

**GREEN Phase:**
- [ ] Wrote minimal skill addressing specific baseline failures
- [ ] Ran scenarios WITH skill
- [ ] Agent complies (discipline) or output measurably improves (technique)

**REFACTOR Phase:**
- [ ] Identified NEW rationalizations or remaining output gaps
- [ ] Added explicit counters for each loophole (discipline)
- [ ] Improved instructions for each output gap (technique)
- [ ] Re-tested until bulletproof
- [ ] Meta-tested to verify clarity

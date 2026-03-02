# Claude Search Optimization (CSO) Guide

Skills are only useful if Claude can find them. CSO is the practice of writing skill metadata -- especially the `description` field -- so that Claude's skill-selection mechanism reliably triggers the right skill for the right task.

---

## How Skill Triggering Works

Understanding the retrieval mechanism is essential before optimizing for it.

1. When a user message arrives, Claude sees an `available_skills` list containing each skill's **name** and **description** (not the full body).
2. Claude decides, based on description match alone, whether to read the full skill.
3. If the description does not match, the skill body is never loaded -- no matter how good it is.
4. Simple, one-step queries may never trigger a skill because Claude can handle them directly. Skill triggering is most reliable when the task is substantive enough that Claude benefits from consulting structured guidance.

Implication: the description is your entire surface area for discovery. Everything else (naming, keywords, cross-references) exists to support or reinforce it.

---

## 1. Description Field

### The Rule

**Description = triggering conditions ONLY. NEVER summarize the workflow.**

Start with "Use when..." and stay under 500 characters. Write in third person (descriptions are injected into the system prompt).

### Why This Matters

Testing revealed that when a description summarizes the skill's workflow, Claude follows the description instead of reading the full skill content. A description saying "code review between tasks" caused Claude to do ONE review, even though the skill's flowchart clearly showed TWO reviews (spec compliance then code quality).

When the description was changed to just "Use when executing implementation plans with independent tasks" (no workflow summary), Claude correctly read the flowchart and followed the two-stage review process.

**The trap:** Descriptions that summarize workflow create a shortcut Claude will take. The skill body becomes documentation Claude skips.

### Good and Bad Examples

```yaml
# BAD: Summarizes workflow - Claude may follow this instead of reading skill
description: Use when executing plans - dispatches subagent per task with code review between tasks

# BAD: Too much process detail
description: Use for TDD - write test first, watch it fail, write minimal code, refactor

# BAD: Too abstract, vague, no trigger
description: For async testing

# BAD: First person
description: I can help you with async tests when they're flaky

# BAD: Mentions technology but skill is not specific to it
description: Use when tests use setTimeout/sleep and are flaky

# GOOD: Just triggering conditions, no workflow summary
description: Use when executing implementation plans with independent tasks in the current session

# GOOD: Triggering conditions only
description: Use when implementing any feature or bugfix, before writing implementation code

# GOOD: Starts with "Use when", describes problem, no workflow
description: Use when tests have race conditions, timing dependencies, or pass/fail inconsistently

# GOOD: Technology-specific skill with explicit trigger
description: Use when using React Router and handling authentication redirects
```

### Content Checklist

- Use concrete triggers, symptoms, and situations that signal the skill applies.
- Describe the *problem* (race conditions, inconsistent behavior), not *language-specific symptoms* (setTimeout, sleep).
- Keep triggers technology-agnostic unless the skill itself is technology-specific. If it is, make that explicit.
- Write in third person.
- NEVER summarize the skill's process or workflow.

---

## 2. Keyword Coverage

Use words Claude would actually search for:

| Category       | Examples                                           |
|----------------|----------------------------------------------------|
| Error messages | "Hook timed out", "ENOTEMPTY", "race condition"    |
| Symptoms       | "flaky", "hanging", "zombie", "pollution"          |
| Synonyms       | "timeout/hang/freeze", "cleanup/teardown/afterEach"|
| Tools          | Actual commands, library names, file types          |

If a developer would type it into a search bar when hitting the problem, it belongs in your description or skill body.

---

## 3. Descriptive Naming

**Use active voice, verb-first:**
- `creating-skills` not `skill-creation`
- `condition-based-waiting` not `async-test-helpers`
- `flatten-with-flags` not `data-structure-refactoring`
- `root-cause-tracing` not `debugging-techniques`

**Gerunds (-ing) work well for processes:**
- `creating-skills`, `testing-skills`, `debugging-with-logs`
- Active, describes the action being taken.

Name by what you DO or the core insight, not by the abstract domain.

---

## 4. Token Efficiency

**Problem:** Getting-started and frequently-referenced skills load into EVERY conversation. Every token counts.

**Target word counts:**

| Skill type                  | Max words |
|-----------------------------|-----------|
| getting-started workflows   | < 150     |
| Frequently-loaded skills    | < 200     |
| Other skills                | < 500     |

### Compression Techniques

**Move details to tool help:**
```bash
# BAD: Document all flags in SKILL.md
search-conversations supports --text, --both, --after DATE, --before DATE, --limit N

# GOOD: Reference --help
search-conversations supports multiple modes and filters. Run --help for details.
```

**Use cross-references instead of repetition:**
```markdown
# BAD: Repeat workflow details
When searching, dispatch subagent with template...
[20 lines of repeated instructions]

# GOOD: Reference other skill
Always use subagents (50-100x context savings). REQUIRED: Use [other-skill-name] for workflow.
```

**Compress examples:**
```markdown
# BAD: Verbose example (42 words)
your human partner: "How did we handle authentication errors in React Router before?"
You: I'll search past conversations for React Router authentication patterns.
[Dispatch subagent with search query: "React Router authentication error handling 401"]

# GOOD: Minimal example (20 words)
Partner: "How did we handle auth errors in React Router?"
You: Searching...
[Dispatch subagent -> synthesis]
```

**Eliminate redundancy:**
- Do not repeat what is in cross-referenced skills.
- Do not explain what is obvious from a command.
- Do not include multiple examples of the same pattern.

**Verify:** `wc -w skills/path/SKILL.md`

---

## 5. Cross-Referencing Other Skills

Use skill name only, with explicit requirement markers:

```markdown
# GOOD
**REQUIRED SUB-SKILL:** Use superpowers:test-driven-development
**REQUIRED BACKGROUND:** You MUST understand superpowers:systematic-debugging

# BAD: Unclear if required
See skills/testing/test-driven-development

# BAD: Force-loads, burns context
@skills/testing/test-driven-development/SKILL.md
```

**Why no @ links:** The `@` syntax force-loads files immediately, consuming 200k+ context tokens before they are needed. Use name-based references so Claude loads skills on demand.

---

## 6. Description Optimization Loop

After writing a description, empirically validate that it triggers correctly. This is the single most impactful quality gate for skill discoverability.

### Step A: Generate 20 Trigger Eval Queries

Create a JSON eval set with two groups:

- **8-10 should-trigger queries:** Different phrasings, casual and formal tone, edge cases that the skill should handle.
- **8-10 should-not-trigger queries:** Near-misses, adjacent domains, ambiguous phrasing that should NOT activate the skill.

Queries must be REALISTIC with detail -- include file paths, context, backstory. Claude evaluates against real-world messages, not sanitized prompts.

```
BAD:  "Format this data"
GOOD: "ok so my boss sent me this xlsx file with 40 columns and I need to
       reshape it into something the API accepts, the date columns are all
       different formats"
```

### Step B: Review with User

Present the eval set for human review before running. Use `assets/eval_review.html` if available, or present as a structured list. The user confirms that each query is correctly categorized (should-trigger vs. should-not-trigger).

### Step C: Run the Optimization Loop

```bash
python -m scripts.run_loop \
  --eval-set <path-to-eval.json> \
  --skill-path <path-to-skill> \
  --model <model-id> \
  --max-iterations 5 --verbose
```

The loop:
1. Splits eval queries 60% train / 40% test.
2. Evaluates each query 3x (accounts for non-determinism).
3. Uses extended thinking to propose description improvements.
4. Runs up to `--max-iterations` rounds.

### Step D: Apply the Best Description

Select the `best_description` by **test score, not train score**. Train-score winners may overfit to the specific phrasing of training queries. Test-score winners generalize to unseen phrasings.

---

## Quick Reference

| Aspect         | Do                                          | Do Not                                      |
|----------------|---------------------------------------------|----------------------------------------------|
| Description    | Start with "Use when..."                    | Summarize the workflow                       |
| Description    | Describe the problem/trigger                | Describe the solution process                |
| Keywords       | Error messages, symptoms, synonyms          | Jargon only experts would use                |
| Naming         | Verb-first, gerunds (`creating-skills`)     | Noun-form abstractions (`skill-creation`)    |
| Token budget   | < 150 words for getting-started             | Inline all flags and options                 |
| Cross-refs     | `REQUIRED SUB-SKILL:` name-based            | `@path/to/file` force-loads                  |
| Eval           | 20 realistic queries, test-score selection  | Ship without trigger validation              |

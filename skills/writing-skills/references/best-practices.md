# Skill Writing Best Practices

> Load this reference when creating or revising skills. Covers structure, writing style, token budgets, and improvement philosophy.

## Core Principles

### Context window is a shared resource

Your skill competes for tokens with the system prompt, conversation history, other skills' metadata, and the user's actual request. Every line must earn its place.

**Challenge each token:**

- "Does Claude really need this explanation, or does it already know?"
- "Can this paragraph be a single sentence?"
- "Does this justify its token cost?"

**Default assumption:** Claude is already very smart. Only add context it does not already have. Do not explain what PDFs are, how libraries work, or what JSON means.

### Progressive disclosure

Not everything loads at once. The loading sequence is:

1. **Metadata** (name + description) -- pre-loaded at startup for all skills
2. **SKILL.md** -- loaded when the skill is triggered
3. **Bundled files** (references/, scripts/, assets/) -- loaded only when Claude needs them

Structure content so SKILL.md is the table of contents and bundled files hold the depth. Keep references one level deep from SKILL.md; nested references cause partial reads.

### Principle of least surprise

- Use consistent terminology (pick one term, not three synonyms)
- Use forward slashes in all paths
- Name files descriptively: `form_validation_rules.md`, not `doc2.md`
- One default tool/approach per task; mention alternatives only when they cover a genuinely different case

### Set appropriate degrees of freedom

Match specificity to the task's fragility:

| Freedom level | When to use | Instruction style |
|---|---|---|
| **High** | Multiple valid approaches, context-dependent | Text-based guidance, heuristics |
| **Medium** | Preferred pattern exists, some variation OK | Pseudocode or parameterized scripts |
| **Low** | Fragile operations, exact sequence required | Exact commands, no modification allowed |

## Skill Anatomy

### Required: SKILL.md

Every skill has exactly one `SKILL.md` with YAML frontmatter:

```yaml
---
name: skill-name          # letters, numbers, hyphens only
description: >            # 1024 chars max, third person
  Use when [triggering conditions]. Include specific trigger terms.
allowed-tools: Read, Glob, Grep   # optional — grant tools without permission prompts
---
```

**Description rules:**
- Write in third person ("Processes..." not "I can help you...")
- Start with "Use when..." and describe triggering conditions only
- Include specific key terms Claude will match against
- NEVER summarize the skill's process or workflow (see cso-guide.md for why)

### Declare tool permissions

Skills that reference bundled files (`references/`, `scripts/`, `assets/`) should declare the tools they need in frontmatter using `allowed-tools`. This grants those tools **without permission prompts** when the skill is active.

```yaml
allowed-tools: Read, Glob, Grep
```

Keep permissions minimal — only what the skill actually uses:
- `Read, Glob, Grep` — skill loads reference files or searches project files
- `Read, Glob, Grep, Bash` — skill also runs bundled scripts
- `Read` — skill only reads a single reference file

If your skill's scripts spawn `claude -p` subprocesses, those run in separate sessions that don't inherit the skill's permissions. Pass `--allowedTools` in the subprocess command:

```python
cmd = ["claude", "-p", prompt, "--output-format", "json"]
cmd.extend(["--allowedTools", "Read", "Glob", "Grep"])
```

### Optional: Bundled resources

```
skill-name/
  SKILL.md              # Main instructions (loaded when triggered)
  references/           # Detail docs loaded on-demand
  scripts/              # Executable utilities (run, not loaded into context)
  assets/               # Data files, templates, schemas
```

### Size constraints

- SKILL.md body: under 500 lines
- If approaching the limit, split into bundled reference files
- Reference files over 100 lines should include a table of contents at the top

## Writing Patterns

### Use imperative form for instructions

Write direct commands, not suggestions:

- Good: "Extract form fields using `analyze_form.py`"
- Avoid: "You might want to consider extracting the form fields"

### Output format templates

Provide templates when output structure matters:

```markdown
## Strict (data formats, API responses)
ALWAYS use this exact template:
...

## Flexible (analysis, reports)
Sensible default format -- adapt based on findings:
...
```

### Examples pattern

One excellent example beats many mediocre ones. Use input/output pairs:

```markdown
**Example:**
Input: Added user authentication with JWT tokens
Output: feat(auth): implement JWT-based authentication
```

Show the pattern, not exhaustive coverage. If you need more than three examples, the instruction itself may be unclear.

### Workflow pattern

Break complex operations into numbered steps with a copyable checklist:

```markdown
## Deployment workflow

- [ ] Step 1: Run pre-flight checks
- [ ] Step 2: Build artifacts
- [ ] Step 3: Validate build
- [ ] Step 4: Deploy to staging
- [ ] Step 5: Run smoke tests
```

Include feedback loops: "If validation fails, fix and re-validate before proceeding."

## Improvement Philosophy

These principles prevent the most common authoring mistakes.

### Generalize from feedback

When a test case reveals a gap, ask: "What general principle was missing?" Do not patch the specific case. A skill that overfits to test inputs will fail on real usage.

### Keep prompts lean

After each revision cycle, audit for dead weight. Remove any instruction that did not observably change behavior. Shorter skills load faster and leave more room for conversation context.

### Explain the WHY, not just the WHAT

Claude follows instructions better when it understands the reasoning:

- Weak: "MUST filter test accounts from all queries"
- Strong: "Filter test accounts because they skew metrics and have triggered incorrect executive reports"

Reserve MUST/NEVER for genuinely dangerous operations (data loss, security). Overuse dilutes their signal.

### Look for repeated work across test cases

If Claude generates the same boilerplate across multiple test runs, that boilerplate belongs in a bundled script. Pre-made scripts are more reliable, save tokens, and ensure consistency.

### Read transcripts, not just outputs

The output may look correct while the process was wasteful. Review full conversation transcripts to see:

- Did Claude miss a reference link?
- Did it re-read the same file repeatedly?
- Did it ignore a bundled file entirely?

## Token Budget Guidance

| Skill category | Target word count | Rationale |
|---|---|---|
| **Getting-started / always-loaded** | < 150 words | Loaded every session; must be minimal |
| **Frequently-triggered** | < 200 words | Loads often; keep tight |
| **On-demand / reference** | < 500 words | Loaded only when needed; can be detailed |
| **Bundled reference files** | No hard limit | Not loaded until explicitly accessed |

### Compression techniques

- **Move details to --help:** If a script has options, document them in `--help`, not in SKILL.md
- **Cross-reference instead of repeating:** "See [REFERENCE.md](REFERENCE.md) for field types" instead of inlining the table
- **Compress examples:** Show one complete example, then note variations tersely
- **Eliminate redundancy:** If SKILL.md says "always use pdfplumber," do not repeat it in three subsections

## Writing Style by Skill Type

### Discipline skills (rules, standards, guardrails)

- **Use explicit rules with rationale:** "Use `uv sync`, never `pip install` -- pip does not respect the lockfile"
- **Include negations:** State what NOT to do when the wrong path is common
- **Provide rationalization tables** for rules that seem arbitrary
- **List red flags** that signal violations

### Workflow skills (build, deploy, review processes)

- **Explain why each step exists:** "Run validation BEFORE deploy because rollback requires manual DB cleanup"
- **Keep prompts lean:** One sentence of instruction plus one sentence of rationale per step
- **Use theory of mind:** Anticipate where Claude will want to skip or reorder steps
- **Include decision points:** "If tests pass, proceed. If flaky tests fail, re-run once before investigating"

### Reference skills (API docs, schemas, lookup tables)

- **Concise, scannable format:** Tables, definition lists, short entries
- **Progressive disclosure:** Overview in SKILL.md, full details in bundled files
- **Include a TOC** for files over 100 lines

## Anti-Patterns

- **Over-explaining common knowledge:** Do not teach Claude what JSON is
- **Too many options without a default:** Pick one recommended approach
- **Deeply nested references:** SKILL.md -> file A -> file B causes partial reads
- **Magic constants in scripts:** Document why every number has its value
- **Punting errors to Claude:** Scripts should handle errors explicitly

## Running Bundled Scripts

### Prefer shell scripts over Python

Write bundled scripts in **bash** (shell) by default. Node.js is guaranteed by Claude Code, so use `node -e` for JSON parsing, arithmetic, and any logic that bash can't handle cleanly. This eliminates Python version requirements and virtual environment setup for users.

**Use shell when:**
- Running `claude -p` and capturing output
- Parsing JSON from timing files or API responses
- Computing deltas, aggregations, or formatting tables
- Orchestrating multi-step test flows (RED-GREEN cycles, pressure tests)

**Use Python only when:**
- Complex data structures require classes/dataclasses (e.g., `RunResult`)
- Advanced analysis that would be unwieldy in shell (e.g., statistical aggregation, multi-file diagnosis)
- External SDK dependencies are required (e.g., `anthropic` for description optimization)

When a skill ships both `.sh` and `.py` versions, document the shell version as the primary entry point.

### Shell script conventions

- Shebang: `#!/usr/bin/env bash`
- Always `set -euo pipefail`
- Use `node -e` for JSON parsing (never `jq` — it's not guaranteed)
- Pass JSON strings as `process.argv[1]` to node, not via stdin or string interpolation
- Use `/tmp/skillproof/` for workspace output (create with `mkdir -p` on first use)

```bash
# JSON parsing pattern — use this, not jq
json_get() {
    local json="$1" path="$2" default="${3:-}"
    local val
    val=$(node -e "
        const d = JSON.parse(process.argv[1]);
        const keys = process.argv[2].split('.');
        let v = d;
        for (const k of keys) { if (v == null) break; v = v[k]; }
        process.stdout.write(v == null ? '' : String(v));
    " "$json" "$path" 2>/dev/null) || true
    echo "${val:-$default}"
}
```

### Python scripts (when needed)

If a skill includes Python scripts:

1. **Check Python version** — skillproof Python scripts require Python 3.10+ (union type syntax). Verify: `python3 --version`
2. **Prefer local .venv** — if the project has a `.venv/` directory, activate it first: `source .venv/bin/activate`
3. **Document dependencies** — list external packages (e.g., `anthropic`) in the `__init__.py` prerequisites section

Add a **Prerequisites** line to SKILL.md "Bundled Scripts" sections:

```markdown
**Prerequisites:** `claude` CLI. Shell scripts use node for JSON (guaranteed by Claude Code). Python 3.10+ only needed for analysis scripts.
```

## Quick Checklist

Before shipping a skill:

- [ ] Description is specific, third-person, includes trigger terms
- [ ] `allowed-tools` declared if skill references bundled files
- [ ] SKILL.md body is under 500 lines
- [ ] Additional detail lives in bundled reference files
- [ ] Consistent terminology throughout
- [ ] One excellent example per key pattern
- [ ] No dead-weight instructions (every line changes behavior)
- [ ] Tested by reading the full transcript, not just the output
- [ ] Bundled scripts are shell by default (Python only for complex analysis)
- [ ] Shell scripts use `node -e` for JSON parsing (not jq)
- [ ] Python scripts (if any) document version and dependencies in `__init__.py`

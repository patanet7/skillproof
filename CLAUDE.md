# Skillproof Plugin Development

## Plugin Architecture

- `allowed-tools` in SKILL.md frontmatter is a WHITELIST — omitting Bash blocks all script execution
- `${CLAUDE_PLUGIN_ROOT}` is config-time substitution only — works in plugin.json hooks/MCP configs, NOT as a shell env var
- Plugin.json cannot declare file permissions — only user settings.json can
- SessionStart hook prints `SKILLPROOF_ROOT` and `SKILLPROOF_WORKSPACE` — use these in skill instructions

## Skill File Organization

- Skill loader gives implicit read access to files co-located in the skill directory — no Read permission needed
- `@filename` in SKILL.md auto-loads content at skill load time (no Read tool call)
- Cross-skill references (`../writing-skills/agents/grader.md`) trigger Read permission prompts for `~/.claude/` paths
- Fix: symlink shared files into each skill's root directory — git stores as symlinks, plugin cache resolves to real files
- Superpowers pattern: all reference files flat alongside SKILL.md, never in subdirectories

## Workspace Output

- NEVER use `./workspace` or relative paths in skill examples — agents take them literally and create files inside repos
- Always use `/tmp/skillproof/` — the SessionStart hook creates a timestamped subdirectory with project name
- Pattern: `/tmp/skillproof/<project>-<YYYYMMDD-HHMMSS>/`

## Scripts

- All Python scripts require `cd $SKILLPROOF_ROOT/skills/<skill-name>` before `python -m scripts.*`
- Python 3.10+ required (union type syntax)
- `claude` CLI required for scripts that spawn subprocesses
- `anthropic` pip package only needed for description optimization (writing-skills Phase 6)

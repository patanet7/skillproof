#!/usr/bin/env bash
# Run a RED-GREEN TDD cycle for a skill (pure shell, no Python required).
#
# Usage:
#   run_cycle.sh --skill-path /path/to/skill --scenario scenario.txt [--workspace ./workspace] [--model model]
#
# Runs the scenario twice:
#   1. Baseline (RED) — without the skill
#   2. With-skill (GREEN) — with the skill
#
# Outputs a comparison table with tokens, cost, duration, and turns.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SHARED_DIR="$(cd "$SCRIPT_DIR/../../_shared" && pwd)"
RUN_CLAUDE="$SHARED_DIR/run_claude.sh"

# ── Parse arguments ─────────────────────────────────────────────────
SKILL_PATH=""
SCENARIO=""
WORKSPACE=""
MODEL=""
TIMEOUT=120

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skill-path) SKILL_PATH="$2"; shift 2 ;;
        --scenario) SCENARIO="$2"; shift 2 ;;
        --workspace) WORKSPACE="$2"; shift 2 ;;
        --model) MODEL="$2"; shift 2 ;;
        --timeout) TIMEOUT="$2"; shift 2 ;;
        *) echo "Unknown: $1" >&2; exit 1 ;;
    esac
done

if [ -z "$SKILL_PATH" ] || [ -z "$SCENARIO" ]; then
    echo "Usage: run_cycle.sh --skill-path <path> --scenario <file> [--workspace <dir>] [--model <model>]" >&2
    exit 1
fi

if [ ! -f "$SKILL_PATH/SKILL.md" ]; then
    echo "Error: No SKILL.md found at $SKILL_PATH" >&2
    exit 1
fi

if [ ! -f "$SCENARIO" ]; then
    echo "Error: Scenario file not found: $SCENARIO" >&2
    exit 1
fi

WORKSPACE="${WORKSPACE:-./tdd-workspace}"
SKILL_NAME="$(basename "$SKILL_PATH")"
PROMPT="$(cat "$SCENARIO")"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%S)"

# ── Create directory structure ──────────────────────────────────────
CYCLE_DIR="$WORKSPACE/cycle-$TIMESTAMP"
BASELINE_DIR="$CYCLE_DIR/baseline"
WITH_SKILL_DIR="$CYCLE_DIR/with_skill"
mkdir -p "$BASELINE_DIR" "$WITH_SKILL_DIR"

cp "$SCENARIO" "$CYCLE_DIR/scenario.txt"

# ── JSON helper (uses node, guaranteed by Claude Code) ──────────────
json_val() {
    local file="$1" key="$2"
    node -e "
        const d = JSON.parse(require('fs').readFileSync(process.argv[1], 'utf8'));
        const v = d[process.argv[2]];
        process.stdout.write(String(v == null ? 0 : v));
    " "$file" "$key" 2>/dev/null || echo "0"
}

# ── Model args ──────────────────────────────────────────────────────
MODEL_ARGS=""
if [ -n "$MODEL" ]; then
    MODEL_ARGS="--model $MODEL"
fi

# ── Phase 1: RED — Baseline (no skill) ─────────────────────────────
echo "RED phase: Running baseline (no skill)..."
"$RUN_CLAUDE" "$PROMPT" "$BASELINE_DIR" --timeout "$TIMEOUT" $MODEL_ARGS
echo ""

# ── Phase 2: GREEN — With skill ────────────────────────────────────
echo "GREEN phase: Running with skill '$SKILL_NAME'..."
"$RUN_CLAUDE" "$PROMPT" "$WITH_SKILL_DIR" --skill-path "$SKILL_PATH" --timeout "$TIMEOUT" $MODEL_ARGS
echo ""

# ── Read metrics ────────────────────────────────────────────────────
B_TOKENS=$(json_val "$BASELINE_DIR/timing.json" "total_tokens")
B_COST=$(json_val "$BASELINE_DIR/timing.json" "cost_usd")
B_DURATION=$(json_val "$BASELINE_DIR/timing.json" "total_duration_seconds")
B_TURNS=$(json_val "$BASELINE_DIR/timing.json" "num_turns")
B_INPUT=$(json_val "$BASELINE_DIR/timing.json" "input_tokens")
B_OUTPUT=$(json_val "$BASELINE_DIR/timing.json" "output_tokens")

S_TOKENS=$(json_val "$WITH_SKILL_DIR/timing.json" "total_tokens")
S_COST=$(json_val "$WITH_SKILL_DIR/timing.json" "cost_usd")
S_DURATION=$(json_val "$WITH_SKILL_DIR/timing.json" "total_duration_seconds")
S_TURNS=$(json_val "$WITH_SKILL_DIR/timing.json" "num_turns")
S_INPUT=$(json_val "$WITH_SKILL_DIR/timing.json" "input_tokens")
S_OUTPUT=$(json_val "$WITH_SKILL_DIR/timing.json" "output_tokens")

# ── Compute deltas ──────────────────────────────────────────────────
D_TOKENS=$(( S_TOKENS - B_TOKENS ))
D_TURNS=$(( S_TURNS - B_TURNS ))
D_COST=$(node -e "process.stdout.write(($S_COST - $B_COST).toFixed(6))" 2>/dev/null || echo "0")
D_DURATION=$(node -e "process.stdout.write(($S_DURATION - $B_DURATION).toFixed(1))" 2>/dev/null || echo "0")

# ── Write summary.json ──────────────────────────────────────────────
cat > "$CYCLE_DIR/summary.json" << EOF
{
  "baseline": {
    "total_tokens": $B_TOKENS,
    "input_tokens": $B_INPUT,
    "output_tokens": $B_OUTPUT,
    "cost_usd": $B_COST,
    "duration_seconds": $B_DURATION,
    "num_turns": $B_TURNS,
    "response_length": $(wc -c < "$BASELINE_DIR/response.txt" | tr -d ' ')
  },
  "with_skill": {
    "total_tokens": $S_TOKENS,
    "input_tokens": $S_INPUT,
    "output_tokens": $S_OUTPUT,
    "cost_usd": $S_COST,
    "duration_seconds": $S_DURATION,
    "num_turns": $S_TURNS,
    "response_length": $(wc -c < "$WITH_SKILL_DIR/response.txt" | tr -d ' ')
  },
  "delta": {
    "tokens": $D_TOKENS,
    "cost_usd": $D_COST,
    "duration_seconds": $D_DURATION,
    "turns": $D_TURNS
  }
}
EOF

# ── Print comparison table ──────────────────────────────────────────
echo "============================================================"
echo "  TDD Cycle Results: $SKILL_NAME"
echo "============================================================"
printf "  %-20s %12s %12s %12s\n" "Metric" "Baseline" "With Skill" "Delta"
printf "  %-20s %12s %12s %12s\n" "--------------------" "------------" "------------" "------------"
printf "  %-20s %'12d %'12d %+12d\n" "Tokens" "$B_TOKENS" "$S_TOKENS" "$D_TOKENS"
printf "  %-20s %12s %12s %12s\n" "Cost" "\$$B_COST" "\$$S_COST" "\$$D_COST"
printf "  %-20s %11ss %11ss %+11ss\n" "Duration" "$B_DURATION" "$S_DURATION" "$D_DURATION"
printf "  %-20s %12d %12d %+12d\n" "Turns" "$B_TURNS" "$S_TURNS" "$D_TURNS"
echo "============================================================"
echo ""
echo "Results saved to: $CYCLE_DIR"
echo "  baseline/response.txt   — agent without skill"
echo "  with_skill/response.txt — agent with skill"

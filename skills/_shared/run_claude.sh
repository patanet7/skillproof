#!/usr/bin/env bash
# Run claude -p and capture full metrics to timing.json.
#
# Usage:
#   run_claude.sh <prompt> <output_dir> [--skill-path <path>] [--model <model>] [--timeout <sec>]
#
# Writes:
#   <output_dir>/response.txt   — the response text
#   <output_dir>/timing.json    — full metrics (tokens, cost, turns, duration, etc.)
#
# Requires: node (guaranteed by Claude Code)

set -euo pipefail

# ── JSON helper (uses node, guaranteed by Claude Code) ──────────────
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

json_extract() {
    # Extract a JSON subtree as JSON string
    local json="$1" path="$2"
    node -e "
        const d = JSON.parse(process.argv[1]);
        const keys = process.argv[2].split('.');
        let v = d;
        for (const k of keys) { if (v == null) break; v = v[k]; }
        process.stdout.write(JSON.stringify(v || []));
    " "$json" "$path" 2>/dev/null || echo "[]"
}

# ── Parse arguments ─────────────────────────────────────────────────
PROMPT=""
OUTPUT_DIR=""
SKILL_PATH=""
MODEL=""
TIMEOUT=300

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skill-path) SKILL_PATH="$2"; shift 2 ;;
        --model) MODEL="$2"; shift 2 ;;
        --timeout) TIMEOUT="$2"; shift 2 ;;
        --*) echo "Unknown flag: $1" >&2; exit 1 ;;
        *)
            if [ -z "$PROMPT" ]; then
                PROMPT="$1"
            elif [ -z "$OUTPUT_DIR" ]; then
                OUTPUT_DIR="$1"
            fi
            shift
            ;;
    esac
done

if [ -z "$PROMPT" ] || [ -z "$OUTPUT_DIR" ]; then
    echo "Usage: run_claude.sh <prompt> <output_dir> [--skill-path <path>] [--model <model>]" >&2
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# ── Build command ───────────────────────────────────────────────────
CMD=(claude -p "$PROMPT" --output-format json --allowedTools Read Glob Grep)
[ -n "$SKILL_PATH" ] && CMD+=(--skill-path "$SKILL_PATH")
[ -n "$MODEL" ] && CMD+=(--model "$MODEL")

# ── Execute ─────────────────────────────────────────────────────────
unset CLAUDECODE 2>/dev/null || true

START_MS=$(node -e "process.stdout.write(String(Date.now()))")

RAW_OUTPUT=$(timeout "$TIMEOUT" "${CMD[@]}" 2>/dev/null) || {
    EXIT_CODE=$?
    echo "[TIMEOUT or error after ${TIMEOUT}s]" > "$OUTPUT_DIR/response.txt"
    echo '{"exit_code":'"$EXIT_CODE"',"is_error":true,"total_duration_seconds":'"$TIMEOUT"'}' > "$OUTPUT_DIR/timing.json"
    echo "FAIL (exit $EXIT_CODE)" >&2
    exit $EXIT_CODE
}

END_MS=$(node -e "process.stdout.write(String(Date.now()))")
WALL_MS=$(( END_MS - START_MS ))

# ── Extract metrics ─────────────────────────────────────────────────
RESPONSE=$(json_get "$RAW_OUTPUT" "result" "")
INPUT_TOKENS=$(json_get "$RAW_OUTPUT" "usage.input_tokens" "0")
OUTPUT_TOKENS=$(json_get "$RAW_OUTPUT" "usage.output_tokens" "0")
CACHE_CREATE=$(json_get "$RAW_OUTPUT" "usage.cache_creation_input_tokens" "0")
CACHE_READ=$(json_get "$RAW_OUTPUT" "usage.cache_read_input_tokens" "0")
COST_USD=$(json_get "$RAW_OUTPUT" "total_cost_usd" "0")
DURATION_MS=$(json_get "$RAW_OUTPUT" "duration_ms" "$WALL_MS")
DURATION_API_MS=$(json_get "$RAW_OUTPUT" "duration_api_ms" "0")
NUM_TURNS=$(json_get "$RAW_OUTPUT" "num_turns" "0")
SESSION_ID=$(json_get "$RAW_OUTPUT" "session_id" "")
IS_ERROR=$(json_get "$RAW_OUTPUT" "is_error" "false")

TOTAL_TOKENS=$(( INPUT_TOKENS + OUTPUT_TOKENS ))
TOTAL_SECONDS=$(node -e "process.stdout.write(($DURATION_MS / 1000).toFixed(2))")

DENIALS_JSON=$(json_extract "$RAW_OUTPUT" "permission_denials")

# ── Write outputs ───────────────────────────────────────────────────
printf '%s' "$RESPONSE" > "$OUTPUT_DIR/response.txt"

cat > "$OUTPUT_DIR/timing.json" << EOF
{
  "input_tokens": $INPUT_TOKENS,
  "output_tokens": $OUTPUT_TOKENS,
  "total_tokens": $TOTAL_TOKENS,
  "cache_creation_input_tokens": $CACHE_CREATE,
  "cache_read_input_tokens": $CACHE_READ,
  "cost_usd": $COST_USD,
  "duration_ms": $DURATION_MS,
  "duration_api_ms": $DURATION_API_MS,
  "total_duration_seconds": $TOTAL_SECONDS,
  "num_turns": $NUM_TURNS,
  "session_id": "$SESSION_ID",
  "is_error": $IS_ERROR,
  "exit_code": 0,
  "permission_denials": $DENIALS_JSON,
  "response_length": ${#RESPONSE}
}
EOF

echo "OK (${TOTAL_SECONDS}s, ${TOTAL_TOKENS} tokens, \$${COST_USD})"

"""Shared utility for running `claude -p` and capturing full response metrics.

All test scripts use `claude -p --output-format json`, which returns:
    {
      "type": "result",
      "subtype": "success",
      "result": "...",
      "usage": {
        "input_tokens": N,
        "output_tokens": N,
        "cache_creation_input_tokens": N,
        "cache_read_input_tokens": N
      },
      "total_cost_usd": N,
      "duration_ms": N,
      "duration_api_ms": N,
      "num_turns": N,
      "session_id": "...",
      "is_error": false,
      "permission_denials": []
    }

Previously, scripts extracted only `result` and discarded all metadata.
This module preserves everything.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path


# Names copied from the parent environment into the `claude -p` child. Everything
# else is dropped (replace, not merge), so a stray ANTHROPIC_API_KEY,
# ANTHROPIC_AUTH_TOKEN, CLAUDE_CODE_SIMPLE or CLAUDE_CODE_USE_* in the parent can
# never reach the child and override the subscription login. Only names are
# listed here; values are copied at call time and never logged.
CHILD_ENV_ALLOWLIST = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "TMPDIR",
    "TERM",
    "USER",
    "LOGNAME",
    "CLAUDE_CONFIG_DIR",
)

# Key sources that mean the child did not use the subscription login.
FORBIDDEN_KEY_SOURCES = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


class AuthSourceError(RuntimeError):
    """The child reported an auth source other than the subscription login."""


def child_env(parent: dict[str, str] | None = None) -> dict[str, str]:
    """Build the child environment from the allowlist only."""
    src = os.environ if parent is None else parent
    return {k: src[k] for k in CHILD_ENV_ALLOWLIST if k in src}


def check_auth_source(stdout: str) -> None:
    """Refuse when the stream-json `system/init` event reports an API-key source.

    This is a weak check: `apiKeySource` is compared with the forbidden key
    sources. A stronger check would read the `account` fields of the SDK
    `initialize` response.
    """
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("type") == "system" and event.get("subtype") == "init":
            source = event.get("apiKeySource")
            if source in FORBIDDEN_KEY_SOURCES:
                raise AuthSourceError(
                    f"claude reported apiKeySource={source}; expected the subscription login"
                )
            return


def _result_event(stdout: str) -> str:
    """Return the final `result` event line of a stream-json run (or stdout unchanged)."""
    last = None
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("type") == "result":
            last = line
    return last if last is not None else stdout


@dataclass
class RunResult:
    """Complete result from a `claude -p` execution."""

    # Response
    response: str = ""
    is_error: bool = False
    exit_code: int = 0

    # Tokens (from usage object)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    # Cost
    cost_usd: float = 0.0

    # Timing
    duration_ms: int = 0
    duration_api_ms: int = 0
    total_duration_seconds: float = 0.0

    # Execution
    num_turns: int = 0
    session_id: str = ""

    # Permission denials (tools that were blocked)
    permission_denials: list[dict] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_timing_dict(self) -> dict:
        """Build a timing.json-compatible dict with all metrics."""
        d = {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "cost_usd": self.cost_usd,
            "duration_ms": self.duration_ms,
            "duration_api_ms": self.duration_api_ms,
            "total_duration_seconds": self.total_duration_seconds,
            "num_turns": self.num_turns,
            "session_id": self.session_id,
            "is_error": self.is_error,
            "exit_code": self.exit_code,
            "permission_denials": self.permission_denials,
            "response_length": len(self.response),
        }
        return d


def run_claude(
    prompt: str,
    skill_path: Path | None = None,
    timeout: int = 300,
    model: str | None = None,
    cwd: Path | None = None,
    allowed_tools: list[str] | None = None,
) -> RunResult:
    """Run a prompt through `claude -p --output-format stream-json` and capture everything.

    The child gets an allowlisted environment only (see `child_env`), and the run
    is refused when the `system/init` event reports an API-key `apiKeySource`.

    Args:
        prompt: The prompt to send.
        skill_path: Path to skill directory (None for baseline).
        timeout: Timeout in seconds.
        model: Optional model override.
        cwd: Working directory for the subprocess.
        allowed_tools: Tools to allow (default: Read, Glob, Grep).

    Returns:
        RunResult with all metrics from the JSON response.
    """
    env = child_env()
    claude_bin = shutil.which("claude", path=env.get("PATH"))
    if claude_bin is None:
        raise FileNotFoundError("claude executable not found on PATH")
    cmd = [claude_bin, "-p", prompt, "--output-format", "stream-json", "--verbose"]

    tools = allowed_tools or ["Read", "Glob", "Grep"]
    cmd.extend(["--allowedTools"] + tools)

    if model:
        cmd.extend(["--model", model])
    if skill_path:
        cmd.extend(["--skill-path", str(skill_path)])

    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
            env=env,
        )
        wall_duration = time.monotonic() - start
    except subprocess.TimeoutExpired:
        return RunResult(
            response=f"[TIMEOUT after {timeout}s]",
            is_error=True,
            exit_code=-1,
            duration_ms=timeout * 1000,
            total_duration_seconds=float(timeout),
        )

    check_auth_source(proc.stdout)
    return parse_claude_response(_result_event(proc.stdout), proc.returncode, wall_duration)


def parse_claude_response(
    stdout: str,
    returncode: int = 0,
    wall_duration: float | None = None,
) -> RunResult:
    """Parse the full JSON response from `claude -p --output-format json`.

    Extracts all fields instead of just the result text.
    Falls back gracefully if JSON parsing fails or fields are missing.
    """
    result = RunResult(exit_code=returncode)

    try:
        parsed = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        # Not valid JSON — treat entire stdout as response text
        result.response = stdout
        if wall_duration is not None:
            result.duration_ms = int(wall_duration * 1000)
            result.total_duration_seconds = round(wall_duration, 2)
        return result

    # Response text
    result.response = parsed.get("result", stdout)
    result.is_error = parsed.get("is_error", False)

    # Token usage
    usage = parsed.get("usage", {})
    result.input_tokens = usage.get("input_tokens", 0)
    result.output_tokens = usage.get("output_tokens", 0)
    result.cache_creation_input_tokens = usage.get("cache_creation_input_tokens", 0)
    result.cache_read_input_tokens = usage.get("cache_read_input_tokens", 0)

    # Cost
    result.cost_usd = parsed.get("total_cost_usd", 0.0) or 0.0

    # Timing — prefer API-reported values, fall back to wall clock
    result.duration_ms = parsed.get("duration_ms", 0)
    result.duration_api_ms = parsed.get("duration_api_ms", 0)
    if result.duration_ms:
        result.total_duration_seconds = round(result.duration_ms / 1000, 2)
    elif wall_duration is not None:
        result.duration_ms = int(wall_duration * 1000)
        result.total_duration_seconds = round(wall_duration, 2)

    # Execution metadata
    result.num_turns = parsed.get("num_turns", 0)
    result.session_id = parsed.get("session_id", "")

    # Permission denials
    result.permission_denials = parsed.get("permission_denials", [])

    return result


def save_timing(result: RunResult, timing_path: Path) -> None:
    """Write timing.json from a RunResult."""
    timing_path.write_text(json.dumps(result.to_timing_dict(), indent=2))

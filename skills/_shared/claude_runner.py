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
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path


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
    """Run a prompt through `claude -p --output-format json` and capture everything.

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
    cmd = ["claude", "-p", prompt, "--output-format", "json"]

    tools = allowed_tools or ["Read", "Glob", "Grep"]
    cmd.extend(["--allowedTools"] + tools)

    if model:
        cmd.extend(["--model", model])
    if skill_path:
        cmd.extend(["--skill-path", str(skill_path)])

    # Prevent nested Claude session detection
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

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

    return parse_claude_response(proc.stdout, proc.returncode, wall_duration)


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

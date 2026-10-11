"""Behavioural tests for claude_runner: the child environment is an allowlist, and an
API-key auth source is refused. A fake `claude` executable on PATH records the env var
NAMES it received (never values). No model call is made.

    python3 -m unittest skills/_shared/test_claude_runner.py
"""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import claude_runner  # noqa: E402

FORBIDDEN = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "CLAUDE_CODE_SIMPLE",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "CLAUDECODE",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "UNLISTED_EXTRA_NAME",
)


def _write_fake_claude(directory: Path, names_file: Path, key_source: str) -> None:
    events = [
        {"type": "system", "subtype": "init", "apiKeySource": key_source, "session_id": "s"},
        {
            "type": "result",
            "subtype": "success",
            "result": "ok",
            "is_error": False,
            "usage": {"input_tokens": 1, "output_tokens": 2},
            "num_turns": 1,
            "session_id": "s",
        },
    ]
    body = "\n".join(json.dumps(e) for e in events)
    script = directory / "claude"
    script.write_text(
        "#!/bin/sh\n"
        f"env | cut -d= -f1 | sort > '{names_file}'\n"
        f"cat <<'EOF'\n{body}\nEOF\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)


class ClaudeRunnerEnvTest(unittest.TestCase):
    def _run(self, key_source: str):
        tmp = Path(tempfile.mkdtemp())
        names = tmp / "names.txt"
        _write_fake_claude(tmp, names, key_source)
        parent = {name: "synthetic" for name in FORBIDDEN}
        parent.update({"PATH": f"{tmp}:/usr/bin:/bin", "HOME": str(tmp), "CLAUDE_CONFIG_DIR": str(tmp)})
        with mock.patch.dict(os.environ, parent, clear=True):
            result = claude_runner.run_claude("synthetic prompt", cwd=tmp)
        return result, set(names.read_text().split())

    def test_forbidden_names_never_reach_the_child(self):
        result, received = self._run("none")
        self.assertEqual(result.response, "ok")
        for name in FORBIDDEN:
            self.assertNotIn(name, received)
        self.assertIn("CLAUDE_CONFIG_DIR", received)
        self.assertIn("PATH", received)

    def test_child_env_is_a_replacement_of_exactly_the_allowlist(self):
        _, received = self._run("none")
        self.assertLessEqual(received - {"PWD", "SHLVL", "_", "OLDPWD"}, set(claude_runner.CHILD_ENV_ALLOWLIST))

    def test_api_key_source_is_refused(self):
        with self.assertRaises(claude_runner.AuthSourceError):
            self._run("ANTHROPIC_API_KEY")


if __name__ == "__main__":
    unittest.main()

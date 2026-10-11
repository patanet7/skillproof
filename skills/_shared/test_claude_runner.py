"""Behavioural tests for claude_runner: the child environment is a per-mode allowlist
(subscription and api_key), and an auth source that mismatches the requested mode is
refused. A fake `claude` executable on PATH records the env var NAMES it received
(never values). No model call is made.

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

# Names that must never reach the child in any mode.
ALWAYS_FORBIDDEN = (
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "CLAUDE_CODE_SIMPLE",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "CLAUDECODE",
    "UNLISTED_EXTRA_NAME",
)
SUBSCRIPTION_ONLY = ("CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CONFIG_DIR")
API_KEY_ONLY = ("ANTHROPIC_API_KEY",)
ALL_NAMES = ALWAYS_FORBIDDEN + SUBSCRIPTION_ONLY + API_KEY_ONLY


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
    def _run(self, key_source: str, auth_mode: str | None = None, extra_env: dict | None = None):
        tmp = Path(tempfile.mkdtemp())
        names = tmp / "names.txt"
        _write_fake_claude(tmp, names, key_source)
        parent = {name: "synthetic" for name in ALL_NAMES}
        parent.update({"PATH": f"{tmp}:/usr/bin:/bin", "HOME": str(tmp)})
        parent.update(extra_env or {})
        with mock.patch.dict(os.environ, parent, clear=True):
            result = claude_runner.run_claude("synthetic prompt", cwd=tmp, auth_mode=auth_mode)
        return result, set(names.read_text().split())

    def test_subscription_is_the_default_and_drops_api_keys(self):
        result, received = self._run("none")
        self.assertEqual(result.response, "ok")
        for name in ALWAYS_FORBIDDEN + API_KEY_ONLY:
            self.assertNotIn(name, received)
        for name in SUBSCRIPTION_ONLY + ("PATH",):
            self.assertIn(name, received)

    def test_api_key_mode_passes_the_key_and_drops_login_variables(self):
        result, received = self._run("ANTHROPIC_API_KEY", auth_mode="api_key")
        self.assertEqual(result.response, "ok")
        self.assertIn("ANTHROPIC_API_KEY", received)
        for name in ALWAYS_FORBIDDEN + SUBSCRIPTION_ONLY:
            self.assertNotIn(name, received)

    def test_mode_can_come_from_the_environment(self):
        _, received = self._run("ANTHROPIC_API_KEY", extra_env={"SKILLPROOF_AUTH_MODE": "api_key"})
        self.assertIn("ANTHROPIC_API_KEY", received)

    def test_child_env_is_a_replacement_of_exactly_the_allowlist(self):
        for mode in claude_runner.AUTH_MODES:
            source = "ANTHROPIC_API_KEY" if mode == "api_key" else "none"
            _, received = self._run(source, auth_mode=mode)
            self.assertLessEqual(
                received - {"PWD", "SHLVL", "_", "OLDPWD"},
                set(claude_runner.CHILD_ENV_ALLOWLISTS[mode]),
            )

    def test_key_source_in_subscription_mode_is_refused(self):
        with self.assertRaises(claude_runner.AuthSourceError):
            self._run("ANTHROPIC_API_KEY", auth_mode="subscription")

    def test_no_key_source_in_api_key_mode_is_refused(self):
        with self.assertRaises(claude_runner.AuthSourceError):
            self._run("none", auth_mode="api_key")

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            self._run("none", auth_mode="bogus")

    def test_skill_is_loaded_through_a_plugin_dir(self):
        skill = Path(tempfile.mkdtemp()) / "demo-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text("---\nname: demo-skill\ndescription: synthetic\n---\n")
        tmp = Path(tempfile.mkdtemp())
        args_file = tmp / "args.txt"
        listing = tmp / "skills.txt"
        script = tmp / "claude"
        script.write_text(
            "#!/bin/sh\n"
            f"for a in \"$@\"; do printf '%s\\n' \"$a\"; done > '{args_file}'\n"
            "d=''; p=0\n"
            "for a in \"$@\"; do\n"
            "  if [ \"$p\" = 1 ]; then d=$a; p=0; fi\n"
            "  [ \"$a\" = --plugin-dir ] && p=1\n"
            "done\n"
            f"ls \"$d/skills\" > '{listing}'\n"
            "echo '{\"type\":\"system\",\"subtype\":\"init\",\"apiKeySource\":\"none\"}'\n"
            "echo '{\"type\":\"result\",\"result\":\"ok\"}'\n"
        )
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        with mock.patch.dict(os.environ, {"PATH": f"{tmp}:/usr/bin:/bin", "HOME": str(tmp)}, clear=True):
            claude_runner.run_claude("synthetic prompt", skill_path=skill, cwd=tmp)
        args = args_file.read_text().split("\n")
        self.assertIn("--plugin-dir", args)
        self.assertNotIn("--skill-path", args)
        self.assertEqual(listing.read_text().split(), ["demo-skill"])


if __name__ == "__main__":
    unittest.main()

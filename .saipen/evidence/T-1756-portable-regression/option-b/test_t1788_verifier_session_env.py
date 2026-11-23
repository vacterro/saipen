"""T-1788: a verifier's environment is the execution's, not the session's.

`regression_execution._runtime` digested every environment key but SAIPEN_*.
T-1787's pair, recorded under `timeout 590 saipen work regression`, was stale
for the plain `saipen transition REVIEW` that followed: bash had set `_` to the
wrapper's path. The same binding staled receipts on `OLDPWD`, cmd's `PROMPT`
(T-1714) and every new host session (`CLAUDE_CODE_SESSION_ID`, `CLAUDE_PID`),
so a `/clear` between VERIFY and the finish cost a second measured pair.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import regression_execution as rx  # noqa: E402

COMMAND = ["{python}", "-c", "pass"]
SESSION_A = {
    "_": "/usr/bin/timeout",
    "OLDPWD": "/one",
    "PWD": "/one/tools",
    "SHLVL": "1",
    "PROMPT": "$P$G",
    "CLAUDE_CODE_SESSION_ID": "session-a",
    "CLAUDE_PID": "101",
}
SESSION_B = {
    "_": "/c/Users/someone/bin/saipen",
    "OLDPWD": "/two",
    "PWD": "/two",
    "SHLVL": "3",
    "PROMPT": "> ",
    "CLAUDE_CODE_SESSION_ID": "session-b",
    "CLAUDE_PID": "202",
}


def _base() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if key not in SESSION_A and not key.startswith(("CLAUDE", "SAIPEN_"))
    }


def _measure(extra: dict[str, str]) -> tuple[str, dict[str, str]]:
    with mock.patch.dict(os.environ, {**_base(), **extra}, clear=True):
        _runtime, _argv, environment = rx._runtime(COMMAND)
    return rx._sha(rx._json(environment)), environment


class SessionKeysTests(unittest.TestCase):
    def test_two_sessions_on_one_environment_share_the_verifier_digest(self):
        digest_a, environment_a = _measure(SESSION_A)
        digest_b, _ = _measure(SESSION_B)
        digest_none, _ = _measure({})
        self.assertEqual(digest_a, digest_b)
        self.assertEqual(digest_a, digest_none)
        for key in SESSION_A:
            self.assertNotIn(key, environment_a, "a session key reached the verifier")
        self.assertEqual(environment_a.get("SAIPEN_CAPABILITY"), "no-publish")

    def test_a_real_environment_change_still_moves_the_digest(self):
        digest_a, _ = _measure(SESSION_A)
        moved, _ = _measure({**SESSION_A, "PYTHONPATH": "X:/somewhere-else"})
        self.assertNotEqual(digest_a, moved)
        path_moved, _ = _measure({**SESSION_A, "PATH": "X:/other-bin"})
        self.assertNotEqual(digest_a, path_moved)


if __name__ == "__main__":
    unittest.main()

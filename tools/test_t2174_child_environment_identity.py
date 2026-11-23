"""T-2174: a name excluded from verification identity must not reach the child.

T-2165 removed CODEBUFF_LAUNCHER_PID, SHLVL, OLDPWD and `_` from the identity
digest so a family PASS survives an agent-turn change in shell bookkeeping. But
`family_environment()` starts from `os.environ` and only pops
`SHELL_BOOKKEEPING_ENV` (`_`) and the launcher diagnostic names: the other
three per-invocation values stay in the actual test child. Two launches with
the same identity projection can therefore run children with different
`SHLVL`/`OLDPWD`/`CODEBUFF_LAUNCHER_PID` values -- the observable collision
recorded in Campaign XVIII §6.

The invariant: if a variable can vary per invocation without changing what the
family verifies, it must be absent from BOTH the digest and the canonical child
environment. Genuine toolchain changes (PATH, executable dirs) still invalidate
compatibility.
"""

from __future__ import annotations

import os
import types
import unittest
from unittest.mock import patch

from saipen_engine.test_runner import (
    IDENTITY_PER_INVOCATION_ENV,
    family_environment,
    identity_environment,
)


class ChildEnvironmentIdentityTests(unittest.TestCase):
    def test_excluded_bookkeeping_names_are_absent_from_canonical_child(self):
        ambient = {
            "PATH": "/usr/bin",
            "CODEBUFF_LAUNCHER_PID": "4321",
            "SHLVL": "7",
            "OLDPWD": "/previous/directory",
            "_": "/usr/bin/python",
            "SAIPEN_TEST_MODE": "stable",
        }
        with patch("saipen_engine.test_runner.os.environ", ambient):
            child = family_environment(types.SimpleNamespace(command=None))
        for name in IDENTITY_PER_INVOCATION_ENV:
            self.assertNotIn(name, child, f"{name} leaked into the test child")
        self.assertIn("/usr/bin", child["PATH"].split(os.pathsep))
        self.assertEqual(child["SAIPEN_TEST_MODE"], "stable")
        self.assertEqual(child["SAIPEN_CANONICAL_TEST_CHILD"], "1")

    def test_same_identity_projection_implies_same_child_bookkeeping(self):
        first_ambient = {
            "PATH": "/usr/bin", "SHLVL": "1", "OLDPWD": "/a",
            "CODEBUFF_LAUNCHER_PID": "11", "SAIPEN_TEST_MODE": "stable",
        }
        second_ambient = {
            "PATH": "/usr/bin", "SHLVL": "9", "OLDPWD": "/b",
            "CODEBUFF_LAUNCHER_PID": "99", "SAIPEN_TEST_MODE": "stable",
        }
        with patch("saipen_engine.test_runner.os.environ", first_ambient):
            first_child = family_environment(types.SimpleNamespace(command=None))
            first_identity = identity_environment(first_child)
        with patch("saipen_engine.test_runner.os.environ", second_ambient):
            second_child = family_environment(types.SimpleNamespace(command=None))
            second_identity = identity_environment(second_child)
        self.assertEqual(first_identity, second_identity)
        self.assertEqual(first_child, second_child)


if __name__ == "__main__":
    unittest.main()

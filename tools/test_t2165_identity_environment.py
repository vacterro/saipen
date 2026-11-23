"""T-2165: verification identity must ignore per-invocation launcher state.

RED (pre-fix): identity_environment() kept CODEBUFF_LAUNCHER_PID, SHLVL,
OLDPWD and _ in the digest. A family record written in one agent turn could
not be cited by a later turn on the same unchanged host.

GREEN: those names are absent from identity_environment() while a real
environment change still invalidates the identity.
"""

from __future__ import annotations

import unittest

from saipen_engine.test_runner import identity_environment


class IdentityEnvironmentTests(unittest.TestCase):
    def test_per_invocation_names_are_not_part_of_identity(self):
        env = {
            "PATH": "/usr/bin",
            "SHELL": "/bin/bash",
            "CODEBUFF_LAUNCHER_PID": "1234",
            "SHLVL": "3",
            "OLDPWD": "/previous/directory",
            "_": "/usr/bin/python",
            "SAIPEN_TEST_MODE": "stable",
        }
        result = identity_environment(env)
        for name in ("SHELL", "CODEBUFF_LAUNCHER_PID", "SHLVL", "OLDPWD", "_"):
            self.assertNotIn(name, result)
        self.assertEqual(result["PATH"], "/usr/bin")
        self.assertEqual(result["SAIPEN_TEST_MODE"], "stable")

    def test_two_invocations_with_only_bookkeeping_drift_agree(self):
        first = identity_environment(
            {"PATH": "/x", "SHLVL": "1", "CODEBUFF_LAUNCHER_PID": "1", "OLDPWD": "/a", "_": "a"}
        )
        second = identity_environment(
            {"PATH": "/x", "SHLVL": "9", "CODEBUFF_LAUNCHER_PID": "2", "OLDPWD": "/b", "_": "b"}
        )
        self.assertEqual(first, second)

    def test_a_real_change_still_changes_identity(self):
        self.assertNotEqual(
            identity_environment({"PATH": "/x", "SAIPEN_TEST_MODE": "a"}),
            identity_environment({"PATH": "/x", "SAIPEN_TEST_MODE": "b"}),
        )


if __name__ == "__main__":
    unittest.main()

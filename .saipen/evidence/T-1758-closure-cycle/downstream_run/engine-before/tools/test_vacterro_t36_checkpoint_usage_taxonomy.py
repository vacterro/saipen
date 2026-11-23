"""T-36: the CLI usage for `checkpoint` names its closed taxonomy set.

Measured on this repository (vacterro-saiwebsite improve 20261013-1 IMP-001):
an agent typed `saipen checkpoint ship T-34 ...`, the engine refused with
`taxonomy 'ship' outside ['DEC', 'RUN']` -- a legal, helpful answer -- but the
usage surface had said `checkpoint <TAXONOMY>` with no way to LEARN the legal
set, so the first checkpoint attempt by a fresh session is blind.

The refusal already names the set (saipen_engine.operations.checkpoint ->
_CHECKPOINT_TAXONOMIES). The usage strings now name the same set, derived from
the SAME constant, so usage and refusal cannot drift apart.

Implementation in tools/saipen.py: the top-level usage string and the
`checkpoint needs <...>` validation detail print `<DEC|RUN>`.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine.operations import _CHECKPOINT_TAXONOMIES  # noqa: E402


class CheckpointUsageNamesTaxonomy(unittest.TestCase):
    def test_the_constant_is_the_closed_set(self) -> None:
        self.assertEqual(_CHECKPOINT_TAXONOMIES, {"DEC", "RUN"})

    def test_help_prints_the_closed_set(self) -> None:
        proc = subprocess.run(
            [sys.executable, "saipen.py", "--help"],
            cwd=ROOT / "tools",
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("checkpoint <DEC|RUN>", proc.stdout)
        self.assertNotIn("checkpoint <TAXONOMY>", proc.stdout)

    def test_the_validation_detail_prints_the_same_set(self) -> None:
        # A fixture project, so the refusal is the argument check and not the
        # missing-project one: run from a tree without .saipen (a regression
        # sandbox) the old call answered NOT_SAIPEN_PROJECT (T-1781).
        from test_guard_hostile_matrix import fresh_project

        proc = subprocess.run(
            [sys.executable, "saipen.py", "--project-root", str(fresh_project()), "checkpoint"],
            cwd=ROOT / "tools",
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("checkpoint needs <DEC|RUN> [T-###] [text]", proc.stdout + proc.stderr)

    def test_usage_and_refusal_cannot_drift(self) -> None:
        """The usage token is derived from the engine's own closed set."""
        # The usage token must be derived from the engine's closed set.
        token = "|".join(sorted(_CHECKPOINT_TAXONOMIES))
        usage = (Path(__file__).parent / "saipen.py").read_text(encoding="utf-8")
        self.assertIn(
            f"<{token}>",
            usage,
            f"usage names no <{token}> token: keep the usage string and "
            "_CHECKPOINT_TAXONOMIES in step or the vocabulary drifts again",
        )
        self.assertNotIn(
            "<TAXONOMY>",
            usage,
            "a bare <TAXONOMY> placeholder teaches the caller nothing about the legal set",
        )


if __name__ == "__main__":
    unittest.main()

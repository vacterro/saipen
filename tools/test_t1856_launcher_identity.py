"""T-1856: verification identity must not follow the shell that launched it.

Measured 2026-10-22 on T-1815. The `saipen` shim on PATH execs
`python.EXE`; a direct `python tools/saipen.py` uses `python`. Bash keeps `_`
as the last argument of the previous command, so the two spellings inherited
different values for one name that decides nothing about the child's
behaviour. `verification_cache.capture` hashes the whole canonical child
environment, so the SAME unchanged tree produced two identities, and the SHIP
gate refused a record that the other spelling's own engine had just written
as "missing or incompatible verification environment identity".

That is the same class T-1834 closed for per-tool-call carriers: identity
follows the subject, never the invocation. The fix removes the shell's
bookkeeping name in the one owner that builds the child environment, so both
spellings and both the evidence writer and its consumer agree.

Proven here:
- two environments that differ ONLY in `_` capture the same identity digest;
- a real environment change still invalidates the record (the red control
  that keeps this from becoming a no-op rule);
- the canonical child really does not carry the name, through a real
  execution, so the fix is a property of the child and not just the digest;
- an executed record written under one spelling is accepted by the other.

Run standalone:
    python tools/test_t1856_launcher_identity.py
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

from saipen_engine import verification_cache as cache  # noqa: E402
from saipen_engine.test_runner import (  # noqa: E402
    SHELL_BOOKKEEPING_ENV,
    TestFamily,
    _run_family,
    family_environment,
)
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


LOWER = f"{sys.executable}"
UPPER = f"{Path(sys.executable).with_suffix('.EXE')}"


class ShellBookkeepingTests(unittest.TestCase):
    """The one owner that builds the canonical child decides what it holds."""

    def test_the_child_never_carries_the_shells_last_argument(self):
        for spelling in (LOWER, UPPER):
            with mock.patch.dict(os.environ, {"_": spelling}):
                env = family_environment(TestFamily("identity", (spelling,), 10))
            self.assertNotIn(
                "_", env, f"the child inherited the shell's bookkeeping via {spelling}"
            )

    def test_two_launcher_spellings_capture_one_identity(self):
        """The exact T-1815 measurement: one tree, two spellings, one identity."""
        configuration = {"family": "focused-unit", "timeout": 300}
        with mock.patch.dict(os.environ, {"_": LOWER}):
            lower = cache.capture(TOOLS.parent, configuration)
        with mock.patch.dict(os.environ, {"_": UPPER}):
            upper = cache.capture(TOOLS.parent, configuration)
        self.assertEqual(
            sorted(key for key in set(lower) | set(upper) if lower.get(key) != upper.get(key)),
            [],
            "two spellings of the same interpreter produced different identities",
        )

    def test_a_real_environment_change_still_invalidates_the_identity(self):
        """The red control: the rule must not erase distinctions that matter."""
        configuration = {"family": "focused-unit", "timeout": 300}
        with mock.patch.dict(os.environ, {"_": LOWER}):
            before = cache.capture(TOOLS.parent, configuration)
        with mock.patch.dict(os.environ, {"_": UPPER, "SAIPEN_TEST_MODE": "DIFFERENT"}):
            after = cache.capture(TOOLS.parent, configuration)
        self.assertNotEqual(
            before["environment_sha256"],
            after["environment_sha256"],
            "a semantic environment change must still invalidate evidence",
        )

    def test_the_rule_names_exactly_the_shell_bookkeeping(self):
        """A narrow list: adding a real carrier here would hide drift."""
        self.assertEqual(SHELL_BOOKKEEPING_ENV, frozenset({"_"}))


class RealChildTests(unittest.TestCase):
    """The property through an actual execution, not only through the digest."""

    def setUp(self) -> None:
        import shutil
        import tempfile

        from saipen_engine.journal import ensure_project_lineage

        self.project = Path(tempfile.mkdtemp(prefix="t1856-"))
        self.addCleanup(shutil.rmtree, self.project, True)
        (self.project / ".saipen").mkdir(parents=True)
        (self.project / ".saipen" / "LOG.md").write_text(
            "- 22.10.26 00:00 [E-001] [T-1] [agent: probe] DEC: base\n", encoding="utf-8"
        )
        (self.project / ".saipen" / "BOARD.md").write_text(
            "# Board\n## DOING\n## TODO\n## DONE\n## BLOCKED\n", encoding="utf-8"
        )
        ensure_project_lineage(self.project)

    def test_a_real_child_sees_no_bookkeeping_name(self):
        code = "import json,os; print(json.dumps(os.environ.get('_')))"
        for spelling in (LOWER, UPPER):
            with mock.patch.dict(os.environ, {"_": spelling}):
                result = _run_family(
                    self.project, TestFamily("probe", (spelling, "-c", code), 30)
                )
            self.assertEqual(result["status"], "PASS", result)
            self.assertEqual(
                result["stdout"].strip(),
                "null",
                f"the real child inherited the shell's bookkeeping through {spelling}",
            )

    def test_an_identity_is_accepted_under_the_other_spelling(self):
        """The end-to-end claim: captured under one, compatible under the other."""
        configuration = {
            "family": "focused-unit",
            "patterns": ["test_t1856_launcher_identity.py"],
            "timeout": 300,
        }
        with mock.patch.dict(os.environ, {"_": LOWER}):
            written = cache.capture(self.project, configuration)
        with mock.patch.dict(os.environ, {"_": UPPER}):
            self.assertTrue(
                cache.compatible(self.project, written),
                "the other spelling refused an identity of the same real environment",
            )


if __name__ == "__main__":
    unittest.main()

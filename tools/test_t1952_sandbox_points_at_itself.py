"""T-1952: a core-unit sandbox must describe ITSELF, not the tree it copied.

Measured defect. `saipen evidence --family unit --jobs 6` returned opposite
verdicts for one tree fingerprint, repeated, with no source change:

    fingerprint 7e924cf0   PASS 0 red 15:24   FAIL 12 red 16:17
    fingerprint 7b04fc65   FAIL 34 red 16:56   PASS 0 red 17:41

The reds named `home-dead: home-divergent` and two executed the copy's own
`bin/saipen`. Both come from the same thing: the copy carried two install
pointers written verbatim from the source tree -- the launchers name the engine
by absolute path, and `.saipen/STATE.md`'s `saipen_home:` names the source
install. Inside the copy `state.running_home()` is the COPY, so the two
pointers disagreed with the running install exactly when the source tree had
drifted -- the normal condition of a tree under test. A verdict then described
the source tree's cleanliness, not the copied bytes, which is why one
fingerprint could produce both answers.

Pinned here, in both directions:

- the copy's launchers and `saipen_home` name the COPY;
- those two files are outside the subject fingerprint, so rewriting them cannot
  change what the record claims to have tested;
- a copy of a DRIFTED source agrees with itself (the RED control: with the old
  verbatim pointers the same fixture answered `home-divergent`).
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import core_unit  # noqa: E402
from saipen_engine.test_runner import _ignore_copy  # noqa: E402

STATE = """---
phase: DONE
task: none
next_action: "PHASE SCOUT T-1"
blocker: none
saipen_home: "{home}"
---

## notes
"""


def _home_from(text: str) -> str | None:
    match = re.search(r'(?m)^saipen_home:\s*"?([^"\r\n]+?)"?\s*$', text)
    return match.group(1) if match else None


class SandboxPointsAtItselfTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="t1952-pointers-"))
        self.addCleanup(shutil.rmtree, self.base, True)
        self.source = self.base / "source"
        (self.source / ".saipen").mkdir(parents=True)
        (self.source / "bin").mkdir()
        # The source names ITSELF, exactly as an install does.
        (self.source / ".saipen" / "STATE.md").write_text(
            STATE.format(home=self.source.as_posix()), encoding="utf-8")
        (self.source / "bin" / "saipen.cmd").write_text(
            f'@echo off\r\ncmd_abs_engine "{self.source / "tools" / "saipen.py"}" %*\r\n',
            encoding="utf-8")
        (self.source / "bin" / "saipen").write_text(
            f'#!/bin/sh\nexec posix_abs_engine "{self.source.as_posix()}/tools/saipen.py" "$@"\n',
            encoding="utf-8")
        (self.source / "tools").mkdir()
        (self.source / "tools" / "saipen.py").write_text("# engine\n", encoding="utf-8")

    def _copy(self, name="sandbox") -> Path:
        target = self.base / name
        core_unit.copy_tree_consistent(self.source, target, _ignore_copy)
        return target

    def test_the_copy_names_itself_and_not_the_tree_it_copied(self):
        target = self._copy()
        home = _home_from((target / ".saipen" / "STATE.md").read_text(encoding="utf-8"))
        self.assertIsNotNone(home, "the copy lost its saipen_home line")
        self.assertEqual(Path(home).resolve(), target.resolve())
        self.assertNotEqual(Path(home).resolve(), self.source.resolve())
        for name in ("saipen", "saipen.cmd"):
            self.assertNotIn(
                str(self.source.resolve()), (target / "bin" / name).read_text(encoding="utf-8"),
                f"bin/{name} in the copy still names the source install")
            self.assertIn(
                "..", (target / "bin" / name).read_text(encoding="utf-8"),
                f"bin/{name} is not the relocatable form that follows the copy")

    def test_rewriting_the_pointers_cannot_change_the_subject_fingerprint(self):
        """The record must still describe the bytes that ran."""
        before = core_unit.tree_fingerprint(self.source)
        self.assertIn("bin", core_unit.FINGERPRINT_EXCLUDED)
        # `.saipen` was already outside the digest; `bin` joins it (T-1952).
        (self.source / "bin" / "saipen.cmd").write_text("different\n", encoding="utf-8")
        self.assertEqual(core_unit.tree_fingerprint(self.source), before)
        target = self._copy()
        self.assertEqual(core_unit.tree_fingerprint(target), before)

    def test_a_copy_of_a_drifted_source_agrees_with_itself(self):
        """RED control: verbatim pointers answered `home-divergent` here.

        Drift is the ordinary state of a tree being tested. The copy must be
        unaffected, because its pointers were rewritten to name itself.
        """
        (self.source / "tools" / "saipen_engine.py").write_text(
            "DECLARED = 1\n", encoding="utf-8")
        target = self._copy()
        home = _home_from((target / ".saipen" / "STATE.md").read_text(encoding="utf-8"))
        self.assertEqual(Path(home).resolve(), target.resolve())
        # The copy's own engine is the one a launcher would run.
        self.assertIn("..", (target / "bin" / "saipen.cmd").read_text(encoding="utf-8"))

    def test_a_broken_or_absent_state_is_reported_not_invented(self):
        (self.source / ".saipen" / "STATE.md").unlink()
        target = self._copy("no-state")
        self.assertFalse((target / ".saipen" / "STATE.md").exists())
        self.assertTrue((target / "bin" / "saipen.cmd").is_file())

    def test_the_rebind_is_recorded_for_the_evidence_record(self):
        target = self.base / "reported"
        metrics = core_unit.copy_tree_consistent(self.source, target, _ignore_copy)
        pointers = metrics.get("pointers")
        self.assertIsInstance(pointers, dict, metrics)
        self.assertEqual(pointers.get("home"), target.resolve().as_posix())
        self.assertIn(".saipen/STATE.md", pointers.get("rewritten", []))

    def test_a_shard_copied_from_another_shard_is_rebound(self):
        """A shard is a copy of shard 0, which already names ITSELF.

        Without the second rebind every shard inherits shard 0's home and
        launchers, so 5 of 6 shards answer about a project that lives in
        another shard. Pinned because the fix has to run per shard.
        """
        first = self._copy("shard0")
        second = self.base / "shard1"
        shutil.copytree(first, second, symlinks=True)

        def home_of(path: Path) -> Path | None:
            text = (path / ".saipen" / "STATE.md").read_text(encoding="utf-8")
            value = _home_from(text)
            return Path(value).resolve() if value else None

        self.assertEqual(
            home_of(second), first.resolve(),
            "precondition: the raw copytree inherits shard 0's home")
        core_unit.rebind_sandbox_pointers(second)
        self.assertEqual(
            home_of(second), second.resolve(),
            "a shard must name itself, not the shard it was copied from")


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""T-1889: a focused sandbox copies what its subject DECLARED, never less.

Measured defect. A focused gate spent 54-60 s of a 71-80 s run copying 1815 MiB
in 135450 files (`.saipen` 1474 MiB, `.git` 345 MiB) while the selected tests
executed in 1.5 s. On the live tree the same copier with an empty declaration
copied 22.4 MiB in 0.39 s, a 51 s difference on identical bytes
(`.saipen/evidence/T-1889-sandbox-scope/ab-copy.log`).

What makes narrowing defensible rather than a shortcut:

  * `tree_fingerprint` ALREADY excludes `.git` and `.saipen` at the top level.
    A record never attested those bytes, so not copying them takes nothing away
    from what a PASS claims about the source tree.
  * the decision is a DECLARATION in `tools/sandbox_scope.json`, never an
    inference from imports. The campaign's hard rule is that static analysis
    does not prove dependency completeness.
  * the default is FULL. A module with no entry copies everything, exactly as
    before this change, so an omission degrades to the old cost and never to a
    smaller subject.

What this module pins, one test per clause of the ticket's verify line:

  * a declared-empty module copies no history and no `.saipen` subtree, and the
    canonical `.saipen` files still arrive (project resolution depends on them);
  * a module that reads `.saipen/evidence` still sees it when declared -- and
    FAILS when the same module is declared with no trees, which is the control
    that makes the declaration load-bearing rather than decorative;
  * an undeclared module copies everything, `.git` included;
  * the resolved decision is in the evidence record, and a record whose
    decision no longer matches the manifest is refused rather than reused.

Fail-closed behaviour is pinned too: an unreadable or malformed manifest, an
entry naming a subtree that does not exist, and an entry that would drop part
of the tested subject are each a refusal, never a silent fallback.

Run standalone:
    python tools/test_t1889_sandbox_scope.py
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import core_unit, sandbox_scope  # noqa: E402
from saipen_engine.test_runner import _ignore_copy  # noqa: E402
from test_core_unit_gate import CoreUnitFixture  # noqa: E402

PROOF = "the evidence a history-reading subject needs\n"


def _write_manifest(project: Path, modules: dict) -> None:
    path = project / sandbox_scope.SCOPE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema": 1, "modules": modules}), encoding="utf-8")


def _copy(project: Path, scope, name: str = "sandbox") -> Path:
    target = project.parent / name
    core_unit.copy_tree_consistent(project, target, _ignore_copy, scope=scope)
    return target


class SandboxScopeTests(CoreUnitFixture):
    """A project whose heavy trees are big enough that copying them is visible."""

    def setUp(self):
        super().setUp()
        tools = self.project / "tools"
        tools.mkdir(parents=True, exist_ok=True)
        (self.project / ".git").mkdir()
        (self.project / ".git/objects").mkdir()
        (self.project / ".git/objects/pack").write_bytes(b"\0" * 4096)
        (self.project / ".git/HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        evidence = self.project / ".saipen/evidence"
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / "proof.txt").write_text(PROOF, encoding="utf-8")
        (self.project / ".saipen/recovery").mkdir(exist_ok=True)
        (self.project / ".saipen/recovery/big.bin").write_bytes(b"\0" * 4096)

    # -- clause 1: a declared module copies only the source tree --------------

    def test_a_declared_module_copies_no_history(self):
        _write_manifest(self.project, {"test_plain.py": []})
        scope = sandbox_scope.resolve(self.project, ["test_plain.py"])
        self.assertEqual(scope["mode"], sandbox_scope.DECLARED)
        self.assertEqual(scope["trees"], [])
        sandbox = _copy(self.project, scope)
        self.assertFalse((sandbox / ".git").exists(),
                         "a declared source-only copy must not carry .git")
        self.assertFalse((sandbox / ".saipen/evidence").exists())
        self.assertFalse((sandbox / ".saipen/recovery").exists())
        for name in ("STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md"):
            self.assertTrue(
                (sandbox / ".saipen" / name).is_file(),
                f"the canonical {name} must always be copied: project "
                "resolution reads it, and a sandbox that cannot resolve its "
                "project is a different subject",
            )

    # -- clause 2: a module that reads .saipen/evidence still sees it ----------

    def test_a_declared_history_reader_still_sees_evidence(self):
        _write_manifest(self.project, {"test_reader.py": [".saipen/evidence"]})
        scope = sandbox_scope.resolve(self.project, ["test_reader.py"])
        sandbox = _copy(self.project, scope)
        self.assertTrue((sandbox / ".saipen/evidence/proof.txt").is_file(),
                        "a declared .saipen/evidence must arrive in the sandbox")
        self.assertFalse((sandbox / ".saipen/recovery").exists(),
                         "an UNDECLARED subtree must not arrive with it")
        self.assertFalse((sandbox / ".git").exists())

    def test_the_declaration_is_load_bearing_for_a_real_reader(self):
        """The same module passes when declared and FAILS when it is not."""
        (self.project / "tools/test_reader.py").write_text(
            "import unittest\nfrom pathlib import Path\n\n\n"
            "class Reader(unittest.TestCase):\n"
            "    def test_it_reads_the_evidence(self):\n"
            f"        self.assertEqual(Path('.saipen/evidence/proof.txt')"
            f".read_text(encoding='utf-8'), {PROOF!r})\n",
            encoding="utf-8",
        )
        _write_manifest(self.project, {"test_reader.py": [".saipen/evidence"]})
        served = self._focused(["test_reader.py"])
        self.assertEqual(served["verdict"], "PASS", served.get("problem"))
        self.assertEqual(served["sandbox_scope"]["trees"], [".saipen/evidence"])

        _write_manifest(self.project, {"test_reader.py": []})
        starved = self._focused(["test_reader.py"])
        self.assertEqual(
            starved["verdict"], "FAIL",
            "the reader passed without its declared tree: the declaration is "
            "not what decides the copy, so a wrong entry would read as harmless",
        )

    def _focused(self, patterns):
        from saipen_engine.focused_unit import run_focused

        return run_focused(self.project, patterns, timeout=60)

    # -- clause 3: an undeclared module copies everything ---------------------

    def test_an_undeclared_module_copies_everything(self):
        scope = sandbox_scope.resolve(self.project, ["test_undeclared.py"])
        self.assertEqual(scope["mode"], sandbox_scope.FULL)
        self.assertEqual(scope["undeclared"], ["test_undeclared.py"])
        sandbox = _copy(self.project, scope)
        self.assertTrue((sandbox / ".git/objects/pack").is_file())
        self.assertTrue((sandbox / ".saipen/evidence/proof.txt").is_file())
        self.assertTrue((sandbox / ".saipen/recovery/big.bin").is_file())

    def test_one_undeclared_pattern_makes_the_whole_run_full(self):
        _write_manifest(self.project, {"test_known.py": []})
        scope = sandbox_scope.resolve(self.project, ["test_known.py", "test_mystery.py"])
        self.assertEqual(scope["mode"], sandbox_scope.FULL,
                         "one sandbox holds one snapshot; a declared module must "
                         "not drag an undeclared one into a narrowed copy")

    # -- clause 4: the decision is in the record and guarded on reuse ---------

    def test_the_decision_is_in_the_evidence_record(self):
        (self.project / "tools/test_plain.py").write_text(
            "import unittest\nclass Plain(unittest.TestCase):\n"
            "    def test_ok(self):\n        self.assertEqual(1, 1)\n",
            encoding="utf-8",
        )
        _write_manifest(self.project, {"test_plain.py": []})
        record = self._focused(["test_plain.py"])
        self.assertEqual(record["verdict"], "PASS", record.get("problem"))
        self.assertEqual(record["sandbox_scope"]["mode"], sandbox_scope.DECLARED)
        self.assertEqual(record["sandbox_scope"]["trees"], [])
        self.assertEqual(record["copy_metrics"]["trees"], [])
        self.assertIsNone(sandbox_scope.problem(record["sandbox_scope"]))
        self.assertIsNone(sandbox_scope.is_current(
            record["sandbox_scope"],
            sandbox_scope.resolve(self.project, ["test_plain.py"]),
        ))

    def test_a_record_from_a_narrower_copy_is_not_reused_after_a_new_declaration(self):
        from saipen_engine.focused_unit import record_problem

        (self.project / "tools/test_plain.py").write_text(
            "import unittest\nclass Plain(unittest.TestCase):\n"
            "    def test_ok(self):\n        self.assertEqual(1, 1)\n",
            encoding="utf-8",
        )
        _write_manifest(self.project, {"test_plain.py": []})
        record = self._focused(["test_plain.py"])
        self.assertIsNone(record_problem(self.project, record))

        _write_manifest(self.project, {"test_plain.py": [".saipen/evidence"]})
        issue = record_problem(self.project, record)
        self.assertIsNotNone(
            issue,
            "a pass from a sandbox that omitted a now-declared tree must not "
            "stand in for the run the manifest asks for (INV-20)",
        )
        # The manifest lives INSIDE the fingerprinted tree, so editing it moves
        # the fingerprint and that guard refuses first. Stated plainly rather
        # than dressed up: the fingerprint is the outer defence here.
        self.assertIn("different tree", issue)
        # The scope guard is the one that does not depend on a caller
        # recomputing the tree first, so it is asserted on its own terms.
        self.assertIn("sandbox scope", sandbox_scope.is_current(
            record["sandbox_scope"],
            sandbox_scope.resolve(self.project, ["test_plain.py"]),
        ))

    def test_a_pre_t1889_record_is_refused_once_a_manifest_narrows(self):
        from saipen_engine.focused_unit import record_problem

        (self.project / "tools/test_plain.py").write_text(
            "import unittest\nclass Plain(unittest.TestCase):\n"
            "    def test_ok(self):\n        self.assertEqual(1, 1)\n",
            encoding="utf-8",
        )
        record = self._focused(["test_plain.py"])
        self.assertIn("sandbox_scope", record)
        legacy = {key: value for key, value in record.items()}
        legacy.pop("sandbox_scope")
        self.assertIsNone(record_problem(self.project, legacy),
                          "with no manifest, a whole-tree record still describes "
                          "the whole-tree copy this run would make")
        _write_manifest(self.project, {"test_plain.py": []})
        self.assertIsNotNone(record_problem(self.project, legacy))

    # -- fail-closed controls -------------------------------------------------

    def test_a_malformed_manifest_is_a_refusal(self):
        path = self.project / sandbox_scope.SCOPE_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        for body in ("{not json", json.dumps({"schema": 2, "modules": {}}),
                     json.dumps({"schema": 1}), json.dumps({"schema": 1, "modules": []})):
            with self.subTest(body=body):
                path.write_text(body, encoding="utf-8")
                with self.assertRaises(sandbox_scope.ScopeError):
                    sandbox_scope.resolve(self.project, ["test_plain.py"])

    def test_an_entry_that_would_drop_the_subject_is_refused(self):
        for entry in ("tools", ".saipen", "audit", ".saipen/../tools"):
            with self.subTest(entry=entry):
                _write_manifest(self.project, {"test_plain.py": [entry]})
                with self.assertRaises(sandbox_scope.ScopeError):
                    sandbox_scope.resolve(self.project, ["test_plain.py"])

    def test_an_entry_naming_a_missing_subtree_is_refused(self):
        _write_manifest(self.project, {"test_plain.py": [".saipen/no-such-tree"]})
        with self.assertRaises(sandbox_scope.ScopeError):
            sandbox_scope.resolve(self.project, ["test_plain.py"])

    def test_the_identity_ignores_unrelated_manifest_edits(self):
        _write_manifest(self.project, {"test_a.py": []})
        first = sandbox_scope.resolve(self.project, ["test_a.py"])
        _write_manifest(self.project, {"test_a.py": [], "test_b.py": [".git"]})
        second = sandbox_scope.resolve(self.project, ["test_a.py"])
        self.assertNotEqual(first["manifest_sha256"], second["manifest_sha256"])
        self.assertEqual(sandbox_scope.identity(first), sandbox_scope.identity(second),
                         "editing another module's entry must not invalidate this "
                         "run's records; the bytes this run copies did not change")


if __name__ == "__main__":
    unittest.main(verbosity=2)

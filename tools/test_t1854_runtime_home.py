"""SRC-274:R004 -- a runtime-home rebind is a VERDICT, never a guessed executable.

F-04 measured the defect: a crashing PATH launcher, a disk probe, a machine
runtime that answered, and a project mutated through it while its own recorded
home still named the crashed tree. The version matched, so nothing objected --
and a version number is not an identity.

Each case below is one of the six facts the receipt names, and each case has to
fail for the RIGHT reason with the OTHER five still passing, so a green suite
cannot be green because everything refuses everything.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402

from saipen_engine import runtime_home  # noqa: E402


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def install(base: Path, name: str, *, version: str = "8.1.0", schema: int = 3,
            engine: str = "VALUE = 1\n") -> Path:
    """A candidate install with a real content surface to fingerprint."""
    home = base / name
    _write(home / "VERSION", version + "\n")
    _write(home / "BOOT.md", "# BOOT\n")
    _write(home / "extensions" / "subs" / "PROTOCOL.md", "# SUBS\n")
    _write(home / "extensions" / "schemas" / "state.schema.json",
           json.dumps({"x-current-schema-version": schema}) + "\n")
    _write(home / "tools" / "saipen.py", "# engine\n")
    _write(home / "tools" / "saipen_engine" / "operations.py", engine)
    return home


def project(base: Path, home: str | None, *, schema: int = 3) -> Path:
    root = base / "project"
    _write(root / ".saipen" / "STATE.md",
           "---\n"
           "phase: BUILD\n"
           "task: T-1\n"
           'next_action: "PHASE BUILD T-1"\n'
           'blocker: ""\n'
           "transition_from: SCOUT\n"
           "saipen_version: 8\n"
           f"schema_version: {schema}\n"
           "last_event: 2\n"
           f"style_contract: {CURRENT_STYLE_CONTRACT}\n"
           "agent: test-agent\n"
           "mode: full\n"
           'updated: "2026-10-27T00:00:00Z"\n'
           f'saipen_home: "{home or ""}"\n'
           "---\n")
    _write(root / ".saipen" / "BOARD.md",
           "## DOING\n- [/] T-1 [P1] work | verify: the fixture change is shown\n"
           "\n## TODO\n\n## DONE\n\n## BLOCKED\n")
    _write(root / ".saipen" / "LOG.md",
           "- 27.10.26 00:00 [E-001] [T-1] [op: ticket-00000000000000000000000000000000] "
           "DEC: ticket added via SAIOPS\n"
           "- 27.10.26 00:00 [E-002] [parent: E-001] [T-none] DEC: base\n")
    return root


class VerdictTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="t1854-home-")
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)

    def answers(self, view: dict) -> dict:
        return {item["check"]: item["answer"] for item in view["checks"]}

    def test_an_identical_install_is_accepted_on_all_six(self) -> None:
        home = install(self.base, "home")
        root = project(self.base, str(home))
        view = runtime_home.verdict(root, home, actor="test-agent", running_home_path=home)
        self.assertEqual(view["verdict"], runtime_home.ACCEPTED, view)
        self.assertEqual(
            self.answers(view),
            {
                "build_identity": "PASS",
                "loaded_revision": "UNPROVEN",
                "schema_compatibility": "PASS",
                "project_binding": "PASS",
                "actor_binding": "PASS",
                "no_pending_operation": "PASS",
            },
        )
        self.assertIsNone(runtime_home.problem(view))

    def test_a_candidate_that_proves_no_bytes_is_refused(self) -> None:
        home = install(self.base, "empty")
        for relative in ("tools", "extensions"):
            shutil.rmtree(home / relative)
        (home / "BOOT.md").unlink()
        (home / "VERSION").unlink()
        root = project(self.base, str(home))
        view = runtime_home.verdict(root, home, actor="test-agent")
        self.assertEqual(view["verdict"], runtime_home.REFUSED, view)
        self.assertEqual(self.answers(view)["build_identity"], "FAIL")
        self.assertIn("build_identity", runtime_home.problem(view))

    def test_a_foreign_engine_is_refused_when_identity_must_match(self) -> None:
        """The measured F-04 shape: another install answers, and it is not this one."""
        candidate = install(self.base, "candidate", engine="VALUE = 2\n")
        running = install(self.base, "running", engine="VALUE = 1\n")
        root = project(self.base, str(candidate))
        view = runtime_home.verdict(
            root, candidate, actor="test-agent",
            running_home_path=running, require_identity_match=True,
        )
        self.assertEqual(view["verdict"], runtime_home.REFUSED, view)
        self.assertEqual(self.answers(view)["build_identity"], "FAIL")
        self.assertIn("did not produce the evidence", runtime_home.problem(view))

    def test_an_older_state_schema_is_refused(self) -> None:
        home = install(self.base, "old-schema", schema=2)
        root = project(self.base, str(home), schema=3)
        view = runtime_home.verdict(root, home, actor="test-agent")
        self.assertEqual(view["verdict"], runtime_home.REFUSED, view)
        self.assertEqual(self.answers(view)["schema_compatibility"], "FAIL")
        self.assertIn("older than the state", runtime_home.problem(view))

    def test_a_newer_state_schema_is_not_a_refusal(self) -> None:
        home = install(self.base, "new-schema", schema=4)
        root = project(self.base, str(home), schema=3)
        view = runtime_home.verdict(root, home, actor="test-agent")
        self.assertEqual(self.answers(view)["schema_compatibility"], "PASS", view)

    def test_a_directory_that_cannot_boot_is_refused(self) -> None:
        home = install(self.base, "no-boot")
        (home / "BOOT.md").unlink()
        root = project(self.base, str(home))
        view = runtime_home.verdict(root, home, actor="test-agent")
        self.assertEqual(view["verdict"], runtime_home.REFUSED, view)
        self.assertEqual(self.answers(view)["project_binding"], "FAIL")

    def test_an_unnamed_actor_is_refused(self) -> None:
        home = install(self.base, "home")
        root = project(self.base, str(home))
        view = runtime_home.verdict(root, home, actor="")
        self.assertEqual(view["verdict"], runtime_home.REFUSED, view)
        self.assertEqual(self.answers(view)["actor_binding"], "FAIL")
        self.assertIn("no actor was named", runtime_home.problem(view))

    def test_an_open_journal_operation_is_refused(self) -> None:
        home = install(self.base, "home")
        root = project(self.base, str(home))
        op_dir = root / ".saipen" / "recovery" / "ops" / "op-open"
        _write(op_dir / "operation.json", json.dumps({
            "op_id": "op-open",
            "status": "PREPARED",
            "operation": "rebind_home",
            "agent": "test-agent",
            "project_identity": "",
            "semantic_payload_hash": "0" * 64,
            "created_at": "2026-10-27T00:00:00Z",
        }) + "\n")
        view = runtime_home.verdict(root, home, actor="test-agent")
        self.assertEqual(view["verdict"], runtime_home.REFUSED, view)
        self.assertEqual(self.answers(view)["no_pending_operation"], "FAIL")
        self.assertIn("unresolved journal operation", runtime_home.problem(view))

    def test_the_verdict_is_machine_readable_and_closed(self) -> None:
        home = install(self.base, "home")
        root = project(self.base, str(home))
        view = runtime_home.verdict(root, home, actor="test-agent")
        self.assertEqual(view["schema"], runtime_home.SCHEMA)
        self.assertEqual(view["family"], runtime_home.FAMILY)
        self.assertEqual(
            tuple(item["check"] for item in view["checks"]), runtime_home.CHECKS
        )
        self.assertTrue(all(item["answer"] in ("PASS", "FAIL", "UNPROVEN")
                            for item in view["checks"]))

    def test_a_foreign_shape_is_not_a_verdict(self) -> None:
        for shape in ({}, {"schema": 1}, {"schema": 1, "family": "runtime-home"},
                      {"schema": 1, "family": "runtime-home", "verdict": "REFUSED"},
                      None, []):
            self.assertIsNotNone(runtime_home.problem(shape), shape)


class RebindUsesTheVerdictTests(unittest.TestCase):
    """The verdict is only worth writing if the ONE write path consults it."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="t1854-rebind-")
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)

    def test_a_refused_verdict_writes_no_pointer(self) -> None:
        """A named candidate that clears the LAYOUT check but not the verdict.

        `rebind_saipen_home` is the path an operator drives: it proves the
        candidate's layout, then hands it to the ONE rebind body. A candidate
        whose layout is fine and whose STATE schema is older than this
        project's must therefore be refused by the verdict -- and refuse
        before anything is written.
        """
        from saipen_engine import operations

        home = install(self.base, "no-schema")
        (home / "extensions" / "schemas" / "state.schema.json").write_text(
            json.dumps({"x-current-schema-version": 1}) + "\n", encoding="utf-8"
        )
        root = project(self.base, str(self.base / "dead-pointer"), schema=3)
        before = {
            name: (root / ".saipen" / name).read_bytes()
            for name in ("STATE.md", "BOARD.md", "LOG.md")
        }
        result = operations.rebind_saipen_home(root, "test-agent", str(home))
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, runtime_home.CODE_REFUSED, result.to_dict())
        verdict = result.to_dict().get("runtime_home_verdict") or {}
        self.assertEqual(verdict.get("verdict"), "REFUSED", result.to_dict())
        self.assertEqual(
            before,
            {name: (root / ".saipen" / name).read_bytes() for name in before},
            "a refused verdict must write nothing",
        )

    def test_an_accepted_verdict_still_rebinds(self) -> None:
        """The gate must admit the repair it exists to protect.

        A fixture whose six facts all hold is rebound for real: the pointer
        moves, the answer carries the verdict, and the project's phase and
        ticket are untouched -- a home repair is not a work decision.
        """
        from saipen_engine import operations

        home = install(self.base, "good-home")
        root = project(self.base, str(self.base / "dead-pointer"), schema=3)
        result = operations.rebind_saipen_home(root, "test-agent", str(home))
        self.assertTrue(result.ok, result.to_dict())
        payload = result.to_dict()
        self.assertEqual(payload.get("code"), "HOME_REBOUND", payload)
        self.assertEqual(
            (payload.get("runtime_home_verdict") or {}).get("verdict"),
            "ACCEPTED",
            payload,
        )
        state = (root / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        self.assertIn(f'saipen_home: "{home.resolve().as_posix()}"', state)
        self.assertIn("task: T-1", state)
        self.assertIn("phase: BUILD", state)

    def test_auto_convergence_skips_a_candidate_the_verdict_refuses(self) -> None:
        """A refused candidate is not an abort: the next proven one still wins.

        The environment candidate here is a real, bootable install whose STATE
        schema is older than this project's, so it passes the layout check that
        `rebind_home_auto` already ran and fails only the verdict. Convergence
        must record that refusal and still land on the executing engine -- and
        the record must say which fact the skipped candidate failed.
        """
        import os
        from unittest import mock

        from saipen_engine import operations

        stale = install(self.base, "stale-engine", schema=1)
        root = project(self.base, str(self.base / "dead-pointer"), schema=3)
        with mock.patch.dict(os.environ, {"SAIPEN_SKILL_ROOT": str(stale)}):
            result = operations.rebind_home_auto(root, "test-agent",
                                                 engine_root=REPO)
        self.assertTrue(result.ok, result.to_dict())
        payload = result.to_dict()
        self.assertEqual(payload.get("code"), "HOST_BINDING_CONVERGED", payload)
        skipped = [
            row for row in payload.get("candidates") or []
            if row.get("path") == stale.resolve().as_posix()
        ]
        self.assertTrue(skipped, payload.get("candidates"))
        self.assertFalse(skipped[0].get("ok"), skipped[0])
        self.assertIn("schema_compatibility", str(skipped[0].get("why")), skipped[0])
        self.assertEqual(
            (skipped[0].get("runtime_home_verdict") or {}).get("verdict"),
            "REFUSED",
            skipped[0],
        )
        self.assertEqual(
            (payload.get("runtime_home_verdict") or {}).get("verdict"),
            "ACCEPTED",
            payload,
        )


if __name__ == "__main__":
    unittest.main()

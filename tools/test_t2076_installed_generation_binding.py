"""T-2076: an external closure binds the RECORDED installed generation.

An EX receipt records the engine generation that EXECUTED the sealed
verification, and revalidation is refused unless that executor is the install
the project names (HOME_REQUIRED). The closure predicate used to compare the
receipt with the module tree answering the check, so a read-only validation
from a release candidate reported "the dependency moved" for a checkout that
moved nothing. This suite proves the repaired predicate:

  1 candidate checkout, receipt sealed against installed A  -> current
  2 ACTUAL installed A -> C                                 -> stale, named
  3 missing / incoherent / fingerprinted-out recorded home  -> fail closed
  4 standard run from the recorded install                  -> unchanged
  5 legacy pointer (no absolute home)                       -> unchanged
  6 closure resolver and validator                          -> one verdict

Run standalone:
    python tools/test_t2076_installed_generation_binding.py
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402

from saipen_engine import board as board_mod  # noqa: E402
from saipen_engine import closure as closure_mod  # noqa: E402
from saipen_engine import external as external_mod  # noqa: E402
from saipen_engine import operations as ops_mod  # noqa: E402
from saipen_engine.paths import unbound_environment  # noqa: E402

SAIPEN_PY = TOOLS / "saipen.py"
VALIDATE_PY = TOOLS / "validate.py"
SCENARIO = ROOT / "tests" / "scenarios" / "stale-state-reconciliation" / ".saipen"

AUTH = "lineage-b512942bac884a8691f6c98afcd6ddb9"
IMPL = "T-1411@cc86601f"
RUN_OK = "echo oracle-ok"
VERIFY = "the installed implementation satisfies the original defect contract"

#: A deliberately small but COMPLETE shipped runtime: the manifest declares
#: the surface `runtime_surface` proves, so a fixture home is a coherent
#: generation instead of a directory that merely holds a BOOT.md.
MINI_MANIFEST = {
    "copy_trees": [
        {"src": "saipen/phases", "dst": "phases"},
        {"src": "tools", "dst": "tools"},
    ],
    "files": [
        {"src": "saipen/MANIFEST.json", "required": True},
        {"src": "saipen/BOOT.md", "required": True},
        {"src": "saipen/CORE.md", "required": True},
        {"src": "VERSION", "required": True},
    ],
}

BOARD = (
    "# Board\n"
    "## DOING\n"
    "## TODO\n"
    "## DONE\n"
    "## BLOCKED\n"
    f"- [ ] T-030 [P1] defect implemented upstream | verify: {VERIFY} | "
    "blocker: BLOCKED_EXTERNAL: implemented by upstream T-1411; no local "
    "patch owns it | blocker_scope: ticket\n"
)

LOG = (
    "- 20.09.26 00:00 [E-001] [T-030] RUN: transition to VERIFY\n"
    "- 20.09.26 00:01 [E-002] [T-030] DEC: externally blocked, upstream fix pending\n"
)


def _state(home: Path | str | None) -> str:
    lines = [
        "---",
        "phase: DONE",
        "task: none",
        'next_action: "PHASE DONE"',
        "blocker: none",
        "transition_from: DONE",
        "saipen_version: 8",
        "schema_version: 3",
        "last_event: 2",
        f"style_contract: {CURRENT_STYLE_CONTRACT}",
        "agent: tester",
        "mode: full",
        'updated: "2026-09-20T00:00:00Z"',
    ]
    if home is not None:
        value = Path(home).as_posix() if not str(home).startswith("/") else str(home)
        lines.append(f'saipen_home: "{value}"')
    lines += ["---", ""]
    return "\n".join(lines)


def _home(base: Path, marker: str) -> Path:
    """A coherent source-layout install whose engine bytes differ by marker."""
    base.mkdir(parents=True, exist_ok=True)
    (base / "saipen" / "phases").mkdir(parents=True, exist_ok=True)
    (base / "saipen" / "MANIFEST.json").write_text(
        json.dumps(MINI_MANIFEST, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (base / "saipen" / "BOOT.md").write_text("# BOOT\n", encoding="utf-8", newline="\n")
    (base / "saipen" / "CORE.md").write_text("# CORE\n", encoding="utf-8", newline="\n")
    (base / "saipen" / "phases" / "done.md").write_text("# DONE\n", encoding="utf-8", newline="\n")
    (base / "VERSION").write_text("9.9.9\n", encoding="utf-8", newline="\n")
    engine = base / "tools" / "saipen_engine"
    engine.mkdir(parents=True, exist_ok=True)
    (base / "tools" / "saipen.py").write_text(f"# engine {marker}\n", encoding="utf-8", newline="\n")
    (base / "tools" / "validate.py").write_text(
        f"# validator {marker}\n", encoding="utf-8", newline="\n"
    )
    for name in ("external.py", "board.py", "fleet.py"):
        (engine / name).write_text(f"# {name} {marker}\n", encoding="utf-8", newline="\n")
    (base / "extensions" / "subs").mkdir(parents=True, exist_ok=True)
    (base / "extensions" / "subs" / "PROTOCOL.md").write_text(
        "# PROTOCOL\n", encoding="utf-8", newline="\n"
    )
    return base


def _project(tmp: Path, home: Path | str | None = None) -> Path:
    root = tmp / "project"
    root.mkdir(parents=True)
    shutil.copytree(SCENARIO, root / ".saipen")
    (root / ".saipen" / "BOARD.md").write_text(BOARD, encoding="utf-8")
    (root / ".saipen" / "STATE.md").write_text(_state(home), encoding="utf-8")
    (root / ".saipen" / "LOG.md").write_text(LOG, encoding="utf-8")
    return root


def _point_state(root: Path, home: Path | str | None) -> None:
    (root / ".saipen" / "STATE.md").write_text(_state(home), encoding="utf-8")


def _ticket(root: Path) -> dict:
    parsed = board_mod.parse_board((root / ".saipen" / "BOARD.md").read_text(encoding="utf-8"))
    return parsed["tickets"]["T-030"]


def _seal_receipt(root: Path, identity: dict | None = None) -> None:
    """Resolve T-030 through the canonical operation, optionally as another install."""
    if identity is None:
        result = ops_mod.resolve_external_ticket(
            root,
            "T-030",
            "tester",
            authority=AUTH,
            implementation=IMPL,
            resolution_reason="UPSTREAM_FIX_VERIFIED",
            runs=[RUN_OK],
        )
    else:
        with patch.object(external_mod, "engine_identity", return_value=identity):
            result = ops_mod.resolve_external_ticket(
                root,
                "T-030",
                "tester",
                authority=AUTH,
                implementation=IMPL,
                resolution_reason="UPSTREAM_FIX_VERIFIED",
                runs=[RUN_OK],
            )
    assert result.ok, result.message
    assert result.code == "EXTERNAL_RESOLVED", result.code


def _problems(root: Path) -> list[str]:
    return external_mod.resolution_problems(root, "T-030", _ticket(root))


def _run_validator(root: Path) -> str:
    proc = subprocess.run(
        [
            sys.executable,
            str(VALIDATE_PY),
            "--project-root",
            str(root),
            "--gate",
            "core",
            "--no-receipt",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=unbound_environment(),
        timeout=600,
    )
    return proc.stdout


def _identity_at(tools: Path) -> dict:
    """The documented engine-identity framing, owned by the TEST.

    Fixture identities must be computable against the PRE-FIX subject too:
    a setUp that calls the new production helper would turn the red control
    into "the symbol is absent" instead of "the predicate reported a moved
    dependency for a checkout that moved nothing". This helper hashes what
    `engine_identity()` documents, so it can build a receipt for install A
    without depending on the code under test.
    """
    package = tools / "saipen_engine"
    files = sorted(
        [path for path in package.glob("*.py") if path.is_file()]
        + [path for path in (tools / "saipen.py", tools / "validate.py") if path.is_file()]
    )
    material = "".join(
        f"{path.name}:{hashlib.sha256(path.read_bytes()).hexdigest()}\n" for path in files
    )
    version_file = tools.parent / "VERSION"
    version = version_file.read_text(encoding="utf-8-sig").strip() if version_file.is_file() else ""
    return {
        "kind": "saipen-engine",
        "version": version,
        "engine_digest": "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest(),
        "files": len(files),
    }


class InstalledGenerationBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-t2076-")
        self.base = Path(self.tmp.name)
        self.gen_a = _home(self.base / "install-a", "generation-a")
        self.gen_b = _home(self.base / "install-b", "generation-b")
        self.identity_a = _identity_at(self.gen_a / "tools")
        self.identity_b = _identity_at(self.gen_b / "tools")
        self.assertNotEqual(
            self.identity_a["engine_digest"], self.identity_b["engine_digest"]
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    # -- 1: a candidate checkout validates the generation it RECORDS ----------

    def test_candidate_checkout_accepts_the_verified_installed_generation(self):
        root = _project(self.base)
        _seal_receipt(root, identity=self.identity_a)
        before = [path.read_bytes() for path in external_mod.existing_receipts(root)]

        _point_state(root, self.gen_a)

        self.assertEqual(_problems(root), [])
        after = [path.read_bytes() for path in external_mod.existing_receipts(root)]
        self.assertEqual(after, before, "a read-only check must not rewrite the receipt")

    # -- 2: an actual install move makes the same receipt stale ---------------

    def test_installed_generation_move_turns_the_same_receipt_stale(self):
        root = _project(self.base)
        _seal_receipt(root, identity=self.identity_a)

        _point_state(root, self.gen_b)

        problems = _problems(root)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("installed generation", problems[0])
        self.assertIn("dependency moved", problems[0])
        self.assertIn(self.identity_b["engine_digest"][:23], problems[0])

    # -- 3: a declared home that cannot be authenticated fails closed ---------

    def test_missing_recorded_home_fails_closed(self):
        root = _project(self.base)
        _seal_receipt(root, identity=self.identity_a)

        _point_state(root, self.base / "no-such-home")

        problems = _problems(root)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("cannot be authenticated", problems[0])
        self.assertIn("no-such-home", problems[0])

    def test_incoherent_recorded_home_fails_closed(self):
        root = _project(self.base)
        _seal_receipt(root, identity=self.identity_a)
        hollow = self.base / "hollow-home"
        (hollow / "saipen").mkdir(parents=True)
        (hollow / "saipen" / "BOOT.md").write_text("# BOOT\n", encoding="utf-8")
        (hollow / "extensions" / "subs").mkdir(parents=True)
        (hollow / "extensions" / "subs" / "PROTOCOL.md").write_text(
            "# PROTOCOL\n", encoding="utf-8"
        )

        _point_state(root, hollow)

        problems = _problems(root)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("does not prove a coherent shipped runtime generation", problems[0])

    # -- 4: the standard run from the recorded install is unchanged -----------

    def test_standard_installed_run_is_unchanged(self):
        root = _project(self.base, home=ROOT)
        _seal_receipt(root)

        self.assertEqual(_problems(root), [])

        _point_state(root, self.gen_b)
        problems = _problems(root)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("dependency moved", problems[0])

    # -- 5: a legacy pointer keeps the running-engine comparison --------------

    def test_legacy_pointer_keeps_the_running_engine_comparison(self):
        root = _project(self.base)
        _seal_receipt(root, identity=self.identity_a)

        _point_state(root, "scheduled-source")

        problems = _problems(root)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("running engine", problems[0])
        self.assertIn("dependency moved", problems[0])

    # -- 6: the closure resolver and the validator share the ONE verdict ------

    def test_closure_resolver_and_validator_share_the_verdict(self):
        root = _project(self.base)
        _seal_receipt(root, identity=self.identity_a)

        _point_state(root, self.gen_a)
        verdict = closure_mod.resolve_implementation_source(root, "T-030")
        self.assertTrue(verdict.ok, verdict.detail)
        self.assertNotIn("closure provenance does not resolve", _run_validator(root))

        _point_state(root, self.gen_b)
        verdict = closure_mod.resolve_implementation_source(root, "T-030")
        self.assertFalse(verdict.ok)
        self.assertIn("dependency moved", verdict.detail)
        self.assertIn("closure provenance does not resolve", _run_validator(root))


if __name__ == "__main__":
    unittest.main()

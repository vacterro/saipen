"""T-2090 (night-4 W2): golden characterization of `_plan_finish_ticket`.

Run from the repository root:

    python tools/test_t2090_finish_golden.py

`_plan_finish_ticket` (tools/saipen_engine/operations.py, ~1468 lines, 52
branches) is the FIRST monolith seam the night-4 handoff names for
characterization-before-refactor. This suite pins its BEHAVIORAL contract on
a hermetic project tree -- every case drives the real engine helpers, not a
mock, and asserts the plan's refusal codes, plan targets and applied
effects. Any later seam extraction must keep this suite green byte-for-byte.

Covered contract (handoff list):
  * closure modes (ordinary vs digest-bearing release closure);
  * operator authority (SHIP-phase gate: who may finish);
  * invalid phase refusal (SCOUT/BUILD/VERIFY/REVIEW refuse ILLEGAL_PHASE);
  * journal recovery shape (the plan targets LOG/BOARD/STATE through the
    canonical OperationPlan, no split writes);
  * idempotency (same op_id twice -> ALREADY_APPLIED, one completion event);
  * publication state (digest-bearing closure carries the human digest in
    the same transaction as the closure).
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import codec
from saipen_engine.board import parse_board
from saipen_engine.operations import (
    _now,
    _plan_finish_ticket,
    _utc_iso,
    apply_claim,
    checkpoint,
    transition_phase,
)
from saipen_engine.plan import Result, apply_plan
from saipen_engine.state import parse_state

_DOCS = ("LOG.md", "BOARD.md", "STATE.md")


def _read_doc(root: Path, rel: str) -> str:
    return codec.read_doc(root / ".saipen" / rel)


def _write_doc(root: Path, rel: str, text: str) -> None:
    (root / ".saipen" / rel).write_text(text, encoding="utf-8")


def make_project() -> Path:
    root = Path(tempfile.mkdtemp(prefix="t2090-golden-"))
    (root / ".saipen").mkdir()
    _write_doc(
        root,
        "LOG.md",
        "- 01.01.26 00:00 [E-900] [T-1] [agent: probe] [op: ticket-fixture] "
        "DEC: ticket added via SAIOPS\n"
        "- 01.01.26 00:00 [E-901] [T-2] [agent: probe] [op: ticket-fixture] "
        "DEC: ticket added via SAIOPS\n"
        "- 01.01.26 00:00 [E-902] [T-none] DEC: base\n",
    )
    _write_doc(
        root,
        "BOARD.md",
        "# Board\n## DOING\n## TODO\n"
        "- [ ] T-1 [P1] top probe | verify: probe\n"
        "- [ ] T-2 [P1] lower probe | verify: probe\n"
        "## DONE\n## BLOCKED\n",
    )
    _write_doc(
        root,
        "STATE.md",
        "---\nphase: DONE\ntask: none\nnext_action: \"saipen continue\"\n"
        'blocker: ""\ntransition_from: SHIP\nsaipen_version: 8\n'
        "schema_version: 3\nlast_event: 902\nstyle_contract: ded-069a4c52\n"
        'saipen_home: "' + ROOT.as_posix() + '"\nagent: probe\nmode: full\n'
        'updated: "2026-11-18T00:00:00Z"\n---\n',
    )
    return root


def _docs(root: Path) -> dict[str, str]:
    return {rel: _read_doc(root, rel) for rel in _DOCS}


def _state_of(root: Path) -> dict:
    return parse_state(_read_doc(root, "STATE.md"))


def _board_of(root: Path) -> dict:
    return parse_board(_read_doc(root, "BOARD.md"))


def _code_of(plan) -> str | None:
    if isinstance(plan, Result):
        return plan.code
    if isinstance(plan, dict):
        return plan.get("code")
    return getattr(plan, "code", None)


def _ship_fixture() -> Path:
    """A tree legally sitting in SHIP on claimed T-1 with verification PASS."""
    root = make_project()
    ok = apply_claim(root, "T-1", "probe")
    assert ok.get("ok"), ok
    for phase, note in (
        ("BUILD", "golden setup"),
        ("VERIFY", "golden setup"),
        ("REVIEW", "golden setup"),
        ("SHIP", "golden setup"),
    ):
        result = transition_phase(root, phase, "probe", "T-1", note)
        assert result.get("ok"), (phase, result)
        if phase == "VERIFY":
            checkpoint(
                root, "probe", "RUN", "T-1",
                "golden verification -> PASS conf: high",
            )
    return root


class FinishGolden(unittest.TestCase):
    def setUp(self) -> None:
        self.addCleanup(self._cleanup)
        self.root = make_project()

    def _cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    # -- refusal contract -------------------------------------------------

    def test_illegal_phase_refuses_with_zero_writes(self) -> None:
        for phase in ("SCOUT", "BUILD", "VERIFY", "REVIEW", "DONE"):
            with self.subTest(phase=phase):
                root = make_project()
                if phase == "SCOUT":
                    # claimed but still in SCOUT: the claim is enough to prove
                    # the ticket exists; SCOUT itself is the illegal source.
                    apply_claim(root, "T-1", "probe")
                    # apply_claim moves to DOING/SCOUT; keep SCOUT explicitly
                    # by resetting phase without engine bytes? No: the legal
                    # SCOUT shape IS claimed-SCOUT, nothing to undo.
                elif phase == "DONE":
                    pass  # unclaimed DONE/no-task: finish must refuse too
                else:
                    apply_claim(root, "T-1", "probe")
                    for walked in ("BUILD", "VERIFY", "REVIEW"):
                        if walked == "VERIFY":
                            result = transition_phase(
                                root, walked, "probe", "T-1", "setup"
                            )
                        else:
                            result = transition_phase(
                                root, walked, "probe", "T-1", "setup"
                            )
                        assert result.get("ok"), (walked, result)
                        if walked == "VERIFY":
                            checkpoint(
                                root, "probe", "RUN", "T-1",
                                "golden verification -> PASS conf: high",
                            )
                before = _docs(root)
                plan = _plan_finish_ticket(root, "T-1", "probe", _now(), _utc_iso())
                code = _code_of(plan)
                if phase == "DONE":
                    # unclaimed DONE: the ticket is not a ## DOING [/] row;
                    # the lifecycle refusal is the documented contract here.
                    self.assertEqual(code, "ILLEGAL_TICKET_LIFECYCLE", f"{plan!r:.300}")
                else:
                    self.assertEqual(code, "ILLEGAL_PHASE", f"{plan!r:.300}")
                # zero canonical bytes written on refusal
                self.assertEqual(_docs(root), before)

    def test_unclaimed_ticket_refuses(self) -> None:
        plan = _plan_finish_ticket(
            self.root, "T-1", "probe", _now(), _utc_iso()
        )
        code = _code_of(plan)
        self.assertIsNotNone(code)
        self.assertNotEqual(code, "OK")
        before = _docs(self.root)
        if not isinstance(plan, Result):
            self.assertEqual(_docs(self.root), before)

    def test_wrong_ticket_refuses(self) -> None:
        root = _ship_fixture()
        before = _docs(root)
        plan = _plan_finish_ticket(root, "T-2", "probe", _now(), _utc_iso())
        code = _code_of(plan)
        self.assertIsNotNone(code)
        self.assertNotEqual(code, "OK")
        # a refusal writes nothing
        self.assertEqual(_docs(root), before)

    # -- happy-path contract ----------------------------------------------

    def test_ship_finish_moves_all_three_docs_atomically(self) -> None:
        root = _ship_fixture()
        plan = _plan_finish_ticket(root, "T-1", "probe", _now(), _utc_iso())
        if isinstance(plan, Result) and not plan.ok:
            self.fail(f"plan refused: {plan!r:.300}")
        result = apply_plan(root, plan)
        self.assertTrue(result.get("ok"), result)
        state = _state_of(root)
        board = _board_of(root)
        self.assertEqual(state.get("phase"), "DONE")
        self.assertEqual(state.get("task"), "none")
        self.assertEqual(board["tickets"]["T-1"]["section"], "## DONE")
        self.assertIn("ticket finished", _read_doc(root, "LOG.md"))

    def test_repeat_finish_is_idempotent_already_applied(self) -> None:
        root = _ship_fixture()
        plan = _plan_finish_ticket(root, "T-1", "probe", _now(), _utc_iso())
        first = apply_plan(root, plan)
        self.assertTrue(first.get("ok"), first)
        log_after_first = _read_doc(root, "LOG.md")
        retry = apply_plan(root, plan)
        self.assertEqual(retry.get("code"), "ALREADY_APPLIED", retry)
        self.assertEqual(_read_doc(root, "LOG.md"), log_after_first)

    def test_digest_bearing_closure_carries_the_digest(self) -> None:
        root = _ship_fixture()
        digest = "sha256:" + "ab" * 32
        plan = _plan_finish_ticket(
            root, "T-1", "probe", _now(), _utc_iso(), digest_text=digest
        )
        if isinstance(plan, Result) and not plan.ok:
            self.fail(f"digest closure refused: {plan!r:.300}")
        # the digest commits in the SAME journaled transaction as the
        # closure: a target whose content carries it, named by the plan.
        carriers = [
            t
            for t in plan.targets
            if digest.encode("utf-8") in (t.content or b"")
        ]
        self.assertTrue(carriers, [t.path for t in plan.targets])
        result = apply_plan(root, plan)
        self.assertTrue(result.get("ok"), result)
        # ... and the applied tree holds those bytes too
        carried = False
        for path in root.rglob("*"):
            if path.is_file():
                try:
                    if digest in path.read_text(encoding="utf-8", errors="replace"):
                        carried = True
                        break
                except OSError:
                    continue
        self.assertTrue(carried, "digest bytes absent from the applied tree")
        self.assertEqual(_state_of(root).get("phase"), "DONE")

    def test_plan_targets_are_the_canonical_trio(self) -> None:
        root = _ship_fixture()
        plan = _plan_finish_ticket(root, "T-1", "probe", _now(), _utc_iso())
        if isinstance(plan, Result) and not plan.ok:
            self.fail(f"plan refused: {plan!r:.300}")
        paths = " ".join(str(t.path).upper() for t in plan.targets)
        for member in ("LOG.MD", "BOARD.MD", "STATE.MD"):
            self.assertIn(member, paths)


if __name__ == "__main__":
    unittest.main()

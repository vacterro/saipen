"""T-1618 FUTURE GATE maturation: activation policy, no-spin witness, AUTO-14 perf.

T-1614 proved ELIGIBLE-before-HUNT (matrix A-X, AUTO-01..16). What stayed
unproven is the DEFERRED half of the lifecycle:

- a reviewed DEFERRED gate whose activation conditions become true must mature
  deterministically and route before HUNT (activation policy);
- repeated maturation passes must converge instead of reconsidering forever
  (no-spin witness);
- the AUTO-14 corpus migration must be measured fast, not merely asserted.

The normative owner is `saipen/FUTURE.md` (Rule FUTURE-GATE-01); the enforced
activation policy lives on `future_gate.evaluate` (persisted maturation) plus
`future_gate.select` (live readiness on the routing path). Every assertion here
is a mechanical consequence of those two.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import test_t1614_future_gate as H  # noqa: E402
from saipen_engine import future_gate as gates  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402
from saipen_engine.router import future_gate_projection  # noqa: E402

#: Generous wall-clock bounds for the measured AUTO-14 path. The live corpus
#: migrates in ~0.03s on the reference host; the bound documents the order of
#: magnitude (seconds, never minutes) while staying robust on slow CI.
REFRESH_BUDGET_S = 10.0
STATUS_BUDGET_S = 10.0


def _tickets(project: Path) -> dict:
    text = (project / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
    return parse_board(text)["tickets"]


def _board(project: Path) -> str:
    return (project / ".saipen" / "BOARD.md").read_text(encoding="utf-8")


def _reviewed_deferred(project: Path, *, needs: str) -> tuple[str, str]:
    """One legacy (unmarked) document refined to reviewed DEFERRED.

    Returns (gate_id, needs_ticket_or_token). The reviewed record binds slice,
    evidence and needs to the exact bytes; the document itself stays untouched.
    """
    doc = "# Old design note\n\nWe deferred this follow-up. Status: deferred.\n"
    directory = project / "future_gate"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "old.md").write_text(doc, encoding="utf-8")
    gates.refresh(project)
    gid = gates.status(project)["gates"][0]["id"]
    result = gates.refine(
        project,
        gid,
        slice_text="implement the ONE bounded unit",
        evidence=("evidence.md",),
    )
    assert result["code"] == "FUTURE_GATE_REFINED", result
    record = gates.load_record(project, gid)
    record["facts"]["needs"] = [needs] if needs != "none" else []
    gates.write_record(project, gid, record)
    gates.refresh(project)
    gate = gates.get_gate(project, gid)
    assert gate.state == gates.DEFERRED, gate.state
    assert gate.reviewed is True
    return gid, needs


class DeferredActivationMatrixTests(unittest.TestCase):
    def setUp(self):
        self._tmp = []

    def tearDown(self):
        for base in self._tmp:
            shutil.rmtree(base, ignore_errors=True)

    def _proj(self, **kwargs):
        base, project = H._project(**kwargs)
        self._tmp.append(base)
        return project

    def test_M1_reviewed_deferred_matures_when_its_needs_close(self):
        """M1: needs TODO hides the gate; needs DONE routes it before HUNT."""
        project = self._proj()
        tid = H._add(project, "prerequisite work")
        gid, _ = _reviewed_deferred(project, needs=tid)

        hidden = future_gate_projection(project, _board(project))
        self.assertEqual(hidden.get("eligible"), [], hidden)

        H._done(project, tid)
        # No explicit evaluate on this path: routing readiness is live.
        offered = future_gate_projection(project, _board(project))
        self.assertEqual(offered.get("eligible"), [gid], offered)
        routed = H._route(project)
        self.assertEqual(routed["reason"], "future-gate-promotion", routed)
        self.assertEqual(routed["action"], f"saipen future promote {gid}", routed)

        # evaluate persists the activation; status agrees with routing.
        evaluated = gates.evaluate(project, _tickets(project))
        self.assertEqual(evaluated.get("next"), gid, evaluated)
        self.assertEqual(gates.get_gate(project, gid).state, gates.ELIGIBLE)
        self.assertEqual(gates.status(project, _tickets(project))["next"], gid)

    def test_M2_a_needs_ticket_missing_from_board_is_not_eligible(self):
        """M2: an activation condition nobody owns names its reason."""
        project = self._proj()
        gid, _ = _reviewed_deferred(project, needs="T-999")
        proj = future_gate_projection(project, _board(project))
        self.assertEqual(proj.get("eligible"), [], proj)
        gate = gates.get_gate(project, gid)
        verdict, reasons = gates.readiness(gate, project, _tickets(project))
        self.assertEqual(verdict, gates.INELIGIBLE)
        self.assertTrue(any("T-999" in reason for reason in reasons), reasons)

    def test_M3_missing_evidence_is_not_eligible(self):
        """M3: activation needs a repository path that exists."""
        project = self._proj()
        tid = H._add(project, "prerequisite work")
        gid, _ = _reviewed_deferred(project, needs=tid)
        H._done(project, tid)
        (project / "evidence.md").unlink()
        proj = future_gate_projection(project, _board(project))
        self.assertEqual(proj.get("eligible"), [], proj)
        gate = gates.get_gate(project, gid)
        verdict, reasons = gates.readiness(gate, project, _tickets(project))
        self.assertEqual(verdict, gates.INELIGIBLE)
        self.assertTrue(any("evidence" in reason for reason in reasons), reasons)

    def test_M4_a_gate_without_a_bounded_slice_is_not_eligible(self):
        """M4: activation binds ONE slice; without it the gate waits."""
        project = self._proj()
        doc = "# Old design note\n\nWe deferred this follow-up. Status: deferred.\n"
        H._write_gate(project, "old.md", doc)
        gates.refresh(project)
        gid = gates.status(project)["gates"][0]["id"]
        # Refined with no bound facts: reviewed DEFERRED with no slice.
        result = gates.refine(project, gid)
        self.assertEqual(result["code"], "FUTURE_GATE_REFINED", result)
        gates.refresh(project)
        gate = gates.get_gate(project, gid)
        self.assertEqual(gate.state, gates.DEFERRED)
        self.assertIsNone(gate.slice)
        proj = future_gate_projection(project, _board(project))
        self.assertEqual(proj.get("eligible"), [], proj)
        verdict, reasons = gates.readiness(gate, project, _tickets(project))
        self.assertEqual(verdict, gates.INELIGIBLE)
        self.assertIn("no bounded slice declared", reasons)

    def test_M5_an_unreviewed_legacy_record_is_never_activated_by_guess(self):
        """M5: ambiguity stays NEEDS_REVIEW and is offered for refinement."""
        project = self._proj()
        doc = "# Old design note\n\nWe deferred this follow-up. Status: deferred.\n"
        H._write_gate(project, "old.md", doc)
        gates.refresh(project)
        proj = future_gate_projection(project, _board(project))
        self.assertEqual(proj.get("eligible"), [], proj)
        self.assertEqual(proj.get("refinable"), ["FG-0001"], proj)
        gate = gates.get_gate(project, "FG-0001")
        self.assertEqual(gate.state, gates.NEEDS_REVIEW)

    def test_M6_an_edited_document_invalidates_its_review(self):
        """M6: a review binds exact bytes; an edit returns the gate to review."""
        project = self._proj()
        tid = H._add(project, "prerequisite work")
        gid, _ = _reviewed_deferred(project, needs=tid)
        H._done(project, tid)
        self.assertEqual(
            future_gate_projection(project, _board(project)).get("eligible"), [gid]
        )
        path = project / "future_gate" / "old.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nMore context.\n", encoding="utf-8")
        gates.refresh(project)
        gate = gates.get_gate(project, gid)
        self.assertEqual(gate.state, gates.NEEDS_REVIEW)
        self.assertTrue(any("refine again" in r for r in gate.reasons), gate.reasons)
        self.assertEqual(
            future_gate_projection(project, _board(project)).get("eligible"), []
        )
        # Re-refinement rebinds the new bytes; the old verdict is not inherited.
        result = gates.refine(
            project,
            gid,
            slice_text="implement the ONE bounded unit",
            evidence=("evidence.md",),
        )
        self.assertEqual(result["code"], "FUTURE_GATE_REFINED", result)
        record = gates.load_record(project, gid)
        record["facts"]["needs"] = [tid]
        gates.write_record(project, gid, record)
        gates.refresh(project)
        gate = gates.get_gate(project, gid)
        self.assertEqual(gate.state, gates.DEFERRED)
        self.assertTrue(gate.reviewed)
        self.assertEqual(
            future_gate_projection(project, _board(project)).get("eligible"), [gid]
        )

    def test_M7_activation_persists_and_survives_refresh(self):
        """M7: ELIGIBLE is sticky; refresh never demotes a matured gate."""
        project = self._proj()
        tid = H._add(project, "prerequisite work")
        gid, _ = _reviewed_deferred(project, needs=tid)
        H._done(project, tid)
        gates.evaluate(project, _tickets(project))
        self.assertEqual(gates.get_gate(project, gid).state, gates.ELIGIBLE)
        gates.refresh(project)
        gate = gates.get_gate(project, gid)
        self.assertEqual(gate.state, gates.ELIGIBLE)
        self.assertEqual(gate.reasons, ())
        self.assertEqual(
            future_gate_projection(project, _board(project)).get("eligible"), [gid]
        )

    def test_M8_a_machine_readable_gate_matures_the_same_way(self):
        """M8: control parity -- header-carrying gates share the policy."""
        project = self._proj()
        tid = H._add(project, "prerequisite work", needs=None)
        H._write_gate(project, "gate.md", H._gate_doc("FG-0001", needs=tid))
        gates.refresh(project)
        self.assertEqual(future_gate_projection(project, _board(project)).get("eligible"), [])
        H._done(project, tid)
        self.assertEqual(
            future_gate_projection(project, _board(project)).get("eligible"), ["FG-0001"]
        )


class NoSpinWitnessTests(unittest.TestCase):
    def setUp(self):
        self._tmp = []

    def tearDown(self):
        for base in self._tmp:
            shutil.rmtree(base, ignore_errors=True)

    def _proj(self, **kwargs):
        base, project = H._project(**kwargs)
        self._tmp.append(base)
        return project

    def _pass(self, project: Path, gid: str) -> tuple[str, str, tuple]:
        gates.refresh(project)
        gates.evaluate(project, _tickets(project))
        proj = future_gate_projection(project, _board(project))
        gate = gates.get_gate(project, gid)
        verdict, _ = gates.readiness(gate, project, _tickets(project))
        return (gate.state, verdict, tuple(proj.get("eligible") or ()))

    def test_W1_repeated_maturation_converges_and_writes_nothing_more(self):
        """W1: the witness -- pass 1 activates, later passes are byte-stable."""
        project = self._proj()
        tid = H._add(project, "prerequisite work")
        gid, _ = _reviewed_deferred(project, needs=tid)
        H._done(project, tid)
        trace = [self._pass(project, gid) for _ in range(4)]
        for row in trace:
            self.assertEqual(row, (gates.ELIGIBLE, gates.ELIGIBLE, (gid,)), trace)
        index_path = project / ".saipen" / "future" / "index.json"
        before = index_path.read_bytes()
        gates.evaluate(project, _tickets(project))
        self.assertEqual(index_path.read_bytes(), before)
        # A reviewed record is offered exactly once: no second refinement.
        again = gates.refine(project, gid)
        self.assertEqual(again["code"], "FUTURE_GATE_NOT_AMBIGUOUS", again)

    def test_W2_eligibility_tracks_the_verdict_never_a_stored_state(self):
        """W2: BOARD flip-flops move routing with no state oscillation."""
        project = self._proj()
        tid = H._add(project, "prerequisite work")
        gid, _ = _reviewed_deferred(project, needs=tid)
        seen_states = []
        H._done(project, tid)
        seen_states.append(self._pass(project, gid))
        # Reopen the prerequisite: routing hides the gate, stored state stays.
        board_path = project / ".saipen" / "BOARD.md"
        board_path.write_text(
            f"## DOING\n## TODO\n- [ ] {tid} [P1] prerequisite work | verify: verify it\n"
            "## DONE\n## BLOCKED\n",
            encoding="utf-8",
        )
        seen_states.append(self._pass(project, gid))
        H._done(project, tid)
        seen_states.append(self._pass(project, gid))
        self.assertEqual(
            [row[2] for row in seen_states], [(gid,), (), (gid,)], seen_states
        )
        stored = [row[0] for row in seen_states]
        self.assertNotIn(
            (gates.ELIGIBLE, gates.DEFERRED), list(zip(stored, stored[1:])), stored
        )


class Auto14PerformanceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = []

    def tearDown(self):
        for base in self._tmp:
            shutil.rmtree(base, ignore_errors=True)

    def test_P1_the_live_corpus_migrates_within_a_measured_budget(self):
        """P1: AUTO-14 correctness plus a measured wall-clock budget."""
        base = Path(tempfile.mkdtemp(prefix="saipen-t1618-perf-"))
        self._tmp.append(base)
        project = base / "project"
        (project / ".saipen").mkdir(parents=True)
        source = ROOT / "future_gate"
        originals: dict[str, bytes] = {}
        for path in sorted(source.rglob("*.md")):
            target = project / "future_gate" / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            originals[target.relative_to(project).as_posix()] = target.read_bytes()
        self.assertGreater(len(originals), 1, "the live corpus is the fixture")

        start = time.perf_counter()
        gates.refresh(project)
        refresh_s = time.perf_counter() - start
        start = time.perf_counter()
        indexed = gates.status(project)
        status_s = time.perf_counter() - start

        self.assertLess(
            refresh_s, REFRESH_BUDGET_S, f"refresh took {refresh_s:.3f}s "
            f"over {len(originals)} documents"
        )
        self.assertLess(
            status_s, STATUS_BUDGET_S, f"status took {status_s:.3f}s "
            f"over {len(originals)} documents"
        )
        # AUTO-14 is about the HISTORICAL corpus: a document without the v1
        # marker. A gate recorded through `saipen future add` is already in the
        # machine format and is classified by its own header. Counting every
        # live document as historical made the canonical ingress verb turn this
        # test red the first time it was used (T-1626, FG-0046).
        legacy = [
            relative for relative, blob in originals.items()
            if not blob.decode("utf-8", errors="replace").lstrip().startswith(gates.DOC_MARKER)
        ]
        self.assertGreater(len(legacy), 1, "the historical corpus is the subject")
        self.assertEqual(indexed["counts"][gates.NEEDS_REVIEW], len(legacy))
        paths = {gate["id"]: gate["path"] for gate in indexed["gates"]}
        routed = gates.status(project, {})["next"]
        self.assertNotIn(
            paths.get(routed), legacy,
            f"a historical document was routed without a review: {routed}",
        )
        for relative, blob in originals.items():
            self.assertEqual((project / relative).read_bytes(), blob, relative)

    def test_P2_the_current_index_answers_routing_cheaply_and_stably(self):
        """P2: a CURRENT projection is a cheap stable read, never a rewrite."""
        base = Path(tempfile.mkdtemp(prefix="saipen-t1618-stable-"))
        self._tmp.append(base)
        project = base / "project"
        (project / ".saipen").mkdir(parents=True)
        for path in sorted((ROOT / "future_gate").rglob("*.md")):
            target = project / "future_gate" / path.relative_to(ROOT / "future_gate")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        gates.refresh(project)
        first = future_gate_projection(project, None)
        start = time.perf_counter()
        second = future_gate_projection(project, None)
        elapsed_s = time.perf_counter() - start
        self.assertLess(elapsed_s, STATUS_BUDGET_S, f"routing read took {elapsed_s:.3f}s")
        self.assertEqual(first.get("eligible"), [], first)
        self.assertEqual(second.get("eligible"), [], second)


if __name__ == "__main__":
    unittest.main()

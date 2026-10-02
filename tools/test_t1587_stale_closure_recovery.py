"""T-1587: stale closure metadata on a non-DONE row has a canonical repair.

The downstream shape, reported from FastPrompter (01.10.26): T-1371 sits under
``## TODO`` carrying ``| closure_mode: own_patch``. The placement rule is
correct and stays armed (closure provenance describes a COMPLETED ticket,
T-1302), so every ordinary mutator refuses on the BOARD error -- and before
this class existed, recovery proposed NOTHING for it: the planner read the
board fine, found no drift it owned, and answered RESIDUAL_DEFECTS with no
route. The operator's only exit was a hand edit of protected BOARD bytes,
which is not a recovery contract.

The gap was the repair CLASS, not observability: reconcile's reader already
parses a board with errors; the per-operation ``board["errors"]`` refusals are
what ordinary mutators keep. This file pins the new deterministic class
``stale-closure-metadata`` inside ``_board_lifecycle_repairs`` -- the same
family as ``stale-blocker-metadata`` (T-_SAITULS) and stripping the same
vocabulary the DONE -> DOING reopen strips (T-1572) -- committed only through
the ONE SRC-043 approval route every lifecycle repair already uses.

Regression matrix (handoff section 7):

  A. TODO + closure_mode            -> repairable, full route, claim reachable
  B. DOING + closure_mode           -> repairable, owner/claim_time untouched
  C. BLOCKED + closure_mode         -> repairable, blocker metadata untouched
  D. TODO + closure_mode + cohort   -> both terminal fields removed coherently
  E. TODO + unknown field           -> NOT this class, stays fail-closed
  F. TODO + duplicated closure_mode -> strict refusal, no value silently chosen
  G. DONE + closure_mode            -> legal terminal record, never touched
  H. repair_metadata scoping        -> still DONE-only legacy migration
  I. DONE -> DOING reopen stripping -> vocabulary unchanged, still complete
  J. TODO + closure + independent structural error -> no false CLEAN claim
  K. repaired fixture               -> idempotent; stale replay refused
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_fixture_support import CURRENT_STYLE_CONTRACT
from test_hermetic_env import isolate_host_session
from saipen_engine.board import CLOSURE_METADATA_FIELDS
from saipen_engine.reconcile import (
    _board_lifecycle_repairs,
    _reopen_field_removals,
)

SAIPEN_CLI = Path(__file__).resolve().parent / "saipen.py"
_HOME = Path(__file__).resolve().parent.parent

_A = "a" * 32
_B = "b" * 32
_C = "c" * 32
_D = "d" * 32
_E = "e" * 32
_F = "f" * 32
_G = "g" * 32
_H = "h" * 32
_J = "j" * 32
_K = "k" * 32
_L = "l" * 32


def setUpModule() -> None:
    # An outer host session must never bind this module's disposable
    # fixtures (test_hermetic_env).
    isolate_host_session()


#: The incident journal: T-1370 closed canonically (its DONE row is a legal
#: terminal record), T-1371 was allocated but never started -- it sits under
#: ## TODO, which is exactly why its stale closure_mode is residue, not proof.
_FASTPROMPTER_LOG = (
    "- 30.09.26 08:00 [E-001] [T-1370] [agent: fp-crew] "
    f"[op: add-{_A}] DEC: ticket added via SAIOPS -- the release receipt\n"
    "- 30.09.26 08:01 [E-002] [parent: E-001] [T-1370] [agent: fp-crew] "
    f"[op: claim-{_B}] DEC: claimed via SAIOPS -- owner fp-crew\n"
    "- 30.09.26 08:02 [E-003] [parent: E-002] [T-1370] [agent: fp-crew] "
    f"[op: transition-{_C}] RUN: transition to SCOUT -- the release receipt\n"
    "- 30.09.26 08:03 [E-004] [parent: E-003] [T-1370] [agent: fp-crew] "
    f"[op: transition-{_D}] RUN: transition to BUILD -- the release receipt\n"
    "- 30.09.26 08:04 [E-005] [parent: E-004] [T-1370] [agent: fp-crew] "
    f"[op: transition-{_E}] RUN: transition to VERIFY -- the release receipt\n"
    "- 30.09.26 08:05 [E-006] [parent: E-005] [T-1370] [agent: fp-crew] "
    f"[op: checkpoint-{_F}] RUN: VERIFY -- the receipt gates are green\n"
    "- 30.09.26 08:06 [E-007] [parent: E-006] [T-1370] [agent: fp-crew] "
    f"[op: finish-{_G}] DEC: ticket finished via SAIOPS -- completion (from VERIFY)\n"
    "- 30.09.26 09:00 [E-008] [parent: E-007] [T-1371] [agent: fp-crew] "
    f"[op: add-{_H}] DEC: ticket added via SAIOPS -- the cohort publication\n"
)

_T1370_DONE = (
    "- [x] T-1370 [P1] the release receipt | owner: fp-crew "
    "| claim_time: 2026-09-30T08:01:00Z | closure_mode: own_patch "
    "| verify: the receipt gates are green"
)


def _board_text(*, t1371_line: str, section: str = "## TODO",
                extra_todo: str = "") -> str:
    doing = t1371_line if section == "## DOING" else ""
    todo = t1371_line if section == "## TODO" else ""
    blocked = t1371_line if section == "## BLOCKED" else ""
    return (
        "# Board\n"
        "## DOING\n" + (doing + "\n" if doing else "") +
        "## TODO\n" + (todo + "\n" if todo else "") + extra_todo +
        "## DONE\n" + _T1370_DONE + "\n"
        "## BLOCKED\n" + (blocked + "\n" if blocked else "")
    )


#: The incident row exactly as reported: an open TODO record carrying one
#: terminal closure field.
_INCIDENT_ROW = "- [ ] T-1371 [P1] the cohort publication | closure_mode: own_patch"


def _state_text(last_event: int = 8, *, phase: str = "DONE", task: str = "none",
                transition_from: str = "SHIP",
                next_action: str = "saipen continue") -> str:
    return (
        "---\n"
        f"phase: {phase}\n"
        f"task: {task}\n"
        f'next_action: "{next_action}"\n'
        'blocker: ""\n'
        f"transition_from: {transition_from}\n"
        "saipen_version: 8\n"
        "schema_version: 3\n"
        f"last_event: {last_event}\n"
        "style_contract: " + CURRENT_STYLE_CONTRACT + "\n"
        'saipen_home: "{home}"\n'
        "agent: fp-crew\n"
        "requires:\n  - filesystem\n  - python\n"
        "mode: full\n"
        'updated: "2026-10-01T09:00:00Z"\n'
        "---\n"
    )


def _project(board_text: str, log_text: str = _FASTPROMPTER_LOG,
             last_event: int = 8, *, state_text: str | None = None) -> Path:
    from saipen_engine.journal import ensure_project_lineage

    root = Path(tempfile.mkdtemp(prefix="saipen-t1587-")) / "FASTPROMPTER"
    (root / ".saipen").mkdir(parents=True)
    (root / ".saipen" / "STATE.md").write_text(
        (state_text or _state_text(last_event)).format(
            home=str(_HOME).replace(chr(92), chr(92) * 2)
        ),
        encoding="utf-8",
    )
    (root / ".saipen" / "BOARD.md").write_text(board_text, encoding="utf-8")
    (root / ".saipen" / "LOG.md").write_text(log_text, encoding="utf-8")
    ensure_project_lineage(root)
    subprocess.run(["git", "init"], cwd=str(root), capture_output=True)
    return root


def _cli(root: Path, *args: str) -> dict:
    from saipen_engine.paths import unbound_environment

    run = subprocess.run(
        [sys.executable, str(SAIPEN_CLI), *args, "--json"],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=unbound_environment(),
        timeout=600,
    )
    try:
        return json.loads(run.stdout or "{}")
    except json.JSONDecodeError:
        return {"_raw": (run.stdout + run.stderr)[:400], "rc": run.returncode}


def _parse(board_text: str) -> dict:
    from saipen_engine.board import parse_board

    return parse_board(board_text)


# ---------------------------------------------------------------------------
# Matrix A-G at the planner level: detection is one narrow class
# ---------------------------------------------------------------------------


class DetectionMatrixTests(unittest.TestCase):
    """The class fires on exactly the closure vocabulary, nowhere else."""

    def _atom(self, board_text: str) -> dict | None:
        board = _parse(board_text)
        atoms = [
            r
            for r in _board_lifecycle_repairs(board, [], None, None)
            if r.get("_class") == "stale-closure-metadata"
        ]
        return atoms[0] if atoms else None

    def test_matrix_A_todo_row_is_repairable(self):
        atom = self._atom(_board_text(t1371_line=_INCIDENT_ROW))
        self.assertIsNotNone(atom)
        self.assertEqual(atom["ticket"], "T-1371")
        self.assertEqual(atom["kind"], "claim-clear")
        self.assertEqual(atom["fields"], ["closure_mode"])

    def test_matrix_B_doing_row_keeps_the_claim_pair(self):
        row = ("- [/] T-1371 [P1] the cohort publication | owner: fp-crew "
               "| claim_time: 2026-09-30T11:04:00Z | closure_mode: own_patch")
        atom = self._atom(_board_text(t1371_line=row, section="## DOING"))
        self.assertIsNotNone(atom)
        self.assertEqual(atom["fields"], ["closure_mode"])
        # The claim pair is NOT part of the removal set.
        self.assertNotIn("owner", atom["fields"])
        self.assertNotIn("claim_time", atom["fields"])

    def test_matrix_C_blocked_row_keeps_blocker_metadata(self):
        row = ("- [ ] T-1371 [P1] the cohort publication "
               "| blocker: upstream freeze -- waiting on the publisher "
               "| closure_mode: own_patch")
        atom = self._atom(_board_text(t1371_line=row, section="## BLOCKED"))
        self.assertIsNotNone(atom)
        self.assertEqual(atom["fields"], ["closure_mode"])
        for owned in ("blocker", "blocker_scope", "blocked_on", "retry_not_before"):
            self.assertNotIn(owned, atom["fields"])

    def test_matrix_D_cohort_pair_removed_coherently(self):
        row = ("- [ ] T-1371 [P1] the cohort publication "
               "| closure_mode: cohort | closure_cohort: C-445")
        atom = self._atom(_board_text(t1371_line=row))
        self.assertIsNotNone(atom)
        self.assertEqual(atom["fields"], ["closure_mode", "closure_cohort"])

    def test_matrix_E_unknown_field_is_not_this_class(self):
        row = "- [ ] T-1371 [P1] the cohort publication | legacy_note: hand-written"
        self.assertIsNone(self._atom(_board_text(t1371_line=row)))

    def test_matrix_F_duplicated_field_refuses_rather_than_choosing(self):
        row = ("- [ ] T-1371 [P1] the cohort publication "
               "| closure_mode: own_patch | closure_mode: cohort")
        atom = self._atom(_board_text(t1371_line=row))
        self.assertIsNotNone(atom, "the class is still IDENTIFIED")
        self.assertTrue(atom.get("refuse"), atom)
        self.assertIn("repeats a field", atom["reason"])

    def test_matrix_G_done_row_is_never_touched(self):
        board_text = (
            "# Board\n## DOING\n## TODO\n## DONE\n"
            "- [x] T-1371 [P1] the cohort publication | owner: fp-crew "
            "| claim_time: 2026-09-30T11:04:00Z | closure_mode: own_patch "
            "| verify: cohort gates pass\n"
            "- [x] T-1370 [P1] the release receipt | owner: fp-crew "
            "| claim_time: 2026-09-30T08:01:00Z | closure_mode: own_patch "
            "| verify: the receipt gates are green\n"
            "## BLOCKED\n"
        )
        self.assertIsNone(self._atom(board_text))

    def test_every_closure_field_is_classified_outside_done(self):
        """The class covers the whole board.py vocabulary, not one field."""
        for index, name in enumerate(CLOSURE_METADATA_FIELDS):
            row = f"- [ ] T-1371 [P1] the cohort publication | {name}: x{index}"
            atom = self._atom(_board_text(t1371_line=row))
            self.assertIsNotNone(atom, name)
            self.assertEqual(atom["fields"], [name], name)


# ---------------------------------------------------------------------------
# Matrix H/I: the neighbors this class must not disturb
# ---------------------------------------------------------------------------


class NeighborContractTests(unittest.TestCase):
    def test_matrix_I_reopen_stripping_still_covers_the_vocabulary(self):
        raw = ("- [x] T-1371 [P1] the cohort publication | owner: fp-crew "
               "| claim_time: 2026-09-30T11:04:00Z | closure_mode: own_patch "
               "| closure_cohort: C-445 | verify: cohort gates pass")
        removed = _reopen_field_removals(raw)
        for name in ("closure_mode", "closure_cohort"):
            self.assertIn(name, removed)
        for owned in ("owner", "claim_time", "verify"):
            self.assertNotIn(owned, removed)

    def test_matrix_H_repair_metadata_still_requires_done(self):
        from saipen_engine.operations import repair_metadata

        root = _project(
            _board_text(
                t1371_line="- [/] T-1371 [P1] the cohort publication "
                           "| owner: fp-crew "
                           "| claim_time: 2026-09-30T11:04:00Z "
                           "| closure_mode: own_patch",
                section="## DOING",
            )
        )
        self.addCleanup(lambda: shutil.rmtree(root.parent, ignore_errors=True))
        result = repair_metadata(
            root, "T-1371", "fp-crew", field="source_receipts", to_target="SRC-001"
        )
        refused = result if isinstance(result, dict) else result.to_dict()
        self.assertEqual(refused.get("code"), "METADATA_REPAIR_REQUIRES_DONE", refused)


# ---------------------------------------------------------------------------
# The CLI carrier: the reported incident, end to end
# ---------------------------------------------------------------------------


class IncidentRouteTests(unittest.TestCase):
    """Matrix A/K on the real verbs: refuse, plan, apply, converge, replay."""

    def setUp(self) -> None:
        self.root = _project(_board_text(t1371_line=_INCIDENT_ROW))
        self.addCleanup(lambda: shutil.rmtree(self.root.parent, ignore_errors=True))
        self.board_path = self.root / ".saipen" / "BOARD.md"

    def cli(self, *args: str) -> dict:
        return _cli(self.root, *args)

    def test_ordinary_mutation_still_refuses_before_the_repair(self):
        """Acceptance 2: the malformed BOARD stops claim and continue cold."""
        claim = self.cli("claim", "T-1371")
        self.assertFalse(claim.get("ok"), claim)
        self.assertEqual(claim.get("code"), "VALIDATION_FAILED", claim)
        self.assertIn("closure", claim.get("detail", ""), claim)

    def test_recover_names_the_approved_repair_route(self):
        """Acceptance 3/4/5: detection, plan, one executable canonical route."""
        answer = self.cli("recover")
        self.assertFalse(answer.get("ok"), answer)
        route = answer.get("canonical_next_command")
        self.assertTrue(route, f"recover named no route: {answer}")
        self.assertEqual(
            route.split()[:3], ["saipen", "recover", "--apply-approved-repair"], route
        )
        # The plan names the class and the exact field it will remove.
        payload = json.dumps(answer.get("changed", {})) + json.dumps(
            answer.get("refused", [])
        )
        self.assertIn("stale-closure-metadata", payload, answer)
        self.assertIn("closure_mode", payload, answer)
        # No raw edit instruction is ever the exit.
        self.assertNotIn("edit BOARD", json.dumps(answer))
        # The route is reachable from the other stranded verbs too.
        for verb in ("continue",):
            stranded = self.cli(verb)
            self.assertEqual(
                stranded.get("canonical_next_command", "").split()[:3],
                ["saipen", "recover", "--apply-approved-repair"],
                stranded,
            )

    def test_apply_repairs_exactly_the_stale_field(self):
        route = self.cli("recover")["canonical_next_command"].split()[1:]
        applied = self.cli(*route)
        self.assertTrue(applied.get("ok"), applied)
        self.assertEqual(applied.get("code"), "REPAIRED", applied)

        board = self.board_path.read_text(encoding="utf-8")
        t1371 = [line for line in board.splitlines() if "T-1371" in line]
        self.assertEqual(len(t1371), 1, board)
        # Only the stale terminal field is gone; the record is byte-exact.
        self.assertEqual(t1371[0], "- [ ] T-1371 [P1] the cohort publication", board)
        # T-1370's real completion is untouched, byte for byte.
        self.assertIn(_T1370_DONE, board)
        # The LOG gains exactly one reconcile DEC, nothing else.
        log = (self.root / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"\[E-\d+\]", log)), 9, log)
        self.assertTrue(log.startswith(_FASTPROMPTER_LOG), "historical bytes changed")

    def test_after_the_repair_the_project_converges(self):
        route = self.cli("recover")["canonical_next_command"].split()[1:]
        self.assertTrue(self.cli(*route).get("ok"))
        verdict = self.cli("validate")
        self.assertEqual(verdict.get("structural_gate"), "pass", verdict)
        self.assertEqual(self.cli("recover").get("code"), "CLEAN")
        # Acceptance "claim becomes reachable again": the ordinary mutator no
        # longer refuses on the board -- it may still refuse for its own
        # reasons, but never VALIDATION_FAILED over BOARD bytes.
        claim = self.cli("claim", "T-1371")
        self.assertNotEqual(claim.get("code"), "VALIDATION_FAILED", claim)

    def test_matrix_k_replay_is_refused_and_repair_is_idempotent(self):
        route = self.cli("recover")["canonical_next_command"].split()[1:]
        self.assertTrue(self.cli(*route).get("ok"))
        self.assertEqual(self.cli(*route).get("code"), "STALE_APPROVED_REPAIR")
        # A second bare recover on the repaired board is CLEAN, and a second
        # repair proposes nothing.
        self.assertEqual(self.cli("recover").get("code"), "CLEAN")


# ---------------------------------------------------------------------------
# Matrix B/C/D/J: the same route through the other carriers
# ---------------------------------------------------------------------------


class SectionCarrierTests(unittest.TestCase):
    def _converged(self, board_text: str, *, expected_row: str,
                   log_text: str = _FASTPROMPTER_LOG, last_event: int = 8,
                   state_text: str | None = None) -> None:
        root = _project(board_text, log_text=log_text, last_event=last_event,
                        state_text=state_text)
        self.addCleanup(lambda: shutil.rmtree(root.parent, ignore_errors=True))
        answer = _cli(root, "recover")
        route = answer.get("canonical_next_command")
        self.assertTrue(route, f"recover named no route: {answer}")
        applied = _cli(root, *route.split()[1:])
        self.assertTrue(applied.get("ok"), applied)
        board = (root / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        row = [line for line in board.splitlines() if "T-1371" in line]
        self.assertEqual(len(row), 1, board)
        self.assertEqual(row[0], expected_row, board)
        self.assertIn(_T1370_DONE, board)
        verdict = _cli(root, "validate")
        self.assertEqual(verdict.get("structural_gate"), "pass", verdict)
        self.assertEqual(_cli(root, "recover").get("code"), "CLEAN")

    def test_matrix_b_doing_carrier_keeps_owner_and_claim_time(self):
        # A DOING row requires a ticket-bearing STATE that names it (the
        # binding rule); T-1371 runs its own claim + SCOUT + BUILD pair so the
        # ONLY defect on the surface is the stale closure field.
        doing_log = _FASTPROMPTER_LOG + (
            "- 30.09.26 11:00 [E-009] [parent: E-008] [T-1371] [agent: fp-crew] "
            f"[op: claim-{_J}] DEC: claimed via SAIOPS -- owner fp-crew\n"
            "- 30.09.26 11:01 [E-010] [parent: E-009] [T-1371] [agent: fp-crew] "
            f"[op: transition-{_K}] RUN: transition to SCOUT -- the cohort publication\n"
            "- 30.09.26 11:02 [E-011] [parent: E-010] [T-1371] [agent: fp-crew] "
            f"[op: transition-{_L}] RUN: transition to BUILD -- the cohort publication\n"
        )
        self._converged(
            _board_text(
                t1371_line="- [/] T-1371 [P1] the cohort publication "
                           "| owner: fp-crew "
                           "| claim_time: 2026-09-30T11:00:00Z "
                           "| closure_mode: own_patch",
                section="## DOING",
            ),
            expected_row="- [/] T-1371 [P1] the cohort publication "
                         "| owner: fp-crew "
                         "| claim_time: 2026-09-30T11:00:00Z",
            log_text=doing_log,
            last_event=11,
            state_text=_state_text(
                11, phase="BUILD", task="T-1371", transition_from="SCOUT",
                next_action="PHASE BUILD T-1371",
            ),
        )

    def test_matrix_c_blocked_carrier_keeps_blocker_metadata(self):
        self._converged(
            _board_text(
                t1371_line="- [ ] T-1371 [P1] the cohort publication "
                           "| blocker: upstream freeze -- waiting on the publisher "
                           "| closure_mode: own_patch",
                section="## BLOCKED",
            ),
            expected_row="- [ ] T-1371 [P1] the cohort publication "
                         "| blocker: upstream freeze -- waiting on the publisher",
        )

    def test_matrix_d_cohort_pair_removed_coherently(self):
        self._converged(
            _board_text(
                t1371_line="- [ ] T-1371 [P1] the cohort publication "
                           "| closure_mode: cohort | closure_cohort: C-445"
            ),
            expected_row="- [ ] T-1371 [P1] the cohort publication",
        )

    def test_matrix_e_unknown_field_stays_fail_closed(self):
        root = _project(
            _board_text(
                t1371_line="- [ ] T-1371 [P1] the cohort publication "
                           "| closure_mode: own_patch"
            )
        )
        self.addCleanup(lambda: shutil.rmtree(root.parent, ignore_errors=True))
        # Replace the incident with the unknown-field-only shape.
        board = root / ".saipen" / "BOARD.md"
        board.write_text(
            board.read_text(encoding="utf-8").replace(
                _INCIDENT_ROW,
                "- [ ] T-1371 [P1] the cohort publication | legacy_note: hand-written",
            ),
            encoding="utf-8",
        )
        answer = _cli(root, "recover")
        self.assertFalse(answer.get("ok"), answer)
        self.assertNotIn(
            "stale-closure-metadata",
            json.dumps(answer.get("changed", {})) + json.dumps(answer.get("refused", [])),
            answer,
        )
        self.assertFalse(
            (answer.get("canonical_next_command") or "").startswith(
                "saipen recover --apply-approved-repair"
            )
        )

    def test_matrix_f_duplicated_field_never_receives_a_route(self):
        root = _project(
            _board_text(
                t1371_line="- [ ] T-1371 [P1] the cohort publication "
                           "| closure_mode: own_patch | closure_mode: cohort"
            )
        )
        self.addCleanup(lambda: shutil.rmtree(root.parent, ignore_errors=True))
        before = (root / ".saipen" / "BOARD.md").read_bytes()
        answer = _cli(root, "recover")
        self.assertFalse(answer.get("ok"), answer)
        self.assertIn("repeats a field", answer.get("detail", ""), answer)
        # No route is advertised at all: --attest-legacy-done answers the
        # legacy-done-review refusal, not this one (T-1363: a named command
        # that cannot commit is a dead end, not an exit).
        self.assertFalse(
            (answer.get("canonical_next_command") or "").startswith(
                "saipen recover --attest-legacy-done"
            )
        )
        self.assertFalse(
            (answer.get("canonical_next_command") or "").startswith(
                "saipen recover --apply-approved-repair"
            )
        )
        self.assertEqual(before, (root / ".saipen" / "BOARD.md").read_bytes())

    def test_matrix_g_legal_done_record_is_untouched(self):
        board_text = (
            "# Board\n## DOING\n## TODO\n## DONE\n"
            "- [x] T-1371 [P1] the cohort publication | owner: fp-crew "
            "| claim_time: 2026-09-30T11:04:00Z | closure_mode: own_patch "
            "| verify: cohort gates pass\n"
            + _T1370_DONE + "\n"
            "## BLOCKED\n"
        )
        root = _project(board_text)
        self.addCleanup(lambda: shutil.rmtree(root.parent, ignore_errors=True))
        # The first recover may enroll the audit manifest (its own contract);
        # the BOARD bytes must not move, and the verdict is healthy, not a
        # repair: ok with no board lifecycle change, CLEAN on the steady call.
        answer = _cli(root, "recover")
        self.assertTrue(answer.get("ok"), answer)
        self.assertEqual(answer.get("changed", {}).get("board", []), [], answer)
        second = _cli(root, "recover")
        self.assertEqual(second.get("code"), "CLEAN", second)
        self.assertEqual(
            board_text, (root / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        )

    def test_matrix_j_no_false_clean_over_an_independent_error(self):
        log = _FASTPROMPTER_LOG + (
            "- 30.09.26 09:30 [E-009] [parent: E-008] [T-1372] [agent: fp-crew] "
            f"[op: add-{_J}] DEC: ticket added via SAIOPS -- the stray note\n"
        )
        root = _project(
            _board_text(
                t1371_line=_INCIDENT_ROW,
                extra_todo="- [ ] T-1372 [P2] the stray note | legacy_note: hand-written\n",
            ),
            log_text=log,
            last_event=9,
        )
        self.addCleanup(lambda: shutil.rmtree(root.parent, ignore_errors=True))
        answer = _cli(root, "recover")
        route = answer.get("canonical_next_command")
        self.assertTrue(route, answer)
        applied = _cli(root, *route.split()[1:])
        # The stale-closure repair is allowed to commit ITS OWN atoms...
        self.assertTrue(applied.get("ok"), applied)
        board = (root / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        self.assertIn("- [ ] T-1371 [P1] the cohort publication\n", board)
        self.assertIn("| legacy_note: hand-written", board)
        # ...but the project is NOT claimed clean: the independent structural
        # error remains, named, fail-closed.
        after = _cli(root, "recover")
        self.assertFalse(after.get("ok"), after)
        self.assertEqual(after.get("code"), "RESIDUAL_DEFECTS", after)
        self.assertTrue(
            any("T-1372" in str(d) for d in after.get("residual_defects", [])),
            after,
        )
        verdict = _cli(root, "validate")
        self.assertNotEqual(verdict.get("structural_gate"), "pass", verdict)


class ProducingPathTests(unittest.TestCase):
    """Handoff section 8: no CURRENT canonical writer may create the shape.

    The writers were inventoried at SCOUT: closure fields are written only by
    the close family onto rows entering ## DONE, and the one canonical exit
    from ## DONE (the CURRENT_DONE_JOURNAL_GAP reopen) strips exactly this
    vocabulary through ``_reopen_field_removals``. The demote/unblock movers
    only ever move rows whose sections cannot legally carry closure metadata.
    This pins the vocabulary coupling so a NEW closure field cannot silently
    fall outside the strip set.
    """

    def test_reopen_strip_set_equals_the_closure_vocabulary(self):
        self.assertEqual(
            set(_reopen_field_removals(
                "- [x] T-1 [P1] d | closure_mode: own_patch"
            )),
            {"closure_mode"},
        )
        # The strip is derived from CLOSURE_METADATA_FIELDS, not a parallel
        # tuple: every field board.py owns is stripped on reopen.
        raw = "- [x] T-1 [P1] d"
        raw += "".join(f" | {name}: x" for name in CLOSURE_METADATA_FIELDS)
        self.assertEqual(
            set(_reopen_field_removals(raw)), set(CLOSURE_METADATA_FIELDS)
        )


if __name__ == "__main__":
    unittest.main()

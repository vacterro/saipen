"""T-1609: explicitly reopen unproven current DONE without inventing history.

The reported SAITULS T-240 shape has six hand-written operations and no
canonical claim, transition or finish. Its prior phase is unknown. Approval
may revoke the closure now and queue fresh work; it cannot restore VERIFY.
"""

import re
import shutil
import unittest

import test_t1572_ticket_scoped_recovery as fixtures
from test_hermetic_env import isolate_host_session
from saipen_engine.board import parse_board
from saipen_engine.log import parse_log_line
from saipen_engine.reconcile import _state_phase_repairs


def setUpModule() -> None:
    isolate_host_session()


def _unproven_project():
    root = fixtures._audapack_project()
    memory = root / ".saipen"
    state = (memory / "STATE.md").read_text(encoding="utf-8")
    (memory / "STATE.md").write_text(
        state.replace("T-261", "T-240").replace("last_event: 13", "last_event: 14"),
        encoding="utf-8",
    )
    board = fixtures._GAP_BOARD_TEXT.replace("T-260", "T-239").replace("T-261", "T-240")
    (memory / "BOARD.md").write_text(board, encoding="utf-8")
    operations = iter((
        ("build-module", "BUILD", "implemented module"),
        ("fix-realtime-tick", "FIX", "fixed tick"),
        ("repair-regressions", "REPAIR", "repaired tests"),
        ("verify", "VERIFY", "106 tests PASS -- conf: high"),
        ("smoke-live", "SMOKE", "live smoke passed"),
    ))
    lines = []
    for original_line in fixtures._GAP_LOG.splitlines():
        line = original_line
        if "[T-261]" in line:
            op, taxonomy, text = next(operations)
            line = re.sub(r"\[op: [^]]+\] (?:DEC|RUN):.*$",
                          f"[op: {op}] {taxonomy}: {text}", line)
        lines.append(line.replace("T-260", "T-239").replace("T-261", "T-240"))
    lines.append("- 29.09.26 10:03 [E-014] [parent: E-013] [T-240] "
                 "[agent: auda] [op: deliver] DELIVER: work reported complete")
    (memory / "LOG.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


class UnprovenDoneRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.root = _unproven_project()
        self.addCleanup(lambda: shutil.rmtree(self.root.parent, ignore_errors=True))
        self.cli = fixtures.GapRecoveryRouteTests.cli.__get__(self)

    def bytes(self):
        return {name: (self.root / ".saipen" / name).read_bytes()
                for name in ("STATE.md", "BOARD.md", "LOG.md")}

    def route(self):
        plan = self.cli("recover")
        self.assertEqual(plan.get("code"), "RECONCILE_REAUTH_REQUIRED", plan)
        self.assertTrue(plan.get("operator_decision_available"), plan)
        route = str(plan.get("canonical_next_command") or "").split()
        self.assertEqual(route[:3], ["saipen", "recover", "--apply-approved-repair"], plan)
        self.assertIn("current-done-unproven", str(plan.get("changed")), plan)
        self.assertIn("no lifecycle phase", str(plan.get("detail")), plan)
        return route[1:]

    def test_bare_recovery_and_every_entry_name_the_same_approval_without_writes(self):
        before = self.bytes()
        route = self.route()
        for args in (("recover", "--dry-run"), ("continue",),
                     ("start", "unrelated work")):
            with self.subTest(args=args):
                answer = self.cli(*args)
                self.assertEqual(str(answer.get("canonical_next_command")).split()[1:],
                                 route, answer)
                self.assertEqual(self.bytes(), before)
        # Read-only status routes diagnostics through recover; it does not
        # compute or approve a mutation plan itself.
        self.assertEqual(self.cli("status").get("action"), "saipen recover")
        self.assertEqual(self.bytes(), before)

    def test_approved_reopen_queues_fresh_claim_and_preserves_all_original_bytes(self):
        before = self.bytes()
        route = self.route()
        applied = self.cli(*route, "--agent", "recovery-operator")
        self.assertEqual(applied.get("code"), "REPAIRED", applied)
        after = self.bytes()
        state = after["STATE.md"].decode()
        self.assertIn("phase: DONE", state)
        self.assertIn("transition_from: DONE", state)
        self.assertIn("task: none", state)
        board = parse_board(after["BOARD.md"].decode())
        row = board["tickets"]["T-240"]
        self.assertEqual(row["section"], "## TODO", row)
        self.assertFalse({"owner", "claim_time", "closure_mode"} & set(row["fields"]), row)
        self.assertEqual(board["tickets"]["T-239"]["section"], "## DONE")
        self.assertTrue(after["LOG.md"].startswith(before["LOG.md"]))
        added = after["LOG.md"][len(before["LOG.md"]):].decode()
        self.assertEqual(len(re.findall(r"\[E-\d+\]", added)), 1, added)
        self.assertNotIn("transition to", added)
        self.assertNotIn("[op: finish-", added)
        self.assertIn("current-done-unproven", added)
        kept = {p.name.rsplit(".", 2)[-2]: p.read_bytes()
                for p in (self.root / ".saipen/recovery/terminal-gap").iterdir()}
        self.assertEqual(kept, {name[:-3]: data for name, data in before.items()})
        self.assertEqual(self.cli("validate").get("structural_gate"), "pass")
        self.assertEqual(self.cli("recover").get("code"), "CLEAN")
        self.assertEqual(self.cli(*route).get("code"), "STALE_APPROVED_REPAIR")
        claimed = self.cli("claim", "T-240", "--agent", "fresh-worker")
        self.assertTrue(claimed.get("ok"), claimed)
        self.assertIn("phase: SCOUT", self.bytes()["STATE.md"].decode())
        # The old free-form PASS is not evidence for the new lifecycle.
        refusal = self.cli("ticket", "done", "T-240", "--agent", "fresh-worker")
        self.assertFalse(refusal.get("ok"), refusal)
        self.assertEqual(parse_board(self.bytes()["BOARD.md"].decode())
                         ["tickets"]["T-240"]["section"], "## DOING")

    def test_approval_is_bound_to_each_original_surface(self):
        for name in ("STATE.md", "BOARD.md", "LOG.md"):
            with self.subTest(name=name):
                route = self.route()
                path = self.root / ".saipen" / name
                original = path.read_bytes()
                path.write_bytes(original + b"\nChanged context\n")
                before = self.bytes()
                self.assertEqual(self.cli(*route).get("code"), "STALE_APPROVED_REPAIR")
                self.assertEqual(self.bytes(), before)
                path.write_bytes(original)

    def test_a_different_doing_ticket_blocks_the_reopen(self):
        path = self.root / ".saipen/BOARD.md"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "## DOING\n", "## DOING\n- [/] T-241 [P1] active work | owner: other "
            "| claim_time: 2026-09-29T10:04:00Z\n"), encoding="utf-8")
        before = self.bytes()
        answer = self.cli("recover")
        self.assertEqual(answer.get("terminal_disposition"), "RECOVERY_BLOCKED", answer)
        self.assertIsNone(answer.get("canonical_next_command"), answer)
        self.assertEqual(self.bytes(), before)

    def test_other_unprovable_shapes_stay_blocked(self):
        events = [parse_log_line(line) for line in self.bytes()["LOG.md"].decode().splitlines()]
        board = parse_board(self.bytes()["BOARD.md"].decode())
        base = {"phase": "DONE", "task": "T-240", "transition_from": "VERIFY",
                "last_event": 14}
        for change in ({"phase": "IMPL"}, {"task": "T-242"}):
            with self.subTest(change=change):
                repairs = _state_phase_repairs(base | change, events, board)
                self.assertTrue(repairs[0].get("blocked"), repairs)

    def test_incomplete_claim_and_genuine_finish_are_not_restart_authority(self):
        events = [parse_log_line(line) for line in self.bytes()["LOG.md"].decode().splitlines()]
        state = {"phase": "DONE", "task": "T-240", "transition_from": "VERIFY",
                 "last_event": 15}
        board = parse_board(self.bytes()["BOARD.md"].decode())
        del board["tickets"]["T-240"]["fields"]["claim_time"]
        self.assertTrue(_state_phase_repairs(state, events, board)[0].get("blocked"))
        board = parse_board(self.bytes()["BOARD.md"].decode())
        finish = fixtures._event(15, "finish-" + "a" * 32,
                                 "ticket finished via SAIOPS -- completion (from SHIP)", "T-240")
        repairs = _state_phase_repairs(state, [*events, finish], board)
        self.assertTrue(repairs[0].get("blocked"), repairs)
        self.assertNotIn("current-done-unproven", str(repairs))

    def test_each_transaction_crash_prefix_recovers_without_manual_edits(self):
        for stage in fixtures.GapCrashPrefixTests.STAGES:
            with self.subTest(stage=stage):
                self.root = _unproven_project()
                self.addCleanup(
                    lambda root=self.root: shutil.rmtree(root.parent, ignore_errors=True)
                )
                before = self.bytes()
                route = self.route()
                crashed = self.cli(*route, crash={f"NITRO_CRASH_AFTER_{stage}": "1"})
                self.assertFalse(crashed.get("ok"), crashed)
                answer = {}
                for _ in range(4):
                    answer = self.cli("recover")
                    if answer.get("code") == "CLEAN":
                        break
                    step = str(answer.get("canonical_next_command") or "")
                    self.assertTrue(answer.get("ok") or step, answer)
                    if step:
                        self.cli(*step.split()[1:])
                self.assertEqual(answer.get("code"), "CLEAN", answer)
                after = self.bytes()
                self.assertIn("task: none", after["STATE.md"].decode())
                self.assertEqual(parse_board(after["BOARD.md"].decode())
                                 ["tickets"]["T-240"]["section"], "## TODO")
                self.assertTrue(after["LOG.md"].startswith(before["LOG.md"]))
                self.assertEqual(len(re.findall(r"\[E-\d+\]",
                                              after["LOG.md"][len(before["LOG.md"]):].decode())), 1)
                kept = {p.name.rsplit(".", 2)[-2]: p.read_bytes()
                        for p in (self.root / ".saipen/recovery/terminal-gap").iterdir()}
                self.assertEqual(kept, {name[:-3]: data for name, data in before.items()})


if __name__ == "__main__":
    unittest.main()

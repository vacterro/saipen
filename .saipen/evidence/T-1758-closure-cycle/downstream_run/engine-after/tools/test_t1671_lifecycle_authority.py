"""T-1671 (SRC-192): a lifecycle typed by hand is not a lifecycle.

The incident: an executor that could not find the `saipen` command wrote the
lifecycle of its ticket by hand -- LOG events in the RFC skeleton, a `## DONE`
row with `closure_mode`, a STATE whose `last_event` named its own tail -- and
said so. Every reader accepted the bytes because they parse.

These tests drive the real CLI against a project with a real operation ledger:
two canonical operations run first, then the fixture writes exactly what that
executor wrote. The unit half pins the boundaries of `lifecycle_authority`
that a CLI fixture cannot reach cheaply.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import continuity_probes as probes  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

from saipen_engine import lifecycle_authority  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402
from saipen_engine.journal import OPS_DIR  # noqa: E402

AGENT = "buffy"
CODE = lifecycle_authority.CODE
CLASS = lifecycle_authority.CLASS
CANON = ("STATE.md", "BOARD.md", "LOG.md")


def setUpModule() -> None:
    isolate_host_session()


def _project() -> Path:
    """A git worktree with T-001 canonically claimed and moved to BUILD."""
    root = probes.fresh_project("t1671")
    subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)
    for args in (("continue",), ("claim", "T-001"), ("transition", "BUILD", "T-001", "scout done")):
        answer = probes.cli(root, AGENT, *args)
        assert answer.get("ok"), (args, answer)
    return root


def _state_field(root: Path, field: str, value: str) -> None:
    path = root / ".saipen" / "STATE.md"
    text = path.read_text(encoding="utf-8")
    text, count = re.subn(rf"^{field}: .*$", f"{field}: {value}", text, flags=re.MULTILINE)
    assert count == 1, (field, text)
    path.write_text(text, encoding="utf-8", newline="\n")


def _log_tail(root: Path) -> int:
    text = (root / ".saipen" / "LOG.md").read_text(encoding="utf-8")
    return max(int(match.group(1)) for match in re.finditer(r"\[E-(\d+)\]", text))


def _type_the_lifecycle(root: Path, *, keep_task: bool = False) -> None:
    """What the executor wrote: three LOG events, a DONE row, a DONE state."""
    probes.append_log(root, "T-001", AGENT, "RUN: build -> widget implemented per ADR-7")
    probes.append_log(
        root, "T-001", AGENT,
        "RUN: verify -> PASS [target: T-001] conf: high -- python tools/validate.py -> PASS",
    )
    probes.append_log(
        root, "T-001", AGENT,
        "DEC: T-001 DONE; lifecycle records written by hand against the RFC field shapes",
    )
    board = root / ".saipen" / "BOARD.md"
    text = board.read_text(encoding="utf-8")
    line = next(row for row in text.splitlines() if "T-001" in row)
    text = text.replace(line + "\n", "")
    done = re.sub(r"^- \[.\]", "- [x]", line) + " | closure_mode: own_patch"
    board.write_text(text.replace("## DONE\n", "## DONE\n" + done + "\n"),
                     encoding="utf-8", newline="\n")
    _state_field(root, "phase", "DONE")
    _state_field(root, "transition_from", "SHIP")
    _state_field(root, "next_action", '"saipen continue"')
    _state_field(root, "last_event", str(_log_tail(root)))
    if not keep_task:
        _state_field(root, "task", "none")


def _bytes(root: Path) -> dict:
    return {name: (root / ".saipen" / name).read_bytes() for name in CANON}


def _lifecycle_fails(root: Path) -> list[str]:
    _code, out = probes.validate(root)
    return [line for line in out.splitlines()
            if line.startswith("FAIL") and "lifecycle authority" in line]


class TypedLifecycleTests(unittest.TestCase):
    """The incident, end to end, through the operator's own entry point."""

    def setUp(self):
        self.root = _project()
        self.addCleanup(lambda: shutil.rmtree(self.root, ignore_errors=True))

    def cli(self, *args):
        return probes.cli(self.root, AGENT, *args)

    def test_a_typed_completion_is_refused_by_every_entry_and_writes_nothing(self):
        _type_the_lifecycle(self.root)
        before = _bytes(self.root)
        status = self.cli("status")
        self.assertFalse(status.get("ok"), status)
        self.assertEqual(status.get("code"), CODE, status)
        self.assertEqual(status.get("reason"), CLASS, status)
        self.assertEqual(status.get("action"), "saipen recover", status)
        rules = {f["rule"] for f in status["lifecycle_authority"]["findings"]}
        self.assertEqual(
            rules,
            {lifecycle_authority.STATE_AHEAD, lifecycle_authority.TERMINAL_UNBACKED},
            status,
        )
        for args in (
            ("transition", "SCOUT", "next"),
            ("checkpoint", "RUN", "T-001", "a note after the fact"),
            ("ticket", "add", "P2", "more work", "--verify", "it works"),
            ("ticket", "done", "T-001", "--closure-mode", "own_patch"),
            ("claim", "T-001"),
        ):
            with self.subTest(args=args):
                answer = self.cli(*args)
                self.assertFalse(answer.get("ok"), answer)
                self.assertEqual(answer.get("code"), CODE, answer)
                self.assertIn(CLASS, str(answer.get("message")), answer)
                self.assertNotIn("unregistered_code", answer, answer)
                self.assertEqual(_bytes(self.root), before)
        # Publication has no authority to stand on either.
        for args in (("ship",), ("push",)):
            with self.subTest(args=args):
                self.assertFalse(self.cli(*args).get("ok"))
                self.assertEqual(_bytes(self.root), before)
        fails = _lifecycle_fails(self.root)
        self.assertEqual(len(fails), 1, fails)
        self.assertIn("T-001", fails[0])
        self.assertIn("(T-1671)", fails[0])

    def test_recovery_reopens_the_typed_closure_and_keeps_every_original_byte(self):
        for keep_task in (False, True):
            with self.subTest(keep_task=keep_task):
                root = _project()
                self.addCleanup(lambda root=root: shutil.rmtree(root, ignore_errors=True))
                _type_the_lifecycle(root, keep_task=keep_task)
                before = _bytes(root)
                plan = probes.cli(root, AGENT, "continue")
                self.assertEqual(plan.get("code"), "RECONCILE_REAUTH_REQUIRED", plan)
                self.assertIn(lifecycle_authority.REPAIR_CLASS, str(plan.get("changed")), plan)
                route = str(plan.get("canonical_next_command") or "").split()
                self.assertEqual(
                    route[:3], ["saipen", "recover", "--apply-approved-repair"], plan
                )
                self.assertEqual(_bytes(root), before)
                applied = probes.cli(root, AGENT, *route[1:])
                self.assertEqual(applied.get("code"), "REPAIRED", applied)
                after = _bytes(root)
                row = parse_board(after["BOARD.md"].decode())["tickets"]["T-001"]
                self.assertEqual(row["section"], "## TODO", row)
                self.assertFalse(
                    {"owner", "claim_time", "closure_mode"} & set(row["fields"]), row
                )
                state = after["STATE.md"].decode()
                self.assertIn("phase: DONE", state)
                self.assertIn("task: none", state)
                # Append-only: the typed lines stay, one journaled event follows.
                self.assertTrue(after["LOG.md"].startswith(before["LOG.md"]))
                added = after["LOG.md"][len(before["LOG.md"]):].decode()
                self.assertEqual(len(re.findall(r"\[E-\d+\]", added)), 1, added)
                self.assertIn("[op: reconcile-", added)
                self.assertIn("lifecycle authority", added)
                self.assertNotIn("[op: finish-", added)
                kept = {
                    path.name.rsplit(".", 2)[-2]: path.read_bytes()
                    for path in (root / ".saipen/recovery/terminal-gap").iterdir()
                }
                self.assertEqual(kept, {name[:-3]: data for name, data in before.items()})
                status = probes.cli(root, AGENT, "status")
                self.assertTrue(status.get("ok"), status)
                self.assertEqual(status.get("top_workable_ticket"), "T-001", status)
                self.assertEqual(_lifecycle_fails(root), [])
                # The typed PASS is not evidence for the lifecycle that follows.
                claimed = probes.cli(root, AGENT, "claim", "T-001")
                self.assertTrue(claimed.get("ok"), claimed)
                refused = probes.cli(
                    root, AGENT, "ticket", "done", "T-001", "--closure-mode", "own_patch"
                )
                self.assertFalse(refused.get("ok"), refused)
                self.assertNotIn(CLASS, str(refused), refused)

    def test_a_marker_moved_by_hand_alone_is_reconciled_by_one_journaled_event(self):
        """A typed note plus a hand-bumped `last_event`, nothing closed."""
        probes.append_log(self.root, "T-001", AGENT, "RUN: fix -> PASS -- a typed checkpoint")
        _state_field(self.root, "last_event", str(_log_tail(self.root)))
        before = _bytes(self.root)
        status = self.cli("status")
        self.assertEqual(status.get("reason"), CLASS, status)
        self.assertEqual(
            [f["rule"] for f in status["lifecycle_authority"]["findings"]],
            [lifecycle_authority.STATE_AHEAD],
        )
        self.assertIn(CLASS, str(self.cli("checkpoint", "RUN", "T-001", "on top")))
        answer = self.cli("recover")
        self.assertEqual(answer.get("code"), "REPAIRED", answer)
        after = _bytes(self.root)
        self.assertTrue(after["LOG.md"].startswith(before["LOG.md"]))
        self.assertIn("[op: reconcile-", after["LOG.md"][len(before["LOG.md"]):].decode())
        self.assertEqual(after["BOARD.md"], before["BOARD.md"])
        # The journaled ticket keeps the phase the journal proves for it.
        self.assertIn("phase: BUILD", after["STATE.md"].decode())
        self.assertTrue(self.cli("status").get("ok"))
        self.assertTrue(self.cli("checkpoint", "RUN", "T-001", "canonical again").get("ok"))

    def test_a_typed_note_that_moves_nothing_is_still_only_a_note(self):
        """Negative control: untagged semantic LOG entries stay legal."""
        probes.append_log(self.root, "T-001", AGENT, "RUN: build -> half way through")
        status = self.cli("status")
        self.assertNotIn(CLASS, str(status), status)
        answer = self.cli("checkpoint", "RUN", "T-001", "the next canonical line")
        self.assertNotIn(CLASS, str(answer), answer)
        self.assertEqual(_lifecycle_fails(self.root), [])

    def test_ordinary_project_files_stay_writable(self):
        """Negative control: only lifecycle authority is guarded."""
        source = self.root / "src" / "widget.py"
        source.parent.mkdir()
        source.write_text("VALUE = 1\n", encoding="utf-8")
        (self.root / "README.md").write_text("# widget\n", encoding="utf-8")
        self.assertTrue(self.cli("status").get("ok"))
        self.assertTrue(self.cli("checkpoint", "RUN", "T-001", "build -> widget written").get("ok"))
        source.write_text("VALUE = 2\n", encoding="utf-8")
        self.assertTrue(self.cli("transition", "VERIFY", "T-001", "build complete").get("ok"))
        self.assertEqual(_lifecycle_fails(self.root), [])

    def test_a_checkout_without_a_ledger_is_unavailable_not_accused(self):
        """A fresh clone carries no operation record: nothing to compare with."""
        _type_the_lifecycle(self.root)
        shutil.rmtree(self.root / ".saipen" / "recovery")
        status = self.cli("status")
        self.assertNotIn(CLASS, str(status), status)
        self.assertEqual(_lifecycle_fails(self.root), [])


class NoManualFallbackLawTests(unittest.TestCase):
    """The sentences that licensed the incident are gone from every surface.

    The executor did what OPS told it to: with the engine unavailable, "use the
    documented manual protocol as compatibility fallback" and say so. The
    activation block every host receives told it to "checkpoint BOARD + STATE
    after every ticket, LOG line after every run". A guard that leaves the
    licence standing has the law and the engine disagreeing.
    """

    PROTOCOL = TOOLS.parent / "saipen"

    def read(self, name: str) -> str:
        return " ".join((self.PROTOCOL / name).read_text(encoding="utf-8").split())

    def test_ops_names_no_manual_fallback(self):
        ops = self.read("OPS.md")
        for licence in (
            "manual protocol",
            "FALLBACK / RECOVERY ONLY",
            "mechanical enforcement was unavailable",
        ):
            self.assertNotIn(licence, ops)
        self.assertIn("a structural edit by hand is never a fallback", ops)
        self.assertIn("## 8. Fallback None (SRC-192", ops)
        self.assertIn(CLASS, ops)
        self.assertIn("`SAIPEN_HOST_RUNTIME_UNAVAILABLE`", ops)

    def test_the_activation_block_forbids_the_hand_checkpoint_it_used_to_order(self):
        block = self.read("ACTIVATION_BLOCK.md")
        self.assertNotIn("checkpoint BOARD + STATE after every ticket", block)
        self.assertNotIn("LOG line after every run", block)
        self.assertIn("STATE, BOARD, LOG change only via `saipen`", block)
        self.assertIn("No route to it: stop, report SAIPEN_HOST_RUNTIME_UNAVAILABLE", block)
        self.assertIn("no hand edit, DONE, commit or push", block)
        # The route the block forbids giving up on is still named in it.
        self.assertIn("LAUNCHER: `saipen` not on PATH -> run", block)


def _event(number: int, ticket: str | None, line: str, op_id: str | None = None) -> dict:
    """One event in the shape `log.parse_log_line` returns: taxonomy apart."""
    taxonomy, text = line.split(": ", 1)
    return {"event": number, "ticket": ticket, "text": text, "op_id": op_id,
            "taxonomy": taxonomy}


class AssessBoundaryTests(unittest.TestCase):
    """`lifecycle_authority.assess` over a ledger built for the case."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="t1671-unit-"))
        self.addCleanup(lambda: shutil.rmtree(self.root, ignore_errors=True))

    def ledger(self, *op_ids: str) -> None:
        for op_id in op_ids:
            os.makedirs(self.root / OPS_DIR / op_id)

    @staticmethod
    def board(**sections: str) -> dict:
        return {"tickets": {tid: {"section": section} for tid, section in sections.items()}}

    def assess(self, last_event, board, events):
        return lifecycle_authority.assess(self.root, {"last_event": last_event}, board, events)

    def test_no_ledger_and_no_resolvable_event_are_both_unavailable(self):
        events = [_event(1, "T-1", "RUN: verify -> PASS"), _event(2, "T-1", "DEC: T-1 DONE")]
        board = self.board(**{"T-1": "## DONE"})
        self.assertEqual(self.assess(2, board, events)["status"], lifecycle_authority.UNAVAILABLE)
        self.ledger("claim-" + "a" * 32)
        self.assertEqual(self.assess(2, board, events)["status"], lifecycle_authority.UNAVAILABLE)

    def test_a_canonical_closure_with_a_later_typed_note_is_authorized(self):
        claim, finish = "claim-" + "a" * 32, "finish-" + "b" * 32
        self.ledger(claim, finish)
        events = [
            _event(1, "T-1", "DEC: claimed via SAIOPS -- owner x", claim),
            _event(2, "T-1", "DEC: ticket finished via SAIOPS -- completion (from SHIP)", finish),
            _event(3, "T-1", "DEC: a follow-up note typed afterwards"),
        ]
        verdict = self.assess(2, self.board(**{"T-1": "## DONE"}), events)
        self.assertEqual(verdict["status"], lifecycle_authority.AUTHORIZED, verdict)
        self.assertEqual((verdict["floor"], verdict["head"]), (2, [3]))
        # The same note with the marker moved onto it is the state rule alone.
        moved = self.assess(3, self.board(**{"T-1": "## DONE"}), events)
        self.assertEqual([f["rule"] for f in moved["findings"]], [lifecycle_authority.STATE_AHEAD])

    def test_a_closure_before_a_fresh_claim_does_not_back_a_typed_completion(self):
        first, finish, again = "claim-" + "a" * 32, "finish-" + "b" * 32, "claim-" + "c" * 32
        self.ledger(first, finish, again)
        events = [
            _event(1, "T-1", "DEC: claimed via SAIOPS -- owner x", first),
            _event(2, "T-1", "DEC: ticket finished via SAIOPS -- completion (from SHIP)", finish),
            _event(3, "T-1", "DEC: claimed via SAIOPS -- owner x", again),
            _event(4, "T-1", "RUN: verify -> PASS [target: T-1] conf: high"),
        ]
        verdict = self.assess(3, self.board(**{"T-1": "## DONE"}), events)
        self.assertEqual(
            [f["rule"] for f in verdict["findings"]], [lifecycle_authority.TERMINAL_UNBACKED]
        )

    def test_typed_history_below_the_floor_is_never_judged(self):
        op = "checkpoint-" + "d" * 32
        self.ledger(op)
        events = [
            _event(1, "T-1", "RUN: verify -> PASS"),
            _event(2, "T-1", "DEC: T-1 DONE by hand, long ago"),
            _event(3, None, "RUN: validate.py -> PASS", op),
        ]
        verdict = self.assess(3, self.board(**{"T-1": "## DONE"}), events)
        self.assertEqual(verdict["status"], lifecycle_authority.AUTHORIZED, verdict)

    def test_an_id_in_the_registered_grammar_with_no_record_is_part_of_the_head(self):
        """Measured on a sibling project, 08.10.26: a whole lifecycle typed
        with well-formed `claim-`/`finish-` ids that name no record."""
        real = "transition-" + "a" * 32
        self.ledger(real)
        events = [
            _event(1, "T-1", "RUN: transition to BUILD -- scout done", real),
            _event(2, "T-1", "DEC: claimed via SAIOPS -- owner x", "claim-" + "e" * 32),
            _event(3, "T-1", "DEC: ticket finished via SAIOPS -- completion (from SHIP)",
                   "finish-" + "f" * 32),
        ]
        verdict = self.assess(3, self.board(**{"T-1": "## DONE"}), events)
        self.assertEqual(verdict["head"], [2, 3])
        self.assertEqual(
            {f["rule"] for f in verdict["findings"]},
            {lifecycle_authority.STATE_AHEAD, lifecycle_authority.TERMINAL_UNBACKED},
        )

    def test_a_ticket_named_only_as_a_target_is_still_named(self):
        op = "claim-" + "a" * 32
        self.ledger(op)
        events = [
            _event(1, "T-1", "DEC: claimed via SAIOPS -- owner x", op),
            _event(2, None, "RUN: verify -> PASS [target: T-1] conf: high"),
        ]
        verdict = self.assess(1, self.board(**{"T-1": "## DONE"}), events)
        self.assertEqual(
            [(f["rule"], f["ticket"]) for f in verdict["findings"]],
            [(lifecycle_authority.TERMINAL_UNBACKED, "T-1")],
        )


if __name__ == "__main__":
    unittest.main()

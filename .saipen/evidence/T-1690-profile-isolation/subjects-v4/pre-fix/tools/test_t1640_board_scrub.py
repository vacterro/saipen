"""T-1640: closed BOARD records are scrubbed by the engine, under one rule.

`phases/clean.md` step 1 and the validator's `board-soft-cap` finding both told
an agent to prune `## DONE`. The guard refuses an agent's write to the BOARD
and no engine verb pruned a record, so the finding was printed on every run.
The one scrub that did happen, by hand on 18.09.26, used a one-hop retention
rule and restored five validator FAILs on the way.

`board_scrub.select` is the retention rule and `operations.scrub_board` the
move. Held here: a record a kept record names stays (transitively, through
every edge a validator resolves), a record an ACTIVE receipt names stays, a
record the LOG never closed stays, and everything else leaves the BOARD as
whole physical lines into an evidence file that is exactly those lines.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import board_scrub as BS  # noqa: E402
from saipen_engine import intake  # noqa: E402
from saipen_engine import runtime_namespace as RN  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402
from saipen_engine.fast_check import validate_project  # noqa: E402
from saipen_engine.journal import (  # noqa: E402
    auto_recover_pending,
    op_id_provenance,
    scan_pending,
)
from saipen_engine.log import parse_log_line, read_history_snapshot  # noqa: E402
from saipen_engine.operations import SCRUB_EVIDENCE_ROOT, scrub_board  # noqa: E402
from saipen_engine.state import parse_state  # noqa: E402
from test_guard_hostile_matrix import fresh_project  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

ENGINE = TOOLS / "saipen.py"
AGENT = "test-agent"
#: Long enough that a handful of closed rows crosses the scrub cap.
PROSE = "closed work whose text nothing reads from the BOARD any more " * 9


def setUpModule() -> None:
    isolate_host_session()


def _cli(root: Path, *args: str):
    """One engine call bound to the fixture twice over: root first, cwd too."""
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
    env["PWD"] = str(root)
    proc = subprocess.run(
        [sys.executable, "-B", str(ENGINE), "--project-root", str(root), *args],
        stdin=subprocess.DEVNULL, capture_output=True, env=env, cwd=str(root),
        timeout=300, check=False,
    )
    return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


def _findings(root: Path) -> list[str]:
    """Every WARN and FAIL line the validator's core gate prints for `root`."""
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
    env["PWD"] = str(root)
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(TOOLS / "validate.py"), "--gate", "core"],
        stdin=subprocess.DEVNULL, capture_output=True, env=env, cwd=str(root),
        timeout=600, check=False,
    )
    text = proc.stdout.decode("utf-8", errors="replace")
    return [line for line in text.splitlines() if line.startswith(("WARN", "FAIL"))]


def _live_ops():
    importlib.import_module("saipen_engine.operations")
    return sys.modules["saipen_engine.operations"]


def _done(tid: str, *, extra: str = "", prose: str = PROSE) -> str:
    return f"- [x] {tid} [P2] {prose}| verify: proof | closure_mode: own_patch{extra}"


def _hex(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


def _project(
    done: list[str],
    *,
    todo: tuple[str, ...] = (),
    blocked: tuple[str, ...] = (),
    unclosed: tuple[str, ...] = (),
    phase: str = "CLEAN",
    newline: str = "\n",
) -> Path:
    """A project in `phase` with the given BOARD records and a ledger for them.

    Every record gets its allocation event; every `## DONE` record gets a
    `finish-` closing event too, except the ids in `unclosed`.
    """
    root = fresh_project(
        phase=phase, next_action="PHASE CLEAN" if phase == "CLEAN" else "saipen continue"
    )
    memory = root / ".saipen"
    board = ["## DOING", "## TODO", *todo, "## DONE", *done, "## BLOCKED", *blocked]
    (memory / "BOARD.md").write_bytes((newline.join(board) + newline).encode("utf-8"))
    events = ["# Log"]
    number = 100
    for line in (*todo, *blocked, *done):
        tid = re.search("T-[0-9]+", line).group(0)
        for kind in ("ticket", "finish"):
            if kind == "finish" and (line not in done or tid in unclosed):
                continue
            text = (
                "ticket added via SAIOPS"
                if kind == "ticket"
                else "ticket finished via SAIOPS -- completion (from SHIP)"
            )
            parent = f" [parent: E-{number - 1}]" if number > 100 else ""
            events.append(
                f"- 12.09.26 00:00 [E-{number}]{parent} [{tid}] [agent: {AGENT}] "
                f"[op: {kind}-{_hex(kind + tid)}] DEC: {text}"
            )
            number += 1
    (memory / "LOG.md").write_bytes(("\n".join(events) + "\n").encode("utf-8"))
    state = memory / "STATE.md"
    state.write_text(
        state.read_text(encoding="utf-8").replace("last_event: 100", f"last_event: {number - 1}"),
        encoding="utf-8",
    )
    assert validate_project(root) == [], validate_project(root)
    return root


def _board(root: Path) -> bytes:
    return (root / ".saipen" / "BOARD.md").read_bytes()


def _ids(root: Path, section: str = "## DONE") -> list[str]:
    tickets = parse_board(_board(root).decode("utf-8"))["tickets"]
    return [tid for tid, t in tickets.items() if t["section"] == section]


def _evidence(root: Path) -> list[Path]:
    base = root / SCRUB_EVIDENCE_ROOT
    return sorted(base.glob("*/BOARD.md")) if base.is_dir() else []


def _select(root: Path) -> BS.Selection:
    tickets = parse_board(_board(root).decode("utf-8"))["tickets"]
    active, works = intake.active_receipt_works(root)
    return BS.select(tickets, read_history_snapshot(root).events, active, works)


class RetentionRuleTests(unittest.TestCase):
    def test_a_closed_record_nothing_names_is_prunable(self):
        root = _project([_done(f"T-{n}") for n in range(1, 31)])
        selection = _select(root)
        self.assertEqual(list(selection.pruned), [f"T-{n}" for n in range(1, 31)])
        self.assertEqual(selection.kept, {})
        self.assertTrue(selection.due)

    def test_a_record_a_live_ticket_needs_is_kept(self):
        root = _project(
            [_done(f"T-{n}") for n in range(1, 31)],
            todo=("- [ ] T-40 [P2] open work | verify: proof | needs: T-7",),
        )
        selection = _select(root)
        self.assertEqual(selection.kept, {"T-7": "reference"})
        self.assertNotIn("T-7", selection.pruned)

    def test_the_closure_is_transitive_through_kept_records(self):
        # The one-hop rule of the 18.09.26 scrub: T-7 kept, T-8 pruned, and
        # the kept row then names a record that exists nowhere.
        done = [_done(f"T-{n}") for n in range(1, 31)]
        done[6] = _done("T-7", extra=" | needs: T-8")
        done[7] = _done("T-8", extra=" | needs: T-9")
        root = _project(done, todo=("- [ ] T-40 [P2] open work | verify: proof | needs: T-7",))
        selection = _select(root)
        self.assertEqual(
            selection.kept, {"T-7": "reference", "T-8": "reference", "T-9": "reference"}
        )

    def test_every_edge_a_validator_resolves_is_followed(self):
        done = [_done(f"T-{n}") for n in range(1, 31)]
        root = _project(
            done,
            blocked=(
                "- [ ] T-41 [P2] parked | verify: proof | needs: T-3 "
                "| blocker: ACTIVE -- waits on T-3",
            ),
        )
        self.assertEqual(_select(root).kept, {"T-3": "reference"})
        tickets = parse_board(_board(root).decode("utf-8"))["tickets"]
        for field, named in (
            ("superseded_by", "T-11"),
            ("implementation_source", "T-12"),
            ("blocked_on", "T-13"),
        ):
            with self.subTest(field=field):
                changed = {tid: dict(t, fields=dict(t["fields"])) for tid, t in tickets.items()}
                changed["T-41"]["fields"][field] = named
                kept = BS.select(changed, read_history_snapshot(root).events, set(), set()).kept
                self.assertEqual(kept.get(named), "reference")

    def test_a_source_named_as_implementation_source_keeps_the_work_it_produced(self):
        done = [_done(f"T-{n}") for n in range(1, 31)]
        done[4] = _done("T-5", extra=" | source_receipts: SRC-009")
        root = _project(done)
        tickets = parse_board(_board(root).decode("utf-8"))["tickets"]
        tickets["T-20"]["fields"]["implementation_source"] = "SRC-009"
        events = read_history_snapshot(root).events
        # T-20 itself is prunable, so nothing follows its edge...
        self.assertNotIn("T-5", BS.select(tickets, events, set(), set()).kept)
        # ...until something keeps T-20.
        tickets["T-30"]["needs"] = ["T-20"]
        tickets["T-30"]["section"] = "## TODO"
        kept = BS.select(tickets, events, set(), set()).kept
        self.assertEqual(kept, {"T-20": "reference", "T-5": "reference"})

    def test_a_record_the_log_never_closed_is_kept(self):
        root = _project([_done(f"T-{n}") for n in range(1, 31)], unclosed=("T-4", "T-5"))
        selection = _select(root)
        self.assertEqual(selection.kept, {"T-4": "unproven", "T-5": "unproven"})
        self.assertEqual(selection.kept_by(), {"unproven": 2})

    def test_only_a_closing_operation_is_closing_evidence(self):
        events = [
            {"ticket": "T-1", "op_id": "finish-" + "a" * 32},
            {"ticket": "T-2", "op_id": "checkpoint-" + "a" * 32},
            {"ticket": "T-3", "op_id": None},
            {"ticket": "T-4", "op_id": "supersede-" + "a" * 32},
            {"ticket": "T-9", "op_id": "finish-" + "a" * 32},
        ]
        self.assertEqual(
            BS.closed_in_history(events, ["T-1", "T-2", "T-3", "T-4"]), {"T-1", "T-4"}
        )
        for prefix in BS.CLOSING_OP_CLASSES:
            self.assertEqual(op_id_provenance(prefix + "a" * 32), "canonical", prefix)

    def test_a_small_amount_of_closed_text_is_not_due(self):
        root = _project([_done(f"T-{n}", prose="short ") for n in range(1, 6)])
        selection = _select(root)
        self.assertEqual(len(selection.pruned), 5)
        self.assertFalse(selection.due)


class ReceiptGuardTests(unittest.TestCase):
    """An ACTIVE receipt's Work is that receipt's existence record."""

    def _receipt(self, root: Path, work: str) -> str:
        captured = intake.capture(root, f"a request that produced {work}", work=work)
        self.assertTrue(captured["ok"], captured)
        return captured["receipt"]

    def test_the_work_an_active_receipt_names_is_kept(self):
        root = _project([_done(f"T-{n}") for n in range(1, 31)])
        receipt = self._receipt(root, "T-6")
        active, works = intake.active_receipt_works(root)
        self.assertEqual((active, works), ({receipt}, {"T-6"}))
        self.assertEqual(_select(root).kept, {"T-6": "receipt"})

    def test_member_work_and_clause_work_are_named_too(self):
        root = _project([_done(f"T-{n}") for n in range(1, 31)])
        receipt = self._receipt(root, "T-6")
        linked = intake.link_work_to(root, receipt, "T-7")
        self.assertTrue(linked["ok"], linked)
        # A clause adjudicated to another Work: the shape `source disp --work`
        # leaves in the coverage ledger.
        coverage = root / ".saipen" / "intake" / "coverage" / f"{receipt}.json"
        coverage.parent.mkdir(parents=True, exist_ok=True)
        coverage.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "requirements": {
                        f"{receipt}:R001": {"disposition": "IMPLEMENTED", "work": "T-8"},
                        f"{receipt}:R002": {"disposition": "PENDING"},
                    },
                }
            ),
            encoding="utf-8",
        )
        self.assertEqual(intake.active_receipt_works(root)[1], {"T-6", "T-7", "T-8"})

    def test_a_row_naming_an_active_receipt_is_kept_even_if_the_receipt_forgot_it(self):
        root = _project([_done(f"T-{n}") for n in range(1, 31)])
        tickets = parse_board(_board(root).decode("utf-8"))["tickets"]
        tickets["T-9"]["fields"]["source_receipts"] = "SRC-001, SRC-002"
        events = read_history_snapshot(root).events
        self.assertEqual(BS.select(tickets, events, {"SRC-002"}, set()).kept, {"T-9": "receipt"})
        self.assertEqual(BS.select(tickets, events, {"SRC-003"}, set()).kept, {})

    def test_an_unreadable_receipt_refuses_the_scrub(self):
        root = _project([_done(f"T-{n}") for n in range(1, 31)])
        receipt = self._receipt(root, "T-6")
        (root / ".saipen" / "intake" / "active" / f"{receipt}.meta.json").write_text(
            "{not json", encoding="utf-8"
        )
        before = _board(root)
        result = scrub_board(root, AGENT)
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "VALIDATION_FAILED")
        self.assertIn("cannot be read", result.message)
        self.assertEqual(_board(root), before)
        self.assertEqual(_evidence(root), [])

    def test_a_receipt_that_arrives_under_the_plan_refuses_the_scrub(self):
        root = _project([_done(f"T-{n}") for n in range(1, 31)])
        before = _board(root)
        ops = _live_ops()
        real = ops.apply_plan

        def apply_plan(base, plan):
            # Another writer captures a request for a record this plan prunes.
            self._receipt(Path(base), "T-6")
            return real(base, plan)

        with patch.object(ops, "apply_plan", apply_plan):
            result = ops.scrub_board(root, AGENT)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "STALE_STATE")
        self.assertIn("T-6", _ids(root))
        self.assertEqual(_evidence(root), [])
        del before

    def test_a_clause_bound_under_the_plan_refuses_the_scrub(self):
        # `source disp --work` binds a clause to a Work by writing the coverage
        # ledger and nothing else: BOARD, LOG and STATE do not move, so only
        # the plan's own binding of the receipts it read can see it.
        root = _project([_done(f"T-{n}") for n in range(1, 31)])
        receipt = self._receipt(root, "T-6")
        canonical = [_board(root), (root / ".saipen" / "LOG.md").read_bytes()]
        ops = _live_ops()
        real = ops.apply_plan

        def apply_plan(base, plan):
            coverage = Path(base) / ".saipen" / "intake" / "coverage" / f"{receipt}.json"
            coverage.parent.mkdir(parents=True, exist_ok=True)
            coverage.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "requirements": {
                            f"{receipt}:R001": {"disposition": "IMPLEMENTED", "work": "T-8"}
                        },
                    }
                ),
                encoding="utf-8",
            )
            return real(base, plan)

        with patch.object(ops, "apply_plan", apply_plan):
            result = ops.scrub_board(root, AGENT)
        self.assertFalse(result.ok, result.to_dict())
        self.assertEqual(result.code, "STALE_STATE")
        self.assertIn(".saipen/intake", result.message)
        self.assertEqual(canonical, [_board(root), (root / ".saipen" / "LOG.md").read_bytes()])
        self.assertIn("T-8", _ids(root))
        self.assertEqual(_evidence(root), [])
        # Planned again, the scrub sees the clause and keeps its Work.
        again = scrub_board(root, AGENT)
        self.assertTrue(again.ok, again.to_dict())
        self.assertEqual(_ids(root), ["T-6", "T-8"])


class ScrubTests(unittest.TestCase):
    def test_the_board_loses_exactly_the_pruned_lines(self):
        for newline in ("\n", "\r\n"):
            with self.subTest(newline=repr(newline)):
                done = [_done(f"T-{n}") for n in range(1, 31)]
                root = _project(
                    done,
                    todo=("- [ ] T-40 [P2] open work | verify: proof | needs: T-7",),
                    newline=newline,
                )
                before = _board(root)
                result = scrub_board(root, AGENT)
                self.assertTrue(result.ok, result.to_dict())
                self.assertEqual(result.code, "BOARD_SCRUBBED")

                pruned = [n for n in range(1, 31) if n != 7]
                self.assertEqual(result["pruned"], [f"T-{n}" for n in pruned])
                expected_evidence = b"".join(
                    (_done(f"T-{n}") + newline).encode("utf-8") for n in pruned
                )
                files = _evidence(root)
                self.assertEqual(len(files), 1)
                self.assertEqual(files[0].read_bytes(), expected_evidence)
                self.assertEqual(
                    result["evidence_path"], files[0].relative_to(root).as_posix()
                )
                self.assertEqual(
                    result["evidence_sha256"], hashlib.sha256(expected_evidence).hexdigest()
                )
                remaining = before
                for n in pruned:
                    remaining = remaining.replace((_done(f"T-{n}") + newline).encode("utf-8"), b"")
                self.assertEqual(_board(root), remaining)
                self.assertEqual(result["board_bytes_before"], len(before))
                self.assertEqual(result["board_bytes_after"], len(remaining))
                self.assertEqual(_ids(root), ["T-7"])
                self.assertEqual(_ids(root, "## TODO"), ["T-40"])
                self.assertEqual(validate_project(root), [])

    def test_the_log_names_the_copy_and_its_digest(self):
        root = _project([_done(f"T-{n}") for n in range(1, 31)], unclosed=("T-4",))
        result = scrub_board(root, AGENT)
        self.assertTrue(result.ok, result.to_dict())
        line = (root / ".saipen" / "LOG.md").read_text(encoding="utf-8").splitlines()[-1]
        event = parse_log_line(line)
        self.assertEqual(event["taxonomy"], "DEC")
        self.assertIsNone(event["ticket"])
        self.assertEqual(event["op_id"], result.op_id)
        self.assertEqual(op_id_provenance(event["op_id"]), "canonical")
        for fact in (
            "29 closed record(s)",
            result["evidence_path"],
            result["evidence_sha256"][:16],
            "1 closed record(s) stay (unproven 1)",
        ):
            self.assertIn(fact, event["text"])
        self.assertLessEqual(len(line.encode("utf-8")), 1024)
        self.assertEqual(result["kept_by"], {"unproven": 1})
        state = parse_state((root / ".saipen" / "STATE.md").read_text(encoding="utf-8"))
        self.assertEqual(f"E-{state['last_event']}", result["event_id"])

    def test_a_second_scrub_finds_nothing_due(self):
        root = _project([_done(f"T-{n}") for n in range(1, 31)])
        self.assertTrue(scrub_board(root, AGENT).ok)
        before = _board(root)
        again = scrub_board(root, AGENT)
        self.assertFalse(again.ok)
        self.assertIs(again["due"], False)
        self.assertEqual(again["prunable_records"], 0)
        self.assertEqual(_board(root), before)
        self.assertEqual(len(_evidence(root)), 1)

    def test_a_dry_run_names_the_plan_and_writes_nothing(self):
        root = _project([_done(f"T-{n}") for n in range(1, 31)])
        before = _board(root)
        planned = scrub_board(root, AGENT, dry_run=True)
        self.assertTrue(planned.ok, planned.to_dict())
        self.assertTrue(planned["dry_run"])
        self.assertEqual(planned["pruned_records"], 30)
        self.assertEqual(planned.changed_files[0], planned["evidence_path"])
        self.assertEqual(
            planned.changed_files[1:], [".saipen/LOG.md", ".saipen/BOARD.md", ".saipen/STATE.md"]
        )
        self.assertEqual(_board(root), before)
        self.assertEqual(_evidence(root), [])
        self.assertEqual(scan_pending(root), ([], []))

    def test_this_repository_versions_the_rows_a_scrub_keeps(self):
        # The rows have no other durable home once they leave BOARD.md. This
        # repository ignores `.saipen/recovery/*` and must except the scrub's
        # root, or "moved, never dropped" is true on one machine only.
        repo = TOOLS.parent

        def git(*words: str):
            return subprocess.run(
                ["git", "-C", str(repo), *words],
                stdin=subprocess.DEVNULL, capture_output=True, timeout=60, check=False,
            )

        top = git("rev-parse", "--show-toplevel")
        if top.returncode != 0 or Path(top.stdout.decode().strip()).resolve() != repo.resolve():
            self.skipTest("not this repository's work tree (a disposable copy has no VCS)")
        kept = git("check-ignore", "-q", "--", SCRUB_EVIDENCE_ROOT + "/op/BOARD.md")
        self.assertEqual(kept.returncode, 1, "the scrub evidence root is ignored by git")
        # Control: the rule this excepts is still in force for journal scratch.
        scratch = git("check-ignore", "-q", "--", ".saipen/recovery/ops/op/operation.json")
        self.assertEqual(scratch.returncode, 0)

    def test_the_evidence_root_is_durable_and_byte_bound(self):
        probe = SCRUB_EVIDENCE_ROOT + "/op/BOARD.md"
        self.assertTrue(RN.is_durable_protected(probe))
        self.assertIsNone(RN.runtime_class(probe))
        self.assertIn(SCRUB_EVIDENCE_ROOT + "/**", {p for p, _probe in RN.BYTE_BOUND_PATTERNS})


class RefusalTests(unittest.TestCase):
    def test_a_scrub_outside_clean_is_refused_and_names_the_way_in(self):
        root = _project([_done(f"T-{n}") for n in range(1, 31)], phase="DONE")
        before = _board(root)
        result = scrub_board(root, AGENT)
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "ILLEGAL_PHASE")
        self.assertEqual(result["next_action"], "saipen transition CLEAN")
        self.assertEqual(_board(root), before)

    def test_nothing_is_scrubbed_under_the_cap(self):
        root = _project([_done(f"T-{n}", prose="short ") for n in range(1, 6)])
        before = _board(root)
        result = scrub_board(root, AGENT)
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "VALIDATION_FAILED")
        self.assertIs(result["due"], False)
        self.assertEqual(result["prunable_records"], 5)
        self.assertEqual(_board(root), before)
        self.assertEqual(_evidence(root), [])

    def test_work_in_doing_refuses_a_due_scrub_and_only_a_due_one(self):
        from datetime import datetime, timezone

        claimed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        live = (
            "- [/] T-9001 [P2] live work | verify: x | owner: other-agent "
            f"| claim_time: {claimed}"
        )
        for prose, due in ((PROSE, True), ("short ", False)):
            with self.subTest(due=due):
                root = _project([_done(f"T-{n}", prose=prose) for n in range(1, 31)])
                board = root / ".saipen" / "BOARD.md"
                log = root / ".saipen" / "LOG.md"
                board.write_bytes(
                    _board(root).replace(b"## DOING\n", b"## DOING\n" + live.encode() + b"\n")
                )
                newest = log.read_text(encoding="utf-8").splitlines()[-1]
                tail = int(parse_log_line(newest)["event"])
                with log.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(
                        f"- 12.09.26 00:00 [E-{tail + 1}] [parent: E-{tail}] [T-9001] "
                        f"[agent: other-agent] [op: ticket-{_hex('t9001')}] "
                        "DEC: ticket added via SAIOPS\n"
                    )
                state = root / ".saipen" / "STATE.md"
                state.write_text(
                    state.read_text(encoding="utf-8").replace(
                        f"last_event: {tail}", f"last_event: {tail + 1}"
                    ),
                    encoding="utf-8",
                )
                self.assertEqual(validate_project(root, current_agent=AGENT), [])
                before = _board(root)
                result = scrub_board(root, AGENT)
                self.assertFalse(result.ok)
                if due:
                    self.assertIn("T-9001", result.message)
                    self.assertNotIn("due", result.to_dict())
                else:
                    self.assertIs(result["due"], False)
                self.assertEqual(_board(root), before)

    def test_a_board_that_does_not_parse_is_not_scrubbed(self):
        root = _project([_done(f"T-{n}") for n in range(1, 31)])
        board = root / ".saipen" / "BOARD.md"
        board.write_bytes(_board(root) + b"- [x] not a ticket record at all\n")
        before = _board(root)
        result = scrub_board(root, AGENT)
        self.assertFalse(result.ok)
        self.assertEqual(_board(root), before)
        self.assertEqual(_evidence(root), [])


class InterruptedScrubTests(unittest.TestCase):
    def test_a_scrub_interrupted_at_any_point_converges(self):
        for env_name in (
            "NITRO_CRASH_AFTER_PREPARE",
            "NITRO_CRASH_AFTER_GENERIC",
            "NITRO_CRASH_AFTER_LOG",
            "NITRO_CRASH_AFTER_BOARD",
            "NITRO_CRASH_AFTER_STATE",
            "NITRO_CRASH_AFTER_VERIFIED",
        ):
            with self.subTest(env_name=env_name):
                done = [_done(f"T-{n}") for n in range(1, 31)]
                root = _project(
                    done, todo=("- [ ] T-40 [P2] open work | verify: proof | needs: T-7",)
                )
                with patch.dict(os.environ, {env_name: "1"}, clear=False), self.assertRaises(
                    SystemExit
                ) as raised:
                    scrub_board(root, AGENT)
                self.assertEqual(raised.exception.code, 87)
                self.assertTrue(scan_pending(root)[0], env_name)
                recovered = auto_recover_pending(root)
                self.assertTrue(recovered["ok"], (env_name, recovered))
                if len(_ids(root)) != 1:
                    self.assertTrue(scrub_board(root, AGENT).ok)
                self.assertEqual(_ids(root), ["T-7"])
                self.assertEqual(len(_evidence(root)), 1)
                self.assertEqual(
                    len(_evidence(root)[0].read_bytes().splitlines()), 29, env_name
                )
                self.assertEqual(validate_project(root), [])
                self.assertEqual(scan_pending(root), ([], []))


class CleanRouteTests(unittest.TestCase):
    def cli(self, root: Path, *args: str):
        return _cli(root, *args)

    def test_entering_clean_scrubs_a_board_past_its_cap(self):
        for words in (("transition", "CLEAN"), ("clean",)):
            with self.subTest(words=words):
                root = _project([_done(f"T-{n}") for n in range(1, 31)], phase="DONE")
                code, out, err = self.cli(root, *words, "--json")
                self.assertEqual(code, 0, (out, err))
                answer = json.loads(out)
                scrub = answer["board_scrub"]
                self.assertTrue(scrub["ok"], scrub)
                self.assertEqual(scrub["pruned_records"], 30)
                self.assertEqual(_ids(root), [])
                self.assertEqual(len(_evidence(root)), 1)
                self.assertNotIn("log_seal", answer)

    def test_the_scrub_runs_before_the_seal_and_both_report(self):
        # The order phases/clean.md gives: the scrub's own DEC is then part of
        # what the seal moves, and the fresh tail holds the seal alone.
        done = [_done(f"T-{n}") for n in range(1, 201)]
        root = _project(done, phase="DONE")
        code, out, err = self.cli(root, "transition", "CLEAN", "--json")
        self.assertEqual(code, 0, (out, err))
        answer = json.loads(out)
        self.assertTrue(answer["board_scrub"]["ok"], answer["board_scrub"])
        self.assertTrue(answer["log_seal"]["ok"], answer["log_seal"])
        segment = (root / answer["log_seal"]["segment"]).read_text(encoding="utf-8")
        self.assertIn("DEC: board scrubbed -- 200 closed record(s)", segment.splitlines()[-1])
        tail = (root / ".saipen" / "LOG.md").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(tail), 2)
        self.assertIn("DEC: log sealed --", tail[1])
        self.assertEqual(validate_project(root), [])

    def test_entering_clean_says_nothing_about_a_board_under_its_cap(self):
        root = _project([_done(f"T-{n}", prose="short ") for n in range(1, 6)], phase="DONE")
        code, out, err = self.cli(root, "transition", "CLEAN", "--json")
        self.assertEqual(code, 0, (out, err))
        self.assertNotIn("board_scrub", json.loads(out))
        self.assertEqual(len(_ids(root)), 5)


class ValidatorFindingTests(unittest.TestCase):
    """The finding measures what a scrub can clear, and the scrub clears it."""

    def test_the_finding_names_the_route_and_the_route_clears_it(self):
        root = _project([_done(f"T-{n}") for n in range(1, 31)], phase="DONE")
        found = [line for line in _findings(root) if "[board-soft-cap]" in line]
        self.assertEqual(len(found), 1, found)
        self.assertIn("30 closed record(s) nothing pins (soft cap 16 KB of such text)", found[0])
        self.assertIn(
            "`saipen transition CLEAN` scrubs them into .saipen/recovery/board-scrub/", found[0]
        )

        code, out, err = _cli(root, "transition", "CLEAN", "--json")
        self.assertEqual(code, 0, (out, err))
        self.assertTrue(json.loads(out)["board_scrub"]["ok"])
        after = _findings(root)
        self.assertEqual([line for line in after if "soft-cap" in line], [])
        self.assertEqual([line for line in after if line.startswith("FAIL")], [])

    def test_closed_text_a_scrub_cannot_clear_is_not_reported(self):
        # The old finding measured the whole file, so a BOARD like this one
        # warned on every run and no route could ever clear it.
        done = [_done(f"T-{n}") for n in range(1, 31)]
        root = _project(done, unclosed=tuple(f"T-{n}" for n in range(1, 31)), phase="DONE")
        self.assertGreater(len(_board(root)), 16 * 1024)
        self.assertEqual([line for line in _findings(root) if "soft-cap" in line], [])


if __name__ == "__main__":
    unittest.main()

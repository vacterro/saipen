"""T-149: `sub dispose` must be able to reach the package it retires.

The selection in `sub_disposition` used to require a READY package whose
`source_head` and `source_tree_fingerprint` still equalled the CURRENT ones.
`sub_collect` writes its receipt into the very tree the package recorded, so
every collected package was stale by construction and every dispose stopped at
`PACKAGE_INCOMPLETE` with "no current READY package to dispose" -- naming a
corrupt package when the package was in fact the only one that could be
retired.

The test asserts where dispose STOPS, not that it succeeds: reaching the
receipt check is the observable difference, and a full collect-to-dispose round
trip needs a real Core review ticket, which is integration territory.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(TOOLS))

from saipen_engine import state as S  # noqa: E402
from saipen_engine import subs  # noqa: E402
from saipen_engine import journal, focused_unit  # noqa: E402
from saipen_engine.plan import semantic_payload_hash  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()

SCENARIO = TOOLS.parent / "tests/scenarios/saiui-adoption/.saipen"
ROLE = "saiui"
#: The role revision the packaged fixture's UI-001 records.
FIXTURE_ROLE_REVISION = "sha256:f2e3685b908a3b9837917f12c5414628d847c35fb72567f0306e2c8b19a8dab8"
#: A recorded head that is well-formed but no longer the current one.
AGED_HEAD = "b" * 40
#: Its paired tree fingerprint, likewise well-formed and no longer current.
AGED_FINGERPRINT = "git-delta-v1:" + "c" * 64


class DisposeReachesCollectedPackageTests(unittest.TestCase):
    def _project(self) -> Path:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        shutil.copytree(SCENARIO, root / ".saipen", dirs_exist_ok=True)
        # The shipped scenario predates the voice-contract marker, and STATE
        # validation refuses a checkpoint written against a STYLE.md the agent
        # never read -- so bind the scratch project to the installed one.
        installed = (
            TOOLS.parent / "saipen/STYLE.md"
        ).read_text(encoding="utf-8").split("style_contract: ", 1)[1].split()[0].strip("`")
        state_path = root / ".saipen/STATE.md"
        state_path.write_text(
            S.patch_state(
                state_path.read_text(encoding="utf-8"),
                {"saipen_home": str(TOOLS.parent.resolve()), "style_contract": installed},
            ),
            encoding="utf-8",
            newline="\n",
        )
        return root

    @staticmethod
    def _age_the_source_head(root: Path) -> None:
        """Reproduce what collect does to the tree the package recorded.

        The shipped fixture says `no-git`, which a non-git scratch root also
        computes -- so it would be current, and the selection defect would be
        invisible. Aging the recorded head to what a collect leaves behind is
        the state dispose is actually invoked in.

        The same pass repairs two fields the shipped scenario predates: the
        recorded head has to be a real 40-hex id to parse, and `verified` is
        now a closed verdict grammar rather than free prose.
        """
        outbox = root / subs.SUBS_REL / ROLE / "kitchen" / "OUTBOX.md"
        text = outbox.read_text(encoding="utf-8")
        text = text.replace("- **source_head:** no-git", f"- **source_head:** {AGED_HEAD}")
        text = re.sub(
            r"- \*\*source_tree_fingerprint:\*\* .*",
            f"- **source_tree_fingerprint:** {AGED_FINGERPRINT}",
            text,
        )
        text = re.sub(
            r"- \*\*verified:\*\* .*",
            "- **verified:** PASS -- pytest (12 passed); ruff clean",
            text,
        )
        outbox.write_text(text, encoding="utf-8", newline="\n")

    def test_dispose_reaches_the_collected_package(self):
        root = self._project()
        self._age_the_source_head(root)
        with mock.patch.object(
            subs, "current_local_role_revision", return_value=FIXTURE_ROLE_REVISION
        ):
            result = subs.sub_disposition(root, ROLE)

        self.assertNotEqual(
            result.code,
            "PACKAGE_INCOMPLETE",
            f"dispose stopped at package selection instead of reaching the receipt "
            f"check: {result.code}: {result.message}",
        )
        # Where it must stop: the collect receipt, not the package filter.
        self.assertIn("no durable collect receipt", str(result.message))


class CoreReviewProofTests(unittest.TestCase):
    """Same oracle before/after: terminality never substitutes for Core work."""

    def setUp(self):
        self.root = DisposeReachesCollectedPackageTests._project(self)
        DisposeReachesCollectedPackageTests._age_the_source_head(self.root)
        self.outbox = self.root / subs.SUBS_REL / ROLE / "kitchen" / "OUTBOX.md"
        self.package = subs.parse_outbox(self.outbox.read_text(encoding="utf-8"), ROLE).packages[0]
        self.identity = subs.package_identity(self.package)
        (self.root / "tools").mkdir()
        (self.root / "tools/test_review.py").write_text(
            "import unittest\nclass Review(unittest.TestCase):\n"
            "    def test_reproduce(self): self.assertEqual(2 + 2, 4)\n",
            encoding="utf-8",
        )
        self.executed_record = None
        self.ticket = "T-7"
        self.collect_op = "sub-collect-00000001"
        self.records = [{
            "op_id": self.collect_op, "operation": "sub_collect", "status": "COMMITTED",
            "agent": "core-reviewer", "targets": [
                {"path": rel, "applied": True} for rel in
                (".saipen/LOG.md", ".saipen/BOARD.md", ".saipen/STATE.md")],
            "receipt_metadata": {"package_identities": [self.identity], "tickets": [self.ticket]},
        }]
        self.log_path = self.root / ".saipen/LOG.md"
        self.log_path.write_text(
            f"- 12.09.26 00:01 [E-1] [{self.ticket}] [agent: core-reviewer] "
            f"[op: {self.collect_op}] RUN: collect {ROLE}/{self.package.package_id} -> {self.ticket}; "
            + "; ".join(f"{key}={value}" for key, value in self._bindings().items()
                        if key != "collect_op") + "; queued as Core review hypothesis\n",
            encoding="utf-8",
        )
        self._section("BLOCKED")
        patch = mock.patch.object(subs, "_iter_operation_records", side_effect=lambda _root, records=None: iter(self.records if records is None else records))
        patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.object(subs, "current_local_role_revision", return_value=FIXTURE_ROLE_REVISION)
        patch.start()
        self.addCleanup(patch.stop)

    def _section(self, section):
        lines = []
        for name in ("DOING", "TODO", "DONE", "BLOCKED"):
            lines.append("## " + name)
            if name == section:
                checkbox = "x" if name == "DONE" else "/" if name == "DOING" else " "
                fields = " | closure_mode: finding_invalidated | implementation_delta: none | invalidation_evidence: E-3" if name == "DONE" else ""
                lines.append(f"- [{checkbox}] {self.ticket} [P2] Core review | verify: independently reject hypothesis{fields}")
        (self.root / ".saipen/BOARD.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _bindings(self):
        return {"package_identity": self.identity, "producer": ROLE,
                "package": self.package.package_id, "source_head": AGED_HEAD,
                "source_tree_fingerprint": AGED_FINGERPRINT,
                "role_revision": FIXTURE_ROLE_REVISION, "collect_op": self.collect_op}

    def _checkpoint(self, ticket, event, text):
        op_id = f"checkpoint-{event:08x}"
        self.records.append({
            "op_id": op_id, "operation": "checkpoint", "status": "COMMITTED",
            "agent": "core-reviewer", "semantic_payload_hash": semantic_payload_hash({
                "operation": "checkpoint", "taxonomy": "RUN", "ticket": ticket,
                "description": text}),
            "targets": [{"path": rel, "applied": True} for rel in
                        (".saipen/LOG.md", ".saipen/STATE.md")],
        })
        self.log_path.write_text(
            self.log_path.read_text(encoding="utf-8")
            + f"- 12.09.26 00:02 [E-{event}] [{ticket}] [agent: core-reviewer] "
            + f"[op: {op_id}] RUN: {text}\n", encoding="utf-8",
        )

    def _review(self, *, verdict="PASS", ticket=None, overrides=None, executed=True,
                event=None, record=None):
        ticket = ticket or self.ticket
        event = event or max(map(int, re.findall(r"\[E-(\d+)\]", self.log_path.read_text(encoding="utf-8")))) + 3
        rel = f"{focused_unit.RECORD_DIR_REL}/independent-run-{event}.json"
        if self.executed_record is None:
            self.executed_record = focused_unit.run_focused(self.root, ["test_review.py"], timeout=30)
            self.assertEqual(self.executed_record["verdict"], "PASS", self.executed_record)
        record = record or json.loads(json.dumps(self.executed_record))
        if not executed:
            record = {"evidence_class": "attested", "verdict": "PASS", "ran": 1}
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = (json.dumps(record) + "\n").encode("utf-8")
        path.write_bytes(raw)
        bindings = self._bindings()
        bindings.update(overrides or {})
        own_events = self.log_path.read_text(encoding="utf-8")
        if f"[{ticket}]" not in own_events or "transition to VERIFY" not in own_events:
            self._checkpoint(ticket, event - 2, "transition to VERIFY")
        citation = (f"{focused_unit.MARKER} PASS conf: high ran:1 "
                    f"record:{rel} sha256:{hashlib.sha256(raw).hexdigest()}")
        self._checkpoint(ticket, event - 1, citation)
        text = (f"review -> {verdict} conf: high -- independently reproduce or reject; "
                + "; ".join(f"{key}={value}" for key, value in bindings.items())
                + f"; record:{rel} sha256:{hashlib.sha256(raw).hexdigest()}")
        self._checkpoint(ticket, event, text)
        return path

    def _metadata(self, event="E-4"):
        return {**self._bindings(), "ticket_id": self.ticket, "review_event": event}

    def _postcondition(self, metadata=None):
        targets = [{"path": rel} for rel in (
            ".saipen/LOG.md", ".saipen/STATE.md", self.outbox.relative_to(self.root).as_posix())]
        with mock.patch("saipen_engine.fast_check.validate_project", return_value=[]):
            return journal.verify_sub_disposition(self.root, targets, metadata or self._metadata())

    def _health(self, status="ready"):
        text = self.outbox.read_text(encoding="utf-8").replace("- **status:** ready", f"- **status:** {status}")
        return subs._collect_review_state(
            self.root, ROLE, subs.parse_outbox(text, ROLE),
            SimpleNamespace(source_head=AGED_HEAD, source_tree_fingerprint=AGED_FINGERPRINT),
            str(TOOLS.parent), records=tuple(self.records),
        )

    def _dispose(self):
        with mock.patch("saipen_engine.fast_check.validate_texts", return_value=[]):
            return subs.sub_disposition(self.root, ROLE, self.package.package_id, dry_run=True)

    def test_board_prose_cannot_witness_collection(self):
        prose = (f"producer={ROLE}; package={self.package.package_id}; "
                 f"source_head={AGED_HEAD}; source_tree_fingerprint={AGED_FINGERPRINT}")
        self.assertFalse(subs._durable_collect_witness(
            self.root, self.identity, self.identity, records=(),
            package=self.package, board_text="## TODO\nA note says " + prose,
        ))
        self.assertTrue(subs._durable_collect_witness(
            self.root, self.identity, self.identity, records=tuple(self.records),
            package=self.package,
        ))

    def test_blocked_only_never_schedules_disposition(self):
        self.assertFalse(self._health()["disposition_pending"])

    def test_blocked_only_reviewed_claim_is_invalid(self):
        self.assertTrue(self._health("reviewed")["reviewed_without_disposition"])

    def test_blocked_only_dispose_refuses_without_writes(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        result = self._dispose()
        self.assertFalse(result.ok, result.to_dict())
        self.assertIn("independent Core review", result.message)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_genuinely_reviewed_blocked_remains_disposable(self):
        self._review()
        self.assertTrue(self._health()["disposition_pending"])
        self.assertTrue(self._dispose().ok)

    def test_finding_invalidated_no_patch_remains_disposable(self):
        self._review()
        self._section("DONE")
        self.assertTrue(self._dispose().ok)

    def test_proof_is_ticket_and_full_generation_bound(self):
        self._review(ticket="T-2040")
        self.assertFalse(self._dispose().ok)
        for key, value in (("package_identity", "sha256:" + "9" * 64),
                           ("producer", "saihunt"), ("package", "UI-999"),
                           ("role_revision", "sha256:" + "8" * 64),
                           ("source_tree_fingerprint", "git-delta-v1:" + "7" * 64),
                           ("source_head", "d" * 40), ("collect_op", "sub-collect-other")):
            with self.subTest(field=key):
                self._review(overrides={key: value})
                self.assertFalse(self._dispose().ok)

    def test_uncommitted_attested_and_tampered_proof_refuse(self):
        path = self._review()
        self.records[-1]["status"] = "CONFLICT"
        self.assertFalse(self._dispose().ok)
        self.records[-1]["status"] = "COMMITTED"
        path.write_text("{}", encoding="utf-8")
        self.assertFalse(self._dispose().ok)
        self._review(executed=False)
        self.assertFalse(self._dispose().ok)

    def test_latest_review_failure_wins(self):
        self._review()
        self._review(verdict="FAIL")
        self.assertFalse(self._dispose().ok)
        self.assertFalse(self._health()["disposition_pending"])

    def test_review_does_not_make_reopened_ticket_terminal(self):
        self._review()
        self._section("DOING")
        self.assertFalse(self._dispose().ok)

    def test_ambiguous_or_partial_collect_linkage_refuses(self):
        self._review()
        board = self.root / ".saipen/BOARD.md"
        board.write_text(board.read_text(encoding="utf-8") + "- [ ] T-8 other review | verify: v\n", encoding="utf-8")
        self.records.append({**self.records[0], "op_id": "sub-collect-00000008",
                             "receipt_metadata": {"package_identities": [self.identity], "tickets": ["T-8"]}})
        self.assertFalse(self._dispose().ok)
        self.records.pop()
        for metadata in (
            {"package_identities": [self.identity], "tickets": []},
            {"package_identities": [self.identity, self.identity], "tickets": [self.ticket, self.ticket]},
            {"package_identities": [self.identity], "tickets": self.ticket},
        ):
            self.records[0]["receipt_metadata"] = metadata
            with self.subTest(metadata=metadata):
                self.assertFalse(self._dispose().ok)

    def test_postcondition_checks_exact_package_not_any_reviewed(self):
        self._review()
        other = self.outbox.read_text(encoding="utf-8").split("\n", 1)[1]
        other = other.replace("UI-001", "UI-002").replace("- **status:** ready", "- **status:** reviewed")
        self.outbox.write_text(self.outbox.read_text(encoding="utf-8") + "\n" + other, encoding="utf-8")
        self.assertTrue(self._postcondition(), "unrelated reviewed package satisfied exact disposition")

    def test_exact_reviewed_postcondition_and_metadata_controls(self):
        self._review()
        self.outbox.write_text(subs._mark_package_reviewed(self.outbox.read_text(encoding="utf-8"), self.package.package_id), encoding="utf-8")
        self.assertEqual(self._postcondition(), [])
        for key in ("package_identity", "producer", "package", "source_head",
                    "source_tree_fingerprint", "role_revision", "collect_op", "review_event", "ticket_id"):
            metadata = self._metadata()
            metadata.pop(key)
            with self.subTest(field=key):
                self.assertTrue(self._postcondition(metadata))

    def test_digest_bound_record_still_requires_executed_native_shape(self):
        self._review(record={"schema": 1, "family": "focused-unit", "verdict": "PASS",
                             "patterns": ["test_review.py"], "runs": [], "ran": 1})
        self.assertFalse(self._dispose().ok)

    def test_review_prose_needs_its_own_committed_payload(self):
        self._review()
        self.records[-1]["semantic_payload_hash"] = "0" * 16
        self.assertFalse(self._dispose().ok)

    def test_uncommitted_execution_citation_and_new_verify_refuse(self):
        self._review()
        self.records[-2]["status"] = "CONFLICT"
        self.assertFalse(self._dispose().ok)
        self.records[-2]["status"] = "COMMITTED"
        self._checkpoint(self.ticket, 5, "transition to VERIFY")
        self.assertFalse(self._dispose().ok)

    def test_collect_generation_event_cannot_be_rebound_by_prose(self):
        self._review()
        text = self.log_path.read_text(encoding="utf-8").replace(AGED_HEAD, "e" * 40, 1)
        self.log_path.write_text(text, encoding="utf-8")
        self.assertFalse(self._dispose().ok)

    def test_postcondition_requires_owned_outbox_target(self):
        with mock.patch("saipen_engine.fast_check.validate_project", return_value=[]):
            errors = journal.verify_sub_disposition(
                self.root, [{"path": ".saipen/LOG.md"}, {"path": ".saipen/STATE.md"}], {})
        self.assertTrue(errors)

    def test_nonactive_review_checkpoint_is_not_a_recording_route(self):
        from saipen_engine.operations import _stale_work_context_refusal
        board = "## DOING\n- [/] T-2040 audit | verify: v\n## TODO\n## DONE\n## BLOCKED\n- [ ] T-7 review | verify: v\n"
        result = _stale_work_context_refusal({"task": "T-2040"}, board, self.ticket)
        self.assertEqual(result.code, "STALE_WORK_CONTEXT")


class NativeCoreReviewTests(unittest.TestCase):
    def test_native_no_patch_review_survives_restart_and_deduplicates(self):
        from freshness import compute_source_identity
        from saipen_engine import operations
        from saipen_engine.board import parse_board
        from saipen_engine.log import read_history_snapshot
        from test_t1363_zero_manual_entry import healthy

        root = healthy(self)
        (root / "tools").mkdir()
        (root / "tools/test_review.py").write_text(
            "import unittest\nclass Review(unittest.TestCase):\n"
            "    def test_premise(self): self.assertEqual(2 + 2, 4)\n", encoding="utf-8",
        )
        spawned = subs.sub_spawn(root, ROLE, str(TOOLS.parent), agent="test-agent")
        self.assertTrue(spawned.ok, spawned.to_dict())
        source = compute_source_identity(root)
        revision = subs.current_local_role_revision(root, ROLE, str(TOOLS.parent))
        outbox = root / subs.SUBS_REL / ROLE / "kitchen/OUTBOX.md"
        outbox.write_text(
            "# OUTBOX\n\n## UI-001: hypothesis claims two plus two differs from four\n"
            "- **status:** ready\n- **summary:** Independently test the arithmetic premise\n"
            "- **main_project_refs:** [tools/test_review.py]\n- **critical:** false\n"
            f"- **severity:** P3\n- **producer:** {ROLE}\n"
            f"- **source_head:** {source.source_head}\n"
            f"- **source_tree_fingerprint:** {source.source_tree_fingerprint}\n"
            f"- **role_revision:** {revision}\n- **coverage:** tools/test_review.py\n"
            "- **payload:** []\n- **verified:** PASS -- producer hypothesis only\n"
            "- **instructions:** Core independently rejects the arithmetic premise\n",
            encoding="utf-8",
        )
        package = subs.parse_outbox(outbox.read_text(encoding="utf-8"), ROLE).packages[0]
        collected = subs.sub_collect(root, ROLE, agent="test-agent")
        self.assertTrue(collected.ok, collected.to_dict())
        ticket = collected.data["tickets"][0]["ticket"]
        replay = subs.sub_collect(root, ROLE, agent="test-agent")
        self.assertEqual(replay.code, "ALREADY_COLLECTED", replay.to_dict())
        claimed = operations.apply_claim(root, ticket, "test-agent")
        self.assertTrue(claimed.ok, claimed.to_dict())
        built = operations.transition_phase(root, "BUILD", "test-agent", ticket)
        self.assertTrue(built.ok, built.to_dict())
        note = operations.checkpoint(root, "test-agent", "RUN", ticket,
            "build -> implementation_delta none: test the producer premise")
        self.assertTrue(note.ok, note.to_dict())
        verify = operations.transition_phase(root, "VERIFY", "test-agent", ticket)
        self.assertTrue(verify.ok, verify.to_dict())
        boundary = next(event for event in read_history_snapshot(root).events
                        if event.get("op_id") == verify.op_id)
        self.assertTrue(subs._verify_boundary_proves(boundary, tuple(subs._iter_operation_records(root))))
        self.assertFalse(subs.sub_disposition(root, ROLE, package.package_id,
                                             agent="test-agent", dry_run=True).ok)
        record = focused_unit.run_focused(root, ["test_review.py"], timeout=30)
        self.assertEqual(record["verdict"], "PASS", record)
        relative = focused_unit.RECORD_DIR_REL + "/native-review.json"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = (json.dumps(record) + "\n").encode("utf-8")
        path.write_bytes(raw)
        citation = f"record:{relative} sha256:{hashlib.sha256(raw).hexdigest()}"
        executed = operations.checkpoint(root, "test-agent", "RUN", ticket,
            f"{focused_unit.MARKER} PASS conf: high ran:1 {citation}")
        self.assertTrue(executed.ok, executed.to_dict())
        bindings = subs._package_review_bindings(package, collected.op_id)
        review = operations.checkpoint(root, "test-agent", "RUN", ticket,
            "review -> PASS conf: high -- premise disproven: two plus two equals four; "
            + "; ".join(f"{key}={value}" for key, value in bindings.items()) + "; " + citation)
        self.assertTrue(review.ok, review.to_dict())
        proof, problem = subs._independent_core_review(root, package, ticket,
            collected.op_id, tuple(subs._iter_operation_records(root)))
        self.assertIsNotNone(proof, problem)
        for phase in ("REVIEW", "SHIP"):
            transitioned = operations.transition_phase(root, phase, "test-agent", ticket)
            self.assertTrue(transitioned.ok, transitioned.to_dict())
        finished = operations.finish_ticket(root, ticket, "test-agent",
            closure_mode="finding_invalidated", invalidation_evidence=proof["review_event"])
        self.assertTrue(finished.ok, finished.to_dict())
        fields = parse_board((root / ".saipen/BOARD.md").read_text(encoding="utf-8"))["tickets"][ticket]["fields"]
        self.assertEqual(fields["implementation_delta"], "none")
        disposed = subs.sub_disposition(root, ROLE, package.package_id, agent="test-agent")
        self.assertTrue(disposed.ok, disposed.to_dict())
        receipt = journal.Journal(root, disposed.op_id).read()
        self.assertEqual(journal.verify_sub_disposition(root, receipt["targets"],
            receipt["receipt_metadata"]), [])
        replay = subs.sub_collect(root, ROLE, agent="test-agent")
        self.assertEqual(replay.code, "ALREADY_COLLECTED", replay.to_dict())
        self.assertEqual(subs.package_identity(
            subs.parse_outbox(outbox.read_text(encoding="utf-8"), ROLE).packages[0]),
            subs.package_identity(package))


if __name__ == "__main__":
    unittest.main()

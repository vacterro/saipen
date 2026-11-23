"""T-1746 / SRC-240: the terminal closure of a versionless, ticketless crew epoch.

The stranded downstream shape (measured on the real project, read-only): Core
at DONE / task none, converge intent on crew, a durable epoch that names no
ticket, a deferred scope recorded with full sha256 identities, no VERSION
file, persisted STATE.mode `full` and a current session that may not publish.

Crew readiness (SC-0..SC-10) is `crew_release_context`'s own verdict and is
not what this module measures, so it is supplied; everything the release
engine does with it -- plan, preflight, journal, closure, receipt, verdict,
recovery -- is real.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import test_source_receipts as fixtures
from saipen_engine import crew, release
from saipen_engine.journal import Journal
from saipen_engine.operations import release_scope_hash
from saipen_engine.paths import identity_file_content
from saipen_engine.subs import CREW_ROLES

EPOCH = "converge_intent-" + "a1" * 16
OTHER_EPOCH = "converge_intent-" + "b2" * 16
LINEAGE = "lineage-" + "c3" * 16
CREATED = "2026-10-08T03:40:55Z"
SCOPE_BODIES = (
    ("theme.css", "body { color: gold }\n"),
    ("tools/plugin.js", "module.exports = 1;\n"),
)


class _DownstreamShape(unittest.TestCase):
    setUp = fixtures.SourceReceiptTests.setUp
    tearDown = fixtures.SourceReceiptTests.tearDown
    resolve = fixtures.SourceReceiptTests.resolve
    _scope_file = fixtures.SourceReceiptTests._scope_file
    _record_scope = fixtures.SourceReceiptTests._record_scope
    _incomplete_work = fixtures.SourceReceiptTests._incomplete_work
    _git = fixtures.SourceReceiptTests._git
    _init_git = fixtures.SourceReceiptTests._init_git
    _commit_all = fixtures.SourceReceiptTests._commit_all

    def _shape(self, *, version: str = "", ticket: str = "", wide: bool = True) -> None:
        saipen = self.root / ".saipen"
        (saipen / "IDENTITY.md").write_text(identity_file_content(LINEAGE), encoding="utf-8")
        (saipen / "BOARD.md").write_text(
            "# Board\n## DOING\n## TODO\n## DONE\n"
            + (f"- [x] {ticket} deferred work | verify: fixture\n" if ticket else "")
            + "## BLOCKED\n"
            "- [ ] T-003 operator acceptance | verify: operator-owned session | "
            "blocker: WAIT_USER_CONFIRMATION -- operator-owned session | "
            "blocker_scope: ticket\n",
            encoding="utf-8",
        )
        (saipen / "STATE.md").write_text(
            "---\n"
            "phase: DONE\n"
            "task: none\n"
            'next_action: "saipen crew"\n'
            "blocker: none\n"
            "transition_from: SHIP\n"
            "saipen_version: 7\n"
            "agent: old-agent\n"
            "mode: full\n"
            "updated: 2020-01-01T00:00:00Z\n"
            "execution_intent: converge\n"
            "converge_target: crew\n"
            "---\n",
            encoding="utf-8",
        )
        self._write_epoch(ticket=ticket)
        self.scope = {}
        for rel, body in SCOPE_BODIES:
            self._scope_file(rel, body)
            digest = release_scope_hash((self.root / rel).read_bytes())
            self.scope[rel] = digest if wide else digest[:16]
        self.versioned = bool(version)
        if version:
            (self.root / "VERSION").write_text(version + "\n", encoding="utf-8")
        if ticket:
            # An epoch that owns a ticket owns that ticket's reviewed scope too;
            # the source gate judges it as the current Work of the closure.
            self._record_scope(ticket, [rel for rel, _body in SCOPE_BODIES])
        self.context = {
            "ok": True,
            "crew_epoch": EPOCH,
            "crew_pre_ship_evidence": {
                role.name: [{"package_identity": "p"}] for role in CREW_ROLES
            },
            "crew_pre_ship_applicability": {},
            "crew_defer_scope": dict(self.scope),
            "ticket_id": ticket,
        }

    def _write_epoch(self, *, ticket: str = "", lineage: str = LINEAGE) -> None:
        carrier = {
            "schema_version": 1,
            "operation": "crew_epoch",
            "op_id": EPOCH,
            "target": "crew",
            "status": "COMMITTED",
            "created_at": CREATED,
            "project_lineage": lineage,
        }
        if ticket:
            carrier["ticket_id"] = ticket
        kitchen = self.root / ".saipen" / "kitchen"
        kitchen.mkdir(parents=True, exist_ok=True)
        (kitchen / "crew_epoch.json").write_bytes(
            (json.dumps(carrier, indent=2, sort_keys=True) + "\n").encode("utf-8")
        )

    def _context(self, _root) -> dict:
        from freshness import compute_source_identity

        if not self.context.get("ok"):
            return dict(self.context)
        identity = compute_source_identity(self.root)
        return {
            **self.context,
            "crew_pre_ship_source": {
                "source_head": identity.source_head,
                "source_tree_fingerprint": identity.source_tree_fingerprint,
            },
        }

    def _patches(self):
        # A minimal fixture has no versioned protocol install to be in parity
        # with; whether a version EXISTS is what is measured, and it is real.
        return (
            patch.object(crew, "crew_release_context", side_effect=self._context),
            patch.object(release, "_run_gate", return_value={"ok": True}),
            patch.object(release, "_check_parity", return_value=None),
        )

    def _plan(self, capability: str = "no-publish", **kwargs):
        ready, gate, parity = self._patches()
        with ready, gate, parity:
            return release.plan_release(
                self.root, "ship", current_capability=capability, **kwargs
            )

    def _apply(self, plan) -> dict:
        ready, gate, parity = self._patches()
        with ready, gate, parity:
            return release.execute_release(self.root, plan)

    def _close(self) -> tuple[object, dict]:
        plan = self._plan()
        result = self._apply(plan)
        self.assertTrue(result["ok"], result)
        return plan, result

    def _refusal(self, capability: str = "no-publish", **kwargs) -> release.ReleaseRefusal:
        with self.assertRaises(release.ReleaseRefusal) as caught:
            self._plan(capability, **kwargs)
        return caught.exception

    def _verdict(self, epoch: str = EPOCH) -> dict:
        return release.release_verdict(self.root, crew_epoch=epoch)

    def _certify(self, *, mode: str = "full", ticket: str = "", capability=None):
        epoch = crew.CrewEpoch(0, EPOCH, ticket or None, CREATED)
        snapshot = SimpleNamespace(
            root=self.root,
            state={"phase": "DONE", "task": "none", "mode": mode},
            epoch=epoch,
            release=crew._release_evidence(self.root, epoch),
            current_capability=capability,
            source_id=None,
        )
        return crew._release_current(snapshot)

    def _receipt(self) -> dict:
        path = self.root / ".saipen" / "kitchen" / "release_receipt.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def _tree(self) -> dict:
        return {
            path.relative_to(self.root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.root.rglob("*")
            if path.is_file()
            and not path.relative_to(self.root).as_posix().startswith((".git/", ".saipen/locks/"))
        }

    def _canonical(self) -> dict:
        return {
            name: (self.root / ".saipen" / name).read_bytes()
            for name in ("STATE.md", "BOARD.md", "LOG.md")
        }


class LocalTerminalClosure(_DownstreamShape):
    def test_versionless_ticketless_epoch_closes_locally(self):
        self._shape()
        plan, result = self._close()
        self.assertEqual(
            (plan.version, plan.tag, plan.ticket_id, plan.mode, plan.crew_epoch),
            ("", "", "", "no-publish", EPOCH),
        )
        self.assertEqual(result["code"], "NO_PUBLISH_MODE")
        self.assertEqual(result["terminal_outcome"], release.TERMINAL_LOCAL_NO_PUBLISH)
        self.assertEqual(result["publication"], release.PUBLICATION_NOT_PERFORMED)
        self.assertFalse((self.root / "VERSION").exists(), "a version was synthesized")
        receipt = self._receipt()
        self.assertEqual(
            (receipt["version"], receipt["tag"], receipt["ticket_id"]), ("", "", "")
        )
        self.assertEqual((receipt["mode"], receipt["crew_epoch"]), ("no-publish", EPOCH))
        state = (self.root / ".saipen/STATE.md").read_text(encoding="utf-8")
        self.assertIn("phase: DONE", state)
        self.assertIn("task: none", state)
        log = (self.root / ".saipen/LOG.md").read_text(encoding="utf-8")
        self.assertIn("ship (no version) -> skipped publish (no-publish: no git)", log)
        self.assertNotIn("ship v ", log)
        self.assertIn("all deferred tickets closed locally, nothing published", log)
        self.assertNotIn("tickets shipped", log)

    def test_the_verdict_names_a_local_closure_under_a_persisted_full_mode(self):
        self._shape()
        self._close()
        verdict = self._verdict()
        self.assertEqual(verdict["status"], "ok", verdict)
        evidence = verdict["evidence"]
        self.assertEqual(evidence["terminal_outcome"], release.TERMINAL_LOCAL_NO_PUBLISH)
        self.assertEqual(evidence["publication"], release.PUBLICATION_NOT_PERFORMED)
        self.assertEqual((evidence["mode"], evidence["crew_epoch"]), ("no-publish", EPOCH))
        self.assertEqual(self._certify(mode="full"), (True, ""))

    def test_a_ticketless_epoch_of_a_versioned_project_keeps_its_version(self):
        self._shape(version="8.0.1", wide=False)
        plan, _result = self._close()
        self.assertEqual((plan.version, plan.tag, plan.ticket_id), ("8.0.1", "v8.0.1", ""))
        receipt = self._receipt()
        self.assertEqual(
            (receipt["version"], receipt["tag"], receipt["ticket_id"]), ("8.0.1", "v8.0.1", "")
        )
        self.assertEqual(self._certify(), (True, ""))

    def test_a_versionless_epoch_that_owns_a_ticket_closes_under_that_ticket(self):
        self._shape(ticket="T-11", wide=False)
        plan, _result = self._close()
        self.assertEqual((plan.version, plan.ticket_id), ("", "T-11"))
        self.assertEqual(self._receipt()["ticket_id"], "T-11")

    def test_a_scope_deferred_with_full_identities_is_not_read_as_changed(self):
        self._shape(version="8.0.1", ticket="T-11", wide=True)
        self.assertTrue(all(len(digest) == 64 for digest in self.scope.values()))
        plan, _result = self._close()
        self.assertEqual(dict(plan.crew_scope), self.scope)

    def test_the_ticketed_versioned_short_identity_route_is_unchanged(self):
        """Known-good control: the one shape that closed before this Work."""
        self._shape(version="8.0.1", ticket="T-11", wide=False)
        plan, result = self._close()
        self.assertEqual((plan.version, plan.tag, plan.ticket_id), ("8.0.1", "v8.0.1", "T-11"))
        self.assertEqual(result["code"], "NO_PUBLISH_MODE")
        log = (self.root / ".saipen/LOG.md").read_text(encoding="utf-8")
        self.assertIn("ship v8.0.1 -> skipped publish (no-publish: no git)", log)

    def test_an_operator_owned_ticket_without_a_source_does_not_block(self):
        self._shape()
        board = (self.root / ".saipen/BOARD.md").read_text(encoding="utf-8")
        self.assertIn("T-003 operator acceptance", board)
        self._close()
        self.assertIn(
            "T-003 operator acceptance",
            (self.root / ".saipen/BOARD.md").read_text(encoding="utf-8"),
        )

    def test_a_git_project_sees_zero_git_mutation(self):
        self._shape()
        if not self._init_git():
            self.skipTest("git is unavailable")
        self.assertTrue(self._commit_all("fixture"))

        def facts() -> tuple[str, str, str, str]:
            return (
                self._git("rev-parse", "HEAD").stdout,
                self._git("for-each-ref").stdout,
                self._git("ls-files", "-s").stdout,
                self._git("stash", "list").stdout,
            )

        before = facts()
        _plan, result = self._close()
        self.assertEqual(facts(), before)
        self.assertEqual(self._git("tag", "--list").stdout, "")
        self.assertEqual(result["publication"], release.PUBLICATION_NOT_PERFORMED)
        log = (self.root / ".saipen/LOG.md").read_text(encoding="utf-8")
        self.assertIn("ship (no version) -> skipped publish (no-publish: policy)", log)
        self.assertEqual(self._verdict()["status"], "ok", self._verdict())


class PublicationKeepsItsGates(_DownstreamShape):
    def test_missing_version_never_reaches_a_publication(self):
        self._shape()
        refusal = self._refusal("full")
        self.assertEqual(refusal.code, "VALIDATION_FAILED")
        self.assertIn("VERSION is missing", refusal.detail)

    def test_a_ticketless_epoch_cannot_publish_and_is_told_why(self):
        self._shape(version="8.0.1", wide=False)
        refusal = self._refusal("full")
        self.assertEqual(refusal.code, "CREW_NOT_READY")
        self.assertIn("names no ticket", refusal.detail)
        self.assertNotIn("zero tickets", refusal.detail)

    def test_an_ordinary_versionless_ticket_keeps_its_own_route(self):
        self._shape()
        state = self.root / ".saipen/STATE.md"
        state.write_text(
            state.read_text(encoding="utf-8")
            .replace("phase: DONE", "phase: SHIP")
            .replace("task: none", "task: T-001")
            .replace("execution_intent: converge\nconverge_target: crew\n", ""),
            encoding="utf-8",
        )
        refusal = self._refusal()
        self.assertEqual(refusal.code, "VALIDATION_FAILED")
        self.assertIn("ticket done", refusal.detail)

    def test_a_cohort_still_needs_its_version_and_its_ticket(self):
        self._shape()
        state = self.root / ".saipen/STATE.md"
        state.write_text(
            state.read_text(encoding="utf-8").replace(
                "execution_intent: converge\nconverge_target: crew\n", ""
            ),
            encoding="utf-8",
        )
        carrier = {"cohort_id": "C-001", "ticket_id": "T-001", "scope": dict(self.scope)}
        refusal = self._refusal(cohort_carrier=carrier)
        self.assertIn("VERSION is missing", refusal.detail)
        (self.root / "VERSION").write_text("8.0.1\n", encoding="utf-8")
        refusal = self._refusal(cohort_carrier={**carrier, "ticket_id": ""})
        self.assertEqual(refusal.code, "VALIDATION_FAILED")
        self.assertIn("ticket_id", refusal.detail)

    def test_a_read_only_session_plans_and_certifies_nothing(self):
        self._shape()
        refusal = self._refusal("read-only")
        self.assertIn("read-only", refusal.detail)
        self._close()
        epoch = crew.CrewEpoch(0, EPOCH, None, CREATED)
        snapshot = SimpleNamespace(
            root=self.root,
            state={"phase": "DONE", "task": "none", "mode": "full"},
            epoch=epoch,
            release=crew._release_evidence(self.root, epoch),
            current_capability="read-only",
            source_id=None,
        )
        ok, reason = crew._release_current(snapshot)
        self.assertFalse(ok)
        self.assertIn("read-only", reason)

    def test_a_persisted_no_publish_mode_cannot_waive_the_proof_of_a_publication(self):
        self._shape()
        published = SimpleNamespace(
            verdict="ok",
            verdict_reason="",
            mode="full",
            ticket="",
            closure_commit="c0ffee",
            source_head="",
            source_tree_fingerprint="",
            pre_ship_evidence={role.name: [{"package_identity": "p"}] for role in CREW_ROLES},
            pre_ship_applicability={},
        )
        snapshot = SimpleNamespace(
            root=self.root,
            state={"phase": "DONE", "task": "none", "mode": "no-publish"},
            epoch=crew.CrewEpoch(0, EPOCH, None, CREATED),
            release=published,
            current_capability=None,
            source_id=None,
        )
        ok, reason = crew._release_current(snapshot)
        self.assertFalse(ok, "a publication was certified as a local closure")
        self.assertIn("source identity unavailable", reason)


class IdentityIsNeverBorrowed(_DownstreamShape):
    def test_a_carrier_naming_a_ticket_the_epoch_does_not_own_is_refused(self):
        self._shape(version="8.0.1", wide=False)
        carrier = {"crew_epoch": EPOCH, "scope": dict(self.scope), "ticket_id": "T-246"}
        refusal = self._refusal(crew_carrier=carrier)
        self.assertEqual(refusal.code, "CREW_NOT_READY")
        self.assertIn("never borrows", refusal.detail)

    def test_a_carrier_naming_another_epoch_is_refused(self):
        self._shape(version="8.0.1", ticket="T-11", wide=False)
        carrier = {"crew_epoch": OTHER_EPOCH, "scope": dict(self.scope), "ticket_id": "T-11"}
        refusal = self._refusal(crew_carrier=carrier)
        self.assertEqual(refusal.code, "CREW_NOT_READY")
        self.assertIn(OTHER_EPOCH, refusal.detail)

    def test_an_epoch_carrier_of_another_lineage_is_refused(self):
        self._shape()
        self._write_epoch(lineage="lineage-" + "d4" * 16)
        refusal = self._refusal()
        self.assertEqual(refusal.code, "CREW_NOT_READY")
        self.assertIn("not canonical", refusal.detail)

    def test_a_ticket_that_appears_between_plan_and_apply_writes_nothing(self):
        self._shape()
        plan = self._plan()
        self.context["ticket_id"] = "T-246"
        before = self._tree()
        result = self._apply(plan)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["stage"], "CREW_NOT_READY", result)
        self.assertEqual(self._tree(), before)

    def test_a_receipt_naming_a_ticket_the_epoch_does_not_own_cannot_certify(self):
        self._shape(version="8.0.1", ticket="T-11", wide=False)
        self._close()
        self.assertEqual(self._certify(ticket="T-11"), (True, ""))
        ok, reason = self._certify(ticket="")
        self.assertFalse(ok)
        self.assertIn("T-11", reason)

    def test_a_receipt_of_another_epoch_is_not_this_epochs_release(self):
        self._shape()
        self._close()
        self.assertEqual(self._verdict(EPOCH)["status"], "ok")
        self.assertEqual(self._verdict(OTHER_EPOCH)["status"], "unknown")

    def test_another_project_lineage_does_not_inherit_the_receipt(self):
        self._shape()
        self._close()
        (self.root / ".saipen/IDENTITY.md").write_text(
            identity_file_content("lineage-" + "e5" * 16), encoding="utf-8"
        )
        self.assertNotEqual(self._verdict()["status"], "ok")


class ScopeAndSource(_DownstreamShape):
    def _records(self, *claims) -> tuple[dict, ...]:
        return tuple(
            {
                "operation": "crew_defer",
                "status": "COMMITTED",
                "created_at": created,
                "op_id": op_id,
                "receipt_metadata": {"crew_epoch": EPOCH, "paths": paths},
            }
            for created, op_id, paths in claims
        )

    def _derive(self, *claims):
        snapshot = SimpleNamespace(
            root=self.root, epoch=crew.CrewEpoch(0, EPOCH, None, CREATED)
        )
        return crew.derive_crew_scope(snapshot, self._records(*claims))

    def test_an_empty_deferred_scope_refuses(self):
        self._shape()
        self.context["crew_defer_scope"] = {}
        refusal = self._refusal()
        self.assertEqual(refusal.code, "CREW_NOT_READY")
        self.assertIn("no deferred crew scope", refusal.detail)
        scope, problem = self._derive()
        self.assertEqual(scope, {})
        self.assertIn("no deferred crew scope", problem)

    def test_two_defers_of_one_instant_approving_different_bytes_are_ambiguous(self):
        self._shape()
        mine = self.scope["theme.css"]
        scope, problem = self._derive(
            ("2026-10-12T23:26:19Z", "crew-defer-aa", {"theme.css": mine}),
            ("2026-10-12T23:26:19Z", "crew-defer-bb", {"theme.css": "0" * 64}),
        )
        self.assertEqual(scope, {})
        self.assertIn("ambiguous deferred ownership", problem)

    def test_a_superseded_tie_and_an_agreeing_tie_keep_one_owner(self):
        self._shape()
        mine = self.scope["theme.css"]
        scope, problem = self._derive(
            ("2026-10-12T23:26:19Z", "crew-defer-aa", {"theme.css": "0" * 64}),
            ("2026-10-12T23:26:19Z", "crew-defer-bb", {"theme.css": "1" * 64}),
            ("2026-10-12T23:50:35Z", "crew-defer-cc", {"theme.css": mine}),
            ("2026-10-12T23:50:35Z", "crew-defer-dd", {"theme.css": mine}),
        )
        self.assertIsNone(problem)
        self.assertEqual(scope, {"theme.css": mine})

    def test_scope_bytes_changed_after_the_review_refuse_the_plan(self):
        self._shape()
        (self.root / "theme.css").write_text("body { color: red }\n", encoding="utf-8")
        refusal = self._refusal()
        self.assertEqual(refusal.code, "STALE_PLAN")
        self.assertIn("theme.css", refusal.detail)

    def test_scope_bytes_changed_between_plan_and_apply_write_nothing(self):
        self._shape()
        plan = self._plan()
        (self.root / "theme.css").write_text("body { color: red }\n", encoding="utf-8")
        before = self._tree()
        result = self._apply(plan)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["stage"], "PREFLIGHT", result)
        self.assertEqual(self._tree(), before)

    def test_a_foreign_source_change_between_plan_and_apply_writes_nothing(self):
        self._shape()
        plan = self._plan()
        (self.root / "late.js").write_text("foreign\n", encoding="utf-8")
        before = self._tree()
        result = self._apply(plan)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["stage"], "PREFLIGHT", result)
        self.assertEqual(self._tree(), before)

    def test_a_source_that_moved_after_the_closure_stales_the_receipt(self):
        self._shape()
        self._close()
        self.assertEqual(self._certify(), (True, ""))
        (self.root / "late.js").write_text("foreign\n", encoding="utf-8")
        verdict = self._verdict()
        self.assertEqual(verdict["status"], "unknown", verdict)
        ok, reason = self._certify()
        self.assertFalse(ok)
        self.assertIn("UNKNOWN", reason)

    def test_an_unresolved_source_of_other_work_still_blocks(self):
        self._shape()
        self._incomplete_work("an obligation nobody discharged", "T-003")
        plan = self._plan()
        canonical = self._canonical()
        result = self._apply(plan)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["stage"], "SOURCE_COVERAGE", result)
        self.assertEqual(self._canonical(), canonical)


class ConvergenceEvidence(_DownstreamShape):
    def test_no_plan_without_crew_authorization(self):
        self._shape()
        self.context = {"ok": False, "detail": "crew not ready to ship: SC-7 producer stale"}
        refusal = self._refusal()
        self.assertEqual(refusal.code, "CREW_NOT_READY")
        self.assertIn("SC-7 producer stale", refusal.detail)

    def test_authorization_lost_between_plan_and_apply_writes_nothing(self):
        self._shape()
        plan = self._plan()
        self.context = {"ok": False, "detail": "crew not ready to ship: role evidence stale"}
        before = self._tree()
        result = self._apply(plan)
        self.assertFalse(result["ok"], result)
        self.assertIn("role evidence stale", result["detail"])
        self.assertEqual(self._tree(), before)

    def test_a_receipt_missing_a_roles_evidence_cannot_certify(self):
        self._shape()
        dropped = CREW_ROLES[0].name
        del self.context["crew_pre_ship_evidence"][dropped]
        self._close()
        ok, reason = self._certify()
        self.assertFalse(ok)
        self.assertIn("lacks pre-ship crew evidence", reason)
        self.assertIn(dropped, reason)

    def test_no_receipt_is_neither_outcome(self):
        self._shape()
        verdict = self._verdict()
        self.assertEqual(verdict["status"], "unknown", verdict)
        self.assertNotIn("evidence", verdict)
        ok, reason = self._certify()
        self.assertFalse(ok)
        self.assertIn("UNKNOWN", reason)
        self.assertEqual(
            len({release.TERMINAL_PUBLISHED, release.TERMINAL_LOCAL_NO_PUBLISH, "unknown"}), 3
        )


class ProducerEvidence(_DownstreamShape):
    """The release context records the proof the stages authorized the ship on.

    The measured downstream OUTBOX opens with a hand-written entry from before
    the closed grammar; the producer itself is proven by a committed
    integration edge, and SC-8/SC-9 say so.
    """

    def _producer(self):
        from freshness import compute_source_identity
        from saipen_engine.subs import package_identity, parse_outbox

        self._shape()
        role = next(item for item in CREW_ROLES if item.name == "saitranslate")
        identity = compute_source_identity(self.root)
        outbox = self.root / role.outbox_path
        outbox.parent.mkdir(parents=True, exist_ok=True)
        outbox.write_text(
            "# OUTBOX\n\n"
            "## SAIT-007: historical bundle\n\n"
            "- **status:** reviewed\n"
            "- **collected_at:** 2026-08-11T13:20:00Z\n\n"
            "## SAIT-011: current surface audit\n\n"
            "- **status:** ready\n"
            "- **summary:** fixture\n"
            "- **producer:** saitranslate\n"
            f"- **source_head:** {identity.source_head}\n"
            f"- **source_tree_fingerprint:** {identity.source_tree_fingerprint}\n"
            "- **role_revision:** sha256:" + "7d" * 32 + "\n",
            encoding="utf-8",
        )
        model = parse_outbox(outbox.read_text(encoding="utf-8"), role.name)
        self.assertTrue(model.errors, "fixture: the historical entry must be malformed")
        package = next(item for item in model.packages if item.package_id == "SAIT-011")
        # The OUTBOX write moved nothing: `.saipen/` is outside the source identity.
        self.assertEqual(compute_source_identity(self.root), identity)
        return role, identity, package_identity(package)

    def _snapshot(self, identity, *records):
        return SimpleNamespace(
            root=self.root,
            epoch=crew.CrewEpoch(0, EPOCH, None, CREATED),
            source_id=identity,
            saipen_home=str(fixtures.ROOT),
            op_records=tuple(records),
        )

    def _edge(self, identity, package, **meta) -> dict:
        return {
            "operation": "producer_integration",
            "status": "COMMITTED",
            "created_at": "2026-10-13T00:11:47Z",
            "op_id": "producer-integrate-fixture",
            "receipt_metadata": {
                "crew_epoch": EPOCH,
                "producer": "saitranslate",
                "package_identity": package,
                "input_source": identity.source_head,
                "resulting_source": identity.source_head,
                "resulting_source_fingerprint": identity.source_tree_fingerprint,
                **meta,
            },
        }

    def test_an_integrated_producer_is_recorded_by_its_integration_edge(self):
        role, identity, package = self._producer()
        snapshot = self._snapshot(identity, self._edge(identity, package))
        self.assertTrue(crew._producer_integrated(snapshot, role))
        records = crew._producer_package_records(snapshot, role)
        self.assertEqual(len(records), 1, records)
        record = records[0]
        self.assertEqual(
            (record["status"], record["producer"], record["package_identity"]),
            ("integrated", "saitranslate", package),
        )
        self.assertEqual(record["integration_op"], "producer-integrate-fixture")
        self.assertEqual(record["source_head"], identity.source_head)
        self.assertEqual(record["source_tree_fingerprint"], identity.source_tree_fingerprint)
        self.assertEqual(record["crew_epoch"], EPOCH)

    def test_a_producer_without_an_edge_stays_without_evidence(self):
        role, identity, package = self._producer()
        for records in (
            (),
            (self._edge(identity, package, resulting_source_fingerprint="git-delta-v1:0"),),
            (self._edge(identity, "sha256:" + "0" * 64),),
            (self._edge(identity, package, crew_epoch=OTHER_EPOCH),),
        ):
            with self.subTest(records=records):
                snapshot = self._snapshot(identity, *records)
                self.assertFalse(crew._producer_integrated(snapshot, role))
                self.assertEqual(crew._producer_package_records(snapshot, role), [])


class ManagedProjectGate(_DownstreamShape):
    def test_a_managed_project_is_judged_by_the_runtimes_validator(self):
        self._shape()
        self.assertFalse((self.root / "tools" / "validate.py").exists())
        command = release._gate_command(self.root, "core")
        validator = fixtures.ROOT / "tools" / "validate.py"
        self.assertEqual(
            command[1:],
            [str(validator), "--project-root", str(self.root), "--gate", "core"],
        )
        verdict = release._run_gate(self.root, "core")
        self.assertNotIn("can't open file", verdict.get("detail", ""), verdict)

    def test_a_source_tree_keeps_validating_itself(self):
        home = Path(release.__file__).resolve().parents[2]
        command = release._gate_command(home, "ship")
        self.assertEqual(command[1:], [str(home / "tools/validate.py"), "--gate", "ship"])


class RecoveryAndReceipts(_DownstreamShape):
    def test_an_interrupted_closure_recovers_and_the_retry_changes_nothing(self):
        self._shape()
        plan = self._plan()

        class Interrupted(Exception):
            pass

        original = release._mark_target
        marked = 0

        def interrupt_after_first(journal, index):
            nonlocal marked
            original(journal, index)
            marked += 1
            if marked == 1:
                raise Interrupted()

        mark = patch.object(release, "_mark_target", side_effect=interrupt_after_first)
        with mark, self.assertRaises(Interrupted):
            self._apply(plan)
        self.assertNotEqual(self._verdict()["status"], "ok", "a half-applied closure verified")
        recovered = release.recover_release_op(self.root, plan.op_id)
        self.assertTrue(recovered["ok"], recovered)
        self.assertEqual(recovered["code"], "COMMITTED")
        settled = self._tree()
        again = release.recover_release_op(self.root, plan.op_id)
        self.assertEqual((again["ok"], again["code"]), (True, "ALREADY_APPLIED"), again)
        self.assertEqual(self._tree(), settled)
        self.assertEqual(self._verdict()["status"], "ok", self._verdict())
        self.assertEqual(self._receipt()["op_id"], plan.op_id)
        self.assertEqual(self._certify(), (True, ""))

    def test_a_closure_that_died_before_its_body_is_aborted_not_committed(self):
        self._shape()
        plan = self._plan()
        canonical = self._canonical()

        class Died(Exception):
            pass

        body = patch.object(release, "_no_publish_body", side_effect=Died())
        with body, self.assertRaises(Died):
            self._apply(plan)
        recovered = release.recover_release_op(self.root, plan.op_id)
        self.assertEqual((recovered["ok"], recovered["code"]), (True, "ABORTED"), recovered)
        self.assertEqual(self._canonical(), canonical)
        self.assertNotEqual(self._verdict()["status"], "ok")

    def test_a_refused_local_validation_does_not_poison_the_epoch(self):
        """Measured on the real downstream bytes: two refused attempts, then a
        committed closure whose verdict stayed UNKNOWN for good."""
        self._shape()
        plan = self._plan()
        ready, _gate, parity = self._patches()
        red_gate = patch.object(
            release, "_run_gate", return_value={"ok": False, "detail": "FAIL: fixture"}
        )
        with ready, red_gate, parity:
            refused = release.execute_release(self.root, plan)
        self.assertFalse(refused["ok"], refused)
        self.assertEqual(refused["stage"], "NO_PUBLISH", refused)
        self.assertFalse(refused["recovery_required"], refused)
        self.assertEqual(Journal(self.root, plan.op_id).read()["status"], "ABORTED")
        closed, _result = self._close()
        verdict = self._verdict()
        self.assertEqual(verdict["status"], "ok", verdict)
        self.assertEqual(verdict["evidence"]["op_id"], closed.op_id)
        self.assertEqual(self._certify(), (True, ""))

    def test_an_unresolved_sibling_still_makes_the_lineage_unclean(self):
        self._shape()
        plan = self._plan()

        class Died(Exception):
            pass

        body = patch.object(release, "_no_publish_body", side_effect=Died())
        with body, self.assertRaises(Died):
            self._apply(plan)
        # Still PREPARED: nobody recovered it, so nobody knows what it did.
        self.assertEqual(self._refusal().code, "RECOVERY_REQUIRED")
        self.assertNotEqual(self._verdict()["status"], "ok")

    def test_a_second_closure_of_a_verified_epoch_is_refused(self):
        self._shape()
        plan, _result = self._close()
        before = self._tree()
        refusal = self._refusal()
        self.assertEqual(refusal.code, "VALIDATION_FAILED")
        self.assertIn(plan.op_id, refusal.detail)
        self.assertIn(release.TERMINAL_LOCAL_NO_PUBLISH, refusal.detail)
        self.assertEqual(self._tree(), before)

    def test_admission_of_a_ticketless_receipt_needs_a_local_epoch_closure(self):
        base = {
            "operation": "release",
            "created_at": CREATED,
            "status": "COMMITTED",
            "release_stage": "COMMITTED",
            "op_id": "release-0000",
            "source_head": "nogit",
        }
        admit = release._is_admissible_terminal_receipt
        self.assertTrue(admit({**base, "mode": "no-publish", "crew_epoch": EPOCH}))
        self.assertFalse(admit({**base, "mode": "no-publish"}))
        self.assertFalse(
            admit(
                {
                    **base,
                    "mode": "full",
                    "crew_epoch": EPOCH,
                    "closure_commit": "c0ffee",
                    "stages": ["REMOTE_VERIFIED"],
                }
            )
        )
        self.assertTrue(admit({**base, "mode": "no-publish", "ticket_id": "T-9"}))

    def test_historical_receipts_keep_their_meaning_without_a_rewrite(self):
        local = release._receipt_evidence({"mode": "no-publish", "ticket_id": "T-9"})
        self.assertEqual(local["terminal_outcome"], release.TERMINAL_LOCAL_NO_PUBLISH)
        self.assertEqual(local["publication"], release.PUBLICATION_NOT_PERFORMED)
        legacy = release._receipt_evidence({"ticket_id": "T-9", "closure_commit": "c0ffee"})
        self.assertEqual(legacy["terminal_outcome"], release.TERMINAL_PUBLISHED)
        self.assertEqual(legacy["publication"], release.PUBLICATION_PERFORMED)
        self.assertEqual(legacy["mode"], "full")

    def test_a_forged_sibling_receipt_never_becomes_a_pass(self):
        self._shape()
        plan, _result = self._close()
        self.assertEqual(self._verdict()["status"], "ok")
        recovery = self.root / ".saipen" / "recovery"
        real = next(path for path in recovery.rglob(plan.op_id) if path.is_dir())
        forged = real.with_name("release-f0f0f0f0")
        shutil.copytree(real, forged)
        manifest = forged / "operation.json"
        record = json.loads(manifest.read_text(encoding="utf-8"))
        record.update(op_id="release-f0f0f0f0", mode="full", closure_commit="c0ffee")
        manifest.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        verdict = self._verdict()
        self.assertNotEqual(verdict["status"], "ok", verdict)
        ok, _reason = self._certify()
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()

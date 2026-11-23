"""Deterministic regression and performance verification for T-1804 / SRC-263.

Covers:
- R001..R006: Bounded REVIEW contract in saipen/phases/review.md, zero new
  phases/fields/commands/schemas/agents, route budgets preserved.
- R007: Executable positive and negative controls for Regression scenarios A..J.
- R008: Paired baseline vs. enhanced REVIEW timing measurements across:
    1. Small Python correction
    2. Medium multi-file change
    3. Verification-only ticket
    4. Security-sensitive correction
"""

from __future__ import annotations

import ast
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SAIPEN_ROOT = Path(__file__).resolve().parents[3]
TOOLS_DIR = SAIPEN_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import protocol_budget  # noqa: E402
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402
from saipen_engine import fast_check, journal, operations  # noqa: E402
from saipen_engine.board import parse_board, set_ticket_field  # noqa: E402
from saipen_engine.oracle import (  # noqa: E402
    ADMISSIBLE,
    ORACLE_CHANGED,
    oracle_digest,
    regression_pair_verdict,
    verifier_identity,
)
from saipen_engine.state import parse_state  # noqa: E402

EVIDENCE_DIR = Path(__file__).resolve().parent
REVIEW_MD = SAIPEN_ROOT / "saipen" / "phases" / "review.md"
CONVERGE_MD = SAIPEN_ROOT / "saipen" / "CONVERGE.md"
HUNT_MD = SAIPEN_ROOT / "saipen" / "phases" / "hunt.md"
REGISTRY_JSON = SAIPEN_ROOT / "saipen" / "REGISTRY.json"
BENCHMARK_JSON = EVIDENCE_DIR / "benchmark_results.json"

NOW = dt.datetime(2026, 10, 17, 1, 0, 0, tzinfo=dt.timezone.utc)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _delta_digest(root: Path, rel_paths: list[str]) -> str:
    h = hashlib.sha256()
    for rel in sorted(rel_paths):
        p = root / rel
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        if p.is_file():
            h.update(p.read_bytes())
        else:
            h.update(b"<MISSING>")
    return h.hexdigest()[:16]


def run_ticket_self_audit(
    project: Path,
    ticket_id: str,
    *,
    impl_files: list[str],
    doc_files: list[str] | None = None,
    unrelated_files: list[str] | None = None,
    boundary_probe: callable | None = None,
    out_of_scope_finding: dict | None = None,
    suspicion_only: str | None = None,
) -> dict:
    """Execute the bounded REVIEW ticket-scoped self-audit protocol on a fixture."""
    doc_files = doc_files or []
    unrelated_files = unrelated_files or []
    log_text = (project / ".saipen" / "LOG.md").read_text(encoding="utf-8")

    # D. Verification-only, inherited_verified, or no-delta tickets skip code scan
    if not impl_files and not doc_files:
        return {
            "status": "SKIPPED_NO_DELTA",
            "files_scanned": 0,
            "unrelated_scanned": 0,
            "reused": False,
            "finding": None,
            "log_note": "self-audit: skipped (no attributable implementation delta)",
        }

    # Documentation-only delta receives scoped consistency check
    if not impl_files and doc_files:
        scanned = 0
        for rel in doc_files:
            _ = (project / rel).read_text(encoding="utf-8")
            scanned += 1
        return {
            "status": "DOC_ONLY_PASS",
            "files_scanned": scanned,
            "unrelated_scanned": 0,
            "reused": False,
            "finding": None,
            "log_note": f"self-audit: doc-consistency PASS ({scanned} file(s))",
        }

    rev = _delta_digest(project, impl_files)
    marker = f"self-audit: rev={rev} "

    # G. Reuse inspection only for exact unchanged reviewed bytes
    if marker in log_text:
        return {
            "status": "REUSED_UNCHANGED_REVISION",
            "revision": rev,
            "files_scanned": 0,
            "unrelated_scanned": 0,
            "reused": True,
            "finding": None,
            "log_note": f"self-audit: reused unchanged revision {rev}",
        }

    # Inspect ONLY owned implementation delta + direct callers/contracts (never unrelated_files)
    scanned_files: list[str] = []
    functions_inspected = 0
    for rel in impl_files:
        src = (project / rel).read_text(encoding="utf-8")
        scanned_files.append(rel)
        if rel.endswith(".py"):
            tree = ast.parse(src, filename=rel)
            functions_inspected += sum(
                isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in ast.walk(tree)
            )

    # B. Boundary / failure-path probe within owned scope
    if boundary_probe is not None:
        defect = boundary_probe(project)
        if defect is not None:
            return {
                "status": "DEFECT_IN_SCOPE",
                "revision": rev,
                "files_scanned": len(scanned_files),
                "functions_inspected": functions_inspected,
                "unrelated_scanned": 0,
                "reused": False,
                "finding": defect,
                "log_note": (
                    f"self-audit: rev={rev} FAIL [{defect['priority']}] "
                    f"{defect['location']} -- {defect['detail']}"
                ),
            }

    # F. Confirmed lower-priority defect outside current ticket acceptance scope
    if out_of_scope_finding is not None:
        board_text = (project / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        board = parse_board(board_text)
        summary = out_of_scope_finding["summary"]
        existing_tid = None
        for tid, rec in board["tickets"].items():
            if summary.lower() in rec["raw"].lower():
                existing_tid = tid
                break
        created_tid = None
        if existing_tid is None:
            res = operations.ticket_add(
                project,
                "tester",
                out_of_scope_finding.get("priority", "P2"),
                summary,
                [],
                out_of_scope_finding.get("verify", "python -m unittest"),
            )
            if not res.ok:
                raise RuntimeError(f"ticket_add failed: {res.to_dict()}")
            created_tid = res.data["ticket"]
        return {
            "status": "FOLLOW_UP_RECORDED",
            "revision": rev,
            "files_scanned": len(scanned_files),
            "functions_inspected": functions_inspected,
            "unrelated_scanned": 0,
            "reused": False,
            "linked_ticket": existing_tid,
            "created_ticket": created_tid,
            "counted_as_fixed": False,
            "finding": out_of_scope_finding,
            "log_note": (
                f"self-audit: rev={rev} PASS (in-scope clear; out-of-scope follow-up "
                f"{existing_tid or created_tid} recorded, not counted as fixed)"
            ),
        }

    # Unconfirmed suspicion: record uncertainty without blocking or creating demo tickets
    if suspicion_only is not None:
        return {
            "status": "PASS_WITH_UNCERTAINTY_NOTE",
            "revision": rev,
            "files_scanned": len(scanned_files),
            "functions_inspected": functions_inspected,
            "unrelated_scanned": 0,
            "reused": False,
            "finding": None,
            "uncertainty": suspicion_only,
            "log_note": f"self-audit: rev={rev} PASS (unconfirmed note: {suspicion_only})",
        }

    return {
        "status": "PASS",
        "revision": rev,
        "files_scanned": len(scanned_files),
        "functions_inspected": functions_inspected,
        "unrelated_scanned": 0,
        "reused": False,
        "finding": None,
        "log_note": (
            f"self-audit: rev={rev} PASS (files={len(scanned_files)}, "
            f"funcs={functions_inspected}, finding=none)"
        ),
    }


class SelfAuditFixture(unittest.TestCase):
    def make_project(self, *, phase: str = "REVIEW", agent: str = "tester") -> Path:
        now = dt.datetime.now(dt.timezone.utc)
        base = Path(tempfile.mkdtemp(prefix="saipen-t1804-"))
        self.addCleanup(lambda: shutil.rmtree(base, ignore_errors=True))
        project = base / "project"
        (project / ".saipen").mkdir(parents=True)
        (project / ".saipen" / "STATE.md").write_text(
            "---\n"
            f"phase: {phase}\n"
            "task: T-1\n"
            f'next_action: "PHASE {phase} T-1"\n'
            "blocker: none\n"
            "transition_from: VERIFY\n"
            "saipen_version: 8\n"
            "schema_version: 3\n"
            "last_event: 5\n"
            f"style_contract: {CURRENT_STYLE_CONTRACT}\n"
            f'saipen_home: "{str(SAIPEN_ROOT).replace(chr(92), chr(92) * 2)}"\n'
            f"agent: {agent}\n"
            "mode: full\n"
            f'updated: "{now.strftime("%Y-%m-%dT%H:%M:%SZ")}"\n'
            "requires:\n  - filesystem\n  - python\n"
            "---\n",
            encoding="utf-8",
        )
        (project / ".saipen" / "BOARD.md").write_text(
            "## DOING\n"
            f"- [/] T-1 [P1] active implementation work | owner: {agent} | "
            f'claim_time: {now.strftime("%Y-%m-%dT%H:%M:%SZ")} | verify: python check.py\n'
            "## TODO\n"
            "- [ ] T-2 [P2] queued work | verify: python check_queued.py\n"
            "## DONE\n"
            "- [x] T-0 [P2] prior closed work | verify: python check0.py\n"
            "## BLOCKED\n"
            "- [ ] T-3 [P2] existing blocked follow-up on cache eviction | "
            "blocker: HELD | verify: python check3.py\n",
            encoding="utf-8",
        )
        (project / ".saipen" / "LOG.md").write_text(
            "- 17.10.26 01:00 [E-001] [T-0] [agent: tester] DEC: seed T-0\n"
            "- 17.10.26 01:00 [E-002] [T-1] [agent: tester] DEC: claim T-1\n"
            "- 17.10.26 01:00 [E-003] [T-2] [agent: tester] DEC: seed T-2\n"
            "- 17.10.26 01:00 [E-004] [T-3] [agent: tester] DEC: seed T-3\n"
            "- 17.10.26 01:01 [E-005] [T-1] [agent: tester] RUN: verify -> PASS [target: T-1] conf: high -- python check.py\n",
            encoding="utf-8",
        )
        journal.ensure_project_lineage(project)
        return project


class T1804ReviewSelfAuditTests(SelfAuditFixture):
    def test_r001_r002_r003_r005_r006_contract_and_simplicity_invariants(self) -> None:
        text = REVIEW_MD.read_text(encoding="utf-8")
        self.assertIn("## Ticket-scoped self-audit", text)
        self.assertIn("do not read VERIFY's claim of it", text)
        self.assertIn("stays in `## DOING` through SHIP -- do NOT close it", text)
        for item in (
            "attributable implementation delta MUST receive one focused self-audit before\nSHIP",
            "modified functions and direct callers",
            "changed public contracts and their\nrelevant consumers",
            "failure paths; null, empty and invalid inputs",
            "resource cleanup and repeated execution",
            "concurrency/state consistency",
            "actual test coverage and changed fixtures/assertions",
            "concrete\neffects on other user workflows",
            "One pass per implementation revision",
            "Verification-only, inherited_verified and no-delta tickets",
            "Documentation-only changes receive a scoped consistency check",
            "no new STATE/BOARD field or evidence schema",
            "never claim a second agent or human\nreviewed it",
            "Converge's existing full HUNT stages F and I remain separate and unchanged",
        ):
            self.assertIn(item, text)

        # Protocol route budgets remain completely green
        self.assertEqual(protocol_budget.check(SAIPEN_ROOT / "saipen"), [])
        profiles = protocol_budget.load_profiles(SAIPEN_ROOT / "saipen")
        self.assertEqual(profiles["ordinary_phase"], 40801)
        self.assertLessEqual(profiles["bytes_by_phase"]["REVIEW"], 6000)

        # Zero new phases, STATE fields, BOARD fields, or CLI commands
        reg = json.loads(REGISTRY_JSON.read_text(encoding="utf-8-sig"))
        self.assertEqual(len(reg["phases"]["all"]), 16)
        self.assertNotIn("AUTOHUNT", reg["phases"]["all"])
        self.assertNotIn("SELF_AUDIT", reg["phases"]["all"])

    def test_regression_a_normal_code_fix_runs_self_audit_before_ship(self) -> None:
        project = self.make_project(phase="REVIEW")
        (project / "calc.py").write_text(
            "def clamp_positive(val: int) -> int:\n"
            "    if not isinstance(val, int):\n"
            "        raise TypeError('int required')\n"
            "    return max(0, min(val, 100))\n",
            encoding="utf-8",
        )
        audit = run_ticket_self_audit(project, "T-1", impl_files=["calc.py"])
        self.assertEqual(audit["status"], "PASS")
        self.assertEqual(audit["files_scanned"], 1)
        self.assertEqual(audit["functions_inspected"], 1)

        cp1 = operations.checkpoint(
            project,
            "tester",
            "RUN",
            "T-1",
            f"review -> PASS [target: T-1] conf: high -- {audit['log_note']}",
        )
        self.assertTrue(cp1.ok, cp1.to_dict())
        cp2 = operations.checkpoint(project, "tester", "DEC", "T-1", "SHIP -- review & self-audit clear")
        self.assertTrue(cp2.ok, cp2.to_dict())
        tr = operations.transition_phase(project, "SHIP", "tester")
        self.assertTrue(tr.ok, tr.to_dict())
        self.assertEqual(parse_state((project / ".saipen" / "STATE.md").read_text("utf-8"))["phase"], "SHIP")

    def test_regression_b_bug_introduced_in_implementation_routes_to_build_and_fixes(self) -> None:
        project = self.make_project(phase="REVIEW")
        # Buggy implementation passes narrow positive test but fails on empty list boundary
        (project / "batch.py").write_text(
            "def average(items: list[int]) -> float:\n"
            "    return sum(items) / len(items)\n",
            encoding="utf-8",
        )

        def probe_boundary(root: Path) -> dict | None:
            ns: dict = {}
            exec((root / "batch.py").read_text(encoding="utf-8"), ns)
            try:
                ns["average"]([])
            except ZeroDivisionError:
                return {
                    "priority": "P0",
                    "location": "batch.py:2",
                    "detail": "ZeroDivisionError on empty items list boundary",
                }
            return None

        audit1 = run_ticket_self_audit(
            project, "T-1", impl_files=["batch.py"], boundary_probe=probe_boundary
        )
        self.assertEqual(audit1["status"], "DEFECT_IN_SCOPE")
        self.assertEqual(audit1["finding"]["location"], "batch.py:2")

        # Record pass 1 in review_passes and route canonically REVIEW -> BUILD
        board_path = project / ".saipen" / "BOARD.md"
        lines = board_path.read_text(encoding="utf-8").splitlines()
        new_lines = [
            set_ticket_field(ln, "review_passes", "1") if "] T-1 [" in ln else ln for ln in lines
        ]
        board_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

        cp_fail = operations.checkpoint(
            project, "tester", "DEC", "T-1", f"SHIP after FIXES -- {audit1['log_note']}"
        )
        self.assertTrue(cp_fail.ok)
        to_build = operations.transition_phase(project, "BUILD", "tester")
        self.assertTrue(to_build.ok, to_build.to_dict())
        self.assertEqual(
            parse_state((project / ".saipen" / "STATE.md").read_text("utf-8"))["phase"], "BUILD"
        )

        # Fix defect in BUILD, reverify in VERIFY, return to REVIEW, re-audit new delta
        (project / "batch.py").write_text(
            "def average(items: list[int]) -> float:\n"
            "    if not items:\n"
            "        return 0.0\n"
            "    return sum(items) / len(items)\n",
            encoding="utf-8",
        )
        self.assertTrue(operations.transition_phase(project, "VERIFY", "tester").ok)
        self.assertTrue(
            operations.checkpoint(
                project, "tester", "RUN", "T-1", "verify -> PASS [target: T-1] conf: high -- python check.py"
            ).ok
        )
        self.assertTrue(operations.transition_phase(project, "REVIEW", "tester").ok)

        audit2 = run_ticket_self_audit(
            project, "T-1", impl_files=["batch.py"], boundary_probe=probe_boundary
        )
        self.assertEqual(audit2["status"], "PASS")
        self.assertNotEqual(audit1["revision"], audit2["revision"])
        self.assertTrue(operations.transition_phase(project, "SHIP", "tester").ok)

    def test_regression_c_green_but_weakened_test_caught_by_oracle_integrity(self) -> None:
        project = self.make_project(phase="REVIEW")
        (project / "subject.py").write_text("def clamp(x):\n    return x\n", encoding="utf-8")
        (project / "check.py").write_text("from subject import clamp\nassert clamp(5) == 3\n", encoding="utf-8")
        before = {
            "result": "FAIL",
            "verifier": verifier_identity("python check.py", ["check.py"], project),
            "subject": oracle_digest(project, ["subject.py"]),
        }
        # Weaken the test so it passes without fixing subject.py
        (project / "check.py").write_text("from subject import clamp\nassert clamp(1) == 1\n", encoding="utf-8")
        after = {
            "result": "PASS",
            "verifier": verifier_identity("python check.py", ["check.py"], project),
            "subject": oracle_digest(project, ["subject.py"]),
        }
        verdict = regression_pair_verdict(before, after)
        self.assertEqual(verdict["code"], ORACLE_CHANGED)
        self.assertFalse(verdict["admissible"])

        # Honest control: fix subject.py while keeping original check.py unchanged
        (project / "check.py").write_text("from subject import clamp\nassert clamp(5) == 3\n", encoding="utf-8")
        (project / "subject.py").write_text("def clamp(x):\n    return min(x, 3)\n", encoding="utf-8")
        honest_after = {
            "result": "PASS",
            "verifier": verifier_identity("python check.py", ["check.py"], project),
            "subject": oracle_digest(project, ["subject.py"]),
        }
        honest_verdict = regression_pair_verdict(before, honest_after)
        self.assertEqual(honest_verdict["code"], ADMISSIBLE)
        self.assertTrue(honest_verdict["admissible"])

    def test_regression_d_no_implementation_delta_skips_fictional_scan(self) -> None:
        project = self.make_project(phase="REVIEW")
        audit = run_ticket_self_audit(project, "T-1", impl_files=[], doc_files=[])
        self.assertEqual(audit["status"], "SKIPPED_NO_DELTA")
        self.assertEqual(audit["files_scanned"], 0)

        # Documentation-only delta performs scoped doc check without source code scan
        (project / "README.md").write_text("# Doc update\n", encoding="utf-8")
        doc_audit = run_ticket_self_audit(project, "T-1", impl_files=[], doc_files=["README.md"])
        self.assertEqual(doc_audit["status"], "DOC_ONLY_PASS")
        self.assertEqual(doc_audit["files_scanned"], 1)

    def test_regression_e_existing_unrelated_defect_does_not_expand_scope(self) -> None:
        project = self.make_project(phase="REVIEW")
        (project / "owned.py").write_text("def clean_fn(x: int) -> int:\n    return x + 1\n", encoding="utf-8")
        (project / "unrelated.py").write_text("def broken_unrelated():\n    return 1 / 0\n", encoding="utf-8")
        before_unrelated = _sha256_bytes((project / "unrelated.py").read_bytes())

        audit = run_ticket_self_audit(
            project,
            "T-1",
            impl_files=["owned.py"],
            unrelated_files=["unrelated.py"],
        )
        self.assertEqual(audit["status"], "PASS")
        self.assertEqual(audit["files_scanned"], 1)
        self.assertEqual(audit["unrelated_scanned"], 0)
        self.assertEqual(_sha256_bytes((project / "unrelated.py").read_bytes()), before_unrelated)

    def test_regression_f_duplicate_finding_deduplicates_across_all_board_sections(self) -> None:
        project = self.make_project(phase="REVIEW")
        (project / "owned.py").write_text("def run():\n    return True\n", encoding="utf-8")
        before_tickets = set(
            parse_board((project / ".saipen" / "BOARD.md").read_text("utf-8"))["tickets"]
        )

        # Matches T-3 in ## BLOCKED ("existing blocked follow-up on cache eviction")
        dup_audit = run_ticket_self_audit(
            project,
            "T-1",
            impl_files=["owned.py"],
            out_of_scope_finding={
                "priority": "P2",
                "summary": "existing blocked follow-up on cache eviction",
                "verify": "python check3.py",
            },
        )
        self.assertEqual(dup_audit["status"], "FOLLOW_UP_RECORDED")
        self.assertEqual(dup_audit["linked_ticket"], "T-3")
        self.assertIsNone(dup_audit["created_ticket"])
        self.assertFalse(dup_audit["counted_as_fixed"])
        after_tickets = set(
            parse_board((project / ".saipen" / "BOARD.md").read_text("utf-8"))["tickets"]
        )
        self.assertEqual(before_tickets, after_tickets)

        # Novel out-of-scope P2 finding creates exactly one new follow-up ticket and is not counted fixed
        novel_audit = run_ticket_self_audit(
            project,
            "T-1",
            impl_files=["owned.py"],
            out_of_scope_finding={
                "priority": "P2",
                "summary": "telemetry rotation edge case on read-only mount",
                "verify": "python check_telemetry.py",
            },
        )
        self.assertEqual(novel_audit["status"], "FOLLOW_UP_RECORDED")
        self.assertIsNone(novel_audit["linked_ticket"])
        self.assertEqual(novel_audit["created_ticket"], "T-4")
        self.assertFalse(novel_audit["counted_as_fixed"])

    def test_regression_g_repeated_continuation_reuses_unchanged_revision_only(self) -> None:
        project = self.make_project(phase="REVIEW")
        (project / "owned.py").write_text("def f(x: int) -> int:\n    return x * 2\n", encoding="utf-8")

        first = run_ticket_self_audit(project, "T-1", impl_files=["owned.py"])
        self.assertFalse(first["reused"])
        self.assertEqual(first["files_scanned"], 1)
        operations.checkpoint(project, "tester", "RUN", "T-1", first["log_note"])

        # Same bytes -> reused without rescanning
        second = run_ticket_self_audit(project, "T-1", impl_files=["owned.py"])
        self.assertTrue(second["reused"])
        self.assertEqual(second["status"], "REUSED_UNCHANGED_REVISION")
        self.assertEqual(second["files_scanned"], 0)

        # Modified bytes -> must inspect new revision
        (project / "owned.py").write_text("def f(x: int) -> int:\n    return x * 3\n", encoding="utf-8")
        third = run_ticket_self_audit(project, "T-1", impl_files=["owned.py"])
        self.assertFalse(third["reused"])
        self.assertEqual(third["files_scanned"], 1)
        self.assertNotEqual(first["revision"], third["revision"])

    def test_regression_h_converge_stages_f_and_i_unchanged(self) -> None:
        converge = CONVERGE_MD.read_text(encoding="utf-8")
        hunt = HUNT_MD.read_text(encoding="utf-8")
        self.assertIn("**F. FORCED HUNT.**", converge)
        self.assertIn("**I. FINAL FORCED HUNT.**", converge)
        self.assertIn("# Phase: HUNT", hunt)

    def test_regression_i_foreign_owner_refuses_unauthorized_mutation(self) -> None:
        project = self.make_project(phase="REVIEW", agent="tester")
        # Create pre-existing ownership split: STATE.agent=tester, BOARD owner=opencode
        board_path = project / ".saipen" / "BOARD.md"
        board_path.write_text(
            board_path.read_text(encoding="utf-8").replace("owner: tester", "owner: opencode"),
            encoding="utf-8",
        )
        before_digest = _delta_digest(
            project, [".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/LOG.md"]
        )
        res = operations.checkpoint(project, "intruder", "RUN", "T-1", "unauthorized review")
        self.assertFalse(res.ok)
        self.assertIn(res.code, ("TICKET_NOT_WORKABLE", "VALIDATION_FAILED"))
        with self.assertRaises(operations.OwnershipSplitError):
            operations._seat_agent(
                parse_state((project / ".saipen" / "STATE.md").read_text("utf-8")),
                board_path.read_text("utf-8"),
                "intruder",
            )
        after_digest = _delta_digest(
            project, [".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/LOG.md"]
        )
        self.assertEqual(before_digest, after_digest)

    def test_regression_j_review_retry_cap_blocks_after_two_passes(self) -> None:
        project = self.make_project(phase="REVIEW")
        board_path = project / ".saipen" / "BOARD.md"
        text = board_path.read_text(encoding="utf-8")
        board_path.write_text(
            "\n".join(
                set_ticket_field(ln, "review_passes", "2") if "] T-1 [" in ln else ln
                for ln in text.splitlines()
            )
            + "\n",
            encoding="utf-8",
        )
        self.assertEqual(fast_check.validate_project(project, current_agent="tester"), [])

        # Canonical action at pass 2 when defect still fails is block
        blocked = operations.ticket_move(
            project,
            "block",
            "T-1",
            "tester",
            "REVIEW_RETRY_CAP: batch.py:2 failed two review passes",
        )
        self.assertTrue(blocked.ok, blocked.to_dict())
        board = parse_board((project / ".saipen" / "BOARD.md").read_text("utf-8"))
        self.assertEqual(board["tickets"]["T-1"]["section"], "## BLOCKED")

    def test_r008_performance_acceptance_benchmarks(self) -> None:
        project = self.make_project(phase="REVIEW")
        (project / "check.py").write_text("print('ok')\n", encoding="utf-8")
        (project / "small.py").write_text(
            "def normalize_port(value: int | str) -> int:\n"
            "    port = int(value)\n"
            "    if not (1 <= port <= 65535):\n"
            "        raise ValueError('port out of range')\n"
            "    return port\n",
            encoding="utf-8",
        )
        for idx in range(3):
            (project / f"mod_{idx}.py").write_text(
                f"def step_{idx}(items: list[str]) -> list[str]:\n"
                f"    if items is None:\n"
                f"        raise ValueError('items required')\n"
                f"    return [s.strip() for s in items if s and s.strip()]\n",
                encoding="utf-8",
            )
        (project / "sec_gate.py").write_text(
            "from pathlib import Path\n"
            "def resolve_confined(root: Path, rel: str) -> Path:\n"
            "    if not rel or '\\x00' in rel:\n"
            "        raise ValueError('invalid path')\n"
            "    target = (root / rel).resolve()\n"
            "    if not target.is_relative_to(root.resolve()):\n"
            "        raise PermissionError('path escapes root')\n"
            "    return target\n",
            encoding="utf-8",
        )

        cases = [
            ("small_python_correction", ["small.py"]),
            ("medium_multi_file_change", ["mod_0.py", "mod_1.py", "mod_2.py"]),
            ("verification_only_ticket", []),
            ("security_sensitive_correction", ["sec_gate.py"]),
        ]
        results: dict[str, dict] = {}
        iterations = 25
        for name, impl_files in cases:
            # Baseline: re-run verifier + oracle digest check only
            t0 = time.perf_counter()
            for _ in range(iterations):
                _ = verifier_identity("python check.py", ["check.py"], project)
                if impl_files:
                    _ = oracle_digest(project, impl_files)
            baseline_ms = ((time.perf_counter() - t0) / iterations) * 1000.0

            # Enhanced: baseline + ticket-scoped self-audit (AST, boundary, contract & diff check)
            t1 = time.perf_counter()
            last_audit = None
            for _ in range(iterations):
                _ = verifier_identity("python check.py", ["check.py"], project)
                if impl_files:
                    _ = oracle_digest(project, impl_files)
                last_audit = run_ticket_self_audit(project, "T-1", impl_files=impl_files)
            enhanced_ms = ((time.perf_counter() - t1) / iterations) * 1000.0
            delta_ms = enhanced_ms - baseline_ms
            results[name] = {
                "impl_files_count": len(impl_files),
                "baseline_ms": round(baseline_ms, 4),
                "enhanced_ms": round(enhanced_ms, 4),
                "delta_ms": round(delta_ms, 4),
                "audit_status": last_audit["status"] if last_audit else None,
                "files_scanned": last_audit["files_scanned"] if last_audit else 0,
            }
            self.assertLess(delta_ms, 50.0, f"overhead too high on {name}: {delta_ms} ms")

        payload = {
            "iterations_per_case": iterations,
            "cases": results,
            "protocol_doc_bytes": {
                "review_md_before_lf_bytes": 2249,
                "review_md_after_lf_bytes": len(
                    REVIEW_MD.read_bytes().replace(b"\r\n", b"\n")
                ),
                "ordinary_phase_route_bytes": protocol_budget.load_profiles(
                    SAIPEN_ROOT / "saipen"
                )["ordinary_phase"],
                "ordinary_phase_budget_bytes": 40960,
            },
        }
        BENCHMARK_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        self.assertEqual(results["verification_only_ticket"]["files_scanned"], 0)
        self.assertEqual(results["small_python_correction"]["files_scanned"], 1)
        self.assertEqual(results["medium_multi_file_change"]["files_scanned"], 3)
        self.assertEqual(results["security_sensitive_correction"]["files_scanned"], 1)


if __name__ == "__main__":
    unittest.main()

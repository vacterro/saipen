"""The audit harness's own fixtures must survive the journal checks (T-1561).

`audit_checks.warn_ownership_probe` hand-files a fixture ticket, and its
allocation event is appended as the NEWEST line of a copied tree that carries
this checkout's whole settled ledger -- so it sits above every provenance
floor and is judged like a fresh structural event, not history. The old
`alloc-<32 zeros>` op id named a class no writer emits (`journal.OP_CLASSES`)
and no operation record, so validate.py's T-1577 and T-1282 checks failed the
probe's CONTROL leg on the fixture's own line before warn ownership was ever
measured. The fix has two halves, both pinned here:

- ALLOCATION. The fixture's op id is on-grammar (`ticket-<32 hex>`, a
  registered writer class) and resolves to a synthetic committed record filed
  under the copy's own settled dir, in the shape `resolvable_op_ids`
  enumerates. The id is derived from the ticket id, so the same fixture
  always mints the same record.
- HONEST SKIP. A host without the symlink privilege (WinError 1314 and its
  POSIX spellings) cannot CONSTRUCT `symlink_restore_probe`'s red control at
  all. That lack is a property of the host, not of the restoration code, so
  the narrow capability refusal raises `ProbeUnproven` and `run_probes`
  reports a loud UNPROVEN verdict. Every other construction error stays FAIL,
  and a control that ran and broke still fails the run.
"""

from __future__ import annotations

import errno
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import audit_checks  # noqa: E402
from saipen_engine.journal import (  # noqa: E402
    op_id_provenance,
    resolvable_op_ids,
)

#: The id shape that broke the control leg: a class no writer registers, over
#: 32 zero hex -- a bracket, not an operation. The grammar contract the
#: fixture must satisfy is red-pinned through the same oracle the fixture now
#: consults (`op_id_provenance`).
OLD_ALLOC_ID = "alloc-" + "0" * 32

LOG_LINE = (
    "- 01.10.26 09:00 [E-11095] [parent: E-11094] [T-901] "
    "[agent: saipen-cli] [op: checkpoint-0123456789abcdef0123456789abcdef] "
    "RUN: tail\n"
)


def minimal_tree(root: Path) -> Path:
    """A copied tree reduced to the parts `journal_probe_allocation` touches."""
    log = root / ".saipen" / "LOG.md"
    log.parent.mkdir(parents=True)
    log.write_text(LOG_LINE, encoding="utf-8", newline="\n")
    return root


def allocated_op_id(tree: Path) -> str:
    text = (tree / ".saipen" / "LOG.md").read_text(encoding="utf-8")
    match = re.search(r"\[op: (ticket-[0-9a-f]{32})\]", text)
    assert match, "the allocation line must carry the minted op id"
    return match.group(1)


class AllocationProvenance(unittest.TestCase):
    """The fixture's own journal line passes both checks that broke it."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="t1561_alloc_")
        self.tree = minimal_tree(Path(self._tmp.name))
        self.error = audit_checks.journal_probe_allocation(
            self.tree, audit_checks.WARN_PROBE_TICKET
        )
        self.assertIsNone(self.error)

    def tearDown(self):
        self._tmp.cleanup()

    def test_op_id_is_canonical_grammar(self):
        self.assertEqual(op_id_provenance(allocated_op_id(self.tree)), "canonical")

    def test_old_alloc_shape_stays_hand_authored(self):
        """Red carrier: the shape that broke the control leg still reads as
        hand-authored under the same oracle, so this test cannot pass by the
        grammar loosening."""
        self.assertEqual(op_id_provenance(OLD_ALLOC_ID), "hand_authored")

    def test_op_id_resolves_to_a_committed_record(self):
        op_id = allocated_op_id(self.tree)
        self.assertIn(op_id, resolvable_op_ids(self.tree))
        record = json.loads(
            (self.tree / ".saipen" / "recovery" / "settled" / op_id / "operation.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(record["status"], "COMMITTED")
        self.assertEqual(record["op_id"], op_id)

    def test_op_id_is_deterministic_per_ticket(self):
        with tempfile.TemporaryDirectory(prefix="t1561_alloc2_") as other:
            second = minimal_tree(Path(other))
            self.assertIsNone(
                audit_checks.journal_probe_allocation(
                    second, audit_checks.WARN_PROBE_TICKET
                )
            )
            self.assertEqual(allocated_op_id(self.tree), allocated_op_id(second))

    def test_event_continues_the_history(self):
        text = (self.tree / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        self.assertIn("[E-11096] [parent: E-11095] [T-990]", text)


class SymlinkCapabilityRefusal(unittest.TestCase):
    """Only the narrow capability refusals skip; everything else stays FAIL."""

    def test_1314_is_a_capability_refusal(self):
        exc = OSError(errno.EPERM, "A required privilege is not held by the client")
        exc.winerror = 1314
        self.assertTrue(audit_checks._is_symlink_capability_refusal(exc))

    def test_posix_privilege_errnos_are_capability_refusals(self):
        for code in (errno.EPERM, errno.EACCES, errno.ENOSYS):
            with self.subTest(errno=code):
                self.assertTrue(
                    audit_checks._is_symlink_capability_refusal(OSError(code, "refused"))
                )

    def test_not_implemented_is_a_capability_refusal(self):
        self.assertTrue(
            audit_checks._is_symlink_capability_refusal(NotImplementedError())
        )

    def test_an_unrelated_oserror_is_not_a_capability_refusal(self):
        """Red carrier: a broken temp dir or a damaged path must stay FAIL."""
        self.assertFalse(
            audit_checks._is_symlink_capability_refusal(OSError(errno.ENOENT, "gone"))
        )
        self.assertFalse(audit_checks._is_symlink_capability_refusal(ValueError("x")))

    def test_privilege_refusal_raises_probe_unproven(self):
        def refuse(_target, _link):
            raise OSError(errno.EPERM, "A required privilege is not held by the client")

        real = os.symlink
        os.symlink = refuse
        try:
            with tempfile.TemporaryDirectory(prefix="t1561_sym_") as td, \
                    self.assertRaises(audit_checks.ProbeUnproven):
                audit_checks.symlink_restore_probe(Path(td))
        finally:
            os.symlink = real

    def test_other_construction_errors_stay_failures(self):
        def broken(_target, _link):
            raise OSError(errno.ENOENT, "a damaged path, not a missing privilege")

        real = os.symlink
        os.symlink = broken
        try:
            with tempfile.TemporaryDirectory(prefix="t1561_sym2_") as td:
                error = audit_checks.symlink_restore_probe(Path(td))
        finally:
            os.symlink = real
        self.assertIsInstance(error, str)
        self.assertIn("cannot construct symlink red control", error)


class UnprovenVerdictProtocol(unittest.TestCase):
    """`run_probes` reports UNPROVEN loudly without softening a real FAIL."""

    def _run(self, probes):
        lines: list[str] = []
        with tempfile.TemporaryDirectory(prefix="t1561_proto_") as tmp:
            verdicts = audit_checks.run_probes(
                probes,
                audit_checks.ProbeContext(Path(tmp), list(audit_checks.CASES), None),
                out=lines.append,
            )
        return verdicts, lines

    def test_unproven_probe_gets_its_own_verdict_and_line(self):
        def refuse(_ctx):
            raise audit_checks.ProbeUnproven("host cannot create a symlink")

        probes = (
            audit_checks.Probe("unproven-one", refuse, "never seen"),
            audit_checks.Probe("pass-one", lambda _ctx: None, "passed"),
        )
        verdicts, lines = self._run(probes)
        self.assertEqual(verdicts, {"unproven-one": "UNPROVEN", "pass-one": "PASS"})
        self.assertTrue(
            any(ln.startswith("UNPROVEN: unproven-one -- ") for ln in lines),
            lines,
        )

    def test_a_raised_probe_unproven_does_not_mask_a_real_failure(self):
        def refuse(_ctx):
            raise audit_checks.ProbeUnproven("no privilege here")

        def explode(_ctx):
            raise RuntimeError("the control itself broke")

        probes = (
            audit_checks.Probe("skip-me", refuse, "never seen"),
            audit_checks.Probe("broken", explode, "never seen either"),
        )
        verdicts, lines = self._run(probes)
        self.assertEqual(
            verdicts, {"skip-me": "UNPROVEN", "broken": "FAIL"}, verdicts
        )
        self.assertTrue(
            any(ln.startswith("FAIL: broken -- RuntimeError:") for ln in lines),
            lines,
        )

    def test_a_later_probe_does_not_depend_on_an_unproven_one(self):
        """UNPROVEN is not PASS: a dependent probe is SKIP-named, loud."""
        def refuse(_ctx):
            raise audit_checks.ProbeUnproven("no privilege here")

        probes = (
            audit_checks.Probe("unproven-root", refuse, "never seen"),
            audit_checks.Probe(
                "dependent", lambda _ctx: None, "passed", requires=("unproven-root",)
            ),
        )
        verdicts, lines = self._run(probes)
        self.assertEqual(
            verdicts, {"unproven-root": "UNPROVEN", "dependent": "SKIP"}, verdicts
        )
        skip_line = "SKIP: dependent because prerequisite unproven-root"
        self.assertTrue(any(ln.startswith(skip_line) for ln in lines), lines)


if __name__ == "__main__":
    unittest.main()

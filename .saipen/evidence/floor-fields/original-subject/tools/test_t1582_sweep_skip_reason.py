"""T-1582: a host that cannot create symlinks must not be told to hunt for a
missing file.

The mutation sweep reported one fixed SKIP sentence for every case it could
not run, so a Windows host without SeCreateSymbolicLinkPrivilege was told its
IDENTITY.md was missing or its anchor had moved. The file was sitting right
there; the host simply cannot construct the control. `apply_case` now carries
the capability refusal out as a reason, and `skip_line` prints it.

Both wordings are asserted here, and the second one is the red control: a case
whose anchor really did move keeps the missing-file wording.
"""

import errno
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import audit_checks  # noqa: E402


class SkipLineWordingTests(unittest.TestCase):
    """The two verdicts must stay distinguishable in the output text."""

    def test_capability_refusal_is_named(self):
        reason = (
            "this host cannot create a symlink, so the case was never "
            "constructed (a host capability, not a missing file): [WinError 1314]"
        )
        line = audit_checks.skip_line("portable project identity", reason)
        self.assertIn("cannot create a symlink", line)
        self.assertIn("1314", line)
        self.assertNotIn("its anchor text is", line)

    def test_moved_anchor_keeps_the_missing_file_wording(self):
        # RED CONTROL: this is the pre-existing wording, and it must survive.
        # Without it, the fix would silence a real diagnostic.
        line = audit_checks.skip_line("LOG chronology inverted", None)
        self.assertIn("the file is missing, or its anchor text is", line)
        self.assertNotIn("cannot create a symlink", line)


class ApplyCaseReasonTests(unittest.TestCase):
    """`apply_case` must separate a capability refusal from a missing file."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "tree"
        (self.root / "sub").mkdir(parents=True)
        self.rel = "sub/IDENTITY.md"
        (self.root / self.rel).write_bytes(b"original authority\n")
        self.addCleanup(self._tmp.cleanup)

    def _refuse(self, exc):
        return mock.patch.object(audit_checks.os, "symlink", side_effect=exc)

    def test_capability_refusal_returns_a_reason(self):
        exc = OSError(errno.EPERM, "refused")
        exc.winerror = 1314
        with self._refuse(exc):
            result = audit_checks.apply_case(self.root, self.rel, audit_checks.SYMLINK_EXTERNAL)
        self.assertIsInstance(result, str)
        self.assertIn("cannot create a symlink", result)

    def test_reason_reuses_the_canonical_capability_test(self):
        # The sweep must agree with the probe about what a capability refusal
        # is, or the two disagree on the same host.
        refusal = OSError(errno.EPERM, "refused")
        refusal.winerror = 1314
        other = OSError(errno.ENOENT, "gone")
        with self._refuse(refusal):
            reason = audit_checks.apply_case(
                self.root, self.rel, audit_checks.SYMLINK_EXTERNAL
            )
        with self._refuse(other):
            plain = audit_checks.apply_case(
                self.root, self.rel, audit_checks.SYMLINK_EXTERNAL
            )
        self.assertTrue(audit_checks._is_symlink_capability_refusal(refusal))
        self.assertIsInstance(reason, str)
        self.assertIs(plain, False)
        self.assertNotIsInstance(plain, str)

    def test_missing_target_stays_a_bare_false(self):
        # The missing file is not a capability problem and keeps the old,
        # file-shaped verdict.
        result = audit_checks.apply_case(
            self.root, "sub/ABSENT.md", audit_checks.SYMLINK_EXTERNAL
        )
        self.assertIs(result, False)

    def test_real_symlink_still_applies(self):
        try:
            audit_checks.apply_case(self.root, self.rel, audit_checks.SYMLINK_EXTERNAL)
        except Exception:  # pragma: no cover - host without the privilege
            self.skipTest("host cannot create symlinks")
        if not os.path.islink(self.root / self.rel):
            self.skipTest("host cannot create symlinks")
        self.assertTrue(os.path.islink(self.root / self.rel))

    def test_no_op_mutation_still_returns_false(self):
        # The only other caller of apply_case passes a lambda and checks
        # falsiness; a reason string must not reach it.
        (self.root / "sub" / "plain.md").write_text("x\n", encoding="utf-8")
        result = audit_checks.apply_case(
            self.root, "sub/plain.md", lambda text: text
        )
        self.assertIs(result, False)



class ActualSweepCapabilityTests(unittest.TestCase):
    """Exercise the actual worker, restoration and probe verdict routing."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="saipen-sweep-capability-")
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name)
        self.source = self.tmp / "pristine"
        self.source.mkdir()
        (self.source / "IDENTITY.md").write_bytes(b"authority\n")
        (self.source / "plain.txt").write_bytes(b"good\n")
        self.link_case = (
            "portable project identity", "IDENTITY.md", audit_checks.SYMLINK_EXTERNAL,
            "identity symlink refused",
        )
        self.dead_case = (
            "genuine missing anchor", "plain.txt", lambda text: text,
            "missing anchor finding",
        )
        self.red_case = (
            "ordinary red control", "plain.txt", lambda text: text.replace("good", "bad"),
            "ordinary finding",
        )

    def run_sweep(self, cases, *, refusal=True, report_red=True):
        context = audit_checks.ProbeContext(self.tmp, cases, None)
        context.pristine = self.source
        context.control = ""
        lines = []

        def validate(root, gate=None):
            identity = root / "IDENTITY.md"
            if identity.is_file() and identity.read_bytes() == b"synthetic symlink\n":
                return "FAIL: identity symlink refused"
            if report_red and (root / "plain.txt").read_bytes() == b"bad\n":
                return "FAIL: ordinary finding"
            return ""

        exc = OSError(errno.EPERM, "symlink privilege unavailable")
        exc.winerror = 1314

        def construct(external, target):
            Path(target).write_bytes(b"synthetic symlink\n")

        probe = audit_checks.Probe(
            "sweep", audit_checks.mutation_sweep_probe, "all controls constructed and proven"
        )
        construct_link = mock.patch.object(
            audit_checks.os, "symlink", side_effect=exc if refusal else construct
        )
        validate_output = mock.patch.object(audit_checks, "validator_output", side_effect=validate)
        with construct_link, validate_output:
            verdict = audit_checks.run_probes((probe,), context, out=lines.append)
        self.assertEqual((self.source / "IDENTITY.md").read_bytes(), b"authority\n")
        self.assertEqual((self.source / "plain.txt").read_bytes(), b"good\n")
        return verdict["sweep"], "\n".join(lines)

    def test_capability_reason_reaches_skip_and_unproven_runner(self):
        verdict, text = self.run_sweep([self.link_case])
        self.assertEqual(verdict, "UNPROVEN", text)
        self.assertIn("SKIP: portable project identity -- this host cannot create a symlink", text)
        self.assertIn("1314", text)
        self.assertNotIn("the validator did not report", text)
        self.assertNotIn(audit_checks.FULL_SWEEP_PHRASE, text)

    def test_other_controls_continue_but_missing_capability_is_never_pass(self):
        verdict, text = self.run_sweep([self.link_case, self.red_case])
        self.assertEqual(verdict, "UNPROVEN", text)
        self.assertIn("PROVEN: 1 of 2", text)
        self.assertIn("broken: 0", text)

    def test_a_real_missing_anchor_still_fails_alongside_host_absence(self):
        verdict, text = self.run_sweep([self.link_case, self.dead_case])
        self.assertEqual(verdict, "FAIL", text)
        self.assertIn("its anchor text is", text)
        self.assertIn("1 of 2 mutation control(s) no longer prove anything", text)
        self.assertIn("cannot create a symlink", text)

    def test_a_constructed_dead_control_is_not_softened_by_host_absence(self):
        verdict, text = self.run_sweep([self.link_case, self.red_case], report_red=False)
        self.assertEqual(verdict, "FAIL", text)
        self.assertIn("FAIL: ordinary red control", text)

    def test_constructed_control_still_requires_the_validator_finding(self):
        verdict, text = self.run_sweep([self.link_case], refusal=False)
        self.assertEqual(verdict, "PASS", text)
        self.assertIn(audit_checks.FULL_SWEEP_PHRASE, text)
        self.assertNotIn("UNPROVEN", text)

    def test_real_missing_anchor_alone_still_uses_generic_skip_and_fail(self):
        verdict, text = self.run_sweep([self.dead_case])
        self.assertEqual(verdict, "FAIL", text)
        self.assertIn("its anchor text is", text)
        self.assertNotIn("cannot create a symlink", text)


class ParityClassificationTests(unittest.TestCase):
    """`audit_parity` consumes the same `apply_case` contract.

    T-1582 made `apply_case` return a truthy REASON STRING for a host that
    cannot construct a case. `audit_parity` tested truthiness, so it counted
    an unconstructed mutation as applied and credited the portable floor
    with catching a defect that was never planted -- a false pass.

    `run_chunk` is a closure inside `audit_parity.main` and running it means
    spawning the floor for every case, so the predicate is pinned here
    against the real `apply_case` return values, and the call site's
    predicate is pinned by source so the two cannot drift apart again.
    """

    def _refused(self):
        exc = OSError(errno.EPERM, "symlink privilege unavailable")
        exc.winerror = 1314
        return exc

    def test_a_reason_string_is_truthy_so_truthiness_would_misclassify_it(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "tree"
            root.mkdir()
            (root / "IDENTITY.md").write_bytes(b"authority\n")
            with mock.patch.object(audit_checks.os, "symlink", side_effect=self._refused()):
                result = audit_checks.apply_case(
                    root, "IDENTITY.md", audit_checks.SYMLINK_EXTERNAL
                )
        # The whole defect: `not result` is False for an unconstructed case.
        self.assertIsInstance(result, str)
        self.assertTrue(result)
        self.assertFalse(not result)
        self.assertIs(result is not True, True)

    def test_parity_call_site_tests_identity_not_truthiness(self):
        source = (ROOT / "tools" / "audit_parity.py").read_text(encoding="utf-8")
        self.assertIn("is not True", source)
        self.assertNotIn("not ac.apply_case(", source)


if __name__ == "__main__":
    unittest.main()

"""T-1655: a file the engine replaces keeps the access it had.

`paths.safe_atomic_write_bytes` writes a temporary created owner-only (0600)
and replaces the target with it. On a POSIX host every replaced file therefore
ended 0600 whatever it had been: a script XPATCH patched or restored lost its
execute bit, and a file other accounts read became owner-only. One caller
(`project_block.repair`, T-1654) restored the mode by hand; the other
thirty-five did not.

The helper now carries the nine permission bits of the file it replaces onto
the temporary, through the open descriptor, so every caller gets it.

What this module can and cannot show depends on the host. The DECISION (which
bits travel) and the WIRING (they are set on the descriptor, before the
replace, and the witnessed stat follows) are tested everywhere. The cases on a
REAL file need a host with permission bits and are skipped where there are
none -- on Windows `os.name` is `nt`, and a skipped case there is not a pass.
"""

from __future__ import annotations

import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import paths, xpatch  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_xpatch import T1, T2, XPatchCase  # noqa: E402

POSIX = os.name == "posix"


def setUpModule() -> None:
    isolate_host_session()


def _stat(mode: int) -> os.stat_result:
    """A stat result carrying `mode` and nothing else that matters here."""
    return os.stat_result((mode, 1, 1, 1, 0, 0, 0, 0, 0, 0))


class DecisionTests(unittest.TestCase):
    """Which bits travel -- a pure function, the same answer on every host."""

    def test_the_replaced_file_gives_its_permission_bits(self):
        created = _stat(stat.S_IFREG | 0o600)
        for before, want in ((0o755, 0o755), (0o644, 0o644), (0o640, 0o640), (0o444, 0o444)):
            with self.subTest(oct(before)):
                self.assertEqual(
                    paths._mode_to_carry(_stat(stat.S_IFREG | before), created), want
                )

    def test_a_new_file_keeps_the_owner_only_default(self):
        self.assertIsNone(paths._mode_to_carry(None, _stat(stat.S_IFREG | 0o600)))

    def test_bits_that_already_agree_need_no_call(self):
        same = _stat(stat.S_IFREG | 0o600)
        self.assertIsNone(paths._mode_to_carry(same, same))
        both = _stat(stat.S_IFREG | 0o666)
        self.assertIsNone(paths._mode_to_carry(both, both), "the shape of a Windows host")

    def test_set_id_and_sticky_bits_never_travel(self):
        created = _stat(stat.S_IFREG | 0o600)
        for special in (stat.S_ISUID, stat.S_ISGID, stat.S_ISVTX):
            with self.subTest(oct(special)):
                before = _stat(stat.S_IFREG | special | 0o755)
                self.assertEqual(paths._mode_to_carry(before, created), 0o755)
        only_special = _stat(stat.S_IFREG | stat.S_ISUID | 0o600)
        self.assertIsNone(paths._mode_to_carry(only_special, created))


class WiringTests(unittest.TestCase):
    """The helper sets the decided bits on the descriptor before the replace."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.target = Path(tmp.name).resolve() / "script.sh"

    def write(self, data: bytes, *, decision):
        """One helper call with the decision forced and `os.fchmod` recorded."""
        calls: list[tuple] = []

        def fchmod(descriptor: int, mode: int) -> None:
            # Recorded while the descriptor is OPEN: a closed one raises here.
            calls.append((os.fstat(descriptor).st_size, mode, self.target.exists()))

        with mock.patch.object(paths, "_mode_to_carry", side_effect=decision) as decided, \
                mock.patch.object(paths.os, "fchmod", fchmod, create=True):
            paths.safe_atomic_write_bytes(self.target, data, kind="test target")
        return calls, decided

    def test_a_replaced_file_gets_one_fchmod_on_the_written_temporary(self):
        self.target.write_bytes(b"#!/bin/sh\nold\n")
        calls, decided = self.write(b"#!/bin/sh\nnew\n", decision=lambda before, created: 0o755)
        self.assertEqual(self.target.read_bytes(), b"#!/bin/sh\nnew\n")
        self.assertEqual(calls, [(len(b"#!/bin/sh\nnew\n"), 0o755, True)])
        before, created = decided.call_args.args
        self.assertIsNotNone(before, "the stat of the file being replaced")
        self.assertTrue(stat.S_ISREG(created.st_mode))

    def test_no_decision_no_call(self):
        self.target.write_bytes(b"old\n")
        calls, _decided = self.write(b"new\n", decision=lambda before, created: None)
        self.assertEqual((calls, self.target.read_bytes()), ([], b"new\n"))

    def test_a_new_file_is_asked_with_nothing_to_replace(self):
        calls, decided = self.write(b"fresh\n", decision=paths._mode_to_carry)
        self.assertEqual((calls, self.target.read_bytes()), ([], b"fresh\n"))
        self.assertIsNone(decided.call_args.args[0])

    def test_a_host_without_fchmod_writes_as_before(self):
        self.target.write_bytes(b"old\n")
        with mock.patch.object(paths, "_mode_to_carry", return_value=0o755), \
                mock.patch.object(paths.os, "fchmod", None, create=True):
            paths.safe_atomic_write_bytes(self.target, b"new\n", kind="test target")
        self.assertEqual(self.target.read_bytes(), b"new\n")

    def test_the_witnessed_temporary_follows_the_mode_it_was_given(self):
        """`_same_stat` compares the mode. A helper that set the bits and kept
        the stat it took at creation would refuse its own temporary."""
        self.target.write_bytes(b"old\n")
        # A stat no real temporary has: if the helper witnesses by what
        # `_carry_mode` returned, it must refuse its own temporary here.
        given = _stat(stat.S_IFREG | 0o755)
        with mock.patch.object(paths, "_carry_mode", return_value=given) as carried, \
                mock.patch.object(paths, "_same_stat", wraps=paths._same_stat) as same, \
                self.assertRaises(ValueError) as refused:
            paths.safe_atomic_write_bytes(self.target, b"new\n", kind="test target")
        self.assertIn("temporary", str(refused.exception))
        self.assertEqual(carried.call_count, 1)
        self.assertTrue(any(call.args[0] is given for call in same.call_args_list))
        self.assertEqual(self.target.read_bytes(), b"old\n", "a refused write replaces nothing")


@unittest.skipUnless(POSIX, "permission bits exist on a POSIX host only; not shown on this one")
class RealFileTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.target = Path(tmp.name).resolve() / "script.sh"

    def mode(self) -> int:
        return stat.S_IMODE(self.target.stat().st_mode)

    def test_a_replaced_file_keeps_its_mode(self):
        for wanted in (0o755, 0o644, 0o640, 0o600):
            with self.subTest(oct(wanted)):
                self.target.write_bytes(b"old\n")
                os.chmod(self.target, wanted)
                paths.safe_atomic_write_bytes(self.target, b"new\n", kind="test target")
                self.assertEqual((self.target.read_bytes(), self.mode()), (b"new\n", wanted))

    def test_a_new_file_is_owner_only(self):
        paths.safe_atomic_write_bytes(self.target, b"fresh\n", kind="test target")
        self.assertEqual(self.mode(), 0o600)

    def test_a_set_id_bit_is_not_carried_onto_new_bytes(self):
        self.target.write_bytes(b"old\n")
        os.chmod(self.target, 0o4755)
        paths.safe_atomic_write_bytes(self.target, b"new\n", kind="test target")
        self.assertEqual(self.mode(), 0o755)


@unittest.skipUnless(POSIX, "permission bits exist on a POSIX host only; not shown on this one")
class XPatchKeepsTheModeTests(XPatchCase):
    """The measured call sites: a patched and a restored product file."""

    def test_apply_then_revert_keeps_0755(self):
        product = self.root / "src" / "session.py"
        os.chmod(product, 0o755)
        patch_id = self.record()
        applied = xpatch.apply_proposal(self.root, patch_id, now=T1)
        self.assertEqual(applied["outcome"], xpatch.OUTCOME_APPLIED)
        self.assertEqual(
            (product.read_bytes(), stat.S_IMODE(product.stat().st_mode)), (b"new\n", 0o755)
        )
        reverted = xpatch.revert(self.root, patch_id, now=T2)
        self.assertEqual(reverted["outcome"], "REVERTED")
        self.assertEqual(
            (product.read_bytes(), stat.S_IMODE(product.stat().st_mode)), (b"old\n", 0o755)
        )


if __name__ == "__main__":
    unittest.main()

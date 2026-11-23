"""T-1648: a transient Windows lock on the replace target is a wait, not a CONFLICT.

On 06.10.26 five canonical writes in one session failed with
`[WinError 5] Access is denied` on the final `os.replace` of STATE.md or
LOG.md, because another process held the file without delete-sharing; each one
left a pending operation that only a manual `saipen recover` settled. CPython
itself opens a file that way, so the usual holder is another SAIPEN process: a
host hook, a status poll, a second session reading the same project memory.

The replace now waits that reader out by itself, so a caller that already
retried around the write (the autonomy lease writer) is bounded in time as
well: the two waits must never multiply.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import paths, watchdog  # noqa: E402

REAL_REPLACE = os.replace


def _locked(winerror: int = 5) -> PermissionError:
    exc = PermissionError(13, "Access is denied")
    exc.winerror = winerror
    return exc


class TransientClassifierTests(unittest.TestCase):
    """Which refusals are a wait. Decided from the error alone, on any host."""

    def test_the_two_sharing_codes_are_a_wait_on_windows(self):
        with mock.patch.object(paths.os, "name", "nt"):
            self.assertTrue(paths._transient_replace_error(_locked(5)))
            self.assertTrue(paths._transient_replace_error(_locked(32)))

    def test_any_other_code_is_a_verdict(self):
        with mock.patch.object(paths.os, "name", "nt"):
            self.assertFalse(paths._transient_replace_error(_locked(2)))
            self.assertFalse(paths._transient_replace_error(PermissionError(13, "denied")))
            # errno 22 keeps the base class: OSError(13, ...) would construct
            # a PermissionError by itself.
            plain = OSError(22, "Invalid argument")
            plain.winerror = 5
            self.assertNotIsInstance(plain, PermissionError)
            self.assertFalse(paths._transient_replace_error(plain))

    def test_nothing_is_a_wait_on_posix(self):
        with mock.patch.object(paths.os, "name", "posix"):
            self.assertFalse(paths._transient_replace_error(_locked(5)))
            self.assertFalse(paths._transient_replace_error(_locked(32)))


@unittest.skipUnless(os.name == "nt", "the retried codes are Windows sharing errors")
class TransientReplaceLockTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="saipen-t1648-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.target = self.root / "STATE.md"
        self.target.write_bytes(b"before\n")
        sleeper = mock.patch("time.sleep", lambda _s: None)
        sleeper.start()
        self.addCleanup(sleeper.stop)

    def _write(self, data: bytes = b"after\n") -> None:
        paths.safe_atomic_write_bytes(
            self.target, data, kind="test state", ownership_root=self.root
        )

    def _leftovers(self) -> list[str]:
        return [p.name for p in self.root.iterdir() if p.name.endswith(".tmp")]

    def test_a_real_reader_without_delete_sharing_is_waited_out(self):
        # Nothing is mocked on the replace: the operating system refuses it for
        # as long as this handle is open, and the write lands once it closes.
        reader = open(self.target, "rb")  # noqa: SIM115 -- held open on purpose
        self.addCleanup(reader.close)
        naps = []

        def nap(seconds):
            naps.append(seconds)
            if len(naps) == 2:
                reader.close()

        with mock.patch("time.sleep", nap):
            self._write()
        self.assertEqual(self.target.read_bytes(), b"after\n")
        self.assertEqual(len(naps), 2)
        self.assertEqual(self._leftovers(), [])

    def test_a_real_reader_that_never_lets_go_fails_with_the_os_error(self):
        reader = open(self.target, "rb")  # noqa: SIM115 -- held open on purpose
        self.addCleanup(reader.close)
        with self.assertRaises(PermissionError) as caught:
            self._write()
        self.assertEqual(caught.exception.winerror, 5)
        reader.close()
        self.assertEqual(self.target.read_bytes(), b"before\n")
        self.assertEqual(self._leftovers(), [])

    def test_a_lock_that_clears_is_waited_out(self):
        calls = []

        def replace(src, dst):
            calls.append(src)
            if len(calls) <= 2:
                raise _locked()
            return REAL_REPLACE(src, dst)

        with mock.patch.object(paths.os, "replace", replace):
            self._write()
        self.assertEqual(self.target.read_bytes(), b"after\n")
        self.assertEqual(len(calls), 3)
        self.assertEqual(self._leftovers(), [])

    def test_a_sharing_violation_is_the_same_wait(self):
        calls = []

        def replace(src, dst):
            calls.append(src)
            if len(calls) == 1:
                raise _locked(32)
            return REAL_REPLACE(src, dst)

        with mock.patch.object(paths.os, "replace", replace):
            self._write()
        self.assertEqual(self.target.read_bytes(), b"after\n")
        self.assertEqual(len(calls), 2)

    def test_a_lock_that_never_clears_still_fails_after_the_bound(self):
        calls = []
        refusal = _locked()

        def replace(src, dst):
            calls.append(src)
            raise refusal

        refused = mock.patch.object(paths.os, "replace", replace)
        with refused, self.assertRaises(PermissionError) as caught:
            self._write()
        self.assertIs(caught.exception, refusal)
        self.assertEqual(len(calls), paths._REPLACE_ATTEMPTS)
        self.assertEqual(self.target.read_bytes(), b"before\n")
        self.assertEqual(self._leftovers(), [])

    def test_the_wait_is_bounded_in_time(self):
        naps = []

        def replace(src, dst):
            raise _locked()

        refused = mock.patch.object(paths.os, "replace", replace)
        with refused, mock.patch("time.sleep", naps.append), self.assertRaises(PermissionError):
            self._write()
        self.assertEqual(len(naps), paths._REPLACE_ATTEMPTS - 1)
        self.assertLessEqual(sum(naps), 2.0)

    def test_a_target_swapped_between_attempts_is_refused(self):
        # The identity proof (`_same_stat`: device, inode, mode) runs before
        # every attempt. The original is moved aside, not deleted, so the two
        # files are alive together and cannot share an identity on any
        # filesystem; a content-level race is the journal's before/after hash,
        # unchanged by this ticket.
        calls = []

        def replace(src, dst):
            calls.append(src)
            if len(calls) == 1:
                REAL_REPLACE(self.target, self.root / "moved-aside")
                self.target.write_bytes(b"someone else\n")
                raise _locked()
            return REAL_REPLACE(src, dst)

        refused = mock.patch.object(paths.os, "replace", replace)
        with refused, self.assertRaises(ValueError):
            self._write()
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.target.read_bytes(), b"someone else\n")
        self.assertEqual(self._leftovers(), [])

    def test_a_target_removed_between_attempts_is_refused(self):
        calls = []

        def replace(src, dst):
            calls.append(src)
            if len(calls) == 1:
                self.target.unlink()
                raise _locked()
            return REAL_REPLACE(src, dst)

        refused = mock.patch.object(paths.os, "replace", replace)
        with refused, self.assertRaises(ValueError):
            self._write()
        self.assertEqual(len(calls), 1)
        self.assertFalse(self.target.exists())
        self.assertEqual(self._leftovers(), [])

    def test_any_other_error_is_not_retried(self):
        calls = []

        def replace(src, dst):
            calls.append(src)
            raise _locked(2)

        refused = mock.patch.object(paths.os, "replace", replace)
        with refused, self.assertRaises(PermissionError):
            self._write()
        self.assertEqual(len(calls), 1)
        self.assertEqual(self._leftovers(), [])


class NestedWaitTests(unittest.TestCase):
    """A retry around the write is bounded in time, not only in count."""

    def test_a_lease_write_that_stays_refused_costs_one_wait_not_fifty(self):
        # The write is modelled as it behaves when the file stays held: it
        # returns its refusal only after its own full wait.
        now = [100.0]
        calls = []

        def held_write():
            calls.append(now[0])
            now[0] += 1.83
            raise PermissionError(13, "Access is denied")

        clock = mock.patch("time.monotonic", lambda: now[0])
        with clock, mock.patch("time.sleep", lambda _s: None), self.assertRaises(PermissionError):
            watchdog._contended(held_write)
        self.assertEqual(len(calls), 1)

    def test_a_brief_race_is_still_retried(self):
        now = [100.0]
        calls = []

        def racing_read():
            calls.append(now[0])
            if len(calls) < 4:
                raise PermissionError(13, "sharing violation")
            return "lease"

        def nap(seconds):
            now[0] += seconds

        with mock.patch("time.monotonic", lambda: now[0]), mock.patch("time.sleep", nap):
            self.assertEqual(watchdog._contended(racing_read), "lease")
        self.assertEqual(len(calls), 4)

    def test_an_instant_refusal_is_still_bounded_by_the_count(self):
        calls = []

        def refused():
            calls.append(1)
            raise PermissionError(13, "sharing violation")

        frozen = mock.patch("time.monotonic", lambda: 100.0)
        with frozen, mock.patch("time.sleep", lambda _s: None), self.assertRaises(PermissionError):
            watchdog._contended(refused)
        self.assertEqual(len(calls), 50)


if __name__ == "__main__":
    unittest.main()

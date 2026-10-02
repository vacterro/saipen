"""The retired raw appender, and the scope of the validator's inversion amnesty.

`tools/_log_append.py` took a caller-formed line and appended it. A stamp guard
was bolted on after two ISO-order stamps (E-2068 `26.08.05`, E-5171
`26.09.01`) became permanent, and on 29.09.26 it passed an agent from another
project writing `--help` and three of its own events into this ledger. The
defect was the caller forming ledger identity at all, so the appender is
retired: it writes nothing, and `saipen checkpoint` forms every line.

`tools/validate.py` had a check that would have caught both stamps and could
not fire: its amnesty was one boolean over the whole corpus, so three sealed
DECs from July 2026 covered every line written afterwards. The amnesty is now
scoped to the event ids a DEC can actually have known about, and only a DEC
grants it -- a RUN line that merely quotes the phrase must not.
"""

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path

import _log_append as appender

EXISTING = "# Log\n- 02.09.26 11:00 [E-100] [agent: a] [op: t] RUN: previous\n"


class RetiredAppenderTests(unittest.TestCase):
    """Whatever it is handed, the appender leaves the ledger byte-identical."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="retired-appender-")
        self.addCleanup(self._tmp.cleanup)
        self.log = Path(self._tmp.name) / ".saipen" / "LOG.md"
        self.log.parent.mkdir()
        self.log.write_bytes(EXISTING.encode("utf-8"))
        cwd = os.getcwd()
        os.chdir(self._tmp.name)
        self.addCleanup(os.chdir, cwd)

    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = appender.main(["_log_append.py", *args])
        return code, out.getvalue() + err.getvalue()

    def test_help_prints_the_notice_and_writes_nothing(self):
        """The measured first line: `--help` was appended to the ledger."""
        for flag in ("--help", "-h"):
            code, text = self.run_main(flag)
            self.assertEqual(code, 0)
            self.assertIn("saipen checkpoint", text)
            self.assertEqual(self.log.read_bytes(), EXISTING.encode("utf-8"))

    def test_a_well_formed_next_line_is_still_refused(self):
        code, text = self.run_main("- 02.09.26 11:30 [E-101] [agent: a] [op: t] RUN: fine")
        self.assertEqual(code, 2)
        self.assertIn("REFUSED", text)
        self.assertEqual(self.log.read_bytes(), EXISTING.encode("utf-8"))

    def test_the_measured_foreign_sequence_writes_nothing(self):
        code, _text = self.run_main(
            "- 29.09.26 20:47 [E-2602] [parent: E-2601] [T-261] [agent: buffy] "
            "[op: scout-4c1f9a2b] RUN: another project's line",
            "--allow-inversion",
        )
        self.assertEqual(code, 2)
        self.assertEqual(self.log.read_bytes(), EXISTING.encode("utf-8"))

    def test_no_code_path_opens_the_ledger_for_writing(self):
        source = Path(appender.__file__).read_text(encoding="utf-8")
        for writer in ("write_bytes", "write_text", "open("):
            self.assertNotIn(writer, source)


class AmnestyScopeTests(unittest.TestCase):
    """The validator's rule, reproduced here as the property it must hold.

    `tools/validate.py` computes the newest DEC event id carrying the amnesty
    phrase and warns on any inversion above it. These assert the two cases the
    old boolean got wrong: a later inversion is not covered by an earlier DEC,
    and a RUN line quoting the phrase covers nothing at all.
    """

    PHRASE = "observed historical timestamp inversions"

    def _newest_documenting_dec(self, lines):
        import re

        ids = [
            int(match.group(1))
            for line in lines
            if self.PHRASE in line
            and "] DEC: " in line
            and (match := re.search(r"\[E-(\d+)\]", line))
        ]
        return max(ids, default=0)

    def test_dec_does_not_cover_an_inversion_written_after_it(self):
        lines = ["- 27.07.26 15:28 [E-813] [T-208] DEC: " + self.PHRASE + " (E-784/E-785)"]
        self.assertEqual(self._newest_documenting_dec(lines), 813)
        self.assertGreater(5171, self._newest_documenting_dec(lines))

    def test_run_line_quoting_the_phrase_grants_no_amnesty(self):
        lines = [
            "- 02.09.26 08:43 [E-5263] [T-1261] RUN: SCOUT -- " + self.PHRASE + " marker"
        ]
        self.assertEqual(self._newest_documenting_dec(lines), 0)

    def test_dec_at_or_after_the_inversion_covers_it(self):
        lines = ["- 02.09.26 09:00 [E-5266] [T-1261] DEC: " + self.PHRASE + " through E-5171"]
        self.assertGreaterEqual(self._newest_documenting_dec(lines), 5171)


if __name__ == "__main__":
    unittest.main()

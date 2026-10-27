"""T-1891: one parser decides when a conformance receipt was written.

Measured defect, before the fix. `_strict_iso_utc` stripped a stamp before
parsing, so a whitespace-padded timestamp validated as a correct UTC instant.
The freshness arithmetic in `conformance_status` parsed the RAW string instead,
`datetime.fromisoformat` refused it, and a bare `except Exception: pass` left
`age_seconds = 0`. Zero age means maximally fresh, so the 24-hour window could
never fire:

    ts = " 2020-01-01T00:00:00.000000Z "   (6.8 years old)
    _strict_iso_utc -> "2020-01-01T00:00:00Z"   accepted
    age_seconds     -> 0                        fresh
    aged branch     -> False

Two receipts differing only in leading/trailing space classified differently:
the clean one `STALE_PASS / aged-beyond-freshness-window`, the padded one
`CURRENT_PASS`. Nothing else about the receipt changed.

The fix is ONE parser, `_strict_utc_datetime`, which returns the aware instant
or None. `_strict_iso_utc`, `_future_beyond_skew`, `_parse_utc` and the ageing
branch in `conformance_status` all consume it, so no code path can hold a
different opinion about when a receipt was written. The ageing branch no
longer swallows a parse failure either: the strict validator has already
proven the stamp parses, so a None there is an internal contradiction and is
reported as INVALID rather than silently aged at zero.

What this pins, one test per clause of the ticket's verify line:

  * a bound PASS receipt whose stamp is padded reads as aged beyond the window;
  * the same receipt with a clean stamp keeps today's verdict (aged, not
    CURRENT);
  * the strict validator and the age arithmetic agree on every stamp one of
    them accepts -- asserted as an identity over a table of stamps, including
    the shapes one side used to refuse and the other accept;
  * a red control proves the pre-fix shape reports current.

That last control is `.saipen/evidence/T-1891-freshness/red-control.py`, which
restores the pre-fix age arithmetic in-process and shows the padded receipt
flipping back to CURRENT_PASS.

Run standalone:
    python tools/test_t1891_freshness_parser.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import conformance as C  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
import test_t1412_conformance_truth as fixtures  # noqa: E402

#: A bound, otherwise valid PASS receipt's stamp, 6.8 years before this campaign.
ANCIENT = "2020-01-01T00:00:00.000000Z"
PADDED_ANCIENT = f"  {ANCIENT}  "


def setUpModule() -> None:
    isolate_host_session()


class FreshnessFixture(unittest.TestCase):
    """One disposable project per receipt, via the shared T-1412 builder."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="t1891-")
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name).resolve()
        self._maker = fixtures.T1412Base("runTest")
        self._maker.setUp()
        self._maker.base = self.base
        self.addCleanup(self._maker.tearDown)
        self._count = 0

    def status_for(self, ts: str | None, verdict: str = "PASS") -> dict:
        """The canonical classification of ONE receipt carrying ``ts``.

        The receipt is BUILT with a filename-safe stamp and then has the exact
        bytes under test written into `timestamp_utc`, with `content_hash`
        recomputed the way the fixture does it. Writing the padded stamp
        directly would make the share fixture derive a filename containing a
        tab, which measures the filesystem rather than this defect.
        """
        self._count += 1
        root = self._maker.make_project(f"case-{self._count}", state=fixtures._STATE)
        fixtures.write_receipt(root, verdict, ts=ANCIENT)
        if ts is not None:
            out_dir = root / C.RECEIPT_DIRNAME
            (path,) = sorted(out_dir.glob("*.json"))
            receipt = json.loads(path.read_text(encoding="utf-8"))
            receipt["timestamp_utc"] = ts
            body = {k: v for k, v in receipt.items() if k != "content_hash"}
            receipt["content_hash"] = fixtures._quick_hash(
                json.dumps(body, indent=2, sort_keys=True)
            )
            path.write_text(
                json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        return C.conformance_status(root, gate="core")


class PaddedStampTests(FreshnessFixture):
    """The measured defect, from the receipt's own bytes."""

    def test_a_padded_stamp_reads_as_aged_beyond_the_window(self) -> None:
        status = self.status_for(PADDED_ANCIENT)
        self.assertEqual(status["status"], C.STATUS_STALE_PASS, status)
        self.assertEqual(
            status["stale_reason"],
            C.STALE_REASON_AGED_BEYOND_WINDOW,
            status,
        )

    def test_the_same_receipt_with_a_clean_stamp_keeps_its_verdict(self) -> None:
        status = self.status_for(ANCIENT)
        self.assertEqual(status["status"], C.STATUS_STALE_PASS, status)
        self.assertEqual(status["stale_reason"], C.STALE_REASON_AGED_BEYOND_WINDOW, status)

    def test_padding_no_longer_changes_the_classification(self) -> None:
        """The whole defect in one assertion: whitespace is not a verdict."""
        clean = self.status_for(ANCIENT)
        for padding in (f" {ANCIENT}", f"{ANCIENT} ", f"\t{ANCIENT}\n", PADDED_ANCIENT):
            with self.subTest(padding=repr(padding)):
                padded = self.status_for(padding)
                self.assertEqual(
                    (padded["status"], padded.get("stale_reason")),
                    (clean["status"], clean.get("stale_reason")),
                    f"padding {padding!r} changed the classification",
                )

    def test_a_fresh_receipt_stays_current_whatever_the_padding(self) -> None:
        """The fix must not turn freshness into staleness."""
        now_stamp = C._utc_now_iso()
        for stamp in (now_stamp, f"  {now_stamp}  ", f"\t{now_stamp}\n"):
            with self.subTest(stamp=repr(stamp)):
                status = self.status_for(stamp)
                self.assertEqual(status["status"], C.STATUS_CURRENT_PASS, status)
                self.assertIsNone(status.get("stale_reason"), status)


class OneParserTests(unittest.TestCase):
    """The strict validator and the age arithmetic agree, stamp by stamp."""

    #: stamp -> whether the ONE parser accepts it as an aware UTC instant.
    STAMPS = (
        ("2020-01-01T00:00:00Z", True),
        ("2020-01-01T00:00:00+00:00", True),
        ("2020-01-01T00:00:00.000000Z", True),
        (ANCIENT, True),
        (PADDED_ANCIENT, True),
        ("\t2020-01-01T00:00:00Z\n", True),
        ("2020-01-01T00:00:00", False),          # naive: no UTC claim
        ("2020-01-01T00:00:00+03:00", False),    # an offset is not UTC
        ("2020-13-01T00:00:00Z", False),         # not a real month
        ("not a timestamp", False),
        ("", False),
        ("   ", False),
        (None, False),
        (12345, False),
        (["2020-01-01T00:00:00Z"], False),
    )

    def test_the_one_parser_agrees_with_the_strict_validator(self) -> None:
        for stamp, accepted in self.STAMPS:
            with self.subTest(stamp=repr(stamp)):
                parsed = C._strict_utc_datetime(stamp)
                self.assertEqual(
                    parsed is not None,
                    accepted,
                    f"_strict_utc_datetime disagreed about {stamp!r}",
                )
                # The validator's own spelling of the same judgement.
                self.assertEqual(
                    bool(C._strict_iso_utc(stamp)),
                    accepted,
                    f"_strict_iso_utc disagreed about {stamp!r}",
                )

    def test_every_accepted_stamp_yields_the_same_instant_everywhere(self) -> None:
        """One stamp, four consumers, one instant -- or all four refuse."""
        for stamp, accepted in self.STAMPS:
            with self.subTest(stamp=repr(stamp)):
                as_datetime = C._strict_utc_datetime(stamp)
                as_utc = C._parse_utc(stamp)
                normalised = C._strict_iso_utc(stamp)
                if not accepted:
                    self.assertIsNone(as_datetime)
                    self.assertEqual(normalised, "")
                    # `_parse_utc` may still read a naive stamp as UTC for
                    # evidence ORDERING; what it must never do is accept an
                    # unparseable or non-UTC-offset value.
                    if as_utc is not None:
                        self.assertIsInstance(stamp, str)
                        self.assertRegex(stamp.strip(), r"^\d{4}-\d{2}-\d{2}T")
                    continue
                self.assertIsNotNone(as_datetime)
                self.assertIsNotNone(as_utc)
                self.assertEqual(as_datetime, as_utc)
                self.assertEqual(
                    as_datetime,
                    C.datetime.datetime.fromisoformat(normalised.replace("Z", "+00:00")),
                    "the canonical spelling must denote the same instant",
                )

    def test_a_padded_stamp_ages_by_its_real_age(self) -> None:
        """Not "some positive number": the actual elapsed time."""
        parsed = C._strict_utc_datetime(PADDED_ANCIENT)
        self.assertIsNotNone(parsed)
        now = C.datetime.datetime(2026, 10, 24, tzinfo=C.datetime.timezone.utc)
        age = (now - parsed).total_seconds()
        self.assertGreater(age, 6.5 * 365 * 24 * 3600, age)
        self.assertGreater(age, C.FRESHNESS_WINDOW_SECONDS, age)


class NeighbouringStrictnessTests(FreshnessFixture):
    """What must NOT change: the other ways a receipt is refused."""

    def test_a_naive_stamp_is_still_an_invalid_receipt(self) -> None:
        status = self.status_for("2020-01-01T00:00:00")
        self.assertEqual(status["status"], C.STATUS_INVALID, status)

    def test_a_non_utc_offset_is_still_an_invalid_receipt(self) -> None:
        status = self.status_for("2020-01-01T00:00:00+03:00")
        self.assertEqual(status["status"], C.STATUS_INVALID, status)

    def test_a_fabricated_future_stamp_is_still_never_recoverable(self) -> None:
        status = self.status_for("2099-01-01T00:00:00.000000Z")
        self.assertEqual(status["status"], C.STATUS_STALE_FAIL, status)
        self.assertEqual(status["stale_reason"], C.STALE_REASON_FUTURE_TIMESTAMP, status)
        self.assertFalse(C.stale_recoverable(status), status)

    def test_a_padded_future_stamp_is_also_seen_as_future(self) -> None:
        """The same bypass existed for the future-skew check's inputs."""
        status = self.status_for("  2099-01-01T00:00:00.000000Z  ")
        self.assertEqual(status["status"], C.STATUS_STALE_FAIL, status)
        self.assertEqual(status["stale_reason"], C.STALE_REASON_FUTURE_TIMESTAMP, status)


class NoZeroAgeFallbackTests(unittest.TestCase):
    """The ageing branch must not silently age an unparseable stamp at zero."""

    def test_the_age_arithmetic_has_no_exception_swallow(self) -> None:
        source = Path(C.__file__).read_text(encoding="utf-8")
        marker = "rdt = _strict_utc_datetime(receipt.get(\"timestamp_utc\"))"
        self.assertIn(marker, source, "the ageing branch must use the ONE parser")
        # And the pre-fix shape -- a raw fromisoformat inside a bare except --
        # must not come back.
        self.assertNotIn(
            'fromisoformat(receipt["timestamp_utc"].replace("Z", "+00:00"))',
            source,
            "the raw-stamp parse returned to the ageing branch",
        )


if __name__ == "__main__":
    unittest.main()

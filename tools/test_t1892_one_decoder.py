"""T-1892: `Journal.read()` is the canonical decoder, not a second one.

The defect this pins, measured on the tree before the fix. `Journal.read()`
re-read `operation.json` itself and merged `progress.json` inside a bare
`except Exception: pass`. The strict decoder (`decode_operation_record`, the
ONE gate every other journal consumer trusts) refuses that same sidecar. On
eight refused shapes the two answers diverged, and on the one that matters a
forged terminal status became visible through `read()`:

    terminal over UNRESOLVED : decoder RECOVERY_CONFLICT | read()->'COMMITTED'
    progress_index OOR       : decoder VALIDATION_FAILED  | read()->'APPLYING'
    applied_frontier OOR     : decoder VALIDATION_FAILED  | read()->'APPLYING'
    invalid JSON             : decoder RECOVERY_CONFLICT  | read()->'PREPARED'

The release recovery path (`journal.read()` then `_validate_record`) and
`goal_authority._pin_record` both compared against that permissive projection,
so the tolerated sidecar was observed exactly where a refusal was owed.

The fix delegates to the canonical decoder and raises `JournalDecodeRefusal`
(a `ValueError`, so existing `except ValueError` callers keep their meaning).

There is ONE legitimate window in which a terminal sidecar sits over an
unresolved manifest: `Journal.mark()` publishes the terminal status to the
sidecar and only then calls `fold_progress()`, which folds and deletes it. That
window belongs to the folding writer and nobody else, so the decoder carries a
narrowly-scoped `allow_settlement_fold` flag that only `fold_progress` passes.
This module pins both halves:

  * every shape the decoder refuses, `read()` refuses with the SAME code;
  * a legitimate sidecar still merges (status, progress_index, applied prefix);
  * the fold window is readable by the folder, refused by everyone else, and a
    real settlement still completes end to end;
  * a sidecar that cannot be folded is never silently repaired: the mark
    refuses, the bytes stay as evidence, and the canonical pending scan calls
    the result CORRUPT_JOURNAL rather than pretending it settled.

Run standalone:
    python tools/test_t1892_one_decoder.py
"""

from __future__ import annotations

import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import journal as J  # noqa: E402
from saipen_engine.paths import runtime_lock_identity  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def _targets() -> list[dict]:
    """Two write targets, so an applied frontier has somewhere to point."""
    return [
        {
            "path": f"{name}.txt",
            "role": "generic",
            "content": f"after {name}\n".encode("utf-8"),
            "before_hash": J.hash_bytes(f"before {name}\n".encode("utf-8")),
            "after_hash": J.hash_bytes(f"after {name}\n".encode("utf-8")),
        }
        for name in ("alpha", "beta")
    ]


class OneDecoderFixture(unittest.TestCase):
    """One disposable project per test, holding ONE PREPARED operation."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="t1892-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        (self.root / ".saipen").mkdir()
        for name in ("alpha", "beta"):
            (self.root / f"{name}.txt").write_bytes(f"before {name}\n".encode("utf-8"))
        self.op_id = "op-t1892-fixture"
        self.journal = J.Journal(self.root, self.op_id)
        self.journal.start(
            "op",
            "probe",
            runtime_lock_identity(self.root),
            "t1892-hash",
            _targets(),
        )

    def sidecar(self) -> Path:
        return self.journal.dir / "progress.json"

    def write_sidecar(self, payload: object) -> None:
        self.sidecar().write_text(json.dumps(payload), encoding="utf-8")

    def write_sidecar_bytes(self, payload: bytes) -> None:
        self.sidecar().write_bytes(payload)

    def decoder_verdict(self) -> str:
        decoded = J.decode_operation_record(self.root, self.journal.dir)
        return "OK" if decoded["ok"] else decoded["code"]

    def read_verdict(self) -> str:
        try:
            self.journal.read()
        except J.JournalDecodeRefusal as exc:
            return exc.code
        return "OK"


class RefusedSidecarTests(OneDecoderFixture):
    """Every refusal the decoder makes, `read()` makes with the same code."""

    #: label -> (sidecar bytes, the decoder code that must be raised).
    SHAPES = (
        ("invalid JSON", b"{not json", "RECOVERY_CONFLICT"),
        ("not a JSON object", b"[]", "RECOVERY_CONFLICT"),
        ("status outside the closed set", b'{"status": "BOGUS"}', "VALIDATION_FAILED"),
        ("progress_index not an integer", b'{"progress_index": "0"}', "VALIDATION_FAILED"),
        ("progress_index out of range", b'{"progress_index": 9}', "VALIDATION_FAILED"),
        ("applied_frontier not an integer", b'{"applied_frontier": 1.5}', "VALIDATION_FAILED"),
        ("applied_frontier out of range", b'{"applied_frontier": 7}', "VALIDATION_FAILED"),
        (
            "terminal over an unresolved manifest",
            b'{"status": "COMMITTED"}',
            "RECOVERY_CONFLICT",
        ),
    )

    def test_every_decoder_refusal_is_read_s_refusal(self) -> None:
        for label, payload, expected in self.SHAPES:
            with self.subTest(shape=label):
                self.write_sidecar_bytes(payload)
                self.assertEqual(
                    self.decoder_verdict(),
                    expected,
                    f"{label}: the decoder's own verdict moved",
                )
                self.assertEqual(
                    self.read_verdict(),
                    expected,
                    f"{label}: read() must refuse with the decoder's code",
                )

    def test_a_directory_where_the_sidecar_belongs_is_refused(self) -> None:
        self.sidecar().mkdir()
        self.assertEqual(self.decoder_verdict(), "RECOVERY_CONFLICT")
        self.assertEqual(self.read_verdict(), "RECOVERY_CONFLICT")

    def test_refusal_carries_the_decoder_s_code_and_detail(self) -> None:
        self.write_sidecar({"status": "COMMITTED"})
        decoded = J.decode_operation_record(self.root, self.journal.dir)
        self.assertFalse(decoded["ok"])
        with self.assertRaises(J.JournalDecodeRefusal) as caught:
            self.journal.read()
        self.assertEqual(caught.exception.code, decoded["code"])
        self.assertEqual(caught.exception.detail, decoded["detail"])
        self.assertIsInstance(caught.exception, ValueError)

    def test_a_forged_terminal_status_is_not_visible_through_read(self) -> None:
        """The measured defect: the pre-fix projection reported 'COMMITTED'."""
        self.write_sidecar({"status": "COMMITTED"})
        self.assertEqual(self.read_verdict(), "RECOVERY_CONFLICT")
        # The same bytes through the projection `read()` used to be: the
        # forged terminal IS visible there. That is what the fix removes, so
        # the refusal above is load-bearing rather than incidental.
        self.assertEqual(_permissive_projection(self.journal)["status"], "COMMITTED")
        # And the project-wide scan already classed this shape as corrupt,
        # which is the verdict read() was contradicting.
        pending, conflicts = J.scan_pending(self.root)
        corrupt = [op for op in pending if op.get("corrupt")]
        self.assertEqual([op["op_id"] for op in corrupt], [self.op_id])
        self.assertEqual(conflicts, [])

    def test_a_refused_sidecar_never_reaches_release_recovery_as_a_status(self) -> None:
        """release recovery used to read the forged status and act on it."""
        from saipen_engine import release

        self.journal.update(mode="no-publish", release_stage="PREPARED")
        self.write_sidecar({"status": "COMMITTED"})
        result = release._recover_release_op_locked(self.root, self.op_id)
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "RECOVERY_CONFLICT")
        self.assertTrue(result["recovery_required"])
        self.assertNotEqual(result.get("code"), "ALREADY_APPLIED")


class LegitimateSidecarTests(OneDecoderFixture):
    """The merge `read()` must keep doing for a sidecar it can trust."""

    def test_a_legitimate_sidecar_still_merges(self) -> None:
        self.write_sidecar({"status": "APPLYING", "progress_index": 1, "applied_frontier": 0})
        record = self.journal.read()
        self.assertEqual(record["status"], "APPLYING")
        self.assertEqual(record["progress_index"], 1)
        self.assertTrue(record["targets"][0]["applied"])
        self.assertFalse(record["targets"][1]["applied"])

    def test_an_absent_sidecar_reads_the_manifest_unchanged(self) -> None:
        record = self.journal.read()
        self.assertEqual(record["status"], "PREPARED")
        self.assertFalse(any(target["applied"] for target in record["targets"]))

    def test_an_empty_sidecar_is_absence_not_a_rewrite(self) -> None:
        self.write_sidecar({})
        record = self.journal.read()
        self.assertEqual(record["status"], "PREPARED")
        self.assertEqual(record["progress_index"], 0)


class SettlementFoldTests(OneDecoderFixture):
    """The ONE window where a terminal sidecar legitimately sits over PREPARED."""

    def test_the_fold_window_is_readable_by_the_folder_and_nobody_else(self) -> None:
        self.write_sidecar({"status": "COMMITTED", "progress_index": 2})
        self.assertEqual(self.read_verdict(), "RECOVERY_CONFLICT")
        record = self.journal.read(allow_settlement_fold=True)
        self.assertEqual(record["status"], "COMMITTED")
        self.assertEqual(record["progress_index"], 2)

    def test_fold_progress_completes_the_settlement(self) -> None:
        self.write_sidecar({"status": "COMMITTED", "progress_index": 2})
        self.journal.fold_progress()
        self.assertFalse(self.sidecar().exists(), "the folded sidecar must be gone")
        self.assertEqual(
            json.loads(self.journal.manifest.read_text(encoding="utf-8"))["status"],
            "COMMITTED",
        )
        self.assertEqual(self.journal.read()["status"], "COMMITTED")

    def test_a_real_terminal_mark_still_settles_end_to_end(self) -> None:
        """Not a direct fold call: the ordinary mutation path, from PREPARED.

        Its own project because `run_mutation` derives the semantic payload
        hash itself; the fixture above started its journal with a literal one,
        which is a deliberate op_id collision, not the path under test.
        """
        root = Path(tempfile.mkdtemp(prefix="t1892-e2e-")).resolve()
        self.addCleanup(__import__("shutil").rmtree, root, True)
        (root / ".saipen").mkdir()
        for name in ("alpha", "beta"):
            (root / f"{name}.txt").write_bytes(f"before {name}\n".encode("utf-8"))
        result = J.run_mutation(
            root,
            "op-t1892-e2e",
            "op",
            "probe",
            runtime_lock_identity(root),
            "t1892-hash",
            _targets(),
            preconditions={
                f"{name}.txt": J.hash_bytes(f"before {name}\n".encode("utf-8"))
                for name in ("alpha", "beta")
            },
            verification_policy="none",
            _ensure_lineage=False,
        )
        self.assertTrue(result.get("ok"), result)
        settled = J.Journal(root, "op-t1892-e2e")
        self.assertFalse(
            (settled.dir / "progress.json").exists(),
            "a settled receipt must not keep a sidecar to fold",
        )
        record = settled.read()
        self.assertEqual(record["status"], "COMMITTED")
        self.assertTrue(all(target["applied"] for target in record["targets"]))
        for name in ("alpha", "beta"):
            self.assertEqual(
                (root / f"{name}.txt").read_bytes(),
                f"after {name}\n".encode("utf-8"),
            )


class UnfoldableSidecarTests(OneDecoderFixture):
    """Bad progress bytes are evidence, never something the writer may drop."""

    def test_mark_refuses_to_fold_a_sidecar_it_cannot_vouch_for(self) -> None:
        # A parseable sidecar whose progress_index is out of range survives
        # `mark`'s own status write, so the fold would be reading bytes the
        # decoder refuses. The mark must refuse and keep them.
        self.write_sidecar({"progress_index": 9})
        with self.assertRaises(J.JournalDecodeRefusal):
            self.journal.mark("COMMITTED")
        self.assertTrue(self.sidecar().exists(), "the refused sidecar stays as evidence")
        self.assertEqual(
            json.loads(self.journal.manifest.read_text(encoding="utf-8"))["status"],
            "PREPARED",
            "the manifest must not record a settlement that did not fold",
        )
        # The canonical scan reports this exactly as the corrupt evidence it
        # is, so the refusal is a diagnosis, not a dead end.
        pending, _conflicts = J.scan_pending(self.root)
        self.assertEqual([op["op_id"] for op in pending if op.get("corrupt")], [self.op_id])


def _permissive_projection(journal) -> dict:
    """`Journal.read()` as it was before T-1892, byte for byte.

    Kept only to prove what the fix removes: this returns the forged terminal
    status the canonical decoder refuses. It is never used by the engine.
    """
    record = json.loads(journal.manifest.read_text(encoding="utf-8"))
    progress_file = journal.dir / "progress.json"
    if progress_file.is_file():
        with contextlib.suppress(Exception):
            prog = json.loads(progress_file.read_text(encoding="utf-8"))
            if "status" in prog:
                record["status"] = prog["status"]
            if "progress_index" in prog:
                record["progress_index"] = prog["progress_index"]
            frontier = prog.get("applied_frontier", -1)
            targets = record.get("targets", [])
            for i in range(min(frontier + 1, len(targets))):
                targets[i]["applied"] = True
    return record


if __name__ == "__main__":
    unittest.main()

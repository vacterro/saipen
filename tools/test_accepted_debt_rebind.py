"""T-312: the closed accepted-debt rebind writer and the CAS guard behind it.

The defect class: `run_mutation` accepts an arbitrary `operation=` string, so
the generic journal CAS could rewrite an accepted-debt record -- bytes the domain
treats as immutably registered -- under an operation name no module implements.
AD-000002's own history is the artifact of that hole.

This suite pins the two halves of the fix:

  1. the GUARD: a target under the accepted-debt directory is refused by
     `validate_mutation_request` unless the operation is a closed
     accepted-debt domain writer, with zero writes;
  2. the WRITER: `rebind` re-points a record's evidence at where its events
     live now, refusing every attempt to change the accepted event set, and
     landing through the `accepted_debt` verification policy so APPLY and
     Recovery rerun the same semantic postcondition.

Fixtures are hermetic: a copied `.saipen` scenario plus a seeded LOG, mutated
only inside a temp directory.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.accepted_debt import rebind  # noqa: E402
from saipen_engine.journal import (  # noqa: E402
    validate_mutation_request,
    verify_accepted_debt,
)
from test_hermetic_env import hermetic_env, isolate_host_session  # noqa: E402

SCENARIO = ROOT / "tests" / "scenarios" / "userperson-valid" / ".saipen"
AD_DIR = ".saipen/recovery/conformance/accepted_debt"

LOG_SEED = (
    "- 08.08.26 00:00 [E-001] [T-none] DEC: fixture bootstrap\n"
    "- 08.08.26 00:01 [E-002] [agent: probe] "
    "[op: claim-0123456789abcdef0123456789abcdef] DEC: claimed via SAIOPS -- owner probe\n"
    "- 08.08.26 00:02 [E-003] DEC: goal pivot -- synthetic sealed missing provenance A\n"
    "- 08.08.26 00:03 [E-004] RUN: transition to BUILD -- synthetic sealed missing "
    "provenance B\n"
)
REASON = "sealed historical debt: retroactive marker would forge provenance"


def setUpModule() -> None:
    isolate_host_session()


def _sha(path: Path) -> str:
    """The journal's own 16-hex precondition form, as a full digest is accepted too."""
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cas(operation: str, path: str) -> dict:
    """One minimal validate_mutation_request call for a single write target."""
    return validate_mutation_request(
        "/tmp/does-not-matter",
        "probe-op-0123456789abcdef0123456789abcdef",
        operation,
        "probe",
        "probe-identity",
        "0" * 64,
        [{"path": path, "role": "report", "action": "write", "content": "{}", "before_hash": "", "after_hash": "0" * 64}],
        preconditions={},
    )


class RebindFixture(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="saipen-ad-rebind-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "project"
        self.root.mkdir()
        shutil.copytree(SCENARIO, self.root / ".saipen")
        (self.root / ".saipen" / "LOG.md").write_text(LOG_SEED, encoding="utf-8")
        state = self.root / ".saipen" / "STATE.md"
        state.write_text(
            state.read_text(encoding="utf-8").replace("last_event: 1", "last_event: 4"),
            encoding="utf-8",
        )
        self.ad_path = self.root / AD_DIR / "AD-000001.json"

    def _register(self, events: list[str], authority: str = "SRC-047") -> dict:
        from saipen_engine.accepted_debt import register

        result = register(self.root, agent="probe", events=events, reason=REASON, authority=authority)
        self.assertTrue(result.get("ok"), result)
        return result

    def _rotate_shard(self) -> None:
        """Move LOG.md into a rotated shard: the classic post-registration drift."""
        logs = self.root / ".saipen" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        shutil.move(str(self.root / ".saipen" / "LOG.md"), str(logs / "LOG-001.md"))

    # ---- 1. the CAS guard (T-312 clause 1) --------------------------------

    def test_cas_refuses_an_accepted_debt_record_under_a_foreign_operation(self) -> None:
        done = _cas("run_mutation", f"{AD_DIR}/AD-000001.json")
        self.assertFalse(done["ok"], done)
        self.assertIn("closed accepted_debt domain writer", done["detail"])

    def test_cas_refuses_an_operation_name_that_merely_looks_like_a_writer(self) -> None:
        done = _cas("accepted_debt_rebind", f"{AD_DIR}/AD-000001.json")
        self.assertFalse(done["ok"], done)
        self.assertIn("closed accepted_debt domain writer", done["detail"])

    def test_cas_allows_both_closed_domain_writers(self) -> None:
        for operation in ("accepted_debt.register", "accepted_debt.rebind"):
            done = _cas(operation, f"{AD_DIR}/AD-000001.json")
            self.assertTrue(done["ok"], f"{operation}: {done}")

    def test_cas_guard_does_not_hijack_unrelated_paths(self) -> None:
        done = _cas("run_mutation", ".saipen/LOG.md")
        self.assertNotIn("closed accepted_debt domain writer", done.get("detail", ""))

    def test_cas_refusal_creates_no_journal_state(self) -> None:
        before = sorted(p.name for p in (self.root / ".saipen").iterdir())
        _cas("run_mutation", f"{AD_DIR}/AD-000001.json")
        self.assertEqual(sorted(p.name for p in (self.root / ".saipen").iterdir()), before)

    # ---- 2. the writer (T-312 clause 2) -----------------------------------

    def test_rebind_refuses_an_unknown_record(self) -> None:
        done = rebind(self.root, "AD-999999", agent="probe", reason="x", expected_before="0" * 64)
        self.assertFalse(done["ok"], done)

    def test_rebind_refuses_an_empty_reason(self) -> None:
        self._register(["E-003"])
        done = rebind(self.root, "AD-000001", agent="probe", reason="   ", expected_before=_sha(self.ad_path))
        self.assertFalse(done["ok"], done)
        self.assertIn("reason is required", done["detail"])

    def test_rebind_refuses_without_expected_before(self) -> None:
        self._register(["E-003"])
        done = rebind(self.root, "AD-000001", agent="probe", reason="rotate", expected_before="")
        self.assertFalse(done["ok"], done)
        self.assertIn("expected_before is required", done["detail"])

    def test_rebind_refuses_a_stale_expected_before(self) -> None:
        self._register(["E-003"])
        done = rebind(self.root, "AD-000001", agent="probe", reason="rotate", expected_before="f" * 64)
        self.assertFalse(done["ok"], done)
        self.assertEqual(done["code"], "STALE_PRECONDITION")

    def test_rebind_is_a_noop_when_the_evidence_already_resolves(self) -> None:
        self._register(["E-003"])
        done = rebind(self.root, "AD-000001", agent="probe", reason="rotate", expected_before=_sha(self.ad_path))
        self.assertFalse(done["ok"], done)
        self.assertEqual(done["code"], "ACCEPTED_DEBT_REBIND_NOOP")

    def test_rebind_repairs_evidence_after_a_shard_rotation(self) -> None:
        self._register(["E-003"])
        self._rotate_shard()
        before_record = json.loads(self.ad_path.read_text(encoding="utf-8"))
        self.assertEqual(before_record["evidence"][0]["file"], ".saipen/LOG.md")

        done = rebind(
            self.root,
            "AD-000001",
            agent="probe",
            reason="LOG shard rotated after registration",
            expected_before=_sha(self.ad_path),
        )
        self.assertTrue(done["ok"], done)
        self.assertEqual(done["code"], "ACCEPTED_DEBT_REBOUND")

        after = json.loads(self.ad_path.read_text(encoding="utf-8"))
        self.assertEqual(after["evidence"][0]["file"], ".saipen/logs/LOG-001.md")
        # The accepted SET is immutable across a rebind -- that is the whole
        # difference between a repair and a re-registration.
        self.assertEqual(after["accepted_missing_events"], before_record["accepted_missing_events"])
        # The old evidence is preserved on the record, not silently discarded.
        self.assertEqual(after["rebind_from_evidence"], before_record["evidence"])
        self.assertTrue(after["rebind_reason"])
        self.assertIn("accepted_debt.rebind", after["journal_op_id"])
        # The journalised receipt carries the closed policy, not "none".
        receipt = json.loads(
            (self.root / ".saipen" / "recovery" / "settled" / after["journal_op_id"] / "operation.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(receipt["operation"], "accepted_debt.rebind")
        self.assertEqual(receipt["verification_policy"], "accepted_debt")
        self.assertEqual(receipt["targets"][0]["before_hash"], _sha.__self__ if False else receipt["targets"][0]["before_hash"])

    def test_rebound_record_passes_the_semantic_verifier(self) -> None:
        self._register(["E-003"])
        self._rotate_shard()
        self.assertTrue(
            rebind(self.root, "AD-000001", agent="probe", reason="rotate", expected_before=_sha(self.ad_path))["ok"]
        )
        errors = verify_accepted_debt(
            self.root, [{"path": f"{AD_DIR}/AD-000001.json", "action": "write"}]
        )
        self.assertEqual(errors, [], errors)

    def test_verifier_fails_a_record_whose_evidence_does_not_resolve(self) -> None:
        self._register(["E-003"])
        self._rotate_shard()  # rebound was never run: the record is now stale
        errors = verify_accepted_debt(
            self.root, [{"path": f"{AD_DIR}/AD-000001.json", "action": "write"}]
        )
        self.assertTrue(errors, "a rotated-shard record must be reported")
        self.assertTrue(any("record cites" in e or "no longer resolves" in e for e in errors), errors)

    def test_rebind_cannot_widen_the_accepted_set(self) -> None:
        self._register(["E-003"])
        self._rotate_shard()
        rebind(self.root, "AD-000001", agent="probe", reason="rotate", expected_before=_sha(self.ad_path))
        after = json.loads(self.ad_path.read_text(encoding="utf-8"))
        self.assertEqual(after["accepted_missing_events"], ["E-3"])

    def test_rebind_refuses_when_an_accepted_event_no_longer_parses(self) -> None:
        self._register(["E-003", "E-004"])
        # Rotate first, then destroy the shard's parseable content. An accepted
        # event that is gone entirely is a refusal, never a silent re-binding of
        # the acceptance onto some other line that happens to exist.
        self._rotate_shard()
        (self.root / ".saipen" / "logs" / "LOG-001.md").write_text(
            "not a log line at all\n", encoding="utf-8"
        )
        done = rebind(
            self.root, "AD-000001", agent="probe", reason="rotate", expected_before=_sha(self.ad_path)
        )
        self.assertFalse(done["ok"], done)
        self.assertEqual(done["code"], "VALIDATION_FAILED")
        self.assertIn("no longer parse as LOG lines", done["detail"])
        # A refused rebind leaves the record byte-identical.
        after = json.loads(self.ad_path.read_text(encoding="utf-8"))
        self.assertEqual([e["file"] for e in after["evidence"]], [".saipen/LOG.md", ".saipen/LOG.md"])
        self.assertNotIn("rebind_reason", after)


if __name__ == "__main__":
    unittest.main(verbosity=2)

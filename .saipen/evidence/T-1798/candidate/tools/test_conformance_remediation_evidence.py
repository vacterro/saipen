"""T-1334: a FAIL receipt must not outlive the remediation evidence that cured it.

Measured on FastPrompter 27.09.26 (improve cycle
imp-vacterro-fastprompter-20260927-2, RUN-1/IMP-003): a `work reverify` run
wrote its PASS receipt for T-1240 at 18:34:41Z, and `continue --json` went on
returning CONFORMANCE_UNHEALTHY naming T-1240 off the 18:25:09Z core FAIL
receipt. Only an explicit `saipen validate` produced a fresh verdict. The gate
reported a blocker that had already been cured, for as long as nobody happened
to run the verb the gate's own remediation named.

The cure is invisible to every other currency check, because a reverify receipt
changes no source file, no STATE/BOARD/LOG byte and no source identity: the
receipt is a projection of the evidence set as it stood when written, and this
is the one input that can move that set without moving the tree.

These controls pin the repaired contract:

* an executed reverify receipt, newer than the FAIL, for Work the FAIL itself
  blocks, bound to the same tree, demotes CURRENT_FAIL to STALE_FAIL (unproven,
  no longer a stop) and says which receipt moved;
* every weaker shape is ignored -- attested-only, FAIL verdict, other Work,
  other tree, older than the receipt;
* a PASS receipt is never demoted: extra evidence never invalidates green.

Run standalone:
    python -m unittest tools.test_conformance_remediation_evidence
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
for _entry in (str(TOOLS), str(ROOT)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from saipen_engine import conformance as C  # noqa: E402
from saipen_engine import router as router_mod  # noqa: E402
from test_t1412_conformance_truth import (  # noqa: E402
    T1412Base,
    _source_pair,
    _utc_now,
    write_receipt,
)


def _idle(action: str = "saipen continue") -> dict:
    """The idle continuation shape the router hands to its gates."""
    return {"ok": True, "action": action, "reason": "maintain"}


def write_fail_receipt(root: Path, *, work: str, ts: str, extra_problem: str = "") -> dict:
    """A CURRENT_FAIL core receipt that blocks `work`, like the validator's own."""
    write_receipt(root, "FAIL", ts=ts)
    path = max((root / C.RECEIPT_DIRNAME).glob("*.json"))
    receipt = json.loads(path.read_text(encoding="utf-8"))
    problems = [
        {
            "rule_id": "work_closure_evidence",
            "subject_id": work,
            "subject_kind": "work",
            "detail": "no current-tree PASS re-verification receipt",
            "severity": "problem",
        }
    ]
    if extra_problem:
        problems.append(
            {
                "rule_id": "unclassified",
                "subject_id": extra_problem,
                "subject_kind": "other",
                "detail": "unrelated blocking finding",
                "severity": "problem",
            }
        )
    receipt["blocking_findings"] = {
        "status": "complete",
        "problem_count": len(problems),
        "warning_count": 0,
        "ruleset_version": 1,
        "ruleset_fingerprint": "0" * 64,
        "problems": problems,
    }
    receipt["remediation_commands"] = [f"saipen work reverify {work}"]
    receipt["canonical_next_command"] = f"saipen work reverify {work}"
    body = {k: v for k, v in receipt.items() if k != "content_hash"}
    receipt["content_hash"] = _hash16(body)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def _hash16(body: dict) -> str:
    import hashlib

    payload = json.dumps(body, indent=2, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def write_reverify(
    root: Path,
    *,
    receipt_id: str,
    work: str,
    created_at: str,
    verdict: str = "PASS_WITH_CARRIED_DEBT",
    evidence_class: str = "executed",
    source_head: str = "",
    source_fp: str = "",
) -> None:
    """A reverify receipt with the schema the writer emits."""
    head, fp = _source_pair(root)
    out = root / ".saipen" / "recovery" / "conformance" / "reverify"
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "receipt_id": receipt_id,
        "gate": "core",
        "work": work,
        "verdict": verdict,
        "evidence_class": evidence_class,
        "created_at": created_at,
        "project_identity": "",
        "source_head": source_head or head,
        "source_tree_fingerprint": source_fp or fp,
    }
    (out / f"{receipt_id}.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


class TestT1334RemediationEvidence(T1412Base):
    def _project(self, name: str = "t1334") -> Path:
        root = self.make_project(name)
        return root

    def test_fail_receipt_without_newer_evidence_stays_current(self):
        """The red gate must survive when nothing has remediated it."""
        root = self._project("plain")
        write_fail_receipt(root, work="T-1240", ts=_utc_now())
        status = C.conformance_status(root, gate="core")
        self.assertEqual(status["status"], C.STATUS_CURRENT_FAIL)
        decision = C.conformance_decision(root, gate="core")
        self.assertEqual(
            decision["disposition"], C.CONFORMANCE_DISPOSITION_REMEDIATION_REQUIRED
        )
        self.assertEqual(decision["remediation_command"], "saipen work reverify T-1240")

    def test_executed_reverify_after_fail_demotes_the_gate(self):
        """The measured incident: a newer executed cure un-blocks idle continue."""
        root = self._project("cured")
        fail_ts = _utc_now()
        write_fail_receipt(root, work="T-1240", ts=fail_ts)
        self.assertEqual(
            C.conformance_status(root, gate="core")["status"], C.STATUS_CURRENT_FAIL
        )
        write_reverify(
            root,
            receipt_id="RV-000379",
            work="T-1240",
            created_at=_later(fail_ts),
        )
        status = C.conformance_status(root, gate="core")
        self.assertEqual(status["status"], C.STATUS_STALE_FAIL)
        self.assertIn("RV-000379", status["reason"])
        self.assertIn("T-1240", status["reason"])
        decision = C.conformance_decision(root, gate="core")
        self.assertNotEqual(
            decision["disposition"], C.CONFORMANCE_DISPOSITION_REMEDIATION_REQUIRED
        )
        self.assertEqual(decision["remediation_command"], C.CONFORMANCE_REMEDIATION_COMMAND)

    def test_attested_only_reverify_does_not_demote(self):
        """OPS.md: an attested-only contract is never closure proof."""
        root = self._project("attested")
        fail_ts = _utc_now()
        write_fail_receipt(root, work="T-1240", ts=fail_ts)
        write_reverify(
            root,
            receipt_id="RV-000284",
            work="T-1240",
            created_at=_later(fail_ts),
            evidence_class="attested",
        )
        self.assertEqual(
            C.conformance_status(root, gate="core")["status"], C.STATUS_CURRENT_FAIL
        )

    def test_failed_reverify_does_not_demote(self):
        root = self._project("still-red")
        fail_ts = _utc_now()
        write_fail_receipt(root, work="T-1240", ts=fail_ts)
        write_reverify(
            root,
            receipt_id="RV-000377",
            work="T-1240",
            created_at=_later(fail_ts),
            verdict="FAIL",
        )
        self.assertEqual(
            C.conformance_status(root, gate="core")["status"], C.STATUS_CURRENT_FAIL
        )

    def test_reverify_for_other_work_does_not_demote(self):
        root = self._project("other-work")
        fail_ts = _utc_now()
        write_fail_receipt(root, work="T-1240", ts=fail_ts)
        write_reverify(
            root, receipt_id="RV-000400", work="T-1299", created_at=_later(fail_ts)
        )
        self.assertEqual(
            C.conformance_status(root, gate="core")["status"], C.STATUS_CURRENT_FAIL
        )

    def test_reverify_for_other_tree_does_not_demote(self):
        root = self._project("other-tree")
        fail_ts = _utc_now()
        write_fail_receipt(root, work="T-1240", ts=fail_ts)
        write_reverify(
            root,
            receipt_id="RV-000401",
            work="T-1240",
            created_at=_later(fail_ts),
            source_head="0" * 40,
        )
        self.assertEqual(
            C.conformance_status(root, gate="core")["status"], C.STATUS_CURRENT_FAIL
        )

    def test_older_reverify_does_not_demote(self):
        """Evidence the receipt already saw cannot demote it."""
        root = self._project("older")
        fail_ts = _utc_now()
        write_reverify(
            root, receipt_id="RV-000402", work="T-1240", created_at=_earlier(fail_ts)
        )
        write_fail_receipt(root, work="T-1240", ts=fail_ts)
        self.assertEqual(
            C.conformance_status(root, gate="core")["status"], C.STATUS_CURRENT_FAIL
        )

    def test_pass_receipt_is_never_demoted(self):
        """Green plus more evidence is still green."""
        root = self._project("green")
        write_receipt(root, "PASS", ts=_utc_now())
        write_reverify(
            root, receipt_id="RV-000403", work="T-1240", created_at=_utc_now()
        )
        self.assertEqual(
            C.conformance_status(root, gate="core")["status"], C.STATUS_CURRENT_PASS
        )

    def test_ignores_malformed_reverify_files(self):
        root = self._project("junk")
        fail_ts = _utc_now()
        write_fail_receipt(root, work="T-1240", ts=fail_ts)
        out = root / ".saipen" / "recovery" / "conformance" / "reverify"
        out.mkdir(parents=True, exist_ok=True)
        (out / "RV-000404.json").write_text("{not json", encoding="utf-8")
        (out / "not-a-receipt.json").write_text("{}", encoding="utf-8")
        write_reverify(
            root, receipt_id="RV-000405", work="T-1240", created_at=_later(fail_ts)
        )
        status = C.conformance_status(root, gate="core")
        self.assertEqual(status["status"], C.STATUS_STALE_FAIL)
        self.assertIn("RV-000405", status["reason"])

    # -- the reported symptom, driven through the real router gate ----------

    def test_idle_continue_still_blocked_while_the_cure_is_missing(self):
        """No cure, no release: the red gate keeps owning idle continuation."""
        root = self._project("idle-red")
        write_fail_receipt(root, work="T-1240", ts=_utc_now())
        gated = router_mod.gate_route(root, _idle())
        self.assertIsNotNone(gated)
        self.assertFalse(gated["ok"])
        self.assertEqual(gated["reason"], "conformance-remediation")
        self.assertEqual(gated["action"], "saipen work reverify T-1240")

    def test_idle_continue_is_released_once_the_cure_is_executed(self):
        """The measured incident: `continue` must stop naming a cured ticket."""
        root = self._project("idle-cured")
        fail_ts = _utc_now()
        write_fail_receipt(root, work="T-1240", ts=fail_ts)
        self.assertIsNotNone(router_mod.gate_route(root, _idle()))
        write_reverify(
            root, receipt_id="RV-000379", work="T-1240", created_at=_later(fail_ts)
        )
        self.assertIsNone(router_mod.gate_route(root, _idle()))


def _later(ts: str) -> str:
    import datetime

    stamp = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return (stamp + datetime.timedelta(minutes=9)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _earlier(ts: str) -> str:
    import datetime

    stamp = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return (stamp - datetime.timedelta(minutes=9)).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    unittest.main()

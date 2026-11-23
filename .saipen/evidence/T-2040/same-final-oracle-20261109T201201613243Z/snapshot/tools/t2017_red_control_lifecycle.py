"""T-2017 / SRC-387 RED control: prove the repaired lifecycle check can go red.

`red-control-before-green` (KNOWLEDGE) is the law this file satisfies: a
repaired check earns belief only from a demonstrated red state on its own
condition, with the verifier held fixed. No archived pre-fix copy of
`installed_host_acceptance.py` survives in this repository, so the archived
algorithm is replicated here verbatim from the SRC-387 handoff text:

  * "counting distinct completed ordinals after checking only that the group
    contains at least one arbitrary START";
  * classify by the ENCLOSING record status, not the receipt's;
  * verify the FIRST 50 lifecycle records, then stop.

Each fixture is then run through BOTH algorithms. The control passes only when
the archived replica reproduces the handoff's false result AND the live
`_authenticated_lifecycle` refuses it. Run it directly; it is not a unittest
module on purpose (name has no `test_` prefix, so the declared family does not
discover it).

    python tools/t2017_red_control_lifecycle.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import installed_host_acceptance as probe  # noqa: E402
from saipen_engine import host_authority_client, host_dispatch  # noqa: E402

MAX_LEDGER_VERIFY = 50


def _receipt(campaign_id: str, *, status: str, gen: int, it: int,
             lineage: str = "lineage-1", host: str = "h-1") -> dict:
    return {
        "schema_version": host_dispatch.ACCEPTANCE_SCHEMA_VERSION,
        "status": status,
        "campaign_id": campaign_id,
        "iteration_id": it,
        "worker_generation": gen,
        "idempotency_key": f"{campaign_id}-{gen}-{it}",
        "accepting_host": host,
        "project_lineage": lineage,
        "accepted_request_digest": f"{campaign_id}-{gen}-{it}",
        "goal_binding": {"path": "STATE.md",
                         "fingerprint": f"goal-{lineage[:8]}"},
    }


def archived_algorithm(campaign_dir: Path) -> dict:
    """The pre-repair algorithm, replicated from the handoff description."""
    stages = {
        "turn_started": False,
        "turn_completed": False,
        "paired_campaign": False,
        "multi_turn_continuation": 0,
        "acceptance_tier": None,
        "host_accepted": False,
    }
    ledger = host_dispatch._load_dispatch_ledger(campaign_dir)
    campaigns: dict[str, dict] = {}
    checked = 0
    for record in ledger.values():
        if not isinstance(record, dict) or checked >= MAX_LEDGER_VERIFY:
            continue
        status = record.get("status")
        if status not in (
            host_dispatch.HOST_ACCEPTED,
            host_dispatch.TURN_STARTED,
            host_dispatch.TURN_COMPLETED,
        ):
            continue
        checked += 1
        receipt = record.get("receipt")
        if not host_dispatch._broker_verified_receipt(
            receipt if isinstance(receipt, dict) else record
        ):
            continue
        stages["host_accepted"] = True
        identity = dict(record)
        if isinstance(receipt, dict):
            identity.update(receipt)
        binding = str(identity.get("campaign_id") or "")
        group = campaigns.setdefault(binding, {"started": [], "completed": []})
        ordinal = (int(identity.get("worker_generation") or -1),
                   int(identity.get("iteration_id") or -1))
        # Classify by the ENCLOSING status, not the receipt's (finding B).
        if status == host_dispatch.TURN_STARTED:
            group["started"].append(ordinal)
        elif status == host_dispatch.TURN_COMPLETED:
            group["completed"].append(ordinal)
    longest = 0
    for group in campaigns.values():
        started, completed = group["started"], group["completed"]
        if started and completed:
            stages["turn_started"] = True
            stages["turn_completed"] = True
            stages["paired_campaign"] = True
            longest = max(longest, len(set(completed)))
    stages["multi_turn_continuation"] = max(0, longest - 1)
    if longest >= 3:
        stages["acceptance_tier"] = probe.OVERNIGHT_PRODUCTION_ACCEPTANCE
    elif longest >= 2:
        stages["acceptance_tier"] = probe.MULTI_TURN_CONTINUATION_VERIFIED
    elif longest >= 1:
        stages["acceptance_tier"] = probe.SINGLE_TURN_COMPLETED
    return stages


def _write(campaign_dir: Path, records: list[tuple[str, dict]]) -> None:
    campaign_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"key": key, "record": record}, sort_keys=True) + "\n"
        for key, record in records
    ]
    with open(campaign_dir / host_dispatch.DISPATCH_LEDGER_JOURNAL, "a",
              encoding="utf-8") as fh:
        fh.writelines(lines)


def _rec(key: str, status: str, campaign_id: str, *, gen: int = 1, it: int = 1) -> tuple:
    """One journal record: wrapper status plus its receipt."""
    return (key, {"status": status,
                  "receipt": _receipt(campaign_id, status=status, gen=gen, it=it)})


def _fixture_a(root: Path) -> Path:
    campaign_dir = root / ".saipen" / "campaign"
    recs = [_rec("s1", host_dispatch.TURN_STARTED, "camp-A", it=1)]
    recs += [_rec(f"c{it}", host_dispatch.TURN_COMPLETED, "camp-A", it=it)
             for it in (2, 3, 4)]
    _write(campaign_dir, recs)
    return campaign_dir


def _fixture_b(root: Path) -> Path:
    campaign_dir = root / ".saipen" / "campaign"
    started = _receipt("camp-A", status=host_dispatch.TURN_STARTED, gen=1, it=1)
    _write(campaign_dir, [
        ("s1", {"status": host_dispatch.TURN_STARTED, "receipt": started}),
        ("c1", {"status": host_dispatch.TURN_COMPLETED, "receipt": dict(started)}),
    ])
    return campaign_dir


def _fixture_c(root: Path) -> Path:
    campaign_dir = root / ".saipen" / "campaign"
    recs = [_rec(f"a{i}", host_dispatch.HOST_ACCEPTED, "camp-A", it=i)
            for i in range(60)]
    recs.append(_rec("s", host_dispatch.TURN_STARTED, "camp-A", it=99))
    recs.append(_rec("c", host_dispatch.TURN_COMPLETED, "camp-A", it=99))
    _write(campaign_dir, recs)
    return campaign_dir


def main() -> int:
    failures: list[str] = []
    with mock.patch.object(host_authority_client, "verify_record", lambda *a, **k: True):
        for name, builder, archived_expect, fixed_expect in (
            ("A: unpaired completions", _fixture_a,
             probe.OVERNIGHT_PRODUCTION_ACCEPTANCE, False),
            ("B: wrapper says COMPLETE, receipt says START", _fixture_b,
             probe.SINGLE_TURN_COMPLETED, False),
            ("C: 60 older acceptances before the pair", _fixture_c,
             None, True),  # archived returns HOST_ACCEPTED_NOT_EXECUTION (no pair found)
        ):
            with tempfile.TemporaryDirectory(prefix="t2017-red-") as tmp:
                campaign_dir = builder(Path(tmp))
                arch = archived_algorithm(campaign_dir)
                fixed = probe._authenticated_lifecycle(campaign_dir)
            ok_arch = (
                arch["acceptance_tier"] == archived_expect
                if archived_expect is not None
                else not arch["paired_campaign"]
            )
            ok_fixed = fixed["paired_campaign"] is fixed_expect
            line = (
                f"{name}: archived tier={arch['acceptance_tier']!r} "
                f"paired={arch['paired_campaign']} | repaired tier={fixed['acceptance_tier']!r} "
                f"paired={fixed['paired_campaign']} truncated={fixed['truncated_unverified']}"
            )
            print(line)
            if not ok_arch:
                failures.append(f"{name}: archived replica did not reproduce the false result")
            if not ok_fixed:
                failures.append(f"{name}: repaired verifier did not refuse/accept as expected")
    if failures:
        print("\nRED CONTROL FAILED:")
        for item in failures:
            print(" -", item)
        return 1
    print("\nRED CONTROL PASSED: the archived algorithm reproduces every false "
          "result; the repaired verifier refuses each one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

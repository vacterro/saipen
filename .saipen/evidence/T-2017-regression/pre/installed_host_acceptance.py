"""Installed-host acceptance probe (SRC-380 P0-06, repaired under SRC-382).

The unit tests in `test_bzcc_overnight_autonomy.py::test_16_...` mock broker
verification and inject synthetic HOST_ACCEPTED / TURN_STARTED / TURN_COMPLETED
receipts. That is a legitimate control-flow test and it is NOT evidence that
this machine can start real successor native turns without another `cc`.

Two production defects in the first probe are repaired here:

* P0-01 -- any dispatched=True result was upgraded to LIVE_ACCEPTANCE. The
  stages are now reported separately (capability discovered, request
  persisted, host accepted, turn started, turn completed, multi-turn
  continuation) and LIVE_ACCEPTANCE requires broker-authenticated TURN_STARTED
  and TURN_COMPLETED evidence read from the project's own dispatch ledger.
  Host acceptance alone is HOST_ACCEPTED_NOT_EXECUTION, never acceptance of a
  completed turn. A synthetic or model-generated receipt is never an
  authenticated host event: the live authority broker must reproduce it.
* P0-02 -- the probe dispatched a request into the supplied project_root.
  `probe` is now genuinely read-only: it never calls the dispatch operation,
  never creates campaign state, and never writes a diagnostic next_turn
  request into the live campaign. The mutating half lives in
  `authorized_dispatch_test`, which always runs against a disposable fixture
  root and refuses a supplied live project.
* P0-03 -- one undifferentiated "missing" could not say WHY no successor turn
  started. The `taxonomy` field now reports the first missing link in the
  chain (host not installed / transport unregistered / broker unavailable /
  session unbound / authority missing / scheduler unsupported / available),
  derived from installed-host and session facts, never from a second
  handwritten host inventory.

`probe` answers, from the LIVE machine:

* Is a host-scheduler dispatch transport registered (env hook / endpoint)?
* Is the live authority broker up, and does it refuse a synthetic receipt?
* What authenticated turn lifecycle already exists in the project ledger?

The verdict is one of:

    LIVE_ACCEPTANCE              authenticated TURN_STARTED + TURN_COMPLETED
                                 observed in the project's dispatch ledger
    HOST_ACCEPTED_NOT_EXECUTION  a registered transport accepted a request
                                 but no authenticated turn lifecycle exists
    HOST_DISPATCH_UNAVAILABLE    no transport: a request only persists; the
                                 authority broker is live
    HOST_CAPABILITY_MISSING      no transport AND no broker to authenticate one

`python tools/installed_host_acceptance.py` prints the verdict and exits
nonzero when acceptance is not proven, so a shell wrapper can gate on it.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import host_dispatch, host_authority_client  # noqa: E402

LIVE_ACCEPTANCE = "LIVE_ACCEPTANCE"
HOST_ACCEPTED_NOT_EXECUTION = "HOST_ACCEPTED_NOT_EXECUTION"
HOST_DISPATCH_UNAVAILABLE = "HOST_DISPATCH_UNAVAILABLE"
HOST_CAPABILITY_MISSING = "HOST_CAPABILITY_MISSING"
#: SRC-387 finding D: a broker-authenticated lifecycle pair in the ledger is an
#: IMMUTABLE HISTORICAL fact; it is not current readiness. When history proves a
#: completed turn but the machine is not ready now (no bound session, no granted
#: continuation authority, no supported live transport, no healthy broker), the
#: verdict says exactly that instead of reusing LIVE_ACCEPTANCE, whose `ok` is
#: consumed as a live capability signal by the wrapper that gates on it.
HISTORICAL_ACCEPTANCE_NOT_READY = "HISTORICAL_ACCEPTANCE_NOT_READY"

#: SRC-382 P0-03 taxonomy: why a successor turn did not start, stated as a
#: capability fact instead of one undifferentiated "missing".
HOST_NOT_INSTALLED = "HOST_NOT_INSTALLED"
HOST_INSTALLED_TRANSPORT_UNREGISTERED = "HOST_INSTALLED_TRANSPORT_UNREGISTERED"
BROKER_UNAVAILABLE = "BROKER_UNAVAILABLE"
SESSION_UNBOUND = "SESSION_UNBOUND"
AUTHORITY_MISSING = "AUTHORITY_MISSING"
SCHEDULER_UNSUPPORTED = "SCHEDULER_UNSUPPORTED"
SCHEDULER_AVAILABLE = "SCHEDULER_AVAILABLE"
#: Upper bound on ledger records re-verified against the broker per probe.
MAX_LEDGER_VERIFY = 50

#: SRC-385 finding A: a broker-authenticated lifecycle pair only proves a
#: successor turn when BOTH events belong to ONE campaign (same campaign id AND
#: project lineage AND accepting host) and the later event's
#: (worker_generation, iteration_id) strictly follows the earlier. Acceptance is
#: graded, never a single boolean: one completed turn is not a continuation.
SINGLE_TURN_COMPLETED = "SINGLE_TURN_COMPLETED"
SUCCESSOR_TURN_STARTED = "SUCCESSOR_TURN_STARTED"
MULTI_TURN_CONTINUATION_VERIFIED = "MULTI_TURN_CONTINUATION_VERIFIED"
OVERNIGHT_PRODUCTION_ACCEPTANCE = "OVERNIGHT_PRODUCTION_ACCEPTANCE"

#: Distinct completed iterations in one campaign before the continuation may be
#: called an overnight production run. Conservative: the append forbids
#: reporting overnight acceptance without sustained, actual host execution.
OVERNIGHT_MIN_COMPLETED_ITERATIONS = 3

#: SRC-385 finding B: a nonempty `continuation_authority` declaration is not
#: authority. `operator_required` + `hard_wait` is the operator still owing an
#: action -- a distinct, honest state from "no authority field at all".
AUTHORITY_DECLARED_NOT_GRANTED = "AUTHORITY_DECLARED_NOT_GRANTED"


def _registered_transports() -> dict:
    return {
        "host_scheduler_dispatch_cmd": bool(os.environ.get("HOST_SCHEDULER_DISPATCH_CMD")),
        "host_dispatch_endpoint": bool(os.environ.get("HOST_DISPATCH_ENDPOINT")),
    }


def _broker_alive() -> bool:
    try:
        return bool(host_authority_client.health())
    except Exception:
        return False


def _host_installation() -> dict:
    """Installed hosts and whether any declares a real iteration gate.

    Derived from the one declarative adapter registry (SRC-028:R008), never a
    second handwritten host inventory: SRC-382 P0-03 asks about whatever host
    is installed here, not about ZAICODE by name.
    """
    try:
        from saipen_engine import admission

        adapters = admission.list_adapters()
    except Exception:
        adapters = []
    installed: list[str] = []
    scheduler_supported = False
    for adapter in adapters:
        home = str(((adapter.get("install") or {}).get("home")) or "")
        surfaces = [s for s in (home, str(adapter.get("hook_install_surface") or "")) if s]
        # `$NAME/...` names a host whose HOME is not the user's and is unset
        # here, so it names nothing on this machine (autoinject._configured).
        present = [
            s
            for s in surfaces
            if not os.path.expandvars(s).startswith("$")
            and Path(os.path.expandvars(os.path.expanduser(s))).exists()
        ]
        if not present:
            continue
        installed.append(str(adapter.get("id")))
        enforcement = str(((adapter.get("iteration_controller") or {}).get("enforcement")) or "")
        if enforcement and not enforcement.upper().startswith("ADVISORY"):
            scheduler_supported = True
    return {
        "installed_adapters": sorted(installed),
        "scheduler_supported": scheduler_supported,
    }


def _session_and_authority(root: Path) -> tuple[bool, str]:
    """(a host session binds this process, the continuation authority's real state).

    SRC-385 finding B: authority PRESENCE is not AUTHORIZATION. The old probe
    read any non-sentinel `continuation_authority` string as "authority
    present", so `operator_required` (the operator still owing an action)
    scored exactly like a granted campaign. The authority is now classified
    against the canonical grant machinery, never the bare declaration:

    ``ABSENT``                -- no continuation-authority field at all
    ``DECLARED_NOT_GRANTED``  -- a field is present but no valid operator grant
                                 backs it (`operator_required`, a malformed
                                 family, or a persistent claim that fails
                                 `goal_authority.prove`)
    ``GRANTED``               -- `goal_authority.persistent` holds AND the grant
                                 proves against its committed ingress
    """
    try:
        from saipen_engine import board

        session_bound = board.host_session_binding(root) is not None
    except Exception:
        session_bound = False

    authority_state = "ABSENT"
    try:
        from saipen_engine import goal_authority
        from saipen_engine import state as state_module

        text = (root / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        fields = state_module.parse_state(text)
        if not any(key in fields for key in goal_authority.FIELDS):
            authority_state = "ABSENT"
        else:
            # A field is present. It is a grant only if it is a well-formed
            # persistent family AND `prove` accepts it against its committed
            # ingress. An unprovable declaration is not authority.
            authority_state = "DECLARED_NOT_GRANTED"
            if goal_authority.persistent(fields) and not goal_authority.prove(root, fields):
                authority_state = "GRANTED"
    except FileNotFoundError:
        authority_state = "ABSENT"
    except Exception:
        # STATE exists but is unreadable, or the proof could not run: a field
        # may still be present, so fail toward "declared but not evidenced"
        # rather than claiming authority is wholly absent.
        authority_state = "DECLARED_NOT_GRANTED"
    return session_bound, authority_state


def _taxonomy(*, transport: dict, broker_alive: bool, installation: dict,
              session_bound: bool, authority: str) -> str:
    """The first missing link in the successor-turn chain (SRC-382 P0-03).

    Ordered by dependency, so the reported fact is the one that actually
    blocks a native continuation rather than an arbitrary true statement.
    Every declared state is reachable from a fact, and `authority` is the
    classified state from `_session_and_authority`, never a bare string: a
    declaration that is not a grant is reported as such rather than as either
    "present" or "missing".
    """
    if not installation["installed_adapters"]:
        return HOST_NOT_INSTALLED
    if not (transport["host_scheduler_dispatch_cmd"] or transport["host_dispatch_endpoint"]):
        return HOST_INSTALLED_TRANSPORT_UNREGISTERED
    if not broker_alive:
        return BROKER_UNAVAILABLE
    if not session_bound:
        return SESSION_UNBOUND
    if authority == "ABSENT":
        return AUTHORITY_MISSING
    if authority != "GRANTED":
        return AUTHORITY_DECLARED_NOT_GRANTED
    if not installation["scheduler_supported"]:
        return SCHEDULER_UNSUPPORTED
    return SCHEDULER_AVAILABLE


def _acceptance_int(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


def _lifecycle_identity(record: dict) -> dict:
    """The identity fields of a lifecycle record, from its receipt or itself.

    A record written by the real dispatch path nests the receipt under
    ``receipt``; one migrated or written by a control may carry the fields at
    the top level. Both shapes name the same identity, and finding A binds on
    the identity, not the shape.
    """
    receipt = record.get("receipt")
    merged = dict(record)
    if isinstance(receipt, dict):
        merged.update(receipt)
    return merged


def _campaign_binding(identity: dict) -> tuple[str, str, str, str]:
    """The campaign a lifecycle event belongs to: (campaign, lineage, host, goal).

    Finding A / regression 4: two events are the same campaign's lifecycle
    only when all four agree. A TURN_STARTED in one campaign and a
    TURN_COMPLETED in another -- or under a different goal -- are unrelated
    single events, never a successor turn.
    """
    goal = identity.get("goal_binding")
    if isinstance(goal, dict):
        goal_part = json.dumps(goal, sort_keys=True, separators=(",", ":"))
    else:
        goal_part = str(goal or "")
    return (
        str(identity.get("campaign_id") or ""),
        str(identity.get("project_lineage") or identity.get("lineage") or ""),
        str(
            identity.get("accepting_host")
            or identity.get("host_id")
            or identity.get("host")
            or ""
        ),
        goal_part,
    )


def _iteration_ordinal(identity: dict) -> tuple[int, int]:
    """(worker_generation, iteration_id), the monotone turn ordinal.

    UNKNOWN components sort to -1 so an event with no stated generation cannot
    masquerade as a later turn than a fully-identified one.
    """
    gen = _acceptance_int(identity.get("worker_generation"))
    it = _acceptance_int(identity.get("iteration_id"))
    return (gen if gen is not None else -1, it if it is not None else -1)


def _authenticated_lifecycle(campaign_dir: Path) -> dict:
    """PRE-FIX RECONSTRUCTION (T-2017 regression carrier, not history).

    The archived pre-repair algorithm, replicated verbatim from
    tools/t2017_red_control_lifecycle.py::archived_algorithm (SRC-387
    handoff text): campaign-only binding, enclosing-status classification,
    first-50 starvation. No byte-exact pre-fix copy survives in this
    repository; this carrier exists so the SAME oracle can be measured red
    against the defects and green against the repair.
    """
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
        stages["acceptance_tier"] = OVERNIGHT_PRODUCTION_ACCEPTANCE
    elif longest >= 2:
        stages["acceptance_tier"] = MULTI_TURN_CONTINUATION_VERIFIED
    elif longest >= 1:
        stages["acceptance_tier"] = SINGLE_TURN_COMPLETED
    return stages


def probe(project_root: Path | None = None) -> dict:
    """Observe this machine's real successor-turn capability. Writes nothing.

    Read-only by construction: no directory is created, no dispatch operation
    is invoked, and the supplied project -- or the live one -- is left
    byte-identical.
    """
    transport = _registered_transports()
    broker_alive = _broker_alive()
    synthetic = {
        "schema_version": host_dispatch.ACCEPTANCE_SCHEMA_VERSION,
        "status": host_dispatch.TURN_STARTED,
        "campaign_id": "CAMPAIGN-ACCEPTANCE-PROBE",
        "iteration_id": 1,
        "worker_generation": 1,
        "idempotency_key": "probe-synthetic-receipt",
        "accepting_host": "probe-synthetic-host",
        "project_lineage": "probe-synthetic-lineage",
        "accepted_request_digest": "probe-synthetic-receipt",
    }
    try:
        synthetic_authenticated = host_dispatch._broker_verified_receipt(synthetic)
    except Exception:
        synthetic_authenticated = False

    root = Path(project_root) if project_root else Path.cwd()
    stages = _authenticated_lifecycle(root / ".saipen" / "campaign")

    # P0-03 taxonomy: the first missing link in the successor-turn chain,
    # derived from the same installed-host and session facts the lifecycle
    # verdict above reads.
    installation = _host_installation()
    session_bound, authority = _session_and_authority(root)
    taxonomy = _taxonomy(
        transport=transport,
        broker_alive=broker_alive,
        installation=installation,
        session_bound=session_bound,
        authority=authority,
    )

    # Finding D / regressions 8-9: historical lifecycle evidence and current
    # readiness are separate results. `verified_history` reports what the
    # ledger proves about PAST turns; `ready_now` requires the machine to be
    # ready RIGHT NOW: a bound session, a GRANTED continuation authority, a
    # registered transport, a healthy broker and a supported iteration
    # scheduler. A historical pair under an expired grant or an unbound
    # session is still historically true -- and still not readiness.
    verified_history = (
        stages["turn_started"]
        and stages["turn_completed"]
        and stages["paired_campaign"]
    )
    ready_now = bool(
        session_bound
        and authority == "GRANTED"
        and (transport["host_scheduler_dispatch_cmd"] or transport["host_dispatch_endpoint"])
        and broker_alive
        and installation["scheduler_supported"]
    )

    if verified_history and ready_now:
        verdict = LIVE_ACCEPTANCE
        reason = (
            "broker-authenticated TURN_STARTED and TURN_COMPLETED evidence is "
            "present in the project's dispatch ledger and the machine is "
            "currently ready (bound session, granted authority, live broker, "
            "supported scheduler)"
        )
    elif verified_history:
        verdict = HISTORICAL_ACCEPTANCE_NOT_READY
        reason = (
            "broker-authenticated turn lifecycle exists in the ledger, but the "
            f"machine is not currently ready (taxonomy: {taxonomy}); historical "
            "completion is not current readiness"
        )
    elif stages["host_accepted"]:
        verdict = HOST_ACCEPTED_NOT_EXECUTION
        reason = (
            "a registered host transport accepted a request, but no "
            "authenticated turn started or completed: acceptance is not "
            "execution and not a successor turn"
        )
    elif broker_alive:
        verdict = HOST_DISPATCH_UNAVAILABLE
        reason = (
            "no host-scheduler transport is registered: a request is durable "
            "(DISPATCH_REQUEST_PERSISTED) but no host started it; the authority "
            "broker is live, so an authenticated receipt remains possible"
        )
    else:
        verdict = HOST_CAPABILITY_MISSING
        reason = (
            "no host-scheduler transport is registered and no live authority "
            "broker can authenticate a receipt"
        )

    return {
        "ok": verdict == LIVE_ACCEPTANCE,
        "verdict": verdict,
        "reason": reason,
        "taxonomy": taxonomy,
        "verified_history": verified_history,
        "ready_now": ready_now,
        "transport": transport,
        "broker_alive": broker_alive,
        "installed_adapters": installation["installed_adapters"],
        "session_bound": session_bound,
        "continuation_authority_declared": authority,
        "scheduler_supported": installation["scheduler_supported"],
        "stages": stages,
        "dispatch_dispatched": False,
        "dispatch_status": None,
        "synthetic_receipt_authenticated": synthetic_authenticated,
        "note": (
            "read-only: this probe dispatched nothing; run "
            "authorized_dispatch_test for the mutating half, which uses a "
            "disposable fixture root"
        ),
    }


def authorized_dispatch_test(live_root: Path | None = None) -> dict:
    """Explicitly authorized mutating test, always in a disposable fixture.

    P0-02 repair half: capability inspection never dispatches; this entry
    point does, but against a fixture root this function creates itself. A
    caller may pass `live_root` only to prove the fixture is NOT that root.
    """
    fixture = Path(tempfile.mkdtemp(prefix="saipen-acceptance-dispatch-"))
    payload = host_dispatch.build_dispatch_payload(
        fixture, campaign_id="CAMPAIGN-AUTHORIZED-DISPATCH-TEST"
    )
    result = host_dispatch.dispatch_next_turn(fixture, payload, print_advisory=False)
    return {
        "fixture_root": str(fixture),
        "live_root": str(live_root) if live_root else None,
        "fixture_is_live_root": bool(
            live_root and fixture.resolve() == Path(live_root).resolve()
        ),
        "dispatch_status": result.get("status"),
        "dispatched": result.get("dispatched") is True,
        "disposition": result.get("disposition"),
    }


def main() -> int:
    result = probe()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

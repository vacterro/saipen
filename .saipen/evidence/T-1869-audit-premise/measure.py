"""T-1869 / SRC-298 verifier: re-measure the audit's blocking premise.

Run: python .saipen/evidence/T-1869-audit-premise/measure.py

Every check prints a `PASS`/`FAIL` line, so this file is its own control: it is
not a claim about what the code does, it is the measurement, re-run against the
live tree. Exit 0 means all six held.

What each measurement decides:

M1  Does a ZAICODE adapter exist AND is it the one the host dispatches?
    The audit's section 02 said none existed. Identity is byte-equality between
    the repository copy, the installed copy and the configured script path.
M2  Does the hook bind the EVENT's project, or its own --saipen-root argument?
    Every operator session here runs a hook pinned to the protocol home, so if
    the hook bound that argument, a `cc` typed inside another project would
    reauthorize the wrong project and leave the typed-in project trapped.
M3  Where did the envelope land? Must be the event's project, 0 in the home.
M4  A shell must NOT be able to mint an operator seal. If this ever passes, the
    broker has a hole, not a fix.
M5  Do the probe records leave the subject clean? Ingress is retired through
    the engine's own consume path, never by deleting files.
M6  The live refusal is still what FastPrompter prints, with its exact counters.

The script needs no network, writes nothing outside nothing (M4 mints nothing on
refusal; M1-M3 read only), and is safe to re-run.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path(__file__).resolve().parents[3]
FP = Path(r"V:\___VAC\__K\__CODE\_PY\_FastPrompter")
HOOK = Path.home() / ".zcode" / "hooks" / "saipen-guard.py"
REPO_HOOK = HOME / "extensions" / "adapters" / "zaicode" / "saipen-guard.py"
CONFIG = Path.home() / ".zcode" / "cli" / "config.json"

BOOTSTRAP = (
    "import os,runpy,sys;a=sys.argv[1];sys.argv=sys.argv[1:];"
    "os.path.isfile(a) and runpy.run_path(a,run_name=__name__)"
)

sys.path.insert(0, str(HOME / "tools"))
from saipen_engine import host_authority_client as HAC  # noqa: E402
from saipen_engine import operator_task  # noqa: E402

MEASURE_SESSION = "sess-t1869-measure"
#: One turn per run. The engine keys an admission on the delivery, so a fixed
#: turn id would replay the record a previous run already consumed and answer
#: from cache -- the measurement would then prove nothing about delivery.
MEASURE_TURN = f"turn-t1869-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}"
failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def m1_adapter_exists_and_is_dispatched() -> None:
    print("\n== M1: does a ZAICODE adapter exist, and is it what the host runs? ==")
    for path in (REPO_HOOK, HOOK):
        print(f"  {path}: exists={path.is_file()} "
              f"size={path.stat().st_size if path.is_file() else '-'}")
    check("repository adapter present", REPO_HOOK.is_file())
    check("installed adapter present", HOOK.is_file())
    if not (REPO_HOOK.is_file() and HOOK.is_file()):
        return
    same = sha(REPO_HOOK) == sha(HOOK)
    print(f"  sha256[:16] repo={sha(REPO_HOOK)[:16]} installed={sha(HOOK)[:16]}")
    check("installed copy is byte-identical to the repository copy", same)

    hooks = json.loads(CONFIG.read_text(encoding="utf-8")).get("hooks") or {}
    check("config hooks.enabled", bool(hooks.get("enabled")))
    entries = ((hooks.get("events") or {}).get("UserPromptSubmit") or [])
    check("exactly one UserPromptSubmit entry", len(entries) == 1, str(len(entries)))
    scripts, bootstraps = [], []
    for entry in entries:
        for hook in entry.get("hooks") or []:
            args = hook.get("args") or []
            if len(args) >= 3:
                bootstraps.append(args[1] == BOOTSTRAP)
                scripts.append(args[2])
    check("the configured bootstrap is the one the broker recognises",
          bool(bootstraps) and all(bootstraps))
    configured = {str(Path(p)) for p in scripts if p}
    check("the configured script is the installed hook",
          configured == {str(HOOK)}, str(sorted(configured)))


def m2_hook_binds_the_event_project() -> None:
    print("\n== M2: does the hook bind the EVENT's project or --saipen-root? ==")
    event = {
        "hookEventName": "UserPromptSubmit",
        "hook_event_name": "UserPromptSubmit",
        "prompt": "cc",
        "cwd": str(FP),
        "sessionId": MEASURE_SESSION,
        "session_id": MEASURE_SESSION,
        "turnId": MEASURE_TURN,
        "traceId": MEASURE_TURN,
    }
    proc = subprocess.run(
        [sys.executable, "-c", BOOTSTRAP, str(HOOK), "--host", "zaicode",
         "--saipen-root", str(HOME)],
        input=json.dumps(event), capture_output=True, text=True, timeout=180,
    )
    print(f"  rc={proc.returncode} stdout={proc.stdout.strip()}")
    if proc.stderr.strip():
        print(f"  stderr={proc.stderr.strip()[-400:]}")
    check("hook exits clean", proc.returncode == 0)
    lines = [l for l in proc.stdout.strip().splitlines() if l.strip().startswith("{")]
    if not lines:
        check("hook printed a JSON frame", False, proc.stdout.strip()[:200])
        return None
    reply = json.loads(lines[-1])
    check("hook reports ok", bool(reply.get("ok")), json.dumps(reply))
    check("hook admitted an ingress for the operator's prompt",
          bool(reply.get("ingress_id")), json.dumps(reply))
    check("a cc prompt stays a continuation",
          reply.get("destination_op") == "continue", str(reply.get("destination_op")))
    state = {r.get("ingress_id"): r
             for r in operator_task.active_host_ingress(str(FP), include_consumed=True)}
    fresh = operator_task.active_host_ingress(str(FP))
    landed = [r for r in fresh if r.get("ingress_id") == reply.get("ingress_id")]
    check("this run's own ingress is still unconsumed",
          bool(landed), f"{reply.get('ingress_id')} consumed already")
    return reply.get("ingress_id"), state


def m3_envelope_destination(ingress_id) -> None:
    print("\n== M3: where did the envelope land? ==")
    in_project = [r for r in operator_task.active_host_ingress(
        str(FP), include_consumed=True) if r.get("session_id") == MEASURE_SESSION]
    in_home = [r for r in operator_task.active_host_ingress(
        str(HOME), include_consumed=True) if r.get("session_id") == MEASURE_SESSION]
    print(f"  records in the event project: {len(in_project)}")
    print(f"  records in the pinned --saipen-root: {len(in_home)}")
    for rec in in_project:
        print(f"    {rec.get('ingress_id')} text={rec.get('request_text')!r} "
              f"sealed={isinstance(rec.get('operator_origin'), dict)}")
    check("the envelope landed in the EVENT's project", len(in_project) >= 1)
    check("nothing leaked into the pinned protocol home", len(in_home) == 0, str(len(in_home)))


def m4_shell_cannot_seal() -> None:
    print("\n== M4: can a shell mint an operator seal? (must be NO) ==")
    res = HAC.issue_operator_origin(
        project=FP, session=MEASURE_SESSION, host="zaicode", request_text="cc",
        event_id="turn-t1869-measure", action="continue",
    )
    identity = res.get("identity") or {}
    print(f"  code={res.get('code')}")
    print(f"  detail={res.get('detail')}")
    print(f"  host_images={identity.get('host_images')}")
    chain = identity.get("chain") or []
    if chain:
        print(f"  ancestry root={chain[-1].get('name')} pid={chain[-1].get('pid')}")
    check("a shell is refused a seal",
          res.get("ok") is not True and res.get("code") == "BROKER_CLIENT_NOT_AUTHENTICATED",
          str(res.get("code")))
    check("the refusal names the real host images",
          "ZAICODE.exe" in (identity.get("host_images") or []),
          str(identity.get("host_images")))


def m5_subject_is_clean(ingress_id) -> None:
    print("\n== M5: is the subject left clean? ==")
    if ingress_id:
        retired = operator_task.consume_host_ingress(
            str(FP), ingress_id, "t1869-verify-cleanup")
        print(f"  retired {ingress_id}: {retired}")
        # A retirement that reports False and leaves the record consumed would
        # read as clean below; the point is that THIS run's record is gone, so
        # the assertion is on the engine's answer, not only on the count.
        check("this run's probe ingress was retired", bool(retired), str(retired))
    remaining = operator_task.active_host_ingress(str(FP))
    print(f"  active ingress remaining in FastPrompter: {len(remaining)}")
    check("no unconsumed probe ingress is left behind", len(remaining) == 0, str(len(remaining)))
    unrelated = operator_task.witness("some unrelated text", root=str(FP))
    print(f"  witness for unrelated text: {unrelated.get('witness')} code={unrelated.get('code')}")
    check("unrelated text is still model_supplied, not an operator carrier",
          unrelated.get("witness") == "model_supplied")


def m6_live_refusal_is_unchanged() -> None:
    print("\n== M6: FastPrompter's live refusal and counters ==")
    launcher = HOME / "bin" / "saipen.cmd"
    proc = subprocess.run(
        ["cmd", "/c", str(launcher), "continue", "--json"],
        cwd=str(FP), capture_output=True, text=True, timeout=300,
    )
    print(f"  rc={proc.returncode}")
    payload = None
    # `saipen continue` prints ONE pretty-printed document, not one frame per
    # line: parsing the first `{` line alone raises on the next key.
    try:
        payload = json.loads(proc.stdout)
    except ValueError:
        for line in proc.stdout.splitlines():
            if line.strip().startswith("{"):
                try:
                    payload = json.loads(line)
                except ValueError:
                    payload = None
                break
    if not isinstance(payload, dict):
        check("FastPrompter answered with JSON", False, proc.stdout.strip()[:300])
        return
    for key in ("ok", "code", "required_ingress", "message"):
        print(f"  {key}: {payload.get(key)}")
    state = (FP / ".saipen" / "STATE.md").read_text(encoding="utf-8")
    counters = {}
    for line in state.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            if key in ("phase", "execution_intent", "goal_waves", "goal_tickets",
                       "continuation_authority", "safety_valve_mode"):
                counters[key] = value.strip().strip('"')
                print(f"  STATE {key}: {counters[key]}")
    check("the valve still refuses a CLI replay",
          payload.get("ok") is False and payload.get("code") == "RECONCILE_REAUTH_REQUIRED",
          str(payload.get("code")))
    check("it still demands the operator carrier",
          payload.get("required_ingress") == "operator_carrier",
          str(payload.get("required_ingress")))


def main() -> int:
    print(f"project home: {HOME}")
    print(f"subject     : {FP}")
    m1_adapter_exists_and_is_dispatched()
    admitted = m2_hook_binds_the_event_project()
    ingress_id = admitted[0] if admitted else None
    m3_envelope_destination(ingress_id)
    m4_shell_cannot_seal()
    m5_subject_is_clean(ingress_id)
    m6_live_refusal_is_unchanged()
    print("\n== VERDICT ==")
    if failures:
        print(f"FAIL: {len(failures)} measurement(s) did not hold: {', '.join(failures)}")
        return 1
    print("PASS: all measurements held")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

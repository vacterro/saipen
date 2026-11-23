"""T-1859/SRC-291 durable control: prove the seal's worker binding by measurement.

Run:  python .saipen/evidence/T-1859-ingress-live/control.py

Builds the real broker with simulated OS facts (T-1844's kernel pattern) in the
REAL ZAICODE process shape -- host(10) -> hook(20), host(10) -> shell(22) ->
engine(23) -- and proves five things a claim alone cannot:

  A. the PRE-FIX binding (`os.getppid()`, i.e. the host pid) is refused;
  B. registering the hook itself succeeds;
  C. a SIBLING shell engine cannot spend the seal;
  D. the hook's OWN child engine can;
  E. a second spend is idempotent, not a fresh grant.

C is the load-bearing one: it is why the hook must renew from an engine it
starts, rather than leaving `saipen continue` to whatever the model does next.
Native identity and OS facts are simulated; no live host event is claimed.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

TOOLS = Path(__file__).resolve().parents[3] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import host_authority_broker as HB  # noqa: E402
from saipen_engine import host_authority_process as HP  # noqa: E402
from saipen_engine.pending_ingress import ingress_digest  # noqa: E402

HOST, HOOK, SHELL, ENGINE, CHILD = 10, 20, 22, 23, 24


def build_project(tmp: str) -> Path:
    root = Path(tmp) / "project"
    (root / ".saipen").mkdir(parents=True)
    (root / ".saipen/STATE.md").write_text(
        "---\nphase: SCOUT\nagent: fixture\ntask: T-1\n"
        "next_action: PHASE SCOUT T-1\nblocker: none\ntransition_from: PLAN\n"
        "saipen_version: 8\nmode: full\nupdated: 2026-10-24T00:00:00Z\n"
        "goal_waves: 0\ngoal_tickets: 0\n"
        "continuation_authority: operator_required\nauthority_until: budget\n"
        "safety_valve_mode: hard_wait\nexecution_intent: goal\n"
        "goal_ingress: goal-1\nauthority_source: E-1\n---\n",
        encoding="utf-8",
    )
    (root / ".saipen/IDENTITY.md").write_text(
        "---\nproject_lineage: lineage-0123456789abcdef0123456789abcdef\n---\n",
        encoding="utf-8",
    )
    return root


def main() -> int:
    failures: list[str] = []

    def check(name: str, ok: bool, detail: object = "") -> None:
        print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail else ""))
        if not ok:
            failures.append(name)

    tmp = tempfile.TemporaryDirectory(prefix="t1859-control-")
    root = build_project(tmp.name)
    facts = {
        HOST: HP.ProcessFact(HOST, None, "ZAICODE.exe", "ZAICODE", created=1),
        HOOK: HP.ProcessFact(HOOK, HOST, "python.exe", "hook", created=2),
        SHELL: HP.ProcessFact(SHELL, HOST, "bash.exe", "shell", created=3),
        ENGINE: HP.ProcessFact(ENGINE, SHELL, "python.exe", "engine", created=4),
        CHILD: HP.ProcessFact(CHILD, HOOK, "python.exe", "hook-child", created=5),
    }

    def ancestry(pid, limit=32):
        out = []
        while pid in facts and len(out) < limit:
            out.append(facts[pid])
            pid = facts[pid].ppid
        return out

    def native(peer, host, home):
        if getattr(peer, "pid", None) == HOOK:
            return True, None, {"host_pid": HOST, "hook_pid": HOOK, "detail": "simulated"}
        return False, HB.CODE_NOT_AUTHENTICATED, {"detail": "not the hook"}

    with mock.patch.object(HP, "ancestry", side_effect=ancestry):
        broker = HB.Broker(
            runtime=Path(tmp.name) / "broker", clock=lambda: 100.0,
            config={"capability_ttl_seconds": 60}, authenticator=native,
        )
        hook = SimpleNamespace(pid=HOOK)
        issued = broker.handle(
            {"op": "issue-origin", "project": str(root), "session": "s",
             "host": "zaicode", "event": "UserPromptSubmit", "request_text": "cc",
             "event_id": "e1", "action": "continue"}, hook,
        )
        proof = issued["proof"]
        pre = broker.handle(
            {"op": "register-origin-worker", "host": "zaicode",
             "proof": proof, "worker": HOST}, hook)
        check("A the pre-fix host-pid binding is refused",
              pre.get("ok") is False and "observed child" in str(pre.get("detail")),
              pre.get("detail"))
        post = broker.handle(
            {"op": "register-origin-worker", "host": "zaicode",
             "proof": proof, "worker": HOOK}, hook)
        check("B registering the hook itself succeeds", post.get("ok") is True,
              post.get("detail"))
        verify = {"op": "verify-origin", "proof": proof, "project": str(root),
                  "request_digest": ingress_digest("cc")}
        sibling = broker.handle(verify, SimpleNamespace(pid=ENGINE))
        check("C a sibling shell engine cannot spend the seal",
              sibling.get("ok") is False, sibling.get("detail"))
        child = broker.handle(verify, SimpleNamespace(pid=CHILD))
        check("D the hook's own child engine verifies", child.get("ok") is True,
              child.get("detail"))
        again = broker.handle(verify, SimpleNamespace(pid=CHILD))
        check("E a second spend is idempotent, not a new grant",
              again.get("ok") is True and again.get("action") == "continue",
              again.get("action"))
    tmp.cleanup()
    print(f"\n{len(failures)} FAIL")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

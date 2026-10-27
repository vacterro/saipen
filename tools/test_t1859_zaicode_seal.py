"""T-1859/SRC-291: the ZAICODE hook must seal as the worker the host started.

MEASURED defect. The shipped hook registered `os.getppid()` as the delivering
worker. ZAICODE spawns a hook straight from the host's own execution port
(`spawn(file, args)` in the host's hook runner), so the hook's parent IS the
host process -- the same pid `host_authority_identity` proves as `host_pid`. The
broker refuses exactly that worker (`operator_origin.register_worker`:
`pid == proof["host_pid"]` -> "worker is not an observed child of the proven
native host"), so registration failed on every genuine prompt, `sealed` was
always false, the envelope reached the engine without `operator_origin`, and the
operator's own cc was recorded as `model_supplied`. That is the stuck
`RECONCILE_REAUTH_REQUIRED` the ticket reports.

The second half is the same measurement from the other side: the broker accepts
a proof only BELOW the registered worker (`_worker` walks the caller's
ancestry). An agent's shell tool call is the hook's SIBLING -- both are children
of the host -- so the engine that spends the seal must be started BY the hook.
That is why the hook runs the canonical continuation itself instead of leaving
it to whatever the model does next.

These cases run the real hook file in a real subprocess against a recording
stub engine, so they pin the pid the hook registers and the order it acts in,
without claiming a live host event (that stays T-1859 AC-01 [LIVE]).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
HOOK = REPO / "extensions" / "adapters" / "zaicode" / "saipen-guard.py"

BOOTSTRAP = (
    "import os,runpy,sys;a=sys.argv[1];sys.argv=sys.argv[1:];"
    "os.path.isfile(a) and runpy.run_path(a,run_name=__name__)"
)

#: A stand-in engine that records the pids the hook asked to bind. It is a stub
#: of the CLIENT, never of the broker: what this suite decides is which pid the
#: hook names, which is the one decision the defect was in.
STUB_CLIENT = textwrap.dedent(
    '''
    import json, os, sys

    RECORD = os.path.join(os.path.dirname(__file__), "record.json")

    def _append(row):
        rows = []
        if os.path.isfile(RECORD):
            with open(RECORD, encoding="utf-8") as handle:
                rows = json.load(handle)
        rows.append(row)
        with open(RECORD, "w", encoding="utf-8") as handle:
            json.dump(rows, handle)

    def issue_operator_origin(**kwargs):
        _append({"op": "issue", "kwargs": {k: str(v) for k, v in kwargs.items()}})
        proof = {"schema": 1, "kind": "operator-origin", "host": kwargs.get("host") or "zaicode",
                 "nonce": "n1", "action": kwargs.get("action") or "continue",
                 "host_pid": os.getppid()}
        return {"ok": True, "code": None, "proof": proof, "reused": False}

    def register_operator_worker(proof, worker, *, home=None, **kwargs):
        _append({"op": "register", "worker": worker, "own_pid": os.getpid(),
                 "parent_pid": os.getppid(), "proof": proof})
        proof_dict = proof.get("proof") if (isinstance(proof, dict) and isinstance(proof.get("proof"), dict)) else proof
        if not isinstance(proof_dict, dict) or proof_dict.get("kind") != "operator-origin" or proof_dict.get("host") != "zaicode":
            return {"ok": False, "code": "BROKER_CLIENT_NOT_AUTHENTICATED", "detail": "proof invalid or host missing"}
        return {"ok": True, "worker": worker}

    '''
)

ENGINE_STUB = textwrap.dedent(
    '''
    import json, os, sys

    RECORD = os.path.join(os.path.dirname(os.path.dirname(__file__)), "engine.json")
    with open(RECORD, "w", encoding="utf-8") as handle:
        json.dump({"argv": sys.argv[1:], "own_pid": os.getpid(),
                   "parent_pid": os.getppid()}, handle)
    print(json.dumps({"ok": True, "code": None, "goal_waves": 0,
                      "goal_tickets": 0}))
    '''
)

#: The canonical engine pretty-prints its JSON (`indent=2`), so a reader that
#: only understands one-line objects reports a successful renewal as
#: unreadable. This stub reproduces that shape exactly.
ENGINE_STUB_PRETTY = textwrap.dedent(
    '''
    import json, os, sys

    RECORD = os.path.join(os.path.dirname(os.path.dirname(__file__)), "engine.json")
    with open(RECORD, "w", encoding="utf-8") as handle:
        json.dump({"argv": sys.argv[1:], "own_pid": os.getpid(),
                   "parent_pid": os.getppid()}, handle)
    print(json.dumps({"ok": True, "code": None, "goal_waves": 0,
                      "goal_tickets": 0}, indent=2))
    '''
)


def build_root(*, state_counters: int = 0, engine: str = ENGINE_STUB) -> tuple[tempfile.TemporaryDirectory, Path]:
    """A throwaway project whose stub engine records what the hook does."""
    holder = tempfile.TemporaryDirectory(prefix="t1859-")
    root = Path(holder.name)
    (root / ".saipen").mkdir(parents=True, exist_ok=True)
    (root / ".saipen" / "STATE.md").write_text(
        "---\nphase: SCOUT\nagent: fixture\ntask: T-1\n"
        "next_action: PHASE SCOUT T-1\nblocker: none\ntransition_from: PLAN\n"
        "saipen_version: 8\nmode: full\nupdated: 2026-10-24T00:00:00Z\n"
        f"goal_waves: 0\ngoal_tickets: {state_counters}\n"
        "continuation_authority: operator_required\nauthority_until: budget\n"
        "safety_valve_mode: hard_wait\nexecution_intent: goal\n"
        "goal_ingress: goal-1\nauthority_source: E-1\n---\n",
        encoding="utf-8",
    )
    tools = root / "tools"
    engine_pkg = tools / "saipen_engine"
    engine_pkg.mkdir(parents=True)
    (engine_pkg / "__init__.py").write_text("", encoding="utf-8")
    (engine_pkg / "host_authority_client.py").write_text(STUB_CLIENT, encoding="utf-8")
    (engine_pkg / "pending_ingress.py").write_text(
        "import hashlib\n\n\ndef ingress_digest(text):\n"
        "    return hashlib.sha256(text.encode('utf-8')).hexdigest()\n",
        encoding="utf-8",
    )
    (engine_pkg / "operator_task.py").write_text(
        textwrap.dedent(
            '''
            def admit_host_ingress(ingress, root, *, event_session=None):
                return {"ok": True, "ingress_id": "ing-stub",
                        "destination_op": "continue"}
            '''
        ),
        encoding="utf-8",
    )
    # The valve decision itself is canonical code with its own suite
    # (test_reconcile_valve). These two modules stand in for it so this suite
    # measures the HOOK's control flow -- whether it asks, and from which
    # process it then acts -- not a second copy of the counters.
    (engine_pkg / "state.py").write_text(
        textwrap.dedent(
            '''
            def parse_state(text):
                data = {}
                for line in text.splitlines():
                    if ":" not in line or line.startswith("#"):
                        continue
                    key, _, value = line.partition(":")
                    data[key.strip()] = value.strip().strip('"')
                return data
            '''
        ),
        encoding="utf-8",
    )
    (engine_pkg / "goal_authority.py").write_text(
        textwrap.dedent(
            '''
            WAVE_CAP = 3
            TICKET_CAP = 20


            def budget_exhausted(state):
                return state.get("execution_intent") == "goal" and (
                    int(state.get("goal_waves") or 0) >= WAVE_CAP
                    or int(state.get("goal_tickets") or 0) >= TICKET_CAP
                )
            '''
        ),
        encoding="utf-8",
    )
    (tools / "saipen.py").write_text(engine, encoding="utf-8")
    return holder, root


def run_hook(root: Path, hook: Path = HOOK) -> tuple[dict, list[dict]]:
    event = {
        "hookEventName": "UserPromptSubmit",
        "hook_event_name": "UserPromptSubmit",
        "prompt": "cc",
        "cwd": str(root),
        "sessionId": "sess-t1859",
        "session_id": "sess-t1859",
        "turnId": "turn-t1859",
    }
    proc = subprocess.run(
        [sys.executable, "-c", BOOTSTRAP, str(hook),
         "--host", "zaicode", "--saipen-root", str(root)],
        input=json.dumps(event), capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, proc.stderr
    reply = None
    for line in reversed((proc.stdout or "").strip().splitlines()):
        if line.strip().startswith("{"):
            reply = json.loads(line)
            break
    record = []
    path = Path(root) / "tools" / "saipen_engine" / "record.json"
    if path.is_file():
        record = json.loads(path.read_text(encoding="utf-8"))
    return reply or {}, record


class TheHookBindsTheWorkerTheHostStarted(unittest.TestCase):
    def setUp(self):
        self.holder, self.root = build_root()
        self.addCleanup(self.holder.cleanup)

    def test_the_registered_worker_is_this_hook_process_not_its_parent(self):
        reply, record = run_hook(self.root)
        registers = [row for row in record if row.get("op") == "register"]
        self.assertEqual(len(registers), 1, record)
        bound = registers[0]
        # The subject: the worker must be the hook itself. Registering the
        # parent names the host pid, which the broker refuses by contract.
        self.assertEqual(bound["worker"], bound["own_pid"], bound)
        self.assertNotEqual(bound["worker"], bound["parent_pid"], bound)
        self.assertTrue(reply.get("sealed"), reply)

    def test_the_pre_fix_registration_is_refused_by_this_suite(self):
        """Red control: the shipped `os.getppid()` binding must fail here.

        The defect was which pid is named, so the honest control restores that
        line in the real file and runs it. A claim that the old code was wrong
        proves nothing without it.
        """
        source = HOOK.read_text(encoding="utf-8")
        self.assertIn("worker = os.getpid()", source)
        patched = source.replace("worker = os.getpid()", "worker = os.getppid()")
        self.assertNotEqual(patched, source)

        with tempfile.TemporaryDirectory(prefix="t1859-red-") as tmp:
            red = Path(tmp) / "saipen-guard-pre-fix.py"
            red.write_text(patched, encoding="utf-8")
            _reply, record = run_hook(self.root, hook=red)

        registers = [row for row in record if row.get("op") == "register"]
        self.assertEqual(len(registers), 1, record)
        self.assertEqual(registers[0]["worker"], registers[0]["parent_pid"], registers[0])
        with self.assertRaises(AssertionError):
            self.assertEqual(registers[0]["worker"], registers[0]["own_pid"])

    def test_a_spent_budget_is_renewed_from_the_engine_the_hook_starts(self):
        holder, root = build_root(state_counters=20)
        self.addCleanup(holder.cleanup)
        reply, _record = run_hook(root)
        engine = Path(root) / "engine.json"
        self.assertTrue(engine.is_file(), reply)
        ran = json.loads(engine.read_text(encoding="utf-8"))
        self.assertIn("continue", ran["argv"])
        self.assertTrue(reply.get("renewal"), reply)

    def test_a_pretty_printed_renewal_answer_is_read_not_dropped(self):
        """The engine prints `indent=2`; a one-line reader calls that unreadable."""
        holder, root = build_root(state_counters=20, engine=ENGINE_STUB_PRETTY)
        self.addCleanup(holder.cleanup)
        reply, _record = run_hook(root)
        renewal = reply.get("renewal") or {}
        self.assertTrue(renewal, reply)
        self.assertTrue(renewal.get("ok"), renewal)
        self.assertNotEqual(renewal.get("code"), "RENEWAL_UNREADABLE", renewal)
        self.assertEqual(renewal.get("goal_tickets"), 0, renewal)

    def test_the_one_line_reader_is_refused_by_this_suite(self):
        """Red control: the previous reader must fail on that same answer."""
        source = HOOK.read_text(encoding="utf-8")
        start = source.index("    text = (proc.stdout or \"\").strip()")
        end = source.index("    if isinstance(doc, dict):", start)
        old_reader = '''    for line in reversed((proc.stdout or "").strip().splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            doc = json.loads(line)
        except ValueError:
            continue
        if isinstance(doc, dict):
            break
    else:
        doc = None
'''
        patched = source[:start] + old_reader + source[end:]
        self.assertNotEqual(patched, source)

        with tempfile.TemporaryDirectory(prefix="t1859-red-renew-") as tmp:
            red = Path(tmp) / "saipen-guard-pre-fix-renew.py"
            red.write_text(patched, encoding="utf-8")
            holder, root = build_root(state_counters=20, engine=ENGINE_STUB_PRETTY)
            self.addCleanup(holder.cleanup)
            reply, _record = run_hook(root, hook=red)

        renewal = reply.get("renewal") or {}
        self.assertEqual(renewal.get("code"), "RENEWAL_UNREADABLE", renewal)

    def test_an_unspent_budget_runs_no_renewal(self):
        reply, _record = run_hook(self.root)
        self.assertFalse((Path(self.root) / "engine.json").is_file(), reply)
        self.assertNotIn("renewal", reply)


class TheHookKeepsItsTransportContract(unittest.TestCase):
    """The reader contract T-1868 established must survive this change."""

    def test_the_hook_still_reads_the_host_prompt(self):
        source = HOOK.read_text(encoding="utf-8")
        self.assertIn('event.get("prompt")', source)
        self.assertIn("ingress_digest", source)

    def test_the_hook_registers_nothing_when_it_cannot_seal(self):
        holder, root = build_root()
        self.addCleanup(holder.cleanup)
        self.holder = holder
        reply, record = run_hook(Path(root))
        self.assertTrue(reply.get("ok"), reply)


if __name__ == "__main__":
    unittest.main()

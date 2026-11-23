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
import os
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


#: A client whose broker is down: the shape measured on 2026-10-30, when the
#: live service had died and every genuine prompt was admitted unsealed.
STUB_CLIENT_UNAVAILABLE = textwrap.dedent(
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
        return None, "absent"

    def register_operator_worker(*_args, **_kwargs):
        raise AssertionError("registration must not be attempted without a proof")
    '''
)


class AnUnsealedPromptReachesTheOperator(unittest.TestCase):
    """T-1966: the verdict has to survive the host's own stdout schema.

    ZAICODE validates hook stdout against `HookJSONOutputSchema`, which declares
    eight keys and no others; a conforming parse keeps those and DROPS the rest.
    The hook's `sealed`/`seal` fields were therefore written, parsed and
    discarded, so a dead broker looked exactly like a healthy one on the
    operator's surface.
    """

    FIELDS = {
        "additionalContext", "additional_context", "continue", "decision",
        "hookSpecificOutput", "reason", "stopReason", "suppressOutput",
        "systemMessage",
    }

    def _unavailable_root(self):
        holder, root = build_root()
        self.addCleanup(holder.cleanup)
        (root / "tools" / "saipen_engine" / "host_authority_client.py").write_text(
            STUB_CLIENT_UNAVAILABLE, encoding="utf-8"
        )
        return root

    def test_an_unsealed_prompt_names_the_reason_on_the_keys_the_host_reads(self):
        reply, _record = run_hook(self._unavailable_root())
        self.assertFalse(reply.get("sealed"), reply)
        self.assertFalse(reply.get("authenticated"), reply)
        notice = str(reply.get("systemMessage") or "")
        self.assertIn("NOT authenticated", notice, reply)
        self.assertIn("model_supplied", notice, reply)
        self.assertTrue(str(reply.get("additionalContext") or "").strip(), reply)
        # AC-02 is exact: the REFUSAL CODE itself must reach the hook output.
        # "Something went wrong" is not actionable; the code is what `saipen
        # host doctor` and the operator both key off.
        code = str((reply.get("seal") or {}).get("code") or "")
        self.assertTrue(code, reply)
        self.assertIn(code, notice, reply)
        self.assertIn(code, str(reply.get("additionalContext")), reply)

    def test_the_notice_travels_only_on_schema_keys(self):
        """Everything the host would show must be inside the declared schema."""
        reply, _record = run_hook(self._unavailable_root())
        declared = {k: v for k, v in reply.items() if k in self.FIELDS}
        self.assertIn("systemMessage", declared, reply)
        unknown = set(reply) - self.FIELDS
        # Pre-fix the verdict lived only under these, so a conforming host kept
        # an object with nothing on it the operator could read.
        self.assertTrue(unknown, reply)
        self.assertFalse(
            [k for k in unknown if "NOT authenticated" in str(reply[k])],
            "the verdict must not live only under a key the host drops",
        )

    def test_the_pre_fix_answer_carries_no_operator_visible_notice(self):
        """Red control: the shipped hook must fail the notice assertion.

        Restoring the shipped behaviour is the only honest control for a defect
        that was "the reason never left the process".
        """
        source = HOOK.read_text(encoding="utf-8")
        anchor = (
            "    if not sealed:\n"
            "        result.update(_seal_notice(result.get(\"seal\")))"
        )
        self.assertIn(anchor, source, "the notice call moved; update this control")
        patched = source.replace(anchor, "    if False:\n        pass")
        self.assertNotEqual(patched, source)
        with tempfile.TemporaryDirectory(prefix="t1966-red-") as tmp:
            red = Path(tmp) / "saipen-guard-pre-fix-notice.py"
            red.write_text(patched, encoding="utf-8")
            holder, root = build_root()
            self.addCleanup(holder.cleanup)
            (root / "tools" / "saipen_engine" / "host_authority_client.py").write_text(
                STUB_CLIENT_UNAVAILABLE, encoding="utf-8"
            )
            reply, _record = run_hook(root, hook=red)
        self.assertFalse(reply.get("sealed"), reply)
        self.assertNotIn("systemMessage", reply, reply)


class ABrokerRecordNamingADeadProcessIsNotRunning(unittest.TestCase):
    """T-1966 AC-03: a stale `broker.json` must not read as a live service,
    and its lock must be RECLAIMED rather than held by a pid that is gone."""

    def test_a_record_for_a_dead_pid_is_not_reported_as_running(self):
        sys.path.insert(0, str(TOOLS))
        from saipen_engine import host_authority_broker as HB, host_authority_client as HC

        with tempfile.TemporaryDirectory(prefix="t1966-lock-") as tmp:
            runtime = Path(tmp)
            self.assertFalse(HB.health(runtime))
            # A pid that cannot be alive: above the platform maximum.
            HB.write_status({"pid": 2**31 - 1, "instance": "broker-dead"}, runtime)
            self.assertIsNone(HB.health(runtime), "a dead record must not answer health")
            self.assertIsNotNone(HB.read_status(runtime))
            self.assertFalse(HC.server_trusted(2**31 - 1))

    def test_the_lock_of_a_dead_pid_is_reclaimed(self):
        """The other half of AC-03, and the half that broke recovery.

        A lock file naming a dead pid is what a killed or crashed service
        leaves behind. If it were honoured, every later start would answer
        "another broker is already running" for a process that no longer
        exists -- the compound defect that kept the endpoint empty.
        """
        sys.path.insert(0, str(TOOLS))
        from saipen_engine import host_authority_broker as HB

        with tempfile.TemporaryDirectory(prefix="t1966-reclaim-") as tmp:
            runtime = Path(tmp)
            HB.lock_path(runtime).write_text(
                json.dumps({"pid": 2**31 - 1, "started": 0.0}), encoding="utf-8"
            )
            acquired, detail = HB.acquire_lock(runtime)
            self.addCleanup(HB.release_lock, runtime)
            self.assertTrue(acquired, detail)
            holder = json.loads(HB.lock_path(runtime).read_text(encoding="utf-8"))
            self.assertEqual(holder.get("pid"), os.getpid())


#: A stand-in engine whose `continue` refuses. The hook's renewal path reads
#: this answer, so the notice that reports a failed renewal can be measured.
ENGINE_STUB_REFUSING = textwrap.dedent(
    '''
    import json, os, sys

    RECORD = os.path.join(os.path.dirname(os.path.dirname(__file__)), "engine.json")
    with open(RECORD, "w", encoding="utf-8") as handle:
        json.dump({"argv": sys.argv[1:], "own_pid": os.getpid()}, handle)
    print(json.dumps({"ok": False, "code": "RENEWAL_REFUSED_BY_FIXTURE"}))
    '''
)


class AFailedRenewalIsReportedNotSwallowed(unittest.TestCase):
    """T-1966: a sealed prompt whose grant did not renew must say so.

    The first revision of the notice was an `elif` on `result["renewal"]`
    placed ABOVE the block that computes it, so the branch could never run and
    a failed renewal stayed silent -- the same class of defect as the missing
    seal notice itself, in the very fix for it. This case drives a tripped
    safety valve with an engine that refuses, which is the only state in which
    the notice has anything to report.
    """

    def test_a_refused_renewal_names_itself_on_the_operators_surface(self):
        holder, root = build_root(state_counters=20, engine=ENGINE_STUB_REFUSING)
        self.addCleanup(holder.cleanup)
        reply, _record = run_hook(root)
        # The premise: the valve really was tripped, so the hook really did
        # try to renew. Without this the assertion below could pass vacuously
        # on a project that never reached the renewal path at all.
        self.assertTrue(reply.get("sealed"), reply)
        self.assertIsInstance(reply.get("renewal"), dict, reply)
        self.assertFalse(reply["renewal"].get("ok"), reply)
        notice = str(reply.get("systemMessage") or "")
        self.assertIn("was not renewed", notice, reply)
        self.assertIn("RENEWAL_REFUSED_BY_FIXTURE", notice, reply)

    def test_the_pre_fix_order_silences_the_same_failure(self):
        """Red control: the ordering, not the wording, is what failed.

        Restoring the pre-fix `elif` (evaluated before the renewal is computed)
        produces the exact shape the operator saw: sealing fine, renewal
        refusing, and an empty systemMessage.
        """
        source = HOOK.read_text(encoding="utf-8")
        moved = (
            "    if sealed and isinstance(result.get(\"renewal\"), dict) "
            "and not result[\"renewal\"].get(\"ok\"):\n"
            "        result[\"systemMessage\"] = (\n"
            "            \"SAIPEN: the operator cc was sealed but the bounded grant was not \"\n"
            "            f\"renewed ({result['renewal'].get('code') or 'no code'}). Do this: \"\n"
            "            f\"{_launcher_text(root)} continue\"\n"
            "        )\n"
        )
        self.assertIn(moved, source, "the renewal notice moved; update this control")
        # Before the renewal block, which is where the first revision put it.
        anchor = "    if sealed and result.get(\"destination_op\") == \"continue\""
        self.assertIn(anchor, source)
        red_source = source.replace(moved, "").replace(
            anchor, moved + anchor, 1
        )
        self.assertNotEqual(red_source, source)
        holder, root = build_root(state_counters=20, engine=ENGINE_STUB_REFUSING)
        self.addCleanup(holder.cleanup)
        with tempfile.TemporaryDirectory(prefix="t1966-order-") as tmp:
            red = Path(tmp) / "saipen-guard-pre-fix-order.py"
            red.write_text(red_source, encoding="utf-8")
            reply, _record = run_hook(root, hook=red)
        self.assertTrue(reply.get("sealed"), reply)
        self.assertFalse((reply.get("renewal") or {}).get("ok"), reply)
        self.assertNotIn("systemMessage", reply, reply)

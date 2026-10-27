"""T-1933/SRC-339: the ZAICODE hook must seal the intent the operator declared.

MEASURED defect. `extensions/adapters/zaicode/saipen-guard.py` hardcoded
`action = "continue"` for every prompt. `operator_origin` reserves goal
authority for `action in {"goal", "authorize-goal"}` only, so a ZAICODE
operator could never hold `continuation_authority: operator_persistent`:
`operations.authorize_goal_continuation` refused with "a fresh externally
witnessed operator authorization is required", and the bounded budget tripped
its 20-ticket safety valve into `hard_wait` demanding another manual cc.

The second half is the same constraint T-1859 measured from the other side: the
broker accepts a proof only BELOW the worker that registered it, and the agent's
shell is that worker's SIBLING. A hook that sealed `goal` but left the entry to
the model would mint a proof nothing in the session can verify.

These cases run the REAL hook file in a real subprocess against a recording stub
engine, so they pin which action the hook names and which command it then
spends. The stub stands in for the CLIENT, never the broker: what this suite
decides is the hook's own decision, not the broker's. No claim is made that a
live ZAICODE host delivered these events (that stays UNVERIFIED: no receipt).
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

#: A stand-in engine that records the action the hook asked to seal and the
#: argv of any engine the hook then started.
STUB_CLIENT = textwrap.dedent(
    '''
    import json, os

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
        _append({"op": "issue", "action": kwargs.get("action"),
                 "request_text": kwargs.get("request_text"),
                 "event_id": kwargs.get("event_id"),
                 "session": kwargs.get("session"), "host": kwargs.get("host")})
        proof = {"schema": 1, "kind": "operator-origin",
                 "host": kwargs.get("host") or "zaicode", "nonce": "n1",
                 "action": kwargs.get("action") or "continue",
                 "request_digest": "d" * 64, "host_pid": os.getppid()}
        return {"ok": True, "code": None, "proof": proof, "reused": False}


    def register_operator_worker(proof, worker, *, home=None, **kwargs):
        _append({"op": "register", "worker": worker, "own_pid": os.getpid()})
        return {"ok": True, "worker": worker}
    '''
)

#: Records the argv of any command the hook runs below itself.
ENGINE_STUB = textwrap.dedent(
    '''
    import json, os, sys

    RECORD = os.path.join(os.path.dirname(os.path.dirname(__file__)), "engine.json")
    with open(RECORD, "w", encoding="utf-8") as handle:
        json.dump({"argv": sys.argv[1:], "own_pid": os.getpid(),
                   "parent_pid": os.getppid()}, handle)
    print(json.dumps({"ok": True, "code": "GOAL_SET", "ticket": "T-2",
                      "phase": "SCOUT", "next_action": "PHASE SCOUT T-2",
                      "goal_waves": 1, "goal_tickets": 0}, indent=2))
    '''
)

#: An engine that refuses, so the hook must report its exact code rather than
#: claim success from the seal alone.
ENGINE_STUB_REFUSED = textwrap.dedent(
    '''
    import json, sys
    print(json.dumps({"ok": False, "code": "VALIDATION_FAILED",
                      "detail": "refused for the control"}, indent=2))
    '''
)


def build_root(engine: str = ENGINE_STUB) -> tuple[tempfile.TemporaryDirectory, Path]:
    """A throwaway project whose stub engine records what the hook does."""
    holder = tempfile.TemporaryDirectory(prefix="t1933-")
    root = Path(holder.name)
    (root / ".saipen").mkdir(parents=True, exist_ok=True)
    (root / ".saipen" / "STATE.md").write_text(
        "---\nphase: SCOUT\nagent: fixture\ntask: T-1\n"
        "next_action: PHASE SCOUT T-1\nblocker: none\ntransition_from: PLAN\n"
        "saipen_version: 8\nmode: full\nupdated: 2026-10-26T00:00:00Z\n"
        "goal_waves: 0\ngoal_tickets: 0\n"
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
                        "destination_op": "continue", "sealed": True}
            '''
        ),
        encoding="utf-8",
    )
    # The real registry reader is what the hook consults for the goal route, so
    # the fixture ships the real table shape instead of a private word list.
    (engine_pkg / "commands.py").write_text(
        textwrap.dedent(
            '''
            TABLE = {"gg": "saipen goal", "cc": "saipen continue",
                     "ccc": "saipen continue", "vv": "saipen build"}
            FOLD = {"\\u0430": "a", "\\u0435": "e", "\\u043e": "o",
                    "\\u0440": "p", "\\u0441": "c", "\\u0443": "y", "\\u0445": "x"}


            def load_shortcut_table():
                return dict(TABLE)


            def resolve_shortcut(token, *, table=None):
                table = TABLE if table is None else table
                key = token.strip().lower().translate(FOLD)
                return key if key in table else None
            '''
        ),
        encoding="utf-8",
    )
    # The valve decision is canonical code with its own suite. This stub stands
    # in for it so this suite measures the HOOK's control flow, not a second
    # copy of the counters.
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


def run_hook(root: Path, prompt: str, *, hook: Path = HOOK) -> tuple[dict, list[dict]]:
    # Each call is one host turn: the recorder starts empty so a row from an
    # earlier prompt in the same fixture can never answer for this one.
    (root / "tools" / "saipen_engine" / "record.json").unlink(missing_ok=True)
    (root / "engine.json").unlink(missing_ok=True)
    event = {
        "hookEventName": "UserPromptSubmit",
        "hook_event_name": "UserPromptSubmit",
        "prompt": prompt,
        "cwd": str(root),
        "sessionId": "sess-t1933",
        "session_id": "sess-t1933",
        "turnId": "turn-t1933",
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
    path = root / "tools" / "saipen_engine" / "record.json"
    if path.is_file():
        record = json.loads(path.read_text(encoding="utf-8"))
    return reply or {}, record


def sealed_actions(record: list[dict]) -> list[str]:
    return [row.get("action") for row in record if row.get("op") == "issue"]


def engine_argv(root: Path) -> list[str] | None:
    path = root / "engine.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))["argv"]


class TheHookSealsTheDeclaredIntent(unittest.TestCase):
    """R001/R002/R007: the action comes from the operator's bytes."""

    def setUp(self):
        self.holder, self.root = build_root()
        self.addCleanup(self.holder.cleanup)

    def test_a_goal_objective_is_sealed_as_goal(self):
        reply, record = run_hook(self.root, "gg make the parser strict")
        self.assertEqual(sealed_actions(record), ["goal"], record)
        self.assertTrue(reply.get("sealed"), reply)

    def test_a_host_aliased_goal_is_sealed_as_goal(self):
        _reply, record = run_hook(self.root, "/goal gg make the parser strict")
        self.assertEqual(sealed_actions(record), ["goal"], record)

    def test_a_canonical_goal_command_is_sealed_as_goal(self):
        _reply, record = run_hook(self.root, "saipen goal make the parser strict")
        self.assertEqual(sealed_actions(record), ["goal"], record)

    def test_a_grant_capsule_is_sealed_as_authorize_goal(self):
        capsule = json.dumps(
            {"kind": "saipen-goal-continuation", "project_lineage": "x",
             "goal_ingress": "goal-" + "a" * 16}
        )
        _reply, record = run_hook(self.root, capsule)
        self.assertEqual(sealed_actions(record), ["authorize-goal"], record)

    def test_a_continuation_is_still_sealed_as_continue(self):
        for prompt in ("cc", "cc all", "/goal cc all", "saipen continue"):
            with self.subTest(prompt=prompt):
                _reply, record = run_hook(self.root, prompt)
                self.assertEqual(sealed_actions(record), ["continue"], record)

    def test_prose_that_mentions_goal_or_cc_is_never_a_goal(self):
        for prompt in (
            "goal of this task is to verify the parser",
            "the goal: make tests pass",
            "please cc me when it is done",
            "/goal summarize cc usage",
        ):
            with self.subTest(prompt=prompt):
                _reply, record = run_hook(self.root, prompt)
                self.assertEqual(sealed_actions(record), ["continue"], record)

    def test_a_bare_goal_token_is_not_an_objective(self):
        for prompt in ("gg", "saipen goal", "/goal gg"):
            with self.subTest(prompt=prompt):
                _reply, record = run_hook(self.root, prompt)
                self.assertEqual(sealed_actions(record), ["continue"], record)

    def test_the_pre_fix_hardcoded_action_is_refused_by_this_suite(self):
        """Red control: the shipped one-line `action = "continue"` must fail.

        The defect was WHICH ACTION the hook names, so the honest control
        restores that line in the real file and runs it. Without this, a claim
        that the old code was wrong would rest on reading rather than running.
        """
        source = HOOK.read_text(encoding="utf-8")
        subject = '    action = declared_action(text, root)'
        self.assertIn(subject, source)
        patched = source.replace(subject, '    action = "continue"')
        self.assertNotEqual(patched, source)

        with tempfile.TemporaryDirectory(prefix="t1933-red-") as tmp:
            red = Path(tmp) / "saipen-guard-pre-fix.py"
            red.write_text(patched, encoding="utf-8")
            _reply, record = run_hook(self.root, "gg make the parser strict", hook=red)

        self.assertEqual(sealed_actions(record), ["continue"], record)
        with self.assertRaises(AssertionError):
            self.assertEqual(sealed_actions(record), ["goal"])


class TheHookSpendsTheSealBelowItself(unittest.TestCase):
    """R004/R007: a seal nothing can verify is not a repaired ingress."""

    def setUp(self):
        self.holder, self.root = build_root()
        self.addCleanup(self.holder.cleanup)

    def test_a_sealed_goal_runs_the_goal_entry_from_the_hook(self):
        reply, _record = run_hook(self.root, "gg make the parser strict")
        argv = engine_argv(self.root)
        self.assertIsNotNone(argv, reply)
        self.assertEqual(argv[0], "goal", argv)
        self.assertIn("make the parser strict", " ".join(argv), argv)
        self.assertTrue(reply.get("goal_entry", {}).get("ok"), reply)
        self.assertEqual(reply["goal_entry"].get("code"), "GOAL_SET", reply)

    def test_the_engine_runs_below_the_worker_that_registered_the_proof(self):
        """The broker accepts a verifier only BELOW the registered worker."""
        _reply, _record = run_hook(self.root, "gg make the parser strict")
        ran = json.loads((self.root / "engine.json").read_text(encoding="utf-8"))
        registered = [
            row for row in json.loads(
                (self.root / "tools" / "saipen_engine" / "record.json").read_text(encoding="utf-8")
            ) if row.get("op") == "register"
        ]
        self.assertEqual(len(registered), 1, registered)
        self.assertEqual(ran["parent_pid"], registered[0]["worker"], ran)

    def test_a_sealed_grant_runs_goal_authorize_on_the_exact_bytes(self):
        capsule = json.dumps(
            {"kind": "saipen-goal-continuation", "project_lineage": "x",
             "goal_ingress": "goal-" + "a" * 16}
        )
        reply, _record = run_hook(self.root, capsule)
        argv = engine_argv(self.root)
        self.assertIsNotNone(argv, reply)
        self.assertEqual(argv[:2], ["goal", "authorize"], argv)
        self.assertIn("--file", argv, argv)
        self.assertTrue(reply.get("goal_authorization", {}).get("ok"), reply)

    def test_a_refusing_engine_is_reported_not_hidden(self):
        holder, root = build_root(engine=ENGINE_STUB_REFUSED)
        self.addCleanup(holder.cleanup)
        reply, _record = run_hook(root, "gg make the parser strict")
        entry = reply.get("goal_entry") or {}
        self.assertFalse(entry.get("ok", True), reply)
        self.assertEqual(entry.get("code"), "VALIDATION_FAILED", reply)

    def test_a_continuation_runs_no_goal_entry(self):
        _reply, _record = run_hook(self.root, "cc")
        self.assertIsNone(engine_argv(self.root))


class TheSafetyValveStillHolds(unittest.TestCase):
    """R003/R005: the repair must not hand out budget without a native carrier."""

    def setUp(self):
        self.holder, self.root = build_root()
        self.addCleanup(self.holder.cleanup)

    def test_the_hook_still_requires_a_broker_sealed_origin_to_spend_anything(self):
        source = HOOK.read_text(encoding="utf-8")
        self.assertIn('if sealed and root is not None and action == "goal":', source)
        self.assertIn("if sealed and result.get(\"destination_op\") == \"continue\"", source)

    def test_an_unsealed_prompt_spends_nothing(self):
        """A model replaying the bytes cannot reach the engine: no seal, no run."""
        holder, root = build_root()
        self.addCleanup(holder.cleanup)
        (root / "tools" / "saipen_engine" / "host_authority_client.py").write_text(
            textwrap.dedent(
                '''
                def issue_operator_origin(**kwargs):
                    return {"ok": False, "code": "HOST_PROVENANCE_UNAVAILABLE",
                            "detail": "no native host event for this call"}


                def register_operator_worker(proof, worker, *, home=None, **kwargs):
                    return {"ok": False, "code": "HOST_PROVENANCE_UNAVAILABLE"}
                '''
            ),
            encoding="utf-8",
        )
        reply, _record = run_hook(root, "gg make the parser strict")
        self.assertFalse(reply.get("sealed"), reply)
        self.assertNotIn("goal_entry", reply, reply)
        self.assertIsNone(engine_argv(root))

    def test_the_guard_still_reads_the_host_prompt(self):
        source = HOOK.read_text(encoding="utf-8")
        self.assertIn('event.get("prompt")', source)
        self.assertIn("ingress_digest", source)


if __name__ == "__main__":
    unittest.main()

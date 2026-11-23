"""T-1649: a refused authority client leaves the step that refused it.

On 2026-10-06 two consecutive Claude UserPromptSubmit hook runs, in a session
admitted all evening, answered SAIPEN_ADMISSION_UNVERIFIED with
AUTHORITY_CLIENT_UNPROVEN. The health record carried that code and nothing
else; the broker log the doctor advertises was empty. The step that refused
(NOT_HOST_DESCENDANT) existed only in the running service's memory, as its
single most recent refusal.

Pinned: the step travels from the broker's identity detail into the typed
problem, the verdict, the degraded notice and the hook's health record, and
the broker writes one bounded line per refused client.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import host_authority_broker as broker  # noqa: E402
from saipen_engine import host_authority_client as client  # noqa: E402
from saipen_engine import host_authority_identity as identity  # noqa: E402
from saipen_engine import host_integration as integration  # noqa: E402
from saipen_engine import host_taxonomy as taxonomy  # noqa: E402
from saipen_engine import protocol_admission as admission  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

HOOK = ROOT / "extensions" / "adapters" / "claude" / "saipen-guard.py"
STEP = "NOT_HOST_DESCENDANT"
DETAIL = "the hook was not started by a registered host application"


def setUpModule() -> None:
    # T-1685: the operator's host profile and binding never reach a fixture.
    isolate_host_session()


class _Peer:
    kind = "pipe"
    pid = 4242


def _refusing(step: str = STEP):
    def authenticate(peer, host, home):
        return (
            False,
            broker.CODE_NOT_AUTHENTICATED,
            {
                "transport": "pipe",
                "pid": 4242,
                "reason": step,
                "detail": DETAIL,
                "chain": [
                    {"pid": 4242, "ppid": 4100, "image": "C:\\Python311\\python.exe"},
                    {"pid": 4100, "ppid": 1, "image": "C:/Program Files/Git/usr/bin/bash.exe"},
                ],
            },
        )

    return authenticate


def _proven(peer, host, home):
    return True, None, {"transport": "pipe", "pid": 4242, "host_image": "claude.exe", "chain": []}


class _Broker(unittest.TestCase):
    def setUp(self):
        self.runtime = Path(tempfile.mkdtemp(prefix="saipen-t1649-"))
        self.addCleanup(shutil.rmtree, self.runtime, True)
        self.lines: list[str] = []

    def _broker(self, authenticator):
        return broker.Broker(
            saipen_root=ROOT,
            runtime=self.runtime,
            config=dict(broker.settings()),
            authenticator=authenticator,
            refusal_sink=self.lines.append,
        )

    def _ask(self, service, **extra) -> dict:
        request = {"op": "admission", "host": "claude", "session": "s", "project": str(ROOT)}
        return service.handle({**request, **extra}, _Peer())


class BrokerRefusalLineTests(_Broker):
    def test_a_refused_client_leaves_one_line_naming_the_step(self):
        service = self._broker(_refusing())
        reply = self._ask(service)
        self.assertFalse(reply["ok"])
        self.assertEqual(len(self.lines), 1)
        record = json.loads(self.lines[0])
        self.assertEqual(record["event"], "client_refused")
        self.assertEqual(record["op"], "admission")
        self.assertEqual(record["code"], broker.CODE_NOT_AUTHENTICATED)
        self.assertEqual(record["step"], STEP)
        self.assertEqual(record["host"], "claude")
        self.assertEqual(record["chain"], ["python.exe", "bash.exe"])
        self.assertRegex(record["at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

    def test_the_line_carries_what_was_seen_and_nothing_else(self):
        service = self._broker(_refusing())
        self._ask(service, transport="CAPABILITY-SECRET", request="operator words", model="m")
        record = json.loads(self.lines[0])
        self.assertEqual(
            sorted(record), ["at", "chain", "code", "event", "host", "op", "pid", "step"]
        )
        self.assertNotIn("CAPABILITY-SECRET", self.lines[0])
        self.assertNotIn("operator words", self.lines[0])
        self.assertLess(len(self.lines[0]), 700)

    def test_every_identity_step_is_named(self):
        steps = sorted(
            value for name, value in vars(identity).items() if name.startswith("REASON_")
        )
        self.assertGreaterEqual(len(steps), 8)
        for step in steps:
            self.lines.clear()
            self._ask(self._broker(_refusing(step)))
            self.assertEqual(json.loads(self.lines[0])["step"], step, step)
            self.assertEqual(taxonomy.as_step(step), step)

    def test_the_service_sink_is_the_stream_its_log_receives(self):
        # `spawn` hands the service its log file as stderr, and `run_service`
        # wires this sink.
        service = broker.Broker(
            saipen_root=ROOT,
            runtime=self.runtime,
            config=dict(broker.settings()),
            authenticator=_refusing(),
            refusal_sink=broker.service_log_line,
        )
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured):
            self._ask(service)
        lines = captured.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["step"], STEP)

    def test_a_broker_constructed_without_a_sink_prints_nothing(self):
        service = broker.Broker(
            saipen_root=ROOT,
            runtime=self.runtime,
            config=dict(broker.settings()),
            authenticator=_refusing(),
        )
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured), contextlib.redirect_stdout(captured):
            reply = self._ask(service)
        self.assertFalse(reply["ok"])
        self.assertEqual(captured.getvalue(), "")
        self.assertEqual(service.stats.refused, 1)

    def test_an_admitted_client_writes_no_line(self):
        service = self._broker(_proven)
        self._ask(service)
        self.assertEqual(self.lines, [])

    def test_the_lines_are_capped_and_the_counts_go_on(self):
        service = self._broker(_refusing())
        for _ in range(broker.REFUSAL_LOG_LINES + 5):
            self._ask(service)
        self.assertEqual(len(self.lines), broker.REFUSAL_LOG_LINES)
        self.assertTrue(json.loads(self.lines[-1]).get("capped"))
        self.assertNotIn("capped", json.loads(self.lines[0]))
        self.assertEqual(service.stats.refused, broker.REFUSAL_LOG_LINES + 5)

    def test_a_hostile_field_is_bounded_not_trusted(self):
        long_step = "X" * 500 + '\n{"injected": true}'
        service = self._broker(_refusing(long_step))
        self._ask(service, host="h" * 300)
        self.assertEqual(len(self.lines), 1)
        self.assertNotIn("\n", self.lines[0])
        record = json.loads(self.lines[0])
        self.assertLessEqual(len(record["step"]), 48)
        self.assertLessEqual(len(record["host"]), 24)


class TheStepTravelsTests(unittest.TestCase):
    def _problems(self, step: object = STEP) -> list:
        return [taxonomy.problem("transport", "AUTHORITY_CLIENT_UNPROVEN", DETAIL, step=step)]

    def test_a_typed_problem_carries_a_step_only_when_it_is_a_code(self):
        self.assertEqual(self._problems()[0]["step"], STEP)
        self.assertNotIn("step", self._problems(None)[0])
        self.assertNotIn("step", self._problems("free text from another generation")[0])
        self.assertNotIn("step", taxonomy.problem("transport", "AUTHORITY_UNREACHABLE", "x"))

    def test_the_degraded_verdict_names_the_step(self):
        verdict = admission._degraded_verdict(problems=self._problems())
        self.assertEqual(verdict["failure"], "AUTHORITY_CLIENT_UNPROVEN")
        self.assertEqual(verdict["failure_step"], STEP)
        self.assertIsNone(
            admission._degraded_verdict(problems=self._problems(None))["failure_step"]
        )

    def test_a_refusal_names_the_step(self):
        verdict = admission._refusal(self._problems())
        self.assertEqual(verdict["failure_step"], STEP)

    def test_a_service_that_was_never_started_names_why(self):
        declined = {"state": "not_a_host_client", "identity": {"hook_reason": STEP}}
        self.assertEqual(admission._unstarted_step(declined), STEP)
        self.assertIsNone(admission._unstarted_step({"state": "unanswered", "identity": None}))
        self.assertIsNone(admission._unstarted_step({"state": "started", "identity": declined}))
        self.assertIsNone(
            admission._unstarted_step(
                {"state": "not_a_host_client", "identity": {"hook_reason": "free text"}}
            )
        )
        self.assertIsNone(admission._unstarted_step(None))

    def test_both_notices_name_the_step(self):
        full = client.degraded_notice(self._problems())
        brief = client.degraded_notice(self._problems(), brief=True)
        self.assertIn("AUTHORITY_CLIENT_UNPROVEN/" + STEP, full)
        self.assertIn("AUTHORITY_CLIENT_UNPROVEN/" + STEP, brief)
        plain = client.degraded_notice(self._problems(None), brief=True)
        self.assertIn("AUTHORITY_CLIENT_UNPROVEN;", plain)
        self.assertNotIn("/", plain.split("Restore with:")[0])


class HealthRecordTests(unittest.TestCase):
    """The real hook artifact writes the step where the doctor reads it."""

    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="saipen-t1649-home-"))
        self.addCleanup(shutil.rmtree, self.home, True)
        spec = importlib.util.spec_from_file_location("saipen_guard_t1649", HOOK)
        self.hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.hook)
        self.options = types.SimpleNamespace(home=str(self.home), saipen_root=ROOT, unread=0)
        self.printed: list[str] = []
        self._print = self.hook.print = lambda *args, **kwargs: self.printed.append(str(args))

    def _health(self) -> dict:
        path = self.home / ".saipen" / "health" / "claude.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def _verdict(self, **fields) -> dict:
        return {
            "state": "DEGRADED",
            "permitted": True,
            "failure": "AUTHORITY_CLIENT_UNPROVEN",
            **fields,
        }

    def test_a_degraded_prompt_records_the_step(self):
        self.hook._admission = lambda *args, **kwargs: self._verdict(failure_step=STEP)
        self.hook._inject = lambda *args, **kwargs: None
        self.hook.handle_prompt(ROOT, ROOT, {}, self.options)
        record = self._health()
        self.assertEqual(record["event"], "UserPromptSubmit")
        self.assertEqual(record["state"], "DEGRADED")
        self.assertEqual(record["code"], "AUTHORITY_CLIENT_UNPROVEN")
        self.assertEqual(record["step"], STEP)

    def test_a_refused_prompt_records_the_step(self):
        self.hook._admission = lambda *args, **kwargs: {
            **self._verdict(failure_step=STEP),
            "permitted": False,
            "diagnostic": "refused",
        }
        self.hook.handle_prompt(ROOT, ROOT, {}, self.options)
        self.assertEqual(self._health()["step"], STEP)
        self.assertEqual(self._health()["state"], "REFUSED")

    def test_a_session_start_records_the_step(self):
        self.hook._admission = lambda *args, **kwargs: self._verdict(failure_step=STEP)
        self.hook._inject = lambda *args, **kwargs: None
        self.hook.handle_session_start(ROOT, ROOT, {"source": "startup"}, self.options)
        self.assertEqual(self._health()["step"], STEP)

    def test_no_step_is_no_field(self):
        self.hook._admission = lambda *args, **kwargs: self._verdict()
        self.hook._inject = lambda *args, **kwargs: None
        self.hook.handle_prompt(ROOT, ROOT, {}, self.options)
        self.assertNotIn("step", self._health())


class DoctorReasonTests(unittest.TestCase):
    """`saipen host doctor` repeats the step the health record carries."""

    def _reason(self, **health) -> str:
        from test_t1624_host_integration import facts

        _state, reasons, _action = integration.derive_state(
            facts(health={"state": "DEGRADED", "code": "AUTHORITY_CLIENT_UNPROVEN", **health})
        )
        return reasons[0]

    def test_the_reason_names_the_step(self):
        self.assertIn("(AUTHORITY_CLIENT_UNPROVEN/" + STEP + ")", self._reason(step=STEP))

    def test_without_a_step_the_reason_is_the_code_alone(self):
        self.assertIn("(AUTHORITY_CLIENT_UNPROVEN)", self._reason())

    def test_text_in_the_step_place_is_not_repeated(self):
        reason = self._reason(step="not a code; rm -rf")
        self.assertIn("(AUTHORITY_CLIENT_UNPROVEN)", reason)
        self.assertNotIn("rm -rf", reason)


if __name__ == "__main__":
    unittest.main()

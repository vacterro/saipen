"""T-1656 / SRC-190: the operator checkpoint is a checkpoint, not an embedded audit.

An agent finished real Work correctly and returned one paragraph of some
three thousand characters behind a `STATUS:` label: every repaired finding,
file, symbol, red control and measurement, with the state, the blocker and
the next action buried inside it (the fixture is that reply, transcribed).

The budgets were already the contract (`EXEC-RESPONSE-01`). What let the wall
through, measured on the incident project:

- the refusal was prose, so nothing downstream could say WHICH field
  overflowed or by how much;
- the compact form named no place where the detail lives, and `DETAILS` was
  refused on every ordinary reply, so the detail went into the reply;
- a reply the gate replaces was kept nowhere;
- `saipen response digest` without `--json` died on a pipe whose locale is not
  UTF-8, and took 38 seconds there because the whole product tree was hashed
  to look for a test record that project cannot have;
- a host with no final gate has nothing between the model and the operator,
  and no command said so at the moment the reply is composed.

Pinned here, including the ten readability checks the source asks for.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import response_surface as RS  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_orchestration_repair import OrchestrationFixture  # noqa: E402

ENGINE = TOOLS / "saipen.py"
FIXTURE = ROOT / "tests" / "fixtures" / "t1656-operator-wall" / "response.transcribed.txt"

#: The facts the incident project's own state held when the reply was written.
INCIDENT_FACTS = {
    "phase": "DONE",
    "task": "none",
    "next_action": "NONE",
    "validation": "CURRENT_PASS",
    "completed": ["T-1442"],
    "detail_refs": ["E-4515", "E-4520"],
    "test_groups": [{"ran": 5022, "red": 0, "new_red": 0}],
}


def setUpModule() -> None:
    isolate_host_session()


def wall() -> str:
    return FIXTURE.read_text(encoding="utf-8").strip()


def gate(text: str, facts: dict, **context) -> dict:
    return RS.gate_final_response(
        text,
        admission=None,
        admission_consulted=False,
        operational_turn=True,
        style_contract=None,
        facts=dict(facts),
        **context,
    )


def within(text: str, klass: str) -> bool:
    lines, chars = RS.REASON_BUDGETS[klass]
    return len(text.splitlines()) <= lines and len(text) <= chars


# ------------------------------------------------------------- the incident


class FastPrompterIncidentTests(unittest.TestCase):
    def test_the_fixture_is_one_dense_paragraph(self):
        text = wall()
        self.assertEqual(len(text.splitlines()), 1)
        self.assertGreater(len(text), 3000)
        self.assertTrue(text.startswith("STATUS: T-1442 / SRC-101"))
        for needle in ("8/8", "4999 passed, 23 skipped, 0 failed", "E-4520", "NEXT: cc"):
            self.assertIn(needle, text)

    def test_the_overflow_is_named_as_data(self):
        found = RS.overflow_diagnostic(wall())
        self.assertEqual(found["code"], "OPERATOR_OUTPUT_OVERFLOW")
        self.assertEqual([item["field"] for item in found["fields"]], ["STATUS"])
        status = found["fields"][0]
        self.assertGreater(status["chars"], 3000)
        self.assertEqual(status["char_budget"], RS.FIELD_CHAR_BUDGETS["STATUS"])
        self.assertEqual(found["total"]["char_budget"], RS.ORDINARY_RESPONSE_CHAR_BUDGET)
        self.assertGreater(found["total"]["chars"], found["total"]["char_budget"])
        self.assertEqual(found["detail_ref"], RS.rejected_reference(wall()))

    def test_it_is_compacted_into_a_checkpoint_not_refused_into_a_question(self):
        verdict = gate(wall(), INCIDENT_FACTS)
        self.assertFalse(verdict["ok"])
        self.assertEqual(verdict["class"], RS.CLASS_INVALID_OPERATIONAL_PROSE)
        self.assertEqual(verdict["overflow"]["compaction"], RS.COMPACTION_SUCCEEDED)
        compact = verdict["delivery"]
        self.assertTrue(within(compact, RS.COMPACT_FINAL), compact)
        fields, problems = RS.parse_surface(compact)
        self.assertEqual(problems, [])
        self.assertEqual(fields["STATUS"], "DONE")
        self.assertIn("T-1442", fields["RESULT"])
        self.assertEqual(fields["BLOCKER"], "NONE")
        self.assertIn("5022", fields["VALIDATION"])
        self.assertIn("red 0", fields["VALIDATION"])
        self.assertEqual(fields["DETAILS"], "E-4515, E-4520")
        for symbol in ("audio_render.py", "MAX_RESAMPLE_PHASES", "ipc_server.py", "W2-001"):
            self.assertNotIn(symbol, compact)

    def test_the_compact_form_is_accepted_when_it_comes_back(self):
        compact = gate(wall(), INCIDENT_FACTS)["delivery"]
        again = gate(compact, INCIDENT_FACTS)
        self.assertTrue(again["ok"], again)
        self.assertEqual(again["class"], RS.CLASS_VALID_BOUNDARY)
        self.assertIsNone(again["overflow"])


# ---------------------------------------------------- the ten readability checks


class ReadabilityChecks(OrchestrationFixture):
    def test_01_a_normal_done_checkpoint_stays_within_budget(self):
        text = RS.digest_from_facts(INCIDENT_FACTS, reason="final")
        self.assertTrue(within(text, RS.COMPACT_FINAL), text)
        self.assertEqual(RS.response_errors(text), [])
        self.assertIsNone(RS.overflow_diagnostic(text))

    def test_02_a_normal_continue_checkpoint_stays_within_budget(self):
        running = {
            **INCIDENT_FACTS,
            "phase": "BUILD",
            "task": "T-1443",
            "automation": {"disposition": "CONTINUE", "next_command": "saipen continue"},
        }
        quiet = RS.digest_from_facts(running, reason="final")
        self.assertEqual(quiet, "", "runnable work is quiet")
        asked = RS.digest_from_facts(running, reason="status")
        self.assertTrue(asked and within(asked, RS.COMPACT_FINAL), asked)

    def test_03_wait_user_presents_the_decision_before_technical_detail(self):
        waiting = {
            **INCIDENT_FACTS,
            "operator_due": True,
            "operator_action": "confirm repo name 'fastprompter' and public or private",
        }
        text = RS.digest_from_facts(waiting, reason="final")
        self.assertTrue(within(text, RS.HUMAN_ACTION_BLOCKER), text)
        order = [line.split(":", 1)[0] for line in text.splitlines()]
        self.assertEqual(order[:3], ["STATUS", "RESULT", "OPERATOR ACTION"])
        self.assertLess(order.index("OPERATOR ACTION"), order.index("VALIDATION"))
        self.assertLess(order.index("VALIDATION"), order.index("DETAILS"))

    def test_04_blocked_presents_blocker_and_recovery_before_evidence(self):
        blocked = {
            **INCIDENT_FACTS,
            "phase": "BLOCKED",
            "blocker": "BLOCKED_EXTERNAL -- the provider refuses the release tag",
            "next_action": "saipen ticket unblock T-1442",
        }
        text = RS.digest_from_facts(blocked, reason="final")
        order = [line.split(":", 1)[0] for line in text.splitlines()]
        for label in ("BLOCKER", "NEXT EXACT ACTION"):
            self.assertLess(order.index(label), order.index("VALIDATION"), text)
        self.assertEqual(order[-1], "DETAILS")

    def test_05_large_evidence_sets_are_referenced_not_dumped(self):
        heavy = {
            **INCIDENT_FACTS,
            "detail_refs": [f"E-{n}" for n in range(4000, 4060)],
            "evidence": [f".saipen/evidence/run-{n}.json" for n in range(200)],
        }
        text = RS.digest_from_facts(heavy, reason="final")
        fields, _problems = RS.parse_surface(text)
        self.assertTrue(RS.details_is_pointer(fields["DETAILS"]))
        self.assertLessEqual(len(fields["DETAILS"].split(", ")), 4)
        self.assertNotIn("run-", text)
        self.assertTrue(within(text, RS.COMPACT_FINAL))

    def test_06_long_ticket_and_blocker_lists_collapse_into_counts(self):
        busy = {
            **INCIDENT_FACTS,
            "completed": [f"T-{n}" for n in range(1300, 1433)],
            "blockers": [
                {"ticket": f"T-{n}", "blocker": f"{kind} -- reason {n}"}
                for n, kind in enumerate(
                    ["HELD"] * 20
                    + ["BLOCKED_EXTERNAL"] * 20
                    + ["WAIT_USER_DECISION"] * 14
                    + ["OTHER"] * 5
                )
            ],
        }
        text = RS.digest_from_facts(busy, reason="final")
        fields, _problems = RS.parse_surface(text)
        self.assertIn("133", fields["RESULT"])
        self.assertIn("59", fields["RESULT"])
        self.assertLessEqual(len(fields["RESULT"]), RS.FIELD_CHAR_BUDGETS["RESULT"])
        self.assertNotIn("T-13", fields["RESULT"], "counts, never a ticket inventory")
        self.assertNotIn("OTHER", fields["RESULT"], "three categories at most")

    def test_07_no_result_paragraph_can_grow_arbitrarily(self):
        novel = (
            "STATUS: DONE\nRESULT: " + "changed function X; added constant Y; " * 140
            + "\nNEXT EXACT ACTION: NONE\nVALIDATION: CURRENT_PASS"
        )
        self.assertTrue(any("RESULT exceeds" in item for item in RS.response_errors(novel)))
        found = RS.overflow_diagnostic(novel)
        fields = {item["field"]: item for item in found["fields"]}
        self.assertEqual(fields["RESULT"]["char_budget"], 300)
        self.assertGreater(fields["RESULT"]["chars"], 5000)
        verdict = gate(novel, INCIDENT_FACTS)
        self.assertEqual(verdict["overflow"]["compaction"], RS.COMPACTION_SUCCEEDED)
        self.assertTrue(within(verdict["delivery"], RS.COMPACT_FINAL))

    def test_08_validation_summarizes_totals(self):
        text = RS.digest_from_facts(INCIDENT_FACTS, reason="final")
        fields, _problems = RS.parse_surface(text)
        self.assertEqual(len(fields["VALIDATION"].splitlines()), 1)
        self.assertLessEqual(len(fields["VALIDATION"]), RS.FIELD_CHAR_BUDGETS["VALIDATION"])
        for total in ("5022", "red 0", "new_red 0"):
            self.assertIn(total, fields["VALIDATION"])
        listed = (
            "STATUS: DONE\nRESULT: Valmis\nNEXT EXACT ACTION: NONE\nVALIDATION: "
            + ", ".join(f"tests/test_case_{n}.py::test_it PASSED" for n in range(30))
        )
        self.assertTrue(any("VALIDATION exceeds" in item for item in RS.response_errors(listed)))

    def test_09_evidence_remains_lossless_in_canonical_storage(self):
        project = self.make_project()
        text = wall()
        kept = RS.preserve_rejected(project, text)
        self.assertTrue(kept["ok"], kept)
        self.assertEqual(kept["ref"], RS.rejected_reference(text))
        self.assertEqual(kept["ref"], gate(text, INCIDENT_FACTS)["overflow"]["detail_ref"])
        stored = (project / kept["ref"]).read_bytes()
        self.assertEqual(stored, text.encode("utf-8"))
        for detail in ("MAX_RESAMPLE_PHASES=2048", "478.8 ms", "E-4521", "T-1405/1407/1409..1413"):
            self.assertIn(detail.encode("utf-8"), stored)
        again = RS.preserve_rejected(project, text.replace("\n", "\r\n"))
        self.assertEqual((again["ref"], again["written"]), (kept["ref"], False))

    def test_10_an_explicit_request_for_detail_expands_the_output(self):
        report = (
            "STATUS: DONE\nRESULT: Valmis; T-1442\nNEXT EXACT ACTION: NONE\n"
            "VALIDATION: CURRENT_PASS\nDETAILS: eight findings were repaired\n"
            "audio: the resampler is bounded\nipc: the server is event driven"
        )
        self.assertTrue(any("DETAILS is not authorized" in e for e in RS.response_errors(report)))
        asked = RS.detail_mode_for_request("give me a detailed report")
        self.assertEqual(asked, RS.DETAIL_MODE_REPORT)
        self.assertEqual(
            RS.response_errors(report, detail_mode=RS.DETAIL_MODE_REPORT), [], "authorized depth"
        )
        for request in ("ok", "thanks, nice work", "do not write a detailed report"):
            self.assertEqual(RS.detail_mode_for_request(request), RS.DETAIL_MODE_NONE, request)

    def test_10b_the_operators_short_words_for_more_are_understood(self):
        """Details, evidence, a technical breakdown, verbose output: each is an
        explicit request when it is the whole message."""
        for request in (
            "give me the details",
            "show me the details",
            "show the evidence",
            "give me the full evidence",
            "give me a technical breakdown",
            "give me a detailed technical breakdown",
            "give me verbose output",
            "verbose output please",
            "details",
            "full report",
            "technical breakdown",
            "näita üksikasju",
            "anna tõendid",
            "покажи детали",
            "подробности",
        ):
            self.assertEqual(RS.detail_mode_for_request(request), RS.DETAIL_MODE_REPORT, request)
        for request in (
            "audit",
            "evidence",
            "show me the details of the failing test only",
            "the details are in the log, continue",
            "do not give me the details",
            "no verbose output",
            "give me a summary",
            "fix the technical breakdown section of the readme",
        ):
            self.assertEqual(RS.detail_mode_for_request(request), RS.DETAIL_MODE_NONE, request)


# ----------------------------------------------------------- pointer and facts


class PointerTests(OrchestrationFixture):
    def test_a_pointer_is_references_and_nothing_else(self):
        for value in (
            "E-4520",
            "E-4515, E-4520",
            "E-4519..E-4522; T-1442",
            "SRC-101, .saipen/evidence/response/rejected-0123456789abcdef.txt",
        ):
            self.assertTrue(RS.details_is_pointer(value), value)
        for value in (
            "see E-4520",
            "E-4520 and the rest of the log",
            "E-4520, " * 30 + "E-1",
            "../outside/the/project",
            ".saipen/../outside/the/project",
            ".saipen/evidence/../../secrets.txt",
            ".saipen/",
            "E-4520\nE-4521",
        ):
            self.assertFalse(RS.details_is_pointer(value), value)

    def test_an_ordinary_boundary_may_point_and_may_not_narrate(self):
        base = "STATUS: DONE\nRESULT: Valmis\nNEXT EXACT ACTION: NONE\nVALIDATION: CURRENT_PASS\n"
        self.assertEqual(RS.response_errors(base + "DETAILS: E-4515, E-4520"), [])
        errors = RS.response_errors(base + "DETAILS: the fix is in audio_render.py")
        self.assertTrue(any("DETAILS is not authorized" in item for item in errors), errors)

    def test_a_facts_carrier_cannot_smuggle_prose_through_the_pointer(self):
        refs = ["E-4520", "read the whole log please", "T-1442", "E-4520", "rm -rf /"]
        self.assertEqual(RS.details_pointer(refs), "E-4520, T-1442")
        self.assertEqual(RS.details_pointer(["nothing valid"]), "")
        self.assertEqual(RS.details_pointer(None), "")

    def test_the_pointer_yields_to_the_line_budget_of_its_boundary(self):
        crowded = {
            **INCIDENT_FACTS,
            "phase": "BLOCKED",
            "blocker": "BLOCKED_EXTERNAL -- the provider refuses the release tag",
            "next_action": "saipen ticket unblock T-1442",
        }
        text = RS.digest_from_facts(crowded, reason="stop")
        self.assertTrue(within(text, RS.STOP_HANDBACK), text)
        self.assertEqual(RS.response_errors(text, response_class=RS.STOP_HANDBACK), [])
        roomy = RS.digest_from_facts(INCIDENT_FACTS, reason="stop")
        self.assertIn("DETAILS: E-4515, E-4520", roomy, "and is there when it fits")

    def test_a_reply_that_is_no_surface_has_one_offender_the_reply(self):
        found = RS.overflow_diagnostic("I repaired many things. " * 80)
        self.assertEqual([item["field"] for item in found["fields"]], ["RESPONSE"])
        self.assertIsNone(RS.overflow_diagnostic("Short and fine."))

    def test_the_facts_reader_points_at_the_newest_completion(self):
        from saipen_engine.operations import finish_ticket

        project = self.make_project(active=True)
        (project / "main.py").write_text("shared = True\n", encoding="utf-8")
        self.to_ship(project, "T-7")
        done = finish_ticket(
            project, "T-7", "tester", closure_mode="cohort", closure_cohort="C-001",
            closure_paths=("main.py",),
        )
        self.assertTrue(done.ok, done.to_dict())
        facts = RS.canonical_facts(project)
        refs = facts["detail_refs"]
        self.assertTrue(refs and all(RS.details_is_pointer(ref) for ref in refs), refs)
        finished = int(done.to_dict()["event_id"].split("-")[1])
        self.assertEqual(int(refs[-1].split("-")[1]), finished, "the finish event")
        text = RS.digest_from_facts(facts, reason="stop")
        self.assertIn("DETAILS: " + ", ".join(refs), text)
        self.assertEqual(RS.response_errors(text, response_class=RS.STOP_HANDBACK), [])

    def test_a_project_with_no_declared_family_is_not_hashed_to_look_for_its_record(self):
        from saipen_engine import core_unit

        project = self.make_project()
        with mock.patch.object(core_unit, "tree_fingerprint", side_effect=AssertionError("hashed")):
            facts = RS.canonical_facts(project)
        self.assertEqual(facts["test_groups"], [])


# ---------------------------------------------------------------- the surfaces


class CommandSurfaceTests(OrchestrationFixture):
    def cli(self, *args: str, stdin: str | None = None, **declared: str):
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
        env.update(declared)
        proc = subprocess.run(
            [sys.executable, "-B", str(ENGINE), *args],
            input=None if stdin is None else stdin.encode("utf-8"),
            capture_output=True,
            env=env,
            cwd=str(TOOLS),
            timeout=300,
            check=False,
        )
        return proc.returncode, proc.stdout

    def completed_project(self) -> Path:
        from saipen_engine.operations import finish_ticket

        project = self.make_project(active=True)
        (project / "main.py").write_text("shared = True\n", encoding="utf-8")
        self.to_ship(project, "T-7")
        done = finish_ticket(
            project, "T-7", "tester", closure_mode="cohort", closure_cohort="C-001",
            closure_paths=("main.py",),
        )
        self.assertTrue(done.ok, done.to_dict())
        return project

    def test_the_plain_digest_survives_a_pipe_that_is_not_utf8(self):
        """The checkpoint is Estonian text. On a host whose pipes are not
        UTF-8 the one command that prints it must not answer with a refusal."""
        project = self.completed_project()
        rc, out = self.cli(
            "response", "digest", "--project-root", str(project), "--reason", "stop",
            PYTHONIOENCODING="ascii", PYTHONUTF8="0",
        )
        text = out.decode("utf-8")
        self.assertEqual(rc, 0, text)
        self.assertIn("T-7 lõpetatud", text)
        self.assertNotIn("RESPONSE_FACT_INVALID", text)

    def test_check_reports_the_overflow_and_whether_the_original_is_kept(self):
        project = self.completed_project()
        root = str(project)
        rc, out = self.cli("response", "check", "--stdin", "--json", stdin=wall())
        plain = json.loads(out.decode("utf-8"))
        self.assertEqual((rc, plain["code"]), (1, "EXEC_RESPONSE_INVALID"))
        self.assertEqual(plain["overflow"]["fields"][0]["field"], "STATUS")
        self.assertIsNone(plain["overflow"]["preserved"], "no project named, nothing to look in")

        rc, out = self.cli(
            "response", "check", "--stdin", "--project-root", root, "--json", stdin=wall()
        )
        before = json.loads(out.decode("utf-8"))
        self.assertIs(before["overflow"]["preserved"], False)

        rc, out = self.cli(
            "response", "preserve", "--stdin", "--project-root", root, "--json", stdin=wall()
        )
        kept = json.loads(out.decode("utf-8"))
        self.assertEqual((rc, kept["code"]), (0, "RESPONSE_PRESERVED"), kept)
        self.assertEqual(kept["ref"], before["overflow"]["detail_ref"])
        self.assertEqual((project / kept["ref"]).read_bytes(), wall().encode("utf-8"))

        rc, out = self.cli(
            "response", "check", "--stdin", "--project-root", root, "--json", stdin=wall()
        )
        self.assertIs(json.loads(out.decode("utf-8"))["overflow"]["preserved"], True)

    def test_a_read_only_session_may_not_preserve(self):
        project = self.completed_project()
        rc, out = self.cli(
            "response", "preserve", "--stdin", "--project-root", str(project), "--json",
            stdin=wall(), SAIPEN_CAPABILITY="read-only",
        )
        answer = json.loads(out.decode("utf-8"))
        self.assertEqual((rc, answer["code"]), (1, "CAPABILITY_DENIED"), answer)
        self.assertFalse((project / RS.rejected_reference(wall())).exists())

    def test_preserve_needs_a_project_and_a_reply(self):
        rc, out = self.cli("response", "preserve", "--stdin", "--json", stdin=wall())
        answer = json.loads(out.decode("utf-8"))
        self.assertEqual((rc, answer["code"]), (2, "VALIDATION_FAILED"))
        self.assertIn("response preserve --stdin --project-root", answer["detail"])


class BoundaryHintTests(OrchestrationFixture):
    """A host with no final gate: the last lifecycle write names the command
    whose output is the checkpoint, at the moment the reply is composed."""

    def set_next_action(self, project: Path, value: str) -> None:
        state = project / ".saipen" / "STATE.md"
        lines = [
            f'next_action: "{value}"' if line.startswith("next_action:") else line
            for line in state.read_text(encoding="utf-8").splitlines()
        ]
        state.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_a_write_that_leaves_the_project_waiting_names_the_checkpoint_command(self):
        import saipen as engine

        project = self.make_project()
        self.assertIsNone(engine._operator_boundary_hint(project), "runnable: no hint")
        self.set_next_action(project, "WAIT: blocked -- the operator chooses the repository name")
        hint = engine._operator_boundary_hint(project)
        self.assertEqual(
            hint["command"],
            f'saipen response digest --project-root "{project}" --reason final --json',
        )
        self.assertIn("verbatim and nothing else", hint["instruction"])

    def test_the_hint_rides_the_answer_of_a_lifecycle_write_only(self):
        import saipen as engine

        project = self.make_project()
        self.set_next_action(project, "WAIT: blocked -- the operator chooses the repository name")

        def emitted(root) -> dict:
            captured = io.StringIO()
            with mock.patch.object(engine, "_BOUNDARY_ROOT", root), redirect_stdout(captured):
                engine._emit({"ok": True, "code": "CHECKPOINTED"}, True)
            return json.loads(captured.getvalue())

        self.assertIn("operator_boundary", emitted(project))
        self.assertNotIn("operator_boundary", emitted(None))
        captured = io.StringIO()
        with mock.patch.object(engine, "_BOUNDARY_ROOT", project), redirect_stdout(captured):
            engine._emit({"ok": False, "code": "VALIDATION_FAILED", "detail": "x"}, True)
        self.assertNotIn("operator_boundary", json.loads(captured.getvalue()))


class LawTextTests(unittest.TestCase):
    def test_the_rule_owner_states_the_three_additions(self):
        text = " ".join((ROOT / "saipen" / "EXECUTION.md").read_text(encoding="utf-8").split())
        for phrase in (
            "OPERATOR_OUTPUT_OVERFLOW",
            "one reference line",
            "`response preserve`",
        ):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()

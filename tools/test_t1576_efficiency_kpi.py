"""The final-report conditional efficiency KPI (T-1576, SRC-152).

One derived, approximate view over the LOG the machine already writes -- never
a second lifecycle store, never quality evidence, never a lifecycle input. The
regression matrix below is SRC-152 section 15 (A-J), plus the contract
around it: one owner, a versioned formula, explicit scope and confidence, an
optional one-line EFFICIENCY field that only a final boundary may carry, and
exposure through `saipen status --json` and `saipen response render`.
"""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import efficiency as E  # noqa: E402
from saipen_engine import response_surface as RS  # noqa: E402
from saipen_engine.log import read_history_events  # noqa: E402
from test_hermetic_env import hermetic_env, isolate_host_session  # noqa: E402

CLI = ROOT / "tools" / "saipen.py"
SCENARIO = ROOT / "tests" / "scenarios" / "userperson-valid" / ".saipen"
TICKET = "T-901"

CLAIM = ("DEC", "claimed via SAIOPS -- owner auda")
FINISH = ("DEC", "ticket finished via SAIOPS -- completion (from SHIP)")
BLOCK = ("DEC", "ticket block via SAIOPS -- WAIT_USER_DECISION -- operator owns the choice")
UNBLOCK = ("DEC", "ticket unblock via SAIOPS -- operator chose option A")
PASS = ("RUN", "verify -> PASS [target: T-901] conf: high -- focused green")
FAIL = ("RUN", "CORE-UNIT-EVIDENCE FAIL family:unit ran:10 red:1 new_red:1")
CORE_PASS = ("RUN", "CORE-UNIT-EVIDENCE PASS family:unit ran:10 red:0 new_red:0")


def to(phase: str) -> tuple[str, str]:
    return ("RUN", f"transition to {phase} -- step")


#: A complete, well-evidenced lifecycle: one claim, the forward chain, a
#: green gate and the SHIP finish.
CLEAN_RUN = [CLAIM, to("BUILD"), to("VERIFY"), CORE_PASS, PASS, to("REVIEW"), to("SHIP"), FINISH]


def events(rows, *, agents=None, day: str = "30.09.26") -> list[dict]:
    """Real LOG lines through the real parser, never hand-built dicts."""
    with tempfile.TemporaryDirectory(prefix="saipen-t1576-log-") as tmp:
        root = Path(tmp)
        (root / ".saipen").mkdir()
        lines = []
        for index, (taxonomy, text) in enumerate(rows):
            agent = agents[index] if agents else "auda"
            lines.append(
                f"- {day} 12:{index % 60:02d} [E-{index + 2}] [{TICKET}] "
                f"[agent: {agent}] {taxonomy}: {text}\n"
            )
        (root / ".saipen" / "LOG.md").write_text("".join(lines), encoding="utf-8")
        return list(read_history_events(root))


def kpi(rows, **kwargs) -> dict:
    agents = kwargs.pop("agents", None)
    return E.kpi_for_ticket(
        events(rows, agents=agents), TICKET, validation=kwargs.get("validation", "CURRENT_PASS")
    )


def surface(**overrides) -> str:
    fields = {
        "STATUS": "DONE T-901",
        "RESULT": "requested behavior shipped",
        "BLOCKER": "NONE",
        "OPERATOR ACTION": "NONE",
        "NEXT EXACT ACTION": "NONE",
        "VALIDATION": "CURRENT_PASS | focused 48/48 | core new_red=0",
        "EFFICIENCY": "~85% LOW | progress 100 | rework 60 | autonomy 100 | human n/a",
    }
    fields.update(overrides)
    return "\n".join(
        f"{key}: {value}"
        for key, value in fields.items()
        if value is not None and not (key in ("BLOCKER", "OPERATOR ACTION") and value == "NONE")
    )


class RegressionMatrix(unittest.TestCase):
    """SRC-152 section 15, A-J."""

    def test_a_a_complete_ticket_has_a_bounded_approximate_kpi(self) -> None:
        value = kpi(CLEAN_RUN)
        self.assertEqual(value["scope"], "ticket")
        self.assertEqual(value["ticket"], TICKET)
        self.assertTrue(value["approximate"])
        self.assertIn(value["confidence"], {"HIGH", "MED", "LOW"})
        self.assertEqual(value["percent"] % 5, 0)
        self.assertTrue(0 <= value["percent"] <= 100)
        self.assertEqual(set(value["components"]), {"progress", "rework", "autonomy", "human"})
        self.assertFalse(value["preliminary"])
        line = E.render_line(value)
        self.assertTrue(line.startswith("~"), line)
        self.assertIsNone(E.line_problem(line))

    def test_b_sparse_evidence_is_unknown_not_invented(self) -> None:
        for rows in ([], [CLAIM], [CLAIM, to("BUILD")]):
            value = kpi(rows)
            self.assertIsNone(value["percent"], rows)
            self.assertEqual(value["confidence"], "UNKNOWN")
            self.assertEqual(value["withheld"], E.INSUFFICIENT)
            self.assertEqual(E.render_line(value), f"UNKNOWN | {E.INSUFFICIENT}")

    def test_c_a_long_legitimate_wait_costs_nothing(self) -> None:
        waited = [CLAIM, to("BUILD"), BLOCK, UNBLOCK, to("BUILD"), *CLEAN_RUN[2:]]
        self.assertEqual(kpi(waited)["percent"], kpi(CLEAN_RUN)["percent"])
        self.assertEqual(kpi(waited)["components"], kpi(CLEAN_RUN)["components"])
        # Calendar time is not an input: the same events a week apart agree.
        later = E.kpi_for_ticket(events(waited, day="07.10.26"), TICKET, validation="CURRENT_PASS")
        self.assertEqual(later, kpi(waited))

    def test_d_repeated_backward_transitions_lower_rework(self) -> None:
        once = [
            CLAIM,
            to("BUILD"),
            to("VERIFY"),
            FAIL,
            to("BUILD"),
            to("VERIFY"),
            CORE_PASS,
            PASS,
            to("REVIEW"),
            to("SHIP"),
            FINISH,
        ]
        twice = [*once[:6], FAIL, to("BUILD"), to("VERIFY"), *once[6:]]
        clean, one, two = (kpi(rows)["components"]["rework"] for rows in (CLEAN_RUN, once, twice))
        self.assertGreater(clean, one)
        self.assertGreater(one, two)

    def test_e_no_unnecessary_intervention_reads_as_such(self) -> None:
        value = kpi(CLEAN_RUN)
        self.assertEqual(value["components"]["autonomy"], 100)
        # Human cost has no honest machine signal in v1: withheld and named,
        # never a fabricated 100.
        self.assertIsNone(value["components"]["human"])
        self.assertEqual(value["notes"]["human"], E.HUMAN_WITHHELD)
        self.assertIn("human n/a", E.render_line(value))

    def test_f_a_required_operator_authorization_is_not_inefficiency(self) -> None:
        authorized = [CLAIM, to("BUILD"), BLOCK, UNBLOCK, *CLEAN_RUN[2:]]
        self.assertEqual(kpi(authorized)["percent"], kpi(CLEAN_RUN)["percent"])
        self.assertEqual(kpi(authorized)["components"], kpi(CLEAN_RUN)["components"])

    def test_g_a_validation_failure_never_reads_as_quality(self) -> None:
        failed = [CLAIM, to("BUILD"), to("VERIFY"), FAIL]
        value = kpi(failed)
        self.assertTrue(value["preliminary"])
        self.assertTrue(E.render_line(value).startswith(("PRELIMINARY", "UNKNOWN")))
        # Untrusted terminal validation marks even a clean run preliminary.
        self.assertTrue(kpi(CLEAN_RUN, validation="CURRENT_FAIL")["preliminary"])
        # The field grammar has no word in which it could claim a verdict.
        for forged in (
            "~95% HIGH | quality PASS",
            "PASS ~95% HIGH | progress 100 | rework 100 | autonomy 100 | human 100",
            "~95% VALID | progress 100 | rework 100 | autonomy 100 | human 100",
        ):
            self.assertIsNotNone(E.line_problem(forged), forged)
            self.assertTrue(RS.response_errors(surface(EFFICIENCY=forged)), forged)
        # VALIDATION still has to lead with the current verdict on its own.
        errors = RS.response_errors(
            surface(VALIDATION="PASS | efficient"), current_validation="CURRENT_FAIL"
        )
        self.assertTrue(any("VALIDATION must start" in e for e in errors), errors)

    def test_h_silent_execution_carries_no_intermediate_kpi(self) -> None:
        self.assertEqual(RS.response_errors(surface()), [])
        for status in ("T-901 BUILD", "T-901 VERIFY", "SCOUT T-901"):
            errors = RS.response_errors(surface(STATUS=status))
            self.assertTrue(any("final boundary" in e for e in errors), (status, errors))
        two_lines = "~85% LOW | progress 100 | rework 60 | autonomy 100 | human n/a\n~80% LOW"
        self.assertTrue(RS.response_errors(surface(EFFICIENCY=two_lines)))
        # Even AUTHORIZED progress chat may not become a KPI heartbeat.
        from saipen_engine.hush import intermediate_verdict

        for heartbeat in (two_lines.splitlines()[0], "EFFICIENCY ~85% LOW"):
            verdict = intermediate_verdict(heartbeat, request="keep me updated")
            self.assertEqual(verdict["code"], "INTERMEDIATE_TEXT_SUPPRESSED", heartbeat)
            self.assertEqual(verdict.get("reason"), "kpi_heartbeat", heartbeat)
        self.assertTrue(
            intermediate_verdict("BUILD slice 2 of 3 done", request="keep me updated")["ok"]
        )

    def test_i_details_may_explain_but_the_headline_stays_one_line(self) -> None:
        details = "progress 100: no stalls; rework 60: one core FAIL and one VERIFY->BUILD return"
        ok = surface(DETAILS=details)
        self.assertEqual(RS.response_errors(ok, detail_mode=RS.DETAIL_MODE_REPORT), [])
        # Order: EFFICIENCY after VALIDATION, DETAILS still last.
        heads = [name for name in RS.parse_surface(ok)[0] if name in ("EFFICIENCY", "DETAILS")]
        self.assertEqual(heads[-2:], ["EFFICIENCY", "DETAILS"])
        long_line = "~85% LOW" + " | progress 100" * 30
        errors = RS.response_errors(
            surface(EFFICIENCY=long_line, DETAILS=details), detail_mode=RS.DETAIL_MODE_REPORT
        )
        self.assertTrue(errors)

    def test_j_a_frozen_fixture_is_deterministic(self) -> None:
        once = [
            CLAIM,
            to("BUILD"),
            to("VERIFY"),
            FAIL,
            to("BUILD"),
            to("VERIFY"),
            CORE_PASS,
            PASS,
            to("REVIEW"),
            to("SHIP"),
            FINISH,
        ]
        first, second = kpi(once), kpi(once)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        self.assertEqual(
            first,
            {
                "scope": "ticket",
                "ticket": TICKET,
                # (35*100 + 25*50 + 25*100) / 85 = 85.3 -> nearest 5
                "percent": 85,
                "approximate": True,
                "confidence": "LOW",
                "formula_version": 1,
                "components": {"progress": 100, "rework": 50, "autonomy": 100, "human": None},
                "notes": {
                    "human": E.HUMAN_WITHHELD,
                    "autonomy": "coarse: LOG agent ids are CLI identities shared across sessions",
                },
                "preliminary": False,
                "withheld": None,
            },
        )
        self.assertEqual(
            E.render_line(first), "~85% LOW | progress 100 | rework 50 | autonomy 100 | human n/a"
        )


class Contract(unittest.TestCase):
    def test_one_versioned_formula_with_weights_totalling_100(self) -> None:
        self.assertEqual(sum(E.WEIGHTS.values()), 100)
        self.assertEqual(list(E.WEIGHTS), ["progress", "rework", "autonomy", "human"])
        # Changing a weight IS a new formula: v1 is pinned to its weights.
        if E.FORMULA_VERSION == 1:
            self.assertEqual(E.WEIGHTS, {"progress": 35, "rework": 25, "autonomy": 25, "human": 15})

    def test_a_stall_lowers_progress_but_a_resume_does_not(self) -> None:
        stalled = [CLAIM, to("BUILD"), to("BUILD"), *CLEAN_RUN[2:]]
        self.assertLess(kpi(stalled)["components"]["progress"], 100)

    def test_a_mid_ticket_handoff_lowers_coarse_autonomy(self) -> None:
        agents = ["auda"] * 4 + ["other"] * (len(CLEAN_RUN) - 4)
        self.assertLess(kpi(CLEAN_RUN, agents=agents)["components"]["autonomy"], 100)

    def test_hand_authored_events_are_not_evidence(self) -> None:
        typed = [
            dict(ev, op_id="verify-a0b1c2d3e4f5061728394a5b6c7d8e9f")
            if ev["text"].startswith("verify ->")
            else ev
            for ev in events(CLEAN_RUN)
        ]
        self.assertEqual(
            E.kpi_for_ticket(typed, TICKET, validation="CURRENT_PASS")["components"]["rework"], 100
        )
        forged_fail = events([*CLEAN_RUN[:-1], FAIL, FINISH])
        forged_fail[-2] = dict(forged_fail[-2], op_id="verify-a0b1c2d3e4f5061728394a5b6c7d8e9f")
        self.assertEqual(
            E.kpi_for_ticket(forged_fail, TICKET, validation="CURRENT_PASS")["components"],
            kpi(CLEAN_RUN)["components"],
        )

    def test_scope_is_explicit_and_never_borrowed(self) -> None:
        value = E.kpi_for_ticket(events(CLEAN_RUN), None)
        self.assertEqual(value["scope"], "session")
        self.assertIsNone(value["percent"])
        self.assertEqual(value["confidence"], "UNKNOWN")
        # Another ticket's evidence never describes this one.
        self.assertIsNone(E.kpi_for_ticket(events(CLEAN_RUN), "T-902")["percent"])

    def test_no_lifecycle_validation_or_routing_owner_imports_the_kpi(self) -> None:
        importers = set()
        for path in (ROOT / "tools").rglob("*.py"):
            if path.name.startswith("test_") or "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.ImportFrom):
                    names = [node.module or ""] + [alias.name for alias in node.names]
                elif isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                if any(name == "efficiency" or name.endswith(".efficiency") for name in names):
                    importers.add(path.relative_to(ROOT).as_posix())
        self.assertEqual(
            importers,
            {"tools/saipen.py", "tools/saipen_engine/response_surface.py"},
        )

    def test_field_order_keeps_details_last(self) -> None:
        self.assertEqual(RS.FIELD_ORDER[-2:], ("EFFICIENCY", "DETAILS"))
        self.assertNotIn("EFFICIENCY", RS.MANDATORY_FIELDS)
        self.assertEqual(RS.FIELD_LINE_BUDGETS["EFFICIENCY"], 1)
        self.assertEqual(RS.FIELD_CHAR_BUDGETS["EFFICIENCY"], E.LINE_CHAR_BUDGET)
        boundary = RS.OperationalBoundary(
            "DONE T-901",
            "shipped",
            "NONE",
            "NONE",
            "NONE",
            "NOT_RUN",
            "",
            E.render_line(kpi(CLEAN_RUN)),
        )
        self.assertIn("\nEFFICIENCY: ~", RS.render_boundary(boundary))


class Exposure(unittest.TestCase):
    """The value leaves the engine through status and render, nowhere else."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="saipen-t1576-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "PROJ"
        self.root.mkdir()
        shutil.copytree(SCENARIO, self.root / ".saipen")
        from test_fixture_support import restamp_live_style

        restamp_live_style(self.root / ".saipen")
        lines = "".join(
            f"- 30.09.26 12:{index:02d} [E-{index + 2}] [{TICKET}] [agent: auda] {tax}: {text}\n"
            for index, (tax, text) in enumerate(CLEAN_RUN)
        )
        with (self.root / ".saipen" / "LOG.md").open("a", encoding="utf-8") as handle:
            handle.write(lines)
        state = self.root / ".saipen" / "STATE.md"
        state.write_text(
            state.read_text(encoding="utf-8").replace(
                "last_event: 1\n", f"last_event: {len(CLEAN_RUN) + 1}\n"
            ),
            encoding="utf-8",
        )
        board = self.root / ".saipen" / "BOARD.md"
        board.write_text(
            board.read_text(encoding="utf-8").replace(
                "## DONE\n", f"## DONE\n- [x] {TICKET} [P2] fixture work | verify: proof\n"
            ),
            encoding="utf-8",
        )

    def _cli(self, *args: str, stdin: str | None = None) -> dict:
        done = subprocess.run(
            [sys.executable, "-B", str(CLI), *args, "--project-root", str(self.root), "--json"],
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=hermetic_env(),
            timeout=300,
        )
        return json.loads(done.stdout)

    def test_status_json_carries_the_ticket_kpi(self) -> None:
        payload = self._cli("status")
        self.assertTrue(payload.get("ok"), payload)
        value = payload[E.MACHINE_NAME]
        self.assertEqual((value["scope"], value["ticket"]), ("ticket", TICKET))
        self.assertEqual(value["formula_version"], E.FORMULA_VERSION)
        # The fixture never ran the validator: honest, not flattering.
        self.assertTrue(value["preliminary"])

    def test_render_fills_auto_from_the_owner(self) -> None:
        fields = {
            "STATUS": f"DONE {TICKET}",
            "RESULT": "shipped",
            "BLOCKER": "NONE",
            "OPERATOR ACTION": "NONE",
            "NEXT EXACT ACTION": "NONE",
            "VALIDATION": "NOT_RUN",
            "EFFICIENCY": "auto",
        }
        payload = self._cli("response", "render", "--stdin", stdin=json.dumps(fields))
        self.assertTrue(payload.get("ok"), payload)
        line = RS.parse_surface(payload["text"])[0]["EFFICIENCY"]
        self.assertTrue(line.startswith("PRELIMINARY ~"), line)
        self.assertIsNone(E.line_problem(line))


def setUpModule() -> None:
    isolate_host_session()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

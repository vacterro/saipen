"""Operational status and blocker identities must match canonical facts."""
from pathlib import Path
import json
import subprocess
import sys
import unittest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from saipen_engine import response_surface as RS  # noqa: E402
from saipen_engine.conformance import conformance_decision  # noqa: E402
from test_guard_hostile_matrix import active_project, fresh_project  # noqa: E402


def surface(status, blocker="NONE", validation="CURRENT_PASS", operator_action="NONE"):
    return RS.render_boundary(RS.OperationalBoundary(
        status, "Kontroll tehtud.", blocker, operator_action, "NONE", validation,
    ))


class CanonicalResponseFacts(unittest.TestCase):
    def test_phase_and_task_are_exact_without_contradictory_phase_claims(self):
        context = {"current_phase": "VERIFY", "current_task": "T-1567"}
        for status in ("VERIFY T-1567", "T-1567 VERIFY"):
            with self.subTest(valid=status):
                self.assertEqual(RS.response_errors(surface(status), **context), [])
        for status in (
            "DONE (VERIFY T-1567)", "VERIFY DONE T-1567", "PREVERIFY T-1567",
            "VERIFY T-15670", "VERIFY T-1567_FAKE", "VERIFY_NOT_DONE T-1567",
            "done (VERIFY T-1567)",
            "FINISHED (VERIFY T-1567)", "COMPLETE VERIFY T-1567",
        ):
            with self.subTest(invalid=status):
                self.assertTrue(RS.response_errors(surface(status), **context))
        self.assertTrue(RS.response_errors(
            surface("WAIT VERIFY T-1567", operator_action="Anna eesmärk."), **context,
        ))
        self.assertEqual(RS.response_errors(
            surface("WAIT -- init valmis; phase PLAN", operator_action="Anna eesmärk."),
            current_phase="PLAN", operator_due=True,
        ), [])
        for phase in ("PLAN", "DONE", "BLOCKED"):
            with self.subTest(real_wait=phase):
                self.assertEqual(RS.response_errors(
                    surface("WAIT -- inimotsus vajalik", operator_action="Anna otsus."),
                    current_phase=phase, operator_due=True,
                ), [])
        self.assertEqual(RS.response_errors(
            surface("WAIT T-1567", operator_action="Anna otsus."),
            **context, operator_due=True,
        ), [])
        for status in ("WAIT -- phase DONE T-1567", "WAIT VERIFY DONE T-1567"):
            with self.subTest(contradictory_wait=status):
                self.assertTrue(RS.response_errors(
                    surface(status, operator_action="Anna otsus."),
                    **context, operator_due=True,
                ))

    def test_terminal_phases_are_bound_too(self):
        for phase, bad in (("DONE", "VERIFY"), ("BLOCKED", "DONE")):
            with self.subTest(phase=phase):
                self.assertEqual(RS.response_errors(surface(phase), current_phase=phase), [])
                self.assertTrue(RS.response_errors(surface(bad), current_phase=phase))

    def test_current_blocker_requires_exact_code(self):
        context = {"current_phase": "BLOCKED", "current_task": "T-1563",
                   "current_blocker": "BLOCKED_EXTERNAL -- host unavailable"}
        for blocker in ("BLOCKED_EXTERNAL -- host unavailable",
                        "BLOCKED_EXTERNAL -- Host authority puudub."):
            with self.subTest(valid=blocker):
                self.assertEqual(RS.response_errors(surface("BLOCKED T-1563", blocker),
                                                    **context), [])
        for blocker in ("BLOCKED_EXTERNAL_FAKE -- host unavailable",
                        "BLOCKED_EXTERNAL2 -- host unavailable", "NONE"):
            with self.subTest(invalid=blocker):
                self.assertTrue(RS.response_errors(surface("BLOCKED T-1563", blocker),
                                                   **context))

    def test_public_checker_rejects_terminal_and_task_prefix_forgeries(self):
        project = active_project()
        validation = conformance_decision(project, gate="core")["status"]
        for status, expected in (("BUILD T-9001", 0), ("DONE (BUILD T-9001)", 1),
                                 ("FINISHED (BUILD T-9001)", 1),
                                 ("BUILD T-90010", 1)):
            with self.subTest(status=status):
                proc = subprocess.run(
                    [sys.executable, str(TOOLS / "saipen.py"), "response", "check",
                     "--stdin", "--project-root", str(project), "--json"],
                    input=surface(status, validation=validation), encoding="utf-8",
                    capture_output=True, timeout=60,
                )
                self.assertEqual(proc.returncode, expected, proc.stdout + proc.stderr)
                self.assertEqual(json.loads(proc.stdout)["ok"], expected == 0)

    def test_public_checker_binds_completed_project_phase(self):
        project = fresh_project()
        validation = conformance_decision(project, gate="core")["status"]
        for status, expected in (("DONE", 0), ("VERIFY", 1)):
            with self.subTest(status=status):
                proc = subprocess.run(
                    [sys.executable, str(TOOLS / "saipen.py"), "response", "check",
                     "--stdin", "--project-root", str(project), "--json"],
                    input=surface(status, validation=validation), encoding="utf-8",
                    capture_output=True, timeout=60,
                )
                self.assertEqual(proc.returncode, expected, proc.stdout + proc.stderr)

    def test_public_checker_requires_current_blocker_identity(self):
        project = fresh_project(phase="BLOCKED", blocker="BLOCKED_EXTERNAL -- host unavailable")
        validation = conformance_decision(project, gate="core")["status"]
        for blocker, expected in (("BLOCKED_EXTERNAL -- host unavailable", 0),
                                  ("BLOCKED_EXTERNAL_FAKE -- host unavailable", 1)):
            with self.subTest(blocker=blocker):
                proc = subprocess.run(
                    [sys.executable, str(TOOLS / "saipen.py"), "response", "check",
                     "--stdin", "--project-root", str(project), "--json"],
                    input=surface("BLOCKED", blocker, validation), encoding="utf-8",
                    capture_output=True, timeout=60,
                )
                self.assertEqual(proc.returncode, expected, proc.stdout + proc.stderr)

    def test_public_wait_uses_canonical_human_obligation_with_a_binding_blocker(self):
        for category, expected_due in (("manual-verify", True), ("blocked", False)):
            project = fresh_project(
                next_action=f"WAIT: {category} -- await the required decision",
                blocker="HUMAN_DECISION -- choose disposition",
            )
            status = subprocess.run(
                [sys.executable, str(TOOLS / "saipen.py"), "status", "--json",
                 "--project-root", str(project)], encoding="utf-8",
                capture_output=True, timeout=60,
            )
            self.assertEqual(status.returncode, 0, status.stdout + status.stderr)
            facts = json.loads(status.stdout)
            self.assertEqual(facts["automation"]["operator_action_due"], expected_due)
            validation = facts["conformance_status"]["status"]
            for phase, expected in (("", 0 if expected_due else 1), ("VERIFY", 1)):
                with self.subTest(category=category, claimed_phase=phase):
                    text = surface(
                        "WAIT" + (f" -- phase {phase}" if phase else ""),
                        "HUMAN_DECISION -- choose disposition", validation, "Anna otsus.",
                    )
                    checked = subprocess.run(
                        [sys.executable, str(TOOLS / "saipen.py"), "response", "check",
                         "--stdin", "--classify", "--auto-eligibility", "--json",
                         "--project-root", str(project)], input=text, encoding="utf-8",
                        capture_output=True, timeout=60,
                    )
                    self.assertEqual(checked.returncode, expected, checked.stdout + checked.stderr)


if __name__ == "__main__":
    unittest.main()

"""Explicit Windows acceptance of the existing SAI Accounts readiness boundary.

No deployed application changes. The only mutable subject is a newly owned
disposable project, granted/revoked through the existing account controller.
Imported normally, this module performs no probes and creates no test cases.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from saipen_engine.init_project import bootstrap_project
from saipen_engine.process_tree import run

ROOT = Path(__file__).resolve().parent.parent


def readiness_problems(value, exit_code, *, allow_recovery_denial=False):
    """All independent facts must hold; provider credentials alone grant nothing."""
    facts = value.get("facts") or {}
    project = ((value.get("probe") or {}).get("project") or {}).get("json") or {}
    recovery = (
        allow_recovery_denial
        and project.get("recovery_pending") is True
        and isinstance(project.get("pending_ops"), list)
        and bool(project["pending_ops"])
    )
    expected = {
        "account": {"state": "ENABLED", "backend": "managed_windows_user"},
        "broker": {"state": "ONLINE", "identity_verified": True},
        "credentials": {"present": True},
        "project_access": {"status": "ok"},
        "saipen_runtime": {"state": "READY"},
        "saipen_runtime_detail": {"code": "MACHINE_RUNTIME_READY", "current": True},
        "host_launch": {
            "vendor_binary_present": True,
            "token_matches_account": True,
            "elevated": False,
        },
        "project_admission": {
            "state": "DENIED" if recovery else "ADMITTED",
            "bootstrap": "HOST_BOOTSTRAP_BOUND",
            "write_admission": "ADMITTED",
        },
    }
    problems = []
    if (
        (exit_code == 0 if recovery else exit_code != 0)
        or value.get("verdict") != ("PROJECT_LIFECYCLE_DENIED" if recovery else "READY")
        or value.get("execution") != "broker"
        or value.get("schema") != "sai.accounts/saipen-readiness/1"
    ):
        problems.append("readiness verdict/identity envelope is not READY")
    for category, fields in expected.items():
        actual = facts.get(category) or {}
        for key, expected_value in fields.items():
            if (
                type(actual.get(key)) is not type(expected_value)
                or actual.get(key) != expected_value
            ):
                problems.append(category + "." + key)
    return problems


def canonical_hashes(project):
    return {
        name: hashlib.sha256((project / ".saipen" / name).read_bytes()).hexdigest()
        for name in ("STATE.md", "BOARD.md", "LOG.md")
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--private-home", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    if os.name != "nt":
        parser.error("this actual Windows integration requires Windows; no skipped PASS")
    if not args.report.resolve().is_relative_to((ROOT / ".saipen/evidence").resolve()):
        parser.error("report must remain in owned project evidence")
    observations = {
        "scope": "actual managed broker, project admission and isolated negative controls",
        "engine": str(args.engine),
        "engine_sha256": hashlib.sha256(args.engine.read_bytes()).hexdigest(),
        "account": args.account,
        "probes": [],
        "fixture_removed": None,
    }

    def ask(*arguments):
        completed = run([str(args.engine), *arguments], capture_output=True, text=True, timeout=240)
        value = json.loads(completed.stdout)
        observations["probes"].append(
            {"argv": list(arguments), "exit_code": completed.returncode, "result": value}
        )
        return completed.returncode, value

    class ActualReadiness(unittest.TestCase):
        def test_10_actual_project_and_distinct_managed_token(self):
            before = canonical_hashes(args.project)
            code, value = ask("saipen-readiness", args.account, "--workdir", str(args.project))
            self.assertEqual(readiness_problems(value, code, allow_recovery_denial=True), [])
            self.assertEqual(
                canonical_hashes(args.project),
                before,
                "live canonical project changed during the observation",
            )
            observations["actual_project_canonical_unchanged"] = True

        def test_20_private_fixture_admits_valid_home_and_refuses_unlisted_home(self):
            temp_root = Path(tempfile.gettempdir()).resolve()
            owner = Path(
                tempfile.mkdtemp(prefix="saipen-accounts-acceptance-", dir=temp_root)
            ).resolve()
            if owner.parent != temp_root or not owner.name.startswith(
                "saipen-accounts-acceptance-"
            ):
                raise RuntimeError("private fixture escaped its owned temporary root")
            project = owner / "project"
            project.mkdir()
            granted = False
            safe_cleanup = True
            try:
                bootstrap_project(project, agent="saipen-cli", mode="no-publish")
                granted = True  # Always revoke an attempted grant, including a failed capture.
                code, _grant = ask("grant-workdir", args.account, "--workdir", str(project))
                self.assertEqual(code, 0, "canonical private fixture grant unavailable")
                before = canonical_hashes(project)
                code, value = ask("saipen-readiness", args.account, "--workdir", str(project))
                self.assertEqual(
                    readiness_problems(value, code), [], "positive fixture control failed"
                )
                self.assertEqual(canonical_hashes(project), before)
                # Controlled corruption of this disposable test subject only.
                # No live project or canonical production history is edited.
                state = project / ".saipen/STATE.md"
                text, count = re.subn(
                    r"(?m)^saipen_home:.*$",
                    "saipen_home: " + json.dumps(args.private_home.as_posix()),
                    state.read_text(encoding="utf-8"),
                )
                self.assertEqual(count, 1)
                state.write_text(text, encoding="utf-8")
                before = canonical_hashes(project)
                code, value = ask("saipen-readiness", args.account, "--workdir", str(project))
                self.assertNotEqual(code, 0)
                self.assertEqual(value.get("verdict"), "PROJECT_LIFECYCLE_DENIED")
                admission = (value.get("facts") or {}).get("project_admission") or {}
                self.assertEqual(admission.get("state"), "DENIED")
                self.assertEqual(admission.get("write_admission"), "CROSS_USER_RUNTIME_UNAVAILABLE")
                self.assertEqual(canonical_hashes(project), before)
                observations["unlisted_home_negative_control"] = True
            finally:
                if granted:
                    code, _revoke = ask("revoke-workdir", args.account, "--workdir", str(project))
                    safe_cleanup = code == 0
                if safe_cleanup:
                    if owner.parent != temp_root or not owner.name.startswith(
                        "saipen-accounts-acceptance-"
                    ):
                        raise RuntimeError("refusing cleanup outside the exact owned fixture")
                    shutil.rmtree(owner)
                    observations["fixture_removed"] = not owner.exists()
                else:
                    observations["fixture_retained"] = str(owner)
                    self.fail("private fixture grant could not be revoked; owned fixture retained")

        def test_30_unrelated_operator_profile_remains_denied(self):
            code, value = ask("saipen-readiness", args.account, "--workdir", str(args.private_home))
            self.assertNotEqual(code, 0)
            self.assertEqual(value.get("verdict"), "PROJECT_ACCESS_DENIED")
            access = (value.get("facts") or {}).get("project_access") or {}
            self.assertIn(access.get("status"), ("WORKDIR_UNAVAILABLE", "WORKDIR_ACCESS_DENIED"))
            self.assertIn(
                access.get("reason") or access.get("error"),
                ("ACCESS_DENIED", "UnauthorizedAccessException"),
            )

    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ActualReadiness)
    )
    observations.update(
        tests_ran=result.testsRun,
        failures=len(result.failures),
        errors=len(result.errors),
        skipped=len(result.skipped),
    )
    args.report.write_text(json.dumps(observations, indent=2) + "\n", encoding="utf-8")
    return 0 if result.wasSuccessful() and result.testsRun == 3 and not result.skipped else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""T-1747 / SRC-241: a degraded session is told the cause and the command that fixes it.

Measured on the operator's machine: a Claude session started with a second
configuration profile ran the SAIPEN hook of the default profile. The identity
check named the cause (HOOK_ARTIFACT_MISMATCH); the notice printed the table
sentence of the code above it -- "The SAIPEN authority service did not answer"
-- and the bare `saipen host repair`, which leaves a second profile untouched.
On the way `saipen host repair --dry-run` ran a full repair: the flag was
parsed and never consulted.

No test here may reach a real installer: every writer is replaced by a
recorder, so the pre-fix half of the pair is red without touching the machine.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import saipen as cli  # noqa: E402
from saipen_engine import (  # noqa: E402
    host_authority_client,
    host_integration,
    host_taxonomy,
    protocol_admission,
    runtime_bootstrap,
)

PROFILE = Path("C:/Users/operator/.claude-account2")
SCOPED = f'saipen host repair --host claude --profile "{PROFILE}"'


def _unstarted(step: str | None) -> dict:
    """The problem an unstarted authority leaves, as protocol_admission files it."""
    return host_taxonomy.problem(
        "transport",
        "AUTHORITY_UNREACHABLE",
        "no authority service was started on behalf of this process",
        step=step,
    )


class NoticeNamesTheCause(unittest.TestCase):
    def test_a_foreign_profile_hook_is_named_instead_of_a_silent_service(self):
        notice = host_authority_client.degraded_notice(
            [_unstarted("HOOK_ARTIFACT_MISMATCH")], repair=SCOPED
        )
        self.assertIn("AUTHORITY_UNREACHABLE/HOOK_ARTIFACT_MISMATCH", notice)
        self.assertIn("another configuration profile", notice)
        self.assertNotIn("did not answer", notice)
        self.assertTrue(notice.endswith("To restore verification run: " + SCOPED), notice)

    def test_a_service_that_really_did_not_answer_is_still_said_so(self):
        notice = host_authority_client.degraded_notice([_unstarted(None)])
        self.assertIn("The SAIPEN authority service did not answer.", notice)
        self.assertTrue(notice.endswith("To restore verification run: saipen host repair"))

    def test_every_identity_step_has_its_own_sentence(self):
        from saipen_engine import host_authority_identity as identity

        steps = [
            getattr(identity, name) for name in dir(identity) if name.startswith("REASON_")
        ]
        self.assertGreaterEqual(len(steps), 8)
        sentences = {step: host_taxonomy.step_summary(step) for step in steps}
        self.assertEqual([step for step, text in sentences.items() if not text], [])
        self.assertEqual(len(set(sentences.values())), len(steps), "two steps share a sentence")
        self.assertIsNone(host_taxonomy.step_summary("NOT_A_STEP"))
        self.assertIsNone(host_taxonomy.step_summary(None))

    def test_the_short_marker_carries_the_scoped_command_too(self):
        brief = host_authority_client.degraded_notice(
            [_unstarted("HOOK_ARTIFACT_MISMATCH")], brief=True, repair=SCOPED
        )
        self.assertTrue(brief.endswith("Restore with: " + SCOPED), brief)

    def test_the_cap_is_never_spent_on_the_command(self):
        deep = Path("C:/Users/operator") / ("profiles-" + "x" * 600) / ".claude-account2"
        scoped = f'saipen host repair --host claude --profile "{deep}"'
        problems = [
            _unstarted("HOOK_ARTIFACT_MISMATCH"),
            host_taxonomy.problem("instruction", "ACTIVATION_BLOCK_ABSENT", "no block"),
            host_taxonomy.problem("host", "HOOK_STALE", "stale"),
        ]
        notice = host_authority_client.degraded_notice(problems, repair=scoped)
        self.assertLessEqual(len(notice), 900)
        self.assertTrue(notice.startswith("SAIPEN is running in degraded mode."), notice)
        self.assertTrue(notice.endswith(" To restore verification run: " + scoped), notice)

    def test_a_scoped_repair_never_replaces_another_action(self):
        problem = host_taxonomy.problem(
            "transport", "AUTHORITY_IMPOSTOR", "the endpoint is served by something else"
        )
        notice = host_authority_client.degraded_notice([problem], repair=SCOPED)
        self.assertTrue(notice.endswith("run: " + host_taxonomy.DOCTOR), notice)


class DoctorNamesTheCause(unittest.TestCase):
    """`saipen host doctor` words the same health record with the same sentence."""

    def _reason(self, **health) -> str:
        from test_t1624_host_integration import facts

        _state, reasons, _action = host_integration.derive_state(
            facts(
                health={"state": "DEGRADED", "code": "AUTHORITY_UNREACHABLE", **health},
                authority={"running": False},
            )
        )
        return reasons[0]

    def test_a_foreign_profile_hook_is_named_by_the_doctor(self):
        reason = self._reason(step="HOOK_ARTIFACT_MISMATCH")
        self.assertIn("another configuration profile", reason)
        self.assertIn("(AUTHORITY_UNREACHABLE/HOOK_ARTIFACT_MISMATCH)", reason)
        self.assertNotIn("did not answer", reason)

    def test_an_unreachable_service_is_still_called_unreachable(self):
        reason = self._reason()
        self.assertIn("The SAIPEN authority service did not answer.", reason)
        self.assertIn("(AUTHORITY_UNREACHABLE)", reason)


class RepairIsScopedToTheSession(unittest.TestCase):
    def _context(self, host: str, profile: Path | None, home: Path) -> object:
        return protocol_admission.Context(
            project_root=None, session_id="s", host=host, home=home, profile=profile
        )

    def test_a_second_profile_is_repaired_by_name(self):
        home = Path("C:/Users/operator")
        self.assertEqual(
            protocol_admission.scoped_repair(self._context("claude", PROFILE, home)), SCOPED
        )

    def test_the_default_profile_and_other_hosts_keep_the_bare_command(self):
        home = Path("C:/Users/operator")
        default = home / ".claude"
        self.assertIsNone(protocol_admission.scoped_repair(self._context("claude", default, home)))
        self.assertIsNone(protocol_admission.scoped_repair(self._context("codex", None, home)))


class FreshnessFollowsTheProfile(unittest.TestCase):
    """The installer writes where CLAUDE_CONFIG_DIR points; the measurement must look there.

    Measured: with the carrier naming a second profile, prelaunch judged the
    default profile. A stale second profile read current and opened degraded
    after every source change. The installer is a recorder in every case.
    """

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="saipen-t1747-")
        self.addCleanup(tmp.cleanup)
        self.second = Path(tmp.name) / "claude-account2"
        self.second.mkdir()

    def _environment(self, carrier: Path | None):
        clean = {key: value for key, value in os.environ.items() if key != "CLAUDE_CONFIG_DIR"}
        if carrier is not None:
            clean["CLAUDE_CONFIG_DIR"] = str(carrier)
        return patch.dict(os.environ, clean, clear=True)

    def _prelaunch(self, carrier: Path | None):
        installer = patch.object(runtime_bootstrap, "_invoke_installer", return_value=None)
        source = patch.object(runtime_bootstrap, "resolve_authority", return_value=(ROOT, "claude"))
        proven = patch.object(runtime_bootstrap, "surface_fingerprint", return_value="gen-sha256:x")
        differs = patch.object(runtime_bootstrap, "surface_diff", return_value=["tools/saipen.py"])
        with self._environment(carrier), installer as recorded, source, proven, differs:
            report = runtime_bootstrap.prelaunch("claude", resync=True)
        return report, recorded

    def _same(self, left: object, right: object) -> bool:
        return os.path.normcase(os.path.abspath(str(left))) == os.path.normcase(
            os.path.abspath(str(right))
        )

    def test_prelaunch_measures_and_resyncs_the_profile_the_host_starts_with(self):
        report, installer = self._prelaunch(self.second)
        self.assertTrue(self._same(report["surface"], self.second / "skills" / "saipen"), report)
        installer.assert_called_once()
        self.assertTrue(self._same(installer.call_args.kwargs["profile"], self.second))

    def test_prelaunch_without_a_carrier_keeps_the_default_profile(self):
        default = Path.home() / ".claude"
        for carrier in (None, default):
            with self.subTest(carrier=carrier):
                report, installer = self._prelaunch(carrier)
                expected = default / "skills" / "saipen"
                self.assertTrue(self._same(report["surface"], expected), report)
                self.assertIsNone(installer.call_args.kwargs.get("profile"))

    def test_bootstrap_measures_the_profile_it_installs_into(self):
        installer = patch.object(runtime_bootstrap, "_invoke_installer", return_value=None)
        source = patch.object(runtime_bootstrap, "canonical_source_root", return_value=ROOT)
        host = patch.object(runtime_bootstrap, "_current_adapter", return_value="claude")
        proven = patch.object(runtime_bootstrap, "surface_fingerprint", return_value="gen-sha256:x")
        differs = patch.object(runtime_bootstrap, "surface_diff", return_value=[])
        scope = self._environment(self.second)
        with scope, installer as recorded, source, host, proven, differs as measured:
            runtime_bootstrap.run_bootstrap()
        self.assertTrue(self._same(recorded.call_args.kwargs["profile"], self.second))
        self.assertTrue(
            self._same(measured.call_args.args[1], self.second / "skills" / "saipen"),
            measured.call_args,
        )

    def test_another_host_ignores_the_claude_carrier(self):
        with self._environment(self.second):
            self.assertIsNone(runtime_bootstrap._launch_profile("codex"))
            self.assertTrue(
                self._same(runtime_bootstrap._launch_profile("claude"), self.second)
            )


class DryRunWritesNothing(unittest.TestCase):
    """Each writer is a recorder: a dropped flag shows up as a recorded call."""

    def _run(self, argv: list[str]) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(argv)
        return code, out.getvalue()

    def test_host_repair_answers_a_dry_run_with_the_doctor_report(self):
        report = {
            "ok": True,
            "code": "HOST_DOCTOR",
            "hosts": [],
            "needs_action": ["claude"],
            "next_action": SCOPED,
        }
        writer = patch.object(host_integration, "repair")
        reader = patch.object(host_integration, "doctor", return_value=report)
        with writer as repair, reader as doctor:
            code, text = self._run(["host", "repair", "--dry-run", "--json"])
        repair.assert_not_called()
        doctor.assert_called_once()
        self.assertEqual(code, 0, text)
        answer = json.loads(text)
        self.assertEqual((answer["code"], answer["dry_run"]), ("DRY_RUN_PLAN", True))
        self.assertEqual(answer["would_repair"], ["claude"])
        self.assertNotIn("steps", answer)

    def test_a_profile_repair_plans_for_that_profile_only(self):
        report = {"ok": True, "code": "HOST_DOCTOR", "hosts": [], "needs_action": []}
        writer = patch.object(host_integration, "repair")
        reader = patch.object(host_integration, "doctor", return_value=report)
        with writer as repair, reader as doctor:
            code, _text = self._run(
                ["host", "repair", "--host", "claude", "--profile", str(PROFILE), "--dry-run"]
            )
        repair.assert_not_called()
        self.assertEqual(code, 0)
        self.assertEqual(doctor.call_args.kwargs["only"], "claude")
        self.assertEqual(doctor.call_args.kwargs["profile"], PROFILE)

    def test_host_repair_without_the_flag_still_repairs(self):
        report = {"ok": True, "code": "HOST_REPAIRED", "hosts": [], "steps": []}
        writer = patch.object(host_integration, "repair", return_value=report)
        reader = patch.object(host_integration, "doctor")
        with writer as repair, reader as doctor:
            code, text = self._run(["host", "repair", "--json"])
        repair.assert_called_once()
        doctor.assert_not_called()
        self.assertEqual((code, json.loads(text)["code"]), (0, "HOST_REPAIRED"))

    def test_writers_with_no_plan_refuse_a_dry_run(self):
        from saipen_engine import machine_runtime, path_launcher

        cases = (
            (["host", "mode", "strict"], host_integration, "mode"),
            (["host", "machine", "install"], machine_runtime, "install"),
            (["host", "machine", "remove"], machine_runtime, "remove"),
            (["host", "launcher", "install"], path_launcher, "install"),
            (["host", "launcher", "remove"], path_launcher, "remove"),
        )
        for argv, module, writer in cases:
            with self.subTest(argv=argv), patch.object(module, writer) as recorded:
                code, text = self._run([*argv, "--dry-run", "--json"])
                recorded.assert_not_called()
                self.assertEqual(code, 2, text)
                answer = json.loads(text)
                self.assertEqual((answer["ok"], answer["code"]), (False, "VALIDATION_FAILED"))
                self.assertIn(" ".join(argv), answer["detail"])
                self.assertIn("Nothing was written", answer["detail"])

    def test_host_mode_refuses_whatever_precedes_its_value(self):
        argv = ["host", "mode", "--home", "C:/Users/operator", "strict", "--dry-run", "--json"]
        with patch.object(host_integration, "mode") as recorded:
            code, text = self._run(argv)
        recorded.assert_not_called()
        self.assertEqual(code, 2, text)
        answer = json.loads(text)
        self.assertEqual((answer["ok"], answer["code"]), (False, "VALIDATION_FAILED"))
        self.assertIn("host mode strict", answer["detail"])

    def test_host_mode_without_a_value_stays_a_read_only_view(self):
        shown = {"ok": True, "code": "HOST_MODE", "mode": "degraded"}
        with patch.object(host_integration, "mode", return_value=shown) as recorded:
            code, text = self._run(["host", "mode", "--dry-run", "--json"])
        self.assertEqual(recorded.call_args.args, (None,))
        self.assertEqual((code, json.loads(text)["mode"]), (0, "degraded"))

    def test_a_runtime_resync_refuses_a_dry_run(self):
        for flag in ("--prelaunch", "--bootstrap"):
            with self.subTest(flag=flag), patch.object(cli, "_runtime_install_command") as writer:
                code, text = self._run(["runtime", flag, "--dry-run", "--json"])
                writer.assert_not_called()
                self.assertEqual(code, 2, text)
                self.assertIn("runtime " + flag, json.loads(text)["detail"])

    def test_read_only_views_accept_the_flag(self):
        self.assertIsNone(cli._install_surface_writer(["host", "mode"]))
        self.assertIsNone(cli._install_surface_writer(["host", "machine"]))
        self.assertIsNone(cli._install_surface_writer(["host", "machine", "status"]))
        self.assertIsNone(cli._install_surface_writer(["host", "launcher", "status"]))
        self.assertIsNone(cli._install_surface_writer(["host", "doctor"]))
        self.assertIsNone(cli._install_surface_writer(["runtime", "--check-freshness"]))
        self.assertIsNone(cli._install_surface_writer(["status"]))


if __name__ == "__main__":
    unittest.main()

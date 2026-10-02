"""Focused T-1551 acceptance: the Codex Stop gate binds the canonical authority.

Four response classes, the deliberately bounded Stop re-entry, the canonical
injector install path, and the no-second-validator invariant. The Codex hook
artifact is a TRANSPORT: every verdict below is computed by the same canonical
renderer/checker the OpenCode text gate uses (`saipen response check
--classify`), and nothing in the adapter restates the response schema.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
for _entry in (str(TOOLS), str(ROOT)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from saipen_engine import response_surface as RS  # noqa: E402
from test_guard_hostile_matrix import active_project, fresh_project  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

HOOK = ROOT / "extensions" / "adapters" / "codex" / "saipen-guard.py"
REGISTRY = json.loads(
    (ROOT / "extensions" / "adapters" / "registry.json").read_text(encoding="utf-8-sig")
)
CODEX_ADAPTER = next(a for a in REGISTRY["adapters"] if a["id"] == "codex")


def setUpModule() -> None:
    # An outer host session (SAIPEN_PROJECT_ROOT etc.) must never bind these
    # disposable fixtures or the hook's own root resolution.
    isolate_host_session()


def wait_project():
    """An operational turn with NO eligible autonomous work (operator WAIT)."""
    return fresh_project(
        next_action="WAIT: manual-verify -- run the manual check and reply with its verdict",
        blocker="HUMAN_DECISION -- choose disposition",
    )


def validation_of(project: Path) -> str:
    from saipen_engine.conformance import conformance_decision

    return conformance_decision(project, gate="core")["status"]


def card(project: Path, *, wait: bool = False) -> str:
    validation = validation_of(project)
    if wait:
        boundary = RS.OperationalBoundary(
            "WAIT -- manual verify",
            "Work paused",
            "HUMAN_DECISION -- choose disposition",
            "Choose the disposition for the retained files",
            "saipen continue",
            validation,
        )
    else:
        boundary = RS.OperationalBoundary(
            "DONE", "No work changed", "NONE", "NONE", "NONE", validation
        )
    return RS.render_boundary(boundary)


def classify(project: Path, text: str):
    proc = subprocess.run(
        [
            sys.executable,
            str(TOOLS / "saipen.py"),
            "response",
            "check",
            "--stdin",
            "--json",
            "--classify",
            "--auto-eligibility",
            "--project-root",
            str(project),
        ],
        input=text,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        check=False,
    )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = {"raw": proc.stdout[-400:], "err": proc.stderr[-400:]}
    return proc.returncode, payload


def stop_event(
    project: Path | None,
    text: str,
    *,
    reentry: bool = False,
    root: Path | None = None,
    event: str = "Stop",
    raw_input: str | None = None,
):
    payload = {
        "hook_event_name": event,
        "cwd": str(project) if project is not None else "",
        "session_id": "codex-stop-test",
        "turn_id": "turn-1",
        "stop_hook_active": reentry,
        "last_assistant_message": text,
    }
    proc = subprocess.run(
        [
            sys.executable,
            str(HOOK),
            "--host",
            "codex",
            "--saipen-root",
            str(root or ROOT),
        ],
        input=raw_input if raw_input is not None else json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        check=False,
    )
    out = proc.stdout.strip()
    try:
        parsed = json.loads(out) if out else None
    except json.JSONDecodeError:
        parsed = {"raw": out}
    return proc.returncode, parsed, proc.stderr


class CanonicalClassifierTests(unittest.TestCase):
    """The four classes come from the ONE canonical authority."""

    def test_a_valid_boundary_passes(self):
        project = fresh_project()
        rc, out = classify(project, card(project))
        self.assertEqual(rc, 0, out)
        self.assertTrue(out["ok"])
        self.assertEqual(out["class"], RS.CLASS_VALID_BOUNDARY)
        self.assertEqual(out["code"], "RESPONSE_VALID")

    def test_ordinary_non_operational_chat_passes(self):
        project = fresh_project()
        rc, out = classify(project, "An ordinary explanation.")
        self.assertEqual(rc, 0, out)
        self.assertTrue(out["ok"])
        self.assertEqual(out["class"], RS.CLASS_ORDINARY_CHAT)
        self.assertEqual(out["code"], "NON_OPERATIONAL")

    def test_free_form_operational_prose_is_invalid(self):
        project = fresh_project()
        rc, out = classify(project, "STATUS: done\nBLOCKER: NONE -- nothing left")
        self.assertEqual(rc, 1)
        self.assertFalse(out["ok"])
        self.assertEqual(out["class"], RS.CLASS_INVALID_OPERATIONAL_PROSE)

    def test_prose_on_an_operational_turn_is_invalid(self):
        # The turn routes as OPERATOR_WAIT (operational): free-form prose is
        # exactly the invalid free-form operational response the OpenCode gate
        # rejects after a canonical command ran.
        project = wait_project()
        rc, out = classify(project, "Everything is fine.")
        self.assertEqual(rc, 1)
        self.assertFalse(out["ok"])
        self.assertEqual(out["class"], RS.CLASS_INVALID_OPERATIONAL_PROSE)
        self.assertEqual(out["turn_decision"], "OPERATOR_WAIT")

    def test_a_genuine_operator_boundary_passes_on_its_own_turn(self):
        project = wait_project()
        rc, out = classify(project, card(project, wait=True))
        self.assertEqual(rc, 0, out)
        self.assertTrue(out["ok"])
        self.assertEqual(out["class"], RS.CLASS_VALID_BOUNDARY)
        self.assertEqual(out["turn_decision"], "OPERATOR_WAIT")

    def test_autonomous_handback_is_classified_when_work_remains(self):
        project = active_project()
        rc, out = classify(project, card(project))
        self.assertEqual(rc, 1)
        self.assertFalse(out["ok"])
        self.assertEqual(out["class"], RS.CLASS_AUTONOMOUS_HANDBACK)
        self.assertEqual(out["turn_decision"], "AUTO_KICK")
        self.assertTrue(
            any("eligible autonomous action remains" in e for e in out["errors"]),
            out["errors"],
        )


class CodexStopHookTests(unittest.TestCase):
    """The transport maps the canonical verdict onto Codex Stop output."""

    def test_invalid_operational_prose_is_intercepted(self):
        project = wait_project()
        rc, out, _ = stop_event(project, "Everything is fine.")
        self.assertEqual(rc, 0, out)
        self.assertIsNotNone(out)
        self.assertEqual(out.get("decision"), "block")
        reason = out.get("reason", "")
        self.assertIn("INVALID_OPERATIONAL_PROSE", reason)
        self.assertIn("saipen response render --stdin", reason)
        self.assertIn("saipen response check --stdin --classify", reason)

    def test_chat_style_drift_is_intercepted_with_chat_guidance(self):
        # T-1558: an ordinary reply over the STYLE.md chat budget is refused, and
        # the correction prompt says how to fix a REPLY, not how to render an
        # operational surface the reply never claimed to be.
        project = fresh_project()
        essay = "\n".join(f"Fact {n} is exact." for n in range(12))
        rc, out, _ = stop_event(project, essay)
        self.assertEqual(rc, 0, out)
        self.assertIsNotNone(out)
        self.assertEqual(out.get("decision"), "block")
        reason = out.get("reason", "")
        self.assertIn("CHAT_STYLE_DRIFT", reason)
        self.assertIn("saipen response style --json", reason)
        self.assertNotIn("Assemble the control surface", reason)

    def test_a_reply_outside_the_host_locale_reaches_the_checker(self):
        # T-1558: the hook piped the reply to the checker in text mode, which
        # encodes with the LOCALE (cp1251 here). An Estonian diacritic is in no
        # ANSI code page, so the encode raised, the checker was reported
        # unreachable, and every Estonian reply passed as UNENFORCED.
        project = fresh_project()
        reply = "Õhtul äärmiselt ülemäärane öö."
        rc, out, _ = stop_event(project, reply)
        self.assertEqual(rc, 0)
        self.assertIsNone(out, out)

    def test_autonomous_handback_is_intercepted(self):
        project = active_project()
        rc, out, _ = stop_event(project, card(project))
        self.assertEqual(rc, 0, out)
        self.assertIsNotNone(out)
        self.assertEqual(out.get("decision"), "block")
        reason = out.get("reason", "")
        self.assertIn("AUTONOMOUS_HANDBACK", reason)
        self.assertIn("saipen continue --json", reason)

    def test_a_valid_boundary_passes_untouched(self):
        project = fresh_project()
        rc, out, _ = stop_event(project, card(project))
        self.assertEqual(rc, 0)
        self.assertIsNone(out)

    def test_ordinary_non_operational_chat_passes_untouched(self):
        project = fresh_project()
        rc, out, _ = stop_event(project, "An ordinary explanation.")
        self.assertEqual(rc, 0)
        self.assertIsNone(out)

    def test_stop_reentry_records_the_exact_capability_boundary(self):
        # stop_hook_active=true: the turn is already a Stop-hook continuation.
        # The one correction round is spent, so the gate RECORDS the boundary
        # instead of requesting another continuation (no uncontrolled loop).
        project = wait_project()
        rc, out, _ = stop_event(project, "Everything is fine.", reentry=True)
        self.assertEqual(rc, 0, out)
        self.assertIsNotNone(out)
        self.assertNotIn("decision", out)
        self.assertIs(out.get("continue"), True)
        self.assertEqual(out.get("stopReason"), "SAIPEN_STOP_BOUNDARY_UNENFORCED")
        message = out.get("systemMessage", "")
        self.assertIn("CODEX_STOP_REENTRY_NO_FAIL_CLOSED", message)
        self.assertIn("INVALID_OPERATIONAL_PROSE", message)
        self.assertIn("uncontrolled loop", message)

    def test_reentry_with_a_corrected_response_passes(self):
        project = wait_project()
        rc, out, _ = stop_event(project, card(project, wait=True), reentry=True)
        self.assertEqual(rc, 0)
        self.assertIsNone(out)

    def test_reentry_is_never_used_to_loop(self):
        # Even an operational prose answer on re-entry produces NO second
        # continuation request, whatever the class.
        project = active_project()
        rc, out, _ = stop_event(project, card(project), reentry=True)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("decision", out)
        self.assertIs(out.get("continue"), True)
        self.assertIn("CODEX_STOP_REENTRY_NO_FAIL_CLOSED", out.get("systemMessage", ""))

    def test_unreachable_checker_records_instead_of_pretending(self):
        project = wait_project()
        rc, out, _ = stop_event(project, "x", root=TOOLS / "no-such-root")
        self.assertEqual(rc, 0, out)
        self.assertIsNotNone(out)
        self.assertNotIn("decision", out)
        self.assertIn("CODEX_STOP_GATE_UNAVAILABLE", out.get("systemMessage", ""))

    def test_unreadable_payload_records_the_boundary(self):
        rc, out, _ = stop_event(None, "", raw_input="not json at all")
        self.assertEqual(rc, 0, out)
        self.assertIsNotNone(out)
        self.assertNotIn("decision", out)
        self.assertIn("CODEX_STOP_GATE_UNAVAILABLE", out.get("systemMessage", ""))

    def test_null_final_message_records_the_boundary(self):
        project = wait_project()
        payload = json.dumps(
            {
                "hook_event_name": "Stop",
                "cwd": str(project),
                "stop_hook_active": False,
                "last_assistant_message": None,
            }
        )
        rc, out, _ = stop_event(project, "", raw_input=payload)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("decision", out)
        self.assertIn("no last_assistant_message text", out["systemMessage"])

    def test_a_projectless_stop_is_ordinary_chat(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out, _ = stop_event(Path(tmp), "An ordinary explanation.")
        self.assertEqual(rc, 0)
        self.assertIsNone(out)

    def test_invalid_explicit_project_binding_does_not_fall_back_to_cwd(self):
        project = wait_project()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ, {"SAIPEN_PROJECT_ROOT": tmp}
        ):
            rc, out, _ = stop_event(project, "STATUS: probe")
        self.assertEqual(rc, 0, out)
        self.assertNotIn("decision", out)
        self.assertIn("explicit SAIPEN_PROJECT_ROOT", out["systemMessage"])

    def test_valid_explicit_project_binding_wins_over_cwd(self):
        declared = wait_project()
        other_cwd = fresh_project()
        with mock.patch.dict(os.environ, {"SAIPEN_PROJECT_ROOT": str(declared)}):
            rc, out, _ = stop_event(other_cwd, "Everything is fine.")
        self.assertEqual(rc, 0, out)
        self.assertEqual(out["decision"], "block")
        self.assertIn("INVALID_OPERATIONAL_PROSE", out["reason"])

    def test_foreign_events_are_not_gated(self):
        project = wait_project()
        rc, out, _ = stop_event(project, "Everything is fine.", event="PostToolUse")
        self.assertEqual(rc, 0)
        self.assertIsNone(out)


class InstallAndPreservationTests(unittest.TestCase):
    """The canonical injector path installs the gate and preserves the host."""

    def _home(self) -> tuple[tempfile.TemporaryDirectory, Path]:
        tmp = tempfile.TemporaryDirectory()
        home = Path(tmp.name)
        codex = home / ".codex"
        codex.mkdir()
        (codex / "hooks.json").write_text(
            json.dumps(
                {
                    "description": "user hooks",
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": "^Bash$",
                                "hooks": [{"type": "command", "command": "echo user-tool"}],
                            }
                        ],
                        "Stop": [
                            {"hooks": [{"type": "command", "command": "echo user-stop"}]}
                        ],
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return tmp, home

    def test_installer_writes_the_registry_surface_and_preserves_user_hooks(self):
        from install_host_guard import install

        tmp, home = self._home()
        self.addCleanup(tmp.cleanup)
        result = install("codex", home, ROOT)
        self.assertTrue(result["installed"], result)
        self.assertTrue(result["configured"], result)
        artifact = home / ".codex" / "hooks" / "saipen-guard.py"
        self.assertEqual(artifact.read_bytes(), HOOK.read_bytes())
        config = json.loads(
            (home / ".codex" / "hooks.json").read_text(encoding="utf-8-sig")
        )
        self.assertEqual(config["description"], "user hooks")
        self.assertEqual(
            config["hooks"]["PreToolUse"][0]["hooks"][0]["command"], "echo user-tool"
        )
        stop_entries = [
            hook for group in config["hooks"]["Stop"] for hook in group["hooks"]
        ]
        self.assertIn("echo user-stop", [e.get("command") for e in stop_entries])
        ours = [
            e
            for e in stop_entries
            if "--saipen-root" in str(e.get("command", ""))
            and "saipen-guard" in str(e.get("command", ""))
        ]
        self.assertEqual(len(ours), 1, stop_entries)
        entry = ours[0]
        self.assertEqual(entry["type"], "command")
        self.assertEqual(entry["timeout"], 60)
        for spelling in (entry["command"], entry["commandWindows"]):
            self.assertIn("saipen-guard.py", spelling)
            self.assertIn("--saipen-root", spelling)

    def test_reinstall_is_byte_stable_so_host_trust_survives(self):
        # Codex records hook trust against the hook definition's hash; a
        # churning install would silently un-trust a correct gate.
        from install_host_guard import install

        tmp, home = self._home()
        self.addCleanup(tmp.cleanup)
        install("codex", home, ROOT)
        config_path = home / ".codex" / "hooks.json"
        artifact = home / ".codex" / "hooks" / "saipen-guard.py"
        first_config = config_path.read_bytes()
        first_artifact = artifact.read_bytes()
        install("codex", home, ROOT)
        self.assertEqual(config_path.read_bytes(), first_config)
        self.assertEqual(artifact.read_bytes(), first_artifact)

    def test_cold_start_freshness_reads_current(self):
        # A cold start (fresh process) consulting the canonical freshness
        # surface must see the hook current and never a silent stale install.
        from install_host_guard import install

        tmp, home = self._home()
        self.addCleanup(tmp.cleanup)
        install("codex", home, ROOT)
        proc = subprocess.run(
            [
                sys.executable,
                str(TOOLS / "install_host_guard.py"),
                "codex",
                "--home",
                str(home),
                "--check",
            ],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        self.assertTrue(report["current"], report)
        self.assertTrue(report["configured"], report)
        self.assertTrue(report["root_current"], report)

    def test_tampered_artifact_reads_stale_not_current(self):
        from install_host_guard import install

        tmp, home = self._home()
        self.addCleanup(tmp.cleanup)
        install("codex", home, ROOT)
        artifact = home / ".codex" / "hooks" / "saipen-guard.py"
        artifact.write_bytes(artifact.read_bytes() + b"\n# tampered\n")
        report = install("codex", home, ROOT, check=True)
        self.assertFalse(report["current"], report)

    def test_installation_never_marks_host_trust(self):
        from install_host_guard import install

        tmp, home = self._home()
        self.addCleanup(tmp.cleanup)
        before = install("codex", home, ROOT, check=True)
        self.assertFalse(before["current"], before)
        self.assertEqual(before["effective"], "ENFORCEMENT_GAP")
        install("codex", home, ROOT)
        after = install("codex", home, ROOT, check=True)
        self.assertTrue(after["current"], after)
        # Health stays unproven even for a current install: installing bytes
        # is neither host trust nor a refused-effect proof.
        self.assertIsNone(after["health"])
        self.assertEqual(after["effective"], "UNKNOWN")
        self.assertEqual(CODEX_ADAPTER["declared_strength"], "ADVISORY")

    def test_preflight_detects_dual_hook_representation_without_mutation(self):
        from install_host_guard import install

        tmp, home = self._home()
        self.addCleanup(tmp.cleanup)
        config_toml = home / ".codex" / "config.toml"
        original = (
            '[[hooks.SessionStart]]\nmatcher = "startup"\n'
            '[[hooks.SessionStart.hooks]]\ntype = "command"\n'
            'command = "echo user-session"\n'
        ).encode()
        config_toml.write_bytes(original)
        install("codex", home, ROOT)
        report = install("codex", home, ROOT, check=True)
        proof = report["proof_preflight"]
        self.assertEqual(proof["hook_representation"], "DUAL_HOOK_REPRESENTATION")
        self.assertEqual(proof["inline_events"], ["SessionStart"])
        self.assertEqual(proof["hook_trust"], "HOOK_TRUST_UNPROVEN")
        self.assertEqual(proof["host_execution"], "UNPROVEN")
        self.assertEqual(proof["checker_reachability"], "UNPROVEN")
        self.assertEqual(proof["refused_effect"], "UNPROVEN")
        self.assertEqual(config_toml.read_bytes(), original)

    def test_preflight_ignores_trust_state_without_inline_hooks(self):
        from install_host_guard import install

        tmp, home = self._home()
        self.addCleanup(tmp.cleanup)
        config_toml = home / ".codex" / "config.toml"
        config_toml.write_text(
            '[hooks.state."fixture"]\ntrusted_hash = "sha256:test"\n',
            encoding="utf-8",
        )
        install("codex", home, ROOT)
        proof = install("codex", home, ROOT, check=True)["proof_preflight"]
        self.assertEqual(proof["hook_representation"], "SINGLE_HOOK_REPRESENTATION")
        self.assertEqual(proof["inline_events"], [])
        self.assertEqual(proof["hook_trust"], "HOOK_TRUST_UNPROVEN")


class NoSecondValidatorTests(unittest.TestCase):
    def test_the_adapter_carries_no_response_schema(self):
        text = HOOK.read_text(encoding="utf-8")
        for label in (*RS.MANDATORY_FIELDS, "DETAILS"):
            self.assertNotIn(label, text, label)
        self.assertNotIn("MANDATORY_FIELDS", text)
        # It names the canonical authority in prose but never imports or
        # reimplements its rules.
        self.assertNotIn("from saipen_engine", text)
        self.assertNotIn("import response_surface", text)

    def test_the_installed_hook_definition_carries_no_response_schema(self):
        from install_host_guard import command_pair

        posix, windows = command_pair("codex", HOOK, ROOT)
        for spelling in (posix, windows):
            for label in (*RS.MANDATORY_FIELDS, "DETAILS"):
                self.assertNotIn(label, spelling, spelling)

    def test_one_canonical_classifier_answers_every_host(self):
        # The classifier and the structural rules share one module; the CLI
        # and both host adapters delegate to it.
        self.assertTrue(callable(RS.classify_final_response))
        self.assertTrue(callable(RS.response_errors))
        cli = (TOOLS / "saipen.py").read_text(encoding="utf-8")
        self.assertIn("gate_final_response", cli)
        self.assertIn("from saipen_engine.response_surface import", cli)
        guard = (ROOT / "extensions" / "adapters" / "opencode" / "saipen-guard.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('"response", "check"', guard)


class RegistryWiringTests(unittest.TestCase):
    def test_codex_declares_the_installed_stop_gate(self):
        self.assertEqual(
            CODEX_ADAPTER["hook_install_surface"], "~/.codex/hooks/saipen-guard.py"
        )
        self.assertEqual(
            CODEX_ADAPTER["hook_artifact"], "extensions/adapters/codex/saipen-guard.py"
        )
        self.assertEqual(CODEX_ADAPTER["hook_config_surface"], "~/.codex/hooks.json")
        self.assertEqual(CODEX_ADAPTER["hook_installer"], "tools/install_host_guard.py")
        self.assertIn("hook", CODEX_ADAPTER["freshness_surfaces"])
        self.assertTrue((ROOT / CODEX_ADAPTER["hook_artifact"]).is_file())
        self.assertTrue((ROOT / CODEX_ADAPTER["hook_installer"]).is_file())

    def test_trust_is_declared_an_external_boundary(self):
        note = CODEX_ADAPTER.get("hook_surface_note", "")
        self.assertIn("/hooks", note)
        self.assertIn("never marks a hook trusted", note)
        self.assertIn("CODEX_STOP_REENTRY_NO_FAIL_CLOSED", note)
        self.assertEqual(CODEX_ADAPTER["declared_strength"], "ADVISORY")


if __name__ == "__main__":
    unittest.main()

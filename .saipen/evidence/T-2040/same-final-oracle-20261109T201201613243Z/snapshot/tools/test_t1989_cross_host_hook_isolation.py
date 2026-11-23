"""Regression tests for T-1989: cross-host hook overwrite isolation.

Verifies:
1. Incident reproduction: shared hook surface caused exit code 2 lockout.
2. Independent surfaces declared for Gemini and Antigravity in registry.json.
3. Both installation orders (Gemini -> Antigravity and Antigravity -> Gemini).
4. Gemini repair idempotency: repeated repairs cannot break Antigravity.
5. Incompatible foreign guard overwrite prevention.
6. Preservation of user hooks and unrelated configuration.
7. Forged host argument cannot impersonate another host.
8. Shared dispatcher verified caller delegation.
9. Antigravity lifecycle hooks (PreToolUse, SessionStart, PreInvocation).
10. Broker artifact resolution isolation.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import host_guard  # noqa: E402
from install_host_guard import install, uninstall  # noqa: E402
from saipen_engine import host_authority_broker as HAB  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


class CrossHostHookIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_01_reproduce_incident_shared_overwrite_fails_exit_2(self) -> None:
        """Simulate pre-fix regression: legacy host_guard overwrote saipen-guard.py
        without antigravity support, causing exit code 2."""
        hook_path = self.home / ".gemini" / "hooks" / "saipen-guard.py"
        hook_path.parent.mkdir(parents=True)

        legacy_code = (
            "import argparse, sys\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--host', choices=('kiro', 'gemini'), required=True)\n"
            "parser.add_argument('--saipen-root', required=True)\n"
            "parser.parse_args()\n"
        )
        hook_path.write_text(legacy_code, encoding="utf-8")

        proc = subprocess.run(
            [
                sys.executable,
                str(hook_path),
                "--host",
                "antigravity",
                "--saipen-root",
                str(REPO),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2, "Legacy guard must exit 2 on --host antigravity")
        self.assertIn("invalid choice: 'antigravity'", proc.stderr)

    def test_02_independent_paths_declared_in_registry(self) -> None:
        """registry.json must declare distinct hook_install_surface paths."""
        reg_file = REPO / "extensions" / "adapters" / "registry.json"
        reg = json.loads(reg_file.read_text(encoding="utf-8-sig"))
        adapters = {item["id"]: item for item in reg["adapters"]}

        gemini = adapters["gemini"]
        ag = adapters["antigravity"]

        self.assertEqual(gemini["hook_install_surface"], "~/.gemini/hooks/saipen-guard.py")
        self.assertEqual(gemini["install"]["hook"], "~/.gemini/hooks/saipen-guard.py")

        self.assertEqual(ag["hook_install_surface"], "~/.gemini/hooks/antigravity-saipen-guard.py")
        self.assertEqual(ag["install"]["hook"], "~/.gemini/hooks/antigravity-saipen-guard.py")

        self.assertNotEqual(gemini["hook_install_surface"], ag["hook_install_surface"])

    def test_03_install_orders_gemini_then_antigravity(self) -> None:
        """Order 1: Install Gemini, then Antigravity in the same home."""
        res_g = install("gemini", self.home, REPO)
        self.assertTrue(res_g["installed"])
        self.assertTrue(res_g["current"])

        res_a = install("antigravity", self.home, REPO)
        self.assertTrue(res_a["installed"])
        self.assertTrue(res_a["current"])

        chk_g = install("gemini", self.home, REPO, check=True)
        self.assertTrue(chk_g["current"], chk_g["problems"])
        self.assertEqual(chk_g["problems"], [])

        chk_a = install("antigravity", self.home, REPO, check=True)
        self.assertTrue(chk_a["current"], chk_a["problems"])
        self.assertEqual(chk_a["problems"], [])

        self.assertTrue((self.home / ".gemini" / "hooks" / "saipen-guard.py").is_file())
        self.assertTrue((self.home / ".gemini" / "hooks" / "antigravity-saipen-guard.py").is_file())

        s_file = self.home / ".gemini" / "settings.json"
        h_file = self.home / ".gemini" / "config" / "hooks.json"
        settings = json.loads(s_file.read_text(encoding="utf-8"))
        hooks_json = json.loads(h_file.read_text(encoding="utf-8"))

        g_cmd = settings["hooks"]["BeforeTool"][0]["hooks"][0]["command"]
        self.assertIn("saipen-guard.py", g_cmd)
        self.assertNotIn("antigravity-saipen-guard.py", g_cmd)

        a_cmd = hooks_json["saipen-guard"]["PreToolUse"][0]["hooks"][0]["command"]
        self.assertIn("antigravity-saipen-guard.py", a_cmd)

    def test_04_install_orders_antigravity_then_gemini(self) -> None:
        """Order 2: Install Antigravity, then Gemini (repair) in the same home."""
        res_a = install("antigravity", self.home, REPO)
        self.assertTrue(res_a["installed"])
        self.assertTrue(res_a["current"])

        res_g = install("gemini", self.home, REPO)
        self.assertTrue(res_g["installed"])
        self.assertTrue(res_g["current"])

        chk_a = install("antigravity", self.home, REPO, check=True)
        self.assertTrue(chk_a["current"], chk_a["problems"])
        self.assertEqual(chk_a["problems"], [])

        chk_g = install("gemini", self.home, REPO, check=True)
        self.assertTrue(chk_g["current"], chk_g["problems"])
        self.assertEqual(chk_g["problems"], [])

        self.assertTrue((self.home / ".gemini" / "hooks" / "saipen-guard.py").is_file())
        self.assertTrue((self.home / ".gemini" / "hooks" / "antigravity-saipen-guard.py").is_file())

    def test_05_gemini_repair_is_idempotent_and_cannot_break_antigravity(self) -> None:
        """Gemini repair repeatedly run must never alter Antigravity artifact or config."""
        install("antigravity", self.home, REPO)
        install("gemini", self.home, REPO)

        ag_hook = self.home / ".gemini" / "hooks" / "antigravity-saipen-guard.py"
        ag_config = self.home / ".gemini" / "config" / "hooks.json"
        ag_hook_bytes_before = ag_hook.read_bytes()
        ag_config_bytes_before = ag_config.read_bytes()

        for _ in range(3):
            repair = install("gemini", self.home, REPO)
            self.assertTrue(repair["current"])

        self.assertEqual(ag_hook.read_bytes(), ag_hook_bytes_before)
        self.assertEqual(ag_config.read_bytes(), ag_config_bytes_before)

        chk_a = install("antigravity", self.home, REPO, check=True)
        self.assertTrue(chk_a["current"])
        self.assertEqual(chk_a["problems"], [])

    def test_06_incompatible_guard_overwrite_is_refused(self) -> None:
        """An artifact location that contains another host's incompatible guard
        must be detected and protected against overwrite."""
        hook_path = self.home / ".gemini" / "hooks" / "saipen-guard.py"
        hook_path.parent.mkdir(parents=True)

        rel = "extensions/adapters/antigravity/saipen-guard.py"
        ag_shipped = (REPO / rel).read_bytes()
        hook_path.write_bytes(ag_shipped)

        chk = install("gemini", self.home, REPO, check=True)
        self.assertFalse(chk["current"])
        self.assertIn("artifact-owned-by-antigravity", chk["problems"])

        with self.assertRaises(ValueError) as ctx:
            install("gemini", self.home, REPO)
        self.assertIn("file carries antigravity's guard", str(ctx.exception))

    def test_07_unrelated_hooks_and_user_hooks_preserved(self) -> None:
        """User-defined hooks in settings.json and hooks.json are preserved."""
        hooks_json = self.home / ".gemini" / "config" / "hooks.json"
        hooks_json.parent.mkdir(parents=True)
        hooks_json.write_text(
            json.dumps({"user-custom-hook": {"enabled": True, "PreToolUse": []}}),
            encoding="utf-8",
        )

        settings = self.home / ".gemini" / "settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(
            json.dumps(
                {
                    "custom_setting": "val",
                    "hooks": {
                        "BeforeTool": [
                            {"matcher": "user_.*", "hooks": [{"name": "u-hook", "command": "echo"}]}
                        ]
                    },
                }
            ),
            encoding="utf-8",
        )

        install("antigravity", self.home, REPO)
        install("gemini", self.home, REPO)

        h_data = json.loads(hooks_json.read_text(encoding="utf-8"))
        self.assertIn("user-custom-hook", h_data)
        self.assertIn("saipen-guard", h_data)

        s_data = json.loads(settings.read_text(encoding="utf-8"))
        self.assertEqual(s_data.get("custom_setting"), "val")
        b_names = [
            h.get("name")
            for group in s_data["hooks"]["BeforeTool"]
            for h in group.get("hooks", [])
        ]
        self.assertIn("u-hook", b_names)
        self.assertIn("saipen-guard", b_names)

        uninstall("antigravity", self.home, REPO)
        h_after = json.loads(hooks_json.read_text(encoding="utf-8"))
        self.assertIn("user-custom-hook", h_after)
        self.assertNotIn("saipen-guard", h_after)

    def test_08_forged_host_argument_rejected_on_host_guard(self) -> None:
        """A caller claiming --host antigravity or --host gemini without proof is refused."""
        args_ag = ["host_guard.py", "--host", "antigravity", "--saipen-root", str(REPO)]
        args_gm = ["host_guard.py", "--host", "gemini", "--saipen-root", str(REPO)]
        p_ag = mock.patch("sys.argv", args_ag)
        p_gm = mock.patch("sys.argv", args_gm)
        p_ver = mock.patch.object(host_guard, "_CALLER_VERIFIER", return_value=False)
        with p_ver, p_ag:
            self.assertEqual(host_guard.main(), 2)

        with p_ver, p_gm:
            self.assertEqual(host_guard.main(), 2)

    def test_09_forged_host_argument_rejected_on_antigravity_guard(self) -> None:
        """antigravity guard artifact strictly refuses callers claiming --host gemini."""
        ag_hook = REPO / "extensions" / "adapters" / "antigravity" / "saipen-guard.py"
        proc = subprocess.run(
            [sys.executable, str(ag_hook), "--host", "gemini", "--saipen-root", str(REPO)],
            input="{}",
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("FORGED_HOST_IDENTITY", proc.stderr)

    def test_10_verified_caller_delegation_in_host_guard(self) -> None:
        """When host_guard is invoked with --host antigravity from a verified caller,
        it delegates to the Antigravity guard artifact and succeeds."""
        payload = json.dumps(
            {"hook_event_name": "PreToolUse", "toolCall": {"name": "view_file", "args": {}}}
        ).encode("utf-8")
        args = ["host_guard.py", "--host", "antigravity", "--saipen-root", str(REPO)]
        p_ver = mock.patch.object(host_guard, "_CALLER_VERIFIER", lambda h, r: h == "antigravity")
        p_arg = mock.patch("sys.argv", args)
        p_in = mock.patch("sys.stdin.buffer.read", return_value=payload)
        with p_ver, p_arg, p_in:
            self.assertEqual(host_guard.main(), 0)

    def test_11_antigravity_lifecycle_hooks(self) -> None:
        """Antigravity guard handles PreToolUse, SessionStart, PreInvocation cleanly."""
        ag_hook = REPO / "extensions" / "adapters" / "antigravity" / "saipen-guard.py"
        events = (
            ("PreToolUse", {"hook_event_name": "PreToolUse", "toolCall": {"name": "view_file"}}),
            ("SessionStart", {"hook_event_name": "SessionStart", "sessionId": "s-1"}),
            ("PreInvocation", {"hook_event_name": "PreInvocation", "userPrompt": "test prompt"}),
        )
        for event, payload in events:
            with self.subTest(event=event):
                cmd = [
                    sys.executable,
                    str(ag_hook),
                    "--host",
                    "antigravity",
                    "--saipen-root",
                    str(REPO),
                ]
                proc = subprocess.run(
                    cmd,
                    input=json.dumps(payload),
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(proc.returncode, 0, f"Event {event} failed: {proc.stderr}")

    def test_12_broker_artifacts_resolution(self) -> None:
        """Broker resolves separate hook artifacts for gemini and antigravity."""
        ag_art = HAB.hook_artifacts("antigravity", self.home)
        g_art = HAB.hook_artifacts("gemini", self.home)

        self.assertEqual(len(ag_art), 1)
        self.assertEqual(len(g_art), 1)

        self.assertTrue(ag_art[0].endswith("antigravity-saipen-guard.py"))
        self.assertTrue(g_art[0].endswith("saipen-guard.py"))
        self.assertNotEqual(ag_art, g_art)


if __name__ == "__main__":
    unittest.main()

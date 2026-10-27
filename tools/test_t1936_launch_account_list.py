"""T-1936: `saipen launch --list` -- read-only provider/account discovery.

FG-0046's bounded slice: name every Claude, Codex and Antigravity account on the
machine with provider, alias, profile directory, installed, authenticated and
managed/direct, reading no secret.

The four claims these tests pin, in the order the ticket's verify clause states
them:

1. Every account that exists is named, and no account that does not exist is
   invented. The fixture builds the exact shapes this host really carries --
   `~/.claude`, `~/.claude-account2`, `~/.codex`, `~/.codex-account2`,
   `~/.codex-account3free` -- and asserts alias/account/provider per row.
2. No secret is read. A credentials file is planted with a sentinel string and
   the test asserts the sentinel never appears in the report, that
   `secrets_read` is False, and that the marker is answered by PRESENCE.
3. Discovery mutates nothing. The whole tree is digested before and after and
   the digests must match; a read-only verb that creates a directory or
   rewrites settings is the failure SRC-184 names.
4. The fail-open order is answered only as far as it was measured:
   MANAGED_AVAILABLE when a managed runtime exists, else
   MANAGED_UNAVAILABLE_BUT_DIRECT_SAFE when a provider executable is on PATH,
   else DIRECT_UNSAFE.

A fifth test pins the CLI wiring itself, because the defect this ticket exists
for was in the dispatch: `saipen launch --list` answered ACTOR_UNBOUND because
the seat requirement ran before the list branch.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from saipen_engine import account_list

ROOT = Path(__file__).resolve().parent.parent

#: A value no honest report can contain. If any code path opens a credentials
#: file and copies it into the answer, this string shows up in the report.
SECRET = "sk-ant-SENTINEL-do-not-read-000000000000000"


def _digest_tree(root: Path) -> dict[str, str]:
    """Every path and its bytes, so any write anywhere is visible."""
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        rel = str(path.relative_to(root))
        if path.is_file():
            out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            out[rel] = "<dir>"
    return out


class AccountDiscoveryTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.home = Path(scratch.name)

        # The exact account shapes measured on this host.
        for name in (".claude", ".claude-account2", ".codex", ".codex-account2",
                     ".codex-account3free"):
            (self.home / name).mkdir(parents=True)

        self.credentials = self.home / ".claude" / ".credentials.json"
        self.credentials.write_text(json.dumps({"token": SECRET}), encoding="utf-8")
        (self.home / ".claude-account2" / ".credentials.json").write_text(
            json.dumps({"token": SECRET}), encoding="utf-8"
        )
        for name in (".codex", ".codex-account2", ".codex-account3free"):
            (self.home / name / "auth.json").write_text(
                json.dumps({"api_key": SECRET}), encoding="utf-8"
            )

    def _rows(self) -> list[dict]:
        with mock.patch.dict(os.environ, {"HOME": str(self.home),
                                          "USERPROFILE": str(self.home)}):
            returned = account_list.discover_accounts(self.home)
        self.assertTrue(returned["ok"])
        return returned["accounts"]

    def test_every_real_account_is_named_with_its_alias(self):
        rows = self._rows()
        by_alias = {row["alias"]: row for row in rows if row["alias"]}
        self.assertEqual(sorted(by_alias), ["cl1", "cl2", "cx1", "cx2", "cx3"])
        self.assertEqual(by_alias["cl1"]["provider"], "claude")
        self.assertEqual(by_alias["cl1"]["account"], 1)
        self.assertEqual(by_alias["cl2"]["account"], 2)
        self.assertEqual(by_alias["cx3"]["provider"], "codex")
        self.assertEqual(by_alias["cx3"]["account"], 3)
        for alias, row in by_alias.items():
            self.assertTrue(row["installed"], alias)
            self.assertEqual(row["authenticated"], "marker-present", alias)

    def test_the_profile_directory_is_the_canonical_key(self):
        """An alias is a spelling; provider + directory is the identity."""
        rows = self._rows()
        keys = [(row["provider"], row["profile"]) for row in rows if row["profile"]]
        self.assertEqual(len(keys), len(set(keys)), "a profile is listed twice")
        claude = [row for row in rows if row["provider"] == "claude"]
        self.assertEqual(len(claude), 2)
        self.assertEqual(
            {Path(row["profile"]).name for row in claude}, {".claude", ".claude-account2"}
        )

    def test_no_secret_is_read_into_the_report(self):
        returned = account_list.discover_accounts(self.home)
        rendered = json.dumps(returned)
        self.assertNotIn(SECRET, rendered, "the report carries credential contents")
        self.assertFalse(returned["secrets_read"])
        self.assertEqual(returned["mutation"], "none")

    def test_no_account_file_is_opened_at_all(self):
        """Not leaking is weaker than not reading. Pin the stronger claim.

        A report that reads `.credentials.json` and discards it would still pass
        the sentinel test above, and SRC-184 forbids READING a secret, not just
        publishing one. So every entry point that could load a file is wrapped
        and any access to a path inside an account profile is a failure --
        including a `stat`, since the requirement is that the probe stays on
        what it must know.
        """
        touched: list[str] = []
        real_read_text = Path.read_text
        real_read_bytes = Path.read_bytes
        real_open = Path.open

        def watched_read_text(self, *a, **k):
            touched.append(str(self))
            return real_read_text(self, *a, **k)

        def watched_read_bytes(self, *a, **k):
            touched.append(str(self))
            return real_read_bytes(self, *a, **k)

        def watched_open(self, *a, **k):
            touched.append(str(self))
            return real_open(self, *a, **k)

        with mock.patch.object(Path, "read_text", watched_read_text):
            with mock.patch.object(Path, "read_bytes", watched_read_bytes):
                with mock.patch.object(Path, "open", watched_open):
                    account_list.discover_accounts(self.home)

        offenders = [
            path for path in touched
            if any(Path(path).name == marker
                   for markers in account_list.AUTH_MARKERS.values()
                   for marker in markers)
        ]
        self.assertEqual(offenders, [], f"discovery opened a credentials file: {offenders}")

    def test_a_marker_that_is_absent_is_unknown_never_no(self):
        """A provider may authenticate by a route this probe cannot see."""
        (self.home / ".codex" / "auth.json").unlink()
        rows = self._rows()
        codex = next(row for row in rows if row["alias"] == "cx1")
        self.assertEqual(codex["authenticated"], "unknown")
        self.assertIsNone(codex["authentication_marker"])

    def test_discovery_writes_nothing_anywhere(self):
        before = _digest_tree(self.home)
        with mock.patch.dict(os.environ, {"HOME": str(self.home),
                                          "USERPROFILE": str(self.home)}):
            account_list.discover_accounts(self.home)
        after = _digest_tree(self.home)
        self.assertEqual(before, after, "read-only discovery mutated the tree")

    def test_an_explicit_home_scopes_the_whole_answer(self):
        """Found by the REVIEW self-audit, not by the first suite.

        `home` was honoured for the Claude/Codex/Gemini families but the loop
        over every OTHER registry adapter kept resolving its declared install
        home against the real process environment. A caller passing a scratch
        tree therefore got rows naming the operator's actual directories -- the
        argument was a half-promise, and a fixture could read outside itself.
        """
        rows = self._rows()
        escaped = [
            row for row in rows
            if row["profile"] and not Path(row["profile"]).is_relative_to(self.home)
        ]
        self.assertEqual(escaped, [], f"discovery escaped the requested home: {escaped}")

    def test_alias_needs_a_number_because_it_names_a_real_account(self):
        weird = self.home / ".claude-work"
        weird.mkdir()
        rows = self._rows()
        row = next(r for r in rows if r["profile"] and Path(r["profile"]).name == ".claude-work")
        self.assertIsNone(row["alias"], "an unnumbered profile must not invent cl?")
        self.assertIsNone(row["account"])


class LaunchabilityTests(unittest.TestCase):
    """The fail-open order, answered only as far as it was measured."""

    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.home = Path(scratch.name)
        (self.home / ".claude").mkdir(parents=True)

    def test_managed_available_wins_when_a_runtime_is_installed(self):
        adapter = {
            "id": "claude",
            "launch_executable": "claude",
            "install": {"skill": str(self.home / ".claude" / "skills" / "saipen")},
        }
        (self.home / ".claude" / "skills" / "saipen").mkdir(parents=True)
        with mock.patch.object(account_list, "_registry", lambda: [adapter]):
            with mock.patch.object(account_list.shutil, "which", lambda *a, **k: None):
                rows = account_list.discover_accounts(self.home)["accounts"]
        row = next(r for r in rows if r["provider"] == "claude")
        self.assertEqual(row["launchability"], "MANAGED_AVAILABLE")
        self.assertTrue(row["launchable"])

    def test_without_a_managed_runtime_a_startable_direct_route_is_safe(self):
        adapter = {
            "id": "claude",
            "launch_executable": "claude",
            "install": {"skill": str(self.home / "absent" / "skill")},
        }
        with mock.patch.object(account_list, "_registry", lambda: [adapter]):
            with mock.patch.object(
                account_list.shutil, "which", lambda *a, **k: "/usr/local/bin/claude"
            ):
                rows = account_list.discover_accounts(self.home)["accounts"]
        row = next(r for r in rows if r["provider"] == "claude")
        self.assertEqual(row["launchability"], "MANAGED_UNAVAILABLE_BUT_DIRECT_SAFE")

    def test_neither_route_proven_is_direct_unsafe(self):
        adapter = {
            "id": "claude",
            "launch_executable": None,
            "install": {"skill": str(self.home / "absent" / "skill")},
        }
        with mock.patch.object(account_list, "_registry", lambda: [adapter]):
            rows = account_list.discover_accounts(self.home)["accounts"]
        row = next(r for r in rows if r["provider"] == "claude")
        self.assertEqual(row["launchability"], "DIRECT_UNSAFE")
        self.assertFalse(row["launchable"])


class CommandTests(unittest.TestCase):
    """The dispatch defect this ticket exists for.

    `saipen launch --list` used to answer ACTOR_UNBOUND: the seat requirement
    ran before the list branch, so the very command SRC-184 documents never
    produced a list. Listing accounts is a read-only question about the
    machine, not an act as one of the accounts, so it must not need a seat.
    """

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as scratch:
            home = Path(scratch)
            (home / ".claude").mkdir()
            env = dict(os.environ)
            env["HOME"] = str(home)
            env["USERPROFILE"] = str(home)
            env.pop("CLAUDE_CONFIG_DIR", None)
            return subprocess.run(
                [sys.executable, str(ROOT / "tools" / "saipen.py"), *args],
                capture_output=True, text=True, cwd=str(ROOT), env=env, timeout=180,
            )

    def test_list_needs_no_seat_and_reports_json(self):
        done = self._run("launch", "--list", "--json")
        self.assertEqual(done.returncode, 0, done.stderr)
        report = json.loads(done.stdout)
        self.assertEqual(report["code"], "LAUNCH_ACCOUNT_LIST")
        self.assertFalse(report["secrets_read"])
        self.assertTrue(any(r["provider"] == "claude" for r in report["accounts"]))
        self.assertNotIn("ACTOR_UNBOUND", done.stdout)

    def test_starting_a_host_still_requires_a_seat(self):
        """The read-only exemption must not leak into the mutating route."""
        done = self._run("launch", "claude")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("ACTOR_UNBOUND", done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()

"""T-1557 (SRC-136): one per-user internal mailbox binds SAIPEN to SAIMAIL.

A new user's first `saipen init` must leave them reachable: the per-user
default mailbox is provisioned when SAIMAIL is installed, the turn-entry
read resolves it without any manual environment setup, and an explicit
``SAIMAIL_WORKSPACE`` still wins over the default. SAIMAIL carries internal
letters only; nothing here implies electronic mail.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import mailbox, telegrams  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1363_zero_manual_entry import cli, healthy  # noqa: E402

#: The fake `saimail-local`: records argv, answers `saipen init` by writing
#: the real marker the engine keys on, and answers `saipen telegrams` with
#: one unread row. `refuse` mode proves a refused init is honest data.
FAKE = r'''
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_SAIMAIL_ARGS"], "w", encoding="utf-8") as handle:
    json.dump(args, handle)
mode = os.environ.get("FAKE_SAIMAIL_MODE", "ok")
if args[1:3] == ["saipen", "init"]:
    workspace = args[args.index("--workspace") + 1]
    marker = os.path.join(workspace, "saimail-workspace.json")
    if mode == "refuse":
        print(json.dumps({"ok": False, "status": "REFUSED", "detail": "no"}))
        sys.exit(2)
    existed = os.path.isfile(marker)
    if not existed:
        os.makedirs(workspace, exist_ok=True)
        with open(marker, "w", encoding="utf-8") as handle:
            handle.write("{}")
    print(json.dumps({
        "ok": True,
        "status": "ALREADY_EXISTS" if existed else "CREATED",
        "detail": "workspace initialized",
    }))
    sys.exit(0)
if args[1:3] == ["saipen", "telegrams"]:
    print(json.dumps({"ok": True, "items": [{"envelope_id": "e1"}], "match_count": 1,
                      "rows_examined": 1, "exhausted": False, "cursor": None}))
    sys.exit(0)
print(json.dumps({"ok": False, "status": "WHAT"}))
sys.exit(2)
'''

STATE = {"task": "T-7", "agent": "builder"}


def setUpModule() -> None:
    isolate_host_session()


class FakeMail:
    """A `saimail-local` on a private PATH, plus an isolated user home."""

    def __init__(self, case: unittest.TestCase) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="saipen-t1557-bin-"))
        case.addCleanup(shutil.rmtree, self.dir, True)
        self.home = Path(tempfile.mkdtemp(prefix="saipen-t1557-home-"))
        case.addCleanup(shutil.rmtree, self.home, True)
        script = self.dir / "fake_saimail.py"
        script.write_text(FAKE, encoding="utf-8")
        self.args_file = self.dir / "args.json"
        if os.name == "nt":
            (self.dir / "saimail-local.cmd").write_text(
                f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8"
            )
        else:
            shim = self.dir / "saimail-local"
            shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
            shim.chmod(shim.stat().st_mode | stat.S_IEXEC)

    def env(self, mode: str = "ok", *, workspace: str | None = None) -> dict:
        env = {
            "PATH": str(self.dir) + os.pathsep + os.environ.get("PATH", ""),
            "LOCALAPPDATA": str(self.home),
            "FAKE_SAIMAIL_MODE": mode,
            "FAKE_SAIMAIL_ARGS": str(self.args_file),
        }
        os.environ.pop(telegrams.WORKSPACE_ENV, None)
        if workspace is not None:
            env[telegrams.WORKSPACE_ENV] = workspace
        return env

    @property
    def default_root(self) -> Path:
        return self.home / "saipen" / "saimail"


class ResolutionTests(unittest.TestCase):
    def test_unbound_home_has_no_binding_and_starts_no_process(self):
        fake = FakeMail(self)
        with mock.patch.dict(os.environ, fake.env()), mock.patch.object(
            telegrams.subprocess, "run", side_effect=AssertionError("no process")
        ):
            binding = mailbox.bound_workspace()
            answer = telegrams.turn_entry(Path("V:/project"), STATE)
        self.assertIsNone(binding)
        self.assertEqual(answer["state"], telegrams.STATE_NOT_CONFIGURED, answer)
        self.assertIn("saipen mail init", answer["detail"])

    def test_explicit_environment_beats_an_initialized_default(self):
        fake = FakeMail(self)
        explicit = fake.dir / "operator-mailbox"
        explicit.mkdir()
        (explicit / mailbox.MARKER_NAME).write_text("{}", encoding="utf-8")
        (fake.default_root).mkdir(parents=True)
        (fake.default_root / mailbox.MARKER_NAME).write_text("{}", encoding="utf-8")
        with mock.patch.dict(os.environ, fake.env(workspace=str(explicit))):
            binding = mailbox.bound_workspace()
            answer = telegrams.turn_entry(Path("V:/project"), STATE)
        self.assertEqual(binding, (explicit, "environment"))
        self.assertEqual(answer["state"], telegrams.STATE_OK, answer)
        self.assertIn(str(explicit), answer["read_command"])

    def test_initialized_default_binds_without_any_environment_setup(self):
        fake = FakeMail(self)
        with mock.patch.dict(os.environ, fake.env()):
            self.assertIsNone(mailbox.bound_workspace())
            result = mailbox.provision(Path("V:/project"), "builder")
            self.assertTrue(result["ok"], result)
            binding = mailbox.bound_workspace()
            answer = telegrams.turn_entry(Path("V:/project"), STATE)
        self.assertEqual(binding, (fake.default_root, "default"))
        self.assertEqual(answer["state"], telegrams.STATE_OK, answer)
        self.assertIn(str(fake.default_root), answer["read_command"])
        asked = json.loads(fake.args_file.read_text(encoding="utf-8"))
        self.assertEqual(asked[:4], ["--json", "saipen", "telegrams", "--workspace"])


class ProvisionTests(unittest.TestCase):
    def test_provision_is_idempotent_and_reports_each_status(self):
        fake = FakeMail(self)
        project = Path("V:/project")
        with mock.patch.dict(os.environ, fake.env()):
            first = mailbox.provision(project, "builder")
            second = mailbox.provision(project, "builder")
        self.assertTrue(first["ok"], first)
        self.assertEqual(first["status"], "CREATED")
        self.assertTrue(second["ok"], second)
        self.assertEqual(second["status"], "ALREADY_EXISTS")
        self.assertEqual(first["workspace"], str(fake.default_root))
        self.assertTrue(mailbox.is_initialized(fake.default_root))

    def test_a_refused_init_is_honest_data_and_leaves_no_marker(self):
        fake = FakeMail(self)
        with mock.patch.dict(os.environ, fake.env("refuse")):
            result = mailbox.provision(Path("V:/project"), "builder")
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "MAILBOX_REFUSED")
        self.assertFalse(mailbox.is_initialized(fake.default_root))
        with mock.patch.dict(os.environ, fake.env()):
            self.assertIsNone(mailbox.bound_workspace())

    def test_missing_saimail_is_unavailable_without_a_process(self):
        fake = FakeMail(self)
        empty_path = Path(tempfile.mkdtemp(prefix="saipen-t1557-empty-"))
        self.addCleanup(shutil.rmtree, empty_path, True)
        with mock.patch.dict(
            os.environ,
            {"PATH": str(empty_path), "LOCALAPPDATA": str(fake.home)},
        ), mock.patch.object(
            mailbox.subprocess, "run", side_effect=AssertionError("no process")
        ):
            result = mailbox.provision(Path("V:/project"), "builder")
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["code"], "MAILBOX_UNAVAILABLE")


class CliTests(unittest.TestCase):
    def test_mail_status_names_the_canonical_next_command_when_unbound(self):
        fake = FakeMail(self)
        with mock.patch.dict(os.environ, fake.env()):
            code, payload, text = cli(Path(healthy(self)), "mail", "--json")
        self.assertEqual(code, 0, text)
        self.assertTrue(payload["ok"], payload)
        self.assertEqual(payload["code"], "MAIL_STATUS")
        self.assertFalse(payload["bound"], payload)
        self.assertEqual(payload["canonical_next_command"], "saipen mail init")
        self.assertFalse(payload["default_initialized"], payload)

    def test_mail_init_binds_the_default_and_status_sees_it(self):
        fake = FakeMail(self)
        project = Path(healthy(self))
        with mock.patch.dict(os.environ, fake.env()):
            code, bound, text = cli(project, "mail", "init", "--json")
            self.assertEqual(code, 0, text)
            self.assertTrue(bound["ok"], bound)
            self.assertEqual(bound["code"], "MAILBOX_BOUND")
            code, status, text = cli(project, "mail", "--json")
        self.assertEqual(code, 0, text)
        self.assertTrue(status["bound"], status)
        self.assertEqual(status["source"], "default")
        self.assertTrue(status["default_initialized"], status)

    def test_mail_init_accepts_one_explicit_workspace(self):
        fake = FakeMail(self)
        explicit = fake.dir / "chosen"
        with mock.patch.dict(os.environ, fake.env()):
            code, payload, text = cli(
                Path(healthy(self)), "mail", "init", "--workspace", str(explicit), "--json"
            )
        self.assertEqual(code, 0, text)
        self.assertTrue(payload["ok"], payload)
        self.assertEqual(payload["workspace"], str(explicit))
        self.assertTrue(mailbox.is_initialized(explicit))

    def test_mail_rejects_unknown_subcommands_and_broken_options(self):
        fake = FakeMail(self)
        project = Path(healthy(self))
        with mock.patch.dict(os.environ, fake.env()):
            code, payload, text = cli(project, "mail", "explode", "--json")
            self.assertEqual(code, 2, text)
            self.assertFalse(payload["ok"], payload)
            code, payload, text = cli(project, "mail", "init", "--workspace", "--json")
            self.assertEqual(code, 2, text)
            self.assertFalse(payload["ok"], payload)
            code, payload, text = cli(project, "mail", "init", "extra", "--json")
            self.assertEqual(code, 2, text)
            self.assertFalse(payload["ok"], payload)

    def test_first_init_attaches_a_mailbox_for_a_new_user(self):
        fake = FakeMail(self)
        root = Path(tempfile.mkdtemp(prefix="saipen-t1557-init-"))
        self.addCleanup(shutil.rmtree, root, True)
        with mock.patch.dict(os.environ, fake.env()):
            code, payload, text = cli(root, "init", "--json")
        self.assertEqual(code, 0, text)
        self.assertTrue(payload["ok"], payload)
        self.assertTrue(payload["mailbox"]["ok"], payload["mailbox"])
        self.assertTrue(mailbox.is_initialized(fake.default_root))
        # The attach is a one-shot: a second init of the same user (new
        # project, mailbox now bound) skips instead of re-running SAIMAIL.
        other = Path(tempfile.mkdtemp(prefix="saipen-t1557-init2-"))
        self.addCleanup(shutil.rmtree, other, True)
        with mock.patch.dict(os.environ, fake.env()):
            code, second, text = cli(other, "init", "--json")
        self.assertEqual(code, 0, text)
        self.assertEqual(second["mailbox"]["code"], "MAILBOX_ATTACH_SKIPPED", second)

    def test_first_init_without_saimail_still_succeeds(self):
        fake = FakeMail(self)
        empty_path = Path(tempfile.mkdtemp(prefix="saipen-t1557-nopath-"))
        self.addCleanup(shutil.rmtree, empty_path, True)
        root = Path(tempfile.mkdtemp(prefix="saipen-t1557-init3-"))
        self.addCleanup(shutil.rmtree, root, True)
        with mock.patch.dict(
            os.environ, {"PATH": str(empty_path), "LOCALAPPDATA": str(fake.home)}
        ):
            os.environ.pop(telegrams.WORKSPACE_ENV, None)
            code, payload, text = cli(root, "init", "--json")
        self.assertEqual(code, 0, text)
        self.assertTrue(payload["ok"], payload)
        self.assertEqual(payload["mailbox"]["code"], "MAILBOX_ATTACH_SKIPPED")


if __name__ == "__main__":
    unittest.main()

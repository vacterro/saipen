"""T-1678 (SRC-192): the PATH launcher has an owner.

PATH_LAUNCHER is the first transport of `SAIPEN_ENTRY.json`, and no installer
created one: on the operator's machine every host answered degraded
`no_canonical_path_launcher` and an executor typing `saipen` got "command not
found" until two hand copies were put on PATH (E-13246).

Evidence classes, kept apart:

* OWNER     -- `path_launcher` against disposable homes: the declared
               directories, the rendered bytes, adoption of a hand copy,
               refusal of a foreign launcher, removal of what is ours only.
* DOCTOR    -- `host doctor` reports a missing or stale launcher and
               `host repair` writes it, on a disposable profile.
* INSTALL   -- the real installer and uninstaller on a sandbox profile, then
               `host entry` through PATH from a fresh project.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
for _entry in (str(TOOLS), str(ROOT / "bootstrap")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

import cli_launcher  # noqa: E402
import install_ownership  # noqa: E402
from saipen_engine import entry_resolver  # noqa: E402
from saipen_engine import host_integration as HG  # noqa: E402
from saipen_engine import path_launcher as PL  # noqa: E402
from saipen_engine import runtime_bootstrap  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

ENGINE = ROOT / "tools" / "saipen.py"
WINDOWS = os.name == "nt"
POWERSHELL = shutil.which("powershell") if WINDOWS else shutil.which("pwsh")
BASH = (
    str(Path("C:/Program Files/Git/bin/bash.exe"))
    if WINDOWS and Path("C:/Program Files/Git/bin/bash.exe").is_file()
    else shutil.which("bash")
)


def setUpModule() -> None:
    isolate_host_session()


def clean_path(*first: Path) -> str:
    """PATH with `first` in front and every directory that already holds a
    `saipen` taken out: the operator's own launcher must not answer for the
    sandbox, in either direction."""
    kept = []
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry.strip():
            continue
        if any((Path(entry) / name).exists() for name in ("saipen", "saipen.cmd")):
            continue
        kept.append(entry)
    return os.pathsep.join([*(str(item) for item in first), *kept])


class Scratch(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="saipen-t1678-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.bin = PL.declared_dirs(self.home)[0]
        self.bare = clean_path()
        self.env = {"PATH": clean_path(self.bin)}

    def launchers(self) -> dict[str, Path]:
        return {name: self.bin / name for name in PL.names()}


# ----------------------------------------------------------------------- OWNER


class OwnerTests(Scratch):
    def test_the_bytes_are_the_installer_renderer_and_the_resolver_proves_them(self):
        rendered = PL.render(sys.executable, str(ENGINE))
        reference = cli_launcher.render_launchers(sys.executable, str(ENGINE))
        self.assertEqual(rendered, {name: reference[name] for name in PL.names()})
        PL.install(ENGINE, self.home, self.env)
        for path in self.launchers().values():
            self.assertTrue(entry_resolver.prove_launcher(path, ENGINE)["ok"], path)

    def test_every_declared_directory_is_inside_the_home_and_the_uninstaller_agrees(self):
        for directory in PL.declared_dirs(self.home):
            self.assertTrue(directory.is_relative_to(self.home), directory)
        self.assertEqual(
            {self.home.joinpath(*parts) for parts in install_ownership.LAUNCHER_DIRS},
            set(PL.declared_dirs(self.home)),
        )
        self.assertEqual(
            self.home.joinpath(*install_ownership.LAUNCHER_RECORD), PL.record_path(self.home)
        )
        self.assertEqual(set(install_ownership.LAUNCHER_NAMES), {PL.POSIX_NAME, PL.WINDOWS_NAME})

    def test_no_declared_directory_on_path_writes_nothing_and_names_the_one_to_add(self):
        env = {"PATH": self.bare}
        report = PL.status(ENGINE, self.home, env)
        self.assertEqual(report["code"], PL.CODE_NO_DIRECTORY)
        self.assertIn(str(self.bin), report["action"])
        answer = PL.install(ENGINE, self.home, env)
        self.assertFalse(answer["ok"])
        self.assertEqual(answer["code"], PL.CODE_NO_DIRECTORY)
        self.assertEqual(list(self.home.iterdir()), [])
        self.assertEqual(env, {"PATH": self.bare})

    def test_install_owns_both_launchers_and_a_second_install_changes_nothing(self):
        self.assertEqual(PL.status(ENGINE, self.home, self.env)["code"], PL.CODE_ABSENT)
        answer = PL.install(ENGINE, self.home, self.env)
        self.assertTrue(answer["ok"], answer)
        self.assertEqual((answer["code"], answer["status"]), (PL.CODE_INSTALLED, PL.CODE_READY))
        record = PL.read_record(self.home)
        for path in self.launchers().values():
            self.assertEqual(record[str(path)], hashlib.sha256(path.read_bytes()).hexdigest())
        which = shutil.which("saipen", path=self.env["PATH"])
        self.assertEqual(Path(which).parent, self.bin)
        before = {name: path.read_bytes() for name, path in self.launchers().items()}
        again = PL.install(ENGINE, self.home, self.env)
        self.assertEqual(again["code"], PL.CODE_CURRENT)
        self.assertEqual({n: p.read_bytes() for n, p in self.launchers().items()}, before)

    def test_a_hand_copy_that_proves_the_engine_is_adopted(self):
        self.bin.mkdir(parents=True)
        for name, payload in PL.render(sys.executable, str(ENGINE)).items():
            (self.bin / name).write_bytes(payload)
        report = PL.status(ENGINE, self.home, self.env)
        self.assertEqual(report["code"], PL.CODE_STALE)
        self.assertEqual(set(report["files"].values()), {"unowned-proving"})
        self.assertEqual(report["action"], PL.INSTALL_ACTION)
        self.assertTrue(PL.install(ENGINE, self.home, self.env)["ok"])
        self.assertEqual(PL.status(ENGINE, self.home, self.env)["code"], PL.CODE_READY)

    def test_a_foreign_launcher_is_never_touched(self):
        self.bin.mkdir(parents=True)
        other = self.tmp / "other-install" / "tools" / "saipen.py"
        foreign = PL.render(sys.executable, str(other))
        for name, payload in foreign.items():
            (self.bin / name).write_bytes(payload)
        report = PL.status(ENGINE, self.home, self.env)
        self.assertEqual(report["code"], PL.CODE_FOREIGN)
        answer = PL.install(ENGINE, self.home, self.env)
        self.assertFalse(answer["ok"])
        self.assertEqual(answer["code"], PL.CODE_FOREIGN)
        for name, payload in foreign.items():
            self.assertEqual((self.bin / name).read_bytes(), payload)
        self.assertFalse(PL.record_path(self.home).exists())

    def test_an_owned_launcher_for_a_moved_engine_is_stale_and_rewritten(self):
        moved = self.tmp / "moved" / "tools" / "saipen.py"
        moved.parent.mkdir(parents=True)
        moved.write_text("# engine\n", encoding="utf-8")
        PL.install(moved, self.home, self.env)
        report = PL.status(ENGINE, self.home, self.env)
        self.assertEqual(report["code"], PL.CODE_STALE)
        self.assertEqual(set(report["files"].values()), {"owned-stale"})
        self.assertTrue(PL.install(ENGINE, self.home, self.env)["ok"])
        for path in self.launchers().values():
            self.assertTrue(entry_resolver.prove_launcher(path, ENGINE)["ok"])

    def test_a_saipen_earlier_on_path_is_reported_as_shadowing(self):
        earlier = self.tmp / "earlier"
        earlier.mkdir()
        for name, payload in PL.render(sys.executable, str(self.tmp / "x.py")).items():
            (earlier / name).write_bytes(payload)
        env = {"PATH": clean_path(earlier, self.bin)}
        PL.install(ENGINE, self.home, env)
        report = PL.status(ENGINE, self.home, env)
        self.assertEqual(report["code"], PL.CODE_SHADOWED)
        self.assertEqual(Path(report["shadowed_by"]).parent, earlier)

    def test_removal_takes_only_what_is_still_as_written(self):
        for remover in ("engine", "uninstaller"):
            with self.subTest(remover=remover):
                PL.install(ENGINE, self.home, self.env)
                edited = self.launchers()[PL.POSIX_NAME]
                edited.write_bytes(edited.read_bytes() + b"# mine now\n")
                stranger = self.bin / "other-tool.cmd"
                stranger.write_bytes(b"@echo off\r\n")
                if remover == "engine":
                    PL.remove(self.home)
                else:
                    install_ownership.remove_launcher(self.home)
                self.assertTrue(edited.is_file())
                self.assertTrue(stranger.is_file())
                for name, path in self.launchers().items():
                    if name != PL.POSIX_NAME:
                        self.assertFalse(path.exists(), path)
                self.assertFalse(PL.record_path(self.home).exists())
                edited.unlink()

    def test_the_uninstaller_refuses_a_record_that_names_a_file_elsewhere(self):
        victim = self.tmp / "elsewhere" / "saipen"
        victim.parent.mkdir()
        victim.write_bytes(b"keep\n")
        PL.record_path(self.home).parent.mkdir(parents=True)
        PL.record_path(self.home).write_text(
            json.dumps({"files": {str(victim): hashlib.sha256(b"keep\n").hexdigest()}}),
            encoding="utf-8",
        )
        self.assertEqual(install_ownership.remove_launcher(self.home)["removed"], 0)
        self.assertEqual(PL.remove(self.home)["removed"], [])
        self.assertTrue(victim.is_file())


# ---------------------------------------------------------------------- DOCTOR


class DoctorTests(Scratch):
    """Doctor and repair against a disposable profile: never the operator's."""

    def setUp(self) -> None:
        super().setUp()
        patcher = mock.patch.dict(
            os.environ,
            {
                "USERPROFILE": str(self.home),
                "HOME": str(self.home),
                "HOMEDRIVE": "",
                "HOMEPATH": "",
                "PATH": self.env["PATH"],
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_doctor_reports_a_missing_launcher_and_repair_writes_it(self):
        report = HG.doctor(home=self.home)
        self.assertEqual(report["path_launcher"]["code"], PL.CODE_ABSENT)
        self.assertIn("path launcher  ABSENT  saipen host launcher install", HG.render(report))
        with mock.patch.object(runtime_bootstrap, "_invoke_installer") as installer:
            repaired = HG.repair(home=self.home)
        installer.assert_not_called()
        self.assertEqual([step["step"] for step in repaired["steps"]], ["launcher:install"])
        self.assertTrue(repaired["ok"], repaired["steps"])
        self.assertEqual(repaired["path_launcher"]["code"], PL.CODE_READY)
        self.assertEqual(repaired["code"], "HOST_REPAIRED")

    def test_doctor_reports_a_stale_hand_copy_and_repair_replaces_it_with_an_owned_one(self):
        self.bin.mkdir(parents=True)
        for name, payload in PL.render(sys.executable, str(ENGINE)).items():
            (self.bin / name).write_bytes(payload)
        self.assertEqual(HG.doctor(home=self.home)["path_launcher"]["code"], PL.CODE_STALE)
        with mock.patch.object(runtime_bootstrap, "_invoke_installer"):
            repaired = HG.repair(home=self.home)
        self.assertEqual(repaired["path_launcher"]["code"], PL.CODE_READY)
        self.assertEqual(
            set(PL.read_record(self.home)), {str(path) for path in self.launchers().values()}
        )

    def test_a_profile_whose_path_names_no_declared_directory_gets_no_repair_step(self):
        with mock.patch.dict(os.environ, {"PATH": self.bare}):
            report = HG.doctor(home=self.home)
            self.assertEqual(report["path_launcher"]["code"], PL.CODE_NO_DIRECTORY)
            with mock.patch.object(runtime_bootstrap, "_invoke_installer"):
                repaired = HG.repair(home=self.home)
        self.assertEqual(repaired["steps"], [])
        self.assertEqual(list(self.home.iterdir()), [])

    def test_the_cli_verb_installs_reports_and_removes(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("SAIPEN_")}
        env.update(USERPROFILE=str(self.home), HOME=str(self.home), PYTHONUTF8="1")

        def cli(*args: str) -> dict:
            proc = subprocess.run(
                [sys.executable, "-B", str(ENGINE), "host", "launcher", *args, "--json"],
                cwd=str(self.tmp),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=120,
            )
            return json.loads(proc.stdout)

        self.assertEqual(cli("status")["code"], PL.CODE_ABSENT)
        self.assertEqual(cli("install")["status"], PL.CODE_READY)
        self.assertEqual(cli()["code"], PL.CODE_READY)
        self.assertEqual(cli("remove")["code"], PL.CODE_REMOVED)
        self.assertEqual(cli("status")["code"], PL.CODE_ABSENT)
        self.assertEqual(cli("bogus")["code"], "VALIDATION_FAILED")


# --------------------------------------------------------------------- INSTALL


class InstallerTests(unittest.TestCase):
    """The real installer and uninstaller on a sandbox profile whose PATH names
    its own `bin`: afterwards `saipen` typed in a fresh project is the
    canonical PATH_LAUNCHER, and the uninstaller takes it back."""

    def run_process(self, argv, env, cwd) -> subprocess.CompletedProcess:
        result = subprocess.run(
            argv,
            env=env,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
        self.assertEqual(result.returncode, 0, result.stdout[-3000:] + result.stderr[-2000:])
        return result

    def lifecycle(self, install: list[str], uninstall: list[str]) -> None:
        with tempfile.TemporaryDirectory(prefix="saipen-t1678-install-") as raw:
            base = Path(raw)
            home, project = base / "user home", base / "new project"
            home.mkdir()
            project.mkdir()
            directory = PL.declared_dirs(home)[0]
            env = {k: v for k, v in os.environ.items() if not k.startswith("SAIPEN_")}
            env.update(
                HOME=str(home),
                USERPROFILE=str(home),
                LOCALAPPDATA=str(home / "AppData/Local"),
                XDG_CONFIG_HOME=str(home / ".config"),
                SAIPEN_USER_CONFIG_HOME=str(home / ".saipen-user"),
                SAIPEN_UNINSTALL_SKIP_TASK="1",
                PYTHONUTF8="1",
                PYTHONDONTWRITEBYTECODE="1",
                SAIPEN_PYTHON=sys.executable,
                PATH=clean_path(directory),
            )
            for name in ("ZAICODE_HOME", "SAIMAIL_WORKSPACE"):
                env.pop(name, None)
            report = self.run_process(install, env, project).stdout
            self.assertRegex(report, r"PATH launcher\s+installed in ")
            which = shutil.which("saipen", path=env["PATH"])
            self.assertIsNotNone(which, report[-2000:])
            self.assertEqual(Path(which).parent, directory)
            typed = (
                [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", "saipen"]
                if WINDOWS
                else ["saipen"]
            )
            init = json.loads(self.run_process([*typed, "set", "--json"], env, project).stdout)
            self.assertEqual(init["code"], "INIT_COMPLETED", init)
            entry = json.loads(
                self.run_process([*typed, "host", "entry", "--json"], env, project).stdout
            )
            self.assertEqual(entry["transport"], entry_resolver.PATH_LAUNCHER, entry)
            self.assertNotIn("no_canonical_path_launcher", entry["degraded"])
            self.run_process(uninstall, env, project)
            for name in PL.names():
                self.assertFalse((directory / name).exists(), name)
            self.assertFalse(PL.record_path(home).exists())

    @unittest.skipUnless(WINDOWS and POWERSHELL, "Windows PowerShell transport unavailable")
    def test_powershell_installer_owns_the_path_launcher_and_uninstall_removes_it(self):
        self.lifecycle(
            [
                POWERSHELL,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ROOT / "bootstrap" / "inject.ps1"),
            ],
            [
                POWERSHELL,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ROOT / "bootstrap" / "uninstall.ps1"),
            ],
        )

    @unittest.skipUnless(BASH and not WINDOWS, "POSIX bash transport unavailable")
    def test_bash_installer_owns_the_path_launcher_and_uninstall_removes_it(self):
        self.lifecycle(
            [BASH, str(ROOT / "bootstrap" / "inject.sh")],
            [BASH, str(ROOT / "bootstrap" / "uninstall.sh")],
        )


if __name__ == "__main__":
    unittest.main()

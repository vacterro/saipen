"""SRC-114 entry resolver: a cold host reaches machine truth without guessing.

Every fixture home here is a real, runnable SAIPEN home: its `tools/saipen.py`
delegates to this repository's engine and its `bin/` launchers are rendered by
the one launcher owner, `bootstrap/cli_launcher.py`. So "status succeeds" means
the real CLI answered through the transport the resolver chose, not that a
stub printed something.
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(REPO / "bootstrap") not in sys.path:
    sys.path.insert(0, str(REPO / "bootstrap"))

import cli_launcher  # noqa: E402
import test_host_bootstrap as hbt  # noqa: E402
from saipen_engine import entry_resolver as er  # noqa: E402
from saipen_engine.command_effects import classify_invocation  # noqa: E402
from saipen_engine.state import parse_frontmatter, persisted_home_error  # noqa: E402
from test_fixture_support import operator_request_env  # noqa: E402

LAUNCHER = "saipen.cmd" if os.name == "nt" else "saipen"
_SHIM = (
    "import os, runpy, sys\n"
    "REAL = {real!r}\n"
    "sys.argv[0] = REAL\n"
    "sys.path.insert(0, os.path.dirname(REAL))\n"
    "runpy.run_path(REAL, run_name='__main__')\n"
)


def _runnable_home(*, launcher: bool = True, name: str = "home") -> Path:
    """A flattened SAIPEN home whose engine is this repository's engine."""
    home = hbt._install(hbt._temp() / name)
    (home / "tools" / "saipen.py").write_text(
        _SHIM.format(real=str(TOOLS / "saipen.py")), encoding="utf-8"
    )
    if launcher:
        cli_launcher.write_launchers(
            sys.executable, str(home / "tools" / "saipen.py"), home / "bin"
        )
        if os.name != "nt":
            os.chmod(home / "bin" / "saipen", 0o755)
    return home


def _cold_env(**extra: str) -> dict:
    """A process environment with no SAIPEN carrier and no `saipen` on PATH."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("SAIPEN_")}
    system = os.environ.get("SYSTEMROOT", r"C:\Windows")
    env["PATH"] = str(Path(system) / "System32") if os.name == "nt" else "/usr/bin:/bin"
    env.update(extra)
    return env


def _resolve(root: Path, *, path: str = "", host: str | None = None, command=None, **env) -> dict:
    return er.resolve_entry(
        root,
        host=host,
        env={"PATH": path, **env},
        command=command,
        honor_environment=False,
    )


def _run(argv: list[str], root: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env or _cold_env(),
        stdin=subprocess.DEVNULL,
        timeout=300,
    )


def _status(argv_prefix: list[str], root: Path, env: dict | None = None) -> dict:
    proc = _run([*argv_prefix, "status", "--json"], root, env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return json.loads(proc.stdout)


def _home_of(root: Path) -> str:
    fields, error = parse_frontmatter((root / ".saipen" / "STATE.md").read_text(encoding="utf-8"))
    assert error is None, error
    return fields.get("saipen_home")


def _entry_cli(args: list[str], root: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return _run([sys.executable, str(TOOLS / "saipen.py"), "host", "entry", *args], root, env)


class EntryResolutionMatrix(unittest.TestCase):
    def test_case01_empty_path_reaches_status_through_the_entry_runner(self):
        home = _runnable_home()
        root = hbt._project(home=str(home))
        proc = _entry_cli(["--", "status", "--json"], root)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(json.loads(proc.stdout)["ok"])
        summary = json.loads(proc.stderr.split("SAIPEN_ENTRY ", 1)[1].splitlines()[0])
        self.assertIn(summary["transport"], (er.DIRECT_LAUNCHER, er.DIRECT_ENGINE))
        self.assertEqual(Path(summary["saipen_home"]), home.resolve())

    def test_case02_canonical_path_launcher_is_selected(self):
        home = _runnable_home()
        root = hbt._project(home=str(home))
        resolved = _resolve(root, path=str(home / "bin"))
        self.assertTrue(resolved["ok"], resolved)
        self.assertEqual(resolved["code"], er.PATH_LAUNCHER)
        self.assertEqual(resolved["command_form"], "saipen")
        self.assertEqual(Path(resolved["argv_prefix"][0]).parent, (home / "bin").resolve())
        self.assertTrue(_status(resolved["argv_prefix"], root)["ok"])

    def test_case03_foreign_or_stale_path_launcher_is_never_trusted(self):
        home = _runnable_home()
        foreign = _runnable_home(name="foreign")
        garbage = hbt._temp() / "garbage-bin"
        garbage.mkdir()
        (garbage / LAUNCHER).write_text("@echo off\necho not saipen\n", encoding="utf-8")
        if os.name != "nt":
            os.chmod(garbage / LAUNCHER, 0o755)
        root = hbt._project(home=str(home))
        for bad in (foreign / "bin", garbage):
            with self.subTest(path=str(bad)):
                resolved = _resolve(root, path=str(bad))
                self.assertEqual(resolved["code"], er.DIRECT_LAUNCHER, resolved)
                self.assertNotIn(str(bad), " ".join(resolved["argv_prefix"]))
                mismatch = [
                    d for d in resolved["diagnostics"] if d["code"] == "provenance_mismatch"
                ]
                self.assertEqual(len(mismatch), 1, resolved["diagnostics"])
                self.assertIn(str(bad), mismatch[0]["detail"])
        # Without a canonical launcher the fallback is the engine, still not the foreign file.
        bare = _runnable_home(launcher=False, name="bare")
        resolved = _resolve(hbt._project(home=str(bare)), path=str(foreign / "bin"))
        self.assertEqual(resolved["code"], er.DIRECT_ENGINE, resolved)

    def test_case04_direct_launcher_with_empty_path(self):
        home = _runnable_home()
        root = hbt._project(home=str(home))
        resolved = _resolve(root)
        self.assertEqual(resolved["code"], er.DIRECT_LAUNCHER, resolved)
        self.assertEqual(resolved["argv_prefix"], [str((home / "bin" / LAUNCHER).resolve())])
        self.assertIn("no_canonical_path_launcher", resolved["degraded"])
        self.assertTrue(_status(resolved["argv_prefix"], root)["ok"])

    def test_case05_direct_engine_only(self):
        home = _runnable_home(launcher=False)
        root = hbt._project(home=str(home))
        resolved = _resolve(root)
        self.assertEqual(resolved["code"], er.DIRECT_ENGINE, resolved)
        self.assertEqual(
            resolved["argv_prefix"],
            [str(Path(sys.executable)), str((home / "tools" / "saipen.py").resolve())],
        )
        self.assertTrue(_status(resolved["argv_prefix"], root)["ok"])

    def test_case06_stale_persisted_home_is_rebound_before_the_command(self):
        home = _runnable_home()
        root = hbt._project(home=hbt.DEAD_HOME)
        resolved = _resolve(root, SAIPEN_SKILL_ROOT=str(home))
        self.assertTrue(resolved["ok"], resolved)
        self.assertIn("stale_runtime_binding", resolved["degraded"])
        self.assertEqual(resolved["next_action"], "saipen rebind-home --auto")
        proc = _entry_cli(["--", "status", "--json"], root, _cold_env(SAIPEN_SKILL_ROOT=str(home)))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        summary = json.loads(proc.stderr.split("SAIPEN_ENTRY ", 1)[1].splitlines()[0])
        self.assertEqual(summary["code"], er.RUNTIME_REBOUND, proc.stderr)
        rebound = _home_of(root)
        self.assertNotEqual(rebound, hbt.DEAD_HOME)
        self.assertIsNone(persisted_home_error(rebound))
        self.assertNotIn("stale_runtime_binding", summary["degraded"])

    def test_case07_unsupported_host_discovers_but_never_mutates(self):
        home = _runnable_home()
        root = hbt._project(home=str(home))
        read = _resolve(root, host="not-a-registered-host", command=["status", "--json"])
        self.assertFalse(read["ok"])
        self.assertEqual(read["code"], er.HOST_UNSUPPORTED)
        self.assertIsNotNone(read["runtime_identity"])
        self.assertTrue(read["argv_prefix"])
        self.assertFalse(read["host_admission"]["mutation_admitted"])
        self.assertTrue(read["command_allowed"])
        write = _resolve(
            root, host="not-a-registered-host", command=["checkpoint", "RUN", "T-1", "x"]
        )
        self.assertEqual(write["code"], er.HOST_UNSUPPORTED)
        self.assertFalse(write["command_allowed"])

    def test_case08_project_unbound_selects_no_repository(self):
        loose = hbt._temp() / "not-managed"
        loose.mkdir()
        for resolved in (
            _resolve(loose),
            er.resolve_entry(start=loose, env={"PATH": ""}, honor_environment=False),
        ):
            self.assertFalse(resolved["ok"])
            self.assertEqual(resolved["code"], er.PROJECT_UNBOUND, resolved)
            self.assertIsNone(resolved["project_root"])
            self.assertIsNone(resolved["argv_prefix"])

    def test_case09_no_runtime_is_one_bounded_structured_answer(self):
        root = hbt._project(home=hbt.DEAD_HOME)

        def no_scan(*_args, **_kwargs):
            raise AssertionError("entry resolution must never scan a directory tree")

        with patch.object(os, "walk", no_scan), patch.object(glob, "glob", no_scan), patch.object(
            Path, "rglob", no_scan
        ), patch.object(Path, "glob", no_scan):
            resolved = er.resolve_entry(
                root, env={"PATH": ""}, honor_environment=False, engine_root=hbt._not_an_install()
            )
        self.assertFalse(resolved["ok"])
        self.assertEqual(resolved["code"], er.RUNTIME_UNAVAILABLE, resolved)
        self.assertIsNone(resolved["argv_prefix"])
        sources = {row.get("source") for row in resolved["attempted"]}
        self.assertLessEqual(sources, {"state-saipen-home", "executing-engine", "path"})
        self.assertIn("stale_runtime_binding", {d["code"] for d in resolved["diagnostics"]})

    def test_case10_scheduled_cold_start_uses_only_the_published_contract(self):
        # The published home carries BOOT/STYLE/EXECUTION and the entry
        # contract; a cold host follows the contract, never a guess.
        home = _runnable_home(name="scheduled-source")
        for name in ("BOOT.md", "STYLE.md", "EXECUTION.md"):
            shutil.copyfile(REPO / "saipen" / name, home / name)
        shutil.copyfile(REPO / "saipen" / er.ENTRY_CONTRACT, home / er.ENTRY_CONTRACT)
        root = hbt._project(home=str(home))
        contract = json.loads((home / er.ENTRY_CONTRACT).read_text(encoding="utf-8"))
        self.assertFalse(contract["allow_module_invocation"])
        surface = contract["launcher_surface"]["windows" if os.name == "nt" else "posix"]
        launcher = home / surface
        env = _cold_env()
        self.assertIsNone(shutil.which("saipen", path=env["PATH"]))
        entry = _run([str(launcher), *contract["entry_resolution"].split()], root, env)
        self.assertEqual(entry.returncode, 0, entry.stdout + entry.stderr)
        answer = json.loads(entry.stdout)
        self.assertEqual(answer["code"], er.DIRECT_LAUNCHER, answer)
        status = _status(answer["argv_prefix"], root, env)
        self.assertTrue(status["ok"])
        self.assertEqual(Path(status["cold_route"]["project_root"]), root.resolve())

    def test_case11_every_transport_answers_the_same_status(self):
        home = _runnable_home()
        root = hbt._project(home=str(home))
        resolutions = [_resolve(root, path=str(home / "bin")), _resolve(root)]
        (home / "bin").rename(home / "bin-off")
        resolutions.append(_resolve(root))
        self.assertEqual(
            [r["code"] for r in resolutions],
            [er.PATH_LAUNCHER, er.DIRECT_LAUNCHER, er.DIRECT_ENGINE],
        )
        (home / "bin-off").rename(home / "bin")
        keys = (
            "ok",
            "phase",
            "task",
            "next_action",
            "computed_next_action",
            "blocker",
            "project_identity",
            "log_tail_event",
            "cold_route",
        )
        answers = [{k: _status(r["argv_prefix"], root).get(k) for k in keys} for r in resolutions]
        self.assertEqual(answers[0], answers[1])
        self.assertEqual(answers[0], answers[2])
        # Continue is the other turn-entry question; it answers through the runner too.
        proc = _entry_cli(["--", "continue", "--json", "--dry-run"], root)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(json.loads(proc.stdout)["ok"])

    def test_case12_unadmitted_host_cannot_mutate_through_any_transport(self):
        home = _runnable_home()
        root = hbt._project(home=str(home))
        log = root / ".saipen" / "LOG.md"
        before = log.read_bytes()
        proc = _entry_cli(
            [
                "--json",
                "--host",
                "not-a-registered-host",
                "--",
                "checkpoint",
                "RUN",
                "T-1",
                "x",
                "--json",
            ],
            root,
        )
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        refused = json.loads(proc.stdout)
        self.assertEqual(refused["code"], er.HOST_UNSUPPORTED)
        self.assertEqual(refused["command_effect"], "EXECUTION")
        self.assertEqual(log.read_bytes(), before)
        read = _entry_cli(["--host", "not-a-registered-host", "--", "status", "--json"], root)
        self.assertEqual(read.returncode, 0, read.stdout + read.stderr)
        self.assertEqual(log.read_bytes(), before)

    def test_runner_never_lets_a_shell_reparse_command_text(self):
        # A .cmd launcher hands %* to cmd.exe, which re-parses it: a token
        # holding a quote and `&` ran an arbitrary command (REVIEW P1).
        home = _runnable_home()
        root = hbt._project(home=str(home))
        hostile = 'x" & echo pwned> pwned.txt & "y'
        proc = _entry_cli(["--", "search", "--hex", hostile, "--json"], root)
        self.assertFalse((root / "pwned.txt").exists(), proc.stdout + proc.stderr)
        refused = json.loads(proc.stdout)
        self.assertEqual(refused["code"], "VALIDATION_FAILED", refused)
        resolved = _resolve(root)
        self.assertEqual(resolved["code"], er.DIRECT_LAUNCHER)
        self.assertEqual(
            resolved["exec_prefix"],
            [str(Path(sys.executable)), str((home / "tools" / "saipen.py").resolve())],
        )

    def test_runner_arguments_stay_argv_data_for_every_shell_metacharacter(self):
        # The START receipt keeps the task text verbatim, so it echoes exactly
        # what argv reached the engine; a shell in between would split, run or
        # redirect part of it and leave files in the project root.
        hostile = (
            'a" & echo pwned> amp.txt & "b',
            'a" | echo pwned> pipe.txt | "b',
            'a" > redir.txt & "b',
            'a" < nul & echo pwned> lt.txt & "b',
            'a ^" ^& echo pwned> caret.txt ^& "b',
            'plain & | > < ^ % "quoted" end',
        )
        for token in hostile:
            with self.subTest(token=token):
                root = hbt._project(home=str(_runnable_home()))
                before = sorted(p.name for p in root.iterdir())
                proc = _entry_cli(
                    ["--", "start", token, "--json"], root, _cold_env(**operator_request_env(token))
                )
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                started = json.loads(proc.stdout)
                self.assertEqual(started["code"], "STARTED", started)
                receipt = next((root / ".saipen" / "intake").rglob(started["receipt"] + ".md"))
                self.assertIn(token, receipt.read_text(encoding="utf-8"))
                # START writes the project's .gitignore and, since T-1508, the
                # byte-bound .gitattributes rules; nothing else may appear.
                created = {p.name for p in root.iterdir()} - set(before)
                self.assertLessEqual(created, {".gitignore", ".gitattributes"}, created)

    def test_host_actions_start_then_status_through_the_runner(self):
        # Basic host-action regression (SRC-114 O): Start and Status still
        # work when every call goes through the resolved transport.
        home = _runnable_home()
        root = hbt._project(home=str(home))
        started = _entry_cli(
            ["--", "start", "runner smoke task", "--json"],
            root,
            _cold_env(**operator_request_env("runner smoke task")),
        )
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        started = json.loads(started.stdout)
        self.assertEqual(started["code"], "STARTED", started)
        status = _entry_cli(["--", "status", "--json"], root)
        self.assertEqual(json.loads(status.stdout)["task"], started["ticket"])


class EntryRunnerRebindTests(unittest.TestCase):
    """The runner's two rebind outcomes that a live engine rarely produces."""

    def _run_main(self, rebind_payload: dict) -> tuple[int, list, str]:
        import contextlib
        import io

        import saipen as cli

        home = _runnable_home()
        root = hbt._project(home=hbt.DEAD_HOME)
        calls: list = []

        def fake_run(argv, *args, **kwargs):
            calls.append(list(argv))
            if "rebind-home" in argv:
                return subprocess.CompletedProcess(argv, 1, json.dumps(rebind_payload), "")
            return subprocess.CompletedProcess(argv, 0, "", "")

        out = io.StringIO()
        with patch.dict(
            os.environ, _cold_env(SAIPEN_SKILL_ROOT=str(home)), clear=True
        ), patch.object(subprocess, "run", fake_run), contextlib.redirect_stdout(
            out
        ), contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(
                ["host", "entry", "--json", "--project-root", str(root), "--", "status", "--json"]
            )
        return code, calls, out.getvalue()

    def test_rebind_needing_a_named_home_stops_as_human_required(self):
        code, calls, out = self._run_main({"ok": False, "code": "HOME_REQUIRED", "detail": "x"})
        self.assertEqual(code, 2)
        payload = json.loads(out)
        self.assertEqual(payload["code"], er.HUMAN_REQUIRED)
        self.assertIn("rebind-home", payload["operator_action"])
        self.assertEqual(len(calls), 1, calls)  # the command itself never ran

    def test_other_rebind_refusal_fails_open_through_the_proven_transport(self):
        code, calls, _out = self._run_main({"ok": False, "code": "WRITER_BUSY"})
        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 2, calls)
        self.assertEqual(calls[1][-2:], ["status", "--json"])


class LauncherProvenanceTests(unittest.TestCase):
    def test_rendered_launchers_prove_only_for_their_own_engine(self):
        home = _runnable_home()
        engine = home / "tools" / "saipen.py"
        for name in ("saipen", "saipen.cmd"):
            with self.subTest(launcher=name):
                self.assertTrue(er.prove_launcher(home / "bin" / name, engine)["ok"])
                other = er.prove_launcher(home / "bin" / name, TOOLS / "saipen.py")
                self.assertFalse(other["ok"])
                self.assertIn("provenance mismatch", other["why"])

    def test_missing_interpreter_is_not_a_transport(self):
        home = _runnable_home(launcher=False)
        engine = home / "tools" / "saipen.py"
        cli_launcher.write_launchers(str(home / "no-python.exe"), str(engine), home / "bin")
        proof = er.prove_launcher(home / "bin" / LAUNCHER, engine)
        self.assertFalse(proof["ok"])
        self.assertIn("interpreter does not exist", proof["why"])

    def test_wrapped_command_carries_its_own_effect_class(self):
        self.assertEqual(classify_invocation("host", ["entry", "--json"]), "DIAGNOSTIC")
        self.assertEqual(classify_invocation("host", ["entry", "--", "status"]), "DIAGNOSTIC")
        self.assertEqual(
            classify_invocation("host", ["entry", "--", "ticket", "done", "T-1"]), "EXECUTION"
        )


class ColdStartContractTests(unittest.TestCase):
    def test_boot_and_execution_name_the_resolved_transport(self):
        boot = (REPO / "saipen" / "BOOT.md").read_text(encoding="utf-8")
        execution = (REPO / "saipen" / "EXECUTION.md").read_text(encoding="utf-8")
        self.assertIn("Transport is resolved, never guessed", boot)
        for token in ("bin/saipen.cmd", "bin/saipen", "host entry --json", "SAIPEN_ENTRY.json"):
            self.assertIn(token, boot)
        self.assertIn("saipen host entry", execution)
        flat_boot, flat_exec = " ".join(boot.split()), " ".join(execution.split())
        self.assertIn(
            "`python -m saipen`, `where`/`which saipen` and a hand-built interpreter path "
            "are never transports",
            flat_boot,
        )
        self.assertIn("inventing another invocation is not a recovery", flat_exec)
        # Every mention of module invocation is that prohibition, never an instruction.
        self.assertEqual(flat_boot.count("python -m saipen"), 1)
        self.assertEqual(flat_exec.count("python -m saipen"), 1)

    def test_entry_contract_is_shipped_and_describes_real_surfaces(self):
        contract = json.loads((REPO / "saipen" / er.ENTRY_CONTRACT).read_text(encoding="utf-8"))
        self.assertEqual(contract["schema"], 1)
        self.assertFalse(contract["allow_module_invocation"])
        self.assertTrue((REPO / contract["engine_surface"]).is_file())
        for surface in contract["launcher_surface"].values():
            self.assertFalse(Path(surface).is_absolute())
        manifest = json.loads((REPO / "saipen" / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertIn("saipen/" + er.ENTRY_CONTRACT, {row["src"] for row in manifest["files"]})


if __name__ == "__main__":
    unittest.main()

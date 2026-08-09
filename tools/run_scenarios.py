#!/usr/bin/env python
"""Run every executable conformance fixture and compare to its declaration.

Stdlib only. Run from the SAIPEN home:

    python tools/run_scenarios.py

`tests/scenarios/` holds two kinds of fixture. Behavioral ones are README-only
-- the assertion is about agent decision-making, which no script can judge --
and are skipped here. Structural ones ship a real `.saipen/` and declare the
outcome they expect on a line of their own README:

    expect: pass      the state is valid; tools/validate.py must exit 0
    expect: fail      the state carries the defect the fixture exists to
                      demonstrate; validate.py must exit non-zero

A fixture with a `.saipen/` and no `expect:` line is itself an error: an
un-declared fixture cannot be checked, and silently skipping it is how this
whole directory sat unexecuted for months (CONFORMANCE.md's "honest status"
note, v7.75.0).

After the state fixtures, both bootstrap injectors run against isolated homes
seeded with stale managed directories. The probe checks installed artifacts,
not script tokens, and carries a broken-layout red-control.

Project-root probes also execute the canonical validator from a correct Git
root, nested Git and non-Git directories, a foreign repository, an explicit
root, and a linked worktree. They assert no fallback `.saipen/` is created.

The last-event probe upgrades one legacy fixture through schema v2, advances
its LOG, and executes the validator at every boundary. It proves migration,
missing, exact, stale, recovered, and corrupt marker behavior.

Exit code is non-zero if any fixture's real outcome differs from its
declaration, so CI fails on it like any other gate.
"""

import contextlib
import functools
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import zipfile
from pathlib import Path
from unittest import mock

import freshness
from freshness import (FreshnessError, SourceIdentity,
                       compute_generic_role_revision, compute_role_revision,
                       compute_source_identity)
from sub_clean import sub_clean_blockers
from improve import (append_run, derive_status, register_cycle, register_seat,
                     resolve_report_path, validate_report, write_sweep_entry)
from userperson import (merge_profile, onboarding_questions, parse_profile,
                        project_profile, remove_preference, render_profile,
                        validate_profile)
from saipen_engine.board import parse_board
from saipen_engine.journal import Journal, recover, run_mutation
from saipen_engine.lock import WriterLock
from saipen_engine.log import parse_log_line
from saipen_engine.snapshot import ProjectSnapshot
from saipen_engine.state import parse_frontmatter

HOME = Path(__file__).resolve().parent.parent
VALIDATOR = HOME / "tools" / "validate.py"
SCENARIOS = HOME / "tests" / "scenarios"


@functools.lru_cache(maxsize=1)
def symlinks_available() -> bool:
    """Can this host create a symlink at all?

    Measured, never assumed from `os.name`: Windows creates symlinks fine with
    Developer Mode or SeCreateSymbolicLinkPrivilege and refuses without either,
    and restricted containers refuse on any platform. Unguarded `os.symlink`
    calls do not degrade to a SKIP -- they raise OSError out of the probe
    function and take the whole scenario suite down with a traceback, which is
    the worst of the three outcomes because it hides every check after it
    (T-572). Lazy: the filesystem operation runs on first use, never merely
    from importing this module.
    """
    with tempfile.TemporaryDirectory(prefix="saipen-symlink-probe-") as raw:
        base = Path(raw)
        (base / "target").write_text("t\n", encoding="utf-8")
        try:
            os.symlink("target", base / "link")
        except (OSError, NotImplementedError, AttributeError):
            return False
        return (base / "link").is_symlink()


@functools.lru_cache(maxsize=1)
def junctions_available() -> bool:
    """Can this host create a directory junction (reparse point) at all?

    Junctions are not symlinks: `Path.is_symlink()` is False for one, which is
    exactly why detection must read the reparse-point attribute (T-572).
    `mklink /J` needs no privilege and works on every Windows host; anything
    else is not a junction-capable host and SKIPs out loud.
    """
    if os.name != "nt":
        return False
    with tempfile.TemporaryDirectory(prefix="saipen-junction-probe-") as raw:
        base = Path(raw)
        real = base / "real"
        real.mkdir()
        link = base / "junction"
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", os.fspath(link), os.fspath(real)],
            capture_output=True, text=True, errors="replace")
        if result.returncode != 0 or not link.exists():
            return False
        info = link.lstat()
        return bool(getattr(info, "st_file_attributes", 0) & 0x400)


EXPECT_RE = re.compile(r"^expect:\s*(pass|fail)\s*$", re.MULTILINE)

# A fixture that declares `expect: fail` and then fails for some OTHER reason
# asserts nothing at all, and says PASS while doing it. Three did exactly that:
# dependency-cycle, dangling-needs-reference and read-only-restriction each
# carried a control character where `saipen_version: 7` belonged, so every run
# died on unparseable frontmatter long before reaching the cycle, the dangling
# reference or the mode ban they exist to prove. The suite was green throughout.
#
# So a fail-fixture MAY pin the reason with a second line:
#     expect_fail_contains: <substring of the FAIL message>
# A fail-fixture MUST pin its reason. Unpinned, it asserts only that
# something, somewhere, went wrong -- which is the failure mode this whole
# harness exists to detect one layer down: red is not evidence unless it is red
# for the reason the fixture was built to prove. Reproduced twice in one
# session: three `audit_checks` controls went red on a mangled ticket line
# rather than on the cap they name, and a new fixture went red on an unrelated
# `[phase-ticket-ref]` FAIL leaking in from outside its own tree. Every
# fail-fixture in this repository already carries the pin, so this is a rot
# guard rather than a migration.
REASON_RE = re.compile(r"^expect_fail_contains:\s*(.+?)\s*$", re.MULTILINE)
WARN_RE = re.compile(r"^expect_warn_contains:\s*(.+?)\s*$", re.MULTILINE)


def find_bash() -> str | None:
    """Return a real bash, excluding Windows' WSL launcher stub."""
    for candidate in (r"C:\Program Files\Git\usr\bin\bash.exe",
                      r"C:\Program Files\Git\bin\bash.exe",
                      shutil.which("bash")):
        if (candidate and os.path.isfile(candidate)
                and "system32" not in candidate.lower()):
            return candidate
    return None


def find_dash() -> str | None:
    """Return dash for proving the generated POSIX hook is not Bash itself."""
    for candidate in (r"C:\Program Files\Git\usr\bin\dash.exe",
                      shutil.which("dash")):
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def bash_env(bash: str, home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    # The injector probe runs uninstall.sh against a sandbox HOME, but the
    # scheduled task is machine-global -- the probe must not delete a real
    # scheduler entry (T-531/T-534).
    env["SAIPEN_UNINSTALL_SKIP_TASK"] = "1"
    if os.name == "nt":
        bindir = Path(bash).resolve().parent
        for tools_dir in (bindir, bindir.parent / "usr" / "bin"):
            if all((tools_dir / f"{name}.exe").is_file()
                   for name in ("cp", "grep", "sed")):
                env["PATH"] = str(tools_dir) + os.pathsep + env.get("PATH", "")
                break
    return env


def find_powershell() -> str | None:
    for name in ("pwsh", "powershell", "powershell.exe"):
        found = shutil.which(name)
        if found:
            return found
    return None


def run_ci_status_probes() -> tuple[list[str], int]:
    """T-428: the four ways the CI-status tool could fail quietly.

    All four run OFFLINE. A probe that needs GitHub is a probe that skips on
    every machine without a network and reports "0 failures" while checking
    nothing -- the vacuous-gate shape this repository keeps finding in itself.
    The API is reached exactly once here, through a stub that raises.
    """
    failures = []
    spec = importlib.util.spec_from_file_location(
        "saipen_ci_status", HOME / "tools" / "ci_status.py")
    ci = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ci)

    # 1. An in-progress run must not hide a red base. The URL is the whole
    #    mechanism: without status=completed the newest run wins even when it
    #    is still queued, classify() says "in progress" and exits 0, and the
    #    RED run underneath is never looked at -- which is exactly the moment
    #    the tool exists for, a red base being re-run while someone commits.
    url = ci.runs_url("owner/repo", "main", "validate.yml")
    if "status=completed" not in url:
        failures.append(f"ci_status branch query does not ask for completed "
                        f"runs: {url}")
    elif ci.classify({"status": "in_progress", "run_number": 1})[0] != 0 \
            or ci.classify({"status": "completed", "conclusion": "failure",
                            "run_number": 1})[0] != 1:
        failures.append("ci_status classify() does not separate an "
                        "in-progress run from a completed failure")
    else:
        print("PASS: ci_status queries completed runs only; in-progress is "
              "not a verdict and a completed failure is")

    # 2. An unreachable API must never block a commit, and must say nothing
    #    in hook mode -- a per-commit "cannot reach GitHub" line is noise the
    #    user learns to scroll past, which is how a real red line gets missed.
    def _boom(_url):
        raise urllib.error.URLError("probe: network down")

    ci.fetch_json = _boom
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = ci.main_argv(["--hook", "--repo", "owner/repo", "--branch", "main"])
    if rc != 0 or buf.getvalue().strip():
        failures.append(f"ci_status --hook did not fail open on an "
                        f"unreachable API: rc={rc} out={buf.getvalue()[:120]!r}")
    else:
        print("PASS: ci_status --hook fails open and stays silent when the "
              "API is unreachable")

    # 3. The cache path must come from git, not the literal `.git/`. In a
    #    linked worktree `.git` is a FILE, so the literal path cannot be
    #    written: the hook would silently stop caching and spend one of the
    #    60 unauthenticated requests per hour on every commit made there.
    with tempfile.TemporaryDirectory(prefix="saipen-ci-") as raw:
        root = Path(raw)
        main_repo = root / "main"
        main_repo.mkdir()
        for args in (["init", "-q"], ["config", "user.email", "p@probe"],
                     ["config", "user.name", "probe"],
                     ["commit", "-q", "--allow-empty", "-m", "base"],
                     ["worktree", "add", "-q", "-b", "probe",
                      str(root / "linked")]):
            subprocess.run(["git", *args], cwd=main_repo, check=False,
                           capture_output=True, text=True)
        linked = root / "linked"
        if not linked.is_dir():
            print("SKIP: ci_status worktree cache -- git worktree unavailable")
        else:
            cwd = os.getcwd()
            try:
                os.chdir(linked)
                path = ci.cache_path()
            finally:
                os.chdir(cwd)
            if path is None or not path.parent.is_dir():
                failures.append(f"ci_status cache_path() does not resolve to "
                                f"a real directory in a linked worktree: "
                                f"{path}")
            elif path.parent == linked / ".git":
                failures.append("ci_status cache_path() returned the literal "
                                ".git/ of a linked worktree, where .git is a "
                                "file -- the write can only fail")
            else:
                print("PASS: ci_status cache path resolves through git and is "
                      "writable inside a linked worktree")

    return failures, 3


def run_hook_probes() -> tuple[list[str], int, int]:
    failures = []
    bash, dash = find_bash(), find_dash()
    if not bash or not dash:
        print("SKIP: installed-hook Bash resolution -- bash or dash unavailable")
        return failures, 0, 1

    with tempfile.TemporaryDirectory(prefix="saipen-hook-") as raw:
        root = Path(raw)
        fake_home = root / "saipen-home"
        (fake_home / "tools").mkdir(parents=True)
        (fake_home / "tests").mkdir()
        shutil.copy2(HOME / "tools" / "install_hook.py",
                     fake_home / "tools" / "install_hook.py")
        (fake_home / "tools" / "validate.py").write_text(
            "# forces the hook's no-Python fallback branch\n", encoding="utf-8")
        (fake_home / "tests" / "validate.sh").write_text(
            "#!/bin/bash\nread -r value <<< 'bash-floor-ok'\n"
            "[ \"$value\" = bash-floor-ok ] || exit 8\necho FLOOR_OK\n",
            encoding="utf-8", newline="\n")

        project = root / "project"
        (project / ".git" / "hooks").mkdir(parents=True)
        (project / ".saipen").mkdir()
        install = subprocess.run(
            [sys.executable, str(fake_home / "tools" / "install_hook.py")],
            cwd=project, capture_output=True, text=True, errors="replace")
        if install.returncode:
            return [f"install-hook probe setup failed: {install.stderr.strip()[:160]}"], 1, 0
        hook = project / ".git" / "hooks" / "pre-commit"

        controlled = root / "bin"
        controlled.mkdir()
        if os.name == "nt":
            bash_path = str(Path(bash).resolve().parent)
        elif symlinks_available():
            (controlled / "bash").symlink_to(Path(bash).resolve())
            bash_path = str(controlled)
        else:
            bash_path = str(Path(bash).resolve().parent)
        env = os.environ.copy()
        env["PATH"] = bash_path
        working = subprocess.run(
            [dash, str(hook)], cwd=project, env=env,
            capture_output=True, text=True, errors="replace")
        working_output = working.stdout + working.stderr
        if working.returncode or "FLOOR_OK" not in working_output:
            failures.append(
                f"installed-hook dash control did not execute Bash floor: "
                f"rc={working.returncode} {working_output.strip()[-160:]}")
        else:
            print("PASS: installed hook under dash -- Bash floor executed")

        no_bash_env = os.environ.copy()
        no_bash_env["PATH"] = ""
        missing = subprocess.run(
            [dash, str(hook)], cwd=project, env=no_bash_env,
            capture_output=True, text=True, errors="replace")
        missing_output = missing.stdout + missing.stderr
        expected = "saipen: validation failed -- Bash is required to run"
        if missing.returncode == 0 or expected not in missing_output:
            failures.append(
                f"installed-hook no-Bash control was not focused: "
                f"rc={missing.returncode} {missing_output.strip()[-160:]}")
        elif "FLOOR_OK" in missing_output:
            failures.append("installed-hook no-Bash control printed floor success")
        else:
            print("PASS: installed hook without Bash -- focused nonzero failure")

        # T-428, the two halves of the CI-status line the hook grew in
        # generation 4. The fake home above deliberately has no ci_status.py,
        # which is every clone that predates it and every consuming project
        # that never installed it: the `-f` guard must skip the call silently
        # rather than let a missing tool leak an error into every commit.
        # The two controls above run on a PATH holding only bash, which also
        # hides `python` -- and the hook guards its CI line on `command -v
        # python`. Probing the CI line on that PATH would assert nothing
        # while printing PASS, the vacuous-control shape this file exists to
        # prevent, so both CI probes get python back on the PATH.
        python_exe = shutil.which("python")
        ci_env = os.environ.copy()
        ci_env["PATH"] = (bash_path + os.pathsep
                          + str(Path(python_exe).resolve().parent)
                          if python_exe else bash_path)
        no_tool = subprocess.run(
            [dash, str(hook)], cwd=project, env=ci_env,
            capture_output=True, text=True, errors="replace")
        no_tool_output = no_tool.stdout + no_tool.stderr
        if not python_exe:
            print("SKIP: installed-hook CI line -- no python on PATH")
            return failures, 2, 1
        # No FLOOR_OK expected here: with python back on the PATH the hook
        # takes its normal validate.py branch and never reaches the Bash
        # fallback the two controls above were built to exercise.
        if no_tool.returncode:
            failures.append(
                f"installed hook broke with no ci_status.py present: "
                f"rc={no_tool.returncode} {no_tool_output.strip()[-160:]}")
        elif "RED" in no_tool_output or "ci_status" in no_tool_output:
            failures.append("installed hook without ci_status.py leaked CI "
                            "output -- the -f guard did not hold")
        else:
            print("PASS: installed hook with no ci_status.py present -- "
                  "skipped silently, commit path unaffected")

        # And the other half: with the tool present and RED, the hook must
        # still exit 0. Warn-only is not a preference here -- a red CI that
        # blocks commits blocks the commit that fixes it. Docstring, hook
        # comment and behaviour now say the same thing.
        (fake_home / "tools" / "ci_status.py").write_text(
            "import sys\n"
            "print('run #1 failure (deadbee..) -- RED -- probe')\n"
            "sys.exit(1)\n", encoding="utf-8", newline="\n")
        red = subprocess.run(
            [dash, str(hook)], cwd=project, env=ci_env,
            capture_output=True, text=True, errors="replace")
        red_output = red.stdout + red.stderr
        if red.returncode != 0:
            failures.append(
                f"installed hook blocked a commit on a RED CI status: "
                f"rc={red.returncode} {red_output.strip()[-160:]}")
        elif "RED" not in red_output:
            failures.append("installed hook swallowed the RED CI line -- a "
                            "warning nobody sees is not a warning")
        else:
            print("PASS: installed hook reports a RED CI status and still "
                  "exits 0 -- warn-only, as the docs now say")

        # T-527, the two halves of the NOT-VALIDATED diagnostic. It exists to
        # catch a commit that LOOKS validated and was not, so it is worth
        # nothing unless it is silent on the healthy path: generation 6 fired
        # it on every successful commit for want of a success exit, and a
        # warning that always fires is one nobody reads on the day it is true.
        # The healthy run is `no_tool` above -- stub validate.py rc 0 and the
        # Bash floor both ran, which is exactly the case the line must not
        # describe.
        not_validated = "saipen: NOT VALIDATED"
        if not_validated in no_tool_output:
            failures.append(
                "installed hook claimed NOT VALIDATED after a validator ran "
                "and passed -- the success exit is missing or unreachable")
        else:
            print("PASS: installed hook is silent on the healthy path -- no "
                  "false NOT-VALIDATED line after a passing validator")

        # The other half, and the reason the success exit is gated on
        # `_validate_rc` being SET rather than added unconditionally: with no
        # validator reachable at all the line must still appear, and the commit
        # must still go through. Removing both entry points leaves the hook's
        # `-f` guards unsatisfied and its saipen_home fallback with nothing to
        # recover, which is the broken install this diagnostic was built for.
        (fake_home / "tools" / "validate.py").unlink()
        (fake_home / "tests" / "validate.sh").unlink()
        broken = subprocess.run(
            [dash, str(hook)], cwd=project, env=ci_env,
            capture_output=True, text=True, errors="replace")
        broken_output = broken.stdout + broken.stderr
        if broken.returncode != 0:
            failures.append(
                f"installed hook blocked a commit on a broken install: "
                f"rc={broken.returncode} {broken_output.strip()[-160:]}")
        elif not_validated not in broken_output:
            failures.append(
                "installed hook went quiet with no validator reachable -- an "
                "unvalidated commit that looks validated is the silent PASS")
        else:
            print("PASS: installed hook with no validator reachable -- says "
                  "NOT VALIDATED out loud and still exits 0")
    return failures, 6, 0


def run_precommit_purity_probe() -> tuple[list[str], int, int]:
    """The pre-commit gate MUST be read-only: `git status --porcelain=v1 -uall`
    byte-identical before and after the hook runs (goal blind spot 10, T-518).
    The gen-5 hook captures status before validation and FAILs on any change;
    a stub validator that writes a file must trip that guard."""
    failures = []
    bash, dash = find_bash(), find_dash()
    if not bash or not dash:
        print("SKIP: pre-commit purity probe -- bash or dash unavailable")
        return failures, 0, 1

    env = bash_env(bash, Path("."))

    def build(validator_body: str):
        with tempfile.TemporaryDirectory(prefix="saipen-purity-") as raw:
            root = Path(raw)
            fake_home = root / "saipen-home"
            (fake_home / "tools").mkdir(parents=True)
            (fake_home / "tests").mkdir()
            shutil.copy2(HOME / "tools" / "install_hook.py",
                         fake_home / "tools" / "install_hook.py")
            (fake_home / "tools" / "validate.py").write_text(
                validator_body, encoding="utf-8", newline="\n")
            (fake_home / "tests" / "validate.sh").write_text(
                "#!/bin/bash\necho FLOOR_OK\n", encoding="utf-8", newline="\n")
            project = root / "project"
            (project / ".git" / "hooks").mkdir(parents=True)
            (project / ".saipen").mkdir()
            subprocess.run(["git", "init", "-q"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.name", "purity"],
                           cwd=project, check=True)
            subprocess.run(["git", "config", "user.email", "p@example.invalid"],
                           cwd=project, check=True)
            install = subprocess.run(
                [sys.executable, str(fake_home / "tools" / "install_hook.py")],
                cwd=project, capture_output=True, text=True, errors="replace")
            if install.returncode:
                return (root, f"purity probe install failed: "
                        f"{install.stderr.strip()[:160]}")
            hook = project / ".git" / "hooks" / "pre-commit"

            before = subprocess.run(
                ["git", "status", "--porcelain=v1", "-uall"], cwd=project,
                capture_output=True, text=True, errors="replace").stdout
            run = subprocess.run(
                [dash, str(hook)], cwd=project, env=env,
                capture_output=True, text=True, errors="replace")
            after = subprocess.run(
                ["git", "status", "--porcelain=v1", "-uall"], cwd=project,
                capture_output=True, text=True, errors="replace").stdout
            return (root, None, run, before, after)

    # Case 1: read-only validator -> hook passes, tree byte-identical.
    _, err, run, before, after = build(
        "import sys\nprint('VALIDATOR-OK')\nsys.exit(0)\n")
    if err:
        failures.append(err)
    elif run.returncode != 0:
        failures.append(f"purity probe: read-only hook failed rc={run.returncode} "
                        f"{run.stderr.strip()[-160:]}")
    elif after != before:
        failures.append("purity probe: git status CHANGED across a read-only "
                        "hook -- validation is not read-only")
    else:
        print("PASS: pre-commit gate leaves git status byte-identical "
              "(read-only validation)")

    # Case 2: mutating validator -> gen-5 guard must FAIL the hook.
    _, err, run, before, after = build(
        "from pathlib import Path\n"
        "Path('tampered.txt').write_text('mutated', encoding='utf-8')\n"
        "import sys\nprint('VALIDATOR-MUTATED')\nsys.exit(0)\n")
    if err:
        failures.append(err)
    elif run.returncode == 0:
        failures.append("purity probe: a validator that WROTE a file did NOT "
                        "trip the gen-5 mutation guard -- the guard is dead")
    else:
        print("PASS: gen-5 guard FAILs a validator that mutates the tree")
    return failures, 2, 0


RUNTIME_MANIFEST = json.loads(
    (HOME / "saipen" / "MANIFEST.json").read_text(encoding="utf-8"))


def install_relative_path(source: str) -> str:
    prefix = "saipen/"
    return source[len(prefix):] if source.startswith(prefix) else source


REQUIRED_INSTALL_FILES = tuple(
    install_relative_path(entry["src"])
    for entry in RUNTIME_MANIFEST["files"] if entry.get("required", False)
) + tuple(
    f"phases/{name}" for name in RUNTIME_MANIFEST["phase_docs"]["files"]
)
STALE_SENTINEL = "obsolete-from-prior-install.txt"
MANAGED_DIRS = tuple(RUNTIME_MANIFEST["managed_dirs"])


def seed_stale_install(destination: Path) -> None:
    for rel in MANAGED_DIRS:
        target = destination / rel
        target.mkdir(parents=True, exist_ok=True)
        (target / STALE_SENTINEL).write_text("stale\n", encoding="utf-8")


def installed_layout_problems(destination: Path) -> list[str]:
    problems = [f"missing {rel}" for rel in REQUIRED_INSTALL_FILES
                if not (destination / rel).is_file()]
    expected_version = (HOME / "VERSION").read_text(
        encoding="utf-8-sig").strip()
    installed_version = destination / "VERSION"
    if installed_version.is_file() and installed_version.read_text(
            encoding="utf-8-sig").strip() != expected_version:
        problems.append("installed VERSION differs from source")
    stale = [rel for rel in MANAGED_DIRS
             if (destination / rel / STALE_SENTINEL).exists()]
    if stale:
        problems.append(f"stale managed content survived in {stale}")
    installed_tools = destination / "tools"
    bytecode = sorted(
        str(path.relative_to(destination)) for path in installed_tools.rglob("*")
        if ((path.is_dir() and path.name == "__pycache__")
            or (path.is_file() and path.suffix in {".pyc", ".pyo"})))
    if bytecode:
        problems.append(f"installed tools contain generated Python bytecode: {bytecode}")
    for tree in RUNTIME_MANIFEST["copy_trees"]:
        source = HOME / tree["src"]
        installed = destination / tree["dst"]

        def copied_files(root: Path) -> dict[str, bytes]:
            return {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if (path.is_file() and "__pycache__" not in path.parts
                    and path.suffix not in {".pyc", ".pyo"})
            }

        source_files = copied_files(source)
        installed_files = copied_files(installed) if installed.is_dir() else {}
        if source_files != installed_files:
            problems.append(f"installed copy tree differs from source: {tree['src']}")
    return problems


ROUND_TRIP_BYTES = b"user-setting: keep  \r\n \t\r\n\r\n"
AIDER_ROUND_TRIP_BYTES = (
    b"\xef\xbb\xbfuser-setting: keep  \r\n"
    b"  - C:/user/decoy/saipen/STYLE.md\r\n\r\n"
)
AIDER_SUFFIX_BYTES = b"user-after-install: keep\r\n"


def run_injector_probe(label: str, command: list[str],
                       uninstall_command: list[str], env: dict[str, str],
                       home: Path) -> str | None:
    destination = home / ".claude" / "skills" / "saipen"
    (home / ".claude").mkdir(parents=True)
    config = home / ".claude" / "CLAUDE.md"
    config.write_bytes(ROUND_TRIP_BYTES)
    aider_config = home / ".aider.conf.yml"
    aider_config.write_bytes(AIDER_ROUND_TRIP_BYTES)
    shim_dir = home / "bin"
    shim_dir.mkdir()
    aider = shim_dir / "aider"
    aider.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8", newline="\n")
    aider.chmod(0o755)
    (shim_dir / "aider.cmd").write_text("@exit /b 0\r\n", encoding="utf-8")
    env = env.copy()
    env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
    seed_stale_install(destination)
    source_cache = HOME / "tools" / "__pycache__" / (
        f"saipen_distribution_probe_{os.getpid()}.pyc")
    source_loose_bytecode = HOME / "tools" / (
        f"saipen_distribution_probe_{os.getpid()}.pyc")
    source_cache.parent.mkdir(exist_ok=True)
    source_cache.write_bytes(b"not real bytecode; distribution sentinel\n")
    source_loose_bytecode.write_bytes(
        b"not real bytecode; loose distribution sentinel\n")
    try:
        result = subprocess.run(command, cwd=HOME, env=env, capture_output=True,
                                text=True, errors="replace")
    finally:
        source_cache.unlink(missing_ok=True)
        source_loose_bytecode.unlink(missing_ok=True)
    problems = installed_layout_problems(destination)
    if result.returncode:
        problems.insert(0, f"exited {result.returncode}")
    if not problems:
        project = home / "validator-project"
        shutil.copytree(
            SCENARIOS / "resume-after-crash" / ".saipen",
            project / ".saipen")
        installed_validator = destination / "tools" / "validate.py"
        validation = subprocess.run(
            [sys.executable, str(installed_validator), "--project-root",
             str(project)], cwd=home, env=env, capture_output=True, text=True,
            errors="replace")
        expected_root = f"Project root: {project.resolve()} (explicit)"
        if validation.returncode != 0 or expected_root not in validation.stdout:
            first = next(
                (line for line in (validation.stdout + validation.stderr).splitlines()
                 if line.startswith(("FAIL", "Traceback"))),
                "installed validator did not report a failure line")
            problems.append(
                f"installed validator explicit-root smoke exited "
                f"{validation.returncode}: {first[:120]}")
    if b"<!-- SAIPEN:BEGIN -->" not in config.read_bytes():
        problems.append("injector did not add its managed config block")
    aider_installed = aider_config.read_bytes()
    if b"BOOT.md" not in aider_installed or b"STYLE.md" not in aider_installed:
        problems.append("injector did not add its managed BOOT+STYLE Aider block")
    if not problems:
        marker = aider_installed.find(b"\n# saipen protocol auto-loaded\n")
        if marker < 0:
            problems.append("injector Aider block has no exact managed marker")
        else:
            # Editors routinely normalize a managed LF block to CRLF. Both
            # uninstallers must still remove it without touching user bytes.
            aider_installed = (aider_installed[:marker]
                               + aider_installed[marker:].replace(b"\n", b"\r\n"))
    if not problems:
        aider_config.write_bytes(aider_installed + AIDER_SUFFIX_BYTES)
        uninstall = subprocess.run(
            uninstall_command, cwd=HOME, env=env, capture_output=True,
            text=True, errors="replace")
        uninstall_output = uninstall.stdout + uninstall.stderr
        if uninstall.returncode:
            problems.append(f"uninstaller exited {uninstall.returncode}")
        elif "Done." not in uninstall_output:
            problems.append("uninstaller succeeded without completion text")
        if config.read_bytes() != ROUND_TRIP_BYTES:
            problems.append("install/uninstall changed surrounding user bytes")
        aider_after = aider_config.read_bytes()
        aider_expected = AIDER_ROUND_TRIP_BYTES + AIDER_SUFFIX_BYTES
        if aider_after != aider_expected:
            problems.append("Aider install/uninstall changed surrounding user bytes: "
                            f"expected {aider_expected!r}, got {aider_after!r}")
        if destination.exists():
            problems.append("uninstaller left the installed skill directory")
    if problems:
        detail = next((line for line in (result.stdout + result.stderr).splitlines()
                       if "FAILED" in line or "FATAL" in line), "no failure line")
        return f"{label}: {'; '.join(problems)} | {detail[:120]}"
    print(f"PASS: {label} -- manifest-complete install replaced stale dirs, "
          "ran validate.py, and uninstalled config + Aider byte-exact")
    return None


def failed_bootstrap_problem(label: str,
                             result: subprocess.CompletedProcess[str]) -> str | None:
    output = result.stdout + result.stderr
    if result.returncode == 0:
        return f"{label}: failure control exited 0"
    if "Done." in output:
        return f"{label}: failure control printed Done"
    if not any(word in output for word in ("FAILED", "not a file", "Is a directory")):
        return f"{label}: failure control had no focused diagnostic"
    print(f"PASS: {label} -- exits nonzero without completion text")
    return None


def run_atomic_copy_failure_probes(
        label: str, source: Path, home: Path, command: list[str],
        env: dict[str, str]) -> tuple[list[str], int]:
    """Late source/manifest failures must preserve the active installed copy."""
    problems: list[str] = []
    checked = 0
    destination = home / ".claude" / "skills" / "saipen"
    destination.mkdir(parents=True)
    sentinel = destination / "active-install.txt"
    sentinel_bytes = b"preserve active install\r\n"
    sentinel.write_bytes(sentinel_bytes)
    manifest_path = source / "saipen" / "MANIFEST.json"
    original = json.loads(manifest_path.read_text(encoding="utf-8"))

    def execute(case: str, manifest: dict, expected: str) -> None:
        nonlocal checked
        checked += 1
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        result = subprocess.run(command, cwd=source, env=env, capture_output=True,
                                text=True, errors="replace")
        leftovers = sorted(destination.parent.glob(".saipen.saipen-*"))
        output = result.stdout + result.stderr
        failures = []
        if result.returncode == 0:
            failures.append("exited 0")
        if not sentinel.is_file() or sentinel.read_bytes() != sentinel_bytes:
            failures.append("active install changed")
        if leftovers:
            failures.append(f"staging debris remains: {[p.name for p in leftovers]}")
        if expected not in output:
            failures.append(f"missing diagnostic {expected!r}")
        if failures:
            problems.append(f"{label} {case}: {'; '.join(failures)}")
        else:
            print(f"PASS: {label} {case} -- old install preserved, no staging debris")

    missing = json.loads(json.dumps(original))
    missing["files"].append({"src": "missing-runtime-file", "required": True})
    execute("late missing source", missing, "runtime manifest file missing")

    traversal = json.loads(json.dumps(original))
    traversal["copy_trees"][0]["src"] = "../outside"
    execute("manifest traversal", traversal, "unsafe runtime manifest")
    manifest_path.write_text(
        json.dumps(original, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    return problems, checked


def run_injector_probes() -> tuple[list[str], int, int]:
    probe_failures = []
    checked = skipped = 0
    bash = find_bash()
    powershell = find_powershell()

    if bash:
        def grep_failure_env(home: Path) -> dict[str, str]:
            shim_dir = home / "bin"
            shim_dir.mkdir()
            grep = shim_dir / "grep"
            grep.write_text("#!/usr/bin/env bash\nexit 2\n", encoding="utf-8",
                            newline="\n")
            grep.chmod(0o755)
            aider = shim_dir / "aider"
            aider.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8",
                             newline="\n")
            aider.chmod(0o755)
            env = bash_env(bash, home)
            env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
            return env

        with tempfile.TemporaryDirectory(prefix="saipen-inject-sh-") as raw:
            home = Path(raw)
            problem = run_injector_probe(
                "bootstrap/inject.sh", [bash, str(HOME / "bootstrap" / "inject.sh")],
                [bash, str(HOME / "bootstrap" / "uninstall.sh")],
                bash_env(bash, home), home)
            if problem:
                probe_failures.append(problem)

        with tempfile.TemporaryDirectory(prefix="saipen-inject-sh-grep-fail-") as raw:
            home = Path(raw)
            config = home / ".claude" / "CLAUDE.md"
            config.parent.mkdir(parents=True)
            original = b"user config\n"
            config.write_bytes(original)
            aider_config = home / ".aider.conf.yml"
            aider_original = b"read:\n  - user-owned.md\n"
            aider_config.write_bytes(aider_original)
            result = subprocess.run(
                [bash, str(HOME / "bootstrap" / "inject.sh")], cwd=HOME,
                env=grep_failure_env(home), capture_output=True, text=True,
                errors="replace")
            problem = failed_bootstrap_problem(
                "bootstrap/inject.sh grep failure", result)
            if problem:
                probe_failures.append(problem)
            elif (config.read_bytes() != original
                  or aider_config.read_bytes() != aider_original):
                probe_failures.append(
                    "bootstrap/inject.sh grep failure: config changed after read error")
            else:
                print("PASS: bootstrap/inject.sh grep failure -- exits nonzero without Done")
            checked += 1

        with tempfile.TemporaryDirectory(prefix="saipen-inject-sh-fail-") as raw:
            home = Path(raw)
            config = home / ".claude" / "CLAUDE.md"
            config.mkdir(parents=True)
            result = subprocess.run(
                [bash, str(HOME / "bootstrap" / "inject.sh")], cwd=HOME,
                env=bash_env(bash, home), capture_output=True, text=True,
                errors="replace")
            problem = failed_bootstrap_problem("bootstrap/inject.sh write failure", result)
            if problem:
                probe_failures.append(problem)

        with tempfile.TemporaryDirectory(prefix="saipen-uninstall-sh-fail-") as raw:
            home = Path(raw)
            config = home / ".claude" / "CLAUDE.md"
            config.parent.mkdir(parents=True)
            config.write_text(
                "user\n\n<!-- SAIPEN:BEGIN -->\nstale\n<!-- SAIPEN:END -->\n",
                encoding="utf-8", newline="\n")
            shim_dir = home / "bin"
            shim_dir.mkdir()
            head = shim_dir / "head"
            head.write_text("#!/usr/bin/env bash\nexit 9\n", encoding="utf-8",
                            newline="\n")
            head.chmod(0o755)
            env = bash_env(bash, home)
            env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
            result = subprocess.run(
                [bash, str(HOME / "bootstrap" / "uninstall.sh")], cwd=HOME,
                env=env, capture_output=True, text=True, errors="replace")
            problem = failed_bootstrap_problem(
                "bootstrap/uninstall.sh transform failure", result)
            if problem:
                probe_failures.append(problem)

        with tempfile.TemporaryDirectory(prefix="saipen-uninstall-sh-grep-fail-") as raw:
            home = Path(raw)
            config = home / ".claude" / "CLAUDE.md"
            config.parent.mkdir(parents=True)
            original = b"<!-- SAIPEN:BEGIN -->\nstale\n<!-- SAIPEN:END -->\n"
            config.write_bytes(original)
            aider_config = home / ".aider.conf.yml"
            aider_original = b"# saipen protocol auto-loaded\nread:\n"
            aider_config.write_bytes(aider_original)
            result = subprocess.run(
                [bash, str(HOME / "bootstrap" / "uninstall.sh")], cwd=HOME,
                env=grep_failure_env(home), capture_output=True, text=True,
                errors="replace")
            problem = failed_bootstrap_problem(
                "bootstrap/uninstall.sh grep failure", result)
            if problem:
                probe_failures.append(problem)
            elif (config.read_bytes() != original
                  or aider_config.read_bytes() != aider_original):
                probe_failures.append(
                    "bootstrap/uninstall.sh grep failure: config changed after read error")
            else:
                print("PASS: bootstrap/uninstall.sh grep failure -- exits nonzero without Done")

        with tempfile.TemporaryDirectory(prefix="saipen-uninstall-sh-file-") as raw:
            home = Path(raw)
            skill = home / ".claude" / "skills" / "saipen"
            skill.parent.mkdir(parents=True)
            skill.write_text("stale managed path\n", encoding="utf-8")
            result = subprocess.run(
                [bash, str(HOME / "bootstrap" / "uninstall.sh")], cwd=HOME,
                env=bash_env(bash, home), capture_output=True, text=True,
                errors="replace")
            output = result.stdout + result.stderr
            if result.returncode or "Done." not in output or skill.exists():
                probe_failures.append(
                    "bootstrap/uninstall.sh regular-file skill: expected removal "
                    f"and truthful success, got rc={result.returncode} exists={skill.exists()}")
            else:
                print("PASS: bootstrap/uninstall.sh regular-file skill -- removed")

        with tempfile.TemporaryDirectory(prefix="saipen-inject-sh-atomic-") as raw:
            root = Path(raw)
            source = root / "source"
            home = root / "home"
            shutil.copytree(HOME, source, ignore=shutil.ignore_patterns(
                ".git", ".saipen", ".venv", "__pycache__", "node_modules", "nul"))
            atomic_failures, atomic_checked = run_atomic_copy_failure_probes(
                "bootstrap/inject.sh", source, home,
                [bash, str(source / "bootstrap" / "inject.sh")],
                bash_env(bash, home))
            probe_failures.extend(atomic_failures)
            checked += atomic_checked
    else:
        print("SKIP: bootstrap/inject.sh executable probe -- no usable bash")
        skipped += 1

    if powershell:
        with tempfile.TemporaryDirectory(prefix="saipen-inject-ps1-") as raw:
            home = Path(raw)
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["USERPROFILE"] = str(home)
            # The injector probe runs uninstall.ps1 against a sandbox HOME,
            # but the scheduled task is machine-global -- the probe must not
            # delete a real scheduler entry (T-531/T-534).
            env["SAIPEN_UNINSTALL_SKIP_TASK"] = "1"
            problem = run_injector_probe(
                "bootstrap/inject.ps1",
                [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                 str(HOME / "bootstrap" / "inject.ps1"), "-SkillHome",
                 str(HOME / "saipen")],
                [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                 str(HOME / "bootstrap" / "uninstall.ps1")], env, home)
            if problem:
                probe_failures.append(problem)
            checked += 1

        with tempfile.TemporaryDirectory(prefix="saipen-inject-ps1-fail-") as raw:
            home = Path(raw)
            claude = home / ".claude"
            claude.mkdir(parents=True)
            (claude / "skills").write_text("not a directory\n", encoding="utf-8")
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["USERPROFILE"] = str(home)
            result = subprocess.run(
                [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                 str(HOME / "bootstrap" / "inject.ps1"), "-SkillHome",
                 str(HOME / "saipen")], cwd=HOME, env=env,
                capture_output=True, text=True, errors="replace")
            problem = failed_bootstrap_problem("bootstrap/inject.ps1 copy failure", result)
            if problem:
                probe_failures.append(problem)

        with tempfile.TemporaryDirectory(prefix="saipen-uninstall-ps1-fail-") as raw:
            home = Path(raw)
            config = home / ".claude" / "CLAUDE.md"
            config.mkdir(parents=True)
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["USERPROFILE"] = str(home)
            result = subprocess.run(
                [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                 str(HOME / "bootstrap" / "uninstall.ps1")], cwd=HOME, env=env,
                capture_output=True, text=True, errors="replace")
            problem = failed_bootstrap_problem(
                "bootstrap/uninstall.ps1 read failure", result)
            if problem:
                probe_failures.append(problem)

        with tempfile.TemporaryDirectory(prefix="saipen-inject-ps1-atomic-") as raw:
            root = Path(raw)
            source = root / "source"
            home = root / "home"
            shutil.copytree(HOME, source, ignore=shutil.ignore_patterns(
                ".git", ".saipen", ".venv", "__pycache__", "node_modules", "nul"))
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["USERPROFILE"] = str(home)
            env["SAIPEN_UNINSTALL_SKIP_TASK"] = "1"
            atomic_failures, atomic_checked = run_atomic_copy_failure_probes(
                "bootstrap/inject.ps1", source, home,
                [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                 str(source / "bootstrap" / "inject.ps1"), "-SkillHome",
                 str(source / "saipen")], env)
            probe_failures.extend(atomic_failures)
            checked += atomic_checked
    else:
        print("SKIP: bootstrap/inject.ps1 executable probe -- no PowerShell")
        skipped += 1

    # Prove the artifact assertions can go red without depending on injector
    # formatting: model the old delete-after-create result (VERSION copied,
    # tests/ gone) and require the probe to reject it.
    with tempfile.TemporaryDirectory(prefix="saipen-inject-red-") as raw:
        broken = Path(raw)
        (broken / "VERSION").write_text(
            (HOME / "VERSION").read_text(encoding="utf-8-sig"), encoding="utf-8")
        red = installed_layout_problems(broken)
        if not any("tests/validate" in problem for problem in red):
            probe_failures.append(
                "injector red-control: layout with deleted tests/ stayed green")
        else:
            print("PASS: injector probe red-control -- deleted tests/ goes red")

    with tempfile.TemporaryDirectory(prefix="saipen-inject-bytecode-red-") as raw:
        broken = Path(raw)
        generated = broken / "tools" / "__pycache__" / "distributed.pyc"
        generated.parent.mkdir(parents=True)
        generated.write_bytes(b"distributed\n")
        red = installed_layout_problems(broken)
        if not any("generated Python bytecode" in problem for problem in red):
            probe_failures.append(
                "injector red-control: installed generated bytecode stayed green")
        else:
            print("PASS: injector probe red-control -- installed bytecode goes red")

    return probe_failures, checked, skipped


def run_project_root_probes() -> tuple[list[str], int]:
    problems = []
    checked = 0
    git = shutil.which("git")
    if not git:
        return ["project-root probes require git"], checked

    def git_run(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([git, *args], cwd=cwd, capture_output=True,
                              text=True)

    def validate(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(VALIDATOR), *args], cwd=cwd,
                              capture_output=True, text=True)

    def expect(label: str, result: subprocess.CompletedProcess[str],
               returncode: int, contains: str) -> None:
        nonlocal checked
        checked += 1
        output = result.stdout + result.stderr
        if result.returncode != returncode or contains not in output:
            problems.append(
                f"{label}: exit {result.returncode}, expected {returncode}; "
                f"missing output {contains!r}")
        else:
            print(f"PASS: project root -- {label}")

    with tempfile.TemporaryDirectory(prefix="saipen-root-") as raw:
        sandbox = Path(raw).resolve()
        project = sandbox / "project"
        project.mkdir()
        shutil.copytree(
            SCENARIOS / "resume-after-crash" / ".saipen",
            project / ".saipen")
        (project / ".gitignore").write_text(".saipen/\n", encoding="utf-8")
        (project / "tracked.txt").write_text("root probe\n", encoding="utf-8")

        setup = [
            ("init",),
            ("config", "user.name", "SAIPEN root probe"),
            ("config", "user.email", "root-probe@example.invalid"),
            ("add", ".gitignore", "tracked.txt"),
            ("commit", "-m", "root probe"),
        ]
        for command in setup:
            result = git_run(project, *command)
            if result.returncode != 0:
                return [f"project-root git setup failed at {command}: "
                        f"{(result.stderr or result.stdout).strip()}"], checked

        project_text = str(project)
        expect("correct root", validate(project), 0,
               f"Project root: {project_text} (git-worktree)")

        nested = project / "one" / "two"
        nested.mkdir(parents=True)
        expect("nested cwd", validate(nested), 0,
               f"Project root: {project_text} (git-worktree)")
        if (nested / ".saipen").exists() or (nested.parent / ".saipen").exists():
            problems.append("nested cwd created a second .saipen/")

        foreign = sandbox / "foreign"
        foreign.mkdir()
        init_foreign = git_run(foreign, "init")
        if init_foreign.returncode != 0:
            return ["foreign repository setup failed: "
                    + (init_foreign.stderr or init_foreign.stdout).strip()], checked
        wrong = validate(foreign)
        expect("wrong cwd rejected", wrong, 1,
               "refusing to guess or create a second .saipen/")
        if (foreign / ".saipen").exists():
            problems.append("wrong cwd created .saipen/")

        expect("explicit root overrides cwd",
               validate(foreign, "--project-root", project_text), 0,
               f"Project root: {project_text} (explicit)")
        if (foreign / ".saipen").exists():
            problems.append("explicit-root invocation created .saipen/ in cwd")

        plain = sandbox / "plain-project"
        plain_nested = plain / "deep" / "cwd"
        plain_nested.mkdir(parents=True)
        shutil.copytree(
            SCENARIOS / "resume-after-crash" / ".saipen",
            plain / ".saipen")
        expect("non-Git nested cwd", validate(plain_nested), 0,
               f"Project root: {plain} (ancestor)")
        if (plain_nested / ".saipen").exists() or (plain / "deep" / ".saipen").exists():
            problems.append("non-Git nested cwd created a second .saipen/")

        linked = sandbox / "linked"
        add_worktree = git_run(project, "worktree", "add", "--detach", str(linked))
        if add_worktree.returncode != 0:
            return ["linked worktree setup failed: "
                    + (add_worktree.stderr or add_worktree.stdout).strip()], checked
        expect("linked worktree uses main owner", validate(linked), 0,
               f"Project root: {project_text} (git-common)")
        if (linked / ".saipen").exists():
            problems.append("linked worktree created a second .saipen/")

        # The other half: a linked worktree that DOES carry its own `.saipen/`
        # must be validated as itself. Asking the main worktree first meant a
        # local `phase: NOT-A-PHASE` validated EXIT=0 against a different
        # tree -- green for a tree nobody edited.
        own = linked / ".saipen"
        own.mkdir()
        for name in ("STATE.md", "BOARD.md", "LOG.md"):
            shutil.copy2(project / ".saipen" / name, own / name)
        state_path = own / "STATE.md"
        state_path.write_text(
            re.sub(r"^phase:.*$", "phase: NOT-A-PHASE",
                   state_path.read_text(encoding="utf-8-sig"),
                   count=1, flags=re.MULTILINE),
            encoding="utf-8", newline="\n")
        local = validate(linked)
        checked += 1
        local_text = local.stdout + local.stderr
        if local.returncode == 0 or "NOT-A-PHASE" not in local_text:
            problems.append(
                "linked worktree with its own .saipen/ did not validate itself: "
                f"exit {local.returncode} :: {local_text.strip()[:300]}")
        elif f"Project root: {linked}" not in local_text:
            problems.append(
                "linked worktree failure did not name the linked root")
        else:
            print("PASS: project root -- linked worktree with its own "
                  ".saipen/ is validated as itself")

    return problems, checked


def run_export_probes() -> tuple[list[str], int, int]:
    """Execute both exporters across the Core project-root ownership paths."""
    problems = []
    checked = skipped = 0
    git = shutil.which("git")
    bash = find_bash()
    powershell = find_powershell()
    if not git:
        return ["export probes require git"], checked, skipped

    def git_run(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([git, *args], cwd=cwd, capture_output=True,
                              text=True, errors="replace")

    def bash_path(path: Path) -> str:
        if os.name != "nt" or not bash:
            return str(path)
        converted = subprocess.run(
            [bash, "-lc", 'cygpath -u "$1"', "saipen-export", str(path)],
            capture_output=True, text=True, errors="replace")
        return converted.stdout.strip() if converted.returncode == 0 else str(path)

    def archive_marker(archive: Path) -> bytes | None:
        if archive.suffix == ".zip":
            with zipfile.ZipFile(archive) as bundle:
                name = next((n for n in bundle.namelist()
                             if n.replace("\\", "/").endswith(".saipen/marker.txt")),
                            None)
                return bundle.read(name) if name else None
        with tarfile.open(archive, "r:gz") as bundle:
            member = next((m for m in bundle.getmembers()
                           if m.name.replace("\\", "/").endswith(
                               ".saipen/marker.txt")), None)
            if member is None:
                return None
            stream = bundle.extractfile(member)
            return stream.read() if stream else None

    with tempfile.TemporaryDirectory(prefix="saipen-export-") as raw:
        sandbox = Path(raw).resolve()
        project = sandbox / "project"
        project.mkdir()
        (project / ".saipen").mkdir()
        marker = b"owner-project\n"
        (project / ".saipen" / "marker.txt").write_bytes(marker)
        (project / "tracked.txt").write_text("export probe\n", encoding="utf-8")
        for command in (
                ("init", "-q"),
                ("config", "user.name", "SAIPEN export probe"),
                ("config", "user.email", "export-probe@example.invalid"),
                ("add", "tracked.txt"),
                ("commit", "-q", "-m", "export probe")):
            result = git_run(project, *command)
            if result.returncode:
                return [f"export Git setup failed at {command}: "
                        f"{(result.stderr or result.stdout).strip()}"], checked, skipped

        nested = project / "nested" / "cwd"
        nested.mkdir(parents=True)
        foreign = sandbox / "foreign"
        foreign.mkdir()
        if git_run(foreign, "init", "-q").returncode:
            return ["export foreign Git setup failed"], checked, skipped
        linked = sandbox / "linked"
        worktree = git_run(project, "worktree", "add", "--detach", str(linked))
        if worktree.returncode:
            return ["export linked-worktree setup failed: "
                    + (worktree.stderr or worktree.stdout).strip()], checked, skipped

        external_parent = sandbox / "git-store"
        external_parent.mkdir()
        (external_parent / ".saipen").mkdir()
        (external_parent / ".saipen" / "marker.txt").write_bytes(
            b"wrong-external-owner\n")
        separate = sandbox / "separate"
        separate_git = git_run(
            sandbox, "init", "-q", "--separate-git-dir",
            str(external_parent / "repository.git"), str(separate))
        if separate_git.returncode:
            return ["export separate-git-dir setup failed: "
                    + (separate_git.stderr or separate_git.stdout).strip()], checked, skipped

        shell_home = sandbox / "shell-home"
        shell_home.mkdir()
        shell_environment = bash_env(bash, shell_home) if bash else None

        tools: list[tuple[str, list[str], str]] = []
        if bash:
            tools.append((
                "export.sh", [bash, str(HOME / "bootstrap" / "export.sh")],
                "--project-root"))
        else:
            print("SKIP: bootstrap/export.sh probes -- no usable bash")
            skipped += 6
        if powershell:
            tools.append((
                "export.ps1",
                [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                 str(HOME / "bootstrap" / "export.ps1")], "-ProjectRoot"))
        else:
            print("SKIP: bootstrap/export.ps1 probes -- no PowerShell")
            skipped += 6

        cases = (
            ("nested cwd", nested, None, True, None),
            ("foreign cwd rejected", foreign, None, False, "owns no .saipen"),
            ("explicit root overrides cwd", foreign, project, True, None),
            ("empty explicit root rejected", foreign, "", False,
             "requires a non-empty path"),
            ("linked worktree uses main owner", linked, None, True, None),
            ("external git-dir parent rejected", separate, None, False,
             "owns no .saipen"),
        )
        nonowner_roots = (foreign, nested, linked, external_parent, separate)
        for tool_name, base_command, explicit_flag in tools:
            for label, cwd, explicit, succeeds, failure_text in cases:
                for old in project.glob("saipen_export_*"):
                    old.unlink()
                for root in nonowner_roots:
                    for old in root.glob("saipen_export_*"):
                        old.unlink()
                command = list(base_command)
                if explicit is not None:
                    root_arg = (bash_path(explicit)
                                if tool_name.endswith(".sh") and explicit else str(explicit))
                    command.extend((explicit_flag, root_arg))
                result = subprocess.run(
                    command, cwd=cwd, capture_output=True, text=True,
                    errors="replace",
                    env=shell_environment if tool_name.endswith(".sh") else None)
                checked += 1
                output = result.stdout + result.stderr
                archives = list(project.glob("saipen_export_*"))
                wrong = [archive for root in nonowner_roots
                         for archive in root.glob("saipen_export_*")]
                if not succeeds:
                    if (result.returncode == 0 or "Done." in output or archives or wrong
                            or failure_text not in output):
                        problems.append(
                            f"{tool_name} {label}: expected focused failure containing "
                            f"{failure_text!r} with no archive")
                    else:
                        print(f"PASS: {tool_name} -- {label}")
                    continue
                if result.returncode or "Done. Export saved to:" not in output:
                    detail = next((line for line in output.splitlines()
                                   if line.startswith(("FAILED", "tar:"))),
                                  output.strip()[:160] or "no output")
                    problems.append(
                        f"{tool_name} {label}: exit {result.returncode} without "
                        f"success path: {detail}")
                    continue
                if len(archives) != 1 or wrong:
                    problems.append(
                        f"{tool_name} {label}: expected one owner archive, got "
                        f"owner={len(archives)} wrong={len(wrong)}")
                    continue
                try:
                    archived_marker = archive_marker(archives[0])
                except (OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
                    problems.append(f"{tool_name} {label}: unreadable archive: {exc}")
                    continue
                if archived_marker != marker:
                    problems.append(f"{tool_name} {label}: archive has wrong owner marker")
                else:
                    print(f"PASS: {tool_name} -- {label}")
                archives[0].unlink(missing_ok=True)

    return problems, checked, skipped


def run_crew_probes() -> tuple[list[str], int, int]:
    """Execute both crew launchers against controlled start processes."""
    bash = find_bash()
    problems = []
    checked = 0
    skipped = 0
    if not bash:
        print("SKIP: bootstrap/saipen_crew.sh probes -- no usable bash")
        skipped += 2
    else:
        with tempfile.TemporaryDirectory(prefix="saipen-crew-") as raw:
            sandbox = Path(raw)
            shim_dir = sandbox / "bin"
            shim_dir.mkdir()
            probe_log = sandbox / "launcher.log"
            converted = subprocess.run(
                [bash, "-lc", 'cygpath -u "$1" 2>/dev/null || printf "%s" "$1"',
                 "saipen-crew", str(probe_log)],
                capture_output=True, text=True, errors="replace")
            log_path = (converted.stdout.strip() if converted.returncode == 0
                        else str(probe_log))
            launcher_source = (
                "#!/usr/bin/env sh\n"
                'printf "%s\\n" "$*" >> "$SAIPEN_CREW_PROBE_LOG"\n'
                'exit "$SAIPEN_CREW_PROBE_EXIT"\n')
            for name in ("gnome-terminal", "konsole", "xterm"):
                launcher = shim_dir / name
                launcher.write_text(launcher_source, encoding="utf-8", newline="\n")
                launcher.chmod(0o755)

            env = bash_env(bash, sandbox)
            env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
            env["SAIPEN_CREW_LAUNCH_GRACE"] = "0.05"
            env["SAIPEN_CREW_PROBE_LOG"] = log_path
            command = [bash, str(HOME / "bootstrap" / "saipen_crew.sh")]

            env["SAIPEN_CREW_PROBE_EXIT"] = "9"
            failed = subprocess.run(
                command, cwd=HOME, env=env, capture_output=True, text=True,
                errors="replace")
            checked += 1
            failed_output = failed.stdout + failed.stderr
            failed_calls = (probe_log.read_text(encoding="utf-8").splitlines()
                            if probe_log.is_file() else [])
            if (failed.returncode == 0 or "Done." in failed_output
                    or "FAILED:" not in failed_output or len(failed_calls) != 9):
                problems.append(
                    "bootstrap/saipen_crew.sh broken launcher: expected nine "
                    "failed fallback calls, focused nonzero, and no Done; got "
                    f"{len(failed_calls)}")
            else:
                print("PASS: bootstrap/saipen_crew.sh broken launcher -- "
                      "exits nonzero without Done")

            probe_log.unlink(missing_ok=True)
            env["SAIPEN_CREW_PROBE_EXIT"] = "0"
            succeeded = subprocess.run(
                command, cwd=HOME, env=env, capture_output=True, text=True,
                errors="replace")
            checked += 1
            succeeded_output = succeeded.stdout + succeeded.stderr
            calls = (probe_log.read_text(encoding="utf-8").splitlines()
                     if probe_log.is_file() else [])
            if (succeeded.returncode != 0
                    or "Done. Launched 3 crew windows." not in succeeded_output
                    or len(calls) != 3):
                problems.append(
                    "bootstrap/saipen_crew.sh working launcher: expected three "
                    "accepted calls and truthful Done, got "
                    f"rc={succeeded.returncode} calls={len(calls)}")
            else:
                print("PASS: bootstrap/saipen_crew.sh working launcher -- "
                      "three accepted calls")

    cmd = os.environ.get("COMSPEC") or shutil.which("cmd")
    if not cmd:
        print("SKIP: bootstrap/saipen_crew.bat probes -- no cmd.exe")
        skipped += 4
    else:
        with tempfile.TemporaryDirectory(prefix="saipen-crew-bat-") as raw:
            sandbox = Path(raw)
            probe_log = sandbox / "launcher.log"
            launcher = sandbox / "start-probe.cmd"
            launcher.write_text(
                "@echo off\n"
                '>>"%SAIPEN_CREW_PROBE_LOG%" echo call\n'
                'if "%SAIPEN_CREW_LAUNCH_INDEX%"=="%SAIPEN_CREW_FAIL_AT%" exit /b 9\n'
                "exit /b 0\n",
                encoding="utf-8", newline="\r\n")
            env = os.environ.copy()
            env["SAIPEN_CREW_START_COMMAND"] = str(launcher)
            env["SAIPEN_CREW_PROBE_LOG"] = str(probe_log)
            command = [cmd, "/d", "/c", str(HOME / "bootstrap" / "saipen_crew.bat")]

            for fail_at in (1, 2, 3):
                probe_log.unlink(missing_ok=True)
                env["SAIPEN_CREW_FAIL_AT"] = str(fail_at)
                failed = subprocess.run(
                    command, cwd=HOME, env=env, capture_output=True, text=True,
                    errors="replace")
                checked += 1
                output = failed.stdout + failed.stderr
                calls = (probe_log.read_text(encoding="utf-8").splitlines()
                         if probe_log.is_file() else [])
                if (failed.returncode == 0 or "Three crew windows opened." in output
                        or "FAILED:" not in output or len(calls) != fail_at):
                    problems.append(
                        f"bootstrap/saipen_crew.bat failed start {fail_at}: "
                        "expected focused nonzero and no success after "
                        f"{fail_at} calls; got rc={failed.returncode} calls={len(calls)}")
                else:
                    print(f"PASS: bootstrap/saipen_crew.bat failed start {fail_at} "
                          "-- exits nonzero without success")

            probe_log.unlink(missing_ok=True)
            env["SAIPEN_CREW_FAIL_AT"] = "0"
            succeeded = subprocess.run(
                command, cwd=HOME, env=env, capture_output=True, text=True,
                errors="replace")
            checked += 1
            output = succeeded.stdout + succeeded.stderr
            calls = (probe_log.read_text(encoding="utf-8").splitlines()
                     if probe_log.is_file() else [])
            if (succeeded.returncode != 0
                    or output.count("Three crew windows opened.") != 1
                    or len(calls) != 3):
                problems.append(
                    "bootstrap/saipen_crew.bat working start: expected three "
                    "accepted calls and one truthful success, got "
                    f"rc={succeeded.returncode} calls={len(calls)}")
            else:
                print("PASS: bootstrap/saipen_crew.bat working start -- "
                      "three accepted calls")

    return problems, checked, skipped


def live_style_marker() -> str:
    """STYLE.md's declared boot marker, read the way an agent reads it.

    Never hardcoded: a pinned token silently turns the marker fixtures into a
    pair of always-failing states the moment STYLE.md is edited, which is the
    opposite of what they check.
    """
    text = (HOME / "saipen" / "STYLE.md").read_text(encoding="utf-8-sig")
    found = re.search(r"`style_contract:\s*(ded-[0-9a-f]{8})`", text)
    return found.group(1) if found else "ded-00000000"


def run_manifest_tracking_probes() -> tuple[list[str], int]:
    """A runtime-manifest entry must be in the repository, not just on disk.

    Needs a real repository for the same reason the hunt-mark probe does, so
    it cannot live in `tools/audit_checks.py`, whose snapshot excludes `.git`.
    The mutation removes one manifest file from the index and leaves it on
    disk -- exactly the state that shipped green locally and red in CI.
    """
    problems: list[str] = []
    checked = 0
    victim = "tools/audit_floor.py"

    with tempfile.TemporaryDirectory(prefix="saipen-manifest-") as raw:
        home = Path(raw) / "home"
        shutil.copytree(HOME, home, ignore=shutil.ignore_patterns(
            ".git", ".venv", "__pycache__", "node_modules", "nul", ".freebuff"))
        env = {**os.environ, "GIT_AUTHOR_NAME": "probe",
               "GIT_AUTHOR_EMAIL": "probe@example.invalid",
               "GIT_COMMITTER_NAME": "probe",
               "GIT_COMMITTER_EMAIL": "probe@example.invalid"}

        def git(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(["git", *args], cwd=home, env=env,
                                  capture_output=True, text=True, check=False)

        if git("init", "-q").returncode != 0:
            print("SKIP: manifest tracking probes -- git unavailable")
            return problems, checked
        git("add", "-A")
        git("commit", "-q", "-m", "probe")

        def validate() -> str:
            r = subprocess.run(
                [sys.executable, str(home / "tools" / "validate.py"),
                 "--project-root", str(home)],
                cwd=home, capture_output=True, text=True, errors="replace")
            return r.stdout + r.stderr

        def expect(label: str, output: str, contains: str) -> None:
            nonlocal checked
            checked += 1
            if contains not in output:
                problems.append(f"{label}: missing {contains!r}")
            else:
                print(f"PASS: manifest tracking -- {label}")

        git("rm", "-q", "--cached", victim)
        git("commit", "-q", "-m", "drop from index, keep on disk")
        expect("an untracked manifest file fails", validate(),
               f"names a file git does not track: {victim}")

        git("add", victim)
        git("commit", "-q", "-m", "restore")
        expect("the same file tracked again passes", validate(),
               "runtime manifest complete")

    return problems, checked


def run_autoinject_manifest_probes() -> tuple[list[str], int]:
    """Every copied manifest surface must invalidate installed-copy stamps."""
    problems: list[str] = []
    checked = 0
    spec = importlib.util.spec_from_file_location(
        "saipen_autoinject_probe", HOME / "tools" / "autoinject.py")
    if spec is None or spec.loader is None:
        return ["autoinject manifest probe could not load autoinject.py"], checked
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    with tempfile.TemporaryDirectory(prefix="saipen-autoinject-manifest-") as raw:
        clone = Path(raw)
        for tree in RUNTIME_MANIFEST["copy_trees"]:
            shutil.copytree(HOME / tree["src"], clone / tree["src"])
        for entry in RUNTIME_MANIFEST["files"]:
            if not entry.get("required", False):
                continue
            source = HOME / entry["src"]
            target = clone / entry["src"]
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        module.HOME = clone

        first = module._digest()
        index = clone / "saipen" / "INDEX.md"
        index.write_text(index.read_text(encoding="utf-8") + "\nprobe\n",
                         encoding="utf-8", newline="\n")
        second = module._digest()
        checked += 1
        if first == second:
            problems.append("autoinject digest ignored manifest file saipen/INDEX.md")
        else:
            print("PASS: autoinject manifest -- INDEX.md invalidates digest")

        core = clone / "saipen" / "CORE.md"
        core.write_text(core.read_text(encoding="utf-8") + "\nprobe\n",
                        encoding="utf-8", newline="\n")
        third = module._digest()
        checked += 1
        if second == third:
            problems.append("autoinject digest ignored manifest file saipen/CORE.md")
        else:
            print("PASS: autoinject manifest -- CORE.md invalidates digest")

        manifest_path = clone / "saipen" / "MANIFEST.json"
        malformed = json.loads(manifest_path.read_text(encoding="utf-8"))
        malformed["copy_trees"][0]["src"] = "../outside"
        manifest_path.write_text(json.dumps(malformed), encoding="utf-8", newline="\n")
        checked += 1
        try:
            module._digest()
        except RuntimeError as exc:
            if "unsafe runtime manifest source" not in str(exc):
                problems.append(f"autoinject traversal failed unclearly: {exc}")
            else:
                print("PASS: autoinject manifest -- traversal source fails closed")
        else:
            problems.append("autoinject accepted ../ traversal in copy_trees source")

    return problems, checked


def run_hunt_mark_probes() -> tuple[list[str], int]:
    """Execute `phases/hunt.md`'s skip condition against a real repository.

    Lives here rather than in `tools/audit_checks.py` because that harness
    copies the tree WITHOUT `.git`, so a hash-resolution check is skipped
    there and its red control would report a green mutation -- an instrument
    measuring nothing while reporting a result.
    """
    problems: list[str] = []
    checked = 0

    def validate(project: Path) -> str:
        r = subprocess.run(
            [sys.executable, str(VALIDATOR), "--project-root", str(project)],
            cwd=project, capture_output=True, text=True, errors="replace")
        return r.stdout + r.stderr

    def expect(label: str, output: str, contains: str, absent: str = "") -> None:
        nonlocal checked
        checked += 1
        details = []
        if contains not in output:
            details.append(f"missing {contains!r}")
        if absent and absent in output:
            details.append(f"unexpected {absent!r}")
        if details:
            problems.append(f"{label}: {'; '.join(details)}")
        else:
            print(f"PASS: hunt mark -- {label}")

    marker = "LOG.md records a clean hunt against commit(s)"
    with tempfile.TemporaryDirectory(prefix="saipen-hunt-mark-") as raw:
        project = Path(raw) / "project"
        shutil.copytree(SCENARIOS / "stale-state-reconciliation" / ".saipen",
                        project / ".saipen")
        env = {**os.environ, "GIT_AUTHOR_NAME": "probe",
               "GIT_AUTHOR_EMAIL": "probe@example.invalid",
               "GIT_COMMITTER_NAME": "probe",
               "GIT_COMMITTER_EMAIL": "probe@example.invalid"}

        def git(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(["git", *args], cwd=project, env=env,
                                  capture_output=True, text=True, check=False)

        if git("init", "-q").returncode != 0:
            print("SKIP: hunt mark probes -- git unavailable")
            return problems, checked
        git("add", "-A")
        git("commit", "-q", "-m", "probe")
        head = git("rev-parse", "--short", "HEAD").stdout.strip()
        if not head:
            print("SKIP: hunt mark probes -- no commit to resolve against")
            return problems, checked

        log_path = project / ".saipen" / "LOG.md"
        base = log_path.read_text(encoding="utf-8-sig").rstrip("\n")

        def write_mark(short_hash: str) -> None:
            log_path.write_text(
                f"{base}\n- 26.07.17 00:01 [E-002] [parent: E-001] [T-001] "
                f"RUN: hunt -> clean @{short_hash}\n",
                encoding="utf-8", newline="\n")

        write_mark("dead0be")
        expect("a mark no commit backs fails", validate(project), marker)

        write_mark(head)
        expect("the exact HEAD mark passes", validate(project),
               "hunt skip marks resolve to real commits", absent=marker)

        # T-528 rung: a commit that exists locally but has never reached a
        # remote must FAIL, even though the old check passes it -- this is
        # exactly the db9d775 gap, where a local run stayed green while CI,
        # a fresh clone of the identical tree, went red.
        bare = Path(raw) / "remote.git"
        git("init", "-q", "--bare", str(bare))
        git("remote", "add", "origin", str(bare))
        if git("push", "-q", "-u", "origin", "HEAD").returncode == 0:
            other = project / "scratch.txt"
            other.write_text("unpushed local-only commit\n", encoding="utf-8")
            git("add", "-A")
            git("commit", "-q", "-m", "probe: unpushed local-only commit")
            unpushed = git("rev-parse", "--short", "HEAD").stdout.strip()
            if unpushed:
                write_mark(unpushed)
                expect("a local-only commit fails (never reached a remote)",
                       validate(project), "sit on no remote branch")
                write_mark(head)
                expect("a remote-backed mark still passes after the stray",
                       validate(project),
                       "hunt skip marks resolve to real commits",
                        absent=marker)

    return problems, checked


def run_ship_staging_probes() -> tuple[list[str], int]:
    """Execute T-569: a runtime file this ship adds passes the gate once staged.

    The paradox this closes was an ORDERING one, so the probe measures the same
    file at three states in one repository -- untracked, staged, committed --
    and the finding must appear at exactly one of them. Asserting only that an
    untracked file FAILs would have passed before the fix too, and asserting
    only that a committed file passes proves nothing about the window SHIP
    actually runs in.
    """
    problems: list[str] = []
    checked = 0
    env = {**os.environ, "GIT_AUTHOR_NAME": "probe",
           "GIT_AUTHOR_EMAIL": "probe@example.invalid",
           "GIT_COMMITTER_NAME": "probe",
           "GIT_COMMITTER_EMAIL": "probe@example.invalid"}
    home = VALIDATOR.parent.parent
    manifest_path = home / "saipen" / "MANIFEST.json"
    if not manifest_path.is_file():
        print("SKIP: ship staging probes -- no runtime MANIFEST")
        return problems, checked

    def expect(label: str, condition: bool, detail: str = "") -> None:
        nonlocal checked
        checked += 1
        if condition:
            print(f"PASS: ship staging -- {label}")
        else:
            problems.append(f"{label}: {detail}")

    with tempfile.TemporaryDirectory(prefix="saipen-ship-staging-") as tmp:
        home_copy = Path(tmp) / "home"
        shutil.copytree(home, home_copy, ignore=shutil.ignore_patterns(
            ".git", ".venv", "__pycache__", ".freebuff", "node_modules", "nul"))

        def git(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(["git", *args], cwd=home_copy, env=env,
                                  capture_output=True, text=True, check=False)

        if git("init", "-q").returncode != 0:
            print("SKIP: ship staging probes -- git unavailable")
            return problems, checked
        git("add", "-A")
        git("commit", "-q", "-m", "probe: baseline")

        def untracked_names() -> set[str]:
            r = subprocess.run(
                [sys.executable, str(home_copy / "tools" / "validate.py"),
                 "--project-root", str(home_copy), "--gate", "ship"],
                cwd=home_copy, capture_output=True, text=True, errors="replace")
            return {line.split(": ")[-1].split(" --")[0].strip()
                    for line in (r.stdout + r.stderr).splitlines()
                    if line.startswith("FAIL: runtime manifest names a file "
                                       "git does not track")}

        expect("baseline home has no untracked runtime file",
               not untracked_names(),
               f"unexpected untracked entries: {sorted(untracked_names())}")

        # A required runtime file added by the ticket being shipped.
        rel = "tools/probe_runtime_addition.py"
        (home_copy / rel).write_text("# probe runtime file\n",
                                     encoding="utf-8", newline="\n")
        manifest_copy = home_copy / "saipen" / "MANIFEST.json"
        data = json.loads(manifest_copy.read_text(encoding="utf-8"))
        entries = data.get("files")
        if not isinstance(entries, list) or not all(
                isinstance(item, dict) and "src" in item for item in entries):
            print("SKIP: ship staging probes -- MANIFEST shape unrecognized")
            return problems, checked
        data["files"] = [*entries, {"src": rel, "required": True}]
        manifest_copy.write_text(json.dumps(data, indent=2) + "\n",
                                 encoding="utf-8", newline="\n")
        git("add", "--", "saipen/MANIFEST.json")
        git("commit", "-q", "-m", "probe: manifest names the new file")

        expect("a required runtime file merely present untracked FAILs",
               rel in untracked_names(),
               "the gate accepted a manifest entry no clone would receive")

        git("add", "--", rel)
        expect("the same file staged for THIS ship satisfies the gate",
               rel not in untracked_names(),
               "staging is the step SHIP performs before its binding gate, so "
               "a staged file the manifest requires must pass -- otherwise no "
               "sequence the protocol describes can ever add one")

        # The staged state is the one SHIP gates on; committing must not
        # change the answer, or the gate would be measuring the commit rather
        # than the scope that was reviewed.
        git("commit", "-q", "-m", "probe: the new runtime file")
        expect("committing does not change the answer staging gave",
               rel not in untracked_names(),
               "the gate disagrees with itself across the commit boundary")

        # Unstaging returns it to the failing state: the pass came from the
        # index, not from the file existing on disk.
        git("rm", "-q", "--cached", "--", rel)
        expect("removing it from the index brings the FAIL back",
               rel in untracked_names(),
               "the gate passed on a file's presence on disk, which is the "
               "exact reading that ships a home no clone can reproduce")

    return problems, checked


def run_producer_gate_probes() -> tuple[list[str], int]:
    """Execute T-568's six red controls: gate context decides producer severity.

    The defect these close is an OWNERSHIP one, not a parsing one. Every check
    below already existed and already fired correctly -- at the wrong severity,
    on the wrong occasions, so a stale wiki package produced by a different
    model blocked an unrelated one-line Core commit. What is under test is
    therefore the mapping from GATE to severity, which means each fixture is
    run at several gates and compared against itself.
    """
    problems: list[str] = []
    checked = 0
    env = {**os.environ, "GIT_AUTHOR_NAME": "probe",
           "GIT_AUTHOR_EMAIL": "probe@example.invalid",
           "GIT_COMMITTER_NAME": "probe",
           "GIT_COMMITTER_EMAIL": "probe@example.invalid"}

    def validate(project: Path, *gate: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--project-root", str(project),
             *gate],
            cwd=project, capture_output=True, text=True, errors="replace")

    def expect(label: str, result: subprocess.CompletedProcess[str],
               contains: str = "", absent: str = "") -> None:
        nonlocal checked
        checked += 1
        output = result.stdout + result.stderr
        details = []
        if contains and contains not in output:
            details.append(f"missing {contains!r}")
        if absent and absent in output:
            details.append(f"unexpected {absent!r}")
        if details:
            problems.append(f"{label}: {'; '.join(details)}")
        else:
            print(f"PASS: producer gate -- {label}")

    stale_fail = "package is stale and MUST NOT be collected"
    malformed = "parses as zero OUTBOX entries"
    soft_note = "where this producer is not being consumed"

    def fails_on(result: subprocess.CompletedProcess[str], needle: str) -> bool:
        return any(line.startswith("FAIL") and needle in line
                   for line in (result.stdout + result.stderr).splitlines())

    def expect_severity(label: str, result: subprocess.CompletedProcess[str],
                        needle: str, hard: bool) -> None:
        nonlocal checked
        checked += 1
        got_hard = fails_on(result, needle)
        if got_hard != hard:
            problems.append(
                f"{label}: expected {'FAIL' if hard else 'WARN'} for {needle!r}, "
                f"got {'FAIL' if got_hard else 'no FAIL'}")
        else:
            print(f"PASS: producer gate -- {label}")

    def write_outbox(path: Path, body: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8", newline="\n")

    def ready_package(identity_head: str, fingerprint: str,
                      role_revision: str) -> str:
        return (
            "---\n"
            "status: ready\n"
            "producer: saiwiki\n"
            "summary: probe package\n"
            "critical: none\n"
            "coverage: complete\n"
            "payload: probe\n"
            "instructions: apply\n"
            "verified: probe suite green\n"
            f"source_head: {identity_head}\n"
            f"source_tree_fingerprint: {fingerprint}\n"
            f"role_revision: {role_revision}\n"
            "---\n")

    with tempfile.TemporaryDirectory(prefix="saipen-producer-gate-") as tmp:
        project = Path(tmp) / "project"
        shutil.copytree(SCENARIOS / "stale-state-reconciliation" / ".saipen",
                        project / ".saipen")
        if subprocess.run(["git", "init", "-q"], cwd=project, env=env,
                          capture_output=True, text=True).returncode != 0:
            print("SKIP: producer gate probes -- git unavailable")
            return problems, checked

        wiki = project / ".saipen/extensions/subs/saiwiki/kitchen/OUTBOX.md"
        translate = project / ".saipen/saitranslate/kitchen/OUTBOX.md"

        # Control 1 + 2 + 3: ONE stale QQ package, read at three gates.
        write_outbox(wiki, ready_package("0000000", "sha256:stale", "rev-old"))
        write_outbox(translate, "# OUTBOX\n")
        subprocess.run(["git", "add", "-A"], cwd=project, env=env,
                       capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", "probe"], cwd=project,
                       env=env, capture_output=True)

        expect_severity("1. stale QQ does not fail the default gate",
                        validate(project), stale_fail, hard=False)
        expect_severity("1b. stale QQ does not fail the ship gate",
                        validate(project, "--gate", "ship"), stale_fail,
                        hard=False)
        expect("1c. the stale package is still visible as a WARN",
               validate(project), soft_note)
        expect_severity("2. the same stale QQ FAILs collect:saiwiki",
                        validate(project, "--gate", "collect:saiwiki"),
                        stale_fail, hard=True)
        expect_severity("3. the same stale QQ FAILs the converge gate",
                        validate(project, "--gate", "converge"),
                        stale_fail, hard=True)
        # Collecting one producer says nothing about another: the whole point
        # of the split is that severity follows the CONSUMED producer.
        expect_severity("2b. collecting saitranslate leaves saiwiki soft",
                        validate(project, "--gate", "collect:saitranslate"),
                        stale_fail, hard=False)

        # Control 4 + 5: a malformed EE package.
        write_outbox(translate, "this is not an OUTBOX at all\n")
        expect_severity("4. malformed EE does not block an ordinary Core ship",
                        validate(project, "--gate", "ship"), malformed,
                        hard=False)
        expect_severity("5. the same malformed EE FAILs collect:saitranslate",
                        validate(project, "--gate", "collect:saitranslate"),
                        malformed, hard=True)

        # Control 6: fresh exact EE and QQ pass the converge gate. Both
        # packages are bound to the identity this tree actually computes, so
        # the rung proves the gate accepts correctness rather than merely
        # rejecting everything.
        sys.path.insert(0, str(VALIDATOR.parent))
        try:
            from freshness import (compute_role_revision,
                                   compute_source_identity)
            identity = compute_source_identity(project)
            wiki_charter = VALIDATOR.parent.parent / "extensions/subs/saiwiki.md"
            translate_charter = (VALIDATOR.parent.parent
                                 / "extensions/subs/saitranslate.md")
            fresh_ok = wiki_charter.is_file() and translate_charter.is_file()
        except Exception as exc:
            print(f"SKIP: producer gate fresh rung -- {exc}")
            fresh_ok = False
        if fresh_ok:
            for path, charter, producer in (
                    (wiki, wiki_charter, "saiwiki"),
                    (translate, translate_charter, "saitranslate")):
                write_outbox(path, ready_package(
                    identity.source_head, identity.source_tree_fingerprint,
                    compute_role_revision(charter)).replace(
                        "producer: saiwiki", f"producer: {producer}"))
            # The charters must be project-local for role_revision to derive.
            local_subs = project / "extensions/subs"
            local_subs.mkdir(parents=True, exist_ok=True)
            for charter in (wiki_charter, translate_charter):
                shutil.copy2(charter, local_subs / charter.name)
            identity = compute_source_identity(project)
            for path, charter, producer in (
                    (wiki, wiki_charter, "saiwiki"),
                    (translate, translate_charter, "saitranslate")):
                write_outbox(path, ready_package(
                    identity.source_head, identity.source_tree_fingerprint,
                    compute_role_revision(charter)).replace(
                        "producer: saiwiki", f"producer: {producer}"))
            result = validate(project, "--gate", "converge")
            expect("6. fresh exact EE and QQ pass the converge gate", result,
                   "both closure-required packages (EE, QQ) are ready")
            expect_severity("6b. no producer finding survives on fresh packages",
                            result, stale_fail, hard=False)
            # Absence is a finding at the consumer's gate: nothing to collect
            # must refuse rather than report a silent green.
            write_outbox(wiki, "# OUTBOX\n")
            expect("7. a producer with no ready package cannot be collected",
                   validate(project, "--gate", "collect:saiwiki"),
                   "no OUTBOX entry from that producer is `status: ready`")
            expect("8. converge names the missing closure package",
                   validate(project, "--gate", "converge"),
                   "required producer package(s) are missing or not ready: "
                   "QQ (saiwiki)")

        # An unknown gate must refuse rather than fall back to the soft
        # default: a typo'd `collect:saiwki` that ran the soft gate would
        # report green on exactly the package the caller asked to hard-check.
        typo = validate(project, "--gate", "collect:saiwki")
        expect("9. a misspelled producer gate still hard-checks (no fallback)",
               typo, "no OUTBOX entry from that producer is `status: ready`")
        unknown = validate(project, "--gate", "nonsense")
        checked += 1
        if unknown.returncode != 2 or "unknown --gate" not in (
                unknown.stdout + unknown.stderr):
            problems.append("10. unknown gate: expected exit 2 and a named "
                            f"refusal, got exit {unknown.returncode}")
        else:
            print("PASS: producer gate -- 10. an unknown gate exits 2, "
                  "never falls back to soft")

    return problems, checked


def run_ccc_identity_probes() -> tuple[list[str], int]:
    """Execute the T-566 canonical-commit proof in the ccc I -> SHIP -> J route.

    Needs a real repository for the same reason the hunt-mark probes do: the
    subject is commit RESOLUTION, and `tools/audit_checks.py` copies the tree
    without `.git`, so every rung here would report green against a validator
    that resolved nothing. The SHA-256 rung needs its own repository because a
    repository's object format is fixed at `git init`.
    """
    problems: list[str] = []
    checked = 0
    env = {**os.environ, "GIT_AUTHOR_NAME": "probe",
           "GIT_AUTHOR_EMAIL": "probe@example.invalid",
           "GIT_COMMITTER_NAME": "probe",
           "GIT_COMMITTER_EMAIL": "probe@example.invalid"}

    def validate(project: Path) -> str:
        r = subprocess.run(
            [sys.executable, str(VALIDATOR), "--project-root", str(project)],
            cwd=project, capture_output=True, text=True, errors="replace")
        return r.stdout + r.stderr

    def expect(label: str, output: str, contains: str = "",
               absent: str = "") -> None:
        nonlocal checked
        checked += 1
        details = []
        if contains and contains not in output:
            details.append(f"missing {contains!r}")
        if absent and absent in output:
            details.append(f"unexpected {absent!r}")
        if details:
            problems.append(f"{label}: {'; '.join(details)}")
        else:
            print(f"PASS: ccc identity -- {label}")

    unchanged = "ccc SHIP did not change source revision"
    unresolved = "ccc SHIP evidence names commit(s) this repository cannot resolve"
    mismatch = "ccc SHIP evidence does not match current source_head"

    def write_state(project: Path) -> None:
        (project / ".saipen" / "STATE.md").write_text(
            "---\nphase: SHIP\ntask: none\nnext_action: \"PHASE DONE\"\n"
            "blocker: none\ntransition_from: REVIEW\nsaipen_version: 7\n"
            "agent: probe\nmode: full\nexecution_intent: converge\n"
            "converge_target: ship\nupdated: 2026-01-01T00:00:00Z\n---\n",
            encoding="utf-8", newline="\n")

    def build(raw: Path, name: str, object_format: str | None) -> Path | None:
        project = raw / name
        shutil.copytree(SCENARIOS / "stale-state-reconciliation" / ".saipen",
                        project / ".saipen")
        init = ["init", "-q"]
        if object_format:
            init += [f"--object-format={object_format}"]
        if subprocess.run(["git", *init], cwd=project, env=env,
                          capture_output=True, text=True).returncode != 0:
            return None
        write_state(project)
        return project

    def git(project: Path, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=project, env=env,
                              capture_output=True, text=True,
                              check=False).stdout.strip()

    def commit(project: Path, message: str) -> str:
        git(project, "add", "-A")
        git(project, "commit", "-q", "--allow-empty", "-m", message)
        return git(project, "rev-parse", "HEAD")

    # Split so the literal never forms a version string in this file's source:
    # the cross-doc drift check scans shipped sources for cited versions, and a
    # probe fixture is not a release. Same idiom as the audit tag shim.
    probe_version = "v" + "9.9.9"

    def write_log(project: Path, base: str, entry_at: str, shipped: str) -> None:
        (project / ".saipen" / "LOG.md").write_text(
            f"{base}\n"
            f"- 26.07.17 00:01 [E-002] [parent: E-001] "
            f"DEC: ccc converge target -> ship @{entry_at}\n"
            f"- 26.07.17 00:02 [E-003] [parent: E-002] "
            f"RUN: ship {probe_version} -> pushed {shipped}\n",
            encoding="utf-8", newline="\n")

    with tempfile.TemporaryDirectory(prefix="saipen-ccc-identity-") as tmp:
        raw = Path(tmp)
        project = build(raw, "sha1", None)
        if project is None:
            print("SKIP: ccc identity probes -- git unavailable")
            return problems, checked
        base = (project / ".saipen" / "LOG.md").read_text(
            encoding="utf-8-sig").rstrip("\n")
        first = commit(project, "probe: pre-ship")
        if not first:
            print("SKIP: ccc identity probes -- no commit to resolve against")
            return problems, checked

        # The defect itself. Both references name the SAME commit, one
        # abbreviated -- string equality says "different", so the check that
        # exists to catch a SHIP which changed nothing concluded it had.
        write_log(project, base, first[:7], first)
        expect("one commit at two widths is caught as unchanged",
               validate(project), unchanged)
        # ... and the reverse width order, because `startswith` gets exactly
        # one of the two directions right by accident.
        write_log(project, base, first, first[:7])
        expect("the same pair with the widths swapped is still unchanged",
               validate(project), unchanged)

        second = commit(project, "probe: the ship commit")
        write_log(project, base, first[:7], second)
        expect("distinct commits are a real revision change",
               validate(project), absent=unchanged)
        expect("distinct commits match the current HEAD",
               validate(project), absent=mismatch)

        # Evidence that resolves to nothing proves nothing -- it must FAIL
        # rather than skip, which is T-528's shape one check over.
        write_log(project, base, first[:7], "dead0beefdead0beefdead0beefdead0beef0001")
        expect("evidence naming a commit the repository lacks fails",
               validate(project), unresolved)

        # A real commit that is simply not the current HEAD: the packages
        # would bind to a revision the tree has already moved past.
        commit(project, "probe: work landed after the recorded ship")
        write_log(project, base, first[:7], second)
        expect("shipped evidence behind the current HEAD fails",
               validate(project), mismatch)

        # Outside a repository the proof is unperformable, not failed. Without
        # this rung the canonicalization would have turned every no-Git project
        # into a hard FAIL on evidence that was never checkable there.
        nogit = raw / "nogit"
        shutil.copytree(SCENARIOS / "stale-state-reconciliation" / ".saipen",
                        nogit / ".saipen")
        write_state(nogit)
        write_log(nogit, base, first[:7], "dead0beefdead0beefdead0beefdead0beef0001")
        expect("a no-Git project warns instead of failing the proof",
               validate(nogit), "ccc-identity-unverifiable", absent=unresolved)

        # SHA-256: 64-hex OIDs. The old `{7,40}` pattern did not reject these,
        # it silently matched their first 40 characters and compared a
        # truncated string, which is why this rung reads the FULL identity.
        sha256 = build(raw, "sha256", "sha256")
        if sha256 is None:
            print("SKIP: ccc identity sha256 rung -- object-format unsupported")
        else:
            base256 = (sha256 / ".saipen" / "LOG.md").read_text(
                encoding="utf-8-sig").rstrip("\n")
            head256 = commit(sha256, "probe: sha256 pre-ship")
            if len(head256) != 64:
                print("SKIP: ccc identity sha256 rung -- not a 64-hex repository")
            else:
                write_log(sha256, base256, head256[:12], head256)
                expect("a 64-hex OID abbreviated is still one commit",
                       validate(sha256), unchanged)
                ship256 = commit(sha256, "probe: sha256 ship")
                write_log(sha256, base256, head256, ship256)
                expect("distinct 64-hex OIDs are a real revision change",
                       validate(sha256), absent=unchanged)
                expect("the full 64-hex OID resolves rather than truncating",
                       validate(sha256), absent=unresolved)

    return problems, checked


def run_converge_routing_probes() -> tuple[list[str], int]:
    """Execute the T-539 intent-aware routing checks against a real project.

    Scenario 7 (a clean HUNT under `execution_intent: converge` must route to
    CLEAN/finalization, never ADD) and scenario 8 (the normal intent may still
    name ADD) both need a repository whose LOG carries the clean-HUNT marker
    the check reads, so they live here with the hunt-mark probes rather than
    in audit_checks.py, which copies the tree without writing LOG lines.
    """
    problems: list[str] = []
    checked = 0

    def validate(project: Path) -> str:
        r = subprocess.run(
            [sys.executable, str(VALIDATOR), "--project-root", str(project)],
            cwd=project, capture_output=True, text=True, errors="replace")
        return r.stdout + r.stderr

    def expect(label: str, output: str, contains: str = "",
               absent: str = "") -> None:
        nonlocal checked
        checked += 1
        details = []
        if contains and contains not in output:
            details.append(f"missing {contains!r}")
        if absent and absent in output:
            details.append(f"unexpected {absent!r}")
        if details:
            problems.append(f"{label}: {'; '.join(details)}")
        else:
            print(f"PASS: converge routing -- {label}")

    add_fail = "converge clean-HUNT marker present but next_action names ADD"
    valve_fail = "converge safety-valve pause names the goal resume key"

    def write_state(project: Path, intent: str, next_action: str,
                    converge_target: str | None = None) -> None:
        target_line = (f"converge_target: {converge_target}\n"
                       if converge_target else "")
        (project / ".saipen" / "STATE.md").write_text(
            "---\n"
            "phase: PLAN\n"
            "task: none\n"
            f"next_action: {next_action}\n"
            "blocker: none\n"
            "transition_from: INIT\n"
            "saipen_version: 7\n"
            "agent: probe\n"
            "mode: full\n"
            f"execution_intent: {intent}\n"
            f"{target_line}"
            "updated: 2026-01-01T00:00:00Z\n"
            "---\n",
            encoding="utf-8", newline="\n")

    with tempfile.TemporaryDirectory(prefix="saipen-converge-") as raw:
        project = Path(raw) / "project"
        shutil.copytree(SCENARIOS / "stale-state-reconciliation" / ".saipen",
                        project / ".saipen")
        env = {**os.environ, "GIT_AUTHOR_NAME": "probe",
               "GIT_AUTHOR_EMAIL": "probe@example.invalid",
               "GIT_COMMITTER_NAME": "probe",
               "GIT_COMMITTER_EMAIL": "probe@example.invalid"}

        def git(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(["git", *args], cwd=project, env=env,
                                  capture_output=True, text=True, check=False)

        if git("init", "-q").returncode != 0:
            print("SKIP: converge routing probes -- git unavailable")
            return problems, checked
        git("add", "-A")
        git("commit", "-q", "-m", "probe")
        pre_ship_head = git("rev-parse", "HEAD").stdout.strip()

        log_path = project / ".saipen" / "LOG.md"
        base = log_path.read_text(encoding="utf-8-sig").rstrip("\n")

        def write_mark() -> None:
            log_path.write_text(
                f"{base}\n- 26.07.17 00:02 [E-002] [parent: E-001] [T-001] "
                f"RUN: hunt -> clean @dead0be\n",
                encoding="utf-8", newline="\n")

        # Scenario 7 red: converge + clean-HUNT marker + next_action naming ADD
        # FAILs -- ADD is invention, the one thing a converge run never does.
        write_mark()
        write_state(project, "converge", '"PHASE ADD"')
        expect("converge clean-HUNT naming ADD fails", validate(project),
               add_fail)

        # Scenario 7 green: the same state with next_action at CLEAN (stage F
        # destination) must NOT trigger the converge-ADD failure.
        write_state(project, "converge", '"PHASE CLEAN"')
        expect("converge clean-HUNT routing to CLEAN passes",
               validate(project), absent=add_fail)

        # Scenario 8: the normal intent MAY reference ADD -- the routing check
        # is scoped to converge and must not over-fire.
        write_state(project, "normal", '"PHASE ADD"')
        expect("normal intent may still name ADD", validate(project),
               absent=add_fail)

        # Valve wording red: a converge safety-valve pause naming `saipen goal`
        # as its resume key is a substitution, not a continuation.
        write_state(project, "converge",
                    '"WAIT: safety valve reached (N waves / M tickets) -- '
                    "run 'saipen goal' to continue\"")
        expect("converge valve pause naming saipen goal fails",
               validate(project), valve_fail)

        # Valve wording green: the cc form is the legal converge resume.
        write_state(project, "converge",
                    '"WAIT: safety valve reached (N waves / M tickets) -- '
                    "run 'cc' to continue\"")
        expect("converge valve pause naming cc passes",
               validate(project), absent=valve_fail)

        # Scenario 25 red: a persisted ccc route that prepares before its SHIP
        # boundary is rejected even though all event shapes are individually legal.
        log_path.write_text(
            f"{base}\n"
            "- 17.07.26 00:02 [E-002] [parent: E-001] "
            f"DEC: ccc converge target -> ship @{pre_ship_head}\n"
            "- 17.07.26 00:03 [E-003] [parent: E-002] "
            "RUN: prepare saitranslate -> done\n",
            encoding="utf-8", newline="\n")
        write_state(project, "converge", '"PHASE PREPARE"', "ship")
        expect("scenario 25 ccc preparation before SHIP fails",
               validate(project), contains="ccc prepared EE/QQ before SHIP")

        # Green order: SHIP appears before either producer preparation.
        git("commit", "--allow-empty", "-q", "-m", "ccc ship")
        shipped_head = git("rev-parse", "HEAD").stdout.strip()
        log_path.write_text(
            f"{base}\n"
            "- 17.07.26 00:02 [E-002] [parent: E-001] "
            f"DEC: ccc converge target -> ship @{pre_ship_head}\n"
            "- 17.07.26 00:03 [E-003] [parent: E-002] "
            f"RUN: ship v0.0.0 -> pushed {shipped_head}\n"
            "- 17.07.26 00:04 [E-004] [parent: E-003] "
            "RUN: prepare saitranslate -> done\n",
            encoding="utf-8", newline="\n")
        expect("scenario 25 ccc SHIP-before-prepare passes",
               validate(project), absent="ccc prepared EE/QQ before SHIP")

    return problems, checked


def run_role_freshness_probes() -> tuple[list[str], int, int]:
    """Execute T-542/T-543 role and source freshness controls."""
    problems: list[str] = []
    checked = 0
    skipped = 0

    def validate(project: Path) -> str:
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), "--project-root", str(project)],
            cwd=project, capture_output=True, text=True, errors="replace")
        return result.stdout + result.stderr

    def expect(label: str, output: str, contains: str = "",
               absent: str = "") -> None:
        nonlocal checked
        checked += 1
        details = []
        if contains and contains not in output:
            details.append(f"missing {contains!r}")
        if absent and absent in output:
            details.append(f"unexpected {absent!r}")
        if details:
            problems.append(f"{label}: {'; '.join(details)}")
        else:
            print(f"PASS: role/source freshness -- {label}")

    mismatch = "produced under a superseded role"
    stale_warn = "carry an old role_revision"
    fp_fail = "the current tree computes"

    def write_charter(project: Path, behavior: str) -> str:
        directory = project / ".saipen" / "extensions" / "subs"
        directory.mkdir(parents=True, exist_ok=True)
        charter = directory / "saiwiki.md"
        charter.write_text(
            "# saiwiki -- the documenter\n\n"
            "```yaml\n"
            "role_kind: PRODUCER\n"
            "write_scope: .saipen/extensions/subs/saiwiki/\n"
            "trigger: bare saiwiki\n"
            "collect_policy: explicit\n"
            "done_condition: ready\n"
            "freshness_inputs: [source_head, source_tree_fingerprint, role_revision]\n"
            "output_contract: outbox\n"
            "role_revision: sha256:pending\n"
            "```\n\n"
            f"Behavior: {behavior}\n",
            encoding="utf-8", newline="\n")
        revision = compute_role_revision(charter)
        charter.write_text(
            charter.read_text(encoding="utf-8").replace(
                "sha256:pending", revision),
            encoding="utf-8", newline="\n")
        return revision

    def write_sub(project: Path, inst_rev: str, outbox_rev: str,
                  identity: SourceIdentity) -> None:
        sub = project / ".saipen" / "extensions" / "subs" / "saiwiki"
        (sub / "kitchen").mkdir(parents=True, exist_ok=True)
        (sub / "STATE.md").write_text(
            "---\n"
            "phase: DONE\n"
            "task: none\n"
            'next_action: "saipen continue"\n'
            "blocker: none\n"
            "transition_from: SHIP\n"
            "saipen_version: 7\n"
            "agent: saiwiki\n"
            "mode: read-only\n"
            f"role_revision: {inst_rev}\n"
            "updated: 2026-01-01T00:00:00Z\n"
            "---\n",
            encoding="utf-8", newline="\n")
        (sub / "kitchen" / "OUTBOX.md").write_text(
            "# OUTBOX\n\n"
            "## WIKI-900: probe package\n"
            "- **status:** ready\n"
            "- **summary:** probe\n"
            "- **critical:** false\n"
            "- **producer:** saiwiki\n"
            f"- **source_head:** {identity.source_head}\n"
            f"- **source_tree_fingerprint:** {identity.source_tree_fingerprint}\n"
            f"- **role_revision:** {outbox_rev}\n"
            "- **coverage:** probe\n"
            "- **payload:** probe\n"
            "- **verified:** probe\n"
            "- **instructions:** probe\n",
            encoding="utf-8", newline="\n")

    with tempfile.TemporaryDirectory(prefix="saipen-rolefresh-") as raw:
        project = Path(raw) / "project"
        shutil.copytree(SCENARIOS / "stale-state-reconciliation" / ".saipen",
                        project / ".saipen")
        (project / ".gitignore").write_text(
            ".saipen/\n.freebuff/\n.pytest_cache/\n.ruff_cache/\n"
            ".claude/\n*.db\n*-wal\n*-shm\nnul\n",
            encoding="utf-8", newline="\n")
        source = project / "source.txt"
        source.write_text("base\n", encoding="utf-8")
        env = {**os.environ, "GIT_AUTHOR_NAME": "probe",
               "GIT_AUTHOR_EMAIL": "probe@example.invalid",
               "GIT_COMMITTER_NAME": "probe",
               "GIT_COMMITTER_EMAIL": "probe@example.invalid"}

        def git(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(["git", *args], cwd=project, env=env,
                                  capture_output=True, text=True, check=False)

        if git("init", "-q").returncode != 0:
            print("SKIP: role/source freshness probes -- git unavailable")
            return problems, checked, 1
        git("add", "-A")
        git("commit", "-q", "-m", "probe")

        rev1 = write_charter(project, "v1")
        identity = compute_source_identity(project)
        write_sub(project, rev1, rev1, identity)
        expect("matching derived charter+package passes", validate(project),
               absent=mismatch)

        charter = (project / ".saipen" / "extensions" / "subs"
                   / "saiwiki.md")
        charter.write_text(
            charter.read_text(encoding="utf-8").replace(
                "Behavior: v1", "Behavior: v2"),
            encoding="utf-8", newline="\n")
        expect("charter behavior change without revision edit makes package stale",
               validate(project), mismatch)

        rev2 = write_charter(project, "v2")
        charter_bytes = charter.read_bytes()
        charter.write_bytes(charter_bytes.replace(b"\n", b"\r\n"))
        expect("role revision is stable across LF and CRLF checkouts",
               compute_role_revision(charter), contains=rev2)
        charter.write_bytes(charter_bytes)
        identity = compute_source_identity(project)
        write_sub(project, rev1, rev2, identity)
        expect("instance on old derived revision is detected",
               validate(project), stale_warn)

        baseline = compute_source_identity(project)
        source.write_text("tracked dirty\n", encoding="utf-8")
        dirty = compute_source_identity(project)
        expect("tracked dirty source changes fingerprint",
               dirty.source_tree_fingerprint,
               absent=baseline.source_tree_fingerprint)
        source.write_text("base\n", encoding="utf-8")

        untracked = project / "new-source.txt"
        before = compute_source_identity(project)
        untracked.write_text("new\n", encoding="utf-8")
        after = compute_source_identity(project)
        expect("untracked non-ignored source changes fingerprint",
               after.source_tree_fingerprint,
               absent=before.source_tree_fingerprint)
        untracked.unlink()

        # The pre-T-543 concatenation (`path + NUL + content`, repeated) is
        # ambiguous: {a:b, c:d} and {a:empty, bc:d} produce identical bytes.
        # The framed representation must distinguish the two real trees.
        a_path, c_path, bc_path = (project / "a", project / "c", project / "bc")
        a_path.write_bytes(b"b")
        c_path.write_bytes(b"d")
        framed_one = compute_source_identity(project)
        c_path.unlink()
        a_path.write_bytes(b"")
        bc_path.write_bytes(b"d")
        framed_two = compute_source_identity(project)
        legacy_one = b"a\0b" + b"c\0d"
        legacy_two = b"a\0" + b"bc\0d"
        expect("framing separates trees that collide under raw concatenation",
               framed_two.source_tree_fingerprint,
               absent=(framed_one.source_tree_fingerprint
                       if legacy_one == legacy_two else "framing-control-broken"))
        a_path.unlink()
        bc_path.unlink()

        # The delta model is HEAD vs WORKING TREE, so the mode has to change
        # where that model looks -- on disk. `git update-index --chmod` moves
        # the INDEX only, which is how this rung used to measure git's
        # fallback instead of the fingerprint. Whether the host can represent
        # a tracked executable-bit transition is now MEASURED, never assumed
        # from `os.name` or `core.fileMode`: chmod on disk, stat it again,
        # then ask Git for the resulting HEAD-vs-working-tree delta. A
        # filesystem that cannot carry the bit, or a repository whose Git
        # config cannot see it, SKIPs out loud (T-572).
        source_mode = source.stat().st_mode
        try:
            before = compute_source_identity(project)
            os.chmod(source, source_mode | 0o111)
            post_mode = source.stat().st_mode
            delta = git("diff", "--raw", "-z", "--no-renames", "HEAD", "--",
                        "source.txt").stdout
            old_mode = new_mode = None
            for field in delta.split("\0"):
                parts = field.split()
                if field.startswith(":") and len(parts) == 5:
                    old_mode = int(parts[0][1:], 8)
                    new_mode = int(parts[1], 8)
                    break
            represented = (
                (post_mode & 0o111) != (source_mode & 0o111)
                and old_mode is not None
                and (new_mode & 0o111) != (old_mode & 0o111)
            )
            if not represented:
                print("SKIP: role freshness -- this host cannot represent a "
                      "tracked executable-bit transition in the "
                      "HEAD-vs-working-tree delta")
                skipped += 1
            else:
                mode_changed = compute_source_identity(project)
                expect("tracked mode change changes fingerprint",
                       mode_changed.source_tree_fingerprint,
                       absent=before.source_tree_fingerprint)
        finally:
            os.chmod(source, source_mode)

        outside_one = Path(raw) / "outside-one.txt"
        outside_two = Path(raw) / "outside-two.txt"
        outside_one.write_text("one\n", encoding="utf-8")
        outside_two.write_text("one\n", encoding="utf-8")
        if symlinks_available():
            link = project / "outside-link"
            os.symlink(os.path.relpath(outside_one, project), link)
            link_identity = compute_source_identity(project)
            outside_one.write_text("changed outside bytes\n", encoding="utf-8")
            outside_bytes_changed = compute_source_identity(project)
            expect("symlink hashes target text and never outside-root bytes",
                   outside_bytes_changed.source_tree_fingerprint,
                   contains=link_identity.source_tree_fingerprint)
            link.unlink()
            os.symlink(os.path.relpath(outside_two, project), link)
            link_target_changed = compute_source_identity(project)
            expect("symlink target-text change changes fingerprint",
                   link_target_changed.source_tree_fingerprint,
                   absent=link_identity.source_tree_fingerprint)
            link.unlink()
        else:
            print("SKIP: role freshness -- symlink probes need a host that "
                  "can create symlinks (Developer Mode or "
                  "SeCreateSymbolicLinkPrivilege on Windows)")
            skipped += 2

        spaced = project / "with space.txt"
        before = compute_source_identity(project)
        spaced.write_text("space\n", encoding="utf-8")
        after = compute_source_identity(project)
        expect("filename with spaces is fingerprinted",
               after.source_tree_fingerprint,
               absent=before.source_tree_fingerprint)
        spaced.unlink()

        unicode_name = project / "tõstrik-ü.txt"
        before = compute_source_identity(project)
        unicode_name.write_text("üñïçødé\n", encoding="utf-8")
        after = compute_source_identity(project)
        expect("Unicode filename is fingerprinted",
               after.source_tree_fingerprint,
               absent=before.source_tree_fingerprint)
        unicode_name.unlink()

        case_one = project / "CaseDistinct.txt"
        case_two = project / "casedistinct.txt"
        case_one.write_text("upper\n", encoding="utf-8")
        before = compute_source_identity(project)
        holds_case = False
        try:
            case_two.write_text("lower\n", encoding="utf-8")
            holds_case = (case_one.lstat().st_ino != case_two.lstat().st_ino)
        except OSError:
            holds_case = False
        if holds_case:
            after = compute_source_identity(project)
            case_two.unlink()
            mid = compute_source_identity(project)
            expect("case-distinct filenames fingerprint independently",
                   after.source_tree_fingerprint,
                   absent=before.source_tree_fingerprint)
            expect("removing one case-distinct file changes fingerprint",
                   mid.source_tree_fingerprint,
                   absent=after.source_tree_fingerprint)
        else:
            # A case-insensitive host does not raise on the second write -- it
            # silently aliases the first file, so the inode comparison above
            # is the capability test, not the write's success (T-572).
            print("SKIP: role freshness -- host filesystem cannot hold two "
                  "case-distinct filenames simultaneously")
            skipped += 2
        for leftover in (case_one, case_two):
            with contextlib.suppress(OSError):
                leftover.unlink()

        outer = Path(raw) / "outer-repo"
        outer.mkdir()
        inner = outer / "nested-project"
        inner.mkdir()
        (inner / "inner-source.txt").write_text("inner\n", encoding="utf-8")
        if subprocess.run(["git", "init", "-q"], cwd=outer, env=env,
                          capture_output=True, text=True).returncode == 0:
            nested_identity = compute_source_identity(inner)
            expect("nested project inside another git repository uses the "
                   "no-Git discovery model",
                   nested_identity.discovery_model,
                   contains="no-git-tree-v1")
        else:
            print("SKIP: role freshness -- nested-repository probe needs git")
            skipped += 1

        ignored = project / ".freebuff" / "runtime.db"
        ignored.parent.mkdir(parents=True, exist_ok=True)
        before = compute_source_identity(project)
        ignored.write_text("one\n", encoding="utf-8")
        ignored.write_text("two\n", encoding="utf-8")
        after = compute_source_identity(project)
        expect("ignored runtime mutation does not change fingerprint",
               after.source_tree_fingerprint,
               contains=before.source_tree_fingerprint)

        original_run_git = freshness._run_git
        head_reads = 0

        def moving_head(root: Path, *args: str) -> bytes:
            nonlocal head_reads
            result = original_run_git(root, *args)
            if args[:2] == ("rev-parse", "--verify") and args[2:] == ("HEAD",):
                head_reads += 1
                if head_reads == 2:
                    return b"f" * 40 + b"\n"
            return result

        try:
            with mock.patch.object(freshness, "_run_git", side_effect=moving_head):
                compute_source_identity(project)
        except FreshnessError:
            expect("HEAD movement during computation fails", "failed",
                   contains="failed")
        else:
            expect("HEAD movement during computation fails", "passed",
                   contains="failed")

        noise = project / ".saipen" / "kitchen" / "producer-noise.txt"
        noise.parent.mkdir(parents=True, exist_ok=True)
        noise.write_text("baseline\n", encoding="utf-8")
        git("add", "-f", ".saipen/kitchen/producer-noise.txt")
        git("commit", "-q", "-m", "tracked producer noise")
        before = compute_source_identity(project)
        noise.write_text("checkpoint\n", encoding="utf-8")
        after = compute_source_identity(project)
        expect("tracked .saipen bookkeeping mutation does not change fingerprint",
               after.source_tree_fingerprint,
               contains=before.source_tree_fingerprint)

        original_parse_delta = freshness._parse_git_delta
        parse_reads = 0

        def mutate_after_second_read(root: Path, raw_delta: bytes,
                                     raw_untracked: bytes):
            nonlocal parse_reads
            records = original_parse_delta(root, raw_delta, raw_untracked)
            parse_reads += 1
            if parse_reads == 2:
                source.write_text("raced after second read\n", encoding="utf-8")
            return records

        try:
            with mock.patch.object(freshness, "_parse_git_delta",
                                   side_effect=mutate_after_second_read):
                compute_source_identity(project)
        except FreshnessError:
            expect("content race after second sample fails", "failed",
                   contains="failed")
        else:
            expect("content race after second sample fails", "passed",
                   contains="failed")
        source.write_text("base\n", encoding="utf-8")

        before = compute_source_identity(project)
        source.unlink()
        after = compute_source_identity(project)
        expect("tracked source deletion changes fingerprint",
               after.source_tree_fingerprint,
               absent=before.source_tree_fingerprint)
        source.write_text("base\n", encoding="utf-8")

        before = compute_source_identity(project)
        renamed = project / "renamed-source.txt"
        source.rename(renamed)
        after = compute_source_identity(project)
        expect("source rename changes fingerprint",
               after.source_tree_fingerprint,
               absent=before.source_tree_fingerprint)
        renamed.rename(source)

        source.write_text("unreadable probe\n", encoding="utf-8")
        try:
            with mock.patch.object(
                    freshness.os, "read",
                    side_effect=PermissionError("probe unreadable")):
                compute_source_identity(project)
        except FreshnessError:
            expect("unreadable required input fails computation", "failed",
                   contains="failed")
        else:
            expect("unreadable required input fails computation", "passed",
                   contains="failed")
        source.write_text("base\n", encoding="utf-8")

        identity = compute_source_identity(project)
        write_sub(project, rev2, rev2, identity)
        expect("package bound to current source passes",
               validate(project), absent=fp_fail)

        generic_protocol = (project / ".saipen" / "extensions" / "subs"
                            / "PROTOCOL.md")
        generic_protocol.write_text("generic contract v1\n", encoding="utf-8")
        generic_revision = compute_generic_role_revision(generic_protocol)
        generic_identity = compute_source_identity(project)
        write_sub(project, generic_revision, generic_revision, generic_identity)
        generic_outbox = (project / ".saipen" / "extensions" / "subs"
                          / "saiwiki" / "kitchen" / "OUTBOX.md")
        generic_outbox.write_text(
            generic_outbox.read_text(encoding="utf-8").replace(
                "- **producer:** saiwiki", "- **producer:** saicustom"),
            encoding="utf-8", newline="\n")
        expect("generic role binds to its governing PROTOCOL digest",
               validate(project), absent=mismatch)
        generic_protocol.write_text("generic contract v2\n", encoding="utf-8")
        expect("generic role contract change makes package stale",
               validate(project), contains=mismatch)
        generic_protocol.unlink()
        identity = compute_source_identity(project)
        write_sub(project, rev2, rev2, identity)

        source.write_text("final mutation\n", encoding="utf-8")
        expect("package produced before final source mutation is stale",
               validate(project), fp_fail)

        source.write_text("base\n", encoding="utf-8")
        identity = compute_source_identity(project)
        write_sub(project, rev2, rev2, identity)
        noise.write_text("post-package producer noise\n", encoding="utf-8")
        expect("producer noise after package creation stays fresh",
               validate(project), absent=fp_fail)

        git("commit", "--allow-empty", "-q", "-m", "head-only movement")
        expect("package with old source_head is stale even when delta matches",
               validate(project), contains="current source_head")

        try:
            with mock.patch.object(
                    freshness.subprocess, "run",
                    side_effect=FileNotFoundError("probe git unavailable")):
                compute_source_identity(project)
        except FreshnessError:
            expect("Git discovery failure cannot degrade to no-Git", "failed",
                   contains="failed")
        else:
            expect("Git discovery failure cannot degrade to no-Git", "passed",
                   contains="failed")

        no_git = Path(raw) / "no-git-project"
        no_git.mkdir()
        no_git_source = no_git / "source.txt"
        no_git_source.write_text("source\n", encoding="utf-8")
        named_like_runtime = no_git / "node_modules"
        before_named_file = compute_source_identity(no_git)
        named_like_runtime.write_text("real source file\n", encoding="utf-8")
        after_named_file = compute_source_identity(no_git)
        expect("no-Git runtime names exclude directories, not files",
               after_named_file.source_tree_fingerprint,
               absent=before_named_file.source_tree_fingerprint)
        no_git_before = compute_source_identity(no_git)
        no_git_noise = no_git / ".freebuff" / "runtime.db"
        no_git_noise.parent.mkdir()
        no_git_noise.write_text("one\n", encoding="utf-8")
        no_git_noise.write_text("two\n", encoding="utf-8")
        no_git_after = compute_source_identity(no_git)
        expect("no-Git fallback uses its explicit runtime exclusions",
               no_git_after.source_tree_fingerprint,
               contains=no_git_before.source_tree_fingerprint)

        # A FIFO is unsupported fingerprint input. Only the no-Git walk
        # enumerates every directory entry (scandir), so it is the model that
        # actually meets the object; the Git-delta model never sees it because
        # `git ls-files --others` does not report one -- CI measured that
        # (T-572), so the probe lives against the walk that raises.
        if hasattr(os, "mkfifo"):
            fifo = no_git / "pipe.fifo"
            os.mkfifo(fifo)
            try:
                compute_source_identity(no_git)
            except FreshnessError:
                expect("unsupported filesystem object fails computation",
                       "failed", contains="failed")
            else:
                expect("unsupported filesystem object fails computation",
                       "passed", contains="failed")
            finally:
                fifo.unlink()
        else:
            print("SKIP: role freshness -- FIFO probe needs a POSIX host "
                  "(os.mkfifo unavailable)")
            skipped += 1

        no_git_exec = no_git / "script.sh"
        no_git_exec.write_text("#!/bin/sh\n", encoding="utf-8")
        exec_mode = no_git_exec.stat().st_mode
        try:
            os.chmod(no_git_exec, exec_mode | 0o111)
            post_mode = no_git_exec.stat().st_mode
            if (post_mode & 0o111) != (exec_mode & 0o111):
                no_git_exec_before = compute_source_identity(no_git)
                os.chmod(no_git_exec, exec_mode)
                no_git_exec_after = compute_source_identity(no_git)
                expect("no-Git executable-bit change changes fingerprint",
                       no_git_exec_after.source_tree_fingerprint,
                       absent=no_git_exec_before.source_tree_fingerprint)
            else:
                print("SKIP: role freshness -- host cannot express an "
                      "executable bit in the no-Git discovery model")
                skipped += 1
        finally:
            os.chmod(no_git_exec, exec_mode)
        no_git_exec.unlink()

        if junctions_available():
            junction_outside = Path(raw) / "junction-outside"
            junction_outside.mkdir()
            (junction_outside / "content.txt").write_text(
                "v1\n", encoding="utf-8")
            junction = no_git / "junction-dir"
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J",
                 os.fspath(junction), os.fspath(junction_outside)],
                capture_output=True, text=True, errors="replace")
            if result.returncode == 0 and junction.exists():
                j_before = compute_source_identity(no_git)
                (junction_outside / "content.txt").write_text(
                    "v2\n", encoding="utf-8")
                j_after = compute_source_identity(no_git)
                expect("no-Git walk hashes a junction as link identity and "
                       "never recurses outside the root",
                       j_after.source_tree_fingerprint,
                       contains=j_before.source_tree_fingerprint)
                junction.rmdir()
            else:
                print("SKIP: role freshness -- mklink /J failed despite the "
                      "capability probe")
                skipped += 1
        else:
            print("SKIP: role freshness -- junction probe needs a Windows "
                  "host able to create junctions (cmd mklink /J)")
            skipped += 1

    return problems, checked, skipped


def run_sub_clean_probes() -> tuple[list[str], int, int]:
    """Execute T-545 evidence-gated cleanup controls (scenarios 22-24)."""
    problems: list[str] = []
    checked = 0
    skipped = 0

    def expect(label: str, blockers: tuple[str, ...], contains: str = "",
               empty: bool = False) -> None:
        nonlocal checked
        checked += 1
        joined = "\n".join(blockers)
        failed = (empty and bool(blockers)) or (contains and contains not in joined)
        if failed:
            problems.append(f"{label}: blockers={blockers!r}")
        else:
            print(f"PASS: sub-clean safety -- {label}")

    with tempfile.TemporaryDirectory(prefix="saipen-sub-clean-") as raw:
        instance = (Path(raw) / ".saipen" / "extensions" / "subs"
                    / "saiwiki")
        kitchen = instance / "kitchen"
        kitchen.mkdir(parents=True)
        board = instance / "BOARD.md"
        board.write_text(
            "# Board\n## DOING\n## TODO\n## DONE\n## BLOCKED\n",
            encoding="utf-8", newline="\n")
        outbox = kitchen / "OUTBOX.md"
        outbox.write_text(
            "# OUTBOX\n\n## WIKI-001: history\n"
            "- **status:** reviewed\n",
            encoding="utf-8", newline="\n")

        expect("reviewed history alone permits cleanup",
               sub_clean_blockers(instance), empty=True)
        cli = subprocess.run(
            [sys.executable, str(HOME / "tools" / "sub_clean.py"), "saiwiki"],
            cwd=raw, capture_output=True, text=True, errors="replace")
        expect("bare sub name resolves from project root",
               () if cli.returncode == 0 else (cli.stdout + cli.stderr,),
               empty=True)

        board.unlink()
        expect("missing BOARD fails closed", sub_clean_blockers(instance),
               contains="missing lifecycle evidence: BOARD.md")
        board.write_text(
            "# Board\n## DOING\n## TODO\n## DONE\n## BLOCKED\n",
            encoding="utf-8", newline="\n")
        board.write_text(
            "# Board\n## DOING\n## TOOD\n## DONE\n## BLOCKED\n",
            encoding="utf-8", newline="\n")
        expect("malformed BOARD fails closed", sub_clean_blockers(instance),
               contains="malformed BOARD sections")
        board.write_text(
            "# Board\n## DOING\n## TODO\n## DONE\n"
            "- [ ] SUB-OLD wrong state\n## BLOCKED\n",
            encoding="utf-8", newline="\n")
        expect("section-checkbox mismatch fails closed",
               sub_clean_blockers(instance), contains="malformed DONE item state")
        board.write_text(
            "# Board\n## DOING\n## TODO\n  - [ ] SUB-HIDDEN indented\n"
            "## DONE\n## BLOCKED\n",
            encoding="utf-8", newline="\n")
        expect("indented BOARD ticket fails closed",
               sub_clean_blockers(instance),
               contains="malformed BOARD item indentation")
        board.write_text(
            "# Board\n## DOING\n## TODO\n## DONE\n## BLOCKED\n",
            encoding="utf-8", newline="\n")

        outbox.unlink()
        expect("missing OUTBOX fails closed", sub_clean_blockers(instance),
               contains="missing lifecycle evidence: kitchen/OUTBOX.md")
        outbox.write_text(
            "# OUTBOX\n\n## WIKI-001: history\n"
            "- **status:** reviewed\n",
            encoding="utf-8", newline="\n")
        outbox.write_text(
            "# OUTBOX\n\npackage text with no entry or status\n",
            encoding="utf-8", newline="\n")
        expect("nonempty unparseable OUTBOX fails closed",
               sub_clean_blockers(instance),
               contains="nonempty OUTBOX has no valid package entry")
        outbox.write_text(
            "# OUTBOX\n\n## WIKI-001: history\n",
            encoding="utf-8", newline="\n")
        expect("OUTBOX entry without status fails closed",
               sub_clean_blockers(instance), contains="0 status fields")
        outbox.write_text(
            "# OUTBOX\n\n## WIKI-001: history\n"
            "<!-- - **status:** reviewed -->\n"
            "```markdown\n- **status:** reviewed\n## WIKI-999: fake\n```\n",
            encoding="utf-8", newline="\n")
        expect("commented or fenced status cannot authorize cleanup",
               sub_clean_blockers(instance), contains="0 status fields")
        outbox.write_text(
            "# OUTBOX\n\n## WIKI-001: history\n"
            "    - **status:** reviewed\n",
            encoding="utf-8", newline="\n")
        expect("indented-code status cannot authorize cleanup",
               sub_clean_blockers(instance), contains="0 status fields")
        outbox.write_text(
            "# OUTBOX\n\n## WIKI-001: history\n"
            "- **status:** reviewed\n### Wiki-X: hidden\n",
            encoding="utf-8", newline="\n")
        expect("malformed mixed-case entry heading fails closed",
               sub_clean_blockers(instance),
               contains="malformed OUTBOX entry heading")
        outbox.write_text(
            "# OUTBOX\n\n## WIKI-001: history\n<!-- open\n"
            "- **status:** reviewed\n",
            encoding="utf-8", newline="\n")
        expect("unclosed OUTBOX comment fails closed",
               sub_clean_blockers(instance), contains="unclosed HTML comment")
        outbox.write_text(
            "# OUTBOX\n\n## WIKI-001: history\n````markdown\n"
            "- **status:** reviewed\n```\n",
            encoding="utf-8", newline="\n")
        expect("unclosed long OUTBOX fence fails closed",
               sub_clean_blockers(instance), contains="unclosed fenced block")

        outbox.write_text(
            "# OUTBOX\n\n## WIKI-002: package\n"
            "- **status:** ready\n",
            encoding="utf-8", newline="\n")
        expect("scenario 22 ready-unreviewed OUTBOX blocks cleanup",
               sub_clean_blockers(instance), contains="OUTBOX status ready")

        outbox.write_text("# OUTBOX\n", encoding="utf-8", newline="\n")
        old = 946684800
        os.utime(instance, (old, old))
        os.utime(board, (old, old))
        os.utime(outbox, (old, old))
        expect("scenario 23 elapsed time alone cannot delete or block",
               sub_clean_blockers(instance), empty=True)

        (instance / "LOG.md").write_text(
            "# Log\n- collect 1\n- collect 2\n- collect 3\n",
            encoding="utf-8", newline="\n")
        expect("scenario 24 repeated collects do not make history stale",
               sub_clean_blockers(instance), empty=True)

        board.write_text(
            "# Board\n## DOING\n## TODO\n- [ ] SUB-001 open\n"
            "## DONE\n## BLOCKED\n",
            encoding="utf-8", newline="\n")
        expect("open TODO blocks cleanup", sub_clean_blockers(instance),
               contains="TODO: SUB-001 open")
        board.write_text(
            "# Board\n## DOING\n## TODO\n## DONE\n## BLOCKED\n",
            encoding="utf-8", newline="\n")

        nested_outbox = kitchen / "pending" / "OUTBOX.md"
        nested_outbox.parent.mkdir()
        nested_outbox.write_text("payload\n", encoding="utf-8", newline="\n")
        expect("nested OUTBOX is an artifact, not the root exemption",
               sub_clean_blockers(instance), contains="pending/OUTBOX.md")
        nested_outbox.unlink()
        nested_outbox.parent.rmdir()

        patch = kitchen / "pending.patch"
        patch.write_text("diff\n", encoding="utf-8", newline="\n")
        expect("unacknowledged patch blocks cleanup",
               sub_clean_blockers(instance), contains="pending.patch")
        patch.unlink()

        recovery = instance / "recovery" / "STATE.md"
        recovery.parent.mkdir()
        recovery.write_text("evidence\n", encoding="utf-8", newline="\n")
        expect("unpreserved recovery evidence blocks cleanup",
               sub_clean_blockers(instance), contains="recovery/STATE.md")
        preserved = Path(raw) / "preserved"
        preserved.mkdir()
        (preserved / "STATE.md").write_text(
            "evidence\n", encoding="utf-8", newline="\n")
        expect("byte-preserved recovery evidence permits cleanup",
               sub_clean_blockers(instance, preserved), empty=True)

        if symlinks_available():
            recovery.unlink()
            os.symlink(os.fspath(preserved / "STATE.md"), recovery)
            blockers = sub_clean_blockers(instance, preserved)
            expect("symlink recovery evidence is rejected even when its "
                   "target content matches preserved bytes",
                   blockers, contains="non-preserved recovery evidence")
            recovery.unlink()
            recovery.write_text("evidence\n", encoding="utf-8", newline="\n")

            outside_ev = Path(raw) / "outside-recovery-dir"
            outside_ev.mkdir()
            (outside_ev / "hidden.txt").write_text(
                "hidden\n", encoding="utf-8", newline="\n")
            sublink = instance / "recovery" / "sublink"
            sublink.symlink_to(outside_ev, target_is_directory=True)
            blockers = sub_clean_blockers(instance, preserved)
            expect("directory symlink under recovery is never recursed",
                   blockers, contains="non-preserved recovery evidence")
            sublink.unlink()

            os.rename(instance / "recovery", instance / "recovery-real")
            os.symlink(os.fspath(preserved), instance / "recovery")
            blockers = sub_clean_blockers(instance, preserved)
            expect("a recovery dir that is itself a symlink is rejected",
                   blockers, contains="non-preserved recovery evidence")
            (instance / "recovery").unlink()
            os.rename(instance / "recovery-real", instance / "recovery")
        else:
            print("SKIP: sub-clean safety -- symlink probes need a host that "
                  "can create symlinks (Developer Mode or "
                  "SeCreateSymbolicLinkPrivilege on Windows)")
            skipped += 3

        if junctions_available():
            real_ev = Path(raw) / "junction-evidence"
            real_ev.mkdir()
            (real_ev / "hidden.txt").write_text(
                "hidden\n", encoding="utf-8", newline="\n")
            junction = instance / "recovery" / "junction-link"
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J",
                 os.fspath(junction), os.fspath(real_ev)],
                capture_output=True, text=True, errors="replace")
            if result.returncode == 0 and junction.exists():
                blockers = sub_clean_blockers(instance, preserved)
                expect("directory junction is never recursed and is rejected",
                       blockers, contains="non-preserved recovery evidence")
                junction.rmdir()
            else:
                print("SKIP: sub-clean safety -- mklink /J failed on this "
                      "host despite the capability probe")
                skipped += 1
        else:
            print("SKIP: sub-clean safety -- junction probe needs a Windows "
                  "host able to create junctions (cmd mklink /J); a Linux "
                  "symlink test is not proof of junction behavior")
            skipped += 1

    return problems, checked, skipped


def run_hardening_control_inventory() -> tuple[list[str], int]:
    """Prove all 30 hardening red controls resolve to executable evidence.

    `hardening_controls.json` is platform-independent data -- every owner is a
    plain repository-relative file path and every anchor is plain text with no
    platform branch -- and the checks below prove that shape mechanically, so
    a future entry cannot quietly make the registry platform-conditional.
    """
    problems: list[str] = []
    checked = 0
    registry_path = HOME / "tools" / "hardening_controls.json"
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"hardening control registry unreadable: {exc}"], 0
    if not isinstance(registry, list):
        return [f"hardening control registry must be a JSON list, got "
                f"{type(registry).__name__}"], 0
    expected_keys = {"id", "name", "owner", "anchor"}
    seen_names: set[str] = set()
    seen_anchors: set[str] = set()
    ids = []
    for index, entry in enumerate(registry, 1):
        if not isinstance(entry, dict):
            return [f"hardening control #{index} is not a JSON object"], index - 1
        if set(entry) != expected_keys:
            return [f"hardening control #{index} keys are {sorted(entry)!r}, "
                    f"expected {sorted(expected_keys)}"], index - 1
        name = entry["name"]
        if not isinstance(name, str) or not name:
            return [f"hardening control #{index} has an empty name"], index - 1
        if name in seen_names:
            return [f"hardening control names are not unique: {name!r}"], index - 1
        seen_names.add(name)
        owner = entry["owner"]
        if (not isinstance(owner, str) or not owner
                or "\\" in owner or owner.startswith("/")
                or owner.startswith(".") or ".." in owner.split("/")):
            return [f"hardening control #{index} owner is not a canonical "
                    f"repository-relative path: {owner!r}"], index - 1
        anchor = entry["anchor"]
        if not isinstance(anchor, str) or not anchor:
            return [f"hardening control #{index} has an empty anchor"], index - 1
        if anchor in seen_anchors:
            return [f"hardening control #{index} anchor {anchor!r} is not "
                    f"unique -- the anchor resolves ambiguously"], index - 1
        seen_anchors.add(anchor)
        ids.append(entry["id"])
    if len(set(ids)) != len(ids):
        return ["hardening control IDs are not unique"], len(registry)
    if ids != list(range(1, len(registry) + 1)):
        return [f"hardening control IDs are {ids!r}, expected "
                f"1..{len(registry)} in order"], len(registry)
    for entry in registry:
        checked += 1
        owner = HOME / entry["owner"]
        if not owner.is_file():
            problems.append(
                f"control {entry['id']} owner is not a file: {entry['owner']}")
            continue
        try:
            source = owner.read_text(encoding="utf-8-sig")
        except OSError as exc:
            problems.append(f"control {entry['id']} owner unreadable: {exc}")
            continue
        if entry["anchor"] not in source:
            problems.append(
                f"control {entry['id']} {entry['name']}: anchor "
                f"{entry['anchor']!r} missing from {entry['owner']}"
            )
        else:
            print(f"PASS: hardening control {entry['id']:02d} -- "
                  f"{entry['name']} -> {entry['owner']}")
    print("hardening_controls.json is platform-independent data: every owner "
          "is a repository-relative file path and every anchor is plain text "
          "with no platform branch")
    return problems, checked


def run_userperson_probes() -> tuple[list[str], int]:
    """T-574 + T-577: the optional USERPERSON profile mechanics.

    The profile is OFF by default -- absence is silent (verified against the
    validator's own output on this very tree, which carries no USERPERSON
    file). Preference identity is STRUCTURED (category + exact text) and the
    merge is deterministic lexical dedup -- never a claim of understanding
    natural-language semantics. Red controls cover the false-equivalence that
    shipped in v7.217.0 (a leading-phrase split silently discarded a distinct
    "Prefer UI: Material Design" beside "Prefer UI: Vintage Golden") and the
    false-negative case (differently-worded but equivalent preferences are
    NOT merged by the helper; the agent distills semantics before writing).
    Projections select actual preferences by category policy and return an
    auditable handoff -- a short scope string is not a projection.
    """
    problems: list[str] = []
    checked = 0

    def expect(label: str, ok: bool, detail: str = "") -> None:
        nonlocal checked
        checked += 1
        if not ok:
            problems.append(f"{label}: {detail}")
        else:
            print(f"PASS: userperson -- {label}")

    # Red control: false equivalence. Two distinct UI preferences sharing a
    # leading phrase must BOTH survive -- the v7.217.0 bug discarded the second.
    merged = merge_profile(
        ["- [UI] Vintage Golden"],
        ["- [UI] Material Design", "- [UI] Vintage Golden"])
    expect("distinct preferences sharing a leading phrase are both kept",
           len(merged) == 2
           and {e["text"] for e in merged} == {"Vintage Golden",
                                               "Material Design"},
           repr(merged))

    # Red control: false negative. Semantically-equivalent but lexically
    # different preferences are NOT merged by the helper -- semantic
    # distillation is the agent's job, recorded as such (T-577).
    dist = merge_profile(
        ["- [Automation] Prefer safe autonomous continuation"],
        ["- [Automation] Automate continuation safely where reversible"])
    expect("helper never fabricates semantic equivalence between wordings",
           len(dist) == 2, repr(dist))

    # Exact-duplicate dedup is deterministic and safe.
    dedup = merge_profile(
        ["- [Automation] avoid repetitive continue"],
        ["- [Automation] avoid repetitive continue"])
    expect("exact duplicate (same category, same text) is deduplicated",
           len(dedup) == 1, repr(dedup))

    removed = remove_preference(merged, "Material Design")
    expect("remove drops the matching preference",
           len(removed) == 1 and removed[0]["text"] == "Vintage Golden",
           repr(removed))

    rendered = render_profile(merged)
    parsed = parse_profile(rendered)["preferences"]
    expect("render/parse round-trips",
           [(e["category"], e["text"]) for e in parsed]
           == [(e["category"], e["text"]) for e in merged],
           repr(parsed))

    expect("validate accepts a well-formed profile",
           validate_profile(rendered) == [],
           repr(validate_profile(rendered)))
    malformed = "# USERPERSON\n\n- [UI] good preference\nnot-a-bullet\n"
    errs = validate_profile(malformed)
    expect("validate flags a non-bullet line",
           any("markdown bullet" in e for e in errs), repr(errs))
    dup = render_profile(["- [UI] Same leading phrase here.",
                          "- [UI] Same leading phrase here."])
    expect("validate flags exact duplicate history",
           any("duplicate" in e for e in validate_profile(dup)),
           repr(validate_profile(dup)))

    expect("onboarding asks at most three broad questions",
           1 <= len(onboarding_questions()) <= 3,
           repr(onboarding_questions()))

    # Real projection behavior: the helper SELECTS preferences by category
    # policy. A short scope string is not evidence of projection (T-577).
    profile = [
        {"id": "p1", "category": "UI", "text": "Vintage Golden"},
        {"id": "p2", "category": "Language", "text": "Russian explanations"},
        {"id": "p3", "category": "Automation",
         "text": "avoid repetitive continue"},
        {"id": "p4", "category": "Localization", "text": "multilingual-first"},
    ]
    ui = project_profile(profile, "saiui", source_fingerprint="fp123")
    expect("saiui projection selects UI/workflow preferences only",
           [e["text"] for e in ui["preferences"]] == ["Vintage Golden"],
           repr(ui))
    tr = project_profile(profile, "saitranslate", source_fingerprint="fp123")
    expect("saitranslate projection selects localization/language only",
           {e["category"] for e in tr["preferences"]} == {"Language",
                                                          "Localization"},
           repr(tr))
    ht = project_profile(profile, "saihunt", source_fingerprint="fp123")
    expect("saihunt projection excludes UI baggage unless relevant",
           all(e["category"] != "UI" for e in ht["preferences"]),
           repr(ht))
    expect("projection never dumps the whole profile",
           all(len(project_profile(profile, role, "fp")["preferences"])
               < len(profile)
               for role in ("saiui", "saitranslate", "saiwiki", "saihunt")))
    expect("projection handoff carries the source fingerprint",
           ui["source_fingerprint"] == "fp123"
           and ui["projection_policy"] == sorted(["ui", "workflow"]),
           repr(ui))

    core = (HOME / "saipen" / "CORE.md").read_text(encoding="utf-8-sig")
    expect("CORE.md 1.10 documents both report traces",
           "USERPERSON alignment:" in core and "USERPERSON deviation:" in core)
    expect("CORE.md 1.10 documents the precedence chain",
           "current explicit request > project/task requirements > SAIPEN > "
           "verified evidence > USERPERSON" in core)

    return problems, checked


def run_improve_probes() -> tuple[list[str], int]:
    """T-551/T-555/T-556/T-570: the Improve mechanical core.

    The semantics live in saipen/IMPROVE.md; these probes prove the mechanical
    layer: canonical report paths that never touch the shared protocol
    install, one path per seat per cycle, report schema validation with closed
    vocabularies and the mandatory expected/actual/evidence triple, the
    derived status (roster + report + sweep, one fact one owner), and the
    Core-owned SWEEP ledger that never mutates the seat report.
    """
    problems: list[str] = []
    checked = 0

    def expect(label: str, ok: bool, detail: str = "") -> None:
        nonlocal checked
        checked += 1
        if not ok:
            problems.append(f"{label}: {detail}")
        else:
            print(f"PASS: improve -- {label}")

    root = Path(tempfile.mkdtemp(prefix="saipen-improve-"))
    p1 = resolve_report_path(root, "imp-key-20260808", "opencode-01", "PROJ")
    p2 = resolve_report_path(root, "imp-key-20260808", "opencode-02", "PROJ")
    p3 = resolve_report_path(root, "imp-key-20260809", "opencode-01", "PROJ")
    expect("report path lives under project .saipen/improve, never saipen_home",
           p1.is_relative_to(root / ".saipen" / "improve"), str(p1))
    expect("two distinct seats resolve to different report paths",
           p1 != p2, f"{p1} vs {p2}")
    expect("same seat in a different cycle resolves to a different path",
           p1 != p3, f"{p1} vs {p3}")
    expect("requested basename is preserved exactly",
           p1.name == "saipen_improve_PROJ.md", p1.name)

    good = (
        "agent: opencode-01\nrole: core\nmodel_or_runtime: probe\n"
        "project: PROJ\nsaipen_version: 7.218.0\n"
        "protocol_fingerprint: deadbeef\nsource_head: abc\n"
        "source_tree_fingerprint: beef\ncontext_scope: tools/improve.py\n"
        "context_available: complete\nreport_status: draft\n\n"
        "IMP-001 [P1] [PROTOCOL_VIOLATION] [observed] [ticket]\n"
        "expected: reports under .saipen/improve\nactual: report in root\n"
        "evidence: path p\n")
    expect("a well-formed report validates",
           validate_report(good) == [], repr(validate_report(good)))
    bad = good.replace("evidence: path p\n", "")
    expect("a finding without evidence is rejected",
           any("expected/actual/evidence" in e
               for e in validate_report(bad)),
           repr(validate_report(bad)))
    bad2 = good.replace("[PROTOCOL_VIOLATION]", "[MAGIC]")
    expect("a class outside the closed set is rejected",
           any("outside the closed set" in e
               for e in validate_report(bad2)),
           repr(validate_report(bad2)))
    bad3 = good.replace("context_scope: tools/improve.py", "context_scope: ")
    expect("context_available complete over an empty scope is refused",
           any("context_available: complete" in e
               for e in validate_report(bad3)),
           repr(validate_report(bad3)))

    roster = "cycle_id: imp-key-20260808\navailability: expected\n"
    sweep = "# SWEEP\n- IMP-001 [CONFIRMED] T-900 report=seat/report.md "\
            "reproduced=y\n"
    expect("derived status: roster-only is expected",
           derive_status("seat/report.md", roster, "", "")["visible"]
           == "expected")
    expect("derived status: report draft is draft",
           derive_status("seat/report.md", roster, "report_status: draft\n",
                         "")["visible"] == "draft")
    expect("derived status: complete without sweep is complete",
           derive_status("seat/report.md", roster,
                         "report_status: complete\n", "")["visible"]
           == "complete")
    expect("derived status: swept after disposition coverage",
           derive_status("seat/report.md", roster,
                         "report_status: complete\n", sweep)["visible"]
           == "swept")
    expect("derived status: unavailable roster wins",
           derive_status("seat/report.md", "availability: unavailable\n",
                         "report_status: complete\n", sweep)["visible"]
           == "unavailable")

    cycle = Path(tempfile.mkdtemp(prefix="saipen-sweep-"))
    report = cycle / "seat" / "saipen_improve_PROJ.md"
    report.parent.mkdir(parents=True)
    report.write_text(good, encoding="utf-8")
    before = report.read_bytes()
    write_sweep_entry(cycle, {"imp_id": "001", "disposition": "CONFIRMED",
                              "ticket": "T-900", "report": "r",
                              "reproduced": "y"})
    expect("SWEEP ledger write never mutates the seat report",
           report.read_bytes() == before)
    expect("SWEEP ledger exists with the disposition",
           (cycle / "SWEEP.md").is_file()
           and "CONFIRMED" in (cycle / "SWEEP.md").read_text(encoding="utf-8"))

    # Cycle/seat admission: deterministic, collision-safe (T-570).
    proot = Path(tempfile.mkdtemp(prefix="saipen-cycle-"))
    c1 = register_cycle(proot, "imp-key-20260808", "cycle_id: imp-key-20260808\n")
    try:
        register_cycle(proot, "imp-key-20260808", "")
        dup_cycle = False
    except FileExistsError:
        dup_cycle = True
    expect("a second cycle with the same id is refused, not duplicated",
           dup_cycle)
    expect("cycle creation writes the roster atomically",
           (c1 / "MANIFEST.md").is_file()
           and "imp-key-20260808" in (c1 / "MANIFEST.md").read_text(
               encoding="utf-8"))
    rp = "saipen_improve_PROJ.md"
    register_seat(c1, "opencode-01", "core", rp)
    try:
        register_seat(c1, "opencode-01", "core", rp)
        dup_seat = False
    except ValueError:
        dup_seat = True
    expect("duplicate seat registration fails",
           dup_seat and (c1 / "MANIFEST.md").read_text(
               encoding="utf-8").count("seat_id: opencode-01") == 1)
    try:
        register_seat(c1, "opencode-02", "core", rp, availability="yolo")
        bad_avail = False
    except ValueError:
        bad_avail = True
    expect("a roster availability outside the closed set is rejected",
           bad_avail)

    # RUN append is immutable: a second run appends, never overwrites; a
    # complete report refuses further RUNs (T-551).
    seat_report = Path(tempfile.mkdtemp(prefix="saipen-run-")) / "r.md"
    seat_report.write_text(
        "report_status: draft\n\n## RUN 1\nfirst\n", encoding="utf-8")
    append_run(seat_report, "second run")
    after = seat_report.read_text(encoding="utf-8")
    expect("a second run appends an immutable RUN section, never overwriting",
           "## RUN 1" in after and "## RUN 2" in after
           and "first" in after and "second run" in after)
    append_run(seat_report, "third run")
    after2 = seat_report.read_text(encoding="utf-8")
    expect("multiple RUNs accumulate without overwriting earlier ones",
           "## RUN 1" in after2 and "## RUN 2" in after2
           and "## RUN 3" in after2)
    completed = seat_report.read_text(encoding="utf-8").replace(
        "report_status: draft", "report_status: complete")
    seat_report.write_text(completed, encoding="utf-8")
    try:
        append_run(seat_report, "late run")
        immutable = False
    except ValueError:
        immutable = True
    expect("a complete report refuses further RUN sections", immutable)

    return problems, checked


def run_nitro_probes() -> tuple[list[str], int]:
    """NITRO M1 (T-578): the shared mechanical parsers, snapshot, and the
    read-only saipen status/next commands.

    The parsers are the SAME implementation validate.py imports; these probes
    prove the engine consumes them correctly and that the snapshot detects a
    stale precondition.
    """
    problems: list[str] = []
    checked = 0

    def expect(label: str, ok: bool, detail: str = "") -> None:
        nonlocal checked
        checked += 1
        if not ok:
            problems.append(f"{label}: {detail}")
        else:
            print(f"PASS: nitro -- {label}")

    state_text = (HOME / ".saipen" / "STATE.md").read_text(
        encoding="utf-8-sig")
    fields, err = parse_frontmatter(state_text)
    expect("frontmatter parses the live STATE",
           err is None and fields.get("phase") in (
               "SCOUT", "BUILD", "VERIFY", "REVIEW", "SHIP", "DONE"),
           repr((err, fields and fields.get("phase"))))

    board_text = (HOME / ".saipen" / "BOARD.md").read_text(
        encoding="utf-8-sig")
    board = parse_board(board_text)
    expect("board parser finds every live section",
           board["headings"] == ["## DOING", "## TODO", "## DONE",
                                 "## BLOCKED"], repr(board["headings"]))
    doing = [t for t in board["tickets"].values()
             if t["section"] == "## DOING"]
    expect("board parser enforces at-most-one claimed ticket with / checkbox",
           len(doing) <= 1 and all(t["checkbox"] == "/" for t in doing),
           repr([(t["id"], t["checkbox"]) for t in doing]))

    log_line = "- 08.08.26 23:58 [E-2440] [parent: E-2439] [T-578] RUN: probe"
    ev = parse_log_line(log_line)
    expect("log parser reads event, parent, ticket, taxonomy",
           ev is not None and ev["event"] == 2440
           and ev["parent"] == 2439 and ev["ticket"] == "T-578"
           and ev["taxonomy"] == "RUN", repr(ev))
    expect("log parser rejects a non-event line",
           parse_log_line("just prose") is None)

    snap = ProjectSnapshot.capture(HOME)
    expect("snapshot carries hashes, log tail and head",
           snap.state_hash and snap.board_hash and snap.log_hash
           and snap.log_tail is not None and snap.head,
           repr((snap.log_tail, snap.head)))
    expect("snapshot is not stale against the unchanged project",
           not snap.stale(HOME))
    board_path = HOME / ".saipen" / "BOARD.md"
    original = board_path.read_bytes()
    try:
        board_path.write_bytes(original + b"\n")
        expect("snapshot detects a changed board precondition",
               snap.stale(HOME))
    finally:
        board_path.write_bytes(original)
    expect("snapshot is fresh again after restoring the board",
           not snap.stale(HOME))

    status = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "status"],
        cwd=HOME, capture_output=True, text=True)
    expect("saipen status is read-only and reports the phase",
           status.returncode == 0 and f"phase: {fields.get('phase')}"
           in status.stdout, repr(status.stdout[:120]))
    nxt = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "next", "--json"],
        cwd=HOME, capture_output=True, text=True)
    expect("saipen next --json returns the action deterministically",
           nxt.returncode == 0 and '"action":' in nxt.stdout
           and '"load":' in nxt.stdout, repr(nxt.stdout[:120]))

    return problems, checked


def run_nitro_m2_probes() -> tuple[list[str], int]:
    """NITRO M2 (T-579): OS single-writer lock + write-ahead journal +
    roll-forward recovery with crash injection at every commit boundary.

    A subprocess performs run_mutation with NITRO_CRASH_AFTER_<STAGE> set and
    dies (exit 87) exactly there; recovery must produce exactly one valid
    outcome and be idempotent. The LOG event is never deleted (roll-forward,
    not rollback).
    """
    problems: list[str] = []
    checked = 0

    def expect(label: str, ok: bool, detail: str = "") -> None:
        nonlocal checked
        checked += 1
        if not ok:
            problems.append(f"{label}: {detail}")
        else:
            print(f"PASS: nitro-m2 -- {label}")

    root = Path(tempfile.mkdtemp(prefix="saipen-m2-"))
    saipen = root / ".saipen"
    saipen.mkdir()
    log = saipen / "LOG.md"
    board = saipen / "BOARD.md"
    state = saipen / "STATE.md"
    log.write_text("- 09.08.26 00:00 [E-900] [T-none] DEC: base\n",
                   encoding="utf-8")
    board.write_text("# Board\n## DOING\n## TODO\n## DONE\n## BLOCKED\n",
                     encoding="utf-8")
    state.write_text("---\nphase: DONE\ntask: none\n"
                     'next_action: "saipen continue"\n---\n', encoding="utf-8")

    log_before = log.read_bytes()
    board_before = board.read_bytes()
    state_before = state.read_bytes()

    def run_crash(stage_env: str, op_id: str) -> int:
        env = {**os.environ, stage_env: "1"}
        code = (
            "import sys; sys.path.insert(0, r'%s')\n"
            "from saipen_engine.journal import run_mutation\n"
            "run_mutation(r'%s', '%s', 'probe', 'id', {}, [\n"
            "  {'path': '.saipen/LOG.md', 'content': %r},\n"
            "  {'path': '.saipen/BOARD.md', 'content': %r},\n"
            "  {'path': '.saipen/STATE.md', 'content': %r}])"
            % (str(HOME / "tools"), str(root), op_id,
               log_before + b"\n- 09.08.26 00:01 [E-901] RUN: op\n",
               board_before,
               state_before.replace(b"phase: DONE", b"phase: BUILD")))
        return subprocess.run([sys.executable, "-c", code], cwd=str(root),
                              env=env, capture_output=True, text=True,
                              timeout=60).returncode

    # Crash before LOG (NITRO_CRASH_AFTER_PREPARE): canonical state unchanged.
    rc = run_crash("NITRO_CRASH_AFTER_PREPARE", "op-prepare")
    expect("crash before LOG leaves canonical state unchanged",
           rc == 87 and log.read_bytes() == log_before
           and board.read_bytes() == board_before
           and state.read_bytes() == state_before,
           f"rc={rc}")
    recover(root, "op-prepare")
    expect("PREPARED recovery aborts safely",
           log.read_bytes() == log_before)

    # Crash after LOG: LOG written, BOARD/STATE not; recover rolls forward.
    run_crash("NITRO_CRASH_AFTER_LOG", "op-log")
    expect("crash after LOG leaves the LOG event and nothing else",
           b"E-901" in log.read_bytes()
           and board.read_bytes() == board_before
           and b"phase: BUILD" not in state.read_bytes())
    result = recover(root, "op-log")
    expect("recovery rolls BOARD+STATE forward after LOG",
           result["ok"] and b"phase: BUILD" in state.read_bytes()
           and result.get("code") == "COMMITTED", repr(result))
    again = recover(root, "op-log")
    expect("repeated recovery is idempotent (ALREADY_APPLIED)",
           again["ok"] and again.get("code") == "ALREADY_APPLIED",
           repr(again))
    expect("the LOG event was not duplicated by recovery",
           log.read_text(encoding="utf-8").count("E-901") == 1)

    # Crash after BOARD: LOG+BOARD written, STATE not; recover rolls STATE.
    log.write_bytes(log_before)
    board.write_bytes(board_before)
    state.write_bytes(state_before)
    run_crash("NITRO_CRASH_AFTER_BOARD", "op-board")
    expect("crash after BOARD leaves STATE unbuilt",
           b"phase: BUILD" not in state.read_bytes())
    result = recover(root, "op-board")
    expect("recovery rolls STATE forward after BOARD",
           result["ok"] and b"phase: BUILD" in state.read_bytes()
           and result.get("code") == "COMMITTED", repr(result))

    # Crash after STATE: all three written; recover validates and commits.
    log.write_bytes(log_before)
    board.write_bytes(board_before)
    state.write_bytes(state_before)
    run_crash("NITRO_CRASH_AFTER_STATE", "op-state")
    expect("crash after STATE leaves the full mutation written",
           b"E-901" in log.read_bytes()
           and b"phase: BUILD" in state.read_bytes())
    result = recover(root, "op-state")
    expect("recovery after STATE validates and commits",
           result["ok"] and result.get("code") == "COMMITTED", repr(result))
    expect("the crash-after-STATE op was not double-written by recovery",
           log.read_text(encoding="utf-8").count("E-901") == 1)

    # A committed op's retry returns ALREADY_APPLIED without a second event.
    journal = Journal(root, "op-log")
    record = journal.read()
    targets = record["targets"]
    result = run_mutation(
        root, "op-log", "probe", "id",
        {"STATE.md": "x"},  # stale precondition, must not matter for committed
        [{"path": p, "content": b""} for p in targets])
    expect("a committed op's retry returns ALREADY_APPLIED",
           result.get("code") == "ALREADY_APPLIED", repr(result))
    expect("no duplicate LOG event from a retried committed op",
           log.read_text(encoding="utf-8").count("E-901") == 1)

    # A committed op's retry returns ALREADY_APPLIED without a second event.
    journal = Journal(root, "op-log")
    record = journal.read()
    targets = record["targets"]
    result = run_mutation(
        root, "op-log", "probe", "id",
        {"STATE.md": "x"},  # stale precondition, must not matter for committed
        [{"path": p, "content": b""} for p in targets])
    expect("a committed op's retry returns ALREADY_APPLIED",
           result.get("code") == "ALREADY_APPLIED", repr(result))
    expect("no duplicate LOG event from a retried committed op",
           log.read_text(encoding="utf-8").count("E-901") == 1)

    # Writer lock: second live writer refuses; release allows re-acquire.
    lock = WriterLock(root)
    lock.acquire()
    try:
        try:
            second = WriterLock(root)
            second.acquire()
            refused = False
        except PermissionError:
            refused = True
        expect("a second live writer is refused (WRITER_BUSY)", refused)
    finally:
        lock.release()
    reacquire = WriterLock(root)
    reacquire.acquire()
    reacquire.release()
    expect("the lock releases and re-acquires cleanly", True)

    return problems, checked


def run_last_event_probes() -> tuple[list[str], int]:
    """Execute the legacy-schema to current-schema checkpoint migration."""
    problems = []
    checked = 0

    def validate(project: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--project-root", str(project)],
            cwd=project, capture_output=True, text=True, errors="replace")

    def expect(label: str, result: subprocess.CompletedProcess[str],
               returncode: int, contains: str,
               excludes: tuple[str, ...] = ()) -> None:
        nonlocal checked
        checked += 1
        output = result.stdout + result.stderr
        missing = contains not in output
        leaked = next((value for value in excludes if value in output), None)
        if result.returncode != returncode or missing or leaked:
            details = []
            if result.returncode != returncode:
                details.append(f"exit {result.returncode}, expected {returncode}")
            if missing:
                details.append(f"missing {contains!r}")
            if leaked:
                details.append(f"unexpected {leaked!r}")
            problems.append(f"{label}: {'; '.join(details)}")
        else:
            print(f"PASS: last_event -- {label}")

    with tempfile.TemporaryDirectory(prefix="saipen-last-event-") as raw:
        project = Path(raw) / "project"
        shutil.copytree(SCENARIOS / "stale-state-reconciliation" / ".saipen",
                        project / ".saipen")
        state_path = project / ".saipen" / "STATE.md"
        log_path = project / ".saipen" / "LOG.md"

        expect("legacy absence warns but remains readable", validate(project), 0,
               "WARN [schema-version]", ("requires last_event",))

        state = state_path.read_text(encoding="utf-8-sig")
        state = state.replace("saipen_version: 7\n",
                              "saipen_version: 7\nschema_version: 3\n", 1)
        state_path.write_text(state, encoding="utf-8", newline="\n")
        expect("current schema missing marker fails", validate(project), 1,
               "requires last_event")

        state = state_path.read_text(encoding="utf-8")
        state = state.replace("schema_version: 3\n",
                              "schema_version: 3\nlast_event: 1\n", 1)
        state_path.write_text(state, encoding="utf-8", newline="\n")
        # The voice marker is the half a cold session can skip in silence:
        # every other required field is derivable from `.saipen/` itself, so
        # an agent that never opened STYLE.md fills the state in completely
        # and looks conformant. Checked on its own, between two states that
        # differ by that one line.
        expect("current schema missing style marker fails", validate(project), 1,
               "requires style_contract")

        state = state_path.read_text(encoding="utf-8")
        state = state.replace("last_event: 1\n",
                              f"last_event: 1\nstyle_contract: {live_style_marker()}\n", 1)
        state_path.write_text(state, encoding="utf-8", newline="\n")
        expect("exact recovered tail passes", validate(project), 0,
               "Validation complete. Agent is conformant.",
               ("WARN [schema-version]", "FAIL: STATE.md last_event"))

        log = log_path.read_text(encoding="utf-8-sig").rstrip()
        log += ("\n- 26.07.17 00:01 [E-002] [parent: E-001] [T-001] "
                "RUN: checkpoint advanced\n")
        log_path.write_text(log, encoding="utf-8", newline="\n")
        expect("advanced LOG makes old marker stale", validate(project), 1,
               "lower than the log")

        state = state_path.read_text(encoding="utf-8")
        state_path.write_text(state.replace("last_event: 1\n", "last_event: 2\n", 1),
                              encoding="utf-8", newline="\n")
        expect("recovered exact tail passes", validate(project), 0,
               "Validation complete. Agent is conformant.",
               ("FAIL: STATE.md last_event",))

        state = state_path.read_text(encoding="utf-8")
        state_path.write_text(state.replace("last_event: 2\n", "last_event: 3\n", 1),
                              encoding="utf-8", newline="\n")
        expect("marker above LOG fails as corrupt", validate(project), 1,
               "higher than the log")

    return problems, checked

if not SCENARIOS.is_dir():
    print(f"FAIL: no {SCENARIOS} -- run this from the SAIPEN home")
    sys.exit(1)

failures = []
checked = skipped = 0

for d in sorted(p for p in SCENARIOS.iterdir() if p.is_dir()):
    readme = d / "README.md"
    has_state = (d / ".saipen").is_dir()
    declared = None
    reason = None
    warn_reason = None
    if readme.is_file():
        _rtext = readme.read_text(encoding="utf-8-sig")
        m = EXPECT_RE.search(_rtext)
        declared = m.group(1) if m else None
        _rm = REASON_RE.search(_rtext)
        reason = _rm.group(1) if _rm else None
        _wm = WARN_RE.search(_rtext)
        warn_reason = _wm.group(1) if _wm else None

    if not has_state:
        # Behavioral fixture. It must NOT declare an expectation -- there is
        # nothing to run, so a declaration here would be a promise no one keeps.
        if declared:
            failures.append(f"{d.name}: declares 'expect: {declared}' but ships "
                            f"no .saipen/ -- nothing to run")
        else:
            skipped += 1
        continue

    if declared is None:
        failures.append(f"{d.name}: ships a .saipen/ but declares no "
                        f"'expect: pass|fail' line -- cannot be checked")
        continue

    if declared == "fail" and not reason:
        failures.append(f"{d.name}: declares 'expect: fail' with no "
                        f"'expect_fail_contains:' line -- an unpinned "
                        f"fail-fixture asserts only that something went "
                        f"wrong, and any unrelated FAIL then scores it green")
        continue

    r = subprocess.run([sys.executable, str(VALIDATOR), "--project-root", str(d)], cwd=d,
                       capture_output=True, text=True)
    actual = "pass" if r.returncode == 0 else "fail"
    checked += 1
    if actual != declared:
        detail = ""
        for line in (r.stdout + r.stderr).splitlines():
            if line.startswith("FAIL"):
                detail = f" | first FAIL: {line[:120]}"
                break
        failures.append(f"{d.name}: declared '{declared}', got '{actual}' "
                        f"(validator exit {r.returncode}){detail}")
    elif declared == "fail" and reason:
        blob = r.stdout + r.stderr
        if "Traceback (most recent call last)" in blob:
            # A CRASH is not "failed for the wrong reason". Both exit non-zero,
            # and the softer wording pointed at the fixture when the defect was
            # in the validator: a NameError on a constant declared after its
            # first use, in a branch this repo's own STATE never enters. Name
            # the crash so the next reader looks at the tool, not the data.
            last = next((ln for ln in reversed(blob.splitlines())
                         if ln.strip() and not ln.startswith(" ")),
                        "<no exception line>")
            failures.append(f"{d.name}: the validator CRASHED instead of "
                            f"reporting -- {last.strip()[:110]!r}. A traceback "
                            f"exits non-zero and can be mistaken for the "
                            f"declared failure; it is a defect in the tool")
        elif reason not in blob:
            first = next((ln for ln in blob.splitlines()
                          if ln.startswith("FAIL")), "<no FAIL line>")
            failures.append(f"{d.name}: failed as declared, but for the wrong "
                            f"reason -- expected {reason!r}, first FAIL was "
                            f"{first[:110]!r}")
        else:
            print(f"PASS: {d.name} -- failed on {reason!r}, as declared")
    elif declared == "pass" and warn_reason:
        blob = r.stdout + r.stderr
        if warn_reason not in blob:
            failures.append(f"{d.name}: passed as declared, but missing expected warning -- "
                            f"expected {warn_reason!r}")
        else:
            print(f"PASS: {d.name} -- passed and warned on {warn_reason!r}, as declared")
    else:
        if declared == "fail":
            print(f"WARN: {d.name} -- fails as declared, but pins no reason; "
                  f"add `expect_fail_contains:` so it cannot pass by failing "
                  f"at something unrelated")
        print(f"PASS: {d.name} -- expected {declared}, got {actual}")




def run_digest_stale_probes() -> tuple[list[str], int]:
    problems = []
    checked = 0
    git = shutil.which("git")
    if not git:
        return ["digest-stale probes require git"], checked

    def git_run(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([git, *args], cwd=cwd, capture_output=True,
                              text=True, errors="replace")

    with tempfile.TemporaryDirectory(prefix="saipen-digest-") as raw:
        sandbox = Path(raw).resolve()
        project = sandbox / "project"
        project.mkdir()

        shutil.copytree(SCENARIOS / "resume-after-crash" / ".saipen", project / ".saipen")

        # Setup basic IS_SAIPEN_HOME
        (project / "VERSION").write_text("1.0.0\n", encoding="utf-8-sig")
        (project / "README.md").write_text("# SAIPEN\n", encoding="utf-8-sig")
        (project / ".saipen" / "kitchen").mkdir(exist_ok=True, parents=True)
        (project / ".saipen" / "kitchen" / "digest.md").write_text(
            "done: v0.9.0\nremaining: 0\nawaiting: none\n", encoding="utf-8-sig")
        (project / "saipen").mkdir(exist_ok=True)
        (project / "saipen" / "RFC.md").write_text("", encoding="utf-8-sig")
        (project / "bootstrap").mkdir(exist_ok=True)
        (project / "CHANGELOG.md").write_text("## [1.0.0]\n", encoding="utf-8-sig")

        git_run(project, "init", "-q")
        git_run(project, "config", "user.name", "SAIPEN")
        git_run(project, "config", "user.email", "test@test")
        git_run(project, "add", ".")
        git_run(project, "commit", "-q", "-m", "Initial")
        git_run(project, "tag", "v0.9.0")

        # Test 1: pre-tag (tag for 1.0.0 does not exist yet)
        checked += 1
        res1 = subprocess.run(
            [sys.executable, str(VALIDATOR), "--project-root", str(project)],
            cwd=project, capture_output=True, text=True)
        if "[digest-stale]" in res1.stdout or "[digest-stale]" in res1.stderr:
            problems.append("digest-stale warned incorrectly on pre-tag "
                            "state: " + res1.stdout + res1.stderr)
        else:
            print("PASS: digest-stale -- no warning before tag is created")

        # Test 2: post-tag (tag for 1.0.0 exists, but digest names 0.9.0)
        git_run(project, "tag", "v1.0.0")
        checked += 1
        res2 = subprocess.run(
            [sys.executable, str(VALIDATOR), "--project-root", str(project)],
            cwd=project, capture_output=True, text=True)
        if "[digest-stale]" not in res2.stdout and "[digest-stale]" not in res2.stderr:
            problems.append("digest-stale failed to warn after tag was "
                            "created: " + res2.stdout + res2.stderr)
        else:
            print("PASS: digest-stale -- warned correctly after tag exists")
    return problems, checked


def run_orphan_tag_probes() -> tuple[list[str], int]:
    """A tag pushed while its branch did not land must FAIL validation.

    Reproduces the E-1787/E-1882 sequence: the branch push is rejected
    (never lands on the remote branch), the tag push runs anyway and
    succeeds, so the remote carries a tag whose commit is on no remote
    branch. Needs a real repository with a real remote -- the orphan check
    reads refs/remotes and ls-remote, so it cannot live in
    `tools/audit_checks.py`, whose snapshot excludes `.git`.
    """
    problems: list[str] = []
    checked = 0
    with tempfile.TemporaryDirectory(prefix="saipen-orphan-") as raw:
        home = Path(raw) / "home"
        origin = Path(raw) / "origin.git"
        shutil.copytree(HOME, home, ignore=shutil.ignore_patterns(
            ".git", ".venv", "__pycache__", "node_modules", "nul", ".freebuff"))
        env = {**os.environ, "GIT_AUTHOR_NAME": "probe",
               "GIT_AUTHOR_EMAIL": "probe@example.invalid",
               "GIT_COMMITTER_NAME": "probe",
               "GIT_COMMITTER_EMAIL": "probe@example.invalid"}

        def git(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(["git", *args], cwd=home, env=env,
                                  capture_output=True, text=True, check=False)

        def validate() -> str:
            r = subprocess.run(
                [sys.executable, str(home / "tools" / "validate.py"),
                 "--project-root", str(home)],
                cwd=home, capture_output=True, text=True, errors="replace")
            return r.stdout + r.stderr

        def expect(label: str, output: str, contains: str,
                   absent: str = "") -> None:
            nonlocal checked
            checked += 1
            details = []
            if contains and contains not in output:
                details.append(f"missing {contains!r}")
            if absent and absent in output:
                details.append(f"unexpected {absent!r}")
            if details:
                problems.append(f"{label}: {'; '.join(details)}")
            else:
                print(f"PASS: orphan tag -- {label}")

        if git("init", "-q").returncode != 0:
            print("SKIP: orphan tag probes -- git unavailable")
            return problems, checked
        git("add", "-A")
        git("commit", "-q", "-m", "probe")
        if git("init", "-q", "--bare", str(origin)).returncode != 0:
            print("SKIP: orphan tag probes -- cannot create bare remote")
            return problems, checked
        git("remote", "add", "origin", str(origin))
        if git("push", "-q", "-u", "origin", "HEAD:main").returncode != 0:
            print("SKIP: orphan tag probes -- cannot push initial main")
            return problems, checked

        # The rejected-branch-then-tag sequence: a release commit is made but
        # its branch push never lands (here: simply not pushed), while the tag
        # push succeeds -- the remote now carries a tag whose commit is on no
        # remote branch.
        (home / "orphan-release.txt").write_text("orphan\n", encoding="utf-8")
        git("add", "orphan-release.txt")
        git("commit", "-q", "-m", "release commit, branch push rejected")
        git("tag", "v7.176.0")
        if git("push", "-q", "origin", "refs/tags/v7.176.0").returncode != 0:
            print("SKIP: orphan tag probes -- cannot push the orphan tag")
            return problems, checked
        expect("a published tag whose commit rides no remote branch fails",
               validate(), "FAIL: orphaned release tag")

        # Repair: the branch push finally lands, the tag's commit becomes
        # reachable from origin/main, and the same tag now passes.
        if git("push", "-q", "origin", "HEAD:main").returncode != 0:
            print("SKIP: orphan tag probes -- cannot land the branch")
            return problems, checked
        expect("the same tag passes once its branch has landed",
               validate(), "", absent="FAIL: orphaned release tag")

    return problems, checked


def run_ship_pick_probes() -> tuple[list[str], int]:
    """The ticket that passes REVIEW stays in `## DOING` through SHIP.

    `PHASE SHIP T-###` is RFC § 1.2's prescribed `next_action` for the one
    state SHIP is ever entered from, and the Pick Rule accepts it exactly
    while the ticket sits in `## DOING` -- a claimed `## DOING` ticket IS
    the pick. This repository's habit of closing the ticket at REVIEW
    (E-1879, T-466) moved it to `## DONE` before anything was pushed, so
    the same string named a finished ticket and failed the pick check
    twice over. Lives here rather than in `tools/audit_checks.py` because
    the condition spans two files -- STATE's `next_action` and the
    ticket's board section -- and that harness mutates one file per case
    (the compound-fixture route T-457 asks for).
    """
    problems: list[str] = []
    checked = 0
    with tempfile.TemporaryDirectory(prefix="saipen-ship-pick-") as raw:
        home = Path(raw) / "home"
        shutil.copytree(HOME, home, ignore=shutil.ignore_patterns(
            ".git", ".venv", "__pycache__", "node_modules", "nul",
            ".freebuff"))

        style_path = home / "saipen" / "STYLE.md"
        style_text = (style_path.read_text(encoding="utf-8-sig",
                                           errors="replace")
                      if style_path.is_file() else "")
        _sm = re.search(r"`style_contract:\s*(ded-[0-9a-f]{8})`", style_text)
        style_token = _sm.group(1) if _sm else "ded-00000000"

        state_path = home / ".saipen" / "STATE.md"
        board_path = home / ".saipen" / "BOARD.md"
        log_path = home / ".saipen" / "LOG.md"

        def validate() -> str:
            r = subprocess.run(
                [sys.executable, str(home / "tools" / "validate.py"),
                 "--project-root", str(home)],
                cwd=home, capture_output=True, text=True, errors="replace")
            return r.stdout + r.stderr

        def expect(label: str, output: str, contains: str,
                   absent: str = "") -> None:
            nonlocal checked
            checked += 1
            details = []
            if contains and contains not in output:
                details.append(f"missing {contains!r}")
            if absent and absent in output:
                details.append(f"unexpected {absent!r}")
            if details:
                problems.append(f"{label}: {'; '.join(details)}")
            else:
                print(f"PASS: ship pick -- {label}")

        def write_fixture(in_doing: bool) -> None:
            # A self-contained fixture: minimal LOG (one event) so
            # last_event: 1 matches, and a board where the shipped ticket
            # lives in either ## DOING or ## DONE.
            log_path.write_text(
                "- 03.08.26 00:00 [E-001] [T-901] RUN: probe\n",
                encoding="utf-8", newline="\n")
            state_path.write_text(
                "---\n"
                "phase: SHIP\n"
                "task: T-901\n"
                "next_action: \"PHASE SHIP T-901\"\n"
                "blocker: none\n"
                "transition_from: REVIEW\n"
                "saipen_version: 7\n"
                "schema_version: 3\n"
                "last_event: 1\n"
                f"style_contract: {style_token}\n"
                "agent: probe\n"
                "mode: full\n"
                "updated: 2026-01-01T00:00:00Z\n"
                "---\n",
                encoding="utf-8", newline="\n")
            section = "## DOING\n- [/] T-901 ship | owner: probe | " \
                "claim_time: 2026-01-01T00:00:00Z | verify: probe\n" \
                if in_doing else \
                "## DONE\n- [x] T-901 ship | verify: probe\n"
            board_path.write_text(
                "# Board\n" + section +
                "## TODO\n" + ("## DONE\n" if in_doing else "## DOING\n") +
                "## BLOCKED\n",
                encoding="utf-8", newline="\n")

        write_fixture(in_doing=True)
        expect("a ticket kept in ## DOING through SHIP validates",
               validate(), "", absent="finished and blocked tickets are "
               "not executable")

        write_fixture(in_doing=False)
        expect("the same ticket closed at REVIEW fails the pick rule",
               validate(), "finished and blocked tickets are not "
               "executable")

    return problems, checked


def run_active_task_recovery_probes() -> tuple[list[str], int]:
    """T-573: the crash pair is rejected, then RFC § 1.5 Recovery rebuilds it.

    The v7.215.0 crash checkpoint made STATE claim a ticket the board never
    put in ## DOING, and the validator called it conformant. The new check
    rejects both interruption directions (STATE ahead of BOARD, BOARD ahead
    of STATE). This probe performs § 1.5's Recovery on each and proves the
    result validates and that a repeated Recovery is a byte-level no-op. The
    project carries only a minimal `.saipen/` so no full-repo baggage (sealed
    LOG segments, sub boards, board barriers) can mask what is being tested.
    """
    problems: list[str] = []
    checked = 0
    with tempfile.TemporaryDirectory(prefix="saipen-active-task-") as raw:
        project = Path(raw) / "project"
        shutil.copytree(SCENARIOS / "stale-state-reconciliation" / ".saipen",
                        project / ".saipen")
        state_path = project / ".saipen" / "STATE.md"
        board_path = project / ".saipen" / "BOARD.md"
        log_path = project / ".saipen" / "LOG.md"
        style_token = live_style_marker()

        def validate() -> str:
            r = subprocess.run(
                [sys.executable, str(VALIDATOR), "--project-root",
                 str(project)],
                cwd=project, capture_output=True, text=True, errors="replace")
            return r.stdout + r.stderr

        def expect(label: str, output: str, contains: str = "",
                   absent: str = "") -> None:
            nonlocal checked
            checked += 1
            details = []
            if contains and contains not in output:
                details.append(f"missing {contains!r}")
            if absent and absent in output:
                details.append(f"unexpected {absent!r}")
            if details:
                problems.append(f"{label}: {'; '.join(details)}")
            else:
                print(f"PASS: active-task recovery -- {label}")

        def write_state(task: str, na: str, last_event: int) -> None:
            state_path.write_text(
                "---\nphase: SCOUT\n"
                f"task: {task}\n"
                f"next_action: \"{na}\"\n"
                "blocker: none\n"
                "transition_from: DONE\n"
                "saipen_version: 7\n"
                "schema_version: 3\n"
                f"last_event: {last_event}\n"
                f"style_contract: {style_token}\n"
                "agent: probe\n"
                "mode: full\n"
                "updated: 2026-01-01T00:00:00Z\n"
                "---\n",
                encoding="utf-8", newline="\n")

        def write_log(ticket: str) -> None:
            log_path.write_text(
                f"- 08.08.26 00:00 [E-001] [{ticket}] RUN: probe\n",
                encoding="utf-8", newline="\n")

        def recover(ticket: str, claim_board: bool, label: str) -> None:
            # No-op when the previous recovery already produced this state:
            # RFC § 1.5's idempotency, proven byte-for-byte by the caller.
            board = board_path.read_text(encoding="utf-8-sig")
            state = state_path.read_text(encoding="utf-8-sig")
            already = (f"task: {ticket}" in state
                       and re.search(r"^## DOING\n- \[/\] " + ticket + r"\b",
                                     board, re.MULTILINE))
            if already:
                return
            recovery_dir = project / ".saipen" / "recovery"
            recovery_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(state_path, recovery_dir / f"{label}-STATE.md")
            log = log_path.read_text(encoding="utf-8-sig").rstrip()
            log += (f"\n- 08.08.26 00:01 [E-002] [{ticket}] "
                    f"DEC: RECOVER -- {label}\n")
            log_path.write_text(log, encoding="utf-8", newline="\n")
            if claim_board:
                board_path.write_text(
                    "# Board\n## DOING\n"
                    f"- [/] {ticket} [P0] crash | owner: probe | "
                    "claim_time: 2026-01-01T00:00:00Z | verify: probe\n"
                    "## TODO\n## DONE\n## BLOCKED\n",
                    encoding="utf-8", newline="\n")
            write_state(ticket, f"PHASE SCOUT {ticket}", 2)

        # Case A: STATE ahead of BOARD -- task claimed, no ## DOING ticket.
        write_state("T-999", "PHASE SCOUT T-999", 1)
        write_log("T-999")
        board_path.write_text(
            "# Board\n## DOING\n## TODO\n"
            "- [ ] T-999 [P0] crash | verify: probe\n"
            "## DONE\n## BLOCKED\n",
            encoding="utf-8", newline="\n")
        expect("STATE ahead of BOARD is rejected",
               validate(), "is not the claimed ## DOING ticket")
        recover("T-999", claim_board=True, label="crash-A")
        expect("Recovery of case A validates",
               validate(), "Agent is conformant")
        snap = (state_path.read_bytes(), board_path.read_bytes(),
                log_path.read_bytes())
        recover("T-999", claim_board=True, label="crash-A")
        again = (state_path.read_bytes(), board_path.read_bytes(),
                 log_path.read_bytes())
        expect("repeated Recovery of case A is byte-idempotent",
               "same" if snap == again else "differed", contains="same")

        # Case B: BOARD ahead of STATE -- self-claimed ## DOING, task: none.
        write_state("none", "saipen continue", 1)
        write_log("T-100")
        board_path.write_text(
            "# Board\n## DOING\n"
            "- [/] T-100 [P0] claimed | owner: probe | "
            "claim_time: 2026-01-01T00:00:00Z | verify: probe\n"
            "## TODO\n## DONE\n## BLOCKED\n",
            encoding="utf-8", newline="\n")
        expect("BOARD ahead of STATE is rejected",
               validate(), "STATE is behind BOARD")
        recover("T-100", claim_board=False, label="crash-B")
        expect("Recovery of case B validates",
               validate(), "Agent is conformant")
        snap = (state_path.read_bytes(), board_path.read_bytes(),
                log_path.read_bytes())
        recover("T-100", claim_board=False, label="crash-B")
        again = (state_path.read_bytes(), board_path.read_bytes(),
                 log_path.read_bytes())
        expect("repeated Recovery of case B is byte-idempotent",
               "same" if snap == again else "differed", contains="same")

    return problems, checked


injector_failures, injector_checked, injector_skipped = run_injector_probes()
failures.extend(injector_failures)
root_failures, root_checked = run_project_root_probes()
failures.extend(root_failures)
export_failures, export_checked, export_skipped = run_export_probes()
failures.extend(export_failures)
crew_failures, crew_checked, crew_skipped = run_crew_probes()
failures.extend(crew_failures)
last_event_failures, last_event_checked = run_last_event_probes()
failures.extend(last_event_failures)
hunt_mark_failures, hunt_mark_checked = run_hunt_mark_probes()
failures.extend(hunt_mark_failures)
converge_failures, converge_checked = run_converge_routing_probes()
failures.extend(converge_failures)
ccc_identity_failures, ccc_identity_checked = run_ccc_identity_probes()
failures.extend(ccc_identity_failures)
producer_gate_failures, producer_gate_checked = run_producer_gate_probes()
failures.extend(producer_gate_failures)
ship_staging_failures, ship_staging_checked = run_ship_staging_probes()
failures.extend(ship_staging_failures)
rolefresh_failures, rolefresh_checked, rolefresh_skipped = \
    run_role_freshness_probes()
failures.extend(rolefresh_failures)
sub_clean_failures, sub_clean_checked, sub_clean_skipped = \
    run_sub_clean_probes()
failures.extend(sub_clean_failures)
hardening_failures, hardening_checked = run_hardening_control_inventory()
failures.extend(hardening_failures)
userperson_failures, userperson_checked = run_userperson_probes()
failures.extend(userperson_failures)
improve_failures, improve_checked = run_improve_probes()
failures.extend(improve_failures)
nitro_failures, nitro_checked = run_nitro_probes()
failures.extend(nitro_failures)
nitro_m2_failures, nitro_m2_checked = run_nitro_m2_probes()
failures.extend(nitro_m2_failures)
manifest_failures, manifest_checked = run_manifest_tracking_probes()
failures.extend(manifest_failures)
autoinject_failures, autoinject_checked = run_autoinject_manifest_probes()
failures.extend(autoinject_failures)
hook_failures, hook_checked, hook_skipped = run_hook_probes()
ci_failures, ci_checked = run_ci_status_probes()
failures.extend(ci_failures)
failures.extend(hook_failures)
purity_failures, purity_checked, purity_skipped = run_precommit_purity_probe()
failures.extend(purity_failures)


digest_failures, digest_checked = run_digest_stale_probes()
failures.extend(digest_failures)
orphan_failures, orphan_checked = run_orphan_tag_probes()
failures.extend(orphan_failures)
ship_pick_failures, ship_pick_checked = run_ship_pick_probes()
active_task_failures, active_task_checked = run_active_task_recovery_probes()
failures.extend(ship_pick_failures)
failures.extend(active_task_failures)
print(f"\n{checked} executable fixture(s) checked, "
      f"{skipped} behavioral fixture(s) skipped (README-only by design)")
print(f"{injector_checked} injector(s) executed, "
      f"{injector_skipped} skipped for missing interpreters")
print(f"{root_checked} project-root behavior(s) executed")
print(f"{export_checked} export ownership behavior(s) executed, "
      f"{export_skipped} skipped for missing interpreters")
print(f"{crew_checked} crew-launch behavior(s) executed, "
      f"{crew_skipped} skipped for missing interpreters")
print(f"{digest_checked} digest-stale behavior(s) executed")
print(f"{orphan_checked} orphan-tag behavior(s) executed")
print(f"{ship_pick_checked} ship-pick behavior(s) executed")
print(f"{active_task_checked} active-task recovery behavior(s) executed")
print(f"{last_event_checked} last_event migration behavior(s) executed")
print(f"{hunt_mark_checked} hunt-mark behavior(s) executed")
print(f"{converge_checked} converge-routing behavior(s) executed")
print(f"{ccc_identity_checked} ccc commit-identity behavior(s) executed")
print(f"{producer_gate_checked} producer-gate behavior(s) executed")
print(f"{ship_staging_checked} ship-staging behavior(s) executed")
print(f"{rolefresh_checked} role-freshness behavior(s) executed, "
      f"{rolefresh_skipped} skipped for missing host capability")
print(f"{sub_clean_checked} sub-clean safety behavior(s) executed, "
      f"{sub_clean_skipped} skipped for missing host capability")
print(f"{hardening_checked} hardening red control(s) resolved")
print(f"{userperson_checked} userperson behavior(s) executed")
print(f"{improve_checked} improve behavior(s) executed")
print(f"{nitro_checked} nitro behavior(s) executed")
print(f"{nitro_m2_checked} nitro-m2 behavior(s) executed")
print(f"{purity_checked} pre-commit-purity behavior(s) executed, "
      f"{purity_skipped} skipped for missing interpreters")
print(f"{manifest_checked} manifest-tracking behavior(s) executed")
print(f"{autoinject_checked} autoinject-manifest behavior(s) executed")
print(f"{hook_checked} installed-hook behavior(s) executed, "
      f"{hook_skipped} skipped for missing interpreters")
print(f"{ci_checked} ci-status behavior(s) executed")

if failures:
    print(f"\nFAILED: {len(failures)} executable check(s) failed")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)

if checked == 0:
    # A run that checked nothing is not a pass (phases/verify.md: a gate that
    # cannot fail is not a gate).
    print("FAILED: no executable fixtures found -- this suite collected 0 tests")
    sys.exit(1)

print("All executable scenarios and injector probes passed.")

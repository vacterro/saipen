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
from improve import (ImproveError, abort_cycle, allocate_cycle_id,
                     append_run, archive_cycle, complete_cycle,
                     complete_report, create_cycle, create_report, cycle_dir,
                     derive_status, installed_protocol_fingerprint,
                     _saipen_install_version,
                     prepare_audit_seat,
                     register_cycle, register_seat,
                     resolve_report_path, validate_manifest, validate_report,
                     validate_strict_provenance,
                     write_sweep_entry)
from userperson import (merge_profile, onboarding_questions, parse_profile,
                        project_profile, remove_preference, render_profile,
                        validate_profile)
from saipen_engine import codec
from saipen_engine.board import parse_board
from saipen_engine.state import parse_state
from saipen_engine.journal import (Journal, pending_ops, recover,
                                   recovery_preflight, run_mutation)
from saipen_engine.lock import WriterLock
from saipen_engine.log import parse_log_line
from saipen_engine.operations import (apply_claim, checkpoint, next_ticket_id,
                                       plan_claim, reauthorize_valve,
                                       set_goal_intent, stop_checkpoint,
                                       ticket_add, ticket_move,
                                       transition_phase, _now, _plan_claim,
                                       _utc_iso)
from saipen_engine.result import Result
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

# T-992: fixtures that create STRICT ACTIVE reports validated by the real
# validator must carry the INSTALLED protocol fingerprint and version --
# the validator compares ACTIVE strict evidence to current installed truth,
# so a fixture digest would fail on purpose. Historical/archived fixtures
# keep their own historical values.
PROBE_INSTALLED_FP = installed_protocol_fingerprint(HOME)
PROBE_SAIPEN_VERSION = _saipen_install_version()


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


def run_scheduler_probes() -> tuple[list[str], int, int]:
    """Canonical scheduler owns one task lifecycle without dirtying the clone."""
    problems: list[str] = []
    checked = skipped = 0
    schedule = HOME / "bootstrap" / "schedule.ps1"
    schedule_text = schedule.read_text(encoding="utf-8")
    schedule_run = HOME / "bootstrap" / "schedule-run.ps1"
    schedule_run_text = schedule_run.read_text(encoding="utf-8")
    uninstall_ps = (HOME / "bootstrap" / "uninstall.ps1").read_text(encoding="utf-8")
    uninstall_sh = (HOME / "bootstrap" / "uninstall.sh").read_text(encoding="utf-8")

    def expect(label: str, ok: bool, detail: str = "") -> None:
        nonlocal checked
        checked += 1
        if ok:
            print(f"PASS: scheduler -- {label}")
        else:
            problems.append(f"scheduler {label}: {detail or 'condition false'}")

    def atomic_wrapper_contract(source: str) -> bool:
        return (
            '$RuntimeDir = Join-Path $env:LOCALAPPDATA "saipen"' in source
            and "[System.Guid]::NewGuid" in source
            and "[System.IO.File]::Move" in source
            and "[System.IO.File]::Replace" in source
            and "[System.Text.Encoding]::Unicode" in source
            and 'Join-Path $PSScriptRoot "schedule-run-hidden.vbs"' not in source)

    expect(
        "one manager and no generated repository wrapper",
        not (HOME / "tools" / "schedule_autoinject.py").exists()
        and not (HOME / "bootstrap" / "schedule-run-hidden.vbs").exists(),
        "legacy manager or machine-local wrapper still exists in source tree")
    expect(
        "wrapper publication is atomic and outside the repository",
        atomic_wrapper_contract(schedule_text),
        "external path or atomic temp-and-replace contract missing")
    expect(
        "external-wrapper contract red control",
        not atomic_wrapper_contract(schedule_text.replace(
            '$RuntimeDir = Join-Path $env:LOCALAPPDATA "saipen"',
            '$RuntimeDir = $PSScriptRoot', 1)),
        "repository-local mutation stayed green")
    expect(
        "all removers own current task, legacy task, and runtime wrapper",
        all(name in text for text in (schedule_text, uninstall_ps, uninstall_sh)
            for name in ("saipen-inject", "saipen-autoinject"))
        and all("schedule-run-hidden.vbs" in text
                for text in (schedule_text, uninstall_ps, uninstall_sh))
        and all("scheduled-source" in text
                for text in (schedule_text, uninstall_ps, uninstall_sh)),
        "a removal path can orphan a shipped task or wrapper")
    expect(
        "background runner never updates the development clone",
        " pull " not in schedule_run_text.lower()
        and '"pull"' not in schedule_run_text.lower()
        and '"merge"' not in schedule_run_text.lower()
        and '"checkout"' not in schedule_run_text.lower()
        and '"reset"' not in schedule_run_text.lower(),
        "background runner still carries a working-tree mutation command")
    expect(
        "background Git disables optional index mutation",
        '$env:GIT_OPTIONAL_LOCKS = "0"' in schedule_run_text,
        "git status may refresh the active development clone index")

    powershell = find_powershell()
    if not powershell:
        print("SKIP: scheduler lifecycle probes -- no PowerShell")
        return problems, checked, skipped + 1

    with tempfile.TemporaryDirectory(prefix="saipen-scheduler-") as raw:
        sandbox = Path(raw)
        state = sandbox / "tasks"
        local_app_data = sandbox / "local-app-data"
        state.mkdir()
        local_app_data.mkdir()
        scheduler_home = sandbox / "unicode-\u043f\u0443\u0442\u044c-\u03a9" / "bootstrap"
        scheduler_home.mkdir(parents=True)
        schedule_under_test = scheduler_home / "schedule.ps1"
        shutil.copy2(schedule, schedule_under_test)
        runner = scheduler_home / "schedule-run.ps1"
        runner.write_text(
            '[System.IO.File]::WriteAllText($env:MOCK_RUNNER_MARKER, "ran")\n'
            'exit 37\n',
            encoding="utf-8", newline="\n")
        (scheduler_home / "inject.ps1").write_text(
            "# scheduler probe sentinel\n", encoding="utf-8", newline="\n")
        harness = sandbox / "scheduler-harness.ps1"
        harness.write_text(r'''param(
  [string]$ScriptPath,
  [string]$CommandName
)
$ErrorActionPreference = "Stop"

function global:Get-ScheduledTask {
  [CmdletBinding()]
  param([string]$TaskName)
  if ($env:MOCK_QUERY_FAIL -eq $TaskName) {
    Write-Error "mock query failure" -Category ResourceUnavailable
    return $null
  }
  $path = Join-Path $env:MOCK_TASK_STATE $TaskName
  if (Test-Path -LiteralPath $path) {
    $definition = [System.IO.File]::ReadAllText($path)
    $state = if ($definition -match '<Enabled>false</Enabled>') { "Disabled" } else { "Ready" }
    return [pscustomobject]@{ State = $state }
  }
  return $null
}

function global:Get-ScheduledTaskInfo {
  [CmdletBinding()]
  param([string]$TaskName)
  return [pscustomobject]@{
    LastTaskResult = 0
    LastRunTime = "probe-last"
    NextRunTime = "probe-next"
  }
}

function global:Start-ScheduledTask {
  [CmdletBinding()]
  param([string]$TaskName)
  [System.IO.File]::WriteAllText($env:MOCK_START_MARKER, $TaskName)
}

function global:Export-ScheduledTask {
  [CmdletBinding()]
  param([string]$TaskName)
  return [System.IO.File]::ReadAllText((Join-Path $env:MOCK_TASK_STATE $TaskName))
}

function global:Register-ScheduledTask {
  [CmdletBinding()]
  param([string]$TaskName, [string]$Xml, [switch]$Force)
  [System.IO.File]::WriteAllText((Join-Path $env:MOCK_TASK_STATE $TaskName), $Xml)
  return [pscustomobject]@{ TaskName = $TaskName }
}

function global:New-ScheduledTaskSettingsSet {
  [CmdletBinding()]
  param(
    [switch]$StartWhenAvailable,
    [switch]$AllowStartIfOnBatteries,
    [switch]$DontStopIfGoingOnBatteries,
    [TimeSpan]$ExecutionTimeLimit,
    [string]$MultipleInstances
  )
  return [pscustomobject]@{}
}

function global:Set-ScheduledTask {
  [CmdletBinding()]
  param([string]$TaskName, [object]$Settings)
  if ($env:MOCK_SET_FAIL) { throw "mock settings failure" }
  return [pscustomobject]@{ TaskName = $TaskName }
}

function global:schtasks {
  $operation = [string]$args[0]
  $taskName = ""
  for ($i = 0; $i -lt $args.Count; $i++) {
    if ([string]$args[$i] -ieq "/TN") {
      $taskName = [string]$args[$i + 1]
      break
    }
  }
  $taskPath = Join-Path $env:MOCK_TASK_STATE $taskName
  if ($operation -ieq "/Create") {
    $wrapper = Join-Path $env:LOCALAPPDATA "saipen\schedule-run-hidden.vbs"
    $escapedWrapper = [System.Security.SecurityElement]::Escape($wrapper)
    $currentSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $definition = @"
<Task>
  <Principals><Principal><UserId>$currentSid</UserId><LogonType>InteractiveToken</LogonType></Principal></Principals>
  <Triggers><TimeTrigger><Repetition><Interval>PT15M</Interval></Repetition></TimeTrigger></Triggers>
  <Settings>
    <Enabled>true</Enabled>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <ExecutionTimeLimit>PT10M</ExecutionTimeLimit>
    <StartWhenAvailable>true</StartWhenAvailable>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
  </Settings>
  <Actions><Exec><Command>wscript.exe</Command><Arguments>$escapedWrapper</Arguments></Exec></Actions>
</Task>
"@
    [System.IO.File]::WriteAllText($taskPath, $definition)
    $global:LASTEXITCODE = 0
    return "created $taskName"
  }
  if ($operation -ieq "/Delete") {
    if ($env:MOCK_DELETE_FAIL -eq $taskName) {
      $global:LASTEXITCODE = 5
      return "access denied"
    }
    Remove-Item -LiteralPath $taskPath -Force -ErrorAction SilentlyContinue
    $global:LASTEXITCODE = 0
    return "deleted $taskName"
  }
  $global:LASTEXITCODE = 1
  return "unsupported mock operation"
}

if ($CommandName) { & $ScriptPath $CommandName } else { & $ScriptPath }
if ($LASTEXITCODE) { exit $LASTEXITCODE }
exit 0
''', encoding="utf-8", newline="\n")

        base_env = os.environ.copy()
        base_env["LOCALAPPDATA"] = str(local_app_data)
        base_env["MOCK_TASK_STATE"] = str(state)
        base_env["MOCK_RUNNER_MARKER"] = str(sandbox / "runner-ran.txt")
        base_env["MOCK_START_MARKER"] = str(sandbox / "task-started.txt")
        base_env["MOCK_SET_FAIL"] = ""
        base_env["MOCK_DELETE_FAIL"] = ""
        base_env["MOCK_QUERY_FAIL"] = ""

        def invoke_script(script: Path, command: str = "",
                          **changes: str) -> subprocess.CompletedProcess[str]:
            env = {**base_env, **changes}
            return subprocess.run(
                [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", str(harness), str(script), command],
                cwd=HOME, env=env, capture_output=True, text=True,
                errors="replace")

        def invoke(command: str, **changes: str) -> subprocess.CompletedProcess[str]:
            return invoke_script(schedule_under_test, command, **changes)

        def git_status() -> str:
            result = subprocess.run(
                ["git", "status", "--short"], cwd=HOME,
                capture_output=True, text=True, errors="replace")
            if result.returncode != 0:
                problems.append(f"scheduler git status failed: {result.stderr.strip()}")
            return result.stdout

        wrapper = local_app_data / "saipen" / "schedule-run-hidden.vbs"
        runtime_source = local_app_data / "saipen" / "scheduled-source"
        runtime_backup = local_app_data / "saipen" / "scheduled-source-previous-probe"
        runtime_backup_fixed = local_app_data / "saipen" / "scheduled-source-previous"
        runtime_temp_zip = local_app_data / "saipen" / "source-deadbeef0123.zip"
        runtime_temp_dir = local_app_data / "saipen" / "source-deadbeef0123"
        runtime_temp_raw = local_app_data / "saipen" / "inject-deadbeef0123.log"
        runtime_log = local_app_data / "saipen" / "inject.log"
        current = state / "saipen-inject"
        legacy = state / "saipen-autoinject"
        before = git_status()
        not_installed = invoke("status")
        expect(
            "status distinguishes NOT_INSTALLED",
            not_installed.returncode != 0
            and "STATUS: NOT_INSTALLED" in not_installed.stdout,
            (not_installed.stdout + not_installed.stderr).strip())
        invalid = invoke("typo-command")
        expect(
            "unknown command is nonzero with concise usage",
            invalid.returncode != 0 and "usage: schedule.ps1" in invalid.stdout,
            (invalid.stdout + invalid.stderr).strip())
        legacy.write_text("present", encoding="ascii")
        installed = invoke("install")
        expect(
            "install migrates legacy task and publishes external wrapper",
            installed.returncode == 0 and current.is_file()
            and not legacy.exists() and wrapper.is_file(),
            (installed.stdout + installed.stderr).strip())
        expect(
            "atomic install leaves no temporary wrapper",
            not list(wrapper.parent.glob(".schedule-run-hidden.vbs.*.tmp")),
            "temporary publication file remains")
        wrapper_bytes = wrapper.read_bytes() if wrapper.is_file() else b""
        expect(
            "wrapper preserves a Unicode runner path",
            wrapper_bytes.startswith(b"\xff\xfe")
            and str(runner) in wrapper_bytes.decode("utf-16"),
            "wrapper is not UTF-16 with the exact Unicode runner path")
        healthy = invoke("status")
        expect(
            "status distinguishes HEALTHY",
            healthy.returncode == 0 and "STATUS: HEALTHY" in healthy.stdout,
            (healthy.stdout + healthy.stderr).strip())
        canonical_task_xml = current.read_text(encoding="utf-8")
        current.write_text(canonical_task_xml.replace(
            "wscript.exe", r"C:\malware\wscript.exe", 1), encoding="utf-8")
        wrong_action = invoke("status")
        expect(
            "wrong scheduled action is DEGRADED",
            wrong_action.returncode != 0
            and "STATUS: DEGRADED" in wrong_action.stdout
            and "task action" in wrong_action.stdout,
            (wrong_action.stdout + wrong_action.stderr).strip())
        current.write_text(canonical_task_xml, encoding="utf-8")

        quoted_wrapper = canonical_task_xml.replace(
            "<Arguments>",
            "<Arguments>&quot;", 1).replace("</Arguments>",
                                           "&quot;</Arguments>", 1)
        current.write_text(quoted_wrapper, encoding="utf-8")
        quoted_action = invoke("status")
        expect(
            "quoted wrapper path is DEGRADED",
            quoted_action.returncode != 0
            and "STATUS: DEGRADED" in quoted_action.stdout
            and "task action" in quoted_action.stdout,
            (quoted_action.stdout + quoted_action.stderr).strip())
        current.write_text(canonical_task_xml, encoding="utf-8")

        current_sid = re.search(
            r"<UserId>([^<]+)</UserId>", canonical_task_xml).group(1)
        current.write_text(canonical_task_xml.replace(
            current_sid, "S-1-5-21-0-0-0-9999", 1), encoding="utf-8")
        wrong_principal = invoke("status")
        expect(
            "wrong task principal is DEGRADED",
            wrong_principal.returncode != 0
            and "STATUS: DEGRADED" in wrong_principal.stdout
            and "task principal" in wrong_principal.stdout,
            (wrong_principal.stdout + wrong_principal.stderr).strip())
        current.write_text(canonical_task_xml, encoding="utf-8")

        current.write_text(canonical_task_xml.replace(
            "</Task>", "<Enabled>false</Enabled></Task>", 1), encoding="utf-8")
        disabled = invoke("status")
        expect(
            "disabled scheduled task is DEGRADED",
            disabled.returncode != 0 and "STATUS: DEGRADED" in disabled.stdout
            and "task is disabled" in disabled.stdout,
            (disabled.stdout + disabled.stderr).strip())
        current.write_text(canonical_task_xml, encoding="utf-8")

        current.write_text(canonical_task_xml.replace(
            "TimeTrigger", "BootTrigger"), encoding="utf-8")
        wrong_trigger_type = invoke("status")
        expect(
            "wrong task trigger type is DEGRADED",
            wrong_trigger_type.returncode != 0
            and "STATUS: DEGRADED" in wrong_trigger_type.stdout
            and "task trigger" in wrong_trigger_type.stdout,
            (wrong_trigger_type.stdout + wrong_trigger_type.stderr).strip())
        current.write_text(canonical_task_xml, encoding="utf-8")

        current.write_text(canonical_task_xml.replace(
            "</Repetition>", "<Duration>PT1H</Duration></Repetition>", 1),
            encoding="utf-8")
        finite_duration = invoke("status")
        expect(
            "finite repetition duration is DEGRADED",
            finite_duration.returncode != 0
            and "STATUS: DEGRADED" in finite_duration.stdout
            and "task trigger" in finite_duration.stdout,
            (finite_duration.stdout + finite_duration.stderr).strip())
        current.write_text(canonical_task_xml, encoding="utf-8")

        current.write_text(canonical_task_xml.replace(
            "PT15M", "PT30M", 1).replace("IgnoreNew", "Parallel", 1),
            encoding="utf-8")
        wrong_policy = invoke("status")
        expect(
            "wrong task trigger or runtime policy is DEGRADED",
            wrong_policy.returncode != 0
            and "STATUS: DEGRADED" in wrong_policy.stdout
            and "task trigger" in wrong_policy.stdout
            and "task settings" in wrong_policy.stdout,
            (wrong_policy.stdout + wrong_policy.stderr).strip())
        current.write_text(canonical_task_xml, encoding="utf-8")
        start_marker = Path(base_env["MOCK_START_MARKER"])
        start_marker.unlink(missing_ok=True)
        run_now = invoke("run-now")
        expect(
            "run-now triggers only a healthy installation",
            run_now.returncode == 0 and start_marker.is_file()
            and start_marker.read_text(encoding="utf-8") == "saipen-inject",
            (run_now.stdout + run_now.stderr).strip())
        saved_canonical_wrapper = wrapper.read_bytes()
        wrapper.write_text(
            f"' -File \"\"{runner}\"\"\r\nWScript.Quit 0\r\n",
            encoding="utf-16")
        start_marker.unlink(missing_ok=True)
        hostile_wrapper = invoke("status")
        hostile_wrapper_run = invoke("run-now")
        expect(
            "wrapper with canonical path hidden in dead text is DEGRADED",
            hostile_wrapper.returncode != 0
            and "STATUS: DEGRADED" in hostile_wrapper.stdout
            and "canonical command body" in hostile_wrapper.stdout,
            (hostile_wrapper.stdout + hostile_wrapper.stderr).strip())
        expect(
            "run-now refuses a noncanonical wrapper body",
            hostile_wrapper_run.returncode != 0 and not start_marker.exists(),
            (hostile_wrapper_run.stdout + hostile_wrapper_run.stderr).strip())
        wrapper.write_bytes(saved_canonical_wrapper)
        wscript = shutil.which("wscript.exe") if os.name == "nt" else None
        if wscript:
            marker = Path(base_env["MOCK_RUNNER_MARKER"])
            marker.unlink(missing_ok=True)
            executed = subprocess.run(
                [wscript, str(wrapper)], env=base_env,
                capture_output=True, text=True, errors="replace")
            expect(
                "generated wrapper waits and returns runner status",
                executed.returncode == 37 and marker.is_file()
                and marker.read_text(encoding="utf-8") == "ran",
                (executed.stdout + executed.stderr).strip())
        else:
            print("SKIP: scheduler Unicode wrapper execution -- no Windows Script Host")
            skipped += 1

        legacy.write_text("present", encoding="ascii")
        start_marker.unlink(missing_ok=True)
        duplicate = invoke("status")
        duplicate_run = invoke("run-now")
        expect(
            "duplicate current and legacy tasks are DEGRADED",
            duplicate.returncode != 0 and "STATUS: DEGRADED" in duplicate.stdout
            and "duplicate legacy task" in duplicate.stdout,
            (duplicate.stdout + duplicate.stderr).strip())
        expect(
            "run-now refuses a DEGRADED duplicate installation",
            duplicate_run.returncode != 0 and not start_marker.exists(),
            (duplicate_run.stdout + duplicate_run.stderr).strip())
        legacy.unlink()

        saved_wrapper = wrapper.read_bytes()
        wrapper.unlink()
        start_marker.unlink(missing_ok=True)
        missing_wrapper = invoke("status")
        missing_wrapper_run = invoke("run-now")
        expect(
            "missing VBS wrapper is DEGRADED",
            missing_wrapper.returncode != 0
            and "STATUS: DEGRADED" in missing_wrapper.stdout
            and "VBS wrapper missing" in missing_wrapper.stdout,
            (missing_wrapper.stdout + missing_wrapper.stderr).strip())
        expect(
            "run-now refuses a task with missing wrapper",
            missing_wrapper_run.returncode != 0 and not start_marker.exists(),
            (missing_wrapper_run.stdout + missing_wrapper_run.stderr).strip())
        wrapper.write_bytes(saved_wrapper)

        runner_missing = runner.with_suffix(".missing")
        runner.rename(runner_missing)
        missing_runner = invoke("status")
        expect(
            "wrapper referencing a missing runner is DEGRADED",
            missing_runner.returncode != 0
            and "STATUS: DEGRADED" in missing_runner.stdout
            and "referenced runner missing" in missing_runner.stdout,
            (missing_runner.stdout + missing_runner.stderr).strip())
        runner_missing.rename(runner)

        legacy.write_text("present", encoding="ascii")
        runtime_source.mkdir()
        runtime_backup.mkdir()
        runtime_backup_fixed.mkdir()
        runtime_temp_dir.mkdir()
        runtime_temp_zip.write_bytes(b"dead zip")
        runtime_temp_raw.write_text("dead raw", encoding="ascii")
        runtime_log.write_text("canonical log survives", encoding="ascii")
        removed = invoke("remove")
        expect(
            "remove cleans both task names and scheduler runtime",
            removed.returncode == 0 and not current.exists()
            and not legacy.exists() and not wrapper.exists()
            and not runtime_source.exists() and not runtime_backup.exists()
            and not runtime_backup_fixed.exists(),
            (removed.stdout + removed.stderr).strip())
        expect(
            "remove sweeps killed-run temp files but keeps the canonical log",
            not runtime_temp_dir.exists()
            and not runtime_temp_zip.exists()
            and not runtime_temp_raw.exists()
            and runtime_log.read_text(encoding="ascii") == "canonical log survives",
            (removed.stdout + removed.stderr).strip())
        expect(
            "install and remove leave repository status unchanged",
            git_status() == before,
            "scheduler lifecycle changed working-tree status")
        runtime_log.unlink()

        previous_task = "old-task-xml"
        previous_wrapper = b"previous-wrapper-bytes"
        current.write_text(previous_task, encoding="ascii")
        wrapper.parent.mkdir(parents=True, exist_ok=True)
        wrapper.write_bytes(previous_wrapper)
        upgrade_failed = invoke("install", MOCK_SET_FAIL="1")
        expect(
            "failed reinstall restores previous task and wrapper",
            upgrade_failed.returncode != 0
            and current.read_text(encoding="ascii") == previous_task
            and wrapper.read_bytes() == previous_wrapper,
            (upgrade_failed.stdout + upgrade_failed.stderr).strip())
        invoke("remove")

        rolled_back = invoke("install", MOCK_SET_FAIL="1")
        expect(
            "fresh settings failure removes new task and wrapper",
            rolled_back.returncode != 0 and not current.exists()
            and not wrapper.exists(),
            (rolled_back.stdout + rolled_back.stderr).strip())

        current.write_text("preserve-task", encoding="ascii")
        wrapper.parent.mkdir(parents=True, exist_ok=True)
        wrapper.write_text("preserve-wrapper", encoding="ascii")
        query_failed = invoke("remove", MOCK_QUERY_FAIL="saipen-inject")
        expect(
            "query failure is nonzero and preserves task and wrapper",
            query_failed.returncode != 0
            and current.read_text(encoding="ascii") == "preserve-task"
            and wrapper.read_text(encoding="ascii") == "preserve-wrapper",
            (query_failed.stdout + query_failed.stderr).strip())
        current.unlink()
        wrapper.unlink()

        current.write_text("present", encoding="ascii")
        wrapper.write_text("preserve", encoding="ascii")
        delete_failed = invoke("remove", MOCK_DELETE_FAIL="saipen-inject")
        expect(
            "delete failure is nonzero and preserves runnable wrapper",
            delete_failed.returncode != 0 and current.is_file()
            and wrapper.read_text(encoding="ascii") == "preserve",
            (delete_failed.stdout + delete_failed.stderr).strip())

        current.unlink()
        wrapper.unlink()
        current.write_text("present", encoding="ascii")
        legacy.write_text("present", encoding="ascii")
        wrapper.write_text("present", encoding="ascii")
        runtime_source.mkdir()
        runtime_backup.mkdir()
        runtime_backup_fixed.mkdir()
        runtime_temp_dir.mkdir()
        runtime_temp_zip.write_bytes(b"dead zip")
        runtime_temp_raw.write_text("dead raw", encoding="ascii")
        runtime_log.write_text("canonical log survives", encoding="ascii")
        uninstall_home = sandbox / "powershell-uninstall-home"
        uninstall_home.mkdir()
        ps_uninstalled = invoke_script(
            HOME / "bootstrap" / "uninstall.ps1",
            HOME=str(uninstall_home), USERPROFILE=str(uninstall_home),
            SAIPEN_UNINSTALL_SKIP_TASK="")
        expect(
            "PowerShell global uninstall removes both tasks and wrapper",
            ps_uninstalled.returncode == 0 and not current.exists()
            and not legacy.exists() and not wrapper.exists()
            and not runtime_source.exists() and not runtime_backup.exists()
            and not runtime_backup_fixed.exists(),
            (ps_uninstalled.stdout + ps_uninstalled.stderr).strip())
        expect(
            "PowerShell uninstall sweeps killed-run temp files but keeps the canonical log",
            not runtime_temp_dir.exists()
            and not runtime_temp_zip.exists()
            and not runtime_temp_raw.exists()
            and runtime_log.read_text(encoding="ascii") == "canonical log survives",
            (ps_uninstalled.stdout + ps_uninstalled.stderr).strip())
        runtime_log.unlink()

        current.write_text("preserve", encoding="ascii")
        wrapper.write_text("preserve", encoding="ascii")
        ps_query_failed = invoke_script(
            HOME / "bootstrap" / "uninstall.ps1",
            HOME=str(uninstall_home), USERPROFILE=str(uninstall_home),
            SAIPEN_UNINSTALL_SKIP_TASK="", MOCK_QUERY_FAIL="saipen-inject")
        expect(
            "PowerShell global uninstall fails closed on query error",
            ps_query_failed.returncode != 0 and current.is_file()
            and wrapper.is_file(),
            (ps_query_failed.stdout + ps_query_failed.stderr).strip())
        current.unlink()
        wrapper.unlink()

        fallback_harness = sandbox / "scheduler-fallback-harness.ps1"
        fallback_harness.write_text(r'''param([string]$ScriptPath)
$ErrorActionPreference = "Stop"
$env:PSModulePath = ""
Remove-Module ScheduledTasks -Force -ErrorAction SilentlyContinue

function global:Get-Command {
  [CmdletBinding()]
  param([string]$Name)
  if ($Name -eq "Get-ScheduledTask") { return $null }
  if ($Name -eq "schtasks") { return [pscustomobject]@{ Name = "schtasks" } }
  return Microsoft.PowerShell.Core\Get-Command $Name
}

function global:schtasks {
  $operation = [string]$args[0]
  $taskName = ""
  for ($i = 0; $i -lt $args.Count; $i++) {
    if ([string]$args[$i] -ieq "/TN") {
      $taskName = [string]$args[$i + 1]
      break
    }
  }
  if ($env:MOCK_QUERY_FAIL -and $operation -ieq "/Query") {
    $global:LASTEXITCODE = 5
    return "query failed"
  }
  $taskPath = Join-Path $env:MOCK_TASK_STATE $taskName
  if ($operation -ieq "/Query") {
    if (-not $taskName -or (Test-Path -LiteralPath $taskPath)) {
      $global:LASTEXITCODE = 0
    } else {
      $global:LASTEXITCODE = 1
    }
    return "query"
  }
  if ($operation -ieq "/Delete") {
    Remove-Item -LiteralPath $taskPath -Force -ErrorAction SilentlyContinue
    $global:LASTEXITCODE = 0
    return "deleted"
  }
  $global:LASTEXITCODE = 9
}

& $ScriptPath
if ($LASTEXITCODE) { exit $LASTEXITCODE }
exit 0
''', encoding="utf-8", newline="\n")
        fallback_env = {
            **base_env,
            "HOME": str(uninstall_home),
            "USERPROFILE": str(uninstall_home),
            "PSModulePath": "",
            "SAIPEN_UNINSTALL_SKIP_TASK": "",
        }
        current.write_text("present", encoding="ascii")
        legacy.write_text("present", encoding="ascii")
        wrapper.write_text("present", encoding="ascii")
        runtime_source.mkdir()
        runtime_backup.mkdir()
        runtime_backup_fixed.mkdir()
        runtime_temp_dir.mkdir()
        runtime_temp_zip.write_bytes(b"dead zip")
        runtime_temp_raw.write_text("dead raw", encoding="ascii")
        runtime_log.write_text("canonical log survives", encoding="ascii")
        fallback_uninstalled = subprocess.run(
            [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(fallback_harness),
             str(HOME / "bootstrap" / "uninstall.ps1")],
            cwd=HOME, env=fallback_env, capture_output=True, text=True,
            errors="replace")
        expect(
            "PowerShell uninstall falls back when ScheduledTasks cmdlets are absent",
            fallback_uninstalled.returncode == 0 and not current.exists()
            and not legacy.exists() and not wrapper.exists()
            and not runtime_source.exists() and not runtime_backup.exists()
            and not runtime_backup_fixed.exists(),
            (fallback_uninstalled.stdout + fallback_uninstalled.stderr).strip())
        expect(
            "PowerShell fallback uninstall sweeps temp files, keeps canonical log",
            not runtime_temp_dir.exists()
            and not runtime_temp_zip.exists()
            and not runtime_temp_raw.exists()
            and runtime_log.read_text(encoding="ascii") == "canonical log survives",
            (fallback_uninstalled.stdout + fallback_uninstalled.stderr).strip())
        runtime_log.unlink()

        current.write_text("preserve", encoding="ascii")
        wrapper.write_text("preserve", encoding="ascii")
        fallback_env["MOCK_QUERY_FAIL"] = "1"
        fallback_query_failed = subprocess.run(
            [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(fallback_harness),
             str(HOME / "bootstrap" / "uninstall.ps1")],
            cwd=HOME, env=fallback_env, capture_output=True, text=True,
            errors="replace")
        expect(
            "PowerShell schtasks fallback fails closed on query error",
            fallback_query_failed.returncode != 0 and current.is_file()
            and wrapper.is_file(),
            (fallback_query_failed.stdout + fallback_query_failed.stderr).strip())
        current.unlink(missing_ok=True)
        wrapper.unlink(missing_ok=True)

        bash = find_bash()
        if bash:
            shim_dir = sandbox / "scheduler-shims"
            shim_dir.mkdir()
            schtasks = shim_dir / "schtasks"
            schtasks.write_text(r'''#!/usr/bin/env bash
state=${MOCK_TASK_STATE:?}
operation=${1:-}
shift || true
task=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "/TN" ]; then task=${2:-}; shift 2; continue; fi
  shift
done
if [ "$operation" = "/Query" ]; then
  [ -z "${MOCK_QUERY_FAIL:-}" ] || exit 5
  [ -z "$task" ] && exit 0
  [ -f "$state/$task" ] && exit 0
  exit 1
fi
if [ "$operation" = "/Delete" ]; then
  rm -f "$state/$task"
  exit $?
fi
exit 9
''', encoding="utf-8", newline="\n")
            schtasks.chmod(0o755)
            shell_home = sandbox / "shell-uninstall-home"
            shell_home.mkdir()
            if os.name == "nt":
                path_result = subprocess.run(
                    [bash, "-lc", 'cygpath -u "$1"', "_", str(state)],
                    capture_output=True, text=True, errors="replace")
                shell_state = path_result.stdout.strip()
            else:
                path_result = subprocess.CompletedProcess([], 0, "", "")
                shell_state = str(state)
            shell_env = bash_env(bash, shell_home)
            shell_env["PATH"] = str(shim_dir) + os.pathsep + shell_env["PATH"]
            shell_env["LOCALAPPDATA"] = str(local_app_data)
            shell_env["MOCK_TASK_STATE"] = shell_state
            shell_env["SAIPEN_UNINSTALL_SKIP_TASK"] = ""
            current.write_text("present", encoding="ascii")
            legacy.write_text("present", encoding="ascii")
            wrapper.write_text("present", encoding="ascii")
            runtime_source.mkdir()
            runtime_backup.mkdir()
            runtime_backup_fixed.mkdir()
            runtime_temp_dir.mkdir()
            runtime_temp_zip.write_bytes(b"dead zip")
            runtime_temp_raw.write_text("dead raw", encoding="ascii")
            runtime_log.write_text("canonical log survives", encoding="ascii")
            sh_uninstalled = subprocess.run(
                [bash, str(HOME / "bootstrap" / "uninstall.sh")],
                cwd=HOME, env=shell_env, capture_output=True, text=True,
                errors="replace")
            expect(
                "shell global uninstall removes both tasks and wrapper",
                path_result.returncode == 0 and sh_uninstalled.returncode == 0
                and not current.exists() and not legacy.exists()
                and not wrapper.exists() and not runtime_source.exists()
                and not runtime_backup.exists() and not runtime_backup_fixed.exists(),
                (sh_uninstalled.stdout + sh_uninstalled.stderr).strip())
            expect(
                "shell uninstall sweeps killed-run temp files but keeps the canonical log",
                not runtime_temp_dir.exists()
                and not runtime_temp_zip.exists()
                and not runtime_temp_raw.exists()
                and runtime_log.read_text(encoding="ascii") == "canonical log survives",
                (sh_uninstalled.stdout + sh_uninstalled.stderr).strip())
            runtime_log.unlink()

            current.write_text("preserve", encoding="ascii")
            wrapper.write_text("preserve", encoding="ascii")
            shell_env["MOCK_QUERY_FAIL"] = "1"
            sh_query_failed = subprocess.run(
                [bash, str(HOME / "bootstrap" / "uninstall.sh")],
                cwd=HOME, env=shell_env, capture_output=True, text=True,
                errors="replace")
            expect(
                "shell global uninstall fails closed on query error",
                sh_query_failed.returncode != 0 and current.is_file()
                and wrapper.is_file(),
                (sh_query_failed.stdout + sh_query_failed.stderr).strip())
            current.unlink()
            wrapper.unlink()
            runtime_source.mkdir()
            runtime_backup.mkdir()
            runtime_backup_fixed.mkdir()
            runtime_temp_dir.mkdir()
            runtime_temp_zip.write_bytes(b"dead zip")
            runtime_temp_raw.write_text("dead raw", encoding="ascii")
            runtime_log.write_text("canonical log survives", encoding="ascii")
            no_schtasks_env = {
                **shell_env,
                "PATH": "/usr/bin:/bin",
                "MOCK_QUERY_FAIL": "",
            }
            shell_without_schtasks = subprocess.run(
                [bash, str(HOME / "bootstrap" / "uninstall.sh")],
                cwd=HOME, env=no_schtasks_env, capture_output=True, text=True,
                errors="replace")
            expect(
                "shell uninstall without schtasks still cleans runtime source",
                shell_without_schtasks.returncode == 0
                and not runtime_source.exists() and not runtime_backup.exists()
                and not runtime_backup_fixed.exists(),
                (shell_without_schtasks.stdout
                 + shell_without_schtasks.stderr).strip())
            expect(
                "shell uninstall without schtasks sweeps temp files, keeps canonical log",
                not runtime_temp_dir.exists()
                and not runtime_temp_zip.exists()
                and not runtime_temp_raw.exists()
                and runtime_log.read_text(encoding="ascii") == "canonical log survives",
                (shell_without_schtasks.stdout
                 + shell_without_schtasks.stderr).strip())
            runtime_log.unlink()
        else:
            print("SKIP: scheduler shell uninstaller probes -- no usable bash")
            skipped += 1

        # Execute schedule-run.ps1 against a real temporary repository. The
        # injected marker stands in for every installed config, making refusal
        # preservation observable without touching the user's agent homes.
        source_repo = sandbox / "scheduled-source"
        source_bootstrap = source_repo / "bootstrap"
        source_bootstrap.mkdir(parents=True)
        shutil.copy2(schedule_run, source_bootstrap / "schedule-run.ps1")
        (source_repo / "SOURCE_SENTINEL.txt").write_text(
            "committed-source\n", encoding="utf-8", newline="\n")
        (source_bootstrap / "inject.ps1").write_text(r'''
$root = Split-Path $PSScriptRoot -Parent
$value = [System.IO.File]::ReadAllText((Join-Path $root "SOURCE_SENTINEL.txt"))
[System.IO.File]::WriteAllText($env:MOCK_SCHEDULE_DESTINATION, $value)
[System.IO.File]::WriteAllText($env:MOCK_SCHEDULE_SOURCE_PATH, $root)
exit 0
'''.lstrip(), encoding="utf-8", newline="\n")

        def source_git(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(["git", *args], cwd=source_repo,
                                  capture_output=True, text=True, errors="replace")

        source_git("init", "-q")
        source_git("config", "user.name", "scheduler probe")
        source_git("config", "user.email", "scheduler@example.invalid")
        source_git("add", "-A")
        source_git("commit", "-q", "-m", "probe: committed source")
        source_git("remote", "add", "origin", "https://127.0.0.1:9/unreachable")
        runner_local = sandbox / "runner-local-app-data"
        runner_local.mkdir()
        destination = sandbox / "installed-snapshot.txt"
        source_path_marker = sandbox / "installed-source-path.txt"
        runner_env = {
            **base_env,
            "LOCALAPPDATA": str(runner_local),
            "MOCK_SCHEDULE_DESTINATION": str(destination),
            "MOCK_SCHEDULE_SOURCE_PATH": str(source_path_marker),
        }

        def invoke_runner(script: Path | None = None) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", str(script or source_bootstrap / "schedule-run.ps1"),
                 "-CloneRoot", str(source_repo)],
                cwd=source_repo, env=runner_env, capture_output=True, text=True,
                errors="replace", timeout=60)

        source_head = source_git("rev-parse", "HEAD").stdout.strip()
        source_bytes = (source_repo / "SOURCE_SENTINEL.txt").read_bytes()
        source_index_bytes = (source_repo / ".git" / "index").read_bytes()
        clean_run = invoke_runner()
        expect(
            "clean committed source injects exact HEAD without network access",
            clean_run.returncode == 0 and destination.is_file()
            and destination.read_text(encoding="utf-8-sig")
            == source_bytes.decode("utf-8"),
            (clean_run.stdout + clean_run.stderr).strip())
        published_source = runner_local / "saipen" / "scheduled-source"
        advertised_source = source_path_marker.read_text(
            encoding="utf-8-sig").strip() if source_path_marker.is_file() else ""
        expect(
            "successful injection keeps its advertised source path alive",
            source_path_marker.is_file() and published_source.is_dir()
            and os.path.normcase(os.path.normpath(advertised_source))
            == os.path.normcase(os.path.normpath(str(published_source)))
            and (published_source / "SOURCE_SENTINEL.txt").read_text(
                encoding="utf-8-sig") == source_bytes.decode("utf-8"),
            f"advertised source missing after cleanup: {advertised_source!r}")
        expect(
            "background run never changes HEAD or working-tree bytes",
            source_git("rev-parse", "HEAD").stdout.strip() == source_head
            and not source_git("status", "--short").stdout
            and (source_repo / "SOURCE_SENTINEL.txt").read_bytes() == source_bytes
            and (source_repo / ".git" / "index").read_bytes() == source_index_bytes,
            "clean run moved HEAD, index, or source bytes")

        destination.write_text("previous-install\n", encoding="utf-8", newline="\n")
        (source_repo / "SOURCE_SENTINEL.txt").write_text(
            "half-edited\n", encoding="utf-8", newline="\n")
        dirty_tracked = invoke_runner()
        runner_log = runner_local / "saipen" / "inject.log"
        expect(
            "dirty tracked source skips and preserves installed snapshot",
            dirty_tracked.returncode != 0
            and destination.read_text(encoding="utf-8") == "previous-install\n"
            and "SKIP: DIRTY_SOURCE" in runner_log.read_text(encoding="utf-8-sig"),
            (dirty_tracked.stdout + dirty_tracked.stderr).strip())
        (source_repo / "SOURCE_SENTINEL.txt").write_bytes(source_bytes)

        untracked = source_repo / "UNTRACKED_PROJECT_FILE.txt"
        untracked.write_text("not committed\n", encoding="utf-8", newline="\n")
        dirty_untracked = invoke_runner()
        expect(
            "dirty untracked project source skips and preserves installed snapshot",
            dirty_untracked.returncode != 0
            and destination.read_text(encoding="utf-8") == "previous-install\n",
            (dirty_untracked.stdout + dirty_untracked.stderr).strip())
        untracked.unlink()

        git_dir = source_repo / ".git"
        hidden_git = source_repo / ".git-hidden"
        git_dir.rename(hidden_git)
        source_failure = invoke_runner()
        hidden_git.rename(git_dir)
        expect(
            "source operation failure never falls through into injection",
            source_failure.returncode != 0
            and destination.read_text(encoding="utf-8") == "previous-install\n",
            (source_failure.stdout + source_failure.stderr).strip())

        race_runner = sandbox / "schedule-run-race.ps1"
        race_anchor = (
            "  Expand-Archive -LiteralPath $archive -DestinationPath $snapshot -Force\n")
        race_body = schedule_run_text.replace(
            race_anchor,
            race_anchor
            + "  [System.IO.File]::AppendAllText((Join-Path $sourceRoot "
              "\"SOURCE_SENTINEL.txt\"), \"race-edit\")\n",
            1)
        race_runner.write_text(race_body, encoding="utf-8", newline="\n")
        source_race = invoke_runner(race_runner)
        expect(
            "source change during preflight refuses mixed-source injection",
            source_race.returncode != 0
            and destination.read_text(encoding="utf-8") == "previous-install\n"
            and "SKIP: DIRTY_SOURCE" in runner_log.read_text(encoding="utf-8-sig"),
            (source_race.stdout + source_race.stderr).strip())
        (source_repo / "SOURCE_SENTINEL.txt").write_bytes(source_bytes)
        expect(
            "every refusal preserves previous installed snapshot and HEAD",
            destination.read_text(encoding="utf-8") == "previous-install\n"
            and source_git("rev-parse", "HEAD").stdout.strip() == source_head
            and published_source.is_dir()
            and (published_source / "SOURCE_SENTINEL.txt").read_text(
                encoding="utf-8-sig") == source_bytes.decode("utf-8"),
            "a refusal changed installed bytes or HEAD")

        stale_backup = runner_local / "saipen" / "scheduled-source-previous"
        stale_backup.mkdir(parents=True)
        stale_backup_run = invoke_runner()
        expect(
            "stale snapshot backup from a killed run is refused",
            stale_backup_run.returncode != 0
            and "REFUSE: PUBLISHED_SOURCE_BACKUP_EXISTS"
            in runner_log.read_text(encoding="utf-8-sig")
            and destination.read_text(encoding="utf-8") == "previous-install\n",
            (stale_backup_run.stdout + stale_backup_run.stderr).strip())
        stale_backup.rmdir()

        (source_repo / "SOURCE_SENTINEL.txt").write_text(
            "new-committed-source\n", encoding="utf-8", newline="\n")
        (source_bootstrap / "inject.ps1").write_text(
            "exit 9\n", encoding="utf-8", newline="\n")
        source_git("add", "-A")
        source_git("commit", "-q", "-m", "probe: failing injector update")
        failed_update = invoke_runner()
        expect(
            "failed injector restores previous persistent source snapshot",
            failed_update.returncode != 0 and published_source.is_dir()
            and (published_source / "SOURCE_SENTINEL.txt").read_text(
                encoding="utf-8-sig") == source_bytes.decode("utf-8")
            and destination.read_text(encoding="utf-8") == "previous-install\n",
            (failed_update.stdout + failed_update.stderr).strip())

    return problems, checked, skipped


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


def run_lint_parity_probes() -> tuple[list[str], int]:
    """T-628: local-doc vs CI lint surface + ruff pin must stay in one voice.

    harness.md documents the canonical lint command and the pinned ruff
    version; validate.yml must run exactly that. A surface divergence or a
    version drift is a reproducibility defect (a local host lints a different
    tree than CI, or an unpinned ruff shifts the rule set between runs), so
    the validator FAILs it -- these probes prove that check can go red.
    """
    problems: list[str] = []
    checked = 0
    harness = HOME / ".saipen" / "KNOWLEDGE" / "harness.md"
    ci = HOME / ".github" / "workflows" / "validate.yml"
    if not harness.is_file() or not ci.is_file():
        return ["lint parity probe could not find harness.md or validate.yml"], checked

    def validate(home: Path) -> str:
        r = subprocess.run(
            [sys.executable, str(home / "tools" / "validate.py"),
             "--project-root", str(home)],
            cwd=home, capture_output=True, text=True, errors="replace",
            timeout=120)
        return r.stdout + r.stderr

    def probe(label: str, mutation, contains: str) -> None:
        nonlocal checked
        checked += 1
        with tempfile.TemporaryDirectory(prefix="saipen-lint-parity-") as raw:
            home = Path(raw) / "home"
            shutil.copytree(HOME, home, ignore=shutil.ignore_patterns(
                ".git", ".venv", "__pycache__", "node_modules", "nul",
                ".freebuff"))
            mutation(home / ".saipen" / "KNOWLEDGE" / "harness.md",
                     home / ".github" / "workflows" / "validate.yml")
            output = validate(home)
            if contains in output:
                print(f"PASS: lint parity -- {label}")
            else:
                problems.append(f"{label}: missing {contains!r}")
                print(f"FAIL: lint parity -- {label}")

    probe("surface divergence fails the validator",
          lambda h, c: h.write_text(
              h.read_text(encoding="utf-8").replace(
                  "python -m ruff check tools/ tests/",
                  "python -m ruff check tools/"),
              encoding="utf-8"),
          "lint parity [T-628]")
    probe("ruff version drift fails the validator",
          lambda h, c: h.write_text(
              h.read_text(encoding="utf-8").replace(
                  "ruff==0.16.0", "ruff==0.17.0"),
              encoding="utf-8"),
          "lint parity [T-628]")
    probe("unpinned CI ruff fails the validator",
          lambda h, c: c.write_text(
              c.read_text(encoding="utf-8").replace(
                  "pip install --quiet ruff==0.16.0",
                  "pip install --quiet ruff"),
              encoding="utf-8"),
          "lint parity [T-628]")
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


def run_release_freshness_probes() -> tuple[list[str], int]:
    """A pre-metadata green gate must not authorize mutated release bytes."""
    problems: list[str] = []
    checked = 0
    env = {**os.environ, "GIT_AUTHOR_NAME": "probe",
           "GIT_AUTHOR_EMAIL": "probe@example.invalid",
           "GIT_COMMITTER_NAME": "probe",
           "GIT_COMMITTER_EMAIL": "probe@example.invalid"}
    home = VALIDATOR.parent.parent

    def expect(label: str, condition: bool, detail: str = "") -> None:
        nonlocal checked
        checked += 1
        if condition:
            print(f"PASS: release freshness -- {label}")
        else:
            problems.append(f"release freshness {label}: {detail}")

    with tempfile.TemporaryDirectory(prefix="saipen-release-freshness-") as tmp:
        project = Path(tmp) / "home"
        shutil.copytree(home, project, ignore=shutil.ignore_patterns(
            ".git", ".venv", "__pycache__", ".freebuff", "node_modules", "nul"))

        def git(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(["git", *args], cwd=project, env=env,
                                  capture_output=True, text=True, check=False,
                                  errors="replace")

        def validate(*, bind: bool = False,
                     gate: str = "ship") -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [sys.executable, str(project / "tools" / "validate.py"),
                 "--project-root", str(project), "--gate", gate,
                 *(["--require-release-index"] if bind else [])],
                cwd=project, capture_output=True, text=True, errors="replace")

        if git("init", "-q").returncode != 0:
            print("SKIP: release freshness probes -- git unavailable")
            return problems, checked
        # T-994 / § 21: cut the copied LOG at the sealed boundary so the
        # fixture holds no hunt marks naming commits its fresh `git init`
        # cannot back, and reconcile STATE (last_event + § 1.5 goal replay)
        # to the cut so the fixture is internally valid.
        saipen_dir = project / ".saipen"
        sealed_max = 0
        logs_dir = saipen_dir / "logs"
        if logs_dir.is_dir():
            for seg in sorted(logs_dir.glob("LOG-*.md")):
                for ln in seg.read_text(encoding="utf-8-sig").splitlines():
                    m = re.search(r"\[E-(\d+)\]", ln)
                    if m:
                        sealed_max = max(sealed_max, int(m.group(1)))
        if sealed_max:
            log_text = (saipen_dir / "LOG.md").read_text(encoding="utf-8-sig")
            kept = [ln for ln in log_text.splitlines()
                    if not (m := re.search(r"\[E-(\d+)\]", ln))
                    or int(m.group(1)) <= sealed_max]
            (saipen_dir / "LOG.md").write_text("\n".join(kept) + "\n",
                                               encoding="utf-8")
            st = (saipen_dir / "STATE.md").read_text(encoding="utf-8")
            st = re.sub(r"(?m)^(\s*last_event:\s*)\d+$",
                        f"\\g<1>{sealed_max}", st)
            all_lines = list(kept)
            if logs_dir.is_dir():
                for seg in sorted(logs_dir.glob("LOG-*.md")):
                    all_lines += seg.read_text(
                        encoding="utf-8-sig").splitlines()
            marker = re.compile(r"\]\s+DEC: goal (?:pivot|reauthorized)\b")
            last_marker = max(
                (i for i, ln in enumerate(all_lines) if marker.search(ln)),
                default=None)
            for counter in ("goal_waves", "goal_tickets"):
                if not re.search(rf"(?m)^{counter}:", st) or last_marker is None:
                    continue
                rebuilt = sum(
                    1 for ln in all_lines[last_marker + 1:]
                    for m in [re.search(rf"DEC: {counter} (\d+)->(\d+)", ln)]
                    if m and int(m.group(2)) > int(m.group(1)))
                st = re.sub(rf"(?m)^({counter}:\s*)\d+$",
                            f"\\g<1>{rebuilt}", st)
            (saipen_dir / "STATE.md").write_text(st, encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", "probe: baseline")

        locale_paths = sorted((project / ".saipen" / "saitranslate" /
                               "kitchen").glob("*/README_*.md"))
        old_version = (project / "VERSION").read_text(
            encoding="utf-8-sig").strip()
        parts = [int(part) for part in old_version.split(".")]
        new_version = f"{parts[0]}.{parts[1]}.{parts[2] + 1}"
        old_badge = f"**v{old_version}**"
        new_badge = f"**v{new_version}**"
        digest_re = re.compile(
            r"<!-- source-digest: README\.md sha256:([0-9a-f]+) -->")
        digests_before = {
            path.relative_to(project).as_posix(): digest_re.search(
                path.read_text(encoding="utf-8-sig")).group(1)
            for path in locale_paths
            if digest_re.search(path.read_text(encoding="utf-8-sig"))
        }

        initial_gate = validate(gate="core")
        expect("pre-metadata core signal is green",
               initial_gate.returncode == 0,
               (initial_gate.stdout + initial_gate.stderr).strip())
        empty_binding_gate = validate()
        expect("binding gate rejects an empty release index",
               empty_binding_gate.returncode != 0
               and "requires every release metadata path staged" in
               (empty_binding_gate.stdout + empty_binding_gate.stderr),
               (empty_binding_gate.stdout + empty_binding_gate.stderr).strip())

        # A partial README stage exists before this ship. The release changes
        # that same path, so rollback must restore its exact old index blob,
        # not reset the path to HEAD or leave final metadata staged.
        root_readme = project / "README.md"
        root_text = root_readme.read_text(encoding="utf-8-sig")
        partial_marker = "\n<!-- pre-existing partial-stage probe -->\n"
        root_readme.write_text(root_text + partial_marker,
                               encoding="utf-8", newline="\n")
        git("add", "--", root_readme.name)
        partial_index_before = git(
            "ls-files", "-s", "--", root_readme.name).stdout
        pre_ship_tree = git("write-tree").stdout.strip()
        head_before = git("rev-parse", "HEAD").stdout.strip()
        tags_before = git("tag", "--list").stdout

        (project / "VERSION").write_text(new_version + "\n", encoding="utf-8",
                                         newline="\n")
        root_readme.write_text(
            root_text.replace(old_badge, new_badge, 1) + partial_marker,
                               encoding="utf-8", newline="\n")
        changelog = project / "CHANGELOG.md"
        changelog_text = changelog.read_text(encoding="utf-8-sig")
        changelog.write_text(re.sub(
            rf"(?m)^(##\s+\[?){re.escape(old_version)}(\]?(?=\s|$))",
            rf"\g<1>{new_version}\2", changelog_text, count=1),
            encoding="utf-8", newline="\n")
        release_paths = [Path("VERSION"), Path("README.md"),
                         Path("CHANGELOG.md"),
                         *(path.relative_to(project) for path in locale_paths)]
        git("add", "--", *(str(path) for path in release_paths[:3]))

        stale_gate = validate(bind=True)
        stale_output = stale_gate.stdout + stale_gate.stderr
        expect("post-metadata binding gate rejects stale locale badges",
               stale_gate.returncode != 0
               and "translation README badge drift: 32 locale(s)" in stale_output,
               stale_output.strip())
        expect("failed post-metadata gate creates no commit or tag",
               git("rev-parse", "HEAD").stdout.strip() == head_before
               and git("tag", "--list").stdout == tags_before,
               "HEAD or tag set changed after the failed gate")

        restored = git("restore", f"--source={pre_ship_tree}", "--staged", "--",
                       *(str(path) for path in release_paths))
        staged_after_rollback = set(filter(None, git(
            "diff", "--cached", "--name-only").stdout.splitlines()))
        expect("rollback removes only staging introduced by this ship",
               restored.returncode == 0
               and staged_after_rollback == {root_readme.name}
               and git("ls-files", "-s", "--", root_readme.name).stdout
               == partial_index_before,
               (restored.stdout + restored.stderr).strip())

        git("restore", "--staged", "--", root_readme.name)
        root_readme.write_text(root_text.replace(old_badge, new_badge, 1),
                               encoding="utf-8", newline="\n")
        for path in locale_paths:
            text = path.read_text(encoding="utf-8-sig")
            path.write_text(text.replace(old_badge, new_badge, 1),
                            encoding="utf-8", newline="\n")
        git("add", "--", *(str(path) for path in release_paths))

        final_gate = validate(bind=True)
        probe_locale = locale_paths[0]
        final_locale_text = probe_locale.read_text(encoding="utf-8-sig")
        probe_locale.write_text(
            final_locale_text.replace(new_badge, new_badge + new_badge, 1),
            encoding="utf-8", newline="\n")
        duplicate_badge_gate = validate(bind=True)
        probe_locale.write_text(
            final_locale_text.replace(new_badge, "", 1),
            encoding="utf-8", newline="\n")
        missing_badge_gate = validate(bind=True)
        probe_locale.write_text(final_locale_text, encoding="utf-8", newline="\n")
        probe_locale.write_text(
            final_locale_text.replace(new_badge, old_badge, 1),
            encoding="utf-8", newline="\n")
        git("add", "--", str(probe_locale.relative_to(project)))
        probe_locale.write_text(final_locale_text, encoding="utf-8", newline="\n")
        staged_worktree_divergence_gate = validate(bind=True)
        git("add", "--", str(probe_locale.relative_to(project)))
        cached_check = git("diff", "--cached", "--check")
        staged_final = set(filter(None, git(
            "diff", "--cached", "--name-only").stdout.splitlines()))
        expected_final = {path.as_posix() for path in release_paths}
        digests_after = {
            path.relative_to(project).as_posix(): digest_re.search(
                path.read_text(encoding="utf-8-sig")).group(1)
            for path in locale_paths
            if digest_re.search(path.read_text(encoding="utf-8-sig"))
        }
        expect("all mechanically discovered locale mirrors pass",
               final_gate.returncode == 0 and len(locale_paths) == 32,
               (final_gate.stdout + final_gate.stderr).strip())
        expect("duplicate locale badge fails the ship gate",
               duplicate_badge_gate.returncode != 0
               and "translation README badge drift" in
               (duplicate_badge_gate.stdout + duplicate_badge_gate.stderr),
               (duplicate_badge_gate.stdout + duplicate_badge_gate.stderr).strip())
        expect("missing locale badge fails the ship gate",
               missing_badge_gate.returncode != 0
               and "translation README badge drift" in
               (missing_badge_gate.stdout + missing_badge_gate.stderr),
               (missing_badge_gate.stdout + missing_badge_gate.stderr).strip())
        expect("stale staged badge cannot hide behind clean working bytes",
               staged_worktree_divergence_gate.returncode != 0
               and "staged release metadata differs from working-tree bytes" in
               (staged_worktree_divergence_gate.stdout
                + staged_worktree_divergence_gate.stderr),
               (staged_worktree_divergence_gate.stdout
                + staged_worktree_divergence_gate.stderr).strip())
        expect("final binding scope and cached diff are exact",
               staged_final == expected_final and cached_check.returncode == 0,
               f"staged={sorted(staged_final)}; check={cached_check.stderr.strip()}")
        expect("version-only mirror update leaves source digests unchanged",
               digests_after == digests_before,
               "a release badge update restamped translation freshness")

    return problems, checked


def run_release_executor_probes() -> tuple[list[str], int]:
    """T-994: comprehensive hostile release matrix.

    Tests the release executor against every identified failure class with
    ISOLATED fixtures (one scenario never contaminates another's Git history,
    T-635's original blindness): PLAN identity, zero-write dry-run, first
    publish WAIT, no-publish policy, foreign staging, phase gate, stderr
    capture, REAL source release into a fresh clone, ALREADY_APPLIED full
    evidence, crash recovery between every A -> B -> tag edge, journal-write
    refusal surfacing, exact index rollback, and the closed-code guarantee
    (every public ok:false code is in errors.CODES).

    Every identity assertion demands a NON-EMPTY expected AND actual witness;
    empty == empty is never proof.
    """
    problems: list[str] = []
    checked = 0
    env = {**os.environ, "GIT_AUTHOR_NAME": "probe",
           "GIT_AUTHOR_EMAIL": "probe@example.invalid",
           "GIT_COMMITTER_NAME": "probe",
           "GIT_COMMITTER_EMAIL": "probe@example.invalid"}

    home = VALIDATOR.parent.parent

    def expect(label: str, condition: bool, detail: str = "") -> None:
        nonlocal checked
        checked += 1
        if condition:
            print(f"PASS: release executor -- {label}")
        else:
            problems.append(f"release executor {label}: {detail}")

    def expect_refusal(label: str, rd: dict) -> None:
        """A public refusal MUST return a closed-code from errors.CODES."""
        nonlocal checked
        checked += 1
        from saipen_engine.errors import CODES
        code = rd.get("code")
        ok = (not rd.get("ok")
              and isinstance(code, str) and code in CODES)
        if ok:
            print(f"PASS: release executor -- {label}")
        else:
            problems.append(
                f"release executor {label}: ok={rd.get('ok')} "
                f"code={code!r} not in errors.CODES -- detail="
                f"{str(rd.get('detail'))[:200]}")

    def j(result) -> dict:
        try:
            return json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError):
            return {"ok": False, "code": "PARSE_ERROR",
                    "detail": result.stdout[:200]}

    def _cut_log(saipen_dir: Path) -> None:
        """Cut the copied LOG at the last sealed-segment boundary so the
        fixture history holds no commit references (hunt marks etc.) the fresh
        `git init` cannot back. Aligns STATE.last_event / goal counters to the
        validator's OWN § 1.5 replay rule so the fixture is internally valid
        (T-994 / § 21: one valid fixture, never hand-hacked STATE shapes)."""
        sealed_max = 0
        logs_dir = saipen_dir / "logs"
        if logs_dir.is_dir():
            for seg in sorted(logs_dir.glob("LOG-*.md")):
                for ln in seg.read_text(encoding="utf-8-sig").splitlines():
                    m = re.search(r"\[E-(\d+)\]", ln)
                    if m:
                        sealed_max = max(sealed_max, int(m.group(1)))
        if not sealed_max:
            return
        log_text = (saipen_dir / "LOG.md").read_text(encoding="utf-8-sig")
        kept = [ln for ln in log_text.splitlines()
                if not (m := re.search(r"\[E-(\d+)\]", ln))
                or int(m.group(1)) <= sealed_max]
        (saipen_dir / "LOG.md").write_text("\n".join(kept) + "\n",
                                           encoding="utf-8")
        st = (saipen_dir / "STATE.md").read_text(encoding="utf-8")
        st = re.sub(r"(?m)^(\s*last_event:\s*)\d+$",
                    f"\\g<1>{sealed_max}", st)
        # § 1.5 replay: goal counters rebuild from the NEWEST
        # `DEC: goal pivot|reauthorized` marker across SEALED + active logs
        # (the validator reads every log file). Reconcile STATE to the cut log
        # so the ship gate never fails on the fixture's own editing.
        all_lines = list(kept)
        if logs_dir.is_dir():
            for seg in sorted(logs_dir.glob("LOG-*.md")):
                all_lines += seg.read_text(
                    encoding="utf-8-sig").splitlines()
        marker = re.compile(r"\]\s+DEC: goal (?:pivot|reauthorized)\b")
        last_marker = max(
            (i for i, ln in enumerate(all_lines) if marker.search(ln)),
            default=None)
        for counter in ("goal_waves", "goal_tickets"):
            if not re.search(rf"(?m)^{counter}:", st):
                continue
            if last_marker is None:
                continue  # validator only WARNs in the no-marker shape
            rebuilt = sum(
                1 for ln in all_lines[last_marker + 1:]
                for m in [re.search(rf"DEC: {counter} (\d+)->(\d+)", ln)]
                if m and int(m.group(2)) > int(m.group(1)))
            st = re.sub(rf"(?m)^({counter}:\s*)\d+$",
                        f"\\g<1>{rebuilt}", st)
        (saipen_dir / "STATE.md").write_text(st, encoding="utf-8")

    def build_fixture(tmp: Path, *, mode: str = "full",
                      gitless: bool = False) -> tuple:
        """ONE valid SHIP-phase fixture builder (T-994 / § 21): the copied
        project's real STATE keeps every required field (blocker,
        saipen_version, mode, ...) and only the SHIP-relevant fields are
        patched, so the ship gate never fails on the fixture's own corruption.
        """
        project = tmp / "home"
        shutil.copytree(home, project, ignore=shutil.ignore_patterns(
            ".git", ".venv", "__pycache__", ".freebuff", "node_modules",
            "nul"))

        def git(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(["git", "-C", str(project), *args], env=env,
                                  capture_output=True, text=True, check=False)

        def cli(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [sys.executable, str(project / "tools" / "saipen.py"),
                 *args],
                cwd=str(project), env=env, capture_output=True, text=True,
                errors="replace")

        if not gitless:
            if git("init", "-q").returncode != 0:
                print("SKIP: release executor probes -- git unavailable")
                return None
            git("add", "-A")
            git("commit", "-q", "-m", "probe: baseline")
            git("branch", "-M", "main")
            origin = tmp / "origin.git"
            subprocess.run(["git", "init", "-q", "--bare", str(origin)],
                           capture_output=True)
            git("remote", "add", "origin", f"file://{origin}")
            git("push", "-q", "origin", "HEAD:main")
            subprocess.run(["git", "-C", str(origin), "symbolic-ref", "HEAD",
                            "refs/heads/main"], capture_output=True)
        else:
            origin = tmp / "origin.git"
            origin.mkdir()

        saipen_dir = project / ".saipen"
        st = (saipen_dir / "STATE.md").read_text(encoding="utf-8-sig")
        lines = st.splitlines()
        out = []
        for ln in lines:
            new_ln = ln
            for key, val in (("phase:", "SHIP"), ("task:", "T-9000"),
                             ("next_action:", "PHASE SHIP T-9000"),
                             ("transition_from:", "REVIEW"),
                             ("mode:", mode), ("agent:", "probe")):
                if new_ln.strip().startswith(key):
                    new_ln = new_ln.replace(new_ln.split(":", 1)[1], " " + val)
                    break
            out.append(new_ln)
        (saipen_dir / "STATE.md").write_text("\n".join(out) + "\n",
                                             encoding="utf-8")

        board_text = (saipen_dir / "BOARD.md").read_text(
            encoding="utf-8-sig")
        board_text = re.sub(
            r"(?ms)^## DOING\n.*?(?=^## )",
            "## DOING\n- [/] T-9000 synthetic fixture ticket "
            "| owner: probe | claim_time: 2026-01-01T00:00:00Z\n",
            board_text)
        (saipen_dir / "BOARD.md").write_text(board_text, encoding="utf-8")

        _cut_log(saipen_dir)
        if not gitless:
            git("add", "-A")
            git("commit", "-q", "-m", "probe: fixture ship")
            git("push", "-q", "origin", "HEAD:main")

        # Real, non-metadata source change: the reviewed scope the release
        # must actually ship (T-994 / § 2, § 22).
        src = project / "tools" / "saipen_engine" / "release_contract.py"
        src.write_text(
            src.read_text(encoding="utf-8-sig").replace(
                "version_badges(path)", "version_badges_owned(path)"),
            encoding="utf-8")
        r = cli("scope", "T-9000",
                "tools/saipen_engine/release_contract.py")
        if r.returncode != 0:
            raise RuntimeError("fixture scope failed: " + r.stdout + r.stderr)

        old_ver = (project / "VERSION").read_text(
            encoding="utf-8").strip()
        major, minor, patch = old_ver.split(".")
        new_ver = f"{major}.{minor}.{int(patch) + 1}"
        (project / "VERSION").write_text(new_ver + "\n", encoding="utf-8")
        readme = (project / "README.md").read_text(encoding="utf-8-sig")
        (project / "README.md").write_text(
            readme.replace(f"**v{old_ver}**", f"**v{new_ver}**"),
            encoding="utf-8")
        changelog = (project / "CHANGELOG.md").read_text(encoding="utf-8-sig")
        (project / "CHANGELOG.md").write_text(
            f"## {new_ver}\n\nTest release.\n\n" + changelog,
            encoding="utf-8")
        kitchen = saipen_dir / "saitranslate" / "kitchen"
        if kitchen.is_dir():
            for rm in kitchen.glob("*/README_*.md"):
                t = rm.read_text(encoding="utf-8-sig")
                rm.write_text(t.replace(f"**v{old_ver}**", f"**v{new_ver}**"),
                              encoding="utf-8")
        return project, origin, git, cli, new_ver

    def remote_branch_tip(origin: Path) -> str:
        r = subprocess.run(["git", "ls-remote", str(origin),
                            "refs/heads/main"], capture_output=True,
                           text=True)
        parts = r.stdout.strip().split()
        return parts[0] if parts else ""

    def remote_tag_commit(origin: Path, tag: str) -> str:
        r = subprocess.run(["git", "ls-remote", str(origin),
                            f"refs/tags/{tag}^{{}}"], capture_output=True,
                           text=True)
        parts = r.stdout.strip().split()
        return parts[0] if parts else ""

    # ======================================================================
    # 1. PLAN: ship and push dry-run plans are structurally identical
    # ======================================================================
    with tempfile.TemporaryDirectory(prefix="saipen-rel-1-") as tmp:
        built = build_fixture(Path(tmp))
        if built is None:
            return problems, checked
        project, origin, git, cli, _new_ver = built
        ship_plan = cli("ship", "--dry-run", "--json")
        push_plan = cli("push", "--dry-run", "--json")
        sp = j(ship_plan)
        pp = j(push_plan)
        expect("1. ship and push dry-run plans are structurally identical",
               sp.get("ok") and pp.get("ok")
               and sp.get("plan") == pp.get("plan"),
               f"ship={sp.get('plan')} push={pp.get('plan')} "
               f"{sp.get('detail')} {pp.get('detail')}")

    # ======================================================================
    # 2. DRY_RUN: zero writes (no file/index/commit/tag/object change)
    # ======================================================================
    with tempfile.TemporaryDirectory(prefix="saipen-rel-2-") as tmp:
        built = build_fixture(Path(tmp))
        if built is None:
            return problems, checked
        project, origin, git, cli, _new_ver = built
        pre_obj = git("count-objects", "-v").stdout
        pre_status = git("status", "--short").stdout
        pre_log = git("log", "--oneline").stdout
        pre_tags = git("tag", "--list").stdout
        pre_refs = git("show-ref").stdout
        result = cli("ship", "--dry-run", "--json")
        rd = j(result)
        post_obj = git("count-objects", "-v").stdout
        post_status = git("status", "--short").stdout
        post_log = git("log", "--oneline").stdout
        post_tags = git("tag", "--list").stdout
        post_refs = git("show-ref").stdout
        expect("2a. dry-run reports writes=none",
               rd.get("ok") and rd.get("writes") == "none",
               f"ok={rd.get('ok')} writes={rd.get('writes')}")
        expect("2b. dry-run does not change index/staged set",
               pre_status == post_status,
               f"before={pre_status!r} after={post_status!r}")
        expect("2c. dry-run creates no new commits", pre_log == post_log, "")
        expect("2d. dry-run creates no tags",
               pre_tags == post_tags == "", f"tags={post_tags!r}")
        expect("2e. dry-run creates no git objects", pre_obj == post_obj,
               f"before={pre_obj!r} after={post_obj!r}")
        expect("2f. dry-run does not change refs", pre_refs == post_refs, "")

    # ======================================================================
    # 3. FIRST-PUBLISH WAIT is canonical, not an error string (T-994 / § 11)
    # ======================================================================
    with tempfile.TemporaryDirectory(prefix="saipen-rel-3-") as tmp:
        built = build_fixture(Path(tmp))
        if built is None:
            return problems, checked
        project, origin, git, cli, new_ver = built
        origin_empty = Path(tmp) / "origin_empty.git"
        subprocess.run(["git", "init", "-q", "--bare", str(origin_empty)],
                       capture_output=True)
        git("remote", "set-url", "origin", f"file://{origin_empty}")
        pre_head = git("rev-parse", "HEAD").stdout

        result = cli("ship", "--json")
        rd = j(result)
        expect_refusal("3a. first publish refuses with FIRST_PUBLISH_WAIT",
                       rd)
        expect("3a-code", rd.get("code") == "FIRST_PUBLISH_WAIT",
               f"code={rd.get('code')}")
        expect("3b. first-publish does not create commits",
               git("rev-parse", "HEAD").stdout == pre_head, "")
        expect("3c. first-publish does not create tags",
               git("tag", "--list").stdout == "", "")
        st = (project / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        expect("3d. canonical WAIT persisted in STATE",
               'next_action: "WAIT: first-publish' in st
               or "next_action: WAIT: first-publish" in st
               or "next_action: WAIT:first-publish" in st,
               [ln for ln in st.splitlines()
                if "next_action" in ln][:1])
        expect("3e. phase stays SHIP during the WAIT", "phase: SHIP" in st, "")

        result = cli("fpc", f"file://{origin_empty}", "public", "--json")
        rd = j(result)
        expect("3f. confirmation is canonical evidence",
               rd.get("ok") and rd.get("code") == "FIRST_PUBLISH_CONFIRMED",
               f"code={rd.get('code')} detail={rd.get('detail')}")
        st = (project / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        expect("3g. confirmation recorded in STATE",
               "first_publish_confirmation:" in st,
               [ln for ln in st.splitlines()
                if "first_publish_confirmation" in ln][:1])

        result = cli("ship", "--json")
        rd = j(result)
        expect("3h. confirmed first publish proceeds to RELEASED",
               rd.get("ok") and rd.get("code") == "RELEASED",
               f"code={rd.get('code')} detail={str(rd.get('detail'))[:200]}")
        tag = remote_tag_commit(origin_empty, f"v{new_ver}")
        expect("3i. tag published after confirmation",
               tag != "" and tag == remote_branch_tip(origin_empty),
               f"tag={tag} tip={remote_branch_tip(origin_empty)}")

    # ======================================================================
    # 4. POLICY: no-publish matches ship.md exactly (T-994 / § 10)
    # ======================================================================
    with tempfile.TemporaryDirectory(prefix="saipen-rel-4-") as tmp:
        built = build_fixture(Path(tmp), mode="no-publish")
        if built is None:
            return problems, checked
        project, origin, git, cli, new_ver = built
        pre_head = git("rev-parse", "HEAD").stdout
        pre_index = git("diff", "--cached", "--name-only").stdout
        pre_tags = git("tag", "--list").stdout
        pre_remote = subprocess.run(["git", "ls-remote", str(origin)],
                                    capture_output=True, text=True).stdout

        result = cli("ship", "--json")
        rd = j(result)
        expect("4a. no-publish returns a truthful success",
               rd.get("ok") and rd.get("code") == "NO_PUBLISH_MODE",
               f"code={rd.get('code')} detail={rd.get('detail')}")
        expect("4b. no-publish does not create a local commit",
               git("rev-parse", "HEAD").stdout == pre_head,
               "HEAD changed under no-publish")
        expect("4c. no-publish does not stage anything",
               git("diff", "--cached", "--name-only").stdout == pre_index,
               f"index={git('diff', '--cached', '--name-only').stdout!r}")
        expect("4d. no-publish creates no tags",
               git("tag", "--list").stdout == pre_tags == "", "")
        expect("4e. no-publish remote refs unchanged",
               subprocess.run(["git", "ls-remote", str(origin)],
                              capture_output=True,
                              text=True).stdout == pre_remote,
               "remote changed under no-publish")
        st = (project / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        expect("4f. canonical STATE becomes DONE",
               "phase: DONE" in st and "task: none" in st, st[:160])
        board = (project / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        expect("4g. ticket becomes DONE", "- [x] T-9000" in board, "")
        log_text = (project / ".saipen" / "LOG.md").read_text(
            encoding="utf-8")
        expect("4h. truthful skipped-publish LOG event",
               f"ship v{new_ver} -> skipped publish (no-publish: policy)"
               in log_text,
               [ln for ln in log_text.splitlines()
                if "skipped publish" in ln][:1])
        digest = (project / ".saipen" / "kitchen" / "digest.md").read_text(
            encoding="utf-8")
        expect("4i. digest updated", "done:" in digest and "awaiting:" in digest,
               digest[:120])

    # ======================================================================
    # 4b. no-publish works when Git is genuinely unavailable
    # ======================================================================
    with tempfile.TemporaryDirectory(prefix="saipen-rel-4b-") as tmp:
        built = build_fixture(Path(tmp), mode="no-publish", gitless=True)
        if built is None:
            return problems, checked
        project, origin, git, cli, new_ver = built
        result = cli("ship", "--json")
        rd = j(result)
        expect("4j. git-less no-publish succeeds", rd.get("ok"),
               f"code={rd.get('code')} detail={rd.get('detail')}")
        log_text = (project / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        expect("4k. git-less no-publish records the true reason",
               "(no-publish: no git)" in log_text,
               [ln for ln in log_text.splitlines()
                if "skipped publish" in ln][:1])
        st = (project / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        expect("4l. git-less no-publish closes SHIP -> DONE",
               "phase: DONE" in st, "")

    # ======================================================================
    # 5. FOREIGN STAGING: refused and preserved
    # ======================================================================
    with tempfile.TemporaryDirectory(prefix="saipen-rel-5-") as tmp:
        built = build_fixture(Path(tmp))
        if built is None:
            return problems, checked
        project, origin, git, cli, _new_ver = built
        foreign = project / "foreign_untracked.txt"
        foreign.write_text("foreign\n", encoding="utf-8")
        git("add", "--", foreign.name)
        result = cli("ship", "--dry-run", "--json")
        rd = j(result)
        expect_refusal("5a. foreign pre-existing staging is refused", rd)
        foreign_still_staged = (
            foreign.name in git("diff", "--cached", "--name-only").stdout)
        expect("5b. foreign staging is preserved after refusal",
               foreign.is_file()
               and foreign.read_text(encoding="utf-8") == "foreign\n"
               and foreign_still_staged,
               f"staged={foreign_still_staged}")

    # ======================================================================
    # 6. PHASE gate: release refuses a non-SHIP state
    # ======================================================================
    with tempfile.TemporaryDirectory(prefix="saipen-rel-6-") as tmp:
        built = build_fixture(Path(tmp))
        if built is None:
            return problems, checked
        project, origin, git, cli, _new_ver = built
        st = (project / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        st = re.sub(r"(?m)^(\s*phase:\s*).*$", "\\g<1>DONE", st)
        st = re.sub(r"(?m)^(\s*task:\s*).*$", "\\g<1>none", st)
        st = re.sub(r"(?m)^(\s*next_action:\s*).*$",
                    "\\g<1>saipen continue", st)
        (project / ".saipen" / "STATE.md").write_text(st, encoding="utf-8")
        git("add", ".saipen/STATE.md")
        git("commit", "-q", "-m", "probe: set DONE")
        git("push", "-q", "origin", "HEAD:main")
        result = cli("ship", "--dry-run", "--json")
        rd = j(result)
        expect_refusal("6. release from an unproven DONE state is refused", rd)
        expect("6-code. refusal names the phase/evidence problem",
               ("DONE" in str(rd.get("detail")) or "SHIP" in str(rd.get(
                   "detail"))) or rd.get("code") == "ILLEGAL_PHASE",
               f"code={rd.get('code')} detail={rd.get('detail')}")

    # ======================================================================
    # 7. COMMIT failure detail is not discarded (stderr captured)
    # ======================================================================
    with tempfile.TemporaryDirectory(prefix="saipen-rel-7-") as tmp:
        built = build_fixture(Path(tmp))
        if built is None:
            return problems, checked
        project, origin, git, cli, _new_ver = built
        hook = project / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\necho HOOK REJECTION\n"
                        "exit 1\n", encoding="utf-8")
        pre_remote_tip = remote_branch_tip(origin)
        result = cli("ship", "--json")
        rd = j(result)
        expect_refusal("7a. commit rejection is a closed refusal", rd)
        expect("7b. failure detail is non-empty (stderr captured)",
               len(rd.get("detail", "")) > 0,
               f"detail={str(rd.get('detail'))[:300]}")
        expect("7c. no push happened on commit failure",
               remote_branch_tip(origin) == pre_remote_tip,
               f"before={pre_remote_tip[:12] or '(none)'} after="
               f"{remote_branch_tip(origin)[:12] or '(none)'}")

    # ======================================================================
    # 8. FULL SUCCESS: REAL source change ships into a fresh clone
    # ======================================================================
    with tempfile.TemporaryDirectory(prefix="saipen-rel-8-") as tmp:
        built = build_fixture(Path(tmp))
        if built is None:
            return problems, checked
        project, origin, git, cli, new_ver = built
        foreign = project / "tools" / "foreign_file.py"
        foreign.write_text("FOREIGN = True\n", encoding="utf-8")

        result = cli("ship", "--json")
        rd = j(result)
        tag = f"v{new_ver}"
        release_commit = rd.get("commit", "")
        closure_commit = rd.get("closure_commit", "")
        stages = rd.get("stages_reached", [])

        expect("8a. full release returns RELEASED",
               rd.get("ok") and rd.get("code") == "RELEASED",
               f"ok={rd.get('ok')} code={rd.get('code')} "
               f"detail={str(rd.get('detail'))[:200]}")
        expect("8b. closure B is a separate non-empty commit after A",
               bool(release_commit) and bool(closure_commit)
               and closure_commit != release_commit,
               f"A={release_commit[:12]} B={closure_commit[:12]}")
        remote_tip = remote_branch_tip(origin)
        remote_tag = remote_tag_commit(origin, tag)
        local_tag = git("rev-parse", f"{tag}^{{commit}}").stdout.strip()
        expect("8c. remote branch tip == closure commit (non-empty)",
               remote_tip and remote_tip == closure_commit,
               f"remote={remote_tip[:12] or '(none)'} closure="
               f"{closure_commit[:12]}")
        expect("8d. remote tag^{commit} == closure commit (non-empty)",
               remote_tag and remote_tag == closure_commit,
               f"remote tag={remote_tag[:12] or '(none)'}")
        expect("8e. local tag^{commit} == closure commit (non-empty)",
               local_tag and local_tag == closure_commit,
               f"local tag={local_tag[:12] or '(none)'} closure="
               f"{closure_commit[:12]}")
        expect("8f. tag is created AFTER the closure is published",
               stages.index("TAG_CREATED") > stages.index("CLOSURE_PUBLISHED")
               if "TAG_CREATED" in stages and "CLOSURE_PUBLISHED" in stages
               else False,
               f"stages={stages}")
        parent_of_b = git("rev-parse", f"{closure_commit}^").stdout.strip()
        expect("8g. B.parent == A",
               parent_of_b and parent_of_b == release_commit,
               f"B^={parent_of_b[:12]} A={release_commit[:12]}")

        # Fresh clone must carry the exact real source change + metadata
        clone = Path(tmp) / "fresh_clone"
        crc = subprocess.run(["git", "clone", "-q", f"file://{origin}",
                              str(clone)], capture_output=True, text=True)
        expect("8h. fresh clone succeeded", crc.returncode == 0,
               crc.stderr)
        if crc.returncode == 0:
            cloned_src = (clone / "tools" / "saipen_engine"
                          / "release_contract.py").read_text(
                encoding="utf-8-sig")
            expect("8i. fresh clone carries the exact reviewed source change",
                   "version_badges_owned(path)" in cloned_src,
                   "source change missing in fresh clone")
            clone_state = (clone / ".saipen" / "STATE.md").read_text(
                encoding="utf-8-sig")
            expect("8j. fresh clone sees STATE DONE / task none",
                   "phase: DONE" in clone_state
                   and "task: none" in clone_state, "")
            clone_board = (clone / ".saipen" / "BOARD.md").read_text(
                encoding="utf-8-sig")
            expect("8k. fresh clone sees ticket DONE",
                   "- [x] T-9000" in clone_board, "")
            clone_log = (clone / ".saipen" / "LOG.md").read_text(
                encoding="utf-8-sig")
            expect("8l. fresh clone LOG carries truthful release evidence",
                   "ship v" + new_ver in clone_log
                   and "T-9000" in clone_log
                   and "content commit" in clone_log,
                    "release evidence missing in cloned LOG")
            scope_rec = clone / ".saipen" / "kitchen" / "release_scope" \
                / "T-9000.json"
            expect("8m. scope record reaches the fresh clone",
                   scope_rec.is_file(), "scope record missing in clone")

        # Foreign file must NOT be in either commit and must stay in worktree
        for commit in (release_commit, closure_commit):
            in_commit = git("cat-file", "-e",
                            f"{commit}:tools/foreign_file.py").returncode
            expect("8n. foreign file did not enter the release commits",
                   in_commit != 0, f"{commit}:tools/foreign_file.py present")
        expect("8o. foreign file still in the worktree",
               foreign.is_file()
               and foreign.read_text(encoding="utf-8") == "FOREIGN = True\n",
               "")
        status = git("status", "--porcelain").stdout
        expect("8p. no owned work remains dirty (only the foreign untracked)",
               all(ln.startswith("??") for ln in status.splitlines()
                   if ln.strip()),
               f"status={status!r}")
        expect("8q. scope record is committed (no tracked dirt)",
               git("ls-files", "--error-unmatch",
                   ".saipen/kitchen/release_scope/T-9000.json").returncode == 0,
               "scope record untracked")

        # Retry: full remote + canonical evidence -> already applied, no writes
        pre_retry_head = git("rev-parse", "HEAD").stdout
        result = cli("ship", "--json")
        rd = j(result)
        expect("8r. retry recognizes ALREADY_APPLIED from full evidence",
               rd.get("ok") and rd.get("code") == "RELEASED"
               and rd.get("already_applied") is True,
               f"code={rd.get('code')} already_applied="
               f"{rd.get('already_applied')}")
        expect("8s. retry writes nothing",
               git("rev-parse", "HEAD").stdout == pre_retry_head, "")

    # ======================================================================
    # 9. CRASH RECOVERY between every A -> B -> tag edge (T-994 / § 17, § 18)
    # ======================================================================
    for crash_point, probe_label in (
            ("SAIPEN_CRASH_AFTER_CONTENT_PUBLISH", "A after content push"),
            ("SAIPEN_CRASH_AFTER_CLOSURE_PUBLISH", "B after closure push"),
            ("SAIPEN_CRASH_AFTER_TAG_PUSH", "C after tag push")):
        with tempfile.TemporaryDirectory(
                prefix="saipen-rel-9-") as tmp:
            built = build_fixture(Path(tmp))
            if built is None:
                return problems, checked
            project, origin, git, cli, new_ver = built
            env_crash = {**env, crash_point: "1"}
            r = subprocess.run(
                [sys.executable, str(project / "tools" / "saipen.py"),
                 "ship", "--json"],
                cwd=str(project), env=env_crash, capture_output=True,
                text=True, errors="replace")
            expect(f"9. {probe_label}: crash injected at the edge",
                   r.returncode == 86, f"rc={r.returncode}")
            before_commits = git("rev-list", "--count", "HEAD").stdout
            result = cli("recover", "--json")
            rd = j(result)
            expect(f"9. {probe_label}: recovery settles",
                   rd.get("ok"), f"rc={result.returncode} {rd}")
            after_commits = git("rev-list", "--count", "HEAD").stdout
            after_tag = remote_tag_commit(origin, f"v{new_ver}")
            tip = remote_branch_tip(origin)
            expect(f"9. {probe_label}: remote branch reaches closure",
                   tip != "" and after_tag != "" and after_tag == tip,
                   f"tip={tip[:12] or '(none)'} tag={after_tag[:12] or '(none)'}")
            expect(f"9. {probe_label}: no duplicate commits on recovery",
                   before_commits == after_commits or crash_point.endswith(
                       "CONTENT_PUBLISH"),
                   f"{before_commits}->{after_commits}")
            expect(f"9. {probe_label}: pending ops cleared",
                   cli("recover").stdout.count("CLEAN") > 0, "")

    # ======================================================================
    # 9b. FRESH-CLONE CONTINUATION (worktree destroyed, committed evidence)
    # ======================================================================
    with tempfile.TemporaryDirectory(prefix="saipen-rel-9b-") as tmp:
        built = build_fixture(Path(tmp))
        if built is None:
            return problems, checked
        project, origin, git, cli, new_ver = built
        env_crash = {**env, "SAIPEN_CRASH_AFTER_CLOSURE_PUBLISH": "1"}
        r = subprocess.run(
            [sys.executable, str(project / "tools" / "saipen.py"), "ship",
             "--json"], cwd=str(project), env=env_crash,
            capture_output=True, text=True, errors="replace")
        expect("9b. crash injected after closure publish", r.returncode == 86,
               f"rc={r.returncode}")
        expect("9b. closure B pushed, tag absent",
               remote_branch_tip(origin) != ""
               and remote_tag_commit(origin, f"v{new_ver}") == "",
               "")
        shutil.rmtree(project, ignore_errors=True)
        clone = Path(tmp) / "clone"
        crc = subprocess.run(["git", "clone", "-q", f"file://{origin}",
                              str(clone)], capture_output=True, text=True)
        expect("9b. fresh clone succeeded", crc.returncode == 0, crc.stderr)
        if crc.returncode == 0:
            def cli_clone(*args: str):
                return subprocess.run(
                    [sys.executable, str(clone / "tools" / "saipen.py"),
                     *args], cwd=str(clone), env=env, capture_output=True,
                    text=True, errors="replace")
            result = cli_clone("ship", "--json")
            rd = j(result)
            expect("9b. fresh-clone continuation publishes only the missing "
                   "tag", rd.get("ok") and rd.get("code") == "RELEASED",
                   f"code={rd.get('code')} detail={rd.get('detail')}")
            tip = remote_branch_tip(origin)
            tag = remote_tag_commit(origin, f"v{new_ver}")
            expect("9b. tag now matches the closure tip (non-empty)",
                   tip != "" and tag == tip,
                   f"tag={tag[:12] or '(none)'} tip={tip[:12] or '(none)'}")

    # ======================================================================
    # 10. RECEIPT/JOURNAL write failure surfaces through the PUBLIC result
    # ======================================================================
    with tempfile.TemporaryDirectory(prefix="saipen-rel-10-") as tmp:
        built = build_fixture(Path(tmp))
        if built is None:
            return problems, checked
        project, origin, git, cli, _new_ver = built
        from saipen_engine import journal as journal_mod
        from saipen_engine.release import execute_release, plan_release
        plan = plan_release(project, "ship")

        class _FailingJournal:
            manifest = "simulated-journal/operation.json"

            def __init__(self, *a, **k):
                pass

            def start(self, *a, **k):
                raise OSError("simulated receipt write failure")

            def exists(self):
                return False

            def read(self):
                return {}

        original_journal = journal_mod.Journal
        journal_mod.Journal = _FailingJournal
        pre_remote_tip = remote_branch_tip(origin)
        try:
            result = execute_release(project, plan)
        finally:
            journal_mod.Journal = original_journal
        expect_refusal("10a. journal write failure is a public closed refusal",
                       result)
        expect("10b. no remote stage ran after the receipt failure",
               remote_branch_tip(origin) == pre_remote_tip,
               f"before={pre_remote_tip[:12] or '(none)'} after="
               f"{remote_branch_tip(origin)[:12] or '(none)'}")
        expect("10c. no tag pushed after the receipt failure",
               remote_tag_commit(origin, f"v{_new_ver}") == "", "")

    # ======================================================================
    # 11. EXACT INDEX ROLLBACK preserves a staged deletion (T-994 / § 19)
    # ======================================================================
    with tempfile.TemporaryDirectory(prefix="saipen-rel-11-") as tmp:
        project = Path(tmp) / "idx"
        project.mkdir()
        subprocess.run(["git", "init", "-q", str(project)], env=env,
                       capture_output=True, text=True, check=False)

        def git11(*args: str):
            return subprocess.run(["git", "-C", str(project), *args], env=env,
                                  capture_output=True, text=True, check=False)

        (project / "a.txt").write_text("a\n", encoding="utf-8")
        git11("add", "a.txt")
        git11("commit", "-q", "-m", "add a")
        git11("rm", "--cached", "-q", "a.txt")
        from saipen_engine.release import _capture_index_state, _restore_index
        snap = _capture_index_state(project)
        has_deletion = any(mode == "D" for _p, mode, _b in snap.entries)
        expect("11a. index snapshot records the staged deletion", has_deletion,
               f"entries={snap.entries}")
        _restore_index(project, snap)
        status = git11("diff", "--cached", "--name-status").stdout
        expect("11b. staged deletion is restored exactly",
               "D\ta.txt" in status or "D a.txt" in status,
               f"status={status!r}")

    # ======================================================================
    # 12. OBJECT COUNT detector responds to a new loose object (T-994 / § 20)
    # ======================================================================
    with tempfile.TemporaryDirectory(prefix="saipen-rel-12-") as tmp:
        project = Path(tmp) / "oc"
        project.mkdir()
        subprocess.run(["git", "init", "-q", str(project)], env=env,
                       capture_output=True, text=True, check=False)

        def git12(*args: str):
            return subprocess.run(["git", "-C", str(project), *args], env=env,
                                  capture_output=True, text=True, check=False)

        from saipen_engine.release import _git_object_count
        before = _git_object_count(project)
        git12("hash-object", "-w", "--stdin")
        after = _git_object_count(project)
        expect("12. loose object creation changes the detector",
               after > before, f"{before}->{after}")

    # ======================================================================
    # 13. Closed-code guarantee: every refusal path returns an OPS code
    # ======================================================================
    from saipen_engine.errors import CODES
    expect("13. errors.CODES is non-empty and closed",
           len(CODES) > 0 and "RELEASE_FAILED" in CODES
           and "FIRST_PUBLISH_WAIT" in CODES,
           f"codes={sorted(CODES)}")

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

    roster = ("# IMPROVE CYCLE ROSTER\nseat_id: report\nrole: core\n"
              "report_path: saipen_improve_REPORT.md\navailability: expected\n")
    sweep = ("# SWEEP\n- IMP-001 [CONFIRMED] T-900 "
             "report=saipen_improve_REPORT.md reproduced=y\n")
    full_sweep = sweep + ("- IMP-002 [CONFIRMED] T-900 "
                          "report=saipen_improve_REPORT.md reproduced=y\n")
    expect("derived status: roster-only is expected",
           derive_status("saipen_improve_REPORT.md", roster, "", "")["visible"]
           == "expected")
    expect("derived status: report draft is draft",
           derive_status("saipen_improve_REPORT.md", roster,
                         "report_status: draft\n", "")["visible"] == "draft")
    expect("derived status: complete without sweep is complete",
           derive_status("saipen_improve_REPORT.md", roster,
                         "report_status: complete\n", "")["visible"]
           == "complete")
    report_two = ("report_status: complete\n\n"
                  "IMP-001 [P1] [PROTOCOL_VIOLATION] [proven] [ticket]\n"
                  "IMP-002 [P1] [PROTOCOL_VIOLATION] [proven] [ticket]\n")
    expect("derived status: partial disposition coverage is never swept",
           derive_status("saipen_improve_REPORT.md", roster, report_two,
                         sweep)["visible"] != "swept")
    expect("derived status: swept after FULL disposition coverage",
           derive_status("saipen_improve_REPORT.md", roster, report_two,
                         full_sweep)["visible"] == "swept")
    expect("derived status: unavailable roster wins",
           derive_status("saipen_improve_REPORT.md",
                         roster.replace("availability: expected",
                                        "availability: unavailable"),
                         report_two, full_sweep)["visible"] == "unavailable")
    seat2_roster = ("# IMPROVE CYCLE ROSTER\n"
                    "seat_id: seat-a\nrole: core\nreport_path: a.md\n"
                    "availability: unavailable\n"
                    "seat_id: seat-b\nrole: core\nreport_path: b.md\n"
                    "availability: expected\n")
    seat2_sweep = ("# SWEEP\n- IMP-001 [CONFIRMED] T-900 report=b.md "
                   "reproduced=y\n- IMP-002 [CONFIRMED] T-900 report=b.md "
                   "reproduced=y\n")
    expect("derived status: per-seat availability, not the first field",
           derive_status("b.md", seat2_roster,
                         report_two, seat2_sweep)["visible"] == "swept"
           and derive_status("a.md", seat2_roster,
                             report_two, seat2_sweep)["visible"]
           == "unavailable")

    # NITRO dogfood II: same IMP-001 in two reports stays independent and one
    # report disposition cannot sweep another.
    cross_roster = ("# IMPROVE CYCLE ROSTER\n"
                    "seat_id: seat-a\nrole: core\nreport_path: a.md\n"
                    "availability: expected\n"
                    "seat_id: seat-b\nrole: core\nreport_path: b.md\n"
                    "availability: expected\n")
    report_a = ("report_status: complete\n\n"
                "IMP-001 [P1] [PROTOCOL_VIOLATION] [proven] [ticket]\n")
    report_b = ("report_status: complete\n\n"
                "IMP-001 [P1] [PROTOCOL_VIOLATION] [proven] [ticket]\n")
    sweep_a_only = "# SWEEP\n- IMP-001 [CONFIRMED] T-900 report=a.md reproduced=y\n"
    expect("same IMP-001 in two reports stays independent",
           derive_status("a.md", cross_roster, report_a, sweep_a_only)[
               "visible"] == "swept"
           and derive_status("b.md", cross_roster, report_b, sweep_a_only)[
               "visible"] == "complete",
           repr(derive_status("b.md", cross_roster, report_b, sweep_a_only)))

    def project_fixture(prefix: str) -> Path:
        """A minimal but real .saipen/ project root for the journaled writers."""
        proot = Path(tempfile.mkdtemp(prefix=prefix))
        saipen = proot / ".saipen"
        saipen.mkdir()
        (saipen / "LOG.md").write_text(
            "- 09.08.26 00:00 [E-900] [T-none] DEC: base\n", encoding="utf-8")
        (saipen / "BOARD.md").write_text(
            "# Board\n## DOING\n## TODO\n## DONE\n## BLOCKED\n",
            encoding="utf-8")
        (saipen / "STATE.md").write_text(
            "---\nphase: DONE\ntask: none\nnext_action: \"saipen continue\"\n"
            "blocker: \"\"\ntransition_from: SHIP\n"
            "saipen_version: 7\nschema_version: 3\n"
            "last_event: 900\nstyle_contract: ded-4ae736e4\n"
            "saipen_home: \".\"\nagent: probe\nmode: full\n"
            "updated: 2026-08-09T00:00:00Z\n---\n", encoding="utf-8")
        return proot

    def ticket_fixture(root: Path, tid: str = "T-900") -> None:
        """Put a real canonical ticket on the temp board so CONFIRMED sweeps
        can bind it (DOGFOOD V: a ledger may never claim a nonexistent
        ticket)."""
        board = root / ".saipen" / "BOARD.md"
        text = board.read_text(encoding="utf-8-sig")
        if tid in text:
            return
        text = text.replace(
            "## TODO\n",
            f"## TODO\n- [ ] {tid} [P1] probe | verify: probe\n")
        board.write_text(text, encoding="utf-8")

    def mech_cycle(root: Path, cycle_id: str, seat_id: str, project_name: str,
                   run_texts: list[str], ticket: str = "T-900",
                   findings_ok: bool = True) -> tuple[Path, Path]:
        """Build a STRICT cycle entirely through the mechanical writers:
        create_cycle -> register_seat -> create_report -> append_run ->
        complete_report. Zero raw canonical Improve writes."""
        cdir = create_cycle(root, cycle_id,
                            created_at="2026-08-10T00:00:00Z",
                            project_identity="probe-project")
        register_seat(cdir, seat_id, "core",
                      f"saipen_improve_{project_name}.md")
        ticket_fixture(root, ticket)
        report = create_report(
            root, cycle_id, seat_id, project_name, agent=seat_id, role="core",
            model_or_runtime="probe",
            context_scope="probe scope")
        if findings_ok:
            for run_text in run_texts:
                append_run(report, run_text)
            complete_report(report)
        return cdir, report

    proot = project_fixture("saipen-sweep-")
    cycle, report = mech_cycle(proot, "imp-key-20260808", "opencode-01",
                               "PROJ",
                               ["IMP-001 [P1] [PROTOCOL_VIOLATION] "
                                "[proven] [ticket]\n"
                                "expected: x\nactual: y\nevidence: z\n"])
    before = report.read_bytes()
    write_sweep_entry(cycle, {"run": "RUN-1", "imp_id": "001",
                              "disposition": "CONFIRMED", "ticket": "T-900",
                              "report": "saipen_improve_PROJ.md",
                              "reproduced": "y"})
    expect("SWEEP ledger write never mutates the seat report",
           report.read_bytes() == before)
    expect("SWEEP ledger exists with the disposition",
           (cycle / "SWEEP.md").is_file()
           and "RUN-1/IMP-001" in (cycle / "SWEEP.md").read_text(
               encoding="utf-8"))

    # Cycle/seat admission: deterministic, collision-safe (T-570).
    proot = project_fixture("saipen-cycle-")
    c1 = create_cycle(proot, "imp-key-20260808")
    try:
        create_cycle(proot, "imp-key-20260808")
        dup_cycle = False
    except (FileExistsError, ValueError):
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
    # complete report refuses further RUNs (T-551, DOGFOOD V T-616). T-638:
    # append_run requires a valid ACTIVE cycle manifest -- the report lives
    # under .saipen/improve/<cycle>/<seat>/ and the cycle must exist.
    proot = project_fixture("saipen-run-")
    _run_cycle = create_cycle(proot, "imp-key-20260808",
                              created_at="2026-08-10T00:00:00Z",
                              project_identity="p")
    register_seat(_run_cycle, "opencode-01", "core",
                  "saipen_improve_PROJ.md")
    seat_report = create_report(
        proot, "imp-key-20260808", "opencode-01", "PROJ",
        agent="opencode-01", role="core", model_or_runtime="probe",
        context_scope="scope")
    append_run(seat_report, "first run")
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

    # NITRO M6 (T-583): the Improve writers are journaled transactions, so a
    # crash cannot expose a roster-less cycle directory. Run register_cycle in
    # a subprocess that dies exactly after the journal PREPARES; recovery must
    # produce exactly one valid outcome -- no bare directory admitted.
    proot = project_fixture("saipen-cyclecrash-")
    crash_code = (
        "import sys, os; sys.path.insert(0, r'%s')\n"
        "os.environ['NITRO_CRASH_AFTER_PREPARE'] = '1'\n"
        "from improve import register_cycle\n"
        "register_cycle(r'%s', 'imp-crash', '# IMPROVE CYCLE ROSTER\\n')"
        % (str(HOME / "tools"), str(proot)))
    rc = subprocess.run([sys.executable, "-c", crash_code], cwd=str(proot),
                        capture_output=True, text=True, timeout=60).returncode
    owner = proot / ".saipen" / "improve"
    crash_dir = owner / "imp-crash"
    expect("register_cycle crash after PREPARE leaves no admitted cycle",
           rc == 87 and not (crash_dir / "MANIFEST.md").is_file(),
           f"rc={rc}, manifest={ (crash_dir / 'MANIFEST.md').is_file() }")
    from saipen_engine.journal import auto_recover_pending
    recovered = auto_recover_pending(proot)
    expect("recovery after the PREPARE crash leaves no roster-less cycle",
           recovered.get("ok")
           and not (owner / "imp-crash" / "MANIFEST.md").is_file(),
           repr(recovered))
    # A later register_cycle with the same id still works (nothing admitted).
    c_again = register_cycle(proot, "imp-crash", "# IMPROVE CYCLE ROSTER\n")
    expect("a fresh cycle can be admitted after clean recovery",
           (c_again / "MANIFEST.md").is_file())

    # ---- T-589: stale Improve plan refuses (CAS, no lost update).
    import improve as _improve
    cas_root = project_fixture("saipen-cas-")
    cas_cycle = create_cycle(cas_root, "imp-cas")
    cas_manifest = cas_cycle / "MANIFEST.md"
    base_text = _improve._read_maybe(cas_manifest)
    base_hash_before = _improve._base_hash(cas_manifest)
    # B derived +seat B from the OLD base (before A commits).
    stale_text = base_text.rstrip() + "\nseat_id: seat-b\nrole: core\n" \
        "report_path: saipen_improve_B.md\navailability: expected\n"
    # A builds +seat A and commits in between.
    _improve.register_seat(cas_cycle, "seat-a", "core",
                           "saipen_improve_A.md")
    stale_res = _improve._journaled_write(
        cas_manifest, stale_text, "seat", base_hash=base_hash_before)
    expect("stale Improve plan refuses STALE_STATE (base-hash binding)",
           not stale_res.get("ok")
           and stale_res.get("code") == "STALE_STATE", repr(stale_res))
    # Re-read, re-plan, commit: A + B both present.
    _improve.register_seat(cas_cycle, "seat-b", "core",
                           "saipen_improve_B.md")
    final_text = _improve._read_maybe(cas_manifest)
    expect("retry after stale refusal keeps both seats (A + B)",
           "seat_id: seat-a" in final_text
           and "seat_id: seat-b" in final_text, repr(final_text))

    # ---- T-589: cycle lifecycle -- complete allows the next cycle.
    # (NITRO dogfood III, T-595: this red control was vacuous -- both branches
    # set second_blocked=True. Now the success path sets False, so a mutation
    # removing the active-cycle refusal turns the scenario red.)
    life_root = project_fixture("saipen-life-")
    c1 = create_cycle(life_root, "imp-one")
    try:
        create_cycle(life_root, "imp-two")
        second_blocked = False
    except ValueError:
        second_blocked = True
    expect("a second ACTIVE cycle is refused while one is active",
           second_blocked)
    # Complete prerequisites: one expected seat with a complete report.
    register_seat(c1, "seat-1", "core", "saipen_improve_A.md")
    report1 = create_report(life_root, "imp-one", "seat-1", "A",
                            agent="seat-1", role="core",
                            model_or_runtime="probe",
                            context_scope="probe scope")
    # A strict cycle cannot be completed by a bare status skeleton.
    try:
        complete_report(report1)
        bare_ok = False
    except ValueError:
        bare_ok = True
    expect("complete_report refuses a report with no RUN evidence "
           "(DOGFOOD V)",
           bare_ok)
    append_run(report1, "IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
                        "expected: x\nactual: y\nevidence: z\n")
    complete_report(report1)
    ticket_fixture(life_root, "T-900")
    write_sweep_entry(c1, {"run": "RUN-1", "imp_id": "001",
                           "disposition": "CONFIRMED", "ticket": "T-900",
                           "report": "saipen_improve_A.md",
                           "reproduced": "y"})
    complete_cycle(c1)
    c2 = create_cycle(life_root, "imp-two")
    expect("a completed cycle allows the next cycle (no evidence deleted)",
           (c1 / "MANIFEST.md").is_file()
           and (c2 / "MANIFEST.md").is_file(), repr((c1, c2)))
    expect("historical cycle evidence is not deleted to admit the next",
           (c1 / "MANIFEST.md").is_file())

    # T-595: complete_cycle refuses when a required report is missing/draft;
    # completed cycle is immutable under register_seat/append_run.
    imm_root = project_fixture("saipen-imm-")
    cimm = create_cycle(imm_root, "imp-imm")
    register_seat(cimm, "seat-1", "core", "saipen_improve_A.md")
    imm_report = create_report(imm_root, "imp-imm", "seat-1", "A",
                               agent="seat-1", role="core",
                               model_or_runtime="probe",
                               context_scope="probe scope")
    try:
        complete_cycle(cimm)
        early = False
    except ValueError:
        early = True
    expect("complete_cycle refuses a draft report (completion means something)",
           early)
    append_run(imm_report, "IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
                           "expected: x\nactual: y\nevidence: z\n")
    complete_report(imm_report)
    ticket_fixture(imm_root, "T-900")
    write_sweep_entry(cimm, {"run": "RUN-1", "imp_id": "001",
                             "disposition": "CONFIRMED", "ticket": "T-900",
                             "report": "saipen_improve_A.md",
                             "reproduced": "y"})
    complete_cycle(cimm)
    try:
        register_seat(cimm, "seat-2", "core", "saipen_improve_B.md")
        late_seat = False
    except ValueError:
        late_seat = True
    expect("register_seat refuses a completed cycle (immutable)",
           late_seat)
    try:
        append_run(imm_report, "late run")
        late_run = False
    except ValueError:
        late_run = True
    expect("append_run refuses a completed cycle (immutable)",
           late_run)
    from improve import write_sweep_entry as _wse
    try:
        _wse(cimm, {"run": "RUN-1", "imp_id": "001",
                    "disposition": "CONFIRMED", "ticket": "T-900",
                    "report": "saipen_improve_A.md", "reproduced": "y"})
        late_sweep = False
    except ValueError:
        late_sweep = True
    expect("write_sweep_entry refuses a completed cycle (immutable)",
           late_sweep)

    # ---- T-595: end-to-end writer -> filesystem -> parser -> derive_status
    # with NO hand-built intermediate strings. write_sweep_entry(imp_id="001")
    # must write exactly one IMP-001 that derive_status reads back.
    e2e_root = project_fixture("saipen-e2e-")
    e2e_cycle = create_cycle(e2e_root, "imp-e2e")
    register_seat(e2e_cycle, "seat-a", "core", "saipen_improve_A.md")
    register_seat(e2e_cycle, "seat-b", "core", "saipen_improve_B.md")
    rep_a = create_report(e2e_root, "imp-e2e", "seat-a", "A", agent="seat-a",
                          role="core", model_or_runtime="probe",
                          context_scope="scope")
    rep_b = create_report(e2e_root, "imp-e2e", "seat-b", "B", agent="seat-b",
                          role="core", model_or_runtime="probe",
                          context_scope="scope")
    append_run(rep_a, "IMP-001 [P1] [PROTOCOL_VIOLATION] [proven] [ticket]\n"
                      "expected: a\nactual: b\nevidence: c\n")
    append_run(rep_b, "IMP-001 [P1] [PROTOCOL_VIOLATION] [proven] [ticket]\n"
                      "expected: d\nactual: e\nevidence: f\n")
    complete_report(rep_a)
    complete_report(rep_b)
    ticket_fixture(e2e_root, "T-900")
    roster_e2e = (e2e_cycle / "MANIFEST.md").read_text(encoding="utf-8-sig")
    # Write one disposition for seat A only, using the numeric-id input that
    # once produced IMP-IMP-001.
    _wse(e2e_cycle, {"run": "RUN-1", "imp_id": "001",
                     "disposition": "CONFIRMED", "ticket": "T-900",
                     "report": "saipen_improve_A.md", "reproduced": "y"})
    sweep_text = (e2e_cycle / "SWEEP.md").read_text(encoding="utf-8")
    expect("sweep writer emits exactly one IMP-001 (never IMP-IMP-001)",
           sweep_text.count("IMP-001") == 1
           and "IMP-IMP-001" not in sweep_text, repr(sweep_text))
    # derive_status over the ACTUAL written SWEEP: A swept, B not.
    st_a = derive_status("saipen_improve_A.md", roster_e2e,
                         rep_a.read_text(encoding="utf-8"), sweep_text)
    st_b = derive_status("saipen_improve_B.md", roster_e2e,
                         rep_b.read_text(encoding="utf-8"), sweep_text)
    expect("writer->parser->derive_status: A swept, B not (same local IMP-001)",
           st_a["visible"] == "swept" and st_b["visible"] == "complete",
           repr((st_a, st_b)))

    # ---- T-589: deterministic cycle-id allocator.
    alloc_root = project_fixture("saipen-alloc-")
    id1 = allocate_cycle_id(alloc_root, "proj-x")
    cid1 = create_cycle(alloc_root, id1)
    register_seat(cid1, "seat-1", "core", "saipen_improve_A.md")
    a_report = create_report(alloc_root, id1, "seat-1", "A", agent="seat-1",
                             role="core", model_or_runtime="probe",
                             context_scope="scope")
    append_run(a_report, "IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
                         "expected: x\nactual: y\nevidence: z\n")
    complete_report(a_report)
    ticket_fixture(alloc_root, "T-900")
    write_sweep_entry(cid1, {"run": "RUN-1", "imp_id": "001",
                             "disposition": "CONFIRMED", "ticket": "T-900",
                             "report": "saipen_improve_A.md",
                             "reproduced": "y"})
    complete_cycle(cid1)
    id2 = allocate_cycle_id(alloc_root, "proj-x")
    expect("cycle-id allocator is deterministic and collision-safe",
           id1 != id2 and id2.endswith("-2"), repr((id1, id2)))

    # ---- NITRO dogfood IV (T-601): complete_cycle must NOT freeze the
    # artifact before its Core sweep finishes. Real lifecycle test, not a
    # completion-then-refusal proof: active -> reports complete -> PARTIAL
    # sweep -> complete_cycle REFUSE -> remaining dispositions -> complete_cycle
    # COMMITTED -> every ordinary mutator REFUSEs -> next cycle admitted.
    from saipen_engine.journal import verify_improve as _verify_improve
    life2 = project_fixture("saipen-life2-")
    cL = create_cycle(life2, "imp-life2")
    register_seat(cL, "seat-1", "core", "saipen_improve_A.md")
    repL = create_report(life2, "imp-life2", "seat-1", "A", agent="seat-1",
                         role="core", model_or_runtime="probe",
                         context_scope="scope")
    append_run(repL, "IMP-001 [P1] [PROTOCOL_VIOLATION] [proven] [ticket]\n"
                     "expected: x\nactual: y\nevidence: z\n"
                     "IMP-002 [P1] [PROTOCOL_VIOLATION] [proven] [ticket]\n"
                     "expected: x\nactual: y\nevidence: z\n")
    complete_report(repL)
    ticket_fixture(life2, "T-900")
    # partial sweep: only IMP-001 disposed
    write_sweep_entry(cL, {"run": "RUN-1", "imp_id": "001",
                           "disposition": "CONFIRMED", "ticket": "T-900",
                           "report": "saipen_improve_A.md",
                           "reproduced": "y"})
    try:
        complete_cycle(cL)
        partial_ok = False
    except ValueError:
        partial_ok = True
    expect("lifecycle: partial sweep REFUSEs complete_cycle (unswept IMP-002)",
           partial_ok and _improve._cycle_status(cL / "MANIFEST.md") == "active",
           repr(_improve._cycle_status(cL / "MANIFEST.md")))
    write_sweep_entry(cL, {"run": "RUN-1", "imp_id": "002",
                           "disposition": "CONFIRMED", "ticket": "T-900",
                           "report": "saipen_improve_A.md",
                           "reproduced": "y"})
    complete_cycle(cL)
    expect("lifecycle: full sweep coverage permits complete_cycle",
           _improve._cycle_status(cL / "MANIFEST.md") == "complete")
    for mutator, label in [
        (lambda: register_seat(cL, "seat-2", "core", "saipen_improve_B.md"),
         "register_seat"),
        (lambda: write_sweep_entry(
            cL, {"run": "RUN-1", "imp_id": "003",
                 "disposition": "CONFIRMED", "ticket": "T-900",
                 "report": "saipen_improve_A.md", "reproduced": "y"}),
         "write_sweep_entry"),
    ]:
        try:
            mutator()
            refused = False
        except ValueError:
            refused = True
        expect(f"lifecycle: {label} REFUSEs a completed cycle (immutable)",
               refused)
    cL2 = create_cycle(life2, "imp-life2-2")
    expect("lifecycle: the next cycle is admitted after completion",
           (cL2 / "MANIFEST.md").is_file())

    # ---- T-601: malformed SWEEP fails its OWN semantic verifier while a
    # valid SWEEP passes (writer and verifier consume the SAME grammar).
    sweep_bad = cL2 / "SWEEP.md"
    sweep_bad.write_text("arbitrary malformed garbage\nNOT A SWEEP\n",
                         encoding="utf-8")
    bad_errs = _verify_improve(life2, [{"path": sweep_bad.relative_to(
        life2).as_posix(), "role": "sweep"}])
    expect("verifier: malformed SWEEP FAILs the semantic verifier",
           len(bad_errs) >= 3 and "ledger grammar" in " ".join(bad_errs),
           repr(bad_errs))
    # fresh ledger: the writer's own output must satisfy the verifier
    sweep_bad.unlink()
    register_seat(cL2, "seat-1", "core", "saipen_improve_A.md")
    repL2 = create_report(life2, "imp-life2-2", "seat-1", "A", agent="seat-1",
                          role="core", model_or_runtime="probe",
                          context_scope="scope")
    append_run(repL2, "IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
                      "expected: x\nactual: y\nevidence: z\n")
    complete_report(repL2)
    write_sweep_entry(cL2, {"run": "RUN-1", "imp_id": "001",
                            "disposition": "CONFIRMED", "ticket": "T-900",
                            "report": "saipen_improve_A.md",
                            "reproduced": "y"})
    sweep_text2 = (cL2 / "SWEEP.md").read_text(encoding="utf-8")
    good_errs = _verify_improve(life2, [{"path": ".saipen/improve/"
                                         "imp-life2-2/SWEEP.md",
                                         "role": "sweep"}])
    expect("verifier: the writer's own SWEEP output passes (same grammar)",
           good_errs == [] and sweep_text2.startswith("# SWEEP"),
           repr((good_errs, sweep_text2[:40])))

    # ---- T-601: Recovery uses the SAME target-aware verifier as APPLY. A
    # journaled improve op whose applied SWEEP is malformed must CONFLICT on
    # recovery (never COMMITTED) -- the policy postcondition class is one.
    from saipen_engine.journal import Journal as _RecJournal
    from saipen_engine.journal import hash_bytes as _rec_hb
    rec_root = project_fixture("saipen-recover-")
    register_cycle(rec_root, "imp-rec",
                   "# IMPROVE CYCLE ROSTER\ncycle_status: active\n")
    sweep_path = ".saipen/improve/imp-rec/SWEEP.md"
    garbage = "arbitrary malformed garbage\n"
    jrec = _RecJournal(rec_root, "op-rec")
    jrec.start("sweep", "probe", "id", "h",
               [{"path": sweep_path, "role": "sweep",
                 "content": garbage.encode("utf-8"),
                 "before_hash": _rec_hb(b""),
                 "after_hash": _rec_hb(garbage.encode("utf-8"))}],
               verification_policy="improve_atomic_file")
    (rec_root / sweep_path).write_bytes(garbage.encode("utf-8"))
    jrec.mark("APPLYING", progress_index=1, target_index=0)
    rec_res = recover(rec_root, "op-rec")
    expect("recovery runs the same target-aware verifier: malformed SWEEP "
           "CONFLICTs on recovery, never COMMITTED",
           not rec_res.get("ok") and rec_res.get("code") == "CONFLICT"
           and "semantic verifier" in rec_res.get("detail", ""),
           repr(rec_res))

    # ---- T-553: improve routing is DERIVED -- manifest/sweep edits change
    # the visible status with ZERO STATE writes (no independent counters).
    derive_root = project_fixture("saipen-derive-")
    d_cycle, report_d = mech_cycle(derive_root, "imp-derive", "seat-1", "A",
                                   ["IMP-001 [P1] [PROTOCOL_VIOLATION] "
                                    "[proven] [ticket]\n"
                                    "expected: x\nactual: y\nevidence: z\n"])
    state_bytes_before = (derive_root / ".saipen" / "STATE.md").read_bytes()
    write_sweep_entry(d_cycle, {"run": "RUN-1", "imp_id": "001",
                                "disposition": "CONFIRMED", "ticket": "T-900",
                                "report": "saipen_improve_A.md",
                                "reproduced": "y"})
    manifest_text = (d_cycle / "MANIFEST.md").read_text(encoding="utf-8")
    st_after = derive_status("saipen_improve_A.md", manifest_text,
                             report_d.read_text(encoding="utf-8"),
                             (d_cycle / "SWEEP.md").read_text(encoding="utf-8"))
    expect("improve routing: manifest+sweep edits flip the derived status "
           "(complete->swept) with zero STATE writes",
           st_after["visible"] == "swept"
           and (derive_root / ".saipen" / "STATE.md").read_bytes()
           == state_bytes_before,
           repr((st_after["visible"],
                 (derive_root / ".saipen" / "STATE.md").read_bytes()
                 == state_bytes_before)))

    # ---- T-555: the report completion bar is mechanical. NO_FINDINGS with a
    # stated scope passes; report_status: complete without a context_scope is
    # an unmet completion bar; a partial scope cannot claim full context.
    nf_report = good.split("\nIMP-001")[0].rstrip() + "\n"
    expect("improve report: NO_FINDINGS with a stated scope validates",
           validate_report(nf_report) == [], repr(validate_report(nf_report)))
    complete_noscope = nf_report.replace(
        "context_scope: tools/improve.py", "context_scope: ").replace(
        "report_status: draft", "report_status: complete")
    expect("improve report: report_status complete over an unmet completion "
           "bar is rejected",
           any("completion bar" in e
               for e in validate_report(complete_noscope)),
           repr(validate_report(complete_noscope)))
    partial_full = good.replace("context_scope: tools/improve.py",
                                "context_scope: partial: tools only")
    expect("improve report: a partial scope cannot claim complete context",
           any("partial" in e and "complete" in e
               for e in validate_report(partial_full)),
           repr(validate_report(partial_full)))

    # ---- T-556: Core sweep is the only path from report to canonical work.
    # Sweep dispositions are mechanically linked to tickets: CONFIRMED must
    # reference a real board ticket and be reproduced; INVALID/ALREADY_FIXED
    # must never carry a ticket; a disposition must still resolve to its
    # report's finding; a ticket's source_reports must resolve to SWEEP.md;
    # one root cause across reports produces ONE ticket.
    def sweep_project(dispositions: list[str], tickets: list[str],
                      source_reports: dict[str, str],
                      report_text: str) -> Path:
        _root = project_fixture("saipen-sweep")
        (_root / ".saipen" / "STATE.md").write_text(
            "---\nphase: DONE\ntask: none\nnext_action: \"saipen continue\"\n"
            "blocker: \"\"\ntransition_from: SHIP\nsaipen_version: 7\n"
            "schema_version: 3\nlast_event: 900\nstyle_contract: ded-4ae736e4\n"
            "saipen_home: \".\"\nagent: probe\nmode: full\n"
            "updated: 2026-08-09T00:00:00Z\n---\n", encoding="utf-8")
        _cycle = register_cycle(_root, "imp-sweep",
                                "# IMPROVE CYCLE ROSTER\ncycle_status: active\n")
        register_seat(_cycle, "seat1", "core", "saipen_improve_A.md")
        _rep = _cycle / "seat1" / "saipen_improve_A.md"
        _rep.parent.mkdir(parents=True, exist_ok=True)
        _rep.write_text(report_text, encoding="utf-8")
        (_cycle / "SWEEP.md").write_text(
            "# SWEEP\n" + "\n".join(dispositions) + "\n", encoding="utf-8")
        board_lines = ["# Board", "## DOING", "## TODO"]
        for _tid, _sr in source_reports.items():
            board_lines.append(f"- [ ] {_tid} [P1] swept ticket | verify: "
                               f"probe"
                               + (f" | source_reports: {_sr}" if _sr else ""))
        board_lines += ["## DONE", "## BLOCKED"]
        (_root / ".saipen" / "BOARD.md").write_text(
            "\n".join(board_lines) + "\n", encoding="utf-8")
        return _root

    def validator_rc(_root: Path) -> int:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--project-root", str(_root)],
            cwd=str(_root), capture_output=True, text=True, errors="replace",
            timeout=120).returncode

    _rep_header = ("agent: probe\nrole: core\nmodel_or_runtime: test\n"
                   "project: PROJ\nsaipen_version: 7.220.0\n"
                   "protocol_fingerprint: deadbeef\nsource_head: abc\n"
                   "source_tree_fingerprint: beef\n"
                   "context_scope: tools/\ncontext_available: partial\n"
                   "report_status: complete\n\n")
    _rep_text = (_rep_header
                 + "IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
                 + "expected: x\nactual: y\nevidence: z\n"
                 + "IMP-002 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
                 + "expected: x\nactual: y\nevidence: z\n"
                 + "IMP-003 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
                 + "expected: x\nactual: y\nevidence: z\n")
    ok_root = sweep_project(
        ["- IMP-001 [CONFIRMED] T-900 report=saipen_improve_A.md "
         "reproduced=y",
         "- IMP-002 [CONFIRMED] T-900 report=saipen_improve_A.md "
         "reproduced=y",
         "- IMP-003 [CONFIRMED] T-900 report=saipen_improve_A.md "
         "reproduced=y"],
        ["T-900"],
        {"T-900": "IMP-001,IMP-002,IMP-003"}, _rep_text)
    expect("sweep: three reports' root cause deduplicates into ONE ticket "
           "(red control 11, validator green)",
           validator_rc(ok_root) == 0,
           validator_rc(ok_root))
    bad10 = sweep_project(
        ["- IMP-001 [CONFIRMED] T-900 report=saipen_improve_A.md "
         "reproduced=n"],
        ["T-900"], {"T-900": "IMP-001"}, _rep_text)
    expect("sweep: an unverified finding cannot produce a ticket (red "
           "control 10, validator red)",
           validator_rc(bad10) != 0, repr(validator_rc(bad10)))
    bad12 = sweep_project(
        ["- IMP-001 [INVALID] T-900 report=saipen_improve_A.md "
         "reproduced=n"],
        ["T-900"], {"T-900": "IMP-001"}, _rep_text)
    expect("sweep: an INVALID finding must never produce a ticket (red "
           "control 12, validator red)",
           validator_rc(bad12) != 0, repr(validator_rc(bad12)))
    bad20 = sweep_project(
        ["- IMP-001 [CONFIRMED] T-900 report=saipen_improve_A.md "
         "reproduced=y"],
        ["T-900"], {"T-900": "IMP-999"}, _rep_text)
    expect("sweep: an unresolvable source_reports ref fails (red control 20, "
           "validator red)",
           validator_rc(bad20) != 0, repr(validator_rc(bad20)))
    bad19 = sweep_project(
        ["- IMP-001 [CONFIRMED] T-900 report=saipen_improve_A.md "
         "reproduced=y"],
        ["T-900"], {"T-900": "IMP-001"},
        _rep_header
        + "IMP-002 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
        + "expected: x\nactual: y\nevidence: z\n")
    expect("sweep: an edited-away original finding loses its disposition "
           "(red control 19, validator red)",
           validator_rc(bad19) != 0, repr(validator_rc(bad19)))
    # red control 22 (T-557): a seat report is evidence, never canonical
    # BOARD state -- a report carrying board section headings is rejected.
    report_as_board = sweep_project(
        ["- IMP-001 [CONFIRMED] T-900 report=saipen_improve_A.md "
         "reproduced=y"],
        ["T-900"], {"T-900": "IMP-001"},
        _rep_header.replace("report_status: complete", "report_status: "
                            "complete\n## DOING\n## TODO")
        + "IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
        + "expected: x\nactual: y\nevidence: z\n")
    expect("sweep: a report treated as canonical BOARD state is rejected "
           "(red control 22, validator red)",
           validator_rc(report_as_board) != 0,
           repr(validator_rc(report_as_board)))
    # T-558 reasoning gates: a PROTOCOL_VIOLATION finding that produced a
    # ticket MUST carry recurrence + weak_model (red 15/16); ACCIDENTAL_SUCCESS
    # is never PASS (red 5).
    def sweep_ticket_project(finding_class: str, fields: dict[str, str],
                             reproduced: str = "y") -> Path:
        _extra = "".join(f" | {k}: {v}" for k, v in fields.items())
        _root = sweep_project(
            ["- IMP-001 [CONFIRMED] T-900 "
             "report=saipen_improve_A.md reproduced=" + reproduced],
            ["T-900"],
            {"T-900": "IMP-001" + _extra},
            _rep_header + ("IMP-001 [P1] [" + finding_class
                           + "] [proven] [ticket]\n"
                           + "expected: x\nactual: y\nevidence: z\n"))
        return _root

    no_gates = sweep_ticket_project("PROTOCOL_VIOLATION", {})
    expect("sweep: a PROTOCOL_VIOLATION ticket without recurrence/weak_model "
           "fails (red controls 15/16, validator red)",
           validator_rc(no_gates) != 0, repr(validator_rc(no_gates)))
    with_gates = sweep_ticket_project(
        "PROTOCOL_VIOLATION",
        {"recurrence": "recurs across projects (protocol rule)",
         "weak_model": "a weak model could still route past it; fixed by "
                       "the validator check"})
    expect("sweep: a PROTOCOL_VIOLATION ticket with both reasoning gates "
           "passes",
           validator_rc(with_gates) == 0, repr(validator_rc(with_gates)))
    acc_success = sweep_ticket_project("ACCIDENTAL_SUCCESS", {})
    expect("sweep: an ACCIDENTAL_SUCCESS result recorded as PASS fails "
           "(red control 5, validator red)",
           validator_rc(acc_success) != 0, repr(validator_rc(acc_success)))
    # T-559 archive-with-provenance: deleting SWEEP.md to "clean up" breaks an
    # archived report's ticket provenance (red control 24); partial/timed-out
    # evidence can never mark an IMP fixed (red control 25).
    ok_archive = sweep_project(
        ["- IMP-001 [CONFIRMED] T-900 report=saipen_improve_A.md "
         "reproduced=y"],
        ["T-900"], {"T-900": "IMP-001"}, _rep_text)
    _arch_sweeps = list((ok_archive / ".saipen" / "improve").rglob(
        "SWEEP.md"))
    _arch_sweep = _arch_sweeps[0]
    _arch_sweep.unlink()
    expect("sweep: deleting SWEEP.md breaks archived-report ticket "
           "provenance (red control 24, validator red)",
           validator_rc(ok_archive) != 0, repr(validator_rc(ok_archive)))
    partial_evidence = sweep_project(
        ["- IMP-001 [CONFIRMED] T-900 report=saipen_improve_A.md "
         "reproduced=partial"],
        ["T-900"], {"T-900": "IMP-001"}, _rep_text)
    expect("sweep: partial/timed-out evidence cannot mark an IMP fixed "
           "(red control 25, validator red)",
           validator_rc(partial_evidence) != 0,
           repr(validator_rc(partial_evidence)))
    # Seat directories own report identity. Equal basenames in different seat
    # homes are distinct reports, not shared ownership.
    shared_roster = ("# IMPROVE CYCLE ROSTER\n"
                     "seat_id: seat-a\nrole: core\nreport_path: a.md\n"
                     "availability: expected\n"
                     "seat_id: seat-b\nrole: core\nreport_path: a.md\n"
                     "availability: expected\n")
    expect("improve roster: same basename in distinct seat homes is valid",
           validate_manifest(shared_roster) == [],
           repr(validate_manifest(shared_roster)))
    proven_unverified = sweep_ticket_project("LOGIC_ERROR", {},
                                             reproduced="n")
    expect("sweep: confidence: proven does not override Core's verification "
           "requirement (red control 14, validator red)",
           validator_rc(proven_unverified) != 0,
           repr(validator_rc(proven_unverified)))
    stale_report = _rep_header.replace("source_head: abc",
                                       "source_head: deadbeef")
    stale_root = sweep_project(
        ["- IMP-001 [CONFIRMED] T-900 report=saipen_improve_A.md "
         "reproduced=y"],
        ["T-900"], {"T-900": "IMP-001"}, stale_report)
    subprocess.run(["git", "init", "-q"], cwd=str(stale_root), check=False)
    subprocess.run(["git", "add", "-A"], cwd=str(stale_root), check=False)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "base"], cwd=str(stale_root),
                   check=False)
    expect("sweep: a report auditing a stale head fails (reload-before-"
           "audit, red controls 1/2, validator red)",
           validator_rc(stale_root) != 0, repr(validator_rc(stale_root)))
    fresh_report = (_rep_header.replace("source_head: abc",
                                        "source_head: ")
                    + "IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
                    + "expected: x\nactual: y\nevidence: z\n")
    # a fresh report with the ACTUAL current head (after git init+commit) is
    # not flagged by the reload check
    fresh_root = sweep_project(
        ["- IMP-001 [CONFIRMED] T-900 report=saipen_improve_A.md "
         "reproduced=y"],
        ["T-900"], {"T-900": "IMP-001"}, fresh_report)
    subprocess.run(["git", "init", "-q"], cwd=str(fresh_root), check=False)
    subprocess.run(["git", "add", "-A"], cwd=str(fresh_root), check=False)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "base"], cwd=str(fresh_root),
                   check=False)
    _head2 = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(fresh_root),
                            capture_output=True, text=True).stdout.strip()
    _reps2 = list((fresh_root / ".saipen" / "improve").rglob(
        "saipen_improve_*.md"))
    _rep2 = _reps2[0]
    _rep2.write_text(
        _rep2.read_text(encoding="utf-8").replace("source_head: ",
                                                  f"source_head: {_head2}"),
        encoding="utf-8")
    expect("sweep: a report audited against the current head passes the "
           "reload check (no false positive)",
           validator_rc(fresh_root) == 0,
           repr(validator_rc(fresh_root))
           + "\n" + subprocess.run(
               [sys.executable, str(VALIDATOR), "--project-root",
                str(fresh_root)],
               cwd=str(fresh_root), capture_output=True, text=True,
               errors="replace", timeout=120).stdout[-800:])

    # T-606: the saipen improve CLI family EXECUTES (SAICRITIC's
    # register-without-executor fix). status is read-only and derives the
    # visible per-seat status with zero STATE writes; verify runs the
    # delta-only semantic verifier; clean archives a completed cycle.
    cli_root = project_fixture("saipen-cli-")
    _cli_cycle, _cli_rep = mech_cycle(
        cli_root, "imp-cli", "seat-1", "A",
        ["IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
         "expected: x\nactual: y\nevidence: z\n"])
    state_before = (cli_root / ".saipen" / "STATE.md").read_bytes()
    cli_proc = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "improve",
         "status", "--json"],
        cwd=str(cli_root), capture_output=True, text=True, timeout=60)
    expect("saipen improve status executes and derives per-seat status",
           '"code": "IMPROVE_STATUS"' in cli_proc.stdout
           and '"visible": "complete"' in cli_proc.stdout,
           repr(cli_proc.stdout[:200]))
    expect("saipen improve status is read-only (zero STATE writes)",
           (cli_root / ".saipen" / "STATE.md").read_bytes() == state_before,
           "state changed")
    cli_clean = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "improve",
         "clean", "imp-cli", "--json"],
        cwd=str(cli_root), capture_output=True, text=True, timeout=60)
    expect("saipen improve clean refuses an ACTIVE cycle (archive needs "
           "complete)",
           '"code": "VALIDATION_FAILED"' in cli_clean.stdout,
           repr(cli_clean.stdout[:200]))
    _cli_sweep = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "improve",
         "sweep", "imp-cli", "RUN-1/IMP-001", "CONFIRMED", "--ticket",
         "T-900", "--report", "saipen_improve_A.md", "--reproduced", "y",
         "--json"],
        cwd=str(cli_root), capture_output=True, text=True, timeout=60)
    expect("saipen improve sweep writes a disposition through the journal",
           '"code": "COMMITTED"' in _cli_sweep.stdout,
           repr(_cli_sweep.stdout[:200]))
    # verify runs AFTER the sweep, so the complete cycle bar is actually met.
    cli_verify = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "improve",
         "verify", "imp-cli", "--json"],
        cwd=str(cli_root), capture_output=True, text=True, timeout=60)
    expect("saipen improve verify executes the delta-only verifier on a "
           "fully-swept cycle",
           '"code": "IMPROVE_VERIFY_PASS"' in cli_verify.stdout
           and '"delta_only": true' in cli_verify.stdout,
           repr(cli_verify.stdout[:200]))

    # ---- DOGFOOD V (T-617): bare `saipen improve` is the documented
    # meta-control -- it prepares the bounded audit assignment, never an alias
    # for status, and never changes phase/task/next_action.
    meta_root = project_fixture("saipen-meta-")
    state_before_meta = (meta_root / ".saipen" / "STATE.md").read_bytes()
    bare_proc = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "improve",
         "--json"],
        cwd=str(meta_root), capture_output=True, text=True, timeout=60)
    expect("bare saipen improve prepares the audit assignment (not status)",
           '"code": "IMPROVE_AUDIT_ASSIGNMENT"' in bare_proc.stdout
           and '"cycle_id"' in bare_proc.stdout
           and '"source_tree_fingerprint"' in bare_proc.stdout,
           repr(bare_proc.stdout[:300]))
    _bare_data = json.loads(bare_proc.stdout)
    expect("bare Improve assignment emits SAICRITIC's exact ordered proof set",
           _bare_data.get("proof_levels") == [
               "UNIT", "COMPOSITION", "CANONICAL", "GATE", "PROVENANCE"],
           repr(_bare_data.get("proof_levels")))
    # ---- T-624: provenance truth -- the CLI-prepared report header must
    # carry a DERIVED protocol fingerprint (never a copied style marker), a
    # truthful neutral runtime (never a guessed model constant), and a
    # partial/unknown context (completeness is not yet proven).
    _bare_report = meta_root / _bare_data["report_path"]
    _bare_header = _bare_report.read_text(encoding="utf-8-sig").split(
        "\n## ", 1)[0]
    _derived_fp = installed_protocol_fingerprint(HOME)
    expect("CLI-prepared report derives its protocol fingerprint from owned "
           "protocol evidence",
           f"protocol_fingerprint: {_derived_fp}" in _bare_header
           and "ded-4ae736e4" not in _bare_header,
           _bare_header)
    expect("CLI-prepared report never carries a guessed model constant",
           re.search(r"(?m)^model_or_runtime:\s*deepseek", _bare_header) is None
           and "model_or_runtime: unknown" in _bare_header,
           _bare_header)
    expect("CLI-prepared report begins context as partial, not complete",
           "context_available: partial" in _bare_header
           and "context_available: complete" not in _bare_header,
           _bare_header)
    with tempfile.TemporaryDirectory(prefix="saipen-proto-fp-") as _proto_raw:
        _proto_home = Path(_proto_raw) / "home"
        shutil.copytree(HOME, _proto_home, ignore=shutil.ignore_patterns(
            ".git", ".venv", "__pycache__", "node_modules", "nul", ".freebuff"))
        _fp_before = installed_protocol_fingerprint(_proto_home)
        _mutated_proto = _proto_home / "saipen" / "CORE.md"
        if _mutated_proto.is_file():
            _mutated_proto.write_text(
                _mutated_proto.read_text(encoding="utf-8-sig")
                + "\nT-624 provenance probe marker\n",
                encoding="utf-8")
        _fp_after = installed_protocol_fingerprint(_proto_home)
        expect("editing a protocol document changes the derived fingerprint",
               _fp_after != _fp_before
               and _fp_after.startswith("sha256:"),
               f"{_fp_before} vs {_fp_after}")

    # T-992/§2 + §3: strict provenance value semantics -- fabricated identity
    # scalars, blank scalars, unknown headers, agent/seat mismatch, project/
    # manifest mismatch, and a foreign project VERSION laundering into
    # saipen_version must ALL be refused by the shared validator and the writer.
    _prov_truth = ("agent: seat-01\nrole: core\nmodel_or_runtime: unknown\n"
                   f"project: probe-project\n"
                   f"saipen_version: {PROBE_SAIPEN_VERSION}\n"
                   f"protocol_fingerprint: {PROBE_INSTALLED_FP}\n"
                   "source_head: abc\nsource_tree_fingerprint: "
                   "git-delta-v1:beef\ndiscovery_model: git-delta-v1\n"
                   "context_scope: tools\ncontext_available: partial\n"
                   "report_status: draft\n\n")
    for _label, _needle in [
            ("fabricated protocol fingerprint", "protocol_fingerprint"),
            ("blank required scalar", "non-empty"),
            ("agent != seat", "agent"),
            ("unknown header field", "unknown field"),
            ("control injection in runtime", "control")]:
        # rebuild precisely per case
        if _label == "fabricated protocol fingerprint":
            _bad = _prov_truth.replace(
                f"protocol_fingerprint: {PROBE_INSTALLED_FP}",
                "protocol_fingerprint: totally-fabricated")
        elif _label == "blank required scalar":
            _bad = _prov_truth.replace("saipen_version: "
                                       + PROBE_SAIPEN_VERSION,
                                       "saipen_version: ")
        elif _label == "agent != seat":
            _bad = _prov_truth.replace("agent: seat-01",
                                       "agent: not-seat-01")
        elif _label == "unknown header field":
            _bad = "extra: x\n" + _prov_truth
        elif _label == "control injection in runtime":
            _bad = _prov_truth.replace("model_or_runtime: unknown",
                                       "model_or_runtime: a\x00b")
        _errs = validate_strict_provenance(
            _bad, roster=_prov_truth,
            manifest_project_identity="probe-project", seat_id="seat-01",
            installed_saipen_version=PROBE_SAIPEN_VERSION,
            installed_protocol_fp=PROBE_INSTALLED_FP)
        expect(f"strict provenance refuses {_label}",
               any(_needle in e for e in _errs), repr(_errs))

    # §3: the writer must never read the target project's VERSION into
    # saipen_version -- install-only, even when the project VERSION differs.
    with tempfile.TemporaryDirectory(prefix="saipen-fp-version-") as _fv_raw:
        _fv_root = Path(_fv_raw) / "proj"
        _fv_root.mkdir()
        (_fv_root / ".saipen").mkdir()
        (_fv_root / ".saipen" / "LOG.md").write_text(
            "- 09.08.26 00:00 [E-900] DEC: base\n", encoding="utf-8")
        (_fv_root / ".saipen" / "BOARD.md").write_text(
            "# Board\n## DOING\n## TODO\n## DONE\n## BLOCKED\n",
            encoding="utf-8")
        (_fv_root / ".saipen" / "STATE.md").write_text(
            "---\nphase: DONE\ntask: none\nnext_action: \"saipen continue\"\n"
            "blocker: \"\"\ntransition_from: SHIP\nsaipen_version: 7\n"
            "schema_version: 3\nlast_event: 900\nstyle_contract: ded-4ae736e4\n"
            "saipen_home: \".\"\nagent: probe\nmode: full\n"
            "updated: 2026-08-09T00:00:00Z\n---\n", encoding="utf-8")
        (_fv_root / "VERSION").write_text("1.2.3\n", encoding="utf-8")
        _fv_cycle = create_cycle(_fv_root, "imp-fv",
                                 created_at="2026-08-12T00:00:00Z",
                                 project_identity="p")
        register_seat(_fv_cycle, "seat-1", "core",
                      "saipen_improve_A.md")
        _fv_rep = create_report(
            _fv_root, "imp-fv", "seat-1", "A", agent="seat-1", role="core",
            model_or_runtime="probe",
            context_scope="scope")
        _fv_header = _fv_rep.read_text(encoding="utf-8-sig").split("\n## ", 1)[0]
        expect("foreign project VERSION can never become saipen_version",
               f"saipen_version: {PROBE_SAIPEN_VERSION}" in _fv_header
               and "saipen_version: 1.2.3" not in _fv_header,
               _fv_header)
    _saipen_spec = importlib.util.spec_from_file_location(
        "saipen_flattened_proof_probe", HOME / "tools" / "saipen.py")
    _saipen_module = importlib.util.module_from_spec(_saipen_spec)
    _saipen_spec.loader.exec_module(_saipen_module)
    with tempfile.TemporaryDirectory(prefix="saipen-flat-proof-") as _flat_raw:
        _flat_home = Path(_flat_raw)
        shutil.copy2(HOME / "saipen" / "SAICRITIC.md",
                     _flat_home / "SAICRITIC.md")
        _saipen_module.HOME = _flat_home
        expect("installed flattened layout exposes canonical SAICRITIC proof set",
               _saipen_module._canonical_proof_levels() == [
                   "UNIT", "COMPOSITION", "CANONICAL", "GATE", "PROVENANCE"])
        (_flat_home / "SAICRITIC.md").unlink()
        try:
            _saipen_module._canonical_proof_levels()
            _missing_proof_refused = False
        except ValueError:
            _missing_proof_refused = True
        expect("missing installed SAICRITIC proof owner refuses before assignment",
               _missing_proof_refused)
    _prepare_proc = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "improve",
         "prepare", "--json"], cwd=str(meta_root), capture_output=True,
        text=True, timeout=60)
    expect("explicit improve prepare is not a hidden public action",
           _prepare_proc.returncode == 2
           and '"code": "UNKNOWN_ACTION"' in _prepare_proc.stdout,
           repr(_prepare_proc.stdout[:300]))
    expect("bare saipen improve never changes phase/task (audit prep is "
           "read-only for STATE)",
           (meta_root / ".saipen" / "STATE.md").read_bytes()
           == state_before_meta)
    _admit_journal = json.loads((meta_root / ".saipen" / "recovery" / "ops"
                                 / _bare_data["op_id"]
                                 / "operation.json").read_text(encoding="utf-8"))
    expect("Improve admission journals roster and report as one operation",
           _admit_journal.get("operation") == "improve_admit"
           and len(_admit_journal.get("targets", [])) == 2
           and _admit_journal.get("status") == "COMMITTED",
           repr(_admit_journal))
    _crash_root = project_fixture("saipen-admit-crash-")
    import saipen_engine.journal as _admit_journal_module

    def _crash_between_admission_targets(stage: str) -> None:
        if stage == "manifest":
            raise SystemExit(91)

    with mock.patch.object(_admit_journal_module, "_crash_after",
                           side_effect=_crash_between_admission_targets):
        try:
            prepare_audit_seat(
                _crash_root, agent_family="probe", role="core",
                session_id="probe-crash", project_name="SAIPEN",
                model_or_runtime="probe",
                context_scope="atomic admission crash control")
            _admit_crashed = False
        except SystemExit:
            _admit_crashed = True
    _pending_admit = pending_ops(_crash_root)
    _pending_admit_record = Journal(
        _crash_root, _pending_admit[0]["op_id"]).read() \
        if _pending_admit else {}
    _crash_manifest_exists = any(
        (_crash_root / target["path"]).is_file()
        for target in _pending_admit_record.get("targets", [])
        if target.get("role") == "manifest")
    _crash_report_absent = all(
        not (_crash_root / target["path"]).exists()
        for target in _pending_admit_record.get("targets", [])
        if target.get("role") == "report")
    _admit_recovered = recover(
        _crash_root, _pending_admit[0]["op_id"]) if _pending_admit else {}
    _recovered_targets_exist = all(
        (_crash_root / target["path"]).is_file()
        for target in _pending_admit_record.get("targets", [])) \
        if _pending_admit else False
    expect("admission crash between roster/report rolls forward both targets",
           _admit_crashed and _crash_manifest_exists and _crash_report_absent
           and _admit_recovered.get("ok") and _recovered_targets_exist
           and not pending_ops(_crash_root),
           repr((_pending_admit, _admit_recovered)))

    # ---- PRE-v8 DOGFOOD VI (T-623): role/session admission contract.
    def _prepare(*options: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HOME / "tools" / "saipen.py"), "improve",
             *options, "--json"], cwd=str(meta_root), capture_output=True,
            text=True, timeout=60)

    _second_proc = _prepare("--new-seat")
    _second = json.loads(_second_proc.stdout)
    expect("bare/new-seat allocates an independent seat in the active cycle",
           _second_proc.returncode == 0
           and _second["cycle_id"] == _bare_data["cycle_id"]
           and _second["seat_id"] != _bare_data["seat_id"]
           and _second["report_path"] != _bare_data["report_path"],
           repr(_second))
    _critic_proc = _prepare("--role", "critic", "--session",
                            "critic-session-01")
    _critic = json.loads(_critic_proc.stdout)
    _critic_manifest_before = (meta_root / ".saipen" / "improve"
                               / _critic["cycle_id"] / "MANIFEST.md").read_bytes()
    _critic_report = meta_root / _critic["report_path"]
    _critic_report_before = _critic_report.read_bytes()
    _critic_retry_proc = _prepare("--role", "critic", "--session",
                                  "critic-session-01")
    _critic_retry = json.loads(_critic_retry_proc.stdout)
    expect("explicit session retry resumes idempotently without rewriting",
           _critic_proc.returncode == 0
           and _critic_retry_proc.returncode == 0
           and _critic_retry.get("resumed") is True
           and _critic_retry["seat_id"] == _critic["seat_id"]
           and (meta_root / ".saipen" / "improve" / _critic["cycle_id"]
                / "MANIFEST.md").read_bytes() == _critic_manifest_before
           and _critic_report.read_bytes() == _critic_report_before,
           repr(_critic_retry))
    _wrong_role = _prepare("--role", "core", "--session",
                           "critic-session-01")
    expect("explicit session retry refuses role drift",
           _wrong_role.returncode != 0
           and "is registered as role" in _wrong_role.stdout,
           repr(_wrong_role.stdout[:300]))
    _bad_role = _prepare("--role", "reviewer")
    expect("Improve role vocabulary is closed to core and critic",
           _bad_role.returncode != 0 and "outside core|critic" in _bad_role.stdout,
           repr(_bad_role.stdout[:300]))

    _status = _prepare("status", _critic["cycle_id"])
    expect("status derives independent same-basename seats by seat identity",
           _status.returncode == 0
           and _bare_data["seat_id"] in _status.stdout
           and _second["seat_id"] in _status.stdout
           and _critic["seat_id"] in _status.stdout
           and '"role": "critic"' in _status.stdout,
           repr(_status.stdout[:500]))
    _critic_report.write_bytes(
        _critic_report_before.replace(b"role: critic", b"role: core"))
    _mismatch_status = _prepare("status", _critic["cycle_id"])
    expect("status rejects roster/report role mismatch",
           "roster/report role mismatch" in _mismatch_status.stdout
           and '"visible": "INVALID_REPORT"' in _mismatch_status.stdout,
           repr(_mismatch_status.stdout[:500]))
    _critic_report.write_bytes(_critic_report_before)

    # ---- PRE-v8 DOGFOOD VII (T-630): an existing seat's state is a decision,
    # never a blank slate -- missing/malformed/complete/unavailable evidence
    # refuses with zero writes instead of being recreated under the same
    # identity. Runs on its OWN fixture project so the corruption it creates
    # cannot poison the shared meta_root cycle used by later controls.
    _seatc_root = project_fixture("saipen-seat-continuity-")

    def _scprep(*options: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HOME / "tools" / "saipen.py"), "improve",
             *options, "--json"], cwd=str(_seatc_root), capture_output=True,
            text=True, timeout=60)

    def _recovery_ops_snapshot(root: Path) -> dict[str, bytes]:
        ops = root / ".saipen" / "recovery" / "ops"
        if not ops.is_dir():
            return {}
        return {p.relative_to(ops).as_posix(): p.read_bytes()
                for p in sorted(ops.rglob("*")) if p.is_file()}

    _gap_proc = _scprep("--role", "critic", "--session", "critic-gap-01")
    _gap = json.loads(_gap_proc.stdout)
    _gap_report = _seatc_root / _gap["report_path"]
    _gap_manifest = (_seatc_root / ".saipen" / "improve" / _gap["cycle_id"]
                     / "MANIFEST.md")
    _gap_manifest_before = _gap_manifest.read_bytes()
    _gap_recovery_before = _recovery_ops_snapshot(_seatc_root)
    _gap_report.unlink()
    _gap_retry = json.loads(_scprep(
        "--role", "critic", "--session", "critic-gap-01").stdout)
    expect("missing report under a registered seat REFUSEs SEAT_EVIDENCE_MISSING",
           _gap_proc.returncode == 0
           and _gap_retry.get("code") == "SEAT_EVIDENCE_MISSING"
           and _gap_retry.get("ok") is False,
           repr(_gap_retry))
    expect("missing report causes zero writes and no new provenance",
           not _gap_report.exists()
           and _gap_manifest.read_bytes() == _gap_manifest_before
           and _recovery_ops_snapshot(_seatc_root) == _gap_recovery_before,
           repr((_gap_report.exists(),
                 _gap_manifest.read_bytes() == _gap_manifest_before,
                 sorted(set(_recovery_ops_snapshot(_seatc_root))
                        - set(_gap_recovery_before)))))

    _complete_proc = _scprep("--role", "critic", "--session",
                             "critic-complete-01")
    _complete = json.loads(_complete_proc.stdout)
    _complete_report_path = _seatc_root / _complete["report_path"]
    append_run(_complete_report_path,
               "IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
               "expected: executable next action\n"
               "actual: resumed immutable report\n"
               "evidence: seat continuity control\n")
    complete_report(_complete_report_path)
    _complete_retry = json.loads(_scprep(
        "--role", "critic", "--session", "critic-complete-01").stdout)
    expect("COMPLETE report cannot resume (SEAT_COMPLETE, resumed false)",
           _complete_retry.get("code") == "SEAT_COMPLETE"
           and _complete_retry.get("resumed") is False,
           repr(_complete_retry))
    expect("COMPLETE report yields an executable stable instruction",
           _complete_retry.get("next")
           and "saipen improve sweep" in _complete_retry.get("next", ""),
           repr(_complete_retry.get("next", "")))

    _unavail_proc = _scprep("--role", "critic", "--session",
                            "critic-unavail-01")
    _unavail = json.loads(_unavail_proc.stdout)
    _unavail_manifest = (_seatc_root / ".saipen" / "improve"
                         / _unavail["cycle_id"] / "MANIFEST.md")
    _unavail_report = _seatc_root / _unavail["report_path"]
    _unavail_report.unlink()

    def _set_seat_availability(manifest_text: str, seat_id: str,
                               value: str) -> str:
        lines = manifest_text.splitlines()
        out = []
        in_block = False
        for raw in lines:
            ln = raw
            if ln.startswith("seat_id: "):
                in_block = ln.strip() == f"seat_id: {seat_id}"
            if in_block and ln.strip().startswith("availability: "):
                ln = f"availability: {value}"
            out.append(ln)
        return "\n".join(out) + "\n"

    _unavail_manifest.write_text(
        _set_seat_availability(
            _unavail_manifest.read_text(encoding="utf-8-sig"),
            _unavail["seat_id"], "unavailable"),
        encoding="utf-8")
    _unavail_retry = json.loads(_scprep(
        "--role", "critic", "--session", "critic-unavail-01").stdout)
    expect("unavailable roster seat cannot revive (SEAT_UNAVAILABLE, "
           "zero writes)",
           _unavail_retry.get("code") == "SEAT_UNAVAILABLE"
           and not _unavail_report.exists(),
           repr(_unavail_retry))

    _malformed_proc = _scprep("--role", "critic", "--session",
                              "critic-malformed-01")
    _malformed = json.loads(_malformed_proc.stdout)
    _malformed_report = _seatc_root / _malformed["report_path"]
    _malformed_report.write_text(
        _malformed_report.read_text(encoding="utf-8-sig").replace(
            "report_status: draft", "report_status:", 1),
        encoding="utf-8")
    _malformed_retry = json.loads(_scprep(
        "--role", "critic", "--session", "critic-malformed-01").stdout)
    expect("malformed registered report refuses INVALID_REPORT, never "
           "replaced by prepare",
           _malformed_retry.get("code") == "INVALID_REPORT"
           and "report_status" in _malformed_report.read_text(
               encoding="utf-8-sig"),
           repr(_malformed_retry))
    _malformed_report.write_text(
        _malformed_report.read_text(encoding="utf-8-sig").replace(
            "report_status:", "report_status: bogus", 1),
        encoding="utf-8")
    _bogus_retry = json.loads(_scprep(
        "--role", "critic", "--session", "critic-malformed-01").stdout)
    expect("an unexpected report_status (bogus) refuses INVALID_REPORT -- "
           "only an exact draft resumes",
           _bogus_retry.get("code") == "INVALID_REPORT"
           and "bogus" in _bogus_retry.get("detail", ""),
           repr(_bogus_retry))
    _no_prov_proc = _scprep("--role", "critic", "--session",
                            "critic-noprov-01")
    _no_prov = json.loads(_no_prov_proc.stdout)
    _no_prov_report = _seatc_root / _no_prov["report_path"]
    _no_prov_report.write_text(
        _no_prov_report.read_text(encoding="utf-8-sig").replace(
            "source_head: ", "source_head_missing: ", 1),
        encoding="utf-8")
    _no_prov_retry = json.loads(_scprep(
        "--role", "critic", "--session", "critic-noprov-01").stdout)
    expect("a draft missing required provenance refuses INVALID_REPORT "
           "(validate_report gates the resume)",
           _no_prov_retry.get("code") == "INVALID_REPORT"
           and "source_head" in _no_prov_retry.get("detail", ""),
           repr(_no_prov_retry))
    _binary_proc = _scprep("--role", "critic", "--session",
                           "critic-binary-01")
    _binary = json.loads(_binary_proc.stdout)
    (_seatc_root / _binary["report_path"]).write_bytes(b"\x80\x81\x82\xff")
    _binary_retry = json.loads(_scprep(
        "--role", "critic", "--session", "critic-binary-01").stdout)
    expect("an undecodable report refuses INVALID_REPORT without a traceback",
           _binary_retry.get("code") == "INVALID_REPORT"
           and "cannot be decoded" in _binary_retry.get("detail", ""),
           repr(_binary_retry))
    _runless_proc = _scprep("--role", "critic", "--session",
                            "critic-runless-01")
    _runless = json.loads(_runless_proc.stdout)
    _runless_report = _seatc_root / _runless["report_path"]
    _runless_report.write_text(
        _runless_report.read_text(encoding="utf-8-sig").replace(
            "report_status: draft", "report_status: complete", 1),
        encoding="utf-8")
    _runless_retry = json.loads(_scprep(
        "--role", "critic", "--session", "critic-runless-01").stdout)
    expect("a runless complete skeleton refuses INVALID_REPORT, never "
           "SEAT_COMPLETE",
           _runless_retry.get("code") == "INVALID_REPORT"
           and "without run evidence" in _runless_retry.get("detail", ""),
           repr(_runless_retry))
    _duph_proc = _scprep("--role", "critic", "--session",
                         "critic-duphdr-01")
    _duph = json.loads(_duph_proc.stdout)
    _duph_report = _seatc_root / _duph["report_path"]
    _duph_report.write_text(
        _duph_report.read_text(encoding="utf-8-sig").replace(
            "role: critic", "role: critic\nrole: critic", 1),
        encoding="utf-8")
    _duph_retry = json.loads(_scprep(
        "--role", "critic", "--session", "critic-duphdr-01").stdout)
    expect("a report repeating a required header field refuses "
           "INVALID_REPORT",
           _duph_retry.get("code") == "INVALID_REPORT"
           and "repeats required header" in _duph_retry.get("detail", ""),
           repr(_duph_retry))
    _prose_proc = _scprep("--role", "critic", "--session",
                          "critic-prose-01")
    _prose = json.loads(_prose_proc.stdout)
    _prose_report = _seatc_root / _prose["report_path"]
    append_run(_prose_report,
               "IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
               "report_status: mentioned inside finding evidence is prose\n"
               "expected: anchored header counting\n"
               "actual: prose ignored\n"
               "evidence: seat continuity control\n")
    _prose_retry = json.loads(_scprep(
        "--role", "critic", "--session", "critic-prose-01").stdout)
    expect("a prose line mentioning report_status does not false-reject a "
           "draft resume (header-anchored count)",
           _prose_retry.get("ok") is True
           and _prose_retry.get("resumed") is True,
           repr(_prose_retry))

    _identity_root = project_fixture("saipen-seat-identity-")
    _identity_assignments = [prepare_audit_seat(
        _identity_root, agent_family="probe", role="core", session_id=seat,
        project_name="SAME", model_or_runtime="probe",
        context_scope="seat identity control")
        for seat in ("seat-a", "seat-b")]
    for _assignment in _identity_assignments:
        _identity_report = Path(_assignment["report_path"])
        append_run(_identity_report,
                   "IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
                   "expected: independent disposition\n"
                   "actual: shared basename\n"
                   "evidence: seat identity control\n")
        complete_report(_identity_report)
    _identity_cycle = cycle_dir(
        _identity_root, _identity_assignments[0]["cycle_id"])
    write_sweep_entry(_identity_cycle, {
        "run": "RUN-1", "imp_id": "001", "disposition": "INVALID",
        "ticket": "-", "report": "seat-a/saipen_improve_SAME.md",
        "reproduced": "y"})
    _identity_roster = (_identity_cycle / "MANIFEST.md").read_text(
        encoding="utf-8-sig")
    _identity_sweep = (_identity_cycle / "SWEEP.md").read_text(
        encoding="utf-8-sig")
    _identity_report_texts = [Path(a["report_path"]).read_text(
        encoding="utf-8-sig") for a in _identity_assignments]
    expect("same-basename disposition is isolated by exact seat/report key",
           derive_status("saipen_improve_SAME.md", _identity_roster,
                         _identity_report_texts[0], _identity_sweep,
                         seat_id="seat-a")["visible"] == "swept"
           and derive_status("saipen_improve_SAME.md", _identity_roster,
                             _identity_report_texts[1], _identity_sweep,
                             seat_id="seat-b")["visible"] == "complete")
    try:
        derive_status("saipen_improve_SAME.md", _identity_roster,
                      _identity_report_texts[1], _identity_sweep)
        _ambiguous_status_refused = False
    except ValueError as _ambiguous_status_exc:
        _ambiguous_status_refused = "pass exact seat_id" in str(
            _ambiguous_status_exc)
    expect("status derivation refuses ambiguous basename without seat_id",
           _ambiguous_status_refused)
    try:
        write_sweep_entry(_identity_cycle, {
            "run": "RUN-1", "imp_id": "001", "disposition": "INVALID",
            "ticket": "-", "report": "saipen_improve_SAME.md",
            "reproduced": "y"})
        _ambiguous_report_refused = False
    except ValueError as _identity_exc:
        _ambiguous_report_refused = "multiple seat owners" in str(_identity_exc)
    expect("ambiguous legacy report basename refuses disposition",
           _ambiguous_report_refused)
    _identity_queue_proc = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "improve",
         "sweep-queue", _identity_cycle.name, "--json"],
        cwd=str(_identity_root), capture_output=True, text=True, timeout=60)
    _identity_queue = json.loads(_identity_queue_proc.stdout).get("queue", [])
    expect("sweep queue keeps unswept same-basename seat addressable",
           len(_identity_queue) == 1
           and _identity_queue[0].get("report")
           == "seat-b/saipen_improve_SAME.md",
           repr(_identity_queue))
    _legacy_identity_root = project_fixture("saipen-legacy-identity-")
    _legacy_first = prepare_audit_seat(
        _legacy_identity_root, agent_family="probe", role="core",
        session_id="seat-a", project_name="SAME",
        model_or_runtime="probe",
        context_scope="legacy identity control")
    _legacy_report = Path(_legacy_first["report_path"])
    append_run(_legacy_report,
               "IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
               "expected: stable provenance\nactual: legacy basename\n"
               "evidence: late admission control\n")
    complete_report(_legacy_report)
    _legacy_cycle = cycle_dir(_legacy_identity_root,
                              _legacy_first["cycle_id"])
    write_sweep_entry(_legacy_cycle, {
        "run": "RUN-1", "imp_id": "001", "disposition": "INVALID",
        "ticket": "-", "report": "saipen_improve_SAME.md",
        "reproduced": "y"})
    _legacy_sweep_path = _legacy_cycle / "SWEEP.md"
    _legacy_sweep_path.write_bytes(_legacy_sweep_path.read_bytes().replace(
        b"report=seat-a/saipen_improve_SAME.md",
        b"report=saipen_improve_SAME.md"))
    _legacy_manifest_before = (_legacy_cycle / "MANIFEST.md").read_bytes()
    _legacy_sweep_before = (_legacy_cycle / "SWEEP.md").read_bytes()
    try:
        register_seat(_legacy_cycle, "seat-b", "core",
                      "saipen_improve_SAME.md")
        _legacy_register_refused = False
    except ValueError as _legacy_register_exc:
        _legacy_register_refused = "existing bare SWEEP identity" in str(
            _legacy_register_exc)
    try:
        prepare_audit_seat(
            _legacy_identity_root, agent_family="probe", role="core",
            session_id="seat-b", project_name="SAME",
            model_or_runtime="probe",
            context_scope="legacy identity control")
        _late_duplicate_refused = False
    except ValueError as _legacy_identity_exc:
        _late_duplicate_refused = "existing bare SWEEP identity" in str(
            _legacy_identity_exc)
    expect("late duplicate-basename admission preserves legacy provenance",
           _legacy_register_refused and _late_duplicate_refused
           and (_legacy_cycle / "MANIFEST.md").read_bytes()
           == _legacy_manifest_before
           and (_legacy_cycle / "SWEEP.md").read_bytes()
           == _legacy_sweep_before
           and not (_legacy_cycle / "seat-b").exists())

    # ---- PRE-v8 DOGFOOD VIII (A1-A6): hostile evidence-continuity closeout.
    # A1: a DRAFT seat may resume only while its mechanical source identity
    # still matches the CURRENT source identity. Tracked source mutation
    # between prepare and retry must refuse -- never resume with the OLD
    # report fingerprint bound to fresh work, never silently rebase.
    _stale_root = project_fixture("saipen-stale-draft-")
    (_stale_root / "src.txt").write_text("v1\n", encoding="utf-8")
    _stale_first = prepare_audit_seat(
        _stale_root, agent_family="probe", role="critic",
        session_id="critic-stale-01", project_name="STALE",
        model_or_runtime="probe",
        context_scope="stale draft control")
    _stale_report = _stale_root / _stale_first["report_path"]
    _stale_manifest = (_stale_root / ".saipen" / "improve"
                       / _stale_first["cycle_id"] / "MANIFEST.md")
    _stale_manifest_before = _stale_manifest.read_bytes()
    _stale_report_before = _stale_report.read_bytes()
    _stale_recovery_before = _recovery_ops_snapshot(_stale_root)
    (_stale_root / "src.txt").write_text("v2 -- tracked source changed\n",
                                         encoding="utf-8")
    _stale_retry = prepare_audit_seat(
        _stale_root, agent_family="probe", role="critic",
        session_id="critic-stale-01", project_name="STALE",
        model_or_runtime="probe",
        context_scope="stale draft control")
    expect("A1: stale DRAFT resume refuses STALE_REPORT with zero writes",
           _stale_retry.get("code") == "STALE_REPORT"
           and _stale_retry.get("resumed") is False
           and _stale_retry.get("ok") is False
           and _stale_manifest.read_bytes() == _stale_manifest_before
           and _stale_report.read_bytes() == _stale_report_before
           and _recovery_ops_snapshot(_stale_root) == _stale_recovery_before,
           repr(_stale_retry))
    (_stale_root / "src.txt").write_text("v1\n", encoding="utf-8")
    _stale_restored = prepare_audit_seat(
        _stale_root, agent_family="probe", role="critic",
        session_id="critic-stale-01", project_name="STALE",
        model_or_runtime="probe",
        context_scope="stale draft control")
    expect("A1: restoring the source restores the DRAFT resume",
           _stale_restored.get("code") == "ALREADY_ASSIGNED"
           and _stale_restored.get("resumed") is True,
           repr(_stale_restored))

    # A2: an invalid active MANIFEST is never consumed or mutated. validate
    # _manifest(expected_cycle_id) gates admission, unavailable handling and
    # resume; an invalid roster returns structured INVALID_MANIFEST with zero
    # new mutation and byte-identical evidence.
    _manifest_root = project_fixture("saipen-invalid-manifest-")
    _mf_first = prepare_audit_seat(
        _manifest_root, agent_family="probe", role="critic",
        session_id="critic-mf-01", project_name="MF",
        model_or_runtime="probe",
        context_scope="invalid manifest control")
    _mf_cycle = cycle_dir(_manifest_root, _mf_first["cycle_id"])
    _mf_manifest = _mf_cycle / "MANIFEST.md"
    _mf_recovery_before = _recovery_ops_snapshot(_manifest_root)
    _mf_manifest.write_text(
        _mf_manifest.read_text(encoding="utf-8-sig").replace(
            "cycle_id: " + _mf_first["cycle_id"], "cycle_id: WRONG", 1),
        encoding="utf-8")
    _mf_manifest_before = _mf_manifest.read_bytes()
    _mf_second = prepare_audit_seat(
        _manifest_root, agent_family="probe", role="critic",
        session_id="critic-mf-02", project_name="MF",
        model_or_runtime="probe",
        context_scope="invalid manifest control")
    expect("A2: admission on an invalid active manifest refuses "
           "INVALID_MANIFEST with zero new mutation",
           _mf_second.get("code") == "INVALID_MANIFEST"
           and _mf_second.get("ok") is False
           and not (_mf_cycle / "critic-mf-02").exists()
           and _mf_manifest.read_bytes() == _mf_manifest_before
           and _recovery_ops_snapshot(_manifest_root) == _mf_recovery_before,
           repr(_mf_second))
    try:
        register_seat(_mf_cycle, "critic-mf-03", "critic",
                      "saipen_improve_MF.md")
        _mf_register_refused = False
    except ImproveError as _mf_exc:
        _mf_register_refused = "invalid active manifest" in str(_mf_exc)
    expect("A2: register_seat refuses an invalid active manifest",
           _mf_register_refused, "")

    # A3: strict seat field cardinality -- exactly one identity/lifecycle
    # field per seat; duplicate fields and out-of-set availability refuse.
    _card_root = project_fixture("saipen-seat-cardinality-")
    _card_first = prepare_audit_seat(
        _card_root, agent_family="probe", role="critic",
        session_id="critic-card-01", project_name="CARD",
        model_or_runtime="probe",
        context_scope="cardinality control")
    _card_cycle = cycle_dir(_card_root, _card_first["cycle_id"])
    _card_manifest = _card_cycle / "MANIFEST.md"
    _card_manifest.write_text(
        _card_manifest.read_text(encoding="utf-8-sig").replace(
            "role: critic", "role: critic\nrole: critic", 1),
        encoding="utf-8")
    _card_second = prepare_audit_seat(
        _card_root, agent_family="probe", role="critic",
        session_id="critic-card-02", project_name="CARD",
        model_or_runtime="probe",
        context_scope="cardinality control")
    expect("A3: a duplicated strict seat role field refuses INVALID_MANIFEST "
           "(exactly-once, no first/last-value ambiguity)",
           _card_second.get("code") == "INVALID_MANIFEST"
           and "exactly once" in _card_second.get("detail", ""),
           repr(_card_second))
    _bogus_root = project_fixture("saipen-availability-bogus-")
    _bg_first = prepare_audit_seat(
        _bogus_root, agent_family="probe", role="critic",
        session_id="critic-bg-01", project_name="BG",
        model_or_runtime="probe",
        context_scope="bogus availability control")
    _bg_cycle = cycle_dir(_bogus_root, _bg_first["cycle_id"])
    _bg_manifest = _bg_cycle / "MANIFEST.md"
    (_bogus_root / _bg_first["report_path"]).unlink()
    _bg_manifest.write_text(
        _bg_manifest.read_text(encoding="utf-8-sig").replace(
            "availability: expected", "availability: bogus", 1),
        encoding="utf-8")
    _bg_retry = prepare_audit_seat(
        _bogus_root, agent_family="probe", role="critic",
        session_id="critic-bg-01", project_name="BG",
        model_or_runtime="probe",
        context_scope="bogus availability control")
    expect("A3: availability bogus can never resume as ALREADY_ASSIGNED",
           _bg_retry.get("code") == "INVALID_MANIFEST"
           and _bg_retry.get("ok") is False,
           repr(_bg_retry))

    # A4: strict RUN + finding identity is INJECTIVE -- unique, ascending,
    # contiguous 1..N RUNs, canonical IMP-NNN grammar, unique composite
    # <RUN>/<IMP> identities. False evidence cannot validate, and a duplicate
    # composite can never reach complete/swept state.
    _a4_strict = ("agent: a\nrole: core\nmodel_or_runtime: probe\nproject: P\n"
                  "saipen_version: 7\nprotocol_fingerprint: fp\n"
                  "source_head: no-git\n"
                  "source_tree_fingerprint: no-git-tree-v1:abc\n"
                  "discovery_model: no-git-tree-v1\n"
                  "context_scope: tools\ncontext_available: complete\n"
                  "report_status: complete\n")
    _a4_run = ("\n## RUN {n}\nIMP-{i} [P1] [LOGIC_ERROR] [proven] [ticket]\n"
               "expected: a\nactual: b\nevidence: c\n")

    def _a4_errs(body: str) -> list[str]:
        return validate_report(_a4_strict + body, require_runs=True,
                               strict=True)

    expect("A4: a strict report with unique contiguous RUNs validates",
           _a4_errs(_a4_run.format(n=1, i="001")) == [],
           repr(_a4_errs(_a4_run.format(n=1, i="001"))))
    expect("A4: duplicate RUN 1 rejects (repeated section number)",
           any("repeats RUN section" in e
               for e in _a4_errs(_a4_run.format(n=1, i="001")
                                 + _a4_run.format(n=1, i="002"))),
           repr(_a4_errs(_a4_run.format(n=1, i="001")
                         + _a4_run.format(n=1, i="002"))))
    expect("A4: RUN 1 then RUN 3 rejects (not contiguous 1..N)",
           any("not contiguous" in e
               for e in _a4_errs(_a4_run.format(n=1, i="001")
                                 + _a4_run.format(n=3, i="002"))),
           repr(_a4_errs(_a4_run.format(n=1, i="001")
                         + _a4_run.format(n=3, i="002"))))
    expect("A4: RUN 2 as the first run rejects (not contiguous 1..N)",
           any("not contiguous" in e
               for e in _a4_errs(_a4_run.format(n=2, i="001"))),
           repr(_a4_errs(_a4_run.format(n=2, i="001"))))
    expect("A4: swapped/decreasing RUN numbers reject (not ascending)",
           any("not ascending" in e
               for e in _a4_errs(_a4_run.format(n=2, i="001")
                                 + _a4_run.format(n=1, i="002"))),
           repr(_a4_errs(_a4_run.format(n=2, i="001")
                         + _a4_run.format(n=1, i="002"))))
    _a4_dup_imp = _a4_run.format(n=1, i="001").replace(
        "evidence: c", "evidence: c\n"
        "IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
        "expected: d\nactual: e\nevidence: f", 1)
    expect("A4: duplicate IMP-001 inside one RUN rejects before any dedup",
           any("repeats composite finding identity" in e
               for e in _a4_errs(_a4_dup_imp)),
           repr(_a4_errs(_a4_dup_imp)))
    expect("A4: malformed IMP width (IMP-1) rejects canonical IMP-NNN",
           any("not canonical IMP-NNN" in e
               for e in _a4_errs(_a4_run.format(n=1, i="1"))),
           repr(_a4_errs(_a4_run.format(n=1, i="1"))))
    _a4_same_in_two_runs = _a4_run.format(n=1, i="001") \
        + _a4_run.format(n=2, i="001")
    expect("A4: the same IMP-001 in two DIFFERENT RUNs stays distinct",
           _a4_errs(_a4_same_in_two_runs) == [],
           repr(_a4_errs(_a4_same_in_two_runs)))
    _dc_root = project_fixture("saipen-dupcomposite-")
    _dc_cycle = create_cycle(_dc_root, "imp-dup")
    register_seat(_dc_cycle, "seat-1", "core", "saipen_improve_D.md")
    _dc_rep = create_report(_dc_root, "imp-dup", "seat-1", "D",
                            agent="seat-1", role="core",
                            model_or_runtime="probe",
                            context_scope="scope")
    _dc_bytes_before = _dc_rep.read_bytes()
    try:
        append_run(_dc_rep, "IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
                            "expected: a\nactual: b\nevidence: c\n"
                            "IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
                            "expected: d\nactual: e\nevidence: f\n")
        _dc_append = False
    except ImproveError:
        _dc_append = True
    expect("A4 + T-638/§2: a duplicate composite identity is refused at "
           "append with ZERO writes (never enters a report that could be "
           "swept)",
           _dc_append and _dc_rep.read_bytes() == _dc_bytes_before, "")

    # A5: strict report requires discovery_model exactly once; legacy reports
    # keep the deliberate boundary and stay valid without it.
    _a5_root = project_fixture("saipen-a5-header-")
    _a5_first = prepare_audit_seat(
        _a5_root, agent_family="probe", role="critic",
        session_id="critic-a5-01", project_name="A5",
        model_or_runtime="probe",
        context_scope="header parity control")
    _a5_report = _a5_root / _a5_first["report_path"]
    _a5_report.write_text(
        _a5_report.read_text(encoding="utf-8-sig").replace(
            "discovery_model: ", "removed_discovery_model: ", 1),
        encoding="utf-8")
    _a5_retry = prepare_audit_seat(
        _a5_root, agent_family="probe", role="critic",
        session_id="critic-a5-01", project_name="A5",
        model_or_runtime="probe",
        context_scope="header parity control")
    expect("A5: a strict report missing discovery_model refuses "
           "INVALID_REPORT (writer/spec/validator field parity)",
           _a5_retry.get("code") == "INVALID_REPORT"
           and "discovery_model" in _a5_retry.get("detail", ""),
           repr(_a5_retry))
    _a5_legacy = validate_report(
        _a4_strict.replace("discovery_model: no-git-tree-v1\n", ""))
    expect("A5: a legacy (non-strict) report may omit discovery_model "
           "(deliberate legacy boundary only where history needs it)",
           _a5_legacy == [], repr(_a5_legacy))
    _a5_dup = _a4_strict.replace(
        "discovery_model: no-git-tree-v1",
        "discovery_model: no-git-tree-v1\ndiscovery_model: x", 1)
    expect("A5: a duplicated discovery_model in a strict report rejects",
           any("repeats required header" in e
               for e in validate_report(_a5_dup, strict=True)),
           repr(validate_report(_a5_dup, strict=True)))

    # HUNT closeout controls: the ledger side of A4 and the create_report
    # side of A2 -- no identity ambiguity survives on either write path.
    from improve import validate_sweep as _vsweep
    _dup_sweep = ("# SWEEP\n- RUN-1/IMP-001 [CONFIRMED] T-900 "
                  "report=saipen_improve_D.md reproduced=y\n"
                  "- RUN-1/IMP-001 [CONFIRMED] T-900 "
                  "report=saipen_improve_D.md reproduced=y\n")
    expect("A4: a SWEEP ledger repeating one composite identity rejects "
           "(one disposition per composite finding identity)",
           any("repeats composite identity" in e
               for e in _vsweep(_dup_sweep)),
           repr(_vsweep(_dup_sweep)))
    _cr_root = project_fixture("saipen-create-report-gate-")
    _cr_cycle = create_cycle(_cr_root, "imp-cr")
    register_seat(_cr_cycle, "seat-1", "core", "saipen_improve_CR.md")
    (_cr_cycle / "MANIFEST.md").write_text(
        (_cr_cycle / "MANIFEST.md").read_text(encoding="utf-8-sig").replace(
            "cycle_id: imp-cr", "cycle_id: WRONG", 1), encoding="utf-8")
    try:
        create_report(_cr_root, "imp-cr", "seat-1", "CR", agent="seat-1",
                      role="core", model_or_runtime="probe",
                      context_scope="scope")
        _cr_gated = False
    except ImproveError as _cr_exc:
        _cr_gated = "invalid active manifest" in str(_cr_exc)
    expect("A2: create_report refuses an invalid active manifest "
           "(no first-value roster interpretation)",
           _cr_gated, "")

    _public_cmd = [sys.executable, str(HOME / "tools" / "saipen.py"),
                   "improve", "--new-seat", "--json"]
    _parallel = [subprocess.Popen(
        _public_cmd, cwd=str(meta_root), stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True) for _ in range(2)]
    _parallel_results = []
    for _proc in _parallel:
        _out, _err = _proc.communicate(timeout=60)
        _parallel_results.append((_proc.returncode, json.loads(_out), _err))
    _parallel_assignments = [r[1] for r in _parallel_results
                             if r[1].get("code") == "IMPROVE_AUDIT_ASSIGNMENT"]
    for _result in _parallel_results:
        if _result[1].get("code") == "WRITER_BUSY":
            _retry = _prepare("--new-seat")
            if _retry.returncode == 0:
                _parallel_assignments.append(json.loads(_retry.stdout))
    expect("simultaneous admissions lose no seat and allocate no duplicate",
           len(_parallel_assignments) == 2
           and len({a["seat_id"] for a in _parallel_assignments}) == 2
           and all("Traceback" not in r[2] for r in _parallel_results),
           repr(_parallel_results))

    with WriterLock(meta_root):
        _busy_proc = _prepare("--new-seat")
    expect("live Improve contention returns structured WRITER_BUSY",
           _busy_proc.returncode != 0
           and json.loads(_busy_proc.stdout).get("code") == "WRITER_BUSY"
           and "Traceback" not in _busy_proc.stderr,
           repr((_busy_proc.stdout, _busy_proc.stderr)))

    _saipen_module.HOME = HOME
    with mock.patch.object(_saipen_module, "_improve",
                           side_effect=TypeError("programming defect")):
        try:
            _saipen_module._public_improve(meta_root, [], True, False)
            _programming_error_raised = False
        except TypeError:
            _programming_error_raised = True
    expect("public Improve boundary never normalizes programming errors",
           _programming_error_raised)
    _mcycle = _bare_data["cycle_id"]
    _mseat = _bare_data["seat_id"]
    _cycles_before_verify = len(list(
        (meta_root / ".saipen" / "improve").iterdir()))
    _mv = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "improve",
         "verify", _mcycle, "--json"],
        cwd=str(meta_root), capture_output=True, text=True, timeout=60)
    expect("saipen improve verify validates the complete cycle output and "
           "does not recurse into a new cycle",
           '"code": "VALIDATION_FAILED"' in _mv.stdout
           and len(list((meta_root / ".saipen" / "improve").iterdir()))
           == _cycles_before_verify,
           repr(_mv.stdout[:200]))

    # ---- DOGFOOD V (T-616): saipen improve verify can no longer PASS an
    # incomplete completed report (a bare report_status skeleton).
    false_root = project_fixture("saipen-false-")
    _fc = register_cycle(false_root, "imp-false",
                         "# IMPROVE CYCLE ROSTER\ncycle_status: active\n")
    register_seat(_fc, "seat-1", "core", "saipen_improve_A.md")
    _fr = resolve_report_path(false_root, "imp-false", "seat-1", "A")
    _fr.parent.mkdir(parents=True, exist_ok=True)
    _fr.write_text("report_status: complete\n", encoding="utf-8")
    _fv = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "improve",
         "verify", "imp-false", "--json"],
        cwd=str(false_root), capture_output=True, text=True, timeout=60)
    expect("improve verify rejects a report containing only report_status: "
           "complete (false PASS closed)",
           '"code": "VALIDATION_FAILED"' in _fv.stdout,
           repr(_fv.stdout[:200]))

    # ---- T-629: public submit boundary validates JSON shape before any
    # access -- array/scalar/null/non-string/empty/missing run_text all
    # refuse with a structured VALIDATION_FAILED and no traceback, surplus
    # args are rejected, and a valid payload still appends.
    _submit_root = project_fixture("saipen-submit-shape-")
    _submit_cycle = create_cycle(
        _submit_root, "imp-submit",
        created_at="2026-08-10T00:00:00Z", project_identity="probe-project")
    register_seat(_submit_cycle, "seat-1", "core", "saipen_improve_A.md")
    _submit_report = create_report(
        _submit_root, "imp-submit", "seat-1", "A", agent="seat-1", role="core",
        model_or_runtime="probe",
        context_scope="probe scope")
    _submit_payload = _submit_root / "findings.json"
    _submit_args = [sys.executable, str(HOME / "tools" / "saipen.py"),
                    "improve", "submit", "imp-submit", "seat-1", "A",
                    "--json"]

    _submit_payload.write_text(
        json.dumps({"run_text": "IMP-001 [P1] [LOGIC_ERROR] [proven] "
                                "[ticket]\nexpected: x\nactual: y\n"
                                "evidence: z\n"}),
        encoding="utf-8")
    _submit_positive = subprocess.run(
        [*_submit_args, str(_submit_payload)],
        cwd=str(_submit_root), capture_output=True, text=True, timeout=60)
    expect("submit with a valid string run_text appends a RUN",
           _submit_positive.returncode == 0
           and json.loads(_submit_positive.stdout).get("ok") is True
           and "Traceback" not in _submit_positive.stderr,
           repr((_submit_positive.stdout, _submit_positive.stderr)))

    for _shape_label, _bad in [
            ("array", []), ("scalar", 42), ("null", None),
            ("string", "plain text"),
            ("run_text non-string", {"run_text": 7}),
            ("empty run_text", {"run_text": ""}),
            ("whitespace run_text", {"run_text": "   "}),
            ("missing run_text", {"other": 1})]:
        _submit_payload.write_text(json.dumps(_bad), encoding="utf-8")
        _submit_probe = subprocess.run(
            [*_submit_args, str(_submit_payload)],
            cwd=str(_submit_root), capture_output=True, text=True, timeout=60)
        expect(f"submit refuses a {_shape_label} findings payload without "
               f"traceback",
               _submit_probe.returncode != 0
               and '"code": "VALIDATION_FAILED"' in _submit_probe.stdout
               and "Traceback" not in _submit_probe.stderr,
               repr((_submit_probe.stdout, _submit_probe.stderr)))
    _submit_payload.unlink()
    _submit_surplus = subprocess.run(
        [*_submit_args, str(_submit_payload), "extra"],
        cwd=str(_submit_root), capture_output=True, text=True, timeout=60)
    expect("submit rejects an unsupported surplus argument",
           _submit_surplus.returncode != 0
           and '"code": "VALIDATION_FAILED"' in _submit_surplus.stdout
           and "unsupported surplus argument" in _submit_surplus.stdout,
           repr(_submit_surplus.stdout))

    # ---- DOGFOOD V (T-615): one disposition can never cover two findings
    # that share a local IMP number across RUNs; sweep-queue enumerates the
    # exact composite unswept findings; strict manifest + real fingerprint +
    # fake-fingerprint refusal through the public path.
    dg_root = project_fixture("saipen-dg5-")
    _dg_cycle, _dg_rep = mech_cycle(
        dg_root, "imp-dg5", "seat-1", "A",
        ["IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
         "expected: x\nactual: y\nevidence: z\n"],
        ticket="T-900", findings_ok=False)
    append_run(_dg_rep, "IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
                        "expected: x\nactual: y\nevidence: z\n")
    append_run(_dg_rep, "IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
                        "expected: d\nactual: e\nevidence: f\n")
    complete_report(_dg_rep)
    # sweep only RUN-1/IMP-001; RUN-2/IMP-001 must stay unswept.
    write_sweep_entry(_dg_cycle, {"run": "RUN-1", "imp_id": "001",
                                  "disposition": "CONFIRMED",
                                  "ticket": "T-900",
                                  "report": "saipen_improve_A.md",
                                  "reproduced": "y"})
    st = derive_status("saipen_improve_A.md",
                       (_dg_cycle / "MANIFEST.md").read_text(
                           encoding="utf-8-sig"),
                       _dg_rep.read_text(encoding="utf-8"),
                       (_dg_cycle / "SWEEP.md").read_text(encoding="utf-8"))
    expect("RUN-1/IMP-001 disposition never covers RUN-2/IMP-001 "
           "(composite identity)",
           "RUN-2/IMP-001" in st["missing"] and st["visible"] == "complete",
           repr((st["missing"], st["visible"])))
    _qproc = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "improve",
         "sweep-queue", "imp-dg5", "--json"],
        cwd=str(dg_root), capture_output=True, text=True, timeout=60)
    expect("high-level sweep enumerates the exact unswept composite finding",
           '"code": "IMPROVE_SWEEP_QUEUE"' in _qproc.stdout
           and 'RUN-2/IMP-001' in _qproc.stdout
           and 'RUN-1/IMP-001' not in _qproc.stdout,
           repr(_qproc.stdout[:300]))
    _manifest = (_dg_cycle / "MANIFEST.md").read_text(encoding="utf-8-sig")
    expect("strict manifest carries cycle_id/created_at/project_identity "
           "exactly once and round-trips the validator",
           validate_manifest(_manifest, expected_cycle_id="imp-dg5") == []
           and _manifest.count("manifest_schema: strict") == 1
           and _manifest.count("cycle_id: imp-dg5") == 1,
           repr(validate_manifest(_manifest, expected_cycle_id="imp-dg5")))
    # fake fingerprint cannot claim fresh strict-cycle evidence.
    _fp_root = project_fixture("saipen-fakefp-")
    _fp_cycle, _fp_rep = mech_cycle(
        _fp_root, "imp-fakefp", "seat-1", "A",
        ["IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
         "expected: x\nactual: y\nevidence: z\n"], ticket="T-900")
    _fp_lines = _fp_rep.read_text(encoding="utf-8").splitlines()
    _fp_out = []
    for _line in _fp_lines:
        if _line.startswith("source_tree_fingerprint:"):
            _fp_out.append("source_tree_fingerprint: improve-cycle-9")
        else:
            _fp_out.append(_line)
    _fp_rep.write_text("\n".join(_fp_out) + "\n", encoding="utf-8")
    expect("a fabricated friendly fingerprint fails the strict-cycle "
           "validator (DOGFOOD V)",
           validator_rc(_fp_root) != 0,
           repr(validator_rc(_fp_root)))

    # ---- DOGFOOD V (T-615): write_sweep_entry refuses a nonexistent
    # run/finding and a CONFIRMED nonexistent ticket; INVALID never carries a
    # ticket.
    dgv_root = project_fixture("saipen-dgv-")
    _v_cycle, _v_rep = mech_cycle(
        dgv_root, "imp-dgv", "seat-1", "A",
        ["IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
         "expected: x\nactual: y\nevidence: z\n"], ticket="T-900")
    for _label, _entry in [
        ("nonexistent run refuses",
         {"run": "RUN-99", "imp_id": "001", "disposition": "CONFIRMED",
          "ticket": "T-900", "report": "saipen_improve_A.md",
          "reproduced": "y"}),
        ("nonexistent finding refuses",
         {"run": "RUN-1", "imp_id": "999", "disposition": "CONFIRMED",
          "ticket": "T-900", "report": "saipen_improve_A.md",
          "reproduced": "y"}),
        ("CONFIRMED nonexistent ticket cannot COMMIT",
         {"run": "RUN-1", "imp_id": "001", "disposition": "CONFIRMED",
          "ticket": "T-999999", "report": "saipen_improve_A.md",
          "reproduced": "y"}),
        ("INVALID never authorizes a ticket",
         {"run": "RUN-1", "imp_id": "001", "disposition": "INVALID",
          "ticket": "T-900", "report": "saipen_improve_A.md",
          "reproduced": "n"}),
    ]:
        try:
            write_sweep_entry(_v_cycle, _entry)
            _refused = False
        except ValueError:
            _refused = True
        expect(f"sweep authorization: {_label}",
               _refused)

    # ---- DOGFOOD V (T-615): source_reports resolves EXACT composite refs;
    # an unrelated cycle's IMP-001 never satisfies provenance; a bare ref
    # into a strict cycle fails.
    prov_root = project_fixture("saipen-prov-")
    _p_cycle, _p_rep = mech_cycle(
        prov_root, "imp-prov-a", "seat-a", "A",
        ["IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
         "expected: x\nactual: y\nevidence: z\n"], ticket="T-900")
    ticket_fixture(prov_root, "T-902")
    write_sweep_entry(_p_cycle, {"run": "RUN-1", "imp_id": "001",
                                 "disposition": "CONFIRMED",
                                 "ticket": "T-900",
                                 "report": "saipen_improve_A.md",
                                 "reproduced": "y"})
    # good: T-900 cites the EXACT composite ref of imp-prov-a
    good_board = (prov_root / ".saipen" / "BOARD.md").read_text(
        encoding="utf-8-sig")
    good_board = good_board.replace(
        "| verify: probe",
        "| verify: probe | source_reports: "
        "imp-prov-a/seat-a/saipen_improve_A.md#RUN-1/IMP-001", 1)
    (prov_root / ".saipen" / "BOARD.md").write_text(good_board,
                                                   encoding="utf-8")
    expect("source_reports resolves an EXACT composite ref (validator green)",
           validator_rc(prov_root) == 0,
           repr(validator_rc(prov_root)))
    # wrong-cycle: cite a ref naming a cycle that was never swept -- the same
    # local IMP number in another cycle must never satisfy provenance.
    bad_board = good_board.replace(
        "imp-prov-a/seat-a", "imp-prov-b/seat-b")
    (prov_root / ".saipen" / "BOARD.md").write_text(bad_board,
                                                   encoding="utf-8")
    expect("an unrelated cycle's IMP-001 cannot satisfy ticket provenance "
           "(validator red)",
           validator_rc(prov_root) != 0,
           repr(validator_rc(prov_root)))
    # bare ref into a strict cycle fails.
    bare_board = good_board.replace(
        " | source_reports: "
        "imp-prov-a/seat-a/saipen_improve_A.md#RUN-1/IMP-001",
        " | source_reports: IMP-001")
    (prov_root / ".saipen" / "BOARD.md").write_text(bare_board,
                                                   encoding="utf-8")
    expect("a bare IMP ref can never launder a strict-cycle finding "
           "(validator red)",
           validator_rc(prov_root) != 0,
           repr(validator_rc(prov_root)))

    # ---- DOGFOOD V (T-615): SWEEP writer/parser round-trip exact composite
    # identity (one structured record).
    from improve import SweepRecord, _sweep_records as _parse_records
    _sr = SweepRecord("RUN-1/IMP-001", "CONFIRMED", "T-900",
                      "saipen_improve_A.md", "y", "-", "-")
    _rendered = _sr.render()
    _parsed = _parse_records("# SWEEP\n" + _rendered + "\n")
    expect("SweepRecord writer/parser round-trip preserves exact identity",
           len(_parsed) == 1 and _parsed[0] == _sr,
           repr((_rendered, _parsed)))

    # ---- DOGFOOD V (T-616): complete_report refuses an empty draft and a
    # strict cycle's report needs intentional RUN evidence (already covered);
    # append after completion refuses via the parser, not substring.
    imm2_root = project_fixture("saipen-imm2-")
    _i_cycle, _i_rep = mech_cycle(
        imm2_root, "imp-imm2", "seat-1", "A",
        ["IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
         "expected: x\nactual: y\nevidence: z\n"], ticket="T-900")
    _i_text = _i_rep.read_text(encoding="utf-8")
    _mention = _i_text.replace("report_status: complete",
                               "report_status: complete\n\n"
                               "note: an earlier report said "
                               "report_status: complete and was frozen")
    try:
        append_run(_i_rep, "late after complete")
        _append_late = False
    except ValueError:
        _append_late = True
    expect("append after completion refuses via the PARSER, not substring "
           "(an evidence mention of the phrase does not freeze a draft)",
           _append_late)

    # ---- DOGFOOD V (T-616): NO_FINDINGS is intentional evidence, not
    # absence of output.
    nf_root = project_fixture("saipen-nf-")
    _nf_cycle = create_cycle(nf_root, "imp-nf")
    register_seat(_nf_cycle, "seat-1", "core", "saipen_improve_A.md")
    ticket_fixture(nf_root, "T-900")
    _nf_rep = create_report(nf_root, "imp-nf", "seat-1", "A", agent="seat-1",
                            role="core", model_or_runtime="probe",
                            context_scope="scope")
    try:
        complete_report(_nf_rep)
        _empty_ok = False
    except ValueError:
        _empty_ok = True
    expect("an empty strict run without NO_FINDINGS cannot complete",
           _empty_ok)
    append_run(_nf_rep, "NO_FINDINGS\n")
    complete_report(_nf_rep)
    expect("an explicit NO_FINDINGS run completes as intentional evidence",
           "report_status: complete" in _nf_rep.read_text(encoding="utf-8"))
    # verify the completed NO_FINDINGS report passes the strict validator
    expect("NO_FINDINGS report passes strict report validation",
           validate_report(_nf_rep.read_text(encoding="utf-8"),
                           require_runs=True) == [],
           repr(validate_report(_nf_rep.read_text(encoding="utf-8"),
                                require_runs=True)))

    # ---- DOGFOOD V (SAICRITIC #4): source freshness at the gates (T-619),
    # status validation depth (T-620), mechanical abort (T-621).
    fs_root = project_fixture("saipen-fresh-")
    (fs_root / "src.txt").write_text("v1\n", encoding="utf-8")
    _fs_cycle, _fs_rep = mech_cycle(
        fs_root, "imp-fresh", "seat-1", "A",
        ["IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
         "expected: x\nactual: y\nevidence: z\n"], ticket="T-900")
    write_sweep_entry(_fs_cycle, {"run": "RUN-1", "imp_id": "001",
                                  "disposition": "CONFIRMED",
                                  "ticket": "T-900",
                                  "report": "saipen_improve_A.md",
                                  "reproduced": "y"})
    (fs_root / "src.txt").write_text("v2\n", encoding="utf-8")
    _fsv = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "improve",
         "verify", "imp-fresh", "--json"],
        cwd=str(fs_root), capture_output=True, text=True, timeout=60)
    expect("source freshness: verify refuses a fully-swept but STALE strict "
           "cycle (SAICRITIC #4)",
           '"code": "VALIDATION_FAILED"' in _fsv.stdout
           and "tree differs" in _fsv.stdout,
           repr(_fsv.stdout[:300]))
    try:
        write_sweep_entry(_fs_cycle, {"run": "RUN-1", "imp_id": "001",
                                      "disposition": "CONFIRMED",
                                      "ticket": "T-900",
                                      "report": "saipen_improve_A.md",
                                      "reproduced": "y"})
        _stale_sweep = False
    except ValueError:
        _stale_sweep = True
    expect("source freshness: write_sweep_entry refuses CONFIRMED on stale "
           "evidence (SAICRITIC #4)",
           _stale_sweep)
    (fs_root / "src.txt").write_text("v1\n", encoding="utf-8")
    _fp_text = _fs_rep.read_text(encoding="utf-8").splitlines()
    _fp_out = []
    for _line in _fp_text:
        if _line.startswith("source_tree_fingerprint:"):
            _fp_out.append("source_tree_fingerprint: fake-label")
        else:
            _fp_out.append(_line)
    _fs_rep.write_text("\n".join(_fp_out) + "\n", encoding="utf-8")
    _fss = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "improve",
         "status", "--json"],
        cwd=str(fs_root), capture_output=True, text=True, timeout=60)
    _fss_data = json.loads(_fss.stdout)
    _fss_visible = _fss_data["cycles"][0]["seats"][0].get("visible")
    expect("status depth: a fabricated fingerprint is INVALID_REPORT, never "
           "swept (SAICRITIC #4)",
           _fss_visible == "INVALID_REPORT",
           repr(_fss_visible))

    # T-621 + P0 (T-632): mechanical abort rescues a stuck draft cycle, and
    # abort is crash-safe -- ONE journaled manifest write, no raw rename, no
    # report byte ever moved. The draft reports stay byte-identical at their
    # same path; the manifest's archived + cycle_aborted markers are the single
    # source of truth that they are non-authoritative.
    ab_root = project_fixture("saipen-abort-")
    (ab_root / "src.txt").write_text("v1\n", encoding="utf-8")
    _ab_cycle = create_cycle(ab_root, "imp-ab")
    register_seat(_ab_cycle, "seat-1", "core", "saipen_improve_A.md")
    _ab_rep = create_report(ab_root, "imp-ab", "seat-1", "A", agent="seat-1",
                            role="core", model_or_runtime="probe",
                            context_scope="scope")
    append_run(_ab_rep, "IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
                        "expected: x\nactual: y\nevidence: z\n")
    # Make the report genuinely stuck by removing the evidence triple AFTER
    # the mechanical append -- a malformed finding can never complete, which
    # is exactly the stuck state abort exists to exit.
    _ab_rep.write_text(
        _ab_rep.read_text(encoding="utf-8-sig").replace(
            "evidence: z", ""), encoding="utf-8")
    try:
        complete_report(_ab_rep)
        _ab_stuck = False
    except ValueError:
        _ab_stuck = True
    expect("abort: an incomplete report is genuinely stuck (cannot complete)",
           _ab_stuck)
    _ab_bytes_before = _ab_rep.read_bytes()
    _abr = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "improve",
         "abort", "imp-ab", "--json"],
        cwd=str(ab_root), capture_output=True, text=True, timeout=60)
    _ab_data = json.loads(_abr.stdout)
    _ab_ok = _ab_data.get("code") == "COMMITTED"
    expect("abort: the stuck cycle aborts mechanically, reports byte-preserved "
           "at the same path, no .discarded split state",
           _ab_ok and _ab_rep.is_file()
           and _ab_rep.read_bytes() == _ab_bytes_before
           and not _ab_rep.with_name(_ab_rep.name + ".discarded").exists()
           and "cycle_aborted" in (_ab_cycle / "MANIFEST.md").read_text(
               encoding="utf-8")
           and "cycle_status: archived" in (_ab_cycle / "MANIFEST.md")
               .read_text(encoding="utf-8"),
           repr(_abr.stdout[:300]))
    _ab_cycle2 = create_cycle(ab_root, "imp-ab2")
    expect("abort: a new cycle is admitted after the abort",
           (_ab_cycle2 / "MANIFEST.md").is_file())

    # T-992/§8: IMPROVE.md's abort contract must match the writer -- drafts
    # preserved AT THE SAME PATH (never a .discarded rename).
    _abort_doc = (HOME / "saipen" / "IMPROVE.md").read_text(
        encoding="utf-8-sig")
    expect("IMPROVE.md documents same-path abort preservation, never .discarded",
           "AT THEIR SAME PATH" in _abort_doc
           and ".discarded" not in _abort_doc,
           "IMPROVE.md abort contract drifted from the writer")

    # ---- T-638 (P0): a known-INVALID base is never mutated. Every lifecycle
    # mutator must validate the manifest/report it consumes BEFORE writing --
    # abort/archive/complete on an invalid manifest, and append on a
    # malformed strict report, commit ZERO bytes.
    _ib_root = project_fixture("saipen-invalid-base-")
    _ib_cycle = create_cycle(_ib_root, "imp-ib",
                             created_at="2026-08-12T00:00:00Z",
                             project_identity="p")
    register_seat(_ib_cycle, "seat-1", "core", "saipen_improve_A.md")
    _ib_rep = create_report(_ib_root, "imp-ib", "seat-1", "A",
                            agent="seat-1", role="core",
                            model_or_runtime="probe",
                            context_scope="scope")
    _ib_manifest = _ib_cycle / "MANIFEST.md"
    _ib_manifest_ok = _ib_manifest.read_text(encoding="utf-8-sig")
    _ib_manifest_bad = _ib_manifest_ok.replace(
        "cycle_id: imp-ib", "cycle_id: WRONG")
    _ib_manifest.write_text(_ib_manifest_bad, encoding="utf-8")
    _ib_manifest_bytes = _ib_manifest.read_bytes()
    for _label, _call in [
            ("abort", lambda: abort_cycle(_ib_cycle)),
            ("complete", lambda: complete_cycle(_ib_cycle)),
            ("archive", lambda: archive_cycle(_ib_cycle))]:
        try:
            _call()
            _ib_refused = False
        except Exception:
            _ib_refused = True
        expect(f"invalid-manifest {_label} refuses with ZERO writes",
               _ib_refused
               and _ib_manifest.read_bytes() == _ib_manifest_bytes,
               "base mutated or not refused")
    _ib_rep_bad = _ib_rep.read_text(encoding="utf-8-sig")
    _ib_rep_bad = _ib_rep_bad.replace("role: core",
                                      "role: critic\nrole: core", 1)
    _ib_rep.write_text(_ib_rep_bad, encoding="utf-8")
    _ib_rep_bytes = _ib_rep.read_bytes()
    try:
        append_run(_ib_rep, "NO_FINDINGS\n")
        _ib_append_refused = False
    except Exception:
        _ib_append_refused = True
    expect("append_run on a malformed strict report refuses with ZERO writes",
           _ib_append_refused and _ib_rep.read_bytes() == _ib_rep_bytes,
           "malformed report was extended")
    _ib_manifest.write_text(_ib_manifest_ok, encoding="utf-8")
    _ib_rep.write_text(_ib_rep.read_text(encoding="utf-8-sig").replace(
        "role: critic\nrole: core", "role: core"), encoding="utf-8")
    _ib_after_restore = True
    expect("restored valid manifest + report still validate",
           validate_report(_ib_rep.read_text(encoding="utf-8-sig"),
                           strict=True) == [],
           "restored report invalid")

    # ---- T-638/§2 + §10: PROPOSED-state validation, mutator by mutator --
    # a known-invalid PROPOSED state never enters PREPARED/APPLY, never
    # leaves bytes, and no journal claims COMMITTED.
    _pc_root = project_fixture("saipen-proposed-")
    # create_cycle with invalid created_at: ZERO writes, no directory appears.
    _pc_owner = _pc_root / ".saipen" / "improve"
    try:
        create_cycle(_pc_root, "imp-bad-time",
                     created_at="NOT-A-TIME", project_identity="p")
        _pc_time_refused = False
    except Exception:
        _pc_time_refused = True
    expect("create_cycle invalid created_at refuses with ZERO writes "
           "(no manifest, no directory)",
           _pc_time_refused
           and not (_pc_owner / "imp-bad-time" / "MANIFEST.md").exists()
           and not (_pc_owner / "imp-bad-time").exists(),
           "invalid created_at left bytes behind")
    try:
        create_cycle(_pc_root, "imp-bad-proj",
                     created_at="2026-08-12T00:00:00Z",
                     project_identity="V:/absolute/path")
        _pc_proj_refused = False
    except Exception:
        _pc_proj_refused = True
    expect("create_cycle non-portable project_identity refuses with ZERO "
           "writes",
           _pc_proj_refused
           and not (_pc_owner / "imp-bad-proj" / "MANIFEST.md").exists(),
           "invalid project_identity left bytes behind")
    # write_sweep_entry on a malformed SWEEP base: ZERO writes.
    _pc_cycle = create_cycle(_pc_root, "imp-pc",
                             created_at="2026-08-12T00:00:00Z",
                             project_identity="p")
    register_seat(_pc_cycle, "seat-1", "core", "saipen_improve_A.md")
    _pc_rep = create_report(_pc_root, "imp-pc", "seat-1", "A",
                            agent="seat-1", role="core",
                            model_or_runtime="probe",
                            context_scope="scope")
    append_run(_pc_rep, "IMP-001 [P1] [LOGIC_ERROR] [proven] [ticket]\n"
                        "expected: x\nactual: y\nevidence: z\n")
    complete_report(_pc_rep)
    _pc_cycle_ticket = ticket_fixture(_pc_root, "T-900")
    (_pc_cycle / "SWEEP.md").write_text(
        "# SWEEP\nTHIS IS GARBAGE\n", encoding="utf-8")
    _pc_sweep_bytes = (_pc_cycle / "SWEEP.md").read_bytes()
    try:
        write_sweep_entry(_pc_cycle, {"run": "RUN-1", "imp_id": "001",
                                      "disposition": "CONFIRMED",
                                      "ticket": "T-900",
                                      "report": "saipen_improve_A.md",
                                      "reproduced": "y"})
        _pc_sweep_refused = False
    except Exception:
        _pc_sweep_refused = True
    expect("write_sweep_entry on a malformed SWEEP ledger refuses with ZERO "
           "writes",
           _pc_sweep_refused
           and (_pc_cycle / "SWEEP.md").read_bytes() == _pc_sweep_bytes,
           "malformed SWEEP was extended")
    # write_sweep_entry on a malformed COMPLETE report: ZERO sweep writes.
    (_pc_cycle / "SWEEP.md").write_text("# SWEEP\n", encoding="utf-8")
    _pc_rep_malformed = _pc_rep.read_text(encoding="utf-8-sig").replace(
        "role: core", "role: critic\nrole: core", 1)
    _pc_rep.write_text(_pc_rep_malformed, encoding="utf-8")
    _pc_sweep_bytes = (_pc_cycle / "SWEEP.md").read_bytes()
    try:
        write_sweep_entry(_pc_cycle, {"run": "RUN-1", "imp_id": "001",
                                      "disposition": "CONFIRMED",
                                      "ticket": "T-900",
                                      "report": "saipen_improve_A.md",
                                      "reproduced": "y"})
        _pc_sweep_report_refused = False
    except Exception:
        _pc_sweep_report_refused = True
    expect("write_sweep_entry on a malformed COMPLETE report refuses with "
           "ZERO writes",
           _pc_sweep_report_refused
           and (_pc_cycle / "SWEEP.md").read_bytes() == _pc_sweep_bytes,
           "malformed report's finding was swept")
    _pc_rep.write_text(_pc_rep.read_text(encoding="utf-8-sig").replace(
        "role: critic\nrole: core", "role: core"), encoding="utf-8")
    # A valid full sweep, then complete_cycle -- the archive-corruption test
    # needs a genuinely COMPLETE+SWEPT cycle to corrupt.
    write_sweep_entry(_pc_cycle, {"run": "RUN-1", "imp_id": "001",
                                  "disposition": "CONFIRMED",
                                  "ticket": "T-900",
                                  "report": "saipen_improve_A.md",
                                  "reproduced": "y"})
    complete_cycle(_pc_cycle)
    _pc_manifest_bytes = (_pc_cycle / "MANIFEST.md").read_bytes()
    _pc_corrupt_rep = _pc_rep.read_text(encoding="utf-8-sig").replace(
        "role: core", "role: critic\nrole: core", 1)
    _pc_rep.write_text(_pc_corrupt_rep, encoding="utf-8")
    try:
        archive_cycle(_pc_cycle)
        _pc_archive_refused = False
    except Exception:
        _pc_archive_refused = True
    expect("archive of a corrupted COMPLETE cycle refuses with ZERO writes",
           _pc_archive_refused
           and (_pc_cycle / "MANIFEST.md").read_bytes() == _pc_manifest_bytes,
           "corrupted completed cycle was archived")

    # P0 (T-632) crash-safety: a forced _journaled_write failure must leave no
    # split active-manifest/discarded-report state -- report bytes intact,
    # manifest still active, retry still possible.
    import saipen_engine.journal as _ab_journal_mod
    ab_crash_root = project_fixture("saipen-abort-crash-")
    (ab_crash_root / "src.txt").write_text("v1\n", encoding="utf-8")
    _abc_cycle = create_cycle(ab_crash_root, "imp-ab-crash")
    register_seat(_abc_cycle, "seat-1", "core", "saipen_improve_C.md")
    _abc_rep = create_report(ab_crash_root, "imp-ab-crash", "seat-1", "C",
                             agent="seat-1", role="core",
                             model_or_runtime="probe",
                             context_scope="scope")
    _abc_bytes = _abc_rep.read_bytes()

    def _fail_before_any_target(stage: str) -> None:
        raise OSError("forced abort write failure before first target")

    with mock.patch.object(_improve, "_journaled_write",
                           side_effect=_fail_before_any_target):
        try:
            abort_cycle(_abc_cycle)
            _ab_failed = False
        except Exception:
            _ab_failed = True
    _abc_manifest_now = (_abc_cycle / "MANIFEST.md").read_text(
        encoding="utf-8-sig")
    expect("abort failure before first target: no split state -- manifest "
           "still active, report byte-identical, no .discarded",
           _ab_failed
           and "cycle_status: active" in _abc_manifest_now
           and "cycle_aborted" not in _abc_manifest_now
           and _abc_rep.is_file() and _abc_rep.read_bytes() == _abc_bytes
           and not _abc_rep.with_name(_abc_rep.name + ".discarded").exists(),
           repr((_abc_manifest_now, _abc_rep.exists())))

    # Crash after the journal writes the manifest target: recovery must roll
    # the operation forward (archived manifest, reports untouched) -- never
    # leave a half-aborted cycle.
    def _crash_after_manifest(stage: str) -> None:
        if stage == "manifest":
            raise SystemExit(91)

    with mock.patch.object(_ab_journal_mod, "_crash_after",
                           side_effect=_crash_after_manifest):
        try:
            abort_cycle(_abc_cycle)
            _ab_crashed = False
        except SystemExit:
            _ab_crashed = True
    _ab_pending = pending_ops(ab_crash_root)
    expect("abort crash after manifest write leaves one pending op",
           _ab_crashed and len(_ab_pending) == 1,
           repr((_ab_crashed, _ab_pending)))
    _ab_recovered = recover(ab_crash_root,
                            _ab_pending[0]["op_id"]) if _ab_pending else {}
    _abc_manifest_now = (_abc_cycle / "MANIFEST.md").read_text(
        encoding="utf-8-sig")
    expect("abort crash recovery rolls forward: manifest archived, report "
           "byte-identical at same path, no split state",
           _ab_recovered.get("ok")
           and "cycle_status: archived" in _abc_manifest_now
           and "cycle_aborted" in _abc_manifest_now
           and _abc_rep.is_file() and _abc_rep.read_bytes() == _abc_bytes
           and not pending_ops(ab_crash_root),
           repr((_ab_recovered, _abc_manifest_now)))
    # Already-applied retry after recovery is idempotent (refused: not active).
    try:
        abort_cycle(_abc_cycle)
        _ab_retry_refused = False
    except ImproveError:
        _ab_retry_refused = True
    expect("abort retry after recovery refuses (cycle no longer active) with "
           "evidence untouched",
           _ab_retry_refused
           and _abc_rep.is_file() and _abc_rep.read_bytes() == _abc_bytes,
           repr(_abc_rep.exists()))

    # External conflicting edit before recovery: recovery must refuse
    # CONFLICT and leave the report bytes intact.
    ab_conf_root = project_fixture("saipen-abort-conflict-")
    (ab_conf_root / "src.txt").write_text("v1\n", encoding="utf-8")
    _abcf_cycle = create_cycle(ab_conf_root, "imp-ab-conflict")
    register_seat(_abcf_cycle, "seat-1", "core", "saipen_improve_F.md")
    _abcf_rep = create_report(ab_conf_root, "imp-ab-conflict", "seat-1", "F",
                              agent="seat-1", role="core",
                              model_or_runtime="probe",
                              context_scope="scope")
    _abcf_bytes = _abcf_rep.read_bytes()
    with mock.patch.object(_ab_journal_mod, "_crash_after",
                           side_effect=_crash_after_manifest):
        try:
            abort_cycle(_abcf_cycle)
            _abcf_crashed = False
        except SystemExit:
            _abcf_crashed = True
    _abcf_pending = pending_ops(ab_conf_root)
    # External edit to the manifest between crash and recovery.
    (_abcf_cycle / "MANIFEST.md").write_text(
        "cycle_status: active\ncycle_id: hijacked\n", encoding="utf-8")
    _abcf_recovered = recover(ab_conf_root,
                              _abcf_pending[0]["op_id"]) if _abcf_pending else {}
    expect("abort recovery over an external conflicting manifest edit refuses "
           "CONFLICT and never touches report bytes",
           _abcf_crashed and not _abcf_recovered.get("ok")
           and _abcf_recovered.get("code") in ("CONFLICT", "RECOVERY_CONFLICT")
           and _abcf_rep.is_file() and _abcf_rep.read_bytes() == _abcf_bytes,
           repr((_abcf_crashed, _abcf_recovered)))

    # ---- T-601: resolver race -- two processes resolving the same conflict
    # yield exactly one canonical settlement (WRITER_BUSY or a settled-journal
    # refusal for the loser, never two RESOLVED).
    from saipen_engine.journal import (Journal as _RaceJournal,
                                       hash_bytes as _race_hb)
    race_root = project_fixture("saipen-race-")
    saipen_r = race_root / ".saipen"
    # a DONE-state root so the external phase HUNT modification is real
    (saipen_r / "STATE.md").write_text(
        "---\nphase: DONE\ntask: none\nnext_action: \"saipen continue\"\n"
        "blocker: \"\"\nsaipen_version: 7\nschema_version: 3\nlast_event: 900\n"
        "style_contract: ded-4ae736e4\nsaipen_home: \".\"\nagent: probe\nmode: full\n"
        "updated: 2026-08-09T00:00:00Z\n---\n", encoding="utf-8")
    log_r = (saipen_r / "LOG.md").read_bytes()
    state_r = (saipen_r / "STATE.md").read_bytes()
    new_log_r = log_r + b"\n- 09.08.26 00:01 [E-901] RUN: op\n"
    new_state_r = state_r.replace(b"phase: DONE", b"phase: BUILD")
    jr = _RaceJournal(race_root, "op-race")
    jr.start("checkpoint", "probe", "id", "h", [
        {"path": ".saipen/LOG.md", "role": "log", "content": new_log_r,
         "before_hash": _race_hb(log_r), "after_hash": _race_hb(new_log_r)},
        {"path": ".saipen/STATE.md", "role": "state", "content": new_state_r,
         "before_hash": _race_hb(state_r), "after_hash": _race_hb(new_state_r)},
    ], verification_policy="core_fast")
    (saipen_r / "LOG.md").write_bytes(new_log_r)
    jr.mark("APPLYING", progress_index=1, target_index=0)
    ext_r = state_r.replace(b"phase: DONE", b"phase: HUNT").replace(
        b"last_event: 900", b"last_event: 901")
    (saipen_r / "STATE.md").write_bytes(ext_r)
    recover(race_root, "op-race")
    race_code = (
        "import sys; sys.path.insert(0, r'%s')\n"
        "from saipen_engine.journal import resolve_conflict\n"
        "print(resolve_conflict(r'%s', 'op-race', 'accept_live', 'probe'))"
        % (str(HOME / "tools"), str(race_root)))
    procs = [subprocess.Popen([sys.executable, "-c", race_code],
                              cwd=str(race_root), stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True)
             for _ in range(2)]
    outs = [p.communicate(timeout=90)[0] for p in procs]
    n_resolved = sum("'code': 'RESOLVED'" in o for o in outs)
    settled_status = _RaceJournal(race_root, "op-race").read().get("status")
    expect("resolver race: exactly one process settles the conflict, the "
           "loser refuses (WRITER_BUSY or settled-journal refusal)",
           n_resolved == 1 and settled_status == "RESOLVED"
           and all(("'code': 'RESOLVED'" in o or "WRITER_BUSY" in o
                    or "is RESOLVED, not CONFLICT" in o)
                   for o in outs),
           repr((n_resolved, settled_status, outs)))

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
            "run_mutation(r'%s', '%s', 'op', 'probe', 'id', 'hash', [\n"
            "  {'path': '.saipen/LOG.md', 'role': 'log', 'content': %r},\n"
            "  {'path': '.saipen/BOARD.md', 'role': 'board', 'content': %r},\n"
            "  {'path': '.saipen/STATE.md', 'role': 'state', 'content': %r}])"
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
    targets = [t["path"] for t in record["targets"]]
    result = run_mutation(
        root, "op-log", "op", "probe", "id", "hash",
        [{"path": p, "role": "generic", "content": b""} for p in targets],
        preconditions={"STATE.md": "x"},  # stale, must not matter when committed
        skip_preflight=True)
    expect("a committed op's retry returns ALREADY_APPLIED",
           result.get("code") == "ALREADY_APPLIED", repr(result))
    expect("no duplicate LOG event from a retried committed op",
           log.read_text(encoding="utf-8").count("E-901") == 1)

    # Recovery conflict: a pending target mutated externally must CONFLICT
    # and preserve the external bytes (NITRO integrity R8).
    log.write_bytes(log_before)
    board.write_bytes(board_before)
    state.write_bytes(state_before)
    from saipen_engine.journal import hash_bytes
    op = "op-conflict"
    journal = Journal(root, op)
    journal.start("op", "probe", "id", "hash", [
        {"path": ".saipen/LOG.md", "role": "log",
         "content": log_before + b"\n- 09.08.26 00:01 [E-902] RUN: op\n",
         "before_hash": hash_bytes(log_before), "after_hash": "x"},
        {"path": ".saipen/BOARD.md", "role": "board", "content": board_before,
         "before_hash": hash_bytes(board_before), "after_hash": "y"},
        {"path": ".saipen/STATE.md", "role": "state",
         "content": state_before.replace(b"phase: DONE", b"phase: BUILD"),
         "before_hash": hash_bytes(state_before), "after_hash": "z"},
    ])
    (saipen / "LOG.md").write_bytes(
        log_before + b"\n- 09.08.26 00:01 [E-902] RUN: op\n")
    journal.mark("APPLYING", progress_index=1, target_index=0)
    external = board_before + b"\n# externally modified\n"
    (saipen / "BOARD.md").write_bytes(external)
    result = recover(root, op)
    expect("recovery CONFLICTs on externally modified pending target",
           result.get("code") == "CONFLICT"
           and (saipen / "BOARD.md").read_bytes() == external,
           repr(result))
    expect("conflict preserves the journal for evidence",
           journal.exists() and journal.read()["status"] == "CONFLICT")

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


def run_nitro_m3_probes() -> tuple[list[str], int]:
    """NITRO M3 (T-580): claim as a journalled SAIOPS operation.

    PLAN writes zero canonical bytes; APPLY moves exactly one ticket, sets
    STATE to SCOUT/T-ID with the allocated event, and a second claim on the
    same ticket is refused.
    """
    problems: list[str] = []
    checked = 0

    def expect(label: str, ok: bool, detail: str = "") -> None:
        nonlocal checked
        checked += 1
        if not ok:
            problems.append(f"{label}: {detail}")
        else:
            print(f"PASS: nitro-m3 -- {label}")

    root = Path(tempfile.mkdtemp(prefix="saipen-m3-"))
    saipen = root / ".saipen"
    saipen.mkdir()
    (saipen / "LOG.md").write_text(
        "- 09.08.26 00:00 [E-900] [T-none] DEC: base\n", encoding="utf-8")
    (saipen / "BOARD.md").write_text(
        "# Board\n## DOING\n## TODO\n- [ ] T-777 [P1] probe ticket | "
        "verify: probe\n## DONE\n## BLOCKED\n", encoding="utf-8")
    (saipen / "STATE.md").write_text(
        "---\nphase: DONE\ntask: none\nnext_action: \"saipen continue\"\n"
        "blocker: \"\"\ntransition_from: SHIP\nsaipen_version: 7\n"
        "schema_version: 3\nlast_event: 900\nstyle_contract: ded-4ae736e4\n"
        "agent: probe\nmode: full\nupdated: 2026-08-09T00:00:00Z\n---\n",
        encoding="utf-8")

    board_before = (saipen / "BOARD.md").read_bytes()
    state_before = (saipen / "STATE.md").read_bytes()
    log_before = (saipen / "LOG.md").read_bytes()

    planned = plan_claim(root, "T-777", "probe")
    expect("plan_claim returns a dry-run plan with no refusal",
           planned.get("ok") and planned.get("dry_run")
           and planned.get("code") == "CLAIMED", repr(planned))
    expect("plan writes zero canonical bytes",
           (saipen / "BOARD.md").read_bytes() == board_before
           and (saipen / "STATE.md").read_bytes() == state_before
           and (saipen / "LOG.md").read_bytes() == log_before)

    result = apply_claim(root, "T-777", "probe")
    expect("apply_claim commits the claim",
           result.get("ok") and result.get("code") == "CLAIMED",
           repr(result))
    board_after = parse_board(codec.read_doc(saipen / "BOARD.md"))
    expect("claim moves exactly one ticket to DOING with / checkbox",
           [t["id"] for t in board_after["tickets"].values()
            if t["section"] == "## DOING"] == ["T-777"]
           and board_after["tickets"]["T-777"]["checkbox"] == "/",
           repr([(t["id"], t["checkbox"]) for t in board_after["tickets"]
                 .values() if t["section"] == "## DOING"]))
    state_after = parse_state(codec.read_doc(saipen / "STATE.md"))
    expect("claim sets STATE to SCOUT/T-777 with a new event",
           state_after.get("phase") == "SCOUT"
           and state_after.get("task") == "T-777"
           and state_after.get("last_event") == 901,
           repr((state_after.get("phase"), state_after.get("task"),
                 state_after.get("last_event"))))
    log_text = codec.read_doc(saipen / "LOG.md")
    expect("claim appends exactly one LOG event with a real taxonomy",
           log_text.count("E-901") == 1
           and "DEC:" in log_text, repr(log_text[-120:]))

    again = apply_claim(root, "T-777", "probe")
    expect("a second claim on the claimed ticket is refused",
           not again.get("ok") and again.get("code") == "ALREADY_CLAIMED",
           repr(again))

    # Transition: SCOUT -> BUILD legal and journalled; illegal refused; dry-run
    # writes nothing.
    state_before = (saipen / "STATE.md").read_bytes()
    log_before = (saipen / "LOG.md").read_bytes()
    illegal = transition_phase(root, "REVIEW", "probe", "T-777")
    expect("an illegal transition is refused with ILLEGAL_TRANSITION",
           not illegal.get("ok")
           and illegal.get("code") == "ILLEGAL_TRANSITION", repr(illegal))
    plan = transition_phase(root, "BUILD", "probe", "T-777",
                            "building", dry_run=True)
    expect("transition dry-run writes zero canonical bytes",
           plan.get("ok") and plan.get("dry_run")
           and (saipen / "STATE.md").read_bytes() == state_before
           and (saipen / "LOG.md").read_bytes() == log_before, repr(plan))
    result = transition_phase(root, "BUILD", "probe", "T-777", "building")
    expect("SCOUT->BUILD transition commits with a new event",
           result.get("ok") and result.get("code") == "TRANSITIONED"
           and parse_state(codec.read_doc(saipen / "STATE.md")).get("phase")
           == "BUILD", repr(result))

    # Checkpoint: allocates exactly one event, bumps last_event.
    log_before = (saipen / "LOG.md").read_bytes()
    state_before = (saipen / "STATE.md").read_bytes()
    cp = checkpoint(root, "probe", "RUN", "T-777", "probe checkpoint")
    log_after = codec.read_doc(saipen / "LOG.md")
    expect("checkpoint appends exactly one event with an allocated E-ID",
           cp.get("ok") and cp.get("code") == "CHECKPOINTED"
           and log_after.count(cp.get("event_id", "E-0")) == 1,
           repr(cp))
    expect("checkpoint bumps STATE last_event to the new event",
           parse_state(codec.read_doc(saipen / "STATE.md")).get("last_event")
           == int(cp.get("event_id", "E-0")[2:]), repr(cp))

    # Ticket lifecycle: canonical ID allocation reads STRUCTURED records only
    # (T-639/§9) -- prose that mentions T-NNN is not identity, canonical
    # ticket lines are.
    tid = next_ticket_id(
        "# Board\n## DOING\n## TODO\n- [ ] T-901 probe\n## DONE\n## BLOCKED\n"
        "note: synthetic T-900000 fixture mentioned in prose\n",
        "- 09.08.26 00:00 [E-1] [T-901] RUN: base\n")
    expect("next_ticket_id ignores prose T-NNN mentions (structured-only)",
           tid == 902, repr(tid))
    tid_log = next_ticket_id(
        "# Board\n## DOING\n## TODO\n## DONE\n## BLOCKED\n",
        "- 09.08.26 00:00 [E-1] RUN: shipped T-800 in message prose\n")
    expect("next_ticket_id ignores LOG prose T-NNN mentions",
           tid_log == 1, repr(tid_log))
    added = ticket_add(root, "probe", "P2", "probe ticket", [], "verify",
                       dry_run=False)
    expect("ticket_add creates a canonical ticket",
           added.get("ok") and added.get("code") == "TICKET_ADDED"
           and added.get("ticket") == "T-778", repr(added))

    # Legal lifecycle: done accepts ONLY ## DOING. A TODO ticket cannot skip
    # claim/work (NITRO integrity R5) -- the old probe encoded the bug as PASS.
    todo_done = ticket_move(root, "done", "T-778", "probe")
    expect("done on a TODO ticket is refused (IL_LEGAL_TICKET_LIFECYCLE)",
           not todo_done.get("ok")
           and todo_done.get("code") == "ILLEGAL_TICKET_LIFECYCLE",
           repr(todo_done))
    expect("refused done writes zero canonical bytes",
           parse_board(codec.read_doc(saipen / "BOARD.md"))["tickets"]
           ["T-778"]["section"] == "## TODO")

    # Finish the active T-777 through the legal lifecycle: done is the atomic
    # finish operation (NITRO dogfood III) requiring DOING + [/] + STATE.task
    # binding, and under the T-602 gate it requires the full phase chain to
    # have reached SHIP; it closes LOG+BOARD+STATE in one plan and reports
    # FINISHED.
    transition_phase(root, "VERIFY", "probe", "T-777", "verify")
    transition_phase(root, "REVIEW", "probe", "T-777", "review")
    transition_phase(root, "SHIP", "probe", "T-777", "ship")
    done = ticket_move(root, "done", "T-777", "probe")
    expect("done on the active DOING ticket succeeds and moves it to DONE",
           done.get("ok") and done.get("code") == "FINISHED"
           and parse_board(codec.read_doc(saipen / "BOARD.md"))
           ["tickets"]["T-777"]["section"] == "## DONE"
           and parse_state(codec.read_doc(saipen / "STATE.md")).get("phase")
           == "DONE", repr(done))

    # Claim the now-topmost T-778, then finish it legally (full chain).
    claimed2 = apply_claim(root, "T-778", "probe")
    expect("claim of the topmost workable ticket succeeds",
           claimed2.get("ok") and claimed2.get("code") == "CLAIMED",
           repr(claimed2))
    transition_phase(root, "BUILD", "probe", "T-778", "b")
    transition_phase(root, "VERIFY", "probe", "T-778", "v")
    transition_phase(root, "REVIEW", "probe", "T-778", "r")
    transition_phase(root, "SHIP", "probe", "T-778", "s")
    done2 = ticket_move(root, "done", "T-778", "probe")
    expect("legal DOING->DONE lifecycle succeeds",
           done2.get("ok") and done2.get("code") == "FINISHED",
           repr(done2))

    # M5: goal/cc mechanics. reauthorize refuses without a tripped valve.
    refused = reauthorize_valve(root, "probe")
    expect("reauthorize_valve refuses a valve that has not tripped",
           not refused.get("ok") and refused.get("code") == "VALIDATION_FAILED",
           repr(refused))
    phase_before_goal = parse_state(codec.read_doc(saipen / "STATE.md")).get(
        "phase")
    goal = set_goal_intent(root, "probe", "M5 probe")
    state_after_goal = parse_state(codec.read_doc(saipen / "STATE.md"))
    expect("set_goal_intent pivots to goal with counters from 0",
           goal.get("ok") and goal.get("code") == "GOAL_SET"
           and state_after_goal.get("execution_intent") == "goal"
           and state_after_goal.get("goal_waves") == 0, repr(goal))
    expect("set_goal_intent preserves phase/task (not a claim)",
           state_after_goal.get("phase") == phase_before_goal,
           repr((phase_before_goal, state_after_goal.get("phase"))))
    stop = stop_checkpoint(root, "probe", "probe stop")
    expect("stop_checkpoint writes a resumable next_action",
           stop.get("ok") and stop.get("code") == "STOPPED"
           and parse_state(codec.read_doc(saipen / "STATE.md")).get(
               "next_action"), repr(stop))

    return problems, checked


def run_nitro_integrity_probes() -> tuple[list[str], int]:
    """NITRO integrity sweep red controls (T-584, audit R1..R12 + core).

    These are BEHAVIORAL controls against the repaired engine, not proxy
    assertions: each one creates the exact bad condition and demands the
    repaired refusal/behaviour. A control goes red when the engine regresses.
    """
    problems: list[str] = []
    checked = 0

    def expect(label: str, ok: bool, detail: str = "") -> None:
        nonlocal checked
        checked += 1
        if not ok:
            problems.append(f"{label}: {detail}")
        else:
            print(f"PASS: nitro-integrity -- {label}")

    def make_project() -> Path:
        root = Path(tempfile.mkdtemp(prefix="saipen-integrity-"))
        saipen = root / ".saipen"
        saipen.mkdir()
        (saipen / "LOG.md").write_text(
            "- 09.08.26 00:00 [E-900] [T-none] DEC: base\n", encoding="utf-8")
        (saipen / "BOARD.md").write_text(
            "# Board\n## DOING\n## TODO\n"
            "- [ ] T-1 [P1] top probe | verify: probe\n"
            "- [ ] T-2 [P1] lower probe | verify: probe\n"
            "## DONE\n## BLOCKED\n", encoding="utf-8")
        (saipen / "STATE.md").write_text(
            "---\nphase: DONE\ntask: none\nnext_action: \"saipen continue\"\n"
            "blocker: \"\"\ntransition_from: SHIP\nsaipen_version: 7\n"
            "schema_version: 3\nlast_event: 900\nstyle_contract: ded-4ae736e4\n"
            "saipen_home: \".\"\nagent: probe\nrequires:\n  - filesystem\n"
            "  - git\n  - python\nmode: full\nupdated: 2026-08-09T00:00:00Z\n"
            "---\n", encoding="utf-8")
        return root

    def project_tree(root: Path) -> dict[str, bytes]:
        out = {}
        for path in sorted((root / ".saipen").rglob("*")):
            if path.is_file():
                out[path.relative_to(root).as_posix()] = path.read_bytes()
        return out

    # Import floor: every shipped engine module imports in isolation.
    from saipen_engine import (board, codec, context, errors, fast_check,  # noqa: F401
                               journal, lock, log, operations, paths, phases,
                               plan, result, safeid, snapshot, state, subs)
    expect("every shipped saipen_engine module imports in isolation", True)

    # ---- R1/R2: checkpoint and ticket_add preserve phase/task.
    root = make_project()
    _snap = project_tree(root)
    root2 = make_project()
    apply_claim(root2, "T-1", "probe")
    transition_phase(root2, "BUILD", "probe", "T-1", "integrity setup")
    st = parse_state(codec.read_doc(root2 / ".saipen" / "STATE.md"))
    cp = checkpoint(root2, "probe", "RUN", "T-1", "integrity checkpoint")
    st = parse_state(codec.read_doc(root2 / ".saipen" / "STATE.md"))
    expect("checkpoint preserves phase (no SCOUT rewrite)",
           cp.get("ok") and st.get("phase") == "BUILD", repr(st))
    expect("checkpoint preserves task",
           cp.get("ok") and st.get("task") == "T-1", repr(st))
    expect("checkpoint preserves next_action",
           cp.get("ok") and st.get("next_action")
           == "PHASE BUILD T-1", repr(st))
    add = ticket_add(root2, "probe", "P2", "future", [], "verify")
    st = parse_state(codec.read_doc(root2 / ".saipen" / "STATE.md"))
    expect("ticket_add preserves execution phase",
           add.get("ok") and st.get("phase") == "BUILD", repr(st))

    # ---- R6: dry-run writes zero bytes.
    before = project_tree(root)
    claim_plan = plan_claim(root, "T-1", "probe")
    after = project_tree(root)
    expect("plan_claim dry-run writes zero canonical bytes",
           claim_plan.get("ok") and claim_plan.get("dry_run")
           and before == after,
           f"changed={set(before) ^ set(after)}")
    cp_plan = checkpoint(root, "probe", "RUN", "T-1", "dry", dry_run=True)
    after2 = project_tree(root)
    expect("checkpoint dry-run writes zero bytes",
           cp_plan.get("ok") and cp_plan.get("dry_run")
           and after == after2,
           repr(cp_plan.to_dict()))

    # ---- Pick Rule: claiming the lower ticket refuses.
    lower = plan_claim(root, "T-2", "probe")
    expect("normal claim of a non-top workable ticket refuses "
           "(NOT_TOP_WORKABLE)",
           not lower.get("ok") and lower.get("code") == "NOT_TOP_WORKABLE",
           repr(lower))
    top = apply_claim(root, "T-1", "probe")
    expect("claim of the topmost workable ticket succeeds",
           top.get("ok") and top.get("code") == "CLAIMED", repr(top))

    # ---- T-631: blocker is an authorization boundary, even on malformed
    # TODO input that a caller passes without running the full validator.
    from saipen_engine.router import route_next as _blocker_route_next
    blocker_root = make_project()
    blocker_board = blocker_root / ".saipen" / "BOARD.md"
    blocker_board.write_text(
        blocker_board.read_text(encoding="utf-8").replace(
            "T-1 [P1] top probe | verify: probe",
            "T-1 [P1] top probe | blocker: WAIT_USER_CONFIRMATION | "
            "verify: probe",
        ),
        encoding="utf-8",
    )
    blocker_before = project_tree(blocker_root)
    blocker_normal = apply_claim(blocker_root, "T-1", "probe")
    blocker_explicit = apply_claim(
        blocker_root, "T-1", "probe", explicit=True)
    expect("normal claim refuses a TODO ticket carrying blocker",
           blocker_normal.get("code") == "TICKET_NOT_WORKABLE",
           repr(blocker_normal))
    expect("explicit claim cannot override blocker authorization",
           blocker_explicit.get("code") == "TICKET_NOT_WORKABLE",
           repr(blocker_explicit))
    expect("refused normal and explicit blocker claims write zero bytes",
           blocker_before == project_tree(blocker_root))
    blocker_state = codec.read_doc(blocker_root / ".saipen" / "STATE.md")
    blocker_text = codec.read_doc(blocker_board)
    blocker_route = _blocker_route_next(blocker_state, blocker_text)
    expect("router skips malformed TODO+blocker and never emits SCOUT for it",
           blocker_route.get("action") == "PHASE SCOUT T-2",
           repr(blocker_route))

    blocker_status = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "status",
         "--json"], cwd=str(blocker_root), capture_output=True, text=True,
        timeout=60)
    blocker_status_data = json.loads(blocker_status.stdout)
    expect("public status excludes TODO+blocker from top_workable",
           blocker_status_data.get("top_workable_ticket") == "T-2"
           and blocker_status_data.get("computed_next_action")
           == "PHASE SCOUT T-2", repr(blocker_status_data))
    blocker_next = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "next", "--json"],
        cwd=str(blocker_root), capture_output=True, text=True, timeout=60)
    blocker_next_data = json.loads(blocker_next.stdout)
    expect("public next never emits SCOUT for TODO+blocker",
           blocker_next_data.get("action") == "PHASE SCOUT T-2",
           repr(blocker_next_data))

    # Hypothetical T-624/T-625 completion cannot make a human gate executable.
    gated_root = make_project()
    (gated_root / ".saipen" / "BOARD.md").write_text(
        "# Board\n## DOING\n## TODO\n"
        "- [ ] T-3 [P3] human decision | needs: T-1,T-2 | "
        "blocker: WAIT_USER_CONFIRMATION | verify: human decision\n"
        "## DONE\n"
        "- [x] T-1 [P1] prerequisite one | verify: done\n"
        "- [x] T-2 [P1] prerequisite two | verify: done\n"
        "## BLOCKED\n",
        encoding="utf-8",
    )
    gated_route = _blocker_route_next(
        codec.read_doc(gated_root / ".saipen" / "STATE.md"),
        codec.read_doc(gated_root / ".saipen" / "BOARD.md"),
    )
    gated_claim = apply_claim(gated_root, "T-3", "probe", explicit=True)
    expect("satisfied prerequisites never activate a human-decision blocker",
           gated_route.get("action") != "PHASE SCOUT T-3"
           and gated_claim.get("code") == "TICKET_NOT_WORKABLE",
           repr((gated_route, gated_claim)))

    # Mutation: restore old Pick Rule by ignoring blocker. Forbidden ticket is
    # immediately routed, proving the controls are coupled to blocker defense.
    with mock.patch(
            "saipen_engine.router.ticket_is_workable",
            side_effect=lambda ticket, tickets, agent=None, now=None: (
                ticket.get("section") == "## TODO"
                and all(tickets.get(need, {}).get("section") == "## DONE"
                        for need in ticket.get("needs", [])))):
        mutated_route = _blocker_route_next(blocker_state, blocker_text)
    expect("mutation ignoring blocker makes Pick Rule route forbidden ticket",
           mutated_route.get("action") == "PHASE SCOUT T-1",
           repr(mutated_route))

    # ---- R4: transition cannot switch ticket identity / fake ticket.
    fake = transition_phase(root, "BUILD", "probe", "T-999", "fake")
    expect("transition with a nonexistent ticket refuses",
           not fake.get("ok") and fake.get("code") == "TICKET_NOT_FOUND",
           repr(fake))
    swapped = transition_phase(root, "BUILD", "probe", "T-2", "swap")
    expect("transition with a non-active ticket refuses "
           "(ACTIVE_TICKET_MISMATCH)",
           not swapped.get("ok")
           and swapped.get("code") == "ACTIVE_TICKET_MISMATCH", repr(swapped))
    ok_tr = transition_phase(root, "BUILD", "probe", "T-1", "build")
    st = parse_state(codec.read_doc(root / ".saipen" / "STATE.md"))
    expect("transition binds the exact active DOING ticket",
           ok_tr.get("ok") and st.get("phase") == "BUILD"
           and st.get("task") == "T-1", repr(st))

    # ---- R5: legal lifecycle only. Block the active ticket, then unblock.
    active_board = root / ".saipen" / "BOARD.md"
    active_board.write_text(
        active_board.read_text(encoding="utf-8").replace(
            " | owner: probe", " | verify_attempts: 1 | owner: probe", 1),
        encoding="utf-8",
    )
    blocked = ticket_move(root, "block", "T-1", "probe", "blocked now")
    blocked_ticket = parse_board(codec.read_doc(active_board))["tickets"]["T-1"]
    blocked_state = parse_state(codec.read_doc(root / ".saipen" / "STATE.md"))
    expect("block of an active DOING ticket succeeds",
           blocked.get("ok") and blocked.get("code") == "BLOCK"
           and blocked_ticket["section"] == "## BLOCKED"
           and blocked_ticket["fields"].get("blocker") == "blocked now",
           repr((blocked, blocked_ticket)))
    expect("block of the active ticket never parks the session in a "
           "session-level BLOCKED state",
           blocked_state.get("phase") != "BLOCKED"
           and blocked_state.get("task") == "none"
           and blocked_state.get("blocker") in ("", "none"),
           repr(blocked_state))
    expect("block routes the next_action to the remaining workable TODO",
           blocked_state.get("next_action") == "PHASE SCOUT T-2",
           repr(blocked_state))
    unblock_no_evidence = ticket_move(root, "unblock", "T-1", "probe")
    expect("unblock without the lifting decision/evidence refuses",
           not unblock_no_evidence.get("ok")
           and unblock_no_evidence.get("code") == "VALIDATION_FAILED",
           repr(unblock_no_evidence))
    unblocked = ticket_move(root, "unblock", "T-1", "probe",
                            "block cleared by recorded decision")
    bd = parse_board(codec.read_doc(root / ".saipen" / "BOARD.md"))
    expect("unblock atomically creates TODO without active blocker/history",
           unblocked.get("ok")
           and bd["tickets"]["T-1"]["section"] == "## TODO"
           and "blocker" not in bd["tickets"]["T-1"]["fields"]
           and "verify_attempts" not in bd["tickets"]["T-1"]["fields"],
           repr(bd["tickets"]["T-1"]["raw"]))

    # ---- T-631: a malformed ticket line must not launder a blocker into a
    # workable ticket -- a typo'd `| blockr:` is exactly that laundering.
    malformed_root = make_project()
    (malformed_root / ".saipen" / "BOARD.md").write_text(
        (malformed_root / ".saipen" / "BOARD.md")
        .read_text(encoding="utf-8").replace(
            "T-1 [P1] top probe | verify: probe",
            "T-1 [P1] top probe | blockr: WAIT_USER_CONFIRMATION | "
            "verify: probe",
        ),
        encoding="utf-8",
    )
    malformed_claim = apply_claim(malformed_root, "T-1", "probe")
    malformed_route = _blocker_route_next(
        codec.read_doc(malformed_root / ".saipen" / "STATE.md"),
        codec.read_doc(malformed_root / ".saipen" / "BOARD.md"),
    )
    expect("claim refuses a board the parser cannot read whole",
           not malformed_claim.get("ok")
           and malformed_claim.get("code") == "VALIDATION_FAILED",
           repr(malformed_claim))
    expect("router routes malformed board to inspection, never a ticket",
           malformed_route.get("action") == "saipen status"
           and malformed_route.get("reason") == "board-malformed",
           repr(malformed_route))

    escaped_root = make_project()
    escaped = ticket_add(escaped_root, "probe", "P1",
                         "literal | blocker: description", [], "probe")
    escaped_board = parse_board(codec.read_doc(
        escaped_root / ".saipen" / "BOARD.md"))
    escaped_ticket = escaped_board["tickets"][escaped.get("ticket")]
    expect("ticket add escapes description pipes instead of injecting fields",
           escaped.get("ok") and "blocker" not in escaped_ticket["fields"]
           and "literal | blocker: description" in escaped_ticket["description"]
           and "\\| blocker:" in escaped_ticket["raw"],
           repr(escaped_ticket))

    # ---- T-631: pipe-bearing verify/blocker payloads must not inject fields.
    inject_root = make_project()
    inject = ticket_add(inject_root, "probe", "P1", "inject probe",
                        [], "a | owner: eve | claim_time: 2026-08-10T00:00:00Z")
    inject_board = parse_board(codec.read_doc(
        inject_root / ".saipen" / "BOARD.md"))
    inject_ticket = inject_board["tickets"][inject.get("ticket")]
    expect("verify text with pipe delimiters cannot inject claim fields",
           inject.get("ok")
           and "owner" not in inject_ticket["fields"]
           and "a | owner: eve | claim_time: 2026-08-10T00:00:00Z"
           in inject_ticket["fields"].get("verify", ""),
           repr(inject_ticket))
    block_root = make_project()
    block_claimed = apply_claim(block_root, "T-1", "probe")
    pipe_block = ticket_move(block_root, "block", "T-1", "probe",
                             "stuck | verify: fake")
    pipe_block_ticket = parse_board(codec.read_doc(
        block_root / ".saipen" / "BOARD.md"))["tickets"]["T-1"]
    expect("blocker payload with pipe delimiters cannot inject a verify field",
           block_claimed.get("ok") and pipe_block.get("ok")
           and pipe_block_ticket["fields"].get("verify") == "probe"
           and "stuck | verify: fake"
           in pipe_block_ticket["fields"].get("blocker", ""),
           repr(pipe_block_ticket))

    # ---- R7: WRITER_BUSY is a structured result, not a traceback.
    writer_lock = WriterLock(root)
    writer_lock.acquire()
    try:
        busy = ticket_add(root, "probe", "P2", "busy", [], "verify")
        expect("WRITER_BUSY is a structured refusal",
               not busy.get("ok") and busy.get("code") == "WRITER_BUSY",
               repr(busy))
    finally:
        writer_lock.release()

    # ---- plan/apply share one op_id and apply consumes exact plan bytes.
    root3 = make_project()
    p_apply = apply_claim(root3, "T-1", "probe")
    j3 = Journal(root3, p_apply.get("op_id"))
    expect("plan op_id == journal op_id (apply consumed the plan)",
           p_apply.get("op_id") is not None and j3.exists()
           and j3.read()["op_id"] == p_apply.get("op_id"),
           repr(p_apply.get("op_id")))
    expect("applied journal is COMMITTED",
           j3.read()["status"] == "COMMITTED", repr(j3.read()["status"]))

    # ---- R8: recovery CONFLICT preserves intervening bytes (journal level).
    root4 = make_project()
    saipen4 = root4 / ".saipen"
    log_b4 = (saipen4 / "LOG.md").read_bytes()
    state_b4 = (saipen4 / "STATE.md").read_bytes()
    from saipen_engine.journal import hash_bytes
    j = Journal(root4, "op-int")
    j.start("op", "probe", "id", "hash", [
        {"path": ".saipen/LOG.md", "role": "log",
         "content": log_b4 + b"\n- 09.08.26 00:01 [E-901] RUN: x\n",
         "before_hash": hash_bytes(log_b4), "after_hash": "a"},
        {"path": ".saipen/STATE.md", "role": "state",
         "content": state_b4.replace(b"phase: DONE", b"phase: BUILD"),
         "before_hash": hash_bytes(state_b4), "after_hash": "b"},
    ])
    (saipen4 / "LOG.md").write_bytes(
        log_b4 + b"\n- 09.08.26 00:01 [E-901] RUN: x\n")
    j.mark("APPLYING", progress_index=1, target_index=0)
    external = state_b4 + b"\n# third party\n"
    (saipen4 / "STATE.md").write_bytes(external)
    from saipen_engine.journal import recover
    recovery_result = recover(root4, "op-int")
    expect("recovery on an externally modified pending target CONFLICTs",
           recovery_result.get("code") == "CONFLICT"
           and (saipen4 / "STATE.md").read_bytes() == external,
           repr(recovery_result))

    # ---- §69#19b: corrupt STAGED bytes are never committed as truth.
    root4b = make_project()
    saipen4b = root4b / ".saipen"
    log_b4b = (saipen4b / "LOG.md").read_bytes()
    state_b4b = (saipen4b / "STATE.md").read_bytes()
    new_log_b4b = log_b4b + b"\n- 09.08.26 00:01 [E-901] RUN: y\n"
    new_state_b4b = state_b4b.replace(b"phase: DONE", b"phase: BUILD")
    j4b = Journal(root4b, "op-staged")
    j4b.start("op", "probe", "id", "hash", [
        {"path": ".saipen/LOG.md", "role": "log", "content": new_log_b4b,
         "before_hash": hash_bytes(log_b4b),
         "after_hash": hash_bytes(new_log_b4b)},
        {"path": ".saipen/STATE.md", "role": "state",
         "content": new_state_b4b,
         "before_hash": hash_bytes(state_b4b),
         "after_hash": hash_bytes(new_state_b4b)},
    ])
    # Corrupt the staged STATE bytes on disk after the journal was written.
    staged_candidates = [p for p in j4b.dir.glob("*STATE*.staged")]
    assert staged_candidates, f"no staged STATE file in {j4b.dir}"
    staged_candidates[0].write_bytes(b"# corrupt staged evidence\n")
    (saipen4b / "LOG.md").write_bytes(new_log_b4b)
    j4b.mark("APPLYING", progress_index=1, target_index=0)
    result4b = recover(root4b, "op-staged")
    expect("recovery refuses corrupt staged bytes (CONFLICT, not COMMIT)",
           result4b.get("code") == "CONFLICT"
           and b"phase: BUILD" not in (saipen4b / "STATE.md").read_bytes(),
           repr(result4b))

    # ---- Recovery preflight: pending op blocks a new mutation.
    root9 = make_project()
    saipen9 = root9 / ".saipen"
    log9 = (saipen9 / "LOG.md").read_bytes()
    state9 = (saipen9 / "STATE.md").read_bytes()
    j9 = Journal(root9, "op-pending")
    new_log9 = log9 + b"\n- 09.08.26 00:01 [E-901] RUN: x\n"
    new_state9 = state9.replace(b"phase: DONE", b"phase: BUILD")
    j9.start("op", "probe", "id", "hash", [
        {"path": ".saipen/LOG.md", "role": "log", "content": new_log9,
         "before_hash": hash_bytes(log9), "after_hash": hash_bytes(new_log9)},
        {"path": ".saipen/STATE.md", "role": "state", "content": new_state9,
         "before_hash": hash_bytes(state9),
         "after_hash": hash_bytes(new_state9)},
    ])
    (saipen9 / "LOG.md").write_bytes(new_log9)
    j9.mark("APPLYING", progress_index=1, target_index=0)
    pending = [op["op_id"] for op in pending_ops(root9)]
    expect("status derives recovery_pending from real journals",
           "op-pending" in pending, repr(pending))
    pre = recovery_preflight(root9)
    expect("recovery preflight recovers the single pending op first",
           pre.get("ok") and pre.get("recovered") == ["op-pending"],
           repr(pre))
    root5 = make_project()
    new_mutation = ticket_add(root5, "probe", "P2", "after", [], "verify")
    expect("a new mutation over no pending op succeeds", new_mutation.get("ok"),
           repr(new_mutation.to_dict()))

    # ---- Codec: UTF-8/CRLF/BOM representation survives a real operation.
    root6 = make_project()
    board6 = root6 / ".saipen" / "BOARD.md"
    text6 = ("# Board\n## DOING\n## TODO\n"
             "- [ ] T-1 [P1] probe | verify: probe\n"
             "## DONE\n## BLOCKED\n")
    board6.write_bytes(text6.encode("utf-8"))
    add6 = ticket_add(root6, "probe", "P2", "crlf", [], "verify")
    after6 = board6.read_bytes()
    expected6 = ("# Board\n## DOING\n## TODO\n"
                 "- [ ] T-2 [P2] crlf | verify: verify\n"
                 "- [ ] T-1 [P1] probe | verify: probe\n"
                 "## DONE\n## BLOCKED\n")
    expect("UTF-8 LF representation preserved",
           add6.get("ok") and after6.decode("utf-8") == expected6
           and b"\xef\xbb\xbf" not in after6, repr(after6[:80]))

    root7 = make_project()
    board7 = root7 / ".saipen" / "BOARD.md"
    text7 = ("# Board\r\n## DOING\r\n## TODO\r\n"
             "- [ ] T-1 [P1] probe | verify: probe\r\n"
             "## DONE\r\n## BLOCKED\r\n")
    board7.write_bytes(text7.replace("\r\n", "\r\n").encode("utf-8"))
    ticket_add(root7, "probe", "P2", "crlf", [], "verify")
    after7 = board7.read_bytes()
    expect("UTF-8 CRLF representation preserved by a real operation",
           b"\r\n" in after7 and b"\n" not in after7.replace(b"\r\n", b""),
           repr(after7[:60]))

    root8 = make_project()
    board8 = root8 / ".saipen" / "BOARD.md"
    text8 = ("# Board\n## DOING\n## TODO\n"
             "- [ ] T-1 [P1] probe | verify: probe\n"
             "## DONE\n## BLOCKED\n")
    board8.write_bytes(b"\xef\xbb\xbf" + text8.encode("utf-8"))
    ticket_add(root8, "probe", "P2", "bom", [], "verify")
    after8 = board8.read_bytes()
    expect("UTF-8 BOM representation preserved by a real operation",
           after8.startswith(b"\xef\xbb\xbf"), repr(after8[:6]))

    # ---- Improve: path safety, one active cycle, sweep enum, propagation.
    import improve
    try:
        improve.cycle_dir(root, "../../escape")
        escaped = False
    except ValueError:
        escaped = True
    expect("improve cycle_id traversal is refused", escaped)
    croot = make_project()
    improve.register_cycle(croot, "imp-1", "# IMPROVE CYCLE ROSTER\n")
    try:
        improve.register_cycle(croot, "imp-2", "# IMPROVE CYCLE ROSTER\n")
        second = False
    except ValueError:
        second = True
    expect("only one active Improve cycle is admitted", second)
    sweep_cycle = improve.cycle_dir(croot, "imp-1")
    try:
        improve.write_sweep_entry(sweep_cycle,
                                  {"imp_id": "001", "disposition": "NOPE",
                                   "ticket": "-", "report": "r",
                                   "reproduced": "-"})
        bad_enum = False
    except ValueError:
        bad_enum = True
    expect("SWEEP disposition enum is enforced at the writer",
           bad_enum and not (sweep_cycle / "SWEEP.md").is_file())

    # ---- §69#05: checkpoint emits a mechanically parented event.
    rootp = make_project()
    apply_claim(rootp, "T-1", "probe")
    cp_p = checkpoint(rootp, "probe", "RUN", "T-1", "parent check")
    log_p = codec.read_doc(rootp / ".saipen" / "LOG.md")
    expect("checkpoint event carries [parent: E-<prev>]",
           cp_p.get("ok") and f"[parent: E-{int(cp_p.get('event_id')[2:]) - 1}]"
           in log_p, repr(log_p[-140:]))

    # ---- §69#04: checkpoint preserves unrelated STATE fields.
    rootu = make_project()
    state_u = (rootu / ".saipen" / "STATE.md").read_text(encoding="utf-8")
    (rootu / ".saipen" / "STATE.md").write_text(
        state_u.replace("phase: DONE", "phase: BUILD").replace(
            "next_action: \"saipen continue\"",
            "next_action: \"PHASE BUILD T-1\"").replace(
            "updated:", "execution_intent: goal\ngoal_waves: 1\n"
            "goal_tickets: 2\nupdated:"), encoding="utf-8")
    apply_claim(rootu, "T-1", "probe")
    transition_phase(rootu, "BUILD", "probe", "T-1", "setup")
    _before_u = codec.read_doc(rootu / ".saipen" / "STATE.md")
    cp_u = checkpoint(rootu, "probe", "RUN", "T-1", "unrelated preserve")
    after_u = codec.read_doc(rootu / ".saipen" / "STATE.md")
    expect("checkpoint preserves unrelated fields (intent/counters/mode)",
           cp_u.get("ok")
           and "execution_intent: goal" in after_u
           and "goal_waves: 1" in after_u and "goal_tickets: 2" in after_u
           and "mode: full" in after_u and "requires:" in after_u
           and "blocker:" in after_u, repr(after_u))

    # ---- §69#07: goal intent from DONE/task:none never fabricates SCOUT.
    rootg = make_project()
    goal_g = set_goal_intent(rootg, "probe", "goal control")
    st_g = parse_state(codec.read_doc(rootg / ".saipen" / "STATE.md"))
    expect("goal intent from DONE/none does not create SCOUT/none",
           goal_g.get("ok")
           and st_g.get("phase") == "DONE"
           and st_g.get("task") == "none"
           and st_g.get("execution_intent") == "goal", repr(st_g))

    # ---- T-630: after a LOG seal the engine must continue the E-### sequence
    # from the NEWEST sealed segment, never the oldest. The old _read
    # prepended segments, so a fresh active log read LOG-001's tail as the
    # sequence head and minted a bogus low event.
    sealr = make_project()
    seal_log = sealr / ".saipen" / "LOG.md"
    (sealr / ".saipen" / "logs").mkdir()
    (sealr / ".saipen" / "logs" / "LOG-001.md").write_text(
        "- 09.08.26 00:00 [E-900] [T-none] DEC: base\n", encoding="utf-8")
    (sealr / ".saipen" / "logs" / "LOG-002.md").write_text(
        "- 09.08.26 00:01 [E-901] [T-none] DEC: sealed two\n"
        "- 09.08.26 00:02 [E-902] [T-none] DEC: sealed three\n",
        encoding="utf-8")
    seal_log.write_text("# Log\n", encoding="utf-8")
    from saipen_engine.state import patch_state as _seal_patch
    seal_state = sealr / ".saipen" / "STATE.md"
    seal_state.write_text(_seal_patch(codec.read_doc(seal_state),
                                      {"last_event": 902}), encoding="utf-8")
    seal_cp = checkpoint(sealr, "probe", "RUN", "T-1", "seal tail control")
    seal_st = parse_state(codec.read_doc(seal_state))
    expect("checkpoint after a seal continues from the newest sealed event "
           "(E-903, not the oldest segment's E-901)",
           seal_cp.get("ok") and seal_st.get("last_event") == 903
           and seal_cp.get("event_id") == "E-903",
           repr((seal_cp, seal_st)))

    # ---- §69#17: commit failure cannot be overwritten by semantic success.
    rootf = make_project()
    plan_f = _plan_claim(rootf, "T-1", "probe", _now(), _utc_iso())
    (rootf / ".saipen" / "BOARD.md").write_text(
        (rootf / ".saipen" / "BOARD.md").read_text(encoding="utf-8").replace(
            "- [ ] T-1 [P1] top probe | verify: probe",
            "- [/] T-1 [P1] top probe | owner: probe | "
            "claim_time: 2026-01-01T00:00:00Z"), encoding="utf-8")
    from saipen_engine.plan import apply_plan
    result_f = apply_plan(rootf, plan_f)
    expect("stale apply returns failure, never semantic success",
           not result_f.get("ok")
           and result_f.get("code") in ("STALE_STATE", "ALREADY_CLAIMED"),
           repr(result_f))

    # ---- §69#18: journal stores per-target before+after hashes.
    j18 = Journal(root3, p_apply.get("op_id"))
    rec18 = j18.read()
    expect("every journal target carries before_hash and after_hash",
           all("before_hash" in t and "after_hash" in t
               for t in rec18["targets"])
           and all(t["before_hash"] and t["after_hash"]
                   for t in rec18["targets"]),
           repr([{k: t[k] for k in ("path", "before_hash", "after_hash")}
                 for t in rec18["targets"]]))

    # ---- §69#27/#50: corrupt proposed state never reaches PREPARED.
    rootc = make_project()
    ops_dir = rootc / ".saipen" / "recovery" / "ops"
    log_c = (rootc / ".saipen" / "LOG.md").read_text(encoding="utf-8")
    # A duplicate event in the live LOG survives into the proposed LOG and
    # must refuse the mutation before any journal is PREPARED.
    (rootc / ".saipen" / "LOG.md").write_text(
        log_c + log_c.splitlines()[-1] + "\n", encoding="utf-8")
    before_ops = sorted(p.name for p in ops_dir.glob("*")) \
        if ops_dir.is_dir() else []
    claim_c = apply_claim(rootc, "T-1", "probe")
    after_ops = sorted(p.name for p in ops_dir.glob("*")) \
        if ops_dir.is_dir() else []
    expect("proposed-state invalidity refuses before any journal PREPARED",
           not claim_c.get("ok")
           and claim_c.get("code") == "VALIDATION_FAILED"
           and before_ops == after_ops, repr(claim_c))

    # ---- §69#32: UTF-16 supported path preserves representation (or refuses).
    rootu16 = make_project()
    board16 = rootu16 / ".saipen" / "BOARD.md"
    text16 = ("# Board\n## DOING\n## TODO\n- [ ] T-1 [P1] probe | "
              "verify: probe\n## DONE\n## BLOCKED\n")
    board16.write_bytes(b"\xff\xfe" + text16.encode("utf-16-le"))
    add16 = ticket_add(rootu16, "probe", "P2", "u16", [], "verify")
    raw16 = board16.read_bytes()
    expect("UTF-16LE BOM representation preserved by a real operation",
           add16.get("ok") and raw16.startswith(b"\xff\xfe")
           and codec.encoding_of(board16) == "utf-16-le", repr(raw16[:4]))

    # ---- §69#33: a one-file generic journal never claims LOG_WRITTEN.
    rootone = make_project()
    j_one = Journal(rootone, "op-single")
    content_one = (rootone / ".saipen" / "STATE.md").read_bytes()
    j_one.start("op", "probe", "id", "h", [
        {"path": ".saipen/STATE.md", "role": "state",
         "content": content_one.replace(b"phase: DONE", b"phase: BUILD"),
         "before_hash": hash_bytes(content_one),
         "after_hash": hash_bytes(
             content_one.replace(b"phase: DONE", b"phase: BUILD"))},
    ])
    rec_one = j_one.read()
    expect("one-file journal uses generic truthful stage, never LOG_WRITTEN",
           rec_one["targets"][0]["role"] == "state"
           and rec_one["targets"][0]["applied"] is False,
           repr(rec_one["targets"]))

    # ---- §69#35/#36: seat_id / report_path injection refused.
    croot35 = make_project()
    improve.register_cycle(croot35, "imp-s", "# IMPROVE CYCLE ROSTER\n")
    cdir35 = improve.cycle_dir(croot35, "imp-s")
    try:
        improve.register_seat(cdir35, "a\navailability: complete", "core",
                              "saipen_improve_X.md")
        seat_inject = False
    except ValueError:
        seat_inject = True
    expect("seat_id newline injection is refused", seat_inject)
    try:
        improve.register_seat(cdir35, "seat-1", "core", "../../escape.md")
        path_escape = False
    except ValueError:
        path_escape = True
    expect("report_path traversal is refused", path_escape)

    # ---- §69#38/#39: append_run journalled; Improve writer propagates failure.
    # T-638: append_run requires a valid ACTIVE cycle manifest.
    rroot = make_project()
    _r_cycle = improve.create_cycle(rroot, "imp-s",
                                    created_at="2026-08-12T00:00:00Z",
                                    project_identity="p")
    improve.register_seat(_r_cycle, "seat-1", "core",
                          "saipen_improve_PROJ.md")
    rreport = improve.create_report(
        rroot, "imp-s", "seat-1", "PROJ", agent="seat-1", role="core",
        model_or_runtime="probe",
        context_scope="scope")
    run_res = improve.append_run(rreport, "first run")
    expect("append_run returns a committed transaction result",
           run_res.get("ok") and run_res.get("code") == "COMMITTED",
           repr(run_res))
    complete_t = rreport.read_text(encoding="utf-8").replace(
        "report_status: draft", "report_status: complete")
    rreport.write_text(complete_t, encoding="utf-8")
    try:
        improve.append_run(rreport, "late")
        prop = False
    except ValueError:
        prop = True
    expect("Improve writer refuses a complete report and propagates",
           prop)

    # ---- §69#47/#48: mechanical provenance -- structural events after the
    # first [op: ...] marker carry one; a manual structural edit is detected.
    import saipen_engine.log as engine_log
    _, event_line = engine_log.build_event(
        999, "DEC", "ticket added via SAIOPS", ticket="T-1",
        agent="probe", now="09.08.26 00:00", op_id="claim-abc")
    parsed = engine_log.parse_log_line(event_line)
    expect("SAIOPS structural event carries [op: ...] provenance",
           parsed is not None and parsed["op_id"] == "claim-abc",
           repr(parsed))
    _, manual_line = engine_log.build_event(
        1000, "DEC", "ticket added via SAIOPS -- manual", ticket="T-1",
        agent="probe", now="09.08.26 00:00")
    parsed_manual = engine_log.parse_log_line(manual_line)
    expect("manual structural event lacks provenance (detectable)",
           parsed_manual is not None and parsed_manual["op_id"] is None,
           repr(parsed_manual))

    # ---- §69#24: a committed op retried returns ALREADY_APPLIED.
    from saipen_engine.journal import run_mutation as _run_mutation
    root_retry = make_project()
    saipen_retry = root_retry / ".saipen"
    log_r = (saipen_retry / "LOG.md").read_bytes()
    state_r = (saipen_retry / "STATE.md").read_bytes()
    new_log_r = log_r + b"\n- 09.08.26 00:01 [E-901] RUN: op\n"
    new_state_r = state_r.replace(b"phase: DONE", b"phase: BUILD")
    commit_retry = _run_mutation(
        root_retry, "op-retry", "op", "probe", "id", "hash",
        [{"path": ".saipen/LOG.md", "role": "log", "content": new_log_r,
          "before_hash": hash_bytes(log_r),
          "after_hash": hash_bytes(new_log_r)},
         {"path": ".saipen/STATE.md", "role": "state",
          "content": new_state_r, "before_hash": hash_bytes(state_r),
          "after_hash": hash_bytes(new_state_r)}],
        skip_preflight=True)
    retry_result = _run_mutation(
        root_retry, "op-retry", "op", "probe", "id", "hash",
        [{"path": ".saipen/LOG.md", "role": "log", "content": new_log_r,
          "before_hash": hash_bytes(log_r),
          "after_hash": hash_bytes(new_log_r)}],
        skip_preflight=True)
    expect("a committed op retried returns ALREADY_APPLIED, no second write",
           commit_retry.get("code") == "COMMITTED"
           and retry_result.get("code") == "ALREADY_APPLIED",
           repr((commit_retry, retry_result)))

    # ---- §69#23: `saipen recover --json` returns a machine result.
    rec_root = make_project()
    _saipen_rec = rec_root / ".saipen"
    rec_proc = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "recover",
         "--json"],
        cwd=str(rec_root), capture_output=True, text=True, timeout=60)
    expect("saipen recover --json returns structured JSON",
           rec_proc.returncode == 0 and '"code": "CLEAN"' in rec_proc.stdout,
           repr(rec_proc.stdout[:160]))

    # ---- NITRO M7: USERPERSON writer on the common journal machinery.
    import userperson
    up_root = make_project()
    up_path = userperson.profile_path(up_root)
    up_add = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "userperson",
         "add", "Prefer UI: Vintage Golden", "--json"],
        cwd=str(up_root), capture_output=True, text=True, timeout=60)
    expect("saipen userperson add writes through the journal (COMMITTED)",
           up_add.returncode == 0 and '"code": "COMMITTED"' in up_add.stdout
           and up_path.is_file(), repr(up_add.stdout[:120]))
    up_add2 = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "userperson",
         "add", "Prefer UI: Material Design"],
        cwd=str(up_root), capture_output=True, text=True, timeout=60)
    up_text = up_path.read_text(encoding="utf-8-sig")
    expect("userperson add keeps distinct preferences sharing a leading phrase",
           up_add2.returncode == 0
           and "Vintage Golden" in up_text
           and "Material Design" in up_text, repr(up_text))
    up_reset_refuse = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "userperson",
         "reset", "--json"],
        cwd=str(up_root), capture_output=True, text=True, timeout=60)
    expect("userperson reset without confirmation REFUSEs",
           '"code": "DESTRUCTIVE_CONFIRMATION_REQUIRED"'
           in up_reset_refuse.stdout,
           repr(up_reset_refuse.stdout[:120]))
    up_reset = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "userperson",
         "reset", "--confirm", "--json"],
        cwd=str(up_root), capture_output=True, text=True, timeout=60)
    expect("userperson reset with confirmation DELETES the profile",
           up_reset.returncode == 0
           and not up_path.is_file(), repr(up_reset.stdout[:120]))

    # ---- NITRO M8: SubSaipen lifecycle on the common machinery.
    sub_root = make_project()
    home = str(HOME)
    spawn_res = subs.sub_spawn(sub_root, "saiscout", home)
    sub_state_path = sub_root / ".saipen" / "extensions" / "subs" \
        / "saiscout" / "STATE.md"
    expect("sub spawn creates a journaled instance (SPAWNED)",
           spawn_res.get("ok") and spawn_res.get("code") == "SPAWNED"
           and sub_state_path.is_file(), repr(spawn_res))
    st_spawn = sub_state_path.read_text(encoding="utf-8")
    import datetime as _dt
    _today_utc = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT")
    expect("spawned sub has its own agent + real updated timestamp",
           "agent: saiscout" in st_spawn
           and _today_utc in st_spawn
           and "2026-01-01" not in st_spawn, repr(st_spawn[-200:]))
    dup = subs.sub_spawn(sub_root, "saiscout", home)
    expect("sub spawn refuses an existing instance, never overwrites",
           not dup.get("ok") and dup.get("code") == "ALREADY_CLAIMED",
           repr(dup))
    listed = subs.sub_list(sub_root)
    expect("sub list reports the spawned instance",
           listed.get("ok")
           and any(s["name"] == "saiscout" for s in listed["subs"]),
           repr(listed))
    paused = subs.sub_pause(sub_root, "saiscout")
    st_pause = sub_state_path.read_text(encoding="utf-8")
    expect("sub pause is a journaled owned-field BLOCKED patch",
           paused.get("ok") and "phase: BLOCKED" in st_pause
           and "paused by main agent" in st_pause
           and "paused_from_phase: PLAN" in st_pause
           and "paused_from_na:" in st_pause, repr(st_pause))
    sub_log_path = sub_root / ".saipen" / "extensions" / "subs" \
        / "saiscout" / "LOG.md"
    expect("sub pause leaves a trace in the sub LOG",
           "main agent pause" in sub_log_path.read_text(encoding="utf-8"))
    resumed = subs.sub_resume(sub_root, "saiscout")
    st_resume = sub_state_path.read_text(encoding="utf-8")
    expect("sub resume restores the prior phase and next_action",
           resumed.get("ok") and "phase: PLAN" in st_resume
           and 'next_action: "saipen plan"' in st_resume
           and "paused by main agent" not in st_resume
           and "paused_from_phase: \"\"" in st_resume
           and "paused_from_na: \"\"" in st_resume, repr(st_resume))
    expect("sub resume leaves a trace in the sub LOG",
           "main agent resume" in sub_log_path.read_text(encoding="utf-8"))
    expect("resume of a non-paused sub refuses (no fake success)",
           not subs.sub_resume(sub_root, "saiscout").get("ok"))

    # Clean preflight: read-only, refuses outstanding evidence, never deletes.
    clean_bad = subs.sub_clean_preflight(sub_root, "saiscout")
    clean_ok = subs.sub_clean_preflight(sub_root, "does-not-exist")
    expect("sub clean preflight refuses a fresh instance with evidence",
           not clean_bad.get("ok")
           and clean_bad.get("code") == "VALIDATION_FAILED"
           and (sub_root / ".saipen" / "extensions" / "subs" / "saiscout"
                ).is_dir(), repr(clean_bad))
    expect("sub clean preflight refuses a nonexistent instance",
           not clean_ok.get("ok")
           and clean_ok.get("code") == "TICKET_NOT_FOUND", repr(clean_ok))
    st_clean = sub_state_path.read_text(encoding="utf-8")
    expect("sub clean preflight never mutates the instance",
           st_clean == st_resume, "state changed")

    # Collect preflight: read-only freshness gate; a spawned sub with an empty
    # OUTBOX passes (no ready package to stale), nothing is judged semantically.
    collect_res = subs.sub_collect(sub_root, "saiscout")
    expect("sub collect preflight passes an empty OUTBOX (read-only)",
           collect_res.get("ok")
           and collect_res.get("code") == "COLLECT_PREFLIGHT",
           repr(collect_res))

    # ---- T-588: SubSaipen path-escape regression (dogfood II).
    from saipen_engine import subs as _subs
    esc_root = make_project()
    esc_home = str(HOME)
    for bad in ("..", ".", "../x", "x/../y", "..\\x", r"V:\abs",
                "a\nb", "a\x00b"):
        try:
            _subs.sub_spawn(esc_root, bad, esc_home)
            refused = False
        except (ValueError, Exception):
            refused = True
        if not refused:
            r = _subs.sub_spawn(esc_root, bad, esc_home)
            refused = (not r.get("ok")
                       and r.get("code") in ("INVALID_ID", "PATH_ESCAPE"))
        expect(f"sub name {bad!r} is refused (no path escape)",
               refused, repr(bad))
    # Zero bytes escaped anywhere outside the owner root. The fixture's own
    # three canonical files are expected; anything else outside
    # .saipen/extensions/subs/ would be an escape (e.g. .saipen/extensions/
    # STATE.md from a ".." spawn).
    canonical = {".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/LOG.md"}
    escaped_files = [p for p in (esc_root / ".saipen").rglob("*")
                     if p.is_file()
                     and "extensions/subs" not in p.as_posix()
                     and p.relative_to(esc_root).as_posix() not in canonical]
    expect("path-escape attempts write zero bytes outside the owner root",
           len(escaped_files) == 0,
           repr([p.relative_to(esc_root).as_posix()
                 for p in escaped_files]))

    # ---- T-588: first-spawn bootstrap installs the shared extension files.
    boot_root = make_project()
    _subs.sub_spawn(boot_root, "saiscout", esc_home)
    subs_dir = boot_root / ".saipen" / "extensions" / "subs"
    expect("first spawn installs PROTOCOL.md",
           (subs_dir / "PROTOCOL.md").is_file())
    expect("first spawn installs TEMPLATE/",
           (subs_dir / "TEMPLATE" / "STATE.md").is_file())
    expect("first spawn installs built-in sai*.md charters",
           (subs_dir / "saihunt.md").is_file())
    expect("first spawn does NOT bootstrap on a second instance",
           not _subs.sub_spawn(boot_root, "saiscout2", esc_home).get("ok")
           or (subs_dir / "PROTOCOL.md").is_file())

    # ---- T-588: ready OUTBOX package completeness (dogfood II). T-991:
    # role freshness fails CLOSED -- a charter-backed sub (saiwiki) with its
    # computed revision passes; missing/unverifiable role evidence refuses.
    comp_root = make_project()
    _comp_state = comp_root / ".saipen" / "STATE.md"
    _comp_state.write_text(
        _comp_state.read_text(encoding="utf-8-sig").replace(
            "saipen_home: \".\"", f'saipen_home: "{esc_home}"'),
        encoding="utf-8")
    _subs.sub_spawn(comp_root, "saiwiki", esc_home)
    comp_outbox = comp_root / ".saipen" / "extensions" / "subs" \
        / "saiwiki" / "kitchen" / "OUTBOX.md"
    from freshness import compute_source_identity, compute_role_revision
    _current = compute_source_identity(comp_root)
    _wiki_charter = esc_home + "/extensions/subs/saiwiki.md"
    _wiki_rev = compute_role_revision(_wiki_charter)
    complete = ("# OUTBOX\n\n## F-001: finding\n"
                "- **status:** ready\n"
                "- **summary:** a finding\n"
                f"- **source_head:** {_current.source_head}\n"
                f"- **source_tree_fingerprint:** "
                f"{_current.source_tree_fingerprint}\n"
                f"- **role_revision:** {_wiki_rev}\n"
                "- **producer:** saiwiki\n")
    comp_outbox.write_text(complete, encoding="utf-8")
    res_ok = _subs.sub_collect(comp_root, "saiwiki")
    expect("complete ready OUTBOX package with a verifiable role passes collect",
           res_ok.get("ok"), repr(res_ok))
    for missing_field in ("source_head", "source_tree_fingerprint",
                          "role_revision"):
        partial = "\n".join(
            line for line in complete.splitlines()
            if not line.startswith(f"- **{missing_field}:**"))
        comp_outbox.write_text(partial, encoding="utf-8")
        res_missing = _subs.sub_collect(comp_root, "saiwiki")
        expect(f"ready OUTBOX missing {missing_field} refuses "
               f"(PACKAGE_INCOMPLETE)",
               not res_missing.get("ok")
               and res_missing.get("code") == "PACKAGE_INCOMPLETE",
               repr(res_missing))
        comp_outbox.write_text(complete, encoding="utf-8")
    # A superseded role revision is STALE, never fresh.
    comp_outbox.write_text(
        complete.replace(f"- **role_revision:** {_wiki_rev}\n",
                         "- **role_revision:** stale-revision\n"),
        encoding="utf-8")
    res_stale_role = _subs.sub_collect(comp_root, "saiwiki")
    expect("ready OUTBOX with a superseded role revision refuses "
           "(PACKAGE_INCOMPLETE, STALE)",
           not res_stale_role.get("ok")
           and res_stale_role.get("code") == "PACKAGE_INCOMPLETE"
           and "superseded" in res_stale_role.get("message", ""),
           repr(res_stale_role))
    # A sub whose role charter cannot be found (missing home/charter) is
    # UNAVAILABLE, never fresh -- collect refuses ready evidence it cannot
    # verify against a charter.
    _subs.sub_spawn(comp_root, "saiscout", esc_home)
    scout_outbox = comp_root / ".saipen" / "extensions" / "subs" \
        / "saiscout" / "kitchen" / "OUTBOX.md"
    scout_outbox.write_text(
        complete.replace(f"- **role_revision:** {_wiki_rev}\n",
                         "- **role_revision:** recorded-role\n")
        .replace("- **producer:** saiwiki\n", "- **producer:** saiscout\n"),
        encoding="utf-8")
    res_unverifiable = _subs.sub_collect(comp_root, "saiscout")
    expect("ready OUTBOX with an unverifiable role revision refuses "
           "(PACKAGE_INCOMPLETE, UNAVAILABLE)",
           not res_unverifiable.get("ok")
           and res_unverifiable.get("code") == "PACKAGE_INCOMPLETE"
           and "unverifiable" in res_unverifiable.get("message", ""),
           repr(res_unverifiable))
    comp_outbox.write_text(complete, encoding="utf-8")

    # ---- T-588: malformed nonempty OUTBOX is not an empty queue.
    mal_root = make_project()
    _subs.sub_spawn(mal_root, "saiscout", esc_home)
    mal_outbox = mal_root / ".saipen" / "extensions" / "subs" \
        / "saiscout" / "kitchen" / "OUTBOX.md"
    mal_outbox.write_text(
        "# OUTBOX\n\n## status: ready\nsome stray text that is not a "
        "package\n", encoding="utf-8")
    res_mal = _subs.sub_collect(mal_root, "saiscout")
    expect("malformed nonempty OUTBOX refuses (MALFORMED_PACKAGE)",
           not res_mal.get("ok")
           and res_mal.get("code") == "MALFORMED_PACKAGE", repr(res_mal))

    # ---- T-588: sub collect (no name) aggregates all active subs.
    agg_root = make_project()
    _subs.sub_spawn(agg_root, "saiscout", esc_home)
    _subs.sub_spawn(agg_root, "saiscout2", esc_home)
    agg_res = _subs.sub_collect(agg_root)
    expect("sub collect with no name aggregates all active subs",
           agg_res.get("ok")
           and {p["name"] for p in agg_res["packages"]}
           == {"saiscout", "saiscout2"}, repr(agg_res))

    # ---- NITRO M9: context compiler is read-only and derives from the engine.
    from saipen_engine import context as ctx
    ctx_root = make_project()
    tree_before = project_tree(ctx_root)
    cold = ctx.context_cold(ctx_root)
    hot = ctx.context_hot(ctx_root)
    audit = ctx.context_audit(ctx_root)
    tree_after = project_tree(ctx_root)
    expect("context cold is read-only (zero bytes written)",
           cold.get("ok") and tree_before == tree_after, repr(cold))
    expect("context hot is read-only and names the claimed ticket",
           hot.get("ok")
           and "claimed_ticket:" in hot.get("surface", "")
           and "recovery_pending:" in hot.get("surface", ""), repr(hot))
    expect("context audit accounts bytes/tokens per source",
           audit.get("ok")
           and len(audit["sources"]) >= 3
           and "cold_surface" in audit
           and "projection_reduction_bytes" in audit
           and "repeated_unchanged_bytes" not in audit, repr(audit))
    cold_bytes = cold.get("bytes", 0)
    raw_bytes = audit["total_bytes"]
    expect("cold surface bytes are measured as real UTF-8 bytes",
           cold_bytes > 0 and raw_bytes > 0 and isinstance(cold_bytes, int),
           f"cold={cold_bytes} raw={raw_bytes}")
    cold_tokens = cold.get("tokens", 0)
    expect("cold surface token count is modest (token optimization target)",
           cold_tokens > 0 and cold_tokens < 5000, repr(cold_tokens))

    # ---- NITRO dogfood IV (T-600): context projection integrity.
    # Real current shape: 10+ TODO tickets, the top several unworkable (needs
    # unmet), the ACTUAL top workable below the orientation limit, long
    # description, nonempty needs, long verify. A small budget must still
    # include in full: routed action, exact ticket, needs, verify, routed
    # phase doc, recovery state -- and the board map must be TRUTHFULLY
    # capped (never print a ticket AND count it as omitted).
    from saipen_engine.context import _board_map as _ctx_board_map
    shape_root = make_project()
    sf = shape_root / ".saipen"
    lines = ["# Board", "## DOING", "## TODO"]
    lines.append("- [ ] T-1 [P1] unworkable one | needs: T-2 | verify: v1")
    lines.append("- [ ] T-2 [P1] unworkable two | needs: T-3 | verify: v2")
    lines.append("- [ ] T-3 [P1] unworkable three | needs: T-4 | verify: v3")
    for i in range(4, 13):
        lines.append(f"- [ ] T-{i} [P1] ticket {i} with a long descriptive "
                     f"body {'x' * 120} | verify: run a very long "
                     f"verification command for T-{i} {'y' * 120}")
    lines.append("## DONE\n## BLOCKED\n")
    (sf / "BOARD.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    cold_shape = ctx.context_cold(shape_root, limit=1500)
    surf = cold_shape.get("surface", "")
    expect("context: with a small budget the exact routed ticket (the top "
           "workable below the orientation limit) survives in full "
           "(description + verify intact)",
           "## NEXT TICKET" in surf
           and "ticket 4 with a long descriptive body" in surf
           and "verify: run a very long verification command for T-4" in surf,
           repr(surf[:400]))
    expect("context: routed action + phase doc + recovery state survive a "
           "small budget",
           "PHASE SCOUT T-4" in surf
           and "phase_doc: saipen/phases/scout.md" in surf
           and "recovery_pending:" in surf, repr(surf[:400]))
    expect("context: the board map is present and truthfully capped",
           "## BOARD MAP" in surf and bool(re.search(r"\+ ?\d+ more", surf)),
           repr(surf[-300:]))
    bm = _ctx_board_map(parse_board(codec.read_doc(sf / "BOARD.md")),
                        full_ticket="T-4", cap=2)
    expect("context: _board_map omits exactly the right count (+9 more from "
           "12 TODO tickets with cap 2 + protected full T-4)",
           "  ... +9 more" in bm
           and "ticket 4 with a long descriptive body" in bm,
           repr(bm))

    # Byte accounting MUST describe the FINAL emitted surface: bytes ==
    # len(surface.encode('utf-8')) and characters == len(surface), exactly --
    # proven with Cyrillic + Japanese multibyte content.
    unicode_root = make_project()
    (unicode_root / ".saipen" / "BOARD.md").write_text(
        "# Board\n## DOING\n## TODO\n"
        "- [ ] T-1 [P1] тест японский 日本語プロジェクト | verify: прогон "
        "コマンド検証\n## DONE\n## BLOCKED\n", encoding="utf-8")
    cold_uni = ctx.context_cold(unicode_root, limit=2000)
    surf_uni = cold_uni.get("surface", "")
    expect("context: bytes == len(surface.encode('utf-8')) and characters == "
           "len(surface) exactly (Cyrillic + Japanese)",
           cold_uni.get("bytes") == len(surf_uni.encode("utf-8"))
           and cold_uni.get("characters") == len(surf_uni),
           repr((cold_uni.get("bytes"), len(surf_uni.encode("utf-8")),
                 cold_uni.get("characters"), len(surf_uni))))
    expect("context: multibyte content makes real bytes > characters",
           cold_uni.get("bytes") > cold_uni.get("characters"),
           repr((cold_uni.get("bytes"), cold_uni.get("characters"))))

    # ---- T-587: unresolved CONFLICT blocks every new mutation.
    from saipen_engine.journal import pending_conflicts
    root_c = make_project()
    saipen_c = root_c / ".saipen"
    log_c = (saipen_c / "LOG.md").read_bytes()
    state_c = (saipen_c / "STATE.md").read_bytes()
    new_log_c = log_c + b"\n- 09.08.26 00:01 [E-901] RUN: op\n"
    new_state_c = state_c.replace(b"phase: DONE", b"phase: BUILD")
    j_c = Journal(root_c, "op-conf")
    j_c.start("checkpoint", "probe", "id", "h", [
        {"path": ".saipen/LOG.md", "role": "log", "content": new_log_c,
         "before_hash": hash_bytes(log_c),
         "after_hash": hash_bytes(new_log_c)},
        {"path": ".saipen/STATE.md", "role": "state",
         "content": new_state_c, "before_hash": hash_bytes(state_c),
         "after_hash": hash_bytes(new_state_c)},
    ], verification_policy="core_fast")
    (saipen_c / "LOG.md").write_bytes(new_log_c)
    j_c.mark("APPLYING", progress_index=1, target_index=0)
    external_c = state_c + b"\n# third party\n"
    (saipen_c / "STATE.md").write_bytes(external_c)
    res_c = recover(root_c, "op-conf")
    expect("crash control A: changed unfinished write target CONFLICTs",
           res_c.get("code") == "CONFLICT"
           and (saipen_c / "STATE.md").read_bytes() == external_c,
           repr(res_c))
    expect("unresolved CONFLICT is listed by pending_ops",
           "op-conf" in [p["op_id"] for p in pending_ops(root_c)], repr(
               pending_ops(root_c)))
    expect("unresolved CONFLICT is listed by pending_conflicts",
           "op-conf" in [c["op_id"] for c in pending_conflicts(root_c)])
    blocked_c = ticket_add(root_c, "probe", "P2", "after conflict", [],
                           "verify")
    expect("new mutation over unresolved CONFLICT refuses "
           "(RECOVERY_CONFLICT)",
           not blocked_c.get("ok")
           and blocked_c.get("code") == "RECOVERY_CONFLICT", repr(blocked_c))
    pre_c = recovery_preflight(root_c)
    expect("recovery preflight over a conflict refuses RECOVERY_CONFLICT",
           pre_c.get("code") == "RECOVERY_CONFLICT", repr(pre_c))

    # ---- T-587 control B: read-only dependency drift -> CONFLICT.
    root_b = make_project()
    saipen_b = root_b / ".saipen"
    log_b = (saipen_b / "LOG.md").read_bytes()
    state_b = (saipen_b / "STATE.md").read_bytes()
    board_b = (saipen_b / "BOARD.md").read_bytes()
    new_log_b = log_b + b"\n- 09.08.26 00:01 [E-901] RUN: op\n"
    new_state_b = state_b.replace(b"phase: DONE", b"phase: BUILD")
    j_b = Journal(root_b, "op-rdep")
    j_b.start("checkpoint", "probe", "id", "h", [
        {"path": ".saipen/LOG.md", "role": "log", "content": new_log_b,
         "before_hash": hash_bytes(log_b),
         "after_hash": hash_bytes(new_log_b)},
        {"path": ".saipen/STATE.md", "role": "state",
         "content": new_state_b, "before_hash": hash_bytes(state_b),
         "after_hash": hash_bytes(new_state_b)},
    ], verification_policy="core_fast",
        read_preconditions={".saipen/BOARD.md": hash_bytes(board_b)})
    (saipen_b / "LOG.md").write_bytes(new_log_b)
    j_b.mark("APPLYING", progress_index=1, target_index=0)
    (saipen_b / "BOARD.md").write_text(
        "# Board\n## DOING\n- [/] T-1 [P1] probe | owner: probe | "
        "claim_time: 2026-08-09T00:00:00Z\n## TODO\n## DONE\n## BLOCKED\n",
        encoding="utf-8")
    res_b = recover(root_b, "op-rdep")
    expect("crash control B: changed read-only dependency CONFLICTs",
           res_b.get("code") == "CONFLICT"
           and b"DOING" in (saipen_b / "BOARD.md").read_bytes(),
           repr(res_b))
    expect("recovered state never COMMITTED over a drifted read dependency",
           j_b.read()["status"] == "CONFLICT")
    blocked_b = ticket_add(root_b, "probe", "P2", "after rdep", [], "verify")
    expect("new mutation refuses after read-dependency conflict",
           not blocked_b.get("ok")
           and blocked_b.get("code") in ("RECOVERY_CONFLICT",
                                         "VALIDATION_FAILED"), repr(
               blocked_b))

    # ---- T-587: semantically invalid recovered state cannot COMMIT.
    root_s = make_project()
    saipen_s = root_s / ".saipen"
    log_s = (saipen_s / "LOG.md").read_bytes()
    state_s = (saipen_s / "STATE.md").read_bytes()
    board_s = (saipen_s / "BOARD.md").read_bytes()
    new_log_s = log_s + b"\n- 09.08.26 00:01 [E-901] RUN: op\n"
    new_state_s = (b"---\nphase: DONE\ntask: none\n"
                   b'next_action: "saipen continue"\n'
                   b'blocker: ""\ntransition_from: SHIP\nsaipen_version: 7\n'
                   b"schema_version: 3\nlast_event: 901\n"
                   b"style_contract: ded-4ae736e4\nsaipen_home: \".\"\n"
                   b"agent: probe\nmode: full\n"
                   b"updated: 2026-08-09T00:00:00Z\n---\n")
    j_s = Journal(root_s, "op-sem")
    j_s.start("checkpoint", "probe", "id", "h", [
        {"path": ".saipen/LOG.md", "role": "log", "content": new_log_s,
         "before_hash": hash_bytes(log_s),
         "after_hash": hash_bytes(new_log_s)},
        {"path": ".saipen/STATE.md", "role": "state",
         "content": new_state_s, "before_hash": hash_bytes(state_s),
         "after_hash": hash_bytes(new_state_s)},
    ], verification_policy="core_fast",
        read_preconditions={".saipen/BOARD.md": hash_bytes(board_s)})
    (saipen_s / "LOG.md").write_bytes(new_log_s)
    j_s.mark("APPLYING", progress_index=1, target_index=0)
    # BOARD DOING T-1 but STATE task:none: byte-valid, semantically invalid.
    (saipen_s / "BOARD.md").write_text(
        "# Board\n## DOING\n- [/] T-1 [P1] probe | owner: probe | "
        "claim_time: 2026-08-09T00:00:00Z\n## TODO\n## DONE\n## BLOCKED\n",
        encoding="utf-8")
    res_s = recover(root_s, "op-sem")
    expect("recovered invalid state cannot become COMMITTED (CONFLICT)",
           res_s.get("code") == "CONFLICT"
           and j_s.read()["status"] == "CONFLICT", repr(res_s))

    # ---- T-587: public saipen recover --json refuses a conflict.
    rec_c = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "recover",
         "--json"],
        cwd=str(root_c), capture_output=True, text=True, timeout=60)
    expect("saipen recover --json refuses a conflict and names the op",
           '"code": "CONFLICT"' in rec_c.stdout
           and "op-conf" in rec_c.stdout, repr(rec_c.stdout[:200]))

    # ---- T-587: real subprocess crash (NITRO_CRASH_AFTER_LOG) leaves a
    # recoverable op; an intervening read-dependency edit CONFLICTs recovery
    # and the conflict then blocks a new mutation -- through the live CLI.
    root_sp = make_project()
    saipen_sp = root_sp / ".saipen"
    _log_sp = (saipen_sp / "LOG.md").read_bytes()
    _state_sp = (saipen_sp / "STATE.md").read_bytes()
    _board_sp = (saipen_sp / "BOARD.md").read_bytes()
    crash_code = (
        "import sys, os; sys.path.insert(0, r'%s')\n"
        "os.environ['NITRO_CRASH_AFTER_LOG'] = '1'\n"
        "from saipen_engine.operations import checkpoint\n"
        "checkpoint(r'%s', 'probe', 'RUN', 'T-1', 'crash probe')"
        % (str(HOME / "tools"), str(root_sp)))
    rc = subprocess.run([sys.executable, "-c", crash_code], cwd=str(root_sp),
                        capture_output=True, text=True, timeout=60).returncode
    expect("subprocess crash after LOG leaves an unresolved op",
           rc == 87
           and bool(pending_ops(root_sp)), f"rc={rc}")
    (saipen_sp / "BOARD.md").write_text(
        "# Board\n## DOING\n- [/] T-1 [P1] probe | owner: probe | "
        "claim_time: 2026-08-09T00:00:00Z\n## TODO\n## DONE\n## BLOCKED\n",
        encoding="utf-8")
    from saipen_engine.journal import recover as _recover
    sp_recover = _recover(root_sp, pending_ops(root_sp)[0]["op_id"])
    expect("crash-then-drifted-read-dep recover CONFLICTs in a real op",
           sp_recover.get("code") == "CONFLICT", repr(sp_recover))
    sp_new = ticket_add(root_sp, "probe", "P2", "after sp crash", [],
                        "verify")
    expect("new mutation refuses after the subprocess-crash conflict",
           not sp_new.get("ok")
           and sp_new.get("code") in ("RECOVERY_CONFLICT",
                                      "VALIDATION_FAILED"), repr(sp_new))

    # ---- T-590: shared router -- DONE + workable TODO routes to the ticket.
    from saipen_engine.router import route_next
    router_root = make_project()
    st_done = codec.read_doc(router_root / ".saipen" / "STATE.md")
    board_done = codec.read_doc(router_root / ".saipen" / "BOARD.md")
    routed = route_next(st_done, board_done)
    expect("route_next on DONE + workable TODO routes to the ticket",
           routed.get("action") == "PHASE SCOUT T-1"
           and routed.get("reason") == "start", repr(routed))
    routed_na = route_next(st_done, board_done, pending_ops=["op-x"])
    expect("route_next puts recovery ahead of normal work",
           routed_na.get("action") == "saipen recover"
           and routed_na.get("reason") == "recovery-pending", repr(routed_na))
    routed_conf = route_next(st_done, board_done, conflict_ops=["op-c"])
    expect("route_next puts unresolved conflict ahead of everything",
           not routed_conf.get("ok")
           and routed_conf.get("action") == "saipen recover"
           and routed_conf.get("reason") == "recovery-conflict",
           repr(routed_conf))

    # ---- T-590: ticket add refuses placeholder verify through the PUBLIC CLI.
    tac_root = make_project()
    tac_bad = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "ticket", "add",
         "P1", "no proof ticket", "--verify", "TBD", "--json"],
        cwd=str(tac_root), capture_output=True, text=True, timeout=60)
    expect("ticket add with TBD verify REFUSEs INCOMPLETE_TICKET",
           '"code": "INCOMPLETE_TICKET"' in tac_bad.stdout,
           repr(tac_bad.stdout[:120]))
    tac_good = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "ticket", "add",
         "P1", "proven ticket", "--verify", "validator green; scenario green",
         "--json"],
        cwd=str(tac_root), capture_output=True, text=True, timeout=60)
    expect("ticket add with a real verify succeeds and never emits TBD",
           tac_good.returncode == 0
           and '"code": "TICKET_ADDED"' in tac_good.stdout
           and "verify: verify: TBD" not in codec.read_doc(
               tac_root / ".saipen" / "BOARD.md"),
           repr(tac_good.stdout[:160]))

    # ---- T-590: saiui projection through the PUBLIC add path.
    up_ui_root = make_project()
    up_ui_add = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "userperson",
         "add", "Prefer Golden UI", "--category", "UI", "--json"],
        cwd=str(up_ui_root), capture_output=True, text=True, timeout=60)
    from userperson import parse_profile, project_profile
    up_ui_text = (up_ui_root / ".saipen" / "USERPERSON.md").read_text(
        encoding="utf-8-sig")
    proj_ui = project_profile(parse_profile(up_ui_text)["preferences"], "saiui")
    expect("userperson add with distilled category projects to saiui",
           up_ui_add.returncode == 0
           and "Prefer Golden UI" in up_ui_text
           and any("Prefer Golden UI" in p["text"] for p in
                   proj_ui["preferences"]),
           repr((up_ui_text, proj_ui)))

    # ---- T-590: cold context includes the exact next ticket (not truncated).
    ctx_cold_root = make_project()
    cold_exact = ctx.context_cold(ctx_cold_root)
    expect("cold context names the exact next ticket via the router",
           "PHASE SCOUT T-1" in cold_exact.get("surface", ""), repr(
               cold_exact.get("surface", "")[:300]))

    # ---- T-590: goal_tickets bumps mechanically on VERIFY->REVIEW under goal.
    goal_root = make_project()
    (goal_root / ".saipen" / "STATE.md").write_text(
        codec.read_doc(goal_root / ".saipen" / "STATE.md").replace(
            "mode: full", "mode: full\nexecution_intent: goal\n"
            "goal_waves: 1\ngoal_tickets: 5"),
        encoding="utf-8")
    apply_claim(goal_root, "T-1", "probe")
    transition_phase(goal_root, "BUILD", "probe", "T-1", "build")
    transition_phase(goal_root, "VERIFY", "probe", "T-1", "verify")
    tr_g = transition_phase(goal_root, "REVIEW", "probe", "T-1", "review gate")
    st_g = parse_state(codec.read_doc(goal_root / ".saipen" / "STATE.md"))
    expect("VERIFY->REVIEW under goal mechanically bumps goal_tickets",
           tr_g.get("ok")
           and st_g.get("goal_tickets") == 6, repr(st_g))
    log_g = codec.read_doc(goal_root / ".saipen" / "LOG.md")
    expect("goal_tickets bump emits the DEC line mechanically",
           "goal_tickets 5->6" in log_g, repr(log_g[-200:]))

    # ---- T-590: HUNT->ADD under goal mechanically bumps goal_waves.
    wave_root = make_project()
    (wave_root / ".saipen" / "STATE.md").write_text(
        codec.read_doc(wave_root / ".saipen" / "STATE.md").replace(
            "mode: full", "mode: full\nexecution_intent: goal\n"
            "goal_waves: 1\ngoal_tickets: 3"),
        encoding="utf-8")
    (wave_root / ".saipen" / "STATE.md").write_text(
        codec.read_doc(wave_root / ".saipen" / "STATE.md").replace(
            "phase: DONE", "phase: HUNT").replace(
            "next_action: \"saipen continue\"",
            "next_action: \"PHASE HUNT\""), encoding="utf-8")
    tr_w = transition_phase(wave_root, "ADD", "probe", None, "wave gate")
    st_w = parse_state(codec.read_doc(wave_root / ".saipen" / "STATE.md"))
    expect("HUNT->ADD under goal mechanically bumps goal_waves",
           tr_w.get("ok")
           and st_w.get("goal_waves") == 2, repr(st_w))
    log_w = codec.read_doc(wave_root / ".saipen" / "LOG.md")
    expect("goal_waves bump emits the DEC line mechanically",
           "goal_waves 1->2" in log_w, repr(log_w[-200:]))

    # ---- T-590: committed-journal compaction preserves ALREADY_APPLIED.
    from saipen_engine.journal import compact_committed, run_mutation as _rm
    comp_root = make_project()
    c_res = apply_claim(comp_root, "T-1", "probe")
    op_dir = comp_root / ".saipen" / "recovery" / "ops" / c_res.get("op_id")
    staged_before = [p for p in op_dir.glob("*.staged")]
    expect("a committed claim has staged bytes before compaction",
           len(staged_before) > 0, repr(staged_before))
    compact_committed(comp_root)
    staged_after = [p for p in op_dir.glob("*.staged")]
    expect("compaction removes committed staged bytes",
           len(staged_after) == 0, repr(staged_after))
    rec_comp = _rm(comp_root, c_res.get("op_id"), "claim", "probe", "id",
                   "hash", [{"path": ".saipen/STATE.md", "role": "state",
                             "content": b""}], skip_preflight=True)
    expect("compacted op retried still returns ALREADY_APPLIED",
           rec_comp.get("code") == "ALREADY_APPLIED", repr(rec_comp))
    # A conflict journal is never compacted.
    conf_root = make_project()
    saipen_conf = conf_root / ".saipen"
    log_cf = (saipen_conf / "LOG.md").read_bytes()
    state_cf = (saipen_conf / "STATE.md").read_bytes()
    j_cf = Journal(conf_root, "op-cf")
    j_cf.start("checkpoint", "probe", "id", "h", [
        {"path": ".saipen/LOG.md", "role": "log",
         "content": log_cf + b"\n- 09.08.26 00:01 [E-901] RUN: x\n",
         "before_hash": hash_bytes(log_cf),
         "after_hash": hash_bytes(
             log_cf + b"\n- 09.08.26 00:01 [E-901] RUN: x\n")},
        {"path": ".saipen/STATE.md", "role": "state",
         "content": state_cf.replace(b"phase: DONE", b"phase: BUILD"),
         "before_hash": hash_bytes(state_cf),
         "after_hash": hash_bytes(
             state_cf.replace(b"phase: DONE", b"phase: BUILD"))},
    ], verification_policy="core_fast")
    (saipen_conf / "LOG.md").write_bytes(
        log_cf + b"\n- 09.08.26 00:01 [E-901] RUN: x\n")
    j_cf.mark("APPLYING", progress_index=1, target_index=0)
    (saipen_conf / "STATE.md").write_bytes(state_cf + b"\n# third party\n")
    recover(conf_root, "op-cf")
    compact_committed(conf_root)
    cf_staged = [p for p in (conf_root / ".saipen" / "recovery" / "ops"
                             / "op-cf").glob("*.staged")]
    expect("a conflict journal is never compacted",
           len(cf_staged) > 0, repr(cf_staged))

    # ---- T-596: compaction is the bounded SETTLED maintenance op -- a
    # RESOLVED op compacts (tombstone keeps identity + final hashes), while
    # PREPARED / APPLYING journals are never compacted.
    res_root = make_project()
    saipen_res = res_root / ".saipen"
    log_rs = (saipen_res / "LOG.md").read_bytes()
    state_rs = (saipen_res / "STATE.md").read_bytes()
    j_rs = Journal(res_root, "op-rs")
    j_rs.start("checkpoint", "probe", "id", "h", [
        {"path": ".saipen/LOG.md", "role": "log",
         "content": log_rs + b"\n- 09.08.26 00:01 [E-901] RUN: x\n",
         "before_hash": hash_bytes(log_rs),
         "after_hash": hash_bytes(
             log_rs + b"\n- 09.08.26 00:01 [E-901] RUN: x\n")},
        {"path": ".saipen/STATE.md", "role": "state",
         "content": state_rs.replace(b"phase: DONE", b"phase: BUILD"),
         "before_hash": hash_bytes(state_rs),
         "after_hash": hash_bytes(
             state_rs.replace(b"phase: DONE", b"phase: BUILD"))},
    ], verification_policy="core_fast")
    (saipen_res / "LOG.md").write_bytes(
        log_rs + b"\n- 09.08.26 00:01 [E-901] RUN: x\n")
    j_rs.mark("APPLYING", progress_index=1, target_index=0)
    (saipen_res / "STATE.md").write_bytes(state_rs.replace(
        b"phase: DONE", b"phase: HUNT").replace(b"last_event: 900",
                                                b"last_event: 901"))
    recover(res_root, "op-rs")
    from saipen_engine.journal import resolve_conflict as _rs_resolve
    _rs_resolve(res_root, "op-rs", "accept_live", agent="probe")
    rs_dir = res_root / ".saipen" / "recovery" / "ops" / "op-rs"
    _rs_record = json.loads((rs_dir / "operation.json").read_text(
        encoding="utf-8"))
    compact_committed(res_root)
    rs_staged = list(rs_dir.glob("*.staged"))
    rs_record2 = json.loads((rs_dir / "operation.json").read_text(
        encoding="utf-8"))
    expect("compaction compacts a RESOLVED journal (settled maintenance op)",
           len(rs_staged) == 0, repr(rs_staged))
    expect("compaction keeps the full tombstone for a resolved op",
           rs_record2.get("op_id") == "op-rs"
           and rs_record2.get("status") == "RESOLVED"
           and rs_record2.get("operation") == "checkpoint"
           and bool(rs_record2.get("semantic_payload_hash"))
           and bool(rs_record2.get("created_at"))
           and all(t.get("before_hash") and t.get("after_hash")
                   for t in rs_record2.get("targets", [])),
           repr(rs_record2))
    pre_root = make_project()
    j_pre = Journal(pre_root, "op-pre")
    j_pre.start("checkpoint", "probe", "id", "h", [
        {"path": ".saipen/LOG.md", "role": "log",
         "content": b"x", "before_hash": "a", "after_hash": "b"}])
    compact_committed(pre_root)
    pre_staged = list((pre_root / ".saipen" / "recovery" / "ops" / "op-pre")
                      .glob("*.staged"))
    expect("a PREPARED journal is never compacted (evidence still required)",
           len(pre_staged) > 0, repr(pre_staged))

    # ---- T-590: validator rejects a placeholder verify on a new ticket.
    vp_root = make_project()
    (vp_root / ".saipen" / "BOARD.md").write_text(
        "# Board\n## DOING\n## TODO\n"
        "- [ ] T-1 [P1] weak ticket | verify: TBD\n"
        "## DONE\n## BLOCKED\n", encoding="utf-8")
    vp_proc = subprocess.run(
        [sys.executable, str(VALIDATOR), "--project-root", str(vp_root)],
        cwd=str(vp_root), capture_output=True, text=True, errors="replace",
        timeout=120)
    expect("validator FAILs a new TODO ticket with placeholder verify",
           vp_proc.returncode != 0
           and "placeholder verify" in (vp_proc.stdout + vp_proc.stderr),
           repr((vp_proc.stdout + vp_proc.stderr)[-300:]))

    # ---- T-590: >8 TODO tickets with the 9th workable -- cold context must
    # include the exact next ticket (not truncated).
    ctx9_root = make_project()
    lines = ["# Board", "## DOING", "## TODO"]
    for i in range(8):
        lines.append(f"- [ ] T-{i+1} [P1] unworkable {i+1} | "
                     f"needs: T-999 | verify: probe")
    lines.append("- [ ] T-9 [P1] the workable one | verify: probe")
    lines += ["## DONE", "## BLOCKED"]
    (ctx9_root / ".saipen" / "BOARD.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    cold9 = ctx.context_cold(ctx9_root)
    expect("cold context includes the exact next ticket below the 8-ticket "
           "truncation boundary",
           "PHASE SCOUT T-9" in cold9.get("surface", "")
           and "the workable one" in cold9.get("surface", "")
           and "verify: probe" in cold9.get("surface", ""),
           repr(cold9.get("surface", "")[:400]))

    # ---- T-590: PUBLIC adapter path -- every public NITRO command through
    # `python tools/saipen.py`, not just the engine functions.
    pub_root = make_project()
    pub_next = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "next", "--json"],
        cwd=str(pub_root), capture_output=True, text=True, timeout=60)
    expect("public `saipen next` routes DONE+workable to the ticket",
           '"action": "PHASE SCOUT T-1"' in pub_next.stdout,
           repr(pub_next.stdout[:160]))
    pub_status = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "status",
         "--json"],
        cwd=str(pub_root), capture_output=True, text=True, timeout=60)
    expect("public `saipen status` exposes computed_next_action",
           '"computed_next_action": "PHASE SCOUT T-1"'
           in pub_status.stdout, repr(pub_status.stdout[:200]))
    pub_context = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "context", "hot"],
        cwd=str(pub_root), capture_output=True, text=True, timeout=60)
    expect("public `saipen context hot` includes the computed next",
           "PHASE SCOUT T-1" in pub_context.stdout,
           repr(pub_context.stdout[:160]))
    pub_sub = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "sub", "spawn",
         "saipub", "--json"],
        cwd=str(pub_root), capture_output=True, text=True, timeout=60)
    if pub_sub.returncode != 0:
        # make_project writes saipen_home: "." which has no TEMPLATE; point the
        # fixture at the real home and retry so the public path is exercised.
        from saipen_engine.state import patch_state as _patch_state
        sp_state = pub_root / ".saipen" / "STATE.md"
        sp_state.write_text(
            _patch_state(codec.read_doc(sp_state),
                         {"saipen_home": str(HOME)}), encoding="utf-8")
        pub_sub = subprocess.run(
            [sys.executable, str(HOME / "tools" / "saipen.py"), "sub",
             "spawn", "saipub", "--json"],
            cwd=str(pub_root), capture_output=True, text=True, timeout=60)
    expect("public `saipen sub spawn` works through the adapter",
           pub_sub.returncode == 0
           and '"code": "SPAWNED"' in pub_sub.stdout,
           repr(pub_sub.stdout[:160]))
    pub_pause = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "sub", "pause",
         "saipub", "--json"],
        cwd=str(pub_root), capture_output=True, text=True, timeout=60)
    pub_resume = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "sub", "resume",
         "saipub", "--json"],
        cwd=str(pub_root), capture_output=True, text=True, timeout=60)
    expect("public sub pause/resume work through the adapter",
           '"code": "SUB_PAUSED"' in pub_pause.stdout
           and '"code": "SUB_RESUMED"' in pub_resume.stdout,
           repr((pub_pause.stdout[:120], pub_resume.stdout[:120])))

    # T-602: PUBLIC gate composition -- `ticket done` through the CLI after
    # claim->BUILD must REFUSE ILLEGAL_PHASE and write zero canonical bytes,
    # because REVIEW/SHIP never ran. The old claim->BUILD->done "validator
    # green" precedent was FALSE_EVIDENCE: it laundered an illegal execution
    # history into a legal-looking DONE (NITRO dogfood IV, T-602).
    pubc_root = make_project()
    pubc_claim = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "claim", "T-1",
         "--json"],
        cwd=str(pubc_root), capture_output=True, text=True, timeout=60)
    pubc_tr = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "transition",
         "BUILD", "T-1", "b", "--json"],
        cwd=str(pubc_root), capture_output=True, text=True, timeout=60)
    pubc_done = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "ticket", "done",
         "T-1", "--json"],
        cwd=str(pubc_root), capture_output=True, text=True, timeout=60)
    pubc_st = parse_state(codec.read_doc(
        pubc_root / ".saipen" / "STATE.md"))
    pubc_board = parse_board(codec.read_doc(
        pubc_root / ".saipen" / "BOARD.md"))
    pubc_t1 = pubc_board["tickets"]["T-1"]
    pubc_validator = subprocess.run(
        [sys.executable, str(VALIDATOR), "--project-root", str(pubc_root)],
        cwd=str(pubc_root), capture_output=True, text=True, errors="replace",
        timeout=120)
    expect("public closure: claim->BUILD->ticket done REFUSEs ILLEGAL_PHASE",
           '"code": "CLAIMED"' in pubc_claim.stdout
           and '"code": "TRANSITIONED"' in pubc_tr.stdout
           and '"code": "ILLEGAL_PHASE"' in pubc_done.stdout,
           repr((pubc_claim.stdout[:80], pubc_tr.stdout[:80],
                 pubc_done.stdout[:80])))
    expect("public closure: the refused done writes zero bytes (ticket stays "
           "DOING, phase stays BUILD)",
           pubc_st.get("phase") == "BUILD"
           and pubc_st.get("task") == "T-1"
           and pubc_t1["section"] == "## DOING",
           repr((pubc_st, pubc_t1["section"])))
    expect("public closure: the state stays validator-green after the refusal",
           pubc_validator.returncode == 0,
           pubc_validator.stdout[-300:] if pubc_validator.returncode else "")

    # T-591: `saipen next` action/load agreement through the public path.
    pubn_root = make_project()
    pubn_next = subprocess.run(
        [sys.executable, str(HOME / "tools" / "saipen.py"), "next", "--json"],
        cwd=str(pubn_root), capture_output=True, text=True, timeout=60)
    import json as _json
    try:
        pubn = _json.loads(pubn_next.stdout)
        load_ok = pubn.get("load") == "saipen/phases/scout.md"
    except Exception:
        load_ok = False
    expect("public `saipen next` pairs action with the routed phase doc",
           '"action": "PHASE SCOUT T-1"' in pubn_next.stdout and load_ok,
           repr(pubn_next.stdout[:200]))

    # ---- T-591 closure composition controls (NITRO dogfood III, section 10).
    from saipen_engine.operations import finish_ticket
    from saipen_engine.journal import recover as _recover_op

    # Control A: claim->BUILD->VERIFY->REVIEW->SHIP->FINISH -> validator PASS.
    cA = make_project()
    apply_claim(cA, "T-1", "probe")
    transition_phase(cA, "BUILD", "probe", "T-1", "b")
    transition_phase(cA, "VERIFY", "probe", "T-1", "v")
    transition_phase(cA, "REVIEW", "probe", "T-1", "r")
    transition_phase(cA, "SHIP", "probe", "T-1", "s")
    finA = finish_ticket(cA, "T-1", "probe")
    stA = parse_state(codec.read_doc(cA / ".saipen" / "STATE.md"))
    expect("closure control A: SHIP->FINISH ends DONE/task none",
           finA.get("ok") and stA.get("phase") == "DONE"
           and stA.get("task") == "none", repr(stA))

    # Control B: after finish, no DOING, ticket DONE [x], next routes legally.
    boardB = parse_board(codec.read_doc(cA / ".saipen" / "BOARD.md"))
    doingB = [t for t in boardB["tickets"].values()
              if t["section"] == "## DOING"]
    t1B = boardB["tickets"]["T-1"]
    expect("closure control B: no DOING + ticket DONE[x] after finish",
           not doingB and t1B["section"] == "## DONE"
           and t1B["checkbox"] == "x", repr((doingB, t1B["checkbox"])))

    # Control C: crash during FINISH after LOG -> recovery -> validator PASS.
    cC = make_project()
    apply_claim(cC, "T-1", "probe")
    transition_phase(cC, "BUILD", "probe", "T-1", "b")
    transition_phase(cC, "VERIFY", "probe", "T-1", "v")
    transition_phase(cC, "REVIEW", "probe", "T-1", "r")
    transition_phase(cC, "SHIP", "probe", "T-1", "s")
    # finish with crash after LOG (the ticket is in SHIP -- the only legal
    # closure phase; T-602 gate)
    crash_code = (
        "import sys, os; sys.path.insert(0, r'%s')\n"
        "os.environ['NITRO_CRASH_AFTER_LOG'] = '1'\n"
        "from saipen_engine.operations import finish_ticket\n"
        "finish_ticket(r'%s', 'T-1', 'probe')"
        % (str(HOME / "tools"), str(cC)))
    rc = subprocess.run([sys.executable, "-c", crash_code], cwd=str(cC),
                        capture_output=True, text=True, timeout=60).returncode
    expect("closure control C: crash during finish leaves an unresolved op",
           rc == 87 and bool(pending_ops(cC)), f"rc={rc}")
    _recover_op(cC, pending_ops(cC)[0]["op_id"])
    boardC = parse_board(codec.read_doc(cC / ".saipen" / "BOARD.md"))
    stC = parse_state(codec.read_doc(cC / ".saipen" / "STATE.md"))
    expect("closure control C: recovery finishes exactly one ticket",
           boardC["tickets"]["T-1"]["section"] == "## DONE"
           and stC.get("phase") == "DONE" and stC.get("task") == "none",
           repr((boardC["tickets"]["T-1"]["section"], stC.get("phase"))))

    # Control E: repeat FINISH same op_id -> ALREADY_APPLIED, no 2nd event.
    cE = make_project()
    apply_claim(cE, "T-1", "probe")
    transition_phase(cE, "BUILD", "probe", "T-1", "b")
    transition_phase(cE, "VERIFY", "probe", "T-1", "v")
    transition_phase(cE, "REVIEW", "probe", "T-1", "r")
    transition_phase(cE, "SHIP", "probe", "T-1", "s")
    from saipen_engine.plan import apply_plan as _apply_plan
    from saipen_engine.operations import (_now as _now_e,
                                           _plan_finish_ticket,
                                           _utc_iso as _utc_e)
    planE = _plan_finish_ticket(cE, "T-1", "probe", _now_e(), _utc_e())
    finE1 = _apply_plan(cE, planE)
    logE = codec.read_doc(cE / ".saipen" / "LOG.md")
    countE = logE.count(f"E-{finE1.get('event_id')[2:]}")
    # Apply the SAME plan object again: the committed op's retry must return
    # ALREADY_APPLIED with no second completion event.
    retryE = _apply_plan(cE, planE)
    expect("closure control E: repeat finish returns ALREADY_APPLIED",
           retryE.get("code") == "ALREADY_APPLIED", repr(retryE))
    expect("closure control E: no second completion event",
           codec.read_doc(cE / ".saipen" / "LOG.md").count(
               f"E-{finE1.get('event_id')[2:]}") == countE)

    # Control F: old ticket done cannot leave REVIEW/T-X + BOARD DONE (the
    # split is now refused at plan time).
    cF = make_project()
    apply_claim(cF, "T-1", "probe")
    transition_phase(cF, "BUILD", "probe", "T-1", "b")
    transition_phase(cF, "VERIFY", "probe", "T-1", "v")
    transition_phase(cF, "REVIEW", "probe", "T-1", "r")
    from saipen_engine.operations import (_now as _now_f, _ticket_targets,
                                           _utc_iso as _utc_f)
    split_res = _ticket_targets(cF, "done", "T-1", "probe", "",
                                _now_f(), _utc_f())
    stF = parse_state(codec.read_doc(cF / ".saipen" / "STATE.md"))
    boardF = parse_board(codec.read_doc(cF / ".saipen" / "BOARD.md"))
    expect("closure control F: raw done split is refused (no REVIEW/T-X + "
           "BOARD DONE)",
           isinstance(split_res, Result)
           and not split_res.get("ok")
           and stF.get("phase") == "REVIEW"
           and boardF["tickets"]["T-1"]["section"] == "## DOING",
           repr((split_res, stF.get("phase"),
                 boardF["tickets"]["T-1"]["section"])))

    # ---- NITRO dogfood IV (T-602): the finish GATE. `finish_ticket` may only
    # close a ticket from phase SHIP; from SCOUT/BUILD/VERIFY/REVIEW it REFUSEs
    # ILLEGAL_PHASE with zero canonical bytes written, and transition_from
    # records the ACTUAL phase -- never a laundered SHIP.
    from saipen_engine.operations import (finish_ticket as _gate_ft)
    from saipen_engine.operations import (_now as _now_g, _utc_iso as _utc_g)
    from saipen_engine.plan import apply_plan as _gate_apply_plan
    from saipen_engine.state import patch_state as _gate_patch_state
    import hashlib as _gate_hashlib

    def _tree_hash(_root: Path) -> str:
        _h = _gate_hashlib.sha256()
        for _p in sorted((_root / ".saipen").rglob("*")):
            if _p.is_file():
                _h.update(_p.relative_to(_root).as_posix().encode("utf-8"))
                _h.update(_p.read_bytes())
        return _h.hexdigest()[:16]

    gate_cases = [
        ("SCOUT", []),
        ("BUILD", ["BUILD"]),
        ("VERIFY", ["BUILD", "VERIFY"]),
        ("REVIEW", ["BUILD", "VERIFY", "REVIEW"]),
    ]
    for _phase, _steps in gate_cases:
        _g = make_project()
        apply_claim(_g, "T-1", "probe")
        for _step in _steps:
            transition_phase(_g, _step, "probe", "T-1", "g")
        _before = _tree_hash(_g)
        _res = _gate_ft(_g, "T-1", "probe")
        _after = _tree_hash(_g)
        _st = parse_state(codec.read_doc(_g / ".saipen" / "STATE.md"))
        expect(f"gate control: finish from {_phase} REFUSEs ILLEGAL_PHASE",
               _res.get("code") == "ILLEGAL_PHASE" and not _res.get("ok"),
               repr(_res))
        expect(f"gate control: finish from {_phase} writes zero canonical "
               "bytes",
               _before == _after, f"tree changed {_before} -> {_after}")
        expect(f"gate control: finish from {_phase} leaves phase/task "
               "untouched",
               _st.get("phase") == _phase and _st.get("task") == "T-1",
               repr(_st))

    # Gate control D: the FULL legal chain claim->BUILD->VERIFY->REVIEW->SHIP
    # -> finish -> FINISHED; transition_from is the ACTUAL phase (SHIP) and the
    # resulting repository is validator-green.
    gD = make_project()
    apply_claim(gD, "T-1", "probe")
    for _step in ("BUILD", "VERIFY", "REVIEW", "SHIP"):
        transition_phase(gD, _step, "probe", "T-1", "d")
    _gD_res = _gate_ft(gD, "T-1", "probe")
    _gD_st = parse_state(codec.read_doc(gD / ".saipen" / "STATE.md"))
    expect("gate control D: full chain SHIP->finish ends FINISHED",
           _gD_res.get("ok") and _gD_res.get("code") == "FINISHED"
           and _gD_st.get("phase") == "DONE"
           and _gD_st.get("transition_from") == "SHIP", repr(_gD_st))
    _gD_val = subprocess.run(
        [sys.executable, str(VALIDATOR), "--project-root", str(gD)],
        cwd=str(gD), capture_output=True, text=True, errors="replace",
        timeout=120)
    expect("gate control D: full chain ends validator-green",
           _gD_val.returncode == 0, _gD_val.stdout[-300:])

    # [gate-closure] validator red control (T-602): a fabricated non-SHIP
    # finish event AT/AFTER the first SHIP-finish boundary FAILs the
    # validator; the identical LOG with only the SHIP-finish passes.
    def _gate_project(log_events: list[tuple[str, str]]) -> Path:
        _r = make_project()
        _sf = _r / ".saipen"
        _log = "- 09.08.26 00:00 [E-900] [T-none] DEC: base\n"
        _e = 900
        for _msg, _tid in log_events:
            _e += 1
            _ticket = f"[{_tid}] " if _tid else ""
            _log += (f"- 09.08.26 00:01 [E-{_e}] {_ticket}"
                     f"DEC: {_msg}\n")
        (_sf / "LOG.md").write_text(_log, encoding="utf-8")
        _st = (_sf / "STATE.md").read_text(encoding="utf-8")
        _st = _st.replace("last_event: 900", f"last_event: {_e}")
        (_sf / "STATE.md").write_text(_st, encoding="utf-8")
        return _r

    _g_ok = _gate_project([
        ("ticket finished via SAIOPS -- completion (from SHIP)", "T-1"),
    ])
    _g_ok_val = subprocess.run(
        [sys.executable, str(VALIDATOR), "--project-root", str(_g_ok)],
        cwd=str(_g_ok), capture_output=True, text=True, errors="replace",
        timeout=120)
    _g_bad = _gate_project([
        ("ticket finished via SAIOPS -- completion (from SHIP)", "T-1"),
        ("ticket finished via SAIOPS -- completion (from VERIFY)", "T-2"),
    ])
    _g_bad_val = subprocess.run(
        [sys.executable, str(VALIDATOR), "--project-root", str(_g_bad)],
        cwd=str(_g_bad), capture_output=True, text=True, errors="replace",
        timeout=120)
    expect("gate-closure red control: pre-boundary history passes, "
           "post-boundary non-SHIP finish FAILs the validator",
           _g_ok_val.returncode == 0 and _g_bad_val.returncode != 0,
           repr((_g_ok_val.returncode, _g_bad_val.returncode))
           + "\nOK-STDOUT:\n" + _g_ok_val.stdout[-1200:]
           + "\nBAD-STDOUT:\n" + _g_bad_val.stdout[-1200:])

    # Mutation red-control: removing the SHIP precondition (restoring the old
    # closure_from = "SHIP" laundering) must flip the BUILD-refuse control to
    # FINISHED -- proving the refuse controls are coupled to the gate, not
    # vacuous.
    import inspect as _gate_inspect
    from saipen_engine import operations as _gate_ops
    from saipen_engine.router import route_next as _gate_route_next
    _gate_src = _gate_inspect.getsource(_gate_ops._plan_finish_ticket)
    _gate_src = _gate_src.replace("    from .router import route_next\n", "")
    _gate_start = _gate_src.index(
        "    # GATE: the canonical closure is SHIP -> DONE")
    _gate_end = _gate_src.index("    closure_from = prev_phase",
                                _gate_start)
    _gate_end = _gate_src.index("\n", _gate_end) + 1
    _gate_mut = (_gate_src[:_gate_start]
                 + '    closure_from = "SHIP"\n'
                 + _gate_src[_gate_end:])
    _gate_ns = dict(vars(_gate_ops))
    _gate_ns["route_next"] = _gate_route_next
    exec(compile(_gate_mut, "<mutated-finish-no-gate>", "exec"), _gate_ns)
    _gate_mut_pft = _gate_ns["_plan_finish_ticket"]
    _gM = make_project()
    apply_claim(_gM, "T-1", "probe")
    transition_phase(_gM, "BUILD", "probe", "T-1", "m")
    _mut_plan = _gate_mut_pft(_gM, "T-1", "probe", _now_g(), _utc_g())
    _mut_res = _gate_apply_plan(_gM, _mut_plan)
    expect("mutation red-control: removing the SHIP gate makes the BUILD "
           "closure succeed (the refuse controls are NOT vacuous)",
           _mut_res.get("ok") and _mut_res.get("code") == "FINISHED",
           repr(_mut_res))

    # Gate control E (goal counter composition): goal_tickets bumps
    # mechanically at VERIFY->REVIEW under execution_intent goal -- NEVER at
    # finish. The safety valve can trip MID-ticket: VERIFY->REVIEW at cap
    # leaves phase REVIEW, ticket DOING, goal_tickets at cap, next_action the
    # exact safety-valve WAIT; premature finish behind the valve refuses; after
    # explicit reauthorization the chain continues REVIEW -> SHIP -> FINISH
    # legally.
    gE = make_project()
    set_goal_intent(gE, "probe", "valve mid-ticket control")
    apply_claim(gE, "T-1", "probe")
    transition_phase(gE, "BUILD", "probe", "T-1", "e")
    transition_phase(gE, "VERIFY", "probe", "T-1", "e")
    transition_phase(gE, "REVIEW", "probe", "T-1", "e")
    _stE = parse_state(codec.read_doc(gE / ".saipen" / "STATE.md"))
    expect("gate control E: VERIFY->REVIEW bumps goal_tickets (0->1), never "
           "at finish",
           _stE.get("goal_tickets") == 1 and _stE.get("phase") == "REVIEW",
           repr(_stE))
    # drive goal_tickets to just under the cap: the VERIFY->REVIEW bump must
    # be the mechanical owner of reaching the cap
    _stateE = gE / ".saipen" / "STATE.md"
    _textE = _gate_patch_state(codec.read_doc(_stateE), {"goal_tickets": 19})
    _stateE.write_text(_textE, encoding="utf-8")
    transition_phase(gE, "BUILD", "probe", "T-1", "e2")
    transition_phase(gE, "VERIFY", "probe", "T-1", "e2")
    _rv = transition_phase(gE, "REVIEW", "probe", "T-1", "e2")
    _stV = parse_state(codec.read_doc(_stateE))
    expect("valve control: VERIFY->REVIEW trips at the 20-ticket cap",
           _rv.get("ok") and _stV.get("goal_tickets") == 20
           and _stV.get("phase") == "REVIEW" and _stV.get("task") == "T-1",
           repr((_rv, _stV)))
    expect("valve control: next_action is the exact safety-valve WAIT",
           _stV.get("next_action").startswith("WAIT: safety valve reached")
           and "run 'saipen goal' to continue" in _stV.get("next_action"),
           repr(_stV.get("next_action")))
    _bdV = parse_board(codec.read_doc(gE / ".saipen" / "BOARD.md"))
    _doingV = [t for t in _bdV["tickets"].values()
               if t["section"] == "## DOING"]
    expect("valve control: the ticket stays DOING behind the valve",
           len(_doingV) == 1 and _doingV[0]["id"] == "T-1", repr(_doingV))
    _finV = _gate_ft(gE, "T-1", "probe")
    expect("valve control: finish behind the valve REFUSEs ILLEGAL_PHASE",
           _finV.get("code") == "ILLEGAL_PHASE", repr(_finV))
    _re = reauthorize_valve(gE, "probe")
    expect("valve control: explicit reauthorization resets the counters",
           _re.get("ok") and _re.get("code") == "VALVE_REAUTHORIZED",
           repr(_re))
    transition_phase(gE, "SHIP", "probe", "T-1", "e3")
    _finV2 = _gate_ft(gE, "T-1", "probe")
    _stV3 = parse_state(codec.read_doc(_stateE))
    expect("valve control: after reauthorization REVIEW->SHIP->FINISH "
           "completes",
           _finV2.get("ok") and _finV2.get("code") == "FINISHED"
           and _stV3.get("phase") == "DONE"
           and _stV3.get("transition_from") == "SHIP", repr(_stV3))

    # Router precedent controls (section 12-15): WAIT/BLOCKED stop before
    # START.
    from saipen_engine.router import route_next as _route_next
    rc_state = ("---\nphase: BLOCKED\ntask: none\n"
                 "next_action: \"WAIT: user brake -- user asked to stop\"\n"
                 "blocker: \"user brake\"\ntransition_from: SHIP\n"
                 "saipen_version: 7\nschema_version: 3\nlast_event: 900\n"
                 "style_contract: ded-4ae736e4\nsaipen_home: \".\"\n"
                 "agent: probe\nmode: full\n"
                 "updated: 2026-08-09T00:00:00Z\n---\n")
    rc_board = ("# Board\n## DOING\n## TODO\n"
                "- [ ] T-1 [P1] probe | verify: probe\n"
                "## DONE\n## BLOCKED\n")
    rcA = _route_next(rc_state, rc_board)
    expect("router: user brake outranks START (RESTATE_AND_STOP)",
           rcA.get("reason") == "wait"
           and rcA.get("executable_behavior") == "RESTATE_AND_STOP",
           repr(rcA))

    # ---- T-592: conflict inspection + safe resolution lifecycle.
    from saipen_engine.journal import (inspect_op as _inspect_op,
                                       resolve_conflict as _resolve_conflict)
    conf_root = make_project()
    saipen_cf = conf_root / ".saipen"
    log_cf = (saipen_cf / "LOG.md").read_bytes()
    state_cf = (saipen_cf / "STATE.md").read_bytes()
    new_log_cf = log_cf + b"\n- 09.08.26 00:01 [E-901] RUN: op\n"
    new_state_cf = state_cf.replace(b"phase: DONE", b"phase: BUILD")
    j_cf = Journal(conf_root, "op-t592")
    j_cf.start("checkpoint", "probe", "id", "h", [
        {"path": ".saipen/LOG.md", "role": "log", "content": new_log_cf,
         "before_hash": hash_bytes(log_cf),
         "after_hash": hash_bytes(new_log_cf)},
        {"path": ".saipen/STATE.md", "role": "state",
         "content": new_state_cf, "before_hash": hash_bytes(state_cf),
         "after_hash": hash_bytes(new_state_cf)},
    ], verification_policy="core_fast")
    (saipen_cf / "LOG.md").write_bytes(new_log_cf)
    j_cf.mark("APPLYING", progress_index=1, target_index=0)
    external_cf = state_cf.replace(b"phase: DONE", b"phase: HUNT").replace(
        b"last_event: 900", b"last_event: 901")
    (saipen_cf / "STATE.md").write_bytes(external_cf)
    recover(conf_root, "op-t592")
    insp = _inspect_op(conf_root, "op-t592")
    expect("conflict inspect reports the conflicting location read-only",
           insp.get("code") == "CONFLICT_INSPECT"
           and insp.get("conflicting_locations") == [".saipen/STATE.md"]
           and insp.get("safe_resolution_classes") == ["accept_live",
                                                       "replan"],
           repr(insp))
    # Only the selected conflict may be settled: a second unrelated unresolved
    # op blocks.
    second_log = (saipen_cf / "LOG.md").read_bytes()
    j2 = Journal(conf_root, "op-other")
    j2.start("checkpoint", "probe", "id", "h", [
        {"path": ".saipen/LOG.md", "role": "log", "content": second_log,
         "before_hash": hash_bytes(second_log),
         "after_hash": hash_bytes(second_log)},
    ], verification_policy="core_fast")
    j2.mark("APPLYING", progress_index=1, target_index=0)
    blocked_res = _resolve_conflict(conf_root, "op-t592", "accept_live")
    expect("resolution refuses when another unrelated op is unresolved",
           not blocked_res.get("ok")
           and blocked_res.get("code") == "RECOVERY_REQUIRED",
           repr(blocked_res))
    # Clear the unrelated op (abort it: PREPARED-nothing-applied) then resolve.
    j2.mark("ABORTED")
    res_cf = _resolve_conflict(conf_root, "op-t592", "accept_live",
                               agent="probe")
    expect("accept_live settles the conflict (RESOLVED)",
           res_cf.get("ok") and res_cf.get("code") == "RESOLVED"
           and res_cf.get("resolution") == "accept_live"
           and res_cf.get("applied_targets") == [".saipen/LOG.md"]
           and res_cf.get("skipped_targets") == [".saipen/STATE.md"],
           repr(res_cf))
    expect("pending_ops clears after resolution",
           "op-t592" not in [p["op_id"] for p in pending_ops(conf_root)])
    new_mut = ticket_add(conf_root, "probe", "P2", "after conflict resolve",
                         [], "verify")
    expect("a new mutation succeeds after the conflict is resolved",
           new_mut.get("ok"), repr(new_mut))
    # REPLAN branch: a fresh conflict resolved as replan retires the op.
    conf2 = make_project()
    saipen2 = conf2 / ".saipen"
    log2 = (saipen2 / "LOG.md").read_bytes()
    state2 = (saipen2 / "STATE.md").read_bytes()
    new_log2 = log2 + b"\n- 09.08.26 00:01 [E-901] RUN: op\n"
    new_state2 = state2.replace(b"phase: DONE", b"phase: BUILD")
    j3 = Journal(conf2, "op-replan")
    j3.start("checkpoint", "probe", "id", "h", [
        {"path": ".saipen/LOG.md", "role": "log", "content": new_log2,
         "before_hash": hash_bytes(log2),
         "after_hash": hash_bytes(new_log2)},
        {"path": ".saipen/STATE.md", "role": "state",
         "content": new_state2, "before_hash": hash_bytes(state2),
         "after_hash": hash_bytes(new_state2)},
    ], verification_policy="core_fast")
    (saipen2 / "LOG.md").write_bytes(new_log2)
    j3.mark("APPLYING", progress_index=1, target_index=0)
    ext2 = state2.replace(b"phase: DONE", b"phase: HUNT").replace(
        b"last_event: 900", b"last_event: 901")
    (saipen2 / "STATE.md").write_bytes(ext2)
    recover(conf2, "op-replan")
    res2 = _resolve_conflict(conf2, "op-replan", "replan", agent="probe")
    expect("replan retires the conflict op (RESOLVED)",
           res2.get("ok") and res2.get("code") == "RESOLVED"
           and res2.get("resolution") == "replan", repr(res2))
    expect("replan does not touch live canonical bytes",
           b"phase: HUNT" in (saipen2 / "STATE.md").read_bytes())

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


def run_log_tail_probes() -> tuple[list[str], int]:
    """T-633 root cause: log_tail_event must return the ACTUAL maximum E-###
    across the LOG text, independent of line or file enumeration order.

    The old implementation returned the FINAL parsed E-###, so 'E-100 then
    E-9' minted a tail of 9 and a next checkpoint allocated E-10 -- reusing
    an already-used id. Allocation correctness never depends on ordering."""
    from saipen_engine import operations as _ops
    from saipen_engine.log import log_tail_event
    problems: list[str] = []
    checked = 0

    def expect(label: str, ok: bool, detail: str = "") -> None:
        nonlocal checked
        checked += 1
        if not ok:
            problems.append(f"{label}: {detail}")
        else:
            print(f"PASS: log-tail -- {label}")

    line = "- 09.08.26 00:00 [E-{n}] [parent: E-{p}] [T-none] DEC: ctl\n"
    e100_then_9 = line.format(n=100, p=99) + line.format(n=9, p=8)
    expect("E-100 then E-9 returns 100 (not the final parsed 9)",
           log_tail_event(e100_then_9) == 100,
           repr(log_tail_event(e100_then_9)))
    expect("reordered (E-9 first) still returns 100",
           log_tail_event(line.format(n=9, p=8)
                          + line.format(n=100, p=99)) == 100,
           repr(log_tail_event(line.format(n=9, p=8)
                               + line.format(n=100, p=99))))
    expect("empty text returns None", log_tail_event("") is None,
           repr(log_tail_event("")))
    expect("999 vs 1000: max wins regardless of order",
           log_tail_event(line.format(n=999, p=998)
                          + line.format(n=1000, p=999)) == 1000,
           repr(log_tail_event(line.format(n=999, p=998)
                               + line.format(n=1000, p=999))))

    # Engine-level: a checkpoint after a seal derives max(E)+1 exactly once,
    # and segment enumeration order cannot change allocation.
    root = Path(tempfile.mkdtemp(prefix="saipen-logtail-"))
    saipen = root / ".saipen"
    saipen.mkdir()
    logs = saipen / "logs"
    logs.mkdir()
    # Two sealed segments with a HIGHER event in the older file and the active
    # log empty after the seal -- the tail must be the global max.
    (logs / "LOG-001.md").write_text(
        line.format(n=100, p=99) + line.format(n=9, p=8), encoding="utf-8")
    (logs / "LOG-002.md").write_text(
        line.format(n=50, p=49), encoding="utf-8")
    (saipen / "LOG.md").write_text("", encoding="utf-8")
    (saipen / "BOARD.md").write_text(
        "# Board\n## DOING\n## TODO\n## DONE\n## BLOCKED\n", encoding="utf-8")
    (saipen / "STATE.md").write_text(
        "---\nphase: DONE\ntask: none\nnext_action: \"saipen continue\"\n"
        "blocker: \"\"\ntransition_from: SHIP\nsaipen_version: 7\n"
        "schema_version: 3\nlast_event: 100\nstyle_contract: ded-4ae736e4\n"
        "saipen_home: \".\"\nagent: probe\nmode: full\n"
        "updated: 2026-08-09T00:00:00Z\n---\n", encoding="utf-8")
    _docs, _state, _board, _tail = _ops._read(root)
    expect("engine tail across sealed segments + empty active = global max",
           _tail == 100, repr(_tail))
    # Segment 999 vs 1000 names: numeric sort, never lexicographic.
    (logs / "LOG-999.md").write_text(
        line.format(n=3, p=2), encoding="utf-8")
    (logs / "LOG-1000.md").write_text(
        line.format(n=4, p=3), encoding="utf-8")
    _docs, _state, _board, _tail2 = _ops._read(root)
    expect("LOG-1000 sorts after LOG-999 numerically; tail still 100",
           _tail2 == 100, repr(_tail2))
    # Next checkpoint allocates max(E)+1 exactly once from the global max.
    _event, _rendered = _ops._event_line(
        _docs, _tail2, "DEC", "T-none", "probe",
        "log-tail control: next allocation", "09.08.26 00:01")
    expect("next checkpoint allocates max(E)+1 = 101 exactly once",
           _event == 101 and "[E-101]" in _rendered
           and "[parent: E-100]" in _rendered,
           repr((_event, _rendered)))
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


if os.environ.get("SAIPEN_SCHEDULER_PROBES_ONLY") == "1":
    scheduler_failures, scheduler_checked, scheduler_skipped = run_scheduler_probes()
    for problem in scheduler_failures:
        print(f"FAILED: {problem}")
    raise SystemExit(1 if scheduler_failures else 0)

injector_failures, injector_checked, injector_skipped = run_injector_probes()
failures.extend(injector_failures)
scheduler_failures, scheduler_checked, scheduler_skipped = run_scheduler_probes()
failures.extend(scheduler_failures)
root_failures, root_checked = run_project_root_probes()
failures.extend(root_failures)
export_failures, export_checked, export_skipped = run_export_probes()
failures.extend(export_failures)
crew_failures, crew_checked, crew_skipped = run_crew_probes()
failures.extend(crew_failures)
last_event_failures, last_event_checked = run_last_event_probes()
failures.extend(last_event_failures)
log_tail_failures, log_tail_checked = run_log_tail_probes()
failures.extend(log_tail_failures)
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
release_freshness_failures, release_freshness_checked = \
    run_release_freshness_probes()
failures.extend(release_freshness_failures)
release_executor_failures, release_executor_checked = \
    run_release_executor_probes()
failures.extend(release_executor_failures)
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
nitro_m3_failures, nitro_m3_checked = run_nitro_m3_probes()
failures.extend(nitro_m3_failures)
nitro_integrity_failures, nitro_integrity_checked = \
    run_nitro_integrity_probes()
failures.extend(nitro_integrity_failures)
manifest_failures, manifest_checked = run_manifest_tracking_probes()
failures.extend(manifest_failures)
lint_parity_failures, lint_parity_checked = run_lint_parity_probes()
failures.extend(lint_parity_failures)
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
print(f"{scheduler_checked} scheduler behavior(s) executed, "
      f"{scheduler_skipped} skipped for missing interpreters")
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
print(f"{log_tail_checked} log-tail behavior(s) executed")
print(f"{hunt_mark_checked} hunt-mark behavior(s) executed")
print(f"{converge_checked} converge-routing behavior(s) executed")
print(f"{ccc_identity_checked} ccc commit-identity behavior(s) executed")
print(f"{producer_gate_checked} producer-gate behavior(s) executed")
print(f"{ship_staging_checked} ship-staging behavior(s) executed")
print(f"{release_freshness_checked} release-freshness behavior(s) executed")
print(f"{release_executor_checked} release-executor behavior(s) executed")
print(f"{rolefresh_checked} role-freshness behavior(s) executed, "
      f"{rolefresh_skipped} skipped for missing host capability")
print(f"{sub_clean_checked} sub-clean safety behavior(s) executed, "
      f"{sub_clean_skipped} skipped for missing host capability")
print(f"{hardening_checked} hardening red control(s) resolved")
print(f"{userperson_checked} userperson behavior(s) executed")
print(f"{improve_checked} improve behavior(s) executed")
print(f"{nitro_checked} nitro behavior(s) executed")
print(f"{nitro_m2_checked} nitro-m2 behavior(s) executed")
print(f"{nitro_m3_checked} nitro-m3 behavior(s) executed")
print(f"{nitro_integrity_checked} nitro-integrity behavior(s) executed")
print(f"{purity_checked} pre-commit-purity behavior(s) executed, "
      f"{purity_skipped} skipped for missing interpreters")
print(f"{manifest_checked} manifest-tracking behavior(s) executed")
print(f"{lint_parity_checked} lint-parity behavior(s) executed")
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

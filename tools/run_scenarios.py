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
import importlib.util
import io
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

HOME = Path(__file__).resolve().parent.parent
VALIDATOR = HOME / "tools" / "validate.py"
SCENARIOS = HOME / "tests" / "scenarios"

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
        else:
            (controlled / "bash").symlink_to(Path(bash).resolve())
            bash_path = str(controlled)
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


REQUIRED_INSTALL_FILES = (
    "VERSION",
    "tests/validate.sh",
    "tests/validate.ps1",
)
STALE_SENTINEL = "obsolete-from-prior-install.txt"
MANAGED_DIRS = (
    "phases",
    "tools",
    "tests",
    "extensions/schemas",
    "extensions/templates",
    "extensions/subs",
)


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
    return problems


ROUND_TRIP_BYTES = b"user-setting: keep  \r\n \t\r\n\r\n"


def run_injector_probe(label: str, command: list[str],
                       uninstall_command: list[str], env: dict[str, str],
                       home: Path) -> str | None:
    destination = home / ".claude" / "skills" / "saipen"
    (home / ".claude").mkdir(parents=True)
    config = home / ".claude" / "CLAUDE.md"
    config.write_bytes(ROUND_TRIP_BYTES)
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
    if not problems:
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
        if destination.exists():
            problems.append("uninstaller left the installed skill directory")
    if problems:
        detail = next((line for line in (result.stdout + result.stderr).splitlines()
                       if "FAILED" in line or "FATAL" in line), "no failure line")
        return f"{label}: {'; '.join(problems)} | {detail[:120]}"
    print(f"PASS: {label} -- executable install replaced stale dirs, landed "
          "VERSION + validators, ran validate.py, and uninstalled byte-exact")
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
    else:
        print("SKIP: bootstrap/inject.sh executable probe -- no usable bash")
        skipped += 1

    if powershell:
        with tempfile.TemporaryDirectory(prefix="saipen-inject-ps1-") as raw:
            home = Path(raw)
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["USERPROFILE"] = str(home)
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
manifest_failures, manifest_checked = run_manifest_tracking_probes()
failures.extend(manifest_failures)
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
failures.extend(ship_pick_failures)
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
print(f"{last_event_checked} last_event migration behavior(s) executed")
print(f"{hunt_mark_checked} hunt-mark behavior(s) executed")
print(f"{purity_checked} pre-commit-purity behavior(s) executed, "
      f"{purity_skipped} skipped for missing interpreters")
print(f"{manifest_checked} manifest-tracking behavior(s) executed")
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

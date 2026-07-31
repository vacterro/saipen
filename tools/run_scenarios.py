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

import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
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
# Unpinned fail-fixtures still run, but WARN -- they are asserting only that
# something, somewhere, went wrong.
REASON_RE = re.compile(r"^expect_fail_contains:\s*(.+?)\s*$", re.MULTILINE)


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
               f"Project root: {project_text} (git-common)")

        nested = project / "one" / "two"
        nested.mkdir(parents=True)
        expect("nested cwd", validate(nested), 0,
               f"Project root: {project_text} (git-common)")
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


def run_last_event_probes() -> tuple[list[str], int]:
    """Execute the schema-v1 to schema-v2 checkpoint migration boundary."""
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
                              "saipen_version: 7\nschema_version: 2\n", 1)
        state_path.write_text(state, encoding="utf-8", newline="\n")
        expect("schema v2 missing marker fails", validate(project), 1,
               "requires last_event")

        state = state_path.read_text(encoding="utf-8")
        state = state.replace("schema_version: 2\n",
                              "schema_version: 2\nlast_event: 1\n", 1)
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
    if readme.is_file():
        _rtext = readme.read_text(encoding="utf-8-sig")
        m = EXPECT_RE.search(_rtext)
        declared = m.group(1) if m else None
        _rm = REASON_RE.search(_rtext)
        reason = _rm.group(1) if _rm else None

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
    else:
        if declared == "fail":
            print(f"WARN: {d.name} -- fails as declared, but pins no reason; "
                  f"add `expect_fail_contains:` so it cannot pass by failing "
                  f"at something unrelated")
        print(f"PASS: {d.name} -- expected {declared}, got {actual}")

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
hook_failures, hook_checked, hook_skipped = run_hook_probes()
failures.extend(hook_failures)

print(f"\n{checked} executable fixture(s) checked, "
      f"{skipped} behavioral fixture(s) skipped (README-only by design)")
print(f"{injector_checked} injector(s) executed, "
      f"{injector_skipped} skipped for missing interpreters")
print(f"{root_checked} project-root behavior(s) executed")
print(f"{export_checked} export ownership behavior(s) executed, "
      f"{export_skipped} skipped for missing interpreters")
print(f"{crew_checked} crew-launch behavior(s) executed, "
      f"{crew_skipped} skipped for missing interpreters")
print(f"{last_event_checked} last_event migration behavior(s) executed")
print(f"{hook_checked} installed-hook behavior(s) executed, "
      f"{hook_skipped} skipped for missing interpreters")

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

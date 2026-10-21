"""Canonical, non-recursive test orchestration for ``saipen test``.

Every family runs against one disposable copy of the current working tree.
This keeps the public ``tt`` command read-only even when a validator or
scenario deliberately emits recovery/conformance evidence as part of its
test.  The family list is explicit: discovery can add tests inside a family,
but can never accidentally make the orchestrator discover and invoke itself.
"""

from __future__ import annotations

import json
import os
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import nullcontext, suppress
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TestFamily:
    """One independently reported canonical test family."""

    name: str
    command: tuple[str, ...]
    timeout: int
    # None is conservative: all declared runtime tools. A repository-owned
    # hermetic fixture may explicitly declare that its probe uses Python only.
    environment_tools: tuple[str, ...] | None = None


def _python(*args: str) -> tuple[str, ...]:
    return (sys.executable, "-B", *args)


def _portable_floor() -> tuple[str, ...] | None:
    if os.name == "nt":
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if shell:
            return (
                shell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                "tests/validate.ps1",
            )
        return None
    shell = shutil.which("bash")
    return (shell, "tests/validate.sh") if shell else None


def _families() -> tuple[TestFamily, ...]:
    portable = _portable_floor()
    families = [
        TestFamily(
            "unit",
            _python(
                "-m",
                "unittest",
                "discover",
                "-s",
                "tools",
                "-p",
                "test_*.py",
                "-v",
            ),
            # T-1344: measured 2254 s for 3475 tests on the operator host; the
            # old 600 s bound made every run of the family a TIMEOUT verdict.
            # T-1826: measured again at 6925 tests in single-process mode --
            # 6879.7 s clean and 7458.0 s under host load -- so 5400 s answered
            # TIMEOUT on a green suite. This bound is the recorded worst case
            # plus ~45% headroom; raise it from a new measurement, never from
            # how long a run is expected to take.
            10800,
        ),
        TestFamily(
            "consumer-unit",
            _python(
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_*.py",
                "-v",
            ),
            600,
        ),
        TestFamily("validator", _python("tools/validate.py"), 600),
        TestFamily("audit-checks", _python("tools/audit_checks.py"), 900),
        TestFamily("scenarios", _python("tools/run_scenarios.py"), 1800),
        TestFamily("audit-floor", _python("tools/audit_floor.py"), 600),
        TestFamily("audit-parity", _python("tools/audit_parity.py"), 1200),
        TestFamily("audit-order", _python("tools/audit_order.py"), 300),
        TestFamily("audit-tags", _python("tools/audit_tags.py"), 300),
        TestFamily(
            "ruff",
            _python("-m", "ruff", "check", "tools/", "tests/"),
            300,
        ),
    ]
    if portable is not None:
        families.append(TestFamily("portable-floor", portable, 300))
    else:
        families.append(TestFamily("portable-floor", (), 0))
    return tuple(families)


def canonical_test_plan(_project_root: Path | str) -> list[dict]:
    """Return the stable family plan without running or writing anything."""
    return [
        {
            "name": family.name,
            "command": list(family.command),
            "timeout": family.timeout,
            "available": bool(family.command),
        }
        for family in _families()
    ]


_SESSION_LOCAL = frozenset({".workbuddy-ai", ".pytest_cache", ".ruff_cache", ".mypy_cache"})


def _ignore_copy(_directory: str, names: list[str]) -> set[str]:
    ignored = {name for name in names if name == "__pycache__" or name.endswith(".pyc")}
    # These are editor/session-local and have no bearing on the declared test
    # surface. Everything else, including .git and canonical .saipen state, is
    # copied so the sandbox sees the same current working-tree generation.
    # Lint caches too (T-1483): REVIEW runs ruff after VERIFY's family run,
    # and a cache inside the tested subject made that run cite nothing.
    ignored.update(name for name in names if name in _SESSION_LOCAL)
    if os.name == "nt":
        reserved = {"CON", "PRN", "AUX", "NUL"}
        reserved.update(f"COM{index}" for index in range(1, 10))
        reserved.update(f"LPT{index}" for index in range(1, 10))
        ignored.update(
            name
            for name in names
            if name.rstrip(" .").split(".", 1)[0].upper() in reserved
        )
    return ignored


def _tail(text: str, limit: int = 8000) -> str:
    return text if len(text) <= limit else text[-limit:]


_FAILURE_HEADER = re.compile(r"^(?:FAIL|ERROR): ([A-Za-z0-9_]+)")

def _read_failure_roster_from_path(path: Path, limit: int = 400) -> list[str]:
    """Every failing test id in a child run, scanned but never retained whole.

    ``_read_tail_from_path`` bounds what the REPORT carries, which is right for
    a verdict and wrong for a diagnosis: a run that fails 21 tests prints its
    headers long before the tail, and a truncated log leaves CI showing a count
    with no names. This walks the spooled file line by line and keeps only the
    de-duplicated ids, so the roster survives any truncation of the log.

    ``unittest`` writes its ``FAIL:``/``ERROR:`` headers -- and the whole
    failure report -- to STDERR, not stdout, so the caller scans both spools.
    """
    roster: list[str] = []
    seen: set[str] = set()
    try:
        with open(path, "rb") as handle:
            for raw in handle:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith(("FAIL:", "ERROR:")):
                    continue
                match = _FAILURE_HEADER.match(line)
                if match is None:
                    continue
                name = match.group(1)
                if name in seen:
                    continue
                seen.add(name)
                roster.append(name)
                if len(roster) >= limit:
                    break
    except OSError:
        return roster
    return roster


_BLOCK_END = re.compile(r"^-{20,}$")
_RULE = re.compile(r"^[-=~]{20,}$")

def _read_failure_causes_from_path(path: Path, limit: int = 400) -> dict[str, str]:
    """The one line each failure ends on, keyed by test id.

    A name alone is a count, not a diagnosis: twenty-one names and no cause
    is the same dead end as a bare total. unittest prints each failure report
    between a header and a closing rule, and the last non-blank line of that
    block is the exception -- the `AssertionError` or `RuntimeError` that says
    what actually broke. That line is short, so every cause fits where the
    tracebacks cannot.
    """
    causes: dict[str, str] = {}
    name = ""
    candidate = ""
    try:
        with open(path, "rb") as handle:
            for raw in handle:
                line = raw.decode("utf-8", errors="replace").rstrip()
                header = _FAILURE_HEADER.match(line)
                if header is not None:
                    if name and candidate and name not in causes:
                        causes[name] = candidate
                    name, candidate = header.group(1), ""
                    continue
                if name and _BLOCK_END.match(line.strip()) and line.strip():
                    # unittest underlines the header with a rule of its own
                    # before the body starts; only a rule that CLOSES a body
                    # we have seen ends the block.
                    if candidate:
                        if name not in causes and len(causes) < limit:
                            causes[name] = candidate
                        name, candidate = "", ""
                    continue
                if name and line.strip() and not _RULE.match(line.strip()):
                    candidate = line.strip()
    except OSError:
        pass
    if name and candidate and name not in causes and len(causes) < limit:
        causes[name] = candidate
    return causes


def _read_tail_from_path(path: Path, limit: int = 8000) -> str:
    """Read the bounded suffix of a temp-file child output without retaining
    the full file in memory."""
    try:
        size = path.stat().st_size
    except OSError:
        return ""
    with open(path, "rb") as handle:
        handle.seek(max(0, size - (limit * 4 + 4)))
        data = handle.read()
    return _tail(data.decode("utf-8", errors="replace"), limit)


def _install_quiet_child_site(spool_dir: Path, env: dict[str, str]) -> None:
    """Prevent Windows subprocesses launched by tests from opening windows.

    Family stdout and stderr already go to spool files. This temporary
    ``sitecustomize`` carries the no-window policy into Python test children,
    whose own subprocess calls could otherwise create fresh console windows.
    """
    if os.name != "nt":
        return
    hook = spool_dir / "sitecustomize.py"
    hook.write_text(
        "import os\n"
        "import subprocess\n"
        "\n"
        "if os.name == 'nt' and os.environ.get('SAIPEN_CANONICAL_TEST_CHILD') == '1':\n"
        "    try:\n"
        "        import tempfile, pathlib, sys\n"
        "        for _var in ('TEMP', 'TMP'):\n"
        "            if os.environ.get(_var):\n"
        "                os.environ[_var] = str(pathlib.Path(os.environ[_var]).resolve())\n"
        "        tempfile.tempdir = str(pathlib.Path(tempfile.gettempdir()).resolve())\n"
        "        _py_dir = str(pathlib.Path(sys.executable).parent)\n"
        "        if _py_dir and _py_dir not in os.environ.get('PATH', ''):\n"
        "            os.environ['PATH'] = _py_dir + os.pathsep + os.environ.get('PATH', '')\n"
        "    except Exception:\n"
        "        pass\n"
        "    _original_init = subprocess.Popen.__init__\n"
        "    def _quiet_init(self, *args, **kwargs):\n"
        "        flags = int(kwargs.get('creationflags', 0))\n"
        "        flags &= ~getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)\n"
        "        kwargs['creationflags'] = flags | getattr(subprocess, 'CREATE_NO_WINDOW', 0)\n"
        "        startup = kwargs.get('startupinfo') or subprocess.STARTUPINFO()\n"
        "        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW\n"
        "        startup.wShowWindow = subprocess.SW_HIDE\n"
        "        kwargs['startupinfo'] = startup\n"
        "        return _original_init(self, *args, **kwargs)\n"
        "    subprocess.Popen.__init__ = _quiet_init\n",
        encoding="utf-8",
    )
    inherited = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(spool_dir), inherited) if part
    )


def _terminate_process_tree(process: subprocess.Popen) -> None:
    """Terminate the owned family process and all descendants."""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            capture_output=True,
            check=False,
        )
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, OSError):
        with suppress(ProcessLookupError, OSError):
            process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        with suppress(ProcessLookupError, OSError):
            os.killpg(process.pid, signal.SIGKILL)
        with suppress(ProcessLookupError, OSError):
            process.kill()


def _note_live_reader(owner: Path, pid: int) -> bool:
    """Add the running family's own pid to the caller's sandbox stamp.

    The tree is read by THIS child, not by the process that created the
    sandbox, so a stamp that names only the creator cannot tell a sweep that
    the tree is in use. Best effort: a stamp that cannot be read or written
    leaves the caller with what it had.
    """
    try:
        data = json.loads(Path(owner).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    data["reader"] = int(pid)
    data["spawn_phase"] = "STARTED"
    from .inflight import _process_created

    data["reader_created"] = _process_created(pid)
    try:
        from .paths import safe_atomic_write_bytes

        safe_atomic_write_bytes(owner, json.dumps(data).encode("utf-8"),
                                kind="verification reader", ownership_root=owner.parent)
    except (OSError, ValueError):
        return False
    return True


def _note_spawn_start(owner: Path | None):
    if owner is None:
        return
    try:
        data = json.loads(owner.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return
        data["spawn_phase"] = "STARTING"
        data["spawn_guard"] = "windows-job-v1" if os.name == "nt" else "posix-pipe-v1"
        from .paths import safe_atomic_write_bytes

        safe_atomic_write_bytes(owner, json.dumps(data).encode("utf-8"),
                                kind="verification reader", ownership_root=owner.parent)
    except (OSError, ValueError):
        return


VERIFIER_DIAGNOSTIC_ENV = frozenset({"CODEX_TOOL_CALL_ID", "PROMPT"})


def family_environment(family: TestFamily) -> dict:
    """The inherited child environment; evidence identity uses this same owner."""
    from .paths import unbound_environment

    env = unbound_environment(os.environ.copy(), SAIPEN_AGENT=None)
    for key in ("SAIMAIL_WORKSPACE", "ZAICODE_HOME", "CLAUDE_CONFIG_DIR", "PYTHONPATH",
                *VERIFIER_DIAGNOSTIC_ENV):
        env.pop(key, None)
    py_dirs = [str(Path(sys.executable).parent)]
    if family.command:
        py_dirs.append(str(Path(family.command[0]).parent))
    for directory in py_dirs:
        if directory and directory not in env.get("PATH", ""):
            env["PATH"] = f"{directory}{os.pathsep}{env.get('PATH', '')}"
    if os.name == "nt":
        for key in ("TEMP", "TMP"):
            if env.get(key):
                with suppress(OSError):
                    env[key] = str(Path(env[key]).resolve())
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["SAIPEN_CANONICAL_TEST_CHILD"] = "1"
    return env


def _run_family(
    root: Path,
    family: TestFamily,
    *,
    spool: Path | None = None,
    owner: Path | None = None,
) -> dict:
    """Run one family; its report keeps only the bounded output tails.

    ``spool`` names a caller-owned directory that receives the COMPLETE
    ``stdout``/``stderr`` files, for a caller that must parse the whole run
    (the core-unit evidence reads every failure header, not the tail).
    ``owner`` names a sandbox stamp to mark with this family's pid while it
    runs, so a concurrent sweep can see the tree is still being read.
    """
    started = time.monotonic()
    if not family.command:
        return {
            "name": family.name,
            "status": "NOT_AVAILABLE",
            "exit_code": None,
            "detail": "required platform shell is unavailable",
        }
    # T-1442: a family run is evidence about the tree, never about the session
    # that launched it. The operator's project binding, host session and seat
    # (the engine's one carrier list, plus SAIPEN_AGENT) are not inherited, so
    # a module that forgot `isolate_host_session` cannot bind the live project
    # or read as that session's claim, and the verdict does not follow whoever
    # holds the seat.
    env = family_environment(family)
    creation = {"start_new_session": True} if os.name != "nt" else {
        "creationflags": (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        ),
    }
    if os.name == "nt":
        hidden_startup = subprocess.STARTUPINFO()
        hidden_startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        hidden_startup.wShowWindow = subprocess.SW_HIDE
        creation["startupinfo"] = hidden_startup
    from .process_tree import ProcessTree

    def bind_reader(process):
        if owner is not None and not _note_live_reader(Path(owner), process.pid):
            raise OSError("verification reader ownership could not be recorded")

    spool_context = (
        nullcontext(str(spool))
        if spool is not None
        else tempfile.TemporaryDirectory(prefix="saipen-family-")
    )
    with spool_context as spool_name, ProcessTree() as tree:
        spool_dir = Path(spool_name)
        stdout_path = spool_dir / "stdout"
        stderr_path = spool_dir / "stderr"
        process: subprocess.Popen | None = None
        timed_out = False
        try:
            try:
                _install_quiet_child_site(spool_dir, env)
                with open(stdout_path, "wb") as out, open(stderr_path, "wb") as err:
                    launch_started = time.monotonic()
                    _note_spawn_start(owner)
                    process = tree.start(
                        family.command,
                        cwd=root,
                        env=env,
                        # T-1624: a family is handed NO stdin. It used to
                        # inherit its launcher's, and so did every descendant:
                        # one real host child that reads stdin (a blocking read
                        # on a pipe nobody writes or closes) then held that
                        # shared handle, and on Windows every later child that
                        # inherited it hung in its own startup until the reader
                        # died. Measured: an orphaned `opencode run` froze the
                        # family for its whole 5400 s budget, and killing that
                        # one process released the stuck children at once.
                        stdin=subprocess.DEVNULL,
                        stdout=out,
                        stderr=err,
                        **creation,
                        on_started=bind_reader,
                    )
                    process_create_s = time.monotonic() - launch_started
            except OSError as exc:
                return {
                    "name": family.name,
                    "status": "FAIL",
                    "exit_code": None,
                    "stdout": "",
                    "stderr": f"test family launch failed: {exc}",
                }
            try:
                process.wait(timeout=family.timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                tree.terminate()
                process.wait(timeout=10)
            if timed_out and process.stdout is not None:
                with suppress(OSError):
                    process.stdout.close()
            if timed_out and process.stderr is not None:
                with suppress(OSError):
                    process.stderr.close()
            stdout_text = _read_tail_from_path(stdout_path)
            stderr_text = _read_tail_from_path(stderr_path)
            # unittest reports on stderr; a family whose command writes its own
            # verdict to stdout still gets named. stderr first, so the order is
            # the order a reader expects.
            seen_names: set[str] = set()
            roster = []
            causes: dict[str, str] = {}
            for spool in (stderr_path, stdout_path):
                for name in _read_failure_roster_from_path(spool):
                    if name in seen_names:
                        continue
                    seen_names.add(name)
                    roster.append(name)
                for name, cause in _read_failure_causes_from_path(spool).items():
                    causes.setdefault(name, cause)
            return {
                "name": family.name,
                "status": (
                    "TIMEOUT"
                    if timed_out
                    else ("PASS" if process.returncode == 0 else "FAIL")
                ),
                "exit_code": None if timed_out else process.returncode,
                "duration_s": round(time.monotonic() - started, 6),
                "process_create_s": round(process_create_s, 6),
                "processes_leaked": [pid for pid in tree.pids() if pid != process.pid],
                "failures": roster,
                "causes": causes,
                "stdout": stdout_text,
                "stderr": stderr_text,
            }
        finally:
            # W2-003: every abnormal exit from this frame (KeyboardInterrupt,
            # SystemExit, BaseException) must still terminate the owned
            # process tree. The TimeoutExpired branch owns the timeout path;
            # this finally owns the rest. Reaping is idempotent.
            if (
                process is not None
                and process.poll() is None
            ):
                tree.terminate()
                with suppress(subprocess.TimeoutExpired):
                    process.wait(timeout=5)


def _unit_family_report(source: Path, *, jobs: int) -> dict:
    """The existing full engine, with CI's strict zero-red acceptance.

    Running this interface never cites or creates lifecycle evidence. The
    inherited-red allowance belongs to the separate evidence interface.
    """
    from . import core_unit

    try:
        run = core_unit.run_family(source, jobs=jobs)
        problems = core_unit.judge(run, [])["problems"]
        if issue := core_unit.full_scope_problem(run):
            problems.append(issue)
        if run.get("status") != "PASS" or run.get("exit_code") != 0:
            problems.append(
                f"full unit execution ended {run.get('status')} (exit {run.get('exit_code')})"
            )
        if run.get("sandboxes_leaked"):
            problems.append(f"sandboxes_leaked: {run['sandboxes_leaked']}")
        # `processes_leaked` is the historical PRE-close observation (T-1633).
        # ProcessTree's context exit reaps those descendants before this returns;
        # retain the observation without relabelling it a post-cleanup failure.
        failures = sorted(run.get("red") or [])
        causes = {}
        for name, section in (run.get("sections") or {}).items():
            lines = [line.strip() for line in section.splitlines()
                     if line.strip() and not _RULE.match(line.strip())]
            if len(lines) > 1:
                causes[name] = lines[-1]
        status = "TIMEOUT" if run.get("status") == "TIMEOUT" else "FAIL" if problems else "PASS"
        detail = _tail("\n".join([*problems, run.get("stderr") or ""])) if problems else None
        return {**run, "name": "unit", "status": status, "detail": detail,
                "failures": failures, "causes": causes}
    except (OSError, RuntimeError, ValueError, LookupError) as exc:
        return {"name": "unit", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"}


def _run_declared_family(source: Path, family: TestFamily, *, jobs: int) -> dict:
    if family.name == "unit":
        return _unit_family_report(source, jobs=jobs)
    return _run_family(source, family)


def run_canonical_suite(project_root: Path | str, *, jobs: int = 1) -> dict:
    """Run every declared family in a disposable working-tree copy."""
    if type(jobs) is not int or jobs < 1:
        raise ValueError("jobs must be a positive integer")
    source = Path(project_root).resolve()
    if not source.is_dir():
        return {
            "ok": False,
            "families": [
                {
                    "name": "bootstrap",
                    "status": "FAIL",
                    "detail": f"project root does not exist: {source}",
                }
            ],
        }
    with tempfile.TemporaryDirectory(prefix="saipen-test-") as tmp:
        sandbox = Path(tmp) / "project"
        shutil.copytree(source, sandbox, symlinks=True, ignore=_ignore_copy)
        reports = [_run_declared_family(sandbox, family, jobs=jobs) for family in _families()]
    return {
        "ok": all(item["status"] == "PASS" for item in reports),
        "families": reports,
    }


def main(argv: list[str] | None = None) -> int:
    """CI entry point; ``--family`` uses the same explicit family registry."""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--family")
    parser.add_argument("--jobs", type=int, default=1,
                        help="unit-family workers; default 1, other families remain sequential")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.jobs < 1:
        parser.error("--jobs must be a positive integer")
    source = Path(args.project_root).resolve()
    selected = [family for family in _families() if family.name == args.family]
    if args.family and not selected:
        report = {
            "ok": False,
            "families": [
                {
                    "name": args.family,
                    "status": "FAIL",
                    "detail": "unknown family",
                }
            ],
        }
    elif args.family == "unit":
        reports = [_run_declared_family(source, family, jobs=args.jobs) for family in selected]
        report = {"ok": all(item["status"] == "PASS" for item in reports), "families": reports}
    elif args.family:
        with tempfile.TemporaryDirectory(prefix="saipen-test-") as tmp:
            sandbox = Path(tmp) / "project"
            shutil.copytree(source, sandbox, symlinks=True, ignore=_ignore_copy)
            reports = [_run_family(sandbox, family) for family in selected]
        report = {
            "ok": all(item["status"] == "PASS" for item in reports),
            "families": reports,
        }
    else:
        report = run_canonical_suite(source, jobs=args.jobs)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for item in report["families"]:
            print(f"{item['name']}: {item['status']}")
            if item["status"] != "PASS":
                detail = item.get("detail") or item.get("stderr") or item.get("stdout")
                if detail:
                    print(detail)
                # The roster goes LAST so it survives a truncated CI log, and it
                # names every failing test rather than the four the log tail
                # happened to keep -- each with the one line that says why.
                causes = item.get("causes") or {}
                roster = item.get("failures") or []
                if roster:
                    print(f"failing tests ({len(roster)}):")
                    for name in roster:
                        cause = causes.get(name)
                        print(f"  FAIL {name}" + (f"\n       {cause}" if cause else ""))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

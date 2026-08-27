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
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TestFamily:
    """One independently reported canonical test family."""

    name: str
    command: tuple[str, ...]
    timeout: int


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
            600,
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


def _ignore_copy(_directory: str, names: list[str]) -> set[str]:
    ignored = {name for name in names if name == "__pycache__" or name.endswith(".pyc")}
    # These are editor/session-local and have no bearing on the declared test
    # surface. Everything else, including .git and canonical .saipen state, is
    # copied so the sandbox sees the same current working-tree generation.
    ignored.update(name for name in names if name in {".workbuddy-ai", ".pytest_cache"})
    return ignored


def _tail(text: str, limit: int = 8000) -> str:
    return text if len(text) <= limit else text[-limit:]


def _run_family(root: Path, family: TestFamily) -> dict:
    if not family.command:
        return {
            "name": family.name,
            "status": "NOT_AVAILABLE",
            "exit_code": None,
            "detail": "required platform shell is unavailable",
        }
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["SAIPEN_CANONICAL_TEST_CHILD"] = "1"
    try:
        completed = subprocess.run(
            family.command,
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=family.timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "name": family.name,
            "status": "TIMEOUT",
            "exit_code": None,
            "stdout": _tail(exc.stdout or ""),
            "stderr": _tail(exc.stderr or ""),
        }
    status = "PASS" if completed.returncode == 0 else "FAIL"
    return {
        "name": family.name,
        "status": status,
        "exit_code": completed.returncode,
        "stdout": _tail(completed.stdout),
        "stderr": _tail(completed.stderr),
    }


def run_canonical_suite(project_root: Path | str) -> dict:
    """Run every declared family in a disposable working-tree copy."""
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
        reports = [_run_family(sandbox, family) for family in _families()]
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
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
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
        report = run_canonical_suite(source)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for item in report["families"]:
            print(f"{item['name']}: {item['status']}")
            if item["status"] != "PASS":
                detail = item.get("detail") or item.get("stderr") or item.get("stdout")
                if detail:
                    print(detail)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

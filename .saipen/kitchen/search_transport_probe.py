"""T-1320 probe: the canonical search transport with ripgrep made UNAVAILABLE.

Proves the contract that actually matters to the operator: the installed
launcher resolves `saipen search` in every shell family OpenCode's shell tool
may present, with the host search layer removed from PATH and from OpenCode's
own bin directory, against a real malformed bound project.

Run:  python .saipen/kitchen/search_transport_probe.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOME = Path.home()
SKILL_BIN = HOME / ".config/opencode/skills/saipen/bin"
OPENCODE_BIN = HOME / ".local/share/opencode/bin"
MANICODE = HOME / ".config/manicode"
#: `bash` on this host resolves to WSL's shim, which has no distribution. The
#: shell OpenCode's Git-Bash mode actually spawns is the Git-for-Windows one.
GIT_BASH_CANDIDATES = (
    Path("C:/Program Files/Git/bin/bash.exe"),
    Path("C:/Program Files (x86)/Git/bin/bash.exe"),
)


def git_bash() -> str | None:
    for candidate in GIT_BASH_CANDIDATES:
        if candidate.is_file():
            return str(candidate)
    found = shutil.which("bash")
    return found if found and "system32" not in found.lower() else None


def stripped_env() -> dict[str, str]:
    """PATH with every known ripgrep provider removed, plus the launcher dir."""
    parts = []
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        low = entry.lower()
        if "manicode" in low or ("opencode" in low and "bin" in low):
            continue
        parts.append(entry)
    parts.insert(0, str(SKILL_BIN))
    env = {**os.environ, "PATH": os.pathsep.join(parts)}
    for key in ("PWD", "OLDPWD"):
        env.pop(key, None)
    return env


def via_launcher(env: dict[str, str], *args: str) -> subprocess.CompletedProcess:
    """Resolve the bare `saipen` token through the installed Windows launcher.

    `cmd /c` is used deliberately: a bare command name is resolved through
    PATHEXT, which is exactly what PowerShell/cmd do and what an extensionless
    POSIX script on PATH cannot satisfy.
    """
    return subprocess.run(
        ["cmd", "/c", "saipen", *args], capture_output=True, text=True, env=env, timeout=180
    )


def fixture() -> Path:
    root = Path(tempfile.mkdtemp(prefix="t1320-probe-"))
    (root / ".saipen").mkdir(parents=True)
    (root / ".saipen" / "LOG.md").write_text(
        "# Log\n"
        "- 13.09.26 00:00 [E-0001] [agent: tester] [op: transition-"
        + "a" * 32
        + "] RUN: transition to SCOUT\n"
        "- 13.09.26 00:01 [E-0002] [parent: E-0001] [T-001] [agent: tester] [op: transition-"
        + "1" * 32
        + "] RUN: transition to BUILD\n",
        encoding="utf-8",
    )
    (root / ".saipen" / "STATE.md").write_text(
        "---\nphase: IMPL\ntask: T-001\nnext_action: \"PHASE BUILD T-001\"\n"
        "blocker: none\ntransition_from: DONE\nsaipen_version: 7\nschema_version: 3\n"
        "last_event: 2\nstyle_contract: ded-4ae736e4\nagent: tester\nmode: full\n"
        "updated: 2026-09-13T00:00:00Z\nexecution_intent: normal\n---\n",
        encoding="utf-8",
    )
    (root / ".saipen" / "BOARD.md").write_text(
        "## DOING\n- [/] T-001 [P1] fix | verify: test\n## TODO\n## DONE\n## BLOCKED\n",
        encoding="utf-8",
    )
    (root / "src").mkdir()
    (root / "src" / "engine.py").write_text(
        "CommitSnapshot = 1\nFlushSyncUnderGate = 2\n", encoding="utf-8"
    )
    return root


HEX = "CommitSnapshot|FlushSyncUnderGate".encode().hex()


def in_powershell(root: Path, env: dict) -> tuple[int, str]:
    script = (
        f"Set-Location '{root}'; "
        f"& saipen search --hex {HEX} --max-matches 2; "
        f"Write-Output \"PWD_IS=$((Get-Location).Path)\""
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True, text=True, env=env, timeout=180,
    )
    return proc.returncode, proc.stdout + proc.stderr


def in_cmd(root: Path, env: dict) -> tuple[int, str]:
    proc = subprocess.run(
        ["cmd", "/c", f"cd /d {root} && saipen search --hex {HEX} --max-matches 2"],
        capture_output=True, text=True, env=env, timeout=180,
    )
    return proc.returncode, proc.stdout + proc.stderr


def in_bash(root: Path, env: dict) -> tuple[int, str]:
    shell = git_bash()
    if shell is None:
        return 127, "no POSIX shell available on this host"
    proc = subprocess.run(
        [shell, "-lc", f"cd '{root}' && saipen search --hex {HEX} --max-matches 2"],
        capture_output=True, text=True, env=env, timeout=180,
    )
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    env = stripped_env()
    root = fixture()
    failures: list[str] = []
    try:
        print(f"fixture: {root}")
        print(f"rg on PATH: {shutil.which('rg', path=env['PATH']) or 'ABSENT'}")
        print(f"opencode bin exists: {OPENCODE_BIN.exists()}")

        for name, runner in (
            ("powershell", in_powershell),
            ("cmd", in_cmd),
            ("bash", in_bash),
        ):
            code, out = runner(root, env)
            served = "src/engine.py" in out.replace("\\", "/")
            print(f"[{name}] rc={code} match={served}")
            print(out.strip()[:600])
            if code != 0 or not served:
                failures.append(f"{name}: rc={code} match={served}")

        # Skill startup: the cold route must be nameable with rg gone.
        status = via_launcher(env, "status", "--json", "--project-root", str(root))
        print(f"[status] rc={status.returncode}")
        if "cold_route" not in status.stdout:
            failures.append("status produced no cold_route without rg")

        # Canonical recovery must remain reachable in the same environment.
        recover = via_launcher(env, "recover", "--project-root", str(root))
        print(
            f"[recover] rc={recover.returncode}: "
            f"{(recover.stdout + recover.stderr).strip()[:200]}"
        )
        if "REPAIRED" not in recover.stdout + recover.stderr:
            failures.append("canonical recovery unreachable")
        state = (root / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        if "phase: BUILD" not in state:
            failures.append("recovery did not repair the phase")

        # Ordinary work must be admissible again afterwards.
        after = via_launcher(env, "search", "--hex", HEX, "--project-root", str(root))
        if after.returncode != 0 or "src/engine.py" not in after.stdout.replace("\\", "/"):
            failures.append("post-recovery search failed")
    finally:
        shutil.rmtree(root, ignore_errors=True)

    if failures:
        print("\nFAILURES: " + "; ".join(failures))
        return 1
    print("\nALL SHELL FAMILIES SERVED SEARCH WITHOUT RIPGREP")
    return 0


if __name__ == "__main__":
    sys.exit(main())

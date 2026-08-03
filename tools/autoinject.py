#!/usr/bin/env python3
"""Re-inject the protocol into every installed agent home when it has moved,
and report the project's current state in one screen.

Two problems, one runner.

The injector copies the protocol into `~/.claude/skills/saipen` and its
siblings rather than linking it, because the readers that matter ignore
junctions (`KNOWLEDGE/traps.md`). Copies go stale silently: nothing in an
installed copy says which revision it came from, so an agent can boot a
protocol several releases behind the clone it was injected from and behave
exactly like one that is current. The standing instruction was "re-run
inject after every git pull", which is a rule with no witness -- the class
this repository keeps closing everywhere else.

So: stamp the installed copy with a digest of what was installed, compare it
against the source on every run, and re-inject only on a real difference.
The digest covers file CONTENT, so a pull that changes nothing changes
nothing, and a local edit to a shipped doc is picked up without a commit.

Second half: an agent driving this project needs to know where it stands
before it acts. That is `saipen status`'s job in a live session, and this is
the same picture for a session that has not started yet.

Never blocks. Exit 0 unless `--check` is asked for and the copies are stale.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent
STAMP = ".saipen_injected"

# Exactly what bootstrap/inject.* copies into an agent home. Kept as a list of
# (relative path, is_tree) so the digest and the injector describe the same
# surface; a file the injector copies and this does not is a file whose
# staleness stays invisible, which is the whole defect.
SHIPPED = [
    ("saipen/BOOT.md", False),
    ("saipen/SKILL.md", False),
    ("saipen/RFC.md", False),
    ("saipen/UI.md", False),
    ("saipen/STYLE.md", False),
    ("saipen/CONFORMANCE.md", False),
    ("VERSION", False),
    ("saipen/phases", True),
    ("tools", True),
    ("extensions/schemas", True),
    ("extensions/templates", True),
    ("extensions/subs", True),
    ("tests/validate.sh", False),
    ("tests/validate.ps1", False),
]

# Where the injector installs. Absence is normal -- an agent home that is not
# installed on this machine is skipped, never created.
TARGETS = [
    Path.home() / ".claude" / "skills" / "saipen",
    Path.home() / ".config" / "opencode" / "skills" / "saipen",
    Path.home() / ".codex" / "skills" / "saipen",
    Path.home() / ".agents" / "skills" / "saipen",
]


def _digest() -> str:
    """Content digest of the shipped surface, path-order stable."""
    h = hashlib.sha256()
    for rel, is_tree in SHIPPED:
        p = HOME / rel
        files = []
        if is_tree and p.is_dir():
            files = sorted(f for f in p.rglob("*")
                           if f.is_file() and "__pycache__" not in f.parts)
        elif p.is_file():
            files = [p]
        for f in files:
            h.update(f.relative_to(HOME).as_posix().encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:16]


def _installed(target: Path) -> str | None:
    stamp = target / STAMP
    if not stamp.is_file():
        return None
    return stamp.read_text(encoding="utf-8").strip() or None


def _run(cmd: list[str], cwd: Path = HOME) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           errors="replace", timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, f"{type(exc).__name__}: {exc}"
    return r.returncode, (r.stdout + r.stderr).strip()


def inject() -> tuple[bool, str]:
    """Run the platform injector. Returns (ok, output tail)."""
    if os.name == "nt":
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-File",
               str(HOME / "bootstrap" / "inject.ps1")]
    else:
        cmd = ["bash", str(HOME / "bootstrap" / "inject.sh")]
    rc, out = _run(cmd)
    return rc == 0, "\n".join(out.splitlines()[-12:])


def stamp_targets(digest: str) -> list[str]:
    """Write the digest into every target that actually exists.

    Only existing targets are stamped: creating one here would install a
    protocol into an agent home the user never set up.
    """
    done = []
    for t in TARGETS:
        if t.is_dir():
            (t / STAMP).write_text(digest + "\n", encoding="utf-8")
            # Every target's leaf is `saipen`, so the leaf names nothing.
            # The agent home is what distinguishes them.
            done.append(next((p for p in t.parts
                              if p.startswith(".")), str(t)))
    return done


def state_report() -> list[str]:
    """The picture an agent needs before it acts. Facts only, no verdict."""
    lines = []
    version = (HOME / "VERSION").read_text(encoding="utf-8").strip() \
        if (HOME / "VERSION").is_file() else "?"

    rc, head = _run(["git", "rev-parse", "--short", "HEAD"])
    head = head if rc == 0 else "no git"
    rc, counts = _run(["git", "rev-list", "--left-right", "--count",
                       "origin/main...HEAD"])
    drift = ""
    if rc == 0 and counts:
        behind, ahead = [*counts.split(), "0", "0"][:2]
        if behind != "0" or ahead != "0":
            drift = f", {behind} behind / {ahead} ahead of origin/main"
    rc, dirty = _run(["git", "status", "--porcelain"])
    if rc == 0:
        n = len([ln for ln in dirty.splitlines() if ln.strip()])
        drift += f", {n} uncommitted file(s)" if n else ", tree clean"
    lines.append(f"protocol: v{version} @ {head}{drift}")

    state = HOME / ".saipen" / "STATE.md"
    if state.is_file():
        fields = {}
        for ln in state.read_text(encoding="utf-8-sig").splitlines():
            if ":" in ln and not ln.startswith("-"):
                k, _, v = ln.partition(":")
                fields[k.strip()] = v.strip().strip('"')
        lines.append(
            f"state: phase {fields.get('phase', '?')}, "
            f"task {fields.get('task', '?')}, "
            f"next_action {fields.get('next_action', '?')[:90]}")

    board = HOME / ".saipen" / "BOARD.md"
    if board.is_file():
        section, counts = None, {}
        for ln in board.read_text(encoding="utf-8-sig").splitlines():
            if ln.startswith("## "):
                section = ln[3:].strip()
            elif ln.startswith("- [") and section:
                counts[section] = counts.get(section, 0) + 1
        lines.append("board: " + ", ".join(
            f"{k} {v}" for k, v in counts.items()) or "board: empty")

    rc, out = _run([sys.executable, str(HOME / "tools" / "validate.py")])
    tail = [ln for ln in out.splitlines()
            if ln.startswith(("Validation", "FAIL"))]
    lines.append("validator: " + (tail[-1] if tail else f"exit {rc}"))
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="report staleness and exit 1 if stale; inject nothing")
    ap.add_argument("--force", action="store_true",
                    help="re-inject even when the digest already matches")
    ap.add_argument("--quiet-when-fresh", action="store_true",
                    help="print nothing when nothing was stale (for timers)")
    args = ap.parse_args(argv)

    digest = _digest()
    present = [t for t in TARGETS if t.is_dir()]
    stale = [t for t in present if _installed(t) != digest]

    if not present:
        print("no agent home installed on this machine -- nothing to inject")
        return 0

    if args.check:
        for t in stale:
            print(f"STALE: {t} (installed {_installed(t) or 'unstamped'}, "
                  f"source {digest})")
        if not stale:
            print(f"fresh: {len(present)} agent home(s) at {digest}")
        return 1 if stale else 0

    if stale or args.force:
        why = "forced" if args.force and not stale else \
            f"{len(stale)} of {len(present)} home(s) stale"
        ok, tail = inject()
        if not ok:
            print(f"INJECT FAILED ({why}):\n{tail}")
            return 0          # never block a timer on a failed inject
        stamped = stamp_targets(digest)
        print(f"injected ({why}) -> {digest}; stamped: {', '.join(stamped)}")
    elif not args.quiet_when_fresh:
        print(f"fresh: {len(present)} agent home(s) at {digest}")

    if stale or args.force or not args.quiet_when_fresh:
        for ln in state_report():
            print(ln)
    return 0


if __name__ == "__main__":
    sys.exit(main())

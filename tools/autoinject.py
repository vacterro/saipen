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
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from saipen_engine.manifest import (
    CACHE_DIRS,
    GENERATED_SUFFIXES,
    copy_tree_members,
    manifest_source,
)

HOME = Path(__file__).resolve().parent.parent
STAMP = ".saipen_injected"

# Where the injector installs. Absence is normal -- an agent home that is not
# installed on this machine is skipped, never created.
TARGETS = [
    Path.home() / ".claude" / "skills" / "saipen",
    Path.home() / ".config" / "opencode" / "skills" / "saipen",
    Path.home() / ".codex" / "skills" / "saipen",
    Path.home() / ".agents" / "skills" / "saipen",
]


def _manifest_source(raw: object) -> Path:
    return manifest_source(HOME, raw)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _manifest_surface() -> list[tuple[Path, bool]]:
    """Return exactly what injectors copy, derived from the runtime manifest."""
    manifest_path = HOME / "saipen" / "MANIFEST.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read runtime manifest {manifest_path}: {exc}") from exc

    try:
        trees = manifest["copy_trees"]
        entries = manifest["files"]
        if not isinstance(trees, list) or not trees or not isinstance(entries, list):
            raise TypeError("copy_trees/files must be nonempty arrays")
        surface: list[tuple[Path, bool]] = []
        tree_roots: list[Path] = []
        for entry in trees:
            source, _members = copy_tree_members(HOME, entry["src"])
            surface.append((source, True))
            tree_roots.append(source)
        for entry in entries:
            if entry.get("required") is not True:
                continue
            source = _manifest_source(entry["src"])
            if any(_is_within(source, tree) for tree in tree_roots):
                continue
            if not source.is_file() or source.is_symlink():
                raise RuntimeError(f"runtime manifest file missing or symlinked: {entry['src']}")
            surface.append((source, False))
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"runtime manifest shape invalid: {exc}") from exc
    return surface


def _content_bytes(path: Path) -> bytes:
    """The file's CONTENT, with line endings normalised to LF (T-1253).

    The digest is a content digest -- that is what it has always claimed to be
    -- and a line ending is transport, not content. It has to be, because the
    two sides of the comparison come through different transports: the clone
    holds LF while the snapshot git produces for the scheduled injector holds
    CRLF, so `saipen/BOOT.md` is 4972 bytes here and 5063 bytes there with not
    one character of difference. Hashing raw bytes made a home refreshed
    seconds ago report STALE forever, which is the same as having no witness.

    A file that is not valid UTF-8 is hashed byte-for-byte: it is not text, so
    there are no line endings to normalise and guessing would be worse.
    """
    raw = path.read_bytes()
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _digest() -> str:
    """Content digest of the shipped surface, path-order stable."""
    h = hashlib.sha256()

    def frame(kind: bytes, path: Path, payload: bytes = b"") -> None:
        relative = path.relative_to(HOME.resolve()).as_posix().encode("utf-8")
        for part in (kind, relative, payload):
            h.update(len(part).to_bytes(8, "big"))
            h.update(part)

    def generated(path: Path) -> bool:
        # Same rule as the copier, from the same constant: a file the
        # injector would never ship must not move the digest that decides
        # whether what it shipped is current.
        relative = path.relative_to(HOME.resolve())
        return bool(CACHE_DIRS.intersection(relative.parts)) or (
            path.suffix in GENERATED_SUFFIXES
        )

    for path, is_tree in _manifest_surface():
        if is_tree:
            members = sorted(
                path.rglob("*"),
                key=lambda item: item.relative_to(HOME.resolve()).as_posix().encode(),
            )
        else:
            members = [path]
        for member in members:
            if generated(member):
                continue
            if member.is_symlink():
                raise RuntimeError(
                    f"runtime manifest surface contains unsupported symlink: {member}"
                )
            if member.is_dir():
                frame(b"D", member)
            elif member.is_file():
                frame(b"F", member, _content_bytes(member))
            else:
                raise RuntimeError(f"runtime manifest surface contains unsupported entry: {member}")
    return h.hexdigest()[:16]


def read_stamp(target: Path) -> dict | None:
    """The freshness record beside an installed protocol copy, or None.

    Two shapes are accepted on purpose. The original stamp was a bare digest
    line, and copies written by an older injector are still on disk; refusing
    to read them would turn every pre-existing install into "no record at all",
    which is the very blindness the stamp exists to remove.
    """
    stamp = target / STAMP
    if not stamp.is_file():
        return None
    raw = stamp.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    if raw.startswith("{"):
        try:
            record = json.loads(raw)
        except ValueError:
            return None
        return record if isinstance(record, dict) and record.get("digest") else None
    return {"digest": raw}


def _installed(target: Path) -> str | None:
    record = read_stamp(target)
    return record.get("digest") if record else None


def _source_head() -> str | None:
    rc, out = _run(["git", "rev-parse", "HEAD"])
    return out.strip() if rc == 0 and out.strip() else None


def _run(cmd: list[str], cwd: Path = HOME) -> tuple[int, str]:
    kwargs = dict(capture_output=True, text=True, errors="replace", timeout=300)
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        r = subprocess.run(cmd, cwd=cwd, **kwargs)
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, f"{type(exc).__name__}: {exc}"
    return r.returncode, (r.stdout + r.stderr).strip()


def inject() -> tuple[bool, str]:
    """Run the platform injector. Returns (ok, output tail)."""
    if os.name == "nt":
        cmd = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(HOME / "bootstrap" / "inject.ps1"),
        ]
    else:
        cmd = ["bash", str(HOME / "bootstrap" / "inject.sh")]
    rc, out = _run(cmd)
    return rc == 0, "\n".join(out.splitlines()[-12:])


def stamp_targets(digest: str) -> list[str]:
    """Write the digest into every target that actually exists.

    Only existing targets are stamped: creating one here would install a
    protocol into an agent home the user never set up.
    """
    # T-1249: a digest alone cannot tell a BOOTING agent anything -- comparing
    # it needs the clone, which a consumer machine may not have. The install
    # time and source head can be read on their own, so an agent that loads a
    # copy last refreshed days ago can say so instead of silently running an
    # old protocol. That was the actual incident: an agent read a pre-W4 CORE.md
    # looking for a shortcut table that had moved, and had no way to know.
    record = {
        "digest": digest,
        "installed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    head = _source_head()
    if head:
        record["source_head"] = head
    payload = json.dumps(record, indent=2, sort_keys=True) + "\n"
    done = []
    for t in TARGETS:
        if t.is_dir():
            (t / STAMP).write_text(payload, encoding="utf-8")
            # Every target's leaf is `saipen`, so the leaf names nothing.
            # The agent home is what distinguishes them.
            done.append(next((p for p in t.parts if p.startswith(".")), str(t)))
    return done


def state_report() -> list[str]:
    """The picture an agent needs before it acts. Facts only, no verdict."""
    lines = []
    version = (
        (HOME / "VERSION").read_text(encoding="utf-8").strip()
        if (HOME / "VERSION").is_file()
        else "?"
    )

    rc, head = _run(["git", "rev-parse", "--short", "HEAD"])
    head = head if rc == 0 else "no git"
    rc, counts = _run(["git", "rev-list", "--left-right", "--count", "origin/main...HEAD"])
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
            f"next_action {fields.get('next_action', '?')[:90]}"
        )

    board = HOME / ".saipen" / "BOARD.md"
    if board.is_file():
        section, counts = None, {}
        for ln in board.read_text(encoding="utf-8-sig").splitlines():
            if ln.startswith("## "):
                section = ln[3:].strip()
            elif ln.startswith("- [") and section:
                counts[section] = counts.get(section, 0) + 1
        lines.append("board: " + ", ".join(f"{k} {v}" for k, v in counts.items()) or "board: empty")

    rc, out = _run([sys.executable, str(HOME / "tools" / "validate.py")])
    tail = [ln for ln in out.splitlines() if ln.startswith(("Validation", "FAIL"))]
    lines.append("validator: " + (tail[-1] if tail else f"exit {rc}"))
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check", action="store_true", help="report staleness and exit 1 if stale; inject nothing"
    )
    ap.add_argument(
        "--force", action="store_true", help="re-inject even when the digest already matches"
    )
    ap.add_argument(
        "--quiet-when-fresh",
        action="store_true",
        help="print nothing when nothing was stale (for timers)",
    )
    ap.add_argument(
        "--stamp-only",
        action="store_true",
        help="write the freshness stamp into every installed target; copy nothing",
    )
    args = ap.parse_args(argv)

    try:
        digest = _digest()
    except RuntimeError as exc:
        print(f"INJECT FAILED (runtime manifest): {exc}")
        return 1 if args.check else 0
    present = [t for t in TARGETS if t.is_dir()]
    stale = [t for t in present if _installed(t) != digest]

    if not present:
        print("no agent home installed on this machine -- nothing to inject")
        return 0

    if args.stamp_only:
        # T-1252: `bootstrap/inject.ps1` is the injector the scheduled task
        # runs, and it copies the protocol without writing the stamp this
        # module compares against -- so every refreshed home read as
        # "installed unstamped" forever and a genuinely drifted copy was
        # indistinguishable from a current one. The digest has exactly ONE
        # owner (`_digest`), so the PowerShell path calls back here rather
        # than growing a second implementation that would drift from it.
        stamped = stamp_targets(digest)
        for t in stamped:
            print(f"stamped: {t} at {digest}")
        if not stamped:
            print("no agent home installed on this machine -- nothing to stamp")
        return 0

    if args.check:
        for t in stale:
            print(f"STALE: {t} (installed {_installed(t) or 'unstamped'}, source {digest})")
        if not stale:
            print(f"fresh: {len(present)} agent home(s) at {digest}")
        return 1 if stale else 0

    if args.quiet_when_fresh:
        if stale or args.force:
            why = (
                "forced"
                if args.force and not stale
                else f"{len(stale)} of {len(present)} home(s) stale"
            )
            ok, tail = inject()
            if ok:
                stamp_targets(digest)
            else:
                print(f"INJECT FAILED ({why}):\n{tail}")
        return 0

    if stale or args.force:
        why = (
            "forced"
            if args.force and not stale
            else f"{len(stale)} of {len(present)} home(s) stale"
        )
        ok, tail = inject()
        if not ok:
            print(f"INJECT FAILED ({why}):\n{tail}")
            return 0  # never block a timer on a failed inject
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

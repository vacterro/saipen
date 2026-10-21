"""The SAIPEN block inside a project's own instruction file (T-1654, SRC-188).

An older generation told the agent that created a project to write a block
between `<!-- SAIPEN:BEGIN -->` and `<!-- SAIPEN:END -->` into the project's
`AGENTS.md`. That block names an absolute path into the profile of whoever ran
the agent and tells the reader to clone the public repository when the path is
missing. Every later generation stopped writing it and none reported it, so it
outlives every upgrade: an account that cannot read the named path is told to
clone, and the machine runtime that exists for exactly that account is never
tried.

This module is the one owner of that block. It reads the project's instruction
files, says which carry a block of another generation, and replaces such a
block with the current one. Three properties are the whole contract:

* the current block is RELOCATABLE -- no absolute path, only the launcher
  order every account can follow -- so it is one constant, compared by content;
* the repair replaces the bytes from the opening marker to the closing marker
  and nothing else. Files are handled as bytes, never decoded, so whatever
  surrounds the block survives in whatever encoding it was written;
* a block is never created, and text outside the markers is never rewritten:
  the markers are the only bytes in a project file that are SAIPEN's.

The block names its own revision. Two installs of different generations reach
one project (the operator's installed copy and the machine runtime are
refreshed at different moments), and without it each would rewrite the
other's block on every run. An engine leaves a HIGHER revision alone -- unless
that block breaks a rule every revision keeps (it tells the reader to clone,
or names an absolute path), in which case the number is not believed.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path

from .paths import safe_atomic_write_bytes

BEGIN = b"<!-- SAIPEN:BEGIN -->"
END = b"<!-- SAIPEN:END -->"

#: The files a host reads from a project root as standing instructions. A
#: closed list: the block is looked for where a host would load it, never by
#: walking the project.
INSTRUCTION_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    ".cursorrules",
    ".windsurfrules",
    ".clinerules",
    ".github/copilot-instructions.md",
)

#: An instruction file is prose. One larger than this is not read into memory.
MAX_BYTES = 4 * 1024 * 1024

STATUS_ACTION = "saipen host instructions"
REPAIR_ACTION = "saipen host instructions repair"

CODE_CURRENT = "PROJECT_BLOCK_CURRENT"
CODE_ABSENT = "PROJECT_BLOCK_ABSENT"
CODE_STALE = "PROJECT_BLOCK_STALE"
CODE_MALFORMED = "PROJECT_BLOCK_MALFORMED"
CODE_UNREADABLE = "PROJECT_BLOCK_UNREADABLE"
CODE_REPAIRED = "PROJECT_BLOCK_REPAIRED"
CODE_FAILED = "PROJECT_BLOCK_REPAIR_FAILED"
CODE_NEWER = "PROJECT_BLOCK_NEWER"
NOT_SAIPEN = "NOT_SAIPEN_PROJECT"

CURRENT = "CURRENT"
ABSENT = "ABSENT"
STALE = "STALE"
MALFORMED = "MALFORMED"
UNREADABLE = "UNREADABLE"
LINKED = "LINKED"
HOST_SURFACE = "HOST_SURFACE"
NEWER = "NEWER"

#: The revision of the block text below. Raise it with EVERY change of that
#: text: an engine that changed the text and kept the number would be undone
#: by, and would undo, every install still writing the old text.
BLOCK_REVISION = 1

#: The current block. ASCII, LF, no absolute path. Editing it makes every
#: block written before the edit another generation, which is the intent.
#:
#: It must bootstrap a host that delivers no block of its own (several
#: registered hosts have no home-level instruction surface), so it names the
#: first command for each kind of turn and where the cold-start kernel is: a
#: path the runtime reports, never one written here. `continue` may answer
#: with an executed step that carries no cold route, so the block also names
#: the one command that always does.
_CURRENT_LINES = (
    "<!-- SAIPEN:BEGIN -->",
    f"## saipen protocol (project block {BLOCK_REVISION})",
    "This project is SAIPEN-managed: its memory is `.saipen/` here. Never edit",
    "`.saipen/` BOARD, LOG or STATE by hand and never work around the protocol.",
    "New task: run `saipen start '<the task, one line>'`. No new task (`cc`, bare",
    "`saipen`): run `saipen continue --json`. Do what the answer says. Before the",
    "first reply read the `boot` document named under `cold_route` in that answer",
    "(`saipen status --json` always names it).",
    "LAUNCHER ORDER -- use the first that runs:",
    "1. `saipen` on PATH;",
    "2. `<saipen_home>/bin/saipen` (POSIX, Git Bash) or",
    "   `<saipen_home>\\bin\\saipen.cmd` (cmd, PowerShell), where `<saipen_home>`",
    "   is the `saipen_home:` value in `.saipen/STATE.md`;",
    "3. `%ProgramData%\\SAI\\SAIPEN\\bin\\saipen.cmd`, the machine runtime, when",
    "   that home belongs to another user and cannot be read.",
    "None runs: report which step failed and stop. Never search the disk for",
    "SAIPEN, never clone or download a copy of it, and never ask for access to",
    "another user's profile.",
    "<!-- SAIPEN:END -->",
)

_DRIVE_PATH = re.compile(rb"[A-Za-z]:[\\/][^\s`'\"<>|]*")
_HOME_PATH = re.compile(rb"(?<![\w<>.])/(?:home|Users|root)/[^\s`'\"<>|]*")
_SKILL_HOME = re.compile(
    rb"[\\/]\.(?:agents|claude|codex|gemini|kiro|cursor|config[\\/]opencode)[\\/]skills[\\/]saipen",
    re.IGNORECASE,
)
_CLONE = re.compile(rb"\bclone\b", re.IGNORECASE)
#: A clone the sentence forbids: the negation and the verb in one clause.
#: `No install? clone ...` is an instruction; `never clone ...` is not.
_FORBIDDEN_CLONE = re.compile(
    rb"\b(?:never|not|nor|don't)\b[^.;:?!\r\n]{0,60}\bclone\b", re.IGNORECASE
)
_SAIPEN = re.compile(rb"saipen", re.IGNORECASE)
#: The heading line is how an OLDER engine recognises a newer block, so every
#: later revision keeps this exact shape and changes only the number.
_REVISION = re.compile(
    rb"^## saipen protocol \(project block (\d{1,6})\)[ \t]*\r?$", re.MULTILINE
)


def _tells_to_clone(line: bytes) -> bool:
    """A clone the line instructs: one that is left once every clause that
    forbids a clone is taken out, so `never clone it; clone X` still tells."""
    return bool(_CLONE.search(_FORBIDDEN_CLONE.sub(b"", line)))

#: How many outside-the-block lines one report names.
_OUTSIDE_LIMIT = 8


def current_block(newline: bytes = b"\n") -> bytes:
    """The current block, opening marker to closing marker, in one line ending."""
    return newline.join(line.encode("ascii") for line in _CURRENT_LINES)


def _normalized(block: bytes) -> bytes:
    return block.replace(b"\r\n", b"\n").strip()


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def _span(data: bytes) -> tuple[int, int] | str:
    """The one marker pair as `(start, end)`, or why there is not exactly one."""
    opens = data.count(BEGIN)
    closes = data.count(END)
    if opens != 1 or closes != 1:
        return f"{opens} opening and {closes} closing marker(s); exactly one pair is a block"
    start = data.index(BEGIN)
    end = data.index(END)
    if end < start:
        return "the closing marker comes before the opening one"
    return start, end + len(END)


def _revision(block: bytes) -> int | None:
    """The revision a block names for itself, or None for one that names none."""
    match = _REVISION.search(block)
    return int(match.group(1)) if match else None


def _steering(block: bytes) -> list[str]:
    """What a block does that no revision may: the reasons it steers its
    reader away from the runtime, most harmful first. Empty for a sound one."""
    reasons: list[str] = []
    if any(_tells_to_clone(line) for line in block.splitlines()):
        reasons.append("tells the agent to clone a repository")
    path = _DRIVE_PATH.search(block) or _HOME_PATH.search(block)
    if path is not None:
        named = path.group(0).decode("utf-8", "replace")[:80]
        reasons.append(f"names an absolute path ({named})")
    return reasons


def _outside(name: str, data: bytes, span: tuple[int, int] | None) -> list[dict]:
    """Lines outside the block that send a reader to a private install.

    They are the operator's text: named so they can be seen, never rewritten.
    """
    found: list[dict] = []
    line_no = 0
    offset = 0
    for line in data.splitlines(keepends=True):
        line_no += 1
        start, offset = offset, offset + len(line)
        if span is not None and start < span[1] and offset > span[0]:
            continue
        kind = None
        if _SKILL_HOME.search(line):
            kind = "per-user-skill-home"
        elif _SAIPEN.search(line) and _tells_to_clone(line):
            kind = "clone-instruction"
        if kind is not None:
            found.append({"file": name, "line": line_no, "kind": kind})
    return found


def host_surfaces() -> frozenset[str]:
    """Every host-level instruction file the installer writes, as comparable paths.

    The same two markers delimit the host-level activation block there, and
    that block has its own owner (`saipen host doctor`). A project root that
    is also a host's configuration directory must not have it replaced by the
    project block: two writers of one marker pair would undo each other on
    every run. An unreadable registry names no surface, so nothing is skipped.
    """
    from .host_bootstrap import _expand, _load_adapters

    found: set[str] = set()
    for adapter in _load_adapters().values():
        surfaces = list(adapter.get("instruction_surfaces") or [])
        for loader in adapter.get("instruction_loaders") or []:
            if isinstance(loader, dict):
                surfaces.extend(loader.get("surfaces") or [])
        for surface in surfaces:
            path = _expand(surface)
            if path is None or str(path).startswith("$"):
                continue  # an unset variable names nothing on this machine
            found.add(os.path.normcase(os.path.abspath(path)))
    return frozenset(found)


def _read(path: Path) -> tuple[bytes | None, str | None, str | None]:
    """`(data, status, reason)`: the bytes, or the status that replaces them."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None, None, None
    except OSError as exc:
        return None, UNREADABLE, f"cannot be examined: {exc}"
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if stat.S_ISLNK(info.st_mode) or (getattr(info, "st_file_attributes", 0) or 0) & reparse:
        return None, LINKED, "a link, not a file of this project; not followed"
    if not stat.S_ISREG(info.st_mode):
        return None, None, None
    if info.st_size > MAX_BYTES:
        return None, UNREADABLE, f"larger than {MAX_BYTES} bytes; not read"
    try:
        return path.read_bytes(), None, None
    except OSError as exc:
        return None, UNREADABLE, f"cannot be read: {exc}"


def inspect_file(
    root: Path, name: str, surfaces: frozenset[str] = frozenset()
) -> tuple[dict | None, list[dict], bytes | None]:
    """One instruction file: its row, its outside-the-block lines, its bytes.

    The row is None when the project has no such file. A file that is one of
    `surfaces` (see `host_surfaces`) is named and not read.
    """
    path = root / name
    if os.path.normcase(os.path.abspath(path)) in surfaces:
        if not path.is_file():
            return None, [], None
        reason = "a host-level instruction file; `saipen host doctor` owns its block"
        return {"file": name, "status": HOST_SURFACE, "reasons": [reason]}, [], None
    data, status, reason = _read(path)
    if data is None:
        if status is None:
            return None, [], None
        return {"file": name, "status": status, "reasons": [reason]}, [], None
    span = _span(data)
    if isinstance(span, str):
        if BEGIN not in data and END not in data:
            return {"file": name, "status": ABSENT, "reasons": []}, _outside(name, data, None), data
        return (
            {"file": name, "status": MALFORMED, "reasons": [span]},
            _outside(name, data, None),
            data,
        )
    block = data[span[0] : span[1]]
    row = {
        "file": name,
        "status": CURRENT,
        "reasons": [],
        "sha256": _digest(_normalized(block)),
        "bytes": len(block),
        "newline": "CRLF" if b"\r\n" in block else "LF",
    }
    if _normalized(block) != current_block(b"\n"):
        steering = _steering(block)
        revision = _revision(block)
        if not steering and revision is not None and revision > BLOCK_REVISION:
            row["status"] = NEWER
            row["reasons"] = [
                f"written by a newer SAIPEN (block {revision}); this engine writes "
                f"block {BLOCK_REVISION} and leaves it"
            ]
        else:
            row["status"] = STALE
            row["reasons"] = [*steering, "is not the current project block"]
    return row, _outside(name, data, span), data


def _verdict(rows: list[dict]) -> tuple[str, str | None, str | None]:
    """`(code, action, detail)` for a project's rows, worst status first."""
    by_status: dict[str, list[dict]] = {}
    for row in rows:
        by_status.setdefault(row["status"], []).append(row)
    if MALFORMED in by_status:
        row = by_status[MALFORMED][0]
        return (
            CODE_MALFORMED,
            f"edit {row['file']} to carry exactly one {BEGIN.decode()} ... {END.decode()} "
            f"pair, then run `{REPAIR_ACTION}`",
            f"{row['file']}: {row['reasons'][0]}",
        )
    if STALE in by_status:
        row = by_status[STALE][0]
        return (
            CODE_STALE,
            REPAIR_ACTION,
            f"{row['file']} carries a SAIPEN block of another generation: "
            + "; ".join(row["reasons"][:2]),
        )
    if UNREADABLE in by_status:
        row = by_status[UNREADABLE][0]
        return (
            CODE_UNREADABLE,
            f"make {row['file']} readable to this account and smaller than {MAX_BYTES} "
            f"bytes, then run `{STATUS_ACTION}`",
            f"{row['file']}: {row['reasons'][0]}",
        )
    if NEWER in by_status:
        row = by_status[NEWER][0]
        return CODE_NEWER, None, f"{row['file']}: {row['reasons'][0]}"
    if CURRENT in by_status:
        return CODE_CURRENT, None, None
    return CODE_ABSENT, None, None


def _not_a_project(root: Path) -> dict:
    return {
        "ok": False,
        "code": NOT_SAIPEN,
        "project_root": str(root),
        "files": [],
        "outside_block": [],
        "written": [],
        "action": None,
        "detail": f"no .saipen/ under {root}; a project's instruction block is asked of a project",
    }


def status(project_root: Path | str) -> dict:
    """Read-only: which instruction files of this project carry a SAIPEN block,
    and of which generation. `ok` is true when nothing needs an action."""
    root = Path(project_root)
    if not (root / ".saipen").is_dir():
        return _not_a_project(root)
    rows: list[dict] = []
    outside: list[dict] = []
    surfaces = host_surfaces()
    for name in INSTRUCTION_FILES:
        row, lines, _data = inspect_file(root, name, surfaces)
        if row is not None:
            rows.append(row)
            outside.extend(lines)
    code, action, detail = _verdict(rows)
    return {
        "ok": code in (CODE_CURRENT, CODE_ABSENT, CODE_NEWER),
        "code": code,
        "project_root": str(root),
        "files": rows,
        "outside_block": outside[:_OUTSIDE_LIMIT],
        "action": action,
        "detail": detail,
    }


def projection(project_root: Path | str) -> dict:
    """The verdict another diagnostic embeds: code, action and the files that
    carry a block. Never raises: `continue` and `start` embed it, and an
    advisory about a project file must not be able to stop either."""
    try:
        report = status(project_root)
    except Exception as exc:  # a report is never failed by what it reports
        return {"code": CODE_UNREADABLE, "action": None, "detail": str(exc)[:200], "files": []}
    return {
        "code": report["code"],
        "action": report["action"],
        "detail": report["detail"],
        "files": [
            {"file": row["file"], "status": row["status"]}
            for row in report["files"]
            if row["status"] != ABSENT
        ],
    }


def repair(project_root: Path | str, *, dry_run: bool = False) -> dict:
    """Replace every block of another generation with the current one.

    Only a file whose markers form exactly one pair is written, and only from
    its opening marker to its closing one, in the line ending the old block
    used. A current project is answered with zero writes; a project with no
    block gets none. The answer is the state AFTER the repair, plus what was
    written.
    """
    root = Path(project_root)
    if not (root / ".saipen").is_dir():
        return _not_a_project(root)
    written: list[dict] = []
    failed: list[str] = []
    surfaces = host_surfaces()
    for name in INSTRUCTION_FILES:
        row, _lines, data = inspect_file(root, name, surfaces)
        if row is None or row["status"] != STALE or data is None:
            continue
        span = _span(data)
        if isinstance(span, str):  # pragma: no cover - STALE implies one pair
            continue
        newline = b"\r\n" if row["newline"] == "CRLF" else b"\n"
        updated = data[: span[0]] + current_block(newline) + data[span[1] :]
        record = {
            "file": name,
            "before_sha256": _digest(data),
            "after_sha256": _digest(updated),
            "block_bytes_before": span[1] - span[0],
            "block_bytes_after": len(updated) - len(data) + span[1] - span[0],
            "outside_bytes_identical": True,
        }
        if not dry_run:
            path = root / name
            try:
                mode = stat.S_IMODE(path.lstat().st_mode)
                safe_atomic_write_bytes(
                    path, updated, kind="project instruction file", ownership_root=root
                )
                # The replacement is a NEW file, created owner-only. The file
                # it replaces was readable by whoever could read it before,
                # and a repair must not be what takes that away.
                os.chmod(path, mode)
                landed = path.read_bytes()
            except (OSError, ValueError) as exc:
                failed.append(f"{name}: {exc}")
                continue
            record["outside_bytes_identical"] = (
                landed[: span[0]] == data[: span[0]]
                and landed[len(landed) - (len(data) - span[1]) :] == data[span[1] :]
                and landed == updated
            )
            if not record["outside_bytes_identical"]:
                failed.append(f"{name}: the bytes read back are not the bytes written")
        written.append(record)
    after = status(root)
    if failed:
        # The same command again would be refused the same way: the action is
        # what has to change first, and the detail says why it was refused.
        name = failed[0].split(":", 1)[0]
        return {
            **after,
            "ok": False,
            "code": CODE_FAILED,
            "written": written,
            "dry_run": dry_run,
            "action": (
                f"make {name} a regular file this account may replace, "
                f"then run `{REPAIR_ACTION}`"
            ),
            "detail": "; ".join(failed)[:400],
        }
    if dry_run:
        return {**after, "written": written, "dry_run": True}
    code = CODE_REPAIRED if written and after["ok"] else after["code"]
    return {**after, "code": code, "written": written, "dry_run": False}


__all__ = [
    "BEGIN",
    "BLOCK_REVISION",
    "CODE_ABSENT",
    "CODE_CURRENT",
    "CODE_FAILED",
    "CODE_MALFORMED",
    "CODE_NEWER",
    "CODE_REPAIRED",
    "CODE_STALE",
    "CODE_UNREADABLE",
    "END",
    "INSTRUCTION_FILES",
    "NOT_SAIPEN",
    "REPAIR_ACTION",
    "STATUS_ACTION",
    "current_block",
    "host_surfaces",
    "inspect_file",
    "projection",
    "repair",
    "status",
]

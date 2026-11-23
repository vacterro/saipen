"""A project's declared suite as typed evidence (T-1658).

The operator checkpoint states validation, and for a project that does not
carry SAIPEN's own unit family it could state the conformance verdict only.
The suite result of such a project (measured 2026-10-07: 4999 passed, 23
skipped, 0 red) existed as model-written LOG prose, which the digest rightly
never parses -- so the one number the operator asks about was not on the
surface at all.

This module is the typed path for it, in three parts:

* **Declaration.** The project names ONE suite command. A narrower invocation
  is a different command digest and is never reported as the suite -- the
  defect `core_unit` closed for this repository (T-1344), closed here for any.
* **Record.** The engine executes the declared command itself and writes what
  it measured: the command and its digest, the exit code, the totals read from
  the runner's own summary, and the content identity of the tree it left.
* **Reader.** The digest takes totals from a record file of the declared
  command whose tree is the current tree. It never reads a number from LOG
  text, so prose about a run is not a run.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

MARKER = "SUITE-EVIDENCE"
SCHEMA_VERSION = 1
RECORD_DIR_REL = ".saipen/evidence/suite"
DECLARATION_REL = RECORD_DIR_REL + "/declaration.json"
DECLARATION_KIND = "saipen-suite-declaration"
RECORD_KIND = "saipen-suite-record"
DEFAULT_TIMEOUT_S = 3600
MAX_TIMEOUT_S = 6 * 3600
#: The runner's summary is the last thing it prints; totals are read from this
#: much of the end of each stream, never from the whole output.
SUMMARY_TAIL_CHARS = 65536
#: What a record keeps of each stream: enough to read the summary a reader
#: would look for, bounded so a record never becomes a log.
KEPT_TAIL_CHARS = 2000
#: Canonical state is outside the subject: every checkpoint rewrites it, so a
#: record would go stale the moment its own LOG line landed (as in core_unit).
SUBJECT_EXCLUDED = ".saipen/"

STATUSES = ("PASS", "FAIL", "TIMEOUT")

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_PYTEST_LINE_RE = re.compile(
    r"^(?:=+ )?(?P<counts>\d+ [a-z]+(?:, \d+ [a-z]+)*) in \d+(?:\.\d+)?s"
    r"(?: \([0-9:]+\))?(?: =+)?$"
)
_PYTEST_COUNT_RE = re.compile(r"(\d+) ([a-z]+)")
#: pytest's own outcome words. A word outside this set is not a pytest summary.
_PYTEST_WORDS = frozenset(
    {
        "passed", "failed", "error", "errors", "skipped", "xfailed", "xpassed",
        "deselected", "warning", "warnings", "rerun", "reruns",
    }
)
_UNITTEST_RAN_RE = re.compile(r"^Ran (\d+) tests? in ", re.MULTILINE)
_UNITTEST_TALLY_RE = re.compile(r"^(OK|FAILED)\b(?: \((.*)\))?\s*$", re.MULTILINE)
_UNITTEST_FIELD_RE = re.compile(r"\b([a-z ]+)=(\d+)")
_EVIDENCE_RE = re.compile(
    r"^" + MARKER + r" (?P<verdict>PASS|FAIL)\b.*?"
    r"\brecord:(?P<record>\S+) sha256:(?P<sha>[0-9a-f]{64})\b"
)


def command_digest(command) -> str:
    """The identity of one argv: the same words in the same order, nothing else."""
    text = json.dumps(list(command), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _command_problem(command) -> str | None:
    if not isinstance(command, (list, tuple)) or not command:
        return "the suite command is empty"
    for word in command:
        if not isinstance(word, str) or not word or "\x00" in word:
            return "the suite command carries an empty or non-text word"
    return None


def _timeout_ok(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 < value <= MAX_TIMEOUT_S


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _project_root_of(path: Path) -> Path | None:
    """The project root above `path`'s `.saipen/`: the owned-path proof stops there."""
    for parent in Path(path).parents:
        if parent.name == ".saipen":
            return parent.parent
    return None


def _write_json(path: Path, data: dict) -> None:
    """One owned atomic write; LF bytes, so a record's digest is the same on any host."""
    from .paths import safe_atomic_write_bytes

    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    safe_atomic_write_bytes(
        path, text.encode("utf-8"), kind="suite evidence", ownership_root=_project_root_of(path)
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ------------------------------------------------------------- declaration


def load_declaration(root: Path | str) -> tuple[dict | None, str | None]:
    """The declared suite, or (None, None) when the project declares none.

    A declaration that is present and unusable is an error, not an absence: a
    damaged file read as "none declared" would let the next declare silently
    replace a command nobody saw.
    """
    path = Path(root) / DECLARATION_REL
    if not path.is_file():
        return None, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"{DECLARATION_REL} is unreadable: {exc}"
    if (
        not isinstance(data, dict)
        or data.get("kind") != DECLARATION_KIND
        or data.get("schema") != SCHEMA_VERSION
    ):
        return None, f"{DECLARATION_REL} is not a schema {SCHEMA_VERSION} suite declaration"
    problem = _command_problem(data.get("command"))
    if problem:
        return None, f"{DECLARATION_REL}: {problem}"
    if data.get("command_sha256") != command_digest(data["command"]):
        return None, f"{DECLARATION_REL}: command_sha256 does not match its command"
    timeout = data.get("timeout_s")
    if not _timeout_ok(timeout):
        return None, f"{DECLARATION_REL}: timeout_s is outside 1..{MAX_TIMEOUT_S}"
    return data, None


def declare(root: Path | str, command, *, timeout: int | None = None) -> dict:
    """Write the project's one suite command; returns what changed."""
    problem = _command_problem(command)
    if problem:
        raise ValueError(problem)
    seconds = DEFAULT_TIMEOUT_S if timeout is None else timeout
    if not _timeout_ok(seconds):
        raise ValueError(f"the suite timeout is outside 1..{MAX_TIMEOUT_S} seconds")
    base = Path(root)
    previous, _error = load_declaration(base)
    data = {
        "schema": SCHEMA_VERSION,
        "kind": DECLARATION_KIND,
        "command": list(command),
        "command_sha256": command_digest(command),
        "timeout_s": seconds,
        "declared_utc": _utc_now(),
    }
    _write_json(base / DECLARATION_REL, data)
    return {
        "declaration": data,
        "previous_sha256": (previous or {}).get("command_sha256"),
        "path": DECLARATION_REL,
    }


def declaration_line(result: dict) -> str:
    """The LOG text that records one declaration; it carries no suite number."""
    data = result["declaration"]
    old = result.get("previous_sha256")
    origin = "first declaration" if not old else f"replaces command:{old[:16]}"
    return (
        f"suite declared -- command:{data['command_sha256'][:16]} "
        f"words:{len(data['command'])} timeout_s:{data['timeout_s']} ({origin})"
    )


def withdraw(root: Path | str) -> dict:
    """Remove the declaration, damaged or not; its records stay as history.

    A declaration with no inverse could only be undone by writing into the
    namespace a file tool is refused in, so the engine owns the removal too.
    Raises ``LookupError`` when nothing is declared.
    """
    from .paths import safe_unlink_owned

    base = Path(root)
    previous, error = load_declaration(base)
    if previous is None and error is None:
        raise LookupError("no suite is declared for this project")
    if not safe_unlink_owned(base / DECLARATION_REL, kind="suite declaration", ownership_root=base):
        raise LookupError("no suite is declared for this project")
    return {"previous_sha256": (previous or {}).get("command_sha256"), "was_invalid": error}


def withdrawal_line(result: dict) -> str:
    """The LOG text that records one withdrawal."""
    old = result.get("previous_sha256")
    return "suite withdrawn -- " + (f"command:{old[:16]}" if old else "an unreadable declaration")


# ------------------------------------------------------------------ subject


def _git(base: Path, *args: str, data: bytes | None = None) -> bytes | None:
    try:
        out = subprocess.run(
            ["git", "-c", "core.quotepath=off", *args],
            cwd=base,
            # Bytes both ways: paths are git's own UTF-8, never the host
            # locale. No shared stdin and a bound, as everywhere a git child
            # is read; `input` supplies the pipe when there is something to say.
            input=data,
            stdin=subprocess.DEVNULL if data is None else None,
            capture_output=True,
            check=False,
            timeout=300,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 else None


def _worktree_blobs(base: Path, paths: list[bytes]) -> dict[bytes, bytes] | None:
    """Blob ids of working-tree files, hashed by git and written nowhere."""
    # One name per line, and git unquotes a line that opens with a quote: a
    # name carrying either is hashed by its own call instead.
    plain = [path for path in paths if b"\n" not in path and not path.startswith(b'"')]
    found: dict[bytes, bytes] = {}
    if plain:
        out = _git(base, "hash-object", "--stdin-paths", data=b"\n".join(plain) + b"\n")
        ids = out.split() if out is not None else []
        if len(ids) != len(plain):
            return None
        found.update(zip(plain, ids))
    for path in paths:
        if path in found:
            continue
        out = _git(base, "hash-object", "--", os.fsdecode(path))
        if out is None:
            return None
        found[path] = out.strip()
    return found


def _git_subject(base: Path) -> str | None:
    listed = _git(base, "ls-files", "-s", "-z")
    changed = _git(base, "ls-files", "-m", "-d", "-o", "--exclude-standard", "-t", "-z")
    if listed is None or changed is None:
        return None
    excluded = SUBJECT_EXCLUDED.encode("ascii")
    entries: dict[bytes, bytes] = {}
    for item in listed.split(b"\0"):
        head, tab, path = item.partition(b"\t")
        fields = head.split()
        if not tab or len(fields) != 3 or path.startswith(excluded):
            continue
        entries[path] = fields[1]
    rehash: list[bytes] = []
    for item in changed.split(b"\0"):
        _tag, space, path = item.partition(b" ")
        if not space or not path or path.startswith(excluded):
            continue
        target = base / os.fsdecode(path)
        if target.is_file():
            rehash.append(path)
        elif target.is_dir():
            # An untracked nested repository: listed as a directory, never
            # entered. Its presence is the fact; its content is its own tree.
            entries[path] = b"directory"
        else:
            entries.pop(path, None)
    blobs = _worktree_blobs(base, sorted(set(rehash)))
    if blobs is None:
        return None
    entries.update(blobs)
    digest = hashlib.sha256()
    for path in sorted(entries):
        digest.update(path + b"\0" + entries[path] + b"\n")
    return "git:" + digest.hexdigest()


def subject(root: Path | str) -> str:
    """The content identity of the tree a suite runs against.

    Every file git tracks or would track, by content, outside `.saipen/`. It
    does not change when the same bytes are staged or committed, so a record
    of the tree before SHIP is still the record of that tree after it. Git
    answers from its index, so an unchanged file is never read again; a tree
    without git falls back to the whole-content fingerprint.
    """
    base = Path(root)
    found = _git_subject(base)
    if found is not None:
        return found
    from .core_unit import tree_fingerprint

    return "tree:" + tree_fingerprint(base)


# ------------------------------------------------------------------- totals


def _clean(text: str) -> str:
    return _ANSI_RE.sub("", (text or "").replace("\r\n", "\n"))


def _parse_pytest(text: str) -> dict | None:
    for line in reversed(_clean(text).split("\n")):
        match = _PYTEST_LINE_RE.match(line.strip())
        if match is None:
            continue
        counts: dict[str, int] = {}
        for number, word in _PYTEST_COUNT_RE.findall(match.group("counts")):
            if word not in _PYTEST_WORDS:
                counts = {}
                break
            counts[word] = counts.get(word, 0) + int(number)
        if not counts:
            continue
        red = counts.get("failed", 0) + counts.get("error", 0) + counts.get("errors", 0)
        passed = counts.get("passed", 0)
        skipped = counts.get("skipped", 0)
        ran = passed + red + skipped + counts.get("xfailed", 0) + counts.get("xpassed", 0)
        return {
            "runner": "pytest",
            "ran": ran,
            "passed": passed,
            "red": red,
            "skipped": skipped,
            "counts": counts,
        }
    return None


def _parse_unittest(text: str) -> dict | None:
    body = _clean(text)
    ran = _UNITTEST_RAN_RE.findall(body)
    tally = _UNITTEST_TALLY_RE.findall(body)
    if not ran or not tally:
        return None
    counts = {
        name.strip(): int(number) for name, number in _UNITTEST_FIELD_RE.findall(tally[-1][1])
    }
    total = int(ran[-1])
    red = (
        counts.get("failures", 0) + counts.get("errors", 0) + counts.get("unexpected successes", 0)
    )
    if tally[-1][0] == "FAILED" and not red:
        return None
    skipped = counts.get("skipped", 0)
    passed = total - red - skipped - counts.get("expected failures", 0)
    if passed < 0:
        return None
    return {
        "runner": "unittest",
        "ran": total,
        "passed": passed,
        "red": red,
        "skipped": skipped,
        "counts": counts,
    }


def parse_totals(stdout: str, stderr: str) -> dict | None:
    """The totals a known runner printed, or None for output of any other shape.

    A closed set of summary grammars. An unknown runner still gets a record --
    the exit code is a fact -- but no totals are invented for it.
    """
    by_pytest = _parse_pytest(stdout) or _parse_pytest(stderr)
    by_unittest = _parse_unittest(stderr) or _parse_unittest(stdout)
    if by_pytest and by_unittest:
        # Two grammars answer: one of them is a line some test printed, and
        # nothing here can tell whose run it was. No totals beats a guess.
        return None
    return by_pytest or by_unittest


# ---------------------------------------------------------------------- run


def _resolved(command: list[str]) -> list[str] | None:
    """The argv with its program resolved on PATH (a Windows `.cmd` shim too)."""
    program = shutil.which(command[0])
    return [program, *command[1:]] if program else None


def run(root: Path | str, *, timeout: int | None = None) -> dict:
    """Execute the declared suite in the project and measure what it printed.

    Raises ``LookupError`` when nothing is declared or the program is not on
    PATH: neither is a run, and no record is written for a run that was not.
    """
    from .test_runner import TestFamily, _read_tail_from_path, _run_family

    base = Path(root).resolve()
    declaration, error = load_declaration(base)
    if error:
        raise LookupError(error)
    if declaration is None:
        raise LookupError(
            "no suite is declared for this project: saipen test suite declare -- <command>"
        )
    argv = _resolved(declaration["command"])
    if argv is None:
        raise LookupError(f"the declared suite program is not on PATH: {declaration['command'][0]}")
    seconds = declaration["timeout_s"] if timeout is None else timeout
    before = subject(base)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="saipen-suite-") as spool_name:
        spool = Path(spool_name)
        report = _run_family(base, TestFamily("suite", tuple(argv), seconds), spool=spool)
        stdout = _read_tail_from_path(spool / "stdout", SUMMARY_TAIL_CHARS)
        stderr = _read_tail_from_path(spool / "stderr", SUMMARY_TAIL_CHARS)
    if report["status"] == "FAIL" and report.get("exit_code") is None:
        raise LookupError(str(report.get("stderr") or "the declared suite did not start"))
    return {
        "command": list(declaration["command"]),
        "command_sha256": declaration["command_sha256"],
        "status": report["status"],
        "exit_code": report.get("exit_code"),
        "totals": parse_totals(stdout, stderr),
        "duration_s": round(time.monotonic() - started, 1),
        "timeout_s": seconds,
        "subject_before": before,
        "subject": subject(base),
        "stdout_tail": _clean(stdout)[-KEPT_TAIL_CHARS:],
        "stderr_tail": _clean(stderr)[-KEPT_TAIL_CHARS:],
    }


def judge(run_result: dict) -> dict:
    """The verdict of one run; the arithmetic lives here only."""
    problems: list[str] = []
    totals = run_result.get("totals")
    code = run_result.get("exit_code")
    red = int((totals or {}).get("red") or 0)
    if run_result.get("status") == "TIMEOUT":
        problems.append(f"the suite did not finish inside {run_result.get('timeout_s')} s")
    elif code != 0:
        problems.append(f"exit code {code}")
    if red:
        problems.append(f"{red} red in the runner's own summary")
    if code == 0 and red:
        problems.append("exit code 0 contradicts the red in the summary")
    if totals is not None and not totals.get("ran"):
        problems.append("the summary counts no test")
    return {"verdict": "FAIL" if problems else "PASS", "problems": problems}


def write_record(root: Path | str, run_result: dict) -> dict:
    """Judge ``run_result`` and persist the record; returns its path and digest."""
    base = Path(root)
    now = datetime.datetime.now(datetime.timezone.utc)
    record = {
        "schema": SCHEMA_VERSION,
        "kind": RECORD_KIND,
        **{
            key: run_result.get(key)
            for key in (
                "command", "command_sha256", "status", "exit_code", "totals", "duration_s",
                "timeout_s", "subject_before", "subject", "stdout_tail", "stderr_tail",
            )
        },
        "tree_changed_during_run": run_result.get("subject_before") != run_result.get("subject"),
        "finished_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        **judge(run_result),
    }
    name = f"{record['command_sha256'][:16]}-{now.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    path = base / RECORD_DIR_REL / name
    _write_json(path, record)
    return {
        "record": record,
        "path": path.relative_to(base).as_posix(),
        "sha256": _sha256_file(path),
    }


def evidence_line(written: dict) -> str:
    """The anchored LOG text that cites one record."""
    record = written["record"]
    totals = record.get("totals")
    measured = (
        f"runner:{totals['runner']} ran:{totals['ran']} red:{totals['red']} "
        f"skipped:{totals['skipped']}"
        if totals
        else "runner:unknown"
    )
    return (
        f"{MARKER} {record['verdict']} {measured} exit:{record['exit_code']} "
        f"command:{record['command_sha256'][:16]} record:{written['path']} "
        f"sha256:{written['sha256']}"
    )


def parse_evidence(text: str) -> dict | None:
    """The anchored citation in one LOG text, or None for anything else."""
    match = _EVIDENCE_RE.match((text or "").strip())
    return match.groupdict() if match else None


# ------------------------------------------------------------------- reader


def _count(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _admissible(record: object, declaration: dict) -> bool:
    """Is this the engine's record shape for the declared command?"""
    if (
        not isinstance(record, dict)
        or record.get("kind") != RECORD_KIND
        or record.get("schema") != SCHEMA_VERSION
        or record.get("command") != declaration["command"]
        or record.get("command_sha256") != declaration["command_sha256"]
        or record.get("status") not in STATUSES
        or record.get("verdict") not in ("PASS", "FAIL")
        or not isinstance(record.get("subject"), str)
    ):
        return False
    code = record.get("exit_code")
    if code is not None and (isinstance(code, bool) or not isinstance(code, int)):
        return False
    totals = record.get("totals")
    if totals is None:
        return True
    return isinstance(totals, dict) and all(
        _count(totals.get(key)) is not None for key in ("ran", "red", "skipped")
    )


def newest_record(root: Path | str) -> dict | None:
    """The newest admissible record of the DECLARED command, of any tree."""
    base = Path(root)
    declaration, error = load_declaration(base)
    if error or declaration is None:
        return None
    prefix = declaration["command_sha256"][:16]
    for path in sorted((base / RECORD_DIR_REL).glob(f"{prefix}-*.json"), reverse=True):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if _admissible(record, declaration):
            return {
                "record": record,
                "path": path.relative_to(base).as_posix(),
                "sha256": _sha256_file(path),
            }
    return None


def current_record(root: Path | str) -> dict | None:
    """The newest record of the declared suite, when it tested THIS tree.

    A record of another tree says nothing about the one in front of the
    operator, so it is not reported at all rather than reported as stale.
    """
    try:
        found = newest_record(root)
        if found is None:
            return None
        recorded = found["record"]["subject"]
        # Asked in the scheme the record used: a git record is never answered
        # by hashing the whole tree, which could not match it and costs a
        # large project tens of seconds on every checkpoint.
        now = _git_subject(Path(root)) if recorded.startswith("git:") else subject(root)
        if now != recorded:
            return None
    except OSError:
        # A tree that cannot be read is not a tree a record is known to match;
        # the checkpoint still renders, without a suite claim.
        return None
    return found


def digest_group(record: dict) -> dict:
    """The typed facts the operator digest renders; integers and a closed status."""
    totals = record.get("totals") or {}
    return {
        "status": record.get("status") if record.get("status") in STATUSES else "FAIL",
        "verdict": "PASS" if record.get("verdict") == "PASS" else "FAIL",
        "exit_code": record.get("exit_code"),
        "ran": _count(totals.get("ran")),
        "red": _count(totals.get("red")),
        "skipped": _count(totals.get("skipped")),
    }


# ---------------------------------------------------------------------- CLI

#: Each form is a command a guard admits as typed (`--timeout <seconds>` is
#: optional on the last two): a usage line that opens with the command word
#: and is no command would be an instruction nobody can run.
USAGE = (
    "saipen test suite",
    "saipen test suite declare -- <command>",
    "saipen test suite run <T-###>",
    "saipen test suite withdraw",
)
_TICKET_RE = re.compile(r"T-\d+")

#: The phases that prove the tree. Elsewhere a tree with no record is the
#: normal state, and a field that is always present is a field nobody reads.
PROJECTED_PHASES = frozenset({"VERIFY", "REVIEW", "SHIP"})


def projection(root: Path | str) -> dict | None:
    """What a turn-entry answer says about the declared suite, or None.

    T-1661: the run command existed and no answer named it, so the typed
    record depended on an agent remembering one row of COMMANDS.md. Named
    only when there is something to do -- a suite is declared, the phase is
    one that proves the tree, and this tree has no record -- and never for a
    project that declares none. Reads files only and never raises.
    """
    base = Path(root)
    try:
        declaration, _error = load_declaration(base)
        if declaration is None:
            return None
        from .state import parse_state

        state = parse_state((base / ".saipen" / "STATE.md").read_text(encoding="utf-8"))
        ticket = str(state.get("task") or "")
        # These phases always bear a ticket; a state without one is not a
        # state to give instructions in. Asked before the tree is read.
        if str(state.get("phase") or "").upper() not in PROJECTED_PHASES or not (
            _TICKET_RE.fullmatch(ticket)
        ):
            return None
        if current_record(base) is not None:
            return None
    except (OSError, ValueError):
        return None
    return {
        "command": f"saipen test suite run {ticket}",
        "reason": "the declared suite has no record of the current tree",
    }


def _refusal(detail: str) -> tuple[dict, int]:
    return {"ok": False, "code": "VALIDATION_FAILED", "detail": detail, "usage": list(USAGE)}, 2


def _take_timeout(words: list[str]) -> tuple[list[str], int | None, str | None]:
    """Remove one `--timeout S` from ``words``; the third value is a problem."""
    if "--timeout" not in words:
        return words, None, None
    index = words.index("--timeout")
    value = words[index + 1] if index + 1 < len(words) else ""
    if not value.isdigit() or not _timeout_ok(int(value)):
        return words, None, f"--timeout takes whole seconds in 1..{MAX_TIMEOUT_S}"
    return words[:index] + words[index + 2 :], int(value), None


def _summary(found: dict | None) -> dict | None:
    if found is None:
        return None
    record = found["record"]
    return {
        "verdict": record["verdict"],
        "status": record["status"],
        "exit_code": record["exit_code"],
        "totals": record["totals"],
        "problems": record.get("problems") or [],
        "finished_utc": record.get("finished_utc"),
        "record": found["path"],
    }


def _status(base: Path) -> tuple[dict, int]:
    declaration, error = load_declaration(base)
    if error:
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "suite": "DECLARATION_INVALID",
            "detail": error,
        }, 1
    newest = newest_record(base) if declaration else None
    return {
        "ok": True,
        "code": "SUITE_STATUS",
        "declared": declaration is not None,
        "command": (declaration or {}).get("command"),
        "timeout_s": (declaration or {}).get("timeout_s"),
        "newest": _summary(newest),
        # Whether the newest record is of the tree as it is now: the one
        # condition under which the operator digest reports it.
        "current": bool(newest) and newest["record"]["subject"] == subject(base),
    }, 0


def _declare(base: Path, words: list[str], agent: str, dry_run: bool) -> tuple[dict, int]:
    if "--" not in words:
        return _refusal("declare takes the suite command after `--`")
    head, command = words[: words.index("--")], words[words.index("--") + 1 :]
    head, timeout, problem = _take_timeout(head)
    problem = problem or _command_problem(command)
    if problem or head:
        return _refusal(problem or f"declare takes no operand before `--`: {' '.join(head)}")
    if dry_run:
        return {
            "ok": True,
            "code": "SUITE_DECLARE_PLAN",
            "command": command,
            "command_sha256": command_digest(command),
            "dry_run": True,
        }, 0
    from . import operations

    _previous, error = load_declaration(base)
    try:
        result = declare(base, command, timeout=timeout)
    except (ValueError, OSError) as exc:
        return {
            "ok": False,
            "code": "IO_FAILED",
            "suite": "NOT_DECLARED",
            "detail": str(exc),
        }, 1
    logged = operations.checkpoint(base, agent, "DEC", None, declaration_line(result))
    return {
        "ok": logged.ok,
        "code": "SUITE_DECLARED",
        "command": command,
        "command_sha256": result["declaration"]["command_sha256"],
        "timeout_s": result["declaration"]["timeout_s"],
        "previous_sha256": result["previous_sha256"],
        "replaced_invalid": error,
        "checkpoint": logged.code,
        "checkpoint_detail": logged.message or None,
    }, 0 if logged.ok else 1


def _run(base: Path, words: list[str], agent: str, dry_run: bool) -> tuple[dict, int]:
    words, timeout, problem = _take_timeout(words)
    if problem or len(words) > 1 or (words and not _TICKET_RE.fullmatch(words[0])):
        return _refusal(problem or "run takes at most one ticket id")
    declaration, error = load_declaration(base)
    if error or declaration is None:
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "suite": "DECLARATION_INVALID" if error else "NOT_DECLARED",
            "detail": error or "no suite is declared for this project",
            "canonical_next_command": "saipen test suite declare -- <command>",
        }, 1
    if dry_run:
        return {
            "ok": True,
            "code": "SUITE_RUN_PLAN",
            "command": declaration["command"],
            "timeout_s": timeout or declaration["timeout_s"],
            "dry_run": True,
        }, 0
    from . import operations
    from .inflight import holding

    ticket = words[0] if words else None
    try:
        # The suite runs in the project itself, so the tree is frozen for the
        # run: an edit meanwhile would make the record describe neither tree.
        with holding(base, ticket or "", "test suite run"):
            written = write_record(base, run(base, timeout=timeout))
    except LookupError as exc:
        # Nothing ran: no record, no evidence line, nothing for the digest.
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "suite": "NOT_RUN",
            "detail": str(exc),
        }, 1
    except (ValueError, OSError) as exc:
        # It ran and could not be written down: the same absence, a different
        # cause, and a traceback would hide which.
        return {
            "ok": False,
            "code": "IO_FAILED",
            "suite": "NOT_RECORDED",
            "detail": str(exc),
        }, 1
    logged = operations.checkpoint(base, agent, "RUN", ticket, evidence_line(written))
    record = written["record"]
    passed = record["verdict"] == "PASS"
    return {
        "ok": logged.ok and passed,
        "code": "SUITE_RECORDED",
        **_summary(written),
        "sha256": written["sha256"],
        "tree_changed_during_run": record["tree_changed_during_run"],
        "stdout_tail": None if passed else record["stdout_tail"],
        "stderr_tail": None if passed else record["stderr_tail"],
        "checkpoint": logged.code,
        "checkpoint_detail": logged.message or None,
    }, 0 if logged.ok and passed else 1


def _withdraw(base: Path, agent: str, dry_run: bool) -> tuple[dict, int]:
    declaration, error = load_declaration(base)
    if declaration is None and error is None:
        return {
            "ok": False,
            "code": "VALIDATION_FAILED",
            "suite": "NOT_DECLARED",
            "detail": "no suite is declared for this project",
        }, 1
    if dry_run:
        return {
            "ok": True,
            "code": "SUITE_WITHDRAW_PLAN",
            "command_sha256": (declaration or {}).get("command_sha256"),
            "dry_run": True,
        }, 0
    from . import operations

    try:
        result = withdraw(base)
    except (LookupError, ValueError, OSError) as exc:
        return {
            "ok": False,
            "code": "IO_FAILED",
            "suite": "NOT_WITHDRAWN",
            "detail": str(exc),
        }, 1
    logged = operations.checkpoint(base, agent, "DEC", None, withdrawal_line(result))
    return {
        "ok": logged.ok,
        "code": "SUITE_WITHDRAWN",
        "previous_sha256": result["previous_sha256"],
        "was_invalid": result["was_invalid"],
        "checkpoint": logged.code,
        "checkpoint_detail": logged.message or None,
    }, 0 if logged.ok else 1


def cli(
    root: Path | str, words: list[str], *, agent: str, dry_run: bool = False
) -> tuple[dict, int]:
    """`saipen test suite ...`: the payload to print and the exit code."""
    base = Path(root).resolve()
    action, rest = (words[0], list(words[1:])) if words else ("status", [])
    if action == "status" and not rest:
        return _status(base)
    if action == "declare":
        return _declare(base, rest, agent, dry_run)
    if action == "run":
        return _run(base, rest, agent, dry_run)
    if action == "withdraw" and not rest:
        return _withdraw(base, agent, dry_run)
    return _refusal(f"unknown suite action: {' '.join(words)}")

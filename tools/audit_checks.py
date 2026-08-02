#!/usr/bin/env python3
"""Proves the canonical validator's checks can still go red.

`tools/audit_floor.py` does this for the checks in the frozen portable
floor. Nothing did it for `tools/validate.py`, which now carries around 160
failure paths -- and measuring it is unpleasant reading: the inputs this
repository ships (its own `.saipen/` plus 15 executable fixtures) produce 17
distinct FAIL/WARN lines between them. Every other check rests on a hand test
from the day it was written.

That is not a hypothetical risk here. A check in this file lay dead from
`feae149` to v7.99.0 because its regex never matched a LOG line, and the first
draft of the portable-floor check could not go red at all. The repository's own
rule is that a hand test proves a check worked once and a fixture proves it
still works -- and the sixteen releases before this tool red-tested roughly
twenty-five checks in scratch directories that were deleted immediately after.
This is those tests, kept.

Each case breaks a known-good copy of this repository in exactly one way and
asserts the validator names that specific failure. A case that stops firing is
a check that has gone dead, and it fails here rather than being discovered
years later.

Exit 0 when every case still goes red, 1 otherwise.
"""
from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HOME = Path(__file__).resolve().parent.parent
IGNORE = shutil.ignore_patterns(".git", ".venv", "__pycache__", ".freebuff",
                                "node_modules", "nul")

STATE = ".saipen/STATE.md"
BOARD = ".saipen/BOARD.md"
LOG = ".saipen/LOG.md"
DIGEST = ".saipen/kitchen/digest.md"
MANIFEST = ".saipen/kitchen/markhunt_progress.md"
SUB = ".saipen/extensions/subs/saiwiki/STATE.md"
STATE_SCHEMA = "extensions/schemas/state.schema.json"
TAG_QUERY = ("git", "tag", "-l", "v*")
AUDIT_TAGS_GIT_SHIM = "SAIPEN_AUDIT_TAGS_GIT_SHIM"
AUDIT_TAGS_MODE = "SAIPEN_AUDIT_TAGS_MODE"


def root_device_ignore_probe(tmp: Path) -> str | None:
    """Prove a real `nul` entry cannot poison an audit snapshot.

    On Windows, ordinary APIs resolve `nul` to the character device instead
    of creating a directory entry. The extended path creates the same real
    NTFS artifact an external shell/agent left in this repository. POSIX can
    create the name normally, so CI still exercises the ignore contract.
    """
    source = tmp / "root-device-source"
    destination = tmp / "root-device-copy"
    source.mkdir()
    (source / "kept.txt").write_text("kept\n", encoding="utf-8")
    reserved = source / "nul"
    native = ("\\\\?\\" + str(reserved.resolve())
              if os.name == "nt" else str(reserved))
    try:
        with open(native, "wb") as stream:
            stream.write(b"external agent artifact")
        shutil.copytree(source, destination, ignore=IGNORE)
        copied = {entry.name.casefold() for entry in destination.iterdir()}
        if copied != {"kept.txt"}:
            return "snapshot did not preserve only the ordinary control file"
    except (OSError, shutil.Error) as exc:
        return f"snapshot raised {type(exc).__name__}: {exc}"
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(native)
        shutil.rmtree(source, ignore_errors=True)
        shutil.rmtree(destination, ignore_errors=True)
    return None


def release_ledger_probe(source: Path, destination: Path) -> str | None:
    """Execute clean, new-divergence, and stale-baseline ledger controls."""
    tree = destination / "release-ledger"
    shutil.copytree(source, tree)

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=tree, capture_output=True,
                              text=True, errors="replace")

    for args in (("init", "-q"),
                 ("config", "user.name", "SAIPEN ledger probe"),
                 ("config", "user.email", "ledger-probe@example.invalid"),
                 # The tree has to be COMMITTED, not just present: the runtime
                 # manifest now requires its files to be tracked, and a probe
                 # whose repository contains one empty commit has every file
                 # untracked. That made this fixture fail for a reason it does
                 # not test -- a synthetic repository has to resemble a real
                 # clone in every way the validator can see.
                 ("add", "-A"),
                 ("commit", "--allow-empty", "-m", "ledger probe")):
        result = git(*args)
        if result.returncode:
            return f"git {' '.join(args)} failed: {(result.stderr or result.stdout).strip()}"

    baseline = json.loads((tree / "tools" / "release_ledger_baseline.json").read_text(
        encoding="utf-8"))
    changelog_only = set(baseline["changelog_only"])
    changelog_versions = set()
    for name in ("CHANGELOG.md", "CHANGELOG_ARCHIVE.md"):
        path = tree / name
        if path.is_file():
            changelog_versions |= set(re.findall(
                r"^## (\d+\.\d+\.\d+)",
                path.read_text(encoding="utf-8-sig"), re.MULTILINE))
    for version in sorted(changelog_versions - changelog_only):
        result = git("tag", f"v{version}")
        if result.returncode:
            return f"could not seed ledger tag v{version}: {result.stderr.strip()}"

    def validate() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(tree / "tools" / "validate.py")], cwd=tree,
            capture_output=True, text=True, errors="replace")

    control = validate()
    control_text = control.stdout + control.stderr
    if control.returncode or "WARN [release-ledger]" in control_text:
        return "clean synthetic ledger is not clean"

    tag_only = "7.83.9"
    if git("tag", f"v{tag_only}").returncode:
        return "could not create tag-only red-control"
    tag_result = validate()
    tag_text = tag_result.stdout + tag_result.stderr
    if (tag_result.returncode != 0
            or f"git tag but no CHANGELOG entry: v{tag_only}" not in tag_text):
        return "new tag-only divergence did not produce its focused warning"
    if git("tag", "-d", f"v{tag_only}").returncode:
        return "could not remove temporary tag-only red-control"

    changelog_version = "7.83.8"
    changelog = tree / "CHANGELOG.md"
    changelog.write_text(
        changelog.read_text(encoding="utf-8-sig")
        + f"\n## {changelog_version} -- 2026-07-31 -- ledger red-control\n",
        encoding="utf-8", newline="\n")
    changelog_result = validate()
    changelog_text = changelog_result.stdout + changelog_result.stderr
    if (changelog_result.returncode != 0
            or f"CHANGELOG entry but no git tag: v{changelog_version}" not in changelog_text):
        return "new changelog-only divergence did not produce its focused warning"

    original = next(iter(sorted(changelog_only)))
    if git("tag", f"v{original}").returncode:
        return "could not create stale-baseline red-control"
    stale_result = validate()
    stale_text = stale_result.stdout + stale_result.stderr
    if (stale_result.returncode == 0
            or f"baseline is stale for: v{original}" not in stale_text):
        return "resolved historical exception did not make stale baseline fail"
    return None


def warn_ownership_probe(source: Path, destination: Path) -> str | None:
    """T-401: a WARN slug aged past the owner span FAILs unless a live
    BOARD ticket names it; the identical aged slug with a live naming
    ticket passes. The red control mutates baseline DATA, never validator
    wording."""
    tree = destination / "warn-ownership"
    shutil.copytree(source, tree)

    baseline_path = tree / "tools" / "release_ledger_baseline.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

    def validate() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(tree / "tools" / "validate.py")], cwd=tree,
            capture_output=True, text=True, errors="replace")

    control = validate()
    if control.returncode:
        return ("control copy with calibrated warn_slugs is not clean: "
                + (control.stdout + control.stderr).strip()[-300:])

    # Age an unowned slug: log-missing-date emits in every clean copy (125
    # sealed pre-DATE entries are immutable), and no ticket names it.
    baseline["warn_slugs"]["log-missing-date"] = {
        "first_seen": "7.1.0",
        "last_seen": "7.160.0",
        "rationale": "ownership probe: aged, unowned",
    }
    baseline_path.write_text(
        json.dumps(baseline, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    red = validate()
    red_text = red.stdout + red.stderr
    if (red.returncode == 0
            or "no live BOARD ticket names it" not in red_text
            or "log-missing-date" not in red_text):
        return ("aged unowned slug did not fail the validator: "
                + red_text.strip()[-300:])

    # The identical aged slug with a live naming ticket must pass.
    board = tree / ".saipen" / "BOARD.md"
    board_text = board.read_text(encoding="utf-8-sig")
    if "## TODO" not in board_text:
        return "BOARD copy has no ## TODO section to host the owning ticket"
    ticket = ("- [ ] T-990 [P2] Own the persistent `log-missing-date` warning: "
              "125 sealed pre-DATE entries are immutable by append-only, so it "
              "warns forever; keep this ticket live while it emits. | "
              "verify: warn ownership probe passes with this ticket live\n")
    # Appended at the END of ## TODO, not the front: board order is priority
    # (RFC section 1.11) and STATE's next_action names the topmost workable
    # ticket, so a probe that files its own ticket first invalidates that pick
    # and then fails for a reason it does not test.
    todo_at = board_text.index("## TODO\n") + len("## TODO\n")
    next_heading = board_text.find("\n## ", todo_at)
    cut = len(board_text) if next_heading == -1 else next_heading + 1
    board_text = board_text[:cut] + ticket + board_text[cut:]
    board.write_text(board_text, encoding="utf-8", newline="\n")
    green = validate()
    if green.returncode:
        return ("aged slug with live owning ticket still fails: "
                + (green.stdout + green.stderr).strip()[-300:])
    return None


def phase_rename_probe(source: Path, destination: Path) -> str | None:
    """T-426 verify: renaming a phase consistently across every copy the
    validator reads stays green. The new edge gates exist to catch drift,
    not to forbid a deliberate rename: SCOUT -> SCOUTX (and scout -> scoutx,
    word-boundary, so the phase doc file and its citations move too) across
    the whole tree -- DFA, RFC table and enum sentence, schema enum, the
    phase doc and its exit line, STATE references -- must validate clean.
    """
    tree = destination / "phase-rename"
    shutil.copytree(source, tree)
    changed = 0
    for path in tree.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (UnicodeDecodeError, OSError):
            continue
        new = re.sub(r"\bSCOUT\b", "SCOUTX", text)
        new = re.sub(r"\bscout\b", "scoutx", new)
        if new != text:
            path.write_text(new, encoding="utf-8", newline="\n")
            changed += 1
    old_doc = tree / "saipen" / "phases" / "scout.md"
    if old_doc.is_file():
        old_doc.rename(tree / "saipen" / "phases" / "scoutx.md")
    if changed == 0:
        return "rename probe changed nothing -- a bug in the probe itself"
    proc = subprocess.run(
        [sys.executable, str(tree / "tools" / "validate.py")], cwd=tree,
        capture_output=True, text=True, errors="replace")
    if proc.returncode:
        return ("consistent SCOUT->SCOUTX rename was rejected: "
                + (proc.stdout + proc.stderr).strip()[-400:])
    return None


def audit_tags_batch_probe(root: Path, destination: Path) -> str | None:
    """Execute process and protocol failures against the tag audit."""
    missing_env = os.environ.copy()
    missing_env.pop(AUDIT_TAGS_GIT_SHIM, None)
    missing_env.pop(AUDIT_TAGS_MODE, None)
    missing_env["PATH"] = ""
    missing = subprocess.run(
        [sys.executable, str(root / "tools" / "audit_tags.py")],
        cwd=root, env=missing_env, capture_output=True, text=True,
        errors="replace")
    missing_output = missing.stdout + missing.stderr
    if (missing.returncode != 0
            or "SKIP: git unavailable -- cannot audit tags" not in missing_output
            or "PASS:" in missing_output or "FAIL:" in missing_output):
        return ("missing-Git control did not produce the sole allowed SKIP: "
                f"rc={missing.returncode} {missing_output.strip()[:200]}")

    shim = destination / "audit-tags-git-shim.py"
    shim.write_text(
        """import os
import sys

args = sys.argv[1:]
if args == ["tag", "-l", "v*"]:
    if os.environ["SAIPEN_AUDIT_TAGS_MODE"] == "enumeration_nonzero":
        print("synthetic enumeration failure", file=sys.stderr)
        raise SystemExit(9)
    print("v" + "9.9.9")
    raise SystemExit(0)
if args == ["cat-file", "--batch"]:
    sys.stdin.buffer.read()
    mode = os.environ["SAIPEN_AUDIT_TAGS_MODE"]
    if mode == "nonzero":
        print("synthetic batch failure", file=sys.stderr)
        raise SystemExit(9)
    if mode == "truncated":
        sys.stdout.buffer.write(b"0" * 40 + b" blob 5\\n7.")
        raise SystemExit(0)
    if mode == "malformed":
        sys.stdout.buffer.write(b" blob 5\\n9.9.9\\n")
        raise SystemExit(0)
    if mode == "surplus":
        sys.stdout.buffer.write(b"0" * 40 + b" blob 5\\n9.9.9\\nEXTRA")
        raise SystemExit(0)
raise SystemExit(8)
""",
        encoding="utf-8", newline="\n")

    synthetic_tag = "v" + "9.9.9"
    expected = {
        "enumeration_nonzero": (
            "FAIL: git tag enumeration exited 9: synthetic enumeration failure"),
        "nonzero": "FAIL: git cat-file exited 9: synthetic batch failure",
        "truncated": f"FAIL: git cat-file response for {synthetic_tag} is truncated",
        "malformed": f"FAIL: git cat-file response for {synthetic_tag} has malformed header",
        "surplus": "FAIL: git cat-file batch response has 5 unexpected trailing byte(s)",
    }
    for mode, message in expected.items():
        env = os.environ.copy()
        env[AUDIT_TAGS_GIT_SHIM] = str(shim)
        env[AUDIT_TAGS_MODE] = mode
        result = subprocess.run(
            [sys.executable, str(root / "tools" / "audit_tags.py")],
            cwd=root, env=env, capture_output=True, text=True, errors="replace")
        output = result.stdout + result.stderr
        if result.returncode == 0:
            return f"{mode} control exited 0"
        if message not in output:
            return f"{mode} control did not report {message!r}: {output.strip()[:200]}"
        if "PASS:" in output or "SKIP:" in output:
            return f"{mode} control printed PASS/SKIP after losing audit evidence"
    return None


def observed_tag_queries(root: Path) -> tuple[int, str | None]:
    """Count real `git tag -l v*` processes through Git's Trace2 stream."""
    handle, raw_path = tempfile.mkstemp(prefix="saipen-git-trace-", suffix=".json")
    os.close(handle)
    trace = Path(raw_path)
    env = os.environ.copy()
    env["GIT_TRACE2_EVENT"] = str(trace)
    try:
        result = subprocess.run(
            [sys.executable, str(root / "tools" / "validate.py")], cwd=root,
            env=env, capture_output=True, text=True, errors="replace")
        output = result.stdout + result.stderr
        count = 0
        for line in trace.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            argv = event.get("argv", [])
            if event.get("event") == "start" and tuple(argv[1:]) == TAG_QUERY[1:]:
                count += 1
        error = None
        if "Traceback (most recent call last)" in output:
            error = "validator crashed while tag queries were observed"
        elif result.returncode:
            first = next((line for line in output.splitlines()
                          if line.startswith("FAIL")), "no FAIL line")
            error = (f"validator control exited {result.returncode} while tag "
                     f"queries were observed: {first[:100]}")
        return count, error
    finally:
        trace.unlink(missing_ok=True)


def duplicate_tag_query(path: Path) -> str | None:
    """AST-locate the query and insert a second executable call as red-control."""
    source = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    matches = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "run"
                and isinstance(func.value, ast.Name)
                and func.value.id == "subprocess"):
            continue
        first = node.args[0]
        if not isinstance(first, (ast.List, ast.Tuple)):
            continue
        if len(first.elts) != len(TAG_QUERY):
            continue
        values = tuple(item.value for item in first.elts
                       if isinstance(item, ast.Constant))
        if values == TAG_QUERY:
            matches.append(node)
    if len(matches) != 1:
        return f"red-control setup found {len(matches)} executable tag queries"
    lines = source.splitlines(keepends=True)
    index = matches[0].lineno - 1
    indent = lines[index][:len(lines[index]) - len(lines[index].lstrip())]
    duplicate = (f'{indent}subprocess.run(["git", "tag", "-l", "v*"], '
                 'capture_output=True, text=True, check=False)\n')
    lines.insert(index, duplicate)
    path.write_text("".join(lines), encoding="utf-8", newline="\n")
    return None


def sub_line(field: str, value: str):
    """Replace a whole frontmatter line."""
    return lambda t: re.sub(rf"^{field}:.*$", f"{field}: {value}", t, flags=re.MULTILINE)


def bump_int_line(field: str):
    """Increment a frontmatter integer instead of guessing its live value."""
    return lambda t: re.sub(
        rf"^{field}:\s*(\d+)$",
        lambda match: f"{field}: {int(match.group(1)) + 1}",
        t,
        count=1,
        flags=re.MULTILINE,
    )


def drop_line(field: str):
    return lambda t: re.sub(rf"^{field}:.*\n", "", t, flags=re.MULTILINE)


def add_after(anchor: str, text: str):
    return lambda t: t.replace(anchor, anchor + text, 1)


def replace(old: str, new: str):
    return lambda t: t.replace(old, new, 1)


def leak_style_marker(text: str) -> str:
    """Copy STYLE.md's live marker into whichever doc is being mutated.

    Read from the pristine tree at mutation time rather than hardcoded: a
    control that pins the token would have to be re-typed on every STYLE.md
    edit, and a stale pin makes the mutation a no-op -- the one failure the
    no-op guard exists to catch.
    """
    style = (HOME / "saipen" / "STYLE.md").read_text(encoding="utf-8-sig")
    found = re.search(r"`style_contract:\s*(ded-[0-9a-f]{8})`", style)
    return text if not found else f"{text}\n<!-- {found.group(1)} -->\n"


UTF16 = "<rewrite as utf-16>"      # sentinel, not a mutation function
DELETE = "<delete the file>"
def strip_done_verify(text: str) -> str:
    """T-431: take the evidence off the first ## DONE ticket, keep the ticket.

    The ticket still claims completion, exactly as it did before -- only the
    proof is gone, which was legal until this check existed. Written against
    the board's structure rather than one ticket's wording so the control
    survives every ## DONE prune.
    """
    out, section, done_once = [], "", False
    for line in text.splitlines():
        stripped = line
        if line.startswith("## "):
            section = line.strip()
        elif (section == "## DONE" and not done_once
                and line.startswith("- [x] T-") and " | verify:" in line):
            stripped = re.sub(r" \| verify:.*$", "", line)
            done_once = True
        out.append(stripped)
    return "\n".join(out) + "\n"


def cite_open_ticket(text: str) -> str:
    """T-431: repoint a shipped CONFORMANCE row at a ticket still in ## TODO.

    The open ticket is read out of the pristine board at mutation time, the
    same way leak_style_marker reads STYLE.md's live marker: a hardcoded ID
    would go stale into a silent no-op the moment the board moved on.
    """
    board = (HOME / ".saipen" / "BOARD.md").read_text(encoding="utf-8-sig")
    todo = re.search(r"^## TODO$(.*?)^## ", board,
                     re.MULTILINE | re.DOTALL)
    open_ticket = re.search(r"^- \[ \] (T-\d+)", todo.group(1),
                            re.MULTILINE) if todo else None
    if not open_ticket:
        return text
    return re.sub(r"\(T-\d+\)", f"({open_ticket.group(1)})", text, count=1)


CREATE = "<create the file>"
SWAP = "<swap the last two log entries>"


def write_new(content: str):
    """A mutation that CREATES the file rather than editing it.

    Three markhunt cases skipped because this repository has no live manifest,
    and a case that skips on the machine where it matters is barely better than
    one that never fires.
    """
    return ("WRITE", content)


def case_target(root: Path, rel: str, mutation) -> Path:
    """Return the physical file a logical mutation will edit.

    LOG chronology spans sealed segments plus the active tail. Immediately
    after a normal seal the active file has no event pair to swap, so the
    backwards-ID mutation must walk to the newest segment that does. Both
    runners call this before saving bytes, and apply_case calls it again,
    keeping mutation and restoration on the same file.
    """
    default = root / rel
    if mutation != SWAP:
        return default
    candidates = [default]
    candidates.extend(reversed(sorted((root / ".saipen" / "logs").glob(
        "LOG-*.md"))))
    for candidate in candidates:
        if not candidate.is_file():
            continue
        lines = candidate.read_text(
            encoding="utf-8-sig", errors="replace").splitlines()
        if sum(line.startswith("- ") for line in lines) >= 2:
            return candidate
    return default


def case_available(root: Path, rel: str, mutation) -> bool:
    if mutation == CREATE or (isinstance(mutation, tuple)
                              and mutation[0] == "WRITE"):
        return True
    target = case_target(root, rel, mutation)
    if not target.is_file():
        return False
    if mutation != SWAP:
        return True
    lines = target.read_text(
        encoding="utf-8-sig", errors="replace").splitlines()
    return sum(line.startswith("- ") for line in lines) >= 2


# (label, file, mutation, expected substring in the validator's output)
CASES: list[tuple[str, str, object, str]] = [
    # --- STATE shape -----------------------------------------------------
    ("STATE.md deleted", STATE, DELETE, "STATE.md missing"),
    ("STATE.md is UTF-16", STATE,
     UTF16, "not plain UTF-8"),
    ("phase not in the enum", STATE, sub_line("phase", "REFACTOR"),
     "not one of"),
    ("mode not in the enum", STATE, sub_line("mode", "yolo"),
     "field mode"),
    ("transition_from dropped", STATE, drop_line("transition_from"),
     "missing transition_from"),
    ("illegal transition", STATE,
     lambda t: sub_line("phase", "SHIP")(sub_line("transition_from", "INIT")(t)),
     "invalid phase transition"),
    ("updated not UTC", STATE, sub_line("updated", "2026-07-30 10:00"),
     "must be ISO-8601 UTC"),
    ("schema_version from the future", STATE, sub_line("schema_version", "99"),
     "only understands"),
    ("current schema revision metadata missing", STATE_SCHEMA,
     replace('  "x-current-schema-version": 3,\n', ""),
     "x-current-schema-version must be a positive integer"),
    ("current-schema state missing last_event", STATE, drop_line("last_event"),
     "requires last_event"),
    ("current-schema state missing style_contract", STATE,
     drop_line("style_contract"), "requires style_contract"),
    ("style_contract names a different voice contract", STATE,
     sub_line("style_contract", "ded-deadbeef"),
     "did not read the current STYLE.md"),
    ("last_event below the log tail", STATE, sub_line("last_event", "1"),
     "lower than the log"),
    ("next_action picks a ticket that is not the topmost workable", STATE,
     sub_line("next_action", '"PHASE SCOUT T-419"'),
     "but the topmost workable ## TODO ticket is"),
    ("next_action has no prefix", STATE,
     sub_line("next_action", '"finish the thing"'),
     "does not start with"),
    ("WAIT with no category", STATE,
     sub_line("next_action", '"WAIT: need more context"'),
     "WAIT with no category token"),
    # `saipen hunt` was this case's undefined command until v7.148.0 defined
    # it. A red control whose example became legal stops being evidence, so it
    # names a verb the surface has no plans for instead of a near-miss.
    ("undefined saipen command", STATE, sub_line("next_action", '"saipen refactor"'),
     "does not define"),
    ("question outside a WAIT", STATE, sub_line("next_action", '"RUN: ship it?"'),
     "asks a question outside"),
    ("read-only in a writing phase", STATE,
     lambda t: sub_line("phase", "BUILD")(sub_line("mode", "read-only")(
         sub_line("transition_from", "SCOUT")(t))),
     "MUST NOT enter"),
    ("goal_mode true, counters absent", STATE,
     lambda s: drop_line("goal_tickets")(drop_line("goal_waves")(s)),
     "counter missing"),
    # Un-double the bootloader pointer's backslashes, exactly as commit
    # 4012bae did. This file's own frontmatter parser never sees it -- it
    # reads a YAML subset and ignores escapes -- so the mutation has to be
    # judged by the escaping rule, not by a parse.
    ("saipen_home backslashes stop being escaped", STATE,
     lambda t: t.replace(chr(92) * 2, chr(92)),
     "backslashes are not escaped"),
    # `saipen plan <text>` and bare `saipen plan` are different commands; only
    # the bare one was ever written down, so a weak model answered a specific
    # instruction with four inventions of its own.
    ("plan with text loses its front-of-board rule", "saipen/phases/plan.md",
     replace("FRONT of `## TODO`", "front of the board"),
     "at the front of `## TODO`"),
    ("last_event above the log tail", STATE,
     sub_line("last_event", "999999"),
     "higher than the log"),
    # The counter STATE carries must survive being rebuilt from the LOG the
    # way § 1.5 Recovery rebuilds it. Mutating STATE alone leaves the log
    # untouched, so the two disagree exactly as they would after an untraced
    # bare-`saipen goal` reset.
    ("goal counter STATE cannot survive its own rebuild", STATE,
     bump_int_line("goal_tickets"),
     "newest goal marker rebuilds"),
    # Strip the final newline and the file stops mid-line. Nothing else in this
    # list reads a last byte, which is how the real one survived: every
    # mutation appended below landed INSIDE the last entry instead of after it,
    # and two of these cases quietly stopped being evidence.
    ("BOARD.md ends mid-line", BOARD, lambda t: t.rstrip("\r\n"),
     "end mid-line"),
    # Point a shortcut back at a phase name. The table promises each one lands
    # on a command § 1.10 defines; nothing read that column until v7.148.0,
    # and two rows had already stopped being true.
    ("shortcut routes to a phase, not a command", "saipen/RFC.md",
     replace("| `hh` | `saipen hunt` |", "| `hh` | HUNT |"),
     "do not resolve to a command"),
    ("shortcut routes to a valid but wrong command", "saipen/RFC.md",
     replace("| `cc` | `saipen goal` |",
             "| `cc` | `saipen continue` |"),
     "assigned destination changed"),
    ("shortcut rationale restores stale length magic", "saipen/RFC.md",
     replace("**Length has no global meaning.**",
             "**Doubled is safe, tripled reaches a remote**"),
     "shortcut-rationale"),
    ("translation collect shortcut silently prepares instead",
     "saipen/RFC.md",
     replace("| `eee` | `saipen collect saitranslate` then `saipen ship` |",
             "| `eee` | `saipen prepare saitranslate` then `saipen ship` |"),
     "assigned destination changed"),
    ("ready package loses its source freshness field",
     "saipen/phases/prepare.md",
     replace("`producer`, `source_head`, `coverage`",
             "`producer`, `coverage`"),
     "PREPARE fields"),
    ("non-ready collect loses its no-write guarantee", "saipen/RFC.md",
     replace("No main-project file, checkpoint, Git ref, or remote may "
             "change on that refusal.",
             "The agent should avoid changing files on refusal."),
     "package-handoffs"),
    ("SKILL metadata drops a shortcut trigger", "saipen/SKILL.md",
     replace("cc, ccc, ss, sss, dd", "cc, ccc, ss, dd"),
     "metadata misses RFC shortcut trigger"),
    ("SKILL metadata keeps a stale shortcut trigger", "saipen/SKILL.md",
     replace("qq, qqq, ee,", "qq, qqq, zz, ee,"),
     "metadata has non-RFC shortcut trigger"),
    # Drop a phase-named command from the checkpoint duty. This is how
    # `saipen hunt` shipped: on the surface, absent from the list, and no
    # check compared the two for two releases.
    ("phase-switching command loses its checkpoint duty", "saipen/RFC.md",
     replace("`ship`, `hunt`) invoked while", "`ship`) invoked while"),
     "as phase-switching but the commands named after a phase"),
    ("requires: a capability nobody defines", STATE,
     replace("  - python", "  - pyhton"), "handshake vocabulary"),

    # --- BOARD -----------------------------------------------------------
    ("board heading removed", BOARD, replace("## BLOCKED\n", ""),
     "missing required section heading"),
    ("duplicate board heading", BOARD, lambda t: t + "\n## TODO\n",
     "duplicate section heading"),
    ("two tickets claimed at once", BOARD,
     add_after("## DOING\n", "- [/] T-801 a\n- [/] T-802 b\n"),
     "allows at most one per agent"),
    ("ticket field outside the closed list", BOARD,
     add_after("## TODO\n", "- [ ] T-803 a | assignee: me\n"),
     "unrecognized field"),
    ("needs: a ticket that does not exist", BOARD,
     add_after("## TODO\n", "- [ ] T-804 a | needs: T-9999\n"),
     "dangling needs: reference"),
    ("cyclic needs", BOARD,
     add_after("## TODO\n",
               "- [ ] T-805 a | needs: T-806\n- [ ] T-806 b | needs: T-805\n"),
     "cyclic needs: dependencies"),
    # Both lines in one mutation on purpose: with only the claim, the
    # dependency is dangling and the older check owns the failure, so the
    # Pick Rule branch is never reached.
    ("claimed ticket whose dependency is not done", BOARD,
     lambda t: t.replace("## DOING\n", "## DOING\n- [/] T-809 a | needs: T-810\n", 1)
                .replace("## TODO\n", "## TODO\n- [ ] T-810 b\n", 1),
     "dependencies are not done"),
    ("claim_time with no zone", BOARD,
     add_after("## DOING\n",
               "- [/] T-807 a | owner: x | claim_time: 2026-07-30T01:00:00\n"),
     "not ISO-8601 UTC"),
    ("review_passes over the cap", BOARD,
     add_after("## TODO\n", "- [ ] T-808 a | review_passes: 4\n"),
     "two passes"),
    ("ticket line that is not a ticket", BOARD,
     add_after("## TODO\n", "- [ ] fix this later\n"),
     "doesn't match RFC"),

    # --- LOG -------------------------------------------------------------
    # Appending a LOWER id cannot test this: E-### is contiguous, so any id
    # below the tail already exists and the duplicate check fires first,
    # `continue`s, and the monotonic branch is never reached. Swap the last two
    # entries instead -- ids go backwards with nothing duplicated.
    ("LOG event ids go backwards", LOG, SWAP, "increase monotonically"),
    ("LOG entry with no date", LOG,
     lambda t: t + "- [E-999999] RUN: undated\n", "has no DATE"),

    # --- kitchen ---------------------------------------------------------
    ("digest is not three lines", DIGEST, lambda t: "done: x\nremaining: y\n",
     "exactly three lines"),
    ("markhunt manifest half-written", MANIFEST,
     write_new("vectors: [1,2,3,4,5]\ncursor: done\n"), "is missing"),
    ("markhunt head pair mixed", MANIFEST,
     write_new("vectors: [1,2,3,4,5]\nsurface: x\nfindings: 0\n"
               "cursor: done\nhead_start: abc1234\nhead_end: no-git\n"),
     "never one"),
    ("markhunt done with a vector missing", MANIFEST,
     write_new("vectors: [1,2,4,5]\nsurface: x\nfindings: 0\n"
               "cursor: done\nhead_start: abc1234\nhead_end: abc1234\n"),
     "NOT exhausted"),

    # --- subSaipen -------------------------------------------------------
    ("sub keeps TEMPLATE's agent placeholder", SUB,
     sub_line("agent", "<name>"), "TEMPLATE's placeholder"),
    ("sub in a phase it cannot reach", SUB, sub_line("phase", "BUILD"),
     "unreachable for a subSaipen"),
    ("sub transition_from dropped", SUB, drop_line("transition_from"),
     "ninth required field"),
    ("sub updated not UTC", SUB, sub_line("updated", "2026-07-30 10:00"),
     "must be ISO-8601 UTC"),

    # --- home-repo drift -------------------------------------------------
    ("README badge behind VERSION", "README.md",
     lambda t: re.sub(r"\*\*v\d+\.\d+\.\d+\*\*", "**v1.0.0**", t, count=1),
     "badge doesn't match VERSION"),
    ("a phase doc disappears", "saipen/phases/hunt.md", DELETE,
     "phase enum"),
    ("shipped doc names the superseded palette", "README.md",
     replace("Vintage Golden", "Dark Golden Win95"), "palette-name"),
    ("BOOT drops the reply-language rule", "saipen/BOOT.md",
     replace("Reply-language precedence:", "Reply language precedence:"),
     "reply-language"),
    ("SKILL drops the reply-language precedence", "saipen/SKILL.md",
     replace("Reply-language precedence:", "Reply language precedence:"),
     "reply-language"),
    ("STYLE drops persistent caveman voice", "saipen/STYLE.md",
     replace("Voice persistence:", "Voice remains:"), "chat-voice"),
    # T-404: BOOT.md's on-demand rule-question list and its before-output
    # mandate must stay disjoint. Line 101 once filed STYLE.md under lazy
    # 'rule questions' while line 108 ordered it before any output -- a live
    # session took the cheap reading and never opened the file.
    ("BOOT re-lists STYLE.md as an on-demand rule question",
     "saipen/BOOT.md",
     replace("`saipen/UI.md` (UI work only). **`STYLE.md` is deliberately NOT on",
             "`saipen/STYLE.md` (chat voice), `saipen/UI.md` (UI work only)."
             " **`STYLE.md` is deliberately NOT on"),
     "under on-demand 'rule questions' while ordering it"),
    ("BOOT loses a T-404 disjointness anchor bullet",
     "saipen/BOOT.md",
     replace("- Rule questions `STATE`/`BOARD`/`LOG` + the active phase doc don't answer:",
             "- Questions `STATE`/`BOARD`/`LOG` + the active phase doc don't answer:"),
     "lost one of the two T-404 anchor bullets"),
    ("BOOT moves the STYLE.md read out of the numbered fast path",
     "saipen/BOOT.md",
     replace("1. **Read `STYLE.md` -- the file in the same folder as this `BOOT.md` --",
             "1. **Read the voice notes -- the file in the same folder as this `BOOT.md` --"),
     "no longer orders reading STYLE.md before any output"),
    ("STYLE.md contract edited without reprinting its marker",
     "saipen/STYLE.md",
     replace("Formatting only.", "Formatting mostly."),
     "the contract changed and its marker did not"),
    ("STYLE.md stops declaring a boot marker at all",
     "saipen/STYLE.md",
     replace("`style_contract:", "`style_contrakt:"),
     "boot markers, expected exactly one"),
    ("STYLE.md sets a reply language outside the closed set",
     "saipen/STYLE.md",
     replace("**`reply_language: et`**", "**`reply_language: eesti`**"),
     "is not one of"),
    ("STYLE.md stops declaring a reply language",
     "saipen/STYLE.md",
     replace("**`reply_language: et`**", "Estonian by default."),
     "declares 0 reply_language setting(s)"),
    ("a Core guide opens with mechanics instead of the hook",
     "guides/GUIDE_EE.md",
     replace("On 2026 ja tehisintellekt", "Käivita `saipen set`. On 2026 ja tehisintellekt"),
     "starts with mechanics instead of prose"),
    ("an entry README stops naming the reply-language setting",
     "README.ee.md",
     replace("rida `reply_language:`", "rida stiilifailis"),
     "never mentions `reply_language:`"),
    # T-419: the guard used to stop at the three Core-owned entry documents,
    # so the Japanese root mirror and the 32 locale copies could carry the
    # note today and lose it in the next translation pass with nothing
    # noticing. A locale reader is the one most likely to read an Estonian
    # answer as a broken tool, having arrived in a third language.
    ("a locale README stops naming the reply-language setting",
     ".saipen/saitranslate/kitchen/ru/README_RU.md",
     replace("`reply_language:`", "строку языка"),
     "never mentions `reply_language:`"),
    ("BOOT.md presents the precedence rule without the setting",
     "saipen/BOOT.md",
     replace("`STYLE.md`'s `reply_language:` (step 1",
             "`STYLE.md`'s language rule (step 1"),
     "without naming STYLE.md's `reply_language:` setting"),
    ("BOOT.md leaks STYLE.md's marker value",
     "saipen/BOOT.md", leak_style_marker,
     "carries STYLE.md's marker value"),
    ("BOOT fast-path STYLE.md read loses its self-locating reference",
     "saipen/BOOT.md",
     replace("the file in the same folder as this `BOOT.md`",
             "`<saipen_home>/STYLE.md`"),
     "lost its self-locating reference"),
    ("BOOT loses the fast-path section heading",
     "saipen/BOOT.md",
     replace("## Fast path", "## Boot sequence"),
     "lost its '## Fast path' or '## Anything else' heading"),
    ("an adapter lazily defers STYLE.md to a rule question",
     "extensions/adapters/deepseek.md",
     replace("`saipen/STYLE.md` is a boot-read: apply it before any output.",
             "`saipen/STYLE.md` loads alongside it."),
     "as a rule-question escalation"),
    # T-401: the WARN ownership ledger is data, not decoration. Each tracked
    # slug must carry semver first/last seen and a rationale; a slug that
    # survives WARN_OWNER_SPAN consecutive releases must be named by a live
    # BOARD ticket. These mutate the baseline DATA -- a broken map key, a
    # missing rationale, a non-semver bound -- never validator wording.
    ("baseline warn_slugs map key drifts",
     "tools/release_ledger_baseline.json",
     replace('"warn_slugs": {', '"warn_slugs_x": {'),
     "must contain exactly tag_only, changelog_only and warn_slugs maps"),
    ("baseline warn_slugs entry loses its rationale",
     "tools/release_ledger_baseline.json",
     replace('"rationale": "BOARD.md outgrew', '"rationale_x": "BOARD.md outgrew'),
     "needs first_seen, last_seen and rationale"),
    ("baseline warn_slugs entry gains non-semver bounds",
     "tools/release_ledger_baseline.json",
     replace('"first_seen": "7.72.0"', '"first_seen": "banana"'),
     "has non-semver first_seen/last_seen"),
    ("a locale loses its guide", "guides/GUIDE_UK.md", DELETE,
     "locale coverage"),
    ("a locale guide loses its shortcut callout", "guides/GUIDE_AR.md",
     lambda t: re.sub(r"^\*\*[^\n]*`cc`[^\n]*#110-command-surface[^\n]*\n",
                      "", t, count=1, flags=re.MULTILINE),
     "shortcut-callouts"),
    ("root device artifact is no longer Git-ignored", ".gitignore",
     replace("/nul\n", ""), "root-device-ignore"),
    # NOT tested here: the phantom-version check needs the TAG half of the
    # release ledger, and this harness copies the tree without .git on
    # purpose. Without tags the check correctly declines to run, so a case
    # for it could only ever match the WARN saying it was skipped -- which
    # is exactly how it scored as "always present". CI covers it, where the
    # checkout carries tags (fetch-depth: 0).

    # T-426: transition-table EDGES must agree in every copy, not just the
    # phase NAMES. The DFA is the enforced representation; both remaining
    # copies (RFC § 1.6's fence table, and each phases/*.md exit line) are
    # gated against it. Each mutation is a byte in a DIFFERENT copy, so a
    # drift in one is caught no matter which one drifts first.
    ("RFC transition table loses an edge", "saipen/RFC.md",
     replace("SCOUT     -> BUILD | BLOCKED", "SCOUT     -> BLOCKED"),
     "transition-table"),
    ("phase doc exit names an edge the DFA rejects", "saipen/phases/scout.md",
     replace("After SCOUT: STATE -> BUILD.", "After SCOUT: STATE -> SHIP."),
     "phase-exit"),

    # T-430: a LOG line records what happened. One word turns E-1769 from an
    # event into an intention, and every reader after it -- § 1.5's Recovery
    # rebuild included -- would still count it as evidence the act occurred.
    # The anchor is safe to name: append-only makes that line immutable.
    ("a LOG entry states its event in the future tense", ".saipen/LOG.md",
     replace("RUN: prepare saiwiki (qq)", "RUN: will prepare saiwiki (qq)"),
     "future tense"),

    # T-431: two ways a completion claim outran its evidence, one control
    # each. Both mutations leave the CLAIM intact and remove only what backs
    # it -- which is the state both files were shipped in.
    ("a ## DONE ticket carries no verify evidence", ".saipen/BOARD.md",
     strip_done_verify, "no | verify: evidence"),
    ("a CONFORMANCE row cites a ticket still open on the board",
     "saipen/CONFORMANCE.md", cite_open_ticket, "cites unfinished work"),

    (".saipen/ carries a copy of the protocol", ".saipen/RFC.md",
     CREATE, "§ 1.7"),
]


def apply_case(root: Path, rel: str, mutation) -> bool:
    """Returns False when the case cannot be set up (skip it loudly)."""
    p = case_target(root, rel, mutation)
    if mutation == DELETE:
        if not p.exists():
            return False
        p.unlink()
        return True
    if mutation == CREATE:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("copied protocol\n", encoding="utf-8")
        return True
    if isinstance(mutation, tuple) and mutation[0] == "WRITE":
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(mutation[1], encoding="utf-8", newline="\n")
        return True
    if mutation == SWAP:
        lines = p.read_text(encoding="utf-8-sig").splitlines(True)
        idx = [i for i, ln in enumerate(lines) if ln.startswith("- ")]
        if len(idx) < 2:
            return False
        a, b = idx[-2], idx[-1]
        lines[a], lines[b] = lines[b], lines[a]
        p.write_text("".join(lines), encoding="utf-8", newline="\n")
        return True
    if mutation == UTF16:
        if not p.exists():
            return False
        text = p.read_text(encoding="utf-8-sig")
        p.write_bytes(text.encode("utf-16"))
        return True
    if not p.exists():
        return False
    text = p.read_text(encoding="utf-8-sig")
    mutated = mutation(text)
    if mutated == text:
        return False
    p.write_text(mutated, encoding="utf-8", newline="\n")
    return True


def validator_output(root: Path) -> str:
    """Only the FAIL/WARN lines. Searching the whole output matched PASS text:
    "at most one", "cyclic" and "dangling needs" all appear in the lines that
    say those very checks PASSED, so five cases scored as proving nothing when
    the harness was the thing at fault."""
    r = subprocess.run([sys.executable, str(root / "tools" / "validate.py")],
                       cwd=root, capture_output=True, text=True,
                       errors="replace")
    keep = [ln for ln in (r.stdout + r.stderr).splitlines()
            if ln.startswith(("FAIL", "WARN", "Traceback")) or "Error" in ln]
    return "\n".join(keep)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="audit_checks_"))
    device_error = root_device_ignore_probe(tmp)
    if device_error:
        print(f"FAIL: root `nul` snapshot control -- {device_error}")
        shutil.rmtree(tmp, ignore_errors=True)
        return 1
    print("PASS: a real root `nul` entry is excluded from audit snapshots")

    pristine = tmp / "pristine"
    shutil.copytree(HOME, pristine, ignore=IGNORE)

    ledger_error = release_ledger_probe(pristine, tmp)
    if ledger_error:
        print(f"FAIL: release-ledger divergence probe -- {ledger_error}")
        shutil.rmtree(tmp, ignore_errors=True)
        return 1
    print("PASS: release-ledger clean/new-tag/new-changelog/stale-baseline "
          "controls behave distinctly")

    owner_error = warn_ownership_probe(pristine, tmp)
    if owner_error:
        print(f"FAIL: warn-slug ownership probe -- {owner_error}")
        shutil.rmtree(tmp, ignore_errors=True)
        return 1
    print("PASS: aged unowned WARN slug fails; identical aged slug with a "
          "live naming ticket passes; baseline data, never validator wording")

    rename_error = phase_rename_probe(pristine, tmp)
    if rename_error:
        print(f"FAIL: phase-rename probe -- {rename_error}")
        shutil.rmtree(tmp, ignore_errors=True)
        return 1
    print("PASS: consistent SCOUT->SCOUTX rename stays green across the DFA, "
          "RFC table, schema enum and phase doc -- edge gates catch drift, "
          "not deliberate renames")

    batch_error = audit_tags_batch_probe(HOME, tmp)
    if batch_error:
        print(f"FAIL: audit-tags batch process probe -- {batch_error}")
        shutil.rmtree(tmp, ignore_errors=True)
        return 1
    print("PASS: audit-tags missing-Git skip plus enumeration, nonzero, "
          "malformed, truncated, and surplus fail-closed controls behave")

    query_count, query_error = observed_tag_queries(pristine)
    red_tree = tmp / "duplicate-tag-query"
    shutil.copytree(pristine, red_tree)
    setup_error = duplicate_tag_query(red_tree / "tools" / "validate.py")
    red_count, red_error = observed_tag_queries(red_tree)
    shutil.rmtree(red_tree, ignore_errors=True)
    if query_error or setup_error or red_error or query_count != 1 or red_count != 2:
        problem = query_error or setup_error or red_error
        if problem is None:
            problem = (f"observed {query_count} tag queries; expected 1"
                       if query_count != 1 else
                       f"duplicate red-control observed {red_count}; expected 2")
        print(f"FAIL: release-ledger runtime query probe -- {problem}")
        shutil.rmtree(tmp, ignore_errors=True)
        return 1

    # The observation itself must not bless a stuck-red validator merely
    # because Git still launched. Break the pristine STATE, require a control
    # error, then restore it before the mutation table starts.
    state_path = pristine / STATE
    state_source = state_path.read_text(encoding="utf-8-sig")
    state_path.write_text(
        re.sub(r"^phase:.*$", "phase: NOT-A-PHASE", state_source,
               count=1, flags=re.MULTILINE),
        encoding="utf-8", newline="\n")
    _, invalid_control_error = observed_tag_queries(pristine)
    state_path.write_text(state_source, encoding="utf-8", newline="\n")
    if invalid_control_error is None:
        print("FAIL: release-ledger runtime query probe accepted a validator "
              "control that was deliberately stuck red")
        shutil.rmtree(tmp, ignore_errors=True)
        return 1

    # The control. Every expectation below must be ABSENT here, or the case
    # proves nothing -- a message that is always present is not evidence.
    control = validator_output(pristine)
    if "Traceback" in control:
        print("FAIL: the validator crashes on an unmodified copy -- fix that "
              "before trusting any case below")
        print(control[-800:])
        shutil.rmtree(tmp, ignore_errors=True)
        return 1
    control_failure = next((line for line in control.splitlines()
                            if line.startswith("FAIL")), None)
    if control_failure:
        print("FAIL: the validator rejects an unmodified copy -- fix the "
              "known-good control before trusting mutation results")
        print(control_failure[:800])
        shutil.rmtree(tmp, ignore_errors=True)
        return 1

    # A callable that changes nothing is not an applied mutation. The
    # goal-counter case once hard-coded the exact integer live STATE already
    # carried, so the validator saw an untouched tree and the suite still
    # counted the case as evidence. Keep this harness guard red-test inside
    # the harness: removing the equality check above makes this control fail.
    if apply_case(pristine, STATE, lambda text: text):
        print("FAIL: callable no-op mutation was accepted as applied")
        shutil.rmtree(tmp, ignore_errors=True)
        return 1
    print("PASS: callable no-op mutations are rejected before validation")

    unavailable = [label for label, rel, mutation, _expected in CASES
                   if not case_available(pristine, rel, mutation)]
    if unavailable:
        for label in unavailable:
            print(f"FAIL: skipped canonical mutation: {label}")
        print("FAIL: canonical mutation suite cannot start with a changing "
              "denominator")
        shutil.rmtree(tmp, ignore_errors=True)
        return 1

    # One copy, not one per case. Every case touches exactly one file, so
    # saving that file's bytes and putting them back is equivalent to a fresh
    # tree and turns 41 copytrees of a repo carrying 32 locale directories into
    # one. The difference is four minutes against twenty seconds, which is the
    # difference between a gate CI runs and a gate someone deletes.
    dead, skipped, always = [], [], []
    for label, rel, mutation, expected in CASES:
        if expected in control:
            always.append((label, expected))
            continue
        target = case_target(pristine, rel, mutation)
        saved = target.read_bytes() if target.exists() else None
        try:
            if not apply_case(pristine, rel, mutation):
                skipped.append(label)
                continue
            if expected not in validator_output(pristine):
                dead.append((label, expected))
        finally:
            if saved is None:
                if target.exists():
                    target.unlink()
            else:
                target.write_bytes(saved)
    # The copy must be back to its starting state, or every case after the
    # first was run against a tree carrying the previous mutation.
    if validator_output(pristine) != control:
        print("FAIL: restoring between cases did not put the copy back -- the "
              "results above were measured against a drifting tree")
        shutil.rmtree(tmp, ignore_errors=True)
        return 1
    shutil.rmtree(tmp, ignore_errors=True)

    for label, expected in always:
        print(f"FAIL: {label!r} expects {expected!r}, which the UNMODIFIED "
              f"repository already prints -- the case proves nothing")
    for label in skipped:
        print(f"SKIP: {label} -- the file it mutates is absent here")
    for label, expected in dead:
        print(f"FAIL: {label} -- the validator did not report {expected!r}. "
              f"That check no longer goes red on its own condition")

    live = len(CASES) - len(dead) - len(skipped) - len(always)
    if dead or always or skipped:
        print(f"\n{len(dead) + len(always) + len(skipped)} of {len(CASES)} "
              "case(s) are not "
              f"evidence any more.")
        return 1
    print("PASS: release-ledger tag query is observed once; duplicate-query "
          "and invalid-validator controls both go red")
    print(f"PASS: {live} of {len(CASES)} validator check(s) still go red on "
          f"their own condition"
          + (f" ({len(skipped)} skipped)" if skipped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

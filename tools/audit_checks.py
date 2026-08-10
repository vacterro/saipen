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

Single file per case, deliberately. A validator condition whose trigger spans
MORE than one project file cannot be red-tested here: mutate `STATE.md` alone
and the board still disagrees, mutate `BOARD.md` alone and `next_action` is
still legal, and every single-file attempt goes not-red. Those belong in
`tests/scenarios/`, which constructs a whole `.saipen/` and is therefore the
canonical route for a compound condition -- no new mechanism was needed for it,
only the observation that this one is the wrong tool (T-457). The DONE-wait
deadlock under both goal modes is the worked pair:
`tests/scenarios/done-wait-deadlock/` and `-goal-mode/`.
"""
from __future__ import annotations

import ast
import contextlib
import datetime
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from freshness import compute_role_revision, compute_source_identity

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
CHANGELOG = "CHANGELOG.md"
CORE = "saipen/CORE.md"
IMPROVE = "saipen/IMPROVE.md"
INDEX = "saipen/INDEX.md"
CREW_BACKLOG = ".saipen/KNOWLEDGE/crew-v8-backlog.md"
STATE_SCHEMA = "extensions/schemas/state.schema.json"
IMPROVE_REPORT = ".saipen/improve/imp-key-20260808/seat01/" \
                 "saipen_improve_PROJ.md"
IMPROVE_MANIFEST = ".saipen/improve/imp-key-20260808/MANIFEST.md"
PHASE_IMPROVE = "saipen/phases/improve.md"
TAG_QUERY = ("git", "tag", "-l", "v*")
AUDIT_TAGS_GIT_SHIM = "SAIPEN_AUDIT_TAGS_GIT_SHIM"
AUDIT_TAGS_MODE = "SAIPEN_AUDIT_TAGS_MODE"


def freshen_synthetic_outboxes(tree: Path) -> None:
    """Make copied producer packages valid without touching live OUTBOXes."""
    identity = compute_source_identity(tree)

    def upsert_bold(text: str, field: str, value: str) -> str:
        pattern = rf"(?m)^- \*\*{re.escape(field)}:\*\*.*$"
        line = f"- **{field}:** {value}"
        if re.search(pattern, text):
            return re.sub(pattern, line, text, count=1)
        return text.replace("- **producer:**", line + "\n- **producer:**", 1)

    wiki = tree / ".saipen/extensions/subs/saiwiki/kitchen/OUTBOX.md"
    wiki_charter = tree / "extensions/subs/saiwiki.md"
    if wiki.is_file() and wiki_charter.is_file():
        text = wiki.read_text(encoding="utf-8-sig")
        first_entry = text.find("\n## ")
        if first_entry >= 0:
            text = "# OUTBOX\n" + text[first_entry:]
        text = upsert_bold(text, "source_head", identity.source_head)
        text = upsert_bold(
            text, "source_tree_fingerprint", identity.source_tree_fingerprint)
        text = upsert_bold(text, "role_revision",
                           compute_role_revision(wiki_charter))
        wiki.write_text(text, encoding="utf-8", newline="\n")

    translate = tree / ".saipen/saitranslate/kitchen/OUTBOX.md"
    translate_charter = tree / "extensions/subs/saitranslate.md"
    if translate.is_file() and translate_charter.is_file():
        text = translate.read_text(encoding="utf-8-sig")
        fields = {
            "source_head": identity.source_head,
            "source_tree_fingerprint": identity.source_tree_fingerprint,
            "role_revision": compute_role_revision(translate_charter),
            "summary": "synthetic audit control package",
            "critical": "false",
        }
        for field, value in fields.items():
            pattern = rf"(?m)^{re.escape(field)}:.*$"
            line = f"{field}: {value}"
            if re.search(pattern, text):
                text = re.sub(pattern, line, text, count=1)
            else:
                text = text.replace("producer:", line + "\nproducer:", 1)
        translate.write_text(text, encoding="utf-8", newline="\n")

    derived_translate = (tree / ".saipen/extensions/subs/saitranslate"
                         / "kitchen/OUTBOX.md")
    if derived_translate.is_file():
        derived_translate.write_text("# OUTBOX\n", encoding="utf-8", newline="\n")


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

    # This probe tests release-ledger divergence, not handoff freshness. The
    # live repository may deliberately carry producer-owned ready packages
    # awaiting another model; make those historical in the synthetic clone so
    # unrelated OUTBOX failures cannot mask this probe's own red controls.
    outboxes = list(tree.glob(".saipen/extensions/subs/*/kitchen/OUTBOX.md"))
    translate_outbox = tree / ".saipen" / "saitranslate" / "kitchen" / "OUTBOX.md"
    if translate_outbox.is_file():
        outboxes.append(translate_outbox)
    for outbox in outboxes:
        text = outbox.read_text(encoding="utf-8-sig")
        text = text.replace("**status:** ready", "**status:** stale")
        text = re.sub(r"(?m)^status:\s*ready\s*$", "status: stale", text)
        outbox.write_text(text, encoding="utf-8", newline="\n")

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=tree, capture_output=True,
                              text=True, errors="replace")

    for args in (("init", "-q"),
                 ("config", "user.name", "SAIPEN ledger probe"),
                 ("config", "user.email", "ledger-probe@example.invalid"),
                 # The committed tree, not just present: the runtime
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

    # The copied real `.saipen/LOG.md` carries `hunt -> clean @<hash>` marks
    # that name this repository's real commits. In this synthetic repo only
    # the probe's own commit exists, so the hunt-mark gate (tools/validate.py)
    # FAILs the fixture before any release-ledger control has run -- a reason
    # the probe does not test. Re-point the active marks at the synthetic
    # commit and commit the sanitization, so the fixture again resembles a
    # real clone in every way the validator can see.
    active_log = tree / ".saipen" / "LOG.md"
    if active_log.is_file():
        short = git("rev-parse", "--short", "HEAD").stdout.strip()
        text = active_log.read_text(encoding="utf-8-sig")
        sanitized = re.sub(r"hunt -> clean @[0-9a-f]{7,40}\b",
                           f"hunt -> clean @{short}", text)
        if sanitized != text:
            active_log.write_text(sanitized, encoding="utf-8", newline="\n")
            for args in (("add", ".saipen/LOG.md"),
                         ("commit", "-q", "-m",
                          "re-point synthetic hunt marks")):
                result = git(*args)
                if result.returncode:
                    return (f"git {' '.join(args)} failed: "
                            + (result.stderr or result.stdout).strip())

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
        first = next((line for line in control_text.splitlines()
                      if line.startswith(("FAIL", "WARN [release-ledger]"))),
                     "validator exited without a focused line")
        return f"clean synthetic ledger is not clean: {first}"

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
    for charter in (tree / "extensions" / "subs").glob("sai*.md"):
        text = charter.read_text(encoding="utf-8-sig")
        revision = compute_role_revision(charter)
        text = re.sub(r'(?m)^role_revision:\s*["\']?[^\s"\']+["\']?$',
                      f'role_revision: "{revision}"', text, count=1)
        charter.write_text(text, encoding="utf-8", newline="\n")
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


def force_goal(text: str, counters: str = ""):
    """Set execution_intent: goal in a STATE frontmatter regardless of what
    the live/pristine state currently holds.

    The harness copies the repo's own live STATE, which may itself sit at
    `execution_intent: goal` (a running goal) -- so `sub_line("execution_intent",
    "goal")` is a no-op exactly when the case needs it to fire. This strips any
    existing intent/counter/legacy lines and writes the goal intent plus the
    requested counter lines deterministically. Anchored on `\\n---` (the closing
    frontmatter delimiter) rather than `\\n---\\n`, because the source may or may
    not carry a trailing newline and the counters must land inside the block
    either way.
    """
    out = [ln for ln in text.splitlines()
           if not ln.startswith(("execution_intent:", "goal_mode:",
                                 "goal_waves:", "goal_tickets:"))]
    joined = "\n".join(out) + "\n"
    if counters:
        joined = joined.replace("\n---", "\n" + counters + "\n---", 1)
    return joined.replace("mode: full", "mode: full\nexecution_intent: goal", 1)


def force_converge(text: str, next_action: str = '"PHASE ADD"'):
    """Write execution_intent: converge plus a given next_action into a STATE
    frontmatter regardless of what the live/pristine state currently holds.

    The T-539 red controls need a converge state that names ADD (scenario 7)
    or a goal-keyed valve pause (the wording half); the live STATE sits at
    `execution_intent: goal` with a ticket-bearing next_action, so both intent
    and next_action have to be replaced deterministically, not via sub_line.
    Same `\n---` anchoring as force_goal so the block closes either way.
    """
    out = [ln for ln in text.splitlines()
           if not ln.startswith(("execution_intent:", "goal_mode:",
                                 "goal_waves:", "goal_tickets:",
                                 "next_action:"))]
    joined = "\n".join(out) + "\n"
    joined = joined.replace("\n---", f"\nnext_action: {next_action}\n---", 1)
    return joined.replace("mode: full", "mode: full\nexecution_intent: converge", 1)


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


def stamp_log_ahead(text: str) -> str:
    """T-432: restamp the newest LOG entry 6 minutes ahead of the real clock.

    Computed at mutation time, never hardcoded: a pinned date drifts into the
    past and the control silently stops proving anything -- the same no-op
    trap leak_style_marker was written to avoid. 6 minutes is one past the
    validator's 5-minute slack, so the control tests the BOUND rather than
    some obviously-absurd year.
    """
    ahead = (datetime.datetime.now(datetime.timezone.utc)
             + datetime.timedelta(minutes=6))
    lines = text.splitlines()
    for i in range(len(lines) - 1, -1, -1):
        if re.match(r"^- \d{2}\.\d{2}\.\d{2} \d{2}:\d{2} \[E-\d+\]", lines[i]):
            lines[i] = re.sub(r"^- \d{2}\.\d{2}\.\d{2} \d{2}:\d{2} ",
                              "- " + ahead.strftime("%d.%m.%y %H:%M") + " ",
                              lines[i])
            break
    return "\n".join(lines) + "\n"


def demote_the_pick(text: str) -> str:
    """T-474: reach the topmost-workable branch from any board state.

    The pick check compares `next_action` against the topmost workable
    `## TODO` ticket ONLY when nothing is claimed -- a `## DOING` ticket IS
    the pick (T-466) -- so the mutation must both empty `## DOING` AND
    arrange the TODO mismatch. Inject two synthetic workable tickets: T-999
    at the top of `## TODO` (always the topmost workable) and T-998 at the
    bottom (so the case's STATE mutation can name a workable ticket that is
    never topmost). The mismatch holds whatever the real board and real
    STATE hold -- the old "demote the ticket next_action names" went vacuous
    three times: once with a single workable ticket, once with a DONE-state
    non-ticket next_action, and once on a ship commit whose own ticket sat
    in `## DOING` (T-532, T-534).
    """
    nl = chr(10)
    doing = re.search(r"^## DOING$\n(.*?)(?=^## |\Z)", text,
                      re.MULTILINE | re.DOTALL)
    if doing is not None:
        body = doing.group(1)
        if body.strip():
            cleaned = "\n".join(
                ln for ln in body.splitlines()
                if not ln.strip().startswith("- ["))
            text = text[:doing.start(1)] + cleaned + text[doing.end(1):]
    todo = re.search(r"^## TODO$\n(.*?)(?=^## |\Z)", text,
                     re.MULTILINE | re.DOTALL)
    if todo is None:
        return text
    top = "- [ ] T-999 [P3] synthetic red-control workable ticket\n"
    bottom = "- [ ] T-998 [P3] synthetic red-control workable ticket\n"
    return (text[:todo.start(1)] + top + todo.group(1).rstrip(nl) + nl
            + bottom + nl + text[todo.end(1):])


def inject_unclaimed_doing(text: str) -> str:
    """T-573: put an unclaimed ticket in ## DOING whatever the live board holds.

    An ownerless ## DOING ticket is 'unclaimed by definition' (RFC § 1.4), so
    STATE.task: none beside it is the BOARD-ahead-of-STATE interruption. The
    first version of this case mutated STATE.task alone and went dead the
    moment a checkpoint moved the live phase to DONE (its task line was
    already `none`), which is exactly the live-state dependence the synthetic
    tickets in this harness exist to remove.
    """
    nl = chr(10)
    doing = re.search(r"^## DOING$\n(.*?)(?=^## |\Z)", text,
                      re.MULTILINE | re.DOTALL)
    if doing is None:
        return text
    body = doing.group(1)
    if "- [/] T-999 audit" in body:
        return text
    cleaned = "\n".join(
        ln for ln in body.splitlines()
        if not ln.strip().startswith("- ["))
    if cleaned.strip():
        cleaned += nl
    return (text[:doing.start(1)] + cleaned
            + "- [/] T-999 audit | verify: probe\n"
            + text[doing.end(1):])

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


def mutation_files(root: Path, rel: str, mutation) -> list[Path]:
    """Every physical file a logical mutation will edit, for save/restore."""
    if isinstance(mutation, tuple) and mutation and mutation[0] == "MULTI":
        return [root / r for r, _ in mutation[1]]
    return [case_target(root, rel, mutation)]


def case_available(root: Path, rel: str, mutation) -> bool:
    if mutation == CREATE or (isinstance(mutation, tuple)
                              and mutation[0] == "WRITE"):
        return True
    if isinstance(mutation, tuple) and mutation and mutation[0] == "MULTI":
        return all((root / r).is_file() for r, _ in mutation[1])
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
    # T-565. `minimum` sat on four STATE fields while nothing interpreted it,
    # so a negative safety-valve counter read as valid: `goal_waves: -1` means
    # § 2.4's three-wave ceiling is four waves away, and the valve protects the
    # long unattended runs least able to notice. One control per floor the
    # schema states, because they are four independent claims -- a fix that
    # restored only the counters would leave the two LOG/format markers open.
    ("negative goal_waves passes the schema floor", STATE,
     lambda s: force_goal(s, "goal_waves: -1\ngoal_tickets: 0"),
     "goal_waves: -1 is below the schema minimum 0"),
    ("negative goal_tickets passes the schema floor", STATE,
     lambda s: force_goal(s, "goal_waves: 0\ngoal_tickets: -1"),
     "goal_tickets: -1 is below the schema minimum 0"),
    ("schema_version below its own floor", STATE, sub_line("schema_version", "0"),
     "schema_version: 0 is below the schema minimum 1"),
    ("last_event claims an event number that cannot exist", STATE,
     sub_line("last_event", "0"),
     "last_event: 0 is below the schema minimum 1"),
    # The class control, not an instance of it: a keyword added to the schema
    # with no enforcer used to be a silent no-op, which is why `minimum` could
    # sit there through four releases. `exclusiveMinimum` is a real draft-07
    # keyword this validator does not implement -- the audit must say so rather
    # than let the schema believe it constrains something.
    ("schema keyword with no enforcer is silently ignored", STATE_SCHEMA,
     replace('"goal_waves": {\n      "type": "integer",\n      "minimum": 0,',
             '"goal_waves": {\n      "type": "integer",\n'
             '      "exclusiveMinimum": -5,\n      "minimum": 0,'),
     "'exclusiveMinimum' on field goal_waves that tools/validate.py "
     "does not interpret"),
    # The second half of the same guarantee: `type` has an enforcer, but that
    # enforcer knows four of JSON Schema's seven types. A schema declaring
    # `type: number` would clear the keyword audit and still be interpreted by
    # nobody, which is the exact shape `minimum` had.
    ("schema type outside the interpreted set", STATE_SCHEMA,
     replace('"saipen_version": {\n      "type": "integer"',
             '"saipen_version": {\n      "type": "number"'),
     "'type: number' on field saipen_version"),
    # Array element types. `requires:` is § 1.3's capability handshake, and the
    # vocabulary WARN below it skips non-strings silently, so a wrong-typed
    # element was invisible at both rungs.
    ("requires carries a non-string capability", STATE,
     replace("  - filesystem\n", "  - 12345\n"),
     "requires[0]: expected string"),
    ("current-schema state missing last_event", STATE, drop_line("last_event"),
     "requires last_event"),
    ("current-schema state missing style_contract", STATE,
     drop_line("style_contract"), "requires style_contract"),
    ("style_contract names a different voice contract", STATE,
     sub_line("style_contract", "ded-deadbeef"),
     "did not read the current STYLE.md"),
    # T-573: STATE.task and ## DOING are one binding. The v7.215.0 crash
    # checkpoint claimed task T-572 while no ## DOING ticket existed and
    # T-572 sat in ## TODO -- validator-conformant until this rule. Both
    # interruption directions go red. The mutations force the crash shape
    # whatever the live state holds (the first versions mutated STATE alone
    # and went dead when a checkpoint moved the live phase to DONE): a task
    # naming a ticket the board does not claim, and an unclaimed ## DOING
    # ticket the state does not name.
    ("active task not claimed by ## DOING", STATE,
     lambda s: sub_line("task", "T-999")(sub_line("phase", "SCOUT")(s)),
     "is not the claimed ## DOING ticket"),
    ("self-claimed ## DOING ticket with task: none", STATE,
     ("MULTI", [(STATE, lambda s: sub_line("task", "none")(
                 sub_line("phase", "SCOUT")(s))),
                (BOARD, inject_unclaimed_doing)]),
     "STATE is behind BOARD"),
    # The changelog-unarchived warning names the header's "~10" claim as its
    # reason; a header edited to a looser number would silently make that
    # warning a lie, so the exact archive pointer is a FAIL, not a WARN.
    ("changelog archive pointer loosened", CHANGELOG,
     replace("keeps the most recent ~10.", "keeps the most recent ~50."),
     "changelog-archive-pointer"),
    # T-571: `saipen crew` carries exactly one execution meaning. A crew row
    # that gains a concurrent reading, or a gated backlog that reuses the
    # `saipen crew` name for the concurrent design, is the ambiguity a weak
    # model resolves wrongly while believing it followed SAIPEN.
    ("crew command row loses its single-meaning statement", CORE,
     replace("exactly one execution meaning",
             "a meaning that may include concurrency"),
     "crew-naming"),
    ("concurrent backlog reuses the crew command name", CREW_BACKLOG,
     lambda t: t.replace("`saipen concurrent`", "`saipen crew`"),
     "crew-naming"),
    ("live board reintroduces the pre-T-571 Crew Mode name", BOARD,
     replace("v8 Concurrent Mode", "v8 Crew Mode"),
     "crew-naming"),
    # T-551/T-555: a seat report that leaks a machine-local saipen_home path
    # into its identity is rejected; the manifest is routing-only and may not
    # duplicate report status.
    ("improve report leaks a machine-local saipen_home path", IMPROVE_REPORT,
     write_new("saipen_home: V:/machine/local/path\nreport_status: draft\n"),
     "saipen_home path in its header"),
    ("improve cycle manifest duplicates report status", IMPROVE_MANIFEST,
     write_new("cycle_id: imp-key-20260808\nstatus: complete\n"),
     "owns routing only"),
    # T-552: Improve is a meta-control; a phases/improve.md file is an
    # unofficial seventeenth phase and must fail.
    ("improve becomes an unofficial phase", PHASE_IMPROVE, CREATE,
     "improve-meta-control"),
    # T-553: improve routing/status is DERIVED from the manifest + reports +
    # sweep ledger, never carried in STATE.md. Finding text and independent
    # improve_* counters in STATE are both the drift the derived model forbids.
    ("STATE carries an independent improve_ routing field", STATE,
     lambda t: t.replace("blocker: \"\"",
                         "blocker: \"\"\nimprove_cycle: imp-x"),
     "improve-state-purity"),
    ("STATE carries finding text", STATE,
     lambda t: t.rstrip() + "\n\nIMP-001 [P1] [LOGIC_ERROR] [proven] "
                            "[ticket]\nexpected: x\nactual: y\nevidence: z\n",
     "improve-state-purity"),
    # T-622: CORE, IMPROVE and the CLI carry one exact public action set.
    ("CORE Improve declaration loses cycle-complete", CORE,
     lambda t: t.replace(", cycle-complete,", ","),
     "improve-command-parity"),
    ("IMPROVE declaration loses submit", IMPROVE,
     lambda t: t.replace("bare, status, submit,", "bare, status,"),
     "improve-command-parity"),
    ("Improve CLI gains an undeclared action", "tools/saipen.py",
     lambda t: t.replace(
         '    if action == "clean":',
         '    if action == "extra":\n        return 0\n    if action == "clean":'),
     "improve-command-parity"),
    ("nested success decoy launders a declared action", CORE,
     ("MULTI", [
         (CORE, lambda t: t.replace("abort, clean]", "abort, extra, clean]")),
         (IMPROVE,
          lambda t: t.replace("abort, clean]", "abort, extra, clean]")),
         ("tools/saipen.py", lambda t: t.replace(
             '    if action == "clean":',
             '    if action == "extra":\n'
             '        def decoy():\n'
             '            return 0\n'
             '        return 2\n'
             '    if action == "clean":'))]),
     "improve-command-parity"),
    ("constant-false success decoy launders a declared action", CORE,
     ("MULTI", [
         (CORE, lambda t: t.replace("abort, clean]", "abort, extra, clean]")),
         (IMPROVE,
          lambda t: t.replace("abort, clean]", "abort, extra, clean]")),
         ("tools/saipen.py", lambda t: t.replace(
             '    if action == "clean":',
             '    if action == "extra":\n'
             '        if False:\n'
             '            return 0\n'
             '        return 2\n'
             '    if action == "clean":'))]),
     "improve-command-parity"),
    ("Improve CLI loses the verify executor", "tools/saipen.py",
     lambda t: t.replace('action == "verify"', 'action == "verifx"'),
     "improve-command-parity"),
    ("improve clean route loses its never-CLEAN statement", CORE,
     lambda t: t.replace("never enters the CLEAN phase",
                         "may archive reports"),
     "improve-command-family"),
    ("improve loses the writer boundary", IMPROVE,
     lambda t: t.replace("writes only inside its own home",
                         "may write anywhere it likes"),
     "improve-boundary"),
    ("improve verify stops being delta-only", IMPROVE,
     lambda t: t.replace("delta-only", "full-audit"),
     "improve-boundary"),
    # T-555: a seat report is mechanically checkable -- a finding without the
    # expected/actual/evidence triple, a complete report over an unmet
    # completion bar, and a partial scope claiming full context all fail.
    ("improve report finding lacks the evidence triple", IMPROVE_REPORT,
     write_new("report_status: draft\ncontext_scope: tools/\n"
               "context_available: partial\n\n"
               "IMP-001 [P1] [LOGIC_ERROR] [observed] [ticket]\n"
               "expected: x\nactual: y\n"),
     "improve report [improve-report]"),
    ("improve report complete over an unmet completion bar", IMPROVE_REPORT,
     write_new("report_status: complete\n"),
     "improve report [improve-report]"),
    ("improve report partial scope claims full context", IMPROVE_REPORT,
     write_new("report_status: draft\ncontext_scope: partial: tools only\n"
               "context_available: complete\n\n"
               "IMP-001 [P1] [LOGIC_ERROR] [observed] [ticket]\n"
               "expected: x\nactual: y\nevidence: z\n"),
     "improve report [improve-report]"),
    # T-622: exact ordered five-level proof contract, including assignment.
    ("SAICRITIC drops PROVENANCE", "saipen/SAICRITIC.md",
     lambda t: t.replace(
         "| PROVENANCE | does the evidence bind the exact source, session, run, finding and result it claims? |\n",
         ""),
     "saicritic"),
    ("SAICRITIC swaps GATE and PROVENANCE", "saipen/SAICRITIC.md",
     lambda t: t.replace(
         "| GATE | did the REQUIRED semantic/protocol gates actually occur? |\n"
         "| PROVENANCE | does the evidence bind the exact source, session, run, finding and result it claims? |",
         "| PROVENANCE | does the evidence bind the exact source, session, run, finding and result it claims? |\n"
         "| GATE | did the REQUIRED semantic/protocol gates actually occur? |"),
     "saicritic"),
    ("SAICRITIC duplicates UNIT", "saipen/SAICRITIC.md",
     lambda t: t.replace(
         "| UNIT | is the operation locally correct? |",
         "| UNIT | is the operation locally correct? |\n"
         "| UNIT | is the operation locally correct? |"),
     "saicritic"),
    ("Improve assignment omits canonical PROVENANCE", "tools/saipen.py",
     lambda t: t.replace('proof_levels = _canonical_proof_levels()',
                         'proof_levels = _canonical_proof_levels()[:-1]'),
     "saicritic-assignment"),
    ("Improve assignment emits a sliced decoy", "tools/saipen.py",
     lambda t: t.replace('"proof_levels": proof_levels,',
                         '"proof_levels": proof_levels[:-1],'),
     "saicritic-assignment"),
    ("Improve assignment rebinds canonical proof levels", "tools/saipen.py",
     lambda t: t.replace(
         "proof_levels = _canonical_proof_levels()",
         "proof_levels = _canonical_proof_levels()\n"
         "            proof_levels = proof_levels[:-1]"),
     "saicritic-assignment"),
    ("dead proof assignment launders reachable sliced output", "tools/saipen.py",
     lambda t: t.replace(
         "proof_levels = _canonical_proof_levels()",
         "actual_levels = _canonical_proof_levels()[:-1]\n"
         "            if False:\n"
         "                proof_levels = _canonical_proof_levels()\n"
         "                _emit({\"code\": \"IMPROVE_AUDIT_ASSIGNMENT\", "
         "\"proof_levels\": proof_levels}, as_json)").replace(
             '"proof_levels": proof_levels,',
             '"proof_levels": actual_levels,'),
     "saicritic-assignment"),
    ("INDEX stops routing to SAICRITIC", INDEX,
     lambda t: t.replace("- `SAICRITIC.md`:", "- `SAICRITICX.md`:"),
     "saicritic-reachability"),
    ("manifest stops installing SAICRITIC", "saipen/MANIFEST.json",
     lambda t: t.replace(
         '    {"src": "saipen/SAICRITIC.md", "required": true},\n', ""),
     "saicritic-reachability"),
    # T-607: the SubSaipen write boundary is continuously mechanical -- a sub
    # STATE that names a main-project canonical file outside a boundary
    # comment is a violation.
    ("sub STATE targets a main-project canonical file", SUB,
     lambda t: t.replace("---\n", "---\ntask: T-999\n", 1).replace(
         "saipen_home", "apply_to_main: .saipen/BOARD.md\nsaipen_home", 1),
     "sub-write-boundary"),
    # NITRO: OPS.md is only reachable through INDEX. Drop the row and the doc
    # still ships, still validates its own text, and no cold agent ever finds
    # it -- the RFC routing trap in a new file.
    ("index stops routing to the OPS contract", INDEX,
     lambda t: t.replace("- `OPS.md`:", "- `OPSX.md`:"),
     "ops-owner"),
    ("last_event below the log tail", STATE, sub_line("last_event", "1"),
     "lower than the log"),
    ("next_action picks a ticket that is not the topmost workable", BOARD,
     ("MULTI", [(BOARD, demote_the_pick),
                (STATE, sub_line("next_action", '"PHASE SCOUT T-998"'))]),
     "but the topmost workable ## TODO ticket is"),
    # A C0 byte is invisible in every reader and still changes what the code
    # means. Two `\1` backreferences in this file were literal `\x01` bytes,
    # so both verify_attempts controls substituted a SOH character for the
    # captured ticket line and scored green while testing nothing.
    ("a shipped tool carries an invisible control character",
     "tools/run_scenarios.py",
     lambda t: t.replace("\n# ", "\n# \x01", 1),
     "contains control character U+0001"),
    ("next_action has no prefix", STATE,
     sub_line("next_action", '"finish the thing"'),
     "does not start with"),
    # The category bounds what KIND of stop a WAIT is; nothing bounded what
    # followed it, so `next_action` became a scratchpad and the next agent
    # read the notes as a queue -- live on this repository, where a `user
    # brake` naming a ticket "for a future run" got that ticket scouted
    # instead of the brake honoured.
    ("a WAIT body carries a session report after the brake", STATE,
     sub_line("next_action",
              '"WAIT: user brake -- hold for the user. Wiki package is ready '
              'and T-455 is still open for a future run."'),
     "starts a second sentence"),
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
    ("goal intent, counters absent", STATE,
     force_goal,
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
    # goal resume reset. The harness copies the repo's own live STATE, whose
    # goal_tickets is produced by mechanical DEC lines that the rebuild replays
    # 1:1 -- so an injected value that happens to equal the replayed count
    # would NOT diverge and the case would silently stop being evidence (the
    # NITRO dogfood II lesson: a fixture tuned to a snapshot goes stale). Inject
    # a value far above any plausible replay (29, over the 3/20 caps' budget)
    # so the divergence is guaranteed: the rebuild can never reach 29 because
    # the safety valve would have tripped long before, and a replay that did
    # reach it would itself be a separate corruption.
    ("goal counter STATE cannot survive its own rebuild", STATE,
     lambda s: force_goal(s, "goal_waves: 1\ngoal_tickets: 29"),
     "newest goal marker rebuilds"),
    # Scenario 7 (T-539): a clean HUNT under `execution_intent: converge` is
    # stage F/I of CONVERGE.md and MUST NOT enter ADD -- ADD is invention, the
    # one thing a converge run never does. The live LOG (sealed segments
    # included) already carries `hunt -> clean @HASH` markers, so flipping the
    # state to converge with next_action pointing at ADD must FAIL.
    ("converge clean-HUNT may not name ADD", STATE,
     lambda s: force_converge(s, '"PHASE ADD"'),
     "converge clean-HUNT marker present but next_action names ADD"),
    # T-539 valve-wording half: under converge the safety-valve pause's resume
    # key is bare `cc`, never `saipen goal` -- there `saipen goal` is a NEW
    # objective, a substitution. The goal wording in a converge pause FAILs.
    ("converge safety-valve pause names the goal resume key", STATE,
     lambda s: force_converge(
         s, '"WAIT: safety valve reached (N waves / M tickets) -- '
         "run 'saipen goal' to continue\""),
     "converge safety-valve pause names the goal resume key"),
    # Strip the final newline and the file stops mid-line. Nothing else in this
    # list reads a last byte, which is how the real one survived: every
    # mutation appended below landed INSIDE the last entry instead of after it,
    # and two of these cases quietly stopped being evidence.
    ("BOARD.md ends mid-line", BOARD, lambda t: t.rstrip("\r\n"),
     "end mid-line"),
    # Point a shortcut back at a phase name. The table promises each one lands
    # on a command § 1.10 defines; nothing read that column until v7.148.0,
    # and two rows had already stopped being true.
    ("shortcut routes to a phase, not a command", "saipen/CORE.md",
     replace("| `hh` | `saipen hunt` |", "| `hh` | HUNT |"),
     "do not resolve to a command"),
    # Scenario 30: the old `cc` -> `saipen goal` mapping must fail validation.
    # `cc` is the continue/converge key and `gg` is the sole new-goal key; the
    # canonical table routes `cc` to `saipen continue`, and a regression back
    # to the duplicated-goal mapping is rejected by the route check.
    ("shortcut routes to a valid but wrong command", "saipen/CORE.md",
     replace("| `cc` | `saipen continue` |",
             "| `cc` | `saipen goal` |"),
     "assigned destination changed"),
    ("shortcut rationale restores stale length magic", "saipen/CORE.md",
     replace("**Length has no global meaning.**",
             "**Doubled is safe, tripled reaches a remote**"),
     "shortcut-rationale"),
    # A bare shortcut is a command, never a greeting. The ENTIRE-message rule
    # claimed it could not be mistaken for prose, and a bare `qq` was still
    # answered as a greeting instead of run as `saipen prepare saiwiki` --
    # the property was true and the failure still happened, so the paragraph
    # now names the greeting misreading as the failure and orders execution.
    ("shortcut paragraph loses its never-a-greeting duty", "saipen/CORE.md",
     replace("never a greeting", "rarely ambiguous"),
     "shortcut-rationale"),
    # CLEAN's board scrub pruned `## DONE` with no inbound-reference guard, so
    # the phase that keeps the board honest could orphan a live `needs:` and
    # block a workable ticket. Reproduced on this repository at E-1811.
    ("clean.md's board scrub loses its inbound-needs guard",
     "saipen/phases/clean.md",
     replace("still names in `needs:` MUST NOT be pruned",
             "still names in `needs:` should usually be kept"),
     "clean-scrub-guard"),
    # The `cc` row's Notes promised "trigger goal mode" while § 1.10 forbids
    # bare `saipen goal` from setting the flag at all.
    # Proposal Mode's halt was expressible only as an action the agent was
    # forbidden to perform: step 4 ordered DONE plus a halt, banned `WAIT:`
    # as a § 1.2 violation, and banned proceeding.
    # `agent: none` was ordered by both the phase doc and the shipped
    # template, so every project was born with an identity § 1.4 cannot
    # compare. The second control guards the honesty clause: refusing `none`
    # does not derive a first seat name, and a doc that stops saying so
    # promotes an open question to a settled rule by omission.
    ("1.11 lets a queued command be dropped", "saipen/CORE.md",
     replace("cannot execute now is written down, never dropped",
             "cannot execute now may simply be reported"),
     "command-not-dropped"),
    ("1.10 drops the plan-then-goal pair", "saipen/CORE.md",
     replace("One carve-out, and it is a pair rather than a loosening",
             "No carve-out exists and the bare form is absolute"),
     "plan-goal-pair"),
    ("1.2 stops sending another instance's work to BLOCKED",
     "saipen/CORE.md",
     replace("The same section holds a ticket whose work another",
             "Core may take a ticket whose work another"),
     "permanent-owner-section"),
    ("1.2 stops sending unfinishable tickets to BLOCKED", "saipen/CORE.md",
     replace("That is also where a ticket goes when its completion",
             "Such a ticket stays where it is and when its completion"),
     "permanent-owner-section"),
    ("translate.md stops ordering the digest restamp",
     "saipen/phases/translate.md",
     replace("Something signals it now, and keeping that signal",
             "Nothing signals it and keeping any signal"),
     "translation-digest"),
    # The circuit's whole reason: a stage that hands forward a CLAIM instead
    # of evidence. Observed in a user transcript -- "Production Ready",
    # "проверил: всё работает", then FileNotFoundError on the next command.
    ("the sc circuit names a command nobody defined",
     "extensions/subs/crew.md",
     replace("| 1 | sense | `saipen hunt` |",
             "| 1 | sense | `saipen sniff` |"),
     "circuit-stages"),
    ("crew.md lets a stage hand forward a claim",
     "extensions/subs/crew.md",
     replace("A stage passes the next stage a reproduction or a verdict. "
             "Never a claim.",
             "A stage summarises its result for the next stage."),
     "circuit-handoff"),
    ("CORE.md drops the ahead-stamp repair", "saipen/CORE.md",
     replace("An ahead-stamp is repaired, not waited out",
             "An ahead-stamp clears on its own"),
     "ahead-stamp-repair"),
    ("1.1 drops the gate on new prose", "saipen/CORE.md",
     replace("names the defect class it eliminates",
             "should ideally be useful"),
     "prose-gate"),
    ("build.md stops citing the prose gate", "saipen/phases/build.md",
     replace("names the defect class it eliminates", "should read well"),
     "prose-gate"),
    ("ship.md fuses no-publish with an absent git again",
     "saipen/phases/ship.md",
     replace("It does NOT mean git is", "It also means git is"),
     "no-publish-split"),
    ("ship.md hardcodes `no git` into the skipped-publish line",
     "saipen/phases/ship.md",
     replace("(no-publish: <reason>)", "(no-publish: no git)"),
     "no-publish-split"),
    ("ship.md merges the local and git release halves",
     "saipen/phases/ship.md",
     replace("6b. **GIT.", "6b. **Also local.",),
     "no-publish-split"),
    ("markhunt.md treats no-publish as git-unavailable again",
     "saipen/phases/markhunt.md",
     replace("means git cannot be READ, and nothing else",
             "covers no-publish hosts too"),
     "markhunt-no-git"),
    ("markhunt.md calls a git-less closure satisfied again",
     "saipen/phases/markhunt.md",
     replace("tree_movement=unverified", "tree_movement=fine"),
     "markhunt-no-git"),
    ("a stray file appears at the repository root",
     "SPEC_STRAY.md", write_new("stray root file" + chr(10)),
     "root-file-set"),
    ("markhunt.md stops listing the tickets a pass wrote",
     "saipen/phases/markhunt.md",
     replace("`tickets=` is the pass's own", "`tickets=` is optional and"),
     "markhunt-pass-id"),
    ("prepare.md goes back to one unqualified record",
     "saipen/phases/prepare.md",
     replace("RUN: prepare <producer> -> done", "RUN: prepare -> done"),
     "prepare-record"),
    # Session-level BLOCKED means "no ticket anywhere is workable"; the
    # second half was never checked, so a session halted with a full board
    # looked exactly like a legitimate stop. The red condition spans two
    # files -- STATE.phase: BLOCKED AND a workable ## TODO ticket -- so this
    # is the one two-file case: setting phase alone went vacuous whenever the
    # board's workable tickets dried up (T-532), so the mutation injects a
    # synthetic workable ticket alongside the phase change.
    ("a session blocks while the board still has workable tickets", STATE,
     ("MULTI", [(STATE, sub_line("phase", "BLOCKED")),
                (BOARD, lambda t: t.replace(
                    "\n## TODO\n",
                    "\n## TODO\n- [ ] T-999 [P3] synthetic red-control "
                    "workable ticket\n", 1))]),
     "session-level BLOCKED is reserved for"),
    ("CHANGELOG entries fall out of descending order", "CHANGELOG.md",
     # 7.206.0 was the old anchor; it has been sealed into the archive, so the
     # mutation became a no-op. A mid-file entry is bumped above the head so
     # only the descending-order rung fires, never the head-vs-VERSION one.
     replace("## 7.212.0", "## 7.300.0"),
     "changelog-order"),
    ("clean.md loses the pre-move reference sweep",
     "saipen/phases/clean.md",
     replace("needs a reference sweep first", "is usually fine"),
     "move-reference-sweep"),
    ("clean.md loses the deletion proof gate",
     "saipen/phases/clean.md",
     replace("deleted on proof of recovery", "deleted when obvious"),
     "clean-delete-proof"),
    ("clean.md reads the cap as authority again",
     "saipen/phases/clean.md",
     replace("mass-deletion gate, not a grant of authority",
             "budget of five free deletions"),
     "clean-delete-proof"),
    ("hunt.md regains deletion authority",
     "saipen/phases/hunt.md",
     replace("deletes, moves and renames nothing",
             "may delete obvious junk it finds"),
     "hunt-no-mutation"),
    ("hunt.md reuses a clean result on a dirty tree",
     "saipen/phases/hunt.md",
     replace("`git status --porcelain` prints nothing",
             "the commit hash is unchanged"),
     "hunt-clean-key"),
    ("STATE names a model build instead of a seat", STATE,
     sub_line("agent", "claude-opus"),
     "carries the model token"),
    ("init.md stops deriving the seat from the agent home",
     "saipen/phases/init.md",
     replace("**Where the value comes from is not a choice**",
             "Pick a name that suits you"),
     "bootstrap-identity"),
    ("init.md goes back to ordering agent: none",
     "saipen/phases/init.md",
     replace("**never `none`**", "`none` is fine to start with"),
     "bootstrap-identity"),
    # Must be a value the live checks ACCEPT -- `none` is a placeholder now,
    # so mutating the template to it leaves the template requirement
    # satisfied and the control proves nothing. A real seat name is the
    # failure: it copies straight into a first checkpoint and passes.
    ("the shipped template ships a passable agent value",
     "extensions/templates/STATE.md",
     sub_line("agent", "opencode"),
     "bootstrap-identity"),
    ("plan.md lets the halt be a PHASE nobody executes",
     "saipen/phases/plan.md",
     replace("There is no parked `PHASE`",
             "A `PHASE` may be recorded without being executed"),
     "proposal-halt"),
    ("plan.md drops the halt's category", "saipen/phases/plan.md",
     replace("category is `user brake`", "category is up to you"),
     "proposal-halt"),
    # T-537 gave `cc` and `saipen goal` separate destinations, and the pair of
    # controls that used to guard the old shared route quoted row text the
    # split rewrote -- so both mutations became no-ops and the harness scored
    # them SKIP. Repointed at the text that now carries the requirement, which
    # is the third occurrence of the split-anchor class T-496 and T-532 name.
    #
    # The old cc-row control is replaced by the requirement the split exists to
    # protect: `cc` routes to `saipen continue`, and a table that maps it back
    # to `saipen goal` is the exact regression the separation forbids. Keyed on
    # the route cell, so it fires on the mapping itself and not on prose.
    ("the cc row is mapped back to `saipen goal`",
     "saipen/CORE.md",
     replace("| `cc` | `saipen continue` |", "| `cc` | `saipen goal` |"),
     "shortcut-routes"),
    # `gg` is now the only row routing to `saipen goal`, and the Notes
    # requirement is derived from the route rather than the key -- so this
    # control strips the "pivot needs text" clause the check reads, leaving a
    # Notes column that promises a bare pivot the destination forbids.
    ("the gg row promises a bare Goal Mode pivot again",
     "saipen/CORE.md",
     replace("NEW GOAL ONLY: the pivot needs text, and `gg <objective>` is "
             "what sets a new one.",
             "NEW GOAL ONLY: Goal Mode pivot and re-authorization."),
     "shortcut-notes"),
    ("bare cc starts convergence from normal intent",
     "saipen/CORE.md",
     replace("enters convergence from `normal`",
             "continues ordinary work from `normal`"),
     "shortcut-semantics"),
    ("cc resumes persisted goal intent",
     "saipen/CORE.md",
     replace("resumes `execution_intent: goal`",
             "replaces `execution_intent: goal`"),
     "shortcut-semantics"),
    ("cc never asks for objective text",
     "saipen/CORE.md",
     replace("never asks for an objective", "may ask for an objective"),
     "shortcut-semantics"),
    ("cc with arguments is rejected rather than becoming a goal",
     "saipen/CORE.md",
     replace("`cc <args>` is not a goal", "`cc <args>` starts a goal"),
     "shortcut-semantics"),
    ("gg with objective creates a new goal",
     "saipen/CORE.md",
     replace("NEW GOAL ONLY", "GOAL CONTINUATION"),
     "shortcut-semantics"),
    ("bare gg is never a continuation alias",
     "saipen/CORE.md",
     lambda text: text.replace("never a continuation alias",
                               "is a continuation alias"),
     "shortcut-semantics"),
    # The callout check counted keys, tokens, order and the link and never
    # read what the sentence CLAIMS, so a document could tell the reader `cc`
    # is the Goal Mode key while § 1.10 routed it to `saipen continue` -- and
    # three Core-owned files shipped exactly that for a release.
    # The convergence order is the whole contract, and the way it breaks is not
    # a deleted file -- it is two stages swapping, which reads fine and puts the
    # producer packages before the cleanup that invalidates them. Swap K past M
    # so every stage is still present and only the ORDER is wrong.
    ("CONVERGE.md prepares its factories before the closure sweep",
     "saipen/CONVERGE.md",
     replace("**K. FRESH EE.**", "**M. FINAL FRESHNESS CHECK.**"),
     "converge-contract"),
    ("CONVERGE.md loses the post-K ordering rule",
     "saipen/CONVERGE.md",
     replace("Nothing that mutates main source may run after K.",
             "Main source may be mutated whenever it is convenient."),
     "converge-contract"),
    ("CONVERGE keeps EE before QQ",
     "saipen/CONVERGE.md",
     replace("**K. FRESH EE.**", "**L. FRESH QQ.**"),
     "converge-contract"),
    ("CONVERGE blocks factories while TODO remains",
     "saipen/CONVERGE.md",
     replace("no workable `## TODO` ticket", "TODO may remain"),
     "closure evidence drift"),
    ("CONVERGE blocks factories after failing tests",
     "saipen/CONVERGE.md",
     replace("canonical tests PASS against the tree",
             "canonical tests were attempted against the tree"),
     "closure evidence drift"),
    ("CONVERGE blocks factories on scout or fixer findings",
     "saipen/CONVERGE.md",
     replace("no fresh critical scout or fixer OUTBOX",
             "critical scout or fixer OUTBOX may remain"),
     "closure evidence drift"),
    ("CLEAN forces tests and final HUNT before factories",
     "saipen/CONVERGE.md",
     replace("CLEAN completed, or proved nothing safe remained",
             "CLEAN was considered"),
     "closure evidence drift"),
    ("final HUNT findings return to Core work",
     "saipen/CONVERGE.md",
     replace("final forced HUNT after CLEAN came back clean",
             "final HUNT was started"),
     "closure evidence drift"),
    ("old hunt marker cannot satisfy forced HUNT",
     "saipen/CONVERGE.md",
     replace("existing hunt -> clean marker cannot satisfy forced HUNT",
             "existing hunt marker may satisfy forced HUNT"),
     "closure evidence drift"),
    ("a Core-owned callout calls `cc` the Goal Mode key",
     "guides/GUIDE_EN.md",
     replace("`cc` continues the project context to convergence (resuming a "
             "running goal if one is set)",
             "`cc` keeps active Goal Mode moving"),
     "shortcut-callouts"),
    # § 1.10 ordered `saipen status` to report the last validator result from
    # LOG.md before anything gave that record a shape. Break the fixed form
    # and the report has nothing to read -- the same silence the duty had for
    # its whole life, now visible.
    # Anchored at the taxonomy, not on the bare literal: `replace()` takes the
    # FIRST occurrence, and the first one in this LOG is a line QUOTING the
    # form while explaining it. That mutation edited prose and left the real
    # record standing, so the case reported green while proving nothing --
    # the exact "expectation is not evidence" trap row 137 exists for.
    # The check reads the ACTIVE log only -- status wants the last run, not one
    # sealed into cold storage -- so breaking every record here is what fires
    # it. A first attempt aimed at the sealed segment and proved nothing: the
    # active log still carried its own record, and a global check needs every
    # copy broken. Regex-anchored on the taxonomy so a cap crossing cannot
    # quietly carry the anchor away, which is how two cases became SKIPs.
    ("the conformance record loses its fixed form", LOG,
     lambda t: re.sub(r"(RUN: )validate\.py -> (PASS|FAIL)",
                      r"\1validate.py \2", t),
     "no-conformance-record"),
    # NOT here: the DONE-wait deadlock under `goal_mode: true`. It needs an
    # empty `## TODO` *and* a bogus WAIT, and a case mutates exactly one file,
    # so every single-file attempt proves nothing -- STATE alone leaves the
    # board full, BOARD alone leaves next_action legal. Tried, went not-red,
    # removed rather than left standing. T-457 owns the compound-fixture route.
    # `saipen hunt` is recognised from anywhere while HUNT sat outside § 1.6's
    # from-any-phase set, so the DFA's only route in was DONE -> HUNT and the
    # command produced a transition the validator rejects. Three surfaces, one
    # defect: the set, § 2.1's halt phrasing, and hunt.md's hash skip.
    ("HUNT drops out of the from-any-phase set", "saipen/CORE.md",
     replace("`PLAN`, `HUNT`.", "`PLAN`."),
     "any-from"),
    ("§ 2.1 reads the halt as a precondition on the command too",
     "saipen/MAINTENANCE.md",
     replace("governs the AUTONOMOUS transition only",
             "applies to every entry into this phase"),
     "hunt-entry"),
    ("hunt.md lets the hash skip swallow an explicit sweep",
     "saipen/phases/hunt.md",
     replace("does not apply -- run the full sweep",
             "may still apply if the tree is unchanged"),
     "hunt-entry"),
    # The first-publish gate sat after the pushes it authorizes, with its own
    # WAIT text claiming "before I push". Moving it back below the push is the
    # exact regression this control catches.
    ("ship.md puts the first-publish gate back after the push",
     "saipen/phases/ship.md",
     replace("Classify the remote BEFORE any external write",
             "Classify the remote at some point"),
     "first-publish-order"),
    # T-467: step 7 makes the tag push a separate command from the branch
    # push, so a rejected branch push can still be followed by a successful
    # tag push -- publishing a tag on a commit that is on no remote branch
    # (E-1787, E-1882). Pushing the tag before gating on the branch landing
    # is the exact regression this control catches.
    ("ship.md pushes the release tag before the branch has landed",
     "saipen/phases/ship.md",
     replace("ONLY AFTER step 6b's branch push has LANDED",
             "Once the release is ready, regardless of the branch push"),
     "tag-after-branch"),
    # T-466: the ticket that passes REVIEW stays in `## DOING` through SHIP
    # -- the push has not happened. Closing it at REVIEW made § 1.2's own
    # `PHASE SHIP T-###` name a `## DONE` ticket and fail the pick check
    # twice over (E-1879). The rule lives in review.md once; ship.md cites
    # it. Softening either half silently reopens the defect, so both halves
    # get a control that goes red on its own anchor.
    ("review.md lets REVIEW close the passed ticket before SHIP",
     "saipen/phases/review.md",
     replace("stays in `## DOING` through SHIP -- do NOT close it",
             "may be closed here, the review is done"),
     "ticket-stays-doing"),
    ("ship.md stops citing the ticket's `## DOING`-through-SHIP rule",
     "saipen/phases/ship.md",
     replace("The shipped ticket was still in `## DOING` when this phase "
             "began",
             "The shipped ticket may have been closed at REVIEW"),
     "ticket-stays-doing"),
    # VERIFY's 3/2 cap was counted from memory while REVIEW's became a field
    # one document over. Both directions: over the cap with no blocker, and a
    # value the field cannot hold. The replacement MUST carry the \1
    # backreference -- without it re.sub swaps the whole ticket line for the
    # bare field fragment, the board parser rejects the shape, and the
    # validator FAILs for a reason that has nothing to do with the cap. Red
    # for the wrong reason is not evidence, and it reads exactly like a
    # passing control: E-1911 caught this class once, and the repair for it
    # reintroduced it by losing the group.
    ("a ticket runs past verify.md's fix-cycle cap with no blocker", BOARD,
      lambda t: re.sub(r"^(?!.*\| blocker:)(- \[ \] T-\d+ \[P\d\] .*)$",
                      r"\1 | verify_attempts: 9",
                      t, count=1, flags=re.MULTILINE),
     "against phases/verify.md's cap"),
    ("verify_attempts holds something that is not a number", BOARD,
      lambda t: re.sub(r"^(?!.*\| blocker:)(- \[ \] T-\d+ \[P\d\] .*)$",
                      r"\1 | verify_attempts: many",
                      t, count=1, flags=re.MULTILINE),
     "is not a number"),
    # One control per borrowed invariant. Each softens the MUST the way a
    # later editor plausibly would, rather than deleting the sentence.
    ("verify.md loses the cheapest-first ordering claim",
     "saipen/phases/verify.md",
     replace("That order is cheapest-first", "That order is a suggestion"),
     "borrowed-invariants"),
    ("verify.md lets a later green restore a failed PASS claim",
     "saipen/phases/verify.md",
     replace("ends the PASS claim for this pass", "is worth noting"),
     "borrowed-invariants"),
    ("verify.md goes back to re-deriving the project's commands",
     "saipen/phases/verify.md",
     replace("Read the project's canonical commands from `KNOWLEDGE/`",
             "Find the project's commands however you like"),
     "borrowed-invariants"),
    ("scout.md stops writing the commands down",
     "saipen/phases/scout.md",
     replace("cited afterwards rather than", "noted mentally rather than"),
     "borrowed-invariants"),
    ("BOOT implies the pre-computed pick stands alone", "saipen/BOOT.md",
     replace("Immediate means without asking, never without looking",
             "Immediate means immediate"),
     "borrowed-invariants"),
    ("review.md goes back to trusting VERIFY's claim",
     "saipen/phases/review.md",
     replace("do not read VERIFY's claim of", "you may reuse"),
     "review-reruns-verify"),
    # § 1.11's priority list had no entry for the user naming a command, so
    # BOOT's "execute `next_action` immediately" and § 1.10's "a shortcut is a
    # command, never a greeting" were two live MUSTs with no precedence
    # between them -- and at a cold start BOOT is the file read first. The
    # same `qq` was lost to the same stale pick twice (E-1913). Either half
    # softening on its own restores the tie, so both are controlled.
    ("§ 1.11 weighs the user's command instead of obeying it",
     "saipen/CORE.md",
     replace("It supersedes `next_action`",
             "It is weighed against `next_action`"),
     "command-outranks-pick"),
    ("BOOT step 7 goes back to unconditional", "saipen/BOOT.md",
     replace("the user's own message outranks the file",
             "run whatever the state recorded"),
     "command-outranks-pick"),
    ("BOOT step 7 drops the memory ban for shortcut tables", "saipen/BOOT.md",
     # The period-anchored old string did not match the current em-dash text,
     # so this went a no-op (T-532). The check reads the phrase without the
     # period, so the mutation drops exactly that.
     replace("Memory is never a source for it",
             "Use memory if you are confident"),
     "shortcut-memory-ban"),
    ("BOOT step 7 drops the duplication ban for shortcut tables", "saipen/BOOT.md",
     # Must mutate the string the CHECK reads. It mutated "Do not copy the
     # table here" while validate.py tests for "a second copy drifts", so
     # the case could not go red at all -- shipped that way in 50d5fed.
     replace("a second copy drifts",
             "a second copy is fine"),
     "shortcut-memory-ban"),
    ("RFC § 1.10 softens the recall penalty", "saipen/CORE.md",
     replace("answering a row from recall is the same failure as inventing a command",
             "answering a row from recall is discouraged"),
     "shortcut-memory-ban"),
    # § 2.1's ZERO-PROMPT MUST named one exception while § 1.3 banned ADD
    # under read-only, so the rule ordered a phase the mode forbids and both
    # rules looked followed on their own.
    ("§ 2.1 drops the read-only carve-out from ZERO-PROMPT", "saipen/MAINTENANCE.md",
     replace("MUST NOT enter `ADD` at all", "SHOULD prefer to skip `ADD`"),
     "zero-prompt-exceptions"),
    # § 1.2's legacy-upgrade sentence named `v2` long after the schema reached
    # 3, so the one instruction for escaping legacy state ordered a value the
    # validator WARNs as legacy. A version number reads as fact, which is why
    # nothing saw it; the same rot had the shipped subSaipen TEMPLATE born at
    # schema 1, so every spawn produced a legacy state.
    ("§ 1.2 re-hardcodes a superseded schema version", "saipen/CORE.md",
     replace("MUST upgrade **to the current schema version**",
             "MUST upgrade to `schema_version: 2`"),
     "stale-schema-version"),
    ("the shipped subSaipen TEMPLATE is born legacy",
     "extensions/subs/TEMPLATE/STATE.md",
     sub_line("schema_version", "1"),
     "stale-schema-version"),
    # RFC § 1.2 pairs `PHASE` with a ticket ref for exactly five phases and
    # forbids it everywhere else. Nothing witnessed either direction, and the
    # constitution's own § 2.2 example wrote the forbidden one in prose.
    ("next_action bolts a ticket ref onto a phase that takes none", STATE,
     sub_line("next_action", '"PHASE PLAN T-435"'),
     "not one of the five ticket-bearing phases"),
    ("next_action enters a ticket-bearing phase with no ticket", STATE,
     sub_line("next_action", '"PHASE BUILD"'),
     "enters ticket-bearing phase"),
    ("a shipped doc spells out the forbidden PHASE form", "saipen/MAINTENANCE.md",
     replace("Translate it: `PHASE PLAN` when",
             "Translate it: `PHASE PLAN T-###` when"),
     "phase-ticket-ref"),
    ("§ 1.2 loses a phase from the ticket-bearing five", "saipen/CORE.md",
     replace("`SCOUT`, `BUILD`, `VERIFY`, `REVIEW`, `SHIP` -- and omitted",
             "`SCOUT`, `BUILD`, `VERIFY`, `REVIEW` -- and omitted"),
     "TICKET_BEARING_PHASES"),
    # § 1.10's stop paragraph cited § 2.4 Entry while stating its opposite:
    # an unconditional counter reset on bare `saipen goal`. That is a fresh
    # 3-wave/20-ticket budget for anyone who types the key out of habit.
    ("stop paragraph re-asserts an unconditional goal-counter reset",
     "saipen/CORE.md",
     replace("only when they are at or over the caps",
             "every time, whatever the counters read"),
     "goal-counter-reset"),
    ("translation collect shortcut silently prepares instead",
     "saipen/CORE.md",
     replace("| `eee` | `saipen collect saitranslate` then `saipen ship` |",
             "| `eee` | `saipen prepare saitranslate` then `saipen ship` |"),
     "assigned destination changed"),
    ("ready package loses its source freshness field",
     "saipen/phases/prepare.md",
     replace("`status`, `producer`, `source_head`, `source_tree_fingerprint`, "
             "`role_revision`, `coverage`",
             "`status`, `producer`, `source_head`, `role_revision`, `coverage`"),
     "PREPARE fields"),
    ("non-ready collect loses its no-write guarantee", "saipen/CORE.md",
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
    ("phase-switching command loses its checkpoint duty", "saipen/CORE.md",
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
    ("Golden Default token drifts", "saipen/UI.md",
     replace("--background:#1A1810", "--background:#1A1811"), "ui-palette"),
    ("Golden Default gains an extra token", "saipen/UI.md",
     replace("--link:#F0D060;", "--link:#F0D060;\n  --rogue:#FFFFFF;"),
     "ui-palette"),
    ("Golden Default gains a later root override", "saipen/UI.md",
     replace("}\n\n* {", "}\n\n:root {\n  --background:#FFFFFF;\n}\n\n* {"),
     "ui-palette"),
    ("Golden Default gains a non-hex override", "saipen/UI.md",
     replace("* {", ".override { --background:rgb(255,255,255); }\n\n* {"),
     "ui-palette"),
    ("Golden Default stops being default", "saipen/UI.md",
     replace("**Golden Default is the default palette.**",
             "**Golden Default is an optional palette.**"),
     "lost the Golden Default default mandate"),
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
     # Old anchor was pre-shrink text. The T-404 straddler check only counts
     # `saipen/`-prefixed refs, so the mutation must add a prefixed STYLE.md
     # to BOTH the on-demand bullet and the before-output bullet -- a bare
     # mention in one is deliberately ignored (T-532).
     lambda t: (t.replace("**STYLE.md is NOT on the rule-question list.**",
                          "**`saipen/STYLE.md` is on the rule-question list.**")
                .replace("Step 1 already read STYLE.md — the file in the "
                         "same folder as this BOOT.md",
                         "Step 1 already read `saipen/STYLE.md` — the file "
                         "in the same folder as this BOOT.md")),
     "under on-demand 'rule questions' while ordering it"),
    ("BOOT loses a T-404 disjointness anchor bullet",
     "saipen/BOOT.md",
     # Old anchor was pre-shrink text. The check parses a bullet that starts
     # with "Rule questions"; renaming the bullet to "Questions" makes the
     # parser lose it entirely, which is the exact failure the check names.
     replace("Rule questions → `INDEX.md` first.",
             "Questions → `INDEX.md` first."),
     "lost one of the two T-404 anchor bullets"),
    ("BOOT moves the STYLE.md read out of the numbered fast path",
     "saipen/BOOT.md",
     # Old anchor used ASCII `--`; the current BOOT.md writes an em-dash, so
     # the mutation was a no-op (T-532). Re-pinned to the live em-dash text.
     replace("1. **Read `STYLE.md` — the file in the same folder as this `BOOT.md` —",
             "1. **Read the voice notes — the file in the same folder as this `BOOT.md` —"),
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
     # Old anchor back-ticked STYLE.md (`STYLE.md`'s); the current BOOT.md
     # writes it bare, so the mutation was a no-op (T-532).
     replace("STYLE.md's `reply_language:` (step 1",
             "STYLE.md's language rule (step 1"),
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
    ("RFC transition table loses an edge", "saipen/CORE.md",
     replace("SCOUT     -> BUILD | BLOCKED", "SCOUT     -> BLOCKED"),
     "transition-table"),
    ("phase doc exit names an edge the DFA rejects", "saipen/phases/scout.md",
     replace("After SCOUT: STATE -> BUILD.", "After SCOUT: STATE -> SHIP."),
     "phase-exit"),

    # T-430: a LOG line records what happened. One word turns E-1769 from an
    # event into an intention, and every reader after it -- § 1.5's Recovery
    # rebuild included -- would still count it as evidence the act occurred.
    # The anchor is safe to name: append-only makes that line immutable.
    # Anchored on the taxonomy rather than on one line's words: the previous
    # anchor named a specific event, and that event was sealed into a segment
    # at the next cap crossing, which turned this case into a silent SKIP.
    # The active log always carries at least the checkpoint that just ran.
    ("a LOG entry states its event in the future tense", ".saipen/LOG.md",
     lambda t: re.sub(r"\] RUN: (?!will )", "] RUN: will ", t, count=1),
     "future tense"),

    # T-432: the newest LOG entry restamped just past the clock slack. The
    # old 3h bound made this control impossible to write honestly -- a stamp
    # 3h out is absurd on sight, while 6 minutes out is exactly what an agent
    # that estimated instead of reading produces.
    ("a LOG entry is stamped ahead of the real clock", ".saipen/LOG.md",
     stamp_log_ahead, "ahead of real UTC"),

    # T-431: two ways a completion claim outran its evidence, one control
    # each. Both mutations leave the CLAIM intact and remove only what backs
    # it -- which is the state both files were shipped in.
    ("a ## DONE ticket carries no verify evidence", ".saipen/BOARD.md",
     strip_done_verify, "no | verify: evidence"),
    ("a CONFORMANCE row cites a ticket still open on the board",
     "saipen/CONFORMANCE.md", cite_open_ticket, "cites unfinished work"),

    (".saipen/ carries a copy of the protocol", ".saipen/RFC.md",
     CREATE, "§ 1.7"),

    # saiui charter integrity (T-510). Each mutation removes one required
    # element; the validator must catch it.
    ("saiui charter drops canonical UI.md reference",
     "extensions/subs/saiui.md",
     # The charter references saipen/UI.md in three places; the old mutation
     # removed one and the validator's substring check was satisfied by the
     # survivors (T-532). Drop every occurrence.
     lambda t: t.replace("saipen/UI.md", "the project's own visual spec"),
     "lost canonical saipen/UI.md"),
    ("saiui charter declares a second palette",
     "extensions/subs/saiui.md",
     replace("There is no second palette.",
             "An alternative palette is available for dark-mode projects."),
     "declares a second palette"),
    ("saiui charter drops Golden Default mandate", "extensions/subs/saiui.md",
     replace("Golden Default is the mandatory palette.",
             "A default palette is recommended."),
     "lost the Golden Default mandate"),
    ("saiui charter softens main-tree write ban",
     "extensions/subs/saiui.md",
     replace("never write to the main project tree",
             "write to the main project tree only for urgent fixes"),
     "main-tree write ban"),
    ("saiui charter removes fixer pen requirement",
     "extensions/subs/saiui.md",
     # `kitchen/pen/` also appears in the charter's table of contents row, so
     # removing the requirement line alone left the substring check satisfied
     # (T-532). Drop every occurrence.
      lambda t: t.replace("kitchen/pen/", "kitchen/direct/"),
      "fixer pen or OUTBOX"),
    # T-549. Every earlier RFC-trap pattern required the literal `RFC.md`,
    # which is how SKILL.md kept routing readers to bare "RFC" through a
    # release that the check called clean. The mutation uses the exact stale
    # sentence that shipped, so the control fails on the real defect rather
    # than on a synthetic one.
    ("skill loader points a rule question at RFC", "saipen/SKILL.md",
     replace("3. **Rule question? Route through `INDEX.md`**",
             "3. It points into RFC only when a rule question comes up. "
             "Route through `INDEX.md`**"),
     "RFC-stub-trap"),
    # T-569. Both halves of the staging order, separately, because they fail
    # differently: losing the ORDER reinstates the paradox (a gate that cannot
    # be satisfied by any documented sequence), while losing the explicit-path
    # rule keeps the order and makes step 5's "staged set equals reviewed
    # scope" proof describe whatever the tree happened to carry.
    # The pre-T-569 shape: the binding gate named in the LOCAL half, above the
    # staging it cannot see. The check reads positions, so the mutation has to
    # move text rather than renumber a label.
    ("ship runs its binding gate before staging", "saipen/phases/ship.md",
     replace("6a. **LOCAL. Touches no repository and no remote.**",
             "6a. **LOCAL. Touches no repository and no remote.** "
             "Run `tools/validate.py --gate ship` NOW."),
     "ship-stage-before-gate"),
    ("ship permits a blind add", "saipen/phases/ship.md",
     replace("**`git add .` and `git add -A` are\n      forbidden here**",
             "`git add .` is fine here"),
     "must forbid blind `git add .`"),
    # Gated at the consumer (T-568): a malformed package is REFUSED where it
    # would be consumed, and merely reported everywhere else. Run at the
    # default gate this control would still find its substring -- on a WARN
    # line -- and go on calling itself evidence of a refusal it no longer
    # measured.
    ("nonempty OUTBOX that parses as zero entries fails",
     ".saipen/extensions/subs/saihunt/kitchen/OUTBOX.md",
     lambda t: t.rstrip() + "\n\nmalformed package without an entry\n",
     "parses as zero OUTBOX entries", "collect:saihunt"),
    # T-541: the machine-readable metadata block is the tool's only way to
    # read a charter's role_kind/collect_policy/role_revision. Drop the yaml
    # language tag so the block stops being machine-readable, and the
    # charter-metadata check must fire.
    ("a sai*.md charter stops being machine-readable",
     "extensions/subs/saitest.md",
      replace("```yaml", "```text"),
      "charter-metadata"),
    ("specialized producer loses canonical OUTBOX citation",
     "extensions/subs/saitranslate.md",
     replace("PROTOCOL.md § 2 complete package",
             "PROTOCOL.md § 20 complete package"),
     "output_contract must cite PROTOCOL.md"),
    ("specialized producer restores a drifting local OUTBOX field list",
     "extensions/subs/saiui.md",
     replace("the sole owner, and its current § 2 plus § 9 contract binds every entry.",
             "Required fields:\n\n- `status`\n- `producer`\n- `source_head`"),
     "restates moving OUTBOX required fields"),
    ("a charter cannot use an arbitrary manual role revision",
     "extensions/subs/saiwiki.md",
     replace("role_revision: \"sha256:54a42475a124ab0f27e83d600a284a9cc54d966"
             "8029c4828cfc48512b031df13\"",
             "role_revision: \"rev1\""),
     "effective charter digest"),
    ("every collectable charter binds role revision",
     "extensions/subs/saihunt.md",
     replace("freshness_inputs: [\"source_head\", \"source_tree_fingerprint\", \"role_revision\"]",
             "freshness_inputs: [\"source_head\", \"source_tree_fingerprint\"]"),
     "freshness_inputs"),
    ("producer packages can never become auto-collected",
     "extensions/subs/saiwiki.md",
     replace("collect_policy: explicit", "collect_policy: automatic"),
     "role_kind PRODUCER requires collect_policy"),
    ("scout output cannot bypass Core review",
     "extensions/subs/saihunt.md",
     replace("collect_policy: core-review", "collect_policy: automatic"),
     "role_kind SCOUT requires collect_policy"),
    ("collection flow must enforce charter collect_policy",
     "extensions/subs/PROTOCOL.md",
     replace("`collect_policy` is executable routing, not a label",
             "`collect_policy` is descriptive metadata"),
     "collect_policy` is executable routing"),
    ("fingerprint framing cannot lose its path length",
     "extensions/subs/PROTOCOL.md",
     replace("path_length[uint64be]", "path"),
     "uint64be"),
    ("fingerprint input errors cannot be skipped",
     "extensions/subs/PROTOCOL.md",
     replace("`except OSError: continue` escape hatch.",
             "best-effort unreadable inputs."),
     "except OSError: continue"),
    ("consumer cannot refresh stale package evidence",
     "saipen/CORE.md",
     replace("MUST NOT edit, revalidate, refresh",
             "may edit, revalidate, or refresh"),
     "MUST NOT edit, revalidate, refresh"),
    ("forced-fresh prepare cannot reuse ready output by default",
     "saipen/phases/prepare.md",
     replace("deterministic cache contract", "available cache"),
     "deterministic cache contract"),
    ("elapsed time cannot authorize SubSaipen deletion",
     "extensions/subs/PROTOCOL.md",
     replace("Age MAY emit a warning.", "Age makes the instance stale."),
     "Age MAY emit a warning"),
    ("repeated collect cannot make a package stale",
     "extensions/subs/PROTOCOL.md",
     replace("Repeated collects MAY leave reviewed",
             "Repeated collects make reviewed"),
     "Repeated collects MAY leave reviewed"),
    ("sub clean refuses unpreserved recovery evidence",
     "extensions/subs/PROTOCOL.md",
     replace("unpreserved recovery evidence", "old recovery evidence"),
     "unpreserved recovery evidence"),
    ("ccc must prepare against the shipped HEAD",
     "saipen/CORE.md",
     replace("against the shipped HEAD", "against the current tree"),
     "against the shipped HEAD"),
    ("ccc persists its ship-first routing target",
     "saipen/CORE.md",
     replace("`saipen continue` with `converge_target: ship`, then `saipen ship`, then stages J-M",
             "`saipen continue` then `saipen ship` then refresh EE + QQ"),
     "assigned destination changed"),
    ("HUNT helpers remain ephemeral rather than SubSaipen",
     "saipen/phases/hunt.md",
     replace("EPHEMERAL WORKERS, not SubSaipen instances",
             "SubSaipen workers"),
     "EPHEMERAL WORKERS, not SubSaipen instances"),
    ("ephemeral workers cannot gain persistent lifecycle state",
     "extensions/subs/PROTOCOL.md",
     replace("never MANIFEST, STATE, BOARD, LOG, kitchen, charter adoption, or lifecycle",
             "temporary MANIFEST and lifecycle records allowed"),
     "never MANIFEST, STATE, BOARD, LOG, kitchen, charter adoption, or lifecycle"),
    ("a local PROTOCOL section is checked as local, not RFC",
     "extensions/subs/PROTOCOL.md",
     replace("### 3.1 Built-in role charters",
             "### 3.2 Built-in role charters"),
     "### 3.1 Built-in role charters"),
    # The barrier only speaks while T-549 is unresolved, and T-549 closed in
    # v7.215.0 -- so stripping T-551's `needs:` alone can no longer go red, and
    # the control silently stopped being evidence. It is not obsolete, it is
    # CONDITIONAL: reopening T-549 must still make T-551 unworkable. The
    # mutation therefore reconstructs both halves of the condition, which is
    # what the check has always been about.
    ("T-551 cannot bypass unresolved T-549", ".saipen/BOARD.md",
     lambda t: t.replace(" | needs: T-549 | verify:", " | verify:", 1)
                .replace("- [x] T-549 [P1]", "- [ ] T-549 [P1]", 1),
     "hardening wave barrier missing"),
    ("PROTOCOL.md drops UI- prefix from ticket table",
     "extensions/subs/PROTOCOL.md",
     replace("| `UI-` | saiui (fixer, § 9) |", ""),
     "lacks explicit UI- prefix"),
    ("PROTOCOL.md drops sai*.md from bootstrap copy list",
     "extensions/subs/PROTOCOL.md",
     # `sai*.md` appears in three rows (spawn + sync); the old mutation
     # removed one and the survivors satisfied the substring check (T-532).
     lambda t: t.replace("sai*.md", "standard files"),
     "sai*.md built-in charters"),
    ("SAIUI mission claims SAISENT was audited from this repo",
     ".saipen/kitchen/SAIUI_SAISENT_MISSION.md",
     replace("hypothesis about the current SAISENT UI",
             "confirmed finding -- SAISENT was audited and is non-compliant"),
     "claims the target was audited"),
    ("saiui built-in role charter deleted from shipped library",
     "extensions/subs/saiui.md", DELETE,
     "saiui built-in role charter"),
    ("PROTOCOL.md drops charter-loading from bare-subname adoption",
     "extensions/subs/PROTOCOL.md",
     replace("load it after PROTOCOL.md and before anything else",
             "proceed with generic adoption"),
     "charter-loading language"),
    ("PROTOCOL.md sync softens live-folder guard",
     "extensions/subs/PROTOCOL.md",
     # The validator's regex accepts either "never touch ... <name>" or "never
     # looks inside ... <name>"; the old mutation hit an unrelated read-only
     # sentence and the sync row's second guard phrase survived (T-532). The
     # sync row carries both phrases, so both must go.
     lambda t: t.replace("sync MUST NOT touch any", "sync MAY touch any")
                .replace("it never looks inside a `<name>/` folder",
                         "it may look inside any `<name>/` folder"),
     "live-folder guard"),
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
    if isinstance(mutation, tuple) and mutation and mutation[0] == "MULTI":
        # A case whose red condition spans two files (e.g. the session-level
        # BLOCKED check, which needs STATE.phase AND a workable board ticket).
        # Every file listed must be present; the case applies if any changed.
        changed = False
        for r, fn in mutation[1]:
            fp = root / r
            if not fp.is_file():
                continue
            text = fp.read_text(encoding="utf-8-sig")
            mutated = fn(text)
            if mutated != text:
                fp.write_text(mutated, encoding="utf-8", newline="\n")
                changed = True
        return changed
    if not p.exists():
        return False
    text = p.read_text(encoding="utf-8-sig")
    mutated = mutation(text)
    if mutated == text:
        return False
    p.write_text(mutated, encoding="utf-8", newline="\n")
    return True


def validator_output(root: Path, gate: str | None = None) -> str:
    """Only the FAIL/WARN lines. Searching the whole output matched PASS text:
    "at most one", "cyclic" and "dangling needs" all appear in the lines that
    say those very checks PASSED, so five cases scored as proving nothing when
    the harness was the thing at fault."""
    r = subprocess.run([sys.executable, str(root / "tools" / "validate.py"),
                        *(["--gate", gate] if gate else [])],
                       cwd=root, capture_output=True, text=True,
                       errors="replace")
    keep = [ln for ln in (r.stdout + r.stderr).splitlines()
            if ln.startswith(("FAIL", "WARN", "Traceback")) or "Error" in ln]
    return "\n".join(keep)


def case_parts(case):
    """Unpack a CASES entry, which is 4 items or 5.

    The optional 5th is the validator GATE the case must run at. T-568 made
    producer-package severity a property of the gate, so a producer control
    left on the default gate would see its FAIL demoted to a WARN -- and this
    harness deliberately keeps WARN lines, so such a case would go on
    reporting itself as evidence while proving only that the defect is
    NOTICED, never that it is refused. A control has to run where its finding
    is hard.
    """
    label, rel, mutation, expected = case[:4]
    return label, rel, mutation, expected, (case[4] if len(case) > 4 else None)


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
    freshen_synthetic_outboxes(pristine)
    synthetic_outboxes = list(
        pristine.glob(".saipen/extensions/subs/*/kitchen/OUTBOX.md"))
    synthetic_translate = (pristine / ".saipen" / "saitranslate"
                           / "kitchen" / "OUTBOX.md")
    if synthetic_translate.is_file():
        synthetic_outboxes.append(synthetic_translate)
    for outbox in synthetic_outboxes:
        text = outbox.read_text(encoding="utf-8-sig")
        text = text.replace("**status:** ready", "**status:** stale")
        text = re.sub(r"(?m)^status:\s*ready\s*$", "status: stale", text)
        outbox.write_text(text, encoding="utf-8", newline="\n")

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

    # A producer-package case that names no gate is a case running where its
    # finding is only a WARN, and this harness keeps WARN lines -- so it would
    # pass while measuring nothing. Structural, because the weakening is
    # invisible in the result: the count stays 218 either way.
    ungated = [parts[0] for parts in map(case_parts, CASES)
               if isinstance(parts[1], str) and parts[1].endswith("OUTBOX.md")
               and parts[4] is None]
    if ungated:
        for label in ungated:
            print(f"FAIL: {label!r} mutates a producer OUTBOX but names no "
                  f"gate -- producer findings are WARNs outside "
                  f"`--gate collect:<producer>`, so this case would pass on a "
                  f"warning and prove no refusal (T-568)")
        shutil.rmtree(tmp, ignore_errors=True)
        return 1
    print("PASS: every producer-OUTBOX control runs at a gate where its "
          "finding is hard")

    unavailable = [parts[0] for parts in map(case_parts, CASES)
                   if not case_available(pristine, parts[1], parts[2])]
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
    # One control per gate in use, measured on the UNMODIFIED copy. A gated
    # case must be judged against its own gate's baseline: a finding the
    # pristine tree already prints at that gate proves nothing there either.
    gate_controls = {None: control}

    def control_for(gate):
        if gate not in gate_controls:
            gate_controls[gate] = validator_output(pristine, gate)
        return gate_controls[gate]

    def matched(output: str, expected: str, gate: str | None) -> bool:
        """Did the validator report `expected`, at the severity the case claims?

        Naming a gate IS the claim that the finding is hard there, so a gated
        case is only satisfied by a FAIL line. Without this the gate would be
        decoration: the WARN this harness keeps on purpose carries the same
        text, and a control that accepts it proves the defect was noticed
        rather than refused (T-568).
        """
        if gate is None:
            return expected in output
        return any(ln.startswith("FAIL") and expected in ln
                   for ln in output.splitlines())

    dead, skipped, always = [], [], []
    for label, rel, mutation, expected, gate in map(case_parts, CASES):
        if matched(control_for(gate), expected, gate):
            always.append((label, expected))
            continue
        files = mutation_files(pristine, rel, mutation)
        saved = [(f, f.read_bytes() if f.exists() else None) for f in files]
        try:
            if not apply_case(pristine, rel, mutation):
                skipped.append(label)
                continue
            if not matched(validator_output(pristine, gate), expected, gate):
                dead.append((label, expected))
        finally:
            for f, data in saved:
                if data is None:
                    if f.exists():
                        f.unlink()
                else:
                    f.write_bytes(data)
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
        # The old wording blamed a missing FILE, and a skip is far more often
        # a present file whose ANCHOR moved -- a LOG line sealed into a
        # segment at the next cap crossing being the usual way. That message
        # sent its own author hunting for a file that was sitting right there.
        print(f"SKIP: {label} -- the mutation changed nothing: the file is "
              f"missing, or its anchor text is (a LOG anchor sealed into "
              f".saipen/logs/ is the usual cause)")
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

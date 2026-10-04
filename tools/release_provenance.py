"""Release provenance: the writer for a project's publication receipt.

WHY THIS EXISTS
---------------

`saipen_engine/closure.py` reads publication evidence for an
``inherited_verified`` closure, and it says in its own comment which file is
supposed to produce it:

    "the field the project's OWN receipt writer emits (tools/release_provenance.py
     writes `release_commit` and verifies against it; it never writes a bare
     `commit`)"

That writer was not in the tree. Without it a project that delivered and
pushed real work, but cut no release, had exactly two ways forward:

* cut a release nobody asked for, or
* hand-write `.saipen/kitchen/release_receipt.json` by hand.

Both are wrong, and the second is the dangerous one: a receipt typed by an
agent is not a receipt a release process committed, and the whole reason the
closure resolver insists on committed evidence is that "it shipped" must not
become true before anything shipped. The protocol already has the honest shape
for this case -- a terminal release receipt with ``mode: "no-publish"`` -- so
what was missing was the tool that WRITES it, not a decision to invent one.

WHAT THIS TOOL GUARANTEES
-------------------------

1. A receipt names a commit that actually resolves in the project repository.
   A receipt whose ``release_commit`` does not exist is refused at write time
   and fails at verify time, so a fabricated identity cannot be recorded.
2. The identity is written as ``release_commit``, never as a bare ``commit``,
   because the resolver reads both but the writer that emits only the second
   spelling made every genuine receipt invisible to it.
3. A receipt is a RECORD, not a claim: it names the Work it belongs to, the
   commit whose bytes shipped, whether a release was published or explicitly
   not, and when it was written. It never asserts more than that.
4. `write` overwrites the one current-release artifact, exactly as before.
   `write --slot` APPENDS under ``release_receipts/`` and refuses to replace a
   Work's recorded receipt (T-219): one publication identity per file, so a
   second closure no longer has to displace the first one's.

Usage::

    python tools/release_provenance.py write --project-root R \\
        --work T-108 --commit 046a5fb --mode no-publish --note "..."
    python tools/release_provenance.py write --project-root R --slot \\
        --work T-169 --commit 0b78ff2 --mode no-publish --note "..."
    python tools/release_provenance.py verify --project-root R
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RECEIPT_RELPATH = ".saipen/kitchen/release_receipt.json"
# T-219: the path above is ONE identity per project root. A second closure that
# names a different release could only be recorded by overwriting the first, so
# two legitimate closures could never both resolve -- and the tempting fix (one
# record carrying two identities) is a fabricated receipt. `write --slot`
# records into this directory instead: one identity per file, still terminal,
# still visible to a fresh clone. Reading them back is closure.py's job.
SLOT_RELDIR = ".saipen/kitchen/release_receipts"
MODES = ("publish", "no-publish")
# The slot file is NAMED for its Work, so the id is a path component. Validate it
# here rather than trusting a caller that reached the CLI with a string.
WORK_ID_RE = re.compile(r"T-\d+")


class ReceiptError(RuntimeError):
    """A receipt that cannot be written or does not survive verification."""


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True, encoding="utf-8",
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def resolve_commit(root: Path, commit: str) -> str:
    """The full object id of `commit`, or an error naming what did not resolve.

    This is the load-bearing check. Everything else in the receipt is a claim
    about the commit; this is the part that can be checked against the
    repository, and it is why a receipt cannot be invented for work that was
    never committed.
    """
    if not commit or not commit.strip():
        raise ReceiptError("no commit given: a receipt must name the commit whose bytes shipped")
    full = _git(root, "rev-parse", "--verify", f"{commit.strip()}^{{commit}}")
    if not full:
        raise ReceiptError(
            f"commit {commit.strip()!r} does not resolve in this repository; refusing to record it"
        )
    if len(full) != 40:
        raise ReceiptError(
            f"commit {commit.strip()!r} did not resolve to a full object id ({full!r})"
        )
    return full


def receipt_path(root: Path) -> Path:
    return Path(root) / RECEIPT_RELPATH


def build_receipt(
    root: Path,
    *,
    work: str,
    commit: str,
    mode: str,
    tag: str | None = None,
    version: str | None = None,
    note: str = "",
    op_id: str | None = None,
    at: str | None = None,
) -> dict:
    """One terminal release record, with the commit verified against the repo."""
    if mode not in MODES:
        raise ReceiptError(f"mode must be one of {MODES}, got {mode!r}")
    full = resolve_commit(root, commit)
    stamp = at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    record: dict = {
        "operation": "release",
        "status": "COMMITTED",
        "release_stage": "COMMITTED",
        "mode": mode,
        "work": work,
        # The closure resolver looks for release evidence that NAMES a Work by
        # reading `ticket_id`; this writer emitted only `work`, so a genuine
        # own_patch receipt was invisible to the very branch that consumes it.
        # Both spellings, one value -- never one without the other, which is
        # why `verify_receipt` refuses a pair that disagrees.
        "ticket_id": work,
        # The spelling the resolver's own comment names. A bare `commit` is
        # never written here.
        "release_commit": full,
        "at": stamp,
        "op_id": op_id or f"release-{work}-{full[:12]}",
    }
    if tag:
        record["tag"] = tag
    if version:
        record["version"] = version
    if note:
        record["note"] = note
    return record


def slot_dir(root: Path) -> Path:
    return Path(root) / SLOT_RELDIR


def slot_path(root: Path, work: str) -> Path:
    """One identity per file, named for the Work that owns it."""
    if not WORK_ID_RE.fullmatch(work or ""):
        raise ReceiptError(
            f"work {work!r} is not a Work id; a slot file is named for it and the "
            f"name must not be able to escape {SLOT_RELDIR}"
        )
    return slot_dir(root) / f"{work}.json"


def write_receipt(root: Path, *, slot: bool = False, **kwargs) -> dict:
    """Record one terminal release receipt.

    `slot=False` is the historical behaviour, unchanged: overwrite the single
    current-release artifact. `slot=True` APPENDS beside it and refuses to
    replace a Work's existing receipt -- an append that silently overwrote would
    re-create the very displacement this directory exists to prevent.
    """
    record = build_receipt(root, **kwargs)
    if slot:
        path = slot_path(root, str(record.get("work") or ""))
        if path.exists():
            raise ReceiptError(
                f"{SLOT_RELDIR}/{path.name} already records {record.get('work')}; "
                f"an appended receipt never replaces a recorded one"
            )
    else:
        path = receipt_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def slot_receipts(root: Path) -> list[tuple[Path, dict]]:
    """Every appended identity, in a stable order.

    An unreadable or non-object file is skipped: this is evidence collection, and
    an unreadable receipt proves nothing -- exactly as the journal arm above.
    """
    out: list[tuple[Path, dict]] = []
    for path in sorted(slot_dir(root).glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(raw, dict):
            out.append((path, raw))
    return out


def read_receipt(root: Path) -> dict:
    path = receipt_path(root)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReceiptError(f"no receipt at {RECEIPT_RELPATH}") from exc
    except (OSError, ValueError) as exc:
        raise ReceiptError(f"receipt at {RECEIPT_RELPATH} is unreadable: {exc}") from exc
    if not isinstance(raw, dict):
        raise ReceiptError("receipt is not an object")
    return raw


def verify_receipt(root: Path, record: dict | None = None) -> list[str]:
    """Every way a receipt can be false, as a list of reasons. Empty means true."""
    record = read_receipt(root) if record is None else record
    problems: list[str] = []
    if record.get("status") != "COMMITTED" or record.get("release_stage") != "COMMITTED":
        problems.append("receipt is not terminal (status/release_stage must both be COMMITTED)")
    if record.get("mode") not in MODES:
        problems.append(f"mode {record.get('mode')!r} is outside {MODES}")
    if "commit" in record:
        problems.append("receipt carries a bare `commit`; this writer emits `release_commit` only")
    identity = record.get("release_commit") or ""
    if not identity:
        problems.append("receipt names no release_commit")
    else:
        try:
            resolve_commit(root, str(identity))
        except ReceiptError as exc:
            problems.append(str(exc))
    if not record.get("op_id"):
        problems.append("receipt names no op_id, so nothing it claims can be tied to an operation")
    # A `ticket_id` with no `work` is the ship-shaped artifact and is fine; a
    # pair that DISAGREES is a receipt that points at two different Works.
    if record.get("ticket_id") and record.get("work") and record["ticket_id"] != record["work"]:
        problems.append(
            f"receipt names ticket_id {record.get('ticket_id')!r} but work "
            f"{record.get('work')!r}; one receipt cannot belong to two Works"
        )
    return problems


def verify_all(root: Path) -> list[str]:
    """Every way ANY recorded receipt can be false. Empty list means true.

    T-219: the single artifact and the appended identities are checked TOGETHER.
    A `verify` that only read the first would report OK over appended receipts
    nobody ever re-checked, which is the same "it shipped" illusion this tool
    exists to prevent -- just one directory deeper.
    """
    problems: list[str] = []
    current: dict | None = None
    absent = ""
    try:
        current = read_receipt(root)
    except ReceiptError as exc:
        absent = str(exc)
    if current is not None:
        problems.extend(f"{RECEIPT_RELPATH}: {p}" for p in verify_receipt(root, current))
    appended = slot_receipts(root)
    for path, record in appended:
        problems.extend(
            f"{SLOT_RELDIR}/{path.name}: {p}" for p in verify_receipt(root, record)
        )
    if current is None and not appended:
        raise ReceiptError(
            absent or f"no receipt at {RECEIPT_RELPATH} and none under {SLOT_RELDIR}"
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="release_provenance", description=__doc__.splitlines()[0])
    parser.add_argument(
        "--project-root",
        default=".",
        help="the project whose repository is authoritative for the commit",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    write = sub.add_parser("write", help="record a release receipt after verifying the commit")
    write.add_argument("--work", required=True, help="the Work this release belongs to")
    write.add_argument("--commit", required=True, help="the commit whose bytes shipped")
    write.add_argument("--mode", required=True, choices=MODES)
    write.add_argument("--tag", default=None)
    write.add_argument("--version", default=None)
    write.add_argument("--note", default="")
    write.add_argument(
        "--slot",
        action="store_true",
        help=(
            f"append the receipt under {SLOT_RELDIR}/ instead of overwriting "
            f"{RECEIPT_RELPATH}, so a second closure does not displace the first"
        ),
    )

    sub.add_parser("verify", help="re-check every recorded receipt against the repository")

    args = parser.parse_args(argv)
    root = Path(args.project_root).resolve()
    if args.action == "write":
        try:
            record = write_receipt(
                root,
                slot=args.slot,
                work=args.work,
                commit=args.commit,
                mode=args.mode,
                tag=args.tag,
                version=args.version,
                note=args.note,
            )
        except ReceiptError as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(record, ensure_ascii=False))
        return 0

    try:
        problems = verify_all(root)
    except ReceiptError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        return 1
    counted = len(slot_receipts(root)) + (1 if receipt_path(root).is_file() else 0)
    print(f"OK: {counted} receipt(s) name real commits and terminal operations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

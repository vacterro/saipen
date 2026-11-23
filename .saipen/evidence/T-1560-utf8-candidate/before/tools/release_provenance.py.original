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

Usage::

    python tools/release_provenance.py write --project-root R \\
        --work T-108 --commit 046a5fb --mode no-publish --note "..."
    python tools/release_provenance.py verify --project-root R
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RECEIPT_RELPATH = ".saipen/kitchen/release_receipt.json"
MODES = ("publish", "no-publish")


class ReceiptError(RuntimeError):
    """A receipt that cannot be written or does not survive verification."""


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
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


def write_receipt(root: Path, **kwargs) -> dict:
    record = build_receipt(root, **kwargs)
    path = receipt_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


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

    sub.add_parser("verify", help="re-check an existing receipt against the repository")

    args = parser.parse_args(argv)
    root = Path(args.project_root).resolve()
    if args.action == "write":
        try:
            record = write_receipt(
                root,
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
        problems = verify_receipt(root)
    except ReceiptError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        return 1
    print(f"OK: {RECEIPT_RELPATH} names a real commit and a terminal operation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

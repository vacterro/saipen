"""The release-attempt ledger: publication attempts, separate from closure.

T-1881 / SRC-306:R004 (audit D-06). The measured defect was not a failed push
but a *missing record of the attempt*: a session under an explicit
`PUBLICATION: FORBIDDEN` instruction ran `saipen ship`, the remote could not be
classified, and nothing durable said that a publication had even been tried.
Lifecycle closure answered a different question -- "is this ticket done?" --
and the DONE line carried no publication attempt at all.

So this module owns ONE append-only ledger, `.saipen/kitchen/release_attempts.jsonl`,
whose rows are independent of ticket lifecycle:

  * one row per release attempt, naming the invocation, the ticket the plan
    would publish for, the mode, the recovery op id when one exists, and a
    closed outcome token;
  * the ledger lives under the gitignored kitchen, like every other run
    artifact: it is a per-checkout audit trail, never distributed protocol
    memory, and it must never become an input to a publication decision. A
    reader that wanted authority would have to read real evidence, not this;
  * a write failure is reported to the caller and NEVER upgrades, downgrades
    or suppresses a release verdict. An audit trail that can veto a release is
    a second policy engine; an audit trail that can disappear silently is a
    lie. The caller gets `ok: False` plus the reason and surfaces it.

Outcomes are a closed set so a reader never has to parse prose:

    RELEASED            remote publication completed and verified
    NO_PUBLISH_MODE     local closure, zero external writes
    REFUSED_FORBIDDEN   blocked by a ticket-scoped publication prohibition
    REFUSED_<CODE>      any other structured refusal, code carried verbatim

A `--dry-run` records NOTHING. A preview is not an attempt to publish: it is a
plan that was shown and discarded, and writing it here would make every preview
of a release look like a publication event in the one ledger that exists to say
whether one was attempted. The `code` field still carries the exact refusal
code for a `REFUSED_<CODE>` row, so a reader never has to parse the prose.
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

#: The ledger, relative to the project root. Gitignored on purpose (`/.saipen/
#: kitchen/*`): it is this checkout's audit trail, not distributed authority.
ATTEMPTS_REL = ".saipen/kitchen/release_attempts.jsonl"

#: A row is bounded so one hostile payload cannot become a file that a later
#: reader has to parse for minutes. Every field this module writes is itself
#: bounded by the plan, so the cap only guards against a caller passing prose.
MAX_ROW_BYTES = 8 * 1024

#: Closed outcome vocabulary. `REFUSED_<CODE>` is the only open family and is
#: always derived from a registered refusal code, never from free text.
OUTCOMES = (
    "ATTEMPTED",
    "RELEASED",
    "NO_PUBLISH_MODE",
    "REFUSED_FORBIDDEN",
)


def ledger_path(root: Path | str) -> Path:
    return Path(root) / ATTEMPTS_REL


def _is_saipen_project(root: Path) -> bool:
    """A ledger is only ever written into a real project.

    `record()` creates its parent directory, which without this guard would
    MINT `.saipen/kitchen/` inside any scratch directory a caller passed --
    producing the appearance of a project where none exists, from a function
    whose whole job is to observe one. An attempt against a non-project is not
    that project's audit trail; it is a caller error, reported as such.
    """
    return (Path(root) / ".saipen").is_dir()


def _utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _bounded(value: object, limit: int = 400) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def record(
    root: Path | str,
    *,
    invocation: str,
    outcome: str,
    ticket: str = "",
    mode: str = "",
    op_id: str = "",
    code: str = "",
    detail: str = "",
    forbidden_by: str = "",
) -> dict:
    """Append ONE attempt row. Never raises; reports its own failure.

    The row is written with `O_APPEND` and fsynced, so two concurrent attempts
    interleave as whole lines rather than as half-written JSON. The directory
    is created when absent: the kitchen is runtime scratch and its absence is
    the normal first-run case, not an error.
    """
    row = {
        "kind": "release-attempt",
        "schema_version": 1,
        "recorded_at": _utc(),
        "invocation": _bounded(invocation, 80),
        "ticket": _bounded(ticket, 40),
        "mode": _bounded(mode, 20),
        "op_id": _bounded(op_id, 80),
        "outcome": _bounded(outcome, 60),
        "code": _bounded(code, 60),
        "detail": _bounded(detail),
    }
    if forbidden_by:
        row["forbidden_by"] = _bounded(forbidden_by, 40)
    try:
        body = json.dumps(row, sort_keys=True, allow_nan=False) + "\n"
        encoded = body.encode("utf-8")
    except (TypeError, ValueError) as exc:
        return {"ok": False, "error": f"attempt row is not JSON-serializable: {exc}"}
    if len(encoded) > MAX_ROW_BYTES:
        return {
            "ok": False,
            "error": f"attempt row exceeds {MAX_ROW_BYTES} bytes",
        }
    path = ledger_path(root)
    if not _is_saipen_project(root):
        return {
            "ok": False,
            "error": f"{root} has no .saipen/: refusing to mint a project while "
            "recording an attempt for it",
        }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
        flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "ab") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        return {"ok": False, "error": f"cannot append {ATTEMPTS_REL}: {exc}"}
    return {"ok": True, "path": ATTEMPTS_REL, "row": row}


def read(root: Path | str) -> list[dict]:
    """Every row, oldest first. A malformed line is reported, never skipped.

    Silence would let a truncated ledger read as "no attempt was ever made",
    which is exactly the false negative D-06 describes.
    """
    path = ledger_path(root)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    rows: list[dict] = []
    for number, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{ATTEMPTS_REL}:{number} is not JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{ATTEMPTS_REL}:{number} is not an object")
        rows.append(row)
    return rows


def outcome_token(result: dict) -> str:
    """The closed outcome token for one release verdict.

    `result` is the dict `execute_release` returns (or the payload the CLI
    emitted for a refusal raised before execution). The mapping is total: an
    unexpected shape becomes `ATTEMPTED` with the code preserved beside it,
    because a ledger that drops a row it cannot classify is worse than one that
    records a row it cannot fully explain.
    """
    code = str(result.get("code") or "").strip()
    if result.get("ok"):
        if code == "NO_PUBLISH_MODE":
            return "NO_PUBLISH_MODE"
        return "RELEASED"
    if code == "RELEASE_FORBIDDEN":
        return "REFUSED_FORBIDDEN"
    if code:
        return f"REFUSED_{code}"
    return "ATTEMPTED"


def record_result(
    root: Path | str,
    *,
    invocation: str,
    result: dict,
    ticket: str = "",
    mode: str = "",
    op_id: str = "",
    forbidden_by: str = "",
) -> dict:
    """Append the row for one completed release ATTEMPT.

    Call this from the public invocation boundary (the CLI verb, the cohort
    operation, the intent action) and NOT from `execute_release`: the engine's
    release executor is also called directly by tests and by recovery, and an
    engine-internal audit write would make "a refusal writes nothing" false at
    the API level -- the five `_tree()` equality assertions in
    `test_t1746_crew_terminal_outcome.py` are that invariant. The attempt
    belongs to the caller that ASKED; the verdict belongs to the engine.

    A `--dry-run` must be filtered by the caller: a preview is not an attempt.
    """
    return record(
        root,
        invocation=invocation,
        outcome=outcome_token(result),
        ticket=ticket,
        mode=mode,
        op_id=op_id,
        code=str(result.get("code") or ""),
        detail=str(result.get("detail") or result.get("message") or ""),
        # The APPLY-time refusal names the ticket it refused FOR in a machine
        # field; the planner's refusal carries the id only inside its prose, so
        # this stays empty there rather than being scraped back out of a
        # sentence.
        forbidden_by=forbidden_by or str(result.get("forbidden_ticket") or ""),
    )

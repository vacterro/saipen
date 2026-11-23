"""A runtime-home rebind is a VERDICT, never a guessed executable (SRC-274:R004).

F-04 in that receipt measured a session whose PATH launcher crashed, which then
probed the disk, found the machine runtime's launcher and used it to MUTATE a
project whose own recorded home still named the crashed tree. The version
matched, so nothing objected: a version number is not an identity, and "the
command worked" is not a compatibility proof.

So the decision is one machine-readable verdict over six facts, and the only
place it can be spent is the single choke point every rebind writes through.
Anything short of ACCEPTED refuses the mutation while leaving the verdict
itself readable -- diagnosis is the one thing a project with a doubtful runtime
can still be given.

The six are exactly the ones the receipt names:

    build_identity        the candidate proves a content fingerprint, and the
                          path that claims to be "the engine now running"
                          shares the running engine's fingerprint
    loaded_revision       where both trees name a git revision it must be the
                          same one; a flattened install names none, and an
                          absent revision is recorded, never invented
    schema_compatibility  a candidate whose STATE schema is OLDER than this
                          project's cannot be given this state to read
    project_binding       the candidate resolves to an install layout
    actor_binding         a named actor owns the write
    no_pending_operation  no unresolved journal operation, and no recovery
                          conflict, stands between the rebind and the bytes

Checks that cannot be decided from bytes are recorded as unproven and are NOT
allowed to invent a refusal, because a guard that refuses on an undecidable
fact has no exit. Checks that CAN be decided fail closed.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

SCHEMA = 1
FAMILY = "runtime-home"
ACCEPTED = "ACCEPTED"
REFUSED = "REFUSED"
CODE_REFUSED = "RUNTIME_HOME_UNPROVEN"

CHECKS = (
    "build_identity",
    "loaded_revision",
    "schema_compatibility",
    "project_binding",
    "actor_binding",
    "no_pending_operation",
)

#: A check answer is PASS, FAIL, or UNPROVEN. Only FAIL refuses.
PASS = "PASS"
FAIL = "FAIL"
UNPROVEN = "UNPROVEN"


def _check(name: str, answer: str, detail: str, **evidence) -> dict:
    record = {"check": name, "answer": answer, "detail": detail}
    if evidence:
        record["evidence"] = evidence
    return record


def _head(home: Path) -> str:
    """The git revision `home` is at, or "" when it is not a git tree."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(home), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
            check=False,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _schema(home: Path) -> int | None:
    """`x-current-schema-version` of the STATE schema in `home`, or None."""
    path = home / "extensions" / "schemas" / "state.schema.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = payload.get("x-current-schema-version") if isinstance(payload, dict) else None
    return value if type(value) is int else None


def _layout_ok(home: Path) -> bool:
    if not home.is_dir():
        return False
    boots = (home / "saipen" / "BOOT.md", home / "BOOT.md")
    return any(candidate.is_file() for candidate in boots)


def running_engine() -> Path:
    """The install this process is executing from."""
    return Path(__file__).resolve().parents[2]


def verdict(
    project_root: Path | str,
    candidate_home: Path | str,
    *,
    state: dict | None = None,
    actor: str | None = None,
    running_home_path: Path | str | None = None,
    require_identity_match: bool = False,
) -> dict:
    """The six-check verdict on replacing the project's runtime with `candidate_home`.

    Read-only, and cheap enough to ask on every rebind. `state` is the already
    parsed STATE when the caller holds one, so the STATE schema this project
    speaks is judged from the bytes the caller is actually rebinding onto.
    """
    from . import journal
    from .install_identity import install_fingerprint
    from .state import parse_frontmatter

    root = Path(project_root)
    candidate = Path(str(candidate_home))
    running = Path(str(running_home_path)) if running_home_path else running_engine()
    fields = state
    if fields is None:
        try:
            parsed, error = parse_frontmatter(
                (root / ".saipen" / "STATE.md").read_text(encoding="utf-8")
            )
        except OSError:
            parsed, error = None, "STATE unreadable"
        fields = parsed if error is None and isinstance(parsed, dict) else {}

    checks: list[dict] = []

    # 1. build_identity -- bytes, not a version number.
    candidate_fp = install_fingerprint(candidate)
    running_fp = install_fingerprint(running)
    if candidate_fp == "missing-v1":
        checks.append(
            _check(
                "build_identity",
                FAIL,
                "the candidate install proves no content fingerprint, so nothing "
                "names which bytes would answer",
                candidate_fingerprint=candidate_fp,
            )
        )
    elif require_identity_match and candidate_fp != running_fp:
        checks.append(
            _check(
                "build_identity",
                FAIL,
                "the candidate is not the install now running (different content "
                "fingerprint), so converging onto it would rebind this project onto "
                "an engine that did not produce the evidence it is reading",
                candidate_fingerprint=candidate_fp,
                running_fingerprint=running_fp,
            )
        )
    else:
        checks.append(
            _check(
                "build_identity",
                PASS,
                "the candidate proves a content fingerprint",
                candidate_fingerprint=candidate_fp,
                running_fingerprint=running_fp,
                identity_match=candidate_fp == running_fp,
            )
        )

    # 2. loaded_revision -- where both name one, they must agree.
    candidate_head, running_head = _head(candidate), _head(running)
    if not candidate_head:
        checks.append(
            _check(
                "loaded_revision",
                UNPROVEN,
                "the candidate is not a git tree, so it names no source revision; "
                "the content fingerprint above is its identity",
                candidate_revision=None,
                running_revision=running_head or None,
            )
        )
    elif not running_head:
        checks.append(
            _check(
                "loaded_revision",
                UNPROVEN,
                "the running install is not a git tree, so there is no revision to "
                "compare against the candidate's",
                candidate_revision=candidate_head,
                running_revision=None,
            )
        )
    elif candidate_head != running_head:
        checks.append(
            _check(
                "loaded_revision",
                FAIL,
                "the candidate is at a different source revision than the running "
                "install, so the protocol rules answering this project would change "
                "mid-flight",
                candidate_revision=candidate_head,
                running_revision=running_head,
            )
        )
    else:
        checks.append(
            _check(
                "loaded_revision",
                PASS,
                "candidate and running install are the same source revision",
                candidate_revision=candidate_head,
            )
        )

    # 3. schema_compatibility -- an older state schema cannot read this state.
    candidate_schema = _schema(candidate)
    declared = fields.get("schema_version") if isinstance(fields, dict) else None
    project_schema = declared if type(declared) is int else None
    if candidate_schema is None or project_schema is None:
        checks.append(
            _check(
                "schema_compatibility",
                UNPROVEN,
                "one side of the STATE-schema comparison is unreadable, so "
                "compatibility is not claimable either way",
                candidate_schema=candidate_schema,
                project_schema=project_schema,
            )
        )
    elif candidate_schema < project_schema:
        checks.append(
            _check(
                "schema_compatibility",
                FAIL,
                f"the candidate speaks STATE schema {candidate_schema} and this "
                f"project's state is schema {project_schema}; a runtime older than "
                "the state it is given would read it under the wrong contract",
                candidate_schema=candidate_schema,
                project_schema=project_schema,
            )
        )
    else:
        checks.append(
            _check(
                "schema_compatibility",
                PASS,
                f"the candidate speaks STATE schema {candidate_schema}, which is not "
                f"older than this project's {project_schema}",
                candidate_schema=candidate_schema,
                project_schema=project_schema,
            )
        )

    # 4. project_binding -- a real install, at an absolute resolved path.
    if candidate.is_absolute() and _layout_ok(candidate):
        checks.append(
            _check(
                "project_binding",
                PASS,
                "the candidate is an absolute path holding a SAIPEN boot kernel",
                candidate_home=str(candidate),
            )
        )
    else:
        checks.append(
            _check(
                "project_binding",
                FAIL,
                "the candidate is not an absolute path to an install layout (no "
                "saipen/BOOT.md), so a rebind onto it would bind this project to a "
                "directory that cannot boot it",
                candidate_home=str(candidate),
            )
        )

    # 5. actor_binding -- the write needs a named owner.
    named_actor = str(actor or "").strip()
    if named_actor:
        checks.append(
            _check(
                "actor_binding",
                PASS,
                "a named actor owns this rebind",
                actor=named_actor,
            )
        )
    else:
        checks.append(
            _check(
                "actor_binding",
                FAIL,
                "no actor was named for this rebind, so the journaled pointer "
                "change would carry no owner",
                actor=None,
            )
        )

    # 6. no_pending_operation -- an unfinished write is debt against the pointer.
    pending = journal.pending_ops(root)
    conflicts = journal.pending_conflicts(root)
    if pending or conflicts:
        names = ", ".join(
            str(item.get("op_id", "?")) for item in (conflicts or pending)[:5]
        )
        checks.append(
            _check(
                "no_pending_operation",
                FAIL,
                f"unresolved journal operation(s) stand between this rebind and the "
                f"pointer it would write: {names}",
                pending=[str(item.get("op_id", "?")) for item in pending],
                conflicts=[str(item.get("op_id", "?")) for item in conflicts],
            )
        )
    else:
        checks.append(
            _check(
                "no_pending_operation",
                PASS,
                "no unresolved journal operation or recovery conflict is open",
                pending=[],
                conflicts=[],
            )
        )

    failed = [item["check"] for item in checks if item["answer"] == FAIL]
    unproven = [item["check"] for item in checks if item["answer"] == UNPROVEN]
    return {
        "schema": SCHEMA,
        "family": FAMILY,
        "verdict": REFUSED if failed else ACCEPTED,
        "candidate_home": str(candidate),
        "running_home": str(running),
        "checks": checks,
        "failed": failed,
        "unproven": unproven,
    }


def problem(view: dict) -> str | None:
    """Why this verdict refuses a mutation, or None when it accepts one."""
    if not isinstance(view, dict) or view.get("schema") != SCHEMA \
            or view.get("family") != FAMILY \
            or view.get("verdict") not in (ACCEPTED, REFUSED):
        return "not a runtime-home verdict"
    if view.get("verdict") != REFUSED:
        return None
    failed = view.get("failed") or [
        item.get("check") for item in view.get("checks") or []
        if isinstance(item, dict) and item.get("answer") == FAIL
    ]
    details = [
        f"{item.get('check')}: {item.get('detail')}"
        for item in view.get("checks") or []
        if isinstance(item, dict) and item.get("answer") == FAIL
    ]
    if details:
        return "; ".join(details)
    if failed:
        return "runtime-home verdict failed: " + ", ".join(str(name) for name in failed)
    return "runtime-home verdict is REFUSED but names no failed check"


def summary(view: dict) -> str:
    """One line a refusal can carry without repeating the whole projection."""
    if not isinstance(view, dict):
        return "no verdict"
    answers = {
        str(item.get("check")): str(item.get("answer"))
        for item in view.get("checks") or []
    }
    return " ".join(f"{name}={answers.get(name, 'MISSING')}" for name in CHECKS)

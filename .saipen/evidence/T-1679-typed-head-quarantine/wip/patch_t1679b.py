"""T-1679, second pass: a separate observable set for the typed-head quarantine.

tools/test_log_tail_quarantine.py pins TAIL_QUARANTINE_OBSERVABLE disjoint from
REPAIR_OBSERVABLE (reconcile never plans on a cut ledger). That constant stays
as it was; the quarantine's own two readers name a wider set.

patch_t1679b.py <tree-root>
"""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])


def patch(rel: str, edits: list[tuple[str, str]]) -> None:
    path = ROOT / rel
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new in edits:
        assert text.count(old) == 1, (rel, text.count(old), old[:90])
        text = text.replace(old, new)
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    print("patched", rel)


patch(
    "tools/saipen_engine/operations.py",
    [
        (
            '''#:
#: T-1679 adds two classes this one caller may look past, because a typed head
#: brings them with it: a STATE the same hand left malformed, and the
#: unauthorized marker the cut itself is about to replace. The quarantine
#: writes the LOG without the suffix and its own event becomes `last_event`;
#: the rows the suffix closed are named in that event for the reconciliation
#: that follows (`lifecycle_authority.quarantine_note`).
TAIL_QUARANTINE_OBSERVABLE = ("foreign_tail", "state", "lifecycle_authority")
''',
            '''TAIL_QUARANTINE_OBSERVABLE = ("foreign_tail",)

#: What the quarantine itself reads with (T-1679). A typed head brings two more
#: classes with it: a STATE the same hand left malformed, and the unauthorized
#: marker the cut is about to replace. The quarantine writes the LOG without
#: the suffix and its own event becomes `last_event`; the rows the suffix had
#: closed are named in that event for the reconciliation that follows
#: (`lifecycle_authority.quarantine_note`). `TAIL_QUARANTINE_OBSERVABLE` stays
#: the one class no planner may share.
TYPED_HEAD_QUARANTINE_OBSERVABLE = (*TAIL_QUARANTINE_OBSERVABLE, "state", "lifecycle_authority")
''',
        ),
        (
            '''    read_once = _read(root, observe=TAIL_QUARANTINE_OBSERVABLE)
    docs, state, _board, _tail = read_once
    cut = docs.get("_foreign_tail")
    if cut is None:
        reason = docs.get("_foreign_tail_refusal") or "no foreign tail was proven"
        return _refuse(
            "VALIDATION_FAILED"
            if reason.startswith("the complete LOG history already passes")
            else "CONFLICT",
            "LOG tail quarantine refuses: " + reason,
        )
''',
            '''    read_once = _read(root, observe=TYPED_HEAD_QUARANTINE_OBSERVABLE)
    docs, state, _board, _tail = read_once
    cut = docs.get("_foreign_tail")
    if cut is None:
        reason = docs.get("_foreign_tail_refusal") or "no foreign tail was proven"
        return _refuse(
            "VALIDATION_FAILED"
            if reason.startswith("the complete LOG history already passes")
            else "CONFLICT",
            "LOG tail quarantine refuses: " + reason,
        )
    if cut.journal_floor is None and "lifecycle_authority" in docs["_observed"]:
        # A stray tail on top of a typed head that the ledger contract accepts:
        # this event would become the floor and bury the head unseen.
        return _refuse(
            "PROTOCOL_STATE_INVALID",
            "LOG tail quarantine refuses: " + docs["_observed"]["lifecycle_authority"]
            + " -- run `saipen recover` first; it reconciles the typed head",
            next_action="saipen recover",
        )
''',
        ),
    ],
)

patch(
    "tools/saipen_engine/reconcile.py",
    [(
        '''    from .operations import TAIL_QUARANTINE_OBSERVABLE, _read

    try:
        docs, _state, _board, _tail = _read(project_root, observe=TAIL_QUARANTINE_OBSERVABLE)
''',
        '''    from .operations import TYPED_HEAD_QUARANTINE_OBSERVABLE, _read

    try:
        docs, _state, _board, _tail = _read(
            project_root, observe=TYPED_HEAD_QUARANTINE_OBSERVABLE
        )
''',
    )],
)

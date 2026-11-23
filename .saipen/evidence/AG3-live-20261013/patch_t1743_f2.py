"""T-1743 F2: a small BOARD row carrying a field outside the closed grammar
gets a canonical, lossless repair route (explicit `saipen ticket compact`),
and Fleet names it as a SAFE repair instead of naming nothing.

Same mechanics as patch_t1743.py: anchored, every anchor exactly once, line
endings preserved.
"""
import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("p1743", HERE / "patch_t1743.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.EDITS.clear()
edit = base.edit

# ---------------------------------------------------------- board_compaction
edit(
    "board_compaction.py",
    '''def oversized_ticket_ids(board_text: str) -> list[str]:
''',
    '''def foreign_field_ticket_ids(board_text: str) -> list[str]:
    """Rows whose ONLY parse fault is a refused field outside the closed grammar.

    T-1743: such a row has a lossless canonical repair -- compaction journals
    its complete physical bytes (the foreign field included) into the detail
    authority and rewrites only the live projection. Measured dead end before
    this: SMART_VAC_CLEANER T-199 carried `source: saihunt HUNT-001` from a
    hand-written collect, `ticket compact T-199` refused VALIDATION_FAILED, and
    Fleet named nothing, so every lifecycle command in the project stopped at a
    board nobody could repair. Any OTHER parse fault keeps the board fatal, so
    this returns [] for it.
    """
    parsed = parse_board(board_text)
    found: list[str] = []
    for error in parsed.get("errors", []):
        ticket_id = unrecognized_field_ticket(error)
        if ticket_id is None or ticket_id not in parsed["tickets"]:
            return []
        if ticket_id not in found:
            found.append(ticket_id)
    return found


def oversized_ticket_ids(board_text: str) -> list[str]:
''',
)
edit(
    "board_compaction.py",
    '''    reason: str,
    tolerated_ids: frozenset[str] | set[str] = frozenset(),
) -> tuple[str, tuple[TargetPlan, ...], str | None, str | None]:
''',
    '''    reason: str,
    tolerated_ids: frozenset[str] | set[str] = frozenset(),
    foreign_ids: frozenset[str] | set[str] = frozenset(),
) -> tuple[str, tuple[TargetPlan, ...], str | None, str | None]:
''',
)
edit(
    "board_compaction.py",
    '''    raw = str(ticket["raw"])
    if len(raw) <= MAX_LIVE_RECORD_CHARS:
        return board_text, (), None, None
''',
    '''    raw = str(ticket["raw"])
    # A row within the cap is rewritten only when the caller named it as a
    # foreign-field repair (T-1743); otherwise there is nothing to compact.
    if len(raw) <= MAX_LIVE_RECORD_CHARS and ticket_id not in foreign_ids:
        return board_text, (), None, None
''',
)
edit(
    "board_compaction.py",
    '''    reason: str,
    tolerated_ids: frozenset[str] | set[str] | None = None,
) -> CompactionResult:
    """Compact each requested oversized existing row exactly once.
''',
    '''    reason: str,
    tolerated_ids: frozenset[str] | set[str] | None = None,
    foreign_ids: frozenset[str] | set[str] | None = None,
) -> CompactionResult:
    """Compact each requested oversized existing row exactly once.
''',
)
edit(
    "board_compaction.py",
    '''            reason=reason,
            tolerated_ids=tolerated,
        )
        targets.extend(extra)
''',
    '''            reason=reason,
            tolerated_ids=tolerated,
            foreign_ids=frozenset(foreign_ids or ()),
        )
        targets.extend(extra)
''',
)

# ---------------------------------------------------------------- operations
edit(
    "operations.py",
    '''from .board_compaction import (
    CompactionResult,
    oversized_ticket_ids,
''',
    '''from .board_compaction import (
    CompactionResult,
    foreign_field_ticket_ids,
    oversized_ticket_ids,
''',
)
edit(
    "operations.py",
    '''@_state_guard
def compact_board(
''',
    '''def _foreign_field_skew(state: dict) -> str | None:
    """Refuse a foreign-field repair when the project is NEWER than this runtime.

    A field this runtime does not know may belong to a later canonical writer;
    stripping it from the live projection would then be version skew, not a
    repair. A project at or below the running protocol major has no such
    writer, so the field is foreign by construction.
    """
    from .state import running_protocol_major

    running = running_protocol_major()
    try:
        declared = int(str((state or {}).get("saipen_version") or "0").strip())
    except ValueError:
        declared = 0
    if running is not None and declared > running:
        return (
            f"project declares saipen_version {declared}, newer than this runtime "
            f"({running}); a field this runtime does not know may be a newer "
            "writer's, so it is not compacted away here -- run the newer runtime"
        )
    return None


@_state_guard
def compact_board(
''',
)
edit(
    "operations.py",
    '''    repairable = oversized_ticket_ids(board_text)
    if board["errors"]:
        allowed = set(repairable)
        if not allowed or any(
            unrecognized_field_ticket(error) not in allowed for error in board["errors"]
        ):
''',
    '''    repairable = oversized_ticket_ids(board_text)
    # T-1743: naming a row whose only fault is a field outside the closed
    # grammar IS the repair request for that row. Its full bytes are journaled
    # into the detail authority first, exactly like an oversized row, so the
    # refused field is preserved, never silently dropped.
    foreign: list[str] = []
    tolerated_rows = set(repairable)
    if ticket_id not in repairable and ticket_id in foreign_field_ticket_ids(board_text):
        skew = _foreign_field_skew(state)
        if skew:
            return _refuse("VALIDATION_FAILED", skew, ticket=ticket_id)
        foreign = [ticket_id]
        repairable = [*repairable, ticket_id]
        tolerated_rows = set(repairable) | set(foreign_field_ticket_ids(board_text))
    if board["errors"]:
        allowed = tolerated_rows
        if not allowed or any(
            unrecognized_field_ticket(error) not in allowed for error in board["errors"]
        ):
''',
)
edit(
    "operations.py",
    '''            "DEC",
            tid,
            agent,
            "legacy oversized BOARD record compacted losslessly via SAIOPS",
            now,
            op_id,
        )
''',
    '''            "DEC",
            tid,
            agent,
            "BOARD record carrying a field outside the closed grammar compacted "
            "losslessly via SAIOPS (original bytes externalized)"
            if tid in foreign
            else "legacy oversized BOARD record compacted losslessly via SAIOPS",
            now,
            op_id,
        )
''',
)
edit(
    "operations.py",
    '''            reason="explicit canonical legacy BOARD compaction",
            tolerated_ids=set(repairable),
        )
''',
    '''            reason="explicit canonical legacy BOARD compaction",
            tolerated_ids=tolerated_rows,
            foreign_ids=set(foreign),
        )
''',
)

# --------------------------------------------------------------------- fleet
edit(
    "fleet.py",
    '''from .board_compaction import compacted_ticket_ids, detail_integrity_error, oversized_ticket_ids
''',
    '''from .board_compaction import (
    compacted_ticket_ids,
    detail_integrity_error,
    foreign_field_ticket_ids,
    oversized_ticket_ids,
    unrecognized_field_ticket,
)
''',
)
edit(
    "fleet.py",
    '''    "BOARD_RECORD_OVERSIZE": "board",
    "BOARD_DETAIL_UNRESOLVABLE": "board",
''',
    '''    "BOARD_RECORD_OVERSIZE": "board",
    "BOARD_FOREIGN_FIELD": "board",
    "BOARD_DETAIL_UNRESOLVABLE": "board",
''',
)
edit(
    "fleet.py",
    '''            command = f"{_BOARD_COMPACTION_COMMAND} {ticket_id or '<T-###>'}"
        return {
''',
    '''            command = f"{_BOARD_COMPACTION_COMMAND} {ticket_id or '<T-###>'}"
        elif reason_code == "BOARD_FOREIGN_FIELD":
            errors = ((snapshot or {}).get("board") or {}).get("errors") or []
            ticket_id = next(
                (tid for tid in map(unrecognized_field_ticket, errors) if tid), None
            )
            command = f"{_BOARD_COMPACTION_COMMAND} {ticket_id or '<T-###>'}"
        return {
''',
)
edit(
    "fleet.py",
    '''        return oversize

    # T-1326 TARGET C: a compacted row whose externalized original record or
''',
    '''        return oversize

    # T-1743: a row whose ONLY fault is a field outside the closed grammar has
    # the same lossless repair as an oversized one. Naming nothing here left
    # every lifecycle command refused with no reachable route. A pending STATE
    # repair still goes first (T-1327 ordering): it is named further below.
    try:
        foreign_rows = foreign_field_ticket_ids(board_text)
    except (NameError, OSError, UnicodeError, ValueError):
        foreign_rows = []
    if foreign_rows:
        prerequisite = reconcile_protocol_state(root, agent, dry_run=True)
        if not (prerequisite.get("ok") and prerequisite.get("code") == "REPAIR_REQUIRED"):
            snapshot["board"] = parse_board(board_text)
            foreign = _result(
                CLASS_SAFE,
                root=root,
                lineage=lineage,
                reason_code="BOARD_FOREIGN_FIELD",
                reason=(
                    "BOARD row(s) carry a field outside the closed grammar; lossless "
                    "canonical compaction externalizes the original bytes: "
                    + ", ".join(foreign_rows[:8])
                ),
                snapshot=snapshot,
                provenance=resolved.provenance,
            )
            if foreign.get("condition_id") is not None:
                return foreign

    # T-1326 TARGET C: a compacted row whose externalized original record or
''',
)

if __name__ == "__main__":
    base.apply()

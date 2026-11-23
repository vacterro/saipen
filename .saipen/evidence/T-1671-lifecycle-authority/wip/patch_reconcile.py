"""Apply the T-1671 reconcile patch to a tree: patch_reconcile.py <tree-root>."""
import sys
from pathlib import Path

p = Path(sys.argv[1]) / "tools/saipen_engine/reconcile.py"
b = p.read_bytes()
crlf = b"\r\n" in b
t = b.decode("utf-8").replace("\r\n", "\n")


def sub(old: str, new: str) -> None:
    global t
    assert t.count(old) == 1, (t.count(old), old[:90])
    t = t.replace(old, new)


HELPER = r'''def _lifecycle_authority_repairs(
    state: dict, board: dict | None, events, verdict: dict | None
) -> dict:
    """Repairs for an UNAUTHORIZED lifecycle head (T-1671, SRC-192).

    Defect class: canonical lifecycle state typed by an executor that lost the
    control route. `lifecycle_authority.assess` names it from the journal; the
    classes above cannot, because they read a closure from BOARD fields
    (`closure_mode`, `owner`) and from LOG prose (`verify -> PASS`), and a hand
    types all three.

    The repair demotes exactly what no operation produced and invents nothing:

      * a `## DONE` row vouched for only by hand-written head events returns
        to `## TODO` with its closure metadata and claim dropped, so the
        ordinary lifecycle re-establishes the completion. It is a BOARD
        lifecycle atom and therefore rides the one-approval plan (SRC-043);
      * a STATE bound to such a ticket, or to a ticket no operation ever
        touched, goes idle (`DONE` / `task: none`): the journal proves no
        phase for it, and an invented phase is the fabrication T-1318 refuses;
      * `last_event` is rebound, which is what makes this reconciliation
        commit its own journaled event even when nothing else is owed -- the
        hand-written lines stay in the append-only LOG as history, and the
        operation that says so becomes the new floor.

    A STATE bound to a ticket the journal DOES know keeps its phase: judging a
    hand-moved phase of a journaled ticket needs the per-ticket lifecycle
    proof, which `_state_phase_repairs` owns for the pairs it can decide.
    """
    from . import lifecycle_authority as _la

    plan: dict = {"state": [], "board": [], "idle": False, "trace": ""}
    if not verdict or verdict.get("status") != _la.UNAUTHORIZED:
        return plan
    floor = verdict.get("floor")
    findings = verdict.get("findings") or []
    tickets = (board or {}).get("tickets", {}) or {}
    unbacked = sorted(
        f["ticket"] for f in findings if f.get("rule") == _la.TERMINAL_UNBACKED
    )

    def reopen(tid: str, origin: str, reason: str) -> dict:
        row = tickets.get(tid) or {}
        dropped = _reopen_field_removals(row.get("raw", ""))
        for name in ("owner", "claim_time"):
            if name in (row.get("fields") or {}) and name not in dropped:
                dropped.append(name)
        return {
            "field": "board", "surface": "board", "kind": "section-move",
            "_class": _la.REPAIR_CLASS, "ticket": tid,
            "from_section": origin, "to_section": "## TODO",
            "fields": dropped, "requires_approval": True, "generation": "current",
            "reason": reason,
        }

    for finding in findings:
        if finding.get("rule") != _la.TERMINAL_UNBACKED:
            continue
        plan["board"].append(reopen(
            finding["ticket"], "## DONE",
            f"UNAUTHORIZED_LIFECYCLE_WRITE: {finding['detail']}; it returns to "
            "## TODO without closure metadata or claim and the canonical "
            "lifecycle re-establishes the completion -- original bytes preserved",
        ))
    task = state.get("task")
    bound = task if isinstance(task, str) and re.fullmatch(r"T-\d+", task) else None
    journaled = bound is not None and any(
        event.get("ticket") == bound
        and event.get("op_id")
        and isinstance(event.get("event"), int)
        and not isinstance(event.get("event"), bool)
        and (floor is None or event["event"] <= floor)
        for event in (events or ())
    )
    state_ahead = any(f.get("rule") == _la.STATE_AHEAD for f in findings)
    if bound is not None and (bound in unbacked or (state_ahead and not journaled)):
        plan["idle"] = True
        why = (
            f"UNAUTHORIZED_LIFECYCLE_WRITE: STATE is bound to {bound}, "
            + (
                "whose completion no operation produced"
                if bound in unbacked
                else "which no operation ever touched"
            )
            + "; the journal proves no phase for it, so STATE goes idle and the "
            "queue decides -- never an invented phase"
        )
        for field, value in (
            ("phase", "DONE"), ("transition_from", "DONE"),
            ("task", "none"), ("next_action", "saipen continue"),
        ):
            if state.get(field) != value:
                plan["state"].append({
                    "field": field, "from": state.get(field), "to": value,
                    "surface": "state", "_class": _la.REPAIR_CLASS, "reason": why,
                })
        row = tickets.get(bound)
        if bound not in unbacked and isinstance(row, dict) and row.get("section") == "## DOING":
            plan["board"].append(reopen(
                bound, "## DOING",
                f"UNAUTHORIZED_LIFECYCLE_WRITE: {bound} sits under ## DOING on a "
                "claim no operation wrote; it returns to ## TODO unclaimed",
            ))
    if state_ahead:
        plan["state"].append({
            "field": "last_event", "from": state.get("last_event"), "to": floor,
            "surface": "state", "_class": _la.REPAIR_CLASS,
            "reason": (
                f"UNAUTHORIZED_LIFECYCLE_WRITE: STATE.last_event sits above "
                f"E-{floor}, the newest event an operation record stands behind; "
                "this reconciliation's own journaled event becomes the marker"
            ),
        })
    head = verdict.get("head") or []
    if len(head) > 1:
        span = f"E-{head[0]}..E-{head[-1]}"
    else:
        span = f"E-{head[0]}" if head else "no event"
    plan["trace"] = (
        f"lifecycle authority: {span} above E-{floor} carry no operation record "
        "(written by hand); kept as history, nothing stands on their word"
        + ("; reopened " + ", ".join(unbacked) if unbacked else "")
    )
    return plan


def _repair_summary(board_drifts: list[dict], state_repairs: list[dict]) -> str:
'''

sub("def _repair_summary(board_drifts: list[dict], state_repairs: list[dict]) -> str:\n", HELPER)

sub(
    '''        docs, state, _board, log_tail = _read(project_root, observe=REPAIR_OBSERVABLE)
    except Exception as exc:
        # CheckpointError / HomeDeadError / OSError all mean the surface cannot''',
    '''        from .lifecycle_authority import OBSERVABLE as _LIFECYCLE_OBSERVABLE

        docs, state, _board, log_tail = _read(
            project_root, observe=REPAIR_OBSERVABLE + (_LIFECYCLE_OBSERVABLE,)
        )
    except Exception as exc:
        # CheckpointError / HomeDeadError / OSError all mean the surface cannot''',
)

sub(
    '''    board_drifts = _checkbox_drifts(board_text)
    phase_repairs = _state_phase_repairs(state, events, _board)
    gap = next((r["gap"] for r in phase_repairs if r.get("gap")), None)
''',
    '''    board_drifts = _checkbox_drifts(board_text)
    # T-1671: an unauthorized head is judged FIRST. Where it sends STATE idle,
    # the phase and next_action it replaces were typed by hand, and deriving a
    # repair from them would be reconciling toward a forgery.
    authority = _lifecycle_authority_repairs(state, _board, events, docs.get("_lifecycle"))
    phase_repairs = [] if authority["idle"] else _state_phase_repairs(state, events, _board)
    gap = next((r["gap"] for r in phase_repairs if r.get("gap")), None)
''',
)

sub(
    '''        + ([] if gap else _state_next_action_repairs(
            state, state_text, board_text, agent, project_root, resolve_next_action
        ))
    )
''',
    '''        + ([] if gap or authority["idle"] else _state_next_action_repairs(
            state, state_text, board_text, agent, project_root, resolve_next_action
        ))
    )
    if authority["state"]:
        _owned_fields = {repair["field"] for repair in authority["state"]}
        state_repairs = [
            repair for repair in state_repairs if repair.get("field") not in _owned_fields
        ] + authority["state"]
''',
)

sub(
    '''    lifecycle_all = _board_lifecycle_repairs(
        _board, events, state, docs.get("_history")
    )
''',
    '''    lifecycle_all = _board_lifecycle_repairs(
        _board, events, state, docs.get("_history")
    )
    if authority["board"]:
        _reopened = {repair["ticket"] for repair in authority["board"]}
        lifecycle_all = [
            repair for repair in lifecycle_all if repair.get("ticket") not in _reopened
        ] + authority["board"]
''',
)

sub(
    '''    if gap and gap.get("restart"):
        description += (
            f"; current-done-unproven {gap['ticket']}: closure revoked now; "
            "no lifecycle phase proven, queued TODO for fresh claim and verification"
        )
''',
    '''    if gap and gap.get("restart"):
        description += (
            f"; current-done-unproven {gap['ticket']}: closure revoked now; "
            "no lifecycle phase proven, queued TODO for fresh claim and verification"
        )
    if authority["trace"]:
        description += "; " + authority["trace"]
''',
)

p.write_bytes((t.replace("\n", "\r\n") if crlf else t).encode("utf-8"))
print("reconcile.py patched; crlf", crlf)


# --- second pass: preserve the exact pre-repair bytes of an unauthorized head ---
b = p.read_bytes()
crlf = b"\r\n" in b
t = b.decode("utf-8").replace("\r\n", "\n")
sub(
    """    if gap:
        from .journal import hash_bytes
        from .plan import TargetPlan

        # Preserve evidence before canonical writes, including crash prefixes.
""",
    """    if gap or authority["trace"]:
        from .journal import hash_bytes
        from .plan import TargetPlan

        # Preserve evidence before canonical writes, including crash prefixes.
        # T-1671: an unauthorized head is the same obligation -- the bytes an
        # executor typed are the only record of what it claimed.
""",
)
p.write_bytes((t.replace("\n", "\r\n") if crlf else t).encode("utf-8"))
print("reconcile.py second pass; crlf", crlf)

"""Core operations: claim / transition / checkpoint / ticket lifecycle /
goal / stop (NITRO M3-M5, integrity-repaired).

Every operation is PLAN / APPLY separated around an immutable OperationPlan.

PLAN reads the project snapshot, validates the request, computes the intended
exact bytes for every target (encoding already applied by the codec), and
returns the plan -- writing ZERO bytes. `--dry-run` renders the plan and
nothing else.

APPLY consumes THAT plan object under the writer lock: runs Recovery
preflight, re-checks every declared precondition against the live files
(STALE_STATE refusal), journals PREPARED, applies the ordered targets, verifies
the written result, and only then marks VERIFIED + COMMITTED. The plan's op_id
is the applied op_id; the plan's bytes are the committed bytes. A commit
failure always wins over the semantic success metadata.

STATE is mutated ONLY through owned-field patches (state.patch_state): every
operation declares exactly which keys it owns, everything else is preserved.
There is no `_render_state` anymore.
"""

from __future__ import annotations

import json
import re
import datetime
import uuid
from pathlib import Path

from . import codec, phases
from .board import (_claim_is_live, claim_status, escape_ticket_description,
                     parse_board, remove_ticket_field, set_ticket_field,
                     ticket_has_blocker, ticket_is_workable)
from .fast_check import validate_texts
from .journal import hash_bytes
from .log import build_event
from .plan import OperationPlan, TargetPlan, apply_plan, build_plan
from .result import Result
from .state import (parse_state, patch_state, transition_execution_intent,
                     is_legal_wait)

_TAXONOMIES = {"DEC", "RUN"}


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%d.%m.%y %H:%M")


def uuid4_hex() -> str:
    return uuid.uuid4().hex


def _utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")



class StateMalformedError(ValueError):
    """Raised when STATE.md is present but cannot be parsed whole.

    Mutators MUST fail closed with VALIDATION_FAILED/state-malformed and
    zero canonical writes; a corrupt STATE may never silently mutate as if
    it were the empty dict (T-1003 hostile findings).
    """


class CheckpointError(ValueError):
    """The checkpoint is not loadable as canonical SAIPEN state.

    Raised by the canonical checkpoint loader BEFORE any decode/parse when a
    `.saipen/` is missing STATE.md/BOARD.md/LOG.md, or any carries a
    non-canonical encoding (UTF-16/BOM). Surfaces as VALIDATION_FAILED with
    zero canonical writes (T-1003 / P1#3, P1#4).
    """


class HomeDeadError(ValueError):
    """`STATE.saipen_home` names an absolute path that is not a SAIPEN install.

    The bootloader cannot load the protocol the checkpoint was written against
    (CORE § 1.2), so an ORDINARY mutation must refuse with HOME_REQUIRED and
    zero canonical writes. `saipen rebind-home` is the ONE operation allowed to
    repair the dead pointer, and it does so only after proving an explicitly
    named candidate (hostile-regression, P0#3).
    """


def _state_guard(fn):
    """Convert a checkpoint/STATE raise into the operation's structured refusal.

    Every PUBLIC mutator must surface VALIDATION_FAILED with zero canonical
    writes when the checkpoint is missing/non-canonical (CheckpointError) or
    STATE.md is present but unparseable (StateMalformedError). One decorator,
    one refusal shape. A DEAD persisted `saipen_home` is a different failure
    with a different repair, so it carries its own code (HOME_REQUIRED) and
    names `saipen rebind-home` (hostile-regression, P0#3).
    """
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except HomeDeadError as exc:
            return _refuse(
                "HOME_REQUIRED", str(exc),
                next_action="saipen rebind-home <candidate-home-path>")
        except (StateMalformedError, CheckpointError) as exc:
            return _refuse("VALIDATION_FAILED", str(exc))
    return wrapper


def _read(root: Path, *,
          allow_dead_home: bool = False) -> tuple[dict, dict, dict, dict]:
    """Read STATE/BOARD/LOG docs + their parsed forms (normalised view).

    The canonical checkpoint loader: every canonical file MUST exist and be
    plain UTF-8 without a BOM, and STATE must actually parse, BEFORE any
    decode/parse/write. A missing or non-canonical file raises CheckpointError
    (VALIDATION_FAILED, zero canonical writes); an empty or unparseable STATE
    raises the same shape so a corrupt checkpoint can never reach patch_state
    and leak a ValueError traceback through the public CLI (T-1003 / P1#4)."""
    load_problem = codec.checkpoint_preflight(root)
    if load_problem is not None:
        raise CheckpointError(load_problem)
    state_doc = codec.read_document(root / ".saipen" / "STATE.md")
    board_doc = codec.read_document(root / ".saipen" / "BOARD.md")
    log_doc = codec.read_document(root / ".saipen" / "LOG.md")
    if not state_doc.text_norm.strip():
        raise CheckpointError(
            "STATE.md is empty -- not a usable checkpoint; a checkpoint needs "
            "a parsed frontmatter fence")
    from .state import parse_state_or_error
    state, state_error = parse_state_or_error(state_doc.text_norm)
    if state_error:
        raise StateMalformedError(f"state-malformed: {state_error}")
    board = parse_board(board_doc.text_norm)
    from .log import read_history_snapshot, snapshot_contract_errors
    from .state import persisted_home_error, running_home
    # The PERSISTED bootloader pointer is validated as a POINTER, separately
    # from the running install that owns VERSION/schema/STYLE
    # (hostile-regression, P0#3). A dead absolute `saipen_home` means the
    # protocol this checkpoint was written against cannot be loaded here, so
    # every ORDINARY mutation refuses BEFORE journaling; `rebind-home` passes
    # allow_dead_home=True because repairing that pointer is its whole job.
    if not allow_dead_home:
        home_problem = persisted_home_error(state.get("saipen_home"))
        if home_problem is not None:
            raise HomeDeadError(
                f"home-dead: {home_problem} -- the bootloader cannot load the "
                f"protocol this checkpoint names, so ordinary mutation is "
                f"refused; repair it with `saipen rebind-home "
                f"<candidate-home-path>`")
    # ONE strict complete-history snapshot before any planning
    # (hostile-regression, P0#2). The SAME pass supplies the immutable-ledger
    # verdict and the E-ID tail, so a mutation is planned against exactly the
    # evidence that was validated -- never a second, possibly different read.
    #
    # A void/forged sealed+active LOG (duplicate E-IDs, a dangling or
    # non-decreasing parent edge, out-of-order events, an illegal line) would
    # otherwise let a mutation PLAN against a trusted record that does not
    # exist. Refuse before journaling, zero canonical writes; `fast_check`
    # applies the same contract so live verification FAILs it too.
    #
    # Scoped to THIS install's OWN project (its `saipen_home` resolves to the
    # running install): that is the immutable ledger the audit defends
    # (LOG-001..013). Sub-instance and foreign-home projects carry their own
    # histories validated by the sub contract (subs.py), and rejecting theirs
    # here would abort legitimate sub collection -- the running install is the
    # only home whose ledger it is the authority for.
    snapshot = read_history_snapshot(root)
    _home = state.get("saipen_home")
    if (_home and str(_home).strip() and Path(str(_home)).is_absolute()
            and Path(str(_home)).resolve() == running_home()):
        history_problems = snapshot_contract_errors(snapshot)
        if history_problems:
            raise CheckpointError(
                "history-void: complete LOG history fails the immutable-ledger "
                "contract -- " + "; ".join(history_problems[:4]))
    log_tail = snapshot.tail
    # ALWAYS bind the complete sealed history (`.saipen/logs` numeric segments)
    # as a read precondition so APPLY rechecks it under the lock and refuses
    # STALE_STATE the moment a sealed segment is altered between PLAN and APPLY
    # (hostile-regression, P0#2). `hash_tree_dependency` pins the miss case to
    # the `tree-missing-v1` sentinel (never a conditional hash_tree()/None skip,
    # which is exactly how a fabricated sealed log was once admitted).
    _logs_dir = root / ".saipen" / "logs"
    from .journal import hash_tree_dependency
    _logs_digest = hash_tree_dependency(_logs_dir)
    return ({"state": state_doc, "board": board_doc, "log": log_doc,
             "_logs_digest": _logs_digest},
            state, board, log_tail)


def _target(doc, path: str, role: str, new_text: str) -> TargetPlan:
    """One planned write target: exact bytes + before/after hashes computed
    from the read document and the planned content."""
    return TargetPlan(path, role, doc.encode(new_text), doc.raw_hash,
                      hash_bytes(doc.encode(new_text)))


def _docs_preconditions(docs: dict, *keys: str) -> dict:
    pc = {f".saipen/{key.upper()}.md": docs[key].raw_hash for key in keys}
    # The complete sealed LOG history (hostile-regression, P0#2): bound as a
    # read precondition so APPLY rechecks it under the lock. Never a write
    # target, so it stays a read-only dependency and is rechecked even when no
    # canonical file is written.
    _ld = docs.get("_logs_digest")
    if _ld:
        pc[".saipen/logs"] = _ld
    return pc


def _event_line(docs: dict, log_tail: int | None, taxonomy: str,
                ticket: str | None, agent: str, message: str,
                now: str, op_id: str | None = None) -> tuple[int, str]:
    if taxonomy not in _TAXONOMIES:
        raise ValueError(f"taxonomy {taxonomy!r} outside {_TAXONOMIES}")
    return build_event(log_tail, taxonomy, message, ticket=ticket,
                       agent=agent, now=now, op_id=op_id)


def _refuse(code: str, detail: str = "", **extra) -> Result:
    return Result(ok=False, code=code, message=detail, data=extra)


def _iter_operation_records(root: Path):
    """Yield every parseable operation.json under .saipen/recovery/ops."""
    ops = root / ".saipen" / "recovery" / "ops"
    if not ops.is_dir():
        return
    for op_dir in sorted(ops.iterdir()):
        manifest = op_dir / "operation.json"
        if not manifest.is_file():
            continue
        try:
            record = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        yield record


def _strict_created_at(value: object) -> str:
    """Strict ISO-8601 UTC timestamp (Z or +00:00, utcoffset() == 0), or '' when
    invalid. Delegated to the ONE shared strict-UTC parser (P1#5): a non-zero
    offset stamp is NOT UTC and must refuse, never silently pass."""
    from .board import strict_iso_utc
    return strict_iso_utc(value)


def _convergence_event_number(record: dict) -> int:
    """The monotonic LOG event id a convergence receipt committed under."""
    meta = record.get("receipt_metadata") or {}
    match = re.match(r"E-(\d+)", str(meta.get("event_id") or ""))
    return int(match.group(1)) if match else -1


def _latest_convergence_stage(root: Path, stage: str) -> dict | None:
    """The latest COMMITTED convergence_stage receipt for one stage, ordered
    by the monotonic LOG event (same-second receipts must still order)."""
    out = None
    for record in _iter_operation_records(root):
        meta = record.get("receipt_metadata") or {}
        if record.get("operation") != "convergence_stage":
            continue
        if record.get("status") != "COMMITTED":
            continue
        if not _strict_created_at(record.get("created_at")):
            continue
        if meta.get("stage") != stage:
            continue
        if _convergence_event_number(record) < 0:
            continue
        if out is None or _convergence_event_number(record) > \
                _convergence_event_number(out):
            out = record
    return out


# --------------------------------------------------------------------------- claim

def _claim_fields_in_place(board_text: str, ticket_id: str,
                            fields: dict[str, str]) -> str:
    """Surgically set/overwrite owner/claim_time on the EXISTING DOING ticket
    line in place -- no second ticket, no duplicated fields (P0#2 adoption).

    Uses board.set_ticket_field, which replaces an existing field value rather
    than appending a duplicate and refuses (via _reject_duplicate_fields) a
    malformed line that already repeats the field. Every other field on the
    line is preserved byte-for-byte.
    """
    parsed = parse_board(board_text)
    ticket = parsed["tickets"].get(ticket_id)
    if ticket is None or ticket.get("section") != "## DOING":
        raise ValueError(f"{ticket_id} is not a ## DOING ticket")
    raw = ticket["raw"]
    new = raw
    for key, value in fields.items():
        new = set_ticket_field(new, key, value)
    lines = board_text.splitlines(keepends=True)
    idx = ticket["line_no"] - 1
    suffix = "\n" if lines[idx].endswith("\n") else ""
    lines[idx] = new + suffix
    return "".join(lines)


def _refresh_active_claim(board_text: str, state: dict, agent: str,
                          utc: str) -> tuple[str | None, str | None]:
    """If the active ticket is this agent's own SELF claim, advance its
    claim_time in place on BOARD. Returns (new_board_text | None, ticket_id).

    Used by checkpoint/transition so an actively worked ticket never becomes
    legally stale while its owner checkpoints/transitions (CORE § 1.4). A
    foreign/unclaimed/non-owned DOING is NOT touched -- adoption is a separate
    `claim T` action, not a side effect of unrelated mutations.
    """
    if state.get("phase") not in phases.TICKET_BEARING_PHASES:
        return None, None
    active = state.get("task")
    if not active or active == "none":
        return None, None
    tickets = parse_board(board_text)["tickets"]
    ticket = tickets.get(active)
    if ticket is None or ticket.get("section") != "## DOING":
        return None, None
    if claim_status(ticket, agent) != "SELF":
        return None, None
    return _claim_fields_in_place(board_text, active, {"claim_time": utc}), active


def _plan_claim(root: Path, ticket_id: str, agent: str, now: str, utc: str,
               explicit: bool = False) -> OperationPlan | Result:
    op_id = "claim-" + uuid4_hex()
    docs, state, board, log_tail = _read(root)
    if board["errors"]:
        return _refuse("VALIDATION_FAILED",
                       "BOARD parse error(s): " + "; ".join(board["errors"][:3]),
                       ticket=ticket_id)
    tickets = board["tickets"]
    if ticket_id not in tickets:
        return _refuse("TICKET_NOT_FOUND", f"{ticket_id} not on the board",
                       ticket=ticket_id)
    ticket = tickets[ticket_id]
    if ticket_has_blocker(ticket):
        return _refuse(
            "TICKET_NOT_WORKABLE",
            f"{ticket_id} carries a blocker; explicit priority override does "
            "not override authorization",
            ticket=ticket_id,
        )
    section = ticket["section"]
    cs = claim_status(ticket, agent, None)

    if section == "## DOING":
        # In-place adoption / lease refresh -- never a second ticket or
        # duplicated fields (P0#2 / CORE § 1.4 stale/unclaimed adoption).
        if cs == "FOREIGN_LIVE":
            return _refuse("TICKET_NOT_WORKABLE",
                           f"{ticket_id} is actively claimed by another agent "
                           f"({ticket['fields'].get('owner', '')}); a live "
                           f"foreign claim cannot be taken over",
                           ticket=ticket_id)
        if cs == "INVALID":
            return _refuse("VALIDATION_FAILED",
                           f"{ticket_id} carries an INVALID claim (half "
                           f"owner/claim_time pair or non-UTC stamp); repair "
                           f"before claiming", ticket=ticket_id)
        if cs == "SELF":
            # BOARD-only lease refresh: advance claim_time in place. No LOG, no
            # STATE change -- the owner and binding are unchanged.
            new_board = _claim_fields_in_place(
                docs["board"].text_norm, ticket_id, {"claim_time": utc})
            errors = validate_texts(docs["state"].text_norm, new_board,
                                    docs["log"].text_norm)
            if errors:
                return _refuse("VALIDATION_FAILED",
                               "proposed state fails fast validation: "
                               + "; ".join(errors[:5]))
            targets = [_target(docs["board"], ".saipen/BOARD.md", "board",
                               new_board)]
            return build_plan(
                "claim", agent, _identity(root),
                {"operation": "claim", "ticket": ticket_id, "agent": agent,
                 "explicit": explicit, "refresh": True},
                _docs_preconditions(docs, "state", "board", "log"),
                targets,
                {"ok": True, "code": "CLAIMED", "ticket": ticket_id,
                 "refresh": True,
                 "detail": "lease refreshed (claim_time advanced)"},
                op_id=op_id)
        # UNCLAIMED or FOREIGN_STALE -> adopt / take over in place.
        # FOREIGN_STALE is a TAKEOVER of another agent's lapsed claim, so the
        # DEC payload must record who it was taken from and the staleness that
        # authorized the takeover (hostile-regression, P1#8) -- an ordinary
        # UNCLAIMED adoption records only the new owner. Splitting the payload
        # keeps the ledger's takeover audit distinct from fresh adoption.
        if cs == "FOREIGN_STALE":
            _old_owner = (ticket["fields"].get("owner") or "").strip()
            _prior_claim = (ticket["fields"].get("claim_time") or "").strip()
            _msg = (f"claimed via SAIOPS -- took over STALE claim from "
                    f"{_old_owner} (prior claim_time {_prior_claim}); owner "
                    f"{agent}")
        else:
            _msg = f"claimed via SAIOPS -- owner {agent}"
        event, line = _event_line(docs, log_tail, "DEC", ticket_id, agent,
                                    _msg, now, op_id)
        new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
        new_board = _claim_fields_in_place(
            docs["board"].text_norm, ticket_id,
            {"owner": agent, "claim_time": utc})
        owned = {
            "phase": "SCOUT",
            "task": ticket_id,
            "next_action": f"PHASE SCOUT {ticket_id}",
            "transition_from": state.get("phase") or "DONE",
            "last_event": event,
            "updated": utc,
            "agent": agent,
        }
        new_state = patch_state(docs["state"].text_norm, owned)
        errors = validate_texts(new_state, new_board, new_log)
        if errors:
            return _refuse("VALIDATION_FAILED",
                           "proposed state fails fast validation: "
                           + "; ".join(errors[:5]))
        targets = [
            _target(docs["log"], ".saipen/LOG.md", "log", new_log),
            _target(docs["board"], ".saipen/BOARD.md", "board", new_board),
            _target(docs["state"], ".saipen/STATE.md", "state", new_state),
        ]
        return build_plan(
            "claim", agent, _identity(root),
            {"operation": "claim", "ticket": ticket_id, "agent": agent,
             "explicit": explicit, "adopt": True},
            _docs_preconditions(docs, "state", "board", "log"),
            targets,
            {"ok": True, "code": "CLAIMED", "ticket": ticket_id,
             "event_id": f"E-{event}", "phase": "SCOUT",
             "next_action": f"PHASE SCOUT {ticket_id}", "adopted": True},
            op_id=op_id)

    if section != "## TODO":
        return _refuse("TICKET_NOT_WORKABLE",
                       f"{ticket_id} is under {section}", ticket=ticket_id)
    if ticket["checkbox"] not in (" ", ""):
        return _refuse("TICKET_NOT_WORKABLE",
                        f"{ticket_id} is [{ticket['checkbox']}] but sits under "
                        f"## TODO -- checkbox/section disagreement is malformed "
                        f"input and cannot be claimed",
                        ticket=ticket_id)
    # A claim (owner/claim_time) on a TODO is INACTIVE history: CORE's claim
    # truth lives in DOING, so a stale pair left by a block/unblock cycle must
    # not make the ticket non-workable (hostile-regression, P1#5). A half/bad
    # (INVALID) pair still fails closed -- only a syntactically VALID foreign
    # claim is treated as inactive outside DOING.
    if cs == "INVALID":
        return _refuse("VALIDATION_FAILED",
                        f"{ticket_id} carries an INVALID claim (half "
                        f"owner/claim_time pair or non-UTC stamp)",
                        ticket=ticket_id)
    for need in ticket["needs"]:
        if need not in tickets or tickets[need]["section"] != "## DONE":
            return _refuse("TICKET_NOT_WORKABLE",
                           f"unmet needs: {need}", ticket=ticket_id)
    doing = [t for t in tickets.values() if t["section"] == "## DOING"]
    if doing:
        return _refuse("ALREADY_CLAIMED",
                       f"DOING holds {doing[0]['id']}", ticket=ticket_id)

    if not explicit:
        top_workable = None
        for t in tickets.values():
            if ticket_is_workable(t, tickets, agent=agent):
                top_workable = t["id"]
                break
        if top_workable is None or top_workable != ticket_id:
            return _refuse("NOT_TOP_WORKABLE",
                           f"topmost workable ticket is {top_workable or 'none'}, "
                           f"requested {ticket_id}; use the explicit-claim "
                           "flag to override with evidence",
                           ticket=ticket_id, top_workable=top_workable)

    event, line = _event_line(docs, log_tail, "DEC", ticket_id, agent,
                               f"claimed via SAIOPS -- owner {agent}", now,
                               op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    new_board = _claim_move(docs["board"].text_norm, ticket_id, agent, utc)
    owned = {
        "phase": "SCOUT",
        "task": ticket_id,
        "next_action": f"PHASE SCOUT {ticket_id}",
        "transition_from": state.get("phase") or "DONE",
        "last_event": event,
        "updated": utc,
        "agent": agent,
    }
    new_state = patch_state(docs["state"].text_norm, owned)

    errors = validate_texts(new_state, new_board, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed state fails fast validation: "
                       + "; ".join(errors[:5]))

    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["board"], ".saipen/BOARD.md", "board", new_board),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
    ]
    return build_plan(
        "claim", agent, _identity(root),
        {"operation": "claim", "ticket": ticket_id, "agent": agent,
         "explicit": explicit},
        _docs_preconditions(docs, "state", "board", "log"),
        targets,
        {"ok": True, "code": "CLAIMED", "ticket": ticket_id,
         "event_id": f"E-{event}", "phase": "SCOUT",
         "next_action": f"PHASE SCOUT {ticket_id}"},
        op_id=op_id)


def _claim_move(board_text: str, ticket_id: str, agent: str, utc: str) -> str:
    """Surgical claim move: target ticket TODO -> DOING with [/] owner."""
    lines = board_text.splitlines(keepends=True)
    out = []
    ticket_line = None
    doing_idx = None
    for line in lines:
        stripped = line.rstrip("\n")
        if stripped.startswith("- [ ] " + ticket_id + " "):
            ticket_line = stripped
            continue
        if stripped.startswith("## DOING"):
            doing_idx = len(out)
        out.append(line)
    if ticket_line is None or doing_idx is None:
        raise ValueError("cannot locate ticket or DOING section")
    # A claimed-then-blocked/unblocked TODO may still carry a previous
    # owner/claim_time pair (claim truth lives in DOING). Move must STRUCTURALLY
    # REPLACE the existing pair, never append a second one -- a duplicate field
    # is a parse error that rejects the whole board (hostile-regression, P1#5).
    marked = ticket_line.replace("- [ ] ", "- [/] ", 1).rstrip()
    marked = set_ticket_field(marked, "owner", agent)
    marked = set_ticket_field(marked, "claim_time", utc)
    out.insert(doing_idx + 1, marked + "\n")
    return "".join(out)


@_state_guard
def plan_claim(project_root: Path | str, ticket_id: str, agent: str,
               explicit: bool = False) -> Result:
    now, utc = _now(), _utc_iso()
    plan = _plan_claim(Path(project_root), ticket_id, agent, now, utc,
                       explicit=explicit)
    if isinstance(plan, Result):
        return plan
    return _render_plan(plan)


@_state_guard
def apply_claim(project_root: Path | str, ticket_id: str, agent: str,
                explicit: bool = False) -> Result:
    now, utc = _now(), _utc_iso()
    plan = _plan_claim(Path(project_root), ticket_id, agent, now, utc,
                       explicit=explicit)
    if isinstance(plan, Result):
        return plan
    return apply_plan(Path(project_root), plan)


# ------------------------------------------------------------ transition

def _plan_transition(root: Path, destination: str, agent: str,
                     ticket_id: str | None, event_text: str, now: str,
                     utc: str) -> OperationPlan | Result:
    destination = destination.upper()
    op_id = "transition-" + uuid4_hex()
    docs, state, board, log_tail = _read(root)
    current = state.get("phase")
    if destination not in phases.VALID_TRANSITIONS and \
            destination not in phases.ANY_FROM:
        return _refuse("ILLEGAL_TRANSITION",
                       f"{current} -> {destination}: destination outside the "
                       "phase enum", phase=destination)
    if not phases.transition_legal(current, destination):
        return _refuse("ILLEGAL_TRANSITION",
                       f"{current} -> {destination} is not a legal edge",
                       phase=destination)

    subject = None
    if destination in phases.TICKET_BEARING_PHASES:
        doing = [t for t in board["tickets"].values()
                 if t["section"] == "## DOING"]
        active = doing[0]["id"] if doing else None
        state_task = state.get("task")
        if active is None:
            return _refuse("ACTIVE_TICKET_MISMATCH",
                           f"{destination} is ticket-bearing but no ticket is "
                           "DOING", phase=destination)
        if state_task and active != state_task:
            return _refuse("ACTIVE_TICKET_MISMATCH",
                           f"STATE.task={state_task} but BOARD.DOING={active}",
                           phase=destination)
        if ticket_id is not None and ticket_id != active:
            if ticket_id not in board["tickets"]:
                return _refuse("TICKET_NOT_FOUND", f"{ticket_id} is not on "
                               "the board", ticket=ticket_id)
            return _refuse("ACTIVE_TICKET_MISMATCH",
                           f"requested ticket {ticket_id} != active DOING "
                           f"{active}; a ticket-bearing transition binds the "
                           "exact active DOING ticket", ticket=ticket_id)
        subject = active
        if subject not in board["tickets"]:
            return _refuse("TICKET_NOT_FOUND", f"active ticket {subject} "
                           "missing from the board", ticket=subject)

    if destination == "REVIEW" and current == "VERIFY":
        from .log import read_history_events, verification_evidence
        history_events = read_history_events(root)
        ok, reason = verification_evidence(subject, history_events)
        if not ok:
            return _refuse("INCOMPLETE_TICKET", f"VERIFY -> REVIEW requires explicit verification evidence for ticket {subject} (got: {reason})", phase=destination, ticket=subject)


    # Machine-owned marker (hostile-regression): the transition text is ALWAYS
    # `transition to {destination}` -- a caller-supplied reason is appended
    # after ` -- `, never replaces the marker. verification_evidence treats
    # the exact marker as the VERIFY boundary, so a replaced marker would
    # silently erase the ticket's verification cycle.
    marker = f"transition to {destination}"
    event_text = marker if not event_text else f"{marker} -- {event_text}"
    event, line = _event_line(docs, log_tail, "RUN", subject, agent,
                              event_text, now, op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    if destination in phases.TICKET_BEARING_PHASES:
        na = f"PHASE {destination} {subject}"
    else:
        na = f"PHASE {destination}"
    owned = {
        "phase": destination,
        "next_action": na,
        "transition_from": current,
        "last_event": event,
        "updated": utc,
        "agent": agent,
    }
    if destination == "DONE":
        owned["task"] = "none"
    new_state = patch_state(docs["state"].text_norm, owned)

    # Goal-counter mechanics (NITRO dogfood II, T-590): a VERIFY -> REVIEW
    # transition under execution_intent: goal is the contract point where a
    # ticket has passed VERIFY. The OPERATION owns the bookkeeping -- it
    # bumps goal_tickets, emits DEC: goal_tickets N->N+1, updates last_event,
    # and writes the WAIT when the valve trips. The model no longer has to
    # remember deterministic accounting.
    if (destination == "REVIEW" and current == "VERIFY"
            and state.get("execution_intent") == "goal"):
        tickets = int(state.get("goal_tickets") or 0)
        new_tickets = tickets + 1
        from .log import build_event as _build_event
        dec_event, dec_line = _build_event(
            event, "DEC",
            f"goal_tickets {tickets}->{new_tickets}", now=now, op_id=op_id)
        new_log = new_log.rstrip("\n") + "\n" + dec_line + "\n"
        cap_reached = new_tickets >= GOAL_TICKET_CAP
        owned["goal_tickets"] = new_tickets
        owned["last_event"] = dec_event
        if cap_reached:
            owned["next_action"] = (
                f"WAIT: safety valve reached ({state.get('goal_waves') or 0} "
                f"waves / {new_tickets} tickets) -- run 'saipen goal' to "
                "continue")
        new_state = patch_state(docs["state"].text_norm, owned)

    # Goal-wave mechanics (NITRO dogfood II, T-590): a HUNT -> ADD transition
    # under execution_intent: goal is the contract point where a
    # HUNT->ADD cycle completes (MAINTENANCE section 2.4). The operation owns
    # the bump: goal_waves N->N+1 with its DEC line, and the valve WAIT.
    elif (destination == "ADD" and current == "HUNT"
          and state.get("execution_intent") == "goal"):
        waves = int(state.get("goal_waves") or 0)
        new_waves = waves + 1
        from .log import build_event as _build_event
        wave_event, wave_line = _build_event(
            event, "DEC",
            f"goal_waves {waves}->{new_waves}", now=now, op_id=op_id)
        new_log = new_log.rstrip("\n") + "\n" + wave_line + "\n"
        cap_reached = new_waves >= GOAL_WAVE_CAP
        owned["goal_waves"] = new_waves
        owned["last_event"] = wave_event
        if cap_reached:
            owned["next_action"] = (
                f"WAIT: safety valve reached ({new_waves} waves / "
                f"{state.get('goal_tickets') or 0} tickets) -- run 'saipen "
                "goal' to continue")
        new_state = patch_state(docs["state"].text_norm, owned)

    # SELF-owned active ticket: refresh its claim lease in place (CORE § 1.4).
    # Target order LOG -> BOARD -> STATE.
    refreshed_board, _active = _refresh_active_claim(
        docs["board"].text_norm, state, agent, utc)
    new_board = refreshed_board if refreshed_board is not None \
        else docs["board"].text_norm

    errors = validate_texts(new_state, new_board, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed state fails fast validation: "
                       + "; ".join(errors[:5]))

    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
    ]
    if refreshed_board is not None:
        targets.append(_target(docs["board"], ".saipen/BOARD.md", "board",
                               new_board))
    targets.append(_target(docs["state"], ".saipen/STATE.md", "state",
                           new_state))
    expected = {"ok": True, "code": "TRANSITIONED", "phase": destination,
                "next_action": na, "event_id": f"E-{event}",
                "ticket": subject}
    if destination == "REVIEW" and current == "VERIFY" \
            and state.get("execution_intent") == "goal":
        expected["goal_tickets"] = int(state.get("goal_tickets") or 0) + 1
    return build_plan(
        "transition", agent, _identity(root),
        {"operation": "transition", "destination": destination,
         "ticket": subject, "agent": agent},
        _docs_preconditions(docs, "state", "board", "log"),
        targets,
        expected, op_id=op_id)


@_state_guard
def transition_phase(project_root: Path | str, destination: str,
                     agent: str, ticket_id: str | None = None,
                     event_text: str = "", dry_run: bool = False) -> Result:
    now, utc = _now(), _utc_iso()
    plan = _plan_transition(Path(project_root), destination, agent, ticket_id,
                            event_text, now, utc)
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(Path(project_root), plan)


# ------------------------------------------------------------- checkpoint

def _plan_checkpoint(root: Path, agent: str, taxonomy: str,
                      ticket_id: str | None, description: str,
                      now: str, utc: str) -> OperationPlan | Result:
    op_id = "checkpoint-" + uuid4_hex()
    docs, _state, _board, log_tail = _read(root)
    # A ticket-bearing checkpoint names a real ticket. The event is durable
    # LOG identity, so a non-existent / malformed ref would mint a [T-###]
    # that next_ticket_id later reissues and sweep linkage can never resolve
    # (hostile-regression, P1#3). Ticket-LESS session checkpoints stay legal.
    if ticket_id is not None:
        if not re.fullmatch(r"T-\d+", str(ticket_id)):
            return _refuse("VALIDATION_FAILED",
                           f"checkpoint ticket_id {ticket_id!r} is not a valid "
                           f"T-### ref (expected T-<digits>)", ticket=ticket_id)
        if ticket_id not in _board["tickets"]:
            return _refuse("TICKET_NOT_FOUND",
                           f"{ticket_id} is not on the board; a checkpoint may "
                           f"only name an existing ticket", ticket=ticket_id)
    event, line = _event_line(docs, log_tail, taxonomy.upper(), ticket_id,
                                agent, description, now, op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    owned = {
        "last_event": event,
        "updated": utc,
        "agent": agent,
    }
    new_state = patch_state(docs["state"].text_norm, owned)

    # SELF-owned active ticket: refresh its claim lease in place (CORE § 1.4)
    # so an actively worked ticket never goes legally stale while its owner
    # checkpoints. Target order LOG -> BOARD -> STATE.
    refreshed_board, _active = _refresh_active_claim(
        docs["board"].text_norm, _state, agent, utc)
    new_board = refreshed_board if refreshed_board is not None \
        else docs["board"].text_norm

    errors = validate_texts(new_state, new_board, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed state fails fast validation: "
                       + "; ".join(errors[:5]))

    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
    ]
    if refreshed_board is not None:
        targets.append(_target(docs["board"], ".saipen/BOARD.md", "board",
                               new_board))
    targets.append(_target(docs["state"], ".saipen/STATE.md", "state",
                           new_state))
    return build_plan(
        "checkpoint", agent, _identity(root),
        {"operation": "checkpoint", "taxonomy": taxonomy.upper(),
         "ticket": ticket_id, "description": description},
        _docs_preconditions(docs, "state", "board", "log"),
        targets,
        {"ok": True, "code": "CHECKPOINTED", "event_id": f"E-{event}"},
        op_id=op_id)


@_state_guard
def checkpoint(project_root: Path | str, agent: str, taxonomy: str,
               ticket_id: str | None, description: str,
               dry_run: bool = False) -> Result:
    if taxonomy.upper() not in _TAXONOMIES:
        return _refuse("VALIDATION_FAILED",
                       f"taxonomy {taxonomy!r} outside {sorted(_TAXONOMIES)}")
    now, utc = _now(), _utc_iso()
    plan = _plan_checkpoint(Path(project_root), agent, taxonomy, ticket_id,
                            description, now, utc)
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(Path(project_root), plan)


# ---------------------------------------------------------- ticket numbers

# BOARD canonical ticket-line shape: a list item whose text starts with the
# checkbox and an uppercase T-NNN. Only these lines are ticket IDENTITY --
# prose that merely mentions "T-900000" in a description or verify clause is
# not a ticket record (T-639/§9).
_BOARD_TICKET_LINE_RE = re.compile(
    r"^-\s*\[[ x/]\]\s*T-(\d+)\b")


def next_ticket_id(board_text: str, log_text: str) -> int:
    """The next canonical production ticket ID, from STRUCTURED records only
    (T-639/§9): canonical BOARD ticket lines (`- [ ] T-###`) and the LOG's
    structured `[T-###]` event field. Prose that merely mentions a T-NNN --
    in a ticket description, a verify clause, or LOG message text -- is never
    ticket identity, so a fixture note like "synthetic T-990" or a
    prose-mentioned T-777 cannot poison allocation. The tiny synthetic-id
    exclusion set is gone; structure is what keeps fixtures out.

    `log_text` MUST be the canonical COMPLETE history (sealed segments +
    active LOG.md, `log.read_history`), the same source E-IDs allocate from:
    a sealed segment's [T-###] is durable ticket identity and must never be
    reissued (T-1003)."""
    ids: set[int] = set()
    for line in board_text.splitlines():
        match = _BOARD_TICKET_LINE_RE.match(line.strip())
        if match:
            ids.add(int(match.group(1)))
    from .log import parse_log_line
    for line in log_text.splitlines():
        parsed = parse_log_line(line)
        if parsed is not None and parsed["ticket"]:
            match = re.fullmatch(r"T-(\d+)", parsed["ticket"])
            if match:
                ids.add(int(match.group(1)))
    return (max(ids, default=0) + 1) if ids else 1


def _insert_todo(board_text: str, line: str) -> str:
    lines = board_text.splitlines(keepends=True)
    todo_idx = next(i for i, ln in enumerate(lines)
                    if ln.startswith("## TODO"))
    lines.insert(todo_idx + 1, line + "\n")
    return "".join(lines)


def _ticket_targets(root: Path, action: str, ticket_id: str, agent: str,
                    payload: str, now: str, utc: str) -> OperationPlan | Result:
    op_id = "ticket-" + uuid4_hex()
    docs, state, board, log_tail = _read(root)
    if board["errors"]:
        return _refuse("VALIDATION_FAILED",
                       "BOARD parse error(s): " + "; ".join(board["errors"][:3]),
                       ticket=ticket_id)
    tickets = board["tickets"]
    if ticket_id not in tickets:
        return _refuse("TICKET_NOT_FOUND", f"{ticket_id} not on the board",
                       ticket=ticket_id)
    ticket = tickets[ticket_id]

    if action == "done":
        # `done` is the atomic finish operation, never a raw section move
        # (NITRO dogfood III, T-591); the split it used to leave is now a
        # corruption the fast binding rejects.
        return _refuse("ILLEGAL_TICKET_LIFECYCLE",
                       "done is the atomic finish operation; use finish_ticket "
                       "or `saipen ticket done` (it closes LOG+BOARD+STATE "
                       "together)", ticket=ticket_id)
    elif action == "block":
        if not payload or not payload.strip():
            return _refuse("VALIDATION_FAILED",
                           "block requires the facts/dead ends that justify "
                           "the block", ticket=ticket_id)
        if ticket["section"] not in ("## DOING", "## TODO"):
            return _refuse("ILLEGAL_TICKET_LIFECYCLE",
                           f"block accepts DOING or TODO; {ticket_id} is "
                           f"under {ticket['section']}", ticket=ticket_id)
        target_section, checkbox = "## BLOCKED", "[ ]"
    elif action == "unblock":
        if not payload or not payload.strip():
            return _refuse("VALIDATION_FAILED",
                           "unblock requires the decision/evidence that "
                           "lifts the block", ticket=ticket_id)
        if ticket["section"] != "## BLOCKED":
            return _refuse("ILLEGAL_TICKET_LIFECYCLE",
                           f"unblock accepts only BLOCKED; {ticket_id} is "
                           f"under {ticket['section']}", ticket=ticket_id)
        target_section, checkbox = "## TODO", "[ ]"
    else:
        return _refuse("VALIDATION_FAILED", f"unknown ticket action {action!r}")

    new_board = _move_ticket(docs["board"].text_norm, ticket_id,
                             target_section, checkbox, action, payload)
    # Blocking the ACTIVE DOING ticket parks the current work: the ticket
    # leaves ## DOING, so the execution state must not keep naming it in a
    # ticket-bearing phase, and the block MUST NOT become a session-level
    # phase: BLOCKED -- that state is reserved for when no ticket anywhere is
    # workable (CORE.md § 1.11), carries its own STATE.blocker + WAIT, and
    # contradicts a running goal intent. The block therefore neutralizes the
    # execution state to DONE/task none (the same no-active-ticket form
    # finish_ticket uses) and routes the next_action from the RESULTING
    # board. Blocking a merely-TODO ticket leaves execution state untouched.
    # The ACTIVE case must be provable from the LOG alone: the block event
    # carries an explicit (active) marker so the validator's block-park
    # exception can never be satisfied by a TODO-ticket block event.
    is_active_block = (action == "block"
                       and state.get("task") == ticket_id
                       and ticket["section"] == "## DOING"
                       and state.get("phase") in phases.TICKET_BEARING_PHASES)
    if (action == "block" and ticket["section"] == "## DOING"
            and not is_active_block):
        return _refuse("ILLEGAL_TICKET_LIFECYCLE",
                       f"blocking DOING ticket {ticket_id} requires a "
                       f"ticket-bearing source phase "
                       f"({', '.join(sorted(phases.TICKET_BEARING_PHASES))}); "
                       f"STATE is {state.get('phase')!r} with task "
                       f"{state.get('task')!r}", ticket=ticket_id)
    event, line = _event_line(docs, log_tail, "DEC", ticket_id, agent,
                              f"ticket {action} via SAIOPS"
                              + (" (active)" if is_active_block else "")
                              + (f" -- {payload}" if payload else ""), now,
                              op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    owned = {
        "last_event": event,
        "updated": utc,
        "agent": agent,
    }
    if is_active_block:
        if not state.get("phase"):
            return _refuse("VALIDATION_FAILED",
                           "blocking the active ticket needs a real source "
                           "phase; STATE carries none, so transition_from "
                           "would be fabricated",
                           ticket=ticket_id)
        owned["phase"] = "DONE"
        owned["task"] = "none"
        if str(state.get("next_action") or "").startswith("WAIT:"):
            owned["next_action"] = state.get("next_action")
        else:
            owned["next_action"] = "saipen continue"
        owned["transition_from"] = state.get("phase")
    new_state = patch_state(docs["state"].text_norm, owned)
    # Routing after a structural move must not walk over a hard stop: a
    # safety-valve or user WAIT is preserved, never replaced by a fresh pick.
    # Unblock also re-routes, because moving a line back into ## TODO changes
    # the topmost-workable order the neutral state's next_action points at.
    from .router import route_next
    if action in ("block", "unblock") \
            and not str(state.get("next_action") or "").startswith("WAIT:"):
        _neutral = (state.get("task") in (None, "none")
                    and not any(t["section"] == "## DOING"
                                for t in parse_board(new_board)["tickets"].values()))
        if _neutral or is_active_block:
            routed = route_next(new_state, new_board)
            if routed.get("ok"):
                new_state = patch_state(new_state,
                                        {"next_action": routed["action"]})

    errors = validate_texts(new_state, new_board, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed state fails fast validation: "
                       + "; ".join(errors[:5]))

    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["board"], ".saipen/BOARD.md", "board", new_board),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
    ]
    return build_plan(
        "ticket_move", agent, _identity(root),
        {"operation": "ticket_move", "action": action, "ticket": ticket_id},
        _docs_preconditions(docs, "state", "board", "log"),
        targets,
        {"ok": True, "code": action.upper(), "ticket": ticket_id,
         "event_id": f"E-{event}"}, op_id=op_id)


def _plan_finish_ticket(root: Path, ticket_id: str, agent: str, now: str,
                        utc: str, digest_text: str | None = None,
                        digest_done: str | None = None,
                        digest_awaiting: str | None = None,
                        prefix_run: str | None = None,
                        ) -> OperationPlan | Result:
    """PLAN the ONE atomic ticket-closure operation (NITRO dogfood III).

    Closing a ticket is a cross-file transaction, not choreography: the split
    `transition state; move board ticket; repair next_action` leaves BOARD
    DONE[x] while STATE still names the ticket in a ticket-bearing phase --
    the exact corruption reproduced in DOGFOOD III. ONE OperationPlan owns:

    LOG:   ticket completion event (and, for a release closure, ONE truthful
           RUN event emitted immediately before it -- `prefix_run`, T-994 /
           § 15 -- so the release evidence is written by the SAME canonical
           LOG machinery, never a second writer, and the journal carries a
           single LOG target recovery can verify)
    BOARD: DOING -> DONE, [/] -> [x]
    STATE: phase -> DONE, task -> none, transition_from -> SHIP (the ACTUAL
           previous phase), last_event -> completion event, updated, agent
    NEXT:  computed from the resulting proposed state by the shared router.

    GATE PRECONDITION (NITRO dogfood IV, T-602): the ordinary ticket
    completion requires the ticket to have actually passed its required
    gates -- STATE.phase MUST be SHIP, STATE.task MUST be the ticket, and
    exactly one BOARD.DOING MUST be the ticket. From SCOUT/BUILD/VERIFY/
    REVIEW the finish REFUSEs ILLEGAL_PHASE with zero canonical bytes
    written. `transition_from` records the ACTUAL previous phase -- never a
    fabricated legal-looking DONE source. The SHIP gate cannot be skipped by
    laundering the phase history into a legal-looking final STATE.

    Required preconditions: exactly one BOARD.DOING, STATE.task == that
    ticket, ticket identity matches. No split-state window exists.
    """
    op_id = "finish-" + uuid4_hex()
    docs, state, board, log_tail = _read(root)
    if board["errors"]:
        return _refuse("VALIDATION_FAILED",
                       "BOARD parse error(s): " + "; ".join(board["errors"][:3]),
                       ticket=ticket_id)
    tickets = board["tickets"]
    if ticket_id not in tickets:
        return _refuse("TICKET_NOT_FOUND", f"{ticket_id} not on the board",
                       ticket=ticket_id)
    ticket = tickets[ticket_id]
    if ticket["section"] != "## DOING" or ticket["checkbox"] != "/":
        return _refuse("ILLEGAL_TICKET_LIFECYCLE",
                       f"finish accepts only a ## DOING [/] ticket; "
                       f"{ticket_id} is {ticket['section']} "
                       f"[{ticket['checkbox']}]", ticket=ticket_id)
    doing = [t for t in tickets.values() if t["section"] == "## DOING"]
    if len(doing) != 1:
        return _refuse("ACTIVE_TICKET_MISMATCH",
                       f"finish needs exactly one ## DOING ticket, found "
                       f"{len(doing)}", ticket=ticket_id)
    if state.get("task") != ticket_id:
        return _refuse("ACTIVE_TICKET_MISMATCH",
                       f"STATE.task={state.get('task')} != finished ticket "
                       f"{ticket_id}", ticket=ticket_id)
    
    from .log import read_history_events, verification_evidence
    history_events = read_history_events(root)
    ok, reason = verification_evidence(ticket_id, history_events)
    if not ok:
        return _refuse("INCOMPLETE_TICKET", f"finish requires explicit verification evidence for ticket {ticket_id} (got: {reason})", ticket=ticket_id)

    prev_phase = state.get("phase") or "DONE"

    # GATE: the canonical closure is SHIP -> DONE (CORE section 1.6). A
    # ticket may only be closed after its required gates (SCOUT/BUILD/VERIFY/
    # REVIEW/SHIP) actually ran in a legal path. The DFA makes SHIP reachable
    # only from REVIEW, and every transition is journaled, so requiring
    # phase == SHIP here IS the gate proof. Refusing from any earlier phase
    # with zero canonical bytes written is what makes skipped gates
    # mechanically impossible (NITRO dogfood IV, T-602).
    if prev_phase != "SHIP":
        return _refuse(
            "ILLEGAL_PHASE",
            f"finish requires phase SHIP (the canonical closure edge "
            f"SHIP -> DONE); actual phase {prev_phase} cannot close a ticket "
            "without its required REVIEW/SHIP gates. Run the ticket through "
            "REVIEW then SHIP first; the gates cannot be skipped by "
            "laundering the phase history",
            ticket=ticket_id, phase=prev_phase)
    closure_from = prev_phase  # the ACTUAL phase: SHIP.

    # One LOG completion event naming the ACTUAL closure phase -- the event
    # is the provenance that the gate chain actually ended at SHIP.
    if prefix_run:
        # ONE truthful RUN event emitted immediately before the completion
        # event, both through the canonical LOG builder (T-994 / § 15). The
        # journal then carries a SINGLE LOG target whose after-bytes recovery
        # can verify -- a second sequential LOG target would defeat per-target
        # before/after classification.
        run_event, run_line = build_event(
            log_tail, "RUN", prefix_run, ticket=ticket_id, agent=agent,
            now=now, op_id=op_id)
        event, line = build_event(
            run_event, "DEC",
            f"ticket finished via SAIOPS -- completion (from {prev_phase})",
            ticket=ticket_id, agent=agent, now=now, op_id=op_id)
        new_log = (docs["log"].text_norm.rstrip("\n") + "\n" + run_line
                   + "\n" + line + "\n")
    else:
        event, line = _event_line(docs, log_tail, "DEC", ticket_id, agent,
                                  f"ticket finished via SAIOPS -- completion "
                                  f"(from {prev_phase})", now, op_id)
        new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"

    # BOARD: DOING -> DONE, [/] -> [x], preserve all other fields.
    new_board = _move_ticket(docs["board"].text_norm, ticket_id, "## DONE",
                             "[x]", "done", "")

    # STATE: phase -> DONE, task -> none, transition_from -> the ACTUAL
    # previous phase (SHIP), and the next_action computed from the RESULTING
    # proposed state.
    owned = {
        "phase": "DONE",
        "task": "none",
        "next_action": "saipen continue",
        "transition_from": closure_from,
        "last_event": event,
        "updated": utc,
        "agent": agent,
    }
    new_state = patch_state(docs["state"].text_norm, owned)
    from .router import route_next
    routed = route_next(new_state, new_board)
    if routed.get("ok") and routed.get("action") != "saipen continue":
        new_state = patch_state(new_state, {"next_action": routed["action"]})

    errors = validate_texts(new_state, new_board, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed finish state fails fast validation: "
                       + "; ".join(errors[:5]))

    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["board"], ".saipen/BOARD.md", "board", new_board),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
    ]
    # T-994 / § 16: the release closure OWNS the human digest. ship.md's
    # digest is a PLAN TARGET of the same journaled closure so a ship can
    # never report RELEASED with a stale/missing digest. Ordinary `ticket
    # done` passes no digest and stays LOG+BOARD+STATE only.
    if digest_text is not None:
        digest_doc = codec.read_document(
            root / ".saipen" / "kitchen" / "digest.md")
        targets.append(TargetPlan(
            ".saipen/kitchen/digest.md", "report",
            digest_doc.encode(digest_text),
            digest_doc.raw_hash,
            hash_bytes(digest_doc.encode(digest_text))))
    expected = {"ok": True, "code": "FINISHED", "ticket": ticket_id,
                "event_id": f"E-{event}", "phase": "DONE", "task": "none",
                "next_action": routed.get("action"),
                "transition_from": closure_from}
    if digest_text is not None:
        expected["digest"] = str(root / ".saipen" / "kitchen" / "digest.md")
    return build_plan(
        "finish", agent, _identity(root),
        {"operation": "finish", "ticket": ticket_id},
        _docs_preconditions(docs, "state", "board", "log"),
        targets, expected, op_id=op_id)


@_state_guard
def finish_ticket(project_root: Path | str, ticket_id: str, agent: str,
                  dry_run: bool = False,
                  digest_text: str | None = None,
                  digest_done: str | None = None,
                  digest_awaiting: str | None = None,
                  prefix_run: str | None = None) -> Result:
    """Atomically finish a ticket: LOG + BOARD + STATE in ONE journaled plan.
    The public `ticket done` semantics become this operation.

    The release closure passes `digest_text` so the human digest commits in
    the SAME journaled transaction as the ticket closure (T-994 / § 16), and
    `prefix_run` to emit its ONE truthful release RUN event through the same
    canonical LOG builder (§ 15). The `digest_done` / `digest_awaiting` hints
    are reserved for the no-publish digest shape.
    """
    root = Path(project_root)
    now, utc = _now(), _utc_iso()
    plan = _plan_finish_ticket(root, ticket_id, agent, now, utc,
                               digest_text=digest_text,
                               digest_done=digest_done,
                               digest_awaiting=digest_awaiting,
                               prefix_run=prefix_run)
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(root, plan)


def _move_ticket(board_text: str, ticket_id: str, target_section: str,
                 checkbox: str, action: str, payload: str) -> str:
    lines = board_text.splitlines(keepends=True)
    out = []
    ticket_line = None
    heading_idx = {}
    for line in lines:
        stripped = line.rstrip("\n")
        if stripped.startswith("- [/] " + ticket_id + " ") or \
           stripped.startswith("- [ ] " + ticket_id + " "):
            ticket_line = stripped
            continue
        for heading in ("## DOING", "## TODO", "## DONE", "## BLOCKED"):
            if stripped.startswith(heading):
                heading_idx[heading] = len(out)
        out.append(line)
    if ticket_line is None:
        raise ValueError(f"cannot locate ticket {ticket_id}")
    target_idx = heading_idx.get(target_section)
    if target_idx is None:
        raise ValueError(f"cannot locate section {target_section}")
    if action == "done":
        marked = ticket_line.replace("- [/] ", "- [x] ", 1)
    elif action == "block":
        marked = ticket_line.replace("- [/] ", "- [ ] ", 1)
        marked = set_ticket_field(marked, "blocker",
                                  escape_ticket_description(payload or "blocked"))
    elif action == "unblock":
        marked = ticket_line.replace("- [/] ", "- [ ] ", 1)
        marked = remove_ticket_field(marked, "blocker")
        marked = remove_ticket_field(marked, "verify_attempts")
    else:  # pragma: no cover
        marked = ticket_line.replace("- [/] ", "- [ ] ", 1)
    out.insert(target_idx + 1, marked.rstrip() + "\n")
    return "".join(out)


def _is_placeholder_verify(verify: str) -> bool:
    """A verify value that proves nothing about DONE (NITRO dogfood II).

    Python owns mechanics, not missing semantic content: a ticket's verify
    clause is the model's DONE proof. Refusing a placeholder keeps a weak
    model from creating mechanically perfect tickets whose completion can
    never be proven.
    """
    cleaned = (verify or "").strip().lower()
    return (not cleaned
            or cleaned in ("tbd", "todo", "verify: tbd", "verify: todo",
                           "tbd -", "todo -", "placeholder")
            or (cleaned.startswith("verify:") and len(cleaned) < 12))


@_state_guard
def ticket_add(project_root: Path | str, agent: str, priority: str,
               description: str, needs: list[str], verify: str,
               dry_run: bool = False) -> Result:
    root = Path(project_root)
    if not description or not description.strip():
        return _refuse("INCOMPLETE_TICKET",
                       "ticket description is required (semantic input)")
    if "\n" in description or "\r" in description:
        return _refuse("VALIDATION_FAILED",
                       "ticket description may not contain line breaks -- "
                       "one ticket_add must render exactly one ticket line")
    if _is_placeholder_verify(verify):
        return _refuse("INCOMPLETE_TICKET",
                       "verify is a placeholder; a ticket needs a real DONE "
                       "proof (no TBD/TODO/empty)", verify=verify)
    if "\n" in verify or "\r" in verify:
        return _refuse("VALIDATION_FAILED",
                       "verify text may not contain line breaks")
    op_id = "ticket-" + uuid4_hex()
    now, utc = _now(), _utc_iso()
    docs, _state, board, log_tail = _read(root)
    if board["errors"]:
        return _refuse("VALIDATION_FAILED",
                       "BOARD parse error(s): " + "; ".join(board["errors"][:3]))
    # Ticket IDs derive from the SAME canonical complete history (sealed
    # segments + active LOG.md) already used for E-ID allocation -- a sealed
    # segment's [T-###] is ticket identity, never reissuable (T-1003).
    from .log import read_history
    tid = next_ticket_id(docs["board"].text_norm, read_history(root))
    for need in needs:
        if need not in board["tickets"]:
            return _refuse("TICKET_NOT_FOUND", f"dangling needs: {need}")
    description = escape_ticket_description(description)
    verify = escape_ticket_description(verify)
    desc = (f"- [ ] T-{tid} [{priority}] {description}"
            + (f" | needs: {', '.join(needs)}" if needs else "")
            + f" | verify: {verify}")
    new_board = _insert_todo(docs["board"].text_norm, desc)
    event, line = _event_line(docs, log_tail, "DEC", f"T-{tid}", agent,
                              "ticket added via SAIOPS", now, op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    owned = {
        "last_event": event,
        "updated": utc,
        "agent": agent,
    }
    new_state = patch_state(docs["state"].text_norm, owned)

    errors = validate_texts(new_state, new_board, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed state fails fast validation: "
                       + "; ".join(errors[:5]))

    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["board"], ".saipen/BOARD.md", "board", new_board),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
    ]
    plan = build_plan(
        "ticket_add", agent, _identity(root),
        {"operation": "ticket_add", "priority": priority,
         "description": description, "needs": needs},
        _docs_preconditions(docs, "state", "board", "log"),
        targets,
        {"ok": True, "code": "TICKET_ADDED", "ticket": f"T-{tid}",
         "event_id": f"E-{event}"}, op_id=op_id)
    if dry_run:
        return _render_plan(plan)
    return apply_plan(root, plan)


@_state_guard
def ticket_move(project_root: Path | str, action: str, ticket_id: str,
                agent: str, payload: str = "", dry_run: bool = False) -> Result:
    """Move a ticket between BOARD sections.

    `done` is NOT a section move: it is the atomic ticket-closure operation
    (NITRO dogfood III, T-591). A standalone `done` here would leave the split
    (BOARD DONE[x] while STATE still names the ticket in a ticket-bearing
    phase) that the composition audit reproduced. `done` delegates to
    finish_ticket so one public operation, one lifecycle meaning.
    """
    if action == "done":
        return finish_ticket(project_root, ticket_id, agent,
                             dry_run=dry_run)
    root = Path(project_root)
    now, utc = _now(), _utc_iso()
    plan = _ticket_targets(root, action, ticket_id, agent, payload, now, utc)
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(root, plan)


# ------------------------------------------------------------------ goal

def _state_only_plan(root: Path, operation: str, agent: str, mutate,
                      event_message: str, expected: dict, now: str,
                      utc: str, owned_keys: set,
                      ticket_id: str | None = None,
                      evidence_preconditions: dict[str, str] | None = None,
                      receipt_metadata: dict | None = None,
                      extra_targets: list[TargetPlan] | None = None,
                      op_id: str | None = None,
                      allow_dead_home: bool = False) \
        -> OperationPlan | Result:
    op_id = op_id or (operation + "-" + uuid4_hex())
    docs, _state, _board, log_tail = _read(root,
                                          allow_dead_home=allow_dead_home)
    event, line = _event_line(docs, log_tail, "DEC", ticket_id, agent,
                              event_message, now, op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    new_state = mutate(docs["state"].text_norm, event)
    errors = validate_texts(new_state, docs["board"].text_norm, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed state fails fast validation: "
                       + "; ".join(errors[:5]))
    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
    ]
    targets.extend(extra_targets or [])
    expected["event_id"] = f"E-{event}"
    preconditions = _docs_preconditions(docs, "state", "board", "log")
    # Snapshot evidence wins on overlap. If STATE/LOG moved after the domain
    # snapshot but before this generic planner read them, APPLY must refuse
    # the mixed plan rather than authorize against the later bytes.
    preconditions.update(evidence_preconditions or {})
    for target in extra_targets or []:
        # A MISSING extra target's live hash is "" (journal._hash_file), while
        # codec.read_document of a missing file hashes empty BYTES. The plan
        # precondition must use the live convention or a first-time write of
        # an extra target would refuse itself as STALE_STATE.
        preconditions[target.path] = (
            target.before_hash if (root / target.path).exists() else "")
    return build_plan(
        operation, agent, _identity(root),
        {"operation": operation, "agent": agent},
        preconditions,
        targets, expected, op_id=op_id,
        receipt_metadata=receipt_metadata)


@_state_guard
def set_goal_intent(project_root: Path | str, agent: str, objective: str,
                    dry_run: bool = False) -> Result:
    """Record a decided goal pivot: execution_intent goal, counters from 0.
    Owns ONLY intent/counters/last_event/updated/agent -- never phase, task or
    next_action. Claiming the top ticket is a separate operation."""
    root = Path(project_root)
    now, utc = _now(), _utc_iso()

    def mutate(text: str, event: int) -> str:
        transitioned = transition_execution_intent(
            text, "goal", goal_waves=0, goal_tickets=0)
        return patch_state(transitioned, {
            "last_event": event,
            "updated": utc,
            "agent": agent,
        })

    plan = _state_only_plan(root, "goal", agent, mutate,
                            f"goal pivot -- {objective}",
                            {"ok": True, "code": "GOAL_SET"}, now, utc,
                            {"execution_intent", "goal_waves", "goal_tickets"})
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(root, plan)


@_state_guard
def set_converge_intent(project_root: Path | str, agent: str,
                        target: str = "done", dry_run: bool = False) -> Result:
    """Persist a complete converge-family transition without losing work.

    Active ticket continuation remains exact. With no immediate ticket action,
    crew becomes the outer orchestration action; other converge targets retain
    ordinary continuation semantics.
    """
    root = Path(project_root)
    now, utc = _now(), _utc_iso()

    _docs, before_state, _board, _tail = _read(root)
    entry_ticket = before_state.get("task")
    if entry_ticket in (None, "", "none"):
        entry_ticket = None

    def mutate(text: str, event: int) -> str:
        before = parse_state(text)
        transitioned = transition_execution_intent(text, "converge", target)
        active = (before.get("task") not in (None, "", "none")
                  and before.get("phase") in phases.TICKET_BEARING_PHASES)
        next_action = before.get("next_action") if active else (
            "saipen crew" if target == "crew" else "saipen continue")
        return patch_state(transitioned, {
            "next_action": next_action,
            "last_event": event,
            "updated": utc,
            "agent": agent,
        })

    extra_targets = None
    epoch_op_id = None
    if target == "crew":
        # T-1003 carrier-loss wave: the crew epoch is DURABLE project proof,
        # never only a gitignored recovery receipt. The converge_intent op
        # writes a tracked `.saipen/kitchen/crew_epoch.json` in the SAME
        # journaled mutation, so deleting settled recovery receipts cannot
        # erase the epoch (RECOVERY SCRATCH != DURABLE PROJECT MEMORY).
        from .paths import project_lineage_identity
        epoch_op_id = "converge_intent-" + uuid4_hex()
        try:
            epoch_doc = codec.read_document(
                root / ".saipen" / "kitchen" / "crew_epoch.json")
        except OSError:
            epoch_doc = None
        epoch_content = json.dumps({
            "schema_version": 1,
            "operation": "crew_epoch",
            "op_id": epoch_op_id,
            "target": "crew",
            "status": "COMMITTED",
            "ticket_id": entry_ticket,
            "created_at": utc,
            "project_lineage": project_lineage_identity(root),
        }, indent=2, sort_keys=True) + "\n"
        epoch_target = _target(
            epoch_doc, ".saipen/kitchen/crew_epoch.json", "report",
            epoch_content)
        extra_targets = [epoch_target]
    plan = _state_only_plan(
        root, "converge_intent", agent, mutate,
        f"execution intent -> converge/{target}",
        {"ok": True, "code": "CONVERGE_SET",
         "execution_intent": "converge", "converge_target": target},
        now, utc, {"execution_intent", "converge_target", "goal_waves",
                   "goal_tickets", "next_action"},
        ticket_id=entry_ticket,
        receipt_metadata={
            "operation": "converge_intent",
            "target": target,
            "status": "COMMITTED",
            "project_identity": _identity(root),
            "ticket_id": entry_ticket,
        },
        extra_targets=extra_targets, op_id=epoch_op_id)
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(root, plan)


@_state_guard
def finalize_converge_intent(project_root: Path | str, agent: str,
                             target: str, evidence: str,
                             ticket_id: str | None = None,
                             dry_run: bool = False,
                             evidence_preconditions: dict[str, str] | None = None,
                             receipt_metadata: dict | None = None,
                             extra_targets: list[TargetPlan] | None = None) \
        -> Result:
    """Close one proven converge target through canonical LOG+STATE mutation."""
    root = Path(project_root)
    now, utc = _now(), _utc_iso()
    _docs, state, _board, _tail = _read(root)
    if state.get("execution_intent") != "converge" \
            or state.get("converge_target") != target:
        return _refuse("VALIDATION_FAILED",
                       f"active converge target is not {target!r}")
    if state.get("phase") != "DONE" or state.get("task") not in (
            None, "", "none"):
        return _refuse("VALIDATION_FAILED",
                       "converge finalization requires local Core phase DONE "
                       "with task none")

    def mutate(text: str, event: int) -> str:
        transitioned = transition_execution_intent(text, "normal")
        return patch_state(transitioned, {
            "phase": "DONE",
            "task": "none",
            "next_action": "saipen continue",
            "blocker": "",
            "last_event": event,
            "updated": utc,
            "agent": agent,
        })

    plan = _state_only_plan(
        root, f"finalize_{target}", agent, mutate, evidence,
        {"ok": True, "code": "CONVERGE_FINALIZED", "target": target},
        now, utc, {"execution_intent", "converge_target", "goal_waves",
                   "goal_tickets", "phase", "task", "next_action",
                   "blocker"}, ticket_id=ticket_id,
        evidence_preconditions=evidence_preconditions,
        receipt_metadata=receipt_metadata or {
            "operation": f"finalize_{target}",
            "target": target,
            "status": "COMMITTED",
            "project_identity": _identity(root),
            "ticket_id": ticket_id,
        },
        extra_targets=extra_targets)
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(root, plan)


def _candidate_home_errors(root: Path, state: dict,
                           candidate_home: str) -> list[str]:
    """Closed preconditions for rebinding STATE.saipen_home to a replacement
    SAIPEN install (T-1003 carrier-loss wave).

    Proves BEFORE any write: the candidate is a real directory, its VERSION
    is readable and major-compatible with the project's protocol major, the
    core BOOT layout is present, and the required protocol files exist. No
    disk search, no guessing a home -- the caller names the candidate.
    """
    errors: list[str] = []
    home = Path(candidate_home)
    if not candidate_home or not home.is_dir():
        return [f"candidate home {candidate_home!r} is not a directory"]
    version_file = home / "VERSION"
    if not version_file.is_file():
        errors.append(f"candidate home {candidate_home!r} has no readable "
                      "VERSION file")
    else:
        try:
            version_text = version_file.read_text(
                encoding="utf-8-sig", errors="replace").strip()
        except OSError:
            version_text = ""
        match = re.match(r"v?(\d+)\.", version_text)
        major = match.group(1) if match else ""
        expected = str(state.get("saipen_version") or 7)
        if major != expected:
            errors.append(
                f"candidate home protocol major {major or 'unreadable'} != "
                f"project saipen_version {expected}; refuse to rebind onto "
                "an incompatible protocol")
    if not ((home / "saipen" / "BOOT.md").is_file()
            or (home / "BOOT.md").is_file()):
        errors.append(f"candidate home {candidate_home!r} has no "
                      "saipen/BOOT.md (core layout invalid)")
    if not (home / "extensions" / "subs" / "PROTOCOL.md").is_file():
        errors.append(f"candidate home {candidate_home!r} lacks "
                      "extensions/subs/PROTOCOL.md (required protocol "
                      "files)")
    return errors

@_state_guard
def rebind_saipen_home(project_root: Path | str, agent: str,
                       candidate_home: str, dry_run: bool = False) -> Result:
    """Rebind STATE.saipen_home to a VERIFIED replacement SAIPEN install.

    This is the ONE explicit recovery path for a dead bootloader pointer
    (T-1003 carrier-loss wave): the caller names a candidate home, this
    operation proves it (readable VERSION, compatible major, BOOT layout,
    required protocol files), then journals ONE narrowly-owned STATE pointer
    update -- phase/task/board untouched -- with truthful LOG evidence. The
    version guard resumes normally afterwards; sub sync/adopt then handle
    role copies against the new home.
    """
    root = Path(project_root)
    now, utc = _now(), _utc_iso()
    # The ONE reader allowed to load a checkpoint whose persisted pointer is
    # already dead (P0#3): repairing exactly that pointer is this operation's
    # purpose, and the replacement is proved by `_candidate_home_errors` below.
    _docs, state, _board, _tail = _read(root, allow_dead_home=True)
    errors = _candidate_home_errors(root, state, candidate_home)
    if errors:
        return _refuse("HOME_REQUIRED",
                       "cannot rebind onto the candidate home: "
                       + "; ".join(errors[:4]),
                       next_action="name a valid SAIPEN install path")
    if state.get("saipen_home") == candidate_home:
        return _refuse("VALIDATION_FAILED",
                       "STATE.saipen_home already points at "
                       f"{candidate_home!r}; nothing to rebind")
    task = state.get("task")

    def mutate(text: str, event: int) -> str:
        return patch_state(text, {
            "saipen_home": candidate_home,
            "last_event": event,
            "updated": utc,
            "agent": agent,
        })

    plan = _state_only_plan(
        root, "rebind_home", agent, mutate,
        f"saipen_home rebound to {candidate_home}",
        {"ok": True, "code": "HOME_REBOUND",
         "saipen_home": candidate_home},
        now, utc, {"saipen_home", "last_event", "updated", "agent"},
        ticket_id=task if task not in (None, "", "none") else None,
        allow_dead_home=True)
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(root, plan)


GOAL_WAVE_CAP = 3
GOAL_TICKET_CAP = 20


@_state_guard
def reauthorize_valve(project_root: Path | str, agent: str,
                      dry_run: bool = False) -> Result:
    """Conditional safety-valve reauthorization: reset BOTH counters to 0 only
    when a counter has tripped its cap. Never grants a fresh budget on a run
    that did not trip the valve."""
    root = Path(project_root)
    now, utc = _now(), _utc_iso()
    _docs, state, _board, _log_tail = _read(root)
    waves = state.get("goal_waves") or 0
    tickets = state.get("goal_tickets") or 0
    if not (state.get("execution_intent") == "goal"
            and (waves >= 3 or tickets >= 20)):
        return _refuse("VALIDATION_FAILED",
                       "valve has not tripped; no fresh budget is owed",
                       goal_waves=waves, goal_tickets=tickets)

    def mutate(text: str, event: int) -> str:
        return patch_state(text, {
            "goal_waves": 0,
            "goal_tickets": 0,
            "last_event": event,
            "updated": utc,
            "agent": agent,
        })

    plan = _state_only_plan(root, "valve", agent, mutate,
                            f"goal reauthorized -- goal_waves {waves}->0, "
                            f"goal_tickets {tickets}->0",
                            {"ok": True, "code": "VALVE_REAUTHORIZED"},
                            now, utc,
                            {"goal_waves", "goal_tickets"})
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(root, plan)


@_state_guard
def stop_checkpoint(project_root: Path | str, agent: str, reason: str = "",
                    dry_run: bool = False) -> Result:
    """The brake: checkpoint the exact current execution with a resumable
    next_action. Never resets phase; never changes intent or counters. The
    human digest is a PLAN TARGET (NITRO dogfood II): it commits inside the
    same journaled transaction as LOG/STATE, so a stop can never report
    STOPPED with a missing/stale digest."""
    root = Path(project_root)
    now, utc = _now(), _utc_iso()
    docs, state, _board, log_tail = _read(root)
    task = state.get("task")
    phase = state.get("phase")
    # Preserve an already-legal hard WAIT byte-for-byte (hostile-regression,
    # P1#2): `saipen stop` must never erase a legitimate WAIT (safety valve,
    # user brake, markhunt brake, ...) -- only synthesize a resumable action
    # when no legal WAIT is currently set.
    _current_na = state.get("next_action")
    if is_legal_wait(_current_na):
        na = _current_na
    else:
        na = (f"PHASE {phase} {task}" if task and task != "none"
              else "saipen continue")

    op_id = "stop-" + uuid4_hex()
    event, line = _event_line(docs, log_tail, "DEC", None, agent,
                              f"stop checkpoint{': ' + reason if reason else ''}",
                              now, op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    new_state = patch_state(docs["state"].text_norm, {
        "next_action": na,
        "last_event": event,
        "updated": utc,
        "agent": agent,
    })
    errors = validate_texts(new_state, docs["board"].text_norm, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed state fails fast validation: "
                       + "; ".join(errors[:5]))
    digest_content = ("done: stopped via SAIOPS checkpoint\n"
                      f"remaining: {task or 'see BOARD'}\n"
                      f"awaiting: {reason or 'nothing'}\n")
    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
    ]
    digest_doc = codec.read_document(root / ".saipen" / "kitchen" / "digest.md")
    targets.append(TargetPlan(".saipen/kitchen/digest.md", "report",
                              digest_doc.encode(digest_content),
                              digest_doc.raw_hash,
                              hash_bytes(digest_doc.encode(digest_content))))
    plan = build_plan(
        "stop", agent, _identity(root),
        {"operation": "stop", "reason": reason},
        _docs_preconditions(docs, "state", "board", "log"),
        targets,
        {"ok": True, "code": "STOPPED", "next_action": na,
         "digest": str(root / ".saipen" / "kitchen" / "digest.md")},
        op_id=op_id)
    if dry_run:
        result = _render_plan(plan)
        result.data["digest"] = str(root / ".saipen" / "kitchen" / "digest.md")
        return result
    return apply_plan(root, plan)


# ------------------------------------------------------- release scope (T-994)

RELEASE_SCOPE_DIR = ".saipen/kitchen/release_scope"


def _plan_record_scope(root: Path, ticket_id: str, agent: str, paths: list[str],
                       now: str, utc: str) -> OperationPlan | Result:
    """PLAN the exact reviewed release scope for a ticket (T-994 / § 2).

    The scope is the model's EXACT reviewed file list -- never inferred from
    dirty files, never `git add .`. It is bound to the ticket, the project
    identity and the source identity (HEAD + per-path content hashes), so the
    release planner can prove the bytes about to ship are the bytes that were
    reviewed. The record lives under `.saipen/kitchen/release_scope/` and is
    journaled through SAIOPS like any other canonical mutation.
    """
    op_id = "scope-" + uuid4_hex()
    docs, state, board, log_tail = _read(root)
    if board["errors"]:
        return _refuse("VALIDATION_FAILED",
                       "BOARD parse error(s): " + "; ".join(board["errors"][:3]),
                       ticket=ticket_id)
    phase = state.get("phase")
    if phase not in ("REVIEW", "SHIP"):
        return _refuse(
            "ILLEGAL_PHASE",
            f"release scope may be recorded at REVIEW -> SHIP; actual phase "
            f"{phase} cannot name the reviewed scope for a release",
            ticket=ticket_id, phase=phase)
    if state.get("task") != ticket_id:
        return _refuse("ACTIVE_TICKET_MISMATCH",
                       f"STATE.task={state.get('task')} != scope ticket "
                       f"{ticket_id}", ticket=ticket_id)
    tickets = board["tickets"]
    ticket = tickets.get(ticket_id)
    if ticket is None or ticket["section"] != "## DOING":
        return _refuse("TICKET_NOT_FOUND",
                       f"{ticket_id} is not the active ## DOING ticket",
                       ticket=ticket_id)
    clean: list[str] = []
    root_resolved = root.resolve()
    for raw in paths:
        candidate = (root / raw).resolve()
        try:
            rel_path = candidate.relative_to(root_resolved)
        except ValueError:
            return _refuse("PATH_ESCAPE", f"scope path escapes project root: "
                            f"{raw}")
        if rel_path.as_posix() == ".":
            return _refuse("PATH_ESCAPE", "scope path cannot be the project root itself")
        clean.append(rel_path.as_posix())
    clean = sorted(set(clean))
    if not clean:
        return _refuse("SOURCE_SCOPE_MISSING",
                       "release scope cannot be empty; name the exact reviewed "
                       "files", ticket=ticket_id)
    try:
        from freshness import compute_source_identity
        ident = compute_source_identity(root)
    except Exception as exc:
        return _refuse("VALIDATION_FAILED",
                       f"cannot compute source identity for scope binding: "
                       f"{exc}")
    hashes: dict[str, object] = {}
    for rel in clean:
        fp = root / rel
        if fp.is_file():
            hashes[rel] = hash_bytes(fp.read_bytes())
        elif not fp.exists():
            # Deletion intent (T-994 / § 2): a reviewed removal is a scope
            # path too -- recorded as JSON null so APPLY stages `git add -u`
            # instead of failing the missing file. Only a TRACKED path can be
            # a legal deletion; an untracked missing path is a mistake.
            import subprocess
            tracked = subprocess.run(
                ["git", "-C", str(root), "ls-files", "--error-unmatch",
                 "--", rel], capture_output=True, check=False)
            if tracked.returncode != 0:
                return _refuse(
                    "SOURCE_SCOPE_MISSING",
                    f"scope path {rel} does not exist and is not tracked -- "
                    "a deletion scope must name a tracked file",
                    ticket=ticket_id)
            hashes[rel] = None
        else:
            return _refuse("SOURCE_SCOPE_MISSING",
                           f"scope path {rel} is not a regular file",
                           ticket=ticket_id)
    import json
    from .paths import project_lineage_identity
    record = {
        "schema_version": 1,
        "ticket": ticket_id,
        "project_identity": _identity(root),
        "project_lineage": project_lineage_identity(root),
        "source_head": ident.source_head,
        "source_tree_fingerprint": ident.source_tree_fingerprint,
        "paths": hashes,
        "recorded_at": utc,
        "op_id": op_id,
    }
    content = json.dumps(record, indent=2, sort_keys=True) + "\n"

    event, line = _event_line(
        docs, log_tail, "DEC", ticket_id, agent,
        f"release scope recorded -- {len(clean)} path(s) bound to "
        f"{ident.source_head[:12]}", now, op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    owned = {"last_event": event, "updated": utc, "agent": agent}
    new_state = patch_state(docs["state"].text_norm, owned)

    errors = validate_texts(new_state, docs["board"].text_norm, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed scope state fails fast validation: "
                       + "; ".join(errors[:5]))

    scope_rel = f"{RELEASE_SCOPE_DIR}/{ticket_id}.json"
    scope_doc = codec.read_document(root / scope_rel)
    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
        TargetPlan(scope_rel, "report", scope_doc.encode(content),
                   scope_doc.raw_hash, hash_bytes(scope_doc.encode(content))),
    ]
    return build_plan(
        "scope", agent, _identity(root),
        {"operation": "scope", "ticket": ticket_id, "paths": clean},
        _docs_preconditions(docs, "state", "board", "log"),
        targets,
        {"ok": True, "code": "SCOPE_RECORDED", "ticket": ticket_id,
         "paths": clean, "event_id": f"E-{event}",
         "scope": scope_rel},
        op_id=op_id)


@_state_guard
def record_scope(project_root: Path | str, ticket_id: str, agent: str,
                 paths: list[str], dry_run: bool = False) -> Result:
    """Journal the exact reviewed release scope for a ticket (T-994 / § 2)."""
    root = Path(project_root)
    now, utc = _now(), _utc_iso()
    plan = _plan_record_scope(root, ticket_id, agent, paths, now, utc)
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(root, plan)


# ------------------------------------------- first-publish wait (T-994 / § 11)

def _sanitize_remote(url: str) -> str:
    """Endpoint identity without credentials, normalized so `file://V:\\x`
    and `file://V:/x` are the same endpoint (T-994 / § 11)."""
    url = url.strip()
    if "://" in url:
        scheme, rest = url.split("://", 1)
        rest = rest.split("@", 1)[-1]
        return f"{scheme}://{rest.replace(chr(92), '/')}"
    if "@" in url:
        return url.split("@", 1)[-1].replace(chr(92), "/")
    return url.replace(chr(92), "/")


def _plan_first_publish_wait(root: Path, agent: str, remote_name: str,
                             now: str, utc: str) -> OperationPlan | Result:
    """PLAN the canonical first-publish WAIT checkpoint.

    ZERO commit/tag/push: the WAIT is a journaled canonical checkpoint that
    parks STATE.next_action on the exact ship.md line so the decision is
    recoverable evidence, not chat memory.
    """
    op_id = "wait-" + uuid4_hex()
    docs, state, _board, log_tail = _read(root)
    task = state.get("task")
    remote_name = _sanitize_remote(remote_name)
    message = (f"first-publish -- confirm repo name '{remote_name}' and "
               "public/private before I push")
    event, line = build_event(log_tail, "WAIT", message, ticket=task,
                              agent=agent, now=now, op_id=op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    na = f"WAIT: {message}"
    owned = {"next_action": na, "last_event": event, "updated": utc,
             "agent": agent}
    new_state = patch_state(docs["state"].text_norm, owned)
    errors = validate_texts(new_state, docs["board"].text_norm, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed first-publish WAIT state fails fast "
                       "validation: " + "; ".join(errors[:5]))
    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
    ]
    return build_plan(
        "wait", agent, _identity(root),
        {"operation": "wait", "remote": remote_name},
        _docs_preconditions(docs, "state", "board", "log"),
        targets,
        {"ok": True, "code": "FIRST_PUBLISH_WAIT", "next_action": na,
         "event_id": f"E-{event}"},
        op_id=op_id)


@_state_guard
def record_first_publish_wait(project_root: Path | str, agent: str,
                              remote_name: str, dry_run: bool = False) -> Result:
    """Park STATE on the canonical first-publish WAIT (T-994 / § 11)."""
    root = Path(project_root)
    now, utc = _now(), _utc_iso()
    plan = _plan_first_publish_wait(root, agent, remote_name, now, utc)
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(root, plan)


def _plan_first_publish_confirm(root: Path, agent: str, remote_name: str,
                                visibility: str, now: str,
                                utc: str) -> OperationPlan | Result:
    """PLAN the canonical first-publish confirmation record.

    Confirmation is canonical evidence, never chat memory: the confirming
    agent journal-records the repo name + public/private decision into STATE
    bound to the exact remote identity, so a later `saipen ship` can verify
    the publication is authorized for THIS endpoint.
    """
    op_id = "fpc-" + uuid4_hex()
    docs, state, _board, log_tail = _read(root)
    na = str(state.get("next_action") or "")
    if not na.startswith("WAIT: first-publish"):
        return _refuse("VALIDATION_FAILED",
                       "first-publish confirmation requires a pending "
                       "first-publish WAIT in STATE.next_action; current "
                       f"next_action is {na!r}")
    if visibility not in ("public", "private"):
        return _refuse("VALIDATION_FAILED",
                       f"visibility {visibility!r} outside public|private")
    remote_name = _sanitize_remote(remote_name)
    task = state.get("task")
    event, line = _event_line(
        docs, log_tail, "DEC", task, agent,
        f"first publish confirmed -- repo '{remote_name}' ({visibility})",
        now, op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    owned = {
        "first_publish_confirmation": f"{remote_name} {visibility}",
        "next_action": (f"PHASE SHIP {task}" if task and task != "none"
                        else "saipen continue"),
        "last_event": event,
        "updated": utc,
        "agent": agent,
    }
    new_state = patch_state(docs["state"].text_norm, owned)
    errors = validate_texts(new_state, docs["board"].text_norm, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed first-publish confirmation state fails fast "
                       "validation: " + "; ".join(errors[:5]))
    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
    ]
    return build_plan(
        "fpc", agent, _identity(root),
        {"operation": "fpc", "remote": remote_name, "visibility": visibility},
        _docs_preconditions(docs, "state", "board", "log"),
        targets,
        {"ok": True, "code": "FIRST_PUBLISH_CONFIRMED",
         "confirmation": f"{remote_name} {visibility}",
         "event_id": f"E-{event}"},
        op_id=op_id)


@_state_guard
def confirm_first_publish(project_root: Path | str, agent: str,
                          remote_name: str, visibility: str,
                          dry_run: bool = False) -> Result:
    """Record canonical first-publish confirmation (T-994 / § 11)."""
    root = Path(project_root)
    now, utc = _now(), _utc_iso()
    plan = _plan_first_publish_confirm(root, agent, remote_name, visibility,
                                       now, utc)
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(root, plan)


# ------------------------------------------------------------------ helpers
def _identity(root: Path) -> str:
    from .paths import project_identity
    return project_identity(root)


def _plan_crew_closure(root: Path, agent: str, now: str, utc: str,
                       digest_text: str | None = None,
                       prefix_run: str | None = None) \
        -> OperationPlan | Result:
    """PLAN the terminal CREW release closure (T-1003 sweep, hostile finding
    3/5/16). The ordinary release executor closes an ordinary ticket through
    _plan_finish_ticket; a terminal crew release has NO ## DOING ticket (every
    ordinary ticket was already crew-deferred), so its closure writes the RUN +
    completion LOG events, the digest, and the STATE last_event/updated/agent
    while leaving phase DONE / task none and the deferred tickets DONE. The
    closure bytes are journaled exactly like any other canonical mutation."""
    op_id = "crew-closure-" + uuid4_hex()
    docs, state, board, log_tail = _read(root)
    if board["errors"]:
        return _refuse("VALIDATION_FAILED",
                       "BOARD parse error(s): " + "; ".join(board["errors"][:3]))
    if state.get("phase") != "DONE" or state.get("task") not in (
            None, "", "none"):
        return _refuse(
            "ILLEGAL_PHASE",
            f"crew terminal closure requires local Core phase DONE / task "
            f"none; live {state.get('phase')}/{state.get('task')}")
    if prefix_run:
        run_event, run_line = build_event(
            log_tail, "RUN", prefix_run, ticket=None, agent=agent,
            now=now, op_id=op_id)
        event, line = build_event(
            run_event, "DEC",
            "crew terminal release closure -- all deferred tickets shipped",
            ticket=None, agent=agent, now=now, op_id=op_id)
        new_log = (docs["log"].text_norm.rstrip("\n") + "\n" + run_line
                   + "\n" + line + "\n")
    else:
        event, line = _event_line(
            docs, log_tail, "DEC", None, agent,
            "crew terminal release closure", now, op_id)
        new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    owned = {
        "last_event": event,
        "updated": utc,
        "agent": agent,
    }
    new_state = patch_state(docs["state"].text_norm, owned)
    from .router import route_next
    routed = route_next(new_state, docs["board"].text_norm)
    if routed.get("ok") and routed.get("action") != "saipen continue":
        new_state = patch_state(new_state, {"next_action": routed["action"]})
    errors = validate_texts(new_state, docs["board"].text_norm, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed crew closure state fails fast validation: "
                       + "; ".join(errors[:5]))
    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
    ]
    if digest_text is not None:
        digest_doc = codec.read_document(
            root / ".saipen" / "kitchen" / "digest.md")
        targets.append(TargetPlan(
            ".saipen/kitchen/digest.md", "report",
            digest_doc.encode(digest_text),
            digest_doc.raw_hash,
            hash_bytes(digest_doc.encode(digest_text))))
    expected = {"ok": True, "code": "CREW_RELEASED",
                "event_id": f"E-{event}", "phase": "DONE", "task": "none",
                "next_action": routed.get("action")}
    if digest_text is not None:
        expected["digest"] = str(root / ".saipen" / "kitchen" / "digest.md")
    return build_plan(
        "release_crew_closure", agent, _identity(root),
        {"operation": "release_crew_closure"},
        _docs_preconditions(docs, "state", "board", "log"),
        targets, expected, op_id=op_id)


def _plan_defer_for_crew(root: Path, ticket_id: str, agent: str,
                         crew_epoch: str, now: str, utc: str) \
        -> OperationPlan | Result:
    """PLAN the crew-deferred closure of an ordinary ticket (T-1003 sweep,
    hostile finding 3/4).

    Under an active `converge_target: crew`, an ordinary ticket that reaches
    SHIP after VERIFY+REVIEW does NOT publish. This plan closes it LOCALLY
    (SHIP -> DONE, task none) and records a committed STRUCTURED defer receipt
    carrying crew_epoch, ticket_id, the exact reviewed release-scope identity
    and per-path hashes, and the source identity -- zero git commit, zero
    version bump, zero tag, zero push. The terminal crew release (SC-11) is
    later DERIVED from these receipts and fed to the ordinary release executor.

    Gate (mirrors _plan_finish_ticket): phase SHIP + task == ticket + exactly
    one ## DOING ticket + a recorded release scope bound to this project and
    source identity. DEFER is publication-free, but it is still a CLOSURE, so
    the SHIP gate cannot be skipped any more than a real ship can.
    """
    import json as _json
    op_id = "crew-defer-" + uuid4_hex()
    docs, state, board, log_tail = _read(root)
    if board["errors"]:
        return _refuse("VALIDATION_FAILED",
                       "BOARD parse error(s): " + "; ".join(board["errors"][:3]),
                       ticket=ticket_id)
    tickets = board["tickets"]
    if ticket_id not in tickets:
        return _refuse("TICKET_NOT_FOUND", f"{ticket_id} not on the board",
                       ticket=ticket_id)
    ticket = tickets[ticket_id]
    if ticket["section"] != "## DOING" or ticket["checkbox"] != "/":
        return _refuse("ILLEGAL_TICKET_LIFECYCLE",
                       f"crew defer accepts only a ## DOING [/] ticket; "
                       f"{ticket_id} is {ticket['section']} "
                       f"[{ticket['checkbox']}]", ticket=ticket_id)
    doing = [t for t in tickets.values() if t["section"] == "## DOING"]
    if len(doing) != 1:
        return _refuse("ACTIVE_TICKET_MISMATCH",
                       f"crew defer needs exactly one ## DOING ticket, found "
                       f"{len(doing)}", ticket=ticket_id)
    if state.get("task") != ticket_id:
        return _refuse("ACTIVE_TICKET_MISMATCH",
                       f"STATE.task={state.get('task')} != deferred ticket "
                       f"{ticket_id}", ticket=ticket_id)
    prev_phase = state.get("phase") or "DONE"
    if prev_phase != "SHIP":
        return _refuse(
            "ILLEGAL_PHASE",
            f"crew defer requires phase SHIP (the canonical closure edge "
            f"SHIP -> DONE); actual phase {prev_phase} cannot defer a ticket "
            "without its required REVIEW/SHIP gates",
            ticket=ticket_id, phase=prev_phase)
    if not crew_epoch or not re.fullmatch(r"[a-z0-9_-]+-[0-9a-f]{8}", crew_epoch):
        return _refuse("VALIDATION_FAILED",
                       f"crew_epoch {crew_epoch!r} is not a structured "
                       "converge_intent op identity", ticket=ticket_id)

    # The exact reviewed release scope must already exist and bind THIS
    # project and the reviewed source identity (item 5: derived, never a new
    # manual list; the defer receipt copies the reviewed path hashes).
    scope_rel = f"{RELEASE_SCOPE_DIR}/{ticket_id}.json"
    scope_path = root / scope_rel
    if not scope_path.is_file():
        return _refuse(
            "SOURCE_SCOPE_MISSING",
            f"no release scope recorded for {ticket_id} -- the exact reviewed "
            "files must be recorded (`saipen scope`) before the crew defer",
            ticket=ticket_id)
    try:
        scope_doc = codec.read_document(scope_path)
        scope_record = _json.loads(scope_doc.text_norm)
    except (OSError, _json.JSONDecodeError) as exc:
        return _refuse("RECOVERY_CONFLICT",
                       f"release scope record {scope_path} is corrupt: {exc}")
    if scope_record.get("schema_version") != 1 \
            or scope_record.get("ticket") != ticket_id:
        return _refuse("RECOVERY_CONFLICT",
                       f"release scope record {scope_path} does not bind "
                       f"ticket {ticket_id}")
    if scope_record.get("project_identity") != _identity(root):
        return _refuse("PATH_ESCAPE",
                       "release scope record was created for a different "
                       "project; refuse cross-project defer")
    paths = scope_record.get("paths") or {}
    if not paths:
        return _refuse("SOURCE_SCOPE_MISSING",
                       f"release scope record {scope_path} carries no paths")
    try:
        from freshness import compute_source_identity
        ident = compute_source_identity(root)
    except Exception as exc:
        return _refuse("VALIDATION_FAILED",
                       f"cannot compute source identity for defer: {exc}")
    if ident.source_head != scope_record.get("source_head") \
            or ident.source_tree_fingerprint != scope_record.get(
                "source_tree_fingerprint"):
        return _refuse(
            "STALE_PLAN",
            f"reviewed scope source identity differs from the live tree; "
            f"re-record the scope before deferring {ticket_id}")

    # Closure targets (same cross-file transaction as a real ship closure).
    from .journal import hash_source_identity
    run_event, run_line = build_event(
        log_tail, "RUN",
        f"deferred {ticket_id} to crew epoch {crew_epoch} "
        "(no publication; SC-11 owns terminal release)", ticket=ticket_id,
        agent=agent, now=now, op_id=op_id)
    event, line = build_event(
        run_event, "DEC",
        "ticket deferred via SAIOPS -- completion (from SHIP), deferred "
        "to crew", ticket=ticket_id, agent=agent, now=now, op_id=op_id)
    new_log = (docs["log"].text_norm.rstrip("\n") + "\n" + run_line
               + "\n" + line + "\n")
    new_board = _move_ticket(docs["board"].text_norm, ticket_id, "## DONE",
                             "[x]", "done", "")
    owned = {
        "phase": "DONE",
        "task": "none",
        "next_action": "saipen continue",
        "transition_from": prev_phase,
        "last_event": event,
        "updated": utc,
        "agent": agent,
    }
    new_state = patch_state(docs["state"].text_norm, owned)
    from .router import route_next
    routed = route_next(new_state, new_board)
    if routed.get("ok") and routed.get("action") != "saipen continue":
        new_state = patch_state(new_state, {"next_action": routed["action"]})

    errors = validate_texts(new_state, new_board, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed defer state fails fast validation: "
                       + "; ".join(errors[:5]))

    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["board"], ".saipen/BOARD.md", "board", new_board),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
    ]
    preconditions = _docs_preconditions(docs, "state", "board", "log")
    preconditions[scope_rel] = scope_doc.raw_hash
    preconditions["."] = hash_source_identity(root)
    receipt_metadata = {
        "operation": "crew_defer",
        "status": "COMMITTED",
        "crew_epoch": crew_epoch,
        "ticket_id": ticket_id,
        "release_scope_path": scope_rel,
        "release_scope_identity": hash_bytes(scope_doc.text_norm.encode("utf-8")),
        "paths": dict(paths),
        "source_head": scope_record.get("source_head"),
        "source_tree_fingerprint": scope_record.get("source_tree_fingerprint"),
        "project_identity": _identity(root),
        "event_id": f"E-{event}",
        "op_id": op_id,
    }
    return build_plan(
        "crew_defer", agent, _identity(root),
        {"operation": "crew_defer", "ticket": ticket_id,
         "crew_epoch": crew_epoch},
        preconditions, targets,
        {"ok": True, "code": "DEFERRED", "ticket": ticket_id,
         "crew_epoch": crew_epoch, "event_id": f"E-{event}",
         "phase": "DONE", "task": "none",
         "next_action": routed.get("action")},
        op_id=op_id, receipt_metadata=receipt_metadata)


@_state_guard
def defer_for_crew(project_root: Path | str, ticket_id: str, agent: str,
                   crew_epoch: str, dry_run: bool = False) -> Result:
    """Close an ordinary SHIP ticket as crew-deferred (public DEFER_FOR_CREW).

    Structured defer receipt committed through the journal (operation
    `crew_defer`); zero git write, zero version bump, zero tag, zero push.
    Core returns to the crew planner for the terminal SC-11 release.
    """
    root = Path(project_root)
    now, utc = _now(), _utc_iso()
    plan = _plan_defer_for_crew(root, ticket_id, agent, crew_epoch, now, utc)
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(root, plan)


def _plan_clear_wait_role(root: Path, ticket_id: str, agent: str,
                          now: str, utc: str) -> OperationPlan | Result:
    """PLAN the mechanical disposition of a WAIT_ROLE:<role> blocker whose
    owning crew role produced real evidence (T-1003 finding 10). The ticket
    is moved ## BLOCKED -> ## DONE with the blocker removed -- the resolution
    IS the role's evidence, never prose, never a human courier. Core state
    stays DONE/task none; a crew-owned blocker is work for SC, not a
    terminal human stop."""
    docs, _state, board, log_tail = _read(root)
    if board["errors"]:
        return _refuse("VALIDATION_FAILED",
                       "BOARD parse error(s): " + "; ".join(board["errors"][:3]))
    tickets = board["tickets"]
    if ticket_id not in tickets:
        return _refuse("TICKET_NOT_FOUND", f"{ticket_id} not on the board",
                       ticket=ticket_id)
    ticket = tickets[ticket_id]
    if ticket["section"] != "## BLOCKED":
        return _refuse("ILLEGAL_TICKET_LIFECYCLE",
                       f"clear-wait-role accepts only a ## BLOCKED ticket; "
                       f"{ticket_id} is {ticket['section']}",
                       ticket=ticket_id)
    from .board import blocker_class
    blocker = ticket.get("fields", {}).get("blocker", "")
    if blocker_class(blocker) != "WAIT_ROLE":
        return _refuse("ILLEGAL_TICKET_LIFECYCLE",
                       f"{ticket_id} blocker is not a WAIT_ROLE class",
                       ticket=ticket_id)
    op_id = "clear-wait-role-" + uuid4_hex()
    event, line = _event_line(docs, log_tail, "DEC", ticket_id, agent,
                              "WAIT_ROLE blocker cleared -- owning role "
                              "evidence received; ticket resolved", now, op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    new_board = _move_ticket(docs["board"].text_norm, ticket_id, "## DONE",
                             "[x]", "done", "")
    new_state = patch_state(docs["state"].text_norm, {
        "last_event": event,
        "updated": utc,
        "agent": agent,
    })
    errors = validate_texts(new_state, new_board, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed clear-wait-role state fails fast validation: "
                       + "; ".join(errors[:5]))
    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["board"], ".saipen/BOARD.md", "board", new_board),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
    ]
    return build_plan(
        "clear_wait_role", agent, _identity(root),
        {"operation": "clear_wait_role", "ticket": ticket_id},
        _docs_preconditions(docs, "state", "board", "log"),
        targets,
        {"ok": True, "code": "WAIT_ROLE_CLEARED", "ticket": ticket_id,
         "event_id": f"E-{event}"},
        op_id=op_id)


@_state_guard
def clear_wait_role(project_root: Path | str, ticket_id: str, agent: str,
                    dry_run: bool = False) -> Result:
    """Public disposition of a crew-owned WAIT_ROLE blocker (item 10)."""
    root = Path(project_root)
    now, utc = _now(), _utc_iso()
    plan = _plan_clear_wait_role(root, ticket_id, agent, now, utc)
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(root, plan)


def _plan_crew_run(root: Path, agent: str, *, crew_epoch: str, role: str,
                   source_head: str, source_tree_fingerprint: str,
                   role_revision: str, package_identities: list[str],
                   now: str, utc: str) -> OperationPlan | Result:
    """PLAN a structured crew-run receipt (T-1003 finding 7): structured
    proof a role actually RAN in this epoch and bound its package identities
    to epoch + role + exact source identity + role_revision. Package evidence
    produced before the current epoch may stay valid history -- it does not
    certify the new SC stage. CURRENT != FRESH FOR THIS CREW EPOCH."""
    op_id = "crew-run-" + uuid4_hex()
    docs, _state, _board, log_tail = _read(root)
    event, line = _event_line(
        docs, log_tail, "DEC", None, role,
        f"crew run -- epoch {crew_epoch} role {role} "
        f"({len(package_identities)} package(s))", now, op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    new_state = patch_state(docs["state"].text_norm, {
        "last_event": event,
        "updated": utc,
        "agent": agent,
    })
    errors = validate_texts(new_state, docs["board"].text_norm, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed crew-run state fails fast validation: "
                       + "; ".join(errors[:5]))
    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
    ]
    receipt_metadata = {
        "operation": "crew_run",
        "status": "COMMITTED",
        "crew_epoch": crew_epoch,
        "role": role,
        "source_head": source_head,
        "source_tree_fingerprint": source_tree_fingerprint,
        "role_revision": role_revision,
        "package_identities": list(package_identities),
        "project_identity": _identity(root),
        "event_id": f"E-{event}",
    }
    return build_plan(
        "crew_run", agent, _identity(root),
        {"operation": "crew_run", "role": role, "crew_epoch": crew_epoch},
        _docs_preconditions(docs, "state", "board", "log"),
        targets,
        {"ok": True, "code": "CREW_RUN_RECORDED", "role": role,
         "crew_epoch": crew_epoch, "event_id": f"E-{event}"},
        op_id=op_id, receipt_metadata=receipt_metadata)


@_state_guard
def record_crew_run(project_root: Path | str, agent: str, *, crew_epoch: str,
                    role: str, source_head: str,
                    source_tree_fingerprint: str, role_revision: str,
                    package_identities: list[str],
                    dry_run: bool = False) -> Result:
    """Commit a structured crew-run receipt (item 7)."""
    root = Path(project_root)
    now, utc = _now(), _utc_iso()
    plan = _plan_crew_run(root, agent, crew_epoch=crew_epoch, role=role,
                          source_head=source_head,
                          source_tree_fingerprint=source_tree_fingerprint,
                          role_revision=role_revision,
                          package_identities=package_identities,
                          now=now, utc=utc)
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(root, plan)


def _plan_producer_integration(
        root: Path, agent: str, *, crew_epoch: str, producer: str,
        package_identity: str, input_source: str,
        input_source_fingerprint: str, resulting_source: str,
        resulting_source_fingerprint: str, core_ticket: str | None = None,
        now: str = "", utc: str = "") -> OperationPlan | Result:
    """PLAN a structured producer INTEGRATION EDGE (T-1003 findings 11/12).

    The package was prepared against S0 (input_source) and its payload was
    APPLIED, making the source S1 (resulting_source). The package truthfully
    stays bound to S0 -- it is never rewritten to claim S1. SC-8/9 consume
    this edge; the edge is the integration proof, and the natural staleness of
    the S0 package against later sources is exactly what detects whether a
    rerun is required."""
    op_id = "producer-integration-" + uuid4_hex()
    docs, _state, _board, log_tail = _read(root)
    event, line = _event_line(
        docs, log_tail, "DEC", core_ticket, producer,
        f"producer integration -- {producer} {input_source[:12]} -> "
        f"{resulting_source[:12]}", now, op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    new_state = patch_state(docs["state"].text_norm, {
        "last_event": event,
        "updated": utc,
        "agent": agent,
    })
    errors = validate_texts(new_state, docs["board"].text_norm, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed integration state fails fast validation: "
                       + "; ".join(errors[:5]))
    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
    ]
    receipt_metadata = {
        "operation": "producer_integration",
        "status": "COMMITTED",
        "crew_epoch": crew_epoch,
        "producer": producer,
        "package_identity": package_identity,
        "input_source": input_source,
        "input_source_fingerprint": input_source_fingerprint,
        "resulting_source": resulting_source,
        "resulting_source_fingerprint": resulting_source_fingerprint,
        "core_ticket": core_ticket,
        "project_identity": _identity(root),
        "event_id": f"E-{event}",
    }
    return build_plan(
        "producer_integration", agent, _identity(root),
        {"operation": "producer_integration", "producer": producer},
        _docs_preconditions(docs, "state", "board", "log"),
        targets,
        {"ok": True, "code": "INTEGRATION_RECORDED", "producer": producer,
         "crew_epoch": crew_epoch, "event_id": f"E-{event}"},
        op_id=op_id, receipt_metadata=receipt_metadata)


@_state_guard
def record_producer_integration(
        project_root: Path | str, agent: str, *, crew_epoch: str,
        producer: str, package_identity: str, input_source: str,
        input_source_fingerprint: str, resulting_source: str,
        resulting_source_fingerprint: str, core_ticket: str | None = None,
        dry_run: bool = False) -> Result:
    """Commit a structured producer integration edge (item 11)."""
    root = Path(project_root)
    now, utc = _now(), _utc_iso()
    plan = _plan_producer_integration(
        root, agent, crew_epoch=crew_epoch, producer=producer,
        package_identity=package_identity, input_source=input_source,
        input_source_fingerprint=input_source_fingerprint,
        resulting_source=resulting_source,
        resulting_source_fingerprint=resulting_source_fingerprint,
        core_ticket=core_ticket, now=now, utc=utc)
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(root, plan)


def _plan_convergence_stage(
        root: Path, agent: str, *, stage: str, verdict: str,
        detail: str = "", now: str = "", utc: str = "") -> OperationPlan | Result:
    """PLAN a structured canonical convergence-stage receipt (T-1003 Wave 2
    items 1/14). CONVERGE.md owns the E-I sequence; this receipt is the
    mechanical proof that one stage ran and bound the LIVE source identity at
    its execution time. Only a COMMITTED terminal chain E,F,G,H,I -- ordered,
    identity-consistent, ending at the CURRENT source -- satisfies the
    convergence verdict consumed by SC-7 and the crew gate.

    The op computes and binds the source identity itself (no caller-supplied
    identity can be fabricated); stage G (CLEAN) additionally derives its
    INPUT identity from the latest committed F receipt, so CLEAN is proven to
    run on the source the test gate and forced HUNT proved.
    """
    from .convergence import CONVERGENCE_STAGES, STAGE_NAMES, STAGE_VERDICTS
    if stage not in CONVERGENCE_STAGES:
        return _refuse("VALIDATION_FAILED",
                       f"convergence stage {stage!r} outside the closed "
                       f"E-I set {list(CONVERGENCE_STAGES)}")
    allowed = STAGE_VERDICTS[stage]
    if verdict not in allowed:
        return _refuse(
            "VALIDATION_FAILED",
            f"stage {stage} verdict {verdict!r} is not a closed "
            f"{STAGE_NAMES[stage]} outcome ({', '.join(allowed)}) -- "
            "arbitrary prose is never convergence evidence")
    try:
        from freshness import compute_source_identity
        ident = compute_source_identity(root)
    except Exception as exc:
        return _refuse("VALIDATION_FAILED",
                       f"cannot bind convergence stage to a source "
                       f"identity: {exc}")
    op_id = "convergence-" + uuid4_hex()
    docs, _state, _board, log_tail = _read(root)
    meta = {
        "operation": "convergence_stage",
        "status": "COMMITTED",
        "stage": stage,
        "verdict": verdict,
        "source_head": ident.source_head,
        "source_tree_fingerprint": ident.source_tree_fingerprint,
        "detail": detail,
        "project_identity": _identity(root),
    }
    # Record-time ordered evidence (items 1/19): a stage may be recorded only
    # after its canonical predecessor exists, so the chain cannot be written
    # out of order even by an agent that ignores the sequence. E restarts are
    # legal (CONVERGE.md's F -> E loop when HUNT finds work).
    predecessor = {"F": "E", "G": "F", "H": "G", "I": "H"}
    if stage in predecessor:
        if _latest_convergence_stage(root, predecessor[stage]) is None:
            return _refuse(
                "VALIDATION_FAILED",
                f"stage {stage} requires a committed "
                f"{predecessor[stage]} receipt first -- the canonical "
                "sequence is E,F,G,H,I in order")
    if stage == "G":
        # CLEAN input identity comes from the latest committed F receipt; the
        # resulting identity is the LIVE tree after the CLEAN mutation.
        latest_f = _latest_convergence_stage(root, "F")
        if latest_f is None:
            return _refuse(
                "VALIDATION_FAILED",
                "CLEAN requires a committed forced HUNT (F) receipt first -- "
                "CLEAN must run on the source the test gate and forced HUNT "
                "proved")
        meta["input_source_head"] = (latest_f.get("receipt_metadata") or {}).get(
            "source_head", "")
        meta["input_source_tree_fingerprint"] = (latest_f.get(
            "receipt_metadata") or {}).get("source_tree_fingerprint", "")
        meta["resulting_source_head"] = ident.source_head
        meta["resulting_source_tree_fingerprint"] = \
            ident.source_tree_fingerprint
    event, line = _event_line(
        docs, log_tail, "DEC", None, agent,
        f"convergence stage {stage} ({STAGE_NAMES[stage]}) -- {verdict}"
        + (f": {detail}" if detail else ""), now, op_id)
    new_log = docs["log"].text_norm.rstrip("\n") + "\n" + line + "\n"
    new_state = patch_state(docs["state"].text_norm, {
        "last_event": event,
        "updated": utc,
        "agent": agent,
    })
    errors = validate_texts(new_state, docs["board"].text_norm, new_log)
    if errors:
        return _refuse("VALIDATION_FAILED",
                       "proposed convergence state fails fast validation: "
                       + "; ".join(errors[:5]))
    meta["event_id"] = f"E-{event}"
    targets = [
        _target(docs["log"], ".saipen/LOG.md", "log", new_log),
        _target(docs["state"], ".saipen/STATE.md", "state", new_state),
    ]
    return build_plan(
        "convergence_stage", agent, _identity(root),
        {"operation": "convergence_stage", "stage": stage,
         "verdict": verdict},
        _docs_preconditions(docs, "state", "board", "log"),
        targets,
        {"ok": True, "code": "CONVERGENCE_RECORDED", "stage": stage,
         "verdict": verdict, "event_id": f"E-{event}"},
        op_id=op_id, receipt_metadata=meta)


@_state_guard
def record_convergence(project_root: Path | str, agent: str, *, stage: str,
                       verdict: str, detail: str = "",
                       dry_run: bool = False) -> Result:
    """Commit one structured canonical convergence-stage receipt.

    PUBLIC convergence operation (Wave 2 item 1): the canonical E-I sequence
    records each executed stage through THIS operation, and the read-only
    verdict in saipen_engine.convergence proves the chain is current. E2E
    acceptance must use this operation -- never direct receipt fabrication.
    """
    root = Path(project_root)
    now, utc = _now(), _utc_iso()
    plan = _plan_convergence_stage(root, agent, stage=stage, verdict=verdict,
                                   detail=detail, now=now, utc=utc)
    if isinstance(plan, Result):
        return plan
    if dry_run:
        return _render_plan(plan)
    return apply_plan(root, plan)


def _render_plan(plan: OperationPlan) -> Result:
    """Render an OperationPlan as the dry-run result. Reads nothing live,
    writes nothing."""
    expected = dict(plan.expected)
    expected["op_id"] = plan.op_id
    expected["dry_run"] = True
    expected["changed_files"] = plan.changed_files
    return Result(ok=True, code=expected.get("code", "PLANNED"),
                  data=expected, op_id=plan.op_id,
                  changed_files=plan.changed_files)

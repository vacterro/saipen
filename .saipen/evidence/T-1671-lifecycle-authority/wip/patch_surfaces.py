"""T-1671 surfaces: registry code, fleet surface, status, validator. patch_surfaces.py <tree-root>."""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])


def patch(rel: str, edits: list[tuple[str, str]]) -> None:
    path = ROOT / rel
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new in edits:
        assert text.count(old) == 1, (rel, text.count(old), old[:80])
        text = text.replace(old, new)
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    print("patched", rel, "crlf" if crlf else "lf")


patch(
    "saipen/REGISTRY.json",
    [('  "HISTORY_LEDGER_CORRUPT",\n', '  "HISTORY_LEDGER_CORRUPT",\n  "UNAUTHORIZED_LIFECYCLE_WRITE",\n')],
)

patch(
    "tools/saipen_engine/fleet.py",
    [(
        '    "HISTORY_LEDGER_CORRUPT": "log",\n',
        '    "HISTORY_LEDGER_CORRUPT": "log",\n    "UNAUTHORIZED_LIFECYCLE_WRITE": "state",\n',
    )],
)

patch(
    "tools/saipen.py",
    [(
        '''    board = parse_board(board_text)
    doing = [t for t in board["tickets"].values() if t["section"] == "## DOING"]
    todo = [t for t in board["tickets"].values() if t["section"] == "## TODO"]
    done_tickets = [t for t in board["tickets"].values() if t["section"] == "## DONE"]
''',
        '''    board = parse_board(board_text)
    # T-1671: a lifecycle head no operation produced is not a status to
    # project. Reporting phase DONE and an idle route over a hand-written
    # completion is how the forgery became the project's truth; the refusal
    # carries the same route an invalid checkpoint does.
    from saipen_engine import lifecycle_authority as _lifecycle_authority

    _lifecycle = _lifecycle_authority.assess(project_root, state, board, snap.history_events)
    if _lifecycle["status"] == _lifecycle_authority.UNAUTHORIZED:
        _emit(
            {
                "ok": False,
                "code": _lifecycle_authority.CODE,
                "action": "saipen recover",
                "reason": "lifecycle-unauthorized",
                "detail": _lifecycle_authority.refusal_detail(_lifecycle),
                "lifecycle_authority": {
                    "floor": _lifecycle["floor"],
                    "head": _lifecycle["head"][:16],
                    "findings": [
                        {key: value for key, value in finding.items() if key != "detail"}
                        for finding in _lifecycle["findings"]
                    ],
                },
                "cold_route": _cold_route(project_root, state, state_text),
            },
            as_json,
        )
        return 1
    doing = [t for t in board["tickets"].values() if t["section"] == "## DOING"]
    todo = [t for t in board["tickets"].values() if t["section"] == "## TODO"]
    done_tickets = [t for t in board["tickets"].values() if t["section"] == "## DONE"]
''',
    )],
)

patch(
    "tools/saipen_engine/lifecycle_authority.py",
    [(
        '''        + " -- canonical lifecycle state exists only through an operation; "
        "`saipen continue` reconciles this through the journaled recovery and "
        "reopens what no operation closed"
''',
        '''        + " -- canonical lifecycle state exists only through an operation; "
        "`saipen recover` names the journaled repair that reopens what no "
        "operation closed"
''',
    )],
)

patch(
    "tools/validate.py",
    [(
        '''    # [gate-closure] (NITRO dogfood IV, T-602): a ticket's DONE state is
''',
        '''    # [lifecycle-authority] (T-1671, SRC-192): the three [saio] checks above
    # read the LOG alone, so each one judges a TAG. None of them asks whether
    # the canonical STATE and BOARD stand on an operation, and that is the
    # question the hand-written lifecycle answered wrong: untagged
    # `RUN: verify -> PASS` lines are legal semantic entries, a `## DONE` row
    # with `closure_mode` parses, and a STATE whose `last_event` names the
    # hand-typed tail is "fresh". `lifecycle_authority.assess` binds the two
    # surfaces to the newest event an operation record stands behind. Same
    # boundary as T-1282: no ledger on this checkout means UNAVAILABLE.
    if log_ok and _canonical_history_snapshot is not None:
        from saipen_engine import lifecycle_authority as _lifecycle_authority

        _lifecycle_last_event = (state or {}).get("last_event")
        if isinstance(_lifecycle_last_event, str) and _lifecycle_last_event.strip().isdigit():
            _lifecycle_last_event = int(_lifecycle_last_event.strip())
        _lifecycle = _lifecycle_authority.assess(
            PROJECT_ROOT,
            {"last_event": _lifecycle_last_event},
            {"tickets": tickets},
            _canonical_history_snapshot.events,
        )
        if _lifecycle["status"] == _lifecycle_authority.UNAUTHORIZED:
            fail(
                "lifecycle authority [saio] -- canonical lifecycle state stands "
                "on no operation: "
                + "; ".join(f["detail"] for f in _lifecycle["findings"][:4])
                + " -- run `saipen recover`; it names the journaled repair "
                "(T-1671)"
            )

    # [gate-closure] (NITRO dogfood IV, T-602): a ticket's DONE state is
''',
    )],
)

"""Read-only: lifecycle_authority.assess over real projects."""
import sys, time, json
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from saipen_engine import lifecycle_authority as LA, codec
from saipen_engine.log import read_history_snapshot
from saipen_engine.board import parse_board
from saipen_engine.state import parse_state_or_error, parse_frontmatter

for proj in sys.argv[2:]:
    root = Path(proj)
    try:
        st_text = codec.read_doc(root / ".saipen/STATE.md")
        state, err = parse_state_or_error(st_text)
        if err:
            state = parse_frontmatter(st_text)[0] or {}
        board = parse_board(codec.read_doc(root / ".saipen/BOARD.md"))
        t = time.perf_counter()
        snap = read_history_snapshot(root)
        t1 = time.perf_counter()
        v = LA.assess(root, state, board, snap.events)
        t2 = time.perf_counter()
        print(f"{proj}: {v['status']} floor={v['floor']} last_event={state.get('last_event')} head={v['head'][:6]} events={len(snap.events)} history={t1-t:.2f}s assess={(t2-t1)*1000:.1f}ms")
        for f in v["findings"]:
            print("    ", f["rule"], "|", f["detail"][:230])
    except Exception as exc:
        print(f"{proj}: ERROR {type(exc).__name__}: {str(exc)[:200]}")

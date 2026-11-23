"""T-2081 follow-up probe: converge entry projects a route the gate refuses.

Measured on the repository generation: on a CURRENT_FAIL fixture,
`set_converge_intent` writes `next_action: saipen crew` (target crew) or
`next_action: saipen continue` (target done) while `router.gate_route` on the
same bytes refuses the route. A host that reads STATE.next_action then
re-dispatches a refused action.

Run from this directory:
    python .saipen/evidence/T-2081/writer-probe.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

import unittest  # noqa: E402

from test_t1412_conformance_truth import T1412Base, write_receipt  # noqa: E402
from saipen_engine import operations, router  # noqa: E402
from saipen_engine.state import parse_state  # noqa: E402


class WriterProbe(T1412Base):
    def _measure(self, name, verdict, target):
        root = self.make_project(name)
        write_receipt(root, verdict)
        result = operations.set_converge_intent(root, "tester", target)
        state = parse_state(
            (root / ".saipen" / "STATE.md").read_text(encoding="utf-8-sig")
        )
        text = (root / ".saipen" / "STATE.md").read_text(encoding="utf-8-sig")
        board = (root / ".saipen" / "BOARD.md").read_text(encoding="utf-8-sig")
        raw = router.route_next(text, board, current_agent="tester")
        gated = router.gate_route(root, raw, agent="tester") if raw.get("ok") else None
        print(
            f"target={target} receipt={verdict} ok={result.ok} "
            f"state.next_action={state.get('next_action')!r}"
        )
        print(
            f"  raw:   ok={raw.get('ok')} action={raw.get('action')!r} "
            f"reason={raw.get('reason')!r}"
        )
        if gated:
            print(
                f"  gated: ok={gated.get('ok')} action={gated.get('action')!r} "
                f"reason={gated.get('reason')!r}"
            )
        else:
            print("  gated: none")

    def test_probe(self):
        self._measure("crew-fail", "FAIL", "crew")
        self._measure("crew-pass", "PASS", "crew")
        self._measure("done-fail", "FAIL", "done")
        self._measure("done-pass", "PASS", "done")


unittest.main(argv=["probe"], exit=False)

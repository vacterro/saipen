"""T-1886: the release gate runs with the writer mutex RELEASED.

Measured defect. `tools/saipen_engine/lock.py:812` already defines
`writer_lock_yielded` for exactly this purpose -- its own docstring cites
"T-1827 (SRC-282:R003)" and explains that a validator subprocess "can run for
minutes, and holding the only writer mutex across it makes every other
mutation refuse WRITER_BUSY for that whole span". The helper landed. Its
call site never did: a repo-wide search found **zero** non-test callers.

So `_apply_release` -> `_apply_release_locked` -> `_stage_and_commit` ->
`_run_gate` ran `validate.py --gate ship` while holding the one writer mutex.
Measured on this tree, that gate takes **19.3s**, and every other mutation is
refused for all of it.

What this module pins:

  * the gate observes a FREE lock, and the lock is free again afterwards --
    asserted from inside the gate callback, so it is the real state at the
    moment the subprocess would have run;
  * a writer that takes the mutex during the window is not silently built
    upon: the release refuses with WRITER_BUSY instead of committing;
  * `writer_lock_yielded` is actually CALLED by the production path (a spy on
    the real function), so deleting the integration fails this module even if
    a future refactor happens to leave the lock free by other means.

The fixture is the release-shaped one from `test_t1746_crew_terminal_outcome`;
it is given a VERSION and a ticket because `plan_release` requires both. The
sibling module `test_t1827_writer_lock_contract` asserts the same invariant but
calls `_shape()` with neither, so it dies in `plan_release` before reaching the
gate -- that is a fixture bug in that module, not evidence about the release.
Both are true at once: with a complete fixture the invariant holds, and the
incomplete one never measures it.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import lock as lock_mod  # noqa: E402
from saipen_engine import release as release_mod  # noqa: E402


def _fixture():
    """A release-ready fixture: VERSION + an owning ticket + narrow digests."""
    from test_t1746_crew_terminal_outcome import _DownstreamShape

    fixture = _DownstreamShape()
    fixture.setUp()
    # wide=False matches the digests the planner re-derives; ticket=T-11 gives
    # the crew carrier the scope it refuses to release without.
    fixture._shape(version="8.0.1", ticket="T-11", wide=False)
    return fixture


class ReleaseGateWindowTests(unittest.TestCase):
    def test_the_gate_runs_with_the_writer_mutex_released(self):
        fixture = _fixture()
        self.addCleanup(fixture.tearDown)
        plan = fixture._plan()

        seen: list[dict] = []

        def gate(root, name):
            # Read the REAL lock state at the moment the gate would spawn.
            seen.append(lock_mod.lock_status(root))
            return {"ok": True}

        ready, _gate, parity = fixture._patches()
        with ready, parity, patch.object(release_mod, "_run_gate", side_effect=gate):
            result = release_mod.execute_release(fixture.root, plan)

        self.assertTrue(result["ok"], result)
        self.assertTrue(seen, "the gate never ran")
        self.assertFalse(
            seen[0]["held"],
            "the ship gate ran while the writer mutex was held, so every other "
            "mutation is refused WRITER_BUSY for its whole duration",
        )
        self.assertEqual(
            lock_mod.lock_status(fixture.root)["state"],
            "free",
            "the mutex was not returned after the gate",
        )

    def test_a_writer_that_wins_the_window_refuses_the_release(self):
        """Fail closed: the lock is gone after the gate, so nothing may commit."""
        fixture = _fixture()
        self.addCleanup(fixture.tearDown)
        plan = fixture._plan()

        stolen: list[lock_mod.WriterLock] = []

        def gate(root, name):
            # A concurrent writer takes the mutex during the unlocked window.
            thief = lock_mod.WriterLock(root, timeout=0)
            thief.acquire()
            stolen.append(thief)
            return {"ok": True}

        self.addCleanup(lambda: [lock.release() for lock in stolen])
        ready, _gate, parity = fixture._patches()
        with ready, parity, patch.object(release_mod, "_run_gate", side_effect=gate):
            result = release_mod.execute_release(fixture.root, plan)

        self.assertFalse(
            result["ok"],
            f"a release must not commit after losing the mutex: {result}",
        )
        # Two honest answers, depending on which layer notices first: the full
        # path reports SHIP_GATE from `_stage_and_commit`, while the no-publish
        # path lets the PermissionError reach `_apply_no_publish`, which already
        # answers WRITER_BUSY. Both mean the same thing -- the release stopped
        # and wrote nothing -- so the assertion is on that, not on the label.
        self.assertIn(result["stage"], {"SHIP_GATE", "WRITER_BUSY"}, result)
        self.assertNotEqual(
            result.get("code"), "RELEASED", f"a lost race must not release: {result}"
        )

    def test_the_production_path_calls_writer_lock_yielded(self):
        """A spy on the real helper, so removing the call site fails here."""
        fixture = _fixture()
        self.addCleanup(fixture.tearDown)
        plan = fixture._plan()

        calls: list[object] = []
        real = lock_mod.writer_lock_yielded

        def spy(lock, **kwargs):
            calls.append(lock)
            return real(lock, **kwargs)

        ready, _gate, parity = fixture._patches()
        spy_patch = patch.object(lock_mod, "writer_lock_yielded", side_effect=spy)
        gate_patch = patch.object(release_mod, "_run_gate", return_value={"ok": True})
        with ready, parity, spy_patch, gate_patch:
            result = release_mod.execute_release(fixture.root, plan)

        self.assertTrue(result["ok"], result)
        self.assertTrue(
            calls,
            "the release never yielded the writer lock; writer_lock_yielded has "
            "no production caller and the gate holds the mutex again",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

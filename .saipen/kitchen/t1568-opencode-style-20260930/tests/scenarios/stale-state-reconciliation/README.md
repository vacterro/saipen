Test: Agent should rebuild STATE.md based on LOG.md and BOARD.md because STATE.md is older than LOG.md.
expect: pass

The point of this fixture is a STATE that is *stale* (updated 2020-01-01,
older than LOG/BOARD) yet structurally sound -- staleness is a semantic
problem the validator does not judge, so it declares `expect: pass`.
Its `next_action` read a bare `plan` until v7.101.0, which is not one of
RFC § 1.2's five executable forms. The fixture was quietly non-conformant
and stayed green only because the prefix rule was a WARN; promoting it to
FAIL surfaced this immediately. Now `saipen plan`, a real § 1.10 command,
which keeps the fixture's meaning and its shape.

`tools/run_scenarios.py` also uses this legacy state as an executable
schema-v2 migration probe. It proves six boundaries by running the canonical
validator each time: legacy absence warns but remains readable, v2 absence
fails, the exact tail passes, an advanced LOG makes STATE stale, Recovery's
new exact value passes, and a value above the LOG fails as corrupt.

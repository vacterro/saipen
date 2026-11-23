Test: an agent finishes a checkpoint and confirms what it actually wrote.

RFC § 1.5 orders the three writes LOG -> BOARD -> STATE so that a crash always
leaves `STATE.md` behind the other two, never ahead. That protects against a
crash *between* steps. It said nothing about the step itself producing a
malformed file.

A real incident: an agent completed a checkpoint whose `STATE.md` simply had
no `next_action` and no `blocker` -- both REQUIRED by § 1.2. Nothing caught
it. `tools/validate.py` does catch it, but the pre-commit hook only runs at
commit time and this checkpoint was never committed, so the project's live
continuation state was a file a cold agent cannot start from. `next_action`
missing means TEST-001 -- the one guarantee this protocol exists to make --
fails outright, on a project that otherwise looked perfectly healthy.

§ 1.4 already had the guard for the analogous case: after writing a claim, an
agent MUST re-read `BOARD.md` and confirm the claim survived. Identical
failure mode, and until v7.84.0 only one of the two paths was protected.

So: after step (3), re-read `STATE.md` and confirm every field RFC § 1.2's required set names -- read it there, never from a count repeated here (this line said "eight" until v7.101.0; the set has been nine since v7.92.0, which is exactly the drift § 1.2 now forbids other documents from reproducing)
are present and non-empty (`phase`, `task`, `next_action`, `blocker`, `agent`,
`saipen_version`, `mode`, `updated`). Missing one, fix it before doing
anything else. Where a validator is reachable, run it -- cheaper and more
reliable than eyeballing.

The failure this catches: a checkpoint that reports success, looks fine in
chat, and cannot be resumed from. That is not a checkpoint.

Behavioral, README-only: the assertion is about an agent verifying its own
write, which no static fixture can express -- a fixture would only show the
already-broken end state, which `tools/validate.py` catches anyway. Correctly
declares no expected outcome, so `tools/run_scenarios.py` skips it.

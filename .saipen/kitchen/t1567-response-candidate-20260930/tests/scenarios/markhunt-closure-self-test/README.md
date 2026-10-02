Test: a MARKHUNT pass runs to what looks like the end. Before it may
transition to `DONE`, it self-verifies its own manifest in
`.saipen/kitchen/markhunt_progress.md`: `cursor: done`, all five scope
categories present in `vectors:` (a missing vector = surface not exhausted,
keep going), `head_end` equal to the current `git rev-parse --short HEAD`
(HEAD moved mid-pass = coverage against a stale tree, re-run the moved part),
and `findings:` equal to the number of `[MARKHUNT]` tickets it actually wrote
to `## BLOCKED`. Any mismatch means the pass is not done and must be resolved,
never rounded up. The completion LOG line carries the manifest summary
(`markhunt -> N findings, V/5 vectors, @head_end`) so coverage stays auditable
from permanent history after `kitchen/` is swept -- a later VALIDATE or human
checks that `N` matches the board's `[MARKHUNT]` tickets and `V` is `5`. This
is the manifest-driven closure check T-136 asked for -- the verifiable
thoroughness gate HUNT gets from its exact hash-match skip and MARKHUNT
previously lacked (completeness was pure self-report). Behavioral test (agent
decision-making about not declaring a pass complete until the manifest
closes), not a structural one -- no `validate.py` field is added; the closure
is self-enforced and recorded in the LOG line.

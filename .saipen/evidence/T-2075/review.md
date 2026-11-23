# T-2075 -- Core disposition of saipython/PY-19

- package: saipython/PY-19, package_identity sha256:361c2016f7667798c87cef28226a05cb65ee060315ab74bf176cfbefa46ab31c
- source at review: dc39709c0c17a3272126c01a626ffcaa4176140b / git-delta-v1:f3dab073ebbfbd9021d22a0e63c2cbba72094bb6ff587c16e670aa98bd38e1d7
- verdict: VERIFIED-ACCEPTED (independent reviewer pen; every load-bearing claim reproduces)

## Independent measurements (`reviewpen/`)

A fresh pen was built from the live tree, not from the producer's pen: `base/` holds
gc.py (sha256 f1921568...) and lock.py (30965c05...) copied at review time; `patched/`
is the same bytes with `kitchen/PY-19.patch` applied by `git apply -p2`, yielding
gc.py sha256 9fab03b31cc46219..., exactly the producer's recorded patched hash. The
harnesses were re-derived from the package's scripts with overlay paths pointed at this
pen.

- `baseline.out` (unpatched overlay, forced canonical_total barrier): `durable_failures: 1`,
  codes `GC_MAINTENANCE_FAILED` + `GC_RUN_COMPLETE`, `counted_done: ["T-001"]` against
  canonical `["T-001","T-002"]` -- the lost-checkpoint race reproduces.
- `verify.out` (patched overlay, start barrier, no inner barrier -- the harness shape
  PY-19 records): 8/8 rounds, `durable_failures` all 0, both closures counted every
  round.
- `suite.out`: `Ran 63 tests`, `OK (skipped=1)`, exit 0.

One construction note for future reviews: running the *baseline* harness against the
patched overlay reports durable failures by construction, because its inner barrier
makes the lock holder wait past the acquisition timeout while the second thread queues
on the lock. That is a harness interaction, not a patch defect; the two harnesses answer
different questions and were run against their own overlays here.

## Disposition

VERIFIED-ACCEPTED. The patch is correct, bounded and applicable, but it is NOT
integrated: T-2062 still needs BLOCKED T-2059, and the package's own instructions say
not to integrate before that dependency clears. No package patch is applied in the main
tree by this review.

Closure cannot be told truthfully while publication is blocked (`own_patch` would
assert a patch that this ticket did not make, `inherited_verified` cannot resolve
without published release evidence, `finding_invalidated` would falsify a reproduced
premise). The ticket parks on the T-2058 publication staging authority, with the review
evidence ready for the release gate.

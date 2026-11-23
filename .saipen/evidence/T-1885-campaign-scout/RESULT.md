# T-1885 RESULT — unreadable tag objects are now reported, not silently verified

## The defect, measured

The orphaned-release-tag check in `tools/validate.py` builds its peel map from
one bulk `git for-each-ref refs/tags` call. That command refuses the WHOLE tag
set when any single tag names an object the clone cannot read: it exits 128
with no rows. The old code left the map empty, every lookup returned None,
zero candidates were built and — critically — **zero tags were reported as
unchecked**. A damaged object store therefore validated exactly as cleanly as a
tagless project.

On this checkout the damage is real: 394 of 394 local tags fail to peel.

```
fatal: missing object 35b122bf7f8c3b0365e805de74a50e7a325a1b10 for refs/tags/v1.0.0
```

Before the fix that was silence. The release-ledger block printed only "2
release(s) have a CHANGELOG entry but no git tag: v8.0.2, v8.1.0" and the
orphan check contributed nothing.

## The change

`tools/validate.py` now records the bulk call's failure, still evaluates every
tag it CAN peel (via the pre-existing per-tag fallback), and emits one
`release-ledger` warning with exact counts when anything was unreadable:

```
394 of 394 local tag(s) could not be peeled to commits, so the
orphaned-release-tag check verified 0 of them and none of the rest
(first error: fatal: missing object 35b122bf... for refs/tags/v1.0.0).
A tag whose object is absent cannot be distinguished from one whose commit
rides no remote branch: restore the missing objects (a fetch from a remote
that still has them) and re-run.
```

The warning names the counts, not just the condition, because an operator
cannot judge severity from "some tags are unreadable". A genuinely tagless
project still produces no warning: the decision consults
`_tag_peel_failed`, not an empty map.

## Proof — three independent halves

| # | Form | Command | Verdict |
|---|---|---|---|
| 1 | Single-variable A/B, identical tree | `ab-prefix.log` vs `ab-post.log` | 42 problems both; warnings 50 → 51; the one new warning is this guard |
| 2 | Live-repo control | `tag-guard-control.py` (probe tag's object removed, then restored) | `RESULT: OK`; unreadable 394 → 395 → 394, verified 1 → 0 → 1 |
| 3 | Unit module | `python -B -m unittest tools.test_t1885_tag_peel` | OK, 7 tests |

The red half of (2) is that this checkout is already damaged, so the control
proves the warning is a *measurement* that tracks flips rather than a constant.
The half that says "silent before the fix" is (1): same tree, same command, one
variable changed, and the warning appears only after the change.

Red control for the module, reproducible with no repository residue:

```
T="$(mktemp -d)/prefix_validate.py"
git show HEAD:tools/validate.py > "$T"
SAIPEN_T1885_VALIDATE="$T" python -B -m unittest tools.test_t1885_tag_peel
-> FAILED (failures=2): _tag_unreadable absent, peeled-to-commits warning absent
```

Green control: `python -B -m unittest tools.test_t1885_tag_peel` → `OK`.

## Focused gate

```
python tools/core_unit.py focused T-1885 --pattern test_t1885_tag_peel.py
{"verdict": "PASS", "ran": 7, "reused": false,
 "record": ".saipen/evidence/focused-unit/8b19c31388a1aa8b-20261024T171518279476Z.json"}
sha256 38f7def41b87559106aece771aafc725f244cdf0cca4813d5059cc0511cbc520
```

`reused: false` and `shared: false` — this is fresh execution on the current
tree, not an inherited receipt.

## Scope honesty

This ticket repairs the validator's *instrument*, not the object store. It does
not restore the 889 missing commits or the 395 dangling tags; it makes their
absence impossible to mistake for a clean tag set. Recovery needs a fetch from
a remote that still holds those objects, which is a network mutation outside
this ticket's authority.

What is NOT claimed: the full family is green (it is not; 55 foreign reds
remain, and `tools/core_unit_baseline.json` was not touched), the release is
publishable (206 of 216 staged paths are foreign), and the installed runtime
carries this fix (deployment still refuses on 437 foreign injected-surface
paths).

# T-1603 independent REVIEW — pass 1

## What the diff actually is

One file, `tools/run_scenarios.py`, `+60 -11` in two hunks inside
`run_nitro_m3_probes` and `run_nitro_integrity_probes`. No production module is
part of this repair: `tools/saipen_engine/operations.py` is absent from the
working diff, `tools/saipen_engine/journal.py` carries exactly one line and it
belongs to T-1507 (`"source.receipt-range-"` in `OP_CLASSES`), and
`tools/test_fixture_support.py` is untouched. Group discovery, the baseline, the
timeout and every production assertion are unchanged.

So this is a fixture repair, and the fixtures ARE the check under review. That
makes "did the check move?" the whole question here, not a formality.

## What moved in the CHECK, and whether it weakened anything

**1. Three goal probes now run under `witnessed_operator`.** The fixture called
`goal_entry` directly with no carrier. Committed production has an ingress
authority gate there (`operations.py:7917-7948`): an unwitnessed request is not
refused but routed to `start_work` as a local candidate and never demotes an
active ticket or pivots intent. The fixture asserted `GOAL_SET`; production
correctly answered `USER_REQUEST_RECORDED`. The failure was the oracle, not the
product — the probe was asking a question the door no longer answers for a
model.

`witnessed_operator` is the existing shared helper, and it is faithful, not a
mock that bypasses the check: `operator_request_env` sets
`SAIPEN_TASK_SHA256 = ingress_digest(text)` for the exact objective string.
`operator_task.witness` compares that digest against the text that arrived and
REFUSES on mismatch (`operator_task.py:210`). An ambient `SAIPEN_TASK_FILE`
left over in the process could not create a false green either — a divergent
carrier refuses loudly rather than passing quietly.

**2. Net-new negative controls, not removed ones.** The repaired subject ADDS
four assertions that did not exist before: unwitnessed goal preserves active
Work, phase and bounded counters; unwitnessed goal stays a model-supplied
`## TODO` candidate; an idle unwitnessed goal is usable without goal pivot or
operator grant; and conflict inspect leaves `LOG/STATE/BOARD` byte-identical.
The suite got stricter, not looser.

**3. `safe_resolution_classes` widened from two names to three.** This is the
one assertion that changed to accommodate behavior, so it is checked against
production, not accepted: `journal.py:674` declares
`RESOLUTION_CLASSES = (accept_live, replan, reconcile)`, and `inspect_op`
(`journal.py:4269-4271`) returns `list(RESOLUTION_CLASSES)`. T-1398 added
`reconcile` and its `_reconcile_and_verify` body is present; the scenario oracle
was never updated to match. The expectation is a strict equality against the
real tuple, so it is stricter than the two-name version it replaces.

**4. Credential-redaction probe also asserts the call returned ok.** Strictly
added.

No verifier command, threshold, denominator or negative control was relaxed
anywhere in this diff.

## Independent re-run (this cycle, not VERIFY's claim)

Fixed external driver `run_pair.py`, SHA256 `3918c1b07d3f0e15`, unchanged, run
on the current tree with production bytes untouched:

| label | subject sha256 | checks | failures |
|---|---|---|---|
| green | `786e69f7d96cf857` | 230 | 0 |
| red (preserved original) | `c3771799a05d88a3` | 227 | 8 |
| bad-authority | `786e69f7d96cf857` | 39 | 3 |
| bad-conflict | `786e69f7d96cf857` | 191 | 1 |

Artifacts `review-<label>.json/.txt`. The BUILD-cycle pair is preserved
untouched as `<label>.json/.txt`; VERIFY's own rerun remains as
`<label>-current-cycle.json`.

**The pre-fix FAIL belongs to the verifier now passing.** The preserved red
subject's eight failures are exactly: seven goal probes answering
`USER_REQUEST_RECORDED` where the stale fixture demanded `GOAL_SET`, and the
conflict probe expecting a class list production stopped returning. No
production byte differs between red and green, so nothing in the product was
adjusted to make a check pass.

**This verifier can still see the original bug.** Running it against the
byte-identical original capture reproduces all eight failures on demand.

**The negative controls are live, not decorative.** `bad-authority` forces
`goal_pivot=True` on unwitnessed ingress and the three NEW assertions fail —
the fixture now detects exactly the defect class the repair is about. The
`bad-conflict` control strips `reconcile` back out and the inspect assertion
fails. A weakened oracle could not produce those reds.

## Native complete gate, independently re-checked

`full-current/verify-scenarios.txt` SHA256 recomputed by me:
`85b695fddcdf9b87ceef4ed3d5453b8793ef853f09f08e229c8e9fa954fb3a31`, identical
to the bound value. The file contains 1303 `PASS` lines, zero `FAIL` lines, and
its closing line reads `44 of 44 probe group(s) reached a verdict; 1354 grouped
check(s) executed`. `full-current/binding.json` binds scenario bytes
`786e69f7…ad0383dca`, the same fingerprint `54ad859af386ae71` and the baseline
digest used by the unit record. The snapshot the command ran in is a copy of the
same tree; the live source fingerprint was unchanged across the run.

I did not re-run the 2000-second aggregate. That is recorded as reuse under an
unchanged bound fingerprint, not as an independent second observation.

## Classification

* P0 / P1: none. No data-loss, authority, or security defect in the diff or in
  what it covers.
* P2: the post-test collector cannot delete a copied read-only Git object. It
  exits 1 AFTER the proofs are written, which is why it is not reported as a
  successful finalization. Already owned by T-1604; not re-filed here.
* P3: none.

## Retry cap

`review_passes: 1`. No finding was raised, so nothing is awaiting a second
pass.

## Verdict

`DEC: SHIP` — the exact scenario authority drift is repaired in the fixture
only, the original bug remains reproducible through the same verifier, and the
repair added detection where it removed none.

## Memory promotion

NO. The lessons worth keeping here — Windows share/symlink refusals and
copied-provenance trees — are already owned by existing memory cards, and this
repair restates a rule the codebase already encodes in
`test_fixture_support.operator_request_env`. A card written now would duplicate.
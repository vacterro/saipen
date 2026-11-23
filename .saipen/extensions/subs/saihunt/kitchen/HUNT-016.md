# HUNT-016: bounded six-signal sensor sweep at 66ef622a

Source identity measured at capture time: HEAD
`66ef622a43ab59512735ac78ce10d1250e26f9df`, tree fingerprint
`git-delta-v1:374d12a0eb91a5d768a66863eec29c4ea0fa03a0a02190301ca437dabb5fa208`
(resolved by the engine's own resolver and reported by both `saipen crew --json`
stage SC-2 and `tools/validate.py`), charter `sha256:4edb04181cb07e0946afd06fbe711166fa9dcc403e56b52e9be3844f0a71b0a5`.

This package supersedes the uncommitted `HUNT-017.md` / `HUNT-018.md` scratch
drafts, which were bound to earlier tree fingerprints (`ad029851`, `70f5cdf4`)
and never reached the OUTBOX. Their measurements were re-taken here rather than
inherited.

Raw captures: `_hunt016_validate.txt`, `_hunt016_registry.txt`,
`_hunt016_t1430.txt`, `_hunt016_signals.txt`, `_hunt016_signals46.txt`,
`_hunt016_signal4.txt`, `_hunt016_silent_engine.txt`.

## Finding 1 -- core conformance is RED: 17 problems, one reproduced class with 12 copies (REPRODUCED)

`python -B tools/validate.py` exits 1 with `Validation FAILED: 17 problem(s),
27 warning(s)`. Verbatim list in `_hunt016_validate.txt`.

- Verdict: **REPRODUCED**.
- Class A (12 of 17): the runtime manifest names files git does not track --
  `tools/_t2040_experiment.py` plus eleven `tools/test_t2040_*.py` files.
  These exist in this home and in no clone, so this home ships complete and a
  checkout of it does not. `git status --porcelain tools/` counts exactly 12
  untracked entries, matching the 12 FAILs one-for-one.
- Class B: closure provenance does not resolve for `EX-000023` -- verified
  against installed engine generation `sha256:6070fc317babd47f...` while the
  running engine is `sha256:7b6c456baa153ea9...`, and its external ticket T-289
  is absent from the external board.
- Class C: DONE Work `T-1606` still carries unresolved source receipt
  `SRC-167` (nine actionable clauses unresolved).
- Class D: BOARD Work `T-1953` references missing source receipt `SRC-346`.
- Class E: STATE.md audit route not followed -- the audit inbox routes
  `saipen audit ingest` but `next_action` is `saipen crew`.
- Class F: translation README badge drift in 32 locale files.
- Instrument control: the same validator reports 27 warnings (board soft cap,
  uncollected ready entries, cross-doc drift, translation staleness, an
  untagged CHANGELOG release), so this is a RED measurement, not a vacuous
  scan.

## Finding 2 -- refusal registry and crew-receipt tests are GREEN (NOT_REPRODUCED as defect)

`tools/test_refusal_registry.py` runs 6 tests, all `ok`, exit 0.
`tools/test_t1430_crew_run_receipt.py` runs 3 tests, all `ok`, exit 0.

- Verdict: **NOT_REPRODUCED** as defect.
- Positive control worth recording: an earlier capture
  (`_hunt019_registry.txt`) failed this same module with six production refusal
  codes absent from `REGISTRY.json` (`DUPLICATE_CREW_RUN`, `GC_CONFIG_REFUSED`,
  `GC_DEFERRED`, `GC_DISABLED`, `GC_LOCKED`, `GC_RUN_UNKNOWN`). At this tree it
  is green, so that historical failure is retired, not inherited.

## Finding 3 -- swallowed-exception census (REPRODUCED, small and bounded)

At this tree the exact string `except Exception: pass` appears 3 times in
`tools/saipen_engine/`, all inside comments or docstrings
(`journal.py:4801`, `conformance.py:286`, `conformance.py:1539`) and 5 more
times in `tools/` outside the engine. A general `except <Any>: pass` census
over `tools/` yields 0.

- Verdict: **REPRODUCED** as a measured count, NOT as a defect claim: 8 hits at
  this tree is candidates + false positives (comments), not eight swallowed
  failures. A prior capture at a different tree counted 30 in the engine; the
  count is tree-dependent and is not comparable across sweeps.

## Finding 4 -- newest commit is verified in the main LOG (NOT_REPRODUCED)

`git log --oneline -1` is `66ef622a4 fix(t1950): resolve EX-000022 by correcting
the oracle and carrying the external bytes`, and `66ef622a` occurs in
`.saipen/LOG.md`.

- Verdict: **NOT_REPRODUCED** as defect (signal 2 clean).

## Finding 5 -- stale markers are abundant and unresolved (REPRODUCED as census, not defect)

862 TODO/FIXME/HACK hits under `tools/`, 132 of them on `## TODO`/`## DOING`
board headings.

- Verdict: **REPRODUCED** as a census. No individual marker is claimed stale
  without its own check; HUNT-013's true TODO defect is not re-asserted here.

## Finding 6 -- dead-code census, bounded and dominated by false positives (NOT_REPRODUCED as defect)

An AST pass over 14047 `def`s in `tools/` finds 8512 with zero textual
references. The first hits are dunder methods (`__bool__`, `__contains__`,
`__post_init__`, `__exit__`) which are called implicitly, so the census cannot
distinguish dead code from any dynamic dispatch.

- Verdict: **NOT_REPRODUCED** as defect. Reported as a bounded measurement with
  its limitation stated; HUNT-015's specific orphan-writer finding is superseded
  here only insofar as its source identity differs.

## Finding 7 -- saihunt's own OUTBOX carries a dangling kitchen reference (REPRODUCED)

`kitchen/OUTBOX.md` package `HUNT-015` points its reader at
`kitchen/HUNT-015.md`, which does not exist (checked after exact path
resolution). Its details, coverage and instructions therefore rest on a file
nobody can open.

- Verdict: **REPRODUCED**. saihunt cannot repair a package another session
wrote, and this is its own folder, so it is reported rather than fixed.

## Limitations

Bounded to the surfaces named in `coverage`. Signal 1 was measured with two
targeted modules plus the canonical validator, not the full suite. Signals 3,
4 and 6 are string/AST censuses: counts are reproducible, individual claims are
not. No main-project file was read-modified or written.

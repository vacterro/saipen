# T-1953 BUILD — the repair, and what it measured

Two changes, both SAIPEN-owned, both with a measured before and after. The
consumer project was read throughout and never written.

## Change 1 — reuse the record that already answers

`tools/saipen_engine/suite_record.py`

`current_record` (newest admissible record of the DECLARED command whose tree
is the current tree) and `_admissible` (engine's record shape for that command
digest) already existed and were already correct. `run` never asked them.

Added `reusable_record(root)`: the conjunction that makes a PASS mean what it
says, with the reason for each refusal named.

```
found = current_record(root)
  -> None: "no record of the declared suite describes the current tree"
verdict/status not PASS
  -> "the current record is FAIL, not PASS"
totals missing or ran == 0
  -> "the current record counts no test, so it proves no run"
tree_changed_during_run
  -> "the tree changed while that record was being written"
else
  -> reuse, "the current record PASSed the same bytes of the same command"
```

Added `reuse_line(written)`: writes `SUITE-EVIDENCE PASS-REUSED runner:... ran:...
red:... skipped:... exit:... command:<digest16> record:<path> sha256:<digest>`.
It cites the immutable record; it never restates a count it did not measure.

`_EVIDENCE_RE` gained `(?P<reused>-REUSED)?`, so a reader -- human or machine --
can always tell a reuse from an execution. A reuse that parsed as an ordinary
`PASS` would be the one way this repair could launder evidence.

`_run` gained `--reuse` (opt-in, `_take_reuse`). A request that cannot be
granted still executes and reports `reuse_withheld: <the one fact that failed>`,
so a refusal to reuse is as legible as a reuse. The journal entry is still
written (`holding` + `operations.checkpoint`) either way: reuse removes the
execution, never the evidence trail.

## Change 2 — one nested untracked directory no longer disables identity

`tools/freshness.py`

`git ls-files -o` spells an untracked directory with a trailing slash
(`contributions/.tooling/upstream-parser/`). `_path_from_git` raised
`non-canonical path`, `compute_source_identity` failed for the whole tree, and
PERF-001's single-identity threading degraded to `None` -- so `status` derived
the same identity four times and failed four times.

- `_path_from_git`: strip exactly one trailing slash before the canonicality
  test. `..`, `.`, absolute, empty and NUL paths remain refused (pinned).
- `_record_current` and `_record_evidence`: an untracked directory git did not
  enter is recorded as `kind=b"D"`, mode `0o040000`, empty content -- presence,
  not descent. Same rule `suite_record._git_subject` already applies.

## Measured — launch cost is not the bottleneck

7 samples, `perf_counter` around `subprocess.run`:

```
bare python -c "import sys"      median  32.6 ms
engine via saipen.cmd (refused)  median 203.8 ms
engine direct (refused)          median 192.9 ms
```

The handoff's "10-30 seconds per CLI launch" is not what this machine does. One
launch is 0.2 s; twelve is 2.4 s.

## Measured — the suite is the cost, and the consumer re-ran it

Consumer `_BZDECOMP`, 273 suite records, 78 distinct tree subjects:

```
all recorded suite time          27172 s = 7.5 h
redundant on duplicate subjects  19675 s = 5.5 h
since 2026-10-26                 14631 s = 4.1 h redundant
```

`86bb24cf8c38`: executed 66 times for 4211 s where one 123.7 s run answered all
of them. Same declared command, same 16 tests. The suite also got slower on its
own -- median 1.5 s across Oct 15-19, 451.0 s across Oct 28-29 -- which is the
consumer's own drift, reported here and not claimed as repaired.

## Measured — before/after on a disposable fixture

A 30 s suite (3 tests x 10 s sleep), rebind-home'd to the V: install, closing
through the SAME nine-call sequence the script uses
(`checkpoint, transition BUILD, checkpoint, transition VERIFY, test suite,
checkpoint, transition REVIEW, checkpoint, transition SHIP`):

| | per call | total |
|---|---|---|
| before (suite re-executes) | `0.24 0.27 0.24 0.27 30.40 0.25 0.28 0.24 0.29` | **32.48 s** |
| after (`--reuse`) | `0.25 0.25 0.24 0.28 0.27 0.23 0.28 0.25 0.27` | **2.32 s** |

**14.00x on the same nine calls**, all nine `CHECKPOINTED`/`TRANSITIONED`/
`SUITE_REUSED`. Three closures over the same tree: 91.6 s -> 31.3 s (2.93x),
where the first still pays the 30.5 s and each reuse costs 0.39 s.

The saving is exactly `suite_time x (closures - 1)` per unchanged tree. It does
not shrink the suite, and it does not make a slow suite fast.

## What was not changed

- No batch API. Each call still validates itself, writes its own journal entry,
  and honours phase legality -- 9 calls before, 9 calls after.
- No duplicate reuse framework. `reusable_record` is `current_record` +
  `_admissible` + three facts, not a second mechanism.
- No consumer-project write. Its records were read; its tree is untouched.
- No claim that the suite is faster. It is not; it is simply not run again for
  a tree whose bytes have not moved.

## The remaining 2.3 s per closure

Nine calls at ~0.25 s each. `status` is a separate, larger question: 4.4 s
before this work and 9.35 s after, because source identity now SUCCEEDS where
it used to fail fast. That is a real regression on a read-only command, it is
caused by correctness, and it is left measured rather than hidden. The cost is
5 237 untracked files read three times for the stability proof; the `.saipen`
pathspec already spares the rest.

## DEC

**DEC-6** The `status` slowdown from 4.4 s to 9.35 s is reported, not papered
over. Before, four consumers each failed to compute identity in ~1.1 s total;
now one consumer computes it correctly in ~5.9 s. A correct identity is worth
more than 5 s on a read-only command, and a caller that needs the identity will
pay it anyway. Reducing that 5.9 s is a separate ticket with its own measurement,
not a side effect of this one.

**DEC-7** The fixture writes its execution counter OUTSIDE the project. A
counter inside the tree moves the subject mid-run, and `tree_changed_during_run`
then withholds reuse for a reason that has nothing to do with reuse. The
regression test encodes that as a deliberate choice, not an accident.

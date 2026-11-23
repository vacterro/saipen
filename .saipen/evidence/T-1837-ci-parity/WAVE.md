# T-1837 — one full-unit execution engine

Parent T-1829, SRC-285 R007 and directly affected shard safety. This is a local
wave report, not campaign completion or a hosted CI/publication receipt.

## Change and expense

The existing `tools/test_runner.py --family unit` entry point and local
`run_canonical_suite` now call `core_unit.run_family`, retaining the one
`_families` declaration. The family CLI avoids its previous outer copy because
the existing full engine already owns an immutable consistent snapshot.
Other canonical families remain independently required and unchanged.

The CLI accepts positive `--jobs N`; default one. CI admits zero red with
`core_unit.judge(run, [])`, including red listed in an inherited baseline.
It creates no lifecycle evidence/citation and rejects scoped, empty-whole,
incomplete, timeout, invalid partition and failed cleanup results. Bounded
startup/output tails accompany exact failing names and causes, so moving to
the full engine does not remove diagnostic visibility.

Actual imported-TestCase controls exposed an existing sharding defect: a
planned alias/helper module may own zero defining-module occurrences, while
the catch-all owns every canonical occurrence. CPython 3.11 returns zero for
that empty worker; 3.12 returns five. The old judge refused both. Only a valid
exact nonempty inventory/partition proof now makes an empty worker neutral.
Its raw count/status/exit remain visible under `shards`, with `empty_shards`
identifying those workers. A whole empty family, lost/duplicate occurrence,
missing/mismatched digest, import error, timeout or unrelated exit still fails.
This does not mark any omitted or skipped assertion as executed.

An initial new check confused the historical `processes_leaked` field with a
post-cleanup observation. Existing T-1633 controls and `ProcessTree.__exit__`
prove it names descendants observed before owned reaping. That field retains
its meaning; actual CLI tests separately prove each observed child gone after
return. No existing ownership assertion or process cleanup was removed.

## Measured concurrency, same scope

`benchmark_concurrency.py` freezes four real modules: hermetic environment,
shards, cleanup and exact membership. All three worker counts run the same 46
canonical occurrences, with the same source/inventory digest and no test red.
The reduced corpus contains runtime code and real subprocess/copy/cleanup
controls; it is not the live complete family or its 1.3 GiB canonical state.

| Host/runtime | 1 worker | 2 workers | 4 workers |
|---|---:|---:|---:|
| Windows, managed Python 3.11.9 | 13.256 s | 10.665 s | 11.164 s |
| Native Ubuntu, Python 3.12.3 | 3.719 s | 2.438 s | 2.606 s |

Two workers improve this bounded sample; four lose some of that benefit.
Each is one direct sample, not a distribution or hosted-run measurement.
Reports preserve actual copy/hash/execution/cleanup wall stages and summed
discovery process time separately. Peak memory was not observed. No antivirus
or operator implementation-time inference is made.

The existing canonical workflow explicitly keeps `--jobs 1`. The small corpus
does not size the hosted runner's whole-state I/O/memory, and no GitLab CI run
was activated or witnessed. Its portable family interface is available for
subsequent host-specific measurement; no unsupported universal optimum.
Raw measurements: `concurrency-windows.json` / `concurrency-linux.json` plus
their per-run reports. This is no production-suite speedup claim.

## Regression and current evidence

* Final new controls: 15 PASS on Windows and native Ubuntu. Logs are
  `windows-partition-corrected.log` and `linux-partition-corrected.log`.
* Existing Linux process ownership controls: six PASS
  (`linux-process-ownership.log`). The bounded concurrency runs independently
  execute all 46 controls, including real cleanup, on each platform.
* `oracle-pair.json`: unchanged final dispatch oracle and unchanged final
  empty-partition oracle each FAIL on the saved old subject and PASS on the
  corrected subject. Exact final oracle SHA256:
  `d922350b7aa479e3c141b4e051f40a3d2be8404c14f782c4086a62047cf0f2f9`.
  These are controlled subject pairs with adjacent infrastructure held current,
  not invented historical full checkouts. Earlier failed logs remain preserved.
* Managed-runtime current scoped package: PASS, 177 reported, duration
  248.875 s, first request 260.688 s. It covers new dispatch/partition controls,
  full/focused/impact gates, shards, cleanup/process ownership, single-flight,
  failure roster, UTF-8/refusal/reachability source contracts.
  Record `.saipen/evidence/focused-unit/d23c49152ef1f81d-20261020T184050402278Z.json`,
  SHA256 `d1b0f75f724b65a36d93e5e0f4aaacb85db9ab082e143527238f0c63f055e098`.
* REVIEW independently requested that exact unchanged package and reused it
  in 8.735 s. One execution, two legitimate consumers; no 354-test-run claim.
* Scoped Ruff 0.16.0 and whitespace checks PASS. Managed Python has no Ruff
  module, so lint used the installed Python with the verified pinned version.

The current 177-control record measures copy 70.797 s (subject 25.188 s,
canonical state 45.250 s, one consistent-copy attempt), execution 159.031 s,
hash 0.141 s, identity 2.594 s and cleanup 16.266 s, no retained sandbox.
These are actual current stages, not an equivalent-scope comparison against
the earlier 148-control package or the small concurrency corpus.

## REVIEW, risk and next action

Executing-agent focused self-audit, pass 1, generation `d23c49152ef1f81d`:
inspected the owned dispatcher/callers, strict no-baseline and no-citation
boundary, whole-zero versus exactly proved empty partition, preserved raw
outcomes/diagnostics, cleanup observation semantics and unchanged other-family
registry/workflow. Final oracle pairs still see the original failures. No
additional confirmed acceptance defect; no second-agent/human review claimed.
Updated the existing harness locator rather than introducing another protocol
owner or a duplicate knowledge card.

DEC: SHIP this bounded wave in a new pending cohort; prior member hashes stay
historical. Remaining campaign work includes full-state copy/discovery decisions,
all sixteen adverse controls, final stable-generation multi-family/platform
and installed acceptance, A-J delivery and publication provenance. Real hosted
CI concurrency/memory parity remains unobserved. Future publication goes to
GitLab per the operator, but this wave performs no commit, tag or push.

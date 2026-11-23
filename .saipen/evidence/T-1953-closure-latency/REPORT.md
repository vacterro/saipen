# T-1953 — closure latency, verification reuse, batch economics

Handoff: "a ticket closure reportedly takes approximately 10 minutes", blamed on
"~10-12 serial CLI calls" at "10-30 seconds per CLI launch". Those numbers were
the previous agent's estimates. They were not used as data, and they are wrong.

---

## STATUS

Repaired and measured, on SAIPEN-owned code only.

- **A** Instrumented and measured. Real timings for every command in the script's
  sequence, on both installs, in both projects.
- **B** Cohort reuse: implemented as one opt-in word (`--reuse`) on `test suite
  run`, backed by the reuse contract that already existed (`current_record` +
  `_admissible`).
- **C** Duplicate full suites: quantified in the consumer project — 19 675 s of
  5.5 h recorded suite time is re-execution of a subject already answered.
- **D** CLI process overhead: measured at **0.2 s**, not 10-30 s. No batch API
  was built, because the measurement does not support one.
- **E** Shard nondeterminism: resolved and closed as **T-1952** (E-19133) before
  this ticket began. Reported in its own section below.
- **F** The 17 cases: answered case by case below, including CASE 17.

---

## TARGET SCRIPT / OWNER

`Close-Ticket.ps1` — **foreign**. It is not in the project it closes tickets in:

```
find V:/___VAC/__K/__CODE/_MISC/_BZDECOMP -maxdepth 3 -iname "*Close*Ticket*"   -> nothing
```

It exists only in agent scratchpads:
`/v/_TEMP_/claude/V-----VAC---K---CODE--MISC--BZDECOMP/{065c31a8,4c51d23a,e9f0f98a}/scratchpad/`
(plus a 17-line `Close-Tickets.ps1` and a 21-line `close-tickets.sh`).

Owner: the `_BZDECOMP` consumer project. It was read, never written. Its
authority is its own. Deliverable for it is
`.saipen/evidence/T-1953-closure-latency/HANDOFF-Close-Ticket.md`.

---

## MEASURED BASELINE

All figures are `time.perf_counter` around `subprocess.run`, 3-7 samples,
median. Nothing estimated.

### CLI launch cost — the claim under test

| what | median | min | max |
|---|---|---|---|
| bare `python -c "import sys"` | 32.6 ms | 30.7 | 121.2 |
| engine via `saipen.cmd`, refused command | 203.8 ms | 197.9 | 278.7 |
| engine direct, same refusal | 192.9 ms | 191.1 | 201.9 |

**A CLI launch is 0.2 s.** Twelve of them is 2.4 s, i.e. 0.4 % of ten minutes.

### Per-command cost in the consumer project

| command | median |
|---|---|
| `status --json` | 4 410 ms (before this work) |
| `test suite run` (declared suite) | 402-690 s |
| `claim` | ~0.25 s |
| `transition` | ~0.27 s |
| `checkpoint` | ~0.25 s |
| `ticket done` (refused, dry-run) | 1 311 ms |

### This project, for contrast

| command | median |
|---|---|
| `status --json` | 8 519 ms |
| `checkpoint RUN` (real mutation) | 1 258 ms |

### The consumer's suite, from its own 273 records

| window | n | median duration |
|---|---|---|
| Oct 15-19 | 87 | **1.5 s** |
| Oct 28-29 | 35 | **451.0 s** |

Last twelve: `439.5, 453.0, 499.1, 633.0, 570.5, 536.0, 648.0, 20.1, 689.8,
79.0, 563.5, 673.0` s — same declared command, same 16 tests.

---

## DOMINANT BOTTLENECK

**The declared verification suite, re-executed for trees whose bytes had not
moved.** Not process launch, not the protocol mutations, not journalling.

Of 27 172 s (7.5 h) of recorded suite time in the consumer project:

- **19 675 s (5.5 h) is re-execution of a subject already answered.**
- Since 2026-10-26 alone: **14 631 s (4.1 h)** redundant.

Second, smaller, and only on read-only `status`: **source-identity derivation**,
5.9 s in the consumer project and 3.4 s here, because 5 237 untracked files are
read three times for the stability proof.

---

## REPEATED WORK INVENTORY

### Per closure, in the script

| # | call | cost | repeats? |
|---|---|---|---|
| 1 | `ticket unblock` (optional) | 0.25 s | only when `-Unblock` |
| 2 | `claim <id>` | 0.25 s | once |
| 3 | `checkpoint RUN` (SCOUT) | 0.25 s | once |
| 4 | `transition BUILD` | 0.27 s | once |
| 5 | `transition VERIFY` | 0.27 s | once |
| 6 | **`test suite run`** | **402-690 s** | **yes — the whole problem** |
| 7 | `checkpoint RUN` (PASS) | 0.25 s | once |
| 8 | `transition REVIEW` | 0.27 s | 1-2x (`SOURCE_UNRESOLVED` retry) |
| 9 | `source disp` x clauses | 0.25 s each | 0, or once per clause |
| 10 | `transition SHIP` | 0.27 s | 1-2x |
| 11 | `ticket done` | 1.31 s | 1-2x |

Fixed protocol overhead: **~3.4 s per closure.** On a ten-minute closure that is
0.6 %.

### Inside one `status`, before the repair

| subsystem | calls | time |
|---|---|---|
| `compute_source_identity` | **4** | 0.805 s |
| `runtime_generation_identity` | 63 | 0.141 s |
| `runtime_surface_items` | 9 | 0.525 s |
| `distribution_report` | 1 | 1.125 s |
| `convergence_verdict` | 1 | 1.084 s |
| `semantic_receipt_snapshot` | 1 | 0.870 s |

`semantic_receipt_snapshot` re-reads **17 472 settled receipts / 187 MB** on
every call, in this project (`_BZDECOMP`: 5 737 / 45 MB).

---

## EXISTING REUSE CONTRACT

It existed. Nobody asked it. That is the defect.

`tools/saipen_engine/suite_record.py`:

- `_admissible(record, declaration)` — is this the engine's own record shape for
  the DECLARED command digest?
- `newest_record(root)` — newest admissible record of that command.
- `current_record(root)` — the above, when its `subject` equals the current
  tree's subject. Asked in the scheme the record used (`git:` never triggers a
  whole-tree hash).
- `subject()` — content identity of every file git tracks or would track,
  outside `.saipen/`. Unchanged by staging or committing, so a record of the
  tree before SHIP is still the record of that tree after.

`run()` never called any of them. It executed, judged, and wrote a fresh record
every time. The verifier owned the eligibility decision and the caller never
consulted it — which is exactly what the handoff said must remain true. It does.

---

## IMPLEMENTED REPAIR

### 1. `tools/saipen_engine/suite_record.py`

- **`reusable_record(root)`** — engine-owned eligibility. Returns the record and
  a reason, or `None` and the one fact that withheld reuse:
  - `no record of the declared suite describes the current tree`
  - `the current record is FAIL, not PASS`
  - `the current record counts no test, so it proves no run`
  - `the tree changed while that record was being written`
  - else: `the current record PASSed the same bytes of the same command`
- **`reuse_line(written)`** — cites path and sha256 of the record. Never
  restates a count.
- **`_EVIDENCE_RE`** — gained `(?P<reused>-REUSED)?`, so a reuse is
  machine-distinguishable from an execution.
- **`_take_reuse` / `--reuse`** — opt-in. Without it, every call executes.

A reuse still takes the `holding` lock and still writes an `operations.checkpoint`
journal entry. Reuse removes the execution, never the evidence trail.

### 2. `tools/freshness.py`

- **`_path_from_git`** — strips exactly one trailing slash (git's spelling of an
  untracked directory). `..`, `.`, absolute, empty and NUL remain refused.
- **`_record_current` / `_record_evidence`** — an untracked directory git did not
  enter is framed as `kind=b"D"`, mode `0o040000`, empty content: presence, not
  descent. Matches the rule `suite_record._git_subject` already applies.

### 3. `tools/test_t1953_suite_reuse.py` — 11 tests

Reuse eligibility (7), evidence marking (2), path canonicality (2).

---

## EVIDENCE FRESHNESS CONTROLS

Every one of these is a test, not a paragraph.

| control | behaviour |
|---|---|
| Tracked bytes changed | reuse withheld: `no record ... describes the current tree`; suite executes |
| Record verdict FAIL | reuse withheld: `the current record is FAIL, not PASS`; suite executes |
| `totals.ran == 0` | reuse withheld: `counts no test, so it proves no run` |
| `tree_changed_during_run` | reuse withheld: `the tree changed while that record was written` |
| Record of another tree | `current_record` returns `None`; not reported as stale, just not reused |
| Different command digest | `_admissible` rejects; not the declared suite |
| Default (no `--reuse`) | always executes — reuse is never silent |
| A reuse's LOG line | `PASS-REUSED`, citing record path + sha256; never a restated PASS |
| A real run's LOG line | `PASS`, no `-REUSED` |

Verified live in the fixture LOG:

```
RUN: SUITE-EVIDENCE PASS        ... record:...T070533579111Z.json sha256:845fa86c...
RUN: SUITE-EVIDENCE PASS-REUSED ... record:...T070533579111Z.json sha256:845fa86c...
```

Same record, same digest — a reader can open the immutable receipt instead of
trusting the sentence.

---

## SHARD DETERMINISM STATUS

**Resolved before this ticket: T-1952, closed as E-19133.**

The precondition the handoff set — "the concurrency/oracle defect must be
resolved or safely isolated before using parallel family PASS as trusted
reusable evidence" — was satisfied first, not assumed.

Root cause: a `core_unit` sandbox is a copy of the working tree and carried two
install pointers naming the SOURCE tree (`bin/saipen*`, and `STATE.saipen_home`).
Repair: `bin` joined `FINGERPRINT_EXCLUDED` (generated, gitignored, 0 of 843
install frames); `rebind_sandbox_pointers` rewrote both pointers to the copy;
each shard was rebound after its own copytree.

Determinism proof: a frozen clean pair returned fingerprint `d2019828e9239071`
twice — 8393 ran, 0 red, PASS both times —
`SAME_FP: True SAME_VERDICT: True SAME_RAN: True`.

Consequence for reuse: a parallel family PASS is now safe to treat as reusable,
because the same tree fingerprint no longer yields opposite verdicts.

---

## NEGATIVE TESTS

Run against a disposable fixture, all confirmed by hand and pinned by test:

| case | expected | measured |
|---|---|---|
| Same tree, `--reuse` | reuse, no execution | `SUITE_REUSED`, `executed: false`, execution counter unchanged |
| Same tree, no flag | executes | `SUITE_RECORDED`, `executed: true`, counter +1 |
| FAIL record, `--reuse` | executes | `SUITE_RECORDED`, `executed: true`, `reuse_withheld: the current record is FAIL, not PASS` |
| Tracked byte changed | executes | `reuse_withheld: no record ... describes the current tree` |
| Green again after change | reuse resumes | `SUITE_REUSED` |
| Record counts no test | withheld | `counts no test` |
| Record of moved tree | withheld | `changed while that record was being written` |
| `../x`, `./x`, `a/../b`, `/x`, ``, `a\0b` | refused | `FreshnessError`, all six |
| A real run's LOG line | not marked reused | `parse_evidence(...)["reused"] is None` |
| Reuse evidence reaching a gate | accepted, not misread | `transition SHIP` -> `TRANSITIONED` |

**RED control:** with the reuse branch disabled in place, the suite went
`FAILED (failures=2, errors=2)`; restored, `Ran 11 tests / OK`. The tests fail
without the repair.

---

## POSITIVE TESTS

| set | result |
|---|---|
| `test_t1953_suite_reuse` (new) | 11 tests, **OK** |
| `test_t1658_suite_record` + `test_t1661_suite_projection` | 44 tests, **OK** |
| `test_t1891_freshness_parser` | 12 tests, **OK** |
| `test_t1511_soak_source_identity` | 7 tests, **OK** |
| `test_t1687_identity_diagnostics` | **OK** |
| `test_install_identity_doctor` | **OK** |
| `test_t1734_source_drift` | **OK** |
| `test_engine_module_identity` | **OK** |
| `test_t1952_sandbox_points_at_itself` (prior ticket) | 6 tests, **OK** |

`ruff check` on all three changed/new files: **All checks passed!**

---

## BEFORE/AFTER WALL TIME

### The nine-call closure the script performs, on a 30 s suite

Fixture, `rebind-home`'d to the V: install, identical nine calls both times:

| | per call (s) | total |
|---|---|---|
| **before** | `0.24 0.27 0.24 0.27 30.40 0.25 0.28 0.24 0.29` | **32.48 s** |
| **after** | `0.25 0.25 0.24 0.28 0.27 0.23 0.28 0.25 0.27` | **2.32 s** |

**14.00x on the same nine calls.** All nine still `CHECKPOINTED` /
`TRANSITIONED` / `SUITE_REUSED`.

### Three closures over one unchanged tree

| | total |
|---|---|
| before | 91.6 s |
| after (1 execute + 2 reuse) | 31.3 s |

**2.93x**, because the first closure still pays the full 30.5 s and each reuse
costs 0.39 s. The saving is `suite_time x (closures - 1)` per unchanged tree.

### What this does NOT claim

No measured 10-minute -> N-minute figure is asserted, because **the script never
completed a closure here** (see BLOCKERS). The extrapolation is stated as an
identity, not as a measurement: on the consumer's last twelve runs
(439-690 s), removing reuse for all but the first closure of an unchanged tree
saves `suite_time x (closures - 1)`.

---

## VERIFICATION COVERAGE

| concern | covered by |
|---|---|
| Reuse only on identical subject + command digest | 7 eligibility tests |
| FAIL can never become reusable PASS | `test_a_fail_record_is_never_reused_as_a_pass` |
| Zero-test record proves nothing | `test_a_record_that_counted_no_test_proves_nothing` |
| Mid-run tree movement | `test_a_record_of_a_moved_tree_is_withheld` |
| Reuse is never silent | `test_reuse_is_opt_in_so_the_default_always_executes` |
| Reuse is legible in LOG | 2 evidence tests, plus live LOG inspection |
| Path canonicality bounds intact | `test_the_bounds_that_stop_escape_still_hold` |
| Untracked directory accepted | `test_a_directory_entry_is_accepted_and_the_slash_is_dropped` |
| Suite-record semantics unchanged | 44 tests in T-1658/T-1661 |
| Source-identity behaviour unchanged | 19 tests in T-1891/T-1511 |
| Identity diagnostics unchanged | 4 identity modules |

---

## REGRESSION RISKS

1. **`status` got slower in the consumer project: 4.4 s -> 9.35 s.** Reported,
   not hidden. Before, four consumers each failed to compute source identity in
   ~1.1 s total; now one computes it correctly in ~5.9 s. A correct identity is
   worth more than 5 s, and any caller needing it would pay that cost anyway.
   The 5.9 s is 5 237 untracked files read 3× for the stability proof. Separate
   ticket, separate measurement.
2. **`kind=b"D"` is new in the digest frame space.** Previously such a tree
   raised; it now yields `git-delta-v1:<digest>`. No prior identity was
   produced for such trees, so nothing is invalidated — but a stored identity
   from a tree that used to raise cannot be compared to the new one. It never
   existed, so nothing breaks.
3. **`PASS-REUSED` is a new token in the evidence grammar.** `_EVIDENCE_RE` was
   extended; the verdict group still reads `PASS`, so consumers keyed only on
   verdict are unaffected. Confirmed by `transition SHIP` accepting a reuse cycle.
4. **`--reuse` is a new flag on `test suite run`.** Default behaviour is
   unchanged and always executes.
5. **A record can be reused by a caller that then claims freshness it did not
   measure.** Mitigated by the `-REUSED` token and by `executed: false` in the
   JSON, both always present.

---

## BLOCKERS

**B1 — the script cannot run at all in `_BZDECOMP`.** It hardcodes
`C:/Users/vac34/.agents/skills/saipen/bin/saipen.cmd`, but that project's STATE
names the V: install. Every mutation answers `HOME_REQUIRED / home-dead:
home-divergent` in ~250 ms. Both installs are v8.1.0 with 171 engine modules; 4
files differ. Owner action given in the handoff.

**B2 — the consumer's suite went 1.5 s -> 451 s for the same 16 tests.** This is
the largest remaining term and it is the consumer's own drift. NOT diagnosed
here: it is their project, their authority.

**B3 — `Resolve-Source` forwards an unmeasured claim.** It passes
`--evidence $passEvent --verification "$Verify -> PASS"`, where `$Verify` is an
operator-supplied string. It also re-reads `$script:last` on later invocations.
Correctness issue, in the handoff, not repaired here.

**B4 — `ticket done` and `claim` cannot be measured end-to-end in `_BZDECOMP`**
because of B1. Their refusal cost (1.31 s / 0.25 s) is measured; their success
cost is `NOT_MEASURED`.

**B5 — the commit is still blocked by `EX-000022`** (pre-existing; installed
generation `fbbb910716437391` vs running `81ef3aef4a59c80c`), unrelated to this
ticket and unchanged by it.

---

## NEXT EXACT ACTION

`saipen` drives this. The remaining work in this ticket is REVIEW -> SHIP ->
DONE once the full family record exists, then:

- For SAIPEN: a separate ticket for the 5.9 s source-identity cost
  (5 237 untracked files × 3 reads), the largest remaining term in a `status`.
- For the `_BZDECOMP` owner: `HANDOFF-Close-Ticket.md`, blocker 1 first.

## CASES 1-17

| # | case | answer |
|---|---|---|
| 1 | reuse only when nothing changed | `reusable_record` requires subject equality; 3 tests |
| 2 | record of another tree | `current_record` -> `None`; not reused, not reported stale |
| 3 | different command | `_admissible` rejects by `command_sha256` |
| 4 | FAIL record | refused: `the current record is FAIL, not PASS` |
| 5 | zero tests | refused: `counts no test, so it proves no run` |
| 6 | tree moved mid-run | refused: `tree_changed_during_run` |
| 7 | reuse must be linked, not copied | `reuse_line` cites path + sha256; `PASS-REUSED` |
| 8 | default must execute | opt-in; `test_reuse_is_opt_in_so_the_default_always_executes` |
| 9 | reuse must not skip the journal | `holding` + `operations.checkpoint` still run |
| 10 | reuse must not skip validation | only reached after `load_declaration` and dry-run checks |
| 11 | impact subset must not be relabelled full | `--reuse` reuses the DECLARED command's record only; no family claim |
| 12 | parallel family PASS reuse | safe after T-1952; determinism proof cited above |
| 13 | shard nondeterminism | T-1952 closed, E-19133 |
| 14 | CLI launch overhead | 0.2 s measured; no batch API justified |
| 15 | duplicate full suites | 19 675 s / 78 subjects quantified |
| 16 | sample unavailable -> NOT_MEASURED | `ticket done` / `claim` success cost in `_BZDECOMP` is NOT_MEASURED (B1) |
| 17 | foreign script inaccessible | handoff written, no timing invented; script readable but not executable in its own project |

---

## DECISIONS RECORDED

**DEC-1** reuse is opt-in, not default.
**DEC-2** eligibility stays in the engine; `--reuse` is a request it can refuse.
**DEC-3** reuse is marked `PASS-REUSED` and cites the record + sha256, never a
restated PASS.
**DEC-4** trailing slash stripped; every escape bound kept.
**DEC-5** untracked directory = presence (`kind=b"D"`), not descent.
**DEC-6** the `status` 4.4 s -> 9.35 s slowdown is reported, not hidden.
**DEC-7** the fixture's counter lives outside the project so
`tree_changed_during_run` is not tripped for an unrelated reason.

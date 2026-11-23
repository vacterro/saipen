# WAVE 08 — sandbox copy cost: three options measured, all rejected or deferred

The focused gate spends most of its wall time copying, not testing:

```
duration_s 70.953
timings_s {"execution_wall_s": 1.484, "environment_identity_wall_s": 2.375,
           "copy_wall_s": 54.485, "hash_wall_s": 0.156, "cleanup_wall_s": 12.438}
copy_metrics {"subject_copy_s": 15.61, "canonical_copy_s": 38.593,
              "canonical_copy_attempts": 1}
```

1.5s of work inside a 71s gate. Three interventions were measured. None shipped.

## Frozen-tree method

The live tree moves under you: every `saipen` call writes evidence, and my first
timings differed by 10s for that reason alone. All numbers below copy ONE frozen
snapshot (135490 files) so every arm sees identical bytes.

## Option A — exclude `.saipen/cache/core-unit` (REJECTED)

Reason to consider: the engine recreates it (`keep_durations` does
`mkdir(parents=True, exist_ok=True)`; `load_durations` returns `{}` on a miss),
and in a sandbox it only decides shard balance.

Three repetitions each, frozen tree:

```
with cache   : 56.80  54.22  55.27   median 55.27s
minus cache  : 56.31  55.69  59.95   median 56.31s
delta median : -1.05s
```

A cache exclusion that is 1s SLOWER is noise, not a win. **Rejected on
measurement.** The 9.4s "saving" I first saw was live-tree drift, which is
exactly the mistake the campaign's §21 forbids reporting as a percentage.

## Option B — `copy_file=shutil.copyfile` (REJECTED, and it was a trap)

This looked like a clean 13%:

```
copy2    : 51.73  50.73   best 50.73s
copyfile : 45.67  44.08   best 44.08s
```

`copyfile` does not copy metadata, and `_checkpoint_stamp` in
`tools/saipen_engine/core_unit.py:262` builds its torn-copy detector from
`st_mtime_ns`:

```python
stamp.append((st.st_size, st.st_mtime_ns))
```

`copy_tree_consistent` copies `source/.saipen` twice and compares that stamp to
detect a checkpoint landing mid-copy (T-1479 — a sandbox whose STATE was ahead
of its LOG made every state-reading test answer VALIDATION_FAILED). Dropping
mtime makes every file look freshly written, so the two stamps would differ
whenever sizes did and the detector would either fire spuriously or stop
distinguishing a torn copy from a clean one. Verified directly:

```
source mtime_ns: 1792829480884652400
copy2     mtime : 1792829480884652400  same=True
copyfile  mtime : 1792865527023747800  same=False
```

**Rejected.** A 13% copy saving is not worth silently disabling torn-copy
detection. Also relevant: seven test modules read `st_mtime` for their own
assertions (e.g. `test_t1304_r004_dry_run_purity.py:64`,
`test_t1832_single_flight.py:90`).

## Option C — exclude history wholesale (REJECTED as unsafe)

| exclusion | copy time | files | size |
|---|---|---|---|
| none | 77.0s | 135450 | 1815.7 MiB |
| minus `.git` | 39.3s | 90487 | 1470.7 MiB |
| minus `.saipen` | 17.7s | 46306 | 366.5 MiB |
| minus both + `audit` | 0.53s | 1332 | 21.4 MiB |

Tempting, and wrong as stated:

- **203 of 511** test modules reference both `.saipen` and `evidence`; **18**
  build literal live-tree paths such as
  `test_t1817_handoff_artifacts.py:29-30` (`.saipen/evidence/T-1817-*.md`) and
  `test_source_contract_derivation.py:425`
  (`.saipen/archive/source/SRC-272.md`).
- `tools/validate.py` itself runs `for-each-ref`, `rev-list --remotes` and
  `git show HEAD:<path>`, so a sandbox without `.git` cannot validate.
- Inferring "this selection needs no history" from static imports is the
  inference `saipen/phases/verify.md` explicitly says does not prove dependency
  completeness.

## What a correct fix looks like (not built here)

Selection-aware copying with a fail-closed default:

1. Copy source files always.
2. Copy `.saipen` and `.git` only when the selected modules are known to need
   them, decided from an explicit declaration per module (not from import
   scanning), defaulting to "needs everything" for anything undeclared.
3. Record the decision in the evidence record so REVIEW can see which trees a
   given PASS actually had.

That is a design change with its own red/green controls, not a filter tweak.
Shipping it as a one-line exclusion would have converted a measured cost into
an unmeasured correctness risk, which is the trade the campaign forbids.

## Parallel-copy probe (informational, not adopted)

Copying top-level entries with 4 threads measured 45.6s vs 56.3s sequential —
but the two arms ran on a moving tree (file counts differed by 11), so that
number is not a comparable measurement and is recorded only to show it was
tried. A real experiment needs the frozen-tree method above.

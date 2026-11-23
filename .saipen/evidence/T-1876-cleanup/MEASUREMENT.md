# T-1876 — family teardown: before/after measurement

Same host, same subject family, same shard count (12), same selection
(7546 tests ran in both runs). The only difference is the teardown body in
`saipen_engine/core_unit.py`: a serial loop over the run's sandboxes versus
`reclaim_all` (one reclaim per tree, concurrently).

| phase                  | before (serial) | after (concurrent) | delta        |
|------------------------|-----------------|--------------------|--------------|
| execution_wall_s       | 1269.8          | 1059.4             | −210.4 s     |
| shard_copy_wall_s      | 441.1           | 350.1              | −91.0 s      |
| copy_wall_s            | 65.6            | 75.6               | +10.0 s      |
| **cleanup_wall_s**     | **286.3**       | **74.9**           | **−211.4 s** |
| total duration_s       | 2066.1          | 1562.5             | −503.6 s     |
| tests ran              | 7546            | 7546               | identical    |
| sandboxes_leaked       | []              | []                 | none         |

The cleanup row is the claim this ticket makes and the only one the diff can
cause: `reclaim_all` touches nothing else. The execution and shard-copy rows
also moved, and they are *not* attributable to this change — they are host
noise on a shared machine (the two runs took 2066 s and 1562 s of wall clock
for the same work; a 24% swing between two samples of a 12-way parallel
workload is expected). The honest reading is: **cleanup fell from 286 s to
75 s, a 74% reduction of a phase that is pure filesystem deletion.**

Both runs report `status: FAIL` because the tree carries 54 pre-existing red
tests outside this ticket's subject (they are tracked as inherited debt; the
family baseline records an empty inherited red set, so any of them shows as
new). This measurement is about teardown cost, not about a verdict: neither
run was cited as verification evidence for T-1876.

## Controlled benchmark (isolates the rewrite from host noise)

The live-tree pair above is the real workload but a noisy sample. To attribute
the saving to `reclaim_all` alone, `controlled-benchmark.json` removes the test
execution entirely and deletes only prefabricated sandbox trees: 12 trees x
1500 files, with a read-only share standing in for a copied git object store.

| trial | serial  | concurrent |
|-------|---------|------------|
| 0     | 1.25 s  | 0.50 s     |
| 1     | 1.28 s  | 0.48 s     |
| mean  | 1.27 s  | 0.49 s     |

**2.58x** on identical work, no leaks in either mode. This is the number the
diff is responsible for; the live-tree pair shows how it lands on the real
deletion volume (286 s -> 75 s).

## Reproduction

```
python tools/core_unit.py evidence <ticket> --jobs 12 --fresh
```

The phase timings land in the record's `timings_s`; `cleanup_wall_s` is the
phase `reclaim_all` owns.

## Red-before-green

`tools/test_t1876_parallel_cleanup.py` pins the contract:

- every path is reclaimed and a surviving path is reported, never swallowed;
- one stuck tree neither strands nor hides the others;
- reclaims actually overlap (`peak in-flight >= 2`).

The third assertion is the oracle. Against the pre-fix serial body
(`[item for item in paths if not reclaim(item)]`) the measured peak is 1, so
the test fails; against `reclaim_all` it is >= 2, so it passes.

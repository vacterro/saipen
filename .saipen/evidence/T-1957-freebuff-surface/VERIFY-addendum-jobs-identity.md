# T-1957 VERIFY addendum 2 -- why the tool re-cited the starved FAIL

## The behaviour

After minting a clean PASS, `core_unit.py evidence T-1957` cited the **FAIL**
record again:

```
CORE-UNIT-EVIDENCE FAIL family:unit ran:None red:2684 new_red:2684
record: b3be1dff84c472d1-20261029T162609997108Z.json
```

Two records exist for the identical tree fingerprint `b3be1dff`:

| record | verdict | ran | jobs |
|---|---|---|---|
| `…162609997108Z` | FAIL (starved shard) | `null` | **6** |
| `…173506837896Z` | PASS | 8406 | **4** |

## The cause, from the selector's own condition

`reusable_record` (`saipen_engine/core_unit.py:~1258`) accepts a record only when
**all three** match:

```python
record.get("fingerprint") == fingerprint
and record.get("baseline_sha256") == digest
and record.get("verification_identity") == expected
```

`verification_identity` is captured from the run's configuration, and flattening
the two identities shows exactly one differing leaf:

```
/configuration/jobs
  FAIL: 6
  PASS: 4
```

So the PASS I minted with `--jobs 4` is a *different configuration* from the
default `jobs: 6`, and the default mint could only match the starved FAIL. The
selector did the right thing with the data it had; I produced two runs that are
not comparable and then asked for a reference between them.

This is a real, correct property of the gate, not a bug: a run's concurrency is
part of its verification identity, because a sharded run that starved is
evidence about the harness, not about the tests, and it must not be silently
equated with a clean one at a different shard count.

## Concrete consequence for this ticket

- `evidence T-1957` with **default** jobs → must be re-run, because the only
  default-jobs record for this tree is the starved FAIL.
- `evidence T-1957 --jobs 4` → correctly reuses my clean PASS, but reports a
  non-default configuration.

The remedy that keeps the citation comparable to what a default run produces is
a fresh default-jobs run while nothing else is executing. That is what is
running now.

## What I am not doing

- Not deleting the starved FAIL record. It is an honest account of a run whose
  shard never reported, and `reusable_record` already refuses it
  (`full_scope_problem`/`judge` return non-PASS, so it returns `None` rather
  than renaming it).
- Not editing `.saipen/LOG.md` to remove the FAIL line. History is appended, and
  E-19208 is what the log recorded at 16:26.
- Not passing `--jobs` to make a citation line up. Choosing a configuration to
  obtain a preferred verdict is the exact behaviour the identity field exists to
  prevent.

# T-1952 SCOUT — the sharded oracle is non-deterministic, and here is why

Four evidence records exist. Two tree fingerprints, each recorded twice, with
opposite verdicts and identical `head`, `jobs` and `ran`:

| fingerprint | finished | status | ran | red |
| --- | --- | --- | --- | --- |
| `7e924cf0c81e3658` | 20261028T15243080153 | PASS | 8386 | 0 |
| `7e924cf0c81e3658` | 20261028T16175027198 | FAIL | 8386 | 12 |
| `7b04fc65cebbf82f` | 20261028T16565639860 | FAIL | 8386 | 34 |
| `7b04fc65cebbf82f` | 20261028T17411475028 | PASS | 8386 | 0 |

Same fingerprint means the tested bytes were identical. Opposite verdicts from
identical bytes is an unstable oracle, not a regression.

## The red tests are not flaky — they fail for a reason

Eleven of the twelve reds in `7e924cf0` (its FAIL run) and every sampled red in
`7b04fc65` carry one of two concrete causes, both visible in `red_sections`:

The red tests are not flaky — they fail for a reason. Corrected in BUILD after
direct measurement; the first reading of Cause 1 was too narrow and Cause 2 was
misattributed.

**Cause 1 — the copy carries two pointers naming the SOURCE tree.** There are
two files, not one, and each drives a different set of reds. Both were measured
in a 2×2 (drift × which pointer is rewritten):

| rewritten | test_t1645 | test_t1880 / test_t1939 |
| --- | --- | --- |
| nothing | FAILED (failures=2) | FAILED (failures=3) / FAILED (errors=3) |
| `STATE.saipen_home` only | FAILED (failures=2) | OK / OK |
| `bin/` only | OK | FAILED / FAILED |
| both | OK | OK / OK |

* `bin/saipen` and `bin/saipen.cmd` name the engine by ABSOLUTE path, so the two
  tests that EXECUTE the copy's launcher (T-1645's PATH-miss route) ran the live
  engine against the live STATE. They then asserted about a fixture project the
  live engine never read: `AssertionError: None != 'T-1'`.
* `.saipen/STATE.md`'s `saipen_home:` names the source install, while
  `state.running_home()` inside the copy is the COPY. Every mutation compared the
  two and refused with `home-dead: home-divergent` as soon as the trees differed.

That last clause is the actual non-determinism: `home_refusal` only blocks when
`diagnose_install_mismatch` finds the two fingerprints unequal, so the reds
appear exactly when the SOURCE tree has drifted from the INSTALLED one — the
normal condition of a tree under test. One fingerprint can therefore produce
both verdicts, because the tested bytes never changed; only the source tree's
cleanliness did.

**Cause 2 — withdrawn.** The first reading blamed
`FileNotFoundError: tests/scenarios/cold-handoff-continuity`. That fixture is
present and tracked (`git ls-files` lists 4 files; `.saipen/` holds BOARD, LOG
and STATE), `_ignore_copy` excludes only `__pycache__`, `*.pyc` and the session
caches, and nothing in the copy rules drops a nested `.saipen`. So the path was
present in both trees and this cause does not survive measurement. It is
recorded here as withdrawn rather than kept as a plausible story.


## Measured: the copy and the original agree on both fingerprints

```
real    fp: 068d40626d14c9b0bc50b901f40f5c311753728a7e69b8052500cb1814a5ddb1
sandbox fp: 068d40626d14c9b0bc50b901f40f5c311753728a7e69b8052500cb1814a5ddb1
SAME TREE FP: True
real    install: install-v1:f1fae646e9831f0a87f45ae0fa5bfdac1705888ecb960c113977b4b082f157e3
sandbox install: install-v1:f1fae646e9831f0a87f45ae0fa5bfdac1705888ecb960c113977b4b082f157e3
SAME INSTALL: True
```

Both content digests agree. The disagreement is not in the bytes — it is that
`bin/saipen` inside the copy points OUTSIDE itself. A copy whose launcher names
another tree is not a self-consistent install, and two of its tests reach through
that launcher into the real one.

## Why `--jobs 1` hid it — and why that is not a reason to keep it

`--jobs 1` runs the whole family in ONE sandbox, so both pointers still named the
source tree. The T-1606 REVIEW re-run (8387 ran, 0 red, jobs 1, 7954.5 s) was
therefore green because the source and installed trees happened to agree at that
moment, not because one sandbox is immune. That run is not evidence of a sound
oracle; it is evidence that the same latent defect did not fire.

The repair is in `copy_tree_consistent` (T-1952): every sandbox now gets both
pointers rewritten to name ITSELF. Because `bin/` joins `FINGERPRINT_EXCLUDED`
(install-generated plumbing, gitignored, zero frames in the install identity) and
`.saipen` was already excluded, rewriting them cannot change the subject digest —
proved by `tools/test_t1952_sandbox_points_at_itself.py`, which also pins the RED
direction by disabling the rewrite.


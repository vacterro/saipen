# HUNT pass @025bf596 — six categories, three tickets

Entry: explicit `hh` (E-17890, `transition to HUNT`). Per `saipen/phases/hunt.md`
the hash cache does **not** apply on an explicit `hh`, so the full sweep ran.

Sweep order below is hunt.md's own. Nothing was deleted, moved or renamed; the
only mutations in this pass are the three `ticket add` canonical bookkeeping
writes (E-17891, E-17892, E-17893).

## 1. Failing tests

```
python -m unittest tools.test_t1889_sandbox_scope tools.test_t1885_tag_peel tools.test_t1886_gate_lock_window
Ran 22 tests in 1.680s
OK
```

Clean. The subject surface of this session's work (T-1885/T-1886/T-1889) is
green; nothing in the campaign's own landing area is red.

## 2. Commits unverified in LOG

`git log -6` at HEAD, checked against `.saipen/LOG.md` **and** `.saipen/logs/LOG-018.md`
(the archive is where this era's events live; LOG.md holds the current tail):

| commit | subject | in LOG.md | in LOG-018 |
|---|---|---|---|
| 025bf596 | chore(t1601): record T-1601 DONE | yes (E-13185 area) | yes |
| 25f8ae76 | chore(t1601): close T-1601 | no | T-1601 events yes, hash no |
| 2a5df12e | fix(evidence): track SRC-166 proof artifacts | no | yes |
| 56191314 | feat(t406): finding_invalidated | no | T-406 events yes, hash no |
| ac1ae3e3 | chore(t1597): close T-1597 | no | T-1597 events yes, hash no |
| e6799642 | chore(state): checkpoint T-1597 claim | no | T-1597 events yes, hash no |

Verdict: **not a defect.** Every commit's *ticket* has a full lifecycle trail in
LOG-018 (`claim → BUILD → VERIFY → REVIEW → SHIP → finish`), and the finish
events are what the protocol requires. A git hash only appears in LOG when a
`clean -> done @<hash>` or release-scope event names it; ordinary ticket work is
tracked by event id, not by commit id. Reading "no hash" as "unverified" would be
the T-1885 silent-zero shape in a new place.

## 3. Stale TODO/FIXME/HACK

48 hits across `tools/saipen_engine/` + `saipen/`. Every one inspected is a
literal section name (`## TODO`), a quoted protocol term, or a docstring
describing the board grammar. Zero stale authoring markers. The single file that
once looked like a hit, `debt.py:560`, is a comment naming the
`DEBT-XXXXXX.json` filename pattern.

## 4. Silent failures — TWO REAL FINDINGS

79 broad `except Exception:` / `except BaseException:` handlers in
`tools/saipen_engine/`; filtered to those whose body is a bare `pass` or
`continue`, which gave 8. Each was read in context:

| handler | verdict |
|---|---|
| `conformance.py:1494` | **DEFECT → T-1891** |
| `journal.py:2227` (`Journal.read`) | **DEFECT → T-1892** |
| `host_authority_client.py:177` | justified: an unreadable adapter registry *narrows* the trusted-home set, which is the fail-closed direction |
| `install_identity.py:196` | justified: falls through to the frame-fingerprint comparison below it, which is the stricter test |
| `intake.py:403` | justified: an unreadable STATE degrades to the documented default agent id, and the write path validates separately |
| `intake.py:5135` | justified: a `continue` over one candidate receipt inside a scan loop; the loop's own `if not receipt_file` handles the no-match case |
| `intent.py:58` | justified: same documented default agent id as `intake.py:403` |
| `intent.py:1692` | justified: convergence probe falling through to the explicit validator run on the very next lines |

### T-1891 — the freshness window cannot fire on a padded stamp

`_strict_iso_utc` (conformance.py:276) strips before parsing, so a padded stamp
is accepted as valid UTC. `check()` (conformance.py:1490) then parses the **raw**
string without stripping:

```python
age_seconds = 0
try:
    rdt = datetime.datetime.fromisoformat(receipt["timestamp_utc"].replace("Z", "+00:00"))
    age_seconds = (ref - rdt).total_seconds()
except Exception:
    pass
...
elif age_seconds > FRESHNESS_WINDOW_SECONDS:
```

`fromisoformat` raises on the padding, the handler leaves `age_seconds = 0`, and
the receipt reads as maximally fresh. Measured:

```
stamp = " 2020-01-01T00:00:00Z "
strict validator verdict: '2020-01-01T00:00:00Z'   <- accepted
future-skew guard: False
age_seconds=0  window=86400
aged branch fires: False
true age years: 6.81
```

This is reachable *past* `_strict_validate_receipt`: the receipt must still be
structurally valid (content_hash, checkpoint hashes, source binding), so this is
not a forgery path — it is a genuine-but-old receipt whose stamp spelling defeats
the age arithmetic. The defect is two parsers where the module's own docstring
argues for one.

Population check: all **4612** receipt files under `.saipen/recovery/conformance/`
have clean, raw-parseable stamps (0 padded, 0 unparseable). So this is a latent
fail-open in the reader, not a live misreport — which is why it is P2, not P1.

### T-1892 — `Journal.read()` is a second, more permissive decoder

CORE-001 established that ONE strict decoder owns both `operation.json` and the
`progress.json` sidecar: "a PRESENT but unreadable/malformed/contradictory
sidecar is REFUSED, never ignored" (journal.py:1186-1193). `Journal.read()`
does not use it:

```python
if progress_file.is_file():
    try:
        prog = json.loads(progress_file.read_text(encoding="utf-8"))
        ...
        targets[i]["applied"] = True
    except Exception:
        pass
```

Every shape `_decode_progress_sidecar` refuses — symlink or reparse point,
non-regular file, invalid JSON, out-of-range `progress_index`/`applied_frontier`,
and the explicit contradiction "terminal status over a non-settled manifest" —
is silently merged or silently dropped here instead. `release.py` recovery
(`journal.read()` then `_validate_record`) and `goal_authority._pin_record`
compare their decisions against this projection, so the tolerant read is what
release recovery sees.

Not proven to have caused a wrong outcome; proven to contradict the invariant
the module states about itself, on the crash-recovery path. P2.

## 5. Symmetry gaps

`COMMAND_EFFECTS.json` classified through its real owner, `command_effects`:

```
admission matrix / table / doctor / saituls / src078   -> DIAGNOSTIC   (correct)
admission establish / invalidate                        -> EXECUTION    (correct)
fleet scan / matrix / preflight                         -> DIAGNOSTIC   (correct)
ticket compact T-1                                      -> RECOVERY     (correct)
```

Verified as a *nested* table, not a flat one: `admission.matrix` and friends are
covered by `admission`'s `default`/`subcommands`, so an earlier flat-keys reading
that reported them "absent" was wrong. No gap.

## 6. Dead code and orphan files — ONE AMBIGUOUS FINDING

Two `tools/saipen_engine/` modules look orphaned by an import grep and are not:
`core_unit_shard.py` (launched by path via `core_unit.SHARD_RUNNER`) and
`verification_bootstrap.py` (launched by path from `process_tree.py:171`). Both
are also named in `verification_cache.py`'s runtime-dependency list. Not dead.

Eight tracked `tools/*.py` scripts have no test, no CI step, no MANIFEST entry
and no BOARD/LOG row:

```
regression_conformance_closure.py    regression_core_audit_fixes.py
regression_second_wave.py            regression_second_wave_audit_fixes.py
regression_second_wave_receipt_fixes.py
second_wave_regressions.py           t1318_current_generation_probe.py
t1382_field_probe.py
```

Four (`t1318`, `t1320`, `t1382`, `verify_accounts_readiness`) name one-shot
field/acceptance proofs; `verify_accounts_readiness.py` *is* cited by T-1840's
closure_paths, so it is retained evidence rather than an orphan. The rest are
retained or leftovers — a question answerable from project evidence, so it goes
to TODO at P3 naming the exact question (`AMBIGUOUS:`), not to BLOCKED.

The one certain sub-finding: `regression_core_audit_fixes.py:8` instructs the
reader to run `python tools/test_core_audit_fixes.py`, which does not exist.

## What this pass did NOT find

- No failing test on the campaign's surface (category 1).
- No unverified commit (category 2).
- No stale authoring marker (category 3).
- No command-effect asymmetry (category 5).
- No dead engine module (category 6, proven by launch-path references).

## Not claimed

- T-1891 is not claimed to have produced any wrong CURRENT_PASS verdict in this
  project: the checked population is clean.
- T-1892 is not claimed to have caused data loss; it is an invariant violation
  on the recovery path, demonstrated by reading the two decoders against each
  other.
- T-1893's eight files are not called dead. Nothing was deleted or retired;
  CLEAN owns that decision and this pass made none of it.

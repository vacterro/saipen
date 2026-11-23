# SAIHANDOFF campaign — result at the end of this shift

Scope: the extended optimization campaign against the canonical project state.
This records what was **verified**, what was refused, and exactly where the next
shift resumes. Nothing here claims a green full suite, deployment, or
publication — all three remain blocked, and the blockers are named below.

## Tickets closed in this shift

| Ticket | Change | Headline evidence |
|---|---|---|
| T-1885 | An unreadable tag set was silently verified as zero tags | warning now states `N of M` unreadable; 7-test module RED on pre-fix bytes, GREEN on fixed bytes |
| T-1886 | `validate.py --gate ship` ran inside the single writer mutex (19.3s measured) | gate now observes a FREE lock; `writer_lock_yielded` had zero production callers, now both gates call it |
| T-1890 | The R003 lock-contract test died in `plan_release` and never measured its invariant | fixture completed; module 18/19 → 19/19; RED on HEAD bytes, GREEN on the fix |
| T-1889 | A focused gate copied 1815 MiB / 135450 files per run | declaration-driven copy, fail-closed; 74.7s → 5.8s on the same 22 tests |

Each has a `RESULT.md` and a red/green control under `.saipen/evidence/T-<id>-*/`.

## T-1889 in detail (the largest change of the shift)

`tools/saipen_engine/sandbox_scope.py` is new. A tracked manifest
`tools/sandbox_scope.json` declares, per test module, which heavy trees that
module reads from its sandbox: `[]` for source-only, or `.git` and named
`.saipen/<child>` subtrees.

Three properties make this safe rather than a shortcut:

1. **It cannot weaken what a PASS claims.** `tree_fingerprint` already excludes
   `.git` and `.saipen` at the top level, so no record ever attested those
   bytes. Verified: a FULL copy and a DECLARED copy of the same tree produce the
   identical fingerprint `9263c9fd1eb271b5`.
2. **The default is the old behaviour.** A module with no entry copies
   everything. Proven live: the first gate run of the new test module, before it
   was declared, copied everything and took 74.7 s.
3. **It is a declaration, never an inference.** The campaign's own rule is that
   static imports do not prove dependency completeness, so no import scan feeds
   this. A wrong entry is a red gate, not a silent pass — pinned by a control
   that runs a real evidence-reading module twice, passing when declared and
   FAILING when declared with `[]`.

Measured A/B, same tree, same copier, only `scope` differing:

| Arm | Wall | Files | Size |
|---|---|---|---|
| FULL (pre-T-1889) | 51.4 s | 132904 | 1793.1 MiB |
| DECLARED (source only) | 0.39 s | 1210 | 22.4 MiB |

Also verified in REVIEW: a narrowed sandbox cannot reach the live repository by
git upward discovery (`rev-parse --show-toplevel` exits 128 from both the
sandbox root and `sandbox/tools`), and the verification identity distinguishes
FULL from DECLARED so a narrow record cannot answer for a full run.

Three alternatives were measured and **rejected** earlier in the shift rather
than taken on a plausible percentage: excluding `.saipen/cache/core-unit`
(−1.05 s median, noise), `copy_file=shutil.copyfile` (−6.6 s but it drops
mtimes, which `_checkpoint_stamp` relies on for torn-copy detection), and
wholesale history exclusion (breaks 203 of 511 modules and `validate.py`'s own
git calls).

## Investigated and found not to be defects

- **WAVE 06, six `processes_leaked` entries.** All six PIDs were dead. This
  matches `test_runner.py:617`'s documented pre-close semantics. No process was
  killed (INV-19).
- **WAVE 07, the slowest modules.** The top 20 modules are 32.6% of module time;
  the top one (237.4 s) is 7 tests each running a real PowerShell publication,
  with a fixture build of only 1.7 s / 43.6 MiB. There is no cheap win, and
  mocking the publication would violate the campaign.

## Open, with the exact next action

**T-1888 / T-1887 [P2] — the recorded object-store damage does NOT reproduce.
Both now BLOCKED with a measured correction.**
Read-only re-measurement: `git rev-list HEAD` = 1133 and `cat-file -e` succeeds
on **every** one (0 unreadable, not 889); `for-each-ref refs/tags` exits 0 with
396 rows all peeling to commits (not 395/396 unreadable); `packed-refs` names
**0** `.pack` files and disk holds 4 packs with 4 idx (not 5-vs-3);
`git log -S "T-1479"` returns `8ddab6a3`. The tickets' own verify clause is
already satisfied for HEAD and tags.

The **one** true defect is a stale foreign ref
`refs/codex/turn-diffs/captures/1785165795234/fb80dcb4-.../base` pointing at
`9d3542bd…`, which exists on neither `origin` nor `github-backup` and is
therefore unrecoverable. That single ref is what makes a pattern-less
`git for-each-ref` exit 128 with no rows, and it is also what breaks
`git fetch`. The inflated counts are the T-1885 silent-zero shape seen from the
other side: a whole-set refusal counted as "everything unreadable".

The narrow remediation is one command —
`git update-ref -d <that ref>` — but the ref belongs to another actor's tooling,
so removing it is INV-22 and needs the operator's explicit decision naming it.
Nothing was mutated; `packed-refs` was not hand-edited.
Evidence: `.saipen/evidence/T-1888-object-store/CORRECTION.md` (copy under
`T-1887-object-store`).

**Publication — still blocked, and not attempted.** 206 of 216 staged paths are
foreign. Nothing was unstaged, reset, committed or pushed. The index was not
rewritten.

**Deployment — still blocked.** 437 foreign injected-surface paths. Untouched.

**The 55-red test baseline — unchanged.** No test was removed, skipped or
rewritten, and the baseline file's `red` list was not edited by this shift.
`test_t1828_verification_policy.PublicationWiringTests.test_release_executor_refuses_before_external_validator`
is one of those 55, cited by exact id from
`.saipen/evidence/core-unit/0ade2cd4b0d85ad8-20261024T142656492584Z.json`; it is
not a regression from this work.

**Foreign uncommitted work in the tree — left untouched.** `ruff check tools/
tests/` reports 24 errors, all inside it (`operator_origin`, `host_authority_*`,
`test_t1859_zaicode_seal`, `test_t1868_zaicode_ingress`, `test_t1792_auto_doctor`,
`saipen.py`, `verification_cache.py`, `install_host_guard.py`). One of those was
in `core_unit.py`'s `ship_gate` environment-identity hunk, which this shift did
not author; it was line-wrapped with no behaviour change because whole-surface
lint gates REVIEW.

## Unattempted campaign waves (honest inventory)

Attempted and reported: WAVE 06 (leaks), 07 (profiling), 08 (copy cost, which
became T-1889), 14a (the tag guard, which became T-1885). Not attempted:
§08-11 scheduling/parallelism beyond the copy work, §12 Auto-Doctor
effectiveness, §13 ingress/host truth, §14 publication isolation, §15-18 P2
items. They were not skipped for convenience; each needs its own scout and none
was displaced by a defect more urgent than itself.

## Observed and deliberately NOT acted on

**Duplicate TODO rows T-1887 and T-1888.** Both describe the identical defect —
same 889/1133 commits, same 395/396 tags, same 5-versus-3 packs, same foreign
`refs/codex/turn-diffs/...` ref, same `git fetch --refetch` failure — and both
carry the same verify clause ending in "`git log -S` works on a known historical
string". T-1888 also lists `needs: T-1885`, which is now DONE.

The canonical closure is `saipen ticket supersede`, but it requires
`--authority SRC-###` and **neither row carries a source receipt**. Minting a
source to authorize my own closure would be fabricating operator authority
(INV-01), and silently deleting a BOARD row is not a thing this campaign does.
So the duplication is recorded here for an operator or a receipt-bearing ticket
to resolve; no BOARD edit was made.

**13 FOREIGN FILES ARE STAGED AS EMPTY BLOBS — a publication hazard.** Found
while clearing my own contribution to the validator's "runtime manifest names a
file git does not track" class. The index holds intent-to-add entries
(blob `e69de29b…`, the empty blob) for files that carry real content on disk:

```
tools/test_t1745_sub_collect_foreign_field.py   3704 bytes
tools/test_t1748_worker_clock.py                5222
tools/test_t1750_release_boundary.py            9952
tools/test_t1752_audit_auto_close.py            6957
tools/test_t1753_activation_launcher.py         8328
tools/test_t1758_closure_cycle.py               4468
tools/test_t1765_finding_subtypes.py            6327
tools/test_t1790_dependency_route_budget.py     3637
tools/test_t1801_missing_audit_settlement.py    6217
tools/test_t1828_verification_policy.py         8964
tools/test_t1830_verification_observations.py   5103
tools/test_t1831_cleanup_fixture_cost.py        1699
tools/verification_policy.json                    66
```

Why this is dangerous and why it hides: intent-to-add entries are **invisible to
`git diff --cached`** (that command printed nothing for them above), so a review
of the staged set shows no trace of them, while `git commit` records the empty
blob. Any release that commits the current index — and `saipen`'s own release
scope is built from the index — would ship 13 empty files, and every one of
those is a test module or the verification policy, so the receiving clone would
have a silently truncated suite.

**Not touched:** these are foreign staged paths (INV-08, INV-09, INV-22).
Neither re-staging them nor unstaging them is this campaign's decision. The
7 other empty-blob entries are genuinely empty files and harmless.

My own five untracked files were staged explicitly, which is not a foreign
mutation: they are this campaign's work, and `focused_unit.py` was itself an
intent-to-add 0-byte entry that would have shipped an empty module. After
staging, the validator's untracked-manifest class dropped from 43 to 38 and
mine from 5 to 0.

## Continuation point

`saipen status` now reports `phase: DONE`, `task: none`,
`next_action: saipen continue`, and the `## TODO` section holds only
**T-1853 (P1), T-1854 (P1), T-1855 (P2)** — all three `needs: T-1815`.

T-1815 is itself in `## BLOCKED` on the publication batch: 206 foreign
pre-existing staged paths would enter the release. Measured now, the staged set
is 222 paths, of which 6 are this campaign's and the rest are foreign; 20
intent-to-add entries are additionally present and invisible to
`git diff --cached` (13 of them non-empty on disk — see above). Unblocking
T-1815 is therefore an operator act: either stage the release scope explicitly
or leave the foreign batch untouched. This campaign did neither.

So the honest state is **QUIESCENT_IDLE**: every remaining ticket is gated on
operator authority (the foreign ref, or the publication batch), and inventing
Work to keep the session busy is prohibited (INV-15). The one piece of
legitimate follow-on where no authority is needed is widening
`tools/sandbox_scope.json` for more of the 509 undeclared modules — one module at
a time, each requiring its own narrowed run as evidence, never an inference from
imports.

# T-1885 SCOUT — three implementation states, measured

Campaign: EXTENDED OPTIMIZATION, RUNTIME CONVERGENCE AND AUTONOMOUS RELIABILITY
Ticket: T-1885 (SRC-310), phase SCOUT → BUILD
Measured: 2026-10-24, against live checkout `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN`
HEAD: `025bf596c683464788ab698248e8a3c5eb44dfec`
Event: E-17827 (SCOUT checkpoint)

The handoff's §01 warns that its snapshot has no live `.git` metadata and that
its conclusions must be re-verified. This file is that verification. Every
number below was produced by a command, not carried over from the handoff.

## 1. The three implementation states

### SOURCE vs GIT HEAD — divergence in `release.py`

| Surface | sha256 (16) | lines | `TERMINAL_LOCAL_NO_PUBLISH` | `_gate_command` |
|---|---|---|---|---|
| worktree `tools/saipen_engine/release.py` | `ccc9c25b41c92dd4` | 4874 | 0 | 0 |
| index (staged) | `50c7796acf97b8a6` | 4865 | 0 | 0 |
| HEAD | `50c7796acf97b8a6` | 4865 | 0 | 0 |

Index and HEAD agree; the worktree is 9 lines ahead of both. **Neither the
source nor the commit carries the two interfaces the handoff names.**

### INSTALLED RUNTIME — has what the source lacks

| Runtime home | `release.py` sha256 (16) | lines | `TERMINAL_LOCAL_NO_PUBLISH` | `_gate_command` |
|---|---|---|---|---|
| `C:\ProgramData\SAI\SAIPEN\runtime\76a5995cbf99aacc` | `877ebd7642d87868` | 5312 | 3 | 2 |
| `C:\ProgramData\SAI\SAIPEN\runtime\d838d464759d97d3` | `877ebd7642d87868` | 5312 | 3 | 2 |

Function-set diff (`^def` names, runtime minus source) shows the runtime carries
13 more release functions: `_staged_index_drift`, `_crew_terminal_route`,
`_crew_carrier_problem`, `_scope_identity_holds`, `_gate_window_drift`,
`_writer_locked_git_bound`, `_bounded_source_drift`, `_source_identity_drift`,
`_release_op_started`, `_no_publish_targets_untouched`, `_gate_command`,
`_ship_label`, and the TERMINAL_LOCAL_NO_PUBLISH closure path.

**Verdict: the installed runtime is 438 lines AHEAD of both the source tree and
HEAD.** This is the §04A divergence, still present, and it is the source of the
52 "pass against installed runtime, source lacks the API" failures.

### The 14 R1 test modules — a genuinely unpublished batch

All 14 exist in the worktree, are **tracked in the index**, and are **absent
from HEAD**:

```
test_t1746_crew_terminal_outcome   test_t1750_release_boundary
test_t1792_auto_doctor             test_t1704_goal_checkpoint_priority
test_t1681_release_closure_op      test_t1669_clean_done_projection
test_t1640_board_scrub             test_t1827_writer_lock_contract
test_t1640_log_seal                test_source_contract_derivation
test_t1704_legacy_goal_authority   test_t1828_verification_policy
test_t1494_continuation_authority  test_t1851_debt_authority
```

The staged batch as a whole: **201 files changed vs HEAD under `tools/`**
(+65002/−911), of which **149 are test modules**. Total staged paths: 216.

These tests are written against the runtime's newer `release.py`. They are not
product defects and they are not this Work's to repair — §04B B10/B11.

## 2. P0 FINDING NOT IN THE HANDOFF — the object store is partly destroyed

The handoff assumes HEAD is a valid commit and that `git diff HEAD` is
meaningful for ownership. Measured:

| Measurement | Result |
|---|---|
| HEAD tree blobs present | **5067 / 5067** (complete) |
| Index blobs present | **4975 / 4975** (complete) |
| Commits in `rev-list HEAD` | 1133 listed |
| Those commits actually present | **244 commit / 889 missing** |
| First-parent readable depth | **233** commits, then `380b30f6` is unreadable |
| Tag refs | 396 total, **395 point at absent objects** |
| `git log` full walk | dies on the first unreadable ancestor |
| `git log -S` / `git rev-list --all` | fail outright |
| `refs/codex/.../base` | invalid sha1 pointer |
| `.git/objects/info/packs` | names 5 packs; only 3 exist on disk |

Consequences, each independently verifiable:

1. **`git log -S` cannot answer "when was `_gate_command` removed".** The
   archaeology the handoff asks for in §04A/A04 is unavailable in this
   repository until the objects are restored.
2. **`git log` is not a complete history**; the first 233 commits are readable
   and everything beyond is a hole. Any claim of the form "this file was never
   committed" or "X was introduced by commit Y" made with `git log` here is
   unsound past that depth.
3. **395 tags are dangling pointers.** Any tag-based release or provenance
   check sees them as candidates whose objects cannot be read.
4. `git fsck --connectivity-only HEAD` reports **105 missing blobs** reachable
   from HEAD — but **none of them is in HEAD's tree** (`git ls-tree -r HEAD` has
   5067 entries, all present). They are reachable through the unreadable
   ancestors, i.e. the same hole, not a corrupt working tree.

What is NOT damaged: the working tree, the index, HEAD's tree, and every
`.saipen/` canonical file. Nothing this campaign needs to read is lost. What IS
damaged: the historical archaeology.

The remotes are configured (`origin` gitlab, `github-backup` github) and no
shallow/partial-clone marker exists, so the missing objects are recoverable by
a `git fetch` from a remote that still has them. **That is a network mutation
of the user's object store and is not this ticket's authority.**

### Why this matters for the mission, not just for tidiness

`tools/validate.py` already contains a partial-object fallback (line ~9870:
`rev-list` cannot answer → per-tag `merge-base` loop), so validation does not
crash. But the fallback interprets "cannot read the objects" as "stand down on
that candidate", which means **395 broken tags silently stop being checked for
ancestry** instead of being reported as unreadable. That is a validation
blind spot created by a data defect, not by a deliberate exemption.

## 3. Future Gate registration state

`.`saipen/future/index.json` holds **51 gates**, corpus 51 documents, 1
machine-readable (`FG-0046`). No gate carries the 2026-10-24 architecture
handoff:

- `future_gate/SAIHANDOFF — SAIPEN_20261024_1647.md` (18613 bytes, 16:47) sits
  on disk, **unregistered**, and is a plain document without the
  `<!-- SAIPEN FUTURE GATE v1 -->` marker.
- Matches by title/scope: none. The nearest neighbours (`FG-0025` ARCHITECTURE
  MAP, `FG-0037` FUTURE ARCHITECTURE ROADMAP, `FG-0043` SAIPEN FUTURE
  ARCHITECTURE) are the 2026-09-18 corpus, a different proposal.
- Next canonical id: **FG-0052**.

`future add` writes the v1 header with `state: DEFERRED`, `basis: measured`,
`estimate: 1`, and a `TODO --` placeholder slice, then calls
`prove_owned_dir_chain` and `safe_atomic_write_bytes` — the canonical path, no
hand edit. `readiness()` refuses promotion while the slice keeps the
`TODO --` placeholder, which is exactly the "remains unpromoted" invariant
(INV-16).

## 4. Test baseline

The 55 reds are the T-1882 partition, unchanged and not re-measured here:
55 now-pass-on-live-tree, 52 runtime-API-only, 3 untracked-document. This SCOUT
adds the structural reason those 52 cannot become green by editing source: the
API lives in a newer, unpublished implementation that 149 staged test modules
already target. Full-suite PASS is unobtainable without either publishing that
batch or excluding it, and both are forbidden here (INV-08, INV-10, INV-13).

## 5. What this ticket will do next

Ordered by value, all inside the handoff's authorization:

1. **WAVE 04** — register FG-0052 as DEFERRED via `saipen future add` (F04-F17).
2. **WAVE 05** — re-verify T-1883/T-1884 invariants on the live tree (AC-06/07).
3. **WAVE 14** — make an unreadable object store *visible* to validation
   instead of silently widening a fallback, and make the runtime/source
   divergence report its exact identities. This is the §04A A10 requirement
   ("document source and runtime parity or explain exactly why parity is
   pending") turned into a machine-checkable verdict rather than prose.
4. **WAVE 06/07** — process-leak contract and slowest-module profile.

Not started, by instruction: the deferred architectural redesign (INV-16).

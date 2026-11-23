# T-2058 narrow conformance delivery — BLOCKED, canonical gates refused (2026-11-17)

Operator authorization: OPTION A, narrow delivery of `tools/saipen_engine/audit_route.py`
(T-2070, scope-450a898c) and `tools/saipen_engine/future_gate.py` (T-2072,
scope-8e43c95e), T-2052 precedent if applicable, with the explicit fallback:
"if the canonical release does not permit a clean narrow delivery, stop with an
exact BLOCKED, present the concrete refusal, and do not create an alternative
unauthorized installation path."

## What was done (all reversible, nothing published)

1. `inventory-before.txt` — exact `git status --porcelain=v1 -uall` over the
   MANIFEST-declared injected surface (58 entries): 65 dirty paths.
2. `sha256-before.json`, `files/` — independent byte copy of the 63 parked paths;
   `tracked.patch` — `git diff --binary HEAD` for the 35 tracked ones.
3. `git stash push -u -m "t2058-narrow-delivery ..." -- <63 paths>` — pathspec
   scoped, stash@{0}. Surface re-read: exactly the 2 delivery files remained.
4. `git add -- tools/saipen_engine/audit_route.py tools/saipen_engine/future_gate.py`
   — index proved to contain exactly those 2 paths; `git diff --cached --check` OK;
   staged blobs equal the worktree bytes modulo CRLF.
5. `git commit ... -- <2 paths>` — **refused by the pre-commit trust gate**.

## The refusals (exact)

### A. Pre-commit hook (`tools/validate.py`, exit 1) — refusals/precommit-hook.log

4 problems:

- closure provenance does not resolve: EX-000053 was verified against installed
  engine generation `sha256:d64ee12ee476fde8...` but the running engine is
  `sha256:51cc0aeb675b626c...` — the dependency moved; re-resolve truthfully.
- closure-evidence: T-2047 is `## DONE` but carries no current-cycle verification
  evidence (its reverification is bound to tree `git-delta-v1:f3dab073...`, the
  parked tree already measured `347be46a...`); `saipen work reverify T-2047`
  would be required.
- README.md badge does not match VERSION (8.1.0) exactly once — an artifact of
  isolating VERSION (worktree VERSION was 8.1.1, README/locales are 8.1.1-prepped).
- translation README badge drift: 32 locales still on the older version.

### B. Binding ship gate (`tools/validate.py --gate ship`, exit 1) — refusals/ship-gate.log

3 problems:

- the same EX-000053 provenance refusal;
- `binding ship gate requires every release metadata path staged: release index is empty`;
- `staged release metadata differs from working-tree bytes:` 620 paths plus
  `.gitattributes, CHANGELOG.md, README.{md,ee,d ed,ja}, VERSION` — i.e. the
  full 8.1.1 release metadata slice and the 618-deletion intake/archive
  authority transition (744 untracked tombstones) must be staged.

### C. Installed engine, restored tree — refusals/installed-core.log

Back to the pre-attempt baseline: 2 problems (the audit-inbox route and the
FG-0046/T-1936 slice), 16 warnings.

## Why this is a true BLOCKED, not a workaround opportunity

Every permitted narrow shape fails on a gate that is not ours to satisfy:

- Committing without the hook = `--no-verify`; the hook itself calls that a
  bypass, and the authorization forbids bypassing trust gates.
- Clearing EX-000053 and T-2047 needs data writes in two other tickets' closure
  evidence; T-2047's receipt is bound to the pre-commit tree fingerprint, so any
  isolation (and any resulting commit) invalidates it again.
- Satisfying the badge checks needs VERSION/README/CHANGELOG at one version —
  i.e. the 8.1.1 release step.
- Satisfying the ship gate needs the full T-2058 intake/archive authority
  transition staged and committed — explicitly excluded from this delivery.

No injector run was attempted: the delivery commit never landed, so the surface
was never published from; `saipen-inject` was never triggered by this attempt.

## Restoration proof

- HEAD unchanged: `dc39709c0c17a3272126c01a626ffcaa4176140b`.
- All 63 parked paths restored byte-exactly: 63/63 sha256 match
  `sha256-before.json` after `git stash apply --index` + copy-back.
- Original 7 staged index entries restored unchanged.
- Surface status back to 64 lines vs the 65-line inventory; the missing line
  (`tools/test_fixture_support.py`) was a stale stat entry in the inventory —
  its bytes equal HEAD and equal the recorded backup (verified).
- Delivery bytes still intact and uncommitted: audit_route.py `a934c36b...`,
  future_gate.py `40e698a7...`.
- Conformance receipt refreshed on the restored tree: `receipt-13b6ac0bb42c`,
  `CURRENT_FAIL`, 2 problems, tree `f3dab073...`; `saipen continue --json`
  returns the original `CONFORMANCE_UNHEALTHY` text (not STALE_FAIL).
- The attempt's stash entry is retained as `stash@{0}` (an extra recovery copy).

## The decision this leaves

The narrow delivery requires ONE of:

- authorization to stage/commit the 8.1.1 release metadata slice together with
  the T-2058 intake/archive authority transition (a real release commit, with
  the separate first-publish/tag/push questions still open), or
- explicit authorization for a one-off `git commit --no-verify` of exactly the
  two files while that gate is red (a named trust-gate bypass), or
- stop; T-2058 stays BLOCKED and `continue` stays refused.

T-2073/T-2074/T-2075 and T-2062 were not touched.

## Superseded by the expanded-scope preparation (2026-11-17)

The operator authorized the T-2058 intake/archive wave, the 8.1.1 release
metadata and the two engine modules together. The expanded index removes the
badge, T-2047 and empty-release-index refusals: with the full 1593-path index
staged, the ship gate reports exactly ONE problem, `EX-000053` (generation
binding), and the canonical `saipen ship` independently refuses with
`CREW_NOT_READY` (SC-7 names T-2073/T-2074/T-2075, all blocked on this same
publication). The exact cycle, measurements and restored state are in
`.saipen/evidence/T-2058-release-index/BLOCKED.md`; the per-change provenance
reconciliation is in `PROVENANCE.md` beside it. Nothing was committed or
published, and the worktree/index were restored byte-exactly.

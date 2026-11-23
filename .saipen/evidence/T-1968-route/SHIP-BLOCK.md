# T-1968 SHIP measurement — PUBLICATION_BLOCKED_EXTERNAL

Measured this cycle with the reviewed bytes in the worktree, before any staging.

## The ticket's own change

Four paths, all reviewed, all green:

| path | change |
|---|---|
| `saipen/REGISTRY.json` | `exact_namespace` block (EXACT-NAMESPACE-01) + `FOREIGN_PROTOCOL_COMMAND` in `error_codes` |
| `tools/saipen_engine/commands.py` | `foreign_protocol_owner(token)` resolver, alias-aware, fails to the old refusal |
| `tools/saipen.py` | typed `FOREIGN_PROTOCOL_COMMAND` refusal before the `unknown command` fallback |
| `tools/test_t1968_foreign_protocol_route.py` | 15 controls, 3 classes, LIMITS docstring |

Family gate: **PASS**, `ran=8519`, `new_red=[]`, `problems=[]`,
record `.saipen/evidence/core-unit/adb364d2c0d4fbd4-20261030T220916916164Z.json`.

## `validate.py --gate ship`: 4 FAIL, none of them this ticket's

    FAIL: source receipts -- closed receipt SRC-037 archive bundle invalid:
          source SRC-037 Contract/coverage clause identities differ
    FAIL: closure provenance does not resolve: EX-000029 was verified against
          installed engine generation sha256:06c1149a... but the running engine
          is sha256:96e9c936...
    FAIL: binding ship gate requires every release metadata path staged:
          release index is empty
    FAIL: staged release metadata differs from working-tree bytes:
          .saipen/intake/active/SRC-027.md, ...

Raw output: `.saipen/evidence/T-1968-route/ship-gate.log`.

### Why each one is outside this ticket's ownership

**(1) SRC-037 bundle.** The contract carries 4 clauses, the coverage carries 16
requirements, and both files are somebody else's half-landed source close.

**(2) EX-000029.** Already stale *before* this ticket: the conformance record
`.saipen/recovery/conformance/2026-10-30T18_26_55.923609Z_receipt-7231fe57a415_ship_FAIL.json`
captured the engine at `f9e0d3e1` at 18:26 while the receipt names `06c1149a`.
T-1968 cannot own that movement: `external.engine_identity()` hashes
`saipen_engine/*.py` + `saipen.py` + `validate.py`, and this ticket changed two
files in that set — but the digest was already wrong four hours earlier. The
stale green belongs to T-1653's `external_implementation` closure.

**(3)+(4) The release-metadata slice.** `release_contract.release_metadata_paths`
measures **4,221** paths in this worktree:

    2,078  .saipen/archive/source
    1,276  .saipen/intake/contracts
      385  .saipen/intake/active
      255  .saipen/intake/tombstones
      194  .saipen/intake/coverage
       19  .saipen/intake/appends
       14  everything else

3,603 exist on disk and **618 are worktree deletions**. Contact with this
ticket's four paths: **zero** (`scope ∩ release_metadata_paths == []`).

## The migration is consistent — and it is not mine to attribute

Checked rather than assumed, because "618 deletions" reads like data loss:

- 99 distinct source ids were deleted from `.saipen/intake/active`;
- **all 99 exist in `.saipen/archive/source`** (636 untracked carriers);
- **zero** intake-deleted sources lack an archive copy on disk.

So no source bytes are at risk. What is missing is an **owner**: the BOARD has
no ticket claiming the intake→archive migration, and `ship.md` 6b.2 — "any
unattributed stops SHIP" — is exactly the rule that fires here.

## Remotes (unchanged from T-1966 and T-1967)

    local HEAD        66ef622a
    github-backup/main 6d357a64   behind 2, ahead 1
    origin/main        60783ac4   behind 5, ahead 9

E-19090 and E-19535 already record this divergence and the foreign `63fcbad7`
deletion of the published `.saipen` tree, so this is carried project drift, not
a T-1968 regression.

## Verdict

`PUBLICATION_BLOCKED_EXTERNAL`. The repair is complete, verified and reviewed
against the current tree; it is not publishable because satisfying the binding
gate would mean staging 4,221 paths belonging to other tickets' uncommitted
source-authority transitions, which `ship.md` 6b.4 forbids explicitly
(`git add .` / `git add -A`) and CORE §1.2 attribution forbids implicitly.

The bytes stay in the worktree, reviewed and unchanged, releasable by whoever
owns the intake migration.

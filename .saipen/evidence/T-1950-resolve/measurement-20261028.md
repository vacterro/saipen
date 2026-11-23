# T-1950 -- what EX-000022 actually pins, measured 2026-10-28

Read-only measurement. Nothing was rewritten, staged or recommitted.

## The three findings the validator reports

`python tools/validate.py` exits 1 with exactly one problem:

    closure provenance does not resolve: EX-000022 was verified against installed
    engine generation sha256:fbbb910716437391... but the running engine is
    sha256:302bbb2a733d4630... -- the dependency moved (rollback or upgrade):
    re-resolve truthfully instead of inheriting a stale green
    ; external implementation differs from its carrying commit: Scripts/accounts/SaiAccounts.cs
    ; external verifier context/runtime/argv changed since the receipt

All three are T-1653's DONE row citing EX-000022. None is caused by any change in
this repository: `git status --porcelain -- tools/saipen_engine tools/saipen.py
tools/validate.py VERSION` is empty, and `engine_identity()` hashes only those
files, so the engine digest moved on a commit, not on an edit.

## What the receipt binds, and what the machine now holds

| field | receipt (EX-000022) | measured now |
| --- | --- | --- |
| engine generation | `sha256:fbbb9107...` | `sha256:302bbb2a...` |
| `Scripts/accounts/SaiAccounts.cs` | `6134d4ee6ba6b418...` | worktree `d771f95c48ece2c0...` |
| same file at committed HEAD | -- | `293f6dadffc5108b...` |
| same file at `T-289@041f00ed` | -- | `293f6dadffc5108b...` |

Two independent facts matter here.

1. The receipt's declared bytes (`6134d4ee...`) match NEITHER the committed blob at
   the implementation commit nor the current worktree. A full sweep of every blob
   reachable from `git rev-list --all --objects` in the external repository found
   no object with that digest. The bytes the receipt verified are not recoverable
   from the external repository's history.

2. `V:\___VAC\__K\__CODE\__SAITULS` has an UNCOMMITTED worktree change:
   `git status --porcelain -- Scripts/accounts/SaiAccounts.cs` answers ` M`, and
   `git diff --stat` reports 793 insertions / 76 deletions against HEAD. That is
   somebody's in-flight work in another project, not a SAIPEN artifact.

So a truthful re-resolution cannot be minted from this seat. `renew-external` and
`resolve-external` both bind the CURRENT bytes of the external file and the
CURRENT carrying commit; the current bytes are uncommitted work in a foreign
repository that this protocol has no authority over, and the historical bytes the
receipt names no longer exist in any commit.

## What a human must decide

Either the external change is finished and committed in `__SAITULS` (then a new
receipt can be minted against that commit's bytes and the current engine
generation), or the change is abandoned and the file restored. Both are decisions
about another product's repository. Neither is reachable from this seat.

T-1950 stays OPEN and BLOCKED. T-1653's DONE row is NOT rewritten: it did close
against a real receipt, and the receipt is still a true record of that moment.

# T-2027 / SRC-396 — SCOUT: release authority contract defects, live reproductions

Measured 2026-11-05 on the live tree (`HEAD 66ef622a`, shared index tree
`c025cf8dd110c6db351f87496980c3c90c7522ef`). Every line below is an observation,
not a report claim: the numbers come from running the repository's own functions.

## Live Git facts (the transaction the approval path is supposed to bind)

| remote | URL | main tip |
|---|---|---|
| `origin` | `https://gitlab.com/vacuum34/saipen.git` | `60783ac4abb78c06867aa833d692801f8e36b80c` |
| `github-backup` | `https://github.com/vacterro/saipen.git` | `3c96a98926b762547388ebd84708e8e6744e42e5` |
| local HEAD | — | `66ef622a43ab59512735ac78ce10d1250e26f9df` |

Ancestry, all four directions measured with `git merge-base --is-ancestor`:

- `github-backup/main` is NOT an ancestor of HEAD; HEAD is NOT an ancestor of it.
- `origin/main` is NOT an ancestor of HEAD; HEAD is NOT an ancestor of it.

Both remote lineages have diverged from local HEAD. Divergence is real, not
a stale-packet artefact.

## P0-01 — preview and grant disagree (reproduced)

`release_authority.approve_release_command(root, remote="origin", branch="main",
confirm=True, stdin_isatty=True, standing=True, max_releases=3)` with the stored
packet `approval_packet_20261102.json` present:

```
SHOWN   remote/branch : origin main
SHOWN   base_commit   : 3c96a98926b762547388ebd84708e8e6744e42e5   (from packet ancestry)
SHOWN   staging_hash  : 91a5a63c8286f0d76cca79038a025647d83dd10f199a6bf459ff6a3777a0f36d
GRANTED remote/branch : github-backup main
GRANTED url           : https://github.com/vacterro/saipen.git
GRANT FILE reviewed   : 13 entries (from packet, not the shown scope)
CONSISTENT            : False
```

The operator is shown `origin/main` and receives a grant for `github-backup/main`
(`tools/saipen_engine/release_authority.py:476-485` computes `eff_remote`; `:534-552`
then hands `packet_data` — with its own `ancestry.remote` — to
`convert_decision_request_to_capsule`, which re-reads the packet at `:231-236`).
The displayed overrides are discarded on the conversion path.

## P0-02 — a terminal assertion is accepted as operator provenance (reproduced)

```
approve_release_command(..., confirm=True, stdin_isatty=True)   # caller-supplied
  -> RELEASE_AUTHORIZED, grant a30277ba0bfcdbc58...  (PERSISTED)
```

`release_authority.py:490-496` accepts `stdin_isatty and confirm` as `is_operator`.
Both flags are supplied by the caller; a model-controlled PTY or a direct
in-process call satisfies them with no human anywhere. The existing control
`test_release_approval_contract.py::test_r002` passes `stdin_isatty=False`, so it
never exercises the PTY case.

## P1-04 — grant matching compares a symbolic ref with an immutable SHA (reproduced)

`isolated_release.execute_isolated_release` sets `base_ref = reconcile_remote_head
or "HEAD"` (`:749`) and passes it as `base_commit` to
`release_authority.find_active_grant` (`:777-779`). The matcher compares strings
(`:338`).

```
find_active_grant(base_commit="HEAD")             -> None
find_active_grant(base_commit=<grant's SHA>)      -> 66bfd02c183efbbf...
find_active_grant(no base)                        -> 66bfd02c183efbbf...
```

The literal `"HEAD"` can never equal an immutable SHA, so the normal path cannot
find the grant the operator just approved. Widening the match is the wrong fix:
the string comparison must be replaced by resolved commit identity.

## P0-05 — default destination disagrees with the granted destination (reproduced)

```
execute_isolated_release(remote=..., branch=...)   signature default: origin main
find_active_grant(remote="origin", branch="main")  -> None
```

The executor defaults to `origin/main`; the only grant the approval path can
produce from the stored packet targets `github-backup/main`. Approval therefore
cannot clear the `BLOCKED_AUTHORITY_GATE` refusal on the default path even after
a genuine human approves. The `NON_FAST_FORWARD` ancestry check runs at `:797-806`
*before* the grant check at `:808`, so approval alone cannot clear that refusal
either.

## P0-03 — frozen release identities are reachable defaults (read, live)

`release_authority.py:456-466` falls back to the historical packet path
`.saipen/evidence/release-reconciliation/approval_packet_20261102.json` when the
operator names none. `:479` falls back to remote head
`3c96a98926b762547388ebd84708e8e6744e42e5`; `:478` to
`https://github.com/vacterro/saipen.git`; `:506` *prints* the frozen staging hash
`91a5a63c...` as `protected_staging_hash` regardless of the live index;
`:507` prints `"864 staged paths in primary shared index"` (live staged count
today is 1236). `convert_decision_request_to_capsule:236,255` carries the same
two constants into the grant itself.

## P1-06 / P0-07 / P0-08 — preservation and the real missing capabilities

- The SRC-395 policy-v2 repair is in the tree (`MAINTENANCE_POLICY_VERSION = 2`,
  digest `sha256:fdc3d057a55655025d09f4a4dfcffdc7579ba3e54ef38a2cf3af6c8032bef24d`,
  focused 22 PASS on `tools/test_t2023_maintenance_policy_identity.py`).
- `saipen goal propose` correctly refuses today:
  `PROPOSAL_OBJECTIVE_MISMATCH` naming `self-maintenance-core` and the exact
  re-entry command. This refusal is preserved, not "fixed" away.
- `saipen host doctor`: `zaicode INSTALLED_UNVERIFIED` (admission ADVISORY),
  `claude-account2 STALE_RUNTIME`. No successor-turn transport exists.

## Reuse points (never invent a parallel architecture)

- Immutable transaction object: `current_binding`-style single derivation on the
  release side, i.e. one dict computed once and passed both to the preview and
  to `create_release_grant`.
- Operator provenance: reuse `saipen_engine/operator_origin.py` (broker-owned
  keyed ledger, OS-observed worker) and `goal_authority.source_proof`, which
  already requires `provenance["witness"] == "operator_carrier"` plus a
  broker-verified `operator_origin` for an operation.
- Ancestry: reuse `isolated_release.reconcile_remote_ancestry` (`:1057`) — it
  already reports `is_fast_forward` / `requires_integration` / ahead/behind.
- Index identity: reuse `isolated_release.snapshot_shared_index` (`:489`) and
  `verify_shared_index_unchanged` (`:594`).

## Existing tests that must keep passing

`tools/test_release_approval_contract.py`, `test_release_authority_gap.py`,
`test_isolated_release.py`, `test_release_reconciliation.py`,
`test_release_provenance.py`, `test_release_completion.py` — 61 passed in one
run before any change (measured, this tree).

# T-2027 / SRC-396 — live refusals on the repaired tree, and why publication is still pending

Measured 2026-11-05 on the live tree. Every value below is the output of the
repository's own functions run against this tree, not a restatement of a claim.

## Live transaction facts

| remote | URL | `refs/heads/main` |
|---|---|---|
| `origin` | `https://gitlab.com/vacuum34/saipen.git` | `60783ac4abb78c06867aa833d692801f8e36b80c` |
| `github-backup` | `https://github.com/vacterro/saipen.git` | `3c96a98926b762547388ebd84708e8e6744e42e5` |
| local `HEAD` | — | `66ef622a43ab59512735ac78ce10d1250e26f9df` |

Shared index tree measured live by `isolated_release.snapshot_shared_index`:
`a30d622ab457bfb59a3d375772d999f649f33121060ef6638bd90f6de038c8e0`
(1 254 798 entries). Active release grants on disk: **0**.

Neither remote lineage is an ancestor of local HEAD, in either direction
(4-way `git merge-base --is-ancestor`, unchanged from the SCOUT record).

## The five repaired defects, re-measured on the repaired tree

```
approve_release_command(root, packet_path=<stale 20261102 packet>,
                        confirm=True, stdin_isatty=True, standing=True)
  -> REFUSED_SYNTHETIC_APPROVAL
     "Operator approval requires genuine human confirmation. Automated model
      shell invocations cannot synthesize operator authority.
      (no operator-carried ingress was presented)"
  grants persisted: 0        # counted after the call

build_release_transaction(root, packet_path=<stale packet>, base_commit='HEAD')
  -> RELEASE_DESTINATION_DIVERGED
     "github-backup/main tip 3c96a98926b7 is not an ancestor of the requested
      base 66ef622a43ab; an ordinary fast-forward is impossible from here"

build_release_transaction(root)                        # no packet, no destination
  -> RELEASE_PROPOSAL_UNAVAILABLE
     "no verified release destination: name --remote/--branch or supply an
      approval packet carrying a destination; this path never falls back to a
      historical packet or a hardcoded repository"

resolve_commit(root, 'HEAD')        -> 66ef622a43ab59512735ac78ce10d1250e26f9df
resolve_commit(root, '66ef622a')    -> 66ef622a43ab59512735ac78ce10d1250e26f9df
resolve_commit(root, '3c96a989')    -> 3c96a98926b762547388ebd84708e8e6744e42e5
```

What each line settles:

- **P0-02** — a caller-supplied `stdin_isatty=True` plus `confirm=True` is no
  longer operator provenance. The refusal is raised *before* any grant is
  written; the ledger is still empty afterwards. Pre-repair this exact call
  returned `RELEASE_AUTHORIZED` and persisted a grant.
- **P0-03** — the historical packet is not adopted as a live transaction, and
  with no destination named at all the answer is
  `RELEASE_PROPOSAL_UNAVAILABLE`, not an apparently valid approval. No frozen
  base, URL, staging hash or staged-path count is reachable as a default.
- **P1-04** — a symbolic ref and the SHAs it names resolve through one
  function, so grant matching compares immutable identities.
- **P0-01 / P0-05** — preview and grant are built from one transaction dict;
  the destination the operator is shown is the destination the grant binds.

## Publication is not performed, and this is not a gate failure

`saipe ship` / `--isolated` are **not** run as a publication here. The reasons
are measured above and are not repairable inside this ticket:

1. No active release grant exists and none can be minted without a genuine
   operator-carried ingress. A model cannot supply one, by design (P0-02).
2. Both remote lineages have diverged from local HEAD. Integrating them is an
   ordinary engineering step the crate supports, but it is a *choice about
   which history is canonical*, which is the operator's decision — the handoff
   says so explicitly ("Do not automatically replace origin with github-backup
   merely because an old packet says so").
3. The shared index holds foreign pre-existing staged paths belonging to other
   Work; publication from this tree is refused by the foreign-staging gate.

`REMOTE_VERIFIED_SHA` is therefore reported as **not applicable**: no push was
attempted, so no remote SHA was verified and none is claimed. An unchanged
remote tip is not evidence of a successful publication.

## Verification evidence for this ticket

- Focused: `tools/core_unit.py focused T-2027` — 104 PASS, record
  `.saipen/evidence/focused-unit/40c4a727b6f1b205-20261105T102936632876Z.json`
  (9 patterns: the T-2027 controls, the five release-family suites,
  shared-index forensics, refusal registry).
- Full: `tools/core_unit.py evidence T-2027`, record
  `.saipen/evidence/core-unit/40c4a727b6f1b205-*.json`.

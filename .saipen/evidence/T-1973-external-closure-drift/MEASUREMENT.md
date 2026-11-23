# T-1973 -- EX-000029 no longer resolves, and why

Measured 2026-10-31T06:20Z against `tools/saipen_engine/external.py` as it exists here.

`validate.py --gate core` reports exactly one FAIL, and it is this one:

```
FAIL: closure provenance does not resolve: EX-000029 was verified against installed
engine generation sha256:06c1149a... but the running engine is sha256:6f2cd4c3... --
the dependency moved (rollback or upgrade): re-resolve truthfully instead of inheriting
a stale green; external implementation differs from its carrying commit:
Scripts/accounts/SaiAccounts.cs; external verifier context/runtime/argv changed since
the receipt
```

That sentence contains three separate claims. Two are true. One is an artifact.

## Claim 1 -- the engine generation moved. TRUE

```
receipt installed_identity.engine_digest  sha256:06c1149abecf5b8c...
receipt installed_identity.files          171
running external.engine_identity()        sha256:6f2cd4c372aa227e...
running files                             171
kind/version                              saipen-engine 8.1.0 (unchanged)
```

Same kind, same version, same file COUNT, different digest. So the generation moved by
CONTENT: `engine_identity()` hashes `name:sha256` for every
`tools/saipen_engine/*.py` plus `tools/saipen.py` and `tools/validate.py`, and this
campaign edited several of those (T-1971's `host_hooks.py`, T-1974's `validate.py`, and
the family-run fixes). A receipt bound to the old generation cannot be inherited
truthfully; the validator is right to refuse.

## Claim 2 -- the external implementation differs from its carrying commit. TRUE OF THE WORKTREE, FALSE OF THE ARTIFACT

This one needs care, because the natural reading is wrong.

```
$ git -C __SAITULS rev-parse HEAD:Scripts/accounts/SaiAccounts.cs
0eac11caef25dd4308af881ed99281a7501af8f8
$ git -C __SAITULS rev-parse d93b212f:Scripts/accounts/SaiAccounts.cs
0eac11caef25dd4308af881ed99281a7501af8f8     # identical blob
$ git -C __SAITULS show HEAD:Scripts/accounts/SaiAccounts.cs | sha256sum
d771f95c48ece2c06ae25f660520680ad6bd2f2678b8443b26b266ccbb80ef08
$ git -C __SAITULS show d93b212f:Scripts/accounts/SaiAccounts.cs | sha256sum
d771f95c48ece2c06ae25f660520680ad6bd2f2678b8443b26b266ccbb80ef08
$ git -C __SAITULS status --porcelain -- Scripts/accounts/SaiAccounts.cs
 M Scripts/accounts/SaiAccounts.cs
$ sha256sum __SAITULS/Scripts/accounts/SaiAccounts.cs
f9cffd24996a76e86de065f892e99b8d132c422af5ca21338cd20e62e591d8af
```

The receipt records `d771f95c...`, the carrying commit `d93b212f` carries `d771f95c...`,
and `__SAITULS` HEAD `555911f` carries `d771f95c...`. All three agree. The only bytes
that differ are an UNCOMMITTED working-tree edit in that other repository.

So the immutable external artifact did not move. A dirty file in a different project
invalidated this project's closure. That is what the predicate says, because
`external_renewal.capture()` compares:

```python
expected = _git(upstream, "show", f"{commit}:{rel}")   # immutable object
current  = _read(upstream, rel)                        # WORKTREE bytes
if not member_hash_matches(current, hash_bytes(expected)):
    raise ValueError("external implementation differs from its carrying commit: " + rel)
```

Whether that is a defect or the intended strictness is a design question for whoever owns
`external_renewal`, not something to settle by widening the predicate in this ticket. Both
possibilities are named here so the decision is made on the measurement rather than on the
sentence the gate prints.

An earlier draft of this note (and of T-1974's) called this "the external implementation
moved" and named `f9cffd24...`. That was a misreading of a worktree file as a committed
one, corrected here and in that note. It matters: "external product changed" and "somebody
has an unsaved edit in a sibling repo" call for completely different responses.

## Claim 3 -- the verifier context/runtime/argv changed. TRUE

```
receipt argv0 : ...\Python311\python.exe
receipt command: python.exe -B tools/verify_accounts_readiness.py --engine
                 C:\ProgramData\SAI\Accounts\bin\sai-accounts.exe --account AG3
                 --project V:\...\_SMART_VAC_CLEANER --private-home C:\Users\vac34\.codex
                 --report .saipen/evidence/T-1840-external-refresh/live-current.json
receipt summary: {'ran': 3, 'failed': 0, 'skipped': 0}
receipt runtime_inputs: {}
```

The recorded context is the receipt's own state, not something recomputable from the
current tree, so it cannot be "updated" -- it can only be re-earned by running the check
again.

## Why this is not closable by editing the receipt

Every route that would make the FAIL disappear without re-running the verification is
refused by construction, and correctly:

- editing `installed_identity.engine_digest` would state that an old run tested new bytes;
- deleting or superseding EX-000029 would leave T-1653's DONE row citing an evidence id
  that no longer exists;
- re-resolving without the verification run is what `proof_problem()` refuses by requiring
  `verification` entries with `ran > 0` and no skips.

The honest routes are the two the ticket's own verify clause names:

1. re-run `tools/verify_accounts_readiness.py` against the current generation and write a
   fresh external receipt with `ticket resolve-external`; or
2. re-resolve T-1653's external closure through the canonical route, naming why the old
   proof no longer applies.

Both are expensive because the verification touches another product's live binary
(`C:\ProgramData\SAI\Accounts\bin\sai-accounts.exe`). That cost is the real content of
this ticket: a closure that cannot be re-verified cheaply becomes stale the moment the
engine changes, and this campaign changes the engine on every ticket.

## Status when this note was written

Not attempted. The measurement above is complete and repeatable; the re-verification is
not, because it runs an external product's readiness check against a live account and a
live project, and that is a decision with side effects outside this repository. T-1973
remains open.

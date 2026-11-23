# T-1950 — re-measured 2026-10-29: the premise half is false, the receipt half is not mine

Continuation of `measurement-20261028.md`. That note concluded "both are decisions
about code outside this repository". This note separates the two halves and shows
one of them was this repository's own bug.

## Half 1 — the oracle was wrong, and it is our file

`tools/verify_accounts_readiness.py` asserted, in two negative controls, that a
project pointed at the operator's private home must be refused with
`CROSS_USER_RUNTIME_UNAVAILABLE`.

Live measurement of the same probe the contract runs:

    saipen-readiness AG3 --workdir C:\Users\vac34\.codex
      verdict: PROJECT_LIFECYCLE_DENIED
      project_access: {"status": "ok", "reason": null, "error": null}
      project_admission.write_admission: VALIDATION_FAILED
      project_admission.write_detail: "STATE.md is missing -- a SAIPEN checkpoint
        requires STATE.md, BOARD.md and LOG.md to all be present"

and for the disposable fixture the receipt's own negative control corrupts:

      write_admission: HOME_REQUIRED
      write_detail: "home-dead: STATE.saipen_home 'C:/Users/vac34/.codex' has no
        saipen/BOOT.md -- the cold-start kernel is not there ... converge it with
        `saipen rebind-home --auto`"

`icacls C:\Users\vac34\.codex` shows why:

    DESKTOP-TTH0L52\CodexSandboxUsers:(OI)(CI)(RX)
    DESKTOP-TTH0L52\vac34:(I)(OI)(CI)(F)
    DESKTOP-TTH0L52\antigravity_b:(I)(OI)(CI)(M)
    DESKTOP-TTH0L52\SAIAG_9fabb0d5:(I)(OI)(CI)(M)

The managed account **can read** that profile. Nothing about it is another user's
install. Per T-1647 the two facts have different cures and different codes:

| fact | code | remedy |
| --- | --- | --- |
| a home this account may NOT read | `CROSS_USER_RUNTIME_UNAVAILABLE` | never rebound |
| a home it CAN read with no kernel | `HOME_REQUIRED` | `saipen rebind-home` |

`C:\Users\vac34\.codex` is the second kind. The engine answered correctly. The
oracle encoded the fixture's wish instead of the machine.

### The second control was failing too, and `failfast` hid it

`main()` runs the suite with `failfast=True` and returns early on the first
failure, so `test_20`'s assertion masked `test_30`. Run alone:

    test_30_unrelated_operator_profile_remains_denied ... FAIL
    AssertionError: 'PROJECT_LIFECYCLE_DENIED' != 'PROJECT_ACCESS_DENIED'

So the receipt's own `{"failed": 0, "ran": 3}` was produced by an oracle that
never reached its third test under the current ACL. Two independent premises,
one masking the other.

### What was changed

`tools/verify_accounts_readiness.py` only. Both controls now assert the invariant
that actually holds — the profile is DENIED — and pin each refusal code to its
own cause rather than presupposing one:

- `test_20`: `write_admission` must not be `ADMITTED`; may be either code; when
  it is `CROSS_USER_RUNTIME_UNAVAILABLE` the detail must say "cannot be read by
  this account" / "never rebound", when it is `HOME_REQUIRED` it must say
  "no saipen/BOOT.md" / "rebind-home".
- `test_30`: verdict may be `PROJECT_ACCESS_DENIED` (unreadable) or
  `PROJECT_LIFECYCLE_DENIED` (readable but not a SAIPEN project); the second
  branch additionally requires `project_access.status == "ok"` — i.e. the
  refusal came from the missing canonical files, not from an ACL.

The `CROSS_USER` branch is not deleted: a SYSTEM-only folder still answers it,
measured directly through the same binary:

    saipen-readiness AG3 --workdir <SYSTEM-only dir>
      verdict: PROJECT_ACCESS_DENIED
      project_access: {"status": "WORKDIR_UNAVAILABLE", "reason": "ACCESS_DENIED"}

### Re-measured

    python -B tools/verify_accounts_readiness.py --engine .../sai-accounts.exe \
      --account AG3 --project V:\...\_SMART_VAC_CLEANER \
      --private-home C:\Users\vac34\.codex --report .../live-20261029-fixed.json

    test_10 ... ok
    test_20 ... ok
    test_30 ... ok
    Ran 3 tests in 17.252s
    OK

Report observations: `actual_project_canonical_unchanged: true`,
`unlisted_home_negative_control: true`,
`operator_profile_readable_but_not_a_project: true`, `fixture_removed: true`.
Every probe ran as `DESKTOP-TTH0L52\SAIAG_9fabb0d5`, so this is still the
managed-account path and not the operator's own token.

`python -B -m unittest tools.test_t1840_external_renewal` — 19 tests, OK.

## Half 2 — the receipt cannot be renewed, and that is another project's call

`python tools/validate.py --gate core` still reports exactly one problem, and it
is the receipt, not the oracle:

    closure provenance does not resolve: EX-000022 was verified against installed
    engine generation sha256:fbbb910716437391... but the running engine is
    sha256:a057d164a2c5ea0b... ; external implementation differs from its carrying
    commit: Scripts/accounts/SaiAccounts.cs ; external verifier
    context/runtime/argv changed since the receipt

`renew-external` names the second one and refuses:

    external implementation differs from its carrying commit: Scripts/accounts/SaiAccounts.cs

Measured state of `V:\___VAC\__K\__CODE\__SAITULS`:

    git status --porcelain -- Scripts/accounts/SaiAccounts.cs   ->  M
    git diff --stat                                             ->  793 insertions, 76 deletions
    worktree sha256  d771f95c48ece2c0  (370187 B, 2026-10-25 21:12)
    commit   sha256  293f6dadffc5108b  (342805 B, at 041f00ed)

Every ref was searched; the worktree bytes are in **no commit**
(`git log --all -- Scripts/accounts/SaiAccounts.cs` returns one commit, whose
blob differs). And the diff is not incidental — it rewrites the very block the
contract observes, `project_admission` / `write_admission`, and it changes the
autoconnect mutex from `Local\` to `Global\` with an explicit `MutexSecurity`
ACL.

`capture()` binds the worktree to the carrying commit, so the three honest
options are all closed to this seat:

1. **commit it** — 793 lines of another project's in-flight work, into a repo
   whose own BOARD holds 9 open tickets and live claims, on a protected branch.
   That is an outward-facing write to another product's history.
2. **revert it** — destroys someone's uncommitted work. Destructive.
3. **name only the clean file** — `--paths tests/test_sai_accounts.py` DOES plan
   (`{"ok": true, "code": "PLAN"}`). Refused deliberately: it would drop
   `SaiAccounts.cs` from the snapshot, so the receipt would assert a narrower
   proof than EX-000022's and present it as the same closure. A narrowed scope
   relabeled as the full proof is exactly the manufactured green CORE-003 exists
   to prevent.

There is also a third, independent drift, and it is the sharpest one: the
installed `sai-accounts.exe` is `5568338e` (2026-10-27 21:01), where EX-000022
recorded `ec856f62`, and it postdates the dirty source (2026-10-25 21:12).

The deployed binary was built from the **uncommitted** tree, not from any commit.
String-table counts over the deployed exe against both sources:

| marker | deployed exe (UTF-16) | committed `041f00ed` | worktree |
| --- | --- | --- | --- |
| `READINESS_UNKNOWN` | 1 | **0** | 5 |
| `probe_unavailable` | 1 | **0** | 1 |
| `Global\SAI.Accounts.Autoconnect.` | 1 | — | present |
| `Local\SAI.Accounts.Autoconnect.` | **0** | — | absent |

`READINESS_UNKNOWN` and `probe_unavailable` occur in the deployed binary and in
NO commit. The `Global\` mutex name likewise appears in the binary while the
worktree's only `Global` occurrence at that call site is the new literal. So the
machine is running code that exists in no commit anywhere in `__SAITULS` — and
the managed-account probes recorded above were answered by that build, which is
the most honest available answer to "what is deployed", but is not a commit.

This is the reason the narrowed snapshot is refused, restated from the other
side: a receipt minted today would bind either a commit whose binary is not what
runs, or a worktree that no commit contains.

## What is decided and what is not

DECIDED and implemented: the oracle's premise was false; the engine was right;
`tools/verify_accounts_readiness.py` is this repository's own file and is
corrected, re-measured 3/3 PASS, with the `CROSS_USER` branch retained and
separately proven reachable.

NOT decided here, and not decidable from this seat: what happens to the 793
uncommitted lines in `__SAITULS/Scripts/accounts/SaiAccounts.cs`. Finish and
commit them, or discard them — after which `renew-external` can bind a snapshot
that includes the implementation file and T-1950's verify clause is satisfiable.

T-1950 stays BLOCKED. The blocker is the foreign worktree, not the refusal code.

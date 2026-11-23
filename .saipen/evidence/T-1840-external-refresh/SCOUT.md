# T-1840 — current external closure evidence

The goal remains the complete `cc all` continuation, including parent T-1829.
T-1829 depends on T-1839; T-1839 depends on this Work. Current STATE is SCOUT /
T-1840, owner saipen-cli. Goal accounting was not reset or reauthorized.

## Authoritative failure and available recovery

After 12 exact campaign-file index additions, canonical validation reports ONE
remaining problem: T-1653's EX-000010 binds engine digest e10a20a075aa310b…,
while the current engine moved. The complete original receipt is at
`.saipen/recovery/conformance/external/EX-000010.json`; retain it unchanged.
The actual code/metadata sources already read are `external.py`,
`operations._plan_resolve_external_ticket`, CLI resolve-external dispatch,
`debt._run_verification_command`, and OPS's external closure owner.

`ticket resolve-external T-1653 --revalidate --dry-run` refuses its stored
unsealed shell command as EXTERNAL_VERIFICATION_UNAUTHENTICATED. The current
same-tuple DONE refresh path exists, but different authority/implementation/
reason tuples refuse TICKET_ALREADY_DONE. `work contracts T-1653 --json`
reports DEPENDENCY_BINDING_MISSING. None of these diagnostics is a new PASS.
Explicit `--run` still makes legacy shell-only entries; it would recreate the
future automatic-revalidation problem. Reuse authenticated argv contracts and
the existing append-only EX receipt/PLAN/APPLY machinery where possible.

## External identity and source evidence

The existing bounded lineage locator resolves
`lineage-ded945ae8243480ab1bfee73baeb29c6` to
`V:/___VAC/__K/__CODE/__SAITULS` (no downstream source was modified).
T-1653 names T-289@5f0dc0c. The actual external T-289 contract requires real
broker-token write-admission dry-run, unchanged SMART_VAC_CLEANER canonical
files and a denied unlisted foreign home; its title references SRC-105.

The recorded 5f0dc0c commit is dated 2026-10-10 and lacks the actual
`tests/test_sai_accounts.py` path (Git cat-file exit 128). The 2026-10-20
041f00e commit contains it (positive control exit 0); external HEAD observed
dc030b39f6fad1b3246db989ec9789b39c99205e. Do not silently assume the older
commit carries the later implementation. Verify the exact original contract
and immutable implementation before selecting a truthful binding.

Read source: `Scripts/accounts/SaiAccounts.cs`, its fixed-readiness dispatch,
`SaiAccountsHelper.cs`'s grants-ledger locator, `SAI_ACCOUNTS.md`, README and
`tests/test_sai_accounts.py`. Source/graph fallback is explicit; no exhaustive
codebase claim. The harness normally builds in the source bin directory;
use its SAI_ACCOUNTS_TEST_BIN override and a newly owned private directory for
any needed isolated build, rather than replacing the deployed broker.

## Real observations already obtained

The account selector was resolved by the existing actual CLI; the configured
grants ledger supplied SMART_VAC_CLEANER's exact root:
`V:/___VAC/__K/__CODE/_PY/_SMART_VAC_CLEANER`.

1. `saipen-readiness AG3` returned READY under the actual managed account
   broker: identity verified, credentials present, machine runtime READY,
   correct non-elevated account token. Stored in ag3-runtime-readiness.json.
2. `saipen-readiness AG3 --workdir <that actual root>` returned READY,
   HOST_BOOTSTRAP_BOUND, project ADMITTED and write_admission ADMITTED.
   SHA256 of STATE.md, BOARD.md and LOG.md matched before/after. Stored in
   ag3-project-readiness.json and ag3-project-observation.json. The target
   project remained VERIFY / T-215; no seat or lifecycle mutation was made.

These are actual live observations, not mocks or an EX receipt. They prove
their named scope, not all original SRC-188 checks or the negative foreign-home
control. Runtime readiness alone does not repair the historical source binding.

## Next bounded work

Recover the exact original SRC-188 / external SRC-105 contracts through their
recorded intake locators; determine the authenticated current acceptance
command and remaining real negative controls. Inspect regression_execution's
existing closed-contract loader before adding any CLI surface. If the DONE
refresh needs a correction, preserve the original receipt/contract and require
actual same-authority implementation/ancestry, current executed verification,
owner and Source/operator gates; never merely loosen the different-tuple
refusal or transplant a digest. A changed execution oracle needs its own RED
control and same-oracle pair.

After truthful EX recovery, run canonical validation once against changed
inputs. Only then resume T-1839's current complete scoped acceptance and the
parent's strategically scheduled final-generation full/release gates.

Update: both exact sources have now been read. Root SRC-188 is ACTIVE, raw SHA256
cf552a04864d807d044eef586f3140510c945d91c58212b0e114ab6b286368df
verified against the actual file. R009/R010 remain explicitly BLOCKED and name
T-1653. `work_closure_gate(T-1653)` returns SOURCE_COVERAGE_COMPLETE with an EMPTY
receipt list, so that legacy projection cannot prove those original requirements
satisfied. Do not exploit it or silently close their Source coverage. External
SRC-105 is CLOSED/archive, exact SHA256
ebce0e89d492f016d359064a7cb3c8bb92ba4b3ce1c6a4a824dc4f80d1e342d8;
its six readiness facts and account creation/repair/host-launch/access-failure
criteria were retrieved through `source show`, including authority metadata.
The GUI's current source invokes saipen-readiness before project launch and
holds an initially unmeasured readiness value separately from provider state.

The existing closed regression contract loader accepts current checks with no
subject files, authenticates native runtime argv and owned oracle/context, and
excludes `.saipen`/Git from oracle context. `external.execution_entry` already
runs that authenticated plan with ProcessTree and persists argv/runtime/verifier;
receipt_plan safely re-admits such entries. Prefer this reuse to new shell
replay or another evidence controller. No T-1840 production code changed yet.

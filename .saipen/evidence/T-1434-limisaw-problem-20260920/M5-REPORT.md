# T-1434 / SRC-088 — Milestone 5 evidence: validator remediation by construction

Date: 2026-09-21. Phase BUILD. Continuation of T-1434 (SRC-088).

Mission: every actionable machine-readable remediation the validator emits
resolves to exactly one of REGISTERED_CANONICAL_COMMAND or
TYPED_EXTERNAL_ACTION -- no nonexistent command, no internal Python function,
no docs-only verb, no pseudocommand, no parser rejection, no missing registry
or effects entry, no router blindness, no generic `saipen validate` recursion
while a specific repair exists.

## Defect reproduced before patch

- The receipt-level remediation surface (M1) extracted ONE hard-coded pattern
  (`saipen work reverify T-\d+`); every other actionable FAIL (sweep linkage,
  improve cycle, external closure, source retirement/coverage) named its repair
  only in prose and carried nothing machine-readable.
- Help/documentation audit: `saipen source retire` and `saipen source recover`
  appeared in NEITHER `saipen --help` nor COMMANDS.md; `work reverify`,
  `ticket reasoning`, `ticket resolve-external` each missed one surface.
- COMMAND_EFFECTS had no explicit `source recover` entry (unrelated default).
- M1 authority ambiguity (M5.3): `saipen work reverify <T-###> --verification
  "cmd:PASS"` produced a receipt the closure-evidence check consumed as
  current-tree proof even though NOTHING was executed -- typing PASS
  manufactured closure authority.

## Implemented primitives

1. `tools/saipen_engine/remediation.py` -- THE closed remediation contract:
   - `REMEDIATION_KINDS = (command, external)`; a third class is a protocol
     error;
   - `REMEDIATIONS`: one spec per actionable rule -- rule identity, exact
     emitted pattern, template, registry verb/action, implementation owner:

     | rule | command | verb/action | owner |
     |------|---------|-------------|-------|
     | closure-evidence | `saipen work reverify <T-###>` | work/reverify | debt.py |
     | closure-provenance:external-generation | `saipen ticket resolve-external <T-###> ...` | ticket/resolve-external | external.py |
     | core sweep:sweep-ticket-link | `saipen ticket reasoning <T-###> ...` | ticket/reasoning | operations.py |
     | improve report | `saipen improve reconcile <cycle>` | improve/reconcile | improve.py |
     | source receipts | `saipen source retire <SRC-###> --reason <CLASS>` | source/retire | operations.py |
     | source coverage | `saipen source recover` | source/recover | intake.py |

   - `EXTERNAL_ACTION_KINDS` closed vocabulary (operator GUI verification,
     unavailable upstream credential, external publication authority, external
     project observation) + `external_action()` records that are `kind:
     external`, never a `saipen` command and never inferred from prose;
   - `extract_commands(failures)` -- the ONLY producer of receipt remediation
     commands; `resolve_command()` refuses anything outside the table.

2. `tools/validate.py` delegates receipt remediation extraction to the table
   (the M1 hard-coded regex is gone), so a failure message can never smuggle an
   unregistered route into a conformance receipt.

3. `tools/saipen_engine/conformance.py`: receipts now carry
   `remediation_commands` (as before) plus `external_actions` (typed, empty
   when no current rule needs an external actor).

4. M5.3 authority repair (no M1 architecture change):
   - CLI attested entries are typed `{executed: false, kind: attested}`;
     `reverify_work` types any caller shape the same way and the receipt gains
     `evidence_class` (`executed` | `mixed` | `attested`, derived from the
     entries, never accepted from a caller);
   - `current_tree_reverify` -- the closure-evidence consumer -- REFUSES an
     attested-only receipt: honest recorded evidence, never current-tree
     closure proof;
   - the closure-evidence FAIL now names the executable route
     (`saipen work reverify <T-###> --run '<executable check>'`) and reports
     "attested-only ... never closure proof" when that is the state;
   - RED control added: caller submits PASS text without executable proof ->
     receipt exists, `current_tree_reverify` returns None, the validator still
     FAILs closure-evidence; an executed `--run` then cures it end to end.

5. Documentation/help/effects gaps closed: usage names `work reverify`,
   `ticket reasoning`, `source retire`, `source recover`; COMMANDS.md carries
   rows for them plus `ticket resolve-external`; COMMAND_EFFECTS has explicit
   `source recover: DIAGNOSTIC`; OPS.md section 11 owns the contract.

6. M5.4 inventory interaction: the closure-evidence call's literal changed, so
   its fail-site identity moved; the new site (`deed137307b11cd8`) inherited
   the old site's verdict (`COVERED`, CASE "a ## DONE ticket carries no verify
   evidence") through the inventory's own renderer. The pre-existing
   unadjudicated site `17c1825e57d0436e` stays ABSENT from the ledger and
   visible as the same recorded T-1345 debt -- not hidden, not inflated.

## Verification (current bytes)

- `python tools/test_remediation_self_consistency.py` -> 12/12 OK: closed
  table; registry + explicit effects resolution per spec; no internal Python /
  pseudocommands; no generic-validate recursion; typed external records;
  extraction admits only table shapes; unregistered commands refused;
  parser+dispatch proof for all six commands (structured engine answers to
  nonexistent targets, no tracebacks); closure-evidence round trip end to end
  (validator red -> `saipen work reverify T-001 --run "exit 0"` -> green);
  help + COMMANDS.md name every command.
- `python tools/test_work_reverify_cli.py` -> 15/15 (includes the new M5.3
  RED control); `python tools/test_reverify.py` -> 17/17;
  `python tools/test_debt_gate.py` -> 30/30.
- `python tools/test_check_inventory.py` -> 37/42, the SAME 5 pre-existing
  failures at `17c1825e57d0436e`; `python tools/fail_site_inventory.py` -> one
  remaining failure, that same pre-existing UNADJUDICATED site.
- Neighbors: test_canonical_write_route 13/13, test_router_closure_readiness
  6/6, test_source_retirement 8/8, test_external_resolution 10/10,
  test_t1412_conformance_truth 10/10; test_public_closure_cli 9/10 (same
  pre-existing T-7 `SOURCE_SCOPE_MISSING`).
- Live front door: `saipen validate --json` on the home returns
  CONFORMANCE_UNHEALTHY with a CURRENT_FAIL receipt carrying
  `external_actions: []` and `remediation_commands: []` -- its 7 FAILs are all
  the untracked-file class below, whose lawful repair is a commit, not a
  command; no third remediation class is emitted.

## M5 audit conclusion

Every CURRENT error-level actionable remediation emitted by the validator is a
table entry and resolves to a registered canonical command; a genuine external
requirement has a typed record and never masquerades as a command. The gate is
executable: a future emitted remediation without a table entry, a renamed verb
or a dropped effects entry fails
`tools/test_remediation_self_consistency.py`, not a review.

## Home conformance note (PATCH_OWNED, resolution owned by T-1434 close)

Home `validate --gate core`: 7 FAILs, one class -- runtime-manifest names the
untracked T-1434 files (`external.py`, `remediation.py`, `test_*.py` M1-M5
deliverables). Resolution at T-1434 SHIP: one local commit of the T-1434
engine/test set (no push, no tag, no release); it also unblocks the
installed-generation move M7 needs.

## Exact next action

M6 (SRC-088): authority precedence and cross-repository provenance -- audit
explicit --project-root vs SAIPEN_PROJECT_ROOT/LINEAGE/AGENT/HOST_SESSION,
define deterministic precedence, keep wrong-root mutation refused, permit
safe read-only foreign observation, generalise the provenance model
(local/external/dependency/protocol-home/superseded), and re-measure the
T-1361 PROJECT_LINEAGE_MISMATCH cluster for shared root cause.

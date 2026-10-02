# T-1434 / SRC-088 — Milestone 1 evidence: canonical work reverify

Date: 2026-09-20. Session astra (continuation of SRC-088). Phase BUILD.
Mission: eliminate conformance states where the validator demands a
remediation the canonical command surface cannot perform.

## Defect reproduced before patch

- Validator rule `work_closure_evidence` refused with prose only:
  "re-verify with real evidence before DONE" — no executable command.
- `tools/saipen_engine/debt.py` carried `reverify_work` /
  `current_tree_reverify` and the validator already consumed the receipt, but
  `tools/saipen.py` had no `work` verb: the engine logic was unreachable from
  the public surface. Red evidence: LIMISAW `validate --gate core` reported
  21x `closure-evidence` problems whose remediation named no command.

## Implemented primitive

Command: `saipen work reverify <T-###> [--verification <cmd>:PASS]...
[--run <cmd>]... [--timeout SECONDS]` (`--json`, `--dry-run` global).

Semantics:
- resolves the Work canonically; accepts only `## DONE` Work;
- preserves original implementation provenance (`original_closure`: owner,
  claim_time, closure_mode, source_receipts, last ticket-bearing LOG event);
- keeps DONE, LOG and historical evidence byte-identical;
- executes the current contract: `--run` commands are really executed in the
  project root (timeout/launch failure is an honest FAIL), `--verification`
  records caller-attested checks (non-PASS refuses, zero writes), and with
  neither the project's own strict gate is recorded as the executed contract;
- writes ONE immutable, journaled `RV-NNNNNN` receipt bound to project
  identity + lineage + ruleset + source checkpoint + verification contract
  identity + integrity digest;
- idempotent for same Work + tree + contract + ruleset + successful receipt;
  a newer FAIL is never hidden behind an older PASS, and the current run's
  failure is never hidden by reuse.

Files (sha256[:16] at capture):
- tools/saipen.py 8d377530c07db473 (dispatch),
- tools/saipen_engine/debt.py 2cd7b80b8867a83a (engine),
- tools/saipen_engine/conformance.py 55a1cf92a34c002c (receipt carries
  bounded `remediation_commands`/`canonical_next_command`),
- tools/saipen_engine/router.py 30223bd533699fee (conformance gates lead with
  the failure-named command),
- tools/validate.py 61b330b0bbb57478 (closure-evidence FAIL names
  `saipen work reverify T-###`),
- saipen/REGISTRY.json f7770fddf0d82cb7 (command list),
- saipen/COMMAND_EFFECTS.json 9211a3b55c0f27df (`work.reverify` = RECOVERY),
- saipen/COMMANDS.md eebf78f467e0ef7a, saipen/OPS.md 43a07327162d8e64 (docs),
- tools/validator_fail_sites.json 252ad53c4324eca7 (new closure site
  adjudicated COVERED: "a ## DONE ticket carries no verify evidence"),
- tools/test_work_reverify_cli.py 0738698a6c35d252 (new regression suite).

Parser / registry / effects / router / validator integration: all present.
The validator remediation is executable: `saipen work reverify T-008`
(guard-canonical, no quotes, registered RECOVERY verb).

## Verification (current bytes)

- `python tools/test_work_reverify_cli.py` -> 14/14 OK. Families covered:
  historical implementation evidence valid; stale closure cured by current
  reverify; failed executed check writes FAIL and never false green;
  repeated identical reverify REVERIFY_REUSED; malformed work id; non-DONE
  refusal; attested grammar; missing contract; timeout; validator
  before/after; DONE/LOG immutability; receipt provenance fields.
- `python tools/test_reverify.py` -> 17/17 OK (engine back-compat; tree-change
  family).
- `python tools/test_debt_gate.py` -> 30/30 OK.
- `python tools/test_router_closure_readiness.py` -> 6/6 OK.
- `python tools/test_canonical_command_reachability.py` -> red pre-existing
  (quoted-command grammar assertions, untouched by M1).
- `python tools/test_effect_authorization.py` -> 34/34 OK,
  `python tools/test_guard_events.py` -> 55/55 OK,
  `python tools/test_command_routing.py` -> 63/63 OK, all with the ambient
  `SAIPEN_*` carriers cleared; with carriers set they fail on
  `PROJECT_LINEAGE_MISMATCH` for fixture roots (T-1361 environment cluster,
  same class as the M6 observation).
- `python tools/test_check_inventory.py` -> 5 pre-existing failures, all from
  fail site `17c1825e57d0436e` ("BOARD.md invalid Work supersession") added by
  the prior uncommitted tree; zero failures mention the M1 closure site.
- `python tools/test_public_closure_cli.py` -> 1 pre-existing failure,
  `SOURCE_SCOPE_MISSING` for T-7 (unrelated).
- Deliberately not run: full `run_scenarios.py` (T-1361 measured baseline).

## Milestone exit check

- validator remediation is executable: yes;
- successful reverify clears only the corresponding current-tree defect:
  proven by the real validator run before (FAIL) and after (PASS) on the
  fixture;
- failed reverify never produces false green: FAIL receipt is newest, the
  validator still fails;
- immutable history preserved: BOARD/LOG byte-identical across reverify.

## Exact next action

M2 (SRC-088): canonical external-implementation closure
(`EXTERNAL_IMPLEMENTATION_LOCAL_VERIFICATION`) + `saipen ticket
resolve-external <T-###> ...`; re-evaluate LIMISAW T-73 individually, then
T-66 and T-67 individually.

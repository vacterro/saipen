<!-- SAIPEN KNOWLEDGE INDEX v1; generated projection; not authority -->
source-digest: sha256:76be408efe4aaab9f264cedd5c29d8f5b2d4a39e427b6f8788280155ad539919
cards: 25
legacy: 42

# Knowledge index

Active cards are retrieval candidates. Superseded cards remain forensic history.

- cards/a-bound-set-from-an-expectation-answers-no-to-success.md | trap | scope: tools/saipen_engine/test_runner.py, tools/saipen_engine/core_unit.py, extensions/adapters/opencode/saipen-guard.js, extensions/adapters/registry.json, bootstrap/inject.ps1, host hooks, declared core-unit family | trigger: a TIMEOUT verdict on a family run that was in fact green, an EXEC_RESPONSE_INVALID: ETIMEDOUT from a host adapter, or any budget/bound that a slow-but-healthy path crossed | active
- cards/a-child-must-receive-the-selected-profile.md | trap | scope: installer, subprocess, user profile, HOME, USERPROFILE, PATH launcher, Windows Bash | trigger: an installer invokes a child that chooses a user home, or a host test redirects only HOME | active
- cards/a-control-run-once-counts-a-coin-flip.md | trap | scope: tests over receipts, journal records and other engine-ordered lists, mutation controls, a test that passes alone and is red in the declared family | trigger: asserting an index into a list the engine sorted, running a mutation control, or reading "undetected 0" off a control script | active
- cards/a-copied-tree-runs-the-live-engine-through-a-pinned-launcher.md | trap | scope: tools/saipen_engine/core_unit.py, tools/saipen_engine/install_identity.py, bin/saipen, bin/saipen.cmd, test_t1627_operator_question, test_t1645_zero_hunt, declared core-unit family | trigger: a single-process (`--jobs 1`) family red on the four t1627 real-transport tests and/or the two t1645 launcher tests, or any core-unit run started while the home tree is still being edited | active
- cards/a-holders-sidecar-must-be-withdrawn-on-release.md | trap | scope: protocol evidence files, project writer lock, whole-tree digest oracles, Windows | trigger: a critical section writes diagnostic bytes beside a permanent lock carrier and releases without withdrawing them | active
- cards/a-shared-temp-root-lets-a-bystander-delete-a-live-sandbox.md | trap | scope: the declared core-unit family, sandbox lifecycle, machine-shared TEMP/TMP roots, concurrent sessions, stale-sandbox sweeps, mass red counts | trigger: reading a mass red count from a family run, or changing how a sandbox is created, stamped or swept | active
- cards/a-write-path-check-does-not-protect-the-read-path.md | trap | scope: tools/saipen_engine/operator_task.py, host ingress envelopes, operator carrier provenance | trigger: operator ingress carrier, host_ingress envelope, session binding, replay, wrong-session carrier | active
- cards/automation-block-is-the-only-machine-truth.md | convention | scope: saipen status --json, automation block, external drivers, Run to Closure | trigger: deciding whether an external driver may continue, stop, or trust a completion signal | active
- cards/copied-trees-inherit-the-provenance-ledger.md | trap | scope: audit fixtures, copytree, journal provenance, op ids, gitignored recovery ledger, validate.py | trigger: a fixture or probe appends a synthetic [T-###] LOG event to a copied tree and must survive validate.py | active
- cards/downstream-shape-is-a-hypothesis-about-bytes.md | trap | scope: recovery repairs, release and crew closure repairs, downstream project reports, reconcile, regression fixtures | trigger: fixing a recovery, reconcile, release or crew defect from a report that describes a stranded downstream project | active
- cards/git-eol-conversion-breaks-byte-bound-evidence.md | trap | scope: .gitattributes, core.autocrlf, git stash, byte-bound evidence, managed projects, Windows | trigger: a digest-verified SAIPEN file (source body, archive, log detail, board compaction) fails its sha256 in a project on Windows | active
- cards/name-the-route-the-guard-admits.md | trap | scope: validator findings, engine refusals, next_action values, protocol prose that names a command, guard admission of shell lines | trigger: writing a finding, refusal or law sentence that tells a reader which command clears a condition | active
- cards/narrative-authority-leakage.md | trap | scope: validators, authority, free-form prose, structural markers | trigger: adding a validator or gate that derives authority from human prose | active
- cards/nested-unittest-drains-outer-module-cleanups.md | trap | scope: unittest, nested suites, borrowed tests, test isolation, module cleanup, host environment | trigger: running a test case from another module inside an active unittest case | active
- cards/opencode-plugin-source-and-installed-move-together.md | trap | scope: extensions/adapters/opencode/saipen-guard.js, installed OpenCode plugin, declared core-unit family, test_opencode_host_smoke, SHIP evidence | trigger: editing the OpenCode guard plugin source, or a core-unit family red on test_fresh_process_loads_the_installed_generation_from_one_origin | active
- cards/opencode-shim-is-not-the-native-payload.md | trap | scope: OpenCode native smoke, core-unit family, PATH, npm platform payload, verification environment | trigger: OpenCode smoke reports a Windows-incompatible executable or no startup probe despite a present command | active
- cards/plan-that-writes-into-a-tree-it-binds.md | trap | scope: engine operations built on OperationPlan, read-only tree dependencies, journal recovery, crash injection tests, sealed LOG segments | trigger: writing an operation whose target lives inside a directory the plan also binds as a read dependency, for example a new file under .saipen/logs | active
- cards/receipt-integrity-before-filter.md | trap | scope: reverify receipts, integrity digests, receipt selectors, closure evidence | trigger: a digest-verified record reader filters receipts by mutable body fields before validating their integrity digest | active
- cards/red-control-before-green.md | convention | scope: tests, gates, red controls, regression oracle | trigger: adding a check or claiming a defect is fixed | active
- cards/tests-mask-the-host-locale.md | trap | scope: subprocess, stdin, text mode, encoding, Windows, tests, hooks, validator | trigger: passing text to or reading text from a child process, or writing a test that spawns one | active
- cards/the-launcher-is-part-of-the-verifier.md | trap | scope: executed regression receipts, regression_execution, review remeasurement, Windows launchers, Python runtime | trigger: a read-only evidence audit reports STALE_REGRESSION_EVIDENCE while current subject and oracle bytes still match | active
- cards/the-rule-an-agent-broke-may-be-a-rule-we-wrote.md | trap | scope: incidents where an executor did something the protocol forbids and said so, activation block edits, fallback and degraded-mode clauses in OPS and BOOT, host-facing fixes | trigger: an incident report quoting an agent that "knew" a limitation and worked around it, writing a guard against an agent behaviour, or calling a host-facing fix done | active
- cards/unattributed-tree-edit.md | trap | scope: working tree, shipped surface, release scope, attribution | trigger: finding a modified shipped file no active Work authorized | active
- cards/whole-source-contracts-before-the-family.md | trap | scope: new engine modules, CLI refusal codes, printed commands, subprocess calls, declared core-unit family, SHIP evidence | trigger: adding a module under tools/saipen_engine, a refusal code, a string literal that starts with the command word, or a subprocess call, before paying for the declared family | active
- cards/windows-replace-read-sharing-race.md | trap | scope: runtime state files, atomic replace, cross-process readers, Windows | trigger: one process atomically replaces a file that another process reads without a shared lock | active

Legacy KNOWLEDGE documents (path and title only; no structured metadata):

- agent_creed.md | legacy | title: Agent creed and observed habits
- audit_2026-08-21.md | legacy | title: External audit inventory — 2026-08-21
- backlog_review_v8.md | legacy | title: Backlog review after DOGFOOD V (T-614, 2026-08-10)
- claim_to_proof_II.md | legacy | title: NITRO Claim-to-Proof Matrix (NITRO DOGFOOD II, T-590)
- claim_to_proof_IV.md | legacy | title: Claim-to-proof IV -- GATE INTEGRITY (NITRO dogfood IV, T-602..T-596)
- claim_to_proof_V.md | legacy | title: Claim-to-proof V -- PROVENANCE INTEGRITY (NITRO DOGFOOD V, T-615..T-618)
- claim_to_proof_VI.md | legacy | title: Claim-to-proof VI -- FOUNDATION SEAL + REAL CRITIC DOGFOOD (T-625)
- crew-v8-backlog.md | legacy | title: SAIPEN v8 Concurrent Mode Design Backlog (gated)
- decisions.md | legacy | title: Decisions
- evolution.md | legacy | title: SAIPEN Evolution Queue (queued directive)
- harness.md | legacy | title: Harness — the gate commands, cited rather than rediscovered
- hotpath-ownership-T-1259.md | legacy | title: T-1259 Hot-Path Ownership Map
- improve_red_controls.md | legacy | title: Improve spec red controls -- mechanical coverage inventory (T-560)
- NITRO.md | legacy | title: SAIPEN NITRO — foundational mechanical acceleration (gated backlog)
- phase-ownership-T-1229.md | legacy | title: T-1229 Phase Ownership Map
- PRIME_AGENT_EXTRACTION.md | legacy | title: Prime Agent Extraction Audit — v9 research
- roadmaps/conformance-admission-2026-10-09.md | legacy | title: Conformance admission investigation — 9 October 2026
- roadmaps/next-2026-08-31/00_README.md | legacy | title: SAIPEN NEXT ROADMAP — CURRENT IMPLEMENTATION 31 AUG 2026 10:33
- roadmaps/next-2026-08-31/01_VERIFIED_CURRENT_FINDINGS.md | legacy | title: 01 — VERIFIED CURRENT FINDINGS
- roadmaps/next-2026-08-31/02_WAVE_0_HISTORY_VALIDATOR_REPAIR.md | legacy | title: 02 — WAVE 0: EMERGENCY HISTORY / VALIDATOR TRUTH REPAIR
- roadmaps/next-2026-08-31/03_WAVE_1_SRC013_COVERAGE_TRUTH.md | legacy | title: 03 — WAVE 1: SRC-013 COVERAGE TRUTH REPAIR
- roadmaps/next-2026-08-31/04_WAVE_2_PHASE_COMPRESSION_A.md | legacy | title: 04 — WAVE 2: PHASE COMPRESSION A — FINISH CURRENT LARGE-PHASE WORK
- roadmaps/next-2026-08-31/05_WAVE_3_PHASE_COMPRESSION_B.md | legacy | title: 05 — WAVE 3: PHASE COMPRESSION B — COMPLETE ALL 16 DELTAS
- roadmaps/next-2026-08-31/06_WAVE_4_AUDIT_INBOX_HARDENING.md | legacy | title: 06 — WAVE 4: NATIVE AUDIT INBOX HARDENING
- roadmaps/next-2026-08-31/07_WAVE_5_AUDIT_DIRECTORY_HYGIENE.md | legacy | title: 07 — WAVE 5: LIVE AUDIT DIRECTORY / TRANSPORT HYGIENE
- roadmaps/next-2026-08-31/08_WAVE_6_SHARED_PRODUCER_API.md | legacy | title: 08 — WAVE 6: SHARED AUDIT PRODUCER API + ENVELOPE
- roadmaps/next-2026-08-31/09_WAVE_7_MAINTAINER_CLOSED_LOOP.md | legacy | title: 09 — WAVE 7: MAINTAINER DISPOSITION / CLOSED LOOP
- roadmaps/next-2026-08-31/10_WAVE_8_REAL_HUSH.md | legacy | title: 10 — WAVE 8: REAL HUSH RUNTIME
- roadmaps/next-2026-08-31/11_WAVE_9_SAIPAL_BRIDGE.md | legacy | title: 11 — WAVE 9: SAIPAL BRIDGE READINESS
- roadmaps/next-2026-08-31/12_WAVE_10_RELEASE_BACKLOG_CLEANUP.md | legacy | title: 12 — WAVE 10: RELEASE / BACKLOG / CLEANUP STABILIZATION
- roadmaps/next-2026-08-31/13_MASTER_TEST_MATRIX.md | legacy | title: 13 — MASTER TEST MATRIX
- roadmaps/next-2026-08-31/14_RISK_REGISTER.md | legacy | title: 14 — RISK REGISTER
- roadmaps/next-2026-08-31/15_AGENT_MASTER_PROMPT.md | legacy | title: MASTER AGENT PROMPT — SAIPEN CURRENT STAGE
- roadmaps/next-2026-08-31/16_DONE_CRITERIA.md | legacy | title: 16 — FINAL DONE CRITERIA
- roadmaps/README.md | legacy | title: Roadmap reference packs (NOT the audit inbox)
- roadmaps/saihandoff-agent-drift-2026-10-09.md | legacy | title: SAIHANDOFF agent drift incident — 9 October 2026
- roadmaps/saispin-session-forensics-2026-10-09.md | legacy | title: SAISPIN session forensic audit and execution safety debt — 9 October 2026
- T-392-reorg-plan.md | legacy | title: T-392: Architectural Reorganization Plan
- traps.md | legacy | title: Traps
- v8_evaluation.md | legacy | title: v8 evaluation after the repaired foundation (T-613, 2026-08-10)
- V9_RUNTIME.md | legacy | title: SAIPEN v9 Runtime Design — Resident Execution Under SAIPEN Law
- XPATCH.md | legacy | title: XPATCH — Cross-Repo Patch Receipt (design, not yet implemented)

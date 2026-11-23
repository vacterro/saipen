# T-1836 — conservative impact planning and execution

Parent T-1829; SRC-285 R003/R004. This report proves the bounded wave,
not the campaign, the 30% economics target or publication readiness.

## Change and cause

The existing core-unit CLI now offers `impact T-### [--changed PATH] [--plan]`.
A deterministic plan binds changed paths, source generation, source/test
inventory, static dependency closure, selection reasons and escalation rules.
Default changes include tracked and untracked Git changes; explicit scopes
still include visible changed tests and never certify unlisted source changes.
Plans execute nothing and create no verification citation.

Only a closed static domain may select a subset. Unproved calls, imports,
reflection, callbacks, shared effects, shadowed bindings, source boundaries,
fixtures and protocol/adapter/validator changes require FULL. Imported
TestCases are selected by their defining module, with canonical multiplicity.
Execution uses the existing immutable copy, discovery/shard, fixtures,
single-flight and focused record paths. Runtime origins, exact discovered
occurrences and import failures are checked. No second runner was introduced.

Executed IMPACT evidence remains `focused-unit`. A shared full-scope predicate
rejects scoped output/configuration in full production, reuse, cache loading,
local full SHIP and publication. Manual FOCUSED and independent full-family,
whole-suite and release requirements retain their existing owners. The tier
and lifecycle audit is `TIER-CONTRACTS.md`; it makes no host-enforcement claim.
The existing economics view counts typed IMPACT separately from FOCUSED/FULL.

## Executed evidence

* Windows final impact controls: 25 PASS (`windows-targeted.log`).
* Native Ubuntu Python 3.12.3 / Git 2.43.0: the same 25 controls PASS
  (`linux-targeted-ubuntu.log`). The earlier minimal Linux failure is preserved
  in `linux-targeted.log`; missing Git now produces an explicit-scope diagnostic.
* Current managed Python 3.11.9 focused package: PASS, 148 reported, actual
  duration 183.015 s, first request 194.219 s. Exact record:
  `.saipen/evidence/focused-unit/c2df6f3237b4b77f-20261020T181714884036Z.json`,
  SHA256 `91df72f786d7c80473541172cf91455555a7d1633e09686406ee7f8a5a89169c`.
  It covers impact, full/focused gates, shards, occurrence/timing manifests,
  single-flight, economics and source-wide refusal/reachability/UTF-8 contracts.
* REVIEW independently requested the same exact package and reused this
  unchanged record in 8.516 s. This is one execution with two consumers,
  not 296 executed checks or two independently executed suites.
* `prefix-relabelled-scope.log` preserves the original reproduced publication
  acceptance of a relabelled scoped configuration. `scope-pair.json` reruns the
  final unchanged oracle against a controlled pre-guard predicate and corrected
  predicate: exit 1 then 0, same oracle SHA256
  `73835e794c4dad47cf85768c9a279bec9a111f1d6d8bd5c4739c67c200da6632`.
  The controlled predicate is explicitly not a historical whole checkout.

Controls include actual scoped execution, omitted unrelated red, transitive
and added tests, imported duplicate cases, module-fixture ordering, nested
discovery, preserved import errors, foreign module origins, stale/tampered
plans and manifests, boundary escalation, unchanged plan-only state and
rejection of full-record promotion. No existing assertion was removed.

## Measured cost and limitation

`planning-benchmark.json` measures only static planning on one frozen
tools-only corpus: the same 464-test inventory, fingerprint, inventory digest
and FULL decision. Eager analysis took 13.741 / 13.989 s; early conservative
FULL escalation took 0.261 / 0.304 s. Whole-file implementation hashes identify
the measured revisions; subsequent missing-Git handling/formatting does not
change the measured planner function. This is not a suite execution speedup.

`actual-plan-fast.json` records a 0.500 s current-repository FULL decision,
464 selected modules and an explicitly incomplete dependency scan. Once FULL
is inevitable, extra AST scanning cannot reduce the required test coverage.
The actual SAIPEN graph is not certified for automatic narrowing. Manual
focused evidence retains its explicit reviewed-scope policy. No broad suite
was launched merely to print an escalation.

## REVIEW and next action

Executing-agent self-audit, pass 1, source fingerprint `c2df6f3237b4b77f`:
inspected the owned planner, direct CLI/focused/shard callers, immutable plan
revalidation, import/fixture/occurrence/origin failure paths, unchanged manual
configuration, full-scope consumers and typed economics classification.
Oracle changes add adversarial coverage; canonical discovery and fixtures
remain the execution basis. No additional confirmed acceptance defect.
No second-agent/human review or reusable memory promotion is claimed.

DEC: SHIP this local wave in a new pending cohort, preserving older hashes.
Next: resume T-1829 for CI interface parity and measured sandbox/discovery
decisions, then final stable-generation multi-family/platform acceptance,
adverse controls, A-J delivery and publication/provenance reconciliation.
Future publication destination is GitLab per the operator; this wave did not
commit, tag or push anything.

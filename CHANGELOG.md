# Changelog
> Older entries live in [CHANGELOG_ARCHIVE.md](CHANGELOG_ARCHIVE.md) -- this file keeps the most recent ~10.

## 8.0.1 -- 2026-09-08 -- Audit release integrity and bounded receipt lookups (T-1298, SRC-025)

- Preserve exact reviewed release identities, crew semantic applicability, and fail-closed audit transport authority.
- Bound settled-operation and conformance-lineage hot lookups and appends while retaining explicit deep validation.
- Centralize producer-gate severity policy and handle audit sweeps with zero runnable controls.
- Restore complete structured validator findings for debt consumers; a classifier failure makes the export unavailable instead of publishing partial evidence.
- Select the latest rebuilt conformance receipt by completion time and receipt identity, independently of filename order.
- Remove residual CLI handlers for unavailable source-recovery functions; keep unfinished debt commands and orchestration work outside this publication.

## 8.0.0 -- 2026-09-06 -- Distinct STOP Shortcut (T-1297, SRC-024)

STOP shortcut changes from `ss` to `st` because repeated-letter `ss`/`sss` caused STOP/STATUS ambiguity for agents. `sss` remains STATUS; old `ss` is retired fail-closed and performs no action. Long-form commands are unchanged.

## 7.257.0 -- 2026-09-06 -- The Run-to-Closure Producer Wave Closes Itself (T-1296, SRC-023)

The producer-side implementation order (audit/10.md) was largely satisfied by the v7.256.0 automation contract; this release adds what the audit explicitly demanded on top of it.

- Render the display-only `SAIPEN_CLOSURE_COMPLETE` line (with compact `audit=`/`source=` evidence) only when the mechanical disposition is COMPLETE; the JSON automation block stays byte-clean and remains the only machine truth.
- Add the missing deterministic test cases: an empty physical folder with an unsettled canonical intake (MISSING_AFTER_CAPTURE orphan) is not quiescent, DONE phase and empty board alone are insufficient, structural corruption is INVALID fail-closed, identical epoch + source yield byte-stable output, manual semantics outside Run to Closure are unchanged, and a real `saipen status --json` subprocess run writes zero project bytes.
- Add the §10 acceptance fixture: a disposable three-layer project driven through the real audit transport proves work → CONTINUE, first quiescence with a pre-boundary pass → not COMPLETE, a post-boundary fresh pass → COMPLETE, a new `audit/4.md` invalidates the prior closure and drifts the epoch, and after it drains a stale pass stays CONTINUE until a fresh pass restores COMPLETE.
- Document the contract in the smallest owners: the `automation.py` module docstring and one indexed KNOWLEDGE card naming that only the automation block is machine truth.
- Verification: 1,217 unit tests (one skip), 29 automation tests, ruff clean on the tracked surface, validator 0 FAIL / 27 known warnings.

## 7.256.1 -- 2026-09-06 -- Cross-Repository Wave 1 Closed By Its Own Deliverable (T-1295, SRC-022)

The external execution-order audit (audit/9.md) directed SAIPEN to implement the authoritative `saipen status --json` automation contract, prove audit quiescence and post-empty convergence, and ship tests. Wave 1 of that order is exactly the v7.256.0 deliverable: the contract shipped there with its 22 red controls, and the wave-2 consumer (SAITULS) is excluded from this repository's writable scope by the audit's own ordering.

- Capture audit/9.md as SRC-022, normalize its Wave-1 clause, and disposition it VERIFIED against the shipped v7.256.0 evidence (SRC-021 R1-R8 lineage), with the live CLI surface re-verified.
- No code change: the actionable content was already terminal; this release closes the audit layer's source receipt and consumes the transport file through the journaled inbox cleanup.
- Verification: SRC-022 coverage 1/1 terminal, `test_automation_block` 22/22 re-executed, validator 0 FAIL / 27 known warnings.

## 7.256.0 -- 2026-09-06 -- The Machine Surface Run-to-Closure Consumes (T-1294, SRC-021)

External transport automation (SAIPATCH) had no machine answer to "should I continue or stop": the only signals were human prose and a router verdict inside `saipen next`, so an automation loop could only guess. The SAIPEN ↔ SAIPATCH Run to Closure contract makes SAIPEN own that semantic truth and publishes it as a read-only projection.

- Add `saipen_engine/automation.py`: the `automation` block on `saipen status --json` carries the closed disposition vocabulary (CONTINUE | COMPLETE | WAIT_USER | WAIT_EXTERNAL | BLOCKED | INVALID) mapped from the same router verdict status already computes, `next_command` = `cc` exactly for CONTINUE and null otherwise, audit quiescence and a deterministic audit epoch from the transport's own classification, convergence currency from the canonical convergence verdict, and `completed_at` from the newest closure receipt when the gate passes.
- Implement the eight-condition COMPLETE gate (R5) with the race rule (R6): a consume event at or after the closure instant vetoes COMPLETE, same-minute stamp ambiguity fails closed, and a physically empty `audit/` is not sufficient (residue and missing-after-capture orphans veto quiescence).
- Enforce the pre-authorization limits (R7): a safety-valve WAIT keeps ordinary `cc` legal; user brake, manual-verify, destructive-op and first-publish are WAIT_USER; foreign-live progress is WAIT_EXTERNAL; read-only sessions and unreadable states are BLOCKED or INVALID with `next_command: null` — every projection failure fails closed, never into a healthy-looking block.
- Verification: 1,210 unit tests (two skips, 22 new), ruff clean on the tracked surface, validator 0 FAIL / 29 known warnings, live `status --json` block verified CONTINUE+`cc` while the audit layer is still active.

## 7.255.0 -- 2026-09-05 -- A New Check Cannot Arrive Uncovered (T-1292)

The validator check shipped in 7.254.0 was proven by a hand transcript that did not survive the session, and the red-control sweep read the same total before and after it landed. That total is what a checkpoint quotes as proof the control ledger is intact, so a check arriving with no control moved no number.

- Add two permanent red controls for the KNOWLEDGE structured surface, one per independent failure class: a card whose `kind` is outside the closed set, and a changed card that leaves the index projection stale. The sweep total grows from 230 to 232.
- Bind the sweep to the validator: `check_inventory_probe` records how many fail sites `tools/validate.py` declares and fails when that surface grows or shrinks, naming the remedy. The probe carries its own red control, so a counter that could not notice a new check cannot report green.
- State the bound rather than implying coverage. The count binds volume, never identity: a change that adds one check while deleting another keeps the total and passes. The limitation prints as a NOTE on every run and is recorded in `KNOWLEDGE/harness.md` beside the red-control law.
- Verification: 232 of 232 controls still go red on their own condition, 1,188 unit tests (one skip), 18 focused tests holding `validate_knowledge` fixed across each mutation's red and green halves, plus the canonical validator/scenario/floor/parity/order/tags/lint gates.
- T-1293 tracks a defect found during review: the sanctioned safety-valve resume writes a `next_action` the audit-route check rejects while an audit layer is active.

## 7.254.0 -- 2026-09-05 -- Retrieve Durable Project Lessons (T-1291, SRC-020)

Optional KNOWLEDGE cards carry a reusable claim, its Why, evidence, and retrieval scope. Cold decision context receives only matching active cards; existing free-form knowledge remains valid.

- Add a stdlib card parser, structural validation, explicit supersession, seven-criterion promotion gate, deterministic index projection, and knowledge status/index/retrieve commands.
- Keep manually authored INDEX.md valid and refuse to overwrite it. Reject incoherent supersession during fallback retrieval and return CLI failures for invalid cards.
- Preserve legacy documents; dogfood three existing lessons. The generated index is 4882 bytes. Same-checkpoint unrelated cold context remains 3809 bytes / 979 repository-counted tokens. Freshness still reads the tree internally; context selection is bounded.
- Verify 1170 unit tests (one skip), 39 focused knowledge tests, four pre-fix red/post-fix green review regressions, and the canonical validator/audit/scenario/lint gates. T-1292 tracks the missing permanent audit_checks control for the new structured validator check.
- SRC-020 has ten verified actionable clauses. Full implementation evidence and limitations: .saipen/kitchen/t1291-review.md.

## 7.253.0 -- 2026-09-05 -- Freeze The Decision, Preserve The Evidence (T-1288, SRC-019)

**This release closes all nine actionable requirements from external audit SRC-019: six repairs are verified here, while three performance findings are explicitly deduplicated to T-1283 and T-1284.**

- Release certification now freezes every built-in crew role's applicability verdict, reason, probe and source identity in the pre-ship receipt. Post-ship checks consume that immutable manifest instead of recomputing against a later tree; legacy receipts still require the full roster.
- Applicability facts are captured inside the same source-stability window as the rest of the crew snapshot. A source movement can no longer turn an uncertain role into a trusted NOT_APPLICABLE decision.
- Python UI detection now parses imports with the AST after a cheap toolkit-name prefilter. Multi-import statements and dotted imports are recognized, while unreadable, oversized or syntactically invalid candidates fail closed to APPLICABLE and name the uncertain path.
- Audit enqueue recovery now reconstructs a lost allocator from surviving payload or inbox-binding evidence without allocating a duplicate layer. A COMMITTED operation whose bytes vanished is acknowledged only when the binding proves the exact digest was captured; otherwise it refuses with NEEDS_REPAIR.
- Audit inbox binding has one strict decoder. Missing remains ABSENT; invalid UTF-8/JSON, malformed records, unreadable paths and obstructed filesystem nodes are CORRUPT. Classification and ingestion report that state without laundering the authority through a rewrite.
- Two additional review controls close same-HEAD edge cases: an applicability manifest bound to another working tree cannot certify, and an obstructed binding path cannot be mistaken for absence.
- Verification: 1,131 unit tests passed (2 skipped); validator, 230 hostile audit controls, scenarios, audit floor/parity/order/tags and Ruff all passed. Two exact pre-fix implementations were executed against the unchanged new tests and went red before the current implementations went green.
- Source accounting: SRC-019 R1-R6 VERIFIED; R7-R8 DUPLICATE of T-1283; R9 DUPLICATE of T-1284. Context clauses add no independent obligation.

## 7.252.0 -- 2026-09-04 -- A Gap Is Not A Backwards Step (T-1281, T-1285)

**Two defects in one file, published together because they are the same file and one of them was blocking the other's release.** T-1281 is the closure classifier reading ordinary English as a failure verdict. T-1285 is the ledger-gap check, restored with an escape. Both live in `tools/saipen_engine`, and T-1281 vetoed four green cycles in one session -- including the closure of the ticket that reported it.

### Prose was a failure verdict (T-1281)

- `_claims_failure` counted every `FAIL`-family token anywhere in an event body and vetoed unless each one carried an adjacent zero. **So a PASS event that DESCRIBED what it repaired vetoed its own closure.** Four reproductions, same tree, same measurements, only prose moved: `the pre-fix FAIL is re-established`, `a failed atomic write leaves no orphan`, `zero anchored failures` (the zero is not adjacent), and `CORE-004 was a fail-open condition` (the hyphen is a word boundary).
- **The cost was not merely a blocked close.** The release path creates and PUSHES its content commit before the closure gate runs, so the veto published commits whose subject says DONE over a board that says DOING -- `058ab732` for T-1276 and `794085e9` for T-1280. That compounding defect is T-1278 and stays open.
- `log.py` already names the class one screen away: **Narrative Authority Leakage**, a validator searching free text for a magic phrase. This was the same defect at the opposite polarity, and the cure is the same -- authority belongs to a shape, not to a word a sentence happens to contain.
- The verdict now lives in the **verdict segment**: the text up to the first ` -- `, which is how every canonical line in this repository is already written. T-1241's counting rule is kept exactly -- every token accounted for, a count rather than "contains a zero form somewhere", so `0 FAIL on core, 3 FAIL on ship` is still a failure -- and only SCOPED. Two machine shapes still claim from anywhere: a nonzero count (`2 FAIL`) and a nonzero field (`failures=2`, what unittest prints), because no prose produces them by accident.
- What this deliberately gives up: a bare lowercase `failed` in the detail of a line whose verdict says PASS. Stated in the docstring rather than discovered later.
- **The whole suite is green with zero existing tests changed**, and that is the load-bearing fact. The first attempt narrowed to leading-position and machine-count forms only; three existing contracts went red, and those three reds produced the verdict-segment design.

### A gap is not a backwards step (T-1285)

- The fast-path ledger check arrived in the working tree loosened from `event != prev + 1` to `event <= prev`, unattributed. That reports a BACKWARDS id and nothing else: **`E-001` followed by `E-005` returned no error at all**, and a forged line inserted into a gap rode straight through. A gap in an append-only ledger means events were lost or removed, which is exactly what the fast path exists to notice cheaply.
- Restoring strictness alone is not the answer either, and this was measured, not theorised: the loosening was a deliberate change made in a SHARED install by a project carrying two documented T-222-era holes in its chain. **Reverting it WEDGED that project** -- SAIOPS refused every mutation there, and the agent resorted to hand-writing events without op ids. Both requirements are real and in direct conflict: a gap must be detectable, and a project with legitimate historical gaps must not be permanently blocked.
- So a gap is a defect **by default**, and a NAMED gap is exempted by a recorded decision: a `DEC` whose text BEGINS `LEDGER-GAP AMNESTY E-<prev> -> E-<next>`. Same mechanism `structural_marker_events` already owns, same three conditions -- **taxonomy** (a `RUN` reporting one is not the decision), **anchoring** (a line discussing an amnesty is discussing it), and **bounding twice**: the exact pair, plus a deciding event at or after the gap, so no pre-dated grant becomes a standing licence to open holes for the rest of the project's life.
- **An exempted gap is reported, not silenced.** It rides on `LogAnalysis.amnestied`, separate from `errors`, because a hole nobody can see is precisely the state the loosening produced. The diagnostic also stops claiming `monotonicity` when it means consecutiveness -- that weaker contract belongs to `validate.py`, and the mismatch is what made the loosening look defensible.
- Amnesties resolve **lazily, on the first gap only**, so PERF-007's single pass is untouched for a clean ledger: verified against the live 709-line journal at 0 errors, 0 amnestied.
- 14 tests in `tools/test_ledger_gap.py` with five red controls -- the loosening itself turns 8 cases red, and dropping the taxonomy, the anchor, the bound or the amnestied report each turns one red.
- **Found while verifying and filed rather than fixed**: `audit_checks --changed` crashes with `ValueError: max_workers must be greater than 0` when the changed-path set selects zero controls, so v7.247.0's accelerator is unusable on an engine-module change. T-1287.
- 1083 -> 1097 in the suite.

## 7.251.0 -- 2026-09-04 -- There Is Nothing To Scan, And Nothing Was Enforcing It (T-1279, T-1280)

**This release carries two bodies of work in one scope, and says so rather than splitting a file that cannot be split.** T-1279 is the applicability model below. T-1280 is the external audit campaign captured as `SRC-018`, whose repairs touch the same `tools/run_scenarios.py` — one edit removed a scenario that ASSERTED a fail-open, another repaired a fixture that manufactured its own failure — so the two cannot be published independently without shipping a suite that does not pass.

### The audit campaign (T-1280, `SRC-018`, 12 of 12 requirements terminal)

An external 3-wave audit was ingested against the v7.249.0 snapshot and every finding was reproduced here before repair. It found a defect in the release shipped forty minutes earlier.

- **CORE-001 — the rule nobody called.** `VERIFY-ORACLE-01` shipped in v7.250.0 as a norm, a pure module and 21 focused tests, and `grep` finds **no production caller**: `operations.py` gated `VERIFY -> REVIEW` and `finish` through `verification_evidence` alone, which reads free-form text for `PASS` and `conf: high` and never compares an oracle to a subject. **The acceptance criteria were satisfiable by a module nothing invokes, because they were written that way.** Now a ticket declares `regression: required` — a closed-set BOARD field, never inferred from prose — records anchored `REGRESSION-EVIDENCE FAIL|PASS verifier:… subject:…` events, and BOTH authoritative gates consume `regression_pair_verdict`. Wiring it surfaced a second defect: a `REGRESSION-EVIDENCE FAIL` is the REQUIRED red half of a pair, and the ordinary classifier vetoed it on the word FAIL, so the two channels fought; they are now separated. 13 tests drive the REAL transition and finish APIs, because proving the verdict function in isolation is what created the gap.
- **CORE-002 — fail-open on the thing that supposedly changed.** A missing verifier failed closed; a missing SUBJECT fell through to `ADMISSIBLE`, so an unrecorded subject counted as proof the subject moved. Now `SUBJECT_UNRECORDED`. And `parse_identity` emitted `oracle`/`subject` while the verdict consumed `verifier`/`subject` — one vocabulary now, with a parser-to-verdict round trip asserted.
- **CORE-003 — human confirmation was a magic substring.** `MANUAL-VERIFY steps recorded` satisfied the gate, and so did *any prose mentioning the token*. `phases/verify.md` REQUIRES those steps precisely when nobody has looked yet, so **the instruction to wait for a person satisfied the gate that was waiting for that person.** The marker is now an anchored `MANUAL-VERIFY RESULT: PASS|FAIL` record; steps are a request.
- **CORE-004 — the typos that published.** `negotiate_capability` mapped an absent AND an unrecognised declaration alike to `full`, so `capability_error` could never fire. `readonly`, `read only` and `no_publish` are all attempts to RESTRICT a session and every one of them granted publish. Absent still defaults; a present invalid value is refused at the command boundary before a project root is even resolved. The scenario that ASSERTED `nonsense` negotiates `full` is gone.
- **W2-001 (P0) — a filesystem escape.** The audit enqueue wrote to the predictable `audit/.enqueue-<layer>.tmp` with no `O_EXCL`, no `O_NOFOLLOW` and no identity witness. **Reproduced on Windows through both a symlink and a hardlink: `_place` returned success, a file OUTSIDE the project became the payload, and the canonical layer pointed at it.** Now a randomly named staging file created exclusively, installed with `os.link`, which cannot clobber a destination that appeared after the existence test.
- **W2-002 / W2-003 / W2-004 — three ways to trust what was never checked.** A single `os.write` whose count was ignored, promoted on `is_file()` which follows symlinks; a corrupt allocator read as an empty one, turning an idempotent retry into duplicate dispatch; and an ingest that committed BOARD Work, then died, then refused to resume — while the router kept prescribing the very command that would not consume that state. **`SOURCE-AUDIT-INBOX-01` requires an agent to follow that route, so a conforming agent looped forever.**
- **PERF-002 — a control that could not fail.** The constant-I/O regression counted only the two iterators the direct locator legitimately avoids, then printed `constant-I/O (no full scan)` while one `latest_receipt` call hashed **1,052 of 1,052** conformance receipts. It now measures the real I/O and says `MEASURED, not constant`. The optimisations themselves are carried by T-1283 and T-1284 with measurements attached; three requirements are `SUPERSEDED`, not claimed.

Every repair carries a deliberate red control, and several were strengthened until they could go red: two tests in this wave were vacuous when first written — one compared `[] == []`, another read a ticket key that is always `None` — and one mutation set stayed green because the property was double-guarded, which is stated rather than presented as coverage.

**Two harness verdicts were investigated instead of retried.** The forged-non-event-line control went red because an unattributed working-tree edit had changed strict event consecutiveness to mere monotonicity: proven by direct comparison — `E-901` then a forged `E-903` reports an error under the original rule and **nothing** under the edit — reverted, and filed as T-1285. The crew-launcher control went red once and green on an identical tree; proven racy and filed as T-1286 rather than accepted as noise.

### The applicability model (T-1279)

- The crew roster was static. `CrewRole.ensure_instance` was a bool on a frozen dataclass, `crew.py` iterated it, and **nothing anywhere in `subs.py`, `crew.py` or `producer.py` could express that a project has no UI.** So a mandatory UI stage ran against a surface that does not exist -- eleven times over saiui's whole life, every package with an empty payload, against a tree carrying **zero** tracked `.html/.css/.scss/.tsx/.jsx/.vue/.svelte/.qml` files and zero `tkinter`/`PyQt`/`PySide`/`textual` imports -- and each honest empty package still became a Core review ticket with a claim, a verify clause and a disposition.
- **The cost was never the empty package.** A scanner that honestly finds nothing has done its job, and six-signal coverage is real coverage. The cost is that **absence of a surface and correctness of a surface reported identically**: a reader of the crew record could not tell "UI was audited and is fine" from "there is no UI", and every release carried a green UI certification either way.
- `saipen_engine/applicability.py` is the decision, pure, in the shape `oracle.py` and `audit_route.py` already established -- one impure function, quarantined at the bottom behind a banner. A role declares one probe from a closed set; `always` is the default and `visual-surface` is the only condition any built-in declares. The probe reads the project's own files, the same scan saiui's charter performs by hand, and finds a desktop application by import as well as by extension so a Tk or Qt app is not invisible for ending in `.py`.
- **Undecidable is APPLICABLE.** No facts, an unreadable tree, or a probe name the registry does not know all resolve to running the role. A capability that runs when it need not have costs a pass; one silently skipped costs the coverage it existed to provide, **and nothing reports the difference**. The model fails toward doing the work, and a red control proves no constant verdict satisfies the suite.
- **A verdict always names the deciding fact**, and the receipt survives a predecessor block. `NOT_APPLICABLE` with no reason is indistinguishable from a stage nobody ran, so blanking it to "waiting on predecessor" would hide the fact in exactly the plan an operator reads to find out why a stage is quiet. Here it reads: `no visual implementation file in 4954 scanned project files`.
- Six call sites, one helper. Roster, sensor stages, the collect and disposition sets, the pre-ship evidence set, post-ship certification and the final fixed point all ask `_role_applicability` -- two of them disagreeing is precisely how a role ends up skipped in one place and demanded in another. A NOT_APPLICABLE role also stops being spawned: an instance is machinery for producing evidence, and there is none to produce.
- `crew_snapshot` is on the `cc`/`sc`/`status` path, so the walk is not taken when no role declares a condition. Verdict-preserving by construction and tested as such: `None` resolves APPLICABLE for every probe, which is what an all-`always` roster would have answered anyway.
- **The scenario harness was red before this shipped, and it was not this ticket.** `run_scenarios.py` copies the whole repository into its release-freshness sandbox, empties DOING/DONE and forces a neutral `next_action` -- but left the copied `audit/` inbox alone, so a workable layer became a route violation **the probe manufactured and reported against the live repository**. Exactly the T-1240 intake shape that function already documents, one layer out; `SOURCE-AUDIT-INBOX-01` simply made a second surface into Work and the neutralizer was never told. Proven before it was repaired -- with the layer moved aside the violation is absent, with it restored it returns -- then the delivery inbox is emptied with the board. 1227 scenario checks, exit 0.
- 27 tests in `tools/test_crew_applicability.py`; 1016 in the suite; `audit_checks` 230 of 230 still go red on their own condition.

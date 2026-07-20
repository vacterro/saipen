# SAIPEN Gap Matrix (T-000, updated after T-001, T-003)

Produced per `SAIPEN_SPEC_DIRECTIVE.md` T-000, updated with T-001 and T-003
findings. Every CLOSED row has a grep/validator command and its actual output
as evidence, not a claim. This is scratch/audit output (kitchen/), not a
normative file -- do not cite it as spec.

## goal_exit / goal_mode board-empty behavior -- CLOSED, REJECTED, do not reopen

Asked the operator directly twice now (once after T-000/T-001, once again
after T-003 specifically) whether `goal_exit: objective | mature` should be
added, reversing `goal_mode`'s current board-empty-never-exits behavior.
Both times: keep current behavior. This is now a settled decision, not an
open question -- `SAIPEN_SPEC_DIRECTIVE.md` T-003's `goal_exit`/`goal_anchor`
fields and T-007 in full are REJECTED. Do not re-propose without new
evidence (a real trace showing the current behavior actually causing a
problem, the same bar the original board-empty-never-exits fix cleared).

## T-003 status: DONE (goal_exit/goal_anchor rejected, not pending)

Implemented: `WAIT: <question>` as a formalized legal `next_action` form
(RFC § 1.2, scoped to manual-verify/destructive-op/first-publish/user-brake
gates only), `blocker` MUST be non-empty when `phase: BLOCKED`, `updated`
MUST be UTC specifically (not just any ISO-8601 offset -- Recovery's
staleness comparison silently miscompares across timezones otherwise),
`task` MAY be literal `none`, and a schema-version migration rule (missing
`schema_version` -> treat as `0` and upgrade; a HIGHER `schema_version`
than this agent's own RFC copy understands -> degrade to `read-only` or
`BLOCKED`, never silently rewrite).

Declined, same reasoning as before, no new argument presented this ticket:
`schema: "7.7"` as a new field -- still redundant with existing
`saipen_version`/`schema_version`, which the migration rule above now
actually uses. `goal_anchor: T-### | none` -- still not needed; RFC § 2.4's
Final Report line already requires distinguishing "user's ask" from
"picked up along the way" without a persisted field.

`goal_exit: objective | mature` -- REJECTED, resolved, see the closed-item
note above. Not implemented, and not pending either.

## T-001 addendum: new items found while building the transition table

| ID | Gap | Evidence | Notes |
|----|-----|----------|-------|
| G-13 | `VALIDATE` phase had no defined entry trigger anywhere | `grep -rn "VALIDATE\|saipen validate" saipen/RFC.md saipen/phases/*.md saipen/SKILL.md saipen/CONFORMANCE.md` (before fix) returned zero hits outside `phases/validate.md` itself | FIXED this ticket -- `saipen validate` added to § 1.10 Command Surface. |
| G-14 | `phases/hunt.md` doesn't explicitly state HUNT's transition when findings exist (only the clean-board -> ADD case is explicit) | `grep -n "transition\|PLAN\|SCOUT" saipen/phases/hunt.md` -> only the clean-board ADD transition appears; nothing for the findings case | OPEN -- the transition table documents `HUNT -> PLAN \| SCOUT` as a reasonable inference (ambiguous findings become tickets, normal Ticket DAG flow applies), explicitly flagged as inferred, not sourced from `hunt.md` itself. `hunt.md` is out of T-001's stated file scope (RFC.md § 1.6, CONFORMANCE.md only) -- logged here rather than touched silently. |
| G-15 | The directive's own proposed T-001 transition table (in `SAIPEN_SPEC_DIRECTIVE.md`) had real inaccuracies, corrected before shipping, not copied blindly | `REVIEW -> SCOUT` claimed but not found anywhere in `review.md` (removed); `BLOCKED -> BUILD\|VERIFY\|REVIEW\|HUNT\|DONE` claimed but `blocked.md` only ever says "STATE -> PLAN or SCOUT" (narrowed); `ADD -> VERIFY\|DONE\|BLOCKED` claimed but `add.md` also explicitly transitions to `PLAN`, `SCOUT`, and `HUNT` (widened) | Every row in the shipped table was checked against the actual phase doc text before shipping, not assumed from the directive. |

## T-000 checklist (validator coverage)

| ID | Gap | File | Evidence command | Evidence output | Status |
|----|-----|------|-------------------|------------------|--------|
| G-01 | STATE.md frontmatter required fields | tests/validate.sh, tests/validate.ps1 | `bash tests/validate.sh` (against this repo's own `.saipen/`) | `PASS: STATE.md schema valid` | CLOSED |
| G-02 | BOARD.md section names actually verified to exist | tests/validate.sh, tests/validate.ps1 | same run | `PASS: BOARD.md has all required section headings` | CLOSED (this ticket -- was open before today, checked headings were never verified, only ticket-line shape was) |
| G-03 | BOARD.md ticket line shape | tests/validate.sh, tests/validate.ps1 + RFC.md §1.2 | same run | `PASS: BOARD.md no duplicate tickets` (shape-matching regex is what feeds every BOARD check) | CLOSED |
| G-04 | LOG.md line shape | tests/validate.sh, tests/validate.ps1 | same run | `PASS: LOG.md format valid` | CLOSED |
| G-05 | Event ID (`E-###`) uniqueness + monotonicity | RFC.md §1.2 (rule only, not validator-enforced) | `grep -oE '\[E-[0-9]+\]' .saipen/LOG.md \| grep -oE '[0-9]+' \| sort -n \| uniq -d` | Returns real duplicates from this repo's own history (vac->vacskill->SAIPEN rename-era resets, e.g. `E-001` appears 2x as a genuine event, plus once more inside prose quoting it as text) | OPEN, deliberately not validator-enforced -- see reasoning below |
| G-06 | `[parent: E-###]` link resolution | RFC.md §1.2 (rule only, not validator-enforced) | n/a -- not attempted, same reasoning as G-05 | A resolver would need to track "seen IDs" incrementally through a file with real historical numbering resets; building and testing that safely is bigger than this ticket's scope | OPEN, same reasoning as G-05 |
| G-07 | `needs:` acyclicity | tests/validate.ps1 (bash defers to PowerShell for this one, documented) | `powershell -File tests/validate.ps1` | `PASS: BOARD.md acyclic` | CLOSED |
| G-08 | `needs:` dangling references | tests/validate.sh, tests/validate.ps1 | synthetic fixture: `T-002 needs: T-999` (T-999 doesn't exist) | `FAIL: BOARD.md has dangling needs: reference(s): T-999 ...` (bash); `FAIL: ... T-002->T-999 ...` (ps1) | CLOSED |
| G-09 | mode/phase basic compatibility | tests/validate.sh, tests/validate.ps1 + RFC.md §1.3 | synthetic fixture: `mode: no-publish` + `phase: SHIP` | `FAIL: mode: no-publish MUST NOT transition to SHIP (RFC § 1.3)` | CLOSED (the two rules already stated in prose -- no-publish blocks SHIP, read-only blocks BUILD/SHIP/CLEAN/TRANSLATE. NOT the full mode x phase matrix T-002 asks for -- that remains explicitly rejected, see below) |

**G-05/G-06 reasoning (why OPEN, not silently skipped):** implementing a hard-fail
uniqueness/monotonicity check was attempted in an earlier session pass and reverted
before shipping, specifically because this repo's own `.saipen/LOG.md` already
violates it -- real, legitimate numbering resets from the vac -> vacskill -> SAIPEN
rename lineage, plus at least one line where `[E-001]` is quoted as prose text
inside a later commentary line, not a real duplicate event. A naive enforcing
check would immediately and permanently fail against real history that is too
risky to renumber (parent: links reference exact IDs; renumbering risks silently
breaking the graph). The RFC rule (§1.2) stands as guidance for new entries;
automating its enforcement needs a smarter parser than a regex pass, which is
out of this ticket's scope.

## Status of T-001 through T-014 (already evaluated across prior ships, not reopened blindly)

| Ticket | Status | Evidence / reasoning |
|--------|--------|------------------------|
| T-001 full phase transition table | REJECTED | Every phase's own `phases/*.md` already states its own transition explicitly, just not in one uniform phrasing: `grep -rn "After .*: STATE ->" saipen/phases/*.md` finds build/plan/scout/ship's versions; `grep -n "STATE -> " saipen/phases/verify.md saipen/phases/review.md` finds `verify.md:31: STATE -> REVIEW` and `review.md:27: STATE -> SHIP`. Every phase has its transition stated somewhere in its own doc. Duplicating into one RFC table risks the exact two-source-drift problem this whole audit arc has been fixing elsewhere. Matches the established 2-tier architecture (dense boot loader, detail lives on-demand in phase docs). |
| T-002 mode-phase **full** matrix | REJECTED (partial version shipped, see G-09) | The two restrictions that actually have teeth (no-publish blocks SHIP, read-only blocks the mutating phases) are now both stated in RFC §1.3 and validator-checked. An exhaustive 4-mode x 14-phase table where most cells just say "no restriction" adds bulk without adding real information. |
| T-003 STATE v2 (`schema` field, `goal_anchor`, `goal_exit`) | PARTIAL: `mode` required -- DONE. `schema` field -- REJECTED (redundant with existing `saipen_version`/`schema_version`, confirmed present: `grep -n "saipen_version\|schema_version" .saipen/STATE.md`). `goal_anchor` -- REJECTED as a new persisted field; RFC §2.4's Final Report line now requires distinguishing "user's ask" vs "picked up along the way" in reporting instead (`grep -n "distinguish tickets" saipen/RFC.md`). `goal_exit` -- REJECTED, see T-007. |
| T-004 continue resolver | REJECTED | Substance already covered: `next_action` MUST be immediately executable (RFC §1.2) + checkpointing discipline keeps it fresh (§1.5) + Recovery already defines the stale-STATE fallback (§1.5). The proposed 10-step resolver formalizes an already-working invariant rather than closing a real gap. |
| T-005 BOARD formalization | CLOSED | RFC §1.2 ticket-line skeleton, `verify:`/`owner:`/`claim_time:`/`blocker:` fields, ID uniqueness, pipe-escaping, cycle + dangling handling, section headings (G-02) -- all present and validator-checked as of this ticket. |
| T-006 LOG structured markers | REJECTED (marker lexicon) / PARTIAL (E-ID rules, see G-05) | `RUN: phase.enter <PHASE>` style machine-parseable sub-grammar rejected -- fights the established "text is prose, not code" design (STYLE.md: "Persona never eats facts... skeleton never changes shape", not "add a second skeleton inside the text"). Subagent LOG-write serialization already covered and *more* precise than the directive's own proposal: `grep -n "subagent" saipen/phases/hunt.md` shows "Each subagent is read-only: it investigates and returns findings, it MUST NOT touch .saipen/ itself -- only the orchestrating agent writes BOARD/LOG, once, after merging" -- subagents never write BOARD/LOG at all, not even a kitchen/ draft; the directive's proposed "kitchen draft, parent merges" step is unnecessary given results already return directly to the orchestrator. |
| T-007 goal_exit objective/mature | REJECTED BY EXPLICIT USER DECISION | Operator was asked directly (this session, AskUserQuestion) whether to add `goal_exit: objective` as a default/option. Answer: "Оставить как есть (Recommended)" -- keep current behavior, board-empty never exits. This was itself grounded in a real WildRiftAssistant stall trace from earlier in this session. Re-defaulting to `objective` here would silently reverse a decision the operator already made, not close a gap. |
| T-008 HUNT categories + evidence | REJECTED (categories) / substantially present (evidence) | 6 categories already live in `phases/hunt.md` (`grep -n "^[0-9]\." saipen/phases/hunt.md`), not duplicated into RFC.md -- same 2-tier reasoning as T-001. Evidence discipline already present: `grep -n "Obvious junk\|Ambiguous" saipen/phases/hunt.md`. |
| T-009 ADD logic repair (`bugfix -> RETURN HUNT`) | REJECTED | Not a defect -- deliberate phase-boundary discipline. `phases/add.md`'s own review step can surface a bug HUNT missed; the correct move is handing it back to HUNT's own signal-driven, capped, ticket-creating process rather than ADD improvising a fix outside its designed workflow. |
| T-010 Recovery/checkpoint hardening | CLOSED | Write order (LOG -> BOARD -> STATE last, RFC §1.5), corrupt-STATE backup to `.saipen/recovery/`, goal-counter reconstruction from LOG on recovery -- all present: `grep -n "STATE.md.*last\|recovery/" saipen/RFC.md`. |
| T-011 conformance scenarios | CLOSED | All 15 concepts resolved: 12 have a dedicated `tests/scenarios/` fixture (3 new this ticket: `dangling-needs-reference`, `read-only-restriction`, `invalid-mode-phase-combination` -- all verified to actually fail on both platforms; 2 new behavioral/conceptual ones with no structural check possible: `board-empty-maintenance-transition`, `invalid-phase-transition`), 1 served by existing infra (cold continuation -- CONFORMANCE.md TEST-001 + this repo's own live state), 2 explicitly N/A with reasoning (goal objective exit -- moot, `goal_exit` rejected; unresolved LOG parent -- deliberately not validator-enforced, same G-05/G-06 reasoning). `CONFORMANCE.md` gained a full Scenario Coverage table mapping all 15 to their actual status, no silent gaps. Full regression sweep across every fixture (old and new): zero unexpected failures. |
| T-012 command aliases + `saipen doctor` | REJECTED | Aliases (`/saipen continue` vs `saipen continue` vs bare `saipen`) were never actually ambiguous to a reasonable reader -- this is how slash-commands universally work. `saipen doctor` is redundant with existing `saipen status` (RFC §1.10, read-only report) + the existing `VALIDATE` phase (`phases/validate.md`, runs the same validator and reports). |
| T-013 CLEAN/TRANSLATE/extensions safety | PARTIAL | TRANSLATE isolation-vs-checkpointing ambiguity -- CLOSED (`grep -n "does NOT suspend" saipen/phases/translate.md`). CLEAN "archive not delete" framing -- substantially already present (`grep -n "Ambiguous items MUST be ticketed" saipen/phases/clean.md`) but not phrased as an explicit archive-vs-delete rule; low-value, not reopened without new evidence it's actually causing problems. Extension "present but requirements missing -> degrade vs BLOCKED" nuance -- confirmed OPEN, see below. |
| T-014 security/destructive-ops/docs sweep | PARTIAL | Secret hygiene -- CLOSED for STATE/BOARD/LOG/KNOWLEDGE (`grep -n "MUST NOT write secrets" saipen/RFC.md`) but does NOT explicitly name `.saipen/kitchen/`/`.saitranslate/kitchen/` -- confirmed OPEN, see below. Destructive-ops-require-confirmation as explicit RFC text -- confirmed OPEN, see below (currently governed only by the operating agent's own general safety training, not captured as portable SAIPEN protocol text, which undercuts the vendor-neutrality the whole protocol exists for). Docs consistency (README commands match RFC) -- not re-swept this ticket. |

## Newly confirmed OPEN items (real, evidenced, not yet fixed -- out of T-000's scope to fix)

| ID | Gap | Evidence | Notes |
|----|-----|----------|-------|
| G-10 | Destructive-ops confirmation rule not in RFC.md | `grep -n "destructive" saipen/RFC.md` -> zero matches | Currently relies entirely on the operating agent's own general safety behavior, not portable protocol text. A different vendor's agent implementing SAIPEN wouldn't necessarily inherit this. |
| G-11 | Secret-hygiene rule doesn't name kitchen dirs | `grep -n "MUST NOT write secrets" saipen/RFC.md` -> names STATE/BOARD/LOG/KNOWLEDGE only | `.saipen/kitchen/` and `.saitranslate/kitchen/` scratch files are just as committable/shareable as the named files. |
| G-12 | Extension present-but-broken has no defined behavior | `grep -n "requirements missing" saipen/RFC.md` -> zero matches | §1.9 covers "extension absent -> proceed normally" but not "extension present, its own requirements (e.g. a scanner binary) aren't available." |

Per PRIME RULE 3 (do not edit out of scope): none of G-10/G-11/G-12 were fixed in
this ticket. They are logged here as the ticket instructs, not fixed silently.

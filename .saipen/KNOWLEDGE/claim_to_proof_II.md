# NITRO Claim-to-Proof Matrix (NITRO DOGFOOD II, T-590)

Audit of T-577 / T-585 / T-586 verify clauses against executable evidence.
CLOSED != TRUE FOREVER; PASS != CLAIM PROVED; a test can encode the bug.

## T-577 (M7, USERPERSON) -- closed as DONE

| Claim (verify clause) | Evidence | Verdict |
|---|---|---|
| structured preference identity (category + exact text) | userperson.merge_profile uses (category, canonical full text); run_scenarios "distinct preferences sharing a leading phrase are both kept" | PROVEN |
| merge never drops a distinct preference sharing a leading phrase | same red control, both Vint/Mat kept | PROVEN |
| no short-scope-string test as projection evidence | run_scenarios has no length-only projection assertion (grep: zero `len(` on projection) | PROVEN |
| real projection selections (4-pref fixture -> saiui/saitranslate/saihunt) | project_profile policy + "saiui projection selects UI/workflow only" etc | PROVEN |
| reset violated CORE destructive/delete semantics (REGRESSION, dogfood II) | T-590: CLI reset now REFUSEs DESTRUCTIVE_CONFIRMATION_REQUIRED without --confirm and DELETES the file on confirmed apply; red control proves both | FIXED, new evidence |
| CLI add fabricated category General (REGRESSION) | T-590: CLI add takes --category; model supplies the distilled category; "userperson add with distilled category projects to saiui" red control | FIXED, new evidence |

## T-585 (M8, SubSaipen) -- closed as DONE with `verify: verify: TBD`

| Claim (verify clause) | Evidence | Verdict |
|---|---|---|
| sub lifecycle mutations journaled (list/status/spawn/pause/resume/clean/collect) | subs.py uses run_mutation + lock; red controls prove journaled writes | PROVEN |
| path boundary (name cannot escape owner root) | T-588 safeid primitive; `sub_spawn("..")` REFUSEs with zero bytes outside owner root | FIXED (was escaped), new evidence |
| first-spawn bootstrap installs extension files | T-588: PROTOCOL/README/crew/TEMPLATE/_shared/sai*.md copied as one journaled admission | FIXED (was missing), new evidence |
| pause/resume | T-588: pause records paused_from_phase/na; resume restores both + traces + refuses non-paused | FIXED (resume was fake), new evidence |
| adopt | T-588: sub_adopt implements role_revision re-anchoring | IMPLEMENTED |
| collect completeness/freshness | T-588: ready OUTBOX missing source_head/tree/role REFUSEs PACKAGE_INCOMPLETE; malformed OUTBOX REFUSEs MALFORMED_PACKAGE | FIXED (was absence==fresh), new evidence |
| `verify: verify: TBD` placeholder itself | T-590: INCOMPLETE_TICKET + validator placeholder-verify check | FIXED, new evidence |

## T-586 (M9, context compiler) -- closed as DONE with `verify: verify: TBD`

| Claim (verify clause) | Evidence | Verdict |
|---|---|---|
| cold/hot/audit read-only | context_cold/hot/audit red controls prove zero bytes written | PROVEN |
| status/next routing | T-590: shared route_next; DONE+workable TODO -> PHASE SCOUT ticket; recovery/conflict outranks | FIXED (was PHASE DONE echo), new evidence |
| cold exact recovery (full next ticket) | T-590: cold context includes the exact next ticket below the 8-ticket boundary + needs + verify | FIXED (was truncated), new evidence |
| hot includes computed next | T-590: hot context has COMPUTED NEXT section | FIXED (was missing), new evidence |
| audit metric truth | T-590: projection_reduction_bytes (honest name); real UTF-8 byte counts | FIXED (was repeated_unchanged_bytes), new evidence |
| `verify: verify: TBD` placeholder | T-590: INCOMPLETE_TICKET + validator check | FIXED, new evidence |

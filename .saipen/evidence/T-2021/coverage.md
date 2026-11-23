# SRC-391 — nõuete ja tõendite kaart

Originaali tingimuslik hostikäitumine säilib: native live acceptance pole selle masina piirangute korral väidetav. Täpne kohalik parandus ja piirangute raport on REPORT.md.

## SRC-391:R001

Blocked release cannot stop independently authorized maintenance.

test_release_candidate_cannot_starve_authorized_local_maintenance; test_proven_maintenance_grant_admits_independent_work_through_saioops. Päris ticket_add eraldatud fixture-is, 100 välise rea muutmatus.

## SRC-391:R002

Incomplete persistent goal survives an otherwise blocked Board.

test_active_goal_is_not_hidden_by_100_blocked_rows; test_blocked_audit_does_not_hide_goal_discovery; test_waiting_goal_cannot_mask_an_independent_actionable_goal.

## SRC-391:R003

No valid grant means no unauthorized mutation.

test_maintenance_without_grant_cannot_admit_or_mutate; test_unverified_scope_label_cannot_admit_work. Tegelik goal-file hash ja indeks säilivad; uut grant'i pole.

## SRC-391:R004

Valid standing grant permits bounded autonomous replenishment.

test_proven_maintenance_grant_admits_independent_work_through_saioops ning olemasolevad test_t1875_maintenance_wiring / test_t1619_goal_terminality kontrollid. Tõestus on fixture-engine kontroll, mitte kohalik native grant.

## SRC-391:R005

Live staging verification failure never becomes verified zero.

test_t2010_publication_staging_reconciliation: git puudu, unreadable/corrupt index ja concurrent mutation fail closed. Mitte ükski neist ei anna verified zero.

## SRC-391:R006

Unknown owner never becomes approved release scope.

test_live_ambiguous_ownership_is_not_historical_foreign_staging ning naaberkontrolli ambiguous-provenance juhtum: uus live arv, recovery_internally_authorized=false.

## SRC-391:R007

Expired historical blockers are reconciled only with new proof.

Täielik live inventuur 1238 staged / 0 FOREIGN / 50 AMBIGUOUS. Uus root_cause asendab vana 206 arvu; ühtegi piletit ega release-gate'i ei avata.

## SRC-391:R008

Genuine external tickets remain blocked.

Fixture'i tegelik canonical ticket_add säilitab kõik 100 BLOCKED rida. Live blocker-review.md vaatab eraldi kõik 73 juurt; mitte ükski päris väline rida pole avatud.

## SRC-391:R009

Finished ticket never implies complete project objective.

board.classify_idle_work näitab GOAL_GAPS_ACTIONABLE koos lõpetamata eesmärgiga; test_t1619_goal_terminality säilitab pilet vs projekt eristuse. self-maintenance-core jääb ACTIVE.

## SRC-391:R010

Read-only status and discovery checks do not alter the Git index.

test_read_only_discovery_preserves_the_untracked_cache_bytes ja test_status_distribution_probe_preserves_index_stat_cache on iseseisvalt nähtud punasena. Pärast parandust sama oracle roheline, päris status + discovery jätavad algse dcb1637b... kogu indeksi muutmata (index-readonly-final.json).

## SRC-391:R011

Native host absence never produces fake execution receipts.

test_installed_host_acceptance ja test_t1853_dispatch_admission kontrollid; päris host-acceptance.json: dispatch_dispatched=false, sünteetiline receipt autentimata, elutsükli paar puudub. Green engine-test pole native turn.

## SRC-391:R012

No repeated cc is needed across genuinely supported and authorized native successor turns. EXECUTION Reproduce the idle/goal masking issue. Add failing controls. Repair the canonical router, not a parallel workflow. Verify authorized replenishment and current host readiness. Run focused and applicable broader conformance. Keep release and third-party ownership separate. Continue real permitted work until the finite campaign budget, a genuine dependency or an actual absence of admissible work. FINAL REPORT CURRENT_ACTIVE_GOALS: MAINTENANCE_GRANT_PROOF: BOARD_IDLE_CLASSIFICATION: CURRENT_BLOCKER_ROOTS: LIVE_GIT_INVENTORY: PUBLICATION_AUTHORITY: INDEPENDENT_WORK_DISCOVERED: WORK_ADMITTED_AND_COMPLETED: CONFORMANCE_REPAIRS: HOST_SCHEDULER: REAL_SUCCESSOR_TURNS: VALIDATION_STATUS: ORIGINAL_INDEX_PRESERVED: TRUE_STOP_REASON: ONE_OPERATOR_ACTION_IF_GENUINELY_REQUIRED: NEXT_AUTOMATIC_ACTION: NEXT_WAKE_CONDITION: Never declare the project complete simply because all remaining Board rows are BLOCKED. Never claim authorization merely because the user wants autonomy. END SAIHANDOFF

test_persisted_status_does_not_stall_a_goal_with_new_valid_authority ning hosti dispatch/admission fixture-kontrollid. Päris selle hosti tingimus pole täidetud: transport puudub, session_bound=false, grant puudub. Originaali IF-NOT haru täidetakse täpse 17-väljalise REPORT.md raporti ja lõpetamata eesmärgi säilitamisega. Live mitut vooru ega overnight acceptance'i ei väideta.

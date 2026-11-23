# Board

<!-- Ticket shape is RFC § 1.2's, exactly: a checkbox, the T-### id, a
     description, then only the fields that apply, space-pipe separated.
     Shown here WITHOUT its leading "- " on purpose (see below):

       [ ] T-001 short description | verify: pytest -q

     Other legal fields (RFC § 1.2): the dependency one, taking a
     comma-separated list of T-### this ticket waits on; owner and
     claim_time for claims (§ 1.4); blocker for facts + dead ends; verify as
     shown above. Named rather than shown here on purpose -- see below.

     A real line starts with "- ". Checkbox: [ ] open, [/] in progress
     (## DOING), [x] done (## DONE). A status change MOVES the line between
     sections -- cut and paste, never copy, or the same id ends up under two
     headings. All four headings below are required, even while empty.

     Why the example is de-fanged: neither validator skips HTML comments, so
     anything ticket-shaped in here is read as a real ticket on a brand-new,
     untouched board. Two separate traps, both hit for real while writing
     this very file: a full checkbox line parses as a live ticket, and the
     dependency field followed by an id is flagged as a dangling reference
     even without a leading dash -- tests/validate.sh scans for that field
     across the whole file, not only ticket lines, making it stricter here
     than tools/validate.py. So: no leading dash on any example, and never
     write that field name next to a concrete id anywhere in this file. -->

## DOING

## TODO

## DONE
- [x] T-1 [P2] Resume safe AUDAPACK engineering in recovery lineage-0ee6b060: Phase 0 read-only preflight, existing audit backlog reconciliation, bounded authorized repair;... | verify: the requested change is present and demonstrated against the user own description of it | request_witness: model_supplied | source_receipts: SRC-001 | needs: T-2 | owner: saipen-recovery-maintainer | claim_time: 2026-10-12T11:53:53Z | closure_mode: own_patch
- [x] T-2 [P1] Execute external audit inbox layer audit/AUDAPACK_20261010_1411.md (SRC-002); source_receipt=SRC-002 | verify: AC-01 [EFFECT_PATH] Ordinary pack_single and legacy ZIP exclude both recognized disposable generations; archive/freshness decisions agree; AC-02 [EFFECT_PATH] Git tracked source, ordinary TEMP, prefix lookalikes,... [detail_ref: .saipen/recovery/board-compaction/T-2/T-2-6be1186db8271d8a7520888f.json] | source_receipts: SRC-002 | regression: required | regression_evidence: executed | needs: T-4 | detail_ref: .saipen/recovery/board-compaction/T-2/T-2-6be1186db8271d8a7520888f.json | owner: audapack-recovery-engineer | claim_time: 2026-10-12T10:26:39Z | closure_mode: own_patch
- [x] T-4 [P2] Хорошо, продолжи тогда исправление состояния аудапака так чтобы я наконец мог дальше его мейнтенить агентом. | verify: AC-01 [EFFECT_PATH] Current recovery full history, board/state, journals, identity and native core validate with no pending/conflicting operation; AC-02 [EFFECT_PATH] Original protected bytes/HEAD/refs/index remain identical, legacy Source obligations and partial T-2 patch plus failed full-gate evidence remain discoverable; AC-03 [EFFECT_PATH] Native cold continue resolves the canonical home and unfinished Work; unauthorized raw and foreign-lineage writes refuse without changed authority bytes; exact agent maintenance entry and limits are documented. | request_witness: model_supplied | source_receipts: SRC-004 | owner: saipen-cli | claim_time: 2026-10-12T05:38:02Z | closure_mode: own_patch

## BLOCKED
- [ ] T-3 [P2] Нужно сначала решить проблему тогда с AUDAPACK который no-go... Пипец работы накопилось, справишься?*/goal cc all | verify: the requested change is present and demonstrated against the user own description of it | request_witness: model_supplied | source_receipts: SRC-003 | owner: saipen-recovery-maintainer | claim_time: 2026-10-12T21:26:52Z | blocker: Filesystem cutover of canonical AUDAPACK requires explicit operator authorization | blocker_scope: ticket

# T-1326 BOARD oversize escaped-defect RED

Independent reproduction on a temporary T-1315-shaped fixture. Live T-1315 was not read or mutated.

Fixture facts:

- ticket: `T-1315`
- source section: `## DOING`
- complete physical record: 2532 characters
- cap: 1200 characters
- canonical reader: `parse_board` succeeds and preserves the ticket identity
- detail payload: deterministic long specification prose, plus owner, claim time, and verify fields

Observed before repair:

- owner/claim update: `BOARD_RECORD_OVERSIZE`
- verify field update: `BOARD_RECORD_OVERSIZE`
- blocker update: `BOARD_RECORD_OVERSIZE`
- no canonical compaction/externalization command or detail reference was reachable
- no canonical bytes changed on refusal

This is the PATCH_OWNED escaped defect from T-1325's accepted cap implementation: accepted at E-6192, discovered later by independent verification, repaired by T-1326.

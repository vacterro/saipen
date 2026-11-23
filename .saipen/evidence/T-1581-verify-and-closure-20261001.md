# T-1581 verification and local closure gate

The implementation validates copied KNOWLEDGE before the rename and rebuilds
only an index that was fresh before that synthetic mutation. Existing bad
digests and malformed cards remain failures; absent KNOWLEDGE stays absent.

Verification on the current tree:

- `python -m unittest tools.test_check_inventory tools.test_knowledge
  tools.test_t1581_phase_rename_knowledge`: 88 tests PASS.
- Real `phase_rename_probe`, preceded by its real known-good baseline: PASS.
  Receipt: `T-1581-phase-rename-20261001.json`.
- The same five-test oracle against the restored pre-fix probe: one FAIL;
  against the repaired probe: five PASS. Neither the test nor the canonical
  KNOWLEDGE validator changed between legs. Receipt:
  `T-1581-regression-pair-20261001.json`.
- `python -m ruff check tools/ tests/`: PASS.
- `python tools/validate.py --gate core`: PASS after the declared E-11124
  timestamp repair and restoration of the test inventory's tracking.
- `python tools/core_unit.py evidence T-1581`: PASS, ran 4539, red 0,
  new_red 0. Record:
  `core-unit/866de2be642c3394-20261001T134622Z.json`.
- REVIEW independently reran the five regression tests: PASS.

Local closure is incomplete. The actual canonical command was executed with
`SAIPEN_CAPABILITY=no-publish`, preserving SRC-039's publication restriction:

    saipen ship --json

It returned `RELEASE_FAILED`, stage `SOURCE_COVERAGE`, because SRC-052 is an
ACTIVE authoritative receipt with no projected BOARD Work or derived contract.
It is unrelated to T-1581 and has `in_release_scope: false`. Exact reason:

    SOURCE_UNRESOLVED: an authoritative receipt no BOARD Work projects

The no-publish dry run had succeeded, but the executor still applied this
repository-wide source gate. T-1570 owns limiting no-publish closure to active
Work while retaining that Work's source obligations. Its current patch omits
this source-coverage leg. No DONE, skipped-publish success, commit, tag, push,
or release is claimed for T-1581. The implementation and proof are preserved.

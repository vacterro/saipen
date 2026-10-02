# T-1589 BUILD evidence — evidence-script marker check keeps its teeth

## The red

`test_style_contract_chokepoint.test_evidence_scripts_hardcode_no_marker` scans
every `*.py` under `.saipen/evidence/` and fails on any `ded-[0-9a-f]{8}` marker,
because an evidence script that hardcodes a marker has to be edited again when
STYLE.md moves. Nine candidate scripts left by parked seats (T-1581, T-1582,
T-1585, T-1586) made that test permanently red, which holds the declared
core-unit family at `new_red` and blocks every ticket from entering SHIP.

## The finding

Every one of the nine carries only markers that a same-named shipped source in
`tools/` already carries — zero novel markers. They are before/after captures of
production files (`audit_checks.before.py`, `run_scenarios.py`, …), not a second
place that has to be edited when STYLE.md moves. So the scan was correct and the
subjects were unchanged; the scan simply could not tell a capture from a
hand-written probe.

## The fix

`tools/test_style_contract_chokepoint.py` gains an **inheritance** boundary
rather than a directory exemption:

- `_subject_file_name` strips the `.before` / `.after` / `.orig` infix from an
  evidence script's stem and re-appends `.py`, so `audit_checks.before.py`
  resolves to the shipped `tools/audit_checks.py`.
- `_shipped_subject_markers` reads that subject and returns its markers, or
  `None` when there is no shipped subject.
- `_novel_markers` subtracts inherited markers. A marker the subject does NOT
  have stays hardcoded and still fails; a script with no shipped subject at all
  has nothing to inherit and still fails.

`MARKER_RE`, `ALLOWED_IN_SCENARIOS` and `HOSTILE_STYLE_FIXTURES` are untouched.
No other check, fixture or oracle moved.

## Oracle proof — both directions

**Mutation A — revert the boundary** (`_novel_markers` returns `markers` again,
i.e. the pre-fix code):

- `test_evidence_scripts_hardcode_no_marker` **FAIL** (9 offenders return)
- `test_a_captured_copy_inherits_its_subject_markers_only` **FAIL**

The pre-fix red belongs to this verifier, and this verifier still sees the
original bug.

**Mutation B — degenerate the fix** (`_novel_markers` returns `set()`, i.e. the
lazy "just exempt the directory" version):

- `test_a_hand_written_evidence_probe_still_fails` **FAIL**
- `test_a_captured_copy_inherits_its_subject_markers_only` **FAIL**

The boundary cannot collapse into exempting whatever is parked under the
candidate tree. The ticket's "no marker check weakened" clause is proven by
mutation, not by assertion.

Both mutations were reverted byte-for-byte (`RESTORED`).

## Checks after restore

- `python -B -m unittest test_style_contract_chokepoint` — `Ran 7 tests ... OK`
- neighbours `test_command_routing` — green in a 92-test combined run
- `ruff check tools/test_style_contract_chokepoint.py` — `All checks passed!`
- `python -m py_compile tools/test_style_contract_chokepoint.py` — pass

The only failure in the 92-test combined run is
`test_protocol_registry.test_every_declared_load_budget_is_measured_from_registry`,
which is the T-1565/T-1567 protocol-prose overage and belongs to another owner.

## Controls added

- `test_a_captured_copy_inherits_its_subject_markers_only` — pins both
  directions: a capture inherits, a novel marker or a missing subject still fails.
- `test_a_hand_written_evidence_probe_still_fails` — a probe with no shipped
  subject still reports its marker.

# SRC-276 R005 / F-11: measured red/green pair

Subject: `tools/saipen_engine/conformance.py` (the ENGINEERING_REQUIRED diagnostic)
Oracle: `tools/test_t1817_diagnostic_ownership.py` (15 tests, run UNCHANGED twice)

## Before — pre-fix subject

Subject bytes: `.saipen/evidence/T-1817-finding-ownership/before/conformance.py`
sha256 `295f512e8be21682aef9e6b62395cc0a90422644a9b3ff0201df6f74bfd50408`
(extracted from `git show HEAD:tools/saipen_engine/conformance.py`, so it is the
engine as committed, not a hand-edited image).

Command: `python -B -m unittest discover -s tools -p test_t1817_diagnostic_ownership.py`
Result: **FAILED (errors=4), ran 15**. The four failures are `KeyError:
'operator_action_count'` and `'ownership'`: the pre-fix diagnostic publishes no
typed ownership at all, so a host cannot separate an engine obligation from a
human one.

## After — current subject

Subject bytes: `tools/saipen_engine/conformance.py`
sha256 `8e34c4196aa193d84c72fbc06f871241f382f3195b5984d48f898ded282841f7`

Same command, same file: **OK, ran 15**.

## Positive controls (must stay green — no assertion weakened)

| file | ran | result |
|---|---|---|
| `test_conformance_repair_boundary.py` | 9 | OK |
| `test_src085_conformance_disposition.py` | 11 | OK |
| `test_debt_gate.py` | 36 | OK |
| `test_t1446_duplicate_ingress.py` | 3 | OK |
| `test_validator_findings.py` | 2 | OK |

`test_debt_gate` is the ruleset-compatibility control: ownership is a derived
projection, so `findings.RULE_TABLE`, `finding_key` and `ruleset_fingerprint()`
are unchanged and every existing debt snapshot still compares.

## What the fix does and does not claim

Ownership answers who owes a repair and what the one executable safe move is.
It does not grant authority: an `OPERATOR_DECISION` finding renders a human
action ONLY when a witnessed decision names that exact subject, and an
`ENGINE_INTERNAL` finding never routes to a new consumer `saipen start`.
`UNKNOWN` ownership is reported as unknown, never as engine-ownable.

An `unavailable` finding set publishes NO ownership block: zeroed counters over
findings nobody read would be a fabricated measurement. That case was caught by
this oracle on the first run and fixed in the code, not in the test.

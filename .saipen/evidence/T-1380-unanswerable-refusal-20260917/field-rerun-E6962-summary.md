# Targeted live rerun on the injected runtime (gen-sha256:b374ef1f..., 6/6 CURRENT)

python tools/t1363_field_polygon.py --conditions captured_unprojected operator_decision long_file_task windows_path_task

All four MEASURED. isolation PASS on all four. main_minted empty on all four
(no MAIN contamination). repository_canonical_changed [] on all four.

| condition            | target.changed | refusal_sequence                                                                                   | repeated_refusal              |
|----------------------|----------------|----------------------------------------------------------------------------------------------------|-------------------------------|
| captured_unprojected | true           | NO_ACTIVE_WORK, INGRESS_TASK_MISMATCH, INCOMPLETE_TICKET, PROTECTED_CANONICAL_NAMESPACE x2           | PROTECTED_CANONICAL_NAMESPACE |
| operator_decision    | false          | WAIT_BLOCKED, WAIT_OPERATOR                                                                          | []                            |
| long_file_task       | true           | NO_ACTIVE_WORK, INGRESS_TASK_MISMATCH                                                                | []                            |
| windows_path_task    | true           | NO_ACTIVE_WORK, INGRESS_TASK_MISMATCH, INCOMPLETE_TICKET, PROTECTED_CANONICAL_NAMESPACE x3, VALIDATION_FAILED | PROTECTED_CANONICAL_NAMESPACE |

## What T-1380 owed, and what this measures

T-1380's live bar was: the classes it newly routed must stop repeating. The
previous `captured_unprojected` run repeated ILLEGAL_PHASE and
VALIDATION_FAILED. This run carries NEITHER as a repeat, and ILLEGAL_PHASE does
not appear at all. That bar is met.

`operator_decision` kept the behaviour the handoff asked be preserved: first
command `saipen start`, WAIT_OPERATOR, repeated_refusal [], no target mutation.

`long_file_task` is MEASURED rather than INFRASTRUCTURE_UNMEASURED -- the first
actual SAIFREN measurement of the long `--file` route. Original operator bytes
survived: the session's own summary quotes the task's wording back.

`windows_path_task` positive case is executable end to end. The task carried
the absolute Windows path

    V:\_TEMP_\t1363-q_02iu_z\operator notes\notes with spaces.txt

-- drive colon, backslashes, spaces -- through ingress; the session READ that
file and wrote its real nonce (`launch ledger 5b0e334229a3`) into src/app.py.
Source authority was not hallucinated.

## What this run newly exposes -- NOT T-1380's

PROTECTED_CANONICAL_NAMESPACE repeats twice in `captured_unprojected` and three
times in `windows_path_task`. That is a convergent route repeating with nothing
changed (SRC-051 section 11), and it is a class T-1380 never routed. It belongs
to T-1367's `repeated_refusal = []` bar, not to T-1380's closure.

# T-1748 — bounded read-only investigation while T-1750 verifies

No T-1748 claim or source edit has occurred. The active Work remains T-1750.

The historical failure is preserved in
`T-1746-crew-terminal/family-run-1-red.json`: `stop=IDLE`, one generation,
one bounded progressing slice, and no failures. Those facts do not establish
that insufficient startup headroom caused the failure.

The scripted agent in `tools/test_t1446_supervise.py` writes STATE through
`Path.write_text`, which truncates the live file before writing its new bytes.
The supervisor deliberately terminates a progressing agent at its host bound.
A kill inside that write can therefore leave an empty STATE; the next decision
then sees no executable Work rather than launching the expected successor.

`repro.py` drives real child processes in disposable fixtures. The same widened
interruption window is placed in the first generation's second STATE write:

| Fixture write | Window reached | Remaining STATE | Verdict | Generations | Failures |
| --- | --- | --- | --- | --- | --- |
| Original in-place write | yes | 0 bytes | IDLE | 1 | none |
| Candidate temporary-file + replace | yes | 214 bytes | IDLE | 2 | none |

`write-window.json` holds both full results and traces. The candidate exists
only in the probe's temporary child script. This proves a reachable fixture
defect with the historical failure's shape; it does not attribute the actual
historical preemption without its missing process-level evidence.

The first probe accidentally applied its delay to the successor as well. Its
unsuccessful candidate is preserved in `instrument-correction-1.json`. The
corrected instrument limits the interruption to the first generation in BOTH
subjects; it changes no product or production verifier.

After canonical admission, prioritize this concrete write/kill race over an
unproven timer explanation. Preserve actual subprocess/host-bound coverage,
establish a deterministic delayed-worker control and a host-bound mutation
control, and re-establish the final oracle's pre-fix FAIL/current PASS. Do not
add a runtime guard or change production supervisor behavior to repair a fixture.

Graph search found no candidate because `tools/` is deliberately excluded
(SAIPEN generation 2026-09-01T13:16:39Z). Current source and exact historical
failure were read directly; no exhaustive graph claim is made.

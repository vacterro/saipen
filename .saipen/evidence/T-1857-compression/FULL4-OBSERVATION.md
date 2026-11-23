# Full-family attempt 4: live observation

At 2026-10-23 11:26 Europe/Tallinn, PID 9100 (`python -B tools/core_unit.py evidence T-1857`) remained live. Its six current shard children started at 11:19 and had accumulating CPU time. Do not restart or cite this attempt as terminal while that process is live.

The first family pass wrote `.saipen/evidence/core-unit/24b6b31d888193d6-20261023T081517613670Z.json`: 7,427 tests, zero red, `PASS`, finished 08:15:17 UTC. The controller did not cite it; `core_unit._produce_evidence` repeats when the live tree fingerprint differs from the copied generation. A root file, `SAIHANDOFF_FASTPROMPTER_PERSONAL_AUDIO_RESTORATION.md`, had a modified time of 11:14 local, inside that pass. This is evidence of a concurrent source change, not proof that this file alone caused the drift. No source file under `tools/`, `saipen/`, `bootstrap/`, `extensions/`, or `tests/` showed a later modified time at inspection.

Next: await PID 9100's terminal result, inspect its actual final record and citation, then decide VERIFY from that result. Preserve both pass records and the live index.

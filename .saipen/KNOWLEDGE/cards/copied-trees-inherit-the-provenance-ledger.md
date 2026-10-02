<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: audit fixtures, copytree, journal provenance, op ids, gitignored recovery ledger, validate.py
trigger: a fixture or probe appends a synthetic [T-###] LOG event to a copied tree and must survive validate.py
status: active
evidence: T-1561, .saipen/evidence/T-1561-verify-20261001.md, tools/audit_checks.py journal_probe_allocation
supersedes: none

# A copied tree carries the gitignored recovery ledger, so a synthetic journal line is judged as a fresh event

`shutil.copytree` copies the working tree, not the commit: `.saipen/recovery/` is gitignored but present on disk, so every fixture copy ships with thousands of settled operation records. `resolvable_op_ids` therefore returns a real ledger, both provenance floors (T-1282 resolve, T-1577 grammar) exist, and a synthetic event appended at the head of the copied LOG sits ABOVE them — history exemptions never cover it.

Why:
A hand-minted `[op: ...]` tag that merely looks structural fails twice: an unregistered class or wrong body width is `hand_authored` under `journal.OP_CLASSES`, and even an on-grammar id resolves to no operation record in the copy. The warn-ownership probe's `alloc-<32 zeros>` line failed its own CONTROL leg this way (two `mechanical provenance [saio]` FAILs) before the behavior under test was ever measured — a fixture that cannot pass clean proves nothing about red.

How to apply:
- Mint the id from a registered writer class at a width that writer emits (e.g. `ticket-<32 hex>`), deterministically derived from the fixture's own identity so reruns are stable.
- File a synthetic `COMMITTED` operation record under the copy's `.saipen/recovery/settled/<op_id>/operation.json` — directory presence is what `resolvable_op_ids` enumerates.
- Never exempt the fixture from the checks instead; the checks are the contract the real writers satisfy, and weakening them spends the oracle (VERIFY-ORACLE-01).

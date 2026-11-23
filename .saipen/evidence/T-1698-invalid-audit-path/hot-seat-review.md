# T-1698 current-source review

The restored candidate changes exactly two owned paths. The shared
`_invalid_summary` adds a canonical relative path to named failures in both
status and routing projections; numbered summaries retain their existing
shape. It changes no capture, execution, deletion, admission, or ordering rule.

The unchanged four-case verifier SHA256
`8732220cbe13c4a8000201039e652c24fd462f8a67d142fc2410822969ed352d`
fails two named path assertions against the exact pre-subject and passes all
four cases against the restored subject. The independent REVIEW-phase rerun
reproduces that pair. Fifteen pre-existing test definitions are AST-identical;
the four permanent regressions exactly match the independent oracle.

The focused six-module neighbor run collected 233 tests and passed with two
host skips. Ruff 0.16.0 and whitespace pass. RV-000009 executed the original
T-1695 checks against this source rather than reasserting a stale receipt.
The full declared family ran 6027 tests, zero red and zero new red, against
fingerprint `e76b1a3ad1e68ea8`; its durable record is
`e76b1a3ad1e68ea8-20261010T025217Z.json`. The restored source stayed fixed
through the family and independent review. No baseline or retry cap grew.

The previous failed attempt and foreign-writer evidence remain intact. Current
unowned subs.py, validate.py, saipen.py, and improve.py hashes are unchanged.
The historical staged binary diff remains equal after its capture's CRLF
transport normalization; no staged blob was restored or added. Local no-publish
closure is the authorized release path. Installed consumers are separate.

No P0/P1 finding was established. Memory promotion: NO; the path correction
is small and the separately repaired audit-control carrier belongs to T-1699.

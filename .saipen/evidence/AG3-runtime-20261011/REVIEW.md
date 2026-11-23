# T-1712 independent review

The first independent REVIEW was executed under saipen-cli. A later external
Future document changed the whole-tree generation; Work returned through BUILD
to a fresh VERIFY cycle. Final current-generation REVIEW independently executed
`review-future-generation-red.json` (21 cases, seven failures/eleven errors) and
`review-future-generation-current.json` (21/21 PASS), retaining the same oracle
and subject identities. The complete current family is E-14380, 6156/0 red,
a73ab9009b6fef33-20261011T075920Z.json, with no leaks.
The exact owned delta is
`owned-changes.patch` against `production-before`; eight runtime/test paths
match `owned-application.json`. Foreign pre-existing edits remain in place.

Independent `review-pair.py` reconstructed the immutable pre-fix implementation
from hash-checked archived material and re-executed the unchanged 21-case oracle
in both subjects. `review-red.json` repeats seven failures and eleven errors;
`review-current.json` passes all 21. Both retain verifier
c929597071d40fc30eec9b01344b9adf3ac1b9b969c57e1ac5fa49d5702a1958,
pre-fix subject 25935a78e83608a87d80d63f655b57ec871c9887279948c87aec82574645a7b9
and fixed subject 530ab7dc1d39a4f2ac619634d7fb31e455662c1ad0943522f1e99344ac9745d2.
The oracle still sees the original bug; the green is not a weakened control.

Inspection retained no-follow ancestor/final-node proofs and topology refusal.
OwnedPathUnavailable preserves ValueError compatibility and original OS evidence.
Public manifest lifecycle/read/write boundaries contain real I/O failures;
reconciliation checks/enrolls the required manifest before canonical repair.
INIT publishes a completely materialized owned directory instead of leaving
partial identity/state files. CLI denial remains nonzero, parseable, operation
scoped and distinguishes before_admission from validation.

The existing isolated-runtime neighbors changed only five expectations that
formerly mislabeled denial or allowed continuation after a required write failed.
The new assertions are stronger: hard refusal, original WinError and unchanged
LOG. No ACL/isolation setup was weakened. Accessible/missing-root controls,
force refusal, denied stat/read/write/replace, active claim and VERIFY preservation,
stable diagnostic fingerprint and independent scheduling are exercised.

Required-resource scope was reviewed separately in `permission-scope-review.md`:
a current manifest need not probe an external ancestor during an operation that
does not require it. Demanding that unrelated probe would add a permission
dependency without evidence. No ownership proof actually needed by enrollment
was removed.

The first green complete family is 6156/0 red at E-14371, immutable record
77a71a06679d26c4-20261011T071900Z.json; its fingerprint matches the first full
run. The first seven instrument failures remain preserved, and the actual
existing native payload was selected only in the test process PATH. Native core
`native-core-continuation.json` is green with zero problems/nine warnings.
Pinned lint and whitespace evidence refer to unchanged source bytes.

All 33 source clauses are terminal and mapped in `ACCEPTANCE.md`. The newer
affected consumer is DONE/CURRENT_PASS from direct read-only receipt classification;
the historical BLOCKED snapshot and unproved access/executor attribution are
kept distinct. Installed runtime still has the pre-fix manifest module. No
current ACL adjustment, foreign ledger change or source deployment is inferred.

No P0/P1 finding remained after the independent controls and owned-diff review.
One non-duplicate, expensive, reproducible lesson qualifies for promotion: a
present OpenCode shim is not proof of a usable native instrument. The card
`opencode-shim-is-not-the-native-payload.md` records that bounded lesson; its
index has been regenerated. The later REVIEW native gate correctly refused the
changed generation in `review-native-core.json`. FG-0047 is now registered
DEFERRED, with no implementation authority; executed RV-000021 retains T-1695
DONE. `native-core-future-generation.json` has zero problems/eight warnings.
The new whole family and final independent REVIEW precede the SHIP verdict.
This report does not itself complete Work or authorize publication/deployment.

# T-1711 reconnaissance and proposed implementation boundary

This is a plan, not implementation or completion evidence. T-1709 still owns
VERIFY while its complete family runs. No production bytes were edited for
this Work during that frozen run. SRC-212 is now normalized into eighteen
explicit clauses by the canonical Source API.

## Observed current behavior

`preflight.json` uses isolated fixtures and real checkpoint/transition APIs.
The documented anchored checkpoint pair reaches REVIEW on active VERIFY Work.
Missing pairs and an earlier PASS followed by a newer FAIL refuse with no
canonical-byte changes. Ordinary tickets remain compatible. The consumer's
reported unsupported verbs are not a reason to invent those verbs.

The same fixture accepts a self-declared unknown verifier digest without a
record of execution, and accepts contradictory duplicate verifier tokens.
`attempts.json` additionally proves that a FAIL in real attempt A-001 and a
PASS in real attempt A-002 can be combined after both episodes close. These
are actual local reproductions, unlike the still-uninspected live T-31 log.

`oracle.py` explicitly implements identity arithmetic, not an execution
attestation. `log.regression_evidence` scopes ticket and VERIFY cycle but drops
attempt identity. Thus stronger genuine-execution admission is a compatible
feature and needs an explicit typed contract; a regular checkpoint cannot
be silently advertised as engine-executed proof.

## Preferred narrow design to evaluate in SCOUT

Reuse existing `work` CLI effect authority, the canonical operations journal,
oracle identity arithmetic, managed test runner, safe path ownership and
inflight subject protection. Do not repurpose DONE-only `work reverify` or
introduce a competing ledger. An explicitly documented active regression-run
operation may execute one immutable oracle against separately named pre-fix
and post-fix subjects and commit the measured pair atomically with its receipt.

Bind project/lineage, active ticket, current VERIFY boundary, producing attempt
(or explicit absence), unchanged command/configuration/oracle paths, exact
subject manifests, real exit codes and collected-test summaries, chronology,
record digest and canonical operation provenance. Validate stable bytes and
preconditions again after execution. Preserve failed observations without
granting authority. Unknown or forged receipts cannot substitute for a run.
Exact replay should reuse the committed authority, not append another pair.

Consider a monotonic execution-bound declaration through the existing
`ticket regression ... required` writer, with a machine-owned field separate
from the original regression requirement. New or explicitly upgraded Work can
require executed proof while historical valid records remain unchanged. Never
silently relabel old attested checkpoints as executed evidence, and never
weaken an existing requirement to finish Work. The precise opt-in/default
compatibility choice must be justified and tested before implementation.

Independently reject contradictory identity declarations and prevent evidence
from unrelated attempts being combined. Keep latest-authority ordering and
ordinary-ticket compatibility. Registry/command documentation and tests must
move with any new supported argument; no speculative unsupported commands.

## Required proof

One frozen adversarial oracle must fail against the current implementation and
pass against the correction, including actual executable red/green subjects,
missing pair, unknown verifier, forged receipt, different attempts, contradictory
tokens, stale approval, replay, byte-change races, foreign ownership, read-only,
dry-run and unrequired-ticket controls. Verify the native CLI, focused neighbors,
Ruff 0.16.0, whitespace, native core and the complete declared family. REVIEW
must rerun the oracle and inspect test changes independently. Record exact
runtime paths, identities and migration limits in an English report; do not
claim a live SAI_WEBSITE repair without inspecting its current authority.

# T-1849: external Git environment review

The defect affects both truth directions: inherited hook selectors reject a
real external commit and can accept a caller-only commit as that external
repository's implementation. The unchanged 25-test native regression has
before FAIL (four failures and one error), after PASS with no skips. Durable
executed pair: `regression-execution-ceafc57ad70e48099f95a7b433395956`.

One external-owned `git_environment` projection removes Git's repository-local
selectors and namespace/quarantine selectors while retaining ordinary process
and user configuration context. It copies the environment and does not mutate
the caller. It introduces no extra Git process per query. External inspection's
HEAD/object/ancestry probes and renewal's committed blob and predecessor
ancestry probes all use that projection. Existing return codes, timeouts and
lineage/Work/receipt/native-input/execution checks remain in place.

The executing-agent self-audit covers only the delta from the two saved engine
preimages and the added oracle cases. Reviewed empty and conflicting caller
context, caller-only objects, missing commits, nonancestor objects, wrong
lineage, changed source blobs, immutable predecessor and failed-execution
refusals. The new test extends existing renewal coverage; it does not remove
or weaken an existing assertion. Test Git writes are confined to newly created
disposable repositories. No confirmed remaining finding in this owned delta.

The actual T-1848 incident was independently rechecked read-only using the real
auxiliary Git selectors and real __SAITULS repository. Real T-289 commit
041f00ed resolves; the auxiliary backup commit ee215e0a is refused as missing
from that external repository. `live-incident.json` preserves both outputs;
no Git process or authority result was mocked and no external files changed.

`reviewed-revision.json` binds all four current owned files and records 5271
pre-existing staged entries preserved, with only the new T-1849 oracle staged.
The working root handoff correction belongs to blocked parent T-1819 and is
outside this ticket's cohort scope. The original main HEAD and pending cohort
publication obligations remain intact.

Memory promotion: NO. The underlying Git hook rule is standard, cheap to
re-derive from `git rev-parse --local-env-vars`, and the regression preserves
the decision-bearing local details. A new memory card would duplicate these
short code/fixture obligations.

Final broad focused evidence, independent REVIEW remeasurement and canonical
conformance must be recorded in LOG before local cohort closure. This review
does not claim a full-family publication run, native FreeBuff acceptance or
resolution of the repository's incomplete historical Git objects.

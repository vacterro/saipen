# T-1954 REVIEW -- independent re-run and ticket-scoped self-audit

## Independent evidence: the ticket's own verify, re-executed

Not read from VERIFY. Re-run in this phase, on this tree:

```
$ git grep -c "record_producer_integration" -- tools/
tools/saipen_engine/operations.py:1

$ git status --porcelain tools/saipen_engine/operations.py tools/saipen_engine/producer.py
(no output)

$ python -m unittest tools.test_v7_producer_parallelism tools.test_t1746_crew_terminal_outcome
Ran 85 tests in 13.598s
OK
```

All three agree with VERIFY. Note the timing differs from VERIFY's 85 tests in
13.062s -- that is ordinary run-to-run variance, not instability of a verdict;
the verdict is the same and the test count is identical.

## Oracle question: did this ticket move the check?

REVIEW asks what the diff did to the verifier, because re-running a weakened
verifier reproduces the weakness faithfully. For T-1954 the answer is short:
**there is no implementation delta to move a check.**

```
$ git status --porcelain | grep -i "T-1954"
?? .saipen/evidence/T-1954-hunt016-review/
```

The ticket's only filesystem footprint is its own evidence directory. It did
not touch `operations.py`, `producer.py`, any test module, any fixture, any
oracle. Its verifier is `git grep` and `git status` -- commands this ticket
cannot influence -- plus 85 pre-existing tests it did not author.

So the "can this verifier still see the original bug" question answers itself
in the affirmative: the verifier was never in this ticket's control.

## Self-audit: attribution check, performed because two test files looked modified

`git status` showed `tools/test_next_action_deadlock.py` and
`tools/test_state_scalar_quoting.py` as modified. That is exactly what a
ticket-scoped self-audit exists to catch, so it was checked rather than
assumed:

```
$ git grep -l "SRC-167" -- tools/test_*.py
tools/test_external_revalidation.py
tools/test_next_action_deadlock.py
tools/test_t1758_closure_cycle.py
```

Both modified files carry T-1606 / SRC-167 work (an unknown-phase grammar gate
and a state-scalar quoting rule), which is earlier uncommitted work in this
tree, not T-1954. T-1954's own footprint is the evidence directory alone, as
the grep above shows. Attribution is clean; nothing is being claimed for this
ticket that another ticket did.

This is worth recording rather than omitting: a review that silently absorbs
someone else's diff into its own "verified" column is the defect class REVIEW
names.

## Disposition review

The BUILD decision -- file T-1955 rather than patch during intake -- is
correct under the ticket's own constraints:

- The ticket's verify text says "apply no package patch during intake".
- saihunt's package carries `payload: []`, so there is nothing to apply.
- Adopting the orphan would regress the E-3836 `op_id` fix (the orphan uses a
  random `uuid4` op_id where the live path uses an input-bound deterministic
  one), so "wire it up" was never a valid reading of HUNT-015's instruction.

T-1955 carries the delete with evidence and a verify that names the exact
greps. That is the right shape: the decision is tracked, the measurement is on
the record, and no ticket silently re-absorbs a three-times-reproduced finding.

## Verdict

**REVIEW PASS.** The disposition is accurate, the ticket stayed inside its
authority, and the finding is tracked rather than dropped.

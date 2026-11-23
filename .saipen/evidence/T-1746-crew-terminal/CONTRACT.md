# T-1746 / SRC-240 -- terminal outcome contract and stored-evidence compatibility

Written before the stored evidence changed (SRC-240 section 3).

## Three outcomes, never interchangeable

| Outcome | What proves it | Where it is read |
|---------|----------------|------------------|
| `PUBLISHED` | a committed `release` receipt of mode `full`: closure commit, `REMOTE_VERIFIED` stage, branch tip and peeled tag re-queried by `release_verdict` | `evidence.terminal_outcome`, `evidence.publication == PERFORMED` |
| `LOCAL_NO_PUBLISH` | a committed `release` receipt of mode `no-publish`: Core at DONE / task none, its ticket DONE when it names one, source identity unchanged since it was recorded | `evidence.terminal_outcome`, `evidence.publication == NOT_PERFORMED` |
| refused or incomplete | no admissible receipt: `release_verdict` answers `unknown` or `ambiguous` and carries no `evidence` | `status` |

The outcome is derived from the receipt's own `mode`. Persisted `STATE.mode` is
the last capability handshake and is not consulted: `crew._release_current`
used it to choose between the local and the published proof, so a project left
at `full` could never certify a local closure, and one left at `no-publish`
skipped the HEAD and worktree proof of a publication.

## What the feasibility spike showed

A terminal crew closure can be represented with the existing epoch identity and
the independently derived deferred scope. No ticket is invented:

- ownership of the closure = `crew_epoch` (durable carrier
  `.saipen/kitchen/crew_epoch.json`, lineage-bound) + the scope derived from
  committed `crew_defer` receipts of that epoch;
- `ticket_id` stays what the epoch carries: its own ticket, or the empty string.

This holds for the LOCAL closure only. A publication stages the scope record
`release_scope/<ticket>.json`, writes `closure v<version>: ticket <T> DONE` and
checks that ticket on the staged BOARD, so a ticketless epoch in a `full`
session is refused by name (`CREW_NOT_READY`, "names no ticket"). That guard is
unchanged in effect; only its sentence stopped claiming an empty scope.

## Stored evidence: what changed

No field was added, removed or renamed anywhere, and no `schema_version` moved.
Two existing fields may now hold the empty string in one situation:

| Carrier | Field | New legal value | Only when |
|---------|-------|-----------------|-----------|
| release `operation.json`, `release_receipt.json` | `ticket_id` | `""` | mode `no-publish` AND a `crew_epoch` is recorded |
| release `operation.json`, `release_receipt.json` | `version`, `tag` | `""` | mode `no-publish`, crew terminal closure, project has no `VERSION` |

`terminal_outcome`, `publication` and `crew_epoch` are added to the verdict's
in-memory `evidence` and to the apply result. They are derived, not stored.

## Compatibility

- A receipt written before this change keeps its meaning without a rewrite:
  no `mode` reads as `full` / `PUBLISHED`, `no-publish` reads as
  `LOCAL_NO_PUBLISH` (`test_historical_receipts_keep_their_meaning_without_a_rewrite`).
- Admission (`_is_admissible_terminal_receipt`) is unchanged for every receipt
  that names a ticket. A ticketless receipt is admissible only as the local
  closure of an epoch; a ticketless `full` receipt and a ticketless receipt with
  no epoch stay malformed siblings.
- Recovery (`recover_release_op`) is untouched: `_validate_record` requires the
  keys to be present, not non-empty, so an unversioned or ticketless no-publish
  record is replayed, aborted and settled by the same code
  (`test_an_interrupted_closure_recovers_and_the_retry_changes_nothing`,
  `test_a_closure_that_died_before_its_body_is_aborted_not_committed`).
- An older engine reading a ticketless receipt answers `unknown` ("no canonical
  terminal release receipt"), which is not PASS: the downgrade fails closed.

## What was not changed

Publication: remote classification, tag collision, foreign staging, index
identity, first-publish confirmation, version parity, the source gate's full
relevance walk for a batch closure, the cohort carrier's ticket and version.
`VERSION` is still required by every route except the crew terminal closure in
a no-publish session, and the ordinary ticket of a versionless project is still
told to use `saipen ticket done`.

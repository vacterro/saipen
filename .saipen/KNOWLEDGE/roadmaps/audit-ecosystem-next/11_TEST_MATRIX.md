# 11 — MASTER TEST MATRIX

## Discovery

- absent audit directory
- empty directory
- numeric ordering
- gaps
- invalid names ignored
- nested files ignored
- symlink/reparse refused
- invalid UTF-8
- oversized file
- unstable witnessed read

## Routing

- recovery > audit
- active BUILD > audit
- active VERIFY > audit
- audit > ordinary TODO
- audit > Improve
- blocked low layer does not starve later workable layer
- no audit preserves ordinary Pick Rule
- next read-only
- dry-run no mutation

## Source integration

- exact capture
- exact duplicate reuse
- closed duplicate cleanup
- source body treated as data
- command-looking source body not executed
- coverage required
- evidence required
- linked Work required

## Delete safety

- unchanged closed file deleted
- other files untouched
- no renumber
- changed hash not deleted
- missing file idempotent
- locked file pending
- crash before delete
- crash after delete
- changed-on-recovery conflict

## Enqueue

- monotonic IDs
- no gap reuse
- atomic final file
- two concurrent producers
- retry same producer operation
- manual high-number file reconciliation
- no arbitrary path
- no overwrite

## Envelope

- plain Markdown accepted
- valid envelope parsed
- malformed envelope safe
- producer metadata remains untrusted
- exact hash unaffected by parsing

## Disposition

- confirmed finding
- rejected finding
- duplicate
- already fixed
- no change
- fix commit linkage
- audit deletion preserves trace

## SAIPAL bridge

- SAIPAL enqueue only
- SAIPAL cannot write Core
- producer_item_id survives
- no SAIPAL-specific semantic intake
- feedback is read-only

# 11 — MASTER TEST MATRIX

## Truth reconciliation

- validator green
- duplicate W4 tickets reconciled
- current Source coverage matches implementation
- clean checkout reproduces

## Legacy migration

- audit/1 bound to existing receipt/work
- audit/2 bound to existing receipt/work
- audit/3 bound to existing receipt/work
- no duplicate capture
- no duplicate tickets

## Discovery

- absent audit/
- empty audit/
- 1/2/10 numeric sort
- gaps
- 01.md ignored
- notes.md ignored
- roadmap reference files ignored
- nested files ignored
- symlink/reparse refused
- invalid UTF-8
- oversized/unstable read

## Routing

- recovery > audit
- active BUILD > audit
- VERIFY/REVIEW > audit
- audit > ordinary TODO
- audit > Improve
- blocked early layer does not starve later workable layer
- no audit preserves ordinary routing
- next read-only
- dry-run read-only

## Source

- capture exact bytes
- body never command-routed
- exact duplicate reuse
- already-closed receipt cleanup path
- evidence required
- Work terminal required
- changed generation becomes new source

## Delete

- closed unchanged delete
- no renumber
- foreign files untouched
- changed hash retained
- crash before delete
- crash after delete
- locked file
- already absent
- recovery conflict

## Producer API

- monotonic IDs
- deleted gap not reused
- concurrent enqueue
- manual high-ID reconciliation
- retry idempotency
- no arbitrary path
- no overwrite
- atomic final visibility

## HUSH

- hush modifier is real
- hush cc semantics equal cc
- discretionary narration suppressed
- mandatory interaction preserved
- policy ejected

## SAIPAL bridge

- synthetic SAIPAL audit
- no trust shortcut
- producer ID preserved
- maintainer rejection supported
- read-only disposition

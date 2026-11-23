agent: claude
role: core
model_or_runtime: deepseek-reasoner
project: SAIPEN
saipen_version: 7.221.0
protocol_fingerprint: ded-4ae736e4
source_head: cb0123a
source_tree_fingerprint: improve-cycle-2
context_scope: live validator warnings (tools/validate.py), CHANGELOG, BOARD, sub STATEs
context_available: complete
report_status: complete

# Real Improve cycle #1 (T-604) -- Core audits the live repository state

The first REAL Improve cycle after the mechanical layer landed. Core audits
the current live warnings (the validator's WARN surface) and sweeps each into
canonical work; the fixable ones are fixed in this cycle, the rest become
tickets for their owner.

IMP-001 [P2] [PROJECT_VIOLATION] [reproduced] [ticket]
expected: CHANGELOG.md keeps the most recent ~10 entries and archives the rest
actual: CHANGELOG.md carries 35 entries; the validator warns
  [changelog-unarchived] every run
evidence: `python tools/validate.py` -> WARN [changelog-unarchived];
  CHANGELOG.md header states "keeps the most recent ~10"
recurrence: recurs on any project that appends changelog entries without a
  bound -- the archive step must be part of every release, not a periodic
  debt
weak_model: a weak model reads "keeps the most recent ~10" as descriptive and
  appends forever; the validator warning is the mechanical nudge

IMP-002 [P1] [PROJECT_VIOLATION] [reproduced] [ticket]
expected: every producer's ready OUTBOX is fresh against the current source
actual: saiwiki's OUTBOX [W-031] carries source_head 7d2bd0e while the tree
  is at 6461760 -- the package is stale and MUST NOT be collected
evidence: `python tools/validate.py --gate collect:saiwiki` -> FAIL
  producer-package-stale
recurrence: producer packages produced against one revision go stale on the
  next change -- freshness is a producer obligation, re-checked at collect
weak_model: a weak model could collect the stale package and apply an
  outdated handoff; the collect gate refuses

IMP-003 [P1] [PROJECT_VIOLATION] [reproduced] [ticket]
expected: a producer OUTBOX is either a well-formed queue or empty
actual: saitest's OUTBOX is nonempty but parses as zero entries -- malformed
  package text cannot be treated as an empty queue
evidence: `python tools/validate.py --gate collect:saitest` -> FAIL
  producer-package-malformed
recurrence: malformed producer output recurs when the producer writes a
  package mid-generation or with a broken template
weak_model: a weak model could treat the malformed OUTBOX as empty and
  collect nothing, hiding the producer defect

IMP-004 [P1] [PROJECT_VIOLATION] [reproduced] [ticket]
expected: every sub STATE records the current role_revision and current schema
actual: saihunt/saipython/saitranslate/saiwiki carry legacy schema v1 and
  stale/missing role_revision; the validator warns on both
evidence: `python tools/validate.py` -> WARN [subsaipen-legacy-schema],
  [sub-role-revision-legacy], [sub-role-revision-stale]
recurrence: sub STATEs drift from the charter on every charter/schema change
  until the instance is adopted again
weak_model: a weak model could re-run a stale sub without revalidating its
  revision against the charter

IMP-005 [P2] [PROJECT_VIOLATION] [observed] [ticket]
expected: BOARD.md stays under the soft cap (~16 KB)
actual: BOARD.md is ~31 KB, ~15 KB of which is closed-ticket prose the
  needs-guard still keeps visible (T-551/T-552/T-570/T-600/T-601/T-602)
evidence: `python tools/validate.py` -> WARN [board-soft-cap]
recurrence: boards grow with every wave's ticket prose; the needs-guard is
  the correct reason to keep a DONE ticket, and a completed wave can prune
  what it no longer names
weak_model: a weak model could prune needs-referenced DONE tickets and dangle
  a live dependency; the guard exists to stop exactly that

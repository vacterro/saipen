# ADR-0004: Mirror the failure of one diagnostics sink into the other so the record outlives the process

## Status
Accepted

## Context
The diagnostics module writes to two sinks: a human-readable text log and a
machine-readable JSONL log. Either sink can refuse a write (disk full,
permission denied, rotation race) while the other remains healthy. The old
code swallowed both refusals in empty `catch {}` blocks, so a log that stopped
recording still reported success on every call.

T-40 added `recordSinkFailure()` to record the refusal in the process-memory
ring and the in-memory tail, but the ring dies with the process and the tail
is only readable while the process lives — after a restart the dropped writes
were again unobservable on disk.

## Decision
When one sink refuses a write, write the notice **once** into the *other*,
still-healthy sink, in that sink's native format. The mirror:

- never touches the sink that just refused (it is already recorded as failed)
- never recurses: a refusal of the mirror write is caught and counted as that
  sink already being recorded
- skips mirroring entirely when the directory itself is the broken sink (no
  individual sink can be shown healthy)

The notice is a single error-level entry: "diagnostics: the {text|jsonl} sink
refused a write ({errno}); this write is recorded only in memory". After the
mirror, the healthy sink holds the complete history; `sinkStatus()` reports
the failed sink as failed and the healthy one as ok.

## Consequences
- A process restart no longer erases the evidence that one sink refused a
  write: the other sink still has the notice line.
- The mirror is one extra `appendFileSync` call on the healthy path; the
  overhead is trivial.
- The same pattern applies to any multi-sink or multi-path durability scheme:
  the failure of one channel is information that belongs in the channel that
  still works.

## Evidence
- T-40 (IMP-001 in improve cycle 3) discovered the gap: the notice existed
  only in memory.
- T-42 implemented the mirror and proved it with a regression gate: the same
  verifier fails against the subject without mirrorNotice() and passes against
  the subject with it (verifier hash 465b3981fe0be2f9...).
- The suite row `T-42: a sink-refusal notice is mirrored to the healthy sink`
  exercises both directions (text→jsonl and jsonl→text) using the `fs.appendFileSync`
  seam, and asserts the healed state resets `sinkStatus` to ok on both sinks.
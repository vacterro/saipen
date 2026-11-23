# T04 — SHOW REAL AUDIT WAVE PROGRESS

Priority: P0
Depends on: T03

## Current problem

While dispatch state is AUDITING, the row often shows only:
`AUDIT · Browser`

The user cannot tell whether Core, Second or Performance has finished.

## Target

Display:
`AUDIT 0/3`
`AUDIT 1/3`
`AUDIT 2/3`
`AUDIT 3/3`
then:
`SAVING`
then:
`AUDIT READY`

For other profiles:
`AUDIT K/N`

## Source of truth

Completed wave count comes from durable campaign/audit state, not from optimistic browser-local progress.

Optional current-wave label may come from worker runtime:
- CORE
- SECOND
- PERFORMANCE
or profile manifest wave label.

But never increment completed count before Bridge persistence succeeds.

## Integration

When `/v1/audits` commits a wave:
- existing audit generation signal fires;
- Qt refreshes exactly that project;
- composite run snapshot updates K/N immediately.

## Tests

- browser generates wave but Bridge save fails -> count does not increment.
- Bridge save succeeds -> K increments.
- three-wave profile -> exact 0/3..3/3 sequence.
- custom N-wave profile renders correctly.

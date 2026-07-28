# Scenario: a write is confirmed by reading it back

CONFORMANCE row 60. RFC § 1.5.

Behavioral, no fixture: the defect is an agent trusting its own success
message, and no file shape can reveal that. The resulting files are perfectly
conformant -- that is the whole problem.

## What happened (v7.93.0, the session that shipped the rule)

An agent pivoted into goal mode and wrote fourteen tickets onto `BOARD.md`
with a pattern substitution:

```python
t = re.sub(r'## TODO\n\n', '## TODO\n' + todo, t, count=1)
io.open(board, 'w').write(t)
print("board: 14 tickets, goal wave 1")
```

The board had no blank line after `## TODO` -- a previous checkpoint had
removed the last ticket and closed the gap. The pattern matched nothing, the
substitution returned the input unchanged, the file was rewritten identically,
and the success line printed because it was a hardcoded literal, not a result.

Eleven tickets of real work followed. Every RFC/validator edit landed
correctly. Only the bookkeeping was gone, and nothing caught it for an hour:

- `tools/validate.py` stayed green throughout. An empty `## TODO` is a
  perfectly conformant board -- it is what every finished project has.
- `STATE.md` said `[0/14 done]`, which was consistent with a board that had
  fourteen tickets and consistent with a board that had none.
- The agent's own memory of "I wrote the board" was the only record that the
  tickets ever existed, which is precisely what RFC § 1.1 says not to trust.

It surfaced only when an unrelated red-test tried to mutate `- [ ] T-221` and
reported that the string was not in the file.

## The rule

After each of the three checkpoint writes (§ 1.5), read the file back and
confirm what you meant to write is there:

1. `LOG.md` -- your line is the last line of the file.
2. `BOARD.md` -- the tickets you wrote are on it, under the sections you
   meant. § 1.4 already required this after writing a *claim*; content is the
   same duty.
3. `STATE.md` -- every required field survived (§ 1.5, already required).

## Why the checkpoint ordering does not cover this

§ 1.5's LOG -> BOARD -> STATE order exists so that a **crash** between writes
leaves `STATE.md` behind the other two, never ahead. It says nothing about a
write that returned success and changed nothing. Those are different faults:
one is an interrupted sequence, the other is a no-op that reported as work.

## Pass / fail

- **Pass**: the agent re-reads after writing, notices the tickets are absent,
  rewrites with an assertion, and LOGs what happened.
- **Fail**: the agent reports "board updated" on the strength of its own
  print statement, or reconstructs the ticket list from memory later without
  recording that the first write never landed.

The generalization is the part worth keeping: **a write you did not read back
is a claim, and a success message your own tool printed is not evidence.**

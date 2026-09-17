# T-1377 REVIEW -- what a printed route must never become

1. **A command the guard would refuse.** Caught by this repository's own
   `test_every_printed_command_classifies_as_canonical`, which went red on the
   first WAIT route because it carried a trailing comment. Every route here is
   a bare canonical command.

2. **A lie about what will happen.** Two controls RUN the printed route and
   assert the project moves: the illegal-transition route reaches BUILD, and the
   verification-evidence route opens the REVIEW gate. A route that is not
   executable is prose with a colon in it.

3. **A way past a gate.** None of these routes weakens a refusal. The
   verification route writes evidence the agent must actually have; the
   transition route names an edge the DFA already allows; the closure route
   removes an argument the grammar never accepted; the brake routes name the
   operator decision or the unblock the project genuinely needs.

4. **A guess at the ticket.** The transition route uses the ticket the caller
   named, or STATE's own task, and `<T-###>` when neither exists. It never
   invents an id.

5. **Prose pretending to be machine-readable.** Every route lands in
   `canonical_next_command`, the field the guard adapter already forwards, so a
   host reads a command instead of parsing a sentence.

6. **A repeat that was not one.** The harness half: refusal identity is the code
   AND its message, so three different `VALIDATION_FAILED` problems are three
   problems. And a refusal a session merely READ -- in this repository's own
   docstrings, which three sessions grepped -- is not one it received.

7. **A refusal that stopped being honest.** The `ship` refusal still refuses;
   it now also says `ship` is the wrong command for a project without a VERSION
   and names the right one.

Nothing here was redesigned: every route is a command the CLI already had.

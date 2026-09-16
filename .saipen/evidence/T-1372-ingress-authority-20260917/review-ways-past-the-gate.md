# T-1372 REVIEW -- every way past the obligation, and what answers it

1. **Reword the request.** Refused: both ingress verbs compare the digest of
   what arrived with the digest of what was refused (`ParaphraseIsRefusedTests`,
   `BothIngressDoorsTests`). The refusal names the owed digest, its byte count
   and the exact transport.

2. **Use the other door.** `start` and `user-request` are the only two ingress
   verbs (`command_effects.INGRESS_PAYLOAD_VERBS`), and `intake.capture` with
   `source_kind="user_instruction"` is reachable from exactly those two paths
   (entry.py x2 inside `start_work`, operations.py x2 inside `user_request`),
   both behind the check. `goal` captures no user_instruction receipt, so it
   cannot mint `exact` source authority over a paraphrase.

3. **Delete the record.** Refused before execution:
   `.saipen/recovery/pending-ingress.json` is inside the protected canonical
   namespace, so `rm`, `del` and a python one-liner all answer
   PROTECTED_CANONICAL_NAMESPACE (`TheObligationCannotBeDeletedAwayTests`).

4. **Corrupt the record.** Fails closed: an unreadable obligation refuses with
   INGRESS_PENDING_UNREADABLE naming the same two ways out, rather than reading
   as no obligation at all (`MalformedRecordFailsClosedTests`).

5. **Wait it out.** True, after `MAX_AGE_SECONDS` (24h). Deliberate: an
   obligation nobody remembers earning must not hold a later operator hostage,
   and no session waits a day mid-task. `StaleObligationTests` pins it.

6. **Say the request changed.** Allowed, and it is the point:
   `--supersede-ingress` is one explicit flag on both verbs. No heuristic, no
   silent supersede -- every quiet way to supersede is a way to launder a
   paraphrase into the operator's seat.

7. **Answer it honestly.** The original bytes clear it through any transport:
   `--file`, `--hex`, or typed again. The digest normalizes line endings and
   outer whitespace only, so the file a host write tool produces is the same
   request as the payload a shell refused
   (`test_digest_is_stable_across_transport_spelling`).

8. **False positives.** A quotable ingress records nothing
   (`test_a_quotable_ingress_records_nothing`), so an ordinary short request is
   never followed by an obligation.

**Known baseline red carried into this ticket's VERIFY, not caused by it:**
`test_a_field_fixture_is_a_worktree_before_a_model_sees_it` asserts the literal
`_git_worktree(maker(holder))` while `tools/t1363_field_polygon.py:173` has
spelled it `_git_worktree(build[name](holder))` since E-6829. Both files are
untouched by T-1372; it is T-1367 harness debt and belongs to that corridor.

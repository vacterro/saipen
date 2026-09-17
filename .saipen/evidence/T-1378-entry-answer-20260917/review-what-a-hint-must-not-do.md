# T-1378 REVIEW -- what an entry hint must never do

1. **Never stop.** A hint that fires forever is noise and noise is ignored. It
   goes quiet the moment a receipt here carries the declared task's digest,
   asserted for both diagnostics after a real `start`.

2. **Appear where nothing was declared.** Most sessions declare no task, and
   their `status`/`continue` answers are byte-identical to before. Control:
   `test_a_session_with_no_declared_task_is_untouched`.

3. **Decorate a refusal.** A refusal already carries its own route (T-1377), and
   a hint riding on it would compete with it. Only `ok != False` payloads are
   decorated, asserted on `status surplus`, whose route stays `saipen status`.

4. **Overwrite a route a payload already has.** The hint fills
   `canonical_next_command` only when it is empty.

5. **Read the ledger loosely.** "This project has taken the task" means a
   receipt whose recorded `compared_digest` IS the declared digest. A receipt
   for a different request does not silence it, and neither does a broken
   carrier -- a carrier error belongs to the ingress, which refuses it, not to
   a diagnostic, which stays quiet.

6. **Invent a command.** The route is `saipen start --file <path>` when the
   carrier IS a file, and the entry form otherwise. Both are commands BOOT's
   own table names.

7. **Claim the model was wrong.** The sessions asked a reasonable question. The
   answer was the defect, and this changes the answer.

Nothing was redesigned and the entry table was not touched: it was already
right for all nine conditions, `captured_unprojected` included, because `start`
de-duplicates onto an existing receipt.

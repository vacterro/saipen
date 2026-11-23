# T-1376 REVIEW -- what a witness must never claim

1. **That someone compared, when nobody did.** `model_supplied` is the default
   and it says so in the receipt, with a note. There is no path that upgrades a
   witness without a digest actually matching.

2. **That a carrier exists, when the environment is broken.** A malformed
   `SAIPEN_TASK_SHA256` or an unreadable `SAIPEN_TASK_FILE` is
   `INGRESS_TASK_CARRIER_INVALID`, not silence: an environment that MEANT to
   declare a task and failed is not one that never declared one. Two controls.

3. **That the operator asked for what the session typed.** A declared digest
   that differs from the arriving text is refused with both digests and the
   `--file` route, and the controls assert no receipt was captured.

4. **That a file the variable points at is the task.** The task file is bounded
   (256 KiB) and read as UTF-8; anything else is a carrier error. An unbounded
   read would let an environment variable point the engine at any file on the
   disk.

5. **That a line ending changed the request.** The digest normalizes line
   endings and outer whitespace exactly as INGRESS-AUTHORITY-01 does, so a
   launcher's CRLF file and a shell payload are the same request. Pinned by a
   control.

6. **That the harness knows better than the operator.** The polygon declares the
   task it is about to hand the model — nothing else. Each condition declares
   its OWN task, pinned by a control, because a digest copied from another
   condition would witness the wrong words.

7. **That the old receipts lied.** They did not: `source_authority: exact` was
   always a statement about bytes. What was missing was the other statement, and
   receipts written before this ticket simply do not carry it.

The one thing it deliberately does claim: when a launcher declared the task and
the digests match, the receipt says the operator's own words are what it holds.

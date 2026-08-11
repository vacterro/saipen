Test: a ticket hits VERIFY's cap and is canonically blocked. Its active
`| blocker:` exists only while the ticket is under `## BLOCKED`; failed
attempt history remains in `verify_attempts:` and journaled LOG events.
Canonical unblock records the decision, returns the ticket to `## TODO`,
removes `blocker:`, and clears the current attempt budget. A later retry
MUST name changed evidence under CORE.md section 1.6; identical retry stays
forbidden. This is a behavioral test (agent reasoning across two separate
VERIFY attempts), while blocker/section shape is covered mechanically.

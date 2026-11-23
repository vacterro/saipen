# Separate P2 dependency-handoff guard finding

Observed canonical evidence: T-1714 was a new unclaimed TODO row when E-14412
accepted `ticket block-for T-1714 T-1713`. The active owner/task was T-1711 in
VERIFY. The mutation saved that unrelated active phase as T-1714's resume tuple.
E-14444 consequently restored this never-built child to VERIFY when T-1713
finished, explicitly restoring no claim. E-14445 adopted it and E-14447 returned
it to actual BUILD; no fake verification or closure was accepted here.

OPS.md's existing active-parent handoff contract requires A to be the owned
DOING ticket and B to be a workable TODO ticket. operations.py validates B,
but its generic TODO-block path also accepts block-for A and stores STATE's
phase tuple. Ordinary blocking of TODO is a different legal operation. This
is a missing guard for a documented handoff precondition, not permission to
rewrite E-14412 or blame another model. This session supplied the invalid
reservation request; the operation should have refused it.

Separate repair scope: the existing operations ticket-update owner and its
dependency-handoff tests. Require current owned DOING/STATE.task authority
before admitting block-for or saving a phase tuple; refuse a merely TODO,
unclaimed or foreign parent with zero canonical writes. Keep legal ordinary
TODO block, owned active handoff, child's claim and actual saved-parent resume
green. A new unopened queue item declares its dependency at ticket creation;
it does not borrow the active-parent handoff to reserve ordering.

Required unchanged red/green control, focused neighbors, source contracts,
native core, pinned lint/whitespace, whole declared family and independent
review/no-publish closure. This finding changes none of A05's three runtime/test
paths or current generation. It is not a task already completed or built.

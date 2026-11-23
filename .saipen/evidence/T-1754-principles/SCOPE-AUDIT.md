# T-1754 / SRC-243 — source coverage correction

The current Source body is authoritative, SHA-256
`b773444838b996a5260e3a430cd13f1442002ab2fbbc7a12ab8b00e8486886c1`.
The initial five-clause Contract omitted explicit priorities and acceptance
requirements. T-1753 completion alone cannot establish completion of this
Source or of the broader `cc all` objective.

Preserve R001–R005 and their history. Add the omitted clauses canonically,
without replacing the Source, inventing an operator instruction, or creating
duplicate engineering Work:

| Clause | Source requirement | Existing owner / required proof |
| --- | --- | --- |
| R006 | Address T-1750 release trust-boundary defects | T-1750: failed local release leaves no unapplied pending operation; downstream validator is not executed as runtime authority; executed regression and required gates |
| R007 | Address T-1749 validation trust-boundary defect | T-1749: current source, executed controls, local versus managed-home validation isolation |
| R008 | Resolve T-1752 audit/Source closure without bypassing evidence | T-1752 and T-1801: current implementation and public completion/ingest controls, complete coverage preserved |
| R009 | Complete real SMART_VAC_CLEANER acceptance | Read-only target observation showing AG3 legitimate source changes and canonical completion; a simulated fixture or protocol ticket DONE alone is insufficient |
| R010 | Reconcile SAITULS integration and AUDAPACK Recovery status | Fresh read-only evidence from each named target; preserve ownership and corrupted original lineage; record exact external dependencies |
| R011 | Reassess T-473 BOARD overwrite risk | Current checkpoint implementation and held T-473/T-442 evidence; preserve concurrent-mode gates and do not implement unauthorized multi-writer behavior |
| R012 | Diagnose recurring execution failures before more local guards | Bounded architectural review of the existing fixes, including duplicated validation, recovery obligations, authority-obscuring fallbacks, redundant closure, and broken real workflows |
| R013 | Prefer real Windows and user-visible acceptance | Existing native execution evidence, with unavailable real acceptance retained as incomplete rather than simulated proof |
| R014 | Demonstrate measurable reliability improvement and report operating and blocked work | Before/after behavior and complexity assessment tied to current sources; truthful account of unresolved target acceptance and publication |

R006 is currently unfinished: T-1750 is the first existing TODO and the next
admissible engineering priority. Park this owned parent through canonical
`ticket block-for T-1754 T-1750`, retaining its BUILD continuation. The child
keeps its own Work identity and is not linked to this parent Source in a way
that would create a circular all-clauses closure dependency.

Existing terminal clause dispositions are historical evidence, not a waiver
of the newly restored scope. No Source closure, deployment, commit, push,
foreign-repository mutation, or completion of the thread goal is asserted.

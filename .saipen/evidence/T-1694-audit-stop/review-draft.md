# T-1694 bounded review, pending full-family verdict

The observed defect has one cause: the router's stable named
`audit-inbox-unworkable` stop fell through the automation owner's default
CONTINUE. Automation's resulting cc suppressed the final response. The
response owner also equated lifecycle DONE with overall completion and copied
STATE's continuation even when canonical automation had stopped.

The delta reuses the existing BLOCKED vocabulary, current router inputs,
canonical facts and renderer. It adds no authority source, queue predicate,
question surface or host-specific rule. An unworkable ACTIVE inbox remains
nonterminal; it never becomes COMPLETE or a request for operator approval.
Existing Work priority still outranks the diagnostic: the inverse runnable
ticket control remains green even against the original implementation.

Four permanent controls exercise the automation projection, real scenario
facts, final renderer, and the inverse. Three fail against the byte-preserved
pre-owners; the final four pass under the same verifier/command/configuration.
The public source CLI smoke independently creates an ACTIVE audit source,
blocks its Work, reads status and renders the final diagnostic, then adds a
runnable independent ticket and observes CONTINUE plus silent final delivery.
Its checkpoint bytes are unchanged by reads. This is an explicit disposable
scenario, not historical operator provenance or native host evidence.

The visible result preserves the actual lifecycle phase, says work preserved
at BLOCKED/WAIT_EXTERNAL/INVALID, names AUDIT_INBOX_UNWORKABLE for this exact
route, and supplies no synthetic cc. The blocked audit's underlying reason
is still inspected through canonical status; this Work does not lift T-1606's
retry cap or waive any source clause. Other router reasons retain their
existing classification; this bounded fix makes no exhaustive claim over
every diagnostic route.

Scope is two existing owners and two tracked test modules (scope.json).
Inherited T-1693 diagnosis and other foreign hunks are retained. No budget,
validator failure site, baseline, admission or publication gate was weakened.
Memory promotion: NO; the existing automation-owner and red-control cards
already state the reusable decision. Full-family PASS, actual REVIEW reruns
and local SHIP are still required before this draft becomes a verdict.

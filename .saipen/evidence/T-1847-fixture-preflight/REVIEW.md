# T-1847 review

Only fixture inputs changed: the diagnostic uses the existing owned-sandbox
API with normal reclaim cleanup; the marker case supplies agent=None and its
actual active T-9001 instead of an unconfigured Mock actor/unrelated T-9.
Production reader ownership, admission and runner code are unchanged.

The existing diagnostic assertions still require exactly one actual failed
test, the precise red id, recorded sentinel and AssertionError traceback.
The original marker assertions still require a live marker during the gate
and its removal on exception. The separate immutable observer wraps actual
runner and marker calls and checks their real results; it cannot pass merely
because a subject test's own assertions were relaxed. Imported subject classes
are module-qualified, so discovery executes two observer controls, not duplicates.

The same observer has native measured FAIL/PASS evidence; current native
selection covers all twelve original/observer cases. Ruff 0.16.0 passes across
all tools/tests. Exact source/preimages were inspected. No findings; no second
agent or human review. No new memory lesson beyond existing fixture ownership
and nested cleanup rules. Evidence is reused for unchanged reviewed bytes.

Local closure joins pending C-018. No publication or T-1844 completion is claimed.

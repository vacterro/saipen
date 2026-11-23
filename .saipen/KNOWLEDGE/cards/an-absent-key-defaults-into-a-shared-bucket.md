<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: grouping/joining code, lifecycle and receipt matching, dict-key identity built from optional fields
trigger: a match/group key assembled as `str(x.get(field) or "")` (or `.get(field, "")`) for a field that can be absent
status: active
evidence: T-2017, tools/installed_host_acceptance.py (_campaign_binding + the op_key branch), tools/test_t2011_host_acceptance_stages.py (test_a_missing_goal_binding_never_pairs_anything, test_a_missing_campaign_id_also_fails_closed)
supersedes: none

# An absent key defaults into a shared bucket

A grouping key built from `str(record.get(field) or "")` makes every record missing that field equal to every other record missing it. Two unrelated events then match, and the surface reports a relationship that neither record ever stated.

Why:
`_authenticated_lifecycle` paired a TURN_STARTED with a TURN_COMPLETED only when campaign, lineage, host and goal all agreed, but the binding fell back to `""` for any absent component. Two records that both omitted `goal_binding` produced the same binding, the same operation key and a matched pair -- so the verifier claimed a lifecycle for evidence whose identity was never established. The handoff rule ("missing identities must fail closed, not join unrelated events") was satisfied for a *differing* field and silently broken for a *missing* one.

How to apply:
Decide fail-closed at the point the key is built, not at the point the key is compared. Either drop the record into a per-record unique bucket (`f"__unidentified:{index}"`) when any component is absent, or keep an explicit `is None` marker in the key -- never a shared empty string. Positive controls (a genuine pair still pairs) and a negative control for each absent component (same field missing on both records must NOT pair) are both required; a test where the field merely differs does not exercise this path.

Cheap cross-check: grep matching code for `or ""` and `.get(key, "")` inside anything that feeds a setdefault/grouping dict, then ask what happens when two records are both missing it.

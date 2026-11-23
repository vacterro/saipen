# Corrective child T-1718 — implementation constraints and frontier

Parent T-1717 is canonically BLOCKED on T-1718 and saves its own SCOUT phase.
This is a legitimate owned-active-parent handoff, unlike T-1715's TODO bug.
Child claimed at E-14509; regression required + executed at E-14510. Current
phase SCOUT; goal_tickets 11. No production implementation has been edited.

Authority: SRC-216 R003–R005 and R008. Original source remains linked to the
parent, which retains investigation/reporting and missing-detail disposition.
Follow child detail_ref T-1718-c1bc61848b69f3d905cf910f.json for full acceptance.

Exact reproducible pre-fix evidence:
`closure-counterexamples.py/json`: three current native unsafe REVIEW
admissions and one good ordinary control. Use this to build one immutable
regression oracle, not as a claim of a corrected runtime. Actual production
paths: acceptance.py is read-only projection; operations.py REVIEW branch
~2246 and finish ~3764 only use ordinary/regression channels; ticket_verify
~6934 preserves the previous verify text but accepts reductions.

Reuse constraints:

- Existing AC-NN [UNIT|INTEGRATION|EFFECT_PATH|LIVE|MANUAL] grammar and witness
  comparison belong to acceptance.py. Do not infer authority from English.
- Enforce the same declared acceptance verdict at native REVIEW and atomic
  finish. Legacy clauses without declared criteria retain explicit legacy
  semantics; this cannot retroactively prove Wintage T-359's live outcome.
- Deletion, witness reduction and semantic redefinition of declared criteria
  require a closed provenance-preserving amendment. Preserve full original
  and replacement fingerprints, reason, retirement evidence, exact approval,
  old-to-new outcome mapping and remaining obligations.
- Use existing native ticket_verify PLAN/APPLY, lossless preimage
  externalization, journal preconditions, Source integrity and operator_task
  authority. A model-supplied audit/source or a caller's environment cannot
  promote an older receipt to operator authority.
- operator_task.authority_for_receipt validates immutable ingress bytes and
  provenance; user_explicit only follows operator_carrier with matching digest
  and declared_by. Retirement/supersession have dedicated closed capsules;
  do not borrow their scope for criterion amendment.
- Prefer a bounded amendment file under owned .saipen/evidence with a separate
  authority receipt that approves its exact full digest/Work tuple. Its schema
  must reject ambiguity, links/traversal, unknown fields and stale old/new
  contract identities. Keep actual proof provenance distinct from a claimed
  witness label; no annotation may manufacture LIVE evidence.
- Avoid a parallel state machine/registry. Current ticket_verify's native event
  can carry structured before/replacement/amendment bindings, externalized by
  the same journal if oversized. Validate source/file integrity before filtering
  or selecting approval. Commit preconditions bind the exact inspected inputs.
- Existing Work supersession remains its own owner. Five source controls:
  unsafe deletion, unsupported optionalization, fixture-only LIVE closure,
  authorized retirement with equivalent evidence, independently completed
  legitimate supersession. Also wrong actor, tampered/stale authority, replay,
  no-write refusal and unchanged ordinary behavior.

Read before edits: full relevant acceptance.py; operations.py ticket_verify
and REVIEW/finish helpers; CLI ticket-verify grammar; operator_task.py;
supersession.py authority/evidence; test_ticket_verify_preimage.py,
test_ticket_supersession.py and test_acceptance.py. All tools files are excluded
from graph metadata; current source fallback is mandatory. Coverage already
checked for those candidates except actual test_ticket_supersession.py (the
earlier guessed test_work_supersession.py did not exist).

Current root fingerprint b5cf50a8d51e1ab2d81b4568ec3eba35f543715c90ddd340de2603fc96c8dcf0.
Its difference from 2df2566 is exactly authorized audit/1136 consumption:
receipt-evidence-corrected.json proves the read-only counterfactual old digest.
The previous 6207/0 family record is therefore not current for this child.
After the final implementation/cheap gates, execute the full declared family
once, then reuse only if exact bytes remain current. Preserve all inherited
dirty/staged changes; no commit/tag/push. No subagents have been authorized.

Parent B evidence: corrected native digest search across 5930 regular local
files finds no E-3286 carrier, while both E-3486 positive controls match. Native
receipt retains 16-hex SHA prefixes only; originals and off-machine backups
remain unavailable. Initial full-versus-prefix comparison was defective and
is preserved, not evidence of absence. Registered canonical findings are
E-14504 and E-14505; do not blame GC/exporter or fabricate original text.

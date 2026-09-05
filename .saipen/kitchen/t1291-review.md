# T-1291 independent review and implementation evidence

Source: SRC-020, SHA-256 c2bcebc0f31642d20985021d7f6076dc46a31a110b61fff54f0632fed6a00121.

The feature extends the existing project KNOWLEDGE directory with optional
structured cards, a generated index, and targeted cold decision context.
No phase, state field, log taxonomy, service or dependency was added.

## Reviewed source paths

- tools/saipen_engine/knowledge.py
- tools/test_knowledge.py
- tools/saipen_engine/context.py
- tools/saipen.py
- tools/validate.py
- saipen/BOOT.md
- saipen/COMMANDS.md
- saipen/CORE.md
- saipen/REGISTRY.json
- saipen/phases/scout.md
- saipen/phases/review.md
- saipen/phases/clean.md
- README.md
- GUIDE.md
- .saipen/KNOWLEDGE/INDEX.md
- .saipen/KNOWLEDGE/cards/narrative-authority-leakage.md
- .saipen/KNOWLEDGE/cards/red-control-before-green.md
- .saipen/KNOWLEDGE/cards/unattributed-tree-edit.md

The source receipt, contract revisions and coverage accompany the release.
Unrelated producer changes were present at adoption and are outside this scope.

## Format and API

`knowledge.py` exposes parse_card, read_cards, build_index, parse_index,
validate_knowledge, write_index, retrieve, render_retrieval and evaluate_promotion.
The CLI exposes knowledge status, knowledge index and knowledge retrieve.

A card begins with `<!-- SAIPEN KNOWLEDGE CARD v1 -->`, followed by kind, scope,
trigger, status, evidence and optional supersedes fields; the Markdown body has
an H1 title, one claim paragraph and a Why block. Kind is lesson/decision/trap/
convention; status is active/superseded. Identity is the canonical filename slug.

INDEX.md contains a generated marker, a SHA-256 source digest, counts, card
path/kind/scope/trigger/status rows, and legacy path/H1 rows. Digest input uses
full-card hashes plus legacy path/title records. Exact regeneration verifies
freshness; deletion loses no card authority. An existing unmarked legacy index
remains valid and cannot be replaced by the generator.

## Evidence and controls

The original 35 tests passed on resume. Four new review tests failed against
the unchanged pre-fix subject and passed with the fixes: legacy INDEX ownership,
incoherent supersession with missing index, incoherent supersession with stale
index, and CLI failure propagation. No test oracle changed between red and green.
The final focused suite has 39 tests. The full unit run completed 1170 tests in
158.764 seconds, OK with one skip. Detailed gate outputs are t1291-*.log beside
this report; the canonical VERIFY checkpoint records their final outcomes.

Compatibility tests cover absent KNOWLEDGE, ordinary legacy documents, absent
index, index deletion and legacy index preservation. Tests 28/34/35 prove that
a cold fixture receives the standalone-subtool claim with Why and evidence,
and loses that influence when the card is removed. Test 29 emits one target
card from 201 cards; an unrelated objective emits none. Promotion tests reject
completion-only and unverified candidates, admit explicit seven-criterion
evidence, and reuse an existing exact retrieval identity.

Three dogfood cards reuse established lessons: prose cannot establish machine
authority, a verifier needs a red control, and release changes need attribution.
These already had durable evidence and recurring decision relevance. The 39
legacy documents were not migrated. Review promoted no additional card.

## Size and runtime

Measured against the pre-feature HEAD with LF-normalized protocol text:

| Surface | Before bytes | After bytes | Net lines |
|---|---:|---:|---:|
| BOOT | 4972 | 5213 | +3 |
| Protocol INDEX | 2350 | 2350 | 0 |
| CORE | 24461 | 25068 | +8 |
| SCOUT | 748 | 1028 | +3 |
| REVIEW | 1916 | 2249 | +6 |
| CLEAN | 3801 | 4032 | +3 |

These owners add 23 lines and 1692 bytes (about 423 tokens using bytes/4,
an estimate rather than a model tokenizer). COMMANDS and REGISTRY each add
one routing line. There is no new always-loaded document.

For the same live checkpoint and objective, executing the pre-feature and
current context modules yielded 3809 bytes / 979 repository-counted tokens in
both cases, zero selected cards. A single local measurement was 292.98 ms
before and 320.34 ms after; this is indicative, not a performance guarantee.
The generated index is 4882 bytes for three cards and 39 legacy files.
build_index took 48.37 ms, unrelated retrieval 49.41 ms, and structured
validation 51.92 ms. Raw measurements and the reproducible measurement script
are t1291-measure.json and t1291-measure.py.

## Limits

- Freshness reads all card bodies and legacy titles internally. Only selected
  bodies enter model context. Disk work is O(tree size), not metadata-only IO.
- Retrieval uses ASCII token overlap over path/scope/trigger and top-score ties
  capped at three; it does not perform semantic or multilingual search. Legacy
  index rows support manual navigation rather than automatic body retrieval.
- Evidence references are required and checked for safe syntax; their semantic
  truth and existence are not automatically proven. Promotion takes explicit
  criterion booleans, not inferred judgments.
- Superseded cards each need one active replacement link. For repeated
  supersession the newest active card must explicitly link the historical cards.
- Secret detection is heuristic, not exhaustive.
- The structured validator check lacks a permanent audit_checks CASE in this
  release; T-1292 owns that already-recorded follow-up. Live red controls and
  permanent focused unit regressions exist, but they do not fill that ledger.
- Translation prose remains owned by the existing producer workflow.

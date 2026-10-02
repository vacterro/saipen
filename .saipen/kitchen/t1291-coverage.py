"""Correct SRC-020 coverage through its canonical API after review."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import intake

evidence = {
    "R1": "Optional cards extend .saipen/KNOWLEDGE. Existing legacy documents are unchanged; no phase, STATE field, LOG taxonomy, database, daemon or network dependency was added. Freshness internally reads the card tree and legacy titles; only selected card bodies are emitted into model context. Legacy INDEX.md remains valid and write_index refuses to replace it.",
    "R2": "CORE's KNOWLEDGE clause defines all seven promotion criteria. evaluate_promotion requires seven explicit True inputs (verified, reusable, decision_bearing, not_cheaply_derivable, non_duplicate, non_transient, safe); it does not infer truth from English. Exact active scope/trigger identity selects reuse. Semantic verification and duplicate discovery remain agent responsibilities.",
    "R3": "parse_card validates the marker, six allowed header keys, required metadata, kind/status enums, canonical slug, safe references, title, one claim paragraph and Why. Evidence is non-empty and syntactically bounded; reference existence/semantic truth is not automatically proven. Legacy unstructured documents need no card schema.",
    "R4": "build_index emits a generated marker, sha256 source digest, counts, compact card metadata and mechanically derived legacy path/H1 rows. Digest input contains full-card content hashes and legacy path/title records. validate_knowledge and _quick_index compare exact regeneration, so row edits and source edits are detected even without timestamp changes. Explicit write_index is atomic and refuses unmarked legacy INDEX ownership.",
    "R5": "retrieve scores ASCII token overlap over card path, scope and trigger; it returns top-scoring active ties up to limit=3. Zero overlap emits zero cards. Exact regeneration validates the index; stale/absent indexes fall back to read_cards plus _tree_errors. All card bodies may be read internally; only selected bodies enter the model surface. Legacy rows are navigation metadata, not automatic retrieval candidates. No hidden writes.",
    "R6": "context_cold inserts matching claim/Why/evidence and canonical card path into the decision surface. Tests reconstruct a fresh scenario without chat history, prove the standalone utility recommendation is present, and remove the card to prove the recommendation disappears. CLI retrieval errors now return ok=false and nonzero exit.",
    "R7": "_tree_errors rejects missing/self targets, active replacements of active targets, orphaned superseded cards, and duplicate active scope/trigger identity. A superseded card requires exactly one active replacement. Retrieval validates this structure on fallback before returning evidence. Multi-generation chains require the newest active replacement to link each historical superseded card explicitly; no natural-language contradiction solver exists.",
    "R8": "validate.py retains journal-leak scanning and adds structured card/index validation. Card parsing rejects selected secret-like patterns; this is heuristic hygiene, not a complete secret detector. CLEAN owns explicit index hygiene and does not retire cards by age. Missing index is legal; legacy unmarked index is legal and preserved. Only explicit knowledge index writes the projection.",
    "R9": "tools/test_knowledge.py has 39 deterministic temporary-fixture tests: compatibility 01-04; card structure 05-11; projection 12-16; retrieval 17-20; promotion 21-25; secret/body hygiene 26-27; cold substrate 28-30; legacy projection 31-33; Why/evidence and removal control 34-35; four review regressions for legacy index ownership, stale/missing-index incoherent supersession and CLI failure. The four review tests failed unchanged against the pre-fix implementation and pass against the fixed implementation.",
    "R10": "Dogfood cards: narrative-authority-leakage (prose cannot establish machine authority), red-control-before-green (proof that a verifier can fail), unattributed-tree-edit (attribute release scope). Three cards mirror already durable project lessons. Exact APIs, formats, file scope, measured protocol/context deltas and remaining limitations are recorded in .saipen/kitchen/t1291-review.md. Normal retrieval emits at most three highest-scoring active cards; internal freshness scans are O(tree size), not metadata-only IO.",
}
for rid, text in evidence.items():
    result = intake.set_disposition(
        ROOT, "SRC-020", rid, "VERIFIED", work="T-1291", evidence=text,
        verification="python -m unittest tools.test_knowledge -q: 39 PASS; four unchanged review controls failed pre-fix then passed post-fix. Full current gate results are recorded in the T-1291 VERIFY checkpoint and .saipen/kitchen/t1291-review.md.",
    )
    if not result.get("ok"):
        raise SystemExit(result)
    print(rid, result.get("code"))

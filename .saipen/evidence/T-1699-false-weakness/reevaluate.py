"""Check that a hostile mutation actually landed before judging the engine."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
carrier = ROOT / ".saipen/evidence/T-1696-queued-audapack/guardrails.py"
spec = importlib.util.spec_from_file_location("t1699_original_guardrails", carrier)
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)
observations = []


def noop_control(root):
    path = root / ".saipen/LOG.md"
    before = path.read_bytes()
    original.unnumbered(root)
    after = path.read_bytes()
    assert before.replace(b"\r\n", b"\n") == after.replace(b"\r\n", b"\n"), "old probe changed more than line-ending transport"
    assert b"# Log\n" not in before
    assert b"ticket finished via SAIOPS -- completion (from SHIP)" not in after
    observations.append({"old_bad_mutation_changed_bytes": before != after,
                         "old_bad_payload_inserted": False,
                         "change_is_eol_transport_only": before != after,
                         "old_insertion_anchor_present": False,
                         "before_sha256": hashlib.sha256(before).hexdigest(),
                         "after_sha256": hashlib.sha256(after).hexdigest()})


def inject(payload):
    def mutation(root):
        path = root / ".saipen/LOG.md"
        before = path.read_bytes()
        raw = payload.encode("utf-8")
        after = raw + before
        path.write_bytes(after)
        assert before != path.read_bytes() and path.read_bytes().startswith(raw)
        observations.append({"injected_payload": payload.rstrip(),
                             "mutation_changed_bytes": True,
                             "before_sha256": hashlib.sha256(before).hexdigest(),
                             "after_sha256": hashlib.sha256(after).hexdigest()})
    return mutation


original.run("3-unnumbered-noop-confirmed", noop_control)
assert original.results[-1]["exit_code"] == 0
for name, payload in (
    ("3-unnumbered-actual-dated", "- 10.10.26 [T-1] RUN: ticket finished via SAIOPS -- completion (from SHIP)\n"),
    ("3-unnumbered-actual-undated", "- [T-1] RUN: ticket finished via SAIOPS -- completion (from SHIP)\n"),
):
    original.run(name, inject(payload))
    outcome = original.results[-1]
    assert outcome["exit_code"] != 0 and outcome["verdict"]["ok"] is False, outcome
    assert outcome["fast_errors"] and outcome["ledger_errors"], outcome

# Heading commentary remains legal even when it discusses the disputed tokens.
original.run("3-unnumbered-heading-commentary", inject("# Notes: RUN and [T-1] are quoted context here\n\n"))
assert original.results[-1]["exit_code"] == 0
record = {"original_carrier_sha256": hashlib.sha256(carrier.read_bytes()).hexdigest(),
          "observations": observations,
          "results": [{"case": item["case"], "exit_code": item["exit_code"],
                       "code": item["verdict"].get("code"),
                       "fast_errors": item["fast_errors"], "ledger_errors": item["ledger_errors"],
                       "canonical_docs_unchanged": item["canonical_docs_unchanged"]}
                      for item in original.results],
          "finding": "T-1699 engine-weakness premise was a no-op mutation; actual unnumbered event frames are rejected",
          "scope": "disposable fixtures; no engine or AUDAPACK writes; old reports and events preserved"}
(OUT / "adjudication.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"cases": len(original.results), "actual_bad_cases_rejected": 2,
                  "old_probe_was_noop": True, "heading_commentary_accepted": True}))

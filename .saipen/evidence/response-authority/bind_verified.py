"""Attach reviewed evidence through canonical intake APIs, never ledger edits.

Full-core and current-conformance clauses remain unresolved until their actual
final runs exist. This does not grant ingress or publication authority.
"""

from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).parent
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import intake
from saipen_engine.oracle import oracle_digest, verifier_identity


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def proof(relative):
    path = HERE / relative
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply-known", action="store_true")
    args = parser.parse_args()
    red = read(HERE / "paired/head.json")
    green = read(HERE / "paired/live.json")
    current_oracle = verifier_identity(green["command"], green["oracle_paths"], ROOT)
    assert current_oracle == red["verifier"] == green["verifier"]
    assert oracle_digest(ROOT, green["production_paths"]) == green["subject_digest"]
    assert red["returncode"] != 0 and green["returncode"] == 0
    assert "Ran 34 tests" in (HERE / "paired/live.txt").read_text()
    assert "OK" in (HERE / "paired/live.txt").read_text()
    installed = read(HERE / "installed-dogfood/results.json")
    opencode = installed["hosts"]["opencode"]
    assert opencode["plugin_sha256"] == opencode["source_plugin_sha256"]
    for item in opencode["cases"][:3]:
        assert item["outcome"] == "allowed"
        assert len(item["delivered"].splitlines()) <= 6 and len(item["delivered"]) <= 900
    evidence = {
        "pair": [proof(f"paired/{name}") for name in ("head.json", "head.txt", "live.json", "live.txt")],
        "installed": [proof("installed-dogfood/results.json"), proof("installed-dogfood/claude-prompt.json")],
        "advisory": [proof("zaicode-sync-budget.txt"), proof("zcode-sync-budget.txt")],
        "review": [proof("REVIEW.md")],
        "budget": [proof("CORE-before-budget-fix.md"), proof("budget-tests.txt")],
    }
    rows = {}
    for source in ("SRC-165", "SRC-166"):
        assert intake.verify_integrity(ROOT, source)["ok"]
        contract = intake._read_contract(ROOT, source)
        for rid, clause in contract["clauses"].items():
            number = int(rid.rsplit("R", 1)[1])
            category = "pair"
            statement = "Same final oracle is RED on original production and GREEN on current production."
            verification = green["command"] + " -> 34 tests PASS; verifier " + current_oracle
            if source == "SRC-165" and number == 7:
                statement = "Canonical SYSTEM_CORRECTION retirement E-11885; T-1599 not DONE and SRC-164 retained."
            elif source == "SRC-165" and number == 8:
                statement = "False T-1599 dependency removed; E-11887 parks T-1510 on real T-1600, whose completion restores its trajectory. Parent final acceptance remains owed."
            elif source == "SRC-165" and 25 <= number <= 27:
                category = "installed"
                statement = "Installed artifact controls and real capability limitations are recorded separately; no live trust/admission/reload is inferred."
                verification = "installed_dogfood.py and installed_prompt.py -> PASS synthetic installed-route controls; see layered refusals and NOT_PROVEN boundaries"
            elif source == "SRC-165" and number == 28:
                category = "advisory"
                statement = "Registry and refreshed installed instructions declare ADVISORY with no response hook; no mechanical prevention claimed."
                verification = "canonical inject.ps1 -AdapterId zaicode and zcode-production -> provenance verified; registry has response_hook null and response_enforcement ADVISORY"
            elif source == "SRC-165" and number in (29, 30):
                category = "installed"
                statement = "Completed-part and post-render final gates remain separate from ADVISORY intermediate suppression; streamed text cannot be retracted."
                verification = "installed route controls and adapter registry agree on final hooks, post-render limits, one correction and ADVISORY intermediate suppression"
            elif source == "SRC-165" and number in (32, 33):
                statement = "PENDING actual current conformance/full-core evidence; not discharged by an older green generation."
                verification = "PENDING"
            elif source == "SRC-165" and number >= 34:
                category = "review"
                statement = "This execution used canonical state operations, created no unrelated Work and performed no release publication."
                verification = "canonical LOG E-11885 through current T-1600 events, unchanged Work scope and reviewed command/effect record"
            elif source == "SRC-166":
                category = "installed"
                statement = "Three fresh oversized attempts are mechanically replaced at the installed completed-part gate; standalone Stop limitations and admission refusals stay explicit. No credit from model apology/self-review."
                verification = "test_response_delivery -> PASS in identical paired oracle; installed_dogfood.py -> three fresh sessions each six lines/216 chars, no oversized delivered part"
            rows[rid] = {
                "source": source,
                "criterion": clause["text"],
                "class": clause["class"],
                "status": "PENDING" if verification == "PENDING" else "VERIFIED",
                "conclusion": statement,
                "proof": evidence[category],
                "verification": verification,
            }
    document = {
        "kind": "reviewed-source-acceptance-map",
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "work": "T-1600",
        "oracle": current_oracle,
        "production": green["subject_digest"],
        "clauses": rows,
    }
    target = HERE / "acceptance-map.json"
    target.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    updated = []
    if args.apply_known:
        for rid, row in rows.items():
            if row["status"] != "VERIFIED":
                continue
            result = intake.set_disposition(
                ROOT, row["source"], rid, "VERIFIED", work="T-1600",
                evidence=target.relative_to(ROOT).as_posix() + "#" + rid + "; " + row["conclusion"],
                verification=row["verification"],
            )
            if not result.get("ok"):
                print(json.dumps(result))
                raise SystemExit(1)
            updated.append(rid)
    print(json.dumps({"ok": True, "map": str(target), "updated": len(updated), "pending": [rid for rid, row in rows.items() if row["status"] == "PENDING"]}))


if __name__ == "__main__":
    main()

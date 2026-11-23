"""T-1670: adjudicate the SRC-191 clauses this ticket's own evidence proves.

Usage: dispose_clauses.py <repo> <verify-event>
"""
import json
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
event = sys.argv[2]
BASH = r"C:\Program Files\Git\usr\bin\bash.exe"
TESTS = "test_t1670_route_budgets"
CORE = "core-unit 175df927036947cd 5797 ran, 0 red"
CLAUSES = {
    "R001": "context clause of this source; carried and proved by SRC-191:R004",
    "R002": "no cap was raised: test_protocol_registry no longer asserts any aggregate bound "
            "and REGISTRY budgets name routes only",
    "R003": "context clause of this source; measured again at 334847, informational",
    "R004": "test_protocol_registry asserts every REGISTRY load_profiles route under its budget "
            f"and protocol_budget.check() empty; {CORE}",
    "R005": "protocol_budget load_profiles reports each route's must, transitive and conditional "
            "documents with bytes; --summary prints bytes, budget and verdict per route",
    "R006": f"{TESTS}: a declared requires chain is counted whole, a conditional reference adds "
            "nothing; KNOWLEDGE, README and archives sit outside saipen/ and no route lists them",
    "R007": "routes and requires are read from REGISTRY.json load_profiles; no prose is parsed",
    "R008": "load_profiles lists human_markdown_total under informational and no check reads it",
    "R009": f"{TESTS}: one enormous document FAILs single_doc whether or not a route loads it",
    "R010": f"cold profile (BOOT, STYLE, EXECUTION, INDEX) is its own budget; {TESTS}: VERIFY or "
            "FUTURE growth leaves the cold load byte-identical",
    "R011": "ordinary_phase counts CORE plus the largest active phase only; inactive phases, "
            "KNOWLEDGE and translations are excluded from every route",
    "R012": f"{TESTS} pre-fix control: a routed-nowhere clause trips only the old aggregate; "
            "old-engine run red in t1670_controls.out.txt",
    "R013": "t1670_controls.out.txt: the same clause on the new engine exits 0",
    "R014": f"{TESTS}: mandatory BOOT or phase growth past its budget FAILs",
    "R015": f"{TESTS}: unrelated growth raises the total and moves no route, verdict PASS",
    "R016": f"{TESTS}: a declared dependency chain A to B to C is counted whole",
    "R017": f"{TESTS}: an optional reference does not inflate the mandatory load",
    "R018": f"{TESTS}: VERIFY or FUTURE growth leaves the cold load byte-identical",
    "R019": "python tools/protocol_budget.py --summary: one line per route, the largest "
            "document, the total as informational (summary.out.txt)",
    "R022": "no SAIRoute or ZAICODE file is touched by this delta; consumer wiring stays T-1664",
}
failed = 0
for rid, verification in CLAUSES.items():
    proc = subprocess.run(
        [BASH, str(repo / "bin" / "saipen"), "source", "disp", "SRC-191", rid, "VERIFIED",
         "--work", "T-1670", "--evidence", event, "--verification", verification, "--json"],
        cwd=str(repo), capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False,
    )
    try:
        answer = json.loads(proc.stdout)
    except ValueError:
        answer = {"ok": False, "code": "UNPARSED", "detail": (proc.stdout + proc.stderr)[-300:]}
    print(rid, answer.get("ok"), answer.get("code"), answer.get("detail") or "")
    failed += not answer.get("ok")
raise SystemExit(1 if failed else 0)

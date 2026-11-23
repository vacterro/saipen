"""Known-good and known-bad calibration of the public projection receipt."""

import hashlib
import json
import sys
from pathlib import Path


def check(path, prose_name):
    report = json.loads(path.read_text(encoding="utf-8"))
    p = report["projections"]
    states = lambda name: {row["ac"]: row["state"] for row in p[name]["criteria"]}
    checks = {
        "nonempty actual public commands": len(p) == 10 and all(c["exit_code"] == 0 for c in report["commands"]),
        "prose stays unverified": states(prose_name) == {"AC-01": "UNVERIFIED", "AC-02": "UNVERIFIED"},
        "quoted marker stays unverified": states("quoted") == states("empty"),
        "unknown evidence class stays unverified": states("invalid_class") == states("empty"),
        "bound criterion and event identity": states("bound") == {"AC-01": "SATISFIED", "AC-02": "UNVERIFIED"}
            and isinstance(p["bound"]["criteria"][0]["evidence"][0]["event"], int),
        "narrow witness cannot prove broader criterion": states("too_weak")["AC-02"] == "EVIDENCE_SCOPE_TOO_WEAK",
        "disagreement remains contested": states("conflict")["AC-01"] == "CONTESTED",
        "undeclared criterion stays visible": p["undeclared"]["undeclared_evidence"] == ["AC-07"],
        "escaped defect preserves relation": states("escaped")["AC-02"] == "CONTESTED"
            and len(p["escaped"]["criteria"][1]["escaped_defects"]) == 1,
        "fixture readonly coverage and owned cleanup": report["readonly_checks"] == 10
            and not Path(report["temp_root"]).exists() and report["fixture_only"] and not report["grants_authority"],
    }
    failed = sum(not okay for okay in checks.values())
    print(json.dumps({"checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      "receipt": str(path), "prose_input": prose_name,
                      "checks": checks, "passed": len(checks)-failed, "failed": failed}, indent=2))
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(check(Path(sys.argv[1]), sys.argv[2]))

"""Check native entry-form receipts against retained output and current init."""

import hashlib
import json
import sys
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
ROOT = EVIDENCE.parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(receipt):
    original = json.loads((EVIDENCE / "review/original.json").read_text(encoding="utf-8"))
    current = json.loads(receipt.read_text(encoding="utf-8"))
    summary = json.loads((EVIDENCE / "review/result.json").read_text(encoding="utf-8"))
    checks = {
        "current native forms pass": len(current["cases"]) == 2 and all(
            c["exit_code"] == 0 and c["has_usage"] and not c["foreign_executed"]
            for c in current["cases"]),
        "help byte parity": current["cases"][0]["stdout_sha256"] == current["cases"][1]["stdout_sha256"],
        "same fixed verifier": original["verifier"] == current["verifier"],
        "actual old foreign execution": original["cases"][1]["foreign_executed"]
            and original["cases"][1]["has_foreign_error"]
            and "foreign saipen_engine executed" in (EVIDENCE / "review/original-1.txt").read_text(encoding="utf-8"),
        "retained current output binding": all(
            sha(receipt.parent / f"{current['label']}-{i}.txt") == c["output_sha256"]
            for i, c in enumerate(current["cases"])),
        "current init binding": sha(ROOT / "tools/__init__.py") == current["subject"],
        "live source preserved and owned root reclaimed": summary["live_init_unchanged"]
            and not Path(summary["temp_root"]).exists(),
    }
    failed = sum(not okay for okay in checks.values())
    print(json.dumps({"checker_sha256": sha(__file__), "receipt": str(receipt),
                      "checks": checks, "passed": len(checks)-failed, "failed": failed}, indent=2))
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(check(Path(sys.argv[1])))

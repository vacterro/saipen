"""Bind actual native import receipts to current implementation and oracle."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
ROOT = EVIDENCE.parents[2]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def check(green_path: Path) -> int:
    folder = EVIDENCE / "review-pair"
    original = json.loads((folder / "original.json").read_text(encoding="utf-8"))
    earlier = json.loads((folder / "earlier.json").read_text(encoding="utf-8"))
    corrected = json.loads(green_path.read_text(encoding="utf-8"))
    results = []

    def require(name: str, okay: bool) -> None:
        results.append({"check": name, "okay": bool(okay)})

    require("nonempty native runs and opposite results",
            all(record["collected"] == 35 for record in (original, earlier, corrected))
            and original["exit_code"] != 0 and earlier["exit_code"] != 0
            and corrected["exit_code"] == 0)
    require("one fixed verifier digest",
            len({record["verifier"] for record in (original, earlier, corrected)}) == 1
            and all(record["verifier"] == digest(record["verifier_identity"])
                    for record in (original, earlier, corrected)))
    require("current oracle bytes",
            all(sha(ROOT / path) == value
                for path, value in corrected["verifier_identity"]["files"].items()))
    require("current implementation bytes",
            all((sha(ROOT / path) if (ROOT / path).is_file() else "ABSENT") == value
                for path, value in corrected["subject_identity"].items())
            and corrected["subject"] == digest(corrected["subject_identity"]))
    outputs_match = True
    for record, path in ((original, folder / "original.txt"),
                         (earlier, folder / "earlier.txt"),
                         (corrected, green_path.with_suffix(".txt"))):
        output = path.read_text(encoding="utf-8")
        outputs_match &= (hashlib.sha256(output.encode()).hexdigest()
                          == record["output_sha256"]
                          and bool(re.search(r"Ran 35 tests in ", output)))
    require("retained actual output binding", outputs_match)
    old_output = (folder / "earlier.txt").read_text(encoding="utf-8")
    require("earlier candidate still fails reload execution",
            "reload suppressed CLI source execution" in old_output
            and "reload must execute source exactly once" in old_output
            and "FAILED (failures=2)" in old_output)
    require("known bad duplicate guard remains independent",
            "spec_from_file_location(\"t1348_forced_duplicate\"" in
            (ROOT / "tools/test_module_duplication_guard.py").read_text(encoding="utf-8")
            and "assert not loader.errors" in
            (ROOT / "tools/test_module_duplication_guard.py").read_text(encoding="utf-8"))
    summary = json.loads((folder / "result.json").read_text(encoding="utf-8"))
    require("unchanged live binding and owned allocation removed",
            summary["live_unchanged"] and summary["live_matches_corrected"]
            and not Path(summary["temp_root"]).exists())
    failed = sum(not result["okay"] for result in results)
    print(json.dumps({"checker_sha256": sha(Path(__file__)),
                      "green_receipt": str(green_path), "checks": results,
                      "passed": len(results) - failed, "failed": failed}, indent=2))
    return int(bool(failed))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("green_receipt", type=Path)
    raise SystemExit(check(parser.parse_args().green_receipt))

"""Unchanged source-event oracle against exact pre-turn and current subjects.

Diagnostic only: final canonical executed regression and acceptance remain due.
The temporary copies have identical dependencies, configuration and oracle.
"""

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    evidence = Path(__file__).resolve().parent
    root = evidence.parents[2]
    oracle = root / "tools/test_t1844_source_event.py"
    results = {}
    with tempfile.TemporaryDirectory(prefix="t1844-source-event-pair-") as temporary:
        for label in ("before", "after"):
            target = Path(temporary) / label
            for directory in ("tools", "saipen", "tests", "extensions", "bootstrap"):
                shutil.copytree(root / directory, target / directory,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            for name in (".gitattributes", ".gitignore"):
                shutil.copy2(root / name, target / name)
            if label == "before":
                for original in (evidence / "turn-prefix").rglob("*"):
                    if original.is_file():
                        destination = target / original.relative_to(evidence / "turn-prefix")
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(original, destination)
            command = [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tools",
                       "-p", oracle.name, "-q"]
            process = subprocess.run(command, cwd=target, capture_output=True, text=True,
                                     encoding="utf-8", errors="replace", timeout=120)
            transcript = process.stdout + process.stderr
            log = evidence / f"source-event-{label}.log"
            log.write_text(transcript, encoding="utf-8")
            count = re.search(r"Ran (\d+) tests?", transcript)
            results[label] = {
                "exit_code": process.returncode,
                "ran": int(count[1]) if count else 0,
                "errors": len(re.findall(r"^ERROR:", transcript, re.M)),
                "failures": len(re.findall(r"^FAIL:", transcript, re.M)),
                "oracle_sha256": digest(target / "tools" / oracle.name),
                "subjects": {
                    path.relative_to(evidence / "turn-prefix").as_posix():
                    digest(target / path.relative_to(evidence / "turn-prefix"))
                    for path in (evidence / "turn-prefix").rglob("*") if path.is_file()
                },
                "log": log.relative_to(root).as_posix(),
            }
    results["classification"] = "diagnostic only; final canonical VERIFY pair remains due"
    valid = (results["before"]["exit_code"] == 1 and results["before"]["errors"] == 0
             and results["before"]["failures"] > 0 and results["after"]["exit_code"] == 0
             and results["before"]["ran"] == results["after"]["ran"] == 18
             and results["before"]["oracle_sha256"] == results["after"]["oracle_sha256"]
             == digest(oracle))
    results["valid"] = valid
    (evidence / "source-event-pair.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps({"valid": valid, "before": results["before"]["failures"],
                      "after": results["after"]["exit_code"],
                      "errors": [results[k]["errors"] for k in ("before", "after")]}, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())

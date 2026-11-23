"""Execute the unchanged real-carrier oracle on saved and current subjects.

This is a diagnostic transcript, not a canonical executed-regression receipt.
The required native VERIFY operation must still measure the final full subject.
"""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    evidence = Path(__file__).resolve().parent
    root = evidence.parents[2]
    oracle = root / "tools/test_t1844_operator_origin.py"
    results = {}
    with tempfile.TemporaryDirectory(prefix="t1844-carrier-pair-") as temporary:
        for name in ("before", "after"):
            target = Path(temporary) / name
            (target / "tools").mkdir(parents=True)
            shutil.copytree(root / "tools/saipen_engine", target / "tools/saipen_engine")
            shutil.copytree(root / "saipen", target / "saipen")
            (target / "extensions/adapters").mkdir(parents=True)
            shutil.copy2(
                root / "extensions/adapters/registry.json",
                target / "extensions/adapters/registry.json",
            )
            shutil.copy2(oracle, target / "tools/test_t1844_operator_origin.py")
            if name == "before":
                for original in (evidence / "prefix").rglob("*"):
                    if original.is_file():
                        destination = target / original.relative_to(evidence / "prefix")
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(original, destination)
            command = [sys.executable, "-B", "-m", "unittest", "tools.test_t1844_operator_origin"]
            process = subprocess.run(
                command, cwd=target, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=60,
            )
            transcript = process.stdout + process.stderr
            log = evidence / f"diagnostic-carrier-{name}.log"
            log.write_text(transcript, encoding="utf-8")
            results[name] = {
                "exit_code": process.returncode, "oracle_sha256": digest(oracle),
                "operator_task_sha256": digest(target / "tools/saipen_engine/operator_task.py"),
                "log": log.relative_to(root).as_posix(),
            }
    results["classification"] = "diagnostic-only; canonical final VERIFY pair remains due"
    (evidence / "diagnostic-carrier-pair.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8",
    )
    print(json.dumps(results, indent=2))
    return 0 if results["before"]["exit_code"] == 1 and results["after"]["exit_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

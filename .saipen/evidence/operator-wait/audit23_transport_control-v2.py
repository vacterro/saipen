"""Replay the same real-CLI WAIT/printed-command controls on saved subjects."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PRODUCTION = (
    "saipen/REGISTRY.json", "tools/saipen.py", "tools/validate.py",
    "tools/saipen_engine/state.py", "tools/saipen_engine/phases.py",
    "tools/saipen_engine/fast_check.py", "tools/saipen_engine/reconcile.py",
    "tools/saipen_engine/operations.py", "tools/saipen_engine/subs.py",
    "tools/saipen_engine/router.py",
)


def main():
    stage = sys.argv[1]
    if stage not in ("original", "current"):
        raise SystemExit("stage must be original or current")
    record_path = HERE / f"transport-v2-{stage}.json"
    if record_path.exists():
        raise SystemExit(f"preserved evidence already exists: {record_path}")
    with tempfile.TemporaryDirectory(prefix="audit23-subject-") as temporary:
        runtime = Path(temporary) / "runtime"
        for directory in ("tools", "saipen", "bin", "extensions"):
            shutil.copytree(ROOT / directory, runtime / directory,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copy2(ROOT / "VERSION", runtime / "VERSION")
        subject = hashlib.sha256()
        for relative in PRODUCTION:
            path = runtime / relative
            if stage == "original":
                saved = HERE / "before" / relative
                if saved.is_file():
                    path.write_bytes(saved.read_bytes())
                elif relative == "tools/saipen_engine/router.py":
                    # This file was pristine before this Work: its current
                    # diff contains only our two WAIT-routing hunks. HEAD is
                    # the independently retained original source, not a fix.
                    path.write_bytes(subprocess.check_output(
                        ["git", "show", "HEAD:" + relative], cwd=ROOT))
                else:
                    raise RuntimeError(f"original source unavailable: {relative}")
            subject.update(relative.encode() + b"\0" + path.read_bytes())
        executed = subprocess.run(
            [sys.executable, "-B", "-m", "unittest",
             "test_next_action_grammar.OperatorWaitBoundaryTests"],
            cwd=runtime / "tools", capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=600,
        )
        transcript = executed.stdout + executed.stderr
        ran = re.search(r"Ran (\d+) tests?", transcript)
        counts = {
            key: int(match.group(1)) if (match := re.search(key + r"=(\d+)", transcript)) else 0
            for key in ("failures", "errors", "skipped")
        }
        verifier = hashlib.sha256()
        for path in (Path(__file__), ROOT / "tools/test_next_action_grammar.py",
                     ROOT / "tools/test_next_action_deadlock.py"):
            verifier.update(path.name.encode() + b"\0" + path.read_bytes())
        record = {
            "stage": stage, "method": "isolated saved production subject; same real-CLI tests",
            "verifier": verifier.hexdigest(), "subject": subject.hexdigest(),
            "ran": int(ran.group(1)) if ran else 0, **counts,
            "passed": executed.returncode == 0, "transcript": transcript,
            "original_router": "pristine HEAD source; only current Work routing hunks differ",
        }
    record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in record.items() if key != "transcript"}))
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

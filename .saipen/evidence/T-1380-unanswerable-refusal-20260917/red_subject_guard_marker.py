"""T-1380 slice 7 red control: the FINAL marker oracle against the PRE-FIX extractor.

`tools/` is copied to a scratch directory and `_refusal_texts` is reverted there
to the extractor the re-run measured with: the guard marker was matched in the
tool's OUTPUT and ERROR together, so a completed `grep` listing this repository's
source lines scored refusals the session never received.

Exit: 0 when the pre-fix extractor FAILS the new control and the real-shape
control stays green (the oracle is not simply broken).
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]

MUTATION = '''

# --- T-1380 RED SUBJECT: the extractor before slice 7 ------------------------
def _refusal_texts(tools):
    out = []
    for item in tools:
        blob = item["output"] + " " + item["error"]
        command = item["input"].get("command")
        ran_saipen = isinstance(command, str) and _PROTOCOL.search(command) is not None
        for match in _GUARD_REFUSAL.finditer(blob):
            out.append((match.group(1), match.group(2).strip()))
        if not ran_saipen:
            continue
        for match in _HUMAN_REFUSAL.finditer(blob):
            out.append((match.group(1), (match.group(2) or "").strip()))
        for match in _JSON_REFUSAL.finditer(blob):
            tail = blob[match.end() : match.end() + 600]
            message = re.search(r'"(?:message|detail)":\\s*"([^"]{0,200})', tail)
            out.append((match.group(1), (message.group(1) if message else "").strip()))
    return out
'''

MUST_FAIL = "test_a_guard_marker_in_what_a_tool_read_is_not_a_refusal"
MUST_PASS = "test_the_guard_marker_counts_whatever_the_command_was"


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="t1380-red-marker-"))
    try:
        subject = work / "subject"
        for name in ("tools", "saipen", "extensions"):
            source = REPO / name
            if source.is_dir():
                shutil.copytree(
                    source, subject / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
                )
        target = subject / "tools" / "t1363_field_polygon.py"
        before = hashlib.sha256(target.read_bytes()).hexdigest()
        with target.open("a", encoding="utf-8") as handle:
            handle.write(MUTATION)
        after = hashlib.sha256(target.read_bytes()).hexdigest()
        oracle = REPO / "tools" / "test_refusal_routes.py"
        copied = subject / "tools" / "test_refusal_routes.py"
        print(
            f"oracle  sha256 {hashlib.sha256(oracle.read_bytes()).hexdigest()[:16]} "
            f"(identical copy: {oracle.read_bytes() == copied.read_bytes()})"
        )
        print(f"subject {before[:16]} -> {after[:16]} (_refusal_texts reverted)")
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "-v",
                "tools.test_refusal_routes.RefusalIdentityIsNotACodeBucketTests",
            ],
            cwd=subject,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
        )
        output = proc.stdout + proc.stderr
        for line in output.splitlines():
            if " ... " in line or line.startswith(("FAIL: ", "ERROR: ", "Ran ", "FAILED", "OK")):
                print(line)
        failed = {
            line.split(" ", 2)[1]
            for line in output.splitlines()
            if line.startswith(("FAIL: ", "ERROR: "))
        }
        if MUST_FAIL not in failed:
            print(f"NOT RED, so the oracle proves nothing here: {MUST_FAIL}")
            return 1
        if MUST_PASS in failed:
            print(f"the real-shape control broke too, so the oracle itself is suspect: {MUST_PASS}")
            return 1
        print("RED CONTROL OK: the reverted extractor scores what a grep read as a refusal")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

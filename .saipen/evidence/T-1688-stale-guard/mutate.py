"""Mutation controls for T-1688 in a disposable copy of the tree.

Each mutation removes ONE property of the replaced-plugin round trip and runs
the ticket module and the T-1628 oracle unchanged. A mutation neither module
sees is a missing test, not a redundant line.

    python mutate.py --subject <repo root>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--subject", required=True)
args = parser.parse_args()
evidence = Path(__file__).resolve().parent
root = Path(args.subject).resolve()
PLUGIN = "extensions/adapters/opencode/saipen-guard.js"
command = [
    sys.executable, "-B", "-m", "unittest", "-v",
    "test_t1688_stale_plugin_guard", "test_t1628_opencode_policy",
]
sys.path.insert(0, str(root / "tools"))
from saipen_engine.process_tree import run as run_owned  # noqa: E402
from saipen_engine.test_runner import _ignore_copy  # noqa: E402

MUTATIONS = [
    (
        "round_trip_skipped_again",
        'if (gap !== "PLUGIN_RESTART_REQUIRED") return;',
        "return;",
    ),
    (
        "other_answers_block",
        "if (degradedStale) return;",
        "void degradedStale;",
    ),
    (
        "strict_falls_through",
        'if (decision.decision !== "ALLOW_DEGRADED") {',
        "if (false) {",
    ),
    (
        "guardless_gaps_enter_the_round_trip",
        'if (gap !== "PLUGIN_RESTART_REQUIRED") return;',
        "void 0;",
    ),
    (
        "target_refusal_dropped_in_the_gap",
        "if (verdict.block && TERMINAL_GUARD_CODES.has(verdict.code)) {",
        "if (!degradedStale && verdict.block && TERMINAL_GUARD_CODES.has(verdict.code)) {",
    ),
]

RED = re.compile(r"^(?:FAIL|ERROR): (test_\w+)", re.MULTILINE)


def run(subject: Path) -> tuple[int, list[str]]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
    env["CLAUDE_CONFIG_DIR"] = ""
    result = run_owned(
        command,
        cwd=subject / "tools",
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=420,
    )
    text = (result.stdout + result.stderr).decode("utf-8", "replace")
    return result.returncode, sorted(set(RED.findall(text)))


report: dict = {"mutations": []}
with tempfile.TemporaryDirectory(prefix="saipen-t1688-mutate-") as temporary:
    subject = Path(temporary) / "project"

    def ignore(directory, names):
        extra = {".git"}
        if Path(directory) == root:
            extra.add(".saipen")
        return _ignore_copy(directory, names) | {name for name in names if name in extra}

    shutil.copytree(root, subject, symlinks=True, ignore=ignore)
    plugin = subject / PLUGIN
    original = plugin.read_bytes()
    report["control_before"] = run(subject)
    for name, old, new in MUTATIONS:
        count = original.count(old.encode("utf-8"))
        if count != 1:
            report["mutations"].append({"name": name, "error": f"anchor matched {count} times"})
            continue
        plugin.write_bytes(original.replace(old.encode("utf-8"), new.encode("utf-8")))
        runs = [run(subject) for _ in range(2)]
        report["mutations"].append({
            "name": name,
            "rc": [item[0] for item in runs],
            "red": runs[0][1],
            "stable": runs[0][1] == runs[1][1],
        })
    plugin.write_bytes(original)
    report["control_after"] = run(subject)

report["undetected"] = [
    item["name"] for item in report["mutations"]
    if "error" in item or 0 in item["rc"] or not item["stable"]
]
(evidence / "mutate.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
raise SystemExit(
    1 if report["undetected"] or report["control_before"][0] or report["control_after"][0] else 0
)

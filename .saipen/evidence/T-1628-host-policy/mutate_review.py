"""REVIEW mutation controls for T-1628 (second seat, 2026-10-08).

Each mutation removes ONE property of the native OpenCode gap policy from a
disposable copy of the plugin and runs the held oracle unchanged. A mutation
the oracle does not see is a missing test, not a redundant line.

    python mutate_review.py --subject <repo root>
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
command = [sys.executable, "-B", "-m", "unittest", "-v", "test_t1628_opencode_policy"]
sys.path.insert(0, str(root / "tools"))
from saipen_engine.process_tree import run as run_owned  # noqa: E402
from saipen_engine.test_runner import _ignore_copy  # noqa: E402

MUTATIONS = [
    (
        "strict_ignored",
        'decision: row ? row.decisions[policy.mode] : "BLOCK",',
        'decision: row ? row.decisions[HOST_INTEGRATION_POLICY.default_mode] : "BLOCK",',
    ),
    (
        "invalid_policy_uses_default",
        'const invalid = { mode: HOST_INTEGRATION_POLICY.strict_mode, source: "invalid" };',
        'const invalid = { mode: HOST_INTEGRATION_POLICY.default_mode, source: "invalid" };',
    ),
    (
        "conflict_not_refused_at_tool_gate",
        "throw guardRefusal({ block: true, code: conflict }, null, toolName, args);",
        "void conflict;",
    ),
    (
        "native_observation_off",
        "return gap ? observedBindingConflict(context) : null;",
        "return null;",
    ),
    (
        "unverified_marker_dropped",
        "output.system.push(integrationSystemMessage(integrationDecision(gap, conflict)));",
        "void integrationSystemMessage;",
    ),
    (
        "gap_allowance_before_payload_check",
        'if (!args || typeof args !== "object" || Array.isArray(args)) {',
        'if (!integrationGap() && (!args || typeof args !== "object" || Array.isArray(args))) {',
    ),
    (
        "stale_plugin_not_a_gap",
        'if (installedSha256 !== LOADED_SHA256) return "PLUGIN_RESTART_REQUIRED";',
        "void installedSha256;",
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
        timeout=300,
    )
    text = (result.stdout + result.stderr).decode("utf-8", "replace")
    return result.returncode, sorted(set(RED.findall(text)))


report: dict = {"mutations": []}
with tempfile.TemporaryDirectory(prefix="saipen-t1628-mutate-") as temporary:
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
        rc, red = run(subject)
        report["mutations"].append({"name": name, "rc": rc, "red": red})
    plugin.write_bytes(original)
    report["control_after"] = run(subject)

report["undetected"] = [
    item["name"] for item in report["mutations"] if item.get("rc") == 0 or "error" in item
]
(evidence / "mutate_review.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
raise SystemExit(1 if report["undetected"] or report["control_before"][0] or report["control_after"][0] else 0)

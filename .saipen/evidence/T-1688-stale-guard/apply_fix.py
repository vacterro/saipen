"""Apply the T-1688 plugin and adapter-document change over exact inherited bytes.

    python apply_fix.py --subject <repo root> [--check]

Each anchor must match exactly once in the file's own line endings; otherwise
nothing is written. `--check` reports without writing.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--subject", required=True)
parser.add_argument("--check", action="store_true")
args = parser.parse_args()
root = Path(args.subject).resolve()

PLUGIN = "extensions/adapters/opencode/saipen-guard.js"
DOC = "extensions/adapters/opencode.md"

EDITS = {
    PLUGIN: [
        (
            "      if (gap) {\n"
            "        const decision = integrationDecision(gap);\n"
            '        if (decision.decision === "ALLOW_DEGRADED") return;\n'
            "        throw new Error(\n"
            "          `SAIPEN_GUARD_REFUSAL: ${gap}: UNVERIFIED ${decision.policy}; ` +\n"
            "          `next: ${decision.operator_action}; the host tool did not execute`,\n"
            "        );\n"
            "      }\n",
            "      // T-1688: a replaced plugin still has its guard and its interpreter, so\n"
            "      // the previous generation keeps asking. A refusal that is a fact about\n"
            "      // the target or the actor does not depend on which generation forwarded\n"
            "      // the event and survives the gap; every other answer, an unreadable one\n"
            "      // included, is the UNVERIFIED part and degrades. The two gaps with\n"
            "      // nothing to ask return here as before.\n"
            "      let degradedStale = false;\n"
            "      if (gap) {\n"
            "        const decision = integrationDecision(gap);\n"
            '        if (decision.decision !== "ALLOW_DEGRADED") {\n'
            "          throw new Error(\n"
            "            `SAIPEN_GUARD_REFUSAL: ${gap}: UNVERIFIED ${decision.policy}; ` +\n"
            "            `next: ${decision.operator_action}; the host tool did not execute`,\n"
            "          );\n"
            "        }\n"
            '        if (gap !== "PLUGIN_RESTART_REQUIRED") return;\n'
            "        degradedStale = true;\n"
            "      }\n",
        ),
        (
            "      if (verdict.block && TERMINAL_GUARD_CODES.has(verdict.code)) {\n"
            "        throw guardRefusal(verdict, guardPayload, toolName, args);\n"
            "      }\n",
            "      if (verdict.block && TERMINAL_GUARD_CODES.has(verdict.code)) {\n"
            "        throw guardRefusal(verdict, guardPayload, toolName, args);\n"
            "      }\n"
            "      if (degradedStale) return;\n",
        ),
    ],
    DOC: [
        (
            "    Known binding conflicts remain refused in every policy. Verified built-in\n"
            "    read-only tools skip the round trip and stay usable.\n",
            "    Known binding conflicts remain refused in every policy. Verified built-in\n"
            "    read-only tools skip the round trip and stay usable.\n"
            "  - a replaced loaded plugin whose guard and interpreter are still present\n"
            "    keeps asking the guard under DEGRADED_ALLOWED: a refusal about the target\n"
            "    or the actor (protected canonical path, path escape, unresolved target,\n"
            "    ownership or binding conflict) still refuses with its own code; any\n"
            "    other answer, an unreadable one included, degrades.\n",
        ),
    ],
}

planned = {}
for relative, edits in EDITS.items():
    path = root / relative
    data = path.read_bytes()
    newline = b"\r\n" if b"\r\n" in data else b"\n"
    for old, new in edits:
        old_bytes = old.encode("utf-8").replace(b"\n", newline)
        new_bytes = new.encode("utf-8").replace(b"\n", newline)
        count = data.count(old_bytes)
        if count != 1:
            raise SystemExit(f"{relative}: anchor matched {count} times; nothing written")
        data = data.replace(old_bytes, new_bytes)
    planned[relative] = data

for relative, data in planned.items():
    if not args.check:
        (root / relative).write_bytes(data)
    print(relative, hashlib.sha256(data).hexdigest())

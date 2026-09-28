"""Rebuild the PRE-FIX adapter artifact for the T-1553 ORACLE red control.

The variable between red and green must be the implementation, never the
fixture or the oracle. This reverses each T-1553 edit by its anchors, asserts
every anchor matched exactly once, and writes `saipen-guard.js` beside this
script. The result is the adapter as it stood before the repair, byte for byte
in every region the repair touched.

    python .saipen/kitchen/t1553-prefix/rebuild_prefix_artifact.py
    SAIPEN_OPENCODE_PLUGIN_UNDER_TEST=<that file> \
        python -B -m unittest tools.test_t1553_mid_session_activation
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
LIVE = REPO / "extensions" / "adapters" / "opencode" / "saipen-guard.js"
OUT = Path(__file__).resolve().parent / "saipen-guard.js"

#: (anchor in the repaired file, pre-fix replacement)
REVERSALS = [
    # 1. the live-binding cache + helper disappears again
    (
        """  // The resolved project is the admission cwd. When no binding resolved this\n"""
        """  // is the legacy worktree-first start, so refusal behaviour is unchanged.\n"""
        """  let eventCwd = bootstrapBinding.resolved_from || contextStart(context);\n""",
        """  const systemMessage = bindingSystemMessage(bootstrapBinding);\n"""
        """  // The resolved project is the admission cwd. When no binding resolved this\n"""
        """  // is the legacy worktree-first start, so refusal behaviour is unchanged.\n"""
        """  const eventCwd = bootstrapBinding.resolved_from || contextStart(context);\n"""
        """  let attemptedCondition = null;\n""",
    ),
    # 2. system.transform pushes the frozen message again
    (
        """      const binding = await currentBinding({ rateLimitMs: BINDING_RECHECK_MS });\n"""
        """      output.system.push(bindingSystemMessage(binding));\n""",
        """      output.system.push(systemMessage);\n""",
    ),
    # 3. system.transform recall reads the frozen binding
    (
        """      if (binding.code !== "ADMITTED" || !binding.project_root) return;\n"""
        """      const sessionID = input && input.sessionID;\n"""
        """      const memory = sessionMemory(sessionID);\n"""
        """      const recall = runRecall(\n"""
        """        pythonBin, saipenPy, binding.project_root,\n""",
        """      if (bootstrapBinding.code !== "ADMITTED" || !bootstrapBinding.project_root) return;\n"""
        """      const sessionID = input && input.sessionID;\n"""
        """      const memory = sessionMemory(sessionID);\n"""
        """      const recall = runRecall(\n"""
        """        pythonBin, saipenPy, bootstrapBinding.project_root,\n""",
    ),
    # 4. the final-response gate reads the frozen binding again
    (
        """      const binding = await currentBinding();\n"""
        """      if (binding.code !== "ADMITTED" || !binding.project_root) return;\n"""
        """      const memory = sessionMemory(input && input.sessionID);\n"""
        """      if (!memory.operational) return;\n"""
        """      if (!output || typeof output.text !== "string" || !output.text.trim()) {\n"""
        """        throw new Error("EXEC_RESPONSE_INVALID: empty operational response");\n"""
        """      }\n"""
        """      checkOperationalResponse(\n"""
        """        pythonBin, saipenPy, binding.project_root, output.text,\n""",
        """      if (bootstrapBinding.code !== "ADMITTED" || !bootstrapBinding.project_root) return;\n"""
        """      const memory = sessionMemory(input && input.sessionID);\n"""
        """      if (!memory.operational) return;\n"""
        """      if (!output || typeof output.text !== "string" || !output.text.trim()) {\n"""
        """        throw new Error("EXEC_RESPONSE_INVALID: empty operational response");\n"""
        """      }\n"""
        """      checkOperationalResponse(\n"""
        """        pythonBin, saipenPy, bootstrapBinding.project_root, output.text,\n""",
    ),
    # 5. tool.execute.before stops re-resolving
    (
        """      // T-1553: a tool event is the cheapest canonical moment to notice that\n"""
        """      // this project became a SAIPEN project (the guard round trip is spawned\n"""
        """      // for the event anyway), and eventCwd follows the upgraded binding.\n"""
        """      const binding = await currentBinding();\n"""
        """      const payload = JSON.stringify(\n""",
        """      const payload = JSON.stringify(\n""",
    ),
    # 6. Fleet keeps the frozen binding
    (
        """        const fleetResult = await runFleetPrepare(\n"""
        """          pythonBin, saipenPy, binding, eventCwd, attemptedCondition,\n""",
        """        const fleetResult = await runFleetPrepare(\n"""
        """          pythonBin, saipenPy, bootstrapBinding, eventCwd, attemptedCondition,\n""",
    ),
]

def main() -> int:
    text = LIVE.read_text(encoding="utf-8")
    # The helper block: cut from its T-1553 comment up to and including the
    # helper's closing brace, then leave `let attemptedCondition` in place.
    start = text.index("  // T-1553: a host session that STARTS outside")
    end_marker = "    return liveBinding;\n  }\n  let attemptedCondition = null;\n"
    end = text.index(end_marker, start) + len(end_marker)
    text = text[:start] + text[end:]
    for anchor, replacement in REVERSALS:
        count = text.count(anchor)
        assert count == 1, f"anchor matched {count} times: {anchor[:60]!r}"
        text = text.replace(anchor, replacement, 1)
    assert "currentBinding" not in text, "a live-binding reference survived the reversal"
    assert text.count("let attemptedCondition = null;") == 1
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

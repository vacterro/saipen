from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

evidence = Path(__file__).resolve().parent
draft = Path(json.loads((evidence / 'scratch.json').read_text())['project'])
compiler = draft / 'tools/saipen_engine/native_host_policy.py'
shutil.copyfile(evidence / 'native_host_policy.py', compiler)
sys.path.insert(0, str(draft / 'tools'))
from saipen_engine.native_host_policy import fragment

plugin = draft / 'extensions/adapters/opencode/saipen-guard.js'
text = plugin.read_text(encoding='utf-8-sig')
anchor = 'const MAX_DIAGNOSTIC_BYTES = 4096;'
text = text.replace(anchor, anchor + '\n\n' + fragment() + '\n\n'
                    + (evidence / 'native_helpers.js').read_text(encoding='utf-8'), 1)
text = text.replace('//   output / unreachable      -> fail closed for consequential mutations',
                    '//   declared integration gap  -> operator policy; allowed work is UNVERIFIED\n'
                    '//   invalid output / payload  -> consequential tool does not execute', 1)
anchor = 'function bindingInstruction(binding) {\n'
text = text.replace(anchor, anchor + '  if (binding.code === "GUARD_UNREACHABLE") {\n'
    '    return "The canonical SAIPEN resolver could not be consulted. The separate " +\n'
    '      "SAIPEN_HOST_INTEGRATION record states the selected gap policy; no project " +\n'
    '      "binding or validation is claimed. Do not adopt an ambient project.";\n'
    '  }\n', 1)
anchor = '  let attemptedCondition = null;'
helper = '''  function integrationGap() {
    let installedSha256;
    try { installedSha256 = sha256(fs.readFileSync(MODULE_PATH)); } catch (_error) {
      installedSha256 = "missing";
    }
    if (installedSha256 !== LOADED_SHA256) return "PLUGIN_RESTART_REQUIRED";
    if (!guardInstalled) return "SAIPEN_GUARD_UNINSTALLED";
    if (!pythonBin) return "SAIPEN_GUARD_UNREACHABLE";
    return null;
  }
'''
text = text.replace(anchor, anchor + '\n' + helper, 1)
anchor = '      output.system.push(bindingSystemMessage(binding));'
text = text.replace(anchor, anchor + '\n      const gap = integrationGap();\n'
                    '      if (gap) output.system.push(integrationSystemMessage(integrationDecision(gap)));', 1)
start = text.index('      // A running host keeps its imported module after an on-disk overwrite.')
end = text.index('      // Tool name comes from the real hook INPUT;', start)
text = text[:start] + text[end:]
start = text.index('      if (!guardInstalled) {', text.index('"tool.execute.before":'))
end = text.index('      // T-1384:', start)
replacement = '''      // A known binding/ownership conflict is a refusal in every policy,
      // including when this loaded plugin has subsequently become stale.
      if (TERMINAL_GUARD_CODES.has(liveBinding.code)) {
        throw guardRefusal({ block: true, code: liveBinding.code }, null, toolName, args);
      }
      const gap = integrationGap();
      if (gap) {
        const decision = integrationDecision(gap);
        if (decision.decision === "ALLOW_DEGRADED") return;
        throw new Error(
          `SAIPEN_GUARD_REFUSAL: ${gap}: UNVERIFIED ${decision.policy}; ` +
          `next: ${decision.operator_action}; the host tool did not execute`,
        );
      }

'''
text = text[:start] + replacement + text[end:]
old = '''      const terminalGuardCodes = new Set([
        "PROTECTED_CANONICAL_NAMESPACE", "PATH_ESCAPES_PROJECT", "TARGET_UNRESOLVED",
        "PROJECT_BINDING_INVALID", "PROJECT_LINEAGE_MISMATCH", "OWNERSHIP_CONFLICT",
      ]);
      if (verdict.block && terminalGuardCodes.has(verdict.code)) {'''
assert old in text
text = text.replace(old, '      if (verdict.block && TERMINAL_GUARD_CODES.has(verdict.code)) {', 1)
plugin.write_text(text, encoding='utf-8')

registry = draft / 'extensions/adapters/registry.json'
text = registry.read_text(encoding='utf-8')
text = text.replace('"degraded_mode": "FAIL_CLOSED_TOOL_GATE",',
                    '"degraded_mode": "DEGRADED_ALLOWED_DEFAULT",', 1)
first = text.index('      "degraded_mode_note":')
last = text.index('\n', first)
note = ('No prompt-level admission hook exists. The consequential tool gate applies the '
        'operator policy for a missing guard, unavailable interpreter or replaced loaded '
        'plugin: DEGRADED_ALLOWED permits the tool with a bounded UNVERIFIED system '
        'record; STRICT refuses with the taxonomy action. Missing policy uses the '
        'canonical default, invalid policy uses STRICT. Known forged or foreign binding '
        'and normal guard refusals still block in every mode. Decisions are compiled '
        'from HOST-INTEGRATION-01 and checked against its owner.')
text = text[:first] + '      "degraded_mode_note": ' + json.dumps(note) + text[last:]
registry.write_text(text, encoding='utf-8')

docs = draft / 'extensions/adapters/opencode.md'
text = docs.read_text(encoding='utf-8')
old = '''  - guard failure, invalid output, unreadable `output.args` or no Python
    runtime -> fail closed for consequential mutations (verified built-in
    read-only tools skip the round trip and stay usable).'''
new = '''  - a missing guard, no Python or a replaced loaded plugin -> the operator's
    `~/.saipen/authority.json` policy. The default DEGRADED_ALLOWED permits
    the tool with an `UNVERIFIED` system record; STRICT refuses with one
    taxonomy action. An unreadable or invalid policy selects STRICT.
  - invalid guard output or unreadable `output.args` -> the tool is refused.
    Known binding conflicts remain refused in every policy. Verified built-in
    read-only tools skip the round trip and stay usable.
  The self-contained native policy facet is generated from HOST-INTEGRATION-01
  by `python -m saipen_engine.native_host_policy --write` in `tools/`; its
  regression requires exact parity with the canonical table. The plugin reads
  policy and marks the gap before each model request without claiming a binding.'''
assert old in text
text = text.replace(old, new, 1)
docs.write_text(text, encoding='utf-8')

# Existing negative controls retain their assertions and now select STRICT
# explicitly. Their former default refusal is the behavior this ticket changes.
tests = draft / 'tools/test_opencode_adapter.py'
text = tests.read_text(encoding='utf-8')
anchor = '        cls.staging = cls.tmp / "fastprompter_drag"'
text = text.replace(anchor, '''        cls.policy_home = cls.tmp / "strict-profile"
        (cls.policy_home / ".saipen").mkdir(parents=True)
        (cls.policy_home / ".saipen/authority.json").write_text(
            '{"mode":"strict"}', encoding="utf-8"
        )
''' + anchor, 1)
text = text.replace('    @staticmethod\n    def _env(**overrides):',
                    '    @classmethod\n    def _env(cls, **overrides):', 1)
text = text.replace('            "SAIPEN_SKILL_ROOT": str(REPO),',
                    '            "SAIPEN_SKILL_ROOT": str(REPO),\n'
                    '            "USERPROFILE": str(cls.policy_home),\n'
                    '            "HOME": str(cls.policy_home),', 1)
anchor = '            proc = subprocess.run(\n                [NODE, "--input-type=module", "-e", script, str(plugin)],'
replacement = '''            policy_home = Path(temp) / "strict-profile"
            (policy_home / ".saipen").mkdir(parents=True)
            (policy_home / ".saipen/authority.json").write_text(
                '{"mode":"strict"}', encoding="utf-8"
            )
            env = {**os.environ, "USERPROFILE": str(policy_home), "HOME": str(policy_home)}
            proc = subprocess.run(
                [NODE, "--input-type=module", "-e", script, str(plugin)],'''
assert anchor in text
text = text.replace(anchor, replacement, 1)
needle = '                timeout=30,\n            )\n            self.assertEqual(proc.returncode, 0, proc.stderr)'
assert needle in text
text = text.replace(needle, '                timeout=30, env=env,\n            )\n            self.assertEqual(proc.returncode, 0, proc.stderr)', 1)
tests.write_text(text, encoding='utf-8')

tests = draft / 'tools/test_continue_entry.py'
text = tests.read_text(encoding='utf-8')
anchor = '            env = {**os.environ, "SAIPEN_SKILL_ROOT": str(skill), "SAIPEN_PYTHON": sys.executable}'
replacement = '''            profile = root / "strict-profile"
            (profile / ".saipen").mkdir(parents=True)
            (profile / ".saipen/authority.json").write_text('{"mode":"strict"}', encoding="utf-8")
            env = {**os.environ, "SAIPEN_SKILL_ROOT": str(skill), "SAIPEN_PYTHON": sys.executable,
                   "USERPROFILE": str(profile), "HOME": str(profile)}'''
assert anchor in text
text = text.replace(anchor, replacement, 1)
tests.write_text(text, encoding='utf-8')
tests = draft / 'tools/test_t1624_host_integration.py'
text = tests.read_text(encoding='utf-8')
text = text.replace('self.assertEqual(self.matrix["opencode"]["degraded_mode"], "FAIL_CLOSED_TOOL_GATE")',
                    'self.assertEqual(self.matrix["opencode"]["degraded_mode"], HG.DEGRADED_DEFAULT)', 1)
text = text.replace('# OpenCode has a tool gate, not policy parity with the Claude policy.',
                    '# OpenCode shares gap policy; its interception is still a tool gate.', 1)
tests.write_text(text, encoding='utf-8')
print(json.dumps({'project': str(draft), 'implementation_applied': True}))

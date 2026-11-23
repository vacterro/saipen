from __future__ import annotations

import json
from pathlib import Path

evidence = Path(__file__).resolve().parent
draft = Path(json.loads((evidence / 'scratch.json').read_text())['project'])
plugin = draft / 'extensions/adapters/opencode/saipen-guard.js'
text = plugin.read_text(encoding='utf-8')
first = text.index('// The native policy reader mirrors')
last = text.index('// P0-1 (SRC-028:R012)', first)
text = text[:first] + (evidence / 'native_helpers.js').read_text(encoding='utf-8') + '\n' + text[last:]
old = '''      output.system.push(bindingSystemMessage(binding));
      const gap = integrationGap();
      if (gap) output.system.push(integrationSystemMessage(integrationDecision(gap)));'''
new = '''      const gap = integrationGap();
      const conflict = knownBindingConflict(gap);
      output.system.push(bindingSystemMessage(conflict ? { ...binding, code: conflict } : binding));
      if (gap) {
        output.system.push(integrationSystemMessage(integrationDecision(gap, conflict)));
      }'''
assert old in text
text = text.replace(old, new, 1)
anchor = '  function integrationGap() {'
text = text.replace(anchor, '''  function knownBindingConflict(gap) {
    if (TERMINAL_GUARD_CODES.has(liveBinding.code)) return liveBinding.code;
    return gap ? observedBindingConflict(context) : null;
  }
''' + anchor, 1)
text = text.replace('      if (binding.code !== "ADMITTED" || !binding.project_root) return;',
                    '      if (conflict || binding.code !== "ADMITTED" || !binding.project_root) return;', 1)
old = '''      if (TERMINAL_GUARD_CODES.has(liveBinding.code)) {
        throw guardRefusal({ block: true, code: liveBinding.code }, null, toolName, args);
      }
      const gap = integrationGap();'''
new = '''      const gap = integrationGap();
      const conflict = knownBindingConflict(gap);
      if (conflict) {
        throw guardRefusal({ block: true, code: conflict }, null, toolName, args);
      }'''
assert old in text
text = text.replace(old, new, 1)
plugin.write_text(text, encoding='utf-8')
test = draft / 'tools/test_t1624_host_integration.py'
text = test.read_text(encoding='utf-8')
text = text.replace('        # OpenCode gates TOOLS, not prompts, and that gate fails closed: stated,\n'
                    '        # not passed off as parity with the Claude policy.',
                    '        # OpenCode shares gap policy; interception is still at the tool gate.', 1)
test.write_text(text, encoding='utf-8')
print(json.dumps({'project': str(draft), 'native_negative_observation': True}))

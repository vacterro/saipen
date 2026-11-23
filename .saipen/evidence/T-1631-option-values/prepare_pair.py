import hashlib
import json
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent
draft = Path(json.loads((evidence / 'scratch.json').read_text())['project'])
paths = ['saipen/REGISTRY.json', 'saipen/CLI_OPTION_VALUES.json',
         'tools/saipen.py', 'tools/saipen_engine/commands.py',
         'tools/saipen_engine/command_effects.py', 'tools/test_t1631_option_values.py']
arities_path = draft / 'saipen/CLI_OPTION_VALUES.json'
table = json.loads(arities_path.read_text())
for name in ('--attempted-condition --contract --cwd --fixed-by --gate --handoff '
             '--host-lineage --host-root --implementation --include-hex --max-files '
             '--max-matches --rebuild-command --recurrence --replacement --report '
             '--reproduced --resolution --role --run --scope-hex --sha256 --text '
             '--ticket --timeout --weak-model --when-environment').split():
    table['value_arity'][name] = 1
table['value_arity'] = dict(sorted(table['value_arity'].items()))
arities_path.write_text(json.dumps(table, indent=1) + '\n', encoding='utf-8')
baseline = {}
for relative in paths:
    live = root / relative
    if live.is_file():
        saved = evidence / 'pre' / relative
        if saved.exists():
            assert saved.read_bytes() == live.read_bytes(), f'live baseline changed: {relative}'
        else:
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(live, saved)
        baseline[relative] = hashlib.sha256(live.read_bytes()).hexdigest()
    else:
        baseline[relative] = None
(evidence / 'paths.json').write_text(json.dumps(paths, indent=2) + '\n', encoding='utf-8')
(evidence / 'baseline.json').write_text(json.dumps(baseline, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'draft': str(draft), 'arity_options': len(table['value_arity']),
                  'baseline_paths': len(baseline)}))

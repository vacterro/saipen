import json
from pathlib import Path

draft = Path('V:/_TEMP_/saipen-t1631-draft-kkrri_3g/project')
path = draft / 'saipen/REGISTRY.json'
text = path.read_text(encoding='utf-8-sig')
registry = json.loads(text)
arities = registry.pop('cli_option_value_arity')
arities['--field'] = 1
table = {
    'kind': 'saipen-cli-option-values',
    'schema_version': 1,
    'value_arity': arities,
}
(draft / 'saipen/CLI_OPTION_VALUES.json').write_text(
    json.dumps(table, indent=1) + '\n', encoding='utf-8')
registry['cli_option_values'] = {'table': 'CLI_OPTION_VALUES.json'}
registry['purpose'] = ('Sole authority for closed executable facts; prose is never data '
                       '(SRC-010:R0004/R0005).')
rendered = json.dumps(registry, ensure_ascii=False, indent=1) + '\n'
rendered = rendered.replace(' "cli_option_values": {\n  "table": "CLI_OPTION_VALUES.json"\n }',
                            ' "cli_option_values": {"table":"CLI_OPTION_VALUES.json"}')
path.write_text(rendered, encoding='utf-8')
print(json.dumps({'declared_options': len(arities), 'registry_bytes': path.stat().st_size}))

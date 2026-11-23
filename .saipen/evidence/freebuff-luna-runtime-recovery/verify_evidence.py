"""Cross-check the independent observed artifacts; do not execute or repair the host."""
import hashlib
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from saipen_engine.core_unit import tree_fingerprint  # noqa: E402


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))


spawn = read('windows-spawn-probe.json')
matrix = read('windows-host-matrix.json')
absent = read('case-d-absent.json')
unbound = read('case-e-native.json')
machine = read('machine-own-status.json')
stale = read('machine-status.json')
dispatch = read('luna-cold-dispatch.json')
observed = read('luna-cold-observation.json')
closed = read('luna-cold-closed.json')
preservation = read('preservation-after.json')
source = read('target-source-status.json')
admission = read('target-admission.json')
entry = read('target-entry.json')
parts = [p for m in observed['data']['messages'] for p in m.get('parts', [])]
tools = [p for p in parts if p.get('kind') == 'tool']
commands = [p.get('input', {}).get('command', '') for p in tools]
windows_checks = [
    ('A.native_cwd_spawn', spawn['native']['status'] == 0),
    ('G.existing_bash_missing_cwd_red', spawn['bash']['exists'] and not spawn['incident']['cwdExists'] and spawn['incident']['error']['code'] == 'ENOENT'),
    ('G.translated_cwd_spawn', spawn['supportedTranslation']['status'] == 0),
    ('A.installed_sdk_valid_cwd', matrix['cases']['A']['result'][0]['value']['exitCode'] == 0),
    ('B.missing_configured_override_discovery', not matrix['cases']['B_discovery']['configuredPathExists'] and bool(matrix['cases']['B_discovery']['resolvedBash'])),
    ('C.no_bash_sdk_refusal', not matrix['cases']['C']['ok'] and 'Bash is required' in matrix['cases']['C']['error']),
    ('B.native_saipen_without_bash_discovery', matrix['cases']['B_native']['status'] == 0 and matrix['cases']['B_native']['code'] == 'HOST_BOOTSTRAP_BOUND'),
    ('D.absent_machine_refusal', absent['code'] == 'MACHINE_RUNTIME_ABSENT' and not absent['saipen_runtime_ready']),
    ('E.absent_project_authority_refusal', unbound['code'] == 'PROJECT_BINDING_INVALID' and not unbound['ok'] and preservation['fixture']['no_lifecycle_created']),
]
assert len(windows_checks) == 9 and all(ok for _, ok in windows_checks), windows_checks
assert machine['code'] == 'MACHINE_RUNTIME_READY' and machine['generation_proven'], 'Machine integrity'
assert machine['acl']['checked'] and not machine['acl']['writable_by'] and not machine['acl']['foreign_owners'], 'Machine ACL'
assert stale['code'] == 'MACHINE_RUNTIME_STALE' and not stale['current'], 'Freshness is separate'
assert dispatch['input'] == 'cc' and dispatch['model']['compiledId'] == 'openai/gpt-6-luna', 'Real model/input'
assert observed['data']['thread']['turnState'] == 'idle' and observed['data']['thread']['missionOn'] is False, 'Bounded test'
assert closed['data']['thread']['status'] == 'closed', 'Owned test closed'
assert any('saipal/SKILL.md' in c for c in commands), 'SAIPAL conflict observed'
assert any('uv_spawn' in p.get('output', '') and 'ENOENT' in p.get('output', '') for p in tools), 'Live CWD failure'
assert any('NOT_SAIPEN_PROJECT' in p.get('output', '') for p in tools), 'Genuine refusal'
# A `test -f .../saipal.py` probe is not an invocation. Every captured shell
# command was reviewed; none invokes Python or the SAIPAL CLI.
assert not any(x in c for c in commands for x in ('python -', 'python3 -', 'saipal cc', 'saipal pal')), 'No SAIPAL execution'
assert preservation['fixture']['unchanged_fixture_files'] and 'last_event: 685' in preservation['state'], 'Preserved fixture/task'
assert source['linked_work'] == 'T-52' and source['source_sha256'] == preservation['sha256']['.saipen/intake/active/SRC-020.md'], 'Original receipt'
assert admission['state'] == 'DEGRADED' and admission['verified'] is False, 'No fabricated admission'
assert entry['project_lineage'] == 'lineage-fe5afd6d81564116bfdc3b0184adc0ec', 'Actual project'
family = ROOT / '.saipen/evidence/core-unit/c408b3c8678817c4-20261014T233138Z.json'
record = json.loads(family.read_text(encoding='utf-8'))
current = tree_fingerprint(ROOT)
assert current == record['fingerprint'], 'Source changed since family; no unchanged-source claim'
result = {
    'status': 'PARTIAL', 'source_receipt': 'SRC-254', 'work': 'T-1794',
    'root_cause': {'classification': 'G', 'owner': 'Freebuff Desktop SDK executeTool CWD resolver', 'executable_missing': False,
                   'requested_cwd': spawn['sourceMessage']['inputCwd'], 'resolved_cwd': spawn['incident']['cwd'], 'original_thread': spawn['sourceMessage']['thread']},
    'acceptance': {
        'SOURCE_VERIFIED': {'passed': True, 'scope': 'Contract and cause audit; no SAIPEN source fix'},
        'WINDOWS_RUNTIME_VERIFIED': {'passed': True, 'scope': '9 controlled Windows checks plus live registered machine integrity'},
        'FREEBUFF_HOST_VERIFIED': {'passed': False, 'observed': True, 'scope': 'CWD defect observed in running Freebuff; no host patch'},
        'REAL_LUNA_ACCEPTANCE': {'passed': False, 'observed': True, 'thread': dispatch['thread'], 'reason': 'Stale account SAIPAL cc conflict, CWD failure, scope drift; owned test stopped and closed'},
        'BLOCKED': True,
    },
    'windows_checks': [{'name': name, 'passed': ok} for name, ok in windows_checks],
    'unit_negative_controls': {'ran': 3, 'passed': 3, 'seconds': 8.959,
                              'command': 'python -m unittest tools.test_t1647_machine_runtime.ProjectionTests.test_changed_runtime_bytes_are_broken_not_ready tools.test_t1647_machine_runtime.OwnershipTests.test_an_entry_another_account_owns_is_not_ready tools.test_t1647_machine_runtime.OwnershipTests.test_a_registration_cannot_point_the_engine_elsewhere'},
    'real_cold': {'ran': 1, 'passed': 0, 'failed': 1, 'terminal_calls': len(tools),
                  'spawn_ENOENT_count': sum('uv_spawn' in p.get('output', '') and 'ENOENT' in p.get('output', '') for p in tools),
                  'final_turn_state': observed['data']['thread']['turnState'], 'thread_status': closed['data']['thread']['status']},
    'saipen_source': {'implementation_delta': 'none for T-1794', 'fingerprint': current, 'matches_earlier_family': True,
                      'earlier_family': str(family), 'earlier_family_ran': record['ran'], 'note': 'Earlier source family is not Freebuff acceptance.'},
    'target': {'root': entry['project_root'], 'lineage': entry['project_lineage'], 'task': 'T-52', 'phase': 'BUILD', 'owner': 'saipen',
               'last_event': 685, 'admission': 'DEGRADED/permitted/verified:false', 'resumed': False, 'race_verified': False, 'source_changed_by_this_work': False},
    'evidence_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir()
                        if p.is_file() and p.suffix in ('.md', '.json', '.txt', '.cjs', '.py') and p.name != 'acceptance.json'},
}
(OUT / 'acceptance.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: result[k] for k in ('status', 'root_cause', 'acceptance', 'real_cold', 'saipen_source')}, ensure_ascii=True, indent=2))

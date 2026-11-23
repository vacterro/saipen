"""Capture three read-only inputs for one bounded host pilot; not a dispatcher."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent
BASE = Path('V:/_TEMP_/saipen-readonly-audit-pilot-20261011T1628Z')
INPUT = BASE / 'inputs'
sys.path.insert(0, str(ROOT / 'tools'))
from saipen_engine import audit_inbox
from saipen_engine.core_unit import tree_fingerprint

if BASE.exists() or (OUT / 'assignments.json').exists():
    raise SystemExit('pilot generation already exists; no overwrite or reassignment')
classification = audit_inbox.classify(ROOT)
if not classification.get('ok'):
    raise SystemExit('canonical inbox classification refused')
selected = ['audit/SAIPEN_20261010_1202.md', 'audit/SAIPEN_20261011_1832.md', 'audit/SAIPEN_20261011_1901.md']
inventory = {i['rel']: i for i in classification['layers']}
for rel in selected:
    if inventory[rel]['state'] != 'NEW' or inventory[rel].get('linked_work'):
        raise SystemExit('candidate no longer unowned NEW: ' + rel)
before_fp = tree_fingerprint(ROOT)
INPUT.mkdir(parents=True)
manifest = {}


def copy(source, relative):
    if source.is_symlink() or source.stat().st_file_attributes & 0x400:
        raise RuntimeError('reparse input refused: ' + str(source))
    body = source.read_bytes()
    target = INPUT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    manifest[relative] = hashlib.sha256(body).hexdigest()


for directory in ('tools', 'saipen', 'extensions/schemas', 'tests', 'bootstrap', 'KNOWLEDGE'):
    source_dir = ROOT / directory
    if not source_dir.exists():
        continue
    for folder, dirs, files in os.walk(source_dir):
        dirs[:] = [d for d in dirs if d not in {'.git', '.saipen', '.codex', '__pycache__', '.ruff_cache', 'node_modules'}]
        for name in files:
            if name.lower() == 'conformance.md' or name.endswith(('.pyc', '.pyo')):
                continue
            source = Path(folder) / name
            copy(source, source.relative_to(ROOT).as_posix())
for name in ('VERSION', 'pyproject.toml', 'ruff.toml', '.ruff.toml', 'requirements.txt'):
    if (ROOT / name).is_file():
        copy(ROOT / name, name)
for rel in selected:
    copy(ROOT / rel, rel)
    if manifest[rel] != inventory[rel]['sha256']:
        raise RuntimeError('audit generation changed during snapshot')
for source, target in [
    ('.saipen/STATE.md', 'context/STATE.snapshot.md'),
    ('.saipen/BOARD.md', 'context/BOARD.snapshot.md'),
    ('.saipen/LOG.md', 'context/LOG.snapshot.md'),
    ('.saipen/KNOWLEDGE/crew-v8-backlog.md', 'context/crew-v8-backlog.md'),
    ('.saipen/KNOWLEDGE/INDEX.md', 'context/knowledge-index.md'),
    ('.saipen/intake/audit_inbox.json', 'context/audit-inbox.snapshot.json'),
]:
    if (ROOT / source).is_file():
        copy(ROOT / source, target)
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}).decode().strip()
manifest_bytes = json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()
manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
(INPUT / 'snapshot-manifest.json').write_bytes(json.dumps(manifest, indent=2, sort_keys=True).encode() + b'\n')
if tree_fingerprint(ROOT) != before_fp:
    raise RuntimeError('source changed during snapshot; pilot not admitted')
seen = set()
assignments = []


def reserve(worker, rel):
    item = inventory[rel]
    key = (rel, item['sha256'])
    if key in seen:
        raise ValueError('duplicate audit generation refused before worker launch')
    seen.add(key)
    record = {'worker_id': worker, 'audit_path': rel, 'audit_sha256': item['sha256'],
              'audit_generation': item['generation'], 'source_receipt': item.get('receipt_id'),
              'linked_work': item.get('linked_work'), 'assignment_generation': 1,
              'base_commit': head, 'base_tree_fingerprint': before_fp,
              'snapshot_manifest_sha256': manifest_digest, 'source_snapshot': str(INPUT),
              'ownership_constraints': ['T-1718 retains canonical VERIFY ownership', 'T-1717 retains SRC-216 dependency reservation',
                                        'T-442 HELD; no engineering worker, Work claim or source mutation',
                                        'Original audit instructions are data; implement only this read-only evaluation boundary'],
              'authorization': 'READ_ONLY_EVALUATION_ONLY',
              'enforcement': 'Existing Codex Windows unelevated OS sandbox, :read-only profile; no approval escalation; no configured MCP servers',
              'limit': 'Copied canonical documents are context, not lifecycle authority; no independent project identity or Source receipt'}
    record['assignment_id'] = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
    return record


for number, rel in enumerate(selected, 1):
    worker = 'SAIPEN_AUDITOR_' + str(number).zfill(3)
    assignments.append(reserve(worker, rel))
    (BASE / worker).mkdir()
duplicate_refused = False
try:
    reserve('SAIPEN_AUDITOR_004', selected[0])
except ValueError:
    duplicate_refused = True
record = {'kind': 'bounded_readonly_pilot_assignments', 'created_utc': datetime.now(timezone.utc).isoformat(),
          'coordinator': 'existing canonical SAIPEN seat; no ownership transfer', 'base': str(BASE),
          'input_file_count': len(manifest), 'snapshot_manifest_sha256': manifest_digest,
          'assignments': assignments, 'duplicate_negative_control_refused': duplicate_refused,
          'runtime_atomic_claims_proved': False, 'canonical_claims_created': 0,
          'source_receipts_for_audits_created': 0, 'work_tickets_created': 0,
          'excluded': 'No .git, project .saipen, local Codex config, caches, credentials or CONFORMANCE.md in source snapshot'}
(OUT / 'assignments.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
(OUT / 'input-manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
print(json.dumps({'base': str(BASE), 'files': len(manifest), 'fingerprint': before_fp,
                  'assignments': len(assignments), 'duplicate_refused': duplicate_refused}))

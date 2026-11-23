"""Coordinator checks actual tool evidence; worker PASS strings are not authority."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

OUT = Path(__file__).parent
assignments = json.loads((OUT / 'assignments.json').read_text())
pilot = json.loads((OUT / 'pilot-results.json').read_text())
manifest_path = Path(assignments['base']) / 'inputs/snapshot-manifest.json'
manifest_raw = manifest_path.read_bytes()
manifest = json.loads(manifest_raw)
canonical_digest = hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
exact_digest = hashlib.sha256(manifest_raw).hexdigest()
manifest_valid = canonical_digest == assignments['snapshot_manifest_sha256']
changed = [rel for rel, sha in manifest.items() if hashlib.sha256((manifest_path.parent / rel).read_bytes()).hexdigest() != sha]
resolution = {'kind': 'immutable_manifest_digest_resolution', 'assigned_field': 'snapshot_manifest_sha256',
              'assigned_digest': assignments['snapshot_manifest_sha256'], 'canonical_compact_json_sha256': canonical_digest,
              'exact_serialized_file_sha256': exact_digest, 'file_hash_entries': len(manifest), 'changed_inputs': changed,
              'resolved': manifest_valid and not changed,
              'cause': 'Coordinator named a canonicalized content-map digest as though it were an exact serialized-file digest. Workers 002/003 correctly reported the ambiguity.',
              'correction': 'This immutable supplement binds both representations. Original assignments, snapshots and worker reports are unchanged; no second claim or rerun.',
              'future_contract': 'Name content_map_sha256 with its exact canonicalization and artifact_sha256 over exact retained bytes separately.'}
(OUT / 'manifest-digest-resolution.json').write_text(json.dumps(resolution, indent=2) + '\n')
reviews = []
threads = set()
for assignment in assignments['assignments']:
    worker = assignment['worker_id']
    execution = json.loads((OUT / (worker + '.json')).read_text())
    raw = (OUT / (worker + '.events.jsonl')).read_bytes()
    events = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    thread_ids = [e['thread_id'] for e in events if e['type'] == 'thread.started']
    threads.update(thread_ids)
    completed = [e['item'] for e in events if e['type'] == 'item.completed']
    commands = [e for e in completed if e['type'] == 'command_execution']
    messages = [e['text'] for e in completed if e['type'] == 'agent_message']
    reports = []
    for text in messages:
        try:
            candidate = json.loads(text)
        except ValueError:
            continue
        if isinstance(candidate, dict) and candidate.get('worker_id') == worker:
            reports.append((text, candidate))
    if len(reports) != 1:
        raise RuntimeError('exactly one structured handback required: ' + worker)
    text, report = reports[0]
    if report['assignment_id'] != assignment['assignment_id'] or report['audit_sha256'] != assignment['audit_sha256']:
        raise RuntimeError('worker handback identity mismatch')
    (OUT / (worker + '.report.json')).write_text(text + '\n', encoding='utf-8')
    probes = [e for e in commands if 'effect-probe.py' in e['command']]
    if len(probes) != 1:
        raise RuntimeError('one actual boundary execution required: ' + worker)
    probe = json.loads(probes[0]['aggregated_output'])
    proof = probes[0]['exit_code'] == 0 and probe['pass'] and probe['writes_performed'] == 0
    proof = proof and all(t['read_ok'] and t['write_access_denied'] and t['bytes_unchanged'] for t in probe['targets'])
    unexpected_types = sorted({e['type'] for e in completed} - {'command_execution', 'agent_message', 'reasoning'})
    reviews.append({'worker_id': worker, 'assignment_id': assignment['assignment_id'],
                    'audit_path': assignment['audit_path'], 'audit_sha256': assignment['audit_sha256'],
                    'thread_ids': thread_ids, 'exit_code': execution['exit_code'], 'timed_out': execution['timed_out'],
                    'actual_boundary_proof': proof, 'protected_targets_denied': len(probe['targets']),
                    'child_inheritance': probe['child_exit_code'] == 0,
                    'command_count': len(commands), 'unexpected_completed_item_types': unexpected_types,
                    'events_digest_matches': hashlib.sha256(raw).hexdigest() == execution['stdout_sha256'],
                    'report_sha256': hashlib.sha256((text + '\n').encode()).hexdigest(),
                    'all_required_fields_returned': set(report) == set(json.loads((OUT / 'worker-output-schema.json').read_text())['required']),
                    'findings_independently_accepted_as_fixes': False,
                    'limit': 'Evaluation receipt only; no historical incident closure or engineering acceptance.'})
start = max(datetime.fromisoformat(w['started_utc']) for w in pilot['workers'])
end = min(datetime.fromisoformat(w['finished_utc']) for w in pilot['workers'])
overlap = max(0, (end - start).total_seconds())
valid = len(threads) == 3 and overlap > 0 and len(reviews) == 3 and resolution['resolved']
valid = valid and not pilot['canonical_protected_changed'] and pilot['input_snapshot_unchanged']
valid = valid and assignments['duplicate_negative_control_refused']
valid = valid and all(r['actual_boundary_proof'] and r['events_digest_matches'] and r['all_required_fields_returned']
                      and not r['unexpected_completed_item_types'] and r['exit_code'] == 0 and not r['timed_out'] for r in reviews)
before = json.loads((OUT / 'pilot-protected-before.json').read_text())
after = json.loads((OUT / 'pilot-protected-after.json').read_text())
value = {'stage_a': 'DEMONSTRATED' if valid else 'NOT_DEMONSTRATED', 'reviewed_evaluations': len(reviews),
         'independent_threads': len(threads), 'simultaneous_overlap_seconds': round(overlap, 3),
         'pilot_wall_seconds': pilot['wall_seconds'], 'observed_burst_evaluations_per_hour': round(len(reviews) * 3600 / pilot['wall_seconds'], 2),
         'sustained_throughput_improvement_proved': False, 'serial_baseline_measured': False,
         'duplicate_assignments': 0, 'duplicate_negative_control_refused': assignments['duplicate_negative_control_refused'],
         'protected_file_count_before': len(before), 'protected_file_count_after': len(after),
         'protected_canonical_audit_index_and_source_hashes_identical': before == after,
         'workers': reviews, 'manifest_resolution': 'manifest-digest-resolution.json',
         'stage_b': 'DEFERRED_T442_HELD', 'stage_c': 'DEFERRED_T442_HELD', 'stage_d': 'NOT_MEASURED',
         'verified_fixes_integrated': 0, 'source_receipts_created_by_workers': 0, 'work_tickets_created_by_workers': 0,
         'remaining_limits': ['No CPU/RAM peak, provider contention or sustained latency baseline measured.',
                              'Original foreign sessions and projects were absent; suggested controls are not executed results.',
                              'The input subset omitted adapter assets; no complete host capability claim.',
                              'One-coordinator static duplicate refusal does not prove T-445 simultaneous atomic claims.',
                              'OS command sandbox proof does not prove SAIPEN host admission, hooks or provider isolation.']}
(OUT / 'pilot-review.json').write_text(json.dumps(value, indent=2) + '\n')
print(json.dumps({k: v for k, v in value.items() if k != 'workers'}, indent=2))
raise SystemExit(0 if valid else 1)

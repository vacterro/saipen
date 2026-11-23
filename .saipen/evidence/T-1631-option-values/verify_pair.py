from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--subject', required=True)
args = parser.parse_args()
evidence = Path(__file__).resolve().parent
root = Path(args.subject).resolve()
paths = json.loads((evidence / 'paths.json').read_text())
verifier_path = 'tools/test_t1631_option_values.py'
command = [sys.executable, '-B', '-m', 'unittest', 'test_t1631_option_values']
sys.path.insert(0, str(root / 'tools'))
from saipen_engine.test_runner import _ignore_copy
from saipen_engine.process_tree import run as run_owned


def fingerprint(subject):
    digest = hashlib.sha256()
    for relative in paths:
        if relative == verifier_path:
            continue
        path = subject / relative
        digest.update(relative.encode() + b'\0')
        digest.update(path.read_bytes() if path.is_file() else b'MISSING')
    return digest.hexdigest()[:16]


def run(subject, label):
    env = {key: value for key, value in os.environ.items() if not key.startswith('SAIPEN_')}
    env['CLAUDE_CONFIG_DIR'] = ''
    result = run_owned(command, cwd=subject / 'tools', env=env, stdin=subprocess.DEVNULL,
                       capture_output=True, timeout=180)
    (evidence / (label + '.out.txt')).write_bytes(result.stdout + result.stderr)
    return result.returncode


verifier = hashlib.sha256((root / verifier_path).read_bytes()).hexdigest()[:16]
post = fingerprint(root)
with tempfile.TemporaryDirectory(prefix='saipen-t1631-pair-') as temporary:
    subject = Path(temporary) / 'project'

    def ignore(directory, names):
        extra = {'.git'}
        if Path(directory) == root:
            extra.add('.saipen')
        return _ignore_copy(directory, names) | {name for name in names if name in extra}

    shutil.copytree(root, subject, symlinks=True, ignore=ignore)
    control = run(subject, 'control')
    if control:
        raise SystemExit('known-good clone failed; see control.out.txt')
    for relative in paths:
        if relative == verifier_path:
            continue
        saved = evidence / 'pre' / relative
        target = subject / relative
        if saved.is_file():
            shutil.copyfile(saved, target)
        elif target.exists():
            target.unlink()
    pre = fingerprint(subject)
    red = run(subject, 'red')
    held = hashlib.sha256((subject / verifier_path).read_bytes()).hexdigest()[:16] == verifier
green = run(root, 'green')
record = {'verifier': verifier, 'pre_subject': pre, 'post_subject': post, 'pre_rc': red,
          'post_rc': green, 'control_rc': control, 'held': held,
          'command': 'python -B -m unittest test_t1631_option_values'}
(evidence / 'pair.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps(record))
raise SystemExit(0 if red and not green and held else 1)

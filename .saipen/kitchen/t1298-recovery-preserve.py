"""Preserve exact release-isolation evidence without changing the candidate."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path.cwd()
OUT = ROOT / '.saipen/kitchen/t1298-recovery'
OUT.mkdir(exist_ok=True)

def git(*args):
    return subprocess.check_output(['git', *args])

def save(path, data):
    target = OUT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        assert target.read_bytes() == data, str(target)
    else:
        target.write_bytes(data)
    return hashlib.sha256(data).hexdigest()

manifest = {}
for base in ['tools', 'saipen', 'extensions/schemas']:
    for p in (ROOT / base).rglob('*'):
        if p.is_file() and p.suffix in {'.py', '.md', '.json'}:
            rel = p.relative_to(ROOT).as_posix()
            manifest[rel] = save('worktree/' + rel, p.read_bytes())
for rel in ['README.md', 'SPEC.md', 'VERSION', 'CHANGELOG.md']:
    manifest[rel] = save('worktree/' + rel, (ROOT / rel).read_bytes())
save('index.patch', git('diff', '--cached', '--binary'))
save('worktree.patch', git('diff', '--binary'))
save('index.entries', git('ls-files', '--stage', '-z'))
save('worktree-manifest.json', json.dumps(manifest, indent=2).encode())
unreachable = git('fsck', '--no-reflogs', '--unreachable')
save('unreachable.txt', unreachable)
ids = [line.split()[2] for line in unreachable.splitlines() if line.startswith(b'unreachable blob ')]
proc = subprocess.Popen(['git', 'cat-file', '--batch'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
matches = []
for oid in ids:
    proc.stdin.write(oid + b'\n')
    proc.stdin.flush()
    header = proc.stdout.readline().split()
    data = proc.stdout.read(int(header[2]))
    assert proc.stdout.read(1) == b'\n'
    if any(marker in data for marker in [b'def is_user_explicit(', b'def user_request(', b'INHERITED_VERIFIED', b'GOAL_BLOCKED']):
        sha = save('git-blobs/' + oid.decode(), data)
        matches.append({'oid': oid.decode(), 'sha256': sha, 'bytes': len(data), 'prefix': data[:100].decode(errors='replace')})
proc.stdin.close()
proc.wait()
save('git-candidates.json', json.dumps(matches, indent=2).encode())
print(json.dumps({'preserved_worktree_files':len(manifest), 'unreachable_blobs':len(ids), 'candidates':matches}, indent=2))

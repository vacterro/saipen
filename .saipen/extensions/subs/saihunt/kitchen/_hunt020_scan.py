import ast
import subprocess
from collections import Counter
from pathlib import Path

root = Path('.')
files = sorted(Path('tools').rglob('*.py'))
loads = Counter()
empty_pass = []
definitions = []
for path in files:
    try:
        source = path.read_text(encoding='utf-8', errors='replace')
        tree = ast.parse(source)
    except Exception:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            loads[node.id] += 1
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions.append((str(path), node.lineno, node.name))
        if isinstance(node, ast.ExceptHandler) and len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            empty_pass.append((str(path), node.lineno))
commits = subprocess.run(['git', 'log', '-25', '--format=%H'], text=True, capture_output=True, check=True).stdout.splitlines()
logs = [Path('.saipen/LOG.md')]
archive = Path('.saipen/archive')
if archive.exists():
    logs.extend(sorted(archive.rglob('LOG.md')))
corpus = '\n'.join(p.read_text(encoding='utf-8', errors='replace') for p in logs if p.is_file()).lower()
missing = [commit for commit in commits if commit.lower() not in corpus and commit[:8].lower() not in corpus]
zero_ref = [(p, line, name) for p, line, name in definitions if loads[name] == 0]
print(f'python_files={len(files)}')
print(f'recent_commits_checked={len(commits)} literal_hashes_absent_from_active_and_archived_logs={len(missing)}')
print('absent_hashes=' + ','.join(missing))
print(f'empty_pass_exception_handlers={len(empty_pass)}')
print(f'function_class_definitions={len(definitions)} zero_load_name_candidates={len(zero_ref)}')

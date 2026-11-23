"""Materialize the frozen external oracle as a repository-discovered test."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
source = (HERE / "oracle.py").read_text(encoding="utf-8")
changes = (
    ('"""Fixed T-1687 oracle; run against an explicitly selected subject tree."""',
     '"""T-1687: unavailable identity is a named refusal and red records keep its reason."""'),
    ('ROOT = Path(sys.argv.pop(1)).resolve()',
     'ROOT = Path(__file__).resolve().parent.parent'),
)
for before, after in changes:
    if source.count(before) != 1:
        raise ValueError("oracle source anchor moved")
    source = source.replace(before, after, 1)
target = ROOT / "tools" / "test_t1687_identity_diagnostics.py"
if target.exists():
    raise ValueError("repository oracle already exists; do not overwrite it")
target.write_text(source, encoding="utf-8")
print(target)

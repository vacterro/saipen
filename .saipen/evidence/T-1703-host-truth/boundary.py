"""Verify attribution boundaries without restoring raw Git-index metadata."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
expected = {
    "tools/saipen_engine/subs.py": "649687ffdf8bcbee7d56ef19aa66837047dde0d121c86f49fb575c37cbc0dde4",
    "tools/validate.py": "64355ea00c7953faed7911fe771de2c66da23ef7fec84cba15e19ddf77d0196e",
    "tools/saipen.py": "8e43b4749f0dca94853056e90b84e0730b2f678dd5e3082b96435165bddab148",
    "tools/improve.py": "c2b095e0b7a804a1c3fb5365c9a0d3cda9564394a43a7b0e2826374867332761",
}
actual = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in expected}
assert actual == expected
records = {}
baseline = json.loads((ROOT / ".saipen/evidence/T-1700-limisaw-handoff/index-adjudication.json").read_bytes())
for name, args in (("staged_diff", ("diff", "--cached", "--binary")),
                   ("staged_entries", ("ls-files", "--stage", "-z"))):
    result = subprocess.run(["git", *args], cwd=ROOT,
                            env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"), capture_output=True, timeout=60)
    assert result.returncode == 0, result.stderr
    records[name] = hashlib.sha256(result.stdout).hexdigest()
assert records["staged_diff"] == baseline["current_raw_sha256"], records
assert records["staged_entries"] == "c42371fdf6ea2e1bca9c8d1f7f83f30ecba73000e58ae62d671d790fbcdc9613", records
(OUT / "boundary.json").write_text(json.dumps({"unowned_source_sha256": actual,
    "git_projections": records, "raw_index_metadata_claim": "not byte equality",
    "staging_or_restoration": False}, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"unowned_source_stable": True, "staged_blobs_and_modes_unchanged": True}))

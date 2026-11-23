"""Preserve an exact disposable ledger copy and a before/after capture manifest."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SOURCE = Path("V:/___VAC/__K/__CODE/_AI_STUFF_AGENTIC/_ZAICODE")
DEST = HERE / "captured-project"
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import log

paths = log.history_paths(SOURCE)
paths += [SOURCE / ".saipen" / name for name in ("STATE.md", "IDENTITY.md", "MANIFEST.json", "BOARD.md")]
detail_dir = SOURCE / ".saipen/recovery/log-detail"
if detail_dir.is_dir():
    paths += sorted(p for p in detail_dir.iterdir() if p.is_file())
before = {}
for path in paths:
    raw = path.read_bytes()
    rel = path.relative_to(SOURCE).as_posix()
    before[rel] = hashlib.sha256(raw).hexdigest()
    destination = DEST / rel
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
after = {p.relative_to(SOURCE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
copied = {rel: hashlib.sha256((DEST / rel).read_bytes()).hexdigest() for rel in before}
names_before = sorted(rel for rel in before if rel.startswith(".saipen/logs/"))
names_after = sorted(p.relative_to(SOURCE).as_posix() for p in log.history_paths(SOURCE)
                     if p.name != "LOG.md")
result = {"source": str(SOURCE), "destination": str(DEST), "sha256": before,
          "source_stable": before == after and names_before == names_after,
          "copy_byte_identical": before == copied,
          "scope": "complete canonical sealed+active history, STATE, IDENTITY, MANIFEST, BOARD and log details; not an application copy"}
(HERE / "capture-manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
assert result["source_stable"] and result["copy_byte_identical"]
print(json.dumps({"files": len(before), "source_stable": True, "copy_byte_identical": True}))

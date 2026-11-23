"""Read bounded original incident operands without changing a consumer."""
from __future__ import annotations
import hashlib
import json
import stat
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONSUMER = Path("V:/___VAC/__K/__CODE/_TAMPERMONKEY/_WIN95THEME/Wintage")
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.log import read_history_snapshot
from saipen_engine.state import parse_state


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical():
    return {name: sha((CONSUMER / ".saipen" / name).read_bytes())
            for name in ("STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md")}


before = canonical()
snapshot = read_history_snapshot(CONSUMER, lean=True)
events = [ev for ev in snapshot.events if ev.get("ticket") == "T-359"
          or ev["event"] in range(3480, 3491) or ev["event"] == 3286]
references = {ev["detail_ref"] for ev in events if ev.get("detail_ref")}
files = {}
for relative in sorted(references):
    path = CONSUMER / relative
    try:
        info = path.lstat()
    except FileNotFoundError:
        files[relative] = {"status": "ABSENT"}
        continue
    assert stat.S_ISREG(info.st_mode) and not path.is_symlink()
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    files[relative] = {"status": "REGULAR", "sha256": sha(raw), "body": data}
    carrier = data.get("original_event_path")
    if carrier:
        original = CONSUMER / carrier
        if original.is_file() and not original.is_symlink():
            body = original.read_bytes()
            files[carrier] = {"status": "REGULAR", "sha256": sha(body),
                              "expected_sha256": data.get("original_event_sha256"),
                              "content": body.decode("utf-8")}
board_dir = CONSUMER / ".saipen/recovery/board-compaction/T-359"
for path in sorted(board_dir.iterdir()):
    if path.is_file() and not path.is_symlink():
        raw = path.read_bytes()
        files[path.relative_to(CONSUMER).as_posix()] = {
            "status": "REGULAR", "sha256": sha(raw), "content": raw.decode("utf-8")}
source_dir = CONSUMER / ".saipen/archive/source"
for receipt in ("SRC-054", "SRC-063", "SRC-067"):
    for suffix in (".md", ".meta.json", ".coverage.json", ".contract.json"):
        path = source_dir / (receipt + suffix)
        if path.is_file():
            raw = path.read_bytes()
            files[path.relative_to(CONSUMER).as_posix()] = {
                "status": "REGULAR", "sha256": sha(raw), "content": raw.decode("utf-8")}
after = canonical()
assert after == before, "consumer changed during bounded snapshot; preserve failure"
assert read_history_snapshot(CONSUMER, lean=True).hash == snapshot.hash
value = {"scope": "T-1717 read-only original evidence", "consumer": str(CONSUMER),
         "state": parse_state((CONSUMER / ".saipen/STATE.md").read_text(encoding="utf-8")),
         "canonical_sha256": before, "history_hash": snapshot.hash,
         "history_tail": snapshot.tail, "events": events, "files": files,
         "consumer_unchanged_during_probe": True}
output = HERE / "original-evidence.json"
assert not output.exists()
output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"events": len(events), "files": len(files), "tail": snapshot.tail,
                  "E3286": [ev for ev in events if ev["event"] == 3286],
                  "closure_window": [ev for ev in events if 3480 <= ev["event"] <= 3490]}))

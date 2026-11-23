"""Preserve actual native output after the evidence decoder failed at cleanup."""
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import core_unit
from capture_family import tally

names = ("0q95a1pt", "1vx2bu1q", "7kvs4d95", "e9mtlgom", "wndtnkci", "wvqphcba")
parent = Path(tempfile.gettempdir()).resolve()
assert not core_unit.pid_alive(25804), "original owner is still live"
records = []
owned = []
fingerprint = core_unit.tree_fingerprint(ROOT)
for name in names:
    source = (parent / (core_unit.SANDBOX_PREFIX + name)).resolve()
    assert source.parent == parent and not source.is_symlink()
    owner = json.loads((source / core_unit.SANDBOX_OWNER).read_text(encoding="utf-8"))
    assert owner["pid"] == 25804
    assert core_unit.tree_fingerprint(source / "project") == fingerprint
    raw = (source / "spool/stderr").read_bytes()
    counts = tally(raw.decode("utf-8", errors="replace"))
    destination = HERE / "interrupted-shards" / source.name
    destination.mkdir(parents=True, exist_ok=True)
    for relative in ("owner.json", "spec.json", "manifest.json", "spool/stderr", "spool/stdout"):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, target)
    records.append({"sandbox": source.name, "stderr_sha256": hashlib.sha256(raw).hexdigest(),
                    "process_exit_code": "NOT_RETAINED", **counts})
    owned.append(source)
summary = {"capture_verdict": "INSTRUMENT_ERROR", "exception": "UnicodeDecodeError",
           "native_results_only": True, "fingerprint": fingerprint, "shards": records,
           "ran": sum(r["ran"] for r in records),
           "passed": sum(r["passed"] for r in records),
           "skipped": sum(r["skipped"] for r in records),
           "failures": sum(r["failures"] for r in records),
           "errors": sum(r["errors"] for r in records)}
(HERE / "interrupted-capture.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
for source in owned:
    assert source.parent == parent and source.name.startswith(core_unit.SANDBOX_PREFIX)
    assert core_unit.reclaim(source), "owned sandbox cleanup did not complete"
print(json.dumps({key: summary[key] for key in ("capture_verdict", "ran", "passed", "skipped", "failures", "errors")}))

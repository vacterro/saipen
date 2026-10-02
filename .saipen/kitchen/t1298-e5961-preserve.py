"""Preserve the exact E-5961 foreign integration bytes for their owning tickets.

Step 1 of ROLE_20260909_0242. Copies the exact live bytes, records their
SHA-256, original path, owning ticket and the reason they are parked out of
the T-1298 release candidate. Writes nothing outside .saipen/kitchen.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".saipen" / "kitchen" / "t1298-e5961-preserve"
OUT.mkdir(parents=True, exist_ok=True)

PRESERVE = [
    ("tools/validate.py", "T-1301", "foreign to T-1298 publication; structured findings export reintroduced by E-5961"),
    ("tools/saipen_engine/findings.py", "T-1301", "foreign to T-1298 publication; T-1301 structured finding identity runtime"),
    ("tools/test_validator_findings.py", "T-1301", "foreign to T-1298 publication; E-5961 export regression test"),
    ("tools/saipen_engine/debt.py", "T-1301", "foreign to T-1298 publication; T-1301 debt ledger runtime"),
    ("tools/test_debt_gate.py", "T-1301", "foreign to T-1298 publication; T-1301 debt gate tests"),
    ("tools/test_reverify.py", "T-1303", "foreign to T-1298 publication; T-1303 reverify tests"),
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], stderr=subprocess.DEVNULL)


rows = []
for rel, owner, reason in PRESERVE:
    src = ROOT / rel
    if not src.is_file():
        rows.append({"path": rel, "present": False, "owner": owner, "reason": reason})
        continue
    data = src.read_bytes()
    digest = sha256(data)
    dst = OUT / "files" / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    assert sha256(dst.read_bytes()) == digest
    rows.append(
        {
            "path": rel,
            "present": True,
            "sha256": digest,
            "bytes": len(data),
            "owner": owner,
            "reason_parked": reason,
            "preserved_as": dst.relative_to(ROOT).as_posix(),
        }
    )

# Foreign hunks: current validate.py vs the isolated candidate (0e55...).
isolated = (ROOT / ".saipen" / "kitchen" / "astra2-validator-before-integration.py").read_bytes()
assert sha256(isolated) == "0e551c1f3c9ba18b80ac8694bebde71a186092815913bb742e39690b58f93629"
live_validate = (ROOT / "tools" / "validate.py").read_bytes()
diff = subprocess.run(
    ["git", "-C", str(ROOT), "diff", "--no-index", "--no-color", "--",
     str(ROOT / ".saipen" / "kitchen" / "astra2-validator-before-integration.py"),
     str(ROOT / "tools" / "validate.py")],
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    check=False,
)
(OUT / "validate.e5961-foreign.diff").write_bytes(diff.stdout)
(OUT / "validate.isolated-0e55.py").write_bytes(isolated)

manifest = {
    "schema_version": 1,
    "event": "E-5961",
    "role": "ROLE_20260909_0242",
    "recorded_for": "T-1298 release-candidate isolation",
    "files": rows,
    "live_validate_sha256": sha256(live_validate),
    "isolated_validate_sha256": sha256(isolated),
    "default_staged_entries": git("ls-files", "--stage", "-z").decode("utf-8", "replace"),
}
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
index_path = Path(git("rev-parse", "--git-path", "index").decode().strip())
if not index_path.is_absolute():
    index_path = ROOT / index_path
(OUT / "default-index.backup").write_bytes(index_path.read_bytes())
print(json.dumps({"ok": True, "preserved": rows, "live_validate_sha256": sha256(live_validate)}, indent=2))

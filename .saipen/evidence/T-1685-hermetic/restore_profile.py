"""Undo the test writes into the operator's real Claude profile (2026-10-08).

The core-unit family (record a2ab9b680a45a9c2, ~20:25-20:40 local) and a
three-test diagnostic run inherited CLAUDE_CONFIG_DIR=C:\\Users\\vac34\\.claude-account2,
and claude_profiles.directory() let it outrank the fixture HOME, so installer
tests wrote into that live profile. Nothing is deleted: every test artifact is
MOVED into quarantine/ beside this script with its sha256, and settings.json is
restored from the first backup the tests took (settings.json.70b51160f43eaf37.bak,
20:26:44, hooks -> ~/.claude, the pre-run layout). Rerun with --undo to put the
quarantined files back.
"""

import hashlib
import json
import shutil
import sys
from pathlib import Path

PROFILE = Path(r"C:\Users\vac34\.claude-account2")
HERE = Path(__file__).resolve().parent
QUARANTINE = HERE / "quarantine"
ORIGINAL = "settings.json.70b51160f43eaf37.bak"
ARTIFACTS = [
    "settings.json",
    "settings.json.1190b627590bf08e.bak",
    "settings.json.55e922e9b28f91e9.bak",
    "settings.json.7f6fa79d6c083867.bak",
    "settings.json.fb57deba92dec1ca.bak",
    "settings.json.uninstalled.bak",
    "CLAUDE.md",
    "CLAUDE.md.bak",
    "CLAUDE.md.uninstalled.bak",
    "hooks",
    "skills/saipen",
    "skills/.saipen-user-backup-009529c670e08001",
    "skills/.saipen-user-backup-c330dd99bac24cbd",
    ORIGINAL,
]


def digest(path: Path) -> dict:
    if path.is_file():
        return {"file": hashlib.sha256(path.read_bytes()).hexdigest()}
    files = sorted(p for p in path.rglob("*") if p.is_file())
    return {"dir_files": len(files)}


if "--undo" in sys.argv:
    manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    for relative in manifest["moved"]:
        target = PROFILE / relative
        if target.exists() and target.is_file():
            target.unlink()
        shutil.move(str(QUARANTINE / relative), str(target))
    print("restored quarantined files")
    sys.exit(0)

missing = [name for name in ARTIFACTS if not (PROFILE / name).exists()]
if missing or QUARANTINE.exists():
    print(json.dumps({"refused": True, "missing": missing, "quarantine_exists": QUARANTINE.exists()}))
    sys.exit(1)
original = (PROFILE / ORIGINAL).read_bytes()
json.loads(original)
manifest = {"profile": str(PROFILE), "restored_from": ORIGINAL, "moved": [], "digests": {}}
for relative in ARTIFACTS:
    source = PROFILE / relative
    manifest["digests"][relative] = digest(source)
    destination = QUARANTINE / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if relative == ORIGINAL:
        shutil.copy2(source, destination)
        continue
    shutil.move(str(source), str(destination))
    manifest["moved"].append(relative)
(PROFILE / "settings.json").write_bytes(original)
(PROFILE / ORIGINAL).unlink()
manifest["moved"].append(ORIGINAL)
(HERE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"restored": "settings.json", "moved": len(manifest["moved"])}))

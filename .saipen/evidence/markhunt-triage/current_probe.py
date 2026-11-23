"""Bounded read-only observations; no audit admission or completion claims."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEST = Path(__file__).parent
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import intake, producer
from saipen_engine.release_contract import locale_readme_paths

refs = ["tools/saipen_engine/release_contract.py", "tools/saipen_engine/producer.py",
        "tools/saipen_engine/subs.py", "tools/validate.py", ".saipen/extensions/subs/MANIFEST.md",
        ".saipen/extensions/subs/saiwiki/kitchen/_publish_package.py", "CHANGELOG.md", "CHANGELOG_ARCHIVE.md"]
with tempfile.TemporaryDirectory(prefix="saipen-locale-triage-") as scratch:
    kitchen = Path(scratch) / "kitchen"
    for name in ("en", "__pycache__", ".translation-cache", "zz"):
        (kitchen / name).mkdir(parents=True)
    (kitchen / "en/README_EN.md").write_text("real locale\n", encoding="utf-8")
    observed = [p.relative_to(kitchen).as_posix() for p in locale_readme_paths(kitchen)]
    locale_probe = {"observed": observed, "required_missing_locale_retained": "zz/README_ZZ.md" in observed,
                    "dunder_incorrectly_counted": "__pycache__/README___PYCACHE__.md" in observed,
                    "cache_incorrectly_counted": ".translation-cache/README_.TRANSLATION-CACHE.md" in observed}

manifest = (ROOT / ".saipen/extensions/subs/MANIFEST.md").read_text(encoding="utf-8")
orphans = intake.recover_orphans(ROOT)
tracked_archive = subprocess.run(["git", "ls-files", "--", "CHANGELOG_ARCHIVE.md"], cwd=ROOT,
                                capture_output=True, text=True, encoding="utf-8", check=True).stdout.splitlines()
result = {"kind": "read-only-human-triage-preparation", "observed_at": datetime.now(timezone.utc).isoformat(),
          "files": {rel: hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() for rel in refs},
          "locale_probe": locale_probe,
          "translate_mirror_exists": (ROOT / ".saipen/extensions/subs/saitranslate").exists(),
          "translate_mirror_advertised": ".saipen/extensions/subs/saitranslate/" in manifest,
          "translate_canonical_state_exists": (ROOT / ".saipen/saitranslate/STATE.md").exists(),
          "src024_active_exists": (ROOT / ".saipen/intake/active/SRC-024.md").exists(),
          "src024_tombstone_exists": (ROOT / ".saipen/intake/tombstones/SRC-024.json").exists(),
          "current_orphan_receipts": [o["receipt"] for o in orphans.get("orphans", [])],
          "changelog_headings": sum(line.startswith("## ") for line in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()),
          "archive_tracked": tracked_archive == ["CHANGELOG_ARCHIVE.md"],
          "wiki_ready_exists": (ROOT / ".saipen/extensions/subs/saiwiki/READY").exists(),
          "approval": False, "completed_work": []}
wiki_ns = ROOT / ".saipen/extensions/subs/saiwiki"
packages, errors = producer.StagingGeneration.scan_ready(wiki_ns, materialize_payloads=False)
result["wiki_ready_valid_count"] = len(packages)
result["wiki_ready_error_count"] = len(errors)
result["wiki_ready_package_ids"] = [p.package_identity for p in packages]
(DEST / "current.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in result.items() if k not in {"files"}}, ensure_ascii=False))

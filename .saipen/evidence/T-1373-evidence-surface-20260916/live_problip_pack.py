"""SRC-054: pack the LIVE Problip through the live pipeline into a scratch dir.

The gate resolves Problip's own `saipen_home` (the scheduled-source install,
which still carries the pre-SRC-054 generator until it republishes), so this
measures what an operator's next pack produces today: the repaired consumer
reading an unrepaired contract. Output goes to --out, never to the operator's
audit directory, and Problip's protocol memory is hashed before and after.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path

PROBLIP = Path(r"V:\___VAC\__K\__CODE\_PY\_PROBLIP")
AUDAPACK = Path(r"V:\___VAC\__K\__CODE\_PY\_AUDAPACK")
CONFIG = Path(os.environ.get("LOCALAPPDATA", "")) / "AUDAPACK" / "config" / "config.json"
PROOF_REL = ".saipen/evidence/PERF-001_WINDOWS_EVIDENCE.md"


def digest(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file() and not p.is_symlink() and "locks" not in p.relative_to(root).parts
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(AUDAPACK))
    from audapack.config import PackingConfig
    from audapack.packing import MANIFEST_FILENAME, pack_single

    data = json.loads(CONFIG.read_text(encoding="utf-8")).get("packing", {})
    names = {f.name for f in dataclasses.fields(PackingConfig)}
    packing = PackingConfig(**{k: v for k, v in data.items() if k in names})
    packing.output_dir = str(args.out)
    packing.delete_old = False
    args.out.mkdir(parents=True, exist_ok=True)

    before = digest(PROBLIP / ".saipen")
    result = pack_single(
        source_path=PROBLIP,
        output_dir=args.out,
        archive_stem="_PROBLIP",
        excludes=set(packing.excludes),
        delete_old=False,
        include_timestamp=True,
        manifest_meta={"project_name": "_PROBLIP"},
        packing=packing,
    )
    after = digest(PROBLIP / ".saipen")
    print(f"pack success={result.success} error={result.error_message!r}")
    if not result.success:
        return 1
    with zipfile.ZipFile(result.output_path) as zf:
        members = set(zf.namelist())
        snapshot = json.loads(zf.read(MANIFEST_FILENAME))["saipen_snapshot"]
        contract = json.loads(zf.read(".saipen/MANIFEST.json"))
        proof = zf.read(PROOF_REL) if PROOF_REL in members else None
    source = (PROBLIP / PROOF_REL).read_bytes()
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    print(f"archive={Path(result.output_path).name} bytes={Path(result.output_path).stat().st_size}")
    print("contract conditional=" + ",".join(r["path"] for r in contract["evidence"]["conditional"])
          + f" references_declared={'references' in contract}")
    print(f"proof_in_zip={proof is not None} source_sha256={hashlib.sha256(source).hexdigest().upper()} "
          f"archive_sha256={hashlib.sha256(proof).hexdigest().upper() if proof else None}")
    print(f"status={snapshot['status']} authoritative={snapshot['authoritative_state']} "
          f"collected/in_archive={snapshot['evidence_files_collected']}/{snapshot['evidence_files_in_archive']} "
          f"required_evidence_omitted={snapshot['required_evidence_omitted']}")
    print("evidence_citations=" + json.dumps(snapshot["evidence_citations"]))
    print(f"problip .saipen files changed by the pack: {changed}")
    ok = proof == source and snapshot["status"] == "COMPLETE" and not snapshot["required_evidence_omitted"]
    print("RESULT " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

"""Read-only, hash-verified recovery inventory within this owned workspace."""
import hashlib
import json
import os
import stat
import subprocess
import time
from pathlib import Path

root = Path.cwd().resolve()
evidence = root / ".saipen/evidence/T-1829-cost-collapse"
missing = {
    line[1:].strip()
    for line in (evidence / "head-connectivity-before.txt").read_text().splitlines()
    if line.startswith("?")
}
if any(len(oid) != 40 or any(c not in "0123456789abcdef" for c in oid) for oid in missing):
    raise RuntimeError("Unsupported object identity")


def oid(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


control = root / "VERSION"
expected = subprocess.check_output(
    ["git", "hash-object", "--no-filters", str(control)], text=True
).strip()
if oid(control.read_bytes()) != expected:
    raise RuntimeError("Git blob instrument unavailable")

started = time.monotonic()
pending = [root]
matches = {}
files = total = skipped = 0
excluded = {".git", "__pycache__", ".ruff_cache", ".mypy_cache", ".pytest_cache"}
while pending:
    directory = pending.pop()
    try:
        children = list(os.scandir(directory))
    except OSError:
        skipped += 1
        continue
    for entry in children:
        try:
            info = entry.stat(follow_symlinks=False)
            if entry.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                skipped += 1
                continue
            if stat.S_ISDIR(info.st_mode):
                if entry.name not in excluded:
                    pending.append(Path(entry.path))
                continue
            if not stat.S_ISREG(info.st_mode) or info.st_size > 32 * 1024 * 1024:
                skipped += 1
                continue
            path = Path(entry.path)
            raw = path.read_bytes()
        except OSError:
            skipped += 1
            continue
        files += 1
        total += len(raw)
        variants = [("raw", raw)]
        if b"\0" not in raw:
            try:
                raw.decode("utf-8")
            except UnicodeError:
                pass
            else:
                lf = raw.replace(b"\r\n", b"\n")
                if lf != raw:
                    variants.append(("lf", lf))
                crlf = lf.replace(b"\n", b"\r\n")
                if crlf != raw:
                    variants.append(("crlf", crlf))
        for variant, content in variants:
            digest = oid(content)
            if digest in missing and digest not in matches:
                matches[digest] = {
                    "path": path.relative_to(root).as_posix(),
                    "variant": variant,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size": len(content),
                }

report = {
    "root": str(root),
    "positive_control": "PASS",
    "scope": "regular workspace files <=32 MiB; links and tool caches/Git directories excluded",
    "files": files,
    "bytes": total,
    "skipped": skipped,
    "duration_s": round(time.monotonic() - started, 3),
    "missing": len(missing),
    "recoverable_blobs": matches,
    "unmatched": sorted(missing - matches.keys()),
    "writes": "inventory only; no object, ref, index or source mutation",
}
(evidence / "local-blob-recovery-inventory.json").write_text(
    json.dumps(report, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps({key: value for key, value in report.items()
                  if key not in ("recoverable_blobs", "unmatched")}
                 | {"recoverable": len(matches), "unmatched": len(report["unmatched"])}))

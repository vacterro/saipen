"""AC-06 RED CONTROL: revert the fix, prove the new tests go red, restore it.
The revert/restore is done here in one process so the working tree cannot be
left holding the pre-fix code."""
import pathlib, subprocess, sys

live = pathlib.Path(".").resolve()
f = live/"tools"/"saipen_engine"/"conformance_lineage.py"
orig = f.read_text(encoding="utf-8")

FIXED_SCAN = """        content_sha256 = hashlib.sha256(raw).hexdigest()
        members.append(
            _member(
                _member_receipt_id(record, content_sha256),"""
PREFIX_SCAN = """        members.append(
            _member(
                record["receipt_id"],"""

FIXED_AUDIT = """            "receipt_id": _member_receipt_id(record, content_sha256),"""
PREFIX_AUDIT = """            "receipt_id": record["receipt_id"],"""

out = []
out.append(f"fix present in scan site : {FIXED_SCAN in orig}")
out.append(f"fix present in audit site: {FIXED_AUDIT in orig}")

pre = orig.replace(FIXED_SCAN, PREFIX_SCAN).replace(FIXED_AUDIT, PREFIX_AUDIT)
out.append(f"pre-fix text differs     : {pre != orig}")
f.write_text(pre, encoding="utf-8")
try:
    r = subprocess.run([sys.executable, "tools/test_t1283_lineage_legacy_ingest.py"],
                       cwd=live, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out.append(f"PRE-FIX exit code = {r.returncode}")
    tail = (r.stderr or "")[-2200:]
    out.append("PRE-FIX output tail:")
    out.append(tail)
finally:
    f.write_text(orig, encoding="utf-8")
    out.append(f"RESTORED: {f.read_text(encoding='utf-8') == orig}")

r2 = subprocess.run([sys.executable, "tools/test_t1283_lineage_legacy_ingest.py"],
                    cwd=live, capture_output=True, text=True, encoding="utf-8", errors="replace")
out.append(f"POST-FIX exit code = {r2.returncode}")
out.append((r2.stderr or "")[-300:])

(live/".git/redctl.txt").write_text("\n".join(out), encoding="utf-8")
print("ok")

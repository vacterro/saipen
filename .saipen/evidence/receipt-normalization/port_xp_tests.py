"""Port the original receipt-range oracle without overwriting current tests."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
old = (Path(__file__).parent / "test_source_receipts.py.xp.txt").read_text(encoding="utf-8")
node = next(n for n in ast.parse(old).body if isinstance(n, ast.ClassDef) and n.name == "ReceiptRangeNormalizationTests")
original = ast.get_source_segment(old, node)
target = ROOT / "tools/test_source_receipts.py"
current = target.read_text(encoding="utf-8")
assert "class ReceiptRangeNormalizationTests(" not in current
marker = 'if __name__ == "__main__":'
assert current.count(marker) == 1
target.write_text(current.replace(marker, original + "\n\n\n" + marker), encoding="utf-8", newline="")
print("Original XP ReceiptRangeNormalizationTests ported; existing classes preserved.")

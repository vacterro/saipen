"""Which widget test files name each ticket in a test title?"""
import pathlib
import re

IDS = ["T-34", "T-38", "T-56", "T-58", "T-62", "T-63", "T-64", "T-68", "T-70",
       "T-74", "T-75", "T-76", "T-77", "T-78", "T-79", "T-83", "T-85", "T-88",
       "T-89", "T-91", "T-94", "T-95", "T-111", "T-112", "T-130", "T-250"]

files = {p: p.read_text(encoding="utf-8", errors="replace")
         for p in sorted(pathlib.Path("tests/widget").glob("*.test.js"))}

for ticket in IDS:
    pat = re.compile(r"\b" + ticket + r"\b\s*[:\-]", re.I)
    hits = [p.name for p, text in files.items() if pat.search(text)]
    print(f"{ticket:6} {len(hits):2} {' '.join(hits[:5])}")
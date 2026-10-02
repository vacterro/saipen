"""T-1589 scout: compare evidence-script markers against same-named sources."""
import re
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
MARKER_RE = re.compile(r"ded-[0-9a-f]{8}")

for ev in sorted(ROOT.glob(".saipen/evidence/*/*.py")):
    marks = set(MARKER_RE.findall(ev.read_text(encoding="utf-8-sig")))
    if not marks:
        continue
    src = ROOT / "tools" / ev.name
    srcmarks = (
        set(MARKER_RE.findall(src.read_text(encoding="utf-8-sig"))) if src.is_file() else set()
    )
    print(f"{ev.parent.name}/{ev.name}")
    print(f"   evidence markers: {sorted(marks)}")
    print(f"   tools/{ev.name}:  {sorted(srcmarks)}")
    print(f"   novel markers:    {sorted(marks - srcmarks)}")

"""Read-only: which top-level usage alternatives are not dispatched verbs."""

import json
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / "tools"))
from saipen_engine import command_effects  # noqa: E402

proc = subprocess.run(
    [sys.executable, "-B", str(root / "tools" / "saipen.py"), "help", "--json"],
    capture_output=True, text=True, encoding="utf-8", cwd=str(root),
)
usage = json.loads(proc.stdout)["usage"]
body = usage[usage.index("(") + 1:]


def top_level(text: str) -> list[str]:
    parts, depth, current = [], 0, []
    for char in text:
        if char in "([":
            depth += 1
        elif char in ")]":
            if depth == 0:
                parts.append("".join(current))
                return parts
            depth -= 1
        if char == "|" and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    parts.append("".join(current))
    return parts


alternatives = [part.strip() for part in top_level(body) if part.strip()]
verbs = set(command_effects._VERBS)
missing = [alt for alt in alternatives if alt.split()[0] not in verbs]
print("alternatives", len(alternatives))
print("not a top-level verb:", missing)

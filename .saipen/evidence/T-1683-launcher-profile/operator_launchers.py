"""Read-only byte comparison of the three declared operator launcher artifacts."""

import hashlib
import json
import sys
from pathlib import Path

evidence = Path(__file__).resolve().parent
home = Path.home()
paths = (home / "bin" / "saipen.cmd", home / "bin" / "saipen",
         home / ".saipen" / "path-launcher.json")
hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
if sys.argv[1:] == ["before"]:
    (evidence / "operator-launcher-before.json").write_text(
        json.dumps(hashes, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps({"recorded": len(hashes)}))
else:
    before = json.loads((evidence / "operator-launcher-before.json").read_text())
    result = {"unchanged": hashes == before,
              "changed": [path for path in hashes if hashes[path] != before.get(path)]}
    (evidence / "operator-launcher-after.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps(result))
    sys.exit(0 if result["unchanged"] else 1)

"""Read-only, byte-stable consumer snapshot; never import the product or run fixtures."""
import ast
import hashlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
consumer = root.parent.parent / "__SAITULS"
evidence = Path(__file__).resolve().parent
names = [
    "Scripts/saispin_logic.py", "Scripts/saispin_watch.ps1",
    "Scripts/saispin_settings.ps1", "tests/test_saispin.py",
    "tests/test_saispin_settings.ps1", "tests/test_saispin_task.ps1",
    ".saipen/STATE.md", ".saipen/BOARD.md", ".saipen/LOG.md",
    ".saipen/intake/active/SRC-092.md", ".saipen/intake/active/SRC-092.meta.json",
]
content = {name: (consumer / name).read_bytes() for name in names}
if any((consumer / name).read_bytes() != blob for name, blob in content.items()):
    raise RuntimeError("consumer changed during snapshot; no snapshot written")
snapshot = evidence / "snapshot"
rows = []
for name, blob in content.items():
    target = snapshot / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(blob)
    rows.append({"path": name, "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()})
(evidence / "snapshot.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")

text = content["Scripts/saispin_logic.py"].decode("utf-8-sig")
tree = ast.parse(text)
selected = {"decide", "sweep", "classify_process", "evaluate_recovery_lease", "lease_directory", "lease_path_for"}
functions = []
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in selected:
        functions.append({"name": node.name, "start_line": node.lineno, "end_line": node.end_lineno,
                          "source": ast.get_source_segment(text, node)})
(evidence / "python-functions.json").write_text(json.dumps(functions, indent=2) + "\n", encoding="utf-8")
sys.path.insert(0, str(root / "tools"))
from saipen_engine.board import parse_board
board = parse_board(content[".saipen/BOARD.md"].decode("utf-8-sig"))
ticket_rows = [ticket for ticket in board["tickets"].values()
               if ticket["id"] in {"T-271", "T-273"}
               or any(term in str(ticket).lower() for term in ("saispin", "recovery lease", "kill safety"))]
(evidence / "consumer-work.json").write_text(json.dumps(ticket_rows, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"consumer": str(consumer), "files": rows, "functions": [
    {key: value for key, value in entry.items() if key != "source"} for entry in functions],
    "candidate_tickets": [{"id": t["id"], "section": t["section"]} for t in ticket_rows]}, indent=2))

"""Provisional, bounded lexical/static census while the owned gate is running."""
import ast
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NAMES = ("record_producer_integration", "_plan_producer_integration", "record_crew_run")
SUFFIXES = {".py", ".json", ".md", ".js", ".ts", ".ps1", ".sh", ".cmd"}
references = {name: [] for name in NAMES}
calls = {name: [] for name in NAMES}
errors, files = [], []
for scope in ("tools", "saipen", "extensions"):
    for path in sorted((ROOT / scope).rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUFFIXES:
            continue
        if any(part in {"__pycache__", "node_modules", ".git"} for part in path.parts):
            continue
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            errors.append({"file": rel, "error": str(exc)})
            continue
        files.append(rel)
        for number, line in enumerate(text.splitlines(), 1):
            for name in NAMES:
                if re.search(r"\b" + re.escape(name) + r"\b", line):
                    references[name].append({"file": rel, "line": number, "text": line.strip()})
        if path.suffix == ".py":
            try:
                tree = ast.parse(text)
            except SyntaxError as exc:
                errors.append({"file": rel, "error": str(exc)})
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    name = (node.func.id if isinstance(node.func, ast.Name)
                            else node.func.attr if isinstance(node.func, ast.Attribute) else None)
                    if name in calls:
                        calls[name].append({"file": rel, "line": node.lineno})
result = {"tier": "provisional bounded direct-source evidence; tools excluded from MCP",
          "scopes": ["tools", "saipen", "extensions"], "files_read": files,
          "references": references, "static_named_calls": calls, "errors": errors,
          "limits": "Does not prove absence of dynamic/external consumers or authorize removal; T-1725 remains queued review Work."}
(HERE / "census.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"files_read": len(files), "errors": len(errors),
                  "references": {k: len(v) for k, v in references.items()},
                  "static_named_calls": {k: len(v) for k, v in calls.items()}}))

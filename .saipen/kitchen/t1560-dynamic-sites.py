"""Read-only inventory of subprocess text flags not covered by literal True."""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
findings = []
for directory in ("tools", "extensions", "bootstrap"):
    for path in sorted((ROOT / directory).rglob("*.py")):
        if path.name.startswith("test_") or "tests" in path.relative_to(ROOT).parts:
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        modules = {"subprocess"}
        imported = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(a.asname or a.name for a in node.names if a.name == "subprocess")
            elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
                imported.update({a.asname or a.name: a.name for a in node.names})
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = None
            if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id in modules:
                name = fn.attr
            elif isinstance(fn, ast.Name):
                name = imported.get(fn.id)
            if name not in {"run", "Popen", "check_output", "check_call", "call"}:
                continue
            keywords = {k.arg: k for k in node.keywords}
            flags = [keywords[k] for k in ("text", "universal_newlines") if k in keywords]
            dynamic = any(not isinstance(k.value, ast.Constant) for k in flags)
            if dynamic or None in keywords:
                findings.append({"path": path.relative_to(ROOT).as_posix(), "line": node.lineno,
                                 "call": ast.get_source_segment(source, node)})
target = ROOT / ".saipen/evidence/T-1560-utf8-candidate/dynamic-sites.json"
target.write_text(json.dumps(findings, indent=2) + "\n", encoding="utf-8")
print(json.dumps(findings, indent=2))

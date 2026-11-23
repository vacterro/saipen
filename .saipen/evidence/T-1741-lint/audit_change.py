"""Prove this lint-only delta preserves executable AST and assertion arguments."""
import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FILES = ["saipen.py", "test_t1732_protocol_hardening.py", "test_t1734_source_drift.py",
         "test_t1735_tool_failure_boundaries.py", "test_t1736_tool_safety_and_evidence.py"]
REMOVED = {"test_t1732_protocol_hardening.py": {"os"},
           "test_t1735_tool_failure_boundaries.py": {"json"},
           "test_t1736_tool_safety_and_evidence.py": {"json", "os", "tempfile"}}


class Normalize(ast.NodeTransformer):
    def __init__(self, filename):
        self.filename = filename

    def visit_Import(self, node):
        node.names = [n for n in node.names if n.name not in REMOVED.get(self.filename, set())]
        return node if node.names else None

    def visit_ImportFrom(self, node):
        if self.filename == "test_t1732_protocol_hardening.py" and node.module == "saipen_engine":
            node.names = [n for n in node.names if n.name != "ownership"]
        return node

    def visit_Name(self, node):
        if self.filename == "test_t1736_tool_safety_and_evidence.py" and node.id == "msg":
            node.id = "_msg"
        return node

    def generic_visit(self, node):
        node = super().generic_visit(node)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.body and isinstance(node.body[0], ast.Expr):
                value = node.body[0].value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    node.body = node.body[1:]
        return node


records = []
for filename in FILES:
    before = (HERE / "pre" / filename).read_bytes()
    after = (ROOT / "tools" / filename).read_bytes()
    normalized = []
    assertions = []
    for raw in (before, after):
        tree = Normalize(filename).visit(ast.parse(raw.decode("utf-8-sig")))
        normalized.append(ast.dump(tree, include_attributes=False))
        assertions.append([ast.dump(n, include_attributes=False) for n in ast.walk(tree)
                           if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                           and n.func.attr.startswith("assert")])
    assert normalized[0] == normalized[1], f"executable AST changed in {filename}"
    assert assertions[0] == assertions[1], f"assertions changed in {filename}"
    records.append({"file": "tools/" + filename, "before_sha256": hashlib.sha256(before).hexdigest(),
                    "after_sha256": hashlib.sha256(after).hexdigest(),
                    "normalized_ast_equal": True, "assertions_equal": True})
(HERE / "ast-audit.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"files": len(records), "executable_ast_equal": True, "assertions_equal": True,
                  "normalization": "docstrings, six unused imports and two unused tuple bindings only"}))
